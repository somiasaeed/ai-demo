"""Run API server: `uv run python -m server.run` from repo root."""

import uvicorn


def main() -> None:
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["server", "agents", "tools", "prompts"],
    )


if __name__ == "__main__":
    main()
