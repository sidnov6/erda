# Feasibility Memo — NAM-SPECULATIVE-DEMO

**Verdict: NO_GO** · EMV **-97.2 $MM** · P(EMV>0) **13%** · Pg **0.05** (user-supplied (§9.8 — the falsification gate failed; no model Pg ships))

_Generated 2026-07-19T07:30:53.322917+00:00 · frozen local snapshot — no live internet at memo time (§10.3) · citation coverage 100% · determinism hash `8d6a30aba50af022…`_

## Geoscience

[template narration — no LLM key configured] You are the Geoscience member of an upstream exploration screening committee. Facts as provided by tools: Tool JSON: {'model': {'model_status': 'NO MODEL — §9.8 falsification gate failed; no Pg from a model', 'pg_source': 'user-supplied', 'in_scoreable_mask': True, 'gate_reference': 'packages/models/cards/NEGATIVE_RESULT.md', 'source_ids': ['model_eval_gbm', 'usgs_provinces', 'globsed']}, 'offsets': {'radius_km': 100.0, 'n_wells': 0, 'n_labeled': 0, 'n_discoveries': 0, 'offset_success_rate': None, 'ne

- **model_status**: NO MODEL — §9.8 falsification gate failed; no Pg from a model _[model_eval_gbm, usgs_provinces, globsed]_
- **offset_wells_100km**: 0 wells _[sodir, nsta, nlog, boem_bsee, nopims, labels_harmonized]_
- **offset_success_rate**: no labeled offsets _[sodir, nsta, nlog, boem_bsee, nopims, labels_harmonized]_
- **basin**: Ocean _[labels_harmonized, usgs_provinces]_
- **basin_wildcats**: 38 wells _[labels_harmonized, usgs_provinces]_

## Fiscal

[template narration — no LLM key configured] You are the Fiscal member of an upstream exploration screening committee. Facts as provided by tools: Tool JSON: {'regime': {'iso3': 'NAM', 'country': 'Namibia', 'regime_type': 'tax_royalty', 'royalty_rate': 0.05, 'royalty_note': '"5% of gross revenue", valued at market value at the agreed off-take point; levied under the Petroleum (Exploration and Production) Act 2 of 1991; deductible in computing Petroleum Income Tax (NAMCOR fiscal regime document). Chambers 2025 practice guide confirms 5% of ma

- **regime_type**: tax_royalty _[curated_fiscal]_
- **cit_rate**: 0.35 fraction _[curated_fiscal]_
- **royalty_rate**: 0.05 fraction _[curated_fiscal]_

## Political Risk

[template narration — no LLM key configured] You are the Political Risk member of an upstream exploration screening committee. Facts as provided by tools: Tool JSON: {'governance': {'iso3': 'NAM', 'wgi_year': 2024, 'wgi_estimates': {'CC.EST': 0.127, 'GE.EST': 0.099, 'PV.EST': 0.547, 'RQ.EST': 0.135, 'RL.EST': 0.328, 'VA.EST': 0.337}, 'source_ids': ['wgi'], 'fsi_total': None, 'fsi_note': 'FSI table absent from snapshot'}, 'sanctions': {'iso3': 'NAM', 'sanctioned': False, 'programs': [], 'lists': [], 'source_ids': ['ofac_eu']}}

- **wgi_rule_of_law**: 0.328 estimate (−2.5…2.5) _[wgi]_
- **sanctioned**: False _[ofac_eu]_

## Infrastructure & Development Concept

[template narration — no LLM key configured] You are the Infrastructure member of an upstream exploration screening committee. Facts as provided by tools: Tool JSON: {'concept': {'water_depth_m': 2707.0, 'host_distance_km': 300.0, 'concept': 'fpso_standalone', 'cost_benchmarks': {'concept': 'fpso_standalone', 'capex_usd_boe_low': '8', 'capex_usd_boe_high': '18', 'opex_usd_bbl_low': '6.28', 'opex_usd_bbl_high': '6.65', 'well_cost_musd_low': '60', 'well_cost_musd_high': '240', 'schedule_years_low': '2.5', 'schedule_years_high': '3.2'}, 'cost_notes': "

- **water_depth_m**: 2707.0 m _[etopo2022, curated_costs, erda_engine.concept]_
- **host_distance_km**: 300.0 km _[etopo2022, curated_costs, erda_engine.concept]_
- **dev_concept**: fpso_standalone _[etopo2022, curated_costs, erda_engine.concept]_

## Environment

[template narration — no LLM key configured] You are the Environment member of an upstream exploration screening committee. Facts as provided by tools: Tool JSON: {'wdpa': {'radius_km': 25.0, 'overlap_pct': 0.0, 'areas': [], 'source_ids': ['wdpa']}}

- **wdpa_overlap_pct**: 0.0 % _[wdpa]_
- **protected_areas_nearby**: 0 areas _[wdpa]_

## Financeability

[template narration — no LLM key configured] You are the Financeability member of an upstream exploration screening committee. Facts as provided by tools: Tool JSON: {'financing': {'n_institutions_checked': 10, 'n_restricting_upstream': 10, 'restricting': [{'institution': 'BNP Paribas', 'type': 'bank', 'policy_url': 'https://web.archive.org/web/20260513095044/https://cdn-group.bnpparibas.com/uploads/file/bnpparibas_csr_sector_policy_oil_gas.pdf'}, {'institution': 'Societe Generale', 'type': 'bank', 'policy_url': 'https://www.societegenerale.com/site

- **institutions_checked**: 10 institutions _[curated_exclusions]_
- **restricting_upstream**: 10 institutions _[curated_exclusions]_

## Economics

[template narration — no LLM key configured] You are the Economist member of an upstream exploration screening committee. Facts as provided by tools: Tool JSON: {'economics': {'pg': 0.05, 'pg_provenance': 'user-supplied (§9.8 — the falsification gate failed; no model Pg ships)', 'npv_success_musd': 1096.51, 'emv_musd': -97.17, 'breakeven_usd_bbl': 42.1, 'government_take': 0.5015, 'payback_year': 5, 'mc': {'emv_mean_musd': -78.28, 'emv_p10_musd': -153.49, 'emv_p50_musd': -97.33, 'emv_p90_musd': 20.62, 'p_emv_positive': 0.1291, 'n_draws': 10000,

- **pg**: 0.05 probability _[user_supplied]_
- **price_m1**: 82.49 $/bbl _[yf_curve]_
- **npv_success**: 1096.51 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **emv**: -97.17 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **breakeven**: 42.1 $/bbl _[erda_engine, curated_fiscal, curated_costs]_
- **government_take**: 0.5015 fraction _[erda_engine, curated_fiscal, curated_costs]_
- **p_emv_positive**: 0.1291 probability _[erda_engine, curated_fiscal, curated_costs]_
- **mc_seed**: 7 _[erda_engine, curated_fiscal, curated_costs]_

## Red Team — what would make this wrong

[template narration — no LLM key configured] You are the Red Team of an exploration screening committee. Facts as provided by tools: All tool JSON: {'environment': {'wdpa': {'radius_km': 25.0, 'overlap_pct': 0.0, 'areas': [], 'source_ids': ['wdpa']}}, 'financeability': {'financing': {'n_institutions_checked': 10, 'n_restricting_upstream': 10, 'restricting': [{'institution': 'BNP Paribas', 'type': 'bank', 'policy_url': 'https://web.archive.org/web/20260513095044/https://cdn-group.bnpparibas.com/uploads/file/bnpparibas_csr_sector

## Citation appendix

- `boem_bsee` ← geoscience.offset_success_rate, geoscience.offset_wells_100km
- `curated_costs` ← economist.breakeven, economist.emv, economist.government_take, economist.mc_seed, economist.npv_success, economist.p_emv_positive, infrastructure.dev_concept, infrastructure.host_distance_km, infrastructure.water_depth_m
- `curated_exclusions` ← financeability.institutions_checked, financeability.restricting_upstream
- `curated_fiscal` ← economist.breakeven, economist.emv, economist.government_take, economist.mc_seed, economist.npv_success, economist.p_emv_positive, fiscal.cit_rate, fiscal.regime_type, fiscal.royalty_rate
- `erda_engine` ← economist.breakeven, economist.emv, economist.government_take, economist.mc_seed, economist.npv_success, economist.p_emv_positive
- `erda_engine.concept` ← infrastructure.dev_concept, infrastructure.host_distance_km, infrastructure.water_depth_m
- `etopo2022` ← infrastructure.dev_concept, infrastructure.host_distance_km, infrastructure.water_depth_m
- `globsed` ← geoscience.model_status
- `labels_harmonized` ← geoscience.basin, geoscience.basin_wildcats, geoscience.offset_success_rate, geoscience.offset_wells_100km
- `model_eval_gbm` ← geoscience.model_status
- `nlog` ← geoscience.offset_success_rate, geoscience.offset_wells_100km
- `nopims` ← geoscience.offset_success_rate, geoscience.offset_wells_100km
- `nsta` ← geoscience.offset_success_rate, geoscience.offset_wells_100km
- `ofac_eu` ← political_risk.sanctioned
- `sodir` ← geoscience.offset_success_rate, geoscience.offset_wells_100km
- `user_supplied` ← economist.pg
- `usgs_provinces` ← geoscience.basin, geoscience.basin_wildcats, geoscience.model_status
- `wdpa` ← environment.protected_areas_nearby, environment.wdpa_overlap_pct
- `wgi` ← political_risk.wgi_rule_of_law
- `yf_curve` ← economist.price_m1

_Screening tool — ranks resemblance and economics at area level; not seismic; never "oil is here."_