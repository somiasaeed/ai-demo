"""Path resolution utilities with traversal protection."""

from pathlib import Path

from ai_demo.config import project_root


def resolve_under_root(relative: str | Path) -> Path:
    """Resolve *relative* under the project root.

    Raises ``ValueError`` if the resolved path escapes the root directory.
    """
    root = project_root()
    resolved = (root / relative).resolve()
    resolved.relative_to(root)  # raises ValueError if outside root
    return resolved
