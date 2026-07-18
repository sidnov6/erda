from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
import pytest

from erda_contracts.contracts import attach_provenance, validate, with_provenance
from erda_contracts.errors import ContractViolation
from erda_contracts.ledger import latest_by_table, read_ledger, write_with_ledger
from erda_contracts.provenance import Provenance

PROV = Provenance(
    source_id="test_src",
    retrieved_at=datetime(2026, 7, 18, 12, 0, tzinfo=UTC),
    source_url="https://example.com/data",
    transform_version="test_src:1.0.0",
)

DATA_SCHEMA = pa.DataFrameSchema(
    {
        "date": pa.Column(pa.DateTime),
        "price_usd_bbl": pa.Column(float, pa.Check.gt(0)),
    }
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"date": pd.to_datetime(["2026-07-01", "2026-07-02"]), "price_usd_bbl": [70.1, 71.2]}
    )


def test_provenance_requires_tz():
    with pytest.raises(ValueError):
        Provenance(
            source_id="x",
            retrieved_at=datetime(2026, 7, 18, 12, 0),  # naive
            source_url="https://example.com",
            transform_version="x:1",
        )


def test_attach_and_validate_roundtrip():
    df = attach_provenance(_frame(), PROV)
    out = validate(df, with_provenance(DATA_SCHEMA), "test_src")
    assert list(out["source_id"].unique()) == ["test_src"]
    assert str(out["retrieved_at"].dt.tz) == "UTC"


def test_validate_rejects_missing_provenance():
    with pytest.raises(ContractViolation, match="missing provenance"):
        validate(_frame(), with_provenance(DATA_SCHEMA), "test_src")


def test_validate_rejects_bad_data():
    df = attach_provenance(_frame(), PROV)
    df.loc[0, "price_usd_bbl"] = -5.0
    with pytest.raises(ContractViolation, match="failures"):
        validate(df, with_provenance(DATA_SCHEMA), "test_src")


def test_ledger_roundtrip(tmp_path: Path):
    df = attach_provenance(_frame(), PROV)
    path, entry = write_with_ledger(df, PROV, "test_table", tmp_path)
    assert path.exists()
    entries = read_ledger(tmp_path)
    assert len(entries) == 1
    assert entries[0].rows == 2
    assert entries[0].content_sha256 == entry.content_sha256
    # second write appends; latest_by_table picks the newer entry
    write_with_ledger(df, PROV, "test_table", tmp_path)
    assert len(read_ledger(tmp_path)) == 2
    assert latest_by_table(tmp_path)["test_table"].rows == 2
