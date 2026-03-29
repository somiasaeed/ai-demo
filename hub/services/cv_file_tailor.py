"""Run the full Strands CV tailorer using samples + job text or samples/job_description.txt."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def tailor_cv_from_samples_sync(
    job_description: str = "",
    use_samples_job_file: bool = False,
) -> tuple[int, str]:
    """
    Run CVTailorerAgent on samples/cv.md + samples/cover_letter.md.

    Args:
        job_description: Pasted job text (written to output/telegram_job_*.txt) unless
            use_samples_job_file is True.
        use_samples_job_file: If True, use samples/job_description.txt instead.

    Returns:
        (version_number, agent summary text)
    """
    root = _repo_root()
    cv = root / "samples" / "cv.md"
    cl = root / "samples" / "cover_letter.md"
    if not cv.is_file():
        raise FileNotFoundError(f"Missing {cv.relative_to(root)} — add your CV there.")
    if not cl.is_file():
        raise FileNotFoundError(f"Missing {cl.relative_to(root)} — add your cover letter there.")

    out = root / "output"
    out.mkdir(parents=True, exist_ok=True)

    if use_samples_job_file:
        job_path = root / "samples" / "job_description.txt"
        if not job_path.is_file():
            raise FileNotFoundError(
                f"Missing {job_path.relative_to(root)} — create it or paste a job with “cv …”."
            )
        job_desc_path = str(job_path.resolve())
    else:
        text = (job_description or "").strip()
        if not text:
            raise ValueError("Job description is empty.")
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        job_path = out / f"telegram_job_{ts}.txt"
        job_path.write_text(text, encoding="utf-8")
        job_desc_path = str(job_path.resolve())

    from agents.cv_tailorer import CVTailorerAgent

    agent = CVTailorerAgent()
    version = agent._next_version(str(out))
    logger.info("CV tailor starting v%s (sample_job_file=%s)", version, use_samples_job_file)
    summary = agent.tailor(
        cv_path=str(cv.resolve()),
        cover_letter_path=str(cl.resolve()),
        job_desc_path=job_desc_path,
        output_dir=str(out.resolve()),
        photo_path=None,
    )
    return version, summary.strip()
