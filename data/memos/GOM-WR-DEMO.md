# Feasibility Memo — GOM-WR-DEMO

**Verdict: GO** · EMV **461.7 $MM** · P(EMV>0) **88%** · Pg **0.22** (user-supplied (§9.8 — the falsification gate failed; no model Pg ships))

_Generated 2026-07-18T19:25:20.035360+00:00 · frozen local snapshot — no live internet at memo time (§10.3) · citation coverage 100% · determinism hash `bf1e496245916f4b…`_

## Geoscience

The geoscience evaluation is hindered by a failed model status, with no predictive model output available due to a falsification gate failure. The basin in question is the Gulf Cenozoic OCS, with a historical success rate and significant exploration history. A data gap exists regarding volumetric maturity, as only count-based maturity is currently available. The nearest wells all have a 'NO_FIELD_LEASE' outcome, indicating a lack of nearby discoveries. Further evaluation is needed to fully assess the prospect.

- **model_status**: NO MODEL — §9.8 falsification gate failed; no Pg from a model _[model_eval_gbm, usgs_provinces, globsed]_
- **offset_wells_100km**: 210 wells _[boem_bsee, labels_harmonized]_
- **offset_success_rate**: 0.59 _[boem_bsee, labels_harmonized]_
- **basin**: Gulf Cenozoic OCS _[labels_harmonized, usgs_provinces]_
- **basin_wildcats**: 11874 wells _[labels_harmonized, usgs_provinces]_

## Fiscal

The fiscal regime in the United States — Gulf of Mexico / Gulf of America federal OCS is a tax-royalty system. The royalty rate for new leases is 12.5%, as set by the One Big Beautiful Bill Act Lease Sales. The federal corporate income tax rate is 21%. A data gap exists regarding special petroleum taxes, as no federal special petroleum profits tax has been identified. Additionally, cost-recovery rules for petroleum, such as depreciation, have not been verified from accessed sources.

- **regime_type**: tax_royalty _[curated_fiscal]_
- **cit_rate**: 0.21 fraction _[curated_fiscal]_
- **royalty_rate**: 0.125 fraction _[curated_fiscal]_

## Political Risk

The governance and sanctions landscape of the potential investment location is unclear due to a lack of available data. A data gap exists in the World Governance Indicators (WGI) table, which would typically provide insight into the country's governance structure. Additionally, information on sanctions programs is also unavailable due to a missing snapshot table. As a result, the committee cannot fully assess the political risk associated with this investment. Further research is needed to fill these data gaps.

- **governance_gap**: snapshot table missing: wgi_governance _[snapshot]_
- **sanctions_gap**: snapshot table missing: sanctions_programs _[snapshot]_

## Infrastructure & Development Concept

The concept under consideration is an fpso_standalone, with a water depth of 2097.6 meters and a host distance of 95 kilometers. Cost benchmarks for this concept are available, with capital expenditure per barrel of oil equivalent ranging from a low to a high value, and operating expenditure per barrel ranging from a low to a high value. Well costs are also estimated to fall within a specified range, while the project schedule is expected to span several years, derived from cited dates of similar projects. A data gap is not explicitly noted in the provided information.

- **water_depth_m**: 2097.6 m _[etopo2022, curated_costs, erda_engine.concept]_
- **host_distance_km**: 95.0 km _[etopo2022, curated_costs, erda_engine.concept]_
- **dev_concept**: fpso_standalone _[etopo2022, curated_costs, erda_engine.concept]_

## Environment

The environmental screening process is hindered by a data gap, as the 'wdpa_areas.parquet' file is missing from the snapshot. This omission means that we lack access to protected area data, which is a crucial component in assessing potential environmental impacts. As a result, our evaluation is incomplete, and we cannot fully consider the potential risks and consequences of investment. The absence of this data limits our ability to conduct a thorough environmental assessment.

- **data_gap**: wdpa_areas.parquet missing from snapshot _[snapshot]_

## Financeability

All institutions checked have restrictions in place for upstream financing. The institutions, including banks and insurers, have publicly available policies outlining their approach to the oil and gas sector. A data gap exists regarding the specific impact of these restrictions on financing options. Financing may be shifting towards alternative arrangements, such as partnerships with national oil companies, trading-house prepay, or private equity, due to European bank and insurer restrictions.

- **institutions_checked**: 10 institutions _[curated_exclusions]_
- **restricting_upstream**: 10 institutions _[curated_exclusions]_

## Economics

The project's economics indicate a positive Expected Monetary Value (EMV) with a mean of $607.37 million and a probability of being positive at 87.97%. The project is expected to break even at a price of $38.2 per barrel and has a payback period of 4 years. The Government take is approximately 41.35%. A data gap is noted for the Pg value, which is user-supplied due to the falsification gate failing and no model Pg being available.

- **pg**: 0.22 probability _[user_supplied]_
- **price_m1**: 82.49 $/bbl _[yf_curve]_
- **npv_success**: 2524.26 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **emv**: 461.74 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **breakeven**: 38.2 $/bbl _[erda_engine, curated_fiscal, curated_costs]_
- **government_take**: 0.4135 fraction _[erda_engine, curated_fiscal, curated_costs]_
- **p_emv_positive**: 0.8797 probability _[erda_engine, curated_fiscal, curated_costs]_
- **mc_seed**: 7 _[erda_engine, curated_fiscal, curated_costs]_

## Red Team — what would make this wrong

This assessment is flawed because it relies on a user-supplied Pg value of 0.22, which lacks a robust provenance due to the failure of the §9.8 falsification gate. Additionally, the cost benchmarks for the fpso_standalone concept are based on limited examples (Liza Ph1 and Ph2) and may not be representative of the entire industry. The opex range is also narrow, citing only Petrobras pre-salt lifting costs, which may not be applicable to all operators. Furthermore, the fiscal model simplifies depreciation and does not account for loss carryforward, which could impact the accuracy of the government take and breakeven price calculations. The price deck is also based on a single indicative curve (M1 settle 2026-07-18) and may not capture potential price volatility. Lastly, data gaps in governance and sanctions information introduce uncertainty into the political risk assessment.

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
- `snapshot` ← environment.data_gap, political_risk.governance_gap, political_risk.sanctions_gap
- `user_supplied` ← economist.pg
- `usgs_provinces` ← geoscience.basin, geoscience.basin_wildcats, geoscience.model_status
- `yf_curve` ← economist.price_m1

_Screening tool — ranks resemblance and economics at area level; not seismic; never "oil is here."_