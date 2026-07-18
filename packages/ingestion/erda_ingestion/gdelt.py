"""gdelt — GDELT DOC 2.0 geopolitical event feed, oil/chokepoint themes (spec §4 #9).

Cadence: 15-min near-real-time feed; registry SLA 2 days. No key.

Drift notes (source_registry.yaml, live-verified 2026-07-18):

- IP-based limit of 1 request / 5 s. The sweep egress IP was throttled
  (persistent HTTP 429 with the GDELT throttle body). The single live attempt
  while building this connector (2026-07-18) returned the same body — recorded
  verbatim in ``tests/fixtures/gdelt_throttle_429.txt``. A 429 carrying that
  body raises a *retryable* SourceUnavailable with a clear "IP throttled"
  message; the orchestrator may retry later with ≥ 5 s spacing.
- Per-article JSON fields are NOT live-confirmed. ``normalize()`` therefore
  parses defensively: every artlist field is optional; a missing/blank/odd-typed
  key becomes None (strings) or NaT (``seen_at``) — never an invented value.
  Articles without a ``url`` are dropped (no dedup key, no click-through), and
  duplicate URLs are deduplicated keeping the first occurrence.
- ``theme_tags`` records the connector's query filter (comma-joined GKG themes;
  each returned article matched at least one). artlist mode does not return
  per-article theme extractions, so no per-article tagging is fabricated.
- ``base.http_get`` is deliberately not used: its retry backoff (1.5 s / 3 s)
  is tighter than GDELT's 5 s IP limit, and the 429 body must be inspected.
  Each ``fetch()`` makes exactly one attempt; module-level monotonic state
  enforces ≥ 5 s spacing between any two requests in this process.
"""

from __future__ import annotations

import time

import httpx
import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import SourceUnavailable
from erda_ingestion.base import BROWSER_UA, FetchResult

SOURCE_ID = "gdelt"
TRANSFORM_VERSION = "gdelt:1.0.0"
TABLE = "gdelt_events"

API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

#: GKG themes covering oil markets + maritime chokepoint risk (TRIDENT framing).
THEMES = (
    "ENV_OIL",
    "ECON_OILPRICE",
    "MARITIME_INCIDENT",
    "PIRACY",
    "BLOCKADE",
)
QUERY = "(" + " OR ".join(f"theme:{t}" for t in THEMES) + ")"
THEME_TAGS = ",".join(THEMES)
MAX_RECORDS = 75

#: Distinctive prefix of the GDELT throttle body (recorded live 2026-07-18;
#: see tests/fixtures/gdelt_throttle_429.txt for the verbatim response).
THROTTLE_MARKER = "Please limit requests to one every 5 seconds"

_MIN_SPACING_S = 5.0
_last_request_at: float | None = None  # monotonic clock; module-level on purpose

COLUMNS = ["seen_at", "title", "url", "domain", "source_country", "theme_tags"]

SCHEMA = pa.DataFrameSchema(
    {
        # seen_at nullable: seendate is not live-confirmed; an article whose
        # timestamp is absent/unparseable keeps NaT rather than a made-up time.
        "seen_at": pa.Column(pd.DatetimeTZDtype(tz="UTC"), nullable=True, coerce=True),
        "title": pa.Column(str, nullable=True),
        "url": pa.Column(str, pa.Check.str_startswith("http"), nullable=False),
        "domain": pa.Column(str, nullable=True),
        "source_country": pa.Column(str, nullable=True),
        "theme_tags": pa.Column(str, nullable=True),
    },
    unique=["url"],
)


def _clean_str(raw: object) -> str | None:
    """Optional string field: strip; blank or non-string (unconfirmed shape) → None."""
    if isinstance(raw, str):
        stripped = raw.strip()
        return stripped or None
    return None


def _parse_seen_at(raw: object):
    """artlist ``seendate`` ('20260718T041500Z' per docs, not live-confirmed) → UTC or NaT."""
    if not isinstance(raw, str) or not raw.strip():
        return pd.NaT
    ts = pd.to_datetime(raw.strip(), format="%Y%m%dT%H%M%SZ", errors="coerce", utc=True)
    if ts is pd.NaT:  # tolerate format drift before giving up
        ts = pd.to_datetime(raw.strip(), errors="coerce", utc=True)
    return ts


def normalize(payload: dict) -> pd.DataFrame:
    """artlist JSON → tidy gdelt_events frame. Defensive: every field optional.

    Missing keys become None/NaT — never invented. Rows without a ``url`` are
    dropped (no identity, no click-through); duplicate URLs keep the first row.
    A payload without an ``articles`` list yields an empty frame (no matching
    coverage), which is honest zero-rows, not fabricated data.
    """
    articles = payload.get("articles") or []
    rows = []
    for art in articles:
        if not isinstance(art, dict):
            continue  # unconfirmed shape: skip garbage entries, invent nothing
        rows.append(
            {
                "seen_at": _parse_seen_at(art.get("seendate")),
                "title": _clean_str(art.get("title")),
                "url": _clean_str(art.get("url")),
                "domain": _clean_str(art.get("domain")),
                "source_country": _clean_str(art.get("sourcecountry")),
                "theme_tags": THEME_TAGS,
            }
        )
    df = pd.DataFrame(rows, columns=COLUMNS)
    df = df[df["url"].notna()]
    df = df.drop_duplicates(subset="url", keep="first")
    df["seen_at"] = pd.to_datetime(df["seen_at"], utc=True, errors="coerce")
    return df.reset_index(drop=True)


def _wait_for_spacing() -> None:
    """Enforce GDELT's 1-request/5-s IP limit between any two requests here."""
    global _last_request_at
    if _last_request_at is not None:
        elapsed = time.monotonic() - _last_request_at
        if elapsed < _MIN_SPACING_S:
            time.sleep(_MIN_SPACING_S - elapsed)
    _last_request_at = time.monotonic()


def _throttled_get(params: dict) -> httpx.Response:
    """One spaced GET. 429 with the known throttle body → retryable 'IP throttled'."""
    _wait_for_spacing()
    try:
        resp = httpx.get(
            API_URL,
            params=params,
            headers={"User-Agent": BROWSER_UA},
            timeout=30.0,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        raise SourceUnavailable(SOURCE_ID, f"{API_URL} → {exc}") from exc
    if resp.status_code == 429:
        body = resp.text.strip()
        if THROTTLE_MARKER in body:
            raise SourceUnavailable(
                SOURCE_ID,
                "IP throttled by GDELT (HTTP 429, known throttle body) — "
                "retryable; keep request spacing ≥ 5 s and try again later",
            )
        raise SourceUnavailable(SOURCE_ID, f"HTTP 429 (unrecognised body): {body[:200]!r}")
    if resp.status_code != 200:
        raise SourceUnavailable(SOURCE_ID, f"HTTP {resp.status_code} from {API_URL}")
    return resp


def fetch(timespan: str = "1d") -> FetchResult:
    """One artlist query over the oil/chokepoint themes; verified query shape."""
    params = {
        "query": QUERY,
        "format": "json",
        "mode": "artlist",
        "maxrecords": str(MAX_RECORDS),
        "timespan": timespan,
    }
    resp = _throttled_get(params)
    try:
        payload = resp.json()
    except ValueError as exc:
        # GDELT can answer 200 with a plain-text error page — that is a source
        # failure, never something to paper over with invented rows (§0 rule 4).
        snippet = resp.text.strip()[:200]
        raise SourceUnavailable(SOURCE_ID, f"non-JSON artlist body: {snippet!r}") from exc
    if not isinstance(payload, dict):
        raise SourceUnavailable(
            SOURCE_ID, f"unexpected artlist payload type: {type(payload).__name__}"
        )
    return FetchResult(frame=normalize(payload), source_url=str(resp.url))
