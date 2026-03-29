"""Resolve user-supplied paths under the project root (no path traversal)."""

from pathlib import Path

from server.config import project_root


def resolve_under_root(relative: str) -> Path:
    root = project_root().resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise ValueError("Path must stay under project root") from e
    return candidate
