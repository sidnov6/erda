# Feasibility Memo — NAM-ORANGE-DEMO

**Verdict: GO** · EMV **556.8 $MM** · P(EMV>0) **86%** · Pg **0.15** (user-supplied (§9.8 — the falsification gate failed; no model Pg ships))

_Generated 2026-07-19T05:19:13.936489+00:00 · frozen local snapshot — no live internet at memo time (§10.3) · citation coverage 100% · determinism hash `2cea7d2f6d770297…`_

## Geoscience

The geoscience evaluation is hindered by a lack of model output due to a failed falsification gate. Available data indicates that the nearest wells are located at significant distances, with the closest wells resulting in dry holes. The basin's success rate is reported, but key volume data is currently unavailable due to a data gap. The basin has seen exploration activity since 1980, with a notable number of wildcats and discoveries. Further evaluation is limited by the absence of certain critical information.

- **model_status**: NO MODEL — §9.8 falsification gate failed; no Pg from a model _[model_eval_gbm, usgs_provinces, globsed]_
- **offset_wells_100km**: 0 wells _[sodir, nsta, nlog, boem_bsee, nopims, labels_harmonized]_
- **offset_success_rate**: no labeled offsets _[sodir, nsta, nlog, boem_bsee, nopims, labels_harmonized]_
- **basin**: Ocean _[labels_harmonized, usgs_provinces]_
- **basin_wildcats**: 38 wells _[labels_harmonized, usgs_provinces]_

## Fiscal

The fiscal regime in Namibia is characterized by a tax and royalty system, with a royalty rate of 5% of gross revenue. The corporate income tax rate is 35%, and an additional profits tax is levied on after-tax net cash flow from petroleum operations, with a first-tier rate of 25%. A data gap exists regarding the rates for the second and third tiers of the additional profits tax, as these are biddable per Petroleum Agreement. The regime also features ringfencing, where losses cannot be offset against income from another licence area.

- **regime_type**: tax_royalty _[curated_fiscal]_
- **cit_rate**: 0.35 fraction _[curated_fiscal]_
- **royalty_rate**: 0.05 fraction _[curated_fiscal]_

## Political Risk

The governance landscape of NAM is characterized by World Governance Indicators (WGI) estimates, which provide insight into various aspects of governance. The WGI estimates include Control of Corruption, Government Effectiveness, Political Stability and Absence of Violence, Regulatory Quality, Rule of Law, and Voice and Accountability. A data gap exists regarding the Fragile States Index (FSI) total, as the FSI table is absent from the snapshot. Meanwhile, NAM is not currently sanctioned, according to available information.

- **wgi_rule_of_law**: 0.328 estimate (−2.5…2.5) _[wgi]_
- **sanctioned**: False _[ofac_eu]_

## Infrastructure & Development Concept

The proposed concept is an fpso_standalone with a water depth of 3317.4 meters and a host distance of 250 kilometers. Cost benchmarks for this concept are available, with capital expenditure per barrel of oil equivalent ranging from $8 to $18 and operating expenditure per barrel ranging from $6.28 to $6.65. Well costs are estimated to be between $60 million and $240 million, and the project schedule is expected to be between 2.5 and 3.2 years. The provided cost notes and source information support these estimates, citing industry examples and reports from reputable sources.

- **water_depth_m**: 3317.4 m _[etopo2022, curated_costs, erda_engine.concept]_
- **host_distance_km**: 250.0 km _[etopo2022, curated_costs, erda_engine.concept]_
- **dev_concept**: fpso_standalone _[etopo2022, curated_costs, erda_engine.concept]_

## Environment

Based on the available data, there is no overlap between the area of interest and protected areas within a 25-kilometer radius. The data indicates a 0.0% overlap, suggesting no intersection with designated conservation zones. The source of this information is the World Database on Protected Areas (WDPA). A data gap is noted as no specific protected areas are listed.

- **wdpa_overlap_pct**: 0.0 % _[wdpa]_
- **protected_areas_nearby**: 0 areas _[wdpa]_

## Financeability

All institutions checked have restrictions in place for upstream financing. The institutions, including banks and insurers, have publicly available policies outlining their approach to the oil and gas sector. A data gap exists regarding the specific impact of these restrictions on financing costs and availability. Financing options may be shifting towards alternative sources, such as national oil company partnerships, trading-house prepay, or private equity, due to European bank and insurer restrictions.

- **institutions_checked**: 10 institutions _[curated_exclusions]_
- **restricting_upstream**: 10 institutions _[curated_exclusions]_

## Economics

The project's economic viability is supported by a positive Expected Monetary Value (EMV) and a relatively low breakeven price. The EMV is estimated to be $556.79 million, with a probability of being positive at 85.67%. A data gap is noted for the Probability of Geologic Success (Pg), which is user-supplied due to a failed falsification gate. The project's economics are also influenced by a government take of 47.55% and a discount rate of 10%.

- **pg**: 0.15 probability _[user_supplied]_
- **price_m1**: 82.49 $/bbl _[yf_curve]_
- **npv_success**: 4561.92 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **emv**: 556.79 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **breakeven**: 37.69 $/bbl _[erda_engine, curated_fiscal, curated_costs]_
- **government_take**: 0.4755 fraction _[erda_engine, curated_fiscal, curated_costs]_
- **p_emv_positive**: 0.8567 probability _[erda_engine, curated_fiscal, curated_costs]_
- **mc_seed**: 7 _[erda_engine, curated_fiscal, curated_costs]_

## Red Team — what would make this wrong

This tool JSON is flawed because it relies on user-supplied Pg (prospective gas) values due to a failed falsification gate, which may not accurately represent the actual gas prospects. Additionally, the proxy labels used for wells are based on limited data, with only a few wells considered and a high distance from the area of interest (over 8,900 km). The cost midpoints are also questionable, as they are derived from a limited number of projects (e.g., Liza Ph1 and Ph2) and may not be representative of the costs for this specific project. Furthermore, the price volatility assumption of 0.25 (25%) may be overly simplistic, and the use of a flat-real price curve may not account for potential fluctuations in the market. Lastly, there are significant data gaps, including the lack of official ministry or revenue authority pages, and the use of outdated documents (e.g., the 2017 NAMCOR fiscal regime document) to verify rates.

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