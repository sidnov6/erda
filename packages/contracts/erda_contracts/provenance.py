"""Provenance (spec §0 rule 5): every persisted number carries these four fields.

They travel as literal columns on every parquet the ingestion layer writes, so a
number can never be separated from where it came from. A number without
provenance is a bug.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, field_validator

#: Column names, in canonical order, present on every persisted table.
PROVENANCE_COLUMNS = ["source_id", "retrieved_at", "source_url", "transform_version"]


class Provenance(BaseModel):
    source_id: str
    retrieved_at: datetime
    source_url: str
    transform_version: str

    @field_validator("retrieved_at")
    @classmethod
    def _tz_aware_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware (UTC)")
        return v.astimezone(UTC)

    @field_validator("source_id", "source_url", "transform_version")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("provenance fields must be non-empty")
        return v


def now_utc() -> datetime:
    return datetime.now(UTC)
