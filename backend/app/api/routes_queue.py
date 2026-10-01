"""
routes_queue.py — API routes that power the React frontend:
  GET  /api/conversations          — list all runs with summary
  GET  /api/conversations/{id}     — full run detail
  POST /api/conversations/{id}/resolve — mark handoff resolved

These endpoints serve data from an in-memory result store populated by
/agent/run calls (no external database needed).
"""
from __future__ import annotations

import time
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api")

# In-memory store of conversation results (populated by /agent/run)
_result_store: dict[str, dict] = {}


def _is_renderable_record(record: dict) -> bool:
    """Only expose real runs that contain at least one caller turn."""
    turns = record.get("raw_turns")
    return bool(
        record.get("conversation_id")
        and isinstance(turns, list)
        and any(isinstance(turn, str) and turn.strip() for turn in turns)
    )


class ResolveRequest(BaseModel):
    resolved_by: Optional[str] = "staff"


def store_result(conversation_id: str, result: dict) -> None:
    """Called by the agent route to persist results for the frontend."""
    if not _is_renderable_record(result):
        return
    result["_stored_at"] = time.time()
    result["_resolved"] = False
    _result_store[conversation_id] = result


def get_stats() -> dict:
    records = [record for record in _result_store.values() if _is_renderable_record(record)]
    total = len(records)
    completed = sum(
        1 for r in records
        if r.get("terminal_state") not in ("escalated",)
    )
    escalated = sum(
        1 for r in records
        if r.get("terminal_state") == "escalated"
    )
    open_escalations = sum(
        1 for r in records
        if r.get("terminal_state") == "escalated" and not r.get("_resolved")
    )
    urgent = sum(
        1 for r in records
        if r.get("escalation_reason") == "clinical_urgent" and not r.get("_resolved")
    )
    return {
        "total": total,
        "completed": completed,
        "escalated": escalated,
        "open_escalations": open_escalations,
        "urgent": urgent,
    }


@router.get("/conversations")
def list_conversations():
    stats = get_stats()
    results = sorted(
        (record for record in _result_store.values() if _is_renderable_record(record)),
        key=lambda r: r.get("_stored_at", 0),
        reverse=True,
    )
    return {"stats": stats, "conversations": results}


@router.get("/conversations/stats")
def conversation_stats():
    """Return dashboard metrics using the frontend's public field names."""
    stats = get_stats()
    total = stats["total"]
    completed = stats["completed"]
    return {
        "total_conversations": total,
        "completed_by_agent": completed,
        "completion_rate": round((completed / total) * 100) if total else 0,
        "escalated_count": stats["escalated"],
        "open_escalated": stats["open_escalations"],
        "urgent_count": stats["urgent"],
    }


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    result = _result_store.get(conversation_id)
    if result is None or not _is_renderable_record(result):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result


@router.post("/conversations/{conversation_id}/resolve")
def resolve_conversation(conversation_id: str, body: ResolveRequest):
    result = _result_store.get(conversation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    result["_resolved"] = True
    result["_resolved_by"] = body.resolved_by
    return {"ok": True, "conversation_id": conversation_id}
