"""yf_curve — Yahoo Finance futures curve via yfinance (spec §4 #3). Cadence: daily.

No key; unofficial source, so every row carries ``indicative=True`` (§4 labelling
rule). Registry (verified 2026-07-18, yfinance 1.5.1):

- Continuous front months: CL=F, BZ=F, RB=F, HO=F. RB/HO quote in **$/gal**
  (crack-spread inputs) — columns are named per unit, never mixed.
- Dated strip: ROOT+monthCode+YY+".NYM" (CLZ26.NYM verified live; 4-digit year
  and bare forms 404). Contract codes are computed *deterministically* from a
  caller-supplied ``asof`` date — no hidden "now".
- Unknown tickers raise ``KeyError`` from ``fast_info`` (not a clean 404) —
  fetch catches broadly and raises ``SourceUnavailable``.

Two tables:

- ``yf_front_months`` — settle/last + prev close for the four continuous roots.
- ``yf_curve_strip``  — dated CL M1..M12 with month_index, contract, expiry,
  settle_usd_bbl.

Degradation (§4 #3, the ONLY sanctioned one): if the dated strip fails but the
front months fetch works, ``run()`` persists front months only — still labelled
indicative — and logs the degradation loudly. A front-month failure raises.

Expiry is the CME CL last-trade rule (3 business days before the 25th of the
month prior to delivery; 4 if the 25th falls on a weekend), computed with
weekday-only business days — exchange holidays are ignored, a documented
±1-day approximation near expiry.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import LedgerEntry
from erda_ingestion.base import FetchResult, run_connector

logger = logging.getLogger(__name__)

SOURCE_ID = "yf_curve"
TRANSFORM_VERSION = "yf_curve:1.0.0"
TABLE_FRONT_MONTHS = "yf_front_months"
TABLE_CURVE_STRIP = "yf_curve_strip"

SOURCE_URL = "https://finance.yahoo.com"

#: ticker → (commodity, unit). RB/HO are $/gal — never label them $/bbl.
FRONT_TICKERS: dict[str, tuple[str, str]] = {
    "CL=F": ("wti", "usd_bbl"),
    "BZ=F": ("brent", "usd_bbl"),
    "RB=F": ("rbob_gasoline", "usd_gal"),
    "HO=F": ("heating_oil", "usd_gal"),
}

#: CME futures month codes, January..December.
MONTH_CODES = "FGHJKMNQUVXZ"

CONTRACT_PATTERN = r"^CL[FGHJKMNQUVXZ]\d{2}\.NYM$"

FRONT_SCHEMA = pa.DataFrameSchema(
    {
        "asof_date": pa.Column(pa.DateTime, nullable=False),
        "ticker": pa.Column(str, pa.Check.isin(list(FRONT_TICKERS)), nullable=False),
        "commodity": pa.Column(
            str,
            pa.Check.isin([commodity for commodity, _ in FRONT_TICKERS.values()]),
            nullable=False,
        ),
        "settle_usd_bbl": pa.Column(float, pa.Check.gt(0), nullable=True),
        "settle_usd_gal": pa.Column(float, pa.Check.gt(0), nullable=True),
        "prev_close_usd_bbl": pa.Column(float, pa.Check.gt(0), nullable=True),
        "prev_close_usd_gal": pa.Column(float, pa.Check.gt(0), nullable=True),
        "indicative": pa.Column(bool, pa.Check.eq(True), nullable=False),
    },
    checks=pa.Check(
        lambda df: df["settle_usd_bbl"].notna() != df["settle_usd_gal"].notna(),
        name="settle_in_exactly_one_unit",
        error="each row must carry a settle in exactly one unit column",
    ),
    unique=["asof_date", "ticker"],
)

STRIP_SCHEMA = pa.DataFrameSchema(
    {
        "asof_date": pa.Column(pa.DateTime, nullable=False),
        "month_index": pa.Column(int, pa.Check.in_range(1, 12), nullable=False),
        "contract": pa.Column(str, pa.Check.str_matches(CONTRACT_PATTERN), nullable=False),
        "expiry": pa.Column(pa.DateTime, nullable=False),
        "settle_usd_bbl": pa.Column(float, pa.Check.gt(0), nullable=False),
        "indicative": pa.Column(bool, pa.Check.eq(True), nullable=False),
    },
    checks=pa.Check(
        lambda df: bool(
            df.sort_values("month_index")
            .groupby("asof_date")["expiry"]
            .apply(lambda s: s.is_monotonic_increasing)
            .all()
        ),
        name="expiry_monotonic_along_curve",
        error="expiry must increase with month_index within an asof batch",
    ),
    unique=["asof_date", "contract"],
)


@dataclass(frozen=True)
class StripContract:
    month_index: int  # 1 = front month
    contract: str  # e.g. "CLQ26.NYM"
    delivery_month: dt.date  # first day of the delivery month
    expiry: dt.date  # last trade date (weekday-only CME rule approximation)


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def cl_last_trade_date(delivery_year: int, delivery_month: int) -> dt.date:
    """CME CL last trade: 3 business days before the 25th of the month prior to
    delivery; 4 business days if the 25th is not a business day. Business days
    are weekdays only (exchange holidays ignored — documented approximation)."""
    prior_year, prior_month = (
        (delivery_year - 1, 12) if delivery_month == 1 else (delivery_year, delivery_month - 1)
    )
    the_25th = dt.date(prior_year, prior_month, 25)
    steps = 3 if the_25th.weekday() < 5 else 4
    day = the_25th
    while steps:
        day -= dt.timedelta(days=1)
        if day.weekday() < 5:
            steps -= 1
    return day


def strip_contracts(asof: dt.date, months: int = 12) -> list[StripContract]:
    """Dated CL contracts M1..M{months} as of ``asof``, deterministically.

    M1 is the nearest delivery month still trading on ``asof`` (its last trade
    date has not passed). Codes follow the live-verified ROOT+monthCode+YY+.NYM
    format.
    """
    if months < 1:
        raise ValueError("months must be >= 1")
    year, month = _next_month(asof.year, asof.month)
    while cl_last_trade_date(year, month) < asof:
        year, month = _next_month(year, month)
    out: list[StripContract] = []
    for i in range(1, months + 1):
        code = f"CL{MONTH_CODES[month - 1]}{year % 100:02d}.NYM"
        out.append(
            StripContract(
                month_index=i,
                contract=code,
                delivery_month=dt.date(year, month, 1),
                expiry=cl_last_trade_date(year, month),
            )
        )
        year, month = _next_month(year, month)
    return out


def _quote_float(value: object, field: str, ticker: str) -> float:
    """None → NaN (missing stays missing); non-numeric junk fails loudly."""
    if value is None:
        return float("nan")
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ContractViolation(SOURCE_ID, f"{ticker} {field} non-numeric: {value!r}") from exc


def _check_usd(quote: Mapping[str, object], ticker: str) -> None:
    currency = quote.get("currency")
    if currency is not None and currency != "USD":
        raise ContractViolation(SOURCE_ID, f"{ticker} quoted in {currency!r}, expected USD")


def normalize_front_months(
    quotes: Mapping[str, Mapping[str, object]], asof: dt.date
) -> pd.DataFrame:
    """fast_info quotes for CL=F/BZ=F/RB=F/HO=F → tidy frame, one row per ticker.

    Settle/prev-close land in the column matching the ticker's unit ($/bbl for
    CL/BZ, $/gal for RB/HO); the other unit's column stays NaN. A missing ticker
    or non-USD quote raises — no partial front-month table is ever produced.
    """
    rows = []
    for ticker, (commodity, unit) in FRONT_TICKERS.items():
        quote = quotes.get(ticker)
        if quote is None:
            raise ContractViolation(SOURCE_ID, f"front-month quote missing for {ticker}")
        _check_usd(quote, ticker)
        settle = _quote_float(quote.get("last_price"), "last_price", ticker)
        prev = _quote_float(quote.get("previous_close"), "previous_close", ticker)
        bbl = unit == "usd_bbl"
        rows.append(
            {
                "asof_date": pd.Timestamp(asof),
                "ticker": ticker,
                "commodity": commodity,
                "settle_usd_bbl": settle if bbl else float("nan"),
                "settle_usd_gal": settle if not bbl else float("nan"),
                "prev_close_usd_bbl": prev if bbl else float("nan"),
                "prev_close_usd_gal": prev if not bbl else float("nan"),
                "indicative": True,  # unofficial source, always (§4)
            }
        )
    return pd.DataFrame(rows)


def normalize_curve_strip(
    quotes: Mapping[str, Mapping[str, object]], asof: dt.date, months: int = 12
) -> pd.DataFrame:
    """Dated-CL quotes → M1..M{months} strip frame, sorted by month_index.

    Contracts are recomputed from ``asof`` so the frame is a pure function of
    (quotes, asof). A hole in the strip (missing contract quote) raises — a
    curve with silent gaps is worse than no curve (§0 rule 4).
    """
    rows = []
    for c in strip_contracts(asof, months):
        quote = quotes.get(c.contract)
        if quote is None:
            raise ContractViolation(
                SOURCE_ID, f"strip quote missing for {c.contract} (M{c.month_index})"
            )
        _check_usd(quote, c.contract)
        rows.append(
            {
                "asof_date": pd.Timestamp(asof),
                "month_index": c.month_index,
                "contract": c.contract,
                "expiry": pd.Timestamp(c.expiry),
                "settle_usd_bbl": _quote_float(quote.get("last_price"), "last_price", c.contract),
                "indicative": True,  # unofficial source, always (§4)
            }
        )
    return pd.DataFrame(rows)


def _fast_quote(ticker: str) -> dict[str, object]:
    """One fast_info snapshot. Registry: unknown tickers raise KeyError (e.g.
    'exchangeTimezoneName'), not a clean 404 — so catch broadly."""
    import yfinance as yf

    try:
        info = yf.Ticker(ticker).fast_info
        return {
            "last_price": info["last_price"],
            "previous_close": info["previous_close"],
            "currency": info["currency"],
        }
    except Exception as exc:
        raise SourceUnavailable(SOURCE_ID, f"fast_info failed for {ticker}: {exc!r}") from exc


def fetch_front_months(asof: dt.date) -> FetchResult:
    quotes = {ticker: _fast_quote(ticker) for ticker in FRONT_TICKERS}
    return FetchResult(frame=normalize_front_months(quotes, asof), source_url=SOURCE_URL)


def fetch_curve_strip(asof: dt.date, months: int = 12) -> FetchResult:
    contracts = strip_contracts(asof, months)
    quotes = {c.contract: _fast_quote(c.contract) for c in contracts}
    return FetchResult(frame=normalize_curve_strip(quotes, asof, months), source_url=SOURCE_URL)


def run(root: Path, asof: dt.date, months: int = 12) -> dict[str, LedgerEntry]:
    """Persist both tables via run_connector. ``asof`` is caller-supplied.

    Front months failing → raise (no data, no invention). Strip failing after
    front months succeeded → §4 #3 sanctioned degradation: front-month-only,
    already labelled indicative, logged loudly. No other fallback exists.
    """
    entries: dict[str, LedgerEntry] = {}
    entries[TABLE_FRONT_MONTHS] = run_connector(
        source_id=SOURCE_ID,
        transform_version=TRANSFORM_VERSION,
        schema=FRONT_SCHEMA,
        fetch=lambda: fetch_front_months(asof),
        table=TABLE_FRONT_MONTHS,
        root=root,
    )
    try:
        entries[TABLE_CURVE_STRIP] = run_connector(
            source_id=SOURCE_ID,
            transform_version=TRANSFORM_VERSION,
            schema=STRIP_SCHEMA,
            fetch=lambda: fetch_curve_strip(asof, months),
            table=TABLE_CURVE_STRIP,
            root=root,
        )
    except (SourceUnavailable, ContractViolation) as exc:
        logger.warning(
            "[%s] dated strip failed; degrading to front-month-only per spec §4 #3 "
            "(indicative already labelled): %s",
            SOURCE_ID,
            exc,
        )
    return entries
