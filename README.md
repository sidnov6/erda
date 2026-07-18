# ERDA

*The earth keeps records.*

ERDA is an upstream capital-allocation intelligence platform: a validated oil-market
terminal, a deep-learning prospectivity engine trained on 50+ years of public
exploration outcomes, and a multi-agent feasibility committee that turns a candidate
block into a cited, EMV-based investment memo.

> In Wagner's Ring, Erda is the primordial goddess who knows everything that lies
> beneath the earth. Petroleum in German is literally "Erdöl" — earth oil.

**Status:** Phase 0 — scaffold + terminal shell. See `ERDA_BUILD_SPEC.md` §14 for the
phase plan and gates.

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

## Development

```
uv sync                  # Python 3.11 workspace
uv run pytest
uv run ruff check .
pnpm -C apps/web dev     # terminal UI on :3000
```
