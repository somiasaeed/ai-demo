from server.paths import resolve_under_root


def run_cv_tailorer(
    cv_path: str,
    cover_letter_path: str,
    job_desc_path: str,
    output_dir: str,
    photo_path: str | None,
) -> str:
    cv = resolve_under_root(cv_path)
    cl = resolve_under_root(cover_letter_path)
    job = resolve_under_root(job_desc_path)
    for p, label in [(cv, "cv_path"), (cl, "cover_letter_path"), (job, "job_desc_path")]:
        if not p.is_file():
            raise FileNotFoundError(f"{label}: file not found: {p}")
    out = resolve_under_root(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    photo = None
    if photo_path:
        pr = resolve_under_root(photo_path)
        if not pr.is_file():
            raise FileNotFoundError(f"photo_path: file not found: {pr}")
        photo = str(pr)

    from agents.cv_tailorer import CVTailorerAgent

    agent = CVTailorerAgent()
    return agent.tailor(
        cv_path=str(cv),
        cover_letter_path=str(cl),
        job_desc_path=str(job),
        output_dir=str(out),
        photo_path=photo,
    )
