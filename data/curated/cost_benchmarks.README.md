# cost_benchmarks.csv — development-concept cost benchmarks

Hand-curated cost benchmarks for the four ERDA development concepts produced by the §10.4
deterministic classifier (onshore · shelf_tieback · deepwater_tieback · fpso_standalone).
Feeds the §10.5 economics engine (capex/opex/schedule per concept) and the memo Economist
section. Per the §7 curated rule: hand-maintained is fine, **uncited is not** — every populated
numeric field traces to a `source_url` that was actually accessed on `retrieved_at`; where no
defensible public range was found the field is **left empty** and listed under
"Unverified / omitted" below. Ranges, never points; numbers come from the cited documents,
never from memory.

- Units: `capex_usd_boe_*` US$/boe (development capex); `opex_usd_bbl_*` US$/bbl (operating /
  lifting cost); `well_cost_musd_*` US$ million per well (drilling & completion);
  `schedule_years_*` years from FID/sanction to first oil (onshore: spud to first production).
- Compiled: **2026-07-19** (all `retrieved_at` values; all URLs fetched that day).
- Row count: 4. Numeric fields: 32 total, **22 populated / 10 intentionally empty**.
- Ranges are NOT inflation-adjusted or normalized across vintages — each carries its source
  year in `notes`. Treat as order-of-magnitude engine inputs with ±30% capex Monte Carlo
  (§10.5), not as current market quotes.

## Sources used (all retrieved 2026-07-19)

Agency / study:

1. **EIA / IHS, "Trends in U.S. Oil and Natural Gas Upstream Costs", March 2016** —
   <https://www.eia.gov/analysis/studies/drilling/pdf/upstream.pdf>
   - Onshore well cost: D&C + facilities "range from $4.9 MM to $8.3 MM" (5 US plays, 2014
     well parameters); 2015 play averages: Bakken $5.9M, Eagle Ford $6.5M, Marcellus $6.1M,
     Midland $7.2M, Delaware $5.2M.
   - Onshore opex: "operating expenses range between $2.00 per Boe to $14.50 per Boe,
     including water disposal".
   - Deepwater GoM well cost: D&C "estimated between $60MM to $240MM for wells in water
     depths from 7,500 feet to 15,000 feet"; Miocene $70–165M, Lower Tertiary $150–220M,
     Jurassic ~$230M.
2. **EIA, Today in Energy #41253 (10 Sep 2019)** —
   <https://www.eia.gov/todayinenergy/detail.php?id=41253> — ND Bakken: average drilling time
   "less than two months"; completion time ranged "from about three months to nearly one
   year" (2014–16).
3. **Chatham House / New Petroleum Producers Group, "Exploration Cost Benchmark: Reference
   Manual" (2019)** —
   <https://www.newproducersgroup.online/wp-content/uploads/2020/11/Reference_manual-update_11012019_formatted.pdf>
   — onshore reference exploration well (2,000 m, Europe) US$3,710,000 total; shallow-water
   reference well (50 m WD, 2,000 m TD) US$14,740,742 total.

Analyst / press:

4. **Rystad Energy via Offshore Magazine, "Offshore oil and gas – the comeback kid"
   (11 Dec 2023)** —
   <https://www.offshore-mag.com/deepwater/article/14301241/rystad-energy-offshore-oil-and-gas-the-comeback-kid>
   — offshore "development cost per barrel dropped significantly from the 2013 high of $18
   per boe to an average of $8 per boe between 2013 and 2022"; offshore breakevens "in the
   low $40s"; deepwater payback ~6 yr, shelf ~10 yr.
5. **Rystad Energy press release, "Shale project economics still reign supreme…" (Sep 2024)** —
   <https://www.rystadenergy.com/news/upstream-breakeven-shale-oil-inflation> — breakevens:
   onshore Middle East $27/bbl, offshore shelf $37/bbl, deepwater $43/bbl, NAm shale $45/bbl
   (context only — breakevens, not capex/boe).
6. **Rystad Energy via Offshore Magazine, "Exploration overdrive urgently required"
   (10 Dec 2020)** —
   <https://www.offshore-mag.com/drilling-completion/article/14188804/exploration-overdrive-urgently-required-rystad-energy-report-claims>
   — deepwater-heavy exploration future puts "the average well cost to around $50 million".
7. **Wood Mackenzie via OE Digital, "GoM operators set sights on tiebacks" (Apr 2017)** —
   <https://www.oedigital.com/news/446933-gom-operators-set-sights-on-tiebacks> — GoM tieback
   breakevens "high $20s-$30/bbl (Brent)" vs standalone "high $40/bbl to the low $50/bbl";
   Shell Kaikias "two-year timeline from sanctioning… to first oil in 2019".
8. **Wood Mackenzie via Forbes, "Deepwater's Back In The Money" (21 Jun 2019)** —
   <https://www.forbes.com/sites/woodmackenzie/2019/06/21/deepwaters-back-in-the-money/> —
   deepwater "average capex/boe has fallen by 60% to under U.S.$8/boe"; "average time from
   FID to first production is now less than three years".
9. **Offshore Magazine, "Gulf operators ramping up their subsea tieback plans" (14 May 2025)** —
   <https://www.offshore-mag.com/regional-reports/us-gulf-of-mexico/article/55290156/gulf-operators-ramping-up-their-subsea-tieback-plans>
   — Chevron Ballymore sanctioned 2022, first oil Apr 2025.
10. **Offshore Magazine, "Deep shelf drilling proves difficult and expensive" (1 Jun 2004)** —
    <https://www.offshore-mag.com/drilling-completion/article/16756708/deep-shelf-drilling-proves-difficult-and-expensive>
    — GoM shelf: "the cost of a 17,000-ft well at $12 million"; a 30,000-ft ultradeep well
    "will require close to $50 million". **2004 USD — oldest figure in the file.**

Company:

11. **ExxonMobil PR, Liza Phase 1 FID (16 Jun 2017)** —
    <https://corporate.exxonmobil.com/news/news-releases/2017/0616_exxonmobil-makes-final-investment-decision-to-proceed-with-liza-oil-development-in-guyana>
    — Phase 1 "expected to cost just over $4.4 billion" incl ~$1.2B FPSO lease
    capitalization; 120,000 b/d.
12. **ExxonMobil PR, Guyana first oil (20 Dec 2019)** —
    <https://corporate.exxonmobil.com/news/news-releases/2019/1220_exxonmobil-begins-oil-production-in-guyana>
    — first oil "less than five years after the first discovery… well ahead of the industry
    average for deepwater developments".
13. **ExxonMobil PR, Liza Phase 2 FID (3 May 2019)** —
    <https://corporate.exxonmobil.com/news/news-releases/2019/0503_exxonmobil-to-proceed-with-liza-phase-2-development-offshore-guyana>
    — Phase 2 "expected to cost $6 billion" incl ~$1.6B FPSO lease capitalization; up to
    220,000 b/d; production expected mid-2022.
14. **Zacks via Yahoo Finance, Petrobras Q1 2024 earnings** —
    <https://finance.yahoo.com/news/petrobras-pbr-q1-earnings-lag-120900783.html> — pre-salt
    lifting cost "$6.28 per barrel" (Q1 2024).
15. **Zacks via Yahoo Finance, Petrobras Q4 2024 earnings** —
    <https://finance.yahoo.com/news/petrobras-q4-earnings-beat-despite-122000850.html> —
    pre-salt lifting cost "$6.65 per barrel" (Q4 2024).
16. **NSTA, 2024 Benchmarking Dashboards (7 Aug 2025)** —
    <https://www.nstauthority.co.uk/news-publications/2024-benchmarking-dashboards-production-efficiency-and-unit-operating-cost/>
    — UKCS unit operating cost £19.49/boe (2024). GBP — cited in notes only, **not** used to
    populate a USD field. (Also accessed: NSTA "Analysis of UKCS Operating Costs in 2016",
    <https://www.nstauthority.co.uk/media/4514/ukcs-operating-cost-analysis.pdf>, UOC
    £12/boe in 2016.)

## Exploration well cost check (task assertion)

The claim "onshore ~single-digit MUSD vs deepwater $60–150M+" **verifies** against published
figures: onshore US$3.71M reference exploration well (source 3) and $4.9–8.3M US development
wells (source 1) vs deepwater GoM D&C $60–240M (source 1) with a ~$50M Rystad global
deepwater average (source 6).

## Derived values (flagged, not copied verbatim from a source)

- `onshore.schedule_years` 0.4–1.2 = sum of cited components (<2 months drilling + 3–12
  months completion, source 2).
- `fpso_standalone.schedule_years` 2.5–3.2 = date arithmetic between cited events: Liza Ph1
  FID 16 Jun 2017 → first oil 20 Dec 2019 (sources 11, 12); Liza Ph2 FID 3 May 2019 →
  expected mid-2022 startup (source 13, planned not actual).
- `deepwater_tieback.schedule_years` low endpoint 2.0 is Kaikias' cited "two-year timeline"
  (source 7); high endpoint 3.0 is WoodMac's "less than three years" average (source 8).

## Unverified / omitted (empty fields — do not fill without a new citation)

- `onshore.capex_usd_boe_*` — no accessible published onshore development capex $/boe range
  found (EIA/IHS unit-cost charts are figures without extractable numbers; Rystad publishes
  breakevens, not capex/boe).
- `shelf_tieback.capex_usd_boe_*` — no shelf-specific $/boe range found; nearest public
  anchors are breakeven $37/bbl (source 5) and WoodMac's Apr 2018 all-FID average $4.9/boe
  vs $11.3/boe in 2011 (<https://www.woodmac.com/press-releases/upstream-fids-pushes-on-with-lower-costs/>,
  accessed — covers all 2018 FIDs, not shelf specifically).
- `shelf_tieback.opex_usd_bbl_*` — only GBP figures found (NSTA UKCS £12/boe 2016,
  £19.49/boe 2024); not converted to USD to avoid injecting an uncited FX assumption.
- `shelf_tieback.schedule_years_*` — no defensible public range found for shallow-water
  tieback sanction-to-first-oil.
- `deepwater_tieback.opex_usd_bbl_*` — no accessible USD/bbl opex or host-tariff benchmark
  found for tiebacks.

## Caveats

- **Vintage mix**: figures span 2004–2025 with no inflation adjustment; the 2004 shelf well
  costs and 2016 EIA/IHS study predate the 2021–24 upstream cost inflation (Rystad, source 5:
  non-OPEC breakeven +5% y/y in 2024). Ranges are deliberately wide.
- **Scope**: the $8–18/boe capex range (source 4) is quoted for offshore as a whole in a
  deepwater-focused article; it is applied to both deepwater rows and NOT to shelf.
- **FPSO opex** is Petrobras pre-salt only — a best-in-class operator; industry-wide FPSO
  opex is likely higher and remains unverified.
- Well cost columns mix development D&C (EIA/IHS) and exploration reference wells (Chatham
  House); per-row `notes` say which is which.
- US/GoM and Guyana/Brazil dominate; ranges may not transfer to high-cost or frontier
  jurisdictions.

## Update policy

Re-verify roughly annually or when the engine's capex sensitivity flags a benchmark as
binding. Any edit must update `retrieved_at` and re-access every URL in that row's
`source_url`; if a URL has died, replace it or empty the fields it backed.
