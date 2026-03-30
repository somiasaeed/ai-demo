"""Base agent with Strands + LiteLLM for any OpenAI-compatible API."""

import logging
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

import litellm
from pydantic import BaseModel
from strands import Agent
from strands.models.litellm import LiteLLMModel

from ai_demo.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Prompts directory — all system prompts live as .txt files here, not hardcoded in Python.
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a system prompt from the prompts/ directory.

    Args:
        name: Prompt file name without extension (e.g. "cv_tailor" -> prompts/cv_tailor.txt)

    Returns:
        Prompt text content.

    Raises:
        FileNotFoundError: If the prompt file doesn't exist.
    """
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}\nAvailable: {list_prompts()}")
    return path.read_text(encoding="utf-8").strip()


def list_prompts() -> list[str]:
    """List all available prompt names."""
    if not PROMPTS_DIR.exists():
        return []
    return sorted(p.stem for p in PROMPTS_DIR.glob("*.txt"))

# Tell LiteLLM to silently drop unsupported params (e.g. temperature for reasoning models)
# instead of raising errors.
litellm.drop_params = True

# Reasoning models (o1, o3, DeepSeek-R1, GLM with reasoning, QwQ, etc.)
# These models do chain-of-thought internally and don't support temperature.
REASONING_MODEL_PATTERNS = ("o1", "o3", "o4", "r1", "qwq", "glm")


def _is_reasoning_model(model_name: str) -> bool:
    """Check if a model is a reasoning model based on its name."""
    name = model_name.lower()
    return any(p in name for p in REASONING_MODEL_PATTERNS)


class AgentCallbackHandler:
    """Callback handler that logs agent activity to the console.

    Shows: tool calls, reasoning progress, and streaming text.
    Strands calls this with **kwargs for every event during agent execution.
    """

    TOOL_LABELS = {
        "read_pdf_tool": "Reading PDF",
        "read_file_tool": "Reading file",
        "write_file_tool": "Writing file",
    }

    def __init__(self) -> None:
        self.tool_count = 0
        self._current_tool: str | None = None
        self._reasoning_shown = False
        self._responding = False
        self._done_shown = False
        self._start_time = time.time()

    def _elapsed(self) -> str:
        return f"[{time.time() - self._start_time:5.1f}s]"

    def __call__(self, **kwargs: Any) -> None:
        reasoning_text = kwargs.get("reasoningText", "")
        data = kwargs.get("data", "")
        complete = kwargs.get("complete", False)
        event = kwargs.get("event", {})

        # Tool start
        tool_use = event.get("contentBlockStart", {}).get("start", {}).get("toolUse")
        if tool_use:
            self.tool_count += 1
            name = tool_use["name"]
            self._current_tool = name
            label = self.TOOL_LABELS.get(name, name)
            print(f"  {self._elapsed()} Step {self.tool_count}: {label}")

        # Tool input (shows file paths for read/write tools)
        tool_input = event.get("contentBlockDelta", {}).get("delta", {}).get("toolUse", {}).get("input", "")
        if tool_input and self._current_tool:
            if '"file_path"' in tool_input or "file_path" in tool_input:
                import json
                try:
                    parsed = json.loads(tool_input) if tool_input.strip().startswith("{") else {}
                    if fp := parsed.get("file_path"):
                        print(f"           -> {fp}")
                except (json.JSONDecodeError, TypeError):
                    pass

        # Reasoning indicator (show once)
        if reasoning_text and not self._reasoning_shown:
            print(f"  {self._elapsed()} Thinking...")
            self._reasoning_shown = True

        # Text streaming started (show once)
        if data and not self._responding:
            self._responding = True
            print(f"  {self._elapsed()} Generating response...")

        # Final response
        if complete and not self._done_shown:
            self._done_shown = True
            print(f"  {self._elapsed()} Done ({self.tool_count} tool calls)")


class AgentConfig(BaseModel):
    """Configuration for an agent."""

    name: str
    system_prompt: str
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class BaseAgent(ABC):
    """Abstract base agent.

    Subclasses define get_tools() and optionally override run() for custom logic.
    The agent uses Strands with LiteLLM to call any OpenAI-compatible API.

    Automatically detects reasoning models (o1, o3, DeepSeek-R1, GLM, QwQ)
    and adjusts parameters accordingly — no temperature, uses max_completion_tokens.
    """

    def __init__(self, config: AgentConfig, settings: Optional[Settings] = None):
        self.config = config
        self.settings = settings or get_settings()
        self.is_reasoning = _is_reasoning_model(self.settings.openai_model)
        self.model = self._create_model()
        self.agent = Agent(
            model=self.model,
            tools=self.get_tools(),
            system_prompt=config.system_prompt,
            callback_handler=AgentCallbackHandler(),
        )

    def _create_model(self) -> LiteLLMModel:
        params = self.settings.get_model_params()
        if self.config.temperature is not None:
            params["temperature"] = self.config.temperature
        if self.config.max_tokens is not None:
            params["max_tokens"] = self.config.max_tokens

        if self.is_reasoning:
            # Reasoning models don't support temperature — they control it internally.
            # They also use max_completion_tokens instead of max_tokens.
            params.pop("temperature", None)
            max_tok = params.pop("max_tokens", 4096)
            params["max_completion_tokens"] = max_tok
            logger.debug(
                "Reasoning model detected (%s) — dropped temperature, using max_completion_tokens=%d",
                self.settings.openai_model,
                max_tok,
            )

        params["stream"] = True
        return LiteLLMModel(
            client_args=self.settings.get_client_args(),
            model_id=self.settings.get_model_id(),
            params=params,
        )

    @abstractmethod
    def get_tools(self) -> list:
        """Return list of @tool-decorated functions for this agent."""
        ...

    def run(self, prompt: str) -> str:
        """Run the agent and return the text response."""
        response = self.agent(prompt)
        text, reasoning = self._extract_text(response.message)

        # Some reasoning models (GLM, DeepSeek-R1) put the final answer inside
        # reasoning blocks with no separate text block. If text is empty but
        # reasoning exists, use the reasoning as the response.
        if not text.strip() and reasoning.strip():
            logger.debug("No text blocks found — using reasoning output as response")
            text = reasoning

        if not text.strip():
            logger.warning("Agent returned empty response")

        return text

    @staticmethod
    def _extract_text(message: Any) -> tuple[str, str]:
        """Extract text and reasoning from agent response.

        Returns:
            Tuple of (response_text, reasoning_text). Reasoning is the model's
            chain-of-thought — used as fallback if no text blocks are present.
        """
        text_parts: list[str] = []
        reasoning_parts: list[str] = []

        def _process_blocks(content: list) -> None:
            for block in content:
                if isinstance(block, dict):
                    if "reasoningContent" in block:
                        rc = block["reasoningContent"]
                        if isinstance(rc, dict) and "reasoningText" in rc:
                            reasoning_parts.append(rc["reasoningText"].get("text", ""))
                        elif isinstance(rc, dict) and "text" in rc:
                            reasoning_parts.append(rc["text"])
                        continue
                    if block.get("type") == "thinking":
                        reasoning_parts.append(block.get("thinking", block.get("text", "")))
                        continue
                    if "text" in block:
                        text_parts.append(block["text"])
                elif hasattr(block, "text"):
                    text_parts.append(block.text)

        if hasattr(message, "content"):
            content = message.content
            if isinstance(content, list):
                _process_blocks(content)
            elif isinstance(content, str):
                text_parts.append(content)
            else:
                text_parts.append(str(content))
        elif isinstance(message, dict) and "content" in message:
            content = message["content"]
            if isinstance(content, list):
                _process_blocks(content)
            elif isinstance(content, str):
                text_parts.append(content)
            else:
                text_parts.append(str(content))
        else:
            text_parts.append(str(message))

        return "".join(text_parts), "".join(reasoning_parts)
