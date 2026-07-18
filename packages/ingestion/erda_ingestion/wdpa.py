"""wdpa — World Database on Protected Areas (Layer 3, spec §12.3). Cadence: per release.

Attribution (LICENSE — non-commercial + attribution, mandatory):
    UNEP-WCMC and IUCN (2026), Protected Planet: The World Database on Protected
    Areas (WDPA), July 2026, Cambridge, UK: UNEP-WCMC and IUCN. www.protectedplanet.net
This dataset is used under the WDPA non-commercial licence; every artefact and any
downstream display must carry the citation above with the release month/year.

Why ERDA ingests it (spec §12.3): offshore exploration blocks must be checked for
overlap with marine protected areas. ERDA needs the actual *polygons*, so the plain
attribute feeds are not enough — this connector consumes the full spatial GDB.

Source (live-verified 2026-07-19, registry: wdpa):
    Open CloudFront bulk, no key:
      https://d1gam3xoknrgr2.cloudfront.net/current/WDPA_<Mon><YYYY>_Public.zip
    A ~1.75 GB File-Geodatabase zip. The <Mon><YYYY> token rotates monthly and only
    the current release is served (previous month → 404), so download_gdb() tries the
    current month then the previous one. The CSV variant (23.8 MB) carries the same
    attributes but NO geometry, so it cannot answer the overlap question — the GDB is
    the only viable path and this module reads it directly.

Two-file design (documented deviation from run_connector, which writes plain parquet):
  1. ``wdpa_areas.parquet`` — a GeoParquet written directly with geopandas, holding the
     marine/coastal polygons (geometry + attributes). This is the artefact the overlap
     check consumes.
  2. ``wdpa_attributes.parquet`` — the attribute-only frame (no geometry) written through
     the normal run_connector path, so provenance + the ledger + freshness all behave
     exactly as for every other source. Its ledger row is the provenance record for the
     sibling GeoParquet, which is stamped with the *same* provenance columns.
  ``run()`` reads the GDB once and produces both; ``fetch()`` is the standalone
  run_connector entrypoint that yields the attribute-only frame.

Schema drift (2026-07 release): the classic ``MARINE`` (0/1/2) and ``WDPAID`` columns are
gone; the release keys sites by ``SITE_ID``/``SITE_PID`` and carries a ``REALM`` column
(Terrestrial / Coastal / Marine). We keep REALM in {Marine, Coastal} and record
``marine = REALM == 'Marine'`` (fully-marine True; coastal/partly-marine False). Grain is
one row per polygon parcel (SITE_PID is the true unique key); a multi-parcel site repeats
its SITE_ID across rows, so ``site_id`` is intentionally NOT unique here.

geopandas/pyogrio are used at runtime. They are not declared in this package's pyproject
(no pyproject edits for this task); they resolve from the shared workspace venv via
erda-labels, which depends on geopandas>=1.0. Imported lazily so the rest of the package
imports without them.
"""

from __future__ import annotations

import zipfile
from datetime import date, timedelta
from pathlib import Path

import httpx
import pandas as pd
import pandera.pandas as pa

from erda_contracts.contracts import attach_provenance
from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_contracts.ledger import LedgerEntry
from erda_contracts.provenance import Provenance
from erda_ingestion.base import BROWSER_UA, FetchResult, run_connector

SOURCE_ID = "wdpa"
TRANSFORM_VERSION = "wdpa:1.0.0"

#: run_connector / ledger table (attribute-only frame + provenance + freshness).
TABLE = "wdpa_attributes"
#: GeoParquet table written directly with geopandas (polygons + attributes).
GEO_TABLE = "wdpa_areas"

CLOUDFRONT_BASE = "https://d1gam3xoknrgr2.cloudfront.net/current"

#: Douglas-Peucker tolerance in DEGREES (data is EPSG:4326). ~0.005° ≈ 500 m at the
#: equator — far below the offshore-block scale the overlap check works at, so it
#: shrinks vertex counts ~15× (live: 337k→21k WKT chars/feature) without moving a
#: coastline enough to matter. preserve_topology keeps rings valid (no self-intersection).
SIMPLIFY_TOLERANCE_DEG = 0.005

#: REALM values kept: fully-marine + coastal (partly-marine) sites. Terrestrial dropped.
KEPT_REALMS = ("Marine", "Coastal")

#: Raw source columns read from the GDB poly layer (also present verbatim in the CSV
#: variant). Order-independent; presence is enforced in normalize().
RAW_COLUMNS = (
    "SITE_ID",
    "NAME",
    "DESIG_ENG",
    "IUCN_CAT",
    "STATUS",
    "STATUS_YR",
    "ISO3",
    "REALM",
)

#: STATUS vocabulary observed live in the 2026-07 release (full-file counts). Pinned so a
#: silent upstream vocabulary change surfaces as ContractViolation instead of slipping by.
KNOWN_STATUSES = (
    "Designated",
    "Established",
    "Proposed",
    "Inscribed",
    "Adopted",
    "Not Reported",
)

#: A truncated/partial cache is not a usable GDB; below this we re-download.
MIN_ZIP_BYTES = 1_000_000_000

_REPO = Path(__file__).resolve().parents[3]
DEFAULT_RAW_ROOT = _REPO / "data" / "raw"
DEFAULT_PARQUET_ROOT = _REPO / "data" / "parquet"

SCHEMA = pa.DataFrameSchema(
    {
        # site_id is NOT unique: a multi-parcel WDPA site repeats it across rows
        # (grain = one polygon parcel; SITE_PID is the true key). No uniqueness check.
        "site_id": pa.Column(str, nullable=False),
        "name": pa.Column(str, nullable=False),
        "desig_eng": pa.Column(str, nullable=False),
        "iucn_cat": pa.Column(str, nullable=False),
        "status": pa.Column(str, pa.Check.isin(KNOWN_STATUSES), nullable=False),
        # 0 is WDPA's "year unknown" sentinel → NA, never a real designation year (§0
        # rule 4: no invented data). Nullable Int64 keeps the gap honest.
        "status_yr": pa.Column("Int64", pa.Check.in_range(1800, 2100), nullable=True),
        # Free string: transboundary sites carry ';'-joined ISO3 (e.g. "MOZ;ZAF"); a
        # 3-char check would false-fail them.
        "iso3": pa.Column(str, nullable=False),
        "marine": pa.Column(bool, nullable=False),
    }
)


def _month_token(d: date) -> str:
    """date → WDPA month token, e.g. 2026-07-19 → 'Jul2026'."""
    return f"{d:%b}{d:%Y}"


def bulk_url(token: str) -> str:
    """CloudFront bulk GDB-zip URL for a month token."""
    return f"{CLOUDFRONT_BASE}/WDPA_{token}_Public.zip"


def _candidate_tokens(asof: date) -> list[str]:
    """Current month then previous — only the live release is served upstream."""
    first_of_month = asof.replace(day=1)
    prev = (first_of_month - timedelta(days=1)).replace(day=1)
    return [_month_token(asof), _month_token(prev)]


def _is_geo(frame: pd.DataFrame) -> bool:
    """True for a geopandas GeoDataFrame, without importing geopandas."""
    return type(frame).__module__.startswith("geopandas")


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    """Raw WDPA rows → tidy marine/coastal frame. Pure; no I/O.

    Accepts a GeoDataFrame (GDB path — geometry simplified and kept) or a plain
    DataFrame (CSV path — geometry absent). Failure semantics (§0 rule 4): a source
    missing a required column, or one that yields zero Marine/Coastal rows, raises —
    it never normalizes into an empty-but-fresh table.
    """
    missing = [c for c in RAW_COLUMNS if c not in raw.columns]
    if missing:
        raise ContractViolation(SOURCE_ID, f"source layer missing columns: {missing}")

    kept = raw.loc[raw["REALM"].isin(KEPT_REALMS)].reset_index(drop=True)
    if kept.empty:
        raise SourceUnavailable(
            SOURCE_ID,
            "no Marine/Coastal rows — REALM vocabulary drifted or wrong layer; "
            "refusing to write an empty-but-fresh table",
        )

    status_yr = pd.to_numeric(kept["STATUS_YR"], errors="coerce").astype("Int64")
    status_yr = status_yr.mask(status_yr == 0)  # 0 = year-unknown sentinel → NA

    out = pd.DataFrame(
        {
            "site_id": kept["SITE_ID"].astype(str),
            "name": kept["NAME"].astype(str),
            "desig_eng": kept["DESIG_ENG"].astype(str),
            "iucn_cat": kept["IUCN_CAT"].astype(str),
            "status": kept["STATUS"].astype(str),
            "status_yr": status_yr,
            "iso3": kept["ISO3"].astype(str),
            "marine": kept["REALM"].eq("Marine"),
        }
    )

    if _is_geo(raw):
        import geopandas as gpd

        geom = kept.geometry.simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)
        if geom.is_empty.any() or geom.isna().any():
            raise ContractViolation(
                SOURCE_ID, f"simplify({SIMPLIFY_TOLERANCE_DEG}) produced empty geometry"
            )
        out = gpd.GeoDataFrame(out, geometry=geom, crs=raw.crs)

    return out


def to_attribute_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop geometry → a plain attribute-only DataFrame for the run_connector path."""
    if _is_geo(frame):
        return pd.DataFrame(frame.drop(columns=frame.geometry.name))
    return frame.copy()


def write_geoparquet(gdf: pd.DataFrame, path: Path) -> Path:
    """Write a GeoDataFrame to GeoParquet (geometry preserved). Requires geopandas."""
    if not _is_geo(gdf):
        raise ContractViolation(SOURCE_ID, "write_geoparquet expects a GeoDataFrame")
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(path)
    return path


def _gdb_vsizip_path(zip_path: Path) -> str:
    """/vsizip/ path to the .gdb directory inside the bulk zip."""
    with zipfile.ZipFile(zip_path) as archive:
        gdbs = sorted({n.split("/")[0] for n in archive.namelist() if ".gdb" in n})
    if len(gdbs) != 1:
        raise SourceUnavailable(SOURCE_ID, f"expected one .gdb in {zip_path}, found {gdbs}")
    return f"/vsizip/{zip_path}/{gdbs[0]}"


def _poly_layer(vsizip_path: str) -> str:
    """Name of the single WDPA_poly_* layer (release-versioned, e.g. WDPA_poly_Jul2026)."""
    import pyogrio

    layers = [row[0] for row in pyogrio.list_layers(vsizip_path)]
    poly = [name for name in layers if name.startswith("WDPA_poly_")]
    if len(poly) != 1:
        raise SourceUnavailable(SOURCE_ID, f"expected one WDPA_poly_* layer, found {layers}")
    return poly[0]


def read_marine_polygons(zip_path: Path) -> pd.DataFrame:
    """Read the marine/coastal polygons from the bulk GDB (filtered at the driver)."""
    import pyogrio

    vsizip = _gdb_vsizip_path(zip_path)
    layer = _poly_layer(vsizip)
    realms = ",".join(f"'{r}'" for r in KEPT_REALMS)
    return pyogrio.read_dataframe(
        vsizip,
        layer=layer,
        columns=list(RAW_COLUMNS),
        where=f"REALM IN ({realms})",
    )


def _download_stream(url: str, dest: Path) -> None:
    """Stream a large file to disk atomically; HTTP failure → SourceUnavailable."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with httpx.stream(
            "GET", url, headers={"User-Agent": BROWSER_UA}, timeout=None, follow_redirects=True
        ) as resp:
            resp.raise_for_status()
            with tmp.open("wb") as fh:
                for chunk in resp.iter_bytes(chunk_size=1 << 20):
                    fh.write(chunk)
    except httpx.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        raise SourceUnavailable(SOURCE_ID, f"{url} → {exc}") from exc
    tmp.replace(dest)


def download_gdb(raw_root: Path = DEFAULT_RAW_ROOT, asof: date | None = None) -> tuple[Path, str]:
    """Ensure the bulk GDB zip is on disk (cache in data/raw); return (path, token).

    Tries the current month then the previous; a usable cache (present + full-size) is
    reused rather than re-fetching 1.75 GB. All candidates failing raises.
    """
    asof = asof or date.today()
    raw_root = Path(raw_root)
    last: str | None = None
    for token in _candidate_tokens(asof):
        dest = raw_root / f"WDPA_{token}_Public.zip"
        if dest.exists() and dest.stat().st_size >= MIN_ZIP_BYTES:
            return dest, token
        url = bulk_url(token)
        try:
            head = httpx.head(
                url, headers={"User-Agent": BROWSER_UA}, timeout=30.0, follow_redirects=True
            )
        except httpx.HTTPError as exc:
            last = f"{url} → {exc}"
            continue
        if head.status_code != 200:
            last = f"{url} → HTTP {head.status_code}"
            continue
        _download_stream(url, dest)
        return dest, token
    raise SourceUnavailable(SOURCE_ID, f"no WDPA bulk for {_candidate_tokens(asof)}: {last}")


def fetch(raw_root: Path = DEFAULT_RAW_ROOT, asof: date | None = None) -> FetchResult:
    """Standalone run_connector entrypoint → attribute-only frame (table wdpa_attributes).

    Downloads (cached) and reads the GDB, then strips geometry. The polygons themselves
    are persisted by run() into the sibling GeoParquet.
    """
    path, token = download_gdb(raw_root, asof)
    normalized = normalize(read_marine_polygons(path))
    return FetchResult(frame=to_attribute_frame(normalized), source_url=bulk_url(token))


def run(
    parquet_root: Path = DEFAULT_PARQUET_ROOT,
    raw_root: Path = DEFAULT_RAW_ROOT,
    asof: date | None = None,
) -> tuple[LedgerEntry, Path]:
    """Full Layer-3 pull: read the GDB once, write both artefacts.

    1. Attribute-only frame → run_connector → wdpa_attributes.parquet + ledger row.
    2. GeoParquet (polygons) → wdpa_areas.parquet, stamped with the SAME provenance as the
       ledger row (so the ledger entry provenances the sibling geometry file too).
    """
    parquet_root = Path(parquet_root)
    path, token = download_gdb(raw_root, asof)
    normalized = normalize(read_marine_polygons(path))
    url = bulk_url(token)
    attributes = to_attribute_frame(normalized)

    entry = run_connector(
        source_id=SOURCE_ID,
        transform_version=TRANSFORM_VERSION,
        schema=SCHEMA,
        fetch=lambda: FetchResult(frame=attributes, source_url=url),
        table=TABLE,
        root=parquet_root,
    )

    prov = Provenance(
        source_id=SOURCE_ID,
        retrieved_at=entry.retrieved_at,
        source_url=entry.source_url,
        transform_version=entry.transform_version,
    )
    geo_path = write_geoparquet(
        attach_provenance(normalized, prov), parquet_root / f"{GEO_TABLE}.parquet"
    )
    return entry, geo_path
