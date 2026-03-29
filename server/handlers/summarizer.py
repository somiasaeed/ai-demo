from server.paths import resolve_under_root


def run_summarizer(file_path: str) -> str:
    path = resolve_under_root(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    from agents.summarizer import SummarizerAgent

    agent = SummarizerAgent()
    return agent.summarize(str(path))
