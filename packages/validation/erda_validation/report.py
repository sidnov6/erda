"""Nightly validation report: one JSON artifact the /validation page renders.

Assembled from whatever tables exist in data/parquet — a missing table shows up
as a freshness failure, never as an invented pass. The report itself carries
generation provenance (generated_at, transform_version).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from erda_contracts.ledger import latest_by_table
from erda_contracts.registry import load_registry
from erda_validation import checks

TRANSFORM_VERSION = "validation_report:1.0.0"
REPORT_NAME = "_validation_report.json"


def _records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _summary(sections: dict[str, list[dict]]) -> dict:
    counts = {"pass": 0, "warn": 0, "fail": 0}
    for rows in sections.values():
        for row in rows:
            status = row.get("status")
            if status in counts:
                counts[status] += 1
    counts["overall"] = "fail" if counts["fail"] else ("warn" if counts["warn"] else "pass")
    return counts


def build_report(
    parquet_root: Path,
    registry_path: Path,
    now: datetime,
    *,
    eia_jodi: tuple[pd.DataFrame, pd.DataFrame] | None = None,
    wpsr: pd.DataFrame | None = None,
    curve: pd.DataFrame | None = None,
) -> dict:
    registry = load_registry(registry_path)
    latest = latest_by_table(parquet_root)

    sections: dict[str, list[dict]] = {
        "freshness": _records(checks.freshness(latest, registry, now)),
    }
    if eia_jodi is not None:
        sections["eia_jodi_reconciliation"] = _records(checks.reconcile_eia_jodi(*eia_jodi))
    if wpsr is not None:
        sections["wpsr_consistency"] = _records(checks.wpsr_internal_consistency(wpsr))
    if curve is not None:
        curve_out = checks.curve_checks(curve, now)
        sections["curve_checks"] = _records(curve_out)

    return {
        "generated_at": now.isoformat(),
        "transform_version": TRANSFORM_VERSION,
        "summary": _summary(sections),
        "sections": sections,
    }


def write_report(report: dict, parquet_root: Path) -> Path:
    path = parquet_root / REPORT_NAME
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path
