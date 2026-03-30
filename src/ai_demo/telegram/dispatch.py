"""Telegram multi-agent router: keyword → async handler."""

from __future__ import annotations

import asyncio
import logging
import re

from ai_demo.agents.general import GeneralAgent
from ai_demo.agents.recipe import RecipeCreatorAgent
from ai_demo.agents.weather import WeatherAgent
from ai_demo.services.cv_pipeline import tailor_cv_from_samples_sync

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers: slash-command parsing and keyword stripping
# ---------------------------------------------------------------------------

def _strip_keyword(text: str, *keywords: str) -> str:
    """Remove the matched keyword (or /command form) and return the rest."""
    s = text.strip()

    # First try to match /keyword or /keyword@BotName with optional space
    for kw in keywords:
        m = re.match(rf"^/{re.escape(kw)}(?:@\S+)?\s*(.*)", s, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip(" ,.?!")

    # Then try to match /keyword without space (e.g. /weatherberlin → berlin)
    for kw in keywords:
        m = re.match(rf"^/{re.escape(kw)}(.+)", s, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip(" ,.?!")

    # Fallback: strip bare keyword with word boundaries
    for kw in keywords:
        s = re.sub(rf"\b{re.escape(kw)}\b", " ", s, flags=re.IGNORECASE)
    return re.sub(r"[\s,]+", " ", s).strip(" ,.?!")

def _slash_arg(text: str, command: str) -> str | None:
    """Match /cmd or /cmd@BotName and return text after the command (multi-line safe)."""
    m = re.match(
        rf"^/{command}(?:@\S+)?\s*(.*)",
        text.strip(),
        re.IGNORECASE | re.DOTALL,
    )
    return None if not m else m.group(1).strip()


def _extract_after_cv_trigger(text: str) -> str:
    s = text.strip()
    for cmd in ("cvfile", "cv", "job", "jd"):
        arg = _slash_arg(s, cmd)
        if arg is not None:
            if cmd == "cvfile":
                return arg if arg else "file"
            return arg
    s = re.sub(
        r"^tailor\s+my\s+(cv|resume)\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"^tailor\s+(cv|resume)\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"^(cv|resume)\s+", "", s, flags=re.IGNORECASE)
    return s.strip()


def _build_job_file_content(body: str) -> str:
    body = body.strip()
    if "|" not in body:
        return body
    left, right = body.split("|", 1)
    left, right = left.strip(), right.strip()
    if not right:
        return left
    if not left:
        return right
    return f"Notes from you:\n{left}\n\n---\n\nJob description:\n{right}"


def _cv_uses_sample_job_file(body: str) -> bool:
    b = body.strip().lower()
    if not b:
        return False
    if b in ("file", "default", "samples", "sample"):
        return True
    if b.startswith("file ") and len(b) < 80:
        return True
    return False


# ---------------------------------------------------------------------------
# Agent detection
# ---------------------------------------------------------------------------

# Order: first regex match wins (weather before cv if both — unlikely)
# Slash-command patterns use (?!file) guard so /cvfile isn't claimed by /cv.
TELEGRAM_AGENT_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("weather", re.compile(r"/weather|\bweather\b", re.IGNORECASE)),
    (
        "cv",
        re.compile(
            r"^/cv(?!file)|^/cvfile|^/job|^/jd|"
            r"\bcv\b|tailor\s*(my\s*)?(cv|resume)\b",
            re.IGNORECASE,
        ),
    ),
    ("recipe", re.compile(r"/recipe|\brecipe\b|\bcook\b", re.IGNORECASE)),
]


def detect_telegram_agent(text: str) -> str:
    for name, pat in TELEGRAM_AGENT_RULES:
        if pat.search(text):
            return name
    return "general"


# ---------------------------------------------------------------------------
# Agent runners
# ---------------------------------------------------------------------------

async def run_telegram_agent(name: str, text: str) -> str:
    if name == "weather":
        query = _strip_keyword(text, "weather") or text
        return await WeatherAgent().run(query, plain_text=True)

    if name == "cv":
        return await _run_cv_telegram(text)

    if name == "recipe":
        prompt = _strip_keyword(text, "recipe", "cook")
        return await RecipeCreatorAgent().run(prompt or text)

    return await GeneralAgent().run(text)


async def _run_cv_telegram(text: str) -> str:
    body = _extract_after_cv_trigger(text)
    if not body:
        return (
            'Send your job description after "cv", for example:\n'
            "cv We are hiring a Senior Python engineer...\n\n"
            "Or use the file on disk:\n"
            "cv file\n"
            "(uses samples/job_description.txt)\n\n"
            "Sources: samples/cv.pdf + cover_letter.pdf (or .md) → output/\n"
            "Photo: photos/photo.jpg or CV_PHOTO_PATH in .env"
        )

    if _cv_uses_sample_job_file(body):
        try:
            version, summary = await asyncio.to_thread(
                tailor_cv_from_samples_sync,
                "",
                True,
            )
        except FileNotFoundError as e:
            return f"Could not run CV tailor: {e}"
        except Exception:
            logger.exception("CV tailor (sample job file) failed")
            raise
    else:
        job_file_text = _build_job_file_content(body)
        try:
            version, summary = await asyncio.to_thread(
                tailor_cv_from_samples_sync,
                job_file_text,
                False,
            )
        except FileNotFoundError as e:
            return f"Could not run CV tailor: {e}"
        except Exception:
            logger.exception("CV tailor failed")
            raise

    head = (
        f"Your CV and cover letter have been tailored (version v{version}).\n"
        f"Saved under output/:\n"
        f"• tailored_cv_v{version}.md / .pdf / .docx\n"
        f"• tailored_cover_letter_v{version}.md / .pdf / .docx\n"
        f"(plus German *_de_* versions)\n\n"
        f"Summary:\n"
    )
    rest = summary[: (4090 - len(head) - 20)]
    if len(summary) > len(rest):
        rest += "\n…(truncated)"
    return head + rest


TELEGRAM_HELP = (
    "Welcome! Send any message to get started.\n\n"
    "I'll ask which agent you want to use:\n"
    "  CV Tailor  - tailor your CV + cover letter for a job\n"
    "  Weather    - get weather for a city\n"
    "  Recipe     - create a recipe from a prompt\n"
    "  General    - general chat\n\n"
    "Commands:\n"
    "  /start, /help  -- show this message"
)

KNOWN_AGENTS: list[str] = ["cv", "weather", "recipe", "general"]

AGENT_INPUT_PROMPTS: dict[str, str] = {
    "cv": (
        "Please paste the job description for CV tailoring.\n\n"
        "You can also type `file` to use samples/job_description.txt."
    ),
    "weather": "Which city would you like the weather for?",
    "recipe": "What would you like a recipe for?",
    "general": "What would you like to ask?",
}
