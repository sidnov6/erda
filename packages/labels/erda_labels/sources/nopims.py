"""nopims — Australia NOPIMS wells: NOPTA OData joined to NOPTA ArcGIS points (spec §5).

Two open NOPTA endpoints, live-verified 2026-07-18 (mini-VERIFY, this build):

1. OData v4 wells entity (registry-verified): ``well/PublicNopimsWells`` on
   services.neats.nopta.gov.au — 8,910 boreholes, no page cap observed (one
   response). Carries spud (``Kick_Off_Date``), purpose (``Borehole_Reason``),
   TD (``Drillers_TD_m``) — but NO lat/lon and NO outcome.
2. ArcGIS ``Public/Petroleum_Wells`` FeatureServer on arcgis.nopta.gov.au —
   8,031 point features, officially documented on
   https://www.nopta.gov.au/maps-and-public-data/spatial-data.html. Carries
   ``Ubhi`` (the same ``ENO…`` borehole identifier the OData entity uses as
   ``Borehole_ID``), ``Latitude``/``Longitude`` in GDA94 (wkid 4283).
   The spec-era GA layers drifted: www.ga.gov.au/arcgis NOPIMS MapServer is
   dead, and GA's boreholes WFS (services.ga.gov.au/gis/boreholes/ows) has
   coordinates + ENO but still no outcome.

JOIN HYGIENE (live 2026-07-18): inner join on ``Borehole_ID`` = ``Ubhi``, an
exact shared surrogate key — NOT a name join. 8,031/8,910 OData boreholes
matched (90.1%); every ArcGIS feature matched, ``Ubhi`` unique, coordinates
100% populated on matched rows. The 879 unmatched boreholes (mostly onshore
legacy records: 872/879 ``Offshore=No``, largely stratigraphic/water bores)
have NO public coordinates anywhere we could verify — they are EXCLUDED, the
count is reported at build time, and exclusion is the documented honest
alternative to fabricating locations. Conflicting duplicate spatial records
would make the join ambiguous and RAISE.

NO OUTCOME LABELS YET: no open NOPTA/GA service publishes a structured
hydrocarbon-outcome code (checked: OData entity + service doc, NOPTA ArcGIS
fields, GA boreholes WFS ``bh:Boreholes``/``gsmlp:BoreholeView`` — its STATUS
vocabulary is operational: abandoned/suspended/completed…). Australia therefore
contributes wells but no labels: ``content_raw`` is ``""`` for every row, and
data/curated/outcome_map.d/nopims.csv maps ``""`` to an explicit
excluded-class (label 0, shows false) so harmonize never guesses.

Column mapping (pre-harmonize standard):

- ``well_id``      = ``"nopims:" + Borehole_ID`` (``ENO…`` surrogate, unique
  across all 8,910 rows live).
- ``lat``/``lon``  = ArcGIS ``Latitude``/``Longitude``, GDA94. DATUM NOTE:
  GDA94 vs WGS84 differs by <2 m — far below the 0.05° model grid and
  harmonize's 3-decimal dedupe precision; documented, not transformed.
  COVERAGE NOTE: the database includes historical non-Australian records
  drilled under Australian administration or kept as references (49 matched
  rows outside an AU bounding box live: Papua New Guinea wells such as
  Aramia 1, plus two historical US wells, e.g. Daisy Bradford 3 at
  32.39N/−94.87W). Coordinates are kept verbatim — geography is the
  downstream mask's job, never silently edited here.
- ``spud_year``    = year of OData ``Kick_Off_Date`` (ISO YYYY-MM-DD; NOPTA's
  designated spud field per the registry). 413 nulls on matched rows live
  stay missing (Int64 NA) — harmonize drops-and-counts them downstream, this
  connector never does.
- ``purpose_raw``  = ``Borehole_Reason`` verbatim; null → ``""`` (3,832
  matched rows live carry no reason — mostly pre-NOPTA onshore/state legacy
  records).
- ``purpose``      — documented mapping over the values observed live
  2026-07-18 (matched-row counts in parens):

  * wildcat   — ``Exploration`` (1,825). NOPIMS does not split wildcat vs
    extension exploration; every exploration borehole maps to wildcat and the
    dataset card carries that caveat.
  * appraisal — ``Appraisal`` (507).
  * other     — ``Development`` (1,608), ``Stratigraphic Investigation``
    (202), ``Water Supply`` (30), ``Moundspring Investigation`` (23),
    ``Research`` (3), ``Geochemistry`` (1), and ``""`` (null, 3,832).

  Any value outside this enumeration RAISES ContractViolation — a new
  exploration variant silently classified "other" would silently shrink the
  wildcat set. Nothing is filtered by purpose here; harmonize selects
  wildcats later.
- ``content_raw``  = ``""`` for every row (no outcome source — see above).
- ``td_m``         = OData ``Drillers_TD_m`` (metres; 3,085 nulls on matched
  rows live stay missing).
- ``discovery_id`` = missing for every row: NOPIMS publishes no discovery
  identifiers.

Rows are never dropped except (a) full-row hard duplicates by PK and (b) the
documented unmatched-coordinate exclusion above; conflicting OData duplicates
sharing a PK survive to fail the schema's uniqueness check loudly. Zero rows
at any stage raise SourceUnavailable — no empty-but-fresh label tables
(§0 rule 4).
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_ingestion.base import FetchResult, http_get

SOURCE_ID = "nopims"
TRANSFORM_VERSION = "nopims:1.0.0"
TABLE = "nopims_wells"

ODATA_URL = (
    "https://services.neats.nopta.gov.au/odata/v1/public/nopims/well/PublicNopimsWells"
)
#: Exactly the fields normalize() uses; keeps responses small and drift loud.
ODATA_SELECT = (
    "Well_ID,Well,Borehole_ID,Borehole,Kick_Off_Date,Borehole_Reason,"
    "Drillers_TD_m,Offshore,Basin"
)

ARCGIS_URL = (
    "https://arcgis.nopta.gov.au/arcgis/rest/services/Public"
    "/Petroleum_Wells/FeatureServer/0/query"
)
ARCGIS_OUT_FIELDS = "Uwi,Ubhi,BHName,Latitude,Longitude,Purpose,Type,KickOffDate"
#: Server maxRecordCount is 8000 (live 2026-07-18); we page on
#: exceededTransferLimit rather than trusting the cap to stay put.
ARCGIS_PAGE_SIZE = 8000

#: Both endpoints answered in one or two pages live; a runaway pagination loop
#: means the endpoint drifted — raise rather than fetch forever.
MAX_PAGES = 100

#: Borehole_Reason → purpose. Complete over the values observed live
#: 2026-07-18 (see module docstring); an unlisted value raises, never defaults.
PURPOSE_MAP = {
    "Exploration": "wildcat",  # NOPIMS has no wildcat/extension split — see docstring
    "Appraisal": "appraisal",
    "Development": "other",
    "Stratigraphic Investigation": "other",
    "Water Supply": "other",
    "Moundspring Investigation": "other",
    "Research": "other",
    "Geochemistry": "other",
    "": "other",  # null Borehole_Reason: legacy records with no stated reason
}

#: Fields normalize() reads from each endpoint; absence means the endpoint
#: did not return what we asked for (or drifted) — SourceUnavailable.
REQUIRED_ODATA_FIELDS = ["Borehole_ID", "Kick_Off_Date", "Borehole_Reason", "Drillers_TD_m"]
REQUIRED_ARCGIS_FIELDS = ["Ubhi", "Latitude", "Longitude"]

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
        "well_id": pa.Column(str, pa.Check.str_startswith("nopims:"), nullable=False),
        # GDA94, noted-not-transformed (module docstring). 100% populated on
        # matched rows live; a future null stays a null value, never a
        # dropped row.
        "lat": pa.Column(float, pa.Check.in_range(-90, 90), nullable=True),
        "lon": pa.Column(float, pa.Check.in_range(-180, 180), nullable=True),
        # Oldest matched spud live is 1921; harmonize applies its own floor.
        "spud_year": pa.Column("Int64", pa.Check.in_range(1900, 2100), nullable=True),
        "purpose_raw": pa.Column(str, nullable=False),
        "purpose": pa.Column(str, pa.Check.isin(["wildcat", "appraisal", "other"]), nullable=False),
        # No outcome source exists (module docstring): every row is "" and the
        # outcome map carries its excluded-class citation. If NOPTA ever
        # publishes outcomes, this check fails loudly and forces re-curation.
        "content_raw": pa.Column(str, pa.Check.isin([""]), nullable=False),
        "td_m": pa.Column(float, pa.Check.ge(0), nullable=True),
        "discovery_id": pa.Column(str, nullable=True),
    },
    unique=["well_id"],
)


def parse_odata_page(payload: dict) -> tuple[list[dict], str | None]:
    """One OData JSON page → (rows, next link). An error body raises.

    OData error responses carry ``{"error": …}`` and no ``value`` key —
    normalizing one into an empty-but-fresh table is §0's worst outcome.
    """
    if "value" not in payload:
        detail = payload.get("error") or "payload has no 'value' key"
        raise SourceUnavailable(SOURCE_ID, f"OData wells: {detail}")
    return payload["value"], payload.get("@odata.nextLink")


def parse_arcgis_page(payload: dict) -> tuple[list[dict], bool]:
    """One ArcGIS query JSON page → (attribute dicts, exceededTransferLimit).

    ArcGIS servers return errors as HTTP 200 with an ``error`` body — that
    must raise, never parse as zero features.
    """
    if "error" in payload:
        raise SourceUnavailable(SOURCE_ID, f"ArcGIS Petroleum_Wells: {payload['error']}")
    if "features" not in payload:
        raise SourceUnavailable(SOURCE_ID, "ArcGIS Petroleum_Wells: payload has no 'features' key")
    attrs = [f.get("attributes", {}) for f in payload["features"]]
    return attrs, bool(payload.get("exceededTransferLimit", False))


def _require_fields(df: pd.DataFrame, required: list[str], endpoint: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SourceUnavailable(
            SOURCE_ID, f"{endpoint} lacks required fields {missing} — endpoint drifted?"
        )


def normalize(odata_rows: list[dict], arcgis_attrs: list[dict]) -> pd.DataFrame:
    """Joined NOPTA rows → pre-harmonize well rows. Pure; raises, never guesses.

    - Zero rows on either side, or zero rows after the join →
      SourceUnavailable (no empty-but-fresh label tables).
    - Blank ``Borehole_ID`` (the PK) → ContractViolation.
    - Conflicting duplicate ArcGIS spatial records (same ``Ubhi``, different
      data) make the join ambiguous → ContractViolation. Conflicting OData
      duplicates survive to fail the schema's uniqueness check loudly.
    - An unmapped ``Borehole_Reason`` or a drifted ``Kick_Off_Date`` format →
      ContractViolation, never a silent default.
    - OData boreholes with no spatial record are EXCLUDED (the documented
      879-row coordinate gap, module docstring) — the only non-duplicate rows
      this connector ever removes.
    """
    if not odata_rows:
        raise SourceUnavailable(SOURCE_ID, "OData wells returned zero rows")
    if not arcgis_attrs:
        raise SourceUnavailable(SOURCE_ID, "ArcGIS Petroleum_Wells returned zero features")

    wells = pd.DataFrame(odata_rows)
    points = pd.DataFrame(arcgis_attrs)
    _require_fields(wells, REQUIRED_ODATA_FIELDS, "OData wells")
    _require_fields(points, REQUIRED_ARCGIS_FIELDS, "ArcGIS Petroleum_Wells")

    # Hard duplicates only: identical records collapse to one. Conflicting
    # OData rows sharing Borehole_ID survive to fail schema uniqueness.
    wells = wells.drop_duplicates(subset=REQUIRED_ODATA_FIELDS).reset_index(drop=True)
    points = points.drop_duplicates(subset=REQUIRED_ARCGIS_FIELDS).reset_index(drop=True)

    pk = wells["Borehole_ID"].fillna("")
    if (pk == "").any():
        raise ContractViolation(
            SOURCE_ID, f"{int((pk == '').sum())} OData rows with blank Borehole_ID (the PK)"
        )
    if points["Ubhi"].duplicated().any():
        conflicted = sorted(points.loc[points["Ubhi"].duplicated(), "Ubhi"].dropna().unique())
        raise ContractViolation(
            SOURCE_ID,
            f"conflicting duplicate spatial records for Ubhi {conflicted[:5]} — join ambiguous",
        )

    joined = wells.merge(
        points[["Ubhi", "Latitude", "Longitude"]],
        how="inner",
        left_on="Borehole_ID",
        right_on="Ubhi",
    )
    if joined.empty:
        raise SourceUnavailable(
            SOURCE_ID,
            "zero boreholes matched between OData and ArcGIS — join key drifted? "
            "refusing an empty-but-fresh table",
        )

    reason = joined["Borehole_Reason"].fillna("")
    unknown = sorted(set(reason) - set(PURPOSE_MAP))
    if unknown:
        raise ContractViolation(
            SOURCE_ID,
            f"unmapped Borehole_Reason {unknown} — classify explicitly in PURPOSE_MAP; "
            "silent 'other' could hide new wildcat variants",
        )

    try:
        kicked_off = pd.to_datetime(joined["Kick_Off_Date"], format="%Y-%m-%d")
    except ValueError as exc:
        raise ContractViolation(
            SOURCE_ID, f"Kick_Off_Date not YYYY-MM-DD — format drifted: {exc}"
        ) from exc

    out = pd.DataFrame(
        {
            "well_id": "nopims:" + joined["Borehole_ID"],
            "lat": joined["Latitude"].astype(float),
            "lon": joined["Longitude"].astype(float),
            "spud_year": kicked_off.dt.year.astype("Int64"),
            "purpose_raw": reason,
            "purpose": reason.map(PURPOSE_MAP),
            # No outcome source exists — explicit empty string, mapped as
            # excluded-class in outcome_map.d/nopims.csv (module docstring).
            "content_raw": "",
            "td_m": joined["Drillers_TD_m"].astype(float),
            "discovery_id": pd.Series(None, index=joined.index, dtype=object),
        },
        columns=COLUMNS,
    )
    return out.reset_index(drop=True)


def _fetch_odata_rows() -> list[dict]:
    rows: list[dict] = []
    url: str | None = ODATA_URL
    params: dict | None = {"$select": ODATA_SELECT, "$format": "json"}
    for _ in range(MAX_PAGES):
        if url is None:
            return rows
        resp = http_get(url, SOURCE_ID, params=params, timeout=120.0)
        page, url = parse_odata_page(resp.json())
        rows.extend(page)
        params = None  # @odata.nextLink already carries the query string
    raise SourceUnavailable(SOURCE_ID, f"OData paging exceeded {MAX_PAGES} pages — runaway loop?")


def _fetch_arcgis_attrs() -> list[dict]:
    attrs: list[dict] = []
    for page in range(MAX_PAGES):
        resp = http_get(
            ARCGIS_URL,
            SOURCE_ID,
            params={
                "where": "1=1",
                "outFields": ARCGIS_OUT_FIELDS,
                "returnGeometry": "false",
                "f": "json",
                "resultOffset": str(page * ARCGIS_PAGE_SIZE),
                "resultRecordCount": str(ARCGIS_PAGE_SIZE),
            },
            timeout=120.0,
        )
        page_attrs, exceeded = parse_arcgis_page(resp.json())
        attrs.extend(page_attrs)
        if not exceeded:
            return attrs
    raise SourceUnavailable(SOURCE_ID, f"ArcGIS paging exceeded {MAX_PAGES} pages — runaway loop?")


def fetch() -> FetchResult:
    frame = normalize(_fetch_odata_rows(), _fetch_arcgis_attrs())
    # Provenance carries the label-bearing endpoint; the coordinate join
    # partner (ARCGIS_URL) is documented here and in the module docstring.
    return FetchResult(frame=frame, source_url=ODATA_URL)
