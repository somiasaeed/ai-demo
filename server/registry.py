"""Single place to register agents for API, Swagger, dashboard, and Telegram.

To add a new agent:
1. Add a Pydantic model in `server/schemas.py` (with discriminator `agent`).
2. Add `InvokeRequest` union member.
3. Implement `server/handlers/your_agent.py` with a sync `run_*` function.
4. Append `AGENT_REGISTRY` below and handle the new type in `dispatch_invoke`.
"""

from server.handlers.cv_tailorer import run_cv_tailorer
from server.handlers.echo import run_echo
from server.handlers.job_search import run_job_search
from server.handlers.summarizer import run_summarizer
from server.schemas import (
    AgentInfo,
    CVTailorerInvoke,
    EchoInvoke,
    InvokeRequest,
    JobSearchInvoke,
    SummarizerInvoke,
)

AGENT_REGISTRY: list[AgentInfo] = [
    AgentInfo(
        id="echo",
        title="Echo",
        description="Returns your text — no LLM. Use to verify routing.",
    ),
    AgentInfo(
        id="summarizer",
        title="Document summarizer",
        description="Summarizes a PDF or text file (path relative to project root).",
    ),
    AgentInfo(
        id="cv_tailorer",
        title="CV & cover letter tailorer",
        description="Tailors CV and cover letter to a job description; writes to output_dir.",
    ),
    AgentInfo(
        id="job_search",
        title="Job search assistant",
        description="Job search strategy, keywords, and next steps from your goal text.",
    ),
]


def list_agent_ids() -> set[str]:
    return {a.id for a in AGENT_REGISTRY}


def dispatch_invoke(body: InvokeRequest) -> str:
    match body:
        case EchoInvoke(text=t):
            return run_echo(t)
        case SummarizerInvoke(file_path=fp):
            return run_summarizer(fp)
        case CVTailorerInvoke(
            cv_path=cv,
            cover_letter_path=cl,
            job_desc_path=job,
            output_dir=out,
            photo_path=ph,
        ):
            return run_cv_tailorer(cv, cl, job, out, ph)
        case JobSearchInvoke(query=q, location=loc):
            return run_job_search(q, loc)
        case _:
            raise ValueError(f"Unhandled agent payload: {type(body)}")
