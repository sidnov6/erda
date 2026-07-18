"""Source registry: data/curated/source_registry.yaml, one entry per source_id.

Written from live VERIFY results (spec §0 rule 6) — never from memory. The
freshness checks read `sla_days` from here; the /validation page renders the
registry as the catalog of record.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator


class SourceEntry(BaseModel):
    source_id: str
    name: str
    access: str  # rest_key | rest | bulk_csv | xlsx | pdf | lib
    base_url: str
    cadence: str  # daily | weekly | monthly | annual | 15min
    sla_days: float
    requires_key: bool = False
    key_env: str | None = None
    verified_at: str  # ISO date of the live VERIFY check
    notes: str = ""

    @field_validator("base_url")
    @classmethod
    def _url(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("base_url must be https")
        return v


def load_registry(path: Path) -> dict[str, SourceEntry]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = {}
    for source_id, meta in raw["sources"].items():
        entries[source_id] = SourceEntry(source_id=source_id, **meta)
    return entries
