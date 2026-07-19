"""wgi — World Bank Worldwide Governance Indicators (Layer 3, spec §10.2).

Cadence: annual (release ~Sep; latest year 2024). Table ``wgi_governance``:
one row per country-indicator-year for the six WGI ".EST" point estimates,
consumed by the committee's governance screening tool.

Live-verified drift notes (registry sweep 2026-07-18 + this connector's build,
2026-07-19):

- Indicator codes in source 3 carry a ``GOV_WGI_`` prefix (``GOV_WGI_CC.EST``
  etc.). The table stores the codes WITHOUT the prefix (``CC.EST`` style) —
  that is the spelling the WGI project itself uses and the one downstream
  tools key on (``erda_agents.tools.screening``).
- Queries MUST pass ``source=3``. Without it, multi-indicator queries return
  an HTTP-200 *message* body (``[{"message": [...]}]``) instead of data —
  :func:`normalize` raises on that shape rather than reading it as empty.
- Some responses carry a UTF-8 BOM — decoded with ``utf-8-sig`` (a no-op when
  the BOM is absent). ``resp.json()`` would choke on the BOM, so decoding goes
  through :func:`_decode`.
- Intermittent timeouts and multi-minute 502 bursts observed live — fetch
  passes ``retries=5`` to the backoff loop in ``http_get``.
- The nominal WGI scale is "approx. −2.5 to +2.5" (the API's own label), and
  PV.EST breaches it in the live 2020:2024 window (YEM 2024 = −2.7506, SOM
  2021 = −2.6070, AFG 2020 = −2.5897, MLI 2023 = −2.5578). The contract bounds
  values at ±3.5 — tight enough to catch unit/scale drift, loose enough not to
  reject real history (same principle as fred's negative WTI settle).
- Nine territories (Anguilla, Cook Islands, French Guiana, Jersey, Martinique,
  Netherlands Antilles, Niue, Reunion, Taiwan China) come back with an empty
  ``countryiso3code``. The table keys on iso3, so those rows are dropped —
  an honest, documented absence, not an imputation (§0 rule 4).
- Null ``value`` entries mark years the source did not score — dropped,
  absent, never zero (§0 rule 4).
"""

from __future__ import annotations

import json

import httpx
import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import SourceUnavailable
from erda_ingestion.base import FetchResult, http_get

SOURCE_ID = "wgi"
TRANSFORM_VERSION = "wgi:1.0.0"
TABLE = "wgi_governance"

BASE_URL = "https://api.worldbank.org/v2/country/all/indicator"

#: Source-3 indicator ids are PREFIX + short code; the table stores short codes.
PREFIX = "GOV_WGI_"

#: The six WGI dimensions, point estimates only (short code → dimension).
INDICATORS = {
    "CC.EST": "control_of_corruption",
    "GE.EST": "government_effectiveness",
    "PV.EST": "political_stability_absence_of_violence",
    "RQ.EST": "regulatory_quality",
    "RL.EST": "rule_of_law",
    "VA.EST": "voice_and_accountability",
}

#: Latest release year is 2024 (live-verified 2026-07-19); next lands ~Sep 2026.
#: Widen or bump when the release cycle turns — the range is a param, not a law.
DEFAULT_DATE_RANGE = "2020:2024"

#: 216 economies × 5 years = 1080 rows/indicator — one page at this size, but
#: fetch still honors the ``pages`` field defensively.
PER_PAGE = 2000

COLUMNS = ["iso3", "country", "indicator", "year", "value"]

SCHEMA = pa.DataFrameSchema(
    {
        "iso3": pa.Column(str, pa.Check.str_length(3, 3), nullable=False),
        "country": pa.Column(str, nullable=False),
        "indicator": pa.Column(str, pa.Check.isin(list(INDICATORS)), nullable=False),
        "year": pa.Column(int, pa.Check.in_range(1996, 2100), nullable=False),
        # NOT ±2.5: the scale is only *approximately* ±2.5 and PV.EST breaches
        # it live (YEM 2024 = −2.7506) — see module docstring. ±3.5 rejects
        # scale drift without falsifying history.
        "value": pa.Column(float, pa.Check.in_range(-3.5, 3.5), nullable=False),
    },
    unique=["iso3", "indicator", "year"],
)


def _decode(resp: httpx.Response) -> list:
    """Response bytes → JSON, tolerating the intermittent UTF-8 BOM."""
    try:
        return json.loads(resp.content.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise SourceUnavailable(SOURCE_ID, f"non-JSON response: {exc}") from exc


def normalize(payload: list) -> pd.DataFrame:
    """World Bank v2 JSON (``[meta, rows]``) → tidy frame per the contract.

    Raises on the API's HTTP-200 failure shapes — a ``[{"message": [...]}]``
    body (e.g. the query omitted ``source=3``) or a body with no data rows —
    rather than normalizing them into an empty-but-fresh table (§0 rule 4).
    Null values and rows without an ISO3 code are dropped (module docstring),
    and the ``GOV_WGI_`` prefix is stripped from indicator ids.
    """
    if (
        isinstance(payload, list)
        and len(payload) >= 1
        and isinstance(payload[0], dict)
        and "message" in payload[0]
    ):
        detail = "; ".join(
            str(m.get("value") or m.get("key") or m) for m in payload[0]["message"]
        )
        raise SourceUnavailable(SOURCE_ID, f"API message body (source=3 missing?): {detail}")
    if not isinstance(payload, list) or len(payload) != 2 or not payload[1]:
        raise SourceUnavailable(SOURCE_ID, "no data rows in response body")

    records = []
    for row in payload[1]:
        value = row.get("value")
        iso3 = row.get("countryiso3code") or ""
        if value is None or not iso3:
            continue  # absent, never zero; identity-less rows can't key the table
        records.append(
            {
                "iso3": iso3,
                "country": row["country"]["value"],
                "indicator": row["indicator"]["id"].removeprefix(PREFIX),
                "year": int(row["date"]),
                "value": float(value),
            }
        )
    if not records:
        raise SourceUnavailable(
            SOURCE_ID, f"{len(payload[1])} rows returned but none carried a value and ISO3"
        )
    df = pd.DataFrame(records, columns=COLUMNS)
    return df.astype({"year": "int64", "value": "float64"})


def _fetch_indicator(code: str, date_range: str) -> pd.DataFrame:
    """All pages of one indicator (defensive pagination; one page in practice)."""
    url = f"{BASE_URL}/{PREFIX}{code}"
    frames = []
    page, pages = 1, 1
    while page <= pages:
        resp = http_get(
            url,
            SOURCE_ID,
            params={
                "source": "3",  # mandatory — see module docstring
                "format": "json",
                "date": date_range,
                "per_page": str(PER_PAGE),
                "page": str(page),
            },
            retries=5,  # live 502 bursts + timeouts (2026-07-19)
        )
        payload = _decode(resp)
        frames.append(normalize(payload))
        pages = int(payload[0].get("pages") or 1)
        page += 1
    return pd.concat(frames, ignore_index=True)


def fetch(date_range: str = DEFAULT_DATE_RANGE) -> FetchResult:
    """Fetch all six .EST indicators for all economies over `date_range`.

    No key required. Each indicator is fetched separately so a silently-empty
    indicator is caught per-code (normalize raises), never averaged away.
    """
    frames = [_fetch_indicator(code, date_range) for code in INDICATORS]
    out = pd.concat(frames, ignore_index=True)
    missing = sorted(set(INDICATORS) - set(out["indicator"].unique()))
    if missing:
        raise SourceUnavailable(SOURCE_ID, f"indicators returned no rows: {missing}")
    return FetchResult(frame=out, source_url=BASE_URL)
