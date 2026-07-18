"""opec — OPEC MOMR crude oil production by secondary sources (spec §4). Cadence: monthly.

Monthly Oil Market Report PDF, no key. Registry (verified 2026-07-18):

- Assets at https://www.opec.org/assets/assetdb/momr-{month}-{yyyy}.pdf (lowercase
  month), *prior* months only — the current month is gated behind momr.opec.org
  until the next release. Filenames are occasionally irregular ("…-1.pdf",
  abbreviated months) — we try candidate URLs and raise SourceUnavailable when all
  miss; we never guess numbers.
- HTML pages are Cloudflare-blocked to non-browser clients; asset downloads work
  with a browser UA (base.http_get sends one). A blocked interstitial would be
  HTML, so any body not starting with %PDF is treated as a miss.

Extraction (pdfplumber) is marked ``extraction="semi_automated"`` on every row, as
spec §4 requires for MOMR table scraping.

Drift sensitivity, load-bearing:

- PAGE NUMBER DRIFTS between issues (June 2026: page 66 of 98). The table is
  located by searching page text for the title phrase "crude oil production based
  on secondary sources" — never by a hardcoded page index.
- TITLE DRIFT: the table is now "DoC crude oil production based on secondary
  sources" (was "OPEC crude oil production based on …"); the invariant suffix is
  what we match. The DoC table appends non-OPEC DoC producers below a "Total
  OPEC" row — we keep only the OPEC-member block above that row.
- The adjacent "… based on direct communication" table (same page in June 2026)
  must NOT match; the title regex anchors on "secondary sources".
- Sentinels: ".." = not available (per MOMR table notes), "-" = blank; both are
  dropped, never imputed. Trailing "*" footnote markers are stripped. Values are
  comma-grouped integers in tb/d (thousand barrels/day == kb/d).
"""

from __future__ import annotations

import calendar
import io
import re
from datetime import UTC, datetime

import pandas as pd
import pandera.pandas as pa
import pdfplumber

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_ingestion.base import FetchResult, http_get

SOURCE_ID = "opec"
TRANSFORM_VERSION = "opec:1.0.0"
TABLE = "opec_production"

ASSET_BASE = "https://www.opec.org/assets/assetdb/"

SCHEMA = pa.DataFrameSchema(
    {
        "country": pa.Column(
            str,
            pa.Check(lambda s: ~s.str.startswith("Total"), name="no_aggregate_rows"),
            nullable=False,
        ),
        "month": pa.Column(pa.DateTime, nullable=False),
        "production_kbd": pa.Column(float, pa.Check.ge(0), nullable=False),
        # §4: MOMR table scraping is flagged, so panels can badge it.
        "extraction": pa.Column(str, pa.Check.eq("semi_automated"), nullable=False),
    },
    unique=["country", "month"],
)

_TITLE_RE = re.compile(r"crude oil production based on secondary sources", re.IGNORECASE)
#: Column labels on the table's header line, in visual order.
_COLUMN_TOKEN_RE = re.compile(
    r"(?P<month>[A-Z][a-z]{2} \d{2}\b)"
    r"|(?P<quarter>[1-4]Q\d{2}\b)"
    r"|(?P<year>\b(?:19|20)\d{2}\b)"
    r"|(?P<change>[A-Z][a-z]{2}/[A-Z][a-z]{2}\b)"
)
_VALUE_RE = re.compile(r"^(?:-?\d[\d,]*(?:\.\d+)?\*?|\.\.|-)$")
_COUNTRY_RE = re.compile(r"^[A-Za-z][A-Za-z .'\-]*$")
#: Independent rounding across ~12 member rows (MOMR notes) is at most ±0.5 tb/d
#: each; a mismatch beyond this means we mis-parsed the table.
_TOTAL_TOLERANCE_KBD = 15.0
_MIN_MEMBER_ROWS = 8


def _clean_value(token: str) -> float | None:
    """One table cell → float kb/d, or None for the documented sentinels."""
    token = token.rstrip("*")  # footnote marker (e.g. Saudi supply-vs-production note)
    if token in {"", "-", "..", "na"}:
        return None
    return float(token.replace(",", ""))


def _table_page_text(pdf_bytes: bytes) -> str:
    """Text of the page holding the secondary-sources table (title search, not index)."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if _TITLE_RE.search(text):
                return text
    raise ContractViolation(
        SOURCE_ID, "no page titled '… crude oil production based on secondary sources'"
    )


def normalize(pdf_bytes: bytes) -> pd.DataFrame:
    """MOMR PDF bytes → tidy OPEC-member monthly production. Pure; no I/O.

    Keeps only the monthly columns (annual/quarterly averages and the m-o-m
    change column are derivable, not observations) and only rows above "Total
    OPEC". Raises ContractViolation when the table cannot be located or the
    parsed members fail the Total-OPEC sum cross-check.
    """
    lines = _table_page_text(pdf_bytes).splitlines()
    title_idx = next(i for i, line in enumerate(lines) if _TITLE_RE.search(line))

    label_idx: int | None = None
    for i in range(title_idx + 1, min(title_idx + 8, len(lines))):
        matches = list(_COLUMN_TOKEN_RE.finditer(lines[i]))
        if sum(m.lastgroup == "month" for m in matches) >= 2:
            label_idx, labels = i, matches
            break
    if label_idx is None:
        raise ContractViolation(SOURCE_ID, "table header with monthly columns not found")

    n_cols = len(labels)
    month_cols = {
        i: pd.Timestamp(datetime.strptime(m.group("month"), "%b %y"))
        for i, m in enumerate(labels)
        if m.lastgroup == "month"
    }

    records: list[dict] = []
    countries: list[str] = []
    totals: list[str] | None = None
    for raw in lines[label_idx + 1 :]:
        line = raw.strip()
        if line.startswith("Total OPEC"):
            parts = line.split()
            if len(parts) >= n_cols + 2:
                totals = parts[-n_cols:]
            break
        if line.startswith(("Total", "Notes", "Source", "Table")):
            break  # ran past the OPEC block without seeing Total OPEC — stop, don't absorb
        parts = line.split()
        if len(parts) < n_cols + 1:
            continue
        values, country = parts[-n_cols:], " ".join(parts[:-n_cols])
        if not _COUNTRY_RE.match(country) or not all(_VALUE_RE.match(v) for v in values):
            continue
        countries.append(country)
        for i, month in month_cols.items():
            value = _clean_value(values[i])
            if value is None:
                continue  # ".."/"-" = not available per MOMR notes — dropped, never imputed
            records.append({"country": country, "month": month, "production_kbd": value})

    if len(countries) < _MIN_MEMBER_ROWS:
        raise ContractViolation(
            SOURCE_ID, f"only {len(countries)} member rows parsed — table layout drifted?"
        )
    df = pd.DataFrame(records)
    if df.empty:
        raise ContractViolation(SOURCE_ID, "no monthly observations parsed from table")

    if totals is not None:
        for i, month in month_cols.items():
            total = _clean_value(totals[i])
            got = df.loc[df["month"] == month, "production_kbd"]
            if total is None or len(got) < len(countries):
                continue  # total unavailable, or a member was ".." — sum check not meaningful
            if abs(got.sum() - total) > _TOTAL_TOLERANCE_KBD:
                raise ContractViolation(
                    SOURCE_ID,
                    f"member sum {got.sum():.0f} vs Total OPEC {total:.0f} "
                    f"for {month:%b %Y} — column misalignment?",
                )

    df["extraction"] = "semi_automated"
    df = df.sort_values(["month", "country"]).reset_index(drop=True)
    return df[["country", "month", "production_kbd", "extraction"]]


def candidate_urls(month_name: str, year: int) -> list[str]:
    """Candidate MOMR asset URLs for one issue, canonical filename first.

    Registry: filenames are occasionally irregular — "…-1.pdf" suffix and
    abbreviated month names have both been observed. Try, never assume.
    """
    month_name = month_name.lower()
    stems = [f"momr-{month_name}-{year}"]
    if month_name[:3] != month_name:
        stems.append(f"momr-{month_name[:3]}-{year}")
    return [f"{ASSET_BASE}{stem}{suffix}.pdf" for stem in stems for suffix in ("", "-1")]


def _recent_months(lookback: int) -> list[tuple[str, int]]:
    """(month_name, year) going back from LAST month — current issue is gated."""
    now = datetime.now(UTC)
    year, month, out = now.year, now.month, []
    for _ in range(lookback):
        month -= 1
        if month == 0:
            month, year = 12, year - 1
        out.append((calendar.month_name[month].lower(), year))
    return out


def fetch(
    month_name: str | None = None, year: int | None = None, lookback: int = 3
) -> FetchResult:
    """Latest open MOMR (or an explicit issue) → normalized frame.

    Probes candidates with retries=1 — a 404 on a guessed filename is a miss to
    move past, not an outage to back off from. A candidate that downloads but is
    not a PDF (Cloudflare interstitial) is also a miss. A PDF that downloads but
    fails to parse raises ContractViolation loudly — falling back to an older
    issue would be a silent staleness fallback the spec does not sanction.
    All candidates missing → SourceUnavailable. Never invented data (§0 rule 4).
    """
    if month_name is not None:
        targets = [(month_name.lower(), year or datetime.now(UTC).year)]
    else:
        targets = _recent_months(lookback)

    tried: list[str] = []
    for name, yr in targets:
        for url in candidate_urls(name, yr):
            try:
                resp = http_get(url, SOURCE_ID, retries=1)
            except SourceUnavailable:
                tried.append(url)
                continue
            if not resp.content.startswith(b"%PDF"):
                tried.append(url)
                continue
            return FetchResult(frame=normalize(resp.content), source_url=url)
    raise SourceUnavailable(SOURCE_ID, f"no open MOMR PDF among candidates: {tried}")
