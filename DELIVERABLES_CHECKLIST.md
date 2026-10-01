# SwasthiQ Front Desk Agent — Deliverables Checklist

Audit date: 2026-10-01  
Scope: assignment deliverables, backend, frontend, documentation, tests, and runtime verification.

## Status legend

- ✅ Done — present and verified.
- 🟡 Incomplete — present or working, but needs polish, correction, or stronger verification.
- 🔴 Not done — missing or not verifiable in this repository.

## Overall result

| Area | Status | Notes |
|---|---:|---|
| Backend implementation | ✅ | FastAPI agent endpoint, schemas, tools, orchestration, safety guard, and queue APIs are present. |
| Frontend implementation | ✅ | React/Vite dashboard, handoff queue, conversation detail, simulation modal, and responsive styling are present. |
| Automated backend tests | ✅ | `45 passed`. |
| Frontend production build | ✅ | `npm run build` passes. |
| End-to-end runtime | ✅ | Clean backend and frontend tested; health, proxy, and simulation requests returned `200 OK`. |
| Assignment documentation | ✅ | README, schema, decisions, transcript, environment template, and this audit are present and updated. |
| Deployment / public URL | 🔴 | No deployed frontend/backend URL is included. |
| Video walkthrough | 🔴 | No recording or completed video script is included. |

## 1. Required repository and setup deliverables

| Status | Deliverable | Evidence / location | Notes |
|---:|---|---|---|
| ✅ | Single-command local startup | [`run.sh`](run.sh) | Starts backend and frontend. |
| ✅ | Docker backend definition | [`backend/Dockerfile`](backend/Dockerfile) | Present. |
| ✅ | Docker Compose setup | [`docker-compose.yml`](docker-compose.yml) | Present. |
| ✅ | Dependency manifests | [`backend/requirements.txt`](backend/requirements.txt), [`frontend/package.json`](frontend/package.json), [`frontend/package-lock.json`](frontend/package-lock.json) | Present. |
| ✅ | Environment configuration | `backend/.env` | Local key is configured; do not commit or share secrets. |
| ✅ | Safe environment template | [`backend/.env.example`](backend/.env.example) | Placeholder-only provider configuration is present. |
| ✅ | Clinic ground-truth data | [`clinic.json`](clinic.json) | Present and used by the backend. |
| ✅ | Frozen response contract | [`schema.md`](schema.md) | Present. |
| ✅ | Official replay runner | [`runner.py`](runner.py) | Present. |
| ✅ | CI workflow | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | Backend tests and frontend build are configured. |
| 🔴 | Public deployment URL | — | No deployed URL found in the repository. |

## 2. Backend and agent deliverables

| Status | Deliverable | Evidence / location | Notes |
|---:|---|---|---|
| ✅ | FastAPI application | [`backend/app/main.py`](backend/app/main.py) | App, CORS, health endpoint, and response capture middleware are present. |
| ✅ | `POST /agent/run` endpoint | [`backend/app/api/routes_agent.py`](backend/app/api/routes_agent.py) | Accepts conversation ID, today, and turns. |
| ✅ | Queue/history endpoints | [`backend/app/api/routes_queue.py`](backend/app/api/routes_queue.py) | Used by the dashboard. |
| ✅ | Pydantic request/response schemas | [`backend/app/schemas.py`](backend/app/schemas.py) | Present. |
| ✅ | LLM integration | [`backend/app/agent/llm_client.py`](backend/app/agent/llm_client.py) | Groq primary with Gemini fallback configuration. Live Groq key/model request tested successfully. |
| ✅ | Tool-calling orchestrator | [`backend/app/agent/orchestrator.py`](backend/app/agent/orchestrator.py) | Multi-step lookup, slot search, booking, cancellation, rescheduling, and escalation loop. |
| ✅ | Deterministic clinic tool layer | [`backend/app/database.py`](backend/app/database.py) | Six clinic operations are implemented. |
| ✅ | Patient lookup and ambiguity handling | `database.py`, `orchestrator.py` | Returns candidates instead of guessing. |
| ✅ | Appointment booking | `database.py` | Validates patient, doctor, date, slot, holidays, and collisions. |
| ✅ | Appointment rescheduling | `database.py` | Present and tested. |
| ✅ | Appointment cancellation | `database.py` | Present and tested. |
| ✅ | Human escalation | `database.py`, `safety_guard.py` | Allowed escalation reasons are constrained. |
| ✅ | Thread-safe booking protection | [`backend/tests/test_tools.py`](backend/tests/test_tools.py) | Concurrency behavior is covered by tests. |
| ✅ | Request-scoped state reset | `database.py`, `orchestrator.py` | Fresh state is created for each run. |
| ✅ | Relative/Hinglish date resolution | [`backend/app/agent/date_resolver.py`](backend/app/agent/date_resolver.py) | Unit tested. |
| ✅ | Emergency hard rule | [`backend/app/agent/safety_guard.py`](backend/app/agent/safety_guard.py) | Runs before LLM calls. |
| ✅ | Medical-advice escalation | `safety_guard.py` | Runs before LLM calls. |
| ✅ | Prompt-injection refusal | `safety_guard.py` | Runs before LLM calls. |
| 🟡 | Fully deterministic live LLM output | `llm_client.py`, `orchestrator.py` | Temperature is `0.0`, but the three-run replay proved that routine LLM tool paths can still vary and can hit provider rate limits. Safety paths are deterministic. |
| ✅ | Explicit post-flight ID validation | [`backend/app/agent/orchestrator.py`](backend/app/agent/orchestrator.py) | `_validate_grounded_ids` rejects IDs not returned by tools. |
| ✅ | Provider error diagnostics | [`backend/app/api/routes_agent.py`](backend/app/api/routes_agent.py) | Provider/grounding failures now emit server-side stack traces and actionable 502/503 responses. |

## 3. Frontend UI deliverables

| Status | Deliverable | Evidence / location | Notes |
|---:|---|---|---|
| ✅ | React application shell | [`frontend/src/App.tsx`](frontend/src/App.tsx) | Loads queue data and controls detail/simulation states. |
| ✅ | Shared clinic sidebar | [`frontend/src/components/Sidebar.tsx`](frontend/src/components/Sidebar.tsx) | Branding, navigation, open-count badge, run simulation action, active status. |
| ✅ | Handoff Queue screen | [`frontend/src/pages/HandoffQueue.tsx`](frontend/src/pages/HandoffQueue.tsx) | Header, subtitle, metrics, open handoffs table. |
| ✅ | Conversation Detail screen | [`frontend/src/pages/ConversationDetail.tsx`](frontend/src/pages/ConversationDetail.tsx) | Transcript, outcome panel, terminal status, back navigation. |
| ✅ | Run Simulation modal | [`frontend/src/components/RunSimulationModal.tsx`](frontend/src/components/RunSimulationModal.tsx) | Presets, editable ID/date/turns, loading state, API errors. |
| ✅ | Conversation transcript | [`frontend/src/components/TranscriptView.tsx`](frontend/src/components/TranscriptView.tsx) | Caller bubbles, agent response, tool-call boxes, terminal action. |
| ✅ | Outcome inspector | [`frontend/src/components/OutcomePanel.tsx`](frontend/src/components/OutcomePanel.tsx) | Terminal state, escalation reason, IDs, tools, turns, tokens, latency. |
| ✅ | Metric cards | [`frontend/src/components/StatCard.tsx`](frontend/src/components/StatCard.tsx) | Conversations, completed, escalated, urgent. |
| ✅ | Handoff table | [`frontend/src/components/HandoffTable.tsx`](frontend/src/components/HandoffTable.tsx) | Reasons, caller preview, time, resolve action. |
| ✅ | UI color system | [`frontend/src/index.css`](frontend/src/index.css) | White clinical workspace, pale-blue borders, blue primary, green success, amber warning, red danger, purple medical status. |
| ✅ | Typography | `frontend/src/index.css`, `frontend/index.html` | Plus Jakarta Sans and JetBrains Mono are configured. |
| ✅ | Status badges | `frontend/src/index.css`, `HandoffTable.tsx` | Clinical, authorization, ambiguity, medical, scope, booked, and resolved styles. |
| ✅ | Responsive/layout styling | `frontend/src/index.css` | Layout and mobile breakpoints are present. |
| ✅ | Loading/error states | `RunSimulationModal.tsx` | Spinner/loading label and visible error panel are present. |
| 🟡 | Exact visual parity with reference PDF | `frontend/src/index.css` and components | The implementation is close and functional; formal screenshot-diff measurement is still outstanding. |
| ✅ | Tool return values in UI | `TranscriptView.tsx`, `schemas.py`, `orchestrator.py` | Tool results are now included in the response and rendered in the transcript. |
| ✅ | Frontend static asset/favicons | [`frontend/index.html`](frontend/index.html) | An inline SVG clinic favicon is configured. |
| ✅ | Frontend production build | `frontend/package.json` | `npm run build` passed successfully. |

## 4. Test and evaluation deliverables

| Status | Deliverable | Evidence / location | Notes |
|---:|---|---|---|
| ✅ | Unit tests | `backend/tests/` | 45 tests passed locally. |
| ✅ | Contract tests | [`backend/tests/test_contract.py`](backend/tests/test_contract.py) | Present. |
| ✅ | Date resolver tests | [`backend/tests/test_date_resolver.py`](backend/tests/test_date_resolver.py) | Present. |
| ✅ | Safety guard tests | [`backend/tests/test_safety_guard.py`](backend/tests/test_safety_guard.py) | Present. |
| ✅ | Tool/concurrency tests | [`backend/tests/test_tools.py`](backend/tests/test_tools.py) | Present. |
| ✅ | Starter conversation fixtures | `conversations/cv_0001.json` through `cv_0015.json` | All 15 files are present. |
| ✅ | Adversarial fixtures | `adversarial/adv_0001.json` through `adv_0008.json` | All 8 files are present. |
| ✅ | Complete 15-conversation replay evidence | `results/` | `python3 runner.py` completed all 15 scripts with 0 failures. |
| 🟡 | Three-run determinism evidence | `results/` | Some three-run files exist, but they cover only selected scenarios and not a complete live-LLM audit. |
| ✅ | Adversarial expected behavior | `safety_guard.py`, `orchestrator.py` | Shared-phone child ambiguity now deterministically escalates as `ambiguous_patient`; the case was verified over HTTP. |
| ✅ | Live HTTP smoke test | Runtime verification | Health, frontend proxy, booking, cancellation/escalation, and safety paths returned `200 OK`. |

## 5. Documentation and submission deliverables

| Status | Deliverable | Evidence / location | Notes |
|---:|---|---|---|
| ✅ | README quickstart | [`README.md`](README.md) | Present. |
| ✅ | API/contract documentation | [`README.md`](README.md), [`schema.md`](schema.md) | Present. |
| ✅ | Architecture documentation | [`README.md`](README.md), [`DECISIONS.md`](DECISIONS.md) | Present. |
| ✅ | Ambiguity and tradeoff log | [`DECISIONS.md`](DECISIONS.md) | Includes phone normalization, guardians, dates, concurrency, and safety. |
| ✅ | AI development transcript | [`ai_transcript.txt`](ai_transcript.txt) | Present. |
| ✅ | Accurate model/benchmark documentation | [`README.md`](README.md), [`DECISIONS.md`](DECISIONS.md) | Current GPT-OSS models, retry behavior, and provider-dependent metrics are documented. |
| 🟡 | Submission-ready security hygiene | `backend/.env`, `.gitignore` | `.env` is now ignored and `.env.example` is safe; rotate the key before external submission because it was exposed during local debugging. |
| 🔴 | Three-minute video script/recording | — | No dedicated video script or recording was found. |
| 🔴 | Public deployment instructions with live URL | — | Docker/local startup exists, but no deployed environment is documented. |
| ✅ | Final evaluator handoff notes | This file | Final commands, evidence, limitations, and next actions are documented here. |

## 6. Recommended final actions before submission

1. Add `backend/.env.example` with placeholder variables only.
2. Correct stale model names and benchmark claims in `README.md` and `DECISIONS.md`.
3. Run the official runner for all 15 starter conversations and save the complete results.
4. Run the eight adversarial cases and resolve the `adv_0004` expected-outcome mismatch.
5. Make the UI determinism badge reflect actual evidence instead of always displaying `STABLE`.
6. Add tool result payloads to `/agent/run` or remove the UI’s expectation that every tool box has a return snippet.
7. Add a short video walkthrough script and, if required, a recording or hosted link.
8. Add a deployment URL, or explicitly state that the submission is local-only.
9. Rotate any API key that has been exposed outside the private local environment.

## Verification commands

```bash
cd swasthiq-front-desk-agent

# Backend tests
cd backend
python3 -m pytest -q

# Frontend build
cd ../frontend
npm run build

# Full replay, with backend running on localhost:8000
cd ..
python3 runner.py
python3 runner.py --repeat 3
```
