"""
llm_client.py — Groq / Gemini LLM client with automatic fallback.

Uses Groq as primary (free tier, high speed, tool calling).
Falls back to Google Gemini if GROQ_API_KEY is absent.
temperature=0.0 is enforced for determinism.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from app.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL_FAST,
    GROQ_MODEL_PRIMARY,
    LLM_TEMPERATURE,
    MAX_AGENT_ITERATIONS,
)


# ------------------------------------------------------------------ #
# Tool definitions for LLM function calling                           #
# ------------------------------------------------------------------ #

TOOL_DEFINITIONS_GROQ = [
    {
        "type": "function",
        "function": {
            "name": "lookup_patient",
            "description": "Resolve a caller to patient records. Returns all matching candidates. Never guesses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Patient name or partial name"},
                    "phone": {"type": "string", "description": "10-digit phone number"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_slots",
            "description": "Return available 15-minute appointment slots for a doctor on a specific date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "string", "description": "e.g. dr_rao or dr_sethi"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["doctor_id", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Create a new appointment in a free slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string"},
                    "doctor_id": {"type": "string"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "start": {"type": "string", "description": "HH:MM 24-hour"},
                },
                "required": ["patient_id", "doctor_id", "date", "start"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Move an existing appointment to a new slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string"},
                    "new_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "new_start": {"type": "string", "description": "HH:MM 24-hour"},
                },
                "required": ["appointment_id", "new_date", "new_start"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string"},
                    "patient_id": {"type": "string", "description": "Optional — for ownership verification"},
                },
                "required": ["appointment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": (
                "Hand the conversation to a human agent. "
                "reason must be exactly one of: "
                "clinical_urgent | medical_advice | not_authorised | ambiguous_patient | out_of_scope"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "enum": [
                            "clinical_urgent", "medical_advice",
                            "not_authorised", "ambiguous_patient", "out_of_scope",
                        ],
                    },
                    "detail": {"type": "string", "description": "Short explanation"},
                },
                "required": ["reason"],
            },
        },
    },
]


# ------------------------------------------------------------------ #
# Groq client wrapper                                                 #
# ------------------------------------------------------------------ #

class GroqClient:
    def __init__(self) -> None:
        import httpx
        from groq import Groq  # type: ignore[import]
        # Groq 0.11's default transport still passes the removed `proxies`
        # argument when paired with httpx 0.28 (required by google-genai).
        # Supplying the client explicitly keeps both dependencies compatible.
        self._client = Groq(api_key=GROQ_API_KEY, http_client=httpx.Client())
        self._model = GROQ_MODEL_PRIMARY

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> tuple[dict, int]:
        """
        Returns (message dict, total_tokens).
        """
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": LLM_TEMPERATURE,
            "max_tokens": 1024,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as primary_error:
            # Retry once with the smaller current Groq model. Preserve the
            # provider error if both attempts fail so the API does not look
            # like an unexplained internal server error.
            kwargs["model"] = GROQ_MODEL_FAST
            try:
                resp = self._client.chat.completions.create(**kwargs)
            except Exception as retry_error:
                raise RuntimeError(
                    "Groq request failed for "
                    f"{GROQ_MODEL_PRIMARY} and {GROQ_MODEL_FAST}: "
                    f"{type(retry_error).__name__}: {retry_error}"
                ) from retry_error

        msg = resp.choices[0].message
        tokens = resp.usage.total_tokens if resp.usage else 0
        return _groq_msg_to_dict(msg), tokens


def _groq_msg_to_dict(msg: Any) -> dict:
    d: dict[str, Any] = {"role": msg.role, "content": msg.content or ""}
    if msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    return d


# ------------------------------------------------------------------ #
# Gemini client wrapper                                               #
# ------------------------------------------------------------------ #

class GeminiClient:
    """Fallback to Google Gemini via google-genai SDK."""

    def __init__(self) -> None:
        import google.generativeai as genai  # type: ignore[import]
        genai.configure(api_key=GEMINI_API_KEY)
        self._model_name = GEMINI_MODEL

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> tuple[dict, int]:
        import google.generativeai as genai  # type: ignore[import]

        # Convert messages to Gemini format
        history = []
        system_text = ""
        for m in messages:
            if m["role"] == "system":
                system_text = m["content"]
            elif m["role"] == "user":
                history.append({"role": "user", "parts": [m["content"]]})
            elif m["role"] == "assistant":
                history.append({"role": "model", "parts": [m["content"]]})

        model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_text,
        )
        # No structured tool calling for Gemini in this simplified fallback
        prompt = history[-1]["parts"][0] if history else ""
        chat_sess = model.start_chat(history=history[:-1])
        response = chat_sess.send_message(prompt)
        text = response.text
        tokens = 0
        try:
            tokens = response.usage_metadata.total_token_count
        except Exception:
            pass
        return {"role": "assistant", "content": text}, tokens


# ------------------------------------------------------------------ #
# Factory                                                             #
# ------------------------------------------------------------------ #

def get_llm_client():
    """Return a Groq client if key is configured, else Gemini."""
    if GROQ_API_KEY:
        return GroqClient()
    if GEMINI_API_KEY:
        return GeminiClient()
    raise RuntimeError(
        "No LLM API key configured. Set GROQ_API_KEY or GEMINI_API_KEY in .env"
    )
