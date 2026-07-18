# ERDA — Build Specification v1.0

**Upstream Oil Exploration Intelligence Platform**
**Author:** Siddharth Jain · **Date:** July 2026 · **Status:** Authoritative build spec for Claude Code
**Repo name:** `erda` · **Tagline:** *The earth keeps records.*
**German hook:** *Erda weiß, was unter der Erde liegt.* (In Wagner's Ring, Erda is the primordial goddess who knows everything that lies beneath the earth. Petroleum in German is literally "Erdöl" — earth oil. The name picked itself. Alternative name if you prefer: FAFNIR, the dragon who hoards buried treasure.)

---

## §0 — How Claude Code must use this document

This file is the single source of truth. Read it fully before writing any code. Work phase by phase (§14), never skipping a phase gate. Rules of engagement:

1. **Plan first.** At the start of each phase, produce a short plan (files, order, tests) before writing code.
2. **Deterministic core is sacred.** Everything in `packages/engine` (economics) and `packages/geo` (raster math) is pure Python: no network calls, no unseeded randomness, no LLM calls. Same inputs → identical outputs.
3. **LLM narrates, code calculates.** No LLM ever performs arithmetic, unit conversion, or NPV math. Agents call typed tools; tools return numbers; the memo template interpolates them. This is a hard architectural rule, not a style preference.
4. **Never fabricate data.** All data comes from the sources in §4–§7. If a source fails, raise a clear error and stop — never invent placeholder numbers. Synthetic data exists in exactly one place: the golden test fixtures in §11, clearly labelled as test artifacts.
5. **Provenance is mandatory.** Every persisted number carries `{source_id, retrieved_at, source_url, transform_version}`. The UI renders these as provenance chips. A number without provenance is a bug.
6. **`VERIFY:` tags.** Wherever this doc says `VERIFY:`, the endpoint/value may have drifted since writing (July 2026). Confirm against the linked source at build time before hardcoding. Free public APIs move; the architecture doesn't.
7. **Honesty gates are real gates.** Phase 3 has a scientific falsification gate (§9.8). If the model does not beat the "drill next to old wells" baseline under spatial cross-validation, STOP and report — do not ship a map that has no skill. The project's credibility depends on this.
8. **TDD on the engine.** Golden-case tests (§11.3) are written before the economics engine. Red tests block phase advancement.

---

## §1 — Mission & positioning

**One-liner:** ERDA is an upstream capital-allocation intelligence platform: a validated oil-market terminal, a deep-learning prospectivity engine trained on 50+ years of public exploration outcomes, and a multi-agent feasibility committee that turns a candidate block into a cited, EMV-based investment memo.

**The economic hook:** a single deepwater exploration well costs $60–150M+ and most are dry. Meanwhile conventional discovered volumes are running at multi-decade lows while demand hasn't peaked. The industry's whole game is "don't drill stupid holes." ERDA is a screening machine for that decision.

**Hero persona (design everything around this):** an E&P new-ventures / exploration screening team evaluating licensing rounds and farm-ins. Secondary: trading-house upstream investment arms; funds screening E&P deals; risk teams using the same engine as an *exclusion* screen. The hero flow is: **Map → pick block → generate Memo.** The terminal is the context around that flow.

**Honest boundaries (print these in the README and the UI footer):**
- ERDA predicts *resemblance to historically successful acreage*, calibrated as a probability. It is a screening tool. It does not replace seismic, and it never claims "oil is here."
- Probabilities are area-level chance-of-success proxies, not prospect-level Pg from a mapped trap.
- Frontier hindcasts (Namibia, Guyana) are narrative case studies with small n, presented as such.
- Everything is public/free data, self-built, not client work.

**Why this is portfolio-stellar:** it fuses three hard disciplines (market data engineering with reconciliation, geospatial deep learning with leakage-safe validation, agentic systems with deterministic economics) into one causal chain — market says *whether* to explore, model says *where*, agents say *if it pencils*. Each layer validates the next: the futures curve becomes the price deck; the calibrated model probability becomes the Pg inside EMV. That integration is the interview story.

---

## §2 — System overview

```
                                ┌─────────────────────────────────────────────┐
                                │                 ERDA UI                     │
                                │  Next.js · deck.gl map hero · terminal      │
                                │  workspace · ⌘K command line · /validation  │
                                └───────▲──────────────▲──────────────▲───────┘
                                        │              │              │
                                 REST/WS│        tiles │         SSE  │
                                ┌───────┴──────────────┴──────────────┴───────┐
                                │              FastAPI  (apps/api)            │
                                └───▲───────────────▲───────────────▲─────────┘
                                    │               │               │
        ┌───────────────────────────┴──┐   ┌────────┴────────┐   ┌──┴──────────────────────┐
        │  LAYER 1 · MARKET            │   │ LAYER 2 · MODEL │   │ LAYER 3 · AGENTS        │
        │  ingestion/ (11 sources)     │   │ prospectivity   │   │ LangGraph committee     │
        │  reconciliation validators   │   │ GBM + patch-CNN │   │ 9 agents · typed tools  │
        │  curve engine · derived      │   │ spatial CV      │   │ deterministic economics │
        │  metrics                     │   │ hindcast        │   │ engine (EMV/NPV/MC)     │
        └──────────────┬───────────────┘   └────────┬────────┘   └──────────┬──────────────┘
                       │                            │                       │
                ┌──────▼────────────────────────────▼───────────────────────▼──────┐
                │      DATA PLANE — DuckDB + GeoParquet + Zarr raster stack        │
                │      contracts (pandera) · provenance ledger · nightly            │
                │      GitHub-Actions refresh · frozen demo snapshot                │
                └───────────────────────────────────────────────────────────────────┘
```

**The three integration seams (this is the architecture, everything else is plumbing):**
1. **Curve → price deck.** Layer 1's futures strip + long-run scenarios feed Layer 3's DCF.
2. **Calibrated probability → EMV.** Layer 2's isotonic-calibrated P(discovery) is the Pg in `EMV = Pg·NPV(success) − (1−Pg)·dry-hole cost`. This is the industry's actual decision metric, computed with your model's number.
3. **Well database → everything.** The harmonized label DB powers the model, the Discovery Monitor panel, per-basin creaming curves (resource-size priors for Monte Carlo), and the Geoscience agent's offset-well summaries.

**Stack:** Python 3.11 (uv), PyTorch + Lightning, LightGBM, xarray/rioxarray/rasterio, GeoPandas, DuckDB (+spatial), Zarr, pandera, FastAPI, LangGraph + Claude API, Next.js 15 (pnpm) + TypeScript + Tailwind, deck.gl + MapLibre, TradingView lightweight-charts, ECharts, cmdk, react-grid-layout. CI: GitHub Actions. Deploy: §15.

---

## §3 — Repository skeleton

```
erda/
├── CLAUDE.md                        # constitution for Claude Code (§12.2)
├── ERDA_BUILD_SPEC.md               # this file
├── .claude/skills/
│   ├── erda-design-system/SKILL.md  # tokens, panel chrome, chart theming (§12.3)
│   ├── erda-data-contracts/SKILL.md # how to add a source: contract→connector→validator→provenance
│   └── erda-agent-tools/SKILL.md    # how to add an agent tool: typed fn→schema→citation rules
├── apps/
│   ├── api/                         # FastAPI: REST + tiles + SSE memo stream
│   └── web/                         # Next.js terminal UI
├── packages/
│   ├── ingestion/                   # per-source connectors (one module per source_id)
│   ├── contracts/                   # pandera schemas + provenance ledger
│   ├── geo/                         # raster stack builder, co-registration, derived channels
│   ├── labels/                      # well-outcome harmonization (Sodir/NSTA/NLOG/BOEM/NOPIMS)
│   ├── models/                      # gbm/, cnn/, calibration/, evaluation/, cards/
│   ├── engine/                      # deterministic economics: dcf.py, emv.py, monte_carlo.py, fiscal.py
│   ├── agents/                      # LangGraph graph, tools/, prompts/, memo_schema.py
│   └── validation/                  # reconciliation checks, nightly report generator
├── data/
│   ├── raw/  data/parquet/  data/zarr/  data/curated/   # curated = hand-maintained CSVs w/ source URLs
├── ops/                             # GH Actions: nightly_refresh.yml, ci.yml, demo_freeze.py
└── notebooks/                       # EDA + model dev only; nothing load-bearing lives here
```

---

## §4 — Data catalog · Layer 1 (market terminal)

All free. Register keys where noted (all free tiers). Every connector lives in `packages/ingestion/<source_id>.py`, declares a pandera contract, and writes parquet + provenance.

| # | source_id | What it gives ERDA | Access | Cadence | Notes |
|---|-----------|--------------------|--------|---------|-------|
| 1 | `eia_v2` | US + international production, consumption, **weekly WPSR inventories**, prices, STEO forecasts | REST, free API key — `VERIFY: https://api.eia.gov/v2/` | Weekly/Monthly | The cornerstone. Series IDs pinned in `curated/eia_series.yaml` |
| 2 | `fred` | Brent (DCOILBRENTEU), WTI (DCOILWTICO) spot history, macro (DXY, CPI) | REST, free key | Daily | Long clean histories for charts |
| 3 | `yf_curve` | Futures strip: CL/BZ/RB/HO front months + individual contracts (e.g. `CLZ26.NYM`) → term structure | `yfinance` (unofficial) | Daily | Graceful degradation: if contract strip fails, fall back to front-month + EIA STEO path. Label as indicative |
| 4 | `jodi` | Monthly production/demand/stocks, 100+ countries | Bulk CSV — `VERIFY: jodidb.org` | Monthly | The free global cross-check against EIA |
| 5 | `baker_hughes` | Weekly US + international rig counts | XLSX download — `VERIFY: rigcount.bakerhughes.com` | Weekly | Classic activity leading indicator |
| 6 | `opec` | MOMR (production by country, secondary sources), Annual Statistical Bulletin | PDF (MOMR) + data downloads (ASB) — `VERIFY: asb.opec.org` | Monthly | MOMR table extraction via `pdfplumber`; mark fields `extraction=semi_automated` |
| 7 | `wb_pinksheet` | World Bank commodity prices (long-run monthly) | XLSX | Monthly | Long-run real price context |
| 8 | `comtrade` | Crude/product trade flows by country pair | REST, free key | Monthly/Annual | Powers trade-flow sankey panel (stretch) |
| 9 | `gdelt` | Geopolitical event feed filtered to energy/chokepoint themes | DOC 2.0 API, no key | 15-min | Event feed panel; reuse TRIDENT chokepoint framing |
| 10 | `sec_reserves` | Majors' reserve replacement from 10-K oil & gas disclosures (XOM, CVX, SHEL, TTE, BP, EQNR) | EDGAR APIs, no key | Annual | Stretch module; parsing SFAS-69-style tables is messy — curated fallback CSV with source URLs |
| 11 | `curated_rounds` | Licensing-round calendar (country, round, close date, blocks, source URL) | Hand-maintained `curated/licensing_rounds.csv` | As-needed | Every row must carry a source URL; validator rejects rows without one |

**Derived metrics engine (`packages/ingestion/derived.py`, pure functions, unit-tested):**
- 3-2-1 crack spread = (2·RBOB·42 + 1·HO·42 − 3·WTI) / 3 ($/bbl)
- Brent–WTI spread; prompt spread M1–M2; curve slope M1–M12 (contango/backwardation flag)
- Days of forward cover = OECD (or US) stocks ÷ consumption rate
- OPEC+ compliance % = delivered cut ÷ pledged cut, per country, from MOMR secondary sources
- Rigs→production lead-lag panel (correlation at 0–12 month lags, computed not asserted)
- Discovery Monitor series from §5's label DB: discovered volumes/year, exploration wells/year, success rate/year — the "world is finding less oil" chart, computed from primary well data, not from a news claim

---

## §5 — Data catalog · Layer 2 labels (the supervised signal)

The crown jewel: harmonized exploration well outcomes. One schema, five regulators.

| source_id | Region | What | Access | Approx. exploration wells |
|-----------|--------|------|--------|---------------------------|
| `sodir` | Norwegian Continental Shelf | Every wellbore since 1966: purpose (WILDCAT/APPRAISAL), content (OIL/GAS/SHOWS/DRY), coordinates, TD, spud/completion dates, discovery linkage | CSV/JSON exports — `VERIFY: factpages.sodir.no` | ~1,900 (≈1,200 wildcats) |
| `nsta` | UK Continental Shelf | Wells, discoveries, fields, licences (GIS layers) | ArcGIS open-data downloads — `VERIFY: opendata-nstauthority.hub.arcgis.com` | ~2,300 E&A |
| `nlog` | Netherlands on/offshore | Wells + results | Downloads — `VERIFY: nlog.nl` | ~600 |
| `boem_bsee` | US Gulf of Mexico | Borehole data, field/reserve data | CSV — `VERIFY: data.boem.gov` | thousands; filter to exploration type codes |
| `nopims` | Australia offshore | Wells + results | `VERIFY: nopims.dmp.wa.gov.au` | ~900 |
| `gem_goget` | Global | Global Oil & Gas Extraction Tracker: fields/units, discovery year, location, status | XLSX/GeoJSON, free registration | Global field-level augmentation + frontier case-study coordinates |

**Label harmonization rules (`packages/labels/harmonize.py`) — these decisions are science, document them in the dataset card:**
1. **Wildcats only** for the primary dataset. Appraisal wells confirm known discoveries → including them is label leakage. (Sensitivity run with appraisal included, reported separately.)
2. Outcome mapping: {OIL, GAS, OIL/GAS} → `1`; {DRY} → `0`; {SHOWS} → `0` in primary (sensitivity: excluded). Per-regulator mapping table in `curated/outcome_map.csv`.
3. Deduplicate re-entries/sidetracks to one decision point per surface location.
4. Every well keeps `spud_year` — all time-aware features and hindcast splits key off it.
5. Target: **≥5,000 harmonized outcomes** after cleaning. Report the actual number; never round up in public copy.

---

## §6 — Data catalog · Layer 2 features (the global raster stack)

All-free gridded geoscience. Master grid: **EPSG:4326, 0.05° (~5 km)**, global, stored as a Zarr cube; continuous → bilinear resample, categorical → nearest.

| Ch | Layer | Source | Notes |
|----|-------|--------|-------|
| 1 | Free-air gravity anomaly | Sandwell & Smith marine gravity (Scripps, `VERIFY:` latest v32+) | Basement structure signal |
| 2 | Vertical gravity gradient | derived from ch1 | Edge detector for basins/highs |
| 3 | Magnetic anomaly | EMAG2 v3 (NOAA NCEI) | Basement/volcanics |
| 4 | Sediment thickness | GlobSed (NOAA total sediment thickness) | THE first-order control — no sediment, no oil |
| 5 | Sediment thickness gradient | derived | Depocenter edges |
| 6 | Moho depth | CRUST1.0 | Crustal architecture |
| 7 | Crustal type (cont/trans/oceanic) | CRUST1.0 | Encode ordinal |
| 8 | Bathymetry/elevation | GEBCO grid | Also drives dev-concept cost class in Layer 3 |
| 9 | Seafloor slope | derived from ch8 | |
| 10 | Surface heat flow | IHFC Global Heat Flow Database (points → kriged) | Source-rock maturity proxy; flag interpolation uncertainty |
| 11 | Distance to shelf break (200 m isobath) | derived | |
| 12 | Distance to nearest **pre-cutoff** discovery | derived from §5 | **Time-aware**: recomputed per training cutoff, else hindcast leaks |
| 13 | Distance to nearest **pre-cutoff** dry hole | derived from §5 | Time-aware, same rule |
| 14 | Geologic province id + type | USGS World Geologic Provinces (`VERIFY:` USGS Energy Data portal) | Also masks scoring: only score pixels with sediment > 500 m inside sedimentary provinces — never publish hotspots on cratons |

Normalization: robust z-score per channel (global stats persisted with `transform_version`). A per-province normalization variant exists behind a flag; the model card reports both, because province-identity leakage is exactly the kind of thing a sharp reviewer probes.

---

## §7 — Data catalog · Layer 3 (feasibility inputs)

| source_id | Feeds agent | What | Access |
|-----------|-------------|------|--------|
| `gem_infra` | Infrastructure | Global pipelines, LNG terminals, refineries (GeoJSON trackers) | Global Energy Monitor downloads, free registration |
| `gebco` | Infrastructure | Water depth at site → dev concept (§10.4) | already in stack |
| `wdpa` | Environment | World Database on Protected Areas polygons | `VERIFY: protectedplanet.net` download/API |
| `wgi` | Political risk | World Bank Worldwide Governance Indicators (6 dims) | World Bank API |
| `fsi` | Political risk | Fragile States Index | Fund for Peace CSV |
| `ofac_eu` | Political risk | OFAC SDN + EU consolidated sanctions lists | Official CSV/XML downloads |
| `eiti_rc` | Fiscal | EITI country data + resourcecontracts.org PSC full texts | Free portals |
| `curated_fiscal` | Fiscal | Per-country regime YAML: type (tax/royalty vs PSC), royalty %, CIT %, PSC splits, ringfencing — each field cites a source URL (EITI report, official law, EY/PwC oil-tax guide PDF) | `curated/fiscal/<ISO3>.yaml` |
| `curated_costs` | Economics | Cost benchmarks by development class (onshore, shelf tieback, deepwater tieback, FPSO standalone): capex $/boe range, opex $/boe, well cost, schedule-to-first-oil — every number cites a public source | `curated/cost_benchmarks.csv` |
| `curated_exclusions` | Financeability | Matrix of major European banks'/insurers' public upstream exclusion policies, with policy URL + date checked | `curated/financing_exclusions.csv` |

**Rule for all `curated_*` files:** hand-maintained is fine — *uncited* is not. The contract validator rejects any curated row lacking `source_url`. This is what lets you say "validated" about qualitative inputs, not just time series.

---

## §8 — Layer 1 spec: the market terminal

Twelve panels in a draggable terminal workspace (§13). Panel = data contract + derived metrics + provenance chips + a freshness badge.

1. **Command bar + ticker tape** — ⌘K command line (`ERDA>` prompt) with Bloomberg-style mnemonics: `CRV` curve, `INV` inventories, `OPEC`, `RIG`, `DISC` discovery monitor, `MAP <region>`, `MEMO <block|lat,lon>`, `VAL` validation, `HELP`. Ticker: Brent, WTI, spreads, curve slope, rig count Δ.
2. **Price & curve deck** — front months + full futures strip; contango/backwardation shading; historical curve ghost (1M/1Y ago).
3. **Spreads** — Brent–WTI, 3-2-1 crack, prompt spread.
4. **Inventories** — WPSR weekly bars vs 5-yr range band; days-of-cover line; JODI global cross-check toggle.
5. **OPEC+ compliance table** — per-country pledged vs delivered (MOMR secondary sources), compliance %, sortable dense grid.
6. **Rigs vs production** — dual axis + computed lead-lag correlation strip.
7. **Discovery Monitor** (the differentiator) — discovered volumes/year and success rate/year from the §5 label DB; per-basin creaming curves (cumulative discovered volume vs wildcat count) showing basin maturity.
8. **Event feed** — GDELT energy/chokepoint stream, severity-tagged, click-through to source.
9. **Prospectivity map** (Layer 2 hero — §13.4).
10. **Basin/block ranking table** — model score, calibration band, top SHAP drivers per row.
11. **Memo viewer** (Layer 3 output) with citation chips.
12. **/validation page** (§11) — a first-class screen, not a buried report.

**Reconciliation validators (`packages/validation/`), run nightly, rendered on /validation:**
- EIA vs JODI country-month production: |Δ| ≤ 5% pass, 5–10% warn, >10% fail with both values shown.
- WPSR week-over-week stock change ≡ reported build/draw (internal consistency).
- Curve monotonic-date check; stale-contract detector.
- Freshness SLA per source (e.g. WPSR ≤ 8 days, rigs ≤ 9 days, JODI ≤ 45 days).
- Unit tests on every derived-metric formula with hand-computed fixtures.

---

## §9 — Layer 2 spec: the prospectivity engine

### 9.1 Two models, deliberately
- **GBM (LightGBM)** on per-point engineered features → the *calibrated, explainable* block ranker (SHAP reason codes, same pattern as CreditForge).
- **Patch CNN** → the *heatmap*. ResNet-18 encoder adapted to 14 input channels, 64×64 patches (~320 km context) centered on well locations, binary head.
- Ship both; the UI shows CNN heatmap + GBM SHAP panel. They cross-check each other; disagreement zones get an "uncertain" hatch.

### 9.2 GBM features (per well / per scored cell)
Channel values at point + neighborhood stats (mean/std at 25 km, 100 km) + time-aware distances (ch12/13) + water-depth class + province historical success rate **computed pre-cutoff only** + basin maturity (position on creaming curve pre-cutoff).

### 9.3 CNN training
AdamW, cosine schedule, BCE with class weights, early stop on spatial-fold PR-AUC. Augment: flips + 90° rotations + channel dropout (robustness to missing grids). **Deep ensemble of 5 seeds** → mean = score, std = uncertainty band shown on map.

### 9.4 Spatial cross-validation (non-negotiable)
Leave-one-province-out across all provinces with ≥30 wildcats, PLUS a 50 km exclusion buffer: any training well within 50 km of a test well is dropped. Naive random CV on spatial data is leakage; a reviewer who knows geospatial ML checks for exactly this, and so does the /validation page.

### 9.5 Temporal hindcast
Train on wells spud ≤ 2005; test 2006–2025. All time-aware features recomputed at the 2005 cutoff. Report the same metric suite. Then the **frontier case-study panel**: using `gem_goget` + a hand-curated CSV of publicly reported frontier discovery locations (Guyana–Suriname: Liza etc.; Namibia Orange Basin: Venus, Graff, Mopane — every row cites a public press source), show where those areas ranked in the ≤2005 model's global percentile *before* anyone drilled them. Present as narrative ("the model had the Orange Basin in the top X% of unscored offshore acreage") — small-n case study, clearly labelled, never a headline metric.

### 9.6 Metrics & baselines
PR-AUC (primary; classes are imbalanced), ROC-AUC, Brier score, reliability diagram, lift@top-decile. Baselines that must be beaten to claim skill:
(a) random; (b) **logistic regression on distance-to-nearest-discovery alone** — the "drill next to old wells" heuristic; (c) sediment-thickness-threshold rule.
Beating (b) under spatial CV is the whole claim. 

### 9.7 Calibration
Isotonic regression fit on out-of-fold predictions. The calibrated probability is what flows into EMV (§10.5). Reliability curve published on /validation.

### 9.8 Falsification gate (Phase 3 exit)
If spatial-CV PR-AUC ≤ baseline (b): stop, write up the negative result honestly, ship the GBM diagnostic + Discovery Monitor + agents on user-supplied Pg, and say so publicly. A documented negative result with clean methodology is still a portfolio asset; a fake heatmap is a liability.

### 9.9 Inference & serving
Sliding window (stride 8 px) → global 0.05° probability + uncertainty rasters → masked per §6 ch14 → COG + vector tiles for deck.gl. Model card (`packages/models/cards/`) documents data, splits, metrics, limitations — linked from the UI footer.

---

## §10 — Layer 3 spec: the agentic feasibility committee

### 10.1 Committee topology (LangGraph)
```
Orchestrator
   ├─(parallel)─ Geoscience · Fiscal · PoliticalRisk · Infrastructure · Environment · Financeability
   ├────────────► Economist (calls deterministic engine — the ONLY path to numbers)
   ├────────────► RedTeam (attacks the draft: leakage? stale fiscal data? optimistic capex?)
   └────────────► Chair (synthesizes memo, enforces citation coverage)
```

### 10.2 Agent briefs
- **Geoscience** — model score + uncertainty at the block, offset wells within 100 km (from §5), basin creaming-curve position, analog discoveries. Tools: `get_model_score`, `get_offset_wells`, `get_basin_stats`.
- **Fiscal** — regime type, royalty/CIT/PSC split from `curated_fiscal`, licensing-round status. Tool: `get_fiscal_regime`.
- **PoliticalRisk** — WGI percentile, FSI, sanctions screen (OFAC/EU), licence-security notes. Tools: `get_governance`, `screen_sanctions`.
- **Infrastructure** — water depth, distance to nearest pipeline/terminal/refinery (GEM), → **development concept classifier** (§10.4). Tool: `classify_dev_concept`.
- **Environment** — WDPA overlap % within block + 25 km buffer, named protected areas. Tool: `get_protected_overlap`.
- **Financeability** — screens `curated_exclusions`: which capital pools could plausibly fund (European bank exclusions → NOC partner / trading-house prepay / PE). Tool: `screen_financing`.
- **Economist** — assembles engine inputs, runs it, reports. NO free-form math.
- **RedTeam** — required section in memo: "What would make this wrong."
- **Chair** — renders memo JSON → MD/PDF; rejects if citation coverage < 0.9.

### 10.3 Tool law
Every tool is a typed Python function over local DuckDB/Zarr — no live internet at memo time (reproducibility; a memo re-run on the same snapshot is byte-identical). Every tool return includes `source_ids`. The memo schema requires `source_ids` on every quantitative field; the coverage checker computes cited-fields/total-fields.

### 10.4 Development concept classifier (deterministic)
water depth ≤ 0 → onshore · ≤ 400 m & host ≤ 50 km → shelf tieback · > 400 m & host ≤ 70 km → deepwater tieback · else FPSO standalone. Concept → capex/opex/schedule row from `curated_costs`.

### 10.5 Economics engine (`packages/engine/`, pure, TDD)
Inputs: Pg (calibrated, §9.7) · resource distribution (lognormal fit to basin creaming curve → P90/P50/P10) · concept costs (§10.4) · fiscal take (§7) · price deck (Layer 1 curve, flat-real beyond strip; scenarios $50/$70/$90) · discount rate 10%.
Outputs: NPV(success), **EMV = Pg·NPV − (1−Pg)·well cost**, breakeven $/bbl, government take %, payback. Monte Carlo (10k, seeded) over resource × price × capex(±30%) → EMV distribution + P(EMV>0).
Tests: golden case hand-computed in the spec fixture; property tests (price↑→NPV↑; royalty↑→take↑; Pg↑→EMV↑ monotonicity).

### 10.6 Memo (the product)
One page: verdict (GO / CONDITIONAL / NO-GO) + EMV headline + six agent sections + RedTeam box + full citation appendix. Verdict logic is deterministic thresholds on EMV, P(EMV>0), sanctions flag, WDPA overlap — the LLM words it, rules decide it.

---

## §11 — Validation framework (the /validation page)

Three pillars, all rendered as a first-class UI screen — validation as a *feature*, which is the resume line.

**11.1 Data validation** — pandera contracts on every source; nightly reconciliation report (§8); freshness SLAs; provenance chips on every number in the UI (hover → source, timestamp, URL).

**11.2 Model validation** — spatial-CV metric table vs the three baselines; reliability diagram; hindcast panel; frontier case studies; ensemble uncertainty map; link to model card. All figures generated by `packages/models/evaluation/`, never pasted by hand.

**11.3 Engine & agent validation** — golden-case + property tests badge (CI); citation-coverage gauge per memo; red-team section presence check; memo determinism check (re-run hash on frozen snapshot).

**Fixtures:** `tests/fixtures/golden_block.yaml` — one fully hand-computed block economics case (every intermediate number worked out in comments) + `tests/fixtures/synthetic_wells.parquet` for pipeline tests. Clearly labelled synthetic; never enters data/.

---

## §12 — Claude Code operating setup

### 12.1 Session discipline
One phase per session where possible. Open with: "Read CLAUDE.md and ERDA_BUILD_SPEC.md §<relevant>. Plan ≤15 lines. Wait for go." Commit per logical step. Run tests before claiming done.

### 12.2 CLAUDE.md must contain
Project one-liner · the 8 rules from §0 verbatim · stack versions · phase order with gates · "deterministic core" file list · provenance schema · command cheatsheet (uv, pnpm, pytest, playwright) · pointer to the three skills.

### 12.3 Custom skills (`.claude/skills/`)
- **erda-design-system** — full §13 tokens, panel chrome spec, chart theming snippets for lightweight-charts/ECharts/deck.gl so every session produces identical styling.
- **erda-data-contracts** — the add-a-source recipe: contract → connector → validator → provenance → panel. Keeps source #12+ as clean as source #1.
- **erda-agent-tools** — the add-a-tool recipe: typed fn → schema → source_ids → register in graph → memo field mapping.

### 12.4 UI iteration loop
Use the **frontend-design skill** for the shell, then a **Playwright MCP screenshot loop**: Claude Code renders → screenshots → self-critiques against §13 → fixes. Budget explicit polish passes; Bloomberg-level is 40% data density, 60% typographic discipline.

---

## §13 — UI spec: the ERDA terminal

### 13.1 Design tokens (the "crude" palette — derived from the subject, not from a template)
- `--bg0 #0C0A07` warm bitumen black (NOT blue-black — crude is brown-black) · `--bg1 #14110C` panel · `--line #262019` hairline
- `--gold #E8A33D` primary accent (black gold; sparingly: commands, active states, curve M1)
- `--oil #3FA66A` discovery/oil wells · `--gas #D64550` gas wells · `--dry #6E6558` dry holes — **industry map convention (green oil / red gas), experts notice this**
- `--cyan #5FB3C9` water/offshore/secondary series · `--warn #E5484D` alerts only
- Prospectivity ramp: **viridis** (perceptually uniform, colorblind-safe — scientific credibility beats neon)
- Type: **Space Grotesk** (display, panel titles, sparingly) · **IBM Plex Sans** (UI) · **IBM Plex Mono** (ALL numerals, `font-variant-numeric: tabular-nums`)
- Density: 8 px grid, 12–13 px data type, hairline borders, zero border-radius on panels, radius 2 px on chips. Motion ≤ 120 ms, reduced-motion respected.
- **Signature element:** the `ERDA>` command line with amber caret + a seismic-wiggle horizontal divider motif (a thin SVG trace) under panel titles. One signature, everything else disciplined.

### 13.2 Layout
```
┌──────────────────────────────────────────────────────────────────────┐
│ ERDA>  _                    ticker: BRENT 74.12 ▲ · WTI · B-W · RIGS │
├───────────────┬──────────────────────────────────┬───────────────────┤
│ CRV curve     │                                  │ DISC monitor      │
│ (lw-charts)   │        PROSPECTIVITY MAP         │ (ECharts)         │
├───────────────┤        (deck.gl hero)            ├───────────────────┤
│ INV inventories│  heat ▓▓▒▒░ · wells ●●○ · infra │ RANK basin table  │
├───────────────┤                                  ├───────────────────┤
│ OPEC table    │   [Generate memo for block ▸]    │ EVENTS feed       │
└───────────────┴──────────────────────────────────┴───────────────────┘
   react-grid-layout: draggable/resizable; presets: MARKET / EXPLORE / MEMO / VAL
```

### 13.3 Reference repos (study, don't fork blindly)
| Repo | Why it's on the list |
|------|----------------------|
| `tradingview/lightweight-charts` | THE canvas library for financial series; curve/price panels |
| `visgl/deck.gl` + `maplibre/maplibre-gl-js` | GPU heatmap/scatter over free CARTO dark basemap — the map hero |
| `finos/perspective` | Trading-grade streaming pivot tables (OPEC/ranking panels) |
| `ag-grid/ag-grid` (community) | Fallback dense grid if Perspective is overkill |
| `apache/echarts` | Creaming curves, calendars, specialty charts |
| `pacocoursey/cmdk` | The ⌘K command palette that becomes `ERDA>` |
| `react-grid-layout/react-grid-layout` | Draggable terminal workspace |
| `shadcn/ui` | Primitives to restyle with §13.1 tokens |
| `OpenBB-finance/OpenBB` | Reference architecture for open financial terminals |
| `sandeep-jaiswar/terminal-ui` | Bloomberg-inspired React component patterns, dark-first tokens |
| `KoNananachan/Neuberg` | Study its 500-panel dock layout + panel registry pattern |
| `keplergl/kepler.gl`, `vasturiano/globe.gl` | Map UX inspiration; globe.gl for one cinematic demo-video shot |

### 13.4 Map spec
MapLibre + CARTO dark-matter tiles · deck.gl layers: prospectivity raster (viridis, opacity slider) · uncertainty hatch · well scatter (oil/gas/dry tokens, time slider by spud year) · GEM infra lines · WDPA overlay · block picker → right-rail block card → "Generate memo" → SSE-streamed agent progress → memo view.

### 13.5 Anti-goals
No light mode. No rounded SaaS cards, no gradients, no glassmorphism, no emoji in UI. No spinner longer than 300 ms without a skeleton. Nothing animates that doesn't carry information.

---

## §14 — Build phases & gates

| Phase | Scope | Gate (must pass to advance) |
|-------|-------|------------------------------|
| **P0** | Scaffold repo (§3), CLAUDE.md, 3 skills, CI, empty shell with tokens + ⌘K | CI green; shell screenshot passes design self-critique |
| **P1** | Layer 1: sources 1–9, derived metrics, validators, nightly Action | Nightly run green; /validation renders reconciliation report; every panel number has provenance chip |
| **P2** | Labels harmonized (§5) + raster stack (§6) + EDA notebook + dataset card | ≥5,000 outcomes or documented actual; stack Zarr written; label-map decisions documented |
| **P3** | GBM → spatial-CV harness → CNN → calibration → hindcast → model card | **Falsification gate §9.8**: beats baseline (b) on spatial CV, calibration plot sane — or honest stop |
| **P4** | Economics engine, TDD | Golden + property tests pass; engine is import-pure (no I/O) |
| **P5** | Agents + memo + SSE streaming | 3 showcase memos: citation coverage ≥ 0.9, red-team section present, deterministic re-run hash matches |
| **P6** | Full UI: map hero, all panels, memo viewer, /validation | Playwright visual suite passes; map interactive < 2 s; demo mode runs fully offline from frozen snapshot |
| **P7** | Deploy + demo freeze + README + model card + video assets | Public URL live; 5 precomputed showcase blocks; README with honest-boundaries section |

Estimated effort: 6–8 focused weeks. Sequence after the RHEINGOLD freeze; P1 and P2 can interleave.

---

## §15 — Deployment

- **Web:** Next.js on Vercel free tier. **API + agents:** FastAPI in Docker on Hugging Face Spaces (your PRAETOR pattern). **Data artifacts:** parquet/Zarr/COG snapshots on a HF Dataset; nightly GitHub Action refreshes and pushes.
- **Demo mode (critical):** `demo_freeze.py` snapshots everything; the public app boots from the snapshot so it *never* breaks mid-demo or mid-video. A "LIVE/SNAPSHOT" badge tells the truth about which mode is running.
- Claude API key server-side only; memo generation rate-limited; showcase memos precomputed so recruiters never wait.

---

## §16 — Claude Code kickoff prompt

```
You are the lead engineer building ERDA — an upstream oil exploration intelligence
platform: validated market terminal + deep-learning prospectivity engine + agentic
feasibility committee. This is a portfolio-defining project judged by energy-finance
professionals and ML reviewers. Correctness and craft over speed.

BEFORE ANY CODE: read CLAUDE.md, then ERDA_BUILD_SPEC.md, in full. They are the
authoritative spec (§ references point into the build spec). Then post a plan
(≤15 lines) for Phase 0 only and wait for my go-ahead.

ENVIRONMENT: confirm versions first (uv --version; node --version; pnpm --version;
python ≥3.11). git init; commit per logical step with clear messages.

RULES OF ENGAGEMENT
- Build strictly in phase order (§14). Never skip a gate. Never claim a gate passed
  without showing the evidence (test output, screenshot, validation report).
- packages/engine and packages/geo are deterministic: pure Python, no network, no
  unseeded randomness, no LLM. The economics engine is TEST-FIRST from the golden
  fixture; a red test blocks everything downstream.
- LLM narrates, code calculates: no model call ever performs arithmetic.
- Never fabricate data. A failing source raises and stops; it does not get invented.
- Every persisted number carries provenance {source_id, retrieved_at, source_url,
  transform_version}. A number without provenance is a bug.
- Honor every VERIFY: tag — confirm live endpoints before hardcoding.
- Phase 3 falsification gate is real: if spatial-CV skill ≤ the distance-to-discovery
  baseline, stop and report honestly. Do not ship a map without demonstrated skill.
- Use .claude/skills/erda-design-system for ALL UI styling; iterate the UI with
  Playwright screenshots against §13; ask ONE focused question when the spec is
  genuinely ambiguous, otherwise proceed.

MILESTONE 1 — Phase 0: scaffold per §3, CLAUDE.md, the three skills, CI, and the
empty terminal shell (tokens, ⌘K ERDA> palette, grid layout, ticker stub). The shell
must look institutional while empty. Then stop for review.
```

---

## §17 — Claude Cowork prompt: the demo video

Paste into Cowork with the deployed URL (or local dev URL) available. Cowork's toolkit here: browser control, screenshots, code execution (ffmpeg/Pillow), file output. No screen-recording assumption, no audio — the video is built from stills → Ken Burns GIF segments → stitched MP4 with burned-in captions (LinkedIn autoplays muted, so captions ARE the audio).

```
You are producing a 55-second silent demo video of ERDA, an oil exploration
intelligence terminal, for a LinkedIn post. Build it from browser screenshots
assembled into motion with ffmpeg. Polished, dark, cinematic, truthful.

INPUTS
- App URL: <PASTE URL> (dark theme is default; app runs in SNAPSHOT demo mode)
- Working dir: create ./erda_video/{shots,segments,cards,final}
- Font for cards: IBM Plex Mono (download TTF); accent color #E8A33D on #0C0A07

HARD RULES
- Never fabricate numbers or claims on title cards. Only use text/metrics visible
  in the app (especially the /validation page). If a metric isn't on screen,
  write the card without numbers.
- 1920x1080 viewport, 100% zoom, hide cursor, wait for data-loaded state (no
  skeletons/spinners in any shot). Retake any shot with cut-off text.
- Keep every scene 3–8s. Total 50–58s. 30fps. Silent, captions burned in.

STORYBOARD (capture stills for each; 3–6 stills per moving scene)
S1 3s  Title card: "ERDA" wordmark + "The earth keeps records." (render as HTML
       in-browser, screenshot it — do not draw text with ffmpeg for cards)
S2 3s  Hook card: "One deepwater well: $100M+. Most come up dry."
S3 6s  Full terminal workspace, slow Ken Burns pan L→R. Caption: "A validated
       oil-market terminal. Every number carries its source."
S4 5s  Curve + spreads panels close-up, gentle zoom-in. Caption: "Futures curve
       in, price deck out."
S5 5s  Discovery Monitor panel. Caption: "The world is finding less new oil
       than at any point in decades."
S6 8s  Map hero: capture a zoom sequence (world → North Sea) by taking stills at
       3 zoom levels, then toggle prospectivity heatmap on; final still with well
       dots visible. Caption: "A CNN trained on 50+ years of public well outcomes."
S7 6s  /validation model panel (spatial CV table or reliability plot). Caption:
       "Validated the hard way: spatial cross-validation and a temporal hindcast."
S8 8s  Memo flow: type `MEMO <showcase block>` in the ERDA> palette (still),
       agent progress (still), finished memo scrolled to verdict + EMV (2 stills).
       Caption: "Nine agents. Deterministic economics. Every claim cited."
S9 4s  Outro card: "ERDA — built on 100% free public data. Self-built, not
       client work." + repo/app link, small stack line.

ASSEMBLY (ffmpeg via code execution)
1. Per scene: stills → motion with zoompan (Ken Burns, ease, 30fps), e.g.
   ffmpeg -loop 1 -i shot.png -vf "zoompan=z='min(zoom+0.0008,1.08)':d=150:s=1920x1080,fps=30" -t 5 seg.mp4
2. Captions: drawtext, IBM Plex Mono 34px, #EDE6DA on rgba(12,10,7,0.72) box,
   bottom-left, 48px margins, consistent across all scenes.
3. Stitch with xfade (0.4s crossfades), then final encode:
   libx264, crf 18, yuv420p, faststart. Target < 60 MB.
4. Also export: (a) 1080x1080 center-crop version, (b) the 3 best stills as PNGs
   for the post, (c) a 6-frame GIF teaser of S6 under 8 MB.

QC CHECKLIST before delivering (verify each, re-shoot if failed)
[ ] No spinners/skeletons/empty panels in any frame
[ ] No cut-off text; captions readable on a phone (test-view at 400px wide)
[ ] Timing 50–58s; smooth crossfades; consistent color/theme across scenes
[ ] Every card claim is verifiable on-screen in the app
[ ] Files in ./erda_video/final: erda_demo_169.mp4, erda_demo_11.mp4,
    still_1..3.png, teaser.gif + a one-line caption suggestion for the post
```

---

## §18 — Launch assets

### 18.1 LinkedIn post (fill [METRIC] placeholders from /validation after Phase 3 — never before)

> The most expensive coin flip in business: one deepwater exploration well can cost over $100 million. Most come up dry.
>
> Meet ERDA. In Wagner's Ring, Erda is the goddess who knows what lies beneath the earth. In German, petroleum is literally "Erdöl", earth oil. The name picked itself.
>
> Three layers:
>
> 1. A market terminal. Prices, curve structure, OPEC+ compliance, rig counts, inventories, and a discovery monitor built from primary well data showing an uncomfortable truth: the world is finding less new oil than at any point in decades. Every number on screen carries its source and timestamp.
>
> 2. A deep learning prospectivity engine. A CNN trained on 50+ years of public exploration outcomes from Norway, the UK, the Netherlands, the Gulf of Mexico and Australia, reading satellite gravity, magnetics, sediment thickness and crustal structure to score where undrilled acreage resembles past success. Validated with spatial cross validation against the obvious baseline, "just drill next to old wells", and a temporal hindcast: train on wells before 2005, test on twenty years of outcomes the model never saw. [METRIC].
>
> 3. An agentic investment committee. Nine agents assess fiscal terms, political risk, infrastructure, environmental overlap and financeability, then a deterministic engine computes expected monetary value. The LLM narrates. Python calculates. Every claim in the memo is cited.
>
> Built end to end on 100% free public data. Self-built, not client work.
>
> Honest limit: this is a screening tool, not seismic. It ranks acreage, it does not find oil.
>
> Would you trust a model to tell you where to drill first?

### 18.2 Resume bullets
- Built ERDA, an oil-exploration intelligence platform: 20+ free public data sources with cross-source reconciliation, a CNN + GBM prospectivity engine trained on [N] historical well outcomes with leakage-safe spatial cross-validation and a 20-year temporal hindcast, and a 9-agent feasibility committee producing cited, EMV-based investment memos via a deterministic economics engine.
- Engineered a global 14-channel geophysical raster stack (satellite gravity, magnetics, sediment thickness, heat flow) and harmonized exploration outcomes from five national regulators into a single supervised dataset.
- Shipped a Bloomberg-style terminal UI (Next.js, deck.gl, TradingView charts) with a first-class validation page: data freshness SLAs, reconciliation reports, model reliability curves and per-memo citation coverage.

### 18.3 Risk register (for your eyes)
MOMR PDF parsing is brittle → semi-automated flag + curated fallback. yfinance is unofficial → indicative label + degradation path. GoM/NOPIMS exploration-type filtering is messy → budget cleaning time. Frontier hindcast is small-n → always framed as case study. Biggest reputational risk is an overclaimed map → §9.8 exists for a reason.

*End of spec — v1.0. VERIFY tags before build. Sie weiß, wo es liegt.*
