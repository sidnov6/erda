# Curated fiscal regime data

Hand-maintained CURATED files per ERDA rule §7: every field carries a
`source_urls` entry that was actually accessed during compilation; numbers come
from those documents, never from memory. Values that could not be verified from
an accessible source are omitted and listed under "Unverified" below.

**Compiled:** 2026-07-19 (all web accesses on this date)
**Files:** `NOR.yaml`, `USA_GOM.yaml`, `NAM.yaml` — one record each, schema:
`iso3, country, regime_type, royalty_rate, cit_rate, special_petroleum_tax,
psc_terms, ringfencing, depreciation_note, engine_mapping, source_urls,
retrieved_at, caveats`.

All three regimes are `tax_royalty` (concession/licence); `psc_terms: null`
throughout. `engine_mapping` gives suggested inputs for the screening engine's
royalty+CIT fiscal model, with the approximation documented where the real
regime has extra layers (Norway special tax, Namibia APT).

## Sources used

### Norway (`NOR.yaml`)
- **norskpetroleum.no petroleum-tax page** (official joint site of the
  Ministry of Energy and the Norwegian Offshore Directorate, ex-NPD):
  <https://www.norskpetroleum.no/en/economy/petroleum-tax/>
  — CIT 22%; special tax technical rate 71.8% (combined marginal 78%, company
  tax deducted from special-tax base); immediate expensing in special-tax base
  since income year 2022 (cash-flow model) with reimbursement of special-tax
  value of losses; 6-year straight-line depreciation in the ordinary base;
  royalties no longer part of the system; NCS-wide loss consolidation.

### US Gulf of Mexico federal OCS (`USA_GOM.yaml`)
- **Final Notices of Sale, OBBBA Lease Sales BBG1/BBG2/BBG3** (Federal
  Register full texts via GovInfo mirror; federalregister.gov HTML was
  bot-blocked, its API metadata endpoint was used to confirm document
  identity):
  - <https://www.govinfo.gov/content/pkg/FR-2025-11-10/html/2025-19828.htm>
  - <https://www.govinfo.gov/content/pkg/FR-2026-02-05/html/2026-02289.htm>
  - <https://www.govinfo.gov/content/pkg/FR-2026-07-08/html/2026-13779.htm>
  - <https://www.federalregister.gov/api/v1/documents/2026-13779.json>
  — royalty "12 1/2 percent for blocks in all water depths" (OBBBA
  §50102(b)(1)(C) minimum; statutory band 12.5%–16 2/3%); rentals $7/$11 per
  acre below/above 200 m.
- **BOEM press release, Lease Sale 256 (Oct 2020)**:
  <https://www.boem.gov/newsroom/press-releases/boem-announces-region-wide-oil-and-gas-lease-sale-gulf-mexico>
  — historical structure: 12.5% for <200 m water depth, 18.75% for all other
  leases.
- **BOEM press release, proposed Lease Sale 262 (Jun 2025)**:
  <https://www.boem.gov/newsroom/press-releases/boem-proposes-oil-and-gas-lease-sale-gulf-america>
  — proposed 16 2/3% at all depths, described as "the lowest rate for
  deepwater since 2007" (implies a 16 2/3% deepwater vintage circa 2007).
- **IRS Publication 542**: <https://www.irs.gov/publications/p542>
  — federal CIT 21% ("multiplying taxable income by 21% (0.21)").

### Namibia (`NAM.yaml`)
- **NAMCOR "Namibian Fiscal Regime" (Aug 2017, PDF)**:
  <https://www.namcor.com.na/wp-content/uploads/2020/02/namibia-fiscal-regime-august-2017.pdf>
  — PIT 35% per licence area; royalty 5% of gross revenue (deductible for
  PIT); three-tier APT on after-tax real ROR thresholds 15%/20%/25%, tier-1
  rate 25% by legislated formula, tiers 2–3 biddable; exploration/opex
  expensed, development 3-yr straight line; per-licence-area ring fence with
  the 1998 exploration-expenditure exception; WHT details.
- **Chambers Oil, Gas and the Transition to Renewables 2025 — Namibia**
  (published 2025-08-07):
  <https://practiceguides.chambers.com/practice-guides/oil-gas-and-the-transition-to-renewables-2025/namibia/trends-and-developments>
  — currency cross-check: same 5% royalty, 35% PIT, three-tier APT,
  per-area ring-fencing; NAMCOR 10% participating interest in practice.

## Unverified / omitted (never approximated)

- **USA:** the claim that the 18.75% deepwater rate began with Central GoM
  Lease Sale 206 (2008) appeared only in search-result summaries, not in any
  accessed primary document — noted as unverified in `USA_GOM.yaml` caveats.
- **USA:** federal cost-recovery rules for petroleum (IDC expensing,
  depletion, MACRS lives) — `depreciation_note` deliberately `null`; not
  verified from an accessed source.
- **USA:** whether Lease Sale 262 (16 2/3% proposal) was ever finalized on
  those terms was not determined; the OBBBA sales are treated as the current
  terms for new leases.
- **Norway:** environmental levies (CO2 tax, NOx tax) and area fees excluded;
  Petroleum Taxation Act statutory text and the expired temporary-uplift
  provisions not separately fetched.
- **Namibia:** official ministry / revenue-authority pages inaccessible on
  compilation date (PwC Namibia petroleum tax card PDF → HTTP 403;
  mme.gov.na → connection refused). Verification therefore rests on the
  state oil company (NAMCOR) document plus a 2025 legal practice guide, not
  on MME/NAMRA pages. APT tiers 2–3 have no fixed statutory rate. Terms of
  individual signed Petroleum Agreements not compiled.

## Maintenance

Re-verify before relying on these for anything beyond screening: US royalty
terms are sale-by-sale (statutorily bounded 12.5%–16 2/3% under OBBBA for new
sales); Norway rates are set annually in the tax resolutions; Namibia terms
may be renegotiated per Petroleum Agreement.
