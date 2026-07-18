# Feasibility Memo — NOR-VORING-DEMO

**Verdict: GO** · EMV **508.2 $MM** · P(EMV>0) **93%** · Pg **0.25** (user-supplied (§9.8 — the falsification gate failed; no model Pg ships))

_Generated 2026-07-18T19:16:12.449989+00:00 · frozen local snapshot — no live internet at memo time (§10.3) · citation coverage 100% · determinism hash `27ac7b182f41c932…`_

## Geoscience

[template narration — no LLM key configured] You are the Geoscience member of an upstream exploration screening committee. Facts as provided by tools: Tool JSON: {'model': {'model_status': 'NO MODEL — §9.8 falsification gate failed; no Pg from a model', 'pg_source': 'user-supplied', 'in_scoreable_mask': True, 'gate_reference': 'packages/models/cards/NEGATIVE_RESULT.md', 'source_ids': ['model_eval_gbm', 'usgs_provinces', 'globsed']}, 'offsets': {'radius_km': 100.0, 'n_wells': 27, 'n_labeled': 27, 'n_discoveries': 13, 'offset_success_rate': 0.481,

- **model_status**: NO MODEL — §9.8 falsification gate failed; no Pg from a model _[model_eval_gbm, usgs_provinces, globsed]_
- **offset_wells_100km**: 27 wells _[sodir, labels_harmonized]_
- **offset_success_rate**: 0.481 _[sodir, labels_harmonized]_
- **basin**: Ocean _[labels_harmonized, usgs_provinces]_
- **basin_wildcats**: 38 wells _[labels_harmonized, usgs_provinces]_

## Fiscal

[template narration — no LLM key configured] You are the Fiscal member of an upstream exploration screening committee. Facts as provided by tools: Tool JSON: {'regime': {'iso3': 'NOR', 'country': 'Norway (Norwegian Continental Shelf)', 'regime_type': 'tax_royalty', 'royalty_rate': 0.0, 'royalty_note': 'No production royalty. norskpetroleum.no (official site of the Ministry of Energy and the Norwegian Offshore Directorate): "Exemptions, such as royalties, are no longer a part of the tax system."', 'cit_rate': 0.22, 'cit_note': '"The ordinary

- **regime_type**: tax_royalty _[curated_fiscal]_
- **cit_rate**: 0.22 fraction _[curated_fiscal]_
- **royalty_rate**: 0.0 fraction _[curated_fiscal]_

## Political Risk

[template narration — no LLM key configured] You are the Political Risk member of an upstream exploration screening committee. Facts as provided by tools: Tool JSON: {'governance': {'data_gap': 'snapshot table missing: wgi_governance'}, 'sanctions': {'data_gap': 'snapshot table missing: sanctions_programs'}}

- **governance_gap**: snapshot table missing: wgi_governance _[snapshot]_
- **sanctions_gap**: snapshot table missing: sanctions_programs _[snapshot]_

## Infrastructure & Development Concept

[template narration — no LLM key configured] You are the Infrastructure member of an upstream exploration screening committee. Facts as provided by tools: Tool JSON: {'concept': {'water_depth_m': 963.8, 'host_distance_km': 130.0, 'concept': 'fpso_standalone', 'cost_benchmarks': {'concept': 'fpso_standalone', 'capex_usd_boe_low': '8', 'capex_usd_boe_high': '18', 'opex_usd_bbl_low': '6.28', 'opex_usd_bbl_high': '6.65', 'well_cost_musd_low': '60', 'well_cost_musd_high': '240', 'schedule_years_low': '2.5', 'schedule_years_high': '3.2'}, 'cost_notes': "c

- **water_depth_m**: 963.8 m _[etopo2022, curated_costs, erda_engine.concept]_
- **host_distance_km**: 130.0 km _[etopo2022, curated_costs, erda_engine.concept]_
- **dev_concept**: fpso_standalone _[etopo2022, curated_costs, erda_engine.concept]_

## Environment

[template narration — no LLM key configured] You are the environment member of an upstream exploration screening committee. Facts as provided by tools: Tool JSON: {'data_gap': 'wdpa_areas.parquet missing from snapshot'}. The snapshot lacks this data — say so and what it means.

- **data_gap**: wdpa_areas.parquet missing from snapshot _[snapshot]_

## Financeability

[template narration — no LLM key configured] You are the Financeability member of an upstream exploration screening committee. Facts as provided by tools: Tool JSON: {'financing': {'n_institutions_checked': 10, 'n_restricting_upstream': 10, 'restricting': [{'institution': 'BNP Paribas', 'type': 'bank', 'policy_url': 'https://web.archive.org/web/20260513095044/https://cdn-group.bnpparibas.com/uploads/file/bnpparibas_csr_sector_policy_oil_gas.pdf'}, {'institution': 'Societe Generale', 'type': 'bank', 'policy_url': 'https://www.societegenerale.com/site

- **institutions_checked**: 10 institutions _[curated_exclusions]_
- **restricting_upstream**: 10 institutions _[curated_exclusions]_

## Economics

[template narration — no LLM key configured] You are the Economist member of an upstream exploration screening committee. Facts as provided by tools: Tool JSON: {'economics': {'pg': 0.25, 'pg_provenance': 'user-supplied (§9.8 — the falsification gate failed; no model Pg ships)', 'npv_success_musd': 2302.91, 'emv_musd': 508.23, 'breakeven_usd_bbl': 33.66, 'government_take': 0.2699, 'payback_year': 4, 'mc': {'emv_mean_musd': 639.18, 'emv_p10_musd': 50.08, 'emv_p50_musd': 508.56, 'emv_p90_musd': 1388.49, 'p_emv_positive': 0.9307, 'n_draws': 10000,

- **pg**: 0.25 probability _[user_supplied]_
- **price_m1**: 82.49 $/bbl _[yf_curve]_
- **npv_success**: 2302.91 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **emv**: 508.23 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **breakeven**: 33.66 $/bbl _[erda_engine, curated_fiscal, curated_costs]_
- **government_take**: 0.2699 fraction _[erda_engine, curated_fiscal, curated_costs]_
- **p_emv_positive**: 0.9307 probability _[erda_engine, curated_fiscal, curated_costs]_
- **mc_seed**: 7 _[erda_engine, curated_fiscal, curated_costs]_

## Red Team — what would make this wrong

[template narration — no LLM key configured] You are the Red Team of an exploration screening committee. Facts as provided by tools: All tool JSON: {'environment': {'data_gap': 'wdpa_areas.parquet missing from snapshot'}, 'financeability': {'financing': {'n_institutions_checked': 10, 'n_restricting_upstream': 10, 'restricting': [{'institution': 'BNP Paribas', 'type': 'bank', 'policy_url': 'https://web.archive.org/web/20260513095044/https://cdn-group.bnpparibas.com/uploads/file/bnpparibas_csr_sector_policy_oil_gas.pdf'}, {'insti

## Citation appendix

- `curated_costs` ← economist.breakeven, economist.emv, economist.government_take, economist.mc_seed, economist.npv_success, economist.p_emv_positive, infrastructure.dev_concept, infrastructure.host_distance_km, infrastructure.water_depth_m
- `curated_exclusions` ← financeability.institutions_checked, financeability.restricting_upstream
- `curated_fiscal` ← economist.breakeven, economist.emv, economist.government_take, economist.mc_seed, economist.npv_success, economist.p_emv_positive, fiscal.cit_rate, fiscal.regime_type, fiscal.royalty_rate
- `erda_engine` ← economist.breakeven, economist.emv, economist.government_take, economist.mc_seed, economist.npv_success, economist.p_emv_positive
- `erda_engine.concept` ← infrastructure.dev_concept, infrastructure.host_distance_km, infrastructure.water_depth_m
- `etopo2022` ← infrastructure.dev_concept, infrastructure.host_distance_km, infrastructure.water_depth_m
- `globsed` ← geoscience.model_status
- `labels_harmonized` ← geoscience.basin, geoscience.basin_wildcats, geoscience.offset_success_rate, geoscience.offset_wells_100km
- `model_eval_gbm` ← geoscience.model_status
- `snapshot` ← environment.data_gap, political_risk.governance_gap, political_risk.sanctions_gap
- `sodir` ← geoscience.offset_success_rate, geoscience.offset_wells_100km
- `user_supplied` ← economist.pg
- `usgs_provinces` ← geoscience.basin, geoscience.basin_wildcats, geoscience.model_status
- `yf_curve` ← economist.price_m1

_Screening tool — ranks resemblance and economics at area level; not seismic; never "oil is here."_