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

RUN uv sync --frozen --no-dev --package erda-api && uv pip install huggingface_hub

# The frozen snapshot is the data plane — a self-contained mini repo-root that
# already holds its own data/{parquet,curated,zarr,memos}. Bake it in, or mount
# it at run time and point ERDA_REPO_ROOT at the mount.
COPY data/snapshot ./data/snapshot

ENV ERDA_REPO_ROOT=/app/data/snapshot \
    GROQ_MODEL=openai/gpt-oss-120b \
    GROQ_MAX_TOKENS=1600 \
    PORT=7860
EXPOSE 7860

# HF Spaces expects the app on $PORT (7860). SNAPSHOT mode → no live fetches,
# no API keys required to serve the demo; GROQ_API_KEY (Space secret) enables
# live memo narration. GROQ_MODEL defaults to gpt-oss-120b — a reasoning model
# with its own free-tier daily-token bucket (the llama-70b bucket drains fast).
#
# Optional: pull the full 1 GB raster stack from a HF dataset at boot (Space
# repos cap at 1 GB, so it cannot ship in-repo; a reduced 3-channel stack —
# elevation_m/province_code/score_mask, all the committee reads — can). Set
# ERDA_STACK_DATASET to swap in the full stack without a rebuild.
CMD ["sh", "-c", "if [ -n \"$ERDA_STACK_DATASET\" ] && [ ! -e data/snapshot/data/zarr/stack.zarr ]; then uv run hf download $ERDA_STACK_DATASET --repo-type dataset --local-dir data/snapshot/data/zarr; fi; uv run uvicorn erda_api.main:app --host 0.0.0.0 --port ${PORT}"]
