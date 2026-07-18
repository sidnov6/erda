# outcome_map.csv

Per-regulator raw well-content code → supervised label (spec §5 rule 2).

- `label`: 1 = discovery ({OIL, GAS, OIL/GAS} families), 0 = not ({DRY}; {SHOWS}
  maps to 0 in the primary dataset and is excluded in a sensitivity run).
- `shows`: true when the code is a shows/traces class — drives the sensitivity
  variant.
- Rows are added ONLY from codes observed in real regulator data, with the
  regulator's documentation page as `source_url` (§7: uncited is rejected).
  `harmonize.map_outcomes` raises on any code not in this file — silent
  mis-mapping is a label bug, the worst kind.
