"""Job search assistant agent — strategy and keywords (no external job APIs)."""

from typing import Optional

from agents.base import BaseAgent, AgentConfig, load_prompt
from settings import Settings


class JobSearchAgent(BaseAgent):
    """Helps with job search strategy, keywords, and next steps."""

    def __init__(self, settings: Optional[Settings] = None):
        config = AgentConfig(
            name="job_search",
            system_prompt=load_prompt("job_search"),
            max_tokens=2048,
        )
        super().__init__(config, settings)

    def get_tools(self) -> list:
        return []

    def search(self, query: str, location: Optional[str] = None) -> str:
        """Return job-search guidance for the user's goal."""
        loc = f"\nPreferred location or region: {location}" if location else ""
        prompt = f"""The user is looking for work. Their goal or target role:
{query}{loc}

Give focused job-search help (keywords, search tips, and next steps)."""
        return self.run(prompt)
