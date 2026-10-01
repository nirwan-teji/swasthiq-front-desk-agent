"""FastAPI route for POST /agent/run."""
import logging

from fastapi import APIRouter, HTTPException
from app.schemas import AgentRequest, AgentResponse
from app.agent import orchestrator

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/agent/run", response_model=AgentResponse)
async def agent_run(request: AgentRequest) -> AgentResponse:
    """
    The single graded endpoint. Processes a full conversation and returns
    a schema.md-compliant response.
    """
    try:
        return orchestrator.run(
            conversation_id=request.conversation_id,
            today=request.today,
            turns=request.turns,
        )
    except RuntimeError as exc:
        # A missing/invalid provider key must be actionable, not an opaque 500.
        logger.exception("Agent run failed during provider or grounding validation")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        # Provider SDK/network failures are service errors, not malformed caller
        # requests. Keep the internal exception out of the public response.
        logger.exception("Unexpected agent run failure")
        raise HTTPException(
            status_code=502,
            detail="The configured language-model provider could not complete the request.",
        ) from exc
