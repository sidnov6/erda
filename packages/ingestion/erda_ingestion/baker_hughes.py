"""baker_hughes — Baker Hughes NA weekly rig count (spec §4). Cadence: weekly, SLA ≤ 9 days (§8).

Source of record: the "North America Rig Count Report - New Report" XLSX on
rigcount.bakerhughes.com. Drift notes (registry, live-verified 2026-07-18):

- Akamai blocks non-browser TLS fingerprints — plain httpx/curl fail, so this
  module fetches with curl_cffi Chrome impersonation (the one connector that
  cannot use ``base.http_get``).
- NA weekly workbook lives at ``/static-files/d28e146b-f462-4769-a061-6ba4eb24a490``
  (UUID stable so far; ~7 MB, content replaced weekly). If the UUID ever 404s,
  the sanctioned fallback is to scrape ``/na-rig-count`` for the current
  xlsx-typed anchor (title ``MM-DD-YYYY … Rig_Count Report.xlsx``) — see
  :func:`find_na_weekly_url`. No other fallback exists; anything else raises.
- Report FORMAT CHANGED Aug 2025: the current workbook covers 2024-01 onward
  only; deeper history sits in separate archive workbooks (xlsb) not ingested
  here. Saudi rig-count METHODOLOGY changed Jan 2024 (site banner) — that
  affects the worldwide/international series, not this NA weekly table, but is
  recorded here so nobody splices international history naively.

Parsing (verified against the 2026-07-18 download): sheet ``NAM Weekly``,
10 banner rows then headers on spreadsheet row 11 — Country, County, Basin,
GOM, DrillFor, Location, State/Province, Trajectory, Year, Month,
US_PublishDate, Rig Count Value. Each row is a disaggregated count; weekly
totals are the sum over a publish date. normalize() keeps it modest for the P1
panel: aggregate to (week, region, basin, drill_for) — US + Canada weekly
totals with an oil/gas split and Basin as published (Canada is all "Other").
County/Location/Trajectory detail is deliberately dropped at this version.
"""

from __future__ import annotations

import io
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import pandera.pandas as pa
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from curl_cffi.requests.exceptions import RequestException

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_ingestion.base import FetchResult

SOURCE_ID = "baker_hughes"
TRANSFORM_VERSION = "baker_hughes:1.0.0"
TABLE = "baker_rigs"

#: UUID verified live 2026-07-18 (registry). Content is replaced weekly in place.
NA_WEEKLY_URL = "https://rigcount.bakerhughes.com/static-files/d28e146b-f462-4769-a061-6ba4eb24a490"
RIG_COUNT_PAGE_URL = "https://rigcount.bakerhughes.com/na-rig-count"

NAM_WEEKLY_SHEET = "NAM Weekly"
#: 0-indexed header row for pandas: the sheet has a 10-row banner, headers on row 11.
HEADER_ROW = 10

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

REGIONS = {"UNITED STATES": "us", "CANADA": "canada"}
DRILL_FOR = {"Oil": "oil", "Gas": "gas", "Miscellaneous": "miscellaneous"}

_RAW_COLUMNS = ["Country", "Basin", "DrillFor", "US_PublishDate", "Rig Count Value"]
_TITLE_DATE = re.compile(r"^(\d{2}-\d{2}-\d{4})")

SCHEMA = pa.DataFrameSchema(
    {
        "week": pa.Column(pa.DateTime, nullable=False),
        "region": pa.Column(str, pa.Check.isin(list(REGIONS.values())), nullable=False),
        "basin": pa.Column(str, nullable=False),
        "drill_for": pa.Column(str, pa.Check.isin(list(DRILL_FOR.values())), nullable=False),
        "rig_count": pa.Column(int, pa.Check.ge(0), nullable=False),
    },
    unique=["week", "region", "basin", "drill_for"],
)


def load_nam_weekly(xlsx: bytes | Path) -> pd.DataFrame:
    """Read the NAM Weekly sheet exactly as published (banner rows, header on row 11)."""
    src: io.BytesIO | Path = io.BytesIO(xlsx) if isinstance(xlsx, bytes) else xlsx
    try:
        return pd.read_excel(src, sheet_name=NAM_WEEKLY_SHEET, header=HEADER_ROW)
    except ValueError as exc:  # sheet gone/renamed → the Aug-2025-style format drift again
        raise ContractViolation(SOURCE_ID, f"cannot read '{NAM_WEEKLY_SHEET}': {exc}") from exc


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    """NAM Weekly rows → tidy (week, region, basin, drill_for, rig_count).

    Rows missing any required field are dropped (never imputed, §0 rule 4);
    an unknown Country or DrillFor value means the workbook layout drifted and
    is a hard ContractViolation, not something to skip silently.
    """
    missing = [c for c in _RAW_COLUMNS if c not in raw.columns]
    if missing:
        raise ContractViolation(SOURCE_ID, f"NAM Weekly columns missing: {missing}")
    df = raw[_RAW_COLUMNS].dropna(subset=_RAW_COLUMNS).copy()

    unknown_country = sorted(set(df["Country"]) - set(REGIONS))
    if unknown_country:
        raise ContractViolation(SOURCE_ID, f"unexpected Country values: {unknown_country}")
    unknown_drill = sorted(set(df["DrillFor"]) - set(DRILL_FOR))
    if unknown_drill:
        raise ContractViolation(SOURCE_ID, f"unexpected DrillFor values: {unknown_drill}")

    df["week"] = pd.to_datetime(df["US_PublishDate"])
    df["region"] = df["Country"].map(REGIONS)
    df["basin"] = df["Basin"].astype(str).str.strip()
    df["drill_for"] = df["DrillFor"].map(DRILL_FOR)
    df["rig_count"] = df["Rig Count Value"].astype(int)
    out = (
        df.groupby(["week", "region", "basin", "drill_for"], as_index=False)["rig_count"]
        .sum()
        .sort_values(["week", "region", "basin", "drill_for"], ignore_index=True)
    )
    if out.empty:
        # Headers matched but zero data rows survived — that is format drift,
        # never an empty-but-fresh table to persist (§0 rule 4).
        raise ContractViolation(SOURCE_ID, "NAM Weekly parsed to zero rows — layout drifted?")
    return out


def find_na_weekly_url(html: str) -> str:
    """Locate the current NA weekly workbook anchor on /na-rig-count (fallback path).

    The page lists the live report plus dated archives, all as xlsx-typed
    ``/static-files/`` anchors whose ``title`` starts ``MM-DD-YYYY`` (e.g.
    "07-17-2026 North_America Rig_Count Report.xlsx"). The latest title date
    is the current report; xlsb archives and undated xlsx files are excluded.
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[datetime, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if "/static-files/" not in href or anchor.get("type") != XLSX_MIME:
            continue
        title = (anchor.get("title") or "").replace("_", " ")
        stamp = _TITLE_DATE.match(title)
        if not stamp or "rig count" not in title.lower():
            continue
        candidates.append((datetime.strptime(stamp.group(1), "%m-%d-%Y"), href))
    if not candidates:
        raise SourceUnavailable(
            SOURCE_ID, f"no dated NA weekly XLSX anchor found on {RIG_COUNT_PAGE_URL}"
        )
    _, href = max(candidates)
    return urljoin(RIG_COUNT_PAGE_URL, href)


def _download(url: str, *, timeout: float = 60.0, retries: int = 3) -> cffi_requests.Response:
    """GET via curl_cffi Chrome impersonation (Akamai TLS-fingerprint gate); retries."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            resp = cffi_requests.get(url, impersonate="chrome", timeout=timeout)
            resp.raise_for_status()
            return resp
        except RequestException as exc:
            last = exc
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise SourceUnavailable(SOURCE_ID, f"{url} → {last}")


def fetch() -> FetchResult:
    """Download the NA weekly workbook; on UUID failure, rediscover it via /na-rig-count."""
    url = NA_WEEKLY_URL
    try:
        resp = _download(url)
    except SourceUnavailable:
        # Registry-sanctioned fallback: the UUID drifted — scrape the page for
        # the current anchor. If that also fails, SourceUnavailable propagates.
        page = _download(RIG_COUNT_PAGE_URL)
        url = find_na_weekly_url(page.text)
        resp = _download(url)
    frame = normalize(load_nam_weekly(resp.content))
    return FetchResult(frame=frame, source_url=url)
