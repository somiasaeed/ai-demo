"""Telegram webhook: send the same JSON as POST /api/v1/invoke in a chat message."""

import asyncio
import json
import logging

import httpx
from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter

from server.config import get_server_settings
from server.registry import dispatch_invoke, list_agent_ids
from server.schemas import InvokeRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telegram"])

_adapter = TypeAdapter(InvokeRequest)


async def _telegram_send_message(token: str, chat_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text[:4090]}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()


def _help_text() -> str:
    ids = ", ".join(sorted(list_agent_ids()))
    return (
        "Send a JSON object matching /api/v1/invoke (field \"agent\" required).\n\n"
        f"Agents: {ids}\n\n"
        "Examples:\n"
        '{"agent":"echo","text":"hello"}\n'
        '{"agent":"summarizer","file_path":"samples/job_description.txt"}\n'
        '{"agent":"job_search","query":"Python backend remote EU"}\n'
    )


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> JSONResponse:
    settings = get_server_settings()
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot token not configured")

    if settings.telegram_webhook_secret and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")

    try:
        update = await request.json()
    except Exception:
        return JSONResponse(content={"ok": True})

    message = update.get("message") or update.get("edited_message")
    if not message:
        return JSONResponse(content={"ok": True})

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if chat_id is None:
        return JSONResponse(content={"ok": True})

    token = settings.telegram_bot_token

    if text in ("/start", "/help", "/agents"):
        await _telegram_send_message(token, chat_id, _help_text())
        return JSONResponse(content={"ok": True})

    try:
        data = json.loads(text)
        body = _adapter.validate_python(data)
    except Exception as e:
        await _telegram_send_message(
            token,
            chat_id,
            "Invalid JSON. Send /help for examples.\nError: " + str(e)[:500],
        )
        return JSONResponse(content={"ok": True})

    try:
        result = await asyncio.to_thread(dispatch_invoke, body)
    except FileNotFoundError as e:
        await _telegram_send_message(token, chat_id, "Error: " + str(e))
        return JSONResponse(content={"ok": True})
    except Exception as e:
        logger.exception("Telegram agent run failed")
        await _telegram_send_message(token, chat_id, "Error: " + str(e)[:3500])
        return JSONResponse(content={"ok": True})

    await _telegram_send_message(token, chat_id, result)
    return JSONResponse(content={"ok": True})
