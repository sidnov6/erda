"""Connector runner: fetch → normalize → provenance → contract → parquet + ledger.

Every connector module declares SOURCE_ID, TRANSFORM_VERSION, a pandera data
schema, and a `fetch() -> FetchResult`. This runner is the only path to disk —
so nothing reaches parquet without provenance and a passing contract (§0 rules
4–5). A failing source raises; it never degrades silently.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
import pandas as pd
import pandera.pandas as pa

from erda_contracts.contracts import attach_provenance, validate, with_provenance
from erda_contracts.errors import SourceUnavailable
from erda_contracts.ledger import LedgerEntry, write_with_ledger
from erda_contracts.provenance import Provenance, now_utc

#: Some corporate/data portals reject default client UAs; a plain browser UA is
#: honest here — we fetch exactly what a human downloading the file would get.
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


@dataclass
class FetchResult:
    frame: pd.DataFrame
    source_url: str


def http_get(
    url: str,
    source_id: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 30.0,
    retries: int = 3,
) -> httpx.Response:
    """GET with retries; raises SourceUnavailable instead of returning bad data."""
    merged = {"User-Agent": BROWSER_UA, **(headers or {})}
    last: Exception | None = None
    for attempt in range(retries):
        try:
            resp = httpx.get(
                url, params=params, headers=merged, timeout=timeout, follow_redirects=True
            )
            resp.raise_for_status()
            return resp
        except httpx.HTTPError as exc:
            last = exc
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    raise SourceUnavailable(source_id, f"{url} → {last}")


def run_connector(
    *,
    source_id: str,
    transform_version: str,
    schema: pa.DataFrameSchema,
    fetch: Callable[[], FetchResult],
    table: str,
    root: Path,
) -> LedgerEntry:
    result = fetch()
    prov = Provenance(
        source_id=source_id,
        retrieved_at=now_utc(),
        source_url=result.source_url,
        transform_version=transform_version,
    )
    df = attach_provenance(result.frame, prov)
    df = validate(df, with_provenance(schema), source_id)
    _, entry = write_with_ledger(df, prov, table, root)
    return entry
