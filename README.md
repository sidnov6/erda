# ERDA

*The earth keeps records.*

ERDA is an upstream capital-allocation intelligence platform: a validated oil-market
terminal, a deep-learning prospectivity engine trained on 50+ years of public
exploration outcomes, and a multi-agent feasibility committee that turns a candidate
block into a cited, EMV-based investment memo.

> In Wagner's Ring, Erda is the primordial goddess who knows everything that lies
> beneath the earth. Petroleum in German is literally "Erdöl" — earth oil.

**Status:** deployable — a Bloomberg-style terminal over 15 live public sources,
a deck.gl map hero (offline basemap, 32,595 harmonized wells, block-pick →
feasibility memo), a nine-agent committee over a deterministic economics engine,
and a first-class /validation page. The prospectivity model was **honestly
stopped at the §9.8 falsification gate** — it did not beat the
distance-to-discovery baseline under spatial cross-validation, so no heatmap
ships; the map is wells + context only. See `ERDA_BUILD_SPEC.md` §14 for the
phase gates, `DEPLOY.md` to run it, and
`packages/models/cards/NEGATIVE_RESULT.md` for the gate write-up.

## The three layers (and the causal chain between them)

```
   LAYER 1 · MARKET            LAYER 2 · MODEL              LAYER 3 · AGENTS
   ─────────────────           ───────────────              ────────────────
   15 sources, reconciled      32,595 wildcat outcomes      9-agent LangGraph
   futures curve → price       from 5 regulators + a        committee over typed
   deck; OPEC compliance;      14-channel raster stack;     tools; deterministic
   inventories; the            spatial-CV honesty gate      economics engine
   Discovery Monitor           (§9.8) — no map ships        (EMV/NPV/Monte Carlo)
        │                            │                            │
        └─ curve → price deck ───────┼──── calibrated Pg would ───┘
                                     │     have fed EMV; the gate
                                     │     failed, so Pg is user-supplied
```

Each layer validates the next: the futures strip becomes the DCF price deck; the
harmonized well DB powers the model, the Discovery Monitor, and the committee's
offset-well tool. The model *would* have supplied the Pg inside
`EMV = Pg·NPV(success) − (1−Pg)·well-cost` — but it failed its spatial-CV gate, so
Pg is user-supplied and every memo says so. That honest break is the point:
market says *whether* to explore, the well record says *where has worked*, the
agents say *if it pencils* — with no fabricated confidence in between.

## Honest boundaries

- ERDA predicts *resemblance to historically successful acreage*, calibrated as a
  probability. It is a screening tool. It does not replace seismic, and it never
  claims "oil is here."
- Probabilities are area-level chance-of-success proxies, not prospect-level Pg from
  a mapped trap.
- Frontier hindcasts (Namibia, Guyana) are narrative case studies with small n,
  presented as such.
- Everything is public/free data, self-built, not client work.

## Layout

```
apps/api        FastAPI: REST + tiles + SSE memo stream
apps/web        Next.js terminal UI
packages/*      ingestion · contracts · geo · labels · models · engine · agents · validation
data/           raw / parquet / zarr (untracked artifacts) · curated/ (tracked, every row cited)
ops/            operational scripts; CI lives in .github/workflows/
```

## Run it locally

```
uv sync                                     # Python 3.11 workspace
cp .env.example .env                        # add free EIA + FRED keys (+ GROQ for memo prose)
uv run python ops/refresh.py                # pull the market layer → data/parquet
uv run python ops/build_labels.py           # harmonize the 5 regulators → wells DB
uv run python ops/build_stack.py            # 14-channel raster stack → data/zarr
uv run uvicorn erda_api.main:app --port 8000    # API + agents
pnpm -C apps/web dev                        # terminal UI on :3000
```

The public demo boots offline from a frozen snapshot — see `DEPLOY.md`.

## Tests & gates

```
uv run pytest                # 420 tests: engine golden case, spatial-CV harness, tools, memo determinism
uv run ruff check .          # deterministic core (engine/geo) is lint-enforced import-pure
pnpm -C apps/web test:e2e    # 8 Playwright specs incl. map interactive < 2 s
```

Every phase gate (§14) is in git history with its evidence — including the P3
commit that records the **failed** falsification gate rather than shipping a map
without demonstrated skill.
