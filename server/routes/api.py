import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from server.config import get_server_settings
from server.registry import AGENT_REGISTRY, dispatch_invoke
from server.schemas import AgentInfo, InvokeRequest, InvokeResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agents"])


def verify_api_key(request: Request) -> None:
    settings = get_server_settings()
    if not settings.api_key_header:
        return
    key = request.headers.get("x-api-key")
    if key != settings.api_key_header:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/agents", response_model=list[AgentInfo])
async def list_agents(_: None = Depends(verify_api_key)) -> list[AgentInfo]:
    return AGENT_REGISTRY


@router.post("/invoke", response_model=InvokeResponse)
async def invoke(body: InvokeRequest, _: None = Depends(verify_api_key)) -> InvokeResponse:
    agent_id = body.agent
    try:
        result = await asyncio.to_thread(dispatch_invoke, body)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Agent %s failed", agent_id)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return InvokeResponse(agent=agent_id, result=result)
