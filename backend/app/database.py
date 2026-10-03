"""
database.py — In-memory clinic state manager.

Key design decisions:
- State is loaded fresh from clinic.json at the start of EVERY /agent/run call.
  An appointment booked in cv_0001 does NOT exist when cv_0002 runs.
- A threading.Lock protects book/reschedule/cancel operations so two concurrent
  requests cannot double-book the same slot.
- get_state() returns a deep-copied snapshot; mutations only happen through the
  provided mutator functions that also hold the lock.
"""
from __future__ import annotations

import copy
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from app.config import CLINIC_JSON_PATH

_lock = threading.Lock()


class ClinicState:
    """
    Thread-safe, per-request copy of clinic.json.
    Instantiate fresh for each POST /agent/run.
    """

    def __init__(self, raw: dict) -> None:
        self._data = copy.deepcopy(raw)
        self._next_ap_id = self._compute_next_ap_id()

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _compute_next_ap_id(self) -> int:
        nums = [
            int(ap["id"].split("_")[1])
            for ap in self._data.get("appointments", [])
        ]
        return max(nums, default=0) + 1

    def _alloc_ap_id(self) -> str:
        ap_id = f"ap_{self._next_ap_id:04d}"
        self._next_ap_id += 1
        return ap_id

    # ------------------------------------------------------------------ #
    # Read accessors (return deep copies to prevent accidental mutation)   #
    # ------------------------------------------------------------------ #

    @property
    def clinic(self) -> dict:
        return self._data["clinic"]

    @property
    def slot_minutes(self) -> int:
        return int(self._data["clinic"]["slot_minutes"])

    @property
    def holidays(self) -> list[str]:
        return self._data.get("holidays", [])

    @property
    def doctors(self) -> list[dict]:
        return copy.deepcopy(self._data["doctors"])

    @property
    def patients(self) -> list[dict]:
        return copy.deepcopy(self._data["patients"])

    @property
    def appointments(self) -> list[dict]:
        return copy.deepcopy(self._data["appointments"])

    # ------------------------------------------------------------------ #
    # Patient lookup helpers                                               #
    # ------------------------------------------------------------------ #

    def get_patient_by_id(self, patient_id: str) -> Optional[dict]:
        for p in self._data["patients"]:
            if p["id"] == patient_id:
                return copy.deepcopy(p)
        return None

    def get_appointments_for_patient(self, patient_id: str) -> list[dict]:
        return [
            copy.deepcopy(ap)
            for ap in self._data["appointments"]
            if ap["patient_id"] == patient_id and ap["status"] == "booked"
        ]

    # ------------------------------------------------------------------ #
    # Doctor helpers                                                       #
    # ------------------------------------------------------------------ #

    def get_doctor_by_id(self, doctor_id: str) -> Optional[dict]:
        for d in self._data["doctors"]:
            if d["id"] == doctor_id:
                return copy.deepcopy(d)
        return None

    # ------------------------------------------------------------------ #
    # Slot computation                                                     #
    # ------------------------------------------------------------------ #

    def _is_clinic_open(self, date_str: str) -> bool:
        """Returns False if the date is a clinic-wide holiday."""
        return date_str not in self.holidays

    def _is_doctor_available(self, doctor: dict, date_str: str) -> bool:
        """Returns False if the doctor is on leave that day."""
        return date_str not in doctor.get("leave_dates", [])

    def _day_abbr(self, date_str: str) -> str:
        """Return Mon/Tue/.../Sun from a YYYY-MM-DD string."""
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%a")  # 'Mon', 'Tue', etc.

    @staticmethod
    def _validate_date(date_str: str) -> Optional[str]:
        if not isinstance(date_str, str) or not date_str.strip():
            return "date must be a non-empty string in YYYY-MM-DD format."
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return f"Invalid date '{date_str}'. Use YYYY-MM-DD, for example 2026-10-03."
        return None

    @staticmethod
    def _validate_start(start: str) -> Optional[str]:
        if not isinstance(start, str) or not start.strip():
            return "start must be a non-empty string in HH:MM 24-hour format."
        try:
            datetime.strptime(start, "%H:%M")
        except ValueError:
            return f"Invalid start time '{start}'. Use HH:MM 24-hour format, for example 09:30."
        return None

    def _generate_slots(self, windows: list[dict], date_str: str) -> list[str]:
        """
        Generate all 15-minute slot start times from the doctor's windows for
        this day's abbr. Slots are HH:MM strings.
        """
        day = self._day_abbr(date_str)
        slots: list[str] = []
        seen: set[str] = set()
        for w in windows:
            if w["day"] != day:
                continue
            cur = datetime.strptime(w["start"], "%H:%M")
            end = datetime.strptime(w["end"], "%H:%M")
            while cur < end:
                t = cur.strftime("%H:%M")
                if t not in seen:
                    seen.add(t)
                    slots.append(t)
                cur += timedelta(minutes=self.slot_minutes)
        slots.sort()
        return slots

    def _booked_starts(self, doctor_id: str, date_str: str) -> set[str]:
        return {
            ap["start"]
            for ap in self._data["appointments"]
            if ap["doctor_id"] == doctor_id
            and ap["date"] == date_str
            and ap["status"] == "booked"
        }

    # ------------------------------------------------------------------ #
    # Public tool implementations                                          #
    # ------------------------------------------------------------------ #

    def search_slots(self, doctor_id: str, date: str) -> dict:
        """
        Returns available 15-minute slot start times for a doctor on a date.
        Checks: clinic holiday, doctor leave, and already-booked slots.
        """
        if not isinstance(doctor_id, str) or not doctor_id.strip():
            return {"error": "doctor_id must be a non-empty string.", "slots": []}
        date_error = self._validate_date(date)
        if date_error:
            return {"error": date_error, "slots": []}

        doctor = self.get_doctor_by_id(doctor_id)
        if doctor is None:
            return {"error": f"Unknown doctor_id: {doctor_id}", "slots": []}

        if not self._is_clinic_open(date):
            return {"error": f"{date} is a clinic holiday.", "slots": [], "doctor_id": doctor_id, "date": date}

        if not self._is_doctor_available(doctor, date):
            return {"error": f"Dr. {doctor['name']} is on leave on {date}.", "slots": [], "doctor_id": doctor_id, "date": date}

        all_slots = self._generate_slots(doctor["windows"], date)
        if not all_slots:
            return {"error": f"Dr. {doctor['name']} does not work on {self._day_abbr(date)}s.", "slots": [], "doctor_id": doctor_id, "date": date}

        booked = self._booked_starts(doctor_id, date)
        available = [s for s in all_slots if s not in booked]

        return {
            "doctor_id": doctor_id,
            "doctor_name": doctor["name"],
            "date": date,
            "slots": available,
        }

    def lookup_patient(
        self,
        name: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> dict:
        """
        Resolve a caller to patient records. NEVER guesses — returns all candidates.
        Matching rules:
          1. Exact phone match (10-digit, stripped of non-digits).
          2. If phone matches exactly one → that patient plus guardian check.
          3. Normalized name substring match (case-insensitive).
        """
        candidates: list[dict] = []

        # Normalize phone
        phone_norm = ""
        if phone:
            phone_norm = "".join(c for c in phone if c.isdigit())
            if phone_norm.startswith("91") and len(phone_norm) == 12:
                phone_norm = phone_norm[2:]

        for p in self._data["patients"]:
            matched_phone = phone_norm and p["phone"] == phone_norm
            matched_name = False
            if name:
                # Case-insensitive substring match on normalized tokens
                name_lower = name.lower().strip()
                patient_name_lower = p["name"].lower()
                # Match if the search name is a substring or all tokens match
                name_tokens = name_lower.split()
                patient_tokens = patient_name_lower.split()
                if name_lower in patient_name_lower:
                    matched_name = True
                elif all(t in patient_tokens for t in name_tokens):
                    matched_name = True

            if phone_norm and name:
                if matched_phone and matched_name:
                    candidates.append(copy.deepcopy(p))
            elif phone_norm:
                if matched_phone:
                    candidates.append(copy.deepcopy(p))
            elif name:
                if matched_name:
                    candidates.append(copy.deepcopy(p))

        return {"candidates": candidates, "count": len(candidates)}

    def book_appointment(
        self,
        patient_id: str,
        doctor_id: str,
        date: str,
        start: str,
    ) -> dict:
        """
        Book a slot. Thread-safe. Validates: slot exists in doctor window,
        not a holiday, doctor not on leave, slot not already taken.
        """
        with _lock:
            for field_name, value in (("patient_id", patient_id), ("doctor_id", doctor_id)):
                if not isinstance(value, str) or not value.strip():
                    return {"error": f"{field_name} must be a non-empty string."}
            date_error = self._validate_date(date)
            if date_error:
                return {"error": date_error}
            start_error = self._validate_start(start)
            if start_error:
                return {"error": start_error}

            doctor = self.get_doctor_by_id(doctor_id)
            if doctor is None:
                return {"error": f"Unknown doctor_id: {doctor_id}"}

            patient = self.get_patient_by_id(patient_id)
            if patient is None:
                return {"error": f"Unknown patient_id: {patient_id}"}

            if not self._is_clinic_open(date):
                return {"error": f"{date} is a clinic holiday."}

            if not self._is_doctor_available(doctor, date):
                return {"error": f"Dr. {doctor['name']} is on leave on {date}."}

            all_slots = self._generate_slots(doctor["windows"], date)
            if start not in all_slots:
                return {"error": f"{start} is not a valid slot for Dr. {doctor['name']} on {date}."}

            booked = self._booked_starts(doctor_id, date)
            if start in booked:
                return {"error": f"Slot {start} on {date} is already booked."}

            # Compute end time
            start_dt = datetime.strptime(start, "%H:%M")
            end_dt = start_dt + timedelta(minutes=self.slot_minutes)
            end_str = end_dt.strftime("%H:%M")

            ap_id = self._alloc_ap_id()
            new_ap = {
                "id": ap_id,
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "date": date,
                "start": start,
                "end": end_str,
                "status": "booked",
            }
            self._data["appointments"].append(new_ap)
            return {
                "appointment_id": ap_id,
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "date": date,
                "start": start,
                "end": end_str,
                "status": "booked",
            }

    def reschedule_appointment(
        self,
        appointment_id: str,
        new_date: str,
        new_start: str,
        patient_id: Optional[str] = None,
    ) -> dict:
        """
        Move an existing appointment to a new slot. Atomically frees old slot
        and claims new one.
        """
        with _lock:
            if not isinstance(appointment_id, str) or not appointment_id.strip():
                return {"error": "appointment_id must be a non-empty string."}
            if not isinstance(patient_id, str) or not patient_id.strip():
                return {"error": "patient_id is required to verify authorization for rescheduling."}
            date_error = self._validate_date(new_date)
            if date_error:
                return {"error": f"new_date: {date_error}"}
            start_error = self._validate_start(new_start)
            if start_error:
                return {"error": f"new_start: {start_error}"}

            ap = None
            for a in self._data["appointments"]:
                if a["id"] == appointment_id and a["status"] == "booked":
                    ap = a
                    break

            if ap is None:
                return {"error": f"No active appointment found with id: {appointment_id}"}

            if ap["patient_id"] != patient_id:
                return {"error": "Appointment does not belong to the specified patient; rescheduling is not authorized."}

            doctor = self.get_doctor_by_id(ap["doctor_id"])
            if not self._is_clinic_open(new_date):
                return {"error": f"{new_date} is a clinic holiday."}
            if not self._is_doctor_available(doctor, new_date):
                return {"error": f"Dr. {doctor['name']} is on leave on {new_date}."}

            all_slots = self._generate_slots(doctor["windows"], new_date)
            if new_start not in all_slots:
                return {"error": f"{new_start} is not a valid slot on {new_date}."}

            # Exclude the old slot from booked check (we're freeing it)
            booked = {
                a["start"]
                for a in self._data["appointments"]
                if a["doctor_id"] == ap["doctor_id"]
                and a["date"] == new_date
                and a["status"] == "booked"
                and a["id"] != appointment_id
            }
            if new_start in booked:
                return {"error": f"Slot {new_start} on {new_date} is already booked."}

            new_end_dt = datetime.strptime(new_start, "%H:%M") + timedelta(minutes=self.slot_minutes)
            ap["date"] = new_date
            ap["start"] = new_start
            ap["end"] = new_end_dt.strftime("%H:%M")

            return {
                "appointment_id": appointment_id,
                "new_date": new_date,
                "new_start": new_start,
                "new_end": ap["end"],
                "status": "rescheduled",
            }

    def cancel_appointment(self, appointment_id: str, patient_id: Optional[str] = None) -> dict:
        """
        Cancel an appointment after verifying it belongs to patient_id.
        """
        with _lock:
            if not isinstance(appointment_id, str) or not appointment_id.strip():
                return {"error": "appointment_id must be a non-empty string."}
            if not isinstance(patient_id, str) or not patient_id.strip():
                return {"error": "patient_id is required to verify authorization for cancellation."}
            for ap in self._data["appointments"]:
                if ap["id"] == appointment_id and ap["status"] == "booked":
                    if ap["patient_id"] != patient_id:
                        return {"error": "Appointment does not belong to the specified patient."}
                    ap["status"] = "cancelled"
                    return {
                        "appointment_id": appointment_id,
                        "status": "cancelled",
                    }
            return {"error": f"No active appointment found with id: {appointment_id}"}

    def escalate_to_human(self, reason: str, detail: Optional[str] = None) -> dict:
        """Record and return escalation; reason must be one of the 5 valid enums."""
        valid = {"clinical_urgent", "medical_advice", "not_authorised", "ambiguous_patient", "out_of_scope"}
        if reason not in valid:
            return {"error": f"Invalid escalation reason: {reason}. Must be one of {sorted(valid)}"}
        return {"escalated": True, "reason": reason, "detail": detail or ""}


# ------------------------------------------------------------------ #
# Module-level raw data cache (loaded once per process)              #
# ------------------------------------------------------------------ #
_raw_clinic: Optional[dict] = None


def load_raw_clinic() -> dict:
    global _raw_clinic
    if _raw_clinic is None:
        with open(CLINIC_JSON_PATH, encoding="utf-8") as f:
            _raw_clinic = json.load(f)
    return _raw_clinic


def fresh_state() -> ClinicState:
    """Return a brand-new ClinicState from the on-disk clinic.json.
    Call once per POST /agent/run — never share across requests."""
    return ClinicState(load_raw_clinic())
