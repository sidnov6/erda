---
name: erda-data-contracts
description: How to add or modify a data source in packages/ingestion — contract, connector, validator, provenance, panel wiring. Use whenever touching ingestion, pandera contracts, or the provenance ledger.
---

# ERDA data contracts — the add-a-source recipe

Follow this every time. Source #12+ must be as clean as source #1. Spec refs: §0 rules 4–6, §4, §7, §8, §11.1, §12.3.

## 1. THE LAW (§0, non-negotiable)

- **Never fabricate data.** If a source fails, raise and stop. No placeholder numbers, ever. Synthetic data exists only in test fixtures (§11.3), clearly labelled.
- **Provenance is mandatory.** Every persisted number carries `{source_id, retrieved_at, source_url, transform_version}`. A number without provenance is a bug.
- **Honor `VERIFY:` tags.** Endpoints in the spec may have drifted since July 2026. Confirm the live endpoint against the linked source at build time before hardcoding anything.

## 2. RECIPE — adding source N

1. **Register** `source_id` + metadata (name, access method, cadence, license/key notes) in the provenance ledger (`packages/contracts`).
2. **Contract.** Write the pandera schema in `packages/contracts`: exact columns, dtypes, nullability rules, units encoded in column names (e.g. `production_kbd`, `price_usd_bbl`). Validation failure = hard error.
3. **Connector.** One module: `packages/ingestion/<source_id>.py`. Fetch → normalize to the contract → attach provenance to every row → write parquet to `data/parquet/`. No other module touches the raw endpoint.
4. **Validator hooks.** In `packages/validation`: freshness SLA for the source (see §5 table below) and a reconciliation partner if one exists (§8 — e.g. EIA↔JODI country-month production: |Δ| ≤5% pass, 5–10% warn, >10% fail with both values shown; WPSR week-over-week change ≡ reported build/draw; curve monotonic-date + stale-contract checks). Runs nightly, renders on /validation.
5. **Derived metrics.** Any computed series goes in `packages/ingestion/derived.py` as a pure function with a unit test against a hand-computed fixture. Never compute metrics inline in a connector or panel.
6. **Panel wiring.** The consuming panel gets a freshness badge and provenance chips (hover → source, timestamp, URL) on every number.
7. **Tests.** Contract test against a small recorded fixture checked into the repo. Never hit the live network in CI.

## 3. CURATED FILES RULE (§7)

Hand-maintained is fine — *uncited* is not. Every row in `data/curated/*` (`curated_rounds`, `curated_fiscal`, `curated_costs`, `curated_exclusions`, ...) must carry a `source_url`. The contract validator rejects any curated row lacking one.

## 4. FAILURE SEMANTICS

Raise typed errors; never return partial or invented data:

- `SourceUnavailable` — fetch failed, endpoint down, auth broken.
- `ContractViolation` — data arrived but failed the pandera schema.
- `StaleData` — freshness SLA breached.

No silent fallbacks. The only degradation paths are the ones the spec names: `yf_curve` contract-strip failure → front-month + EIA STEO path, labelled **indicative** (§4 #3); `opec` MOMR table extraction marked `extraction=semi_automated` with curated fallback; `sec_reserves` curated fallback CSV with source URLs. Anything else that fails, fails loudly.

## 5. CADENCE + SLA (§4, §8)

| source_id | Cadence | Freshness SLA | Endpoint note |
|-----------|---------|---------------|---------------|
| `eia_v2` (WPSR) | Weekly/Monthly | WPSR ≤ 8 days | `VERIFY: https://api.eia.gov/v2/` — series IDs pinned in `curated/eia_series.yaml` |
| `baker_hughes` | Weekly | ≤ 9 days | `VERIFY: rigcount.bakerhughes.com` (XLSX) |
| `jodi` | Monthly | ≤ 45 days | `VERIFY: jodidb.org` (bulk CSV) |
| `fred` | Daily | daily series, flag if stale | free key |
| `yf_curve` | Daily | daily; stale-contract detector applies | unofficial; degradation path above |
| `opec` | Monthly | monthly MOMR cycle | `VERIFY: asb.opec.org` (ASB); MOMR via `pdfplumber` |
| `wb_pinksheet` | Monthly | monthly | XLSX |
| `comtrade` | Monthly/Annual | per release | free key |
| `gdelt` | 15-min | near-real-time feed | DOC 2.0 API, no key |
| `sec_reserves` | Annual | annual 10-K cycle | EDGAR, no key |
| `curated_rounds` | As-needed | n/a — citation rule applies | every row needs `source_url` |
| `wdpa` (Layer 3) | per release | per release | `VERIFY: protectedplanet.net` |

SLAs without a number in the spec: pick a sensible multiple of cadence, encode it in the validator, and document it on /validation — do not leave a source without an SLA.
