"""Telegram multi-agent router: keyword → async handler (single place to extend agents)."""

from __future__ import annotations

import asyncio
import logging
import re

from hub.agents.general_agent import GeneralAgent
from hub.agents.recipe_creator import RecipeCreatorAgent
from hub.agents.weather_agent import WeatherAgent
from hub.services.cv_file_tailor import tailor_cv_from_samples_sync

logger = logging.getLogger(__name__)


def _strip_keyword(text: str, *keywords: str) -> str:
    s = text
    for kw in keywords:
        s = re.sub(rf"\b{re.escape(kw)}\b", " ", s, flags=re.IGNORECASE)
    return re.sub(r"[\s,]+", " ", s).strip(" ,.?!")


def _slash_arg(text: str, command: str) -> str | None:
    """Match /cmd or /cmd@BotName and return text after the command."""
    m = re.match(rf"^/{command}(?:@\S+)?\s*(.*)$", text.strip(), re.IGNORECASE)
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


# Order: first regex match wins (weather before cv if both — unlikely)
TELEGRAM_AGENT_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("weather", re.compile(r"\bweather\b", re.IGNORECASE)),
    (
        "cv",
        re.compile(
            r"^/cv\b|^/cvfile\b|^/job\b|^/jd\b|"
            r"\bcv\b|tailor\s*(my\s*)?(cv|resume)\b",
            re.IGNORECASE,
        ),
    ),
    ("recipe", re.compile(r"\brecipe\b|\bcook\b", re.IGNORECASE)),
]


def detect_telegram_agent(text: str) -> str:
    for name, pat in TELEGRAM_AGENT_RULES:
        if pat.search(text):
            return name
    return "general"


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
            "Send your job description after “cv”, for example:\n"
            "cv We are hiring a Senior Python engineer…\n\n"
            "Or use the file on disk:\n"
            "cv file\n"
            "(uses samples/job_description.txt)\n\n"
            "Sources: samples/cv.md + samples/cover_letter.md → output/"
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
    "Commands:\n"
    "• weather <city>\n"
    "• cv <job description> — tailors samples/cv.md + cover_letter.md → output/\n"
    "• cv file — use samples/job_description.txt as the job posting\n"
    "• cv notes | job description — optional split\n"
    "• /cvfile — same as “cv file”\n"
    "• recipe <prompt>\n"
    "• /help"
)
