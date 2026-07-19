# ERDA API — FastAPI + agents, for Hugging Face Spaces (Docker SDK) or any host.
# Serves the frozen demo snapshot so the public app boots offline (§15). Build
# from the repo root:  docker build -f apps/api/Dockerfile -t erda-api .
FROM python:3.11-slim

# System deps for geopandas/pyogrio/rasterio wheels + libgomp for lightgbm.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 libexpat1 \
    && rm -rf /var/lib/apt/lists/*

# uv for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

# Workspace metadata first for layer caching.
COPY pyproject.toml uv.lock .python-version ./
COPY apps/api/pyproject.toml apps/api/
COPY packages ./packages
COPY apps/api/erda_api apps/api/erda_api

RUN uv sync --frozen --no-dev --package erda-api

# The frozen snapshot is the data plane. Bake it in for a self-contained image,
# or mount it at run time and point ERDA_REPO_ROOT at the mount.
COPY data/snapshot ./data/snapshot
COPY data/curated ./data/curated

ENV ERDA_REPO_ROOT=/app/data/snapshot \
    PORT=7860
EXPOSE 7860

# HF Spaces expects the app on $PORT (7860). SNAPSHOT mode → no live fetches,
# no API keys required to serve the demo.
CMD ["sh", "-c", "uv run uvicorn erda_api.main:app --host 0.0.0.0 --port ${PORT}"]
