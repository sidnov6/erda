from datetime import UTC, datetime

import pandas as pd
from fastapi.testclient import TestClient

from erda_api.main import app
from erda_contracts.contracts import attach_provenance
from erda_contracts.ledger import write_with_ledger
from erda_contracts.provenance import Provenance

client = TestClient(app)


def test_validation_absent_is_honest(monkeypatch, tmp_path):
    monkeypatch.setenv("ERDA_DATA_ROOT", str(tmp_path))
    resp = client.get("/api/validation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert "refresh" in body["reason"]


def test_mode_shell_when_no_data(monkeypatch, tmp_path):
    monkeypatch.setenv("ERDA_DATA_ROOT", str(tmp_path))
    assert client.get("/api/mode").json()["mode"] == "SHELL"


def test_mode_live_and_sources_freshness(monkeypatch, tmp_path):
    monkeypatch.setenv("ERDA_DATA_ROOT", str(tmp_path))
    prov = Provenance(
        source_id="fred",
        retrieved_at=datetime.now(UTC),
        source_url="https://api.stlouisfed.org/fred/series/observations",
        transform_version="fred:1.0.0",
    )
    df = attach_provenance(pd.DataFrame({"v": [1.0]}), prov)
    write_with_ledger(df, prov, "fred_series", tmp_path)

    assert client.get("/api/mode").json()["mode"] == "LIVE"
    sources = client.get("/api/sources").json()["sources"]
    fred = next(s for s in sources if s["source_id"] == "fred")
    assert fred["freshness"]["status"] == "pass"
    # sources with no data written are honestly failed, not hidden
    gdelt = next(s for s in sources if s["source_id"] == "gdelt")
    assert gdelt["freshness"]["status"] == "fail"
