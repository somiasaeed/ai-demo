"""Default conversational agent for Telegram."""

from __future__ import annotations

from hub.core.llm import chat_completion
from hub.core.prompts import load_prompt


class GeneralAgent:
    async def run(self, message: str) -> str:
        m = (message or "").strip()
        if not m:
            return "Hi! Ask me anything, or say \"weather\" plus a city to get a forecast."
        system = load_prompt("general")
        return await chat_completion(system, m)
