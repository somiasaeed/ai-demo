"""API security: key verification."""

from fastapi import HTTPException, Request, status

from ai_demo.config import get_settings


def verify_api_key(request: Request) -> None:
    """FastAPI dependency — require X-API-Key header when ``api_key_header`` is configured."""
    settings = get_settings()
    if not settings.api_key_header:
        return
    key = request.headers.get("x-api-key")
    if key != settings.api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
