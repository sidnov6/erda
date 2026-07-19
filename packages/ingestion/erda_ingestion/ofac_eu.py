"""ofac_eu — sanctions programs, jurisdiction-level (Layer 3). Cadence: weekly.

.. warning:: **SCOPE — READ BEFORE CONSUMING.** This table is a
   **jurisdiction-level screening signal** for licence-security notes: "does a
   US (OFAC) or EU sanctions programme reference this country?". It is **NOT
   entity-level compliance screening** — it must never be used to clear or
   block a counterparty, and a row does **not** mean the country is under
   comprehensive embargo (the ``program`` column carries the exact authority so
   consumers can distinguish CUBA from a single targeted designation).

Sources (live-verified 2026-07-18/19, see source_registry.yaml):

- **OFAC** sanctions list service, anonymous GET (HEAD not supported; responses
  chunked; content-type historically unreliable — never trusted here):
  ``SDN.CSV`` (19,168 entries live 2026-07-19) + ``CONS_PRIM.CSV`` (480
  non-SDN consolidated entries: SSI, NS-CMIC, HKAA, NS-PLC…). Both are
  headerless 12-column CSVs (ent_num, name, type, program, …) terminated by a
  lone DOS EOF byte (0x1A) line, with ``-0-`` as the in-band null sentinel —
  sentinels never reach the output table. ``ADD.CSV`` exists but is
  deliberately not fetched: it lists entity *addresses*, and an SDN's mailing
  country (commonly AE, TR, GB…) is not a sanctioned-jurisdiction signal.
- **EU FSF** consolidated financial sanctions file, XML with the static public
  access token (``dG9rZW4tMjAxNw``; 403 without it — token kept out of
  provenance URLs per house style). The export is **point-in-time**: root
  ``generationDate`` was 2026-06-05 when pulled on 2026-07-19 (~6 weeks
  stale), so every EU row records it in ``list_generated_at`` and freshness
  claims must be bounded by that date, not by ``retrieved_at``.

Country derivation — explicit dicts only, no substring guessing:

- OFAC program cells hold one or more tokens joined by ``"] ["``
  (e.g. ``UKRAINE-EO13661] [RUSSIA-EO14024``). Each token maps through
  :data:`OFAC_COUNTRY_PROGRAMS` (visible country tokens → iso3) or must be in
  :data:`OFAC_NON_COUNTRY_PROGRAMS` (thematic authorities: SDGT, NPWMD,
  GLOMAG…). An unknown token is upstream drift and raises ContractViolation —
  a silently ignored new country program would corrupt the screen.
- EU ``<regulation programme="…">`` codes are mostly ISO3-like
  (:data:`EU_COUNTRY_PROGRAMMES`); thematic codes
  (:data:`EU_NON_COUNTRY_PROGRAMMES`) are excluded, unknowns raise.
  ``designation_count`` counts distinct ``sanctionEntity`` elements per
  programme.

Judgement calls (all live-inspected 2026-07-19):

- **Ukraine-named programs map to UKR, not RUS.** OFAC UKRAINE-EO13660/61/62/85
  and EU ``UKR`` are "Ukraine-/Russia-related": designees are predominantly
  Russian, but the programmes concern the jurisdiction of Ukraine — EO 13685
  comprehensively embargoes the Crimea *region of Ukraine*, which is exactly
  what a licence-security screen on Ukraine must surface. Russia is
  independently flagged by its own tokens (RUSSIA-EO14024: 6,353 entries).
- **Syria**: OFAC's comprehensive SYRIA program was revoked mid-2025 (absent
  from the live file); SYR still derives from PAARSSR-EO13894 (174 entries,
  Assad-regime designees, live-confirmed Syrian nationals) and HRIT-SY. The
  SYRIA / SYRIA-EO13894 tokens stay in the map in case of reinstatement.
- **SDNZ is a second EU Sudan code** (2024 defence-industry listings,
  entity-inspected) → SDN alongside ``SDN``; RUSDA (Russia destabilising
  activities) → RUS.
- **CMIC-EO13959 → CHN and HKAA → HKG**: targeted investment-prohibition /
  autonomy authorities, not embargoes — but a China/Hong Kong licence note
  should surface them; the program code keeps them distinguishable.
- **Excluded despite having a real geography**: BALKANS (multi-country region,
  no single iso3), IRGC/IFSR/IFCA/561-Related (Iran-specific acronyms with no
  visible country token — IRN is already flagged by ten explicit tokens),
  SSIDES/PAIPA/PEESA (Russia-related acts, RUS already flagged), UHRPA
  (Xinjiang-targeted, 1 entry — mapping it would editorialize CHN from a
  non-visible token), EU UNLI (mixed UN-listing transposals).

Table ``sanctions_programs``: one row per (list_source, program, iso3);
``designation_count`` gives magnitude so consumers can weigh a 6,353-entry
comprehensive program against a single targeted designation. A floor check
guarantees the comprehensively-sanctioned jurisdictions the screen exists for
(CUB, IRN, PRK, SYR, RUS, BLR, VEN) are all present — vanishing coverage is a
loud failure, never a quietly thinner table (§0 rule 4).
"""

from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET

import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import ContractViolation, SourceUnavailable
from erda_ingestion.base import FetchResult, http_get

SOURCE_ID = "ofac_eu"
TRANSFORM_VERSION = "ofac_eu:1.0.0"
TABLE = "sanctions_programs"

OFAC_EXPORT_ROOT = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/"
OFAC_SDN_URL = OFAC_EXPORT_ROOT + "SDN.CSV"
OFAC_CONS_PRIM_URL = OFAC_EXPORT_ROOT + "CONS_PRIM.CSV"

EU_FSF_URL = "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content"
#: Static public FSF access token (base64 of "token-2017"; published by the
#: Commission for file access). 403 without it — live-verified 2026-07-19.
#: Public value, but kept out of provenance URLs per house style (cf. fred).
EU_FSF_TOKEN = "dG9rZW4tMjAxNw"
EU_NS = "{http://eu.europa.ec/fpi/fsd/export}"

#: Provenance string: one fetch spans three endpoints (two OFAC CSVs, one EU XML).
SOURCE_URL = f"{OFAC_SDN_URL} + {OFAC_CONS_PRIM_URL} + {EU_FSF_URL}"

#: Headerless OFAC export layout (SDN.CSV and CONS_PRIM.CSV share it):
#: ent_num, name, type, program, title, call_sign, vess_type, tonnage, grt,
#: vess_flag, vess_owner, remarks. ``-0-`` is OFAC's null sentinel.
OFAC_COLUMN_COUNT = 12
#: Multiple programs in one cell are joined with "] [" — e.g.
#: ``SDGT] [IRGC] [IFSR`` (live 2026-07-19).
OFAC_PROGRAM_JOINER = "] ["

ISO3_NAMES = {
    "AFG": "Afghanistan",
    "BLR": "Belarus",
    "CAF": "Central African Republic",
    "CHN": "China",
    "COD": "Democratic Republic of the Congo",
    "CUB": "Cuba",
    "ETH": "Ethiopia",
    "GIN": "Guinea",
    "GTM": "Guatemala",
    "HKG": "Hong Kong",
    "HTI": "Haiti",
    "IRN": "Iran",
    "IRQ": "Iraq",
    "LBN": "Lebanon",
    "LBY": "Libya",
    "MDA": "Moldova",
    "MLI": "Mali",
    "MMR": "Myanmar",
    "NIC": "Nicaragua",
    "PRK": "North Korea",
    "RUS": "Russia",
    "SDN": "Sudan",
    "SOM": "Somalia",
    "SSD": "South Sudan",
    "SYR": "Syria",
    "TUN": "Tunisia",
    "UKR": "Ukraine",
    "VEN": "Venezuela",
    "YEM": "Yemen",
}

#: OFAC program tokens with a visible country/jurisdiction token → iso3.
#: Every token below was observed in the live 2026-07-19 pull except
#: SYRIA / SYRIA-EO13894 (revoked mid-2025; retained for reinstatement).
OFAC_COUNTRY_PROGRAMS = {
    "BELARUS": "BLR",
    "BELARUS-EO14038": "BLR",
    "BURMA-EO14014": "MMR",
    "CAATSA - IRAN": "IRN",
    "CAATSA - RUSSIA": "RUS",
    "CAR": "CAF",  # Central African Republic (OFAC's own abbreviation)
    "CMIC-EO13959": "CHN",  # Chinese Military-Industrial Complex (investment ban)
    "CUBA": "CUB",
    "CUBA-EO14404": "CUB",
    "DARFUR": "SDN",  # Sudan region
    "DPRK": "PRK",
    "DPRK-NKSPEA": "PRK",
    "DPRK2": "PRK",
    "DPRK3": "PRK",
    "DPRK4": "PRK",
    "DRCONGO": "COD",
    "ETHIOPIA-EO14046": "ETH",
    "HKAA": "HKG",  # Hong Kong Autonomy Act
    "HRIT-IR": "IRN",
    "HRIT-SY": "SYR",
    "IFCA": "IRN",  # Iran Freedom and Counter-Proliferation Act — "I" is Iran
    "IRAN": "IRN",
    "IRAN-CON-ARMS-EO": "IRN",
    "IRAN-EO13846": "IRN",
    "IRAN-EO13871": "IRN",
    "IRAN-EO13876": "IRN",
    "IRAN-EO13902": "IRN",
    "IRAN-HR": "IRN",
    "IRAN-TRA": "IRN",
    "IRAQ2": "IRQ",
    "IRAQ3": "IRQ",
    "LEBANON": "LBN",
    "LIBYA2": "LBY",
    "LIBYA3": "LBY",
    "MALI-EO13882": "MLI",
    "NICARAGUA": "NIC",
    "NICARAGUA-NHRAA": "NIC",
    "PAARSSR-EO13894": "SYR",  # EO 13894 Syria situation; designees live-confirmed Syrian
    "RUSSIA-EO14024": "RUS",
    "RUSSIA-EO14065": "RUS",
    "SOMALIA": "SOM",
    "SOUTH SUDAN": "SSD",
    "SUDAN-EO14098": "SDN",
    "SYRIA": "SYR",  # revoked mid-2025, absent live 2026-07-19; kept for reinstatement
    "SYRIA-EO13894": "SYR",  # legacy tag for EO 13894, absent live 2026-07-19
    "UKRAINE-EO13660": "UKR",  # Ukraine-/Russia-related — see module docstring
    "UKRAINE-EO13661": "UKR",
    "UKRAINE-EO13662": "UKR",
    "UKRAINE-EO13685": "UKR",  # Crimea region embargo
    "VENEZUELA": "VEN",
    "VENEZUELA-EO13850": "VEN",
    "VENEZUELA-EO13884": "VEN",
    "YEMEN": "YEM",
}

#: Thematic / non-single-country OFAC tokens, pinned from the live 2026-07-19
#: sweep so a NEW unknown token (possibly a new country program) surfaces as
#: ContractViolation instead of being silently dropped. Exclusion rationale for
#: the near-miss cases lives in the module docstring.
OFAC_NON_COUNTRY_PROGRAMS = frozenset(
    {
        "561-Related",  # Iran CISADA §561 FFI list — no visible country token
        "BALKANS",  # Western Balkans, multi-country
        "BALKANS-EO14033",
        "CYBER2",
        "CYBER3",
        "CYBER4",
        "ELECTION-EO13848",
        "FTO",
        "GLOMAG",
        "HOSTAGES-EO14078",
        "ICC-EO14203",
        "IFSR",  # Iranian Financial Sanctions Regulations — IRN flagged elsewhere
        "ILLICIT-DRUGS-EO14059",
        "IRGC",  # Iran's IRGC — IRN flagged elsewhere
        "MAGNIT",
        "NPWMD",
        "NS-PLC",  # Palestinian Legislative Council (non-state)
        "PAIPA",
        "PEESA-EO14039",  # Russia pipeline act — RUS flagged elsewhere
        "SDGT",
        "SDNT",
        "SDNTK",
        "SSIDES",  # Ukraine-act designations of Russian persons — RUS flagged elsewhere
        "TCO",
        "UHRPA",  # Xinjiang-targeted — see docstring
    }
)

#: EU FSF programme codes that name a country (mostly ISO3 already).
EU_COUNTRY_PROGRAMMES = {
    "AFG": "AFG",
    "BLR": "BLR",
    "CAF": "CAF",
    "COD": "COD",
    "GIN": "GIN",
    "GTM": "GTM",
    "HTI": "HTI",
    "IRN": "IRN",
    "IRQ": "IRQ",
    "LBY": "LBY",
    "MDA": "MDA",
    "MLI": "MLI",
    "MMR": "MMR",
    "NIC": "NIC",
    "PRK": "PRK",
    "RUS": "RUS",
    "RUSDA": "RUS",  # Russia destabilising activities regime
    "SDN": "SDN",
    "SDNZ": "SDN",  # second Sudan code (2024 defence-industry listings, entity-inspected)
    "SOM": "SOM",
    "SSD": "SSD",
    "SYR": "SYR",
    "TUN": "TUN",
    "UKR": "UKR",  # territorial-integrity regime — see module docstring
    "VEN": "VEN",
    "YEM": "YEM",
}

#: Thematic EU programme codes (pinned live 2026-07-19; unknowns raise).
EU_NON_COUNTRY_PROGRAMMES = frozenset(
    {
        "CHEM",  # chemical weapons
        "CYB",  # cyber-attacks
        "EUAQ",  # EU Al-Qaida list
        "HAM",  # Hamas / PIJ regime
        "HR",  # global human-rights regime
        "TAQA",  # Taliban / Al-Qaida (UN transposition)
        "TERR",  # terrorism (CP 931)
        "UNLI",  # mixed UN-listing transposals (sample: Haiti)
    }
)

#: Jurisdictions the screen exists for — all must be present in every refresh.
COMPREHENSIVE_FLOOR = frozenset({"CUB", "IRN", "PRK", "SYR", "RUS", "BLR", "VEN"})

SCHEMA = pa.DataFrameSchema(
    {
        "iso3": pa.Column(str, pa.Check.str_matches(r"^[A-Z]{3}$"), nullable=False),
        "country_name": pa.Column(str, pa.Check.isin(list(ISO3_NAMES.values())), nullable=False),
        "program": pa.Column(str, pa.Check.str_length(min_value=1), nullable=False),
        "list_source": pa.Column(str, pa.Check.isin(["OFAC", "EU"]), nullable=False),
        "designation_count": pa.Column(int, pa.Check.ge(1), nullable=False),
        # EU rows: the export's point-in-time generationDate (staleness bound).
        # OFAC rows: null — the CSV exports carry no in-band generation date;
        # their freshness is governed by provenance retrieved_at.
        "list_generated_at": pa.Column(
            pd.DatetimeTZDtype(tz="UTC"), nullable=True, coerce=True
        ),
    },
    unique=["list_source", "program", "iso3"],
)


def read_ofac_csv(text: str) -> pd.DataFrame:
    """Headerless OFAC export text → frame of (ent_num, name, sdn_type, programs).

    Tolerates exactly one kind of short row: the lone DOS EOF byte (0x1A) that
    terminates both live files (observed 2026-07-19). Anything else short or
    long is drift and raises.
    """
    rows = []
    for lineno, row in enumerate(csv.reader(io.StringIO(text)), start=1):
        if len(row) == 1 and row[0].strip("\x1a").strip() == "":
            continue  # DOS EOF marker line
        if len(row) != OFAC_COLUMN_COUNT:
            raise ContractViolation(
                SOURCE_ID,
                f"OFAC CSV line {lineno}: expected {OFAC_COLUMN_COUNT} columns, got {len(row)}",
            )
        rows.append((row[0].strip(), row[1].strip(), row[2].strip(), row[3].strip()))
    if not rows:
        raise SourceUnavailable(SOURCE_ID, "OFAC CSV parsed to zero entries")
    return pd.DataFrame(rows, columns=["ent_num", "name", "sdn_type", "programs"])


def split_program_tokens(cell: str) -> list[str]:
    """One OFAC program cell → individual program tokens."""
    return [t.strip() for t in cell.split(OFAC_PROGRAM_JOINER) if t.strip()]


def normalize_ofac(entries: pd.DataFrame) -> pd.DataFrame:
    """OFAC entry frame(s) → country-program rows with designation counts.

    Every token must be either a mapped country program or a pinned thematic
    program; an unknown token raises (it may be a brand-new country program
    the screen must not silently miss).
    """
    counts: dict[str, int] = {}
    unknown: set[str] = set()
    for cell in entries["programs"]:
        for token in split_program_tokens(cell):
            if token in OFAC_COUNTRY_PROGRAMS:
                counts[token] = counts.get(token, 0) + 1
            elif token not in OFAC_NON_COUNTRY_PROGRAMS:
                unknown.add(token)
    if unknown:
        raise ContractViolation(
            SOURCE_ID,
            f"unknown OFAC program tokens (upstream drift, review + pin): {sorted(unknown)}",
        )
    if not counts:
        raise ContractViolation(SOURCE_ID, "no country-program rows derived from OFAC exports")
    out = pd.DataFrame(
        {
            "iso3": [OFAC_COUNTRY_PROGRAMS[t] for t in counts],
            "program": list(counts),
            "designation_count": list(counts.values()),
        }
    )
    out["country_name"] = out["iso3"].map(ISO3_NAMES)
    out["list_source"] = "OFAC"
    out["list_generated_at"] = pd.Series(
        pd.NaT, index=out.index, dtype="datetime64[ns, UTC]"
    )
    return out


def normalize_eu(xml_bytes: bytes) -> pd.DataFrame:
    """EU FSF full-list XML → country-programme rows.

    ``designation_count`` = distinct sanctionEntity elements per programme.
    The export root's ``generationDate`` (point-in-time; ~6 weeks stale at the
    2026-07-19 pull) is recorded on every row as ``list_generated_at``.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise SourceUnavailable(SOURCE_ID, f"EU FSF response is not parseable XML: {exc}") from exc
    if root.tag != EU_NS + "export":
        raise SourceUnavailable(
            SOURCE_ID, f"EU FSF root element is {root.tag!r}, expected FSF <export> — drift?"
        )
    generation_raw = root.get("generationDate")
    if not generation_raw:
        raise ContractViolation(SOURCE_ID, "EU FSF export lacks generationDate attribute")
    generated_at = pd.to_datetime(generation_raw, utc=True)

    entity_counts: dict[str, int] = {}
    unknown: set[str] = set()
    n_entities = 0
    for entity in root.iter(EU_NS + "sanctionEntity"):
        n_entities += 1
        programmes = set()
        for regulation in entity.findall(EU_NS + "regulation"):
            programme = (regulation.get("programme") or "").strip()
            if not programme:
                continue
            if programme in EU_COUNTRY_PROGRAMMES:
                programmes.add(programme)
            elif programme not in EU_NON_COUNTRY_PROGRAMMES:
                unknown.add(programme)
        for programme in programmes:
            entity_counts[programme] = entity_counts.get(programme, 0) + 1
    if unknown:
        raise ContractViolation(
            SOURCE_ID,
            f"unknown EU FSF programme codes (upstream drift, review + pin): {sorted(unknown)}",
        )
    if n_entities == 0:
        raise SourceUnavailable(SOURCE_ID, "EU FSF export contains zero sanctionEntity elements")
    if not entity_counts:
        raise ContractViolation(SOURCE_ID, "no country-programme rows derived from EU FSF export")
    out = pd.DataFrame(
        {
            "iso3": [EU_COUNTRY_PROGRAMMES[p] for p in entity_counts],
            "program": list(entity_counts),
            "designation_count": list(entity_counts.values()),
        }
    )
    out["country_name"] = out["iso3"].map(ISO3_NAMES)
    out["list_source"] = "EU"
    out["list_generated_at"] = generated_at
    return out


def normalize(ofac_entries: pd.DataFrame, eu_xml: bytes) -> pd.DataFrame:
    """Combine both lists into the sanctions_programs table and enforce the floor."""
    frame = pd.concat([normalize_ofac(ofac_entries), normalize_eu(eu_xml)], ignore_index=True)
    missing = COMPREHENSIVE_FLOOR - set(frame["iso3"])
    if missing:
        raise ContractViolation(
            SOURCE_ID,
            "comprehensive-floor jurisdictions absent from derived screen "
            f"(coverage collapsed?): {sorted(missing)}",
        )
    frame = frame.sort_values(["list_source", "iso3", "program"]).reset_index(drop=True)
    return frame[
        ["iso3", "country_name", "program", "list_source", "designation_count", "list_generated_at"]
    ]


def _decode_csv(payload: bytes, url: str) -> str:
    """OFAC CSVs are UTF-8 with BOM; served content-type is unreliable, so the
    bytes are decoded strictly — mojibake must fail, not corrupt names."""
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceUnavailable(SOURCE_ID, f"{url}: response is not UTF-8 CSV ({exc})") from exc


def fetch() -> FetchResult:
    """Download OFAC SDN + consolidated CSVs and the EU FSF XML; normalize.

    GET only — the OFAC service does not answer HEAD (verified 2026-07-18/19).
    """
    sdn_resp = http_get(OFAC_SDN_URL, SOURCE_ID, timeout=120.0)
    cons_resp = http_get(OFAC_CONS_PRIM_URL, SOURCE_ID, timeout=120.0)
    ofac_entries = pd.concat(
        [
            read_ofac_csv(_decode_csv(sdn_resp.content, OFAC_SDN_URL)),
            read_ofac_csv(_decode_csv(cons_resp.content, OFAC_CONS_PRIM_URL)),
        ],
        ignore_index=True,
    )
    eu_resp = http_get(
        EU_FSF_URL, SOURCE_ID, params={"token": EU_FSF_TOKEN}, timeout=180.0
    )
    frame = normalize(ofac_entries, eu_resp.content)
    # Provenance carries the endpoints, never the (public) token param.
    return FetchResult(frame=frame, source_url=SOURCE_URL)
