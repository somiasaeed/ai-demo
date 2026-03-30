"""Echo agent — returns input text (no LLM). Used to verify routing."""


def run_echo(text: str) -> str:
    return text if text else "(empty)"
