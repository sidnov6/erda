# opec_targets.csv — OPEC+ crude production targets (as of July 2026)

Hand-curated table of the **required crude production levels** ("targets") for OPEC and
non-OPEC countries participating in the Declaration of Cooperation (DoC), as most recently
adjusted and **in force for July 2026**. Feeds the ERDA compliance panel:
`compliance % = delivered production (OPEC MOMR secondary sources) / target_kbd`.

- Units: `target_kbd` is thousand barrels per day (kb/d) of crude oil.
- Compiled: **2026-07-18** (all `retrieved_at` values).
- Row count: 22 (18 with targets, 4 with empty `target_kbd` — see Exempt / no-target below).

## How the current targets are constructed

Two layers are in force:

1. **DoC required production levels for 2025–2026** — set by the **38th OPEC and non-OPEC
   Ministerial Meeting (ONOMM), 5 Dec 2024**, which extended the 35th/36th ONOMM levels until
   **31 December 2026**. Reaffirmed by the 40th ONOMM (30 Nov 2025) and the 41st ONOMM
   (7 Jun 2026). These are the operative targets for the eleven countries with no voluntary-cut
   layer (Nigeria, Congo, Gabon, Equatorial Guinea, Azerbaijan, Bahrain, Brunei, Malaysia,
   Mexico, Sudan, South Sudan). `effective_from = 2025-01`.

2. **Monthly required-production tables of the seven voluntary-adjustment countries**
   (Saudi Arabia, Russia, Iraq, Kuwait, Kazakhstan, Algeria, Oman — eight including the UAE
   until April 2026). These countries are phasing out the 1.65 mb/d additional voluntary
   adjustments announced in April 2023; each monthly virtual meeting publishes a per-country
   "Required Production (kbd)" table for the following month. The **July 2026** levels
   (`effective_from = 2026-07`) come from the **7 June 2026** meeting (+188 kb/d group
   increment). For these seven countries the monthly table, not the 38th ONOMM level, is the
   operative compliance target.

## Decision documents used (all retrieved 2026-07-18)

Primary (opec.org):

- 38th ONOMM, 5 Dec 2024 — required production levels for 2025–2026:
  <https://www.opec.org/pr-detail/28-05-dec-2024.html>
  (table image: <https://www.opec.org/assets/imagedb/pic/1738743572.png>)
- 40th ONOMM, 30 Nov 2025 — reaffirmed 38th ONOMM levels until 31 Dec 2026; approved the
  maximum-sustainable-capacity assessment mechanism for 2027 baselines:
  <https://www.opec.org/pr-detail/243582-30-november-2025.html>
- Seven/eight-country meeting, 5 Apr 2026 — May 2026 table (+206 kb/d; last table including
  the UAE, at 3,447 kb/d): <https://www.opec.org/pr-detail/1756597-5-april-2026.html>
  (table image: <https://www.opec.org/assets/imagedb/pic/1775398028.png>)
- Seven-country meeting, 3 May 2026 — June 2026 levels (+188 kb/d; first meeting without the
  UAE): <https://www.opec.org/pr-detail/1779602-3-may-2026.html>
- **Seven-country meeting, 7 Jun 2026 — July 2026 levels (+188 kb/d); source of the
  `target_kbd` values for the seven:** <https://www.opec.org/pr-detail/604-7-june-2026.html>
  (table image: <https://www.opec.org/assets/imagedb/pic/1780835667.png>)
- Seven-country meeting, 5 Jul 2026 — August 2026 levels (+188 kb/d), already announced:
  <https://www.opec.org/pr-detail/609-5-july-2026.html>
  (table image: <https://www.opec.org/assets/imagedb/pic/1783246215.png>)

Secondary (used where a primary was not machine-accessible):

- 41st ONOMM, 7 Jun 2026 (reaffirmation of DoC levels until 31 Dec 2026; next ministerial
  29 Nov 2026): Brunei Department of Energy summary,
  <https://www.energy.gov.bn/41st-opec-and-non-opec-ministerial-meeting-41st-onomm/>
- UAE exit from OPEC and OPEC+ (announced 28 Apr 2026, effective 1 May 2026): Middle East
  Council on Global Affairs,
  <https://mecouncil.org/publication/the-uaes-exit-from-opec-when-politics-and-oil-mix/>.
  The primary WAM statement (<https://www.wam.ae/en/article/bzxzuh7-uae-announces-decision-exit-opec-opec+>)
  is JS-rendered and could not be fetched programmatically; the CSV row is flagged as
  secondary-sourced.

Note on transcription: OPEC publishes the per-country tables as **PNG images** embedded in the
press releases, not as machine-readable text. All `target_kbd` values were transcribed from
those images (URLs recorded per row in `notes`).

## Exempt / no-target countries (empty `target_kbd`)

- **Iran, Libya, Venezuela** — exempt from DoC production targets; they do not appear in the
  38th ONOMM required-production table. Rows kept with empty `target_kbd` so the compliance
  panel can label them explicitly rather than compute a bogus ratio.
- **United Arab Emirates** — exited OPEC and OPEC+ effective **1 May 2026** (announced
  28 Apr 2026). No current DoC target. Last published monthly required level: 3,447 kb/d for
  May 2026. Absent from the June/July/August 2026 tables.
- **Angola** is not in the file: it left OPEC in January 2024 and is not a DoC participant.

## Unverified countries

None omitted for lack of verification — every country in the 38th ONOMM required-production
table, plus the three exempt members and the UAE, is covered by an accessible source listed
above.

## Caveats — read before trusting this file

- **Targets change at ministerial and monthly meetings; re-check this file after every one.**
  Known schedule as of compilation: next seven-country monthly meeting **2 Aug 2026**; JMMC
  meets bimonthly (65th expected ~Aug 2026); **42nd ONOMM on 29 Nov 2026**.
- **August 2026 levels are already announced** (5 Jul 2026 meeting) and take effect
  2026-08-01: Saudi Arabia 10,416; Russia 9,887; Iraq 4,405; Kuwait 2,660; Kazakhstan 1,618;
  Algeria 1,001; Oman 836 kb/d. When the compliance panel rolls to August data, update the
  seven rows (or add a month dimension).
- The seven countries retain "full flexibility to increase, pause or reverse" the voluntary-cut
  phase-out, and compensation schedules for overproduction since Jan 2024 (extended to
  Dec 2026) mean some countries' *effective* required levels can sit below the published table.
  This file records the published required-production levels only, not compensation-adjusted
  ones.
- **Market context:** the US–Israel–Iran conflict (from late Feb 2026) and Strait of Hormuz
  disruption have pushed actual Gulf output far below targets (press reports put Saudi March
  2026 production near 7.8 mb/d vs a >10 mb/d target). Expect compliance ratios well under
  100% for reasons unrelated to policy conformity.
- The 40th ONOMM approved a maximum-sustainable-capacity assessment mechanism to set **2027
  baselines**; expect a structurally new table for 2027.
- Mexico appears in the official 38th ONOMM table (1,753 kb/d) and is included as published;
  OPEC MOMR secondary-source coverage of Mexico may differ from other DoC participants.
- OPEC's monthly increments are rounded per country; monthly tables may differ by ±1 kb/d from
  naive addition (e.g. Iraq July 4,378 + 26 vs August 4,405). Always transcribe the newest
  table rather than adding increments.
