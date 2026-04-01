"""Telegram webhook — multi-turn conversation: agent selection then input."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Body, Header, HTTPException, status
from fastapi.responses import JSONResponse

from hub.config import get_settings
from hub.services.telegram_outbound import (
    answer_callback_query,
    register_bot_commands,
    send_telegram_document,
    send_telegram_message,
)
from hub.telegram import dispatch as telegram_dispatch
from hub.services.prayer_scheduler import register_user

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
            {"text": "Prayer Times", "callback_data": "agent:prayer"},
        ],
        [
            {"text": "General Chat", "callback_data": "agent:general"},
        ],
    ]
}

_AGENT_SELECTION_TEXT = "Which agent would you like to use?"


# ---------- background runner ----------

async def _run_agent_background(token: str, chat_id: int, agent_name: str, text: str) -> None:
    # Send "working on it" status
    status_msg = telegram_dispatch.AGENT_STATUS_MESSAGES.get(
        agent_name, "Working on it — please wait..."
    )
    await send_telegram_message(token, chat_id, status_msg)

    try:
        async def _send_progress(cid: int, msg: str) -> None:
            await send_telegram_message(token, cid, msg)

        result, file_paths = await asyncio.wait_for(
            telegram_dispatch.run_telegram_agent(
                agent_name, text, send_fn=_send_progress, chat_id=chat_id
            ),
            timeout=900,  # 15-minute timeout for CV agent (multiple tool calls)
        )

        # Send result text (split if too long)
        try:
            await send_telegram_message(token, chat_id, result)
        except Exception:
            logger.exception("Failed to send result message")
            # Try sending a shorter fallback
            try:
                await send_telegram_message(
                    token, chat_id, f"Done! {len(file_paths)} file(s) generated. Sending files..."
                )
            except Exception:
                logger.exception("Failed to send fallback message")

        # Send generated files as Telegram documents
        sent, failed = 0, 0
        for fpath in file_paths:
            try:
                await send_telegram_document(token, chat_id, fpath)
                sent += 1
            except Exception:
                failed += 1
                logger.exception("Failed to send file via Telegram: %s", fpath)

        if file_paths:
            await send_telegram_message(
                token, chat_id,
                f"Sent {sent} of {len(file_paths)} files." + (f" {failed} failed." if failed else ""),
            )
    except asyncio.TimeoutError:
        logger.error("Agent %s timed out for chat_id=%s", agent_name, chat_id)
        try:
            await send_telegram_message(
                token,
                chat_id,
                "Sorry, the request timed out. Please try again.",
            )
        except Exception:
            logger.exception("Failed to send timeout message to Telegram")
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

    # Always show agent selection keyboard again after completion
    try:
        await send_telegram_message(
            token, chat_id, _AGENT_SELECTION_TEXT,
            reply_markup=_AGENT_SELECTION_KEYBOARD,
        )
    except Exception:
        logger.exception("Failed to send agent selection keyboard")


# ---------- webhook ----------

@router.post("/telegram")
async def telegram_webhook(
    payload: dict = Body(...),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> JSONResponse:
    settings = get_settings()

    # Validate Telegram secret token when configured
    if settings.telegram_webhook_secret:
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram webhook secret",
            )

    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set; webhook accepted but no reply sent")
        return JSONResponse({"ok": True})

    telegram_dispatch._ensure_loaded()
    token = settings.telegram_bot_token

    # --- Handle callback_query (inline button tap) ---
    callback = payload.get("callback_query")
    if callback:
        chat_id = (callback.get("message") or {}).get("chat", {}).get("id")
        callback_id = callback.get("id")
        data = callback.get("data", "")

        if callback_id:
            await answer_callback_query(token, callback_id)

        if data.startswith("agent:") and chat_id:
            agent_name = data.split(":", 1)[1]

            # Special handling for prayer agent: show location options
            if agent_name == "prayer":
                prayer_keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "My Current Location", "callback_data": "prayer:location"},
                            {"text": "Enter a City", "callback_data": "prayer:city"},
                        ]
                    ]
                }
                await send_telegram_message(
                    token, chat_id,
                    "How would you like to get prayer times?",
                    reply_markup=prayer_keyboard,
                )
                return JSONResponse({"ok": True})

            if agent_name in telegram_dispatch.KNOWN_AGENTS:
                _set_state(chat_id, f"awaiting_input:{agent_name}")
                prompt = telegram_dispatch.AGENT_INPUT_PROMPTS.get(agent_name, "Please enter your input:")
                await send_telegram_message(token, chat_id, prompt)
            else:
                await send_telegram_message(
                    token, chat_id, "Unknown agent. Please try again."
                )

        # Handle prayer sub-options
        if data.startswith("prayer:") and chat_id:
            prayer_choice = data.split(":", 1)[1]
            if prayer_choice == "location":
                await send_telegram_message(
                    token, chat_id,
                    "Please share your location using the attachment button (paperclip icon). "
                    "You'll get today's prayer times and be registered for daily reminders!",
                )
            elif prayer_choice == "city":
                _set_state(chat_id, "awaiting_input:prayer")
                await send_telegram_message(
                    token, chat_id,
                    "Which city would you like prayer times for? (e.g. Berlin, Istanbul, Karachi)",
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

    # --- Handle location message ---
    location = message.get("location")
    if location:
        lat = location.get("latitude")
        lng = location.get("longitude")
        if lat is not None and lng is not None:
            from hub.services.prayer_scheduler import register_user
            register_user(chat_id, lat, lng)

            from hub.agents.prayer import PrayerAgent
            agent = PrayerAgent()
            try:
                result = await agent.run(lat=lat, lng=lng)
            except Exception:
                logger.exception("Prayer agent failed for location")
                result = "Could not fetch prayer times. Please try again."
            await send_telegram_message(
                token, chat_id, result
            )
            await send_telegram_message(
                token, chat_id,
                "You are now registered for daily prayer reminders! "
                "You will receive a notification at each prayer time.",
            )
        return JSONResponse({"ok": True})

    # Deduplicate by message_id
    message_id = message.get("message_id")
    if message_id is not None:
        if message_id in _processed_message_ids:
            logger.debug("Skipping duplicate message_id=%s", message_id)
            return JSONResponse({"ok": True})
        _processed_message_ids.add(message_id)

    if not text or text in ("/start", "/help"):
        await send_telegram_message(token, chat_id, telegram_dispatch.TELEGRAM_HELP)
        return JSONResponse({"ok": True})

    # Check conversation state
    state = _get_state(chat_id)

    if state.startswith("awaiting_input:"):
        agent_name = state.split(":", 1)[1]
        _set_state(chat_id, "idle")
        asyncio.create_task(
            _run_agent_background(token, chat_id, agent_name, text)
        )
    else:
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
