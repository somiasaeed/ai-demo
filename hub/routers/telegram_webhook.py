"""Telegram webhook — delegates to hub.telegram_dispatch (multi-agent registry)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from hub.config import get_hub_settings
from hub.services.telegram_outbound import send_telegram_message
from hub.telegram_dispatch import TELEGRAM_HELP, detect_telegram_agent, run_telegram_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["telegram"])


@router.post("/telegram")
async def telegram_webhook(payload: dict = Body(...)) -> JSONResponse:
    hub = get_hub_settings()
    if not hub.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set; webhook accepted but no reply sent")
        return JSONResponse({"ok": True})

    message = payload.get("message") or payload.get("edited_message")
    if not message:
        return JSONResponse({"ok": True})

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if chat_id is None:
        return JSONResponse({"ok": True})

    token = hub.telegram_bot_token

    if not text or text in ("/start", "/help"):
        await send_telegram_message(token, chat_id, TELEGRAM_HELP)
        return JSONResponse({"ok": True})

    try:
        agent_name = detect_telegram_agent(text)
        result = await run_telegram_agent(agent_name, text)
        await send_telegram_message(token, chat_id, result)
    except Exception:
        logger.exception("Telegram pipeline failed")
        try:
            await send_telegram_message(
                token,
                chat_id,
                "Sorry, something went wrong processing your message. Try again later.",
            )
        except Exception:
            logger.exception("Failed to send error message to Telegram")

    return JSONResponse({"ok": True})
