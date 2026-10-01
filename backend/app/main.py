"""
main.py — FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_agent import router as agent_router
from app.api.routes_queue import router as queue_router
from app.api.routes_agent import agent_run as _agent_run_fn
from app.api.routes_queue import store_result
from app.schemas import AgentRequest
import app.api.routes_agent as _ar_module

app = FastAPI(
    title="SwasthiQ Clinic Front Desk Agent",
    description="AI-powered clinic front desk for Sunrise Clinic, Dehradun.",
    version="1.0.0",
)

# Allow the React frontend on any port during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router)
app.include_router(queue_router)


# Intercept /agent/run responses to populate the frontend store
from fastapi import Request, Response
from fastapi.routing import APIRoute
import json as _json
from datetime import datetime, timezone


@app.middleware("http")
async def capture_agent_runs(request: Request, call_next):
    request_payload = {}
    if request.url.path == "/agent/run" and request.method == "POST":
        try:
            request_payload = _json.loads(await request.body())
        except Exception:
            request_payload = {}

    response = await call_next(request)

    if request.url.path == "/agent/run" and request.method == "POST":
        # Never consume/rebuild error responses. FastAPI's structured error
        # body must pass through untouched so provider failures remain visible.
        if response.status_code >= 400:
            return response

        # Read body bytes — note: streaming body already consumed by the route
        # so we capture via response body bytes
        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk

        try:
            result_data = _json.loads(body_bytes.decode("utf-8"))
            conv_id = result_data.get("conversation_id", "unknown")
            # Keep UI-only transcript metadata in the dashboard store without
            # changing the frozen /agent/run response contract.
            result_data["raw_turns"] = request_payload.get("turns", [])
            result_data["today"] = request_payload.get("today", "")
            result_data["caller_preview"] = (
                request_payload.get("turns", [""])[0]
                if request_payload.get("turns") else ""
            )
            result_data["created_at"] = datetime.now(timezone.utc).isoformat()
            if request_payload.get("turns"):
                store_result(conv_id, result_data)
        except Exception:
            pass

        return Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    return response


@app.get("/health")
def health():
    return {"status": "ok"}
