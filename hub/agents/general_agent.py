"""Default conversational agent for Telegram when the message is not routed to weather."""

from __future__ import annotations

from hub.services.llm import chat_completion

_SYSTEM = """You are a concise, friendly assistant in a Telegram chat.
Answer helpfully in plain text (no markdown tables). Keep messages reasonably short unless the user asks for detail."""


class GeneralAgent:
    async def run(self, message: str) -> str:
        m = (message or "").strip()
        if not m:
            return "Hi! Ask me anything, or say “weather” plus a city to get a forecast."
        return await chat_completion(_SYSTEM, m)
