"""OpenAI-compatible chat completions via raw httpx."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from hub.config import Settings, get_settings

# Models that commonly reject `temperature` on chat completions
_REASONING_HINTS = ("o1", "o3", "o4", "r1", "glm", "qwq")


def _should_omit_temperature(model: str) -> bool:
    m = model.lower()
    return any(h in m for h in _REASONING_HINTS)


def _build_payload(settings: Settings, system: str, user: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": settings.openai_max_tokens,
    }
    if not _should_omit_temperature(settings.openai_model):
        base["temperature"] = settings.openai_temperature
    return base


# Transient network errors worth retrying (cloud/z.ai connection drops, esp. under load).
_RETRYABLE = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ReadError)


async def _post_with_retry(url: str, headers: dict, payload: dict, retries: int = 4) -> dict:
    """POST with exponential backoff on transient connection/read errors."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(url, headers=headers, json=payload)
                r.raise_for_status()
                return r.json()
        except _RETRYABLE as exc:
            last_exc = exc
            if attempt < retries - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
    assert last_exc is not None
    raise last_exc


async def chat_completion(system_prompt: str, user_message: str) -> str:
    """Single-turn chat; returns assistant text or raises on API errors."""
    settings = get_settings()
    url = settings.openai_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = _build_payload(settings, system_prompt, user_message)

    data = await _post_with_retry(url, headers, payload)

    choice = data.get("choices", [{}])[0]
    msg = choice.get("message") or {}
    content = msg.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()

    # Some providers return content as list of parts
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        if parts:
            return "\n".join(parts).strip()

    return json.dumps(data)[:2000]
