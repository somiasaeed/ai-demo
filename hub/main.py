"""AI Agent Hub — run: `uvicorn hub.main:app --host 127.0.0.1 --port 80`"""

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles

from hub.config import get_settings
from hub.core.security import create_access_token, verify_password
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

# ── Conditionally disable /docs and /redoc based on PRODUCTION flag ──────────
_settings = get_settings()

app = FastAPI(
    title="AI Agent Hub",
    description="CV Tailor, Weather, Recipe Creator, General agent + Telegram webhook.",
    version="1.0.0",
    docs_url=None if _settings.production else "/docs",
    redoc_url=None if _settings.production else "/redoc",
    openapi_url=None if _settings.production else "/openapi.json",
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


# ── Auth endpoints ───────────────────────────────────────────────────────────


@app.post("/auth/login")
async def login(form: OAuth2PasswordRequestForm = Depends()) -> dict:
    """OAuth2-compatible login. Returns a JWT access token."""
    settings = get_settings()
    if form.username != settings.admin_username or not verify_password(
        form.password, settings.admin_password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=form.username, secret=settings.jwt_secret)
    return {"access_token": token, "token_type": "bearer"}


# ── Public routes ────────────────────────────────────────────────────────────


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
