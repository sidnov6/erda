"""comtrade — UN Comtrade crude-oil (HS 2709) export values by reporter-year (spec §4).

Cadence: monthly/annual releases, SLA 70 days (source_registry.yaml). Table
`comtrade_crude_exports`: one row per reporter-year of world crude exports.

Live-verified drift notes (registry sweep + this connector's build, 2026-07-18):

- Keyless ``/public/v1/preview/C/A/HS`` works but hard-caps responses at 500
  records. The cap is reported honestly via the top-level ``count`` field —
  ``count == 500`` means the response was truncated, and every row from such a
  response carries ``truncated=True`` (spec honesty: a capped table must say so).
- ``maxRecords`` is *ignored* by the preview endpoint (verified live: a
  ``maxRecords=3`` request returned all 500 rows) — never rely on request params
  for cap detection.
- Without ``includeDesc=TRUE`` the API returns null ``reporterISO`` /
  ``reporterDesc``; with ``partnerCode=0`` alone it also returns partner2 /
  mode-of-transport / customs breakdown rows that duplicate the world aggregate.
  Because the API has been observed ignoring params, :func:`normalize` re-filters
  to the world-aggregate slice (partner2Code=0, motCode=0, customsCode=C00)
  instead of trusting the request.
- Free key (env ``COMTRADE_API_KEY``) unlocks ``/data/v1/get`` (100k records,
  500 calls/day, 1 req/s). Key goes in the ``Ocp-Apim-Subscription-Key`` header;
  calls are throttled to 1/s; provenance carries the endpoint, never the key.

World-aggregate rows are flagged ``isReported=false`` / ``isAggregate=true`` by
the API — surfaced as ``is_estimate`` (UN-derived aggregate, not a value the
reporter filed directly). Rows missing the export value or the reporter identity
are dropped, never imputed (§0 rule 4).
"""

from __future__ import annotations

import os
import time

import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import SourceUnavailable
from erda_ingestion.base import FetchResult, http_get

SOURCE_ID = "comtrade"
TRANSFORM_VERSION = "comtrade:1.0.0"
TABLE = "comtrade_crude_exports"

BASE_URL = "https://comtradeapi.un.org"
PREVIEW_URL = f"{BASE_URL}/public/v1/preview/C/A/HS"
KEYED_URL = f"{BASE_URL}/data/v1/get/C/A/HS"

#: Keyless preview hard cap (registry drift note): count == 500 → truncated.
PREVIEW_CAP = 500

#: HS 2709 = crude petroleum oils; flow X = exports; partner 0 = world.
QUERY = {
    "cmdCode": "2709",
    "flowCode": "X",
    "partnerCode": "0",
    "partner2Code": "0",
    "motCode": "0",
    "customsCode": "C00",
    "includeDesc": "TRUE",
}

COLUMNS = ["year", "reporter_iso", "reporter", "export_value_usd", "is_estimate", "truncated"]

SCHEMA = pa.DataFrameSchema(
    {
        "year": pa.Column(int, pa.Check.in_range(1962, 2100), nullable=False),
        "reporter_iso": pa.Column(str, pa.Check.str_length(3, 3), nullable=False),
        "reporter": pa.Column(str, nullable=False),
        "export_value_usd": pa.Column(float, pa.Check.ge(0), nullable=False),
        "is_estimate": pa.Column(bool, nullable=False),
        "truncated": pa.Column(bool, nullable=False),
    },
    unique=["year", "reporter_iso"],
)


def _is_world_aggregate(row: dict) -> bool:
    """Keep only the one-row-per-reporter world slice; breakdown rows duplicate it."""
    return (
        row.get("flowCode") == "X"
        and row.get("cmdCode") == "2709"
        and row.get("partnerCode") == 0
        and row.get("partner2Code") == 0
        and row.get("motCode") == 0
        and row.get("customsCode") == "C00"
    )


def normalize(payload: dict) -> pd.DataFrame:
    """Comtrade response JSON → tidy frame per the contract.

    Defensively re-filters to world-aggregate rows (the API ignores params —
    see module docstring), drops rows missing value or reporter identity
    (missing data is dropped, never imputed), and marks every surviving row
    ``truncated=True`` when the response hit the 500-record preview cap.
    """
    truncated = payload.get("count") == PREVIEW_CAP
    records = []
    for row in payload.get("data") or []:
        if not _is_world_aggregate(row):
            continue
        value = row.get("primaryValue")
        iso = row.get("reporterISO")
        name = row.get("reporterDesc")
        year = row.get("refYear")
        if value is None or iso is None or name is None or year is None:
            continue
        records.append(
            {
                "year": int(year),
                "reporter_iso": str(iso),
                "reporter": str(name),
                "export_value_usd": float(value),
                "is_estimate": (not row.get("isReported", False)) or bool(row.get("isAggregate")),
                "truncated": truncated,
            }
        )
    df = pd.DataFrame(records, columns=COLUMNS)
    return df.astype(
        {"year": "int64", "export_value_usd": "float64", "is_estimate": bool, "truncated": bool}
    )


def fetch(years: tuple[int, ...] | None = None) -> FetchResult:
    """Fetch crude-export values for `years` (default: the last three full years).

    Keyless → preview endpoint (500-row cap honestly marked via `truncated`).
    With COMTRADE_API_KEY → /data/v1/get, key in header, throttled 1 req/s.
    """
    if years is None:
        current = pd.Timestamp.now(tz="UTC").year
        years = tuple(range(current - 3, current))

    key = os.environ.get("COMTRADE_API_KEY")
    url = KEYED_URL if key else PREVIEW_URL
    headers = {"Ocp-Apim-Subscription-Key": key} if key else None

    frames = []
    for i, year in enumerate(sorted(years)):
        if key and i > 0:
            time.sleep(1.0)  # registry drift note: keyed tier is limited to 1 req/s
        resp = http_get(url, SOURCE_ID, params={**QUERY, "period": str(year)}, headers=headers)
        try:
            payload = resp.json()
        except ValueError as exc:
            raise SourceUnavailable(SOURCE_ID, f"non-JSON response for {year}: {exc}") from exc
        if payload.get("error"):
            raise SourceUnavailable(SOURCE_ID, f"API error for {year}: {payload['error']}")
        frame = normalize(payload)
        if frame.empty and payload.get("data"):
            raise SourceUnavailable(
                SOURCE_ID,
                f"{year}: {len(payload['data'])} rows returned but none matched the "
                "world-aggregate shape — response schema or params drifted",
            )
        frames.append(frame)

    out = pd.concat(frames, ignore_index=True)
    if out.empty:
        raise SourceUnavailable(SOURCE_ID, f"no data for any requested year {sorted(years)}")
    # Provenance carries the endpoint, never the key.
    return FetchResult(frame=out, source_url=url)
