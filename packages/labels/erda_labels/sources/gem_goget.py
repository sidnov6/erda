"""gem_goget — GEM Global Oil & Gas Extraction Tracker (GoGET) field points.

GLOBAL AUGMENTATION SOURCE — NOT A WELL-LABEL SOURCE. GoGET describes
*fields/projects* (one point per known accumulation/extraction project),
not exploration wellbores: it has no well purpose codes and no per-well
outcome/content codes. It therefore produces NO ``outcome_map.d`` fragment
and never enters the harmonized §5 label set (its rows are all, by
construction, discoveries — using them as labels would be pure
survivorship bias). It feeds frontier case-study coordinates and the
Discovery Monitor (``status == "discovered"`` recency, ``discovery_year``
time series).

Release + endpoint (live-verified 2026-07-18, HTTP 200):
    https://publicgemdata.nyc3.cdn.digitaloceanspaces.com/interim_maps/goget_map_2026-03.geojson
    March 2026 release, open GeoJSON (CC BY), 12,620,640 bytes,
    7,673 Point features. The canonical XLSX (which adds reserves figures)
    is one-shot-form gated with ephemeral presigned URLs — reserves are
    therefore ABSENT from this table and are never invented (§0 rule 4).
    The filename is release-versioned: on a quarterly refresh, list the
    bucket (``?prefix=interim_maps/``) to find the new name. A stale
    pinned URL fails loudly with SourceUnavailable; it never degrades.

Observed inventories (full 2026-03 release, 7,673 features):

- ``status`` (verbatim, pinned in KNOWN_STATUSES; a NEW value in a future
  release is a ContractViolation — extend the pin deliberately, never let
  vocabulary drift through silently): operating 6481, discovered 455,
  mothballed 240, in-development 229, "not found" 213, abandoned 21,
  decommissioning 17, cancelled 10, "underground gas storage" 6,
  exploration 1.
- ``discovery-year``: a 4-digit string or ``""`` (2,459 empty). Empty →
  missing (pd.NA), NEVER 0. Any other unparseable value raises. Observed
  range 1887–2025.
- geometry: every feature is a Point; coordinates duplicate the
  ``Latitude``/``Longitude`` properties exactly (checked across the full
  release). GEM publishes web-map (WGS84) coordinates.
- ``project-id``: unique string PK ("L1000003…"); prefixed here as
  ``gem_goget:<project-id>``.

Rows are never dropped except hard duplicates (fully identical rows,
i.e. the same PK carrying the same payload twice); conflicting rows that
share a PK survive normalize and fail the schema's uniqueness check.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_ingestion.base import FetchResult, http_get

SOURCE_ID = "gem_goget"
TRANSFORM_VERSION = "gem_goget:1.0.0"
TABLE = "goget_fields"

#: Release-versioned open-GeoJSON path (registry: gem_goget). Live-verified
#: 2026-07-18. Quarterly refresh: poll the bucket with ?prefix=interim_maps/.
DOWNLOAD_URL = (
    "https://publicgemdata.nyc3.cdn.digitaloceanspaces.com/interim_maps/"
    "goget_map_2026-03.geojson"
)

#: Verbatim status vocabulary observed in the 2026-03 release (counts in the
#: module docstring). Pinned so vocabulary drift in a future release raises.
KNOWN_STATUSES = [
    "operating",
    "discovered",
    "mothballed",
    "in-development",
    "not found",
    "abandoned",
    "decommissioning",
    "cancelled",
    "underground gas storage",
    "exploration",
]

SCHEMA = pa.DataFrameSchema(
    {
        "field_id": pa.Column(str, pa.Check.str_startswith("gem_goget:"), nullable=False),
        "name": pa.Column(str, nullable=False),
        "country": pa.Column(str, nullable=False),
        "status": pa.Column(str, pa.Check.isin(KNOWN_STATUSES), nullable=False),
        # Nullable Int64: empty discovery-year stays missing; harmonize-style
        # dropping is NOT this module's job (and this table never harmonizes).
        "discovery_year": pa.Column("Int64", pa.Check.in_range(1800, 2100), nullable=True),
        "lat": pa.Column(float, pa.Check.in_range(-90, 90), nullable=False),
        "lon": pa.Column(float, pa.Check.in_range(-180, 180), nullable=False),
    },
    unique=["field_id"],
)


def _parse_discovery_year(raw: object, project_id: str) -> int | None:
    """'1953' → 1953; '' / None → None (missing, never 0); else raise."""
    text = str(raw).strip() if raw is not None else ""
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        raise ContractViolation(
            SOURCE_ID,
            f"{project_id}: unparseable discovery-year {raw!r} — refusing to guess",
        ) from None


def normalize(payload: dict) -> pd.DataFrame:
    """GoGET GeoJSON FeatureCollection → tidy goget_fields frame. Pure.

    Failure semantics (§0 rule 4): a payload that is not a FeatureCollection
    or has zero features is a source failure and raises — it never
    normalizes into an empty-but-fresh table. Malformed features (missing
    project-id, non-Point geometry, unparseable discovery-year) raise
    ContractViolation; nothing is skipped or imputed.
    """
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        raise SourceUnavailable(
            SOURCE_ID, "payload is not a GeoJSON FeatureCollection (no 'features' list)"
        )
    if not features:
        raise SourceUnavailable(
            SOURCE_ID, "zero features — refusing to write an empty-but-fresh table"
        )

    records: list[dict] = []
    years: list[int | None] = []
    for feature in features:
        props = feature.get("properties") or {}
        project_id = props.get("project-id")
        if not project_id:
            raise ContractViolation(
                SOURCE_ID, f"feature without project-id (name={props.get('name')!r})"
            )
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Point":
            raise ContractViolation(
                SOURCE_ID,
                f"{project_id}: geometry is {geometry.get('type')!r}, expected Point",
            )
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2:
            raise ContractViolation(
                SOURCE_ID, f"{project_id}: malformed Point coordinates {coordinates!r}"
            )
        years.append(_parse_discovery_year(props.get("discovery-year"), project_id))
        records.append(
            {
                "field_id": f"{SOURCE_ID}:{project_id}",
                "name": str(props.get("name") or ""),
                "country": str(props.get("country-area1") or ""),
                "status": str(props.get("status") or ""),
                # GeoJSON order is [lon, lat]
                "lat": float(coordinates[1]),
                "lon": float(coordinates[0]),
            }
        )

    df = pd.DataFrame.from_records(records)
    df["discovery_year"] = pd.array(years, dtype="Int64")
    df = df[["field_id", "name", "country", "status", "discovery_year", "lat", "lon"]]
    # Hard duplicates only: identical PK with identical payload collapses to
    # one row. A PK repeated with CONFLICTING payload survives here and fails
    # SCHEMA's unique=["field_id"] — conflicts are surfaced, never resolved
    # by silent row-dropping.
    return df.drop_duplicates().reset_index(drop=True)


def fetch(url: str = DOWNLOAD_URL) -> FetchResult:
    """Download the release GeoJSON and normalize. For quarterly refresh."""
    resp = http_get(url, SOURCE_ID, timeout=120.0)
    try:
        payload = resp.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise SourceUnavailable(SOURCE_ID, f"{url} returned a non-JSON body: {exc}") from exc
    return FetchResult(frame=normalize(payload), source_url=url)


def load_local(path: Path | str, *, source_url: str = DOWNLOAD_URL) -> FetchResult:
    """Normalize an already-downloaded release file (e.g. data/raw/…).

    ``source_url`` defaults to this release's canonical URL: the caller
    asserts the file is an unmodified download of that URL (the checked
    copy at data/raw/goget_map_2026-03.geojson matches the live object
    byte-for-byte: 12,620,640 bytes, verified 2026-07-18). Pass a
    different ``source_url`` if the file came from elsewhere — provenance
    must never claim an origin the bytes did not have.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise SourceUnavailable(SOURCE_ID, f"local GoGET file missing: {file_path}")
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SourceUnavailable(SOURCE_ID, f"{file_path} is not valid JSON: {exc}") from exc
    return FetchResult(frame=normalize(payload), source_url=source_url)
