"""Request bodies for /api/v1/invoke — add a model + branch in registry when you add an agent."""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class EchoInvoke(BaseModel):
    """Test agent — no LLM."""

    agent: Literal["echo"] = "echo"
    text: str = Field(default="", description="Text to echo back")


class SummarizerInvoke(BaseModel):
    """Summarize a PDF or text file on the server (path relative to project root)."""

    agent: Literal["summarizer"] = "summarizer"
    file_path: str = Field(..., description="e.g. samples/job_description.txt")


class CVTailorerInvoke(BaseModel):
    """Tailor CV and cover letter; writes under output_dir."""

    agent: Literal["cv_tailorer"] = "cv_tailorer"
    cv_path: str = Field(..., description="Path to CV PDF")
    cover_letter_path: str = Field(..., description="Path to cover letter PDF")
    job_desc_path: str = Field(..., description="Path to job description text file")
    output_dir: str = Field(default="output", description="Output directory")
    photo_path: str | None = Field(default=None, description="Optional photo for CV PDF/DOCX")


class JobSearchInvoke(BaseModel):
    """Job search strategy and keywords."""

    agent: Literal["job_search"] = "job_search"
    query: str = Field(..., description="Target role or job-search goal")
    location: str | None = Field(default=None, description="Optional region or city")


InvokeRequest = Annotated[
    Union[EchoInvoke, SummarizerInvoke, CVTailorerInvoke, JobSearchInvoke],
    Field(discriminator="agent"),
]


class InvokeResponse(BaseModel):
    agent: str
    result: str


class AgentInfo(BaseModel):
    id: str
    title: str
    description: str
