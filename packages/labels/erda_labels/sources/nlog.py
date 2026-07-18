"""nlog — Netherlands NLOG boreholes via TNO GDN geoservices WFS (spec §5).

Endpoint (registry-verified 2026-07-18; WFS moved 2025-12 to gdngeoservices.nl,
old gdw.nlog.nl is dead): one GetFeature GET on ``nlog:gdw_ng_wll_all_utm`` with
``srsName=EPSG:4326`` returns all 6,728 boreholes as GeoJSON (~10 MB). GeoJSON
axis order is [lon, lat] (verified: HILVERSUM-01 → [5.048, 52.245]).

Column mapping (pre-harmonize standard):

- ``well_id``      = ``"nlog:" + BOREHOLE_CODE`` (unique in the 2026-07-18
  snapshot; sidetracks carry their own codes, e.g. ``GTV-01-S1``).
- ``lat``/``lon``  = GeoJSON Point coordinates (y, x). WGS84 per srsName.
- ``spud_year``    = year of ``START_DATE_DRILLING`` (ISO ``YYYY-MM-DD``).
  Oldest observed spud is 1800 (19th-century state coal/exploration boreholes,
  some with placeholder-looking ``1800-01-01`` dates) — kept verbatim;
  harmonize's 1900 floor is a downstream science decision, not ours.
- ``purpose_raw``  = ``BOREHOLE_TYPE_CODE`` verbatim.
- ``purpose``      — documented mapping over the 16 type codes observed live on
  2026-07-18 (count in parens; descriptions are the WFS's own
  ``BOREHOLE_TYPE_DESCRIPTION``):

  * wildcat   — ``EXP-HC`` (1,768, "Exploration hydrocarbon") and legacy
    ``EXP`` (179, same description).
  * appraisal — ``EVA-HC`` (736, "Appraisal hydrocarbon").
  * other     — every non-hydrocarbon-exploration type: ``DEV-HC`` (2,747
    development), ``DEV-PS`` (614 rock salt), ``DEV-I`` (178 injection),
    ``DEV-PH`` (111 geothermal), ``EXP-C`` (101 coal), ``OBS`` (66),
    ``DEV-SG`` (65 gas storage), ``VKN-G`` (64 geological exploration),
    ``DEV-C`` (40 coal), ``EXP-W`` (30 geothermal expl.), ``EXP-S`` (24 rock
    salt expl.), ``DEV-SC`` (4 CO2 storage), ``DEV`` (1).

  A type code outside this enumeration (including a missing one) RAISES
  ContractViolation — NLOG has drifted codes before, and a new exploration
  variant silently classified "other" would silently shrink the wildcat set
  (the sodir WILDCAT-CCS lesson). Nothing is filtered here: purpose="other"
  rows stay; harmonize selects wildcats later.
- ``content_raw``  = ``BOREHOLE_RESULT_CODE`` verbatim; the 171 boreholes with
  a null result become empty string "" (mapped excluded-class in
  data/curated/outcome_map.d/nlog.csv — never guessed).
- ``td_m``         = ``END_DEPTH_MAH`` (measured along-hole total depth,
  metres; chosen over END_DEPTH_MTVD as the conventional "TD"; 119 nulls stay
  null).
- ``discovery_id`` = ``FIELD_CODE`` (3,065 non-null), else None.

Rows are never dropped except full-row hard duplicates by PK; conflicting
duplicates (same BOREHOLE_CODE, different data) fail the schema's uniqueness
check. Zero features or a truncated WFS page (numberReturned < numberMatched)
raise SourceUnavailable — no empty-but-fresh tables (§0 rule 4).
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_ingestion.base import FetchResult, http_get

SOURCE_ID = "nlog"
TRANSFORM_VERSION = "nlog:1.0.0"
TABLE = "nlog_wells"

WFS_URL = "https://www.gdngeoservices.nl/geoserver/nlog/ows"
WFS_PARAMS = {
    "service": "WFS",
    "version": "2.0.0",
    "request": "GetFeature",
    "typeNames": "nlog:gdw_ng_wll_all_utm",
    "srsName": "EPSG:4326",
    "outputFormat": "application/json",
}

#: BOREHOLE_TYPE_CODE → purpose. Complete over the 16 codes observed live on
#: 2026-07-18 (see module docstring); an unlisted code raises, never defaults.
PURPOSE_MAP = {
    "EXP-HC": "wildcat",
    "EXP": "wildcat",
    "EVA-HC": "appraisal",
    "DEV-HC": "other",
    "DEV-PS": "other",
    "DEV-I": "other",
    "DEV-PH": "other",
    "EXP-C": "other",
    "OBS": "other",
    "DEV-SG": "other",
    "VKN-G": "other",
    "DEV-C": "other",
    "EXP-W": "other",
    "EXP-S": "other",
    "DEV-SC": "other",
    "DEV": "other",
}

COLUMNS = [
    "well_id",
    "lat",
    "lon",
    "spud_year",
    "purpose_raw",
    "purpose",
    "content_raw",
    "td_m",
    "discovery_id",
]

SCHEMA = pa.DataFrameSchema(
    {
        "well_id": pa.Column(str, nullable=False),
        # WGS84 per srsName=EPSG:4326; every 2026-07-18 feature has a geometry,
        # but a future null geometry stays a null coordinate — never a dropped row.
        "lat": pa.Column(float, pa.Check.in_range(-90, 90), nullable=True),
        "lon": pa.Column(float, pa.Check.in_range(-180, 180), nullable=True),
        # Oldest observed spud year is 1800 — pre-1900 boreholes are genuine
        # history here; harmonize applies its own 1900 floor downstream.
        "spud_year": pa.Column("Int64", pa.Check.in_range(1500, 2100), nullable=True),
        "purpose_raw": pa.Column(str, nullable=False),
        "purpose": pa.Column(str, pa.Check.isin(["wildcat", "appraisal", "other"]), nullable=False),
        "content_raw": pa.Column(str, nullable=False),
        "td_m": pa.Column(float, pa.Check.ge(0), nullable=True),
        "discovery_id": pa.Column(str, nullable=True),
    },
    unique=["well_id"],
)


def normalize(payload: dict) -> pd.DataFrame:
    """WFS GetFeature GeoJSON → pre-harmonize well rows. Pure; raises, never guesses.

    - No ``features`` key (e.g. a WFS ExceptionReport parsed upstream) →
      SourceUnavailable.
    - Zero features, or numberReturned < numberMatched (server-side paging
      truncation) → SourceUnavailable: an empty-but-fresh label table is §0's
      worst outcome.
    - Missing BOREHOLE_CODE (the PK) or an unmapped BOREHOLE_TYPE_CODE →
      ContractViolation.
    """
    if "features" not in payload:
        raise SourceUnavailable(SOURCE_ID, "payload has no 'features' key — not a GeoJSON response")
    features = payload["features"]
    matched = payload.get("numberMatched")
    returned = payload.get("numberReturned")
    if isinstance(matched, int) and isinstance(returned, int) and returned < matched:
        raise SourceUnavailable(
            SOURCE_ID,
            f"truncated WFS response: numberReturned={returned} < numberMatched={matched}",
        )
    if not features:
        raise SourceUnavailable(SOURCE_ID, "zero features — refusing an empty-but-fresh table")

    rows = []
    missing_pk = 0
    unknown_types: set[str | None] = set()
    for feature in features:
        props = feature.get("properties") or {}
        code = props.get("BOREHOLE_CODE")
        if not code:
            missing_pk += 1
            continue
        geometry = feature.get("geometry")
        if geometry and geometry.get("coordinates"):
            lon, lat = geometry["coordinates"][0], geometry["coordinates"][1]
        else:
            lon, lat = None, None
        spud = props.get("START_DATE_DRILLING")
        spud_year = int(spud[:4]) if spud and spud[:4].isdigit() else None
        type_code = props.get("BOREHOLE_TYPE_CODE")
        purpose = PURPOSE_MAP.get(type_code)
        if purpose is None:
            unknown_types.add(type_code)
        result_code = props.get("BOREHOLE_RESULT_CODE")
        field_code = props.get("FIELD_CODE")
        rows.append(
            {
                "well_id": f"nlog:{code}",
                "lat": lat,
                "lon": lon,
                "spud_year": spud_year,
                "purpose_raw": type_code if type_code is not None else "",
                "purpose": purpose,
                "content_raw": result_code if result_code is not None else "",
                "td_m": props.get("END_DEPTH_MAH"),
                "discovery_id": field_code if field_code else None,
            }
        )

    if missing_pk:
        raise ContractViolation(SOURCE_ID, f"{missing_pk} features missing BOREHOLE_CODE (the PK)")
    if unknown_types:
        raise ContractViolation(
            SOURCE_ID,
            f"unmapped BOREHOLE_TYPE_CODE {sorted(unknown_types, key=str)} — "
            "classify explicitly in PURPOSE_MAP; silent 'other' could hide new wildcat variants",
        )

    df = pd.DataFrame(rows, columns=COLUMNS)
    # Hard duplicates only: identical rows sharing the PK collapse to one;
    # conflicting rows with the same PK survive to fail the schema's uniqueness
    # check loudly. No other row is ever dropped here.
    df = df.drop_duplicates().reset_index(drop=True)
    df["lat"] = df["lat"].astype(float)
    df["lon"] = df["lon"].astype(float)
    df["spud_year"] = df["spud_year"].astype("Int64")
    df["td_m"] = df["td_m"].astype(float)
    return df


def fetch() -> FetchResult:
    resp = http_get(WFS_URL, SOURCE_ID, params=WFS_PARAMS, timeout=180.0)
    try:
        payload = resp.json()
    except ValueError as exc:
        # WFS failures come back as an XML ExceptionReport, not GeoJSON.
        raise SourceUnavailable(
            SOURCE_ID, f"non-JSON WFS response (ExceptionReport?): {resp.text[:200]!r}"
        ) from exc
    return FetchResult(frame=normalize(payload), source_url=str(resp.url))
