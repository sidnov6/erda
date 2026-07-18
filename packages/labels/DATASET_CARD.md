# ERDA Harmonized Exploration Well Outcomes — Dataset Card

**Version:** harmonize 1.1.0 · **Built:** 2026-07-18 (live fetches, all sources) ·
**Artifacts:** `data/parquet/wells_harmonized.parquet` + variant parquets + `labels_summary.json`
**Regulators:** Sodir (NO) · NSTA (UK) · NLOG (NL) · BOEM/BSEE (US GoM) · NOPIMS/NOPTA (AU)

## Headline counts (computed, never rounded up — spec §5 rule 5)

| Set | n | positives | success |
|---|---|---|---|
| All decision points (5 regulators) | **32,595** | — | — |
| **PRIMARY** (labeled wildcats) | **17,329** | 10,502 | 60.6% |
| primary_ex_boem (true per-well outcomes only) | 4,885 | 2,012 | 41.2% |
| with_appraisal (sensitivity) | 19,509 | 12,176 | 62.4% |
| shows_excluded (sensitivity) | 16,427 | 10,460 | 63.7% |

The ≥5,000 gate (§14 P2) is met: 17,329 primary outcomes. Honest split: **4,885**
carry true per-well regulator outcomes; **12,444** (BOEM GoM) carry a lease-level
proxy label (below).

## Decisions (the science — §5)

1. **Wildcats only in primary.** Appraisal wells confirm known discoveries —
   including them is label leakage. Sensitivity variant `with_appraisal` reports
   the effect. Purpose mapping per regulator is documented in each
   `erda_labels/sources/*.py` docstring; notable: NSTA "Exploration" ≈ wildcat;
   BOEM `E` conflates wildcat+appraisal (no distinction exists in the raw data);
   CCS wells (Sodir `WILDCAT-CCS`, NSTA `C`-prefix registrations) are **not**
   petroleum exploration → `other`, out of the label set.
2. **Outcome mapping** lives in `data/curated/outcome_map.d/*.csv` — one cited
   row per code *observed in real data* (53 rows total). Families: oil/gas/
   condensate → 1; shows/traces/indications → 0 with `shows=true` (excluded in
   the `shows_excluded` sensitivity); DRY → 0. Unmapped codes raise — nothing is
   ever guessed.
3. **Excluded-class policy** (extension to §5, forced by real data): codes with
   **no recorded geological outcome** — blank, Unknown/UNK, NOT AVAILABLE/NOT
   APPLICABLE, NLOG `FLR` ("technical failure": hole failed before testing its
   objective), Sodir `WATER/GAS` (single ambiguous well) — get `excluded=true`
   and leave the training set. *An unknown outcome is not a dry hole.* Codes
   with a definitive non-hydrocarbon outcome (WATER, SALT, COAL on a
   hydrocarbon well) are valid negatives and stay.
4. **Decision-point dedupe:** wellbores cluster by (source, lat/lon rounded to
   3 dp ≈ 110 m). Any hydrocarbon success in the cluster → success (the
   location's exploration decision found oil); earliest spud year kept;
   `n_wellbores` exposes cluster size. Limitations: dense multi-slot pads can
   merge distinct wells; a co-located later success can lift an early wildcat's
   label (decision-point semantics, accepted and stated).
5. **spud_year mandatory** (time-aware features/hindcast key off it): dropped
   and counted — Sodir 53, BOEM 1,021, NOPIMS 413, others 0.

## Per-source notes and caveats

- **sodir** (2,197 wellbores → 1,197 primary, 45.6% success): richest outcome
  vocabulary (15 codes incl. GAS/CONDENSATE, OIL SHOWS…). Coordinates are ED50
  decimal degrees — the ~100–200 m datum shift vs WGS84 is far below the 0.05°
  grid and is documented, not transformed. Success rate matches Sodir's own
  published technical discovery rates (~40–50%).
- **nsta** (5,129 E&A → 2,401 primary, 35.9%): outcome = `FLOWCLASS` (19
  observed values). Carbon-storage wellbores (`C`-prefix `WELLREGNO`) are
  forced to `other` — the adversarial review caught two CS wells inside the
  E&A pull; a CS well with null FLOWCLASS would otherwise have entered as a
  fake dry hole.
- **nlog** (6,728 boreholes → 1,287 primary, 47.0%): includes genuine
  19th-century mining-era boreholes (spud floor lowered to 1800). Non-HC
  purposes (salt, water, coal, geothermal) land in `other`.
- **boem_bsee** (55,513 → 12,444 primary, 68.2% under proxy): **the GoM label
  is a lease-level PROXY** — a borehole is positive when its bottom lease
  appears in the BOEM field→lease master. Known failure modes: dry wildcats on
  later-productive leases become false positives; the 68.2% rate vs 36–47% for
  true-outcome regulators quantifies the inflation. P3 must run
  `primary_ex_boem` sensitivity and report both; refinement path: constrain
  the join by first-production dates.
- **nopims** (8,910 NOPTA boreholes; 8,031 coordinate-matched via the
  Geoscience Australia layer, 879 excluded and counted): **contributes wells
  but no labels** — no structured outcome exists in public NOPTA/GA data
  (outcomes live inside released well-report PDFs). All rows are
  `excluded=true`; Australia still powers well density/context layers.
- **gem_goget** (7,673 global fields/discoveries, March 2026 release):
  augmentation only, firewalled from labels (survivorship bias — it tracks
  fields that exist, not wells that failed). Reserves fields await the
  registration-gated XLSX (one-shot human form); per-discovery volumes are
  therefore ABSENT, and the Discovery Monitor's creaming curves are
  count-based, labelled as such.

## Known limitations (for reviewers)

Success rates here are *technical* discovery rates (any movable hydrocarbons),
not commercial rates. The five regulators cover mature offshore basins — the
model's negatives under-represent frontier failure (the P3 model card must
carry this). BOEM proxy inflation above. NOPIMS labels absent. Volumes absent.
The 60.6% headline success is proxy-inflated; 41.2% (ex-BOEM) is the honest
true-outcome number.

## Provenance

Every source table row carries `{source_id, retrieved_at, source_url,
transform_version}`; fetch details and drift notes live in
`data/curated/source_registry.yaml` (live-verified 2026-07-18). Outcome-map
rows cite regulator documentation. This card, the code
(`erda_labels/harmonize.py`), and 102 offline tests are the reproducibility
contract: `uv run python ops/build_labels.py` rebuilds everything from the
sources.
