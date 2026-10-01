"""
test_contract.py — Validates output format against schema.md contract.
Tests schema validation, enum restrictions, and structure.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.schemas import (
    AgentRequest,
    AgentResponse,
    ToolCall,
    Metrics,
    TERMINAL_STATES,
    ESCALATION_REASONS,
)


def test_allowed_enums():
    valid_states = {"booked", "rescheduled", "cancelled", "escalated", "refused", "abandoned"}
    valid_reasons = {"clinical_urgent", "medical_advice", "not_authorised", "ambiguous_patient", "out_of_scope"}
    # Verify typing literals match expected set
    assert set(TERMINAL_STATES.__args__) == valid_states
    assert set(ESCALATION_REASONS.__args__) == valid_reasons


def test_agent_request_validation():
    req = AgentRequest(
        conversation_id="cv_test",
        today="2026-10-01",
        turns=["Hello", "I want an appointment"]
    )
    assert req.conversation_id == "cv_test"
    assert len(req.turns) == 2


def test_agent_response_contract_booked():
    resp = AgentResponse(
        conversation_id="cv_0001",
        terminal_state="booked",
        escalation_reason=None,
        patient_id="pt_0001",
        appointment_id="ap_0016",
        reply="Your appointment with Dr. Rao is confirmed.",
        tool_calls=[
            ToolCall(
                name="book_appointment",
                arguments={"patient_id": "pt_0001", "doctor_id": "dr_rao", "date": "2026-10-08", "start": "10:00"}
            )
        ],
        metrics=Metrics(turns=4, tokens=1200, latency_ms=1450)
    )
    data = resp.model_dump()
    assert data["terminal_state"] == "booked"
    assert data["escalation_reason"] is None
    assert data["appointment_id"] == "ap_0016"
    assert len(data["tool_calls"]) == 1
    assert data["metrics"]["turns"] == 4


def test_agent_response_contract_escalated():
    resp = AgentResponse(
        conversation_id="cv_0011",
        terminal_state="escalated",
        escalation_reason="clinical_urgent",
        patient_id=None,
        appointment_id=None,
        reply="Please seek emergency care immediately.",
        tool_calls=[],
        metrics=Metrics(turns=3, tokens=450, latency_ms=300)
    )
    data = resp.model_dump()
    assert data["terminal_state"] == "escalated"
    assert data["escalation_reason"] == "clinical_urgent"
    assert data["patient_id"] is None

