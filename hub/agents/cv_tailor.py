"""CV Tailor — rewrites CV content for a target role from plain text (no PDF I/O)."""

from __future__ import annotations

from hub.services.llm import chat_completion

_SYSTEM = """You are an expert CV/resume editor. Given the candidate's CV text and a job description,
produce an improved CV in Markdown: clear headings, bullet points, quantified impact where possible,
and alignment with the job description. Keep facts truthful; you may reorder and rephrase.
End with a short "Changes summary" section."""


class CVTailorAgent:
    """Tailors CV text to a job description using the configured LLM."""

    async def run(self, cv_text: str, job_description: str) -> str:
        user = f"CV:\n{cv_text}\n\n---\n\nJob description:\n{job_description}"
        return await chat_completion(_SYSTEM, user)
