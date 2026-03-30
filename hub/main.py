"""AI Agent Hub — run: `uvicorn hub.main:app --host 127.0.0.1 --port 80`"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from hub.routers import rest_agents, telegram_webhook

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
for _name in (
    "strands",
    "strands.models",
    "strands.models.openai",
    "strands.telemetry",
    "strands.event_loop",
    "LiteLLM",
    "LiteLLM Router",
    "httpx",
    "httpcore",
    "openai",
    "openai._base_client",
):
    logging.getLogger(_name).setLevel(logging.WARNING)


def _filter_reasoning_warning(record: logging.LogRecord) -> bool:
    return "reasoningContent is not supported" not in record.getMessage()


for _name in ("strands.models.openai", "strands.models"):
    logging.getLogger(_name).addFilter(_filter_reasoning_warning)


_STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="AI Agent Hub",
    description="CV Tailor, Weather, Recipe Creator, General agent + Telegram webhook.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rest_agents.router, prefix="/api")
app.include_router(telegram_webhook.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(_STATIC / "index.html")


app.mount(
    "/static",
    StaticFiles(directory=str(_STATIC)),
    name="hub_static",
)
