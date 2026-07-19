"""Meta endpoints: validation report, source catalog, data mode.

Honesty rules: a missing report/table returns an explicit "absent" payload —
the UI renders the truth (NO FEED / stale), never a placeholder number.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from erda_api import data
from erda_validation import checks

router = APIRouter(prefix="/api")


@router.get("/validation")
def validation_report() -> dict:
    report = data.read_validation_report()
    if report is None:
        return {
            "available": False,
            "reason": "no validation report generated yet — run ops/refresh.py",
        }
    return {"available": True, "report": report}


@router.get("/sources")
def sources() -> dict:
    reg = data.registry()
    latest = data.ledger_latest()
    fresh = checks.freshness(latest, reg, datetime.now(UTC))
    freshness_by_source = {row["source_id"]: row for row in fresh.to_dict(orient="records")}
    return {
        "sources": [
            {
                "source_id": entry.source_id,
                "name": entry.name,
                "access": entry.access,
                "cadence": entry.cadence,
                "sla_days": entry.sla_days,
                "requires_key": entry.requires_key,
                "verified_at": entry.verified_at,
                "freshness": freshness_by_source.get(entry.source_id),
            }
            for entry in reg.values()
        ]
    }


@router.get("/model")
def model_evaluation() -> dict:
    """§11.2 model validation: the spatial-CV evaluation as measured — including
    the §9.8 falsification-gate verdict. A failed gate is served, not hidden."""
    import json

    path = data.parquet_root() / "model_eval_gbm.json"
    if not path.exists():
        return {"available": False, "reason": "no model evaluation yet — run ops/train_gbm.py"}
    report = json.loads(path.read_text(encoding="utf-8"))
    report.pop("lgbm_params", None)  # params live in the repo; keep the payload lean
    return {"available": True, "evaluation": report}


@router.get("/mode")
def mode() -> dict:
    """LIVE vs SNAPSHOT vs SHELL — the badge tells the truth (§15).

    SNAPSHOT when the data root carries a demo-freeze manifest (the public app
    boots from a frozen snapshot so it never breaks mid-demo). LIVE when tables
    exist without one; SHELL when there is no data at all.
    """
    import json

    latest = data.ledger_latest()
    manifest_path = data.parquet_root() / "_snapshot_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        return {
            "mode": "SNAPSHOT",
            "tables": len(latest),
            "frozen_at": manifest.get("frozen_at"),
            "note": "public demo boots from a frozen snapshot (§15)",
        }
    if not latest:
        return {"mode": "SHELL", "tables": 0}
    newest = max(e.retrieved_at for e in latest.values())
    return {"mode": "LIVE", "tables": len(latest), "newest_retrieved_at": newest.isoformat()}
