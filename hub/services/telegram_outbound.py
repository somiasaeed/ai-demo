"""Send messages to Telegram users (Bot API)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def send_telegram_message(
    bot_token: str,
    chat_id: int,
    text: str,
    reply_markup: dict[str, Any] | None = None,
) -> None:
    """POST sendMessage. Truncates to Telegram's safe length."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text[:4090]}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, json=payload)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError:
            logger.exception("Telegram sendMessage failed: %s", r.text)
            raise


async def send_telegram_document(
    bot_token: str,
    chat_id: int,
    file_path: str,
    caption: str = "",
) -> None:
    """POST sendDocument to upload a file to a Telegram chat."""
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    from pathlib import Path

    p = Path(file_path)
    if not p.is_file():
        logger.warning("File not found for Telegram upload: %s", file_path)
        return
    async with httpx.AsyncClient(timeout=60.0) as client:
        with open(file_path, "rb") as f:
            files = {"document": (p.name, f)}
            payload: dict[str, Any] = {"chat_id": chat_id}
            if caption:
                payload["caption"] = caption[:1024]
            r = await client.post(url, data=payload, files=files)
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError:
                logger.exception("Telegram sendDocument failed: %s", r.text)


async def answer_callback_query(bot_token: str, callback_query_id: str, text: str = "") -> None:
    """Acknowledge a callback query (button tap) so the loading spinner stops."""
    url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, json=payload)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError:
            logger.exception("Telegram answerCallbackQuery failed: %s", r.text)


async def register_bot_commands(bot_token: str) -> None:
    """Register the bot's slash-command menu in Telegram."""
    commands = [
        {"command": "cv", "description": "Tailor your CV + cover letter for a job"},
        {"command": "cvfile", "description": "Tailor CV using samples/job_description.txt"},
        {"command": "weather", "description": "Get weather for a city"},
        {"command": "recipe", "description": "Create a recipe from a prompt"},
        {"command": "prayer", "description": "Get prayer times + Tahajjud for your location"},
        {"command": "jobs", "description": "Search jobs (Germany) + tailor CV; subscribe to alerts"},
        {"command": "help", "description": "Show available agents and commands"},
    ]
    url = f"https://api.telegram.org/bot{bot_token}/setMyCommands"
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, json={"commands": commands})
        try:
            r.raise_for_status()
            logger.info("Telegram bot commands registered")
        except httpx.HTTPStatusError:
            logger.exception("Failed to register bot commands: %s", r.text)
