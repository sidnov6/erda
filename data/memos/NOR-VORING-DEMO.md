# Feasibility Memo — NOR-VORING-DEMO

**Verdict: GO** · EMV **508.2 $MM** · P(EMV>0) **93%** · Pg **0.25** (user-supplied (§9.8 — the falsification gate failed; no model Pg ships))

_Generated 2026-07-19T05:17:49.992066+00:00 · frozen local snapshot — no live internet at memo time (§10.3) · citation coverage 100% · determinism hash `1efc44758a84af21…`_

## Geoscience

The geoscience evaluation is hindered by a failed model status, with no model-generated data available due to a falsification gate failure. The available data is user-supplied, with a notable offset success rate. Nearby wells have shown varied outcomes, including gas discoveries and dry wells. A data gap exists regarding volumetric maturity, as it awaits gated XLSX data. The basin's success rate and discovery history are available, but the lack of modeled data limits the depth of analysis.

- **model_status**: NO MODEL — §9.8 falsification gate failed; no Pg from a model _[model_eval_gbm, usgs_provinces, globsed]_
- **offset_wells_100km**: 27 wells _[sodir, labels_harmonized]_
- **offset_success_rate**: 0.481 _[sodir, labels_harmonized]_
- **basin**: Ocean _[labels_harmonized, usgs_provinces]_
- **basin_wildcats**: 38 wells _[labels_harmonized, usgs_provinces]_

## Fiscal

The Norwegian Continental Shelf operates under a tax-royalty regime with no production royalty. The ordinary company tax rate is 22%, with investments depreciated straight-line over six years. A special petroleum tax applies to petroleum extraction income, with a technical rate of 71.8% and a cash-flow tax model allowing for immediate write-off of investments. The combined marginal tax rate is 78%, although the effective distortionary burden on marginal investments may be closer to the 22% ordinary layer due to the special tax's approximately NPV-neutral design. A data gap exists regarding environmental levies and area fees on the Norwegian Continental Shelf.

- **regime_type**: tax_royalty _[curated_fiscal]_
- **cit_rate**: 0.22 fraction _[curated_fiscal]_
- **royalty_rate**: 0.0 fraction _[curated_fiscal]_

## Political Risk

The governance structure of the country, identified by the ISO3 code 'NOR', is characterized by various estimates, including Control of Corruption, Government Effectiveness, and Regulatory Quality. The World Governance Indicators (WGI) estimates are available, but the Fragile States Index (FSI) data is absent. Sanctions screening indicates that the country is not currently sanctioned. The data sources for these assessments include the World Governance Indicators and OFAC/EU sanctions lists. A data gap exists regarding the FSI total due to the absence of the FSI table.

- **wgi_rule_of_law**: 1.949 estimate (−2.5…2.5) _[wgi]_
- **sanctioned**: False _[ofac_eu]_

## Infrastructure & Development Concept

The concept under consideration is an fpso_standalone, with a water depth of 963.8 meters and a host distance of 130 kilometers. Cost benchmarks for this concept are available, with capital expenditure per barrel of oil equivalent ranging from $8 to $18 and operating expenditure per barrel ranging from $6.28 to $6.65. Well costs are estimated to be between $60 million and $240 million, and the project schedule is expected to be between 2.5 and 3.2 years.

- **water_depth_m**: 963.8 m _[etopo2022, curated_costs, erda_engine.concept]_
- **host_distance_km**: 130.0 km _[etopo2022, curated_costs, erda_engine.concept]_
- **dev_concept**: fpso_standalone _[etopo2022, curated_costs, erda_engine.concept]_

## Environment

Based on the available data, there is no overlap between the area of interest and protected areas within a 25-kilometer radius. The data indicates a 0.0% overlap, suggesting no intersection with designated conservation zones. The source of this information is listed as 'wdpa', implying that the data is derived from the World Database on Protected Areas. No specific protected areas are identified within the specified radius.

- **wdpa_overlap_pct**: 0.0 % _[wdpa]_
- **protected_areas_nearby**: 0 areas _[wdpa]_

## Financeability

All institutions checked have restrictions in place for upstream financing. The institutions, including banks and insurers, have publicly available policies outlining their approach to the oil and gas sector. A data gap exists regarding the specific impact of these restrictions on financing options. Financing may be shifting towards alternative arrangements, such as partnerships with national oil companies, trading-house prepay, or private equity, due to European bank and insurer restrictions.

- **institutions_checked**: 10 institutions _[curated_exclusions]_
- **restricting_upstream**: 10 institutions _[curated_exclusions]_

## Economics

The project's economics are characterized by a user-supplied probability of geological success (Pg) of 0.25, with a noted data provenance issue due to a failed falsification gate and lack of model Pg. The expected monetary value (EMV) is $508.23 million, with a net present value (NPV) of $2,302.91 million in the success case. The government take is approximately 26.99%, and the project is expected to break even at a price of $33.66 per barrel. A Monte Carlo analysis with 10,000 draws indicates a 93.07% probability of a positive EMV.

- **pg**: 0.25 probability _[user_supplied]_
- **price_m1**: 82.49 $/bbl _[yf_curve]_
- **npv_success**: 2302.91 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **emv**: 508.23 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **breakeven**: 33.66 $/bbl _[erda_engine, curated_fiscal, curated_costs]_
- **government_take**: 0.2699 fraction _[erda_engine, curated_fiscal, curated_costs]_
- **p_emv_positive**: 0.9307 probability _[erda_engine, curated_fiscal, curated_costs]_
- **mc_seed**: 7 _[erda_engine, curated_fiscal, curated_costs]_

## Red Team — what would make this wrong

This analysis is flawed because it relies on a user-supplied Pg value of 0.25, which may not accurately reflect the project's geoscience potential. The falsification gate failed, indicating that the model did not produce a reliable Pg estimate. Additionally, the cost benchmarks are based on a limited number of projects, such as Liza Ph1 and Ph2, which may not be representative of the project's actual costs. The opex range is also based on a single operator, Petrobras, which may not be indicative of industry-wide costs. The price deck is based on an indicative curve, which may not reflect actual market prices. The fiscal model simplifies loss carryforward, which could impact the accuracy of the government take and NPV calculations.

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
- `ofac_eu` ← political_risk.sanctioned
- `sodir` ← geoscience.offset_success_rate, geoscience.offset_wells_100km
- `user_supplied` ← economist.pg
- `usgs_provinces` ← geoscience.basin, geoscience.basin_wildcats, geoscience.model_status
- `wdpa` ← environment.protected_areas_nearby, environment.wdpa_overlap_pct
- `wgi` ← political_risk.wgi_rule_of_law
- `yf_curve` ← economist.price_m1

_Screening tool — ranks resemblance and economics at area level; not seismic; never "oil is here."_