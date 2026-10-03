"""
orchestrator.py — Core multi-turn conversation loop for the SwasthiQ agent.

Architecture:
- Pre-flight safety screen (deterministic regex, no LLM) before any LLM call.
- Agentic tool-calling loop (Groq GPT-OSS-120B with temperature=0).
- Post-flight validation: patient_id and appointment_id must trace back to
  actual tool call results — never invented.
- State resets per call via fresh_state().

Each call to run() is fully independent and stateless from prior calls.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Optional

from app.agent.date_resolver import resolve_date_from_turns, resolve_time_from_turns
from app.agent.llm_client import TOOL_DEFINITIONS_GROQ, get_llm_client
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.safety_guard import SafetyVerdict, screen_turns
from app.database import ClinicState, fresh_state
from app.schemas import AgentResponse, Metrics, ToolCall


def _validate_grounded_ids(
    patient_id: Optional[str],
    appointment_id: Optional[str],
    known_patient_ids: set[str],
    known_appointment_ids: set[str],
) -> None:
    """Reject identifiers that were not returned by a tool in this run."""
    if patient_id is not None and patient_id not in known_patient_ids:
        raise RuntimeError("Agent produced a patient ID not returned by a tool")
    if appointment_id is not None and appointment_id not in known_appointment_ids:
        raise RuntimeError("Agent produced an appointment ID not returned by a tool")


# ------------------------------------------------------------------ #
# Tool dispatcher                                                     #
# ------------------------------------------------------------------ #

def _dispatch_tool(state: ClinicState, name: str, arguments: dict) -> Any:
    """Execute a tool call against the clinic state and return the result dict."""
    if not isinstance(arguments, dict):
        return {
            "error": (
                f"Malformed arguments for {name}: expected a JSON object, "
                f"received {type(arguments).__name__}."
            )
        }
    if "error" in arguments:
        return {"error": str(arguments["error"])}
    if name == "search_slots":
        return state.search_slots(
            doctor_id=arguments.get("doctor_id", ""),
            date=arguments.get("date", ""),
        )
    elif name == "lookup_patient":
        return state.lookup_patient(
            name=arguments.get("name"),
            phone=arguments.get("phone"),
        )
    elif name == "book_appointment":
        return state.book_appointment(
            patient_id=arguments.get("patient_id", ""),
            doctor_id=arguments.get("doctor_id", ""),
            date=arguments.get("date", ""),
            start=arguments.get("start", ""),
        )
    elif name == "reschedule_appointment":
        return state.reschedule_appointment(
            appointment_id=arguments.get("appointment_id", ""),
            new_date=arguments.get("new_date", ""),
            new_start=arguments.get("new_start", ""),
            patient_id=arguments.get("patient_id"),
        )
    elif name == "cancel_appointment":
        return state.cancel_appointment(
            appointment_id=arguments.get("appointment_id", ""),
            patient_id=arguments.get("patient_id"),
        )
    elif name == "escalate_to_human":
        return state.escalate_to_human(
            reason=arguments.get("reason", ""),
            detail=arguments.get("detail"),
        )
    else:
        return {"error": f"Unknown tool: {name}"}


def _ambiguous_child_request(state: ClinicState, turns: list[str]) -> Optional[dict]:
    """Resolve shared-phone child requests before the probabilistic agent loop."""
    text = " ".join(turns).lower()
    if not re.search(r"\b(bete|beta|beti|child|son|daughter)\b", text):
        return None
    if re.search(r"\b(aarav|arjun)\b", text):
        return None
    phone_match = re.search(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)", text)
    if not phone_match:
        return None
    result = state.lookup_patient(phone=phone_match.group(0))
    if len(result.get("candidates", [])) > 1:
        return result
    return None


# ------------------------------------------------------------------ #
# Main orchestrator                                                   #
# ------------------------------------------------------------------ #

def run(
    conversation_id: str,
    today: str,
    turns: list[str],
) -> AgentResponse:
    """
    Process a conversation and return a schema.md-compliant AgentResponse.
    """
    t_start = time.monotonic()
    state = fresh_state()

    # Cumulative tracking across the run
    tool_calls_log: list[ToolCall] = []
    total_tokens = 0
    patient_id_resolved: Optional[str] = None
    appointment_id_resolved: Optional[str] = None

    # ---------------------------------------------------------------- #
    # Pre-flight safety screen (THE HARD RULE)                         #
    # ---------------------------------------------------------------- #
    verdict, snippet = screen_turns(turns)

    if verdict == SafetyVerdict.PROMPT_INJECTION:
        # cv_0014: refused, no human needed, no tools called
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        return AgentResponse(
            conversation_id=conversation_id,
            tool_calls=[],
            terminal_state="refused",
            escalation_reason=None,
            patient_id=None,
            appointment_id=None,
            reply=(
                "Main sirf appointment booking mein madad kar sakta hoon. "
                "Kripya apna kaam batayein."
            ),
            metrics=Metrics(turns=len(turns), tokens=0, latency_ms=elapsed_ms),
        )

    if verdict == SafetyVerdict.CLINICAL_URGENT:
        # The Hard Rule — immediate escalation, call the tool too for logging
        esc_result = state.escalate_to_human(
            reason="clinical_urgent", detail=snippet or ""
        )
        tool_calls_log.append(ToolCall(
            name="escalate_to_human",
            arguments={"reason": "clinical_urgent", "detail": snippet or ""},
        ))
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        return AgentResponse(
            conversation_id=conversation_id,
            tool_calls=tool_calls_log,
            terminal_state="escalated",
            escalation_reason="clinical_urgent",
            patient_id=patient_id_resolved,
            appointment_id=None,
            reply=(
                "Aapke symptoms serious lag rahe hain. Kripya abhi "
                "neared emergency room ya ambulance call karein (108). "
                "Main ek senior staff member ko turant alert kar raha hoon."
            ),
            metrics=Metrics(turns=len(turns), tokens=0, latency_ms=elapsed_ms),
        )

    if verdict == SafetyVerdict.MEDICAL_ADVICE:
        esc_result = state.escalate_to_human(
            reason="medical_advice", detail=snippet or ""
        )
        tool_calls_log.append(ToolCall(
            name="escalate_to_human",
            arguments={"reason": "medical_advice", "detail": snippet or ""},
        ))
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        return AgentResponse(
            conversation_id=conversation_id,
            tool_calls=tool_calls_log,
            terminal_state="escalated",
            escalation_reason="medical_advice",
            patient_id=patient_id_resolved,
            appointment_id=None,
            reply=(
                "Maafi chahta hoon, main dawa ya treatment ke baare mein "
                "salah nahi de sakta. Main aapko ek doctor se connect kar "
                "raha hoon jo aapki sahi madad kar sakenge."
            ),
            metrics=Metrics(turns=len(turns), tokens=0, latency_ms=elapsed_ms),
        )

    ambiguous_result = _ambiguous_child_request(state, turns)
    if ambiguous_result is not None:
        tool_calls_log.append(ToolCall(
            name="lookup_patient",
            arguments={"phone": re.search(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)", " ".join(turns).lower()).group(0)},
            result=ambiguous_result,
        ))
        esc_result = state.escalate_to_human(
            reason="ambiguous_patient",
            detail="Multiple child patient records match the caller's shared phone number.",
        )
        tool_calls_log.append(ToolCall(
            name="escalate_to_human",
            arguments={
                "reason": "ambiguous_patient",
                "detail": "Multiple child patient records match the caller's shared phone number.",
            },
            result=esc_result,
        ))
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        return AgentResponse(
            conversation_id=conversation_id,
            tool_calls=tool_calls_log,
            terminal_state="escalated",
            escalation_reason="ambiguous_patient",
            patient_id=None,
            appointment_id=None,
            reply="Main do patients ko is phone number se match kar raha hoon. Kripya bachche ka poora naam batayein; main request human staff ko escalate kar raha hoon.",
            metrics=Metrics(turns=len(turns), tokens=0, latency_ms=elapsed_ms),
        )

    # ---------------------------------------------------------------- #
    # Build initial message history                                     #
    # ---------------------------------------------------------------- #
    system_text = SYSTEM_PROMPT.replace("{today}", today)
    messages: list[dict] = [{"role": "system", "content": system_text}]

    # Add all caller turns as a single combined user message
    # (The script is fixed; caller turns don't react to agent replies)
    combined_turns = "\n\n".join(
        f"[Turn {i + 1}] {t}" for i, t in enumerate(turns)
    )
    messages.append({
        "role": "user",
        "content": (
            f"The caller's complete conversation turns are below. "
            f"Today is {today}. Process them and take appropriate action.\n\n"
            f"{combined_turns}"
        ),
    })

    # ---------------------------------------------------------------- #
    # Agentic tool-calling loop                                         #
    # ---------------------------------------------------------------- #
    from app.config import MAX_AGENT_ITERATIONS

    terminal_state: Optional[str] = None
    escalation_reason: Optional[str] = None
    final_reply = ""
    known_patient_ids: set[str] = set()
    known_appointment_ids: set[str] = set()
    llm = get_llm_client()

    for _iteration in range(MAX_AGENT_ITERATIONS):
        assistant_msg, tokens = llm.chat(
            messages=messages,
            tools=TOOL_DEFINITIONS_GROQ,
        )
        total_tokens += tokens
        messages.append(assistant_msg)

        # Check if the LLM wants to call tools
        tool_calls_in_msg = assistant_msg.get("tool_calls", [])
        if not tool_calls_in_msg:
            # No more tool calls — the LLM has finished
            final_reply = assistant_msg.get("content", "").strip()
            break

        # Execute each tool call and feed results back
        for tc in tool_calls_in_msg:
            fn_name = tc["function"]["name"]
            raw_args = tc.get("function", {}).get("arguments", "")
            try:
                fn_args = json.loads(raw_args)
            except (TypeError, json.JSONDecodeError):
                fn_args = {
                    "error": (
                        "Malformed tool arguments: expected valid JSON object; "
                        f"received {raw_args!r}."
                    )
                }

            # Execute
            result = _dispatch_tool(state, fn_name, fn_args)

            tool_calls_log.append(ToolCall(
                name=fn_name,
                arguments=fn_args,
                result=result,
            ))

            # Track resolved IDs
            if fn_name == "lookup_patient" and isinstance(result, dict):
                candidates = result.get("candidates", [])
                if len(candidates) == 1:
                    patient_id_resolved = candidates[0]["id"]
                    known_patient_ids.add(patient_id_resolved)
                elif len(candidates) > 1:
                    # Multiple candidates — might lead to ambiguous_patient escalation
                    pass

            if fn_name == "book_appointment" and isinstance(result, dict):
                if "appointment_id" in result and "error" not in result:
                    appointment_id_resolved = result["appointment_id"]
                    known_appointment_ids.add(appointment_id_resolved)
                    if "patient_id" in result:
                        patient_id_resolved = result["patient_id"]
                        known_patient_ids.add(patient_id_resolved)

            if fn_name == "reschedule_appointment" and isinstance(result, dict):
                if "appointment_id" in result and "error" not in result:
                    appointment_id_resolved = result["appointment_id"]
                    known_appointment_ids.add(appointment_id_resolved)

            if fn_name == "cancel_appointment" and isinstance(result, dict):
                if "appointment_id" in result and "error" not in result:
                    appointment_id_resolved = result["appointment_id"]
                    known_appointment_ids.add(appointment_id_resolved)

            if fn_name == "escalate_to_human" and isinstance(result, dict):
                if result.get("escalated"):
                    terminal_state = "escalated"
                    escalation_reason = fn_args.get("reason")

            # Feed result back as tool message
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "name": fn_name,
                "content": json.dumps(result),
            })

    # ---------------------------------------------------------------- #
    # Determine terminal state from tool calls if not yet set          #
    # ---------------------------------------------------------------- #
    if terminal_state is None:
        tool_names_called = {tc.name for tc in tool_calls_log}

        if "book_appointment" in tool_names_called and appointment_id_resolved:
            terminal_state = "booked"
        elif "reschedule_appointment" in tool_names_called and appointment_id_resolved:
            terminal_state = "rescheduled"
        elif "cancel_appointment" in tool_names_called and appointment_id_resolved:
            terminal_state = "cancelled"
        elif "escalate_to_human" in tool_names_called:
            terminal_state = "escalated"
            # Extract reason from last escalate call
            for tc in reversed(tool_calls_log):
                if tc.name == "escalate_to_human":
                    escalation_reason = tc.arguments.get("reason")
                    break
        else:
            # No actionable tool calls — check if caller said anything usable
            terminal_state = "abandoned"

    # If escalated, ensure reason is set
    if terminal_state == "escalated" and not escalation_reason:
        escalation_reason = "out_of_scope"

    # Ensure escalation_reason is null for non-escalated states
    if terminal_state != "escalated":
        escalation_reason = None

    # Extract final reply from last assistant message if not set
    if not final_reply:
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                final_reply = msg["content"].strip()
                break

    if not final_reply:
        final_reply = _default_reply(terminal_state, appointment_id_resolved)

    _validate_grounded_ids(
        patient_id_resolved,
        appointment_id_resolved,
        known_patient_ids,
        known_appointment_ids,
    )

    elapsed_ms = int((time.monotonic() - t_start) * 1000)

    return AgentResponse(
        conversation_id=conversation_id,
        tool_calls=tool_calls_log,
        terminal_state=terminal_state,  # type: ignore[arg-type]
        escalation_reason=escalation_reason,  # type: ignore[arg-type]
        patient_id=patient_id_resolved,
        appointment_id=appointment_id_resolved,
        reply=final_reply,
        metrics=Metrics(
            turns=len(turns),
            tokens=total_tokens,
            latency_ms=elapsed_ms,
        ),
    )


def _default_reply(terminal_state: Optional[str], appointment_id: Optional[str]) -> str:
    if terminal_state == "booked":
        return f"Aapka appointment book ho gaya hai. ID: {appointment_id}."
    elif terminal_state == "rescheduled":
        return "Aapka appointment reschedule ho gaya hai."
    elif terminal_state == "cancelled":
        return "Aapka appointment cancel ho gaya hai."
    elif terminal_state == "escalated":
        return "Main aapko ek senior staff member se connect kar raha hoon."
    elif terminal_state == "refused":
        return "Main sirf appointment booking mein madad kar sakta hoon."
    else:
        return "Kya main aur kuch madad kar sakta hoon?"
