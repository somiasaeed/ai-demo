"""Load prompt templates from hub/prompts/*.txt files."""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt text file from hub/prompts/{name}.txt.

    Raises FileNotFoundError if the file doesn't exist.
    """
    path = _PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        available = sorted(p.stem for p in _PROMPTS_DIR.glob("*.txt"))
        raise FileNotFoundError(f"Prompt not found: {path}\nAvailable: {available}")
    return path.read_text(encoding="utf-8").strip()
