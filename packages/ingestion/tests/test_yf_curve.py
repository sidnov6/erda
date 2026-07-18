"""yf_curve tests — OFFLINE ONLY. Fixture is real fast_info output recorded from
https://finance.yahoo.com on 2026-07-18 (see fixtures/yf_curve_fast_info_sample.json);
no test touches the network."""

import datetime as dt
import json
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import read_ledger
from erda_ingestion import yf_curve
from erda_ingestion.base import FetchResult, run_connector

FIXTURE = Path(__file__).parent / "fixtures" / "yf_curve_fast_info_sample.json"
ASOF = dt.date(2026, 7, 18)  # fixture recording date

EXPECTED_STRIP = [
    "CLQ26.NYM",
    "CLU26.NYM",
    "CLV26.NYM",
    "CLX26.NYM",
    "CLZ26.NYM",
    "CLF27.NYM",
    "CLG27.NYM",
    "CLH27.NYM",
    "CLJ27.NYM",
    "CLK27.NYM",
    "CLM27.NYM",
    "CLN27.NYM",
]


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text())


# --- deterministic contract-code computation -------------------------------


def test_strip_contracts_asof_recording_date():
    contracts = yf_curve.strip_contracts(ASOF)
    assert [c.contract for c in contracts] == EXPECTED_STRIP  # all 12 resolved live
    assert [c.month_index for c in contracts] == list(range(1, 13))
    # CLQ26 last trade: 25 Jul 2026 is a Saturday → 4 business days back → Tue 21 Jul
    assert contracts[0].expiry == dt.date(2026, 7, 21)
    assert contracts[0].delivery_month == dt.date(2026, 8, 1)


def test_strip_contracts_rolls_front_month_after_expiry():
    # 2026-07-22 is past CLQ26's last trade (2026-07-21) → front month is CLU26
    contracts = yf_curve.strip_contracts(dt.date(2026, 7, 22))
    assert contracts[0].contract == "CLU26.NYM"
    assert contracts[0].expiry == dt.date(2026, 8, 20)


def test_strip_contracts_year_rollover():
    # Jan-27 delivery stops trading 2026-12-22; on 12-28 the front month is Feb-27
    contracts = yf_curve.strip_contracts(dt.date(2026, 12, 28))
    assert contracts[0].contract == "CLG27.NYM"
    assert contracts[-1].contract == "CLF28.NYM"  # M12 wraps into 2028


def test_strip_contracts_rejects_bad_months():
    with pytest.raises(ValueError):
        yf_curve.strip_contracts(ASOF, months=0)


# --- normalize: front months ------------------------------------------------


def test_normalize_front_months_units_and_labels():
    df = yf_curve.normalize_front_months(_fixture()["front"], ASOF)
    assert len(df) == 4
    by = df.set_index("ticker")
    # CL/BZ are $/bbl; the $/gal columns stay NaN
    assert by.loc["CL=F", "settle_usd_bbl"] == pytest.approx(82.49, abs=0.01)
    assert pd.isna(by.loc["CL=F", "settle_usd_gal"])
    assert by.loc["BZ=F", "prev_close_usd_bbl"] == pytest.approx(85.05, abs=0.01)
    # RB/HO are $/gal (crack-spread inputs); the $/bbl columns stay NaN
    assert by.loc["RB=F", "settle_usd_gal"] == pytest.approx(3.3927, abs=0.001)
    assert pd.isna(by.loc["RB=F", "settle_usd_bbl"])
    assert by.loc["HO=F", "prev_close_usd_gal"] == pytest.approx(3.9552, abs=0.001)
    # unofficial source → indicative on every row (§4)
    assert df["indicative"].all() and df["indicative"].dtype == bool
    assert pd.api.types.is_datetime64_any_dtype(df["asof_date"])


def test_normalize_front_months_missing_ticker_raises():
    quotes = _fixture()["front"]
    del quotes["HO=F"]
    with pytest.raises(ContractViolation, match="HO=F"):
        yf_curve.normalize_front_months(quotes, ASOF)


def test_normalize_front_months_non_usd_raises():
    quotes = _fixture()["front"]
    quotes["CL=F"]["currency"] = "EUR"
    with pytest.raises(ContractViolation, match="EUR"):
        yf_curve.normalize_front_months(quotes, ASOF)


def test_normalize_front_months_null_prev_close_kept_as_nan():
    quotes = _fixture()["front"]
    quotes["RB=F"]["previous_close"] = None  # missing stays missing, never imputed
    df = yf_curve.normalize_front_months(quotes, ASOF)
    row = df.set_index("ticker").loc["RB=F"]
    assert pd.isna(row["prev_close_usd_gal"])
    assert row["settle_usd_gal"] == pytest.approx(3.3927, abs=0.001)


# --- normalize: dated strip -------------------------------------------------


def test_normalize_curve_strip_shape_and_order():
    df = yf_curve.normalize_curve_strip(_fixture()["strip"], ASOF)
    assert len(df) == 12
    assert df["month_index"].tolist() == list(range(1, 13))
    assert df["contract"].tolist() == EXPECTED_STRIP
    assert df["expiry"].is_monotonic_increasing
    assert df["settle_usd_bbl"].iloc[0] == pytest.approx(82.49, abs=0.01)
    assert df["settle_usd_bbl"].iloc[-1] == pytest.approx(72.52, abs=0.01)
    assert df["indicative"].all()


def test_normalize_curve_strip_missing_contract_raises():
    quotes = _fixture()["strip"]
    del quotes["CLZ26.NYM"]  # a hole in the curve is never papered over
    with pytest.raises(ContractViolation, match="CLZ26.NYM"):
        yf_curve.normalize_curve_strip(quotes, ASOF)


def test_normalize_non_numeric_price_raises():
    quotes = _fixture()["strip"]
    quotes["CLQ26.NYM"]["last_price"] = "n/a"
    with pytest.raises(ContractViolation, match="non-numeric"):
        yf_curve.normalize_curve_strip(quotes, ASOF)


# --- fetch failure path (registry: fast_info raises KeyError, catch broadly) --


def test_fetch_maps_fast_info_keyerror_to_source_unavailable(monkeypatch):
    class FakeFastInfo:
        def __getitem__(self, key):
            raise KeyError("exchangeTimezoneName")  # observed live 2026-07-18

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def fast_info(self):
            return FakeFastInfo()

    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=FakeTicker))
    with pytest.raises(SourceUnavailable, match="fast_info failed"):
        yf_curve.fetch_front_months(ASOF)
    with pytest.raises(SourceUnavailable, match="fast_info failed"):
        yf_curve.fetch_curve_strip(ASOF)


# --- run_connector integration (fake fetch, tmp_path) ------------------------


def test_runner_front_months_full_path(tmp_path):
    frame = yf_curve.normalize_front_months(_fixture()["front"], ASOF)

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=yf_curve.SOURCE_URL)

    entry = run_connector(
        source_id=yf_curve.SOURCE_ID,
        transform_version=yf_curve.TRANSFORM_VERSION,
        schema=yf_curve.FRONT_SCHEMA,
        fetch=fake_fetch,
        table=yf_curve.TABLE_FRONT_MONTHS,
        root=tmp_path,
    )
    assert entry.rows == 4
    written = pd.read_parquet(tmp_path / "yf_front_months.parquet")
    for col in ["source_id", "retrieved_at", "source_url", "transform_version"]:
        assert col in written.columns
    assert (written["source_id"] == "yf_curve").all()
    assert written["indicative"].all()
    assert read_ledger(tmp_path)[0].table == "yf_front_months"


def test_runner_strip_full_path(tmp_path):
    frame = yf_curve.normalize_curve_strip(_fixture()["strip"], ASOF)

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=frame, source_url=yf_curve.SOURCE_URL)

    entry = run_connector(
        source_id=yf_curve.SOURCE_ID,
        transform_version=yf_curve.TRANSFORM_VERSION,
        schema=yf_curve.STRIP_SCHEMA,
        fetch=fake_fetch,
        table=yf_curve.TABLE_CURVE_STRIP,
        root=tmp_path,
    )
    assert entry.rows == 12
    written = pd.read_parquet(tmp_path / "yf_curve_strip.parquet")
    assert written["month_index"].tolist() == list(range(1, 13))
    assert (written["transform_version"] == "yf_curve:1.0.0").all()


def test_runner_rejects_negative_settle(tmp_path):
    bad = yf_curve.normalize_curve_strip(_fixture()["strip"], ASOF)
    bad.loc[0, "settle_usd_bbl"] = -1.0

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=yf_curve.SOURCE_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=yf_curve.SOURCE_ID,
            transform_version=yf_curve.TRANSFORM_VERSION,
            schema=yf_curve.STRIP_SCHEMA,
            fetch=fake_fetch,
            table=yf_curve.TABLE_CURVE_STRIP,
            root=tmp_path,
        )
    assert read_ledger(tmp_path) == []  # nothing persisted


def test_runner_rejects_indicative_false(tmp_path):
    bad = yf_curve.normalize_front_months(_fixture()["front"], ASOF)
    bad["indicative"] = False  # unofficial data must stay labelled (§4)

    def fake_fetch() -> FetchResult:
        return FetchResult(frame=bad, source_url=yf_curve.SOURCE_URL)

    with pytest.raises(ContractViolation):
        run_connector(
            source_id=yf_curve.SOURCE_ID,
            transform_version=yf_curve.TRANSFORM_VERSION,
            schema=yf_curve.FRONT_SCHEMA,
            fetch=fake_fetch,
            table=yf_curve.TABLE_FRONT_MONTHS,
            root=tmp_path,
        )


# --- run(): spec §4 #3 degradation ------------------------------------------


def test_run_degrades_to_front_month_only_when_strip_fails(tmp_path, monkeypatch, caplog):
    front_frame = yf_curve.normalize_front_months(_fixture()["front"], ASOF)
    monkeypatch.setattr(
        yf_curve,
        "fetch_front_months",
        lambda asof: FetchResult(frame=front_frame, source_url=yf_curve.SOURCE_URL),
    )

    def broken_strip(asof, months=12):
        raise SourceUnavailable(yf_curve.SOURCE_ID, "fast_info failed for CLQ26.NYM")

    monkeypatch.setattr(yf_curve, "fetch_curve_strip", broken_strip)

    with caplog.at_level("WARNING"):
        entries = yf_curve.run(tmp_path, ASOF)

    assert set(entries) == {yf_curve.TABLE_FRONT_MONTHS}  # strip absent, not invented
    assert (tmp_path / "yf_front_months.parquet").exists()
    assert not (tmp_path / "yf_curve_strip.parquet").exists()
    assert "degrading to front-month-only" in caplog.text  # loud, labelled (§4 #3)
    assert len(read_ledger(tmp_path)) == 1


def test_run_raises_when_front_months_fail(tmp_path, monkeypatch):
    def broken_front(asof):
        raise SourceUnavailable(yf_curve.SOURCE_ID, "fast_info failed for CL=F")

    monkeypatch.setattr(yf_curve, "fetch_front_months", broken_front)
    with pytest.raises(SourceUnavailable):
        yf_curve.run(tmp_path, ASOF)
    assert read_ledger(tmp_path) == []  # no degradation path for front months


def test_run_writes_both_tables_when_all_succeeds(tmp_path, monkeypatch):
    fixture = _fixture()
    monkeypatch.setattr(
        yf_curve,
        "fetch_front_months",
        lambda asof: FetchResult(
            frame=yf_curve.normalize_front_months(fixture["front"], asof),
            source_url=yf_curve.SOURCE_URL,
        ),
    )
    monkeypatch.setattr(
        yf_curve,
        "fetch_curve_strip",
        lambda asof, months=12: FetchResult(
            frame=yf_curve.normalize_curve_strip(fixture["strip"], asof, months),
            source_url=yf_curve.SOURCE_URL,
        ),
    )
    entries = yf_curve.run(tmp_path, ASOF)
    assert set(entries) == {yf_curve.TABLE_FRONT_MONTHS, yf_curve.TABLE_CURVE_STRIP}
    assert entries[yf_curve.TABLE_CURVE_STRIP].rows == 12
    tables = {e.table for e in read_ledger(tmp_path)}
    assert tables == {"yf_front_months", "yf_curve_strip"}
