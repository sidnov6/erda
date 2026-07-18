"""gem_infra — GEM oil/gas pipelines + LNG terminals (GOIT + GGIT-LNG), Layer 3.

Context layer for distance-to-infrastructure queries: a decimated point set
per pipeline and one point per LNG terminal unit. NOT the full route
geometry — see the decimation note below before using this table for
anything but proximity/density work.

Release + endpoint (live-verified 2026-07-19, HTTP 200):
    Open bucket https://publicgemdata.nyc3.cdn.digitaloceanspaces.com/ —
    files are release-versioned and ROTATE by release, and old releases
    linger beside new ones (goit_map_2025-03 and goit_map_2026-06 are both
    live today). fetch() therefore lists the bucket (?prefix=interim_maps/)
    every run and picks the LATEST key per tracker by the YYYY-MM suffix;
    it never hardcodes a filename. Current at verification:

    - goit_map_2026-06.geojson      211,894,140 bytes — Global Oil
      Infrastructure Tracker: oil AND NGL pipelines (fuel "Oil" 1,317 /
      "NGL" 239 in this release; tracker-display uniformly "Oil pipeline").
      Both map to kind ``oil_pipeline`` — the table has no fuel column, and
      the NGL inclusion is documented here rather than invented into a
      fifth kind.
    - ggit-lng_map_2025-11.geojson  196,079,995 bytes — Global Gas
      Infrastructure Tracker map: gas pipelines (fuel "Gas", line
      geometries) AND LNG terminal units (Point features, facility-type
      "import"/"export" → kinds ``lng_import``/``lng_export``).

    GEM publishes NO refineries tracker — verified against the full live
    bucket listing 2026-07-19. Do not look for one; refinery proximity is
    out of scope for this source.

Size/memory note: these files are huge (~200 MB each). fetch() streams each
object to ``data/raw/<filename>`` (1 MiB chunks, .part tmp + atomic rename,
byte-size check against the listing's authoritative Size) and reuses an
existing byte-size-identical local copy instead of re-pulling ~400 MB per
run. Parsing is a single ``json.load`` per file — ``ijson`` is not in the
dependency set, and peak RSS of ~1–2 GB is acceptable for this quarterly
one-shot batch job. The raw artifacts stay under data/raw/ for provenance.

Decimation (documented, load-bearing): pipeline geometries carry hundreds
of thousands of vertices (1.8M+ across kept gas pipelines alone). Each
feature's coordinates are flattened (MultiLineString parts concatenated in
order) and sampled every 50th vertex, PLUS the final vertex so pipeline
termini survive. One row per sampled vertex; ``vertex_idx`` is the ordinal
of the sampled vertex within its (kind, project_id) group — a running
counter across a project's units, NOT the index into the original
polyline. This is a representative point set for distance queries, not the
route geometry.

Filters + quirks (observed across both full releases, 2026-07-19):

- status filter: only ``operating`` and ``construction`` rows are kept
  (dropped verbatim statuses in these releases: proposed, cancelled,
  shelved, retired, mothballed, idled, "mixed status"). Zero surviving
  rows → ContractViolation, never an empty-but-fresh table.
- ``start-year``: 4-digit string, ``""`` (missing → pd.NA, never 0), or —
  on five operating gas pipelines — a phased-commissioning range
  ("2013-2017", "2020-2021") → the FIRST year (earliest in-service), or
  "Before 2024" → pd.NA (an upper bound is not a start year). Any other
  form raises; nothing is guessed.
- 4 of 1,198 Point features in ggit-lng_map_2025-11 have a blank
  facility-type (e.g. Klaipeda Small-Scale LNG Terminal) and cannot be
  classified into the kind enum without inventing a fact — they are
  skipped and counted, with a drift guard: more than
  ``UNCLASSIFIABLE_TOLERANCE`` such skips raises ContractViolation.
- multi-country pipelines keep GEM's verbatim ``country-area1`` label
  (e.g. "Russia, Mongolia, China").
- provenance: FetchResult.source_url is the bucket listing URL (the only
  stable entry point across rotating filenames). kind → object mapping is
  deterministic: ``oil_pipeline`` rows come from the goit_map_* object,
  everything else from ggit-lng_map_*; exact release filenames are the
  ones under data/raw/ at the retrieved_at timestamp.
"""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import httpx
import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_ingestion.base import BROWSER_UA, FetchResult, http_get

SOURCE_ID = "gem_infra"
TRANSFORM_VERSION = "gem_infra:1.0.0"
TABLE = "gem_infra"

BUCKET_URL = "https://publicgemdata.nyc3.cdn.digitaloceanspaces.com/"
LISTING_URL = BUCKET_URL + "?prefix=interim_maps/"

#: The two release-versioned map objects this connector consumes.
TRACKERS = ("goit", "ggit-lng")

_KEY_RE = re.compile(r"^interim_maps/(goit|ggit-lng)_map_(\d{4}-\d{2})\.geojson$")

#: Only in-service or being-built infrastructure enters the table.
KEPT_STATUSES = ("operating", "construction")

#: Pipeline decimation stride (see module docstring). ~90k rows total from
#: ~2.5M raw vertices in the 2026-06/2025-11 releases.
VERTEX_STRIDE = 50

#: Blank-facility-type Point skips allowed per ggit-lng release before the
#: quirk is treated as vocabulary drift (4 observed in 2025-11).
UNCLASSIFIABLE_TOLERANCE = 10

KINDS = ["oil_pipeline", "gas_pipeline", "lng_import", "lng_export"]

_YEAR_RANGE_RE = re.compile(r"^(\d{4})\s*[-–]\s*\d{4}$")
_YEAR_BEFORE_RE = re.compile(r"^[Bb]efore\s+\d{4}$")

SCHEMA = pa.DataFrameSchema(
    {
        "kind": pa.Column(str, pa.Check.isin(KINDS), nullable=False),
        "project_id": pa.Column(str, pa.Check.str_length(min_value=1), nullable=False),
        "name": pa.Column(str, nullable=False),
        "status": pa.Column(str, pa.Check.isin(list(KEPT_STATUSES)), nullable=False),
        "country": pa.Column(str, nullable=False),
        # Nullable Int64: empty start-year stays missing, never 0 (§0 rule 4).
        "start_year": pa.Column("Int64", pa.Check.in_range(1800, 2100), nullable=True),
        "vertex_idx": pa.Column("int64", pa.Check.ge(0), nullable=False),
        "lat": pa.Column(float, pa.Check.in_range(-90, 90), nullable=False),
        "lon": pa.Column(float, pa.Check.in_range(-180, 180), nullable=False),
    },
    unique=["kind", "project_id", "vertex_idx"],
)


@dataclass(frozen=True)
class ReleaseFile:
    """One current map object resolved from the bucket listing."""

    key: str  # e.g. "interim_maps/goit_map_2026-06.geojson"
    size: int  # bytes, from the listing — authoritative for the reuse check
    release: str  # e.g. "2026-06"


def resolve_current_files(listing_xml: str) -> dict[str, ReleaseFile]:
    """S3-style listing XML → latest ReleaseFile per tracker.

    Old releases linger in the bucket beside new ones, so "latest" is the
    max YYYY-MM suffix per tracker (ISO year-month sorts lexicographically).
    A missing tracker or a truncated listing is a source failure.
    """
    try:
        root = ET.fromstring(listing_xml)
    except ET.ParseError as exc:
        raise SourceUnavailable(SOURCE_ID, f"bucket listing is not parseable XML: {exc}") from exc

    for el in root.iter():
        if el.tag.endswith("IsTruncated") and (el.text or "").strip().lower() == "true":
            raise SourceUnavailable(
                SOURCE_ID, "bucket listing is truncated — latest-release pick would be unreliable"
            )

    best: dict[str, ReleaseFile] = {}
    for contents in root.iter():
        if not contents.tag.endswith("Contents"):
            continue
        key = size = None
        for child in contents:
            if child.tag.endswith("Key"):
                key = child.text or ""
            elif child.tag.endswith("Size"):
                size = int(child.text or "0")
        match = _KEY_RE.match(key or "")
        if not match or size is None:
            continue
        tracker, release = match.group(1), match.group(2)
        if tracker not in best or release > best[tracker].release:
            best[tracker] = ReleaseFile(key=key, size=size, release=release)

    missing = [t for t in TRACKERS if t not in best]
    if missing:
        raise SourceUnavailable(
            SOURCE_ID, f"no {missing} map object in bucket listing — naming scheme drifted?"
        )
    return best


def _parse_start_year(raw: object, project_id: str) -> int | None:
    """'1982' → 1982; '' → None; '2013-2017' → 2013; 'Before 2024' → None.

    The range form is a phased in-service window on five operating gas
    pipelines (observed live 2026-07-19) — the first year is the earliest
    year the project was in service, not an invention. "Before YYYY" is an
    upper bound, not a start year → missing. Anything else raises.
    """
    text = str(raw).strip() if raw is not None else ""
    if text == "":
        return None
    if len(text) == 4 and text.isdigit():
        return int(text)
    range_match = _YEAR_RANGE_RE.match(text)
    if range_match:
        return int(range_match.group(1))
    if _YEAR_BEFORE_RE.match(text):
        return None
    raise ContractViolation(
        SOURCE_ID, f"{project_id}: unparseable start-year {raw!r} — refusing to guess"
    )


def _flatten_line(geometry: dict, project_id: str) -> list[list[float]]:
    """LineString/MultiLineString → flat [lon, lat] vertex list, order kept."""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if gtype == "LineString":
        flat = list(coords)
    elif gtype == "MultiLineString":
        flat = [vertex for part in coords for vertex in part]
    else:
        raise ContractViolation(
            SOURCE_ID, f"{project_id}: pipeline geometry is {gtype!r}, expected a line"
        )
    if not flat:
        raise ContractViolation(SOURCE_ID, f"{project_id}: pipeline has no coordinates")
    return flat


def _sample_vertices(flat: list[list[float]]) -> list[list[float]]:
    """Every VERTEX_STRIDE-th vertex, plus the final vertex (pipeline terminus)."""
    picked = list(range(0, len(flat), VERTEX_STRIDE))
    if picked[-1] != len(flat) - 1:
        picked.append(len(flat) - 1)
    return [flat[i] for i in picked]


def _classify(tracker: str, props: dict, geometry: dict) -> str | None:
    """Feature → kind, or None for the documented blank-facility-type quirk."""
    if tracker == "goit":
        # Whole tracker is "Oil pipeline" (fuel Oil or NGL — docstring note).
        return "oil_pipeline"
    facility = str(props.get("facility-type") or "").strip().lower()
    if facility == "import":
        return "lng_import"
    if facility == "export":
        return "lng_export"
    if str(props.get("fuel") or "").strip() == "Gas":
        return "gas_pipeline"
    if geometry.get("type") == "Point" and facility == "":
        return None  # known 2025-11 quirk: terminal unit with blank facility-type
    raise ContractViolation(
        SOURCE_ID,
        f"{props.get('project-id')!r}: unclassifiable feature "
        f"(facility-type={props.get('facility-type')!r}, fuel={props.get('fuel')!r}, "
        f"geometry={geometry.get('type')!r})",
    )


def normalize(payload: dict, tracker: str) -> pd.DataFrame:
    """One tracker's GeoJSON FeatureCollection → tidy gem_infra rows. Pure.

    Failure semantics (§0 rule 4): a payload that is not a FeatureCollection,
    has zero features, or has zero operating/construction features raises —
    never an empty-but-fresh table. Malformed features raise ContractViolation;
    the only sanctioned skips are non-kept statuses (the documented filter)
    and the counted blank-facility-type quirk (see module docstring).
    """
    if tracker not in TRACKERS:
        raise ValueError(f"unknown tracker {tracker!r}; expected one of {TRACKERS}")
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        raise SourceUnavailable(
            SOURCE_ID, f"{tracker}: payload is not a GeoJSON FeatureCollection"
        )
    if not features:
        raise SourceUnavailable(
            SOURCE_ID, f"{tracker}: zero features — refusing an empty-but-fresh table"
        )

    records: list[dict] = []
    years: list[int | None] = []
    vertex_counter: dict[tuple[str, str], int] = {}
    unclassifiable = 0

    for feature in features:
        props = feature.get("properties") or {}
        project_id = str(props.get("project-id") or "").strip()
        if not project_id:
            raise ContractViolation(
                SOURCE_ID, f"{tracker}: feature without project-id (name={props.get('name')!r})"
            )
        status = str(props.get("status") or "").strip()
        if status not in KEPT_STATUSES:
            continue  # documented filter: context layer keeps real steel only

        geometry = feature.get("geometry") or {}
        kind = _classify(tracker, props, geometry)
        if kind is None:
            unclassifiable += 1
            continue

        start_year = _parse_start_year(props.get("start-year"), project_id)
        base = {
            "kind": kind,
            "project_id": project_id,
            "name": str(props.get("name") or ""),
            "status": status,
            "country": str(props.get("country-area1") or ""),
        }

        if kind in ("lng_import", "lng_export"):
            # Terminals: one row per unit from the Latitude/Longitude props
            # (floats, verbatim equal to the Point geometry across the full
            # 2025-11 release — checked live).
            try:
                lat = float(props["Latitude"])
                lon = float(props["Longitude"])
            except (KeyError, TypeError, ValueError):
                raise ContractViolation(
                    SOURCE_ID,
                    f"{project_id}: terminal without usable Latitude/Longitude "
                    f"({props.get('Latitude')!r}, {props.get('Longitude')!r})",
                ) from None
            points = [[lon, lat]]
        else:
            points = _sample_vertices(_flatten_line(geometry, project_id))

        for lon_lat in points:
            group = (kind, project_id)
            idx = vertex_counter.get(group, 0)
            vertex_counter[group] = idx + 1
            records.append(
                {
                    **base,
                    "vertex_idx": idx,
                    "lat": float(lon_lat[1]),  # GeoJSON order is [lon, lat]
                    "lon": float(lon_lat[0]),
                }
            )
            years.append(start_year)

    if unclassifiable > UNCLASSIFIABLE_TOLERANCE:
        raise ContractViolation(
            SOURCE_ID,
            f"{tracker}: {unclassifiable} unclassifiable features exceeds the "
            f"pinned tolerance of {UNCLASSIFIABLE_TOLERANCE} — facility-type drifted?",
        )
    if not records:
        raise ContractViolation(
            SOURCE_ID,
            f"{tracker}: no {'/'.join(KEPT_STATUSES)} features — status vocabulary drifted?",
        )

    df = pd.DataFrame.from_records(records)
    df["start_year"] = pd.array(years, dtype="Int64")
    df["vertex_idx"] = df["vertex_idx"].astype("int64")
    columns = ["kind", "project_id", "name", "status", "country", "start_year"]
    return df[[*columns, "vertex_idx", "lat", "lon"]]


def _download(url: str, dest: Path, expected_size: int, *, retries: int = 3) -> None:
    """Stream a huge object to disk: .part tmp, size check, atomic rename."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with httpx.stream(
                "GET",
                url,
                headers={"User-Agent": BROWSER_UA},
                timeout=httpx.Timeout(30.0, read=600.0),
                follow_redirects=True,
            ) as resp:
                resp.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_bytes(1 << 20):
                        fh.write(chunk)
            actual = tmp.stat().st_size
            if actual != expected_size:
                raise SourceUnavailable(
                    SOURCE_ID, f"{url}: truncated download ({actual} of {expected_size} bytes)"
                )
            tmp.replace(dest)
            return
        except httpx.HTTPError as exc:  # connection resets are real on these objects
            last = exc
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
        finally:
            tmp.unlink(missing_ok=True)
    raise SourceUnavailable(SOURCE_ID, f"{url} → {last}")


def fetch(raw_dir: Path | str = Path("data/raw")) -> FetchResult:
    """List the bucket, resolve current releases, download/reuse, normalize.

    A local copy under ``raw_dir`` whose byte size equals the listing's
    authoritative Size is reused instead of re-pulling ~400 MB; any
    mismatch (partial download, replaced release) triggers a fresh
    streamed download. See the module docstring for the memory note.
    """
    raw_dir = Path(raw_dir)
    listing = http_get(LISTING_URL, SOURCE_ID)
    current = resolve_current_files(listing.text)
    frames = []
    for tracker in TRACKERS:
        release_file = current[tracker]
        url = BUCKET_URL + release_file.key
        local = raw_dir / Path(release_file.key).name
        if not (local.exists() and local.stat().st_size == release_file.size):
            _download(url, local, release_file.size)
        try:
            payload = json.loads(local.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SourceUnavailable(SOURCE_ID, f"{local} is not valid JSON: {exc}") from exc
        frames.append(normalize(payload, tracker))
        del payload  # cap peak memory between the two ~200 MB parses
    frame = pd.concat(frames, ignore_index=True)
    return FetchResult(frame=frame, source_url=LISTING_URL)
