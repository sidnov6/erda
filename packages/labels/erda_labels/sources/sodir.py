"""sodir — Norwegian Offshore Directorate FactPages exploration wellbores (spec §5).

Endpoint (registry-verified 2026-07-18): the SSRS CSV export
``wellbore_exploration_all`` on factpages.sodir.no. The query string is a
literal-ampersand SSRS report path (``?/Factpages/external/tableview/…&rs:…``),
NOT standard ``key=value`` pairs — it must be passed as one exact URL string,
never split into an httpx ``params`` dict (verified byte-identical through
httpx on 2026-07-18). Legacy npdfactpages paths 404. Live download 2026-07-18:
2,197 wellbores, 87 columns (registry sweep noted 85 — additions are
tolerated; columns are selected by name), UTF-8 with BOM, CRLF.

Column mapping (pre-harmonize standard):

- ``well_id``      = ``"sodir:" + wlbWellboreName`` (unique across all 2,197
  rows on 2026-07-18; sidetracks carry their own names, e.g. ``2/1-13 S``).
- ``lat``/``lon``  = ``wlbNsDecDeg``/``wlbEwDecDeg`` decimal degrees, 100%
  populated live. DATUM NOTE: ``wlbGeodeticDatum`` says ED50 on 2,195/2,197
  rows (2 blank) — the ED50→WGS84 shift on the Norwegian shelf is ~100–200 m,
  far below both the 0.05° model grid and harmonize's 3-decimal dedupe
  precision. Documented here and in the dataset card, NOT transformed.
- ``spud_year``    = year of ``wlbEntryDate`` (rig entry, ``DD.MM.YYYY``; the
  registry's designated spud proxy). 53 blanks live stay missing (Int64 NA) —
  harmonize drops-and-counts them downstream, this connector never does.
- ``purpose_raw``  = ``wlbPurpose`` verbatim (after padding strip).
- ``purpose``      — documented mapping over the values observed live on
  2026-07-18 (counts in parens; legal values per the FactPages attribute
  documentation, https://factpages.sodir.no/en/wellbore/Attributes):

  * wildcat   — ``WILDCAT`` (1,434).
  * appraisal — ``APPRAISAL`` (758).
  * other     — ``WILDCAT-CCS`` (2) and ``APPRAISAL-CCS`` (2): CO2-storage
    exploration wells probing saline aquifers/depleted structures for CO2
    injection, NOT petroleum exploration — counting them as petroleum
    wildcats would poison the labels (their legal content value is WATER).
    Also ``""`` (1 blank, wellbore 35/11-27 A, not yet classified at
    retrieval time).

  Any purpose outside this enumeration RAISES ContractViolation — a new
  exploration variant silently classified "other" would silently shrink the
  wildcat set. Nothing is filtered here: purpose="other" rows stay; harmonize
  selects wildcats later.
- ``content_raw``  = ``wlbContent`` verbatim after stripping the export's
  trailing varchar padding; blanks (63 live) become ``""`` and get an
  explicit excluded-class row in data/curated/outcome_map.d/sodir.csv —
  never guessed. All 15 observed values are mapped there.
- ``td_m``         = ``wlbTotalDepth`` (measured depth, metres; 58 blanks
  live stay missing).
- ``discovery_id`` = ``"sodir:" + dscNpdidDiscovery + ":" + wlbDiscovery``
  (stable numeric surrogate key + human name, e.g.
  ``sodir:43814:1/2-1 Blane``). Verified live 2026-07-18: the two fields are
  always jointly present or jointly blank (1,389 present / 808 blank);
  jointly blank → missing.

Whitespace: this SSRS export pads many varchar fields with trailing spaces
(e.g. ``'CAMPANIAN           '``); every text field is stripped before use.

Rows are never dropped except full-row hard duplicates by PK; conflicting
duplicates (same wellbore name, different data) survive to fail the schema's
uniqueness check loudly. Zero data rows raise SourceUnavailable — no
empty-but-fresh label tables (§0 rule 4).
"""

from __future__ import annotations

import io

import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_ingestion.base import FetchResult, http_get

SOURCE_ID = "sodir"
TRANSFORM_VERSION = "sodir:1.0.0"
TABLE = "sodir_wells"

#: Literal-ampersand SSRS report query — pass EXACTLY as one string; the part
#: after ``?`` is a report path + ``rs:``/``rc:`` directives, not key=value
#: params. httpx preserves it byte-identically (verified 2026-07-18).
EXPORT_URL = (
    "https://factpages.sodir.no/public"
    "?/Factpages/external/tableview/wellbore_exploration_all"
    "&rs:Command=Render&rc:Toolbar=false&rc:Parameters=f&rs:Format=CSV"
    "&Top100=false&IpAddress=not_used&CultureCode=en"
)

#: Attribute documentation for wlbPurpose/wlbContent legal values — the
#: citation used by data/curated/outcome_map.d/sodir.csv.
ATTRIBUTES_URL = "https://factpages.sodir.no/en/wellbore/Attributes"

#: wlbPurpose → purpose. Complete over the values observed live 2026-07-18
#: (see module docstring); an unlisted value raises, never defaults.
PURPOSE_MAP = {
    "WILDCAT": "wildcat",
    "APPRAISAL": "appraisal",
    "WILDCAT-CCS": "other",  # CO2-storage exploration, not petroleum
    "APPRAISAL-CCS": "other",  # CO2-storage appraisal, not petroleum
    "": "other",  # 1 not-yet-classified wellbore live
}

#: Source columns this connector reads; absence of any means the endpoint did
#: not return the export we asked for (or it drifted) — SourceUnavailable.
REQUIRED_SOURCE_COLUMNS = [
    "wlbWellboreName",
    "wlbNsDecDeg",
    "wlbEwDecDeg",
    "wlbEntryDate",
    "wlbPurpose",
    "wlbContent",
    "wlbTotalDepth",
    "wlbDiscovery",
    "dscNpdidDiscovery",
]

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
        "well_id": pa.Column(str, pa.Check.str_startswith("sodir:"), nullable=False),
        # ED50, noted-not-transformed (module docstring). 100% populated live;
        # a future blank coordinate stays a null value — never a dropped row.
        "lat": pa.Column(float, pa.Check.in_range(-90, 90), nullable=True),
        "lon": pa.Column(float, pa.Check.in_range(-180, 180), nullable=True),
        # NCS drilling starts 1966; harmonize applies its own 1900 floor.
        "spud_year": pa.Column("Int64", pa.Check.in_range(1900, 2100), nullable=True),
        "purpose_raw": pa.Column(str, nullable=False),
        "purpose": pa.Column(str, pa.Check.isin(["wildcat", "appraisal", "other"]), nullable=False),
        "content_raw": pa.Column(str, nullable=False),
        "td_m": pa.Column(float, pa.Check.ge(0), nullable=True),
        "discovery_id": pa.Column(str, nullable=True),
    },
    unique=["well_id"],
)


def _numeric(series: pd.Series, name: str) -> pd.Series:
    """Blank → missing; anything unparseable raises, never guessed."""
    try:
        return pd.to_numeric(series.replace("", None), errors="raise").astype(float)
    except (ValueError, TypeError) as exc:
        raise ContractViolation(SOURCE_ID, f"unparseable numeric in {name}: {exc}") from exc


def normalize(csv_text: str) -> pd.DataFrame:
    """SSRS CSV export text → pre-harmonize well rows. Pure; raises, never guesses.

    - Missing required source columns (e.g. an HTML error body, or a renamed
      export) → SourceUnavailable.
    - Zero data rows → SourceUnavailable: an empty-but-fresh label table is
      §0's worst outcome.
    - Blank wellbore name (the PK) or an unmapped wlbPurpose value →
      ContractViolation.
    - A drifted wlbEntryDate format (not DD.MM.YYYY) → ContractViolation,
      never a coerced-to-missing year.
    """
    # httpx decodes the body but keeps the UTF-8 BOM as a character.
    df = pd.read_csv(io.StringIO(csv_text.lstrip("\ufeff")), dtype=str, keep_default_na=False)

    missing = [c for c in REQUIRED_SOURCE_COLUMNS if c not in df.columns]
    if missing:
        raise SourceUnavailable(
            SOURCE_ID, f"export lacks required columns {missing} — not the report we asked for?"
        )
    if df.empty:
        raise SourceUnavailable(SOURCE_ID, "zero data rows — refusing an empty-but-fresh table")

    # The export pads varchar fields with trailing spaces — strip every field.
    df = df.apply(lambda s: s.str.strip())

    name = df["wlbWellboreName"]
    if (name == "").any():
        raise ContractViolation(
            SOURCE_ID, f"{int((name == '').sum())} rows with blank wlbWellboreName (the PK)"
        )

    unknown = sorted(set(df["wlbPurpose"]) - set(PURPOSE_MAP))
    if unknown:
        raise ContractViolation(
            SOURCE_ID,
            f"unmapped wlbPurpose {unknown} — classify explicitly in PURPOSE_MAP; "
            "silent 'other' could hide new wildcat variants",
        )

    try:
        entered = pd.to_datetime(df["wlbEntryDate"].replace("", None), format="%d.%m.%Y")
    except ValueError as exc:
        raise ContractViolation(
            SOURCE_ID, f"wlbEntryDate not DD.MM.YYYY — format drifted: {exc}"
        ) from exc

    npdid, disc_name = df["dscNpdidDiscovery"], df["wlbDiscovery"]
    has_discovery = (npdid != "") | (disc_name != "")
    discovery_id = ("sodir:" + npdid + ":" + disc_name).where(has_discovery, None)

    out = pd.DataFrame(
        {
            "well_id": "sodir:" + name,
            "lat": _numeric(df["wlbNsDecDeg"], "wlbNsDecDeg"),
            "lon": _numeric(df["wlbEwDecDeg"], "wlbEwDecDeg"),
            "spud_year": entered.dt.year.astype("Int64"),
            "purpose_raw": df["wlbPurpose"],
            "purpose": df["wlbPurpose"].map(PURPOSE_MAP),
            "content_raw": df["wlbContent"],
            "td_m": _numeric(df["wlbTotalDepth"], "wlbTotalDepth"),
            "discovery_id": discovery_id,
        },
        columns=COLUMNS,
    )
    # Hard duplicates only: identical rows sharing the PK collapse to one;
    # conflicting rows with the same PK survive to fail the schema's
    # uniqueness check loudly. No other row is ever dropped here.
    return out.drop_duplicates().reset_index(drop=True)


def fetch() -> FetchResult:
    resp = http_get(EXPORT_URL, SOURCE_ID, timeout=120.0)
    return FetchResult(frame=normalize(resp.text), source_url=EXPORT_URL)
