"""CV Tailor Text — rewrites CV content from plain text (no PDF I/O)."""

from __future__ import annotations

from hub.core.llm import chat_completion
from hub.core.prompts import load_prompt


class CVTailorTextAgent:
    """Tailors CV text to a job description using the configured LLM."""

    def __init__(self):
        self._system = load_prompt("cv_tailor_text")

    async def run(self, cv_text: str, job_description: str) -> str:
        user = f"CV:\n{cv_text}\n\n---\n\nJob description:\n{job_description}"
        return await chat_completion(self._system, user)
