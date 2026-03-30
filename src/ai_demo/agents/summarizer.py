"""Summarizer Agent: reads a document and produces a structured summary."""

from typing import Optional

from ai_demo.agents.base import BaseAgent, AgentConfig, load_prompt
from ai_demo.config import Settings
from ai_demo.core.document import read_pdf_tool, read_file_tool


class SummarizerAgent(BaseAgent):
    """Agent that summarizes documents (PDF or text)."""

    def __init__(self, settings: Optional[Settings] = None):
        config = AgentConfig(
            name="summarizer",
            system_prompt=load_prompt("summarizer"),
            max_tokens=2048,
        )
        super().__init__(config, settings)

    def get_tools(self) -> list:
        return [read_pdf_tool, read_file_tool]

    def summarize(self, file_path: str) -> str:
        """Summarize a document.

        Args:
            file_path: Path to a PDF or text file.

        Returns:
            Structured summary of the document.
        """
        ext = file_path.rsplit(".", 1)[-1].lower()
        tool_hint = "read_pdf_tool" if ext == "pdf" else "read_file_tool"

        prompt = f"""\
Please summarize this document.

File: {file_path}

Use {tool_hint} to read the file, then produce a structured summary."""

        return self.run(prompt)
