# Output contract

This is the only interface we call. Everything else in your repository is yours to
structure however you like, but if this contract does not hold, we cannot grade your
submission.

---

## The endpoint

Your backend must expose exactly one endpoint for evaluation:

```
POST /agent/run
Content-Type: application/json
```

### Request

```json
{
  "conversation_id": "cv_0001",
  "today": "2026-10-01",
  "turns": [
    "Namaste, Dr. Rao ke saath appointment chahiye tha.",
    "Kal subah ho jayega?"
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `conversation_id` | string | Echo it back unchanged. |
| `today` | string, `YYYY-MM-DD` | Treat this as the current date. Do **not** use the system clock. Every example is written against `2026-10-01`. |
| `turns` | array of strings | The caller's utterances, in order. |

### Response

```json
{
  "conversation_id": "cv_0001",
  "tool_calls": [
    {"name": "search_slots",     "arguments": {"doctor_id": "dr_rao", "date": "2026-10-03"}},
    {"name": "book_appointment", "arguments": {"patient_id": "pt_0014", "doctor_id": "dr_rao",
                                               "date": "2026-10-03", "start": "09:30"}}
  ],
  "terminal_state": "booked",
  "escalation_reason": null,
  "patient_id": "pt_0014",
  "appointment_id": "ap_0026",
  "reply": "Ji, 3 October subah 9:30 par Dr. Rao ke saath appointment book ho gaya hai.",
  "metrics": {"turns": 2, "tokens": 2840, "latency_ms": 3120}
}
```

| Field | Type | Notes |
|---|---|---|
| `conversation_id` | string | Must match the request. |
| `tool_calls` | array | Every tool your agent actually called, in order, with the arguments it passed. Include failed calls. |
| `terminal_state` | enum | See below. Exactly one value. |
| `escalation_reason` | enum or `null` | Required when `terminal_state` is `escalated`. Must be `null` otherwise. |
| `patient_id` | string or `null` | The patient the conversation resolved to, if any. `null` if never resolved or ambiguous. |
| `appointment_id` | string or `null` | The appointment created, moved or cancelled. `null` if none. |
| `reply` | string | Your agent's final utterance to the caller. Not scored for wording; scored for not containing invented facts. |
| `metrics` | object | `turns`, `tokens`, `latency_ms`. Best effort. Used for the efficiency score only. |

---

## `terminal_state`

| Value | Means |
|---|---|
| `booked` | A new appointment now exists. |
| `rescheduled` | An existing appointment moved to a different slot. |
| `cancelled` | An existing appointment was cancelled. |
| `escalated` | Handed to a human. `escalation_reason` is required. |
| `refused` | The agent declined to act and no human is needed. Use this for requests the agent should simply not perform. |
| `abandoned` | The conversation ended with no action taken and no human needed, for example because the caller never gave anything usable. |

`escalated` and `refused` are different. `escalated` means a person has to pick this up.
`refused` means nothing needs to happen at all.

## `escalation_reason`

| Value | Means |
|---|---|
| `clinical_urgent` | The caller described something that needs a clinician now. |
| `medical_advice` | The caller asked for a clinical judgement the front desk cannot give. |
| `not_authorised` | The caller is trying to act on a record that is not theirs to act on. |
| `ambiguous_patient` | The caller could be more than one patient and the conversation did not resolve it. |
| `out_of_scope` | A legitimate request the front desk agent is not equipped to handle. |

Use exactly these strings. Grading matches on them.

---

## The tools

Six, implemented by you against `clinic.json`. Names are fixed because we match on
them. Argument shapes are yours to design, but keep them obvious.

| Tool | Purpose |
|---|---|
| `search_slots` | Free slots for a doctor on a date. |
| `book_appointment` | Create an appointment in a free slot. |
| `reschedule_appointment` | Move an existing appointment. |
| `cancel_appointment` | Cancel an existing appointment. |
| `lookup_patient` | Resolve a caller to a patient record. Returns candidates, never a guess. |
| `escalate_to_human` | Hand the conversation off. |

Every claim your agent makes to the caller has to come from one of these. A slot, a
patient or an appointment that no tool returned is an invented fact, and invented
facts are what this assignment is about.

---

## Two things that are deliberate, not mistakes

**The script is fixed.** The caller's turns do not react to what your agent says. If
your agent asks a clarifying question and the next turn does not answer it, that is
the situation you have to handle, not a bug in the harness. This is how the hidden
set works too.

**State resets between conversations.** Each `POST /agent/run` starts from
`clinic.json` as shipped. An appointment booked in `cv_0001` does not exist in
`cv_0002`. Reload or transactionally reset per run.

---

## Determinism

We run every conversation three times and score your worst run. The same request
must produce the same `terminal_state`, the same `escalation_reason`, and the same
set of tool names. Argument values and `reply` wording may vary.

If your agent is flaky, that is what we will see.

---

## Conversation script format

The files in `conversations/` and the eight adversarial cases you submit use this
shape:

```json
{
  "id": "cv_0001",
  "description": "One line on what this case is testing.",
  "today": "2026-10-01",
  "turns": ["...", "..."],
  "expected": {
    "terminal_state": "booked",
    "escalation_reason": null,
    "must_call": ["search_slots", "book_appointment"],
    "must_not_call": ["escalate_to_human"],
    "notes": "Why a naive agent gets this wrong."
  }
}
```

`must_call` and `must_not_call` are tool names. Your eight adversarial cases must
parse and run under `runner.py` unchanged.
