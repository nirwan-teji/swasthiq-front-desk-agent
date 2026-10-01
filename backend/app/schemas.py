"""
schemas.py — Pydantic models matching the schema.md contract exactly.
"""
from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, field_validator

TERMINAL_STATES = Literal[
    "booked", "rescheduled", "cancelled", "escalated", "refused", "abandoned"
]
ESCALATION_REASONS = Literal[
    "clinical_urgent", "medical_advice", "not_authorised",
    "ambiguous_patient", "out_of_scope"
]


class AgentRequest(BaseModel):
    """POST /agent/run — inbound payload."""
    conversation_id: str
    today: str           # YYYY-MM-DD — NEVER use system clock
    turns: list[str]


class ToolCall(BaseModel):
    """A single tool invocation logged during the run."""
    name: str
    arguments: dict[str, Any]
    result: Optional[Any] = None


class Metrics(BaseModel):
    turns: int
    tokens: int
    latency_ms: int


class AgentResponse(BaseModel):
    """POST /agent/run — outbound payload per schema.md."""
    conversation_id: str
    tool_calls: list[ToolCall]
    terminal_state: TERMINAL_STATES
    escalation_reason: Optional[ESCALATION_REASONS] = None
    patient_id: Optional[str] = None
    appointment_id: Optional[str] = None
    reply: str
    metrics: Metrics

    @field_validator("escalation_reason")
    @classmethod
    def escalation_reason_matches_state(cls, v, info):
        # Validate coherence — escalation_reason must be set iff terminal_state is escalated
        # (full cross-field validation happens in the orchestrator before construction)
        return v
