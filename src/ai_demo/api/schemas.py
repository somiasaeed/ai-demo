"""Request/response models for the unified API."""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator


# ---- Per-agent request models (hub-style, used by /api/agents/*) ----

class CVTailorRequest(BaseModel):
    cv_text: str = Field(..., min_length=1)
    job_description: str = Field(..., min_length=1)


class CVTailorFilesRequest(BaseModel):
    """File-based CV pipeline — writes to output/ using samples/cv.pdf + cover letter."""

    job_description: str | None = Field(
        default=None,
        description="Job posting text; ignored if use_sample_job_file is true",
    )
    use_sample_job_file: bool = Field(
        default=False,
        description="If true, read samples/job_description.txt",
    )

    @model_validator(mode="after")
    def need_input(self) -> "CVTailorFilesRequest":
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


# ---- Discriminated-union invoke models (server-style, used by /api/v1/invoke) ----

class EchoInvoke(BaseModel):
    agent: Literal["echo"] = "echo"
    text: str = Field(default="", description="Text to echo back")


class SummarizerInvoke(BaseModel):
    agent: Literal["summarizer"] = "summarizer"
    file_path: str = Field(..., description="e.g. samples/job_description.txt")


class CVTailorInvoke(BaseModel):
    agent: Literal["cv_tailor"] = "cv_tailor"
    cv_path: str = Field(..., description="Path to CV PDF")
    cover_letter_path: str = Field(..., description="Path to cover letter PDF")
    job_desc_path: str = Field(..., description="Path to job description text file")
    output_dir: str = Field(default="output", description="Output directory")
    photo_path: str | None = Field(default=None, description="Optional photo for CV PDF/DOCX")


class JobSearchInvoke(BaseModel):
    agent: Literal["job_search"] = "job_search"
    query: str = Field(..., description="Target role or job-search goal")
    location: str | None = Field(default=None, description="Optional region or city")


InvokeRequest = Annotated[
    Union[EchoInvoke, SummarizerInvoke, CVTailorInvoke, JobSearchInvoke],
    Field(discriminator="agent"),
]


# ---- Shared response models ----

class AgentResponse(BaseModel):
    agent: str
    result: str


InvokeResponse = AgentResponse


class AgentInfo(BaseModel):
    id: str
    title: str
    description: str
