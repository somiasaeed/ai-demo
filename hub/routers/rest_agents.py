"""REST endpoints — hub agents (all admin-protected)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from hub.agents.cv_tailor_text import CVTailorTextAgent
from hub.agents.general import GeneralAgent
from hub.agents.recipe import RecipeAgent
from hub.agents.weather import WeatherAgent
from hub.core.security import require_admin
from hub.services.cv_pipeline import tailor_cv_from_samples_sync

router = APIRouter(prefix="/agents", tags=["agents"])


class CVTailorRequest(BaseModel):
    cv_text: str = Field(..., min_length=1)
    job_description: str = Field(..., min_length=1)


class CVTailorFilesRequest(BaseModel):
    job_description: str | None = Field(
        default=None,
        description="Job posting text; ignored if use_sample_job_file is true",
    )
    use_sample_job_file: bool = Field(
        default=False,
        description="If true, read samples/job_description.txt",
    )

    @model_validator(mode="after")
    def need_input(self) -> CVTailorFilesRequest:
        if self.use_sample_job_file:
            return self
        if not (self.job_description or "").strip():
            raise ValueError("Provide job_description or set use_sample_job_file=true")
        return self


class WeatherRequest(BaseModel):
    query: str = Field(..., description="City or place name", min_length=1)


class RecipeRequest(BaseModel):
    prompt: str = Field(..., min_length=1)


class GeneralRequest(BaseModel):
    message: str = Field(..., min_length=1)


class AgentResponse(BaseModel):
    agent: str
    result: str


@router.post("/cv-tailor", response_model=AgentResponse)
async def cv_tailor(
    body: CVTailorRequest,
    _admin: dict = Depends(require_admin),
) -> AgentResponse:
    agent = CVTailorTextAgent()
    try:
        out = await agent.run(body.cv_text, body.job_description)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return AgentResponse(agent="cv_tailor_text", result=out)


@router.post("/cv-tailor-files", response_model=AgentResponse)
async def cv_tailor_files(
    body: CVTailorFilesRequest,
    _admin: dict = Depends(require_admin),
) -> AgentResponse:
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
async def weather(
    body: WeatherRequest,
    _admin: dict = Depends(require_admin),
) -> AgentResponse:
    agent = WeatherAgent()
    try:
        out = await agent.run(body.query)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return AgentResponse(agent="weather", result=out)


@router.post("/recipe", response_model=AgentResponse)
async def recipe(
    body: RecipeRequest,
    _admin: dict = Depends(require_admin),
) -> AgentResponse:
    agent = RecipeAgent()
    try:
        out = await agent.run(body.prompt)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return AgentResponse(agent="recipe", result=out)


@router.post("/general", response_model=AgentResponse)
async def general(
    body: GeneralRequest,
    _admin: dict = Depends(require_admin),
) -> AgentResponse:
    agent = GeneralAgent()
    try:
        out = await agent.run(body.message)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return AgentResponse(agent="general", result=out)
