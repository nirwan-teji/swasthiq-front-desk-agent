"""
test_tools.py — Unit tests for the tool layer (database.py).
These tests run against the real clinic.json and require no LLM API key.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import threading
from app.database import fresh_state


@pytest.fixture
def state():
    return fresh_state()


# ------------------------------------------------------------------ #
# search_slots                                                        #
# ------------------------------------------------------------------ #

def test_search_slots_normal(state):
    """Dr. Rao has slots on a regular Thursday."""
    result = state.search_slots(doctor_id="dr_rao", date="2026-10-08")
    assert "error" not in result
    assert len(result["slots"]) > 0
    # 09:00 should be taken by ap_0015
    assert "09:00" not in result["slots"]


def test_search_slots_holiday(state):
    """2026-10-02 is a clinic holiday — no slots."""
    result = state.search_slots(doctor_id="dr_rao", date="2026-10-02")
    assert "error" in result
    assert result["slots"] == []


def test_search_slots_doctor_on_leave(state):
    """Dr. Sethi is on leave 5-7 Oct."""
    result = state.search_slots(doctor_id="dr_sethi", date="2026-10-05")
    assert "error" in result
    assert result["slots"] == []


def test_search_slots_sunday_no_windows(state):
    """No doctor has Sunday windows — expect empty slots."""
    result = state.search_slots(doctor_id="dr_rao", date="2026-10-04")
    assert result["slots"] == []


def test_search_slots_unknown_doctor(state):
    result = state.search_slots(doctor_id="dr_nobody", date="2026-10-08")
    assert "error" in result


# ------------------------------------------------------------------ #
# lookup_patient                                                      #
# ------------------------------------------------------------------ #

def test_lookup_by_phone_unique(state):
    """Exact phone → unique match."""
    result = state.lookup_patient(phone="9812200311")
    assert result["count"] == 1
    assert result["candidates"][0]["name"] == "Harpreet Singh"


def test_lookup_by_name_ambiguous(state):
    """'Sharma' matches three patients — must return all three."""
    result = state.lookup_patient(name="Sharma")
    assert result["count"] >= 3


def test_lookup_by_name_and_phone(state):
    """Name + phone → unique match."""
    result = state.lookup_patient(name="Rajesh Kumar Sharma", phone="9812200011")
    assert result["count"] == 1
    assert result["candidates"][0]["id"] == "pt_0001"


def test_lookup_no_match(state):
    result = state.lookup_patient(name="Zardoz Nobody")
    assert result["count"] == 0


def test_lookup_guardian(state):
    """Sunita Gupta (pt_0008) is guardian of Aarav and Arjun."""
    result = state.lookup_patient(phone="9812200166", name="Sunita Gupta")
    assert result["count"] == 1
    patient = result["candidates"][0]
    assert "pt_0006" in patient["guardian_of"] or "pt_0007" in patient["guardian_of"]


# ------------------------------------------------------------------ #
# book_appointment                                                    #
# ------------------------------------------------------------------ #

def test_book_appointment_success(state):
    """Book a free slot for Dr. Rao on Saturday 3 Oct."""
    result = state.book_appointment(
        patient_id="pt_0013",
        doctor_id="dr_rao",
        date="2026-10-03",
        start="09:00",  # first slot; 09:15 and 09:45 are taken
    )
    assert "appointment_id" in result
    assert "error" not in result


def test_book_appointment_taken_slot(state):
    """09:00 on 2026-10-08 is already booked."""
    result = state.book_appointment(
        patient_id="pt_0013",
        doctor_id="dr_rao",
        date="2026-10-08",
        start="09:00",
    )
    assert "error" in result


def test_book_appointment_holiday(state):
    result = state.book_appointment(
        patient_id="pt_0013",
        doctor_id="dr_rao",
        date="2026-10-02",
        start="09:00",
    )
    assert "error" in result


def test_double_booking_prevention_concurrent(state):
    """Race condition: two threads try to book the same slot simultaneously."""
    results = []

    def book():
        r = state.book_appointment(
            patient_id="pt_0026",
            doctor_id="dr_rao",
            date="2026-10-03",
            start="09:00",
        )
        results.append(r)

    t1 = threading.Thread(target=book)
    t2 = threading.Thread(target=book)
    t1.start(); t2.start()
    t1.join(); t2.join()

    successes = [r for r in results if "appointment_id" in r]
    errors = [r for r in results if "error" in r]
    assert len(successes) == 1, "Only one booking should succeed"
    assert len(errors) == 1, "One should fail with an error"


# ------------------------------------------------------------------ #
# reschedule_appointment                                              #
# ------------------------------------------------------------------ #

def test_reschedule_success(state):
    """Reschedule ap_0001 (pt_0001, dr_rao, 2026-10-01 09:30) to Sat 09:00."""
    result = state.reschedule_appointment(
        appointment_id="ap_0001",
        new_date="2026-10-03",
        new_start="09:00",
    )
    assert "error" not in result
    assert result["status"] == "rescheduled"


def test_reschedule_unknown_appointment(state):
    result = state.reschedule_appointment(
        appointment_id="ap_9999",
        new_date="2026-10-03",
        new_start="09:00",
    )
    assert "error" in result


# ------------------------------------------------------------------ #
# cancel_appointment                                                  #
# ------------------------------------------------------------------ #

def test_cancel_own_appointment(state):
    """pt_0004 has ap_0002 today — cancel it."""
    result = state.cancel_appointment(appointment_id="ap_0002", patient_id="pt_0004")
    assert result["status"] == "cancelled"


def test_cancel_wrong_patient(state):
    """ap_0002 belongs to pt_0004, not pt_0013."""
    result = state.cancel_appointment(appointment_id="ap_0002", patient_id="pt_0013")
    assert "error" in result


# ------------------------------------------------------------------ #
# escalate_to_human                                                   #
# ------------------------------------------------------------------ #

def test_escalate_valid_reason(state):
    result = state.escalate_to_human(reason="clinical_urgent")
    assert result["escalated"] is True
    assert result["reason"] == "clinical_urgent"


def test_escalate_invalid_reason(state):
    result = state.escalate_to_human(reason="bad_reason")
    assert "error" in result
