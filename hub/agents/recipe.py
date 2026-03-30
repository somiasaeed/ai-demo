"""Recipe Creator — generates a recipe from user prompt via LLM."""

from __future__ import annotations

from hub.core.llm import chat_completion
from hub.core.prompts import load_prompt


class RecipeAgent:
    async def run(self, prompt: str) -> str:
        p = (prompt or "").strip()
        if not p:
            return "Describe what you want to cook, ingredients you have, or dietary needs."
        system = load_prompt("recipe")
        return await chat_completion(system, p)
