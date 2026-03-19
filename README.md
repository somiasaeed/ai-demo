# AI Agent Demo

Minimal example of an AI agent workflow using [Strands Agents](https://github.com/strands-agents/strands-agents-python) with any OpenAI-compatible API.

## Project Structure

```
ai-demo/
├── main.py              # CLI with subcommands (one per agent)
├── settings.py          # Pydantic settings from .env
├── agents/
│   ├── base.py          # BaseAgent + prompt loader + callback handler
│   ├── cv_tailorer.py   # CV tailoring agent
│   └── summarizer.py    # Document summarizer agent
├── tools/
│   └── document.py      # @tool functions: read_pdf, read_file, write_file
├── prompts/
│   ├── cv_tailorer.txt  # System prompt for CV tailorer
│   └── summarizer.txt   # System prompt for summarizer
├── samples/
│   ├── cv.pdf
│   ├── cover_letter.pdf
│   └── job_description.txt
├── photos/              # Put your CV photo here (e.g. photo.jpg)
├── pyproject.toml
└── .env.example
```

## Key Patterns

1. **Settings** (`settings.py`) — Pydantic `BaseSettings` loads `OPENAI_*` config from `.env`
2. **Base Agent** (`agents/base.py`) — Abstract class wiring Strands Agent + LiteLLM, with reasoning model detection and activity logging
3. **Prompts** (`prompts/*.txt`) — System prompts as plain text files, loaded by `load_prompt("name")`. Never hardcoded in Python
4. **Tools** (`tools/document.py`) — `@tool`-decorated functions the agent calls autonomously
5. **Concrete Agents** (`agents/*.py`) — Subclass with `get_tools()` and a convenience method
6. **CLI Subcommands** (`main.py`) — Each agent gets its own subcommand

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Configure your LLM API
cp .env.example .env
# Edit .env with your API key

# 3. Run an agent
uv run main.py cvtailor --cv samples/cv.pdf --cover-letter samples/cover_letter.pdf --job-desc samples/job_description.txt

# Optional: add a photo to the CV (placed at top right of first page)
# Put your photo in the photos/ folder, then:
uv run main.py cvtailor --cv samples/cv.pdf --cover-letter samples/cover_letter.pdf --job-desc samples/job_description.txt --photo photos/photo.jpg

# Or summarize a document
uv run main.py summarize --file samples/cv.pdf
```

## Example Output

```
==================================================
  CV & Cover Letter Tailorer
==================================================
  CV:           samples/cv.pdf
  Cover Letter: samples/cover_letter.pdf
  Job Desc:     samples/job_description.txt
  Output:       output/ (v1)
  Model:        glm-5 (reasoning)
==================================================

Agent workflow:
  [  0.0s] Thinking...
  [  2.1s] Step 1: Reading PDF
           -> samples/cv.pdf
  [  3.4s] Step 2: Reading PDF
           -> samples/cover_letter.pdf
  [  4.2s] Step 3: Reading file
           -> samples/job_description.txt
  [  8.7s] Step 4: Writing file
           -> output/tailored_cv_v1.md
  [ 12.3s] Step 5: Writing file
           -> output/tailored_cover_letter_v1.md
  [ 14.1s] Done (5 tool calls)

--------------------------------------------------
Summary of changes:
--------------------------------------------------
...

Output saved to output/ (v1):
  tailored_cv_v1.md  + .pdf
  tailored_cover_letter_v1.md  + .pdf

Completed in 14.1s
```

## Versioned Output

Each run auto-increments the version number. Previous outputs are preserved:

```
output/
├── tailored_cv_v1.md
├── tailored_cv_v1.pdf
├── tailored_cover_letter_v1.md
├── tailored_cover_letter_v1.pdf
├── tailored_cv_v2.md          # second run
├── tailored_cv_v2.pdf
└── ...
```

## Using a Different LLM

Any OpenAI-compatible API works. Edit `.env`:

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# Anthropic (via LiteLLM)
OPENAI_API_KEY=sk-ant-...
OPENAI_BASE_URL=https://api.anthropic.com
OPENAI_MODEL=claude-sonnet-4-20250514

# Local (Ollama)
OPENAI_API_KEY=unused
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=llama3.1
```

Reasoning models (o1, o3, DeepSeek-R1, GLM, QwQ) are auto-detected — temperature is dropped and `max_completion_tokens` is used instead.

---

## Adding a New Agent

Follow these 3 steps:

### Step 1: Create the prompt (`prompts/my_agent.txt`)

```text
You are an expert at X.

## Workflow
1. Use tool_a to do something
2. Use tool_b to do something else
3. Produce the result

## Rules
- Rule one
- Rule two
```

### Step 2: Create the agent (`agents/my_agent.py`)

```python
from typing import Optional

from agents.base import BaseAgent, AgentConfig, load_prompt
from settings import Settings
from tools.document import read_file_tool, write_file_tool  # pick tools you need


class MyAgent(BaseAgent):
    def __init__(self, settings: Optional[Settings] = None):
        config = AgentConfig(
            name="my_agent",
            system_prompt=load_prompt("my_agent"),  # loads prompts/my_agent.txt
            max_tokens=2048,
        )
        super().__init__(config, settings)

    def get_tools(self) -> list:
        """Return the tools this agent can call."""
        return [read_file_tool, write_file_tool]

    def do_work(self, input_path: str) -> str:
        """Convenience method for this agent's task."""
        return self.run(f"Process this file: {input_path}")
```

### Step 3: Add a subcommand in `main.py`

```python
def cmd_myagent(args: argparse.Namespace) -> None:
    from agents.my_agent import MyAgent
    agent = MyAgent()
    result = agent.do_work(args.input)
    print(result)

# In main(), add to subparsers:
my_parser = subparsers.add_parser("myagent", help="Description of what it does")
my_parser.add_argument("--input", required=True, help="Input file")

# And add to commands dict:
commands = {
    "cvtailor": cmd_cvtailor,
    "summarize": cmd_summarize,
    "myagent": cmd_myagent,
}
```

### Adding a New Tool

Tools are just functions decorated with `@tool`. Add to `tools/document.py` or create a new file in `tools/`:

```python
from strands import tool

@tool
def search_web_tool(query: str) -> str:
    """Search the web for information.

    Args:
        query: Search query string.

    Returns:
        Search results as text.
    """
    # your implementation
    return results
```

Then include it in your agent's `get_tools()` list.

### Architecture Overview

```
main.py (CLI)
  └── subcommand selects agent
        └── Agent (agents/*.py)
              ├── system_prompt loaded from prompts/*.txt
              ├── tools from tools/*.py
              └── BaseAgent (agents/base.py)
                    ├── LiteLLM model (any OpenAI-compatible API)
                    ├── Reasoning model auto-detection
                    └── Activity logging via callback handler
```
