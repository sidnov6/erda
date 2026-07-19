"""Freeze a demo snapshot (spec §15): copy the data plane to an immutable dir
so the public app boots offline and never breaks mid-demo/video.

The snapshot is a self-contained mini repo-root at data/snapshot/, holding a
data/ subtree (parquet, curated, zarr, memos) that mirrors the live layout — so
one env var, ERDA_REPO_ROOT=data/snapshot, points every path resolver at the
frozen copy. A manifest records the freeze time and a content hash per table so
the SNAPSHOT badge and /validation attest to exactly what is frozen.

Usage: uv run python ops/demo_freeze.py
Serve: ERDA_REPO_ROOT=$(pwd)/data/snapshot uv run uvicorn erda_api.main:app
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "data"
ROOT = REPO / "data" / "snapshot"  # a mini repo-root
DST = ROOT / "data"  # its data/ subtree


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    (DST / "parquet").mkdir(parents=True)

    table_hashes = {}
    for parquet in sorted((SRC / "parquet").glob("*.parquet")):
        shutil.copy2(parquet, DST / "parquet" / parquet.name)
        table_hashes[parquet.name] = _sha256(parquet)
    for report in ("_validation_report.json", "labels_summary.json", "model_eval_gbm.json"):
        src = SRC / "parquet" / report
        if src.exists():
            shutil.copy2(src, DST / "parquet" / report)

    shutil.copytree(SRC / "curated", DST / "curated", ignore=shutil.ignore_patterns("snapshot"))
    if (SRC / "memos").exists():
        shutil.copytree(SRC / "memos", DST / "memos")
    if (SRC / "zarr" / "stack.zarr").exists():
        shutil.copytree(SRC / "zarr" / "stack.zarr", DST / "zarr" / "stack.zarr")

    def _dir_bytes(p: Path) -> int:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())

    manifest = {
        "frozen_at": datetime.now(UTC).isoformat(),
        "n_tables": len(table_hashes),
        "table_sha256": table_hashes,
        "total_bytes": _dir_bytes(ROOT),
        "note": "ERDA demo snapshot (§15) — the public app boots from this, offline.",
    }
    (DST / "parquet" / "_snapshot_manifest.json").write_text(json.dumps(manifest, indent=2))

    mb = manifest["total_bytes"] / 1e6
    print(f"[freeze] {len(table_hashes)} tables → {DST}")
    print(f"[freeze] total {mb:.1f} MB, frozen_at {manifest['frozen_at']}")
    print(f"[freeze] serve with: ERDA_REPO_ROOT={ROOT} uv run uvicorn erda_api.main:app")
    return 0


if __name__ == "__main__":
    sys.exit(main())
