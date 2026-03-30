"""REST endpoints for all agents — per-agent routes + unified invoke + listing."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import TypeAdapter

from ai_demo.agents.cv_tailor_text import CVTailorTextAgent
from ai_demo.agents.echo import run_echo
from ai_demo.agents.general import GeneralAgent
from ai_demo.agents.job_search import JobSearchAgent
from ai_demo.agents.recipe import RecipeCreatorAgent
from ai_demo.agents.summarizer import SummarizerAgent
from ai_demo.agents.weather import WeatherAgent
from ai_demo.api.schemas import (
    AgentInfo,
    AgentResponse,
    CVTailorFilesRequest,
    CVTailorInvoke,
    CVTailorRequest,
    EchoInvoke,
    GeneralRequest,
    InvokeRequest,
    JobSearchInvoke,
    RecipeRequest,
    SummarizerInvoke,
    WeatherRequest,
)
from ai_demo.api.security import verify_api_key
from ai_demo.config import get_settings
from ai_demo.core.paths import resolve_under_root
from ai_demo.services.cv_pipeline import tailor_cv_from_samples_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])

# ---- Agent registry (metadata for listing endpoint) ----

AGENT_REGISTRY: list[AgentInfo] = [
    AgentInfo(
        id="echo",
        title="Echo",
        description="Returns your text — no LLM. Use to verify routing.",
    ),
    AgentInfo(
        id="cv_tailor",
        title="CV Tailor (text)",
        description="Tailor CV text to a job description — returns markdown.",
    ),
    AgentInfo(
        id="cv_tailor_files",
        title="CV Tailor (file-based)",
        description="Tailor CV + cover letter using sample files; writes to output/.",
    ),
    AgentInfo(
        id="summarizer",
        title="Document summarizer",
        description="Summarize a PDF or text file.",
    ),
    AgentInfo(
        id="weather",
        title="Weather",
        description="Current weather for any city.",
    ),
    AgentInfo(
        id="recipe",
        title="Recipe Creator",
        description="Generate a recipe from a prompt.",
    ),
    AgentInfo(
        id="job_search",
        title="Job search assistant",
        description="Job search strategy, keywords, and next steps.",
    ),
    AgentInfo(
        id="general",
        title="General Chat",
        description="General-purpose conversational agent.",
    ),
]

_invoke_adapter = TypeAdapter(InvokeRequest)


# ---- Per-agent REST endpoints (hub-style) ----


@router.post("/cv-tailor", response_model=AgentResponse)
async def cv_tailor(body: CVTailorRequest) -> AgentResponse:
    agent = CVTailorTextAgent()
    try:
        out = await agent.run(body.cv_text, body.job_description)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return AgentResponse(agent="cv_tailor", result=out)


@router.post("/cv-tailor-files", response_model=AgentResponse)
async def cv_tailor_files(body: CVTailorFilesRequest) -> AgentResponse:
    try:
        version, summary = await asyncio.to_thread(
            tailor_cv_from_samples_sync,
            (body.job_description or "").strip(),
            body.use_sample_job_file,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    text = (
        f"version=v{version}\n\n{summary}\n\n"
        f"Files under output/: tailored_*_v{version}.* (EN+DE, md/pdf/docx)"
    )
    return AgentResponse(agent="cv_tailor_files", result=text)


@router.post("/weather", response_model=AgentResponse)
async def weather(body: WeatherRequest) -> AgentResponse:
    agent = WeatherAgent()
    try:
        out = await agent.run(body.query)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return AgentResponse(agent="weather", result=out)


@router.post("/recipe", response_model=AgentResponse)
async def recipe(body: RecipeRequest) -> AgentResponse:
    agent = RecipeCreatorAgent()
    try:
        out = await agent.run(body.prompt)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return AgentResponse(agent="recipe_creator", result=out)


@router.post("/general", response_model=AgentResponse)
async def general(body: GeneralRequest) -> AgentResponse:
    agent = GeneralAgent()
    try:
        out = await agent.run(body.message)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return AgentResponse(agent="general", result=out)


# ---- Unified invoke endpoint (server-style discriminated union) ----


@router.post("/invoke", response_model=AgentResponse)
async def invoke(body: InvokeRequest, _: None = Depends(verify_api_key)) -> AgentResponse:
    agent_id = body.agent
    try:
        result = await asyncio.to_thread(_dispatch_invoke, body)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Agent %s failed", agent_id)
        raise HTTPException(status_code=500, detail=str(e)) from e
    return AgentResponse(agent=agent_id, result=result)


# ---- Listing endpoint ----


@router.get("", response_model=list[AgentInfo])
async def list_agents(_: None = Depends(verify_api_key)) -> list[AgentInfo]:
    return AGENT_REGISTRY


# ---- Dispatch logic (sync, called via to_thread) ----


def _dispatch_invoke(body: InvokeRequest) -> str:
    match body:
        case EchoInvoke(text=t):
            return run_echo(t)
        case SummarizerInvoke(file_path=fp):
            path = resolve_under_root(fp)
            if not path.is_file():
                raise FileNotFoundError(f"File not found: {path}")
            agent = SummarizerAgent()
            return agent.summarize(str(path))
        case CVTailorInvoke(
            cv_path=cv,
            cover_letter_path=cl,
            job_desc_path=job,
            output_dir=out,
            photo_path=ph,
        ):
            cv_p = resolve_under_root(cv)
            cl_p = resolve_under_root(cl)
            job_p = resolve_under_root(job)
            out_p = resolve_under_root(out)
            for p, label in [(cv_p, "cv_path"), (cl_p, "cover_letter_path"), (job_p, "job_desc_path")]:
                if not p.is_file():
                    raise FileNotFoundError(f"{label}: file not found: {p}")
            out_p.mkdir(parents=True, exist_ok=True)
            if ph:
                ph_p = resolve_under_root(ph)
                if not ph_p.is_file():
                    raise FileNotFoundError(f"photo_path: file not found: {ph_p}")
                ph = str(ph_p)
            from ai_demo.agents.cv_tailor import CVTailorAgent
            agent = CVTailorAgent()
            return agent.tailor(
                cv_path=str(cv_p),
                cover_letter_path=str(cl_p),
                job_desc_path=str(job_p),
                output_dir=str(out_p),
                photo_path=ph,
            )
        case JobSearchInvoke(query=q, location=loc):
            agent = JobSearchAgent()
            return agent.search(q, loc)
        case _:
            raise ValueError(f"Unhandled agent payload: {type(body)}")
