# Feasibility Memo — GOM-WR-DEMO

**Verdict: GO** · EMV **461.7 $MM** · P(EMV>0) **88%** · Pg **0.22** (user-supplied (§9.8 — the falsification gate failed; no model Pg ships))

_Generated 2026-07-19T05:16:30.326159+00:00 · frozen local snapshot — no live internet at memo time (§10.3) · citation coverage 100% · determinism hash `f58c9f101ced228b…`_

## Geoscience

The model status indicates a falsification gate failure, resulting in no model-generated data. The Pg data is instead user-supplied. A data gap exists regarding volumetric maturity, as it awaits gated GOGET XLSX. The basin in question has a high success rate, with a significant number of discoveries made. There is a notable presence of nearby wells, all of which have a 'NO_FIELD_LEASE' outcome.

- **model_status**: NO MODEL — §9.8 falsification gate failed; no Pg from a model _[model_eval_gbm, usgs_provinces, globsed]_
- **offset_wells_100km**: 210 wells _[boem_bsee, labels_harmonized]_
- **offset_success_rate**: 0.59 _[boem_bsee, labels_harmonized]_
- **basin**: Gulf Cenozoic OCS _[labels_harmonized, usgs_provinces]_
- **basin_wildcats**: 11874 wells _[labels_harmonized, usgs_provinces]_

## Fiscal

The fiscal regime in the United States — Gulf of Mexico / Gulf of America federal OCS is a tax-royalty system. The royalty rate for new leases is 12.5%, as per the One Big Beautiful Bill Act. The federal corporate income tax rate is 21%. A special petroleum profits tax is not identified in the sources consulted, with the federal take structure consisting of bonus bids, rentals, royalty, and corporate income tax. Royalty rates vary by lease vintage, with existing deepwater leases potentially bearing different rates.

- **regime_type**: tax_royalty _[curated_fiscal]_
- **cit_rate**: 0.21 fraction _[curated_fiscal]_
- **royalty_rate**: 0.125 fraction _[curated_fiscal]_

## Political Risk

The governance structure of the investment location is characterized by estimates from the World Governance Indicators (WGI), which provide insights into various aspects of governance. The WGI estimates for 2024 indicate a range of scores, including Control of Corruption, Government Effectiveness, and Regulatory Quality. A data gap is noted for the Fragile States Index (FSI) total, as the FSI table is absent from the snapshot. The country is not currently sanctioned, according to available information.

- **wgi_rule_of_law**: 0.962 estimate (−2.5…2.5) _[wgi]_
- **sanctioned**: False _[ofac_eu]_

## Infrastructure & Development Concept

The proposed concept is an fpso_standalone with a water depth of 2097.6 meters and a host distance of 95 kilometers. Cost benchmarks for this concept are available, with capital expenditure per barrel of oil equivalent ranging from $8 to $18 and operating expenditure per barrel ranging from $6.28 to $6.65. The project schedule is estimated to be between 2.5 and 3.2 years, derived from cited project timelines. Well costs are estimated to range from $60 to $240 million.

- **water_depth_m**: 2097.6 m _[etopo2022, curated_costs, erda_engine.concept]_
- **host_distance_km**: 95.0 km _[etopo2022, curated_costs, erda_engine.concept]_
- **dev_concept**: fpso_standalone _[etopo2022, curated_costs, erda_engine.concept]_

## Environment

Based on the available data, there is no overlap between the area of interest and protected areas within a 25-kilometer radius. The data indicates that the percentage of overlap is zero. The source of this information is the World Database on Protected Areas (WDPA). A data gap is present as the specific protected areas are not listed.

- **wdpa_overlap_pct**: 0.0 % _[wdpa]_
- **protected_areas_nearby**: 0 areas _[wdpa]_

## Financeability

All institutions checked have restrictions in place for upstream financing. The list of restricting institutions includes multiple banks and insurers, with publicly available policies accessible via provided URLs. A data gap exists regarding the specific details of these restrictions, but it is noted that European bank and insurer restrictions are driving financing towards alternative options. The capital note suggests that these restrictions are pushing financing towards partnerships with national oil companies, trading-house prepay, or private equity.

- **institutions_checked**: 10 institutions _[curated_exclusions]_
- **restricting_upstream**: 10 institutions _[curated_exclusions]_

## Economics

The project's economics indicate a positive Expected Monetary Value (EMV) of $461.74 million, with a probability of 87.97% that the EMV will be positive. The Government take is 41.35%, and the breakeven price is $38.2 per barrel. A data gap exists regarding the geological chance of success (Pg), which is marked as user-supplied due to a failed falsification gate, with no modelled Pg available. The project's Net Present Value (NPV) in the success case is $2,524.26 million.

- **pg**: 0.22 probability _[user_supplied]_
- **price_m1**: 82.49 $/bbl _[yf_curve]_
- **npv_success**: 2524.26 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **emv**: 461.74 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **breakeven**: 38.2 $/bbl _[erda_engine, curated_fiscal, curated_costs]_
- **government_take**: 0.4135 fraction _[erda_engine, curated_fiscal, curated_costs]_
- **p_emv_positive**: 0.8797 probability _[erda_engine, curated_fiscal, curated_costs]_
- **mc_seed**: 7 _[erda_engine, curated_fiscal, curated_costs]_

## Red Team — what would make this wrong

This tool JSON has several potential issues. The Pg (prospective gas) value of 0.22 is user-supplied, as the model failed the falsification gate, which may not be reliable. The proxy labels used for the geoscience model may not accurately represent the actual data. The cost midpoints, such as the capex and opex values, are based on benchmarks and may not reflect the actual costs of the project. The price volatility assumption of 0.25 may not capture the full range of potential price fluctuations. Additionally, there are data gaps, such as the lack of verification of state-level applicability of taxes and the omission of federal levies like inspection fees, which could impact the accuracy of the results. The use of a flat-real price curve and straight-line depreciation may also oversimplify the actual fiscal model.

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