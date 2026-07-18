"""fred — FRED spot histories + macro (spec §4 #2). Cadence: daily.

Official REST API, free key (env FRED_API_KEY; register at fredaccount.stlouisfed.org).
Series pinned here rather than in code paths so additions stay declarative:

- DCOILBRENTEU  Brent spot, $/bbl
- DCOILWTICO    WTI spot, $/bbl
- DTWEXBGS      Broad dollar index (FRED has no ICE DXY; this is the Fed broad
                index — labelled as such in the UI, never called DXY unqualified)
- CPIAUCSL      US CPI (all urban), index

Missing key → SourceUnavailable. No key, no data, no invention (§0 rule 4).
"""

from __future__ import annotations

import os

import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import SourceUnavailable
from erda_ingestion.base import FetchResult, http_get

SOURCE_ID = "fred"
TRANSFORM_VERSION = "fred:1.0.0"
TABLE = "fred_series"

API_URL = "https://api.stlouisfed.org/fred/series/observations"

SERIES = {
    "DCOILBRENTEU": "brent_usd_bbl",
    "DCOILWTICO": "wti_usd_bbl",
    "DTWEXBGS": "usd_broad_index",
    "CPIAUCSL": "us_cpi_index",
}

SCHEMA = pa.DataFrameSchema(
    {
        "date": pa.Column(pa.DateTime, nullable=False),
        "series_id": pa.Column(str, pa.Check.isin(list(SERIES)), nullable=False),
        "metric": pa.Column(str, pa.Check.isin(list(SERIES.values())), nullable=False),
        # No positivity check: WTI settled at −36.98 on 2020-04-20 (live-hit on
        # the first full-history fetch). Negative prices are market reality;
        # rejecting them would falsify history.
        "value": pa.Column(float, nullable=False),
    },
    unique=["date", "series_id"],
)


def normalize(series_id: str, payload: dict) -> pd.DataFrame:
    """FRED observations JSON → tidy frame. '.' marks missing values → dropped.

    A payload without an ``observations`` key (e.g. a FRED error body such as
    ``{"error_code": …, "error_message": …}``) is a source failure — it must
    raise, never normalize into an empty-but-fresh table (§0 rule 4).
    """
    if "observations" not in payload:
        detail = payload.get("error_message") or "payload has no 'observations' key"
        raise SourceUnavailable(SOURCE_ID, f"{series_id}: {detail}")
    obs = payload["observations"]
    df = pd.DataFrame(obs, columns=["date", "value"])
    df = df[df["value"] != "."]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = df["value"].astype(float)
    df["series_id"] = series_id
    df["metric"] = SERIES[series_id]
    return df[["date", "series_id", "metric", "value"]]


def fetch(observation_start: str = "2000-01-01") -> FetchResult:
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise SourceUnavailable(SOURCE_ID, "FRED_API_KEY not set — register a free key")
    frames = []
    for series_id in SERIES:
        resp = http_get(
            API_URL,
            SOURCE_ID,
            params={
                "series_id": series_id,
                "api_key": key,
                "file_type": "json",
                "observation_start": observation_start,
            },
        )
        frames.append(normalize(series_id, resp.json()))
    # Provenance carries the endpoint, never the key.
    return FetchResult(frame=pd.concat(frames, ignore_index=True), source_url=API_URL)
