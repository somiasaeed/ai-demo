"""Telegram webhook — multi-turn conversation: agent selection then input."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Body, Header, HTTPException, status
from fastapi.responses import JSONResponse

from ai_demo.config import get_settings
from ai_demo.services.telegram_outbound import (
    answer_callback_query,
    register_bot_commands,
    send_telegram_message,
)
from ai_demo.telegram.dispatch import (
    AGENT_INPUT_PROMPTS,
    KNOWN_AGENTS,
    TELEGRAM_HELP,
    run_telegram_agent,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["telegram"])

# Deduplicate retries and track conversation state per chat.
_processed_message_ids: set[int] = set()
_user_states: dict[int, str] = {}  # chat_id -> "idle" | "awaiting_input:<agent>"


# ---------- state helpers ----------


def _get_state(chat_id: int) -> str:
    return _user_states.get(chat_id, "idle")


def _set_state(chat_id: int, state: str) -> None:
    if state == "idle":
        _user_states.pop(chat_id, None)
    else:
        _user_states[chat_id] = state


# ---------- inline keyboard for agent selection ----------

_AGENT_SELECTION_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "CV Tailor", "callback_data": "agent:cv"},
            {"text": "Weather", "callback_data": "agent:weather"},
        ],
        [
            {"text": "Recipe", "callback_data": "agent:recipe"},
            {"text": "General Chat", "callback_data": "agent:general"},
        ],
    ]
}

_AGENT_SELECTION_TEXT = "Which agent would you like to use?"


# ---------- background runner ----------


async def _run_agent_background(token: str, chat_id: int, agent_name: str, text: str) -> None:
    """Run the agent in the background and send the result back to Telegram."""
    try:
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


# ---------- webhook ----------


@router.post("/telegram")
async def telegram_webhook(
    payload: dict = Body(...),
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
) -> JSONResponse:
    settings = get_settings()

    # Webhook secret verification (from server/)
    if (
        settings.telegram_webhook_secret
        and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret",
        )

    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set; webhook accepted but no reply sent")
        return JSONResponse({"ok": True})

    token = settings.telegram_bot_token

    # --- Handle callback_query (inline button tap) ---
    callback = payload.get("callback_query")
    if callback:
        chat_id = (callback.get("message") or {}).get("chat", {}).get("id")
        callback_id = callback.get("id")
        data = callback.get("data", "")

        # Acknowledge the button tap immediately
        if callback_id:
            await answer_callback_query(token, callback_id)

        if data.startswith("agent:") and chat_id:
            agent_name = data.split(":", 1)[1]
            if agent_name in KNOWN_AGENTS:
                _set_state(chat_id, f"awaiting_input:{agent_name}")
                prompt = AGENT_INPUT_PROMPTS.get(agent_name, "Please enter your input:")
                await send_telegram_message(token, chat_id, prompt)
            else:
                await send_telegram_message(
                    token, chat_id, "Unknown agent. Please try again."
                )
        return JSONResponse({"ok": True})

    # --- Handle regular message ---
    message = payload.get("message") or payload.get("edited_message")
    if not message:
        return JSONResponse({"ok": True})

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if chat_id is None:
        return JSONResponse({"ok": True})

    # Deduplicate by message_id
    message_id = message.get("message_id")
    if message_id is not None:
        if message_id in _processed_message_ids:
            logger.debug("Skipping duplicate message_id=%s", message_id)
            return JSONResponse({"ok": True})
        _processed_message_ids.add(message_id)

    if not text or text in ("/start", "/help"):
        await send_telegram_message(token, chat_id, TELEGRAM_HELP)
        return JSONResponse({"ok": True})

    # Check conversation state
    state = _get_state(chat_id)

    if state.startswith("awaiting_input:"):
        # User already selected an agent — run it with their input
        agent_name = state.split(":", 1)[1]
        _set_state(chat_id, "idle")
        asyncio.create_task(
            _run_agent_background(token, chat_id, agent_name, text)
        )
    else:
        # User is idle — show agent selection keyboard
        await send_telegram_message(
            token, chat_id, _AGENT_SELECTION_TEXT,
            reply_markup=_AGENT_SELECTION_KEYBOARD,
        )

    return JSONResponse({"ok": True})


# ---------- register commands on startup ----------


@router.on_event("startup")
async def _on_startup() -> None:
    settings = get_settings()
    if settings.telegram_bot_token:
        await register_bot_commands(settings.telegram_bot_token)
