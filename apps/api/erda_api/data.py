"""Data-plane access for the API: parquet tables + ledger + registry.

The API serves numbers only with their provenance attached (§0 rule 5) and
never computes domain math — that lives in packages (engine in P4, derived
metrics in erda_ingestion.derived, called with values read from tables).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

from erda_contracts.ledger import LedgerEntry, latest_by_table
from erda_contracts.registry import SourceEntry, load_registry
from erda_validation.report import REPORT_NAME


def repo_root() -> Path:
    return Path(os.environ.get("ERDA_REPO_ROOT", Path(__file__).resolve().parents[3]))


def parquet_root() -> Path:
    return Path(os.environ.get("ERDA_DATA_ROOT", repo_root() / "data" / "parquet"))


def registry_path() -> Path:
    return repo_root() / "data" / "curated" / "source_registry.yaml"


@lru_cache(maxsize=1)
def _registry_cached() -> dict[str, SourceEntry]:
    return load_registry(registry_path())


def registry() -> dict[str, SourceEntry]:
    return _registry_cached()


def read_table(table: str) -> pd.DataFrame | None:
    path = parquet_root() / f"{table}.parquet"
    if not path.exists():
        return None
    return pd.read_parquet(path)


def ledger_latest() -> dict[str, LedgerEntry]:
    return latest_by_table(parquet_root())


def read_validation_report() -> dict | None:
    path = parquet_root() / REPORT_NAME
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def provenance_of(df: pd.DataFrame) -> dict:
    """Extract the (batch-constant) provenance from a table's columns."""
    row = df.iloc[0]
    return {
        "source_id": str(row["source_id"]),
        "retrieved_at": pd.Timestamp(row["retrieved_at"]).isoformat(),
        "source_url": str(row["source_url"]),
        "transform_version": str(row["transform_version"]),
    }
