"""JWT + OAuth2 security — admin-only access for the Agent Hub.

This module is self-contained: no other hub module imports it at import-time,
so circular-dependency risk is zero.  All secrets come from hub.config.Settings.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# ── constants ────────────────────────────────────────────────────────────────

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── password hashing (bcrypt) ────────────────────────────────────────────────


def hash_password(password: str) -> str:
    import bcrypt

    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    import bcrypt

    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT helpers ──────────────────────────────────────────────────────────────

def create_access_token(subject: str, secret: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": subject, "exp": expire, "iat": datetime.now(UTC), "jti": secrets.token_hex(8)}
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> dict:
    """Return decoded payload or raise HTTPException 401."""
    try:
        return jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ── FastAPI dependency — inject into any route ───────────────────────────────

def require_admin(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependency that validates the JWT and returns the decoded payload.

    Usage::

        @router.post("/agents/...")
        async def my_route(_: dict = Depends(require_admin)):
            ...
    """
    # Import here to avoid circular imports at module level
    from hub.config import get_settings

    settings = get_settings()
    payload = decode_access_token(token, settings.jwt_secret)

    if payload.get("sub") != settings.admin_username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )
    return payload


# ── CLI: generate credentials for .env ──────────────────────────────────────

if __name__ == "__main__":
    import getpass
    import sys

    print("=== AI Agent Hub — Credential Generator ===\n")

    jwt_secret = secrets.token_urlsafe(32)
    print(f"JWT_SECRET={jwt_secret}\n")

    username = input("Admin username [admin]: ").strip() or "admin"
    password = getpass.getpass("Admin password: ")
    if not password:
        print("Password cannot be empty.", file=sys.stderr)
        sys.exit(1)

    pw_hash = hash_password(password)
    print(f"\nADMIN_USERNAME={username}")
    print(f"ADMIN_PASSWORD_HASH={pw_hash}")
    print("\nCopy these values into your .env file.")
