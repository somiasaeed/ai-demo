"""Send messages to Telegram users (Bot API)."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def send_telegram_message(bot_token: str, chat_id: int, text: str) -> None:
    """POST sendMessage. Truncates to Telegram's safe length."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text[:4090]}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, json=payload)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError:
            logger.exception("Telegram sendMessage failed: %s", r.text)
            raise
