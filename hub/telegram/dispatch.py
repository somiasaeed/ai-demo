"""Telegram multi-agent router: keyword -> async handler (single place to extend agents)."""

from __future__ import annotations

import asyncio
import logging
import re
import typing
from pathlib import Path

from hub.agents.general import GeneralAgent
from hub.agents.prayer import PrayerAgent
from hub.agents.recipe import RecipeAgent
from hub.agents.weather import WeatherAgent
from hub.core.prompts import load_prompt
from hub.services.cv_pipeline import tailor_cv_from_samples_sync

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Helpers: slash-command parsing and keyword stripping
# ---------------------------------------------------------------------------

def _strip_keyword(text: str, *keywords: str) -> str:
    """Remove the matched keyword (or /command form) and return the rest."""
    s = text.strip()

    for kw in keywords:
        m = re.match(rf"^/{re.escape(kw)}(?:@\S+)?\s*(.*)", s, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip(" ,.?!")

    for kw in keywords:
        m = re.match(rf"^/{re.escape(kw)}(.+)", s, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip(" ,.?!")

    for kw in keywords:
        s = re.sub(rf"\b{re.escape(kw)}\b", " ", s, flags=re.IGNORECASE)
    return re.sub(r"[\s,]+", " ", s).strip(" ,.?!")


def _slash_arg(text: str, command: str) -> str | None:
    """Match /cmd or /cmd@BotName and return text after the command."""
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
    s = re.sub(r"^tailor\s+my\s+(cv|resume)\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^tailor\s+(cv|resume)\s*", "", s, flags=re.IGNORECASE)
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
    ("prayer", re.compile(r"/prayer|\bprayer\b|\bsalah\b|\bnamaz\b|\btahajjud\b", re.IGNORECASE)),
]


def detect_telegram_agent(text: str) -> str:
    for name, pat in TELEGRAM_AGENT_RULES:
        if pat.search(text):
            return name
    return "general"


# ---------------------------------------------------------------------------
# Agent runners
# ---------------------------------------------------------------------------

async def run_telegram_agent(
    name: str,
    text: str,
    send_fn: typing.Callable[[int, str], typing.Any] | None = None,
    chat_id: int = 0,
) -> tuple[str, list[str]]:
    """Run an agent and return (result_text, list_of_file_paths).

    Non-CV agents return an empty file list.
    """
    if name == "weather":
        query = _strip_keyword(text, "weather") or text
        return await WeatherAgent().run(query, plain_text=True), []

    if name == "cv":
        return await _run_cv_telegram(text, send_fn=send_fn, chat_id=chat_id)

    if name == "recipe":
        prompt = _strip_keyword(text, "recipe", "cook")
        return await RecipeAgent().run(prompt or text), []

    if name == "prayer":
        query = _strip_keyword(text, "prayer", "salah", "namaz") or text
        return await PrayerAgent().run(query), []

    return await GeneralAgent().run(text), []


async def _run_cv_telegram(
    text: str,
    send_fn: typing.Callable[[int, str], typing.Any] | None = None,
    chat_id: int = 0,
) -> tuple[str, list[str]]:
    body = _extract_after_cv_trigger(text)
    if not body:
        return load_prompt("telegram_cv_usage"), []

    # Build a progress callback that sends Telegram updates
    _loop = asyncio.get_event_loop()
    def _progress(msg: str) -> None:
        if send_fn and chat_id:
            try:
                asyncio.run_coroutine_threadsafe(send_fn(chat_id, msg), _loop)
            except Exception:
                pass

    if _cv_uses_sample_job_file(body):
        try:
            version, summary = await asyncio.to_thread(
                tailor_cv_from_samples_sync,
                "",
                True,
                _progress,
            )
        except FileNotFoundError as e:
            return f"Could not run CV tailor: {e}", []
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
                _progress,
            )
        except FileNotFoundError as e:
            return f"Could not run CV tailor: {e}", []
        except Exception:
            logger.exception("CV tailor failed")
            raise

    # Collect generated PDF file paths for sending via Telegram
    out_dir = _repo_root() / "output"
    file_paths: list[str] = []
    for prefix in ("tailored_cv", "tailored_cv_de", "tailored_cover_letter", "tailored_cover_letter_de"):
        candidate = out_dir / f"{prefix}_v{version}.pdf"
        if candidate.is_file():
            file_paths.append(str(candidate))

    head = (
        f"Your CV and cover letter have been tailored (version v{version}).\n\n"
        f"Summary:\n"
    )
    rest = summary[: (4090 - len(head) - 20)]
    if len(summary) > len(rest):
        rest += "\n...(truncated)"
    return head + rest, file_paths


# ---------------------------------------------------------------------------
# Constants loaded from prompt files
# ---------------------------------------------------------------------------

def _get_telegram_help() -> str:
    return load_prompt("telegram_help")


def _load_agent_prompts() -> dict[str, str]:
    """Load input prompts from telegram_agent_<name>.txt files."""
    prompts = {}
    for name in KNOWN_AGENTS:
        try:
            prompts[name] = load_prompt(f"telegram_agent_{name}")
        except FileNotFoundError:
            logger.warning("No prompt file for agent '%s'", name)
            prompts[name] = "Please enter your input:"
    return prompts


def _load_agent_status_messages() -> dict[str, str]:
    """Load working-on-it messages from telegram_status_<name>.txt files."""
    messages = {}
    for name in KNOWN_AGENTS:
        try:
            messages[name] = load_prompt(f"telegram_status_{name}")
        except FileNotFoundError:
            messages[name] = "Working on it — please wait..."
    return messages


# Lazy-loaded constants (populated on first webhook call)
TELEGRAM_HELP = ""
KNOWN_AGENTS: list[str] = ["cv", "weather", "recipe", "prayer", "general"]
AGENT_INPUT_PROMPTS: dict[str, str] = {}
AGENT_STATUS_MESSAGES: dict[str, str] = {}


def _ensure_loaded() -> None:
    global TELEGRAM_HELP, AGENT_INPUT_PROMPTS, AGENT_STATUS_MESSAGES
    if not TELEGRAM_HELP:
        TELEGRAM_HELP = _get_telegram_help()
        AGENT_INPUT_PROMPTS = _load_agent_prompts()
        AGENT_STATUS_MESSAGES = _load_agent_status_messages()
