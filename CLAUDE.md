# CLAUDE.md — ERDA project constitution

Read this before touching code. `ERDA_BUILD_SPEC.md` is the single source of truth; § references below point into it.

## 1. What ERDA is

ERDA is an upstream capital-allocation intelligence platform: a validated oil-market terminal, a deep-learning prospectivity engine trained on 50+ years of public exploration outcomes, and a multi-agent feasibility committee that turns a candidate block into a cited, EMV-based investment memo.

## 2. The 8 rules (§0, verbatim — non-negotiable)

1. **Plan first.** At the start of each phase, produce a short plan (files, order, tests) before writing code.
2. **Deterministic core is sacred.** Everything in `packages/engine` (economics) and `packages/geo` (raster math) is pure Python: no network calls, no unseeded randomness, no LLM calls. Same inputs → identical outputs.
3. **LLM narrates, code calculates.** No LLM ever performs arithmetic, unit conversion, or NPV math. Agents call typed tools; tools return numbers; the memo template interpolates them. This is a hard architectural rule, not a style preference.
4. **Never fabricate data.** All data comes from the sources in §4–§7. If a source fails, raise a clear error and stop — never invent placeholder numbers. Synthetic data exists in exactly one place: the golden test fixtures in §11, clearly labelled as test artifacts.
5. **Provenance is mandatory.** Every persisted number carries `{source_id, retrieved_at, source_url, transform_version}`. The UI renders these as provenance chips. A number without provenance is a bug.
6. **`VERIFY:` tags.** Wherever this doc says `VERIFY:`, the endpoint/value may have drifted since writing (July 2026). Confirm against the linked source at build time before hardcoding. Free public APIs move; the architecture doesn't.
7. **Honesty gates are real gates.** Phase 3 has a scientific falsification gate (§9.8). If the model does not beat the "drill next to old wells" baseline under spatial cross-validation, STOP and report — do not ship a map that has no skill. The project's credibility depends on this.
8. **TDD on the engine.** Golden-case tests (§11.3) are written before the economics engine. Red tests block phase advancement.

## 3. Stack + toolchain versions

Toolchain (confirmed on this machine):
- Python 3.11 — pinned via uv (system uv 0.11.23)
- node v26.3.1
- pnpm 11.9.0

Stack (§2): PyTorch + Lightning, LightGBM, xarray/rioxarray/rasterio, GeoPandas, DuckDB (+spatial), Zarr, pandera, FastAPI, LangGraph + Claude API, Next.js 15 (pnpm) + TypeScript + Tailwind, deck.gl + MapLibre, TradingView lightweight-charts, ECharts, cmdk, react-grid-layout. CI: GitHub Actions. Deploy: §15.

## 4. Phase order & gates (§14)

Standing rule: **never skip a gate, never claim a gate passed without evidence** (test output, screenshot, validation report).

| Phase | Scope | Gate |
|-------|-------|------|
| P0 | Scaffold repo (§3), CLAUDE.md, 3 skills, CI, empty shell with tokens + ⌘K | CI green; shell screenshot passes design self-critique |
| P1 | Layer 1: sources 1–9, derived metrics, validators, nightly Action | Nightly run green; /validation renders reconciliation report; every panel number has provenance chip |
| P2 | Labels harmonized (§5) + raster stack (§6) + EDA notebook + dataset card | ≥5,000 outcomes or documented actual; stack Zarr written; label-map decisions documented |
| P3 | GBM → spatial-CV harness → CNN → calibration → hindcast → model card | Falsification gate §9.8: beats baseline (b) on spatial CV, calibration plot sane — or honest stop |
| P4 | Economics engine, TDD | Golden + property tests pass; engine is import-pure (no I/O) |
| P5 | Agents + memo + SSE streaming | 3 showcase memos: citation coverage ≥ 0.9, red-team section present, deterministic re-run hash matches |
| P6 | Full UI: map hero, all panels, memo viewer, /validation | Playwright visual suite passes; map interactive < 2 s; demo mode runs fully offline from frozen snapshot |
| P7 | Deploy + demo freeze + README + model card + video assets | Public URL live; 5 precomputed showcase blocks; README with honest-boundaries section |

## 5. Deterministic core

Files: `packages/engine/**` and `packages/geo/**`.
- Pure Python. No network. No unseeded randomness. No LLM calls. Same inputs → identical outputs.
- The economics engine is test-first from the golden fixture (`tests/fixtures/golden_block.yaml`); a red test blocks everything downstream.
- Monte Carlo is seeded (10k runs, §10.5). Property tests enforce monotonicity (price↑→NPV↑; royalty↑→take↑; Pg↑→EMV↑).

## 6. Provenance schema

Every persisted number carries:

```
{source_id, retrieved_at, source_url, transform_version}
```

A number without provenance is a bug. Curated files are hand-maintained but never uncited: the contract validator rejects any `curated_*` row lacking `source_url` (§7).

## 7. Command cheatsheet

```
uv sync                          # install/refresh Python workspace deps
uv run pytest                    # run tests (engine tests must be green before advancing)
uv run ruff check .              # lint Python
pnpm -C apps/web dev             # Next.js dev server
pnpm -C apps/web lint            # lint web
pnpm -C apps/web build           # production build
pnpm -C apps/web exec playwright test   # Playwright visual/E2E suite (P6 gate; also §12.4 screenshots)
```

UI iteration (§12.4): use the Playwright MCP screenshot loop — render → screenshot → self-critique against §13 tokens → fix. Budget explicit polish passes; do not claim a UI gate passed without a screenshot.

## 8. Repo layout notes

- uv workspace at the repo root; each Python package lives under `packages/<pkg>/` with importable name `erda_<pkg>` (e.g. `packages/engine/erda_engine/dcf.py`).
- Full skeleton: §3. `apps/api` (FastAPI), `apps/web` (Next.js), `packages/{ingestion,contracts,geo,labels,models,engine,agents,validation}`, `data/{raw,parquet,zarr,curated}`, `notebooks/` (nothing load-bearing).
- GitHub Actions workflows live in `.github/workflows/` (`nightly_refresh.yml`, `ci.yml`); `ops/` holds scripts like `demo_freeze.py`.

## 9. Skills (`.claude/skills/`)

- `erda-design-system` — use for ALL UI styling: §13 tokens, panel chrome, chart theming for lightweight-charts/ECharts/deck.gl.
- `erda-data-contracts` — use when adding any data source: contract → connector → validator → provenance → panel.
- `erda-agent-tools` — use when adding any agent tool: typed fn → schema → source_ids → register in graph → memo field mapping.
