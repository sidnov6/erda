from fastapi import FastAPI

from erda_api import __version__

app = FastAPI(title="ERDA API", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Data endpoints arrive in Phase 1 with provenance attached."""
    return {"status": "ok", "service": "erda-api", "version": __version__}
