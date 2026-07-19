"""Generate a feasibility memo from the frozen snapshot (CLI, §10).

Usage:
  uv run python ops/make_memo.py --spec ops/showcase_blocks.json --block <id>
  uv run python ops/make_memo.py --spec ... --all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ops.refresh import load_dotenv  # noqa: E402


def run_one(spec: dict) -> dict:
    from erda_agents.committee import BlockRequest, run_committee
    from erda_agents.narrators import default_narrator
    from erda_agents.render import memo_markdown
    from erda_agents.tools.base import SnapshotContext

    ctx = SnapshotContext(repo_root=REPO)
    narrator = default_narrator()
    request = BlockRequest(
        block_id=spec["block_id"],
        lat=spec["lat"],
        lon=spec["lon"],
        iso3=spec["iso3"],
        country_name=spec["country_name"],
        host_distance_km=spec["host_distance_km"],
        pg=spec["pg"],
        resource_p90_p50_p10=tuple(spec["resource_p90_p50_p10"]),
        well_cost_musd=spec["well_cost_musd"],
    )
    try:
        memo, _ = run_committee(ctx, request, narrator)
    except RuntimeError as exc:
        # LLM unavailable (e.g. Groq rate limit) → fall back to the labelled
        # template narrator. The verdict + quant hash are narrator-independent
        # (§11.3), so the memo's evidence is identical; only the prose differs,
        # and the UI badge tells the truth about which narrator ran.
        from erda_agents.narrators import TemplateNarrator

        print(f"[warn] narrator failed ({exc}); using TemplateNarrator")
        narrator = TemplateNarrator()
        memo, _ = run_committee(ctx, request, narrator)
    record = {
        "memo": memo.model_dump(),
        "markdown": memo_markdown(memo),
        "narrator": type(narrator).__name__,
        "request": spec,
    }
    out = REPO / "data" / "memos"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{spec['block_id']}.json").write_text(json.dumps(record, indent=2))
    (out / f"{spec['block_id']}.md").write_text(record["markdown"])
    print(
        f"[memo] {spec['block_id']}: {memo.verdict} · EMV {memo.verdict_basis.emv_musd:,.1f} $MM "
        f"· coverage {memo.citation_coverage:.0%} · hash {memo.quant_hash[:12]} "
        f"· narrator {record['narrator']}"
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--block", default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--check-determinism", action="store_true",
                        help="run twice, compare quant hashes")
    args = parser.parse_args()

    load_dotenv(REPO / ".env")
    specs = json.loads(Path(args.spec).read_text())["blocks"]
    selected = specs if args.all else [s for s in specs if s["block_id"] == args.block]
    if not selected:
        raise SystemExit(f"no block matching {args.block!r} in {args.spec}")

    for spec in selected:
        record = run_one(spec)
        if args.check_determinism:
            again = run_one(spec)
            a = record["memo"]["quant_hash"]
            b = again["memo"]["quant_hash"]
            status = "IDENTICAL" if a == b else "MISMATCH — determinism broken"
            print(f"[determinism] {spec['block_id']}: {status}")
            if a != b:
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
