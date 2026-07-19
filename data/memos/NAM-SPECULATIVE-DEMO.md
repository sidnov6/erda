# Feasibility Memo — NAM-SPECULATIVE-DEMO

**Verdict: NO_GO** · EMV **-97.2 $MM** · P(EMV>0) **13%** · Pg **0.05** (user-supplied (§9.8 — the falsification gate failed; no model Pg ships))

_Generated 2026-07-19T09:50:41.873590+00:00 · frozen local snapshot — no live internet at memo time (§10.3) · citation coverage 100% · determinism hash `8d6a30aba50af022…`_

## Geoscience

The screening model failed the §9.8 falsification gate, resulting in no predictive generation (Pg) and a negative result recorded in the referenced package. Within the 100‑km offset radius there are zero wells, zero labeled outcomes and zero discoveries, and the offset success rate is unavailable. The nearest historic wells lie between 8 782.8 km and 8 786.7 km away, with the three closest recorded as dry holes and the remaining wells lacking outcome data. Basin‑level activity comprises 38 wildcat permits and 15 discoveries from 1980 to 2025, giving a historical success rate of 0.395. Maturity is assessed on a count basis, and volumetric estimates are pending the gated GOGET spreadsheet; consequently, quantitative offset analysis cannot be provided due to these data gaps.

- **model_status**: NO MODEL — §9.8 falsification gate failed; no Pg from a model _[model_eval_gbm, usgs_provinces, globsed]_
- **offset_wells_100km**: 0 wells _[sodir, nsta, nlog, boem_bsee, nopims, labels_harmonized]_
- **offset_success_rate**: no labeled offsets _[sodir, nsta, nlog, boem_bsee, nopims, labels_harmonized]_
- **basin**: Ocean _[labels_harmonized, usgs_provinces]_
- **basin_wildcats**: 38 wells _[labels_harmonized, usgs_provinces]_

## Fiscal

Namibia applies a tax‑royalty fiscal regime, imposing a 5 % royalty on the market value of gross petroleum revenue and a 35 % Petroleum Income Tax (PIT) on taxable income, both deductible in the PIT computation. In addition, an Additional Profits Tax (APT) is levied on after‑tax net cash flow on a three‑tier basis, with a legislated first‑tier rate of 25 % that becomes payable once the licence area achieves an inflation‑adjusted real rate of return above 15 %, while higher tiers trigger at 20 % and 25 % returns and are negotiated per agreement. PIT and APT are ring‑fenced per licence area; losses cannot be offset against other areas and may be carried forward indefinitely, although exploration expenditure incurred after the 1998 amendment may be deducted against PIT in a producing area. PSC terms are not provided in the source data, and statutory rates for APT tiers two and three are absent, being subject to bid‑off in individual petroleum agreements.

- **regime_type**: tax_royalty _[curated_fiscal]_
- **cit_rate**: 0.35 fraction _[curated_fiscal]_
- **royalty_rate**: 0.05 fraction _[curated_fiscal]_

## Political Risk

Namibia’s 2024 Worldwide Governance Indicators show low performance across most dimensions, with scores of 0.099 for Government Effectiveness, 0.127 for Control of Corruption, 0.135 for Regulatory Quality, 0.328 for Rule of Law, and 0.337 for Voice and Accountability; Political Stability and Violence/terrorism registers a modest 0.547. The country is not listed on any U.S. or EU sanctions programs, and no entries appear on OFAC or EU sanction lists. The Freedom‑in‑the‑World (FSI) rating is unavailable in the current snapshot, indicating a data gap for that metric. Overall, governance metrics suggest a challenging operating environment, while the absence of sanctions reduces immediate compliance risk.

- **wgi_rule_of_law**: 0.328 estimate (−2.5…2.5) _[wgi]_
- **sanctioned**: False _[ofac_eu]_

## Infrastructure & Development Concept

The development is planned as a standalone FPSO operating in ultra‑deep water of approximately 2,707 m, located roughly 300 km from shore. Capital expenditures are benchmarked at $8–$18 per barrel‑of‑oil‑equivalent, with well‑drilling costs ranging from $60 M to $240 M and a construction schedule of 2.5–3.2 years from final investment decision to first oil. Operating expenses are anchored to Petrobras pre‑salt lifting costs, estimated at $6.28–$6.65 per barrel for 2024. All cost and schedule parameters are derived from publicly disclosed deepwater projects and industry cost studies.

- **water_depth_m**: 2707.0 m _[etopo2022, curated_costs, erda_engine.concept]_
- **host_distance_km**: 300.0 km _[etopo2022, curated_costs, erda_engine.concept]_
- **dev_concept**: fpso_standalone _[etopo2022, curated_costs, erda_engine.concept]_

## Environment

Within a 25 km radius of the target location, the World Database on Protected Areas (WDPA) reports zero percent overlap with any protected area. The WDPA dataset does not list any specific protected areas within this buffer, indicating an absence of formally designated conservation zones in the immediate vicinity. Consequently, there are no identified protected-area constraints on land use or development for the project. No additional data gaps are noted beyond the lack of listed areas.

- **wdpa_overlap_pct**: 0.0 % _[wdpa]_
- **protected_areas_nearby**: 0 areas _[wdpa]_

## Financeability

Our screening of ten European banks and insurers identified that all ten institutions have explicit policies restricting upstream oil‑and‑gas financing. The restricting entities include major banks such as BNP Paribas, Société Générale, Crédit Agricole, ING, HSBC, Barclays and NatWest Group, as well as insurers Allianz, AXA and Munich Re, each with publicly available policy documents. These European financing constraints effectively channel capital toward national‑oil‑company partnerships, trading‑house pre‑payment structures, or private‑equity arrangements. (Source: curated_exclusions).

- **institutions_checked**: 10 institutions _[curated_exclusions]_
- **restricting_upstream**: 10 institutions _[curated_exclusions]_

## Economics

The project’s net‑present‑value under a successful outcome is $1,096.5 million, yet the expected monetary value (EMV) is –$97.2 million, with only a 12.9 % chance of a positive EMV across 10,000 Monte‑Carlo simulations (mean EMV –$78.3 million, p10 –$153.5 million, p90 $20.6 million). The breakeven oil price is $42.1 per barrel, comfortably below the current indicative price of $82.49 per barrel (M1 curve as of 2026‑07‑18). Government take is 50.15 % and the fiscal model applies royalty plus corporate income tax with straight‑line depreciation and no loss carry‑forward, using a 10 % discount rate. A key data gap is the production‑growth factor (Pg), which is user‑supplied (§9.8) and lacks a calibrated model, limiting confidence in the forward production profile.

- **pg**: 0.05 probability _[user_supplied]_
- **price_m1**: 82.49 $/bbl _[yf_curve]_
- **npv_success**: 1096.51 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **emv**: -97.17 MUSD _[erda_engine, curated_fiscal, curated_costs]_
- **breakeven**: 42.1 $/bbl _[erda_engine, curated_fiscal, curated_costs]_
- **government_take**: 0.5015 fraction _[erda_engine, curated_fiscal, curated_costs]_
- **p_emv_positive**: 0.1291 probability _[erda_engine, curated_fiscal, curated_costs]_
- **mc_seed**: 7 _[erda_engine, curated_fiscal, curated_costs]_

## Red Team — what would make this wrong

- The “Pg = 5 %” is not derived from any geological model – the model gate failed and the value is simply “user‑supplied (§9.8)”, so the whole economic output rests on a guess rather than a calibrated reserve estimate.  
- The offset‑well proxy is empty (0 wells, 0 labeled discoveries, no success‑rate) and the nearest wells are all dry holes thousands of kilometres away, making any “success_rate = 0.395” for the basin meaningless for this prospect.  
- Cost benchmarks are taken from a handful of Exxon‑Liza FPSO case studies and a single Rystad‑Offshore‑Magazine range, then presented as low/high mid‑points (CAPEX $8‑$18 / boe, OPEX $6.28‑$6.65 / bbl) without any confidence interval or sensitivity to water‑depth, location or market‑wide cost volatility.  
- The price assumption uses a flat‑real curve (M1 $82.49 / bbl) with a single σ = 0.25, yet the price deck only lists three static scenarios and labels the curve “indicative”, so volatility and upside/downside risk are severely under‑represented.  
- Critical fiscal pieces are missing or oversimplified: the APT tiers 2‑3 have no statutory rates (only the 25 % first tier is recorded), the 10 % NAMCOR participating interest and withholding‑tax regimes are omitted, and the “no loss carry‑forward” note ignores the documented ring‑fencing exceptions.  
- Source gaps (403 on PwC tax card, no FSI score, no official ministry pages) mean the model is built on secondary or archived documents that may be outdated for the 2023‑2025 Orange Basin discoveries.

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