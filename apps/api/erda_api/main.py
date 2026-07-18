from fastapi import FastAPI

from erda_api import __version__
from erda_api.routes_memo import router as memo_router
from erda_api.routes_meta import router as meta_router
from erda_api.routes_panels import router as panels_router

app = FastAPI(title="ERDA API", version=__version__)
app.include_router(meta_router)
app.include_router(panels_router)
app.include_router(memo_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe. Data endpoints arrive in Phase 1 with provenance attached."""
    return {"status": "ok", "service": "erda-api", "version": __version__}
