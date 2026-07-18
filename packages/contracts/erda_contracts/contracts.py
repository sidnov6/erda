"""Pandera contract helpers (spec §11.1).

Every source declares a pandera schema for its *data* columns; this module
extends it with the mandatory provenance columns and runs validation with
failure semantics that stop the pipeline (ContractViolation) instead of
persisting bad data.
"""

from __future__ import annotations

import pandas as pd
import pandera.pandas as pa

from erda_contracts.errors import ContractViolation
from erda_contracts.provenance import PROVENANCE_COLUMNS, Provenance

_PROVENANCE_SCHEMA_COLUMNS: dict[str, pa.Column] = {
    "source_id": pa.Column(str, nullable=False),
    "retrieved_at": pa.Column(pd.DatetimeTZDtype(tz="UTC"), nullable=False, coerce=True),
    "source_url": pa.Column(str, nullable=False),
    "transform_version": pa.Column(str, nullable=False),
}


def with_provenance(schema: pa.DataFrameSchema) -> pa.DataFrameSchema:
    """Extend a data schema with the four mandatory provenance columns."""
    return schema.add_columns(_PROVENANCE_SCHEMA_COLUMNS)


def attach_provenance(df: pd.DataFrame, prov: Provenance) -> pd.DataFrame:
    """Stamp provenance columns onto every row of a fetched table."""
    out = df.copy()
    out["source_id"] = prov.source_id
    out["retrieved_at"] = pd.Timestamp(prov.retrieved_at)
    out["source_url"] = prov.source_url
    out["transform_version"] = prov.transform_version
    return out


def validate(df: pd.DataFrame, schema: pa.DataFrameSchema, source_id: str) -> pd.DataFrame:
    """Validate against a provenance-extended schema; raise ContractViolation on failure."""
    missing = [c for c in PROVENANCE_COLUMNS if c not in df.columns]
    if missing:
        raise ContractViolation(source_id, f"missing provenance columns: {missing}")
    try:
        return schema.validate(df, lazy=True)
    except pa.errors.SchemaErrors as exc:
        summary = exc.failure_cases.head(10).to_string(index=False)
        detail = f"{len(exc.failure_cases)} failures:\n{summary}"
        raise ContractViolation(source_id, detail) from exc
