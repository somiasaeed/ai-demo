"""Recipe Creator — generates a recipe from user prompt via LLM."""

from __future__ import annotations

from hub.services.llm import chat_completion

_SYSTEM = """You are a helpful chef. Given ingredients, dietary constraints, or a dish name,
respond with:
- Recipe title
- Servings and prep/cook time (estimate)
- Ingredient list with amounts
- Numbered steps
Keep it practical for home cooking. Use metric units unless the user asks otherwise."""


class RecipeCreatorAgent:
    async def run(self, prompt: str) -> str:
        p = (prompt or "").strip()
        if not p:
            return "Describe what you want to cook, ingredients you have, or dietary needs."
        return await chat_completion(_SYSTEM, p)
