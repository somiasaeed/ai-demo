"""FastAPI application: mount under project root (imports `agents`, `settings`)."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from server.config import get_server_settings, project_root
from server.routes.api import router as api_router
from server.routes.telegram import router as telegram_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Demo — multi-agent API",
        description=(
            "Invoke registered agents via REST. Same payloads work from the dashboard or Telegram "
            "(send JSON in chat). See `server/registry.py` to add agents."
        ),
        version="0.1.0",
    )

    s = get_server_settings()
    origins = [o.strip() for o in s.cors_origins.split(",") if o.strip()]
    if not origins:
        origins = ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(telegram_router, prefix="/api/v1")

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/dashboard/")

    front = Path(project_root()) / "frontend"
    if front.is_dir():
        app.mount(
            "/dashboard",
            StaticFiles(directory=str(front), html=True),
            name="dashboard",
        )

    return app


app = create_app()
