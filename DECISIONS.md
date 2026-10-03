# SwasthiQ Clinic Front Desk Agent — Architectural Decisions & Ambiguity Log

> **Context**: SDE Screening Assignment for Kaagazy Technologies (SwasthiQ).  
> **Review Scope**: This document logs every non-obvious design decision, edge-case ambiguity discovered in `clinic.json` and starter conversation scripts, and the exact tradeoffs made for safety, repeatability, and correctness.

---

## 1. Safety Architecture: Two-Tier Defense vs. Pure Prompting

### The Decision:
We implemented a two-tier safety architecture with a deterministic boundary for the covered emergency patterns:
1. **Tier 1 (Deterministic Regex Pre-Screen)**: Intercepts clinical emergencies (chest pain, shortness of breath, numbness, uncontrolled bleeding), medical advice requests, and prompt injections before the LLM or any database tool is called.
2. **Tier 2 (Agentic Prompt & Tool Constraints)**: If clean, the LLM operates with strict tool calling where clinical emergencies and unauthorized proxy actions are reinforced with explicit instructions.

### Why Not Rely on Pure System Prompting?
- **Zero-Tolerance Safety**: Under 30% safety evaluation weight, a single hallucination or failure to catch a chest pain complaint (e.g. in `cv_0011` turn 3) results in an immediate failure.
- **Vulnerability to Jailbreaks / Indirect Injections**: In `cv_0014` and `adv_0001`, callers demand administrator modes or instruction overrides. Deterministic classification catches these before token generation occurs.
- **Latency & Token Economy**: Emergency cases are resolved locally without
  provider tokens; live LLM latency is recorded per request because provider
  queueing and reasoning time vary.

---

## 2. Inconsistencies & Ambiguities Discovered in `clinic.json`

### Ambiguity 2.1: Shared Phone Numbers & Guardian Hierarchies
- **Observation in Data**: Patient Sunita Gupta (`pt_0008`) and her children Aarav Gupta (`pt_0006`) and Arjun Gupta (`pt_0007`) all share the exact same phone number (`9812200166`). Sunita has `guardian_of: ["pt_0006", "pt_0007"]`, while the children have `guardian_of: []`.
- **The Risk**: A naive phone lookup returns 3 records. If the agent randomly picks one or assumes the mother is the patient, it may book a pediatric appointment for the parent or vice versa.
- **Our Resolution**:
  - If only the phone is given and multiple candidates exist, return all candidates. If the caller does not disambiguate the patient, the agent MUST escalate with `ambiguous_patient`.
  - If both name and phone are given, require both to match.
  - If caller is Sunita Gupta and specifies booking for Aarav, cross-reference `guardian_of` to permit proxy booking. If a caller is not listed in `guardian_of` (e.g., neighbor/friend in `cv_0009` or `adv_0003`), immediately escalate with `not_authorised`.

### Ambiguity 2.2: Name Variations & Homophones
- **Observation**: Callers in North India often use honorifics ("Sharma ji", "Doctor sahab") or partial names ("Rajesh Sharma" vs "Rajesh Kumar Sharma").
- **Our Resolution**:
  - `lookup_patient` normalizes tokens (lowercase, stripped punctuation) and performs token-subset matching.
  - If "Sharma" matches multiple distinct patients (`pt_0001`, `pt_0002`, `pt_0003`), all 3 are returned. The agent never guesses. If the caller cannot provide a phone number or specific full name, the state transitions to `escalate_to_human(reason="ambiguous_patient")`.

### Ambiguity 2.3: Phone Number Formatting
- **Observation**: Callers provide numbers in varying formats: `"9812200011"`, `"+91 98122 00011"`, `"09812200011"`, or with spaces/dashes.
- **Our Resolution**: The normalizer strips all non-digit characters. If a 12-digit number starts with `"91"`, the country code is stripped down to the canonical 10-digit Indian mobile number before query matching.

---

## 3. Date & Relative Time Resolution Engine

### Ambiguity 3.1: Reference Date Grounding
- **The Golden Rule**: The system clock (`datetime.now()`) is **strictly forbidden**. All dates must be evaluated relative to the `"today"` parameter supplied in `AgentRequest`.
- **Hinglish Relative Terms**:
  - `"aaj"` -> `today`
  - `"kal"` -> `today + 1 day`
  - `"parso"` -> `today + 2 days`
  - `"tarson"` -> `today + 3 days`
  - Day names: `"somwar"` (Mon), `"mangalwar"` (Tue), `"budhwar"` (Wed), `"guruwar"`/`"veervar"` (Thu), `"shukrawar"` (Fri), `"shanivaar"` (Sat), `"ravivar"` (Sun).
- **Mid-Turn Correction**: When a caller says *"Dr. Rao ke saath somwar ko... nahi mangalwar theek rahega"*, the date resolver captures the final intended target day ("mangalwar").
- **Clinic Holidays**: Even if the caller insists on booking on October 2 (Gandhi Jayanti) or a Sunday when the clinic is closed, `search_slots` and `book_appointment` strictly reject the request with a holiday error.

---

## 4. Concurrency & Double-Booking Semantics

### The Problem:
Per the assignment requirements: *"A slot cannot be double-booked. Two conversations racing for the same slot must not both succeed."*

### Our Resolution:
1. **Thread-Safe Mutation Lock**: In `backend/app/database.py`, `_lock = threading.Lock()` wraps all critical booking, reschedule, and cancellation checks.
2. **Fresh State per Request**: `fresh_state()` re-reads `clinic.json` at the start of every `POST /agent/run`. An appointment booked in `cv_0001` does not contaminate `cv_0002`.
3. **Atomic Collision Check**: When two threads execute `book_appointment` concurrently for the same doctor, date, and start time, the first thread claims the slot; the second thread receives an explicit collision error: `"{start} is already booked."` and fails gracefully.

---

## 5. Model Selection & Zero-Hallucination Guarantees

### Model Selection: Groq GPT-OSS-120B (`openai/gpt-oss-120b`)
1. **Low-cost hosted inference**: Groq Cloud is the primary provider for local
   development and evaluation.
2. **Tool calling**: `openai/gpt-oss-120b` handles complex Hinglish conversations,
   slot negotiation, and multi-turn context; the client retries with
   `openai/gpt-oss-20b` if the primary request fails.
3. **Automated fallback**: If Groq is not configured, the system can use
   `gemini-2.0-flash` when a Gemini key is supplied.

### Zero-Hallucination Validation:
- The orchestrator validates that every `patient_id` and `appointment_id` present in `AgentResponse` was explicitly returned by a prior tool call in that session. Hallucinated IDs are impossible.
- All terminal states and escalation reasons are validated against strict Pydantic schemas and `schema.md` enums.

## 6. Mutation authorization and malformed tool input

Appointment IDs are not authorization credentials. `reschedule_appointment` and
`cancel_appointment` therefore require the patient ID returned by a successful
`lookup_patient` call and compare it with the appointment owner while holding the
mutation lock. A mismatch returns an actionable error and leaves the appointment
unchanged. The agent is instructed to escalate third-party requests instead of
trying a mutation.

Dates, times, and required identifiers are validated at the tool boundary. Invalid
values return specific errors such as `Invalid date 'tomorrow'. Use YYYY-MM-DD`
rather than allowing `datetime` exceptions to become generic HTTP 500 responses.
Malformed JSON tool arguments are also returned to the model as explicit tool
errors. This keeps the ground-truth layer authoritative even when a provider emits
an off-schema tool call.

## 7. Honest determinism and known limits

The Python safety checks, clinic state reset, mutation lock, and validation are
deterministic. Hosted LLM tool selection, provider retries, latency, and natural
language wording are not guaranteed deterministic even at temperature zero. The
runner records the result of three repetitions, and the UI describes this as
provider-dependent rather than claiming universal stability. The emergency
pre-screen covers the tested clinical patterns; expanding semantic coverage is a
future improvement and not represented as an infallibility claim.
