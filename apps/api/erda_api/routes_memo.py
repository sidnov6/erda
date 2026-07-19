"""Memo endpoints (§10, §15): SSE-streamed committee runs + persisted memos.

POST /api/memo streams node-by-node progress and persists the result under
data/memos/. Generation is rate-limited by simplicity: one run at a time.
Narration uses the server-side Claude key when configured; otherwise the
labelled template narrator (§15: key server-side only, never client).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from erda_agents.committee import BlockRequest, build_graph
from erda_agents.narrators import default_narrator
from erda_agents.render import memo_markdown
from erda_agents.tools.base import SnapshotContext
from erda_api import data

router = APIRouter(prefix="/api")
_run_lock = threading.Lock()


def memos_dir() -> Path:
    path = data.repo_root() / "data" / "memos"
    path.mkdir(parents=True, exist_ok=True)
    return path


class MemoRequest(BaseModel):
    block_id: str = Field(min_length=1, max_length=64)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    iso3: str = Field(min_length=3, max_length=3)
    country_name: str
    host_distance_km: float = Field(gt=0, le=5000)
    pg: float = Field(gt=0, lt=1, description="user-supplied Pg (§9.8 — no model Pg)")
    resource_p90: float = Field(gt=0)
    resource_p50: float = Field(gt=0)
    resource_p10: float = Field(gt=0)
    well_cost_musd: float = Field(gt=0)


@router.post("/memo")
def generate_memo(req: MemoRequest) -> StreamingResponse:
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(429, "a memo run is already in progress")

    def stream():
        try:
            ctx = SnapshotContext(repo_root=data.repo_root())
            narrator = default_narrator()
            request = BlockRequest(
                block_id=req.block_id,
                lat=req.lat,
                lon=req.lon,
                iso3=req.iso3.upper(),
                country_name=req.country_name,
                host_distance_km=req.host_distance_km,
                pg=req.pg,
                resource_p90_p50_p10=(req.resource_p90, req.resource_p50, req.resource_p10),
                well_cost_musd=req.well_cost_musd,
            )
            app = build_graph(ctx, narrator)
            state = {"request": request, "sections": [], "tool_payloads": {}, "memo": None}
            memo = None
            for update in app.stream(state):
                for node, payload in update.items():
                    yield f"data: {json.dumps({'type': 'node', 'agent': node})}\n\n"
                    if payload and payload.get("memo") is not None:
                        memo = payload["memo"]
            if memo is None:
                yield f"data: {json.dumps({'type': 'error', 'detail': 'no memo produced'})}\n\n"
                return
            record = {
                "memo": memo.model_dump(),
                "markdown": memo_markdown(memo),
                "narrator": type(narrator).__name__,
            }
            path = memos_dir() / f"{req.block_id}.json"
            path.write_text(json.dumps(record, indent=2))
            yield f"data: {json.dumps({'type': 'memo', 'block_id': req.block_id})}\n\n"
        except Exception as exc:  # streamed errors must reach the client honestly
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
        finally:
            _run_lock.release()

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/memos")
def list_memos() -> dict:
    items = []
    for path in sorted(memos_dir().glob("*.json")):
        record = json.loads(path.read_text())
        memo = record["memo"]
        items.append(
            {
                "block_id": memo["block_id"],
                "verdict": memo["verdict"],
                "emv_musd": memo["verdict_basis"]["emv_musd"],
                "generated_at": memo["generated_at"],
                "citation_coverage": memo["citation_coverage"],
                "narrator": record.get("narrator"),
            }
        )
    return {"memos": items}


@router.get("/memos/{block_id}")
def get_memo(block_id: str) -> dict:
    path = memos_dir() / f"{block_id}.json"
    if not path.exists() or "/" in block_id or ".." in block_id:
        raise HTTPException(404, f"no memo for {block_id}")
    return json.loads(path.read_text())


@router.get("/memo-validation")
def memo_validation() -> dict:
    """§11.3 engine & agent validation: per-memo citation coverage, red-team
    presence, verdict, and the quantitative-core determinism hash. Rendered on
    /validation as a first-class pillar."""
    from erda_agents.memo_schema import MIN_CITATION_COVERAGE

    rows = []
    for path in sorted(memos_dir().glob("*.json")):
        record = json.loads(path.read_text())
        memo = record["memo"]
        coverage = memo["citation_coverage"]
        redteam_present = bool(memo.get("redteam_narrative", "").strip())
        rows.append(
            {
                "block_id": memo["block_id"],
                "verdict": memo["verdict"],
                "citation_coverage": coverage,
                "coverage_pass": coverage >= MIN_CITATION_COVERAGE,
                "redteam_present": redteam_present,
                "quant_hash": memo["quant_hash"],
                "narrator": record.get("narrator"),
                "pg_provenance": memo["verdict_basis"]["pg_provenance"],
            }
        )
    overall = "pass" if rows and all(
        r["coverage_pass"] and r["redteam_present"] for r in rows
    ) else ("fail" if rows else "empty")
    return {
        "available": bool(rows),
        "min_coverage": MIN_CITATION_COVERAGE,
        "overall": overall,
        "memos": rows,
    }
