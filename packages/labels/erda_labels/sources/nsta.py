"""nsta — UK NSTA offshore wellbore top-holes (WGS84), E&A subset (spec §5).

WELL-LABEL SOURCE. ArcGIS REST query API on the full top-holes layer
(live-verified 2026-07-18, serviceItemId b5752e9f56a949e3ad44a08144e621a8,
layer 0 "WELLS_TOP_HOLES_WGS84_PROD_B", wkid 4326, maxRecordCount 2000):

    https://services-eu1.arcgis.com/OZMfUznmLTnWccBc/arcgis/rest/services/
    UKCS_offshore_wellbore_top_holes_(WGS84)/FeatureServer/0/query

13,374 wellbores total; ``ORIGINTENT IN ('Exploration','Appraisal')`` selects
the 5,129 E&A wellbores (Exploration 2,955 + Appraisal 2,174; the other
observed values are Development 8,244 and "Carbon capture & storage" 1 —
excluded by the WHERE clause, not fetched). NOTE the Hub also publishes an
"E&A wellbore results (ED50)" layer — that is a 110-well curated subset,
NOT this dataset; we use the full WGS84 top-holes layer.

Purpose mapping (documented per §5; the WHERE clause pins the vocabulary,
so any other ORIGINTENT arriving is server-side drift and raises):

- ``Exploration`` → ``wildcat``. NSTA's "Exploration" is the original
  wellbore intent of testing an undrilled prospect — the closest UK
  equivalent of a wildcat/new-field-wildcat. NSTA does not distinguish
  wildcat vs other-exploration subtypes, so ≈ wildcat is the honest,
  documented reading (dataset card carries the caveat).
- ``Appraisal`` → ``appraisal`` (delineation of an existing find).
- CARBON-STORAGE OVERRIDE → ``other``: the WHERE clause does NOT keep CCS
  out of the E&A subset. NSTA registers carbon-storage wellbores under CS
  licences with a ``C``-prefixed registration number (e.g. ``C48/30- 21``,
  the "Hewett CCS Appraisal well" drilled by Bacton CCS Ltd; ``C44/27- 3``
  drilled by Net Zero North Sea Storage) and still records their intent as
  ``Exploration``/``Appraisal``. Those wells probe CO2 stores, not
  petroleum prospects — counting them as wildcats/appraisals would poison
  the labels (the sodir WILDCAT-CCS lesson), so any WELLREGNO matching
  ``C<digit>…`` maps to ``other`` regardless of ORIGINTENT. ``purpose_raw``
  stays the verbatim ORIGINTENT; nothing is filtered here — harmonize
  selects wildcats later.

Column mapping (field aliases from the layer metadata):

- ``WELLREGNO`` ("Well registration no.", unique across the E&A subset,
  0 duplicate groups live-checked) → ``well_id`` = ``nsta:<WELLREGNO>``
  verbatim, embedded spaces preserved (e.g. ``nsta:41/18- 2``).
- geometry (point, wkid 4326) → ``lat``/``lon``. PREFERRED over the
  ``TOPHOLEYDD``/``TOPHOLEXDD`` string fields: those are strings, differ
  from geometry in the 4th decimal (different top-hole reduction), and are
  null on at least one E&A record whose geometry is present. The DD
  strings are the fallback when geometry is absent; both absent → missing
  (never dropped here); a non-numeric DD string raises.
- ``SPUDDATE`` (epoch-ms, may be negative for pre-1970 spuds, e.g.
  −110160000000 → 1966; 0 nulls in the E&A subset live) → ``spud_year``
  nullable Int64. Missing stays missing — dropping is harmonize's job.
- ``ORIGINTENT`` → ``purpose_raw`` (verbatim) and ``purpose`` (see above).
- ``FLOWCLASS`` ("Original hydrocarbon flow class") → ``content_raw``
  verbatim; null → ``""`` (502 nulls live — an explicit excluded-class
  code in data/curated/outcome_map.d/nsta.csv, never guessed to dry).
- ``TDTVDSSM`` (TD true vertical depth subsea, metres) → ``td_m``
  nullable float (289 nulls live). Some old records carry literal 0
  (e.g. 13/21a- 1) — published value, kept verbatim, not recoded to
  missing. 25 of 5,129 live records store TVDSS in the negative-down
  (elevation) sign convention (e.g. 13/21a- 8: TVDSSM −930.55 with
  measured depth TDMDDEPM 1010.41 and TVDSSF −3053 ft agreeing) — for
  every one |TVDSS| ≤ measured depth as physics requires, and an
  offshore TD hundreds of metres ABOVE sea level is impossible, so the
  reading is unambiguous: negatives are sign-flipped to the dominant
  positive-down convention (documented transform, not fabrication).
- ``TARGETFLD`` ("Target field") → ``discovery_id``. The sentinel string
  ``"No Data Available"`` (3,423 of 5,129 live) is NSTA's explicit
  no-value marker → missing (None), documented here per the sentinel
  rule; real field names (e.g. ``CAPTAIN``) pass through verbatim.

Observed FLOWCLASS inventory (E&A subset, live 2026-07-18, n=5,129):
Dry Hole 1,413; Oil Well 1,181; Gas Well 683; Oil Show 555; null 502;
Gas Show 216; Gas and Oil Well 212; Gas and Condensate Well 185;
Oil and Gas Shows 72; Unknown 63; Condensate Well with Gas Shows 13;
Gas and Condensate Show 13; Condensate Well with Oil Shows 7;
Oil and Condensate Shows 4; Oil Well with Gas Show 4;
Oil Well with Condensate Shows 1; Gas Well with Oil Show 2;
Oil and Condensate Well 2; Gas, Oil and Condensate Well 1.
Each maps in data/curated/outcome_map.d/nsta.csv; an unmapped code raises
in harmonize (§5) — never guessed. ("Hydrocarbon Indications" appears in
the registry note for the FULL layer but was NOT observed in the E&A
subset, so it is deliberately absent from the fragment.)

Failure semantics (§0 rule 4): ArcGIS returns HTTP 200 with an
``{"error": …}`` body on bad queries — treated as SourceUnavailable.
Zero features, a missing required attribute (field-rename drift would
otherwise silently blank a label column), an unexpected ORIGINTENT, or
non-numeric coordinate/depth payloads all raise. Rows are never dropped
except hard duplicates (same PK, identical payload — e.g. pagination
overlap); a PK repeated with conflicting payload survives normalize and
fails SCHEMA's uniqueness check loudly.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_ingestion.base import FetchResult, http_get

SOURCE_ID = "nsta"
TRANSFORM_VERSION = "nsta:1.0.0"
TABLE = "nsta_wells"

QUERY_URL = (
    "https://services-eu1.arcgis.com/OZMfUznmLTnWccBc/arcgis/rest/services/"
    "UKCS_offshore_wellbore_top_holes_(WGS84)/FeatureServer/0/query"
)

WHERE = "ORIGINTENT IN ('Exploration','Appraisal')"

#: Requested explicitly (not ``*``) so intent is documented; normalize
#: additionally asserts every one is present on every feature — a silent
#: field rename upstream must fail loudly, not blank a label column.
REQUEST_FIELDS = [
    "WELLREGNO",
    "ORIGINTENT",
    "FLOWCLASS",
    "SPUDDATE",
    "TDTVDSSM",
    "TARGETFLD",
    "TOPHOLEXDD",
    "TOPHOLEYDD",
]

#: Layer maxRecordCount (live-verified 2026-07-18).
PAGE_SIZE = 2000
#: 5,129 E&A wellbores today → 3 pages; 50 pages = 100k headroom. Beyond
#: that the pagination is runaway (server ignoring resultOffset) → raise.
MAX_PAGES = 50

#: WHERE-clause-pinned vocabulary; any other value is drift and raises.
#: Overridden to "other" for carbon-storage registrations (see CS_REGNO).
PURPOSE_MAP = {"Exploration": "wildcat", "Appraisal": "appraisal"}

#: Carbon-storage wellbore registration (CS licence wells, e.g. "C48/30- 21"):
#: CO2-store probes recorded with petroleum-style ORIGINTENT — mapped to
#: purpose "other", never wildcat/appraisal (module docstring).
CS_REGNO = re.compile(r"C\d")

#: NSTA's explicit no-value marker on TARGETFLD (3,423 of 5,129 live).
NO_DATA_SENTINEL = "No Data Available"

SCHEMA = pa.DataFrameSchema(
    {
        "well_id": pa.Column(str, pa.Check.str_startswith("nsta:"), nullable=False),
        # Nullable: a wellbore without coordinates stays in the table with
        # missing lat/lon — filtering is harmonize's decision, not ours.
        "lat": pa.Column(float, pa.Check.in_range(-90, 90), nullable=True),
        "lon": pa.Column(float, pa.Check.in_range(-180, 180), nullable=True),
        "spud_year": pa.Column("Int64", pa.Check.in_range(1900, 2100), nullable=True),
        "purpose_raw": pa.Column(str, pa.Check.isin(list(PURPOSE_MAP)), nullable=False),
        # "other" = the carbon-storage override (CS_REGNO), never a default.
        "purpose": pa.Column(
            str, pa.Check.isin(["wildcat", "appraisal", "other"]), nullable=False
        ),
        "content_raw": pa.Column(str, nullable=False),
        "td_m": pa.Column(float, pa.Check.ge(0), nullable=True),
        "discovery_id": pa.Column(str, nullable=True),
    },
    unique=["well_id"],
)


def _require(attrs: dict, field: str, well: object) -> object:
    """Attribute presence check — a missing KEY is vocabulary drift and raises
    (a present-but-null VALUE is ordinary missing data and passes through)."""
    if field not in attrs:
        raise ContractViolation(
            SOURCE_ID,
            f"feature (WELLREGNO={well!r}) lacks attribute {field!r} — "
            "field vocabulary drifted upstream; refusing to normalize",
        )
    return attrs[field]


def _spud_year(raw: object, well: str) -> int | None:
    """Epoch-ms → calendar year (UTC). Negative pre-1970 values are real
    (−110160000000 → 1966). None stays missing; non-numeric raises."""
    if raw is None:
        return None
    try:
        return pd.Timestamp(int(raw), unit="ms", tz="UTC").year
    except (ValueError, TypeError):
        raise ContractViolation(
            SOURCE_ID, f"{well}: SPUDDATE {raw!r} is not epoch-ms — refusing to guess"
        ) from None


def _float_or_missing(raw: object, well: str, field: str) -> float:
    """Numeric or None; '' / None → NaN (missing stays missing); a
    non-numeric non-empty value is malformed data and raises."""
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return float("nan")
    try:
        return float(raw)
    except (ValueError, TypeError):
        raise ContractViolation(
            SOURCE_ID, f"{well}: {field} {raw!r} is not numeric — refusing to guess"
        ) from None


def _coords(feature: dict, attrs: dict, well: str) -> tuple[float, float]:
    """(lat, lon): geometry preferred; DD string fields are the fallback
    (they are strings, differ in the 4th decimal, and can be null when the
    geometry is present); both absent → missing, row kept."""
    geometry = feature.get("geometry") or {}
    if geometry.get("x") is not None and geometry.get("y") is not None:
        return (
            _float_or_missing(geometry["y"], well, "geometry.y"),
            _float_or_missing(geometry["x"], well, "geometry.x"),
        )
    return (
        _float_or_missing(_require(attrs, "TOPHOLEYDD", well), well, "TOPHOLEYDD"),
        _float_or_missing(_require(attrs, "TOPHOLEXDD", well), well, "TOPHOLEXDD"),
    )


def _check_page(payload: dict) -> list[dict]:
    """ArcGIS page → feature list. ArcGIS reports failures as HTTP 200 with
    an ``error`` body — that is a source failure, never an empty page."""
    if not isinstance(payload, dict) or "error" in payload:
        err = payload.get("error", {}) if isinstance(payload, dict) else {}
        raise SourceUnavailable(
            SOURCE_ID,
            f"ArcGIS error body: code={err.get('code')!r} message={err.get('message')!r}",
        )
    features = payload.get("features")
    if not isinstance(features, list):
        raise SourceUnavailable(SOURCE_ID, "payload has no 'features' list")
    return features


def normalize(pages: Sequence[dict]) -> pd.DataFrame:
    """ArcGIS query page payloads → tidy nsta_wells frame. Pure.

    Zero features across all pages raises — an empty-but-fresh label table
    is a poisoned label table (§0 rule 4). Rows are never dropped except
    hard duplicates (identical payload, same PK); missing values stay
    missing; sentinels become explicit values (FLOWCLASS null → ``""``,
    TARGETFLD "No Data Available" → None) per the module docstring.
    """
    features: list[dict] = []
    for payload in pages:
        features.extend(_check_page(payload))
    if not features:
        raise SourceUnavailable(
            SOURCE_ID, "zero E&A wellbores — refusing to write an empty-but-fresh table"
        )

    records: list[dict] = []
    years: list[int | None] = []
    for feature in features:
        attrs = feature.get("attributes") or {}
        well = attrs.get("WELLREGNO")
        if not well:
            raise ContractViolation(
                SOURCE_ID, f"feature without WELLREGNO (attributes={sorted(attrs)!r})"
            )
        purpose_raw = _require(attrs, "ORIGINTENT", well)
        if purpose_raw not in PURPOSE_MAP:
            raise ContractViolation(
                SOURCE_ID,
                f"{well}: ORIGINTENT {purpose_raw!r} outside the WHERE-pinned "
                "vocabulary {'Exploration','Appraisal'} — server-side drift",
            )
        flowclass = _require(attrs, "FLOWCLASS", well)
        target_field = _require(attrs, "TARGETFLD", well)
        lat, lon = _coords(feature, attrs, well)
        years.append(_spud_year(_require(attrs, "SPUDDATE", well), well))
        td_m = _float_or_missing(_require(attrs, "TDTVDSSM", well), well, "TDTVDSSM")
        if td_m < 0:  # NaN < 0 is False — missing stays missing
            # 25/5,129 records use the negative-down (elevation) convention;
            # corroborated sign-flip, see module docstring.
            td_m = -td_m
        records.append(
            {
                "well_id": f"{SOURCE_ID}:{well}",
                "lat": lat,
                "lon": lon,
                "purpose_raw": str(purpose_raw),
                # Carbon-storage registrations are CO2 probes, not petroleum
                # exploration — "other" regardless of ORIGINTENT (docstring).
                "purpose": "other" if CS_REGNO.match(well) else PURPOSE_MAP[purpose_raw],
                "content_raw": "" if flowclass is None else str(flowclass),
                "td_m": td_m,
                "discovery_id": (
                    None
                    if target_field is None or target_field == NO_DATA_SENTINEL
                    else str(target_field)
                ),
            }
        )

    df = pd.DataFrame.from_records(records)
    df["spud_year"] = pd.array(years, dtype="Int64")
    df = df[
        [
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
    ]
    # Hard duplicates only (pagination overlap re-serves identical rows);
    # a PK repeated with CONFLICTING payload survives here and fails
    # SCHEMA's unique=["well_id"] — surfaced, never silently resolved.
    return df.drop_duplicates().reset_index(drop=True)


def fetch(page_size: int = PAGE_SIZE) -> FetchResult:
    """Paginate the E&A query (resultOffset, OBJECTID-ordered for stable
    pages) until ``exceededTransferLimit`` clears; normalize all pages."""
    pages: list[dict] = []
    offset = 0
    for _ in range(MAX_PAGES):
        resp = http_get(
            QUERY_URL,
            SOURCE_ID,
            params={
                "where": WHERE,
                "outFields": ",".join(REQUEST_FIELDS),
                "orderByFields": "OBJECTID",
                "resultOffset": offset,
                "resultRecordCount": page_size,
                "f": "json",
            },
            timeout=120.0,
        )
        try:
            payload = resp.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise SourceUnavailable(SOURCE_ID, f"{QUERY_URL} returned non-JSON: {exc}") from exc
        features = _check_page(payload)
        pages.append(payload)
        if payload.get("exceededTransferLimit") and features:
            offset += len(features)
            continue
        break
    else:
        raise SourceUnavailable(
            SOURCE_ID,
            f"pagination did not terminate after {MAX_PAGES} pages "
            "(server ignoring resultOffset?) — refusing a possibly-partial table",
        )
    return FetchResult(frame=normalize(pages), source_url=QUERY_URL)
