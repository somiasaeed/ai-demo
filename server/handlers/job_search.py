def run_job_search(query: str, location: str | None) -> str:
    from agents.job_search import JobSearchAgent

    agent = JobSearchAgent()
    return agent.search(query=query, location=location)
