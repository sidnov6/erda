"""jodi — JODI Oil World Database, bulk CSV (spec §4). Cadence: monthly, SLA ≤ 45 days (§8).

Drift notes (source_registry.yaml, live-verified 2026-07-18):

- The bulk download lives on **jodidata.org** — jodidb.org is only the
  interactive UI. Anonymous GET, ~23 MB zip containing a single CSV
  (`NewProcedure_Primary_CSV.csv`) with columns REF_AREA, TIME_PERIOD,
  ENERGY_PRODUCT, FLOW_BREAKDOWN, UNIT_MEASURE, OBS_VALUE, ASSESSMENT_CODE.
- OBS_VALUE carries absence markers, not numbers: ``-`` (data not available)
  and ``x`` (not applicable) per the registry, plus two more observed live in
  the 2026-07-18 file: literal ``N/A`` (~1.6M rows) and SDMX-style ``..``
  (~0.5M rows). All four are **absence markers, never zeros** — normalize()
  drops those rows outright; imputing 0 would fabricate data (§0 rule 4).
- Units vary row by row (KBBL, KBD, KL, KTONS, CONVBBL), so the observation
  stays a plain ``value`` column alongside ``unit_measure`` — a unit-suffixed
  column name would lie for four of the five units.
- Negative values are legitimate (stock changes, statistical differences,
  revision artifacts in other flows) and are kept.

Primary table ``jodi_oil``: filtered to ENERGY_PRODUCT == CRUDEOIL, flow and
unit columns kept. TIME_PERIOD ("2026-01") becomes a month-start timestamp.
"""

from __future__ import annotations

import io
import zipfile
from typing import IO

import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_ingestion.base import FetchResult, http_get

SOURCE_ID = "jodi"
TRANSFORM_VERSION = "jodi:1.0.0"
TABLE = "jodi_oil"

ZIP_URL = "https://www.jodidata.org/_resources/files/downloads/oil-data/world_Primary_CSV.zip"

RAW_COLUMNS = [
    "REF_AREA",
    "TIME_PERIOD",
    "ENERGY_PRODUCT",
    "FLOW_BREAKDOWN",
    "UNIT_MEASURE",
    "OBS_VALUE",
    "ASSESSMENT_CODE",
]

#: OBS_VALUE absence markers (see module docstring). Dropped, never zeroed.
#: '-' and 'x' per registry; 'N/A' and '..' observed live 2026-07-18.
ABSENCE_MARKERS = frozenset({"-", "x", "N/A", ".."})

#: SDMX codelists observed in the 2026-07-18 file. Pinned so silent upstream
#: additions surface as ContractViolation instead of slipping through unreviewed.
FLOWS = [
    "CLOSTLV",
    "DIRECUSE",
    "INDPROD",
    "OSOURCES",
    "REFINOBS",
    "STATDIFF",
    "STOCKCH",
    "TOTEXPSB",
    "TOTIMPSB",
    "TRANSBAK",
]
UNITS = ["CONVBBL", "KBBL", "KBD", "KL", "KTONS"]

SCHEMA = pa.DataFrameSchema(
    {
        "period": pa.Column(pa.DateTime, nullable=False),
        "ref_area": pa.Column(str, pa.Check.str_length(2, 2), nullable=False),
        "energy_product": pa.Column(str, pa.Check.isin(["CRUDEOIL"]), nullable=False),
        "flow_breakdown": pa.Column(str, pa.Check.isin(FLOWS), nullable=False),
        "unit_measure": pa.Column(str, pa.Check.isin(UNITS), nullable=False),
        # Negative values are real (STOCKCH draws, STATDIFF) — no sign check.
        "value": pa.Column(float, nullable=False),
        "assessment_code": pa.Column(str, nullable=False),
    },
    unique=["ref_area", "period", "energy_product", "flow_breakdown", "unit_measure"],
)


def read_raw(handle: IO[bytes] | IO[str]) -> pd.DataFrame:
    """Read the bulk CSV with every field as a literal string.

    ``keep_default_na=False`` is load-bearing: pandas would otherwise turn the
    ``N/A`` absence marker into NaN before normalize() can account for it.
    """
    return pd.read_csv(handle, dtype=str, keep_default_na=False)


def extract_csv(zip_bytes: bytes) -> pd.DataFrame:
    """Extract the single CSV member from the bulk zip; anything else is drift."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise SourceUnavailable(SOURCE_ID, f"bulk download is not a zip: {exc}") from exc
    members = [n for n in archive.namelist() if n.lower().endswith(".csv")]
    if len(members) != 1:
        raise SourceUnavailable(
            SOURCE_ID, f"expected exactly one CSV in bulk zip, found {members}"
        )
    with archive.open(members[0]) as handle:
        return read_raw(handle)


def normalize(raw: pd.DataFrame, product: str = "CRUDEOIL") -> pd.DataFrame:
    """Raw bulk rows → tidy jodi_oil frame.

    Rows whose OBS_VALUE is an absence marker ('-', 'x', 'N/A', '..') are
    dropped — they mean "no data", never zero. Any other non-numeric OBS_VALUE
    is an unknown upstream marker and fails loudly rather than being guessed at.
    """
    missing = [c for c in RAW_COLUMNS if c not in raw.columns]
    if missing:
        raise ContractViolation(SOURCE_ID, f"bulk CSV missing columns: {missing}")

    df = raw.loc[raw["ENERGY_PRODUCT"] == product, RAW_COLUMNS].copy()
    if df.empty:
        # The bulk file always carries CRUDEOIL rows; an empty slice means the
        # product codelist drifted — never persist an empty-but-fresh table.
        raise ContractViolation(
            SOURCE_ID, f"no rows for ENERGY_PRODUCT == {product!r} — product codelist drifted?"
        )
    df = df[~df["OBS_VALUE"].isin(ABSENCE_MARKERS)]

    values = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    bad = df.loc[values.isna(), "OBS_VALUE"].unique().tolist()
    if bad:
        raise ContractViolation(SOURCE_ID, f"unrecognized OBS_VALUE markers: {bad[:10]}")

    out = pd.DataFrame(
        {
            "period": pd.to_datetime(df["TIME_PERIOD"], format="%Y-%m"),
            "ref_area": df["REF_AREA"],
            "energy_product": df["ENERGY_PRODUCT"],
            "flow_breakdown": df["FLOW_BREAKDOWN"],
            "unit_measure": df["UNIT_MEASURE"],
            "value": values.astype(float),
            "assessment_code": df["ASSESSMENT_CODE"].astype(str),
        }
    )
    return out.reset_index(drop=True)


def fetch() -> FetchResult:
    """Download the bulk zip (~23 MB, anonymous GET), extract, normalize."""
    resp = http_get(ZIP_URL, SOURCE_ID, timeout=120.0)
    frame = normalize(extract_csv(resp.content))
    return FetchResult(frame=frame, source_url=ZIP_URL)
