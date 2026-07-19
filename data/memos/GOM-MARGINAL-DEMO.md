# Feasibility Memo — GOM-MARGINAL-DEMO

**Verdict: CONDITIONAL** · EMV **2.8 $MM** · P(EMV>0) **51%** · Pg **0.18** (user-supplied (§9.8 — the falsification gate failed; no model Pg ships))

_Generated 2026-07-19T07:07:58.702991+00:00 · frozen local snapshot — no live internet at memo time (§10.3) · citation coverage 100% · determinism hash `d9363febd704c449…`_

## Geoscience

The model status indicates a falsification gate failure, resulting in no model-generated data. The Pg data is instead user-supplied. The basin in question is the Gulf Cenozoic OCS, with a historical success rate of 0.684. A data gap exists regarding volume maturity, as it awaits gated GOGET XLSX data. Nearby wells have shown a success rate of 0.68 within a 100km radius.

- **model_status**: NO MODEL — §9.8 falsification gate failed; no Pg from a model _[model_eval_gbm, usgs_provinces, globsed]_
- **offset_wells_100km**: 444 wells _[boem_bsee, labels_harmonized]_
- **offset_success_rate**: 0.68 _[boem_bsee, labels_harmonized]_
- **basin**: Gulf Cenozoic OCS _[labels_harmonized, usgs_provinces]_
- **basin_wildcats**: 11874 wells _[labels_harmonized, usgs_provinces]_

## Fiscal

The United States' Gulf of Mexico federal OCS regime operates under a tax-royalty system, with a royalty rate of 12.5% for new leases. The corporate income tax rate is 21%. A special petroleum profits tax is not identified in the sources consulted, and the federal take structure consists of bonus bids, rentals, royalty, and corporate income tax. Note that royalty rates vary by lease vintage, with existing deepwater leases potentially bearing different rates.

- **regime_type**: tax_royalty _[curated_fiscal]_
- **cit_rate**: 0.21 fraction _[curated_fiscal]_
- **royalty_rate**: 0.125 fraction _[curated_fiscal]_

## Political Risk

The governance structure of the country, as indicated by the World Governance Indicators (WGI) estimates, suggests a stable environment with positive estimates for control of corruption, government effectiveness, and rule of law. However, the estimates also indicate a negative score for political violence. A data gap exists regarding the Fragile States Index (FSI) total, as the FSI table is absent from the snapshot. The country is not currently sanctioned, according to available information.

- **wgi_rule_of_law**: 0.962 estimate (−2.5…2.5) _[wgi]_
- **sanctioned**: False _[ofac_eu]_

## Infrastructure & Development Concept

The proposed concept is an fpso_standalone with a water depth of 1782.5 meters and a host distance of 110 kilometers. Cost benchmarks for this concept are available, with capital expenditure per barrel of oil equivalent ranging from a low to a high value, and operating expenditure per barrel ranging from a low to a high value. Well costs are also estimated to range from a low to a high value. A data gap exists for specific investment amounts, as only relative cost ranges are provided.

- **water_depth_m**: 1782.5 m _[etopo2022, curated_costs, erda_engine.concept]_
- **host_distance_km**: 110.0 km _[etopo2022, curated_costs, erda_engine.concept]_
- **dev_concept**: fpso_standalone _[etopo2022, curated_costs, erda_engine.concept]_

## Environment

Based on the available data, there is no overlap between the proposed project area and protected areas within a 25-kilometer radius, as indicated by a 0.0% overlap percentage. The World Database on Protected Areas (WDPA) was consulted as the source for this information. No specific protected areas are listed as being within the area of interest. A data gap is not noted in this assessment, as the necessary information is present.

- **wdpa_overlap_pct**: 0.0 % _[wdpa]_
- **protected_areas_nearby**: 0 areas _[wdpa]_

## Financeability

All institutions checked have restrictions in place for upstream financing. The institutions, including banks and insurers, have publicly available policies outlining their approach to the oil and gas sector. A data gap exists regarding the specific impact of these restrictions on financing options. Financing may be shifting towards alternative arrangements, such as partnerships with national oil companies, trading-house prepay, or private equity, due to European bank and insurer restrictions.

- **institutions_checked**: 10 institutions _[curated_exclusions]_
- **restricting_upstream**: 10 institutions _[curated_exclusions]_

## Economics

The project's economic viability is supported by a positive Expected Monetary Value (EMV) and a relatively low breakeven price. The Government take is approximately 45%. A data gap exists regarding the Probability of Geology (Pg), which is marked as user-supplied due to a failed falsification gate. The project's Net Present Value (NPV) in the success case is substantial, with a payback period of 4 years. The economic assumptions are based on a discount rate and a price deck with an indicative price of around $82.49 per barrel as of 2026-07-18.

- **pg**: 0.18 probability _[user_supplied]_
- **price_m1**: 82.49 $/bbl _[yf_curve]_
- **npv_success**: 653.28 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **emv**: 2.79 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **breakeven**: 44.28 $/bbl _[erda_engine, curated_fiscal, curated_costs]_
- **government_take**: 0.4497 fraction _[erda_engine, curated_fiscal, curated_costs]_
- **p_emv_positive**: 0.5109 probability _[erda_engine, curated_fiscal, curated_costs]_
- **mc_seed**: 7 _[erda_engine, curated_fiscal, curated_costs]_

## Red Team — what would make this wrong

This tool JSON is flawed because it relies on user-supplied Pg (prospective gas) values due to a failed falsification gate, which may not be accurate. The proxy labels used for wells are also based on a limited dataset, with only 444 labeled wells out of an unknown total. Additionally, the cost midpoints and price volatility assumptions are simplified and may not reflect real-world variations. The data gaps in fiscal regime details, such as bonus bids and royalty suspension volumes, could also lead to incorrect calculations. Furthermore, the use of a single, indicative price curve (M1 settle 2026-07-18) may not account for potential price fluctuations, and the discount rate assumption of 0.1 may not be suitable for all scenarios.

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
- `ofac_eu` ← political_risk.sanctioned
- `user_supplied` ← economist.pg
- `usgs_provinces` ← geoscience.basin, geoscience.basin_wildcats, geoscience.model_status
- `wdpa` ← environment.protected_areas_nearby, environment.wdpa_overlap_pct
- `wgi` ← political_risk.wgi_rule_of_law
- `yf_curve` ← economist.price_m1

_Screening tool — ranks resemblance and economics at area level; not seismic; never "oil is here."_