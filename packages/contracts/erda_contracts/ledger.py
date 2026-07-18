"""The provenance ledger: one append-only record per persisted table write.

Lives beside the parquet artifacts (data/parquet/_ledger.jsonl). The /validation
page and freshness checks read this to know what was written, when, from where.
JSONL keeps appends atomic and diffable; the ledger is small.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from erda_contracts.provenance import Provenance

LEDGER_NAME = "_ledger.jsonl"


class LedgerEntry(BaseModel):
    source_id: str
    table: str
    path: str
    rows: int
    content_sha256: str
    retrieved_at: datetime
    source_url: str
    transform_version: str


def _hash_frame(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values.tobytes()).hexdigest()


def write_with_ledger(
    df: pd.DataFrame, prov: Provenance, table: str, root: Path
) -> tuple[Path, LedgerEntry]:
    """Write a validated, provenance-stamped frame to parquet and append the ledger."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{table}.parquet"
    df.to_parquet(path, index=False)
    entry = LedgerEntry(
        source_id=prov.source_id,
        table=table,
        path=str(path.relative_to(root)),
        rows=len(df),
        content_sha256=_hash_frame(df),
        retrieved_at=prov.retrieved_at,
        source_url=prov.source_url,
        transform_version=prov.transform_version,
    )
    with (root / LEDGER_NAME).open("a", encoding="utf-8") as fh:
        fh.write(entry.model_dump_json() + "\n")
    return path, entry


def read_ledger(root: Path) -> list[LedgerEntry]:
    ledger = root / LEDGER_NAME
    if not ledger.exists():
        return []
    entries = []
    with ledger.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                entries.append(LedgerEntry.model_validate(json.loads(line)))
    return entries


def latest_by_table(root: Path) -> dict[str, LedgerEntry]:
    """Most recent ledger entry per table (later lines win)."""
    return {e.table: e for e in read_ledger(root)}
