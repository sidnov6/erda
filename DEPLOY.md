# ERDA — deployment (§15)

Two services: the **web** terminal (Next.js → Vercel) and the **API + agents**
(FastAPI → Hugging Face Spaces, Docker). The public app runs in **SNAPSHOT mode**
— it boots from a frozen data snapshot and needs no live sources or API keys, so
it never breaks mid-demo. A LIVE/SNAPSHOT badge in the footer states which mode
is running.

## 0. Freeze the snapshot (once, before deploying)

```
uv run python ops/build_labels.py           # if data/ is empty (needs EIA/FRED keys)
uv run python ops/build_stack.py            # 14-channel raster stack
uv run python ops/make_memo.py --spec ops/showcase_blocks.json --all   # 5 showcase memos
uv run python ops/demo_freeze.py            # → data/snapshot/ (self-contained mini repo-root)
```

`demo_freeze.py` writes `data/snapshot/` with a content-hash manifest. Everything
below serves from it.

## 1. API → Hugging Face Spaces (Docker SDK)

```
# from the repo root
docker build -f apps/api/Dockerfile -t erda-api .
docker run -p 7860:7860 erda-api          # smoke test: curl localhost:7860/api/mode → SNAPSHOT
```

Push to a Space (SDK = Docker). The image bakes in `data/snapshot/` and sets
`ERDA_REPO_ROOT=/app/data/snapshot`, so **no secrets are required** to serve the
demo. To run it LIVE instead (nightly-refreshed), unset `ERDA_REPO_ROOT`, mount a
writable `data/`, and set `EIA_API_KEY`, `FRED_API_KEY`, and `GROQ_API_KEY`
(memo narration) / `ANTHROPIC_API_KEY` as Space secrets.

Note the Space URL, e.g. `https://<user>-erda-api.hf.space`.

## 2. Web → Vercel

The web app proxies `/api/erda/*` → the API via a Next.js rewrite that reads
`ERDA_API_URL` **at build time** (`apps/web/next.config.ts`). Set it in Vercel:

```
Project → Settings → Environment Variables
  ERDA_API_URL = https://<user>-erda-api.hf.space
Framework preset: Next.js · Root directory: apps/web · Build: pnpm build
```

Redeploy so the rewrite picks up the URL. The web app holds no secrets — all data
comes through the proxy.

## 3. Nightly data refresh (optional, LIVE mode)

`.github/workflows/nightly_refresh.yml` runs `ops/refresh.py` and uploads the
parquet artifacts. It needs repo secrets `EIA_API_KEY`, `FRED_API_KEY`,
`COMTRADE_API_KEY`. Re-run `demo_freeze.py` + redeploy the API to publish a fresh
snapshot. (GDELT is IP-throttled from some networks; the EVENTS panel states this
honestly and it clears from GitHub's egress.)

## Honest boundaries (printed in the UI footer and README)

- ERDA ranks *resemblance to historically successful acreage*; it is a screening
  tool, not seismic, and never claims "oil is here."
- **No prospectivity heatmap ships**: the model did not beat the
  distance-to-discovery baseline under spatial cross-validation (§9.8). The map
  is wells + context only; see `packages/models/cards/NEGATIVE_RESULT.md` and the
  /validation page.
- Memo Pg is user-supplied (§9.8) — stated on every memo.
- Everything is public/free data, self-built, not client work.
