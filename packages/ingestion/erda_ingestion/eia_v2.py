"""eia_v2 — EIA Open Data v2, WPSR weekly series (spec §4 #1). Cadence: weekly.

Freshness SLA: WPSR <= 8 days (§8; source_registry.yaml). Series IDs are pinned
in data/curated/eia_series.yaml (§4) — five US weekly series (crude/gasoline/
distillate stocks, crude production, product supplied), each pinned with the
public EIA doc URL it was verified against on 2026-07-18 (§7 citation rule).

Drift notes implemented against (source_registry.yaml, live-verified 2026-07-18):

- Keyless requests get 403 API_KEY_MISSING for EVERY route (key check precedes
  route resolution). Missing EIA_API_KEY → SourceUnavailable, like fred.
- api_key goes as a query parameter. Register: eia.gov/opendata/register.php.
- v1 series IDs translate via /v2/seriesid/{SERIES_ID} — the confirmed route.
  Exact v2 WPSR child routes were verifiable only with a key, so we do not
  guess at them; the translation route is the one pinned here.
- The v2 error body is {"error": {"code", "message"}} — parsed defensively so
  an error JSON on a 200 also maps to SourceUnavailable, never to empty data.

Value quirks handled in normalize(): v2 serves numbers both as JSON numbers and
as strings; null value = missing datum → dropped, never imputed (§0 rule 4).
A response whose row count is below response.total is truncated → hard failure,
no silent partial data.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
import yaml

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_ingestion.base import FetchResult, http_get

SOURCE_ID = "eia_v2"
TRANSFORM_VERSION = "eia_v2:1.0.0"
TABLE = "eia_v2_weekly"

API_URL = "https://api.eia.gov/v2/seriesid"

#: Spec §4: series IDs live in data/curated/eia_series.yaml, not in code.
SERIES_PATH = Path(__file__).resolve().parents[3] / "data" / "curated" / "eia_series.yaml"

#: Units are encoded in metric names: kbbl = thousand barrels (stocks),
#: kbd = thousand barrels per day (flows).
_METRIC_PATTERN = r"^[a-z0-9_]+_(kbbl|kbd)$"
_SERIES_PATTERN = r"^PET\.[A-Z0-9]+\.W$"

SCHEMA = pa.DataFrameSchema(
    {
        "period": pa.Column(pa.DateTime, nullable=False),
        "series_id": pa.Column(str, pa.Check.str_matches(_SERIES_PATTERN), nullable=False),
        "metric": pa.Column(str, pa.Check.str_matches(_METRIC_PATTERN), nullable=False),
        "value": pa.Column(float, pa.Check.ge(0), nullable=False),
    },
    unique=["period", "series_id"],
)


def load_series(path: Path = SERIES_PATH) -> list[dict]:
    """Load the pinned series list; enforce the §7 curated rule (uncited = rejected)."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    pins = raw.get("series") if isinstance(raw, dict) else None
    if not pins:
        raise ContractViolation(SOURCE_ID, f"no series pinned in {path}")
    for pin in pins:
        missing = [k for k in ("series_id", "metric", "source_url") if not pin.get(k)]
        if missing:
            raise ContractViolation(SOURCE_ID, f"curated row {pin} missing {missing} (spec §7)")
    return pins


def _raise_if_api_error(payload: dict) -> None:
    """EIA errors arrive as {"error": {"code", "message"}} — e.g. the keyless
    403 API_KEY_MISSING body recorded 2026-07-18. Always SourceUnavailable."""
    err = payload.get("error")
    if err:
        raise SourceUnavailable(SOURCE_ID, f"{err.get('code')}: {err.get('message')}")


def normalize(series_id: str, metric: str, payload: dict) -> pd.DataFrame:
    """EIA v2 seriesid JSON → tidy frame. null value = missing → dropped."""
    _raise_if_api_error(payload)
    response = payload.get("response")
    if not isinstance(response, dict) or "data" not in response:
        raise SourceUnavailable(SOURCE_ID, f"{series_id}: malformed payload, no response.data")
    rows = response["data"]
    if not rows:
        # Every pinned WPSR series has decades of history — an empty data list
        # is upstream failure/drift, never an empty-but-fresh table (§0 rule 4).
        raise SourceUnavailable(SOURCE_ID, f"{series_id}: response.data is empty")
    total = response.get("total")
    if total is not None and int(total) > len(rows):
        raise SourceUnavailable(
            SOURCE_ID, f"{series_id}: truncated response ({len(rows)}/{total} rows)"
        )
    df = pd.DataFrame(rows, columns=["period", "value"])
    df = df[df["value"].notna()]  # null = missing datum, dropped, never imputed
    df["period"] = pd.to_datetime(df["period"])
    df["value"] = df["value"].astype(float)  # v2 serves numbers and strings both
    df["series_id"] = series_id
    df["metric"] = metric
    return df[["period", "series_id", "metric", "value"]]


def fetch(series_path: Path = SERIES_PATH) -> FetchResult:
    key = os.environ.get("EIA_API_KEY")
    if not key:
        raise SourceUnavailable(
            SOURCE_ID, "EIA_API_KEY not set — register at eia.gov/opendata/register.php"
        )
    frames = []
    for pin in load_series(series_path):
        resp = http_get(
            f"{API_URL}/{pin['series_id']}",
            SOURCE_ID,
            params={"api_key": key},
        )
        frames.append(normalize(pin["series_id"], pin["metric"], resp.json()))
    # Provenance carries the endpoint, never the key.
    return FetchResult(frame=pd.concat(frames, ignore_index=True), source_url=API_URL)
