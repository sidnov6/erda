from fastapi.testclient import TestClient

from erda_api import __version__
from erda_api.main import app

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "erda-api", "version": __version__}
