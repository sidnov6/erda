"""Fetch the five regulator well tables + GOGET, harmonize, write the label DB.

Output: data/parquet/wells_harmonized.parquet (all decision points, excluded
flag carried) + variant parquets + labels_summary.json with every count the
dataset card and the ≥5,000 gate claim rest on. Counts are computed, never
asserted (§5 rule 5: report the actual number).

Usage: uv run python ops/build_labels.py [--offline]  (offline = reuse tables)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

PARQUET = REPO / "data" / "parquet"
FRAGMENTS = REPO / "data" / "curated" / "outcome_map.d"


def fetch_sources() -> list[tuple[str, str]]:
    from erda_contracts.errors import ErdaDataError
    from erda_ingestion.base import run_connector
    from erda_labels.sources import boem_bsee, gem_goget, nlog, nopims, nsta, sodir

    failures = []
    for mod in (sodir, nsta, nlog, boem_bsee, nopims, gem_goget):
        try:
            entry = run_connector(
                source_id=mod.SOURCE_ID,
                transform_version=mod.TRANSFORM_VERSION,
                schema=mod.SCHEMA,
                fetch=mod.fetch,
                table=mod.TABLE,
                root=PARQUET,
            )
            print(f"[ok]   {mod.TABLE}: {entry.rows} rows")
        except ErdaDataError as exc:
            failures.append((mod.SOURCE_ID, str(exc)))
            print(f"[FAIL] {mod.SOURCE_ID}: {exc}")
    return failures


def harmonize_all() -> dict:
    from erda_contracts.errors import ContractViolation
    from erda_labels import harmonize

    frames = []
    for frag_path in sorted(FRAGMENTS.glob("*.csv")):
        frames.append(harmonize.load_outcome_map(frag_path))
    outcome_map = pd.concat(frames, ignore_index=True)

    counts: dict = {"sources": {}, "generated_at": datetime.now(UTC).isoformat()}
    mapped_frames = []
    for source_id, table in [
        ("sodir", "sodir_wells"),
        ("nsta", "nsta_wells"),
        ("nlog", "nlog_wells"),
        ("boem_bsee", "boem_bsee_wells"),
        ("nopims", "nopims_wells"),
    ]:
        path = PARQUET / f"{table}.parquet"
        if not path.exists():
            raise ContractViolation(source_id, f"{table} missing — fetch first")
        df = pd.read_parquet(path)
        raw_n = len(df)

        # §5 rule 4: every well keeps spud_year; drop-and-count the rest.
        no_spud = df["spud_year"].isna()
        no_coord = df["lat"].isna() | df["lon"].isna()
        dropped = df[no_spud | no_coord]
        kept = df[~(no_spud | no_coord)].copy()
        kept["spud_year"] = kept["spud_year"].astype(int)

        mapped = harmonize.map_outcomes(kept, outcome_map, source_id)
        mapped_frames.append(mapped)
        counts["sources"][source_id] = {
            "raw_wellbores": raw_n,
            "dropped_no_spud_year": int(no_spud.sum()),
            "dropped_no_coordinates": int((no_coord & ~no_spud).sum()),
            "kept_wellbores": len(kept),
        }
        print(f"[map]  {source_id}: {raw_n} raw → {len(kept)} kept "
              f"({int(no_spud.sum())} no-spud, {int((no_coord & ~no_spud).sum())} no-coord)")

    all_wells = pd.concat(mapped_frames, ignore_index=True)
    keep_cols = [
        "well_id", "source_id", "lat", "lon", "spud_year", "purpose", "content_raw",
        "label", "shows", "excluded", "td_m", "discovery_id",
    ]
    all_wells = all_wells[keep_cols]
    deduped = harmonize.dedupe_decision_points(all_wells)
    deduped = harmonize.validate_harmonized(deduped)
    variants = harmonize.sensitivity_variants(deduped)

    deduped.to_parquet(PARQUET / "wells_harmonized.parquet", index=False)
    for name, frame in variants.items():
        frame.to_parquet(PARQUET / f"wells_{name}.parquet", index=False)

    counts["decision_points"] = len(deduped)
    counts["variants"] = {
        name: {
            "n": len(frame),
            "positives": int(frame["label"].sum()),
            "success_rate": round(float(frame["label"].mean()), 4) if len(frame) else None,
            "by_source": frame.groupby("source_id").size().to_dict(),
        }
        for name, frame in variants.items()
    }
    counts["gate_5000"] = {
        "target": 5000,
        "primary_actual": len(variants["primary"]),
        "met": bool(len(variants["primary"]) >= 5000),
    }
    (PARQUET / "labels_summary.json").write_text(json.dumps(counts, indent=2))
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="reuse existing tables")
    args = parser.parse_args()

    failures = [] if args.offline else fetch_sources()
    counts = harmonize_all()
    primary = counts["variants"]["primary"]
    print(f"\n[labels] decision points: {counts['decision_points']}")
    print(f"[labels] PRIMARY (wildcats, labeled): n={primary['n']}, "
          f"positives={primary['positives']}, success={primary['success_rate']:.1%}")
    print(f"[labels] ≥5,000 gate: actual {counts['gate_5000']['primary_actual']} "
          f"→ {'MET' if counts['gate_5000']['met'] else 'NOT MET — report honestly'}")
    if failures:
        print(f"\n{len(failures)} source failure(s): {[f[0] for f in failures]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
