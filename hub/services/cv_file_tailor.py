"""Run the full Strands CV tailorer: samples PDFs + job text, optional CV photo."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}
_PHOTO_NAMES = (
    "photo.jpg",
    "photo.jpeg",
    "photo.png",
    "photo.webp",
    "cv_photo.jpg",
    "cv_photo.png",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _find_cv_photo(root: Path) -> str | None:
    """Env CV_PHOTO_PATH, then photos/* or samples/* common names, then first image in photos/."""
    raw = os.environ.get("CV_PHOTO_PATH", "").strip()
    if raw:
        p = Path(raw) if os.path.isabs(raw) else (root / raw)
        if p.is_file():
            return str(p.resolve())
        logger.warning("CV_PHOTO_PATH set but file not found: %s", p)

    for folder in (root / "photos", root / "samples"):
        if not folder.is_dir():
            continue
        for name in _PHOTO_NAMES:
            cand = folder / name
            if cand.is_file():
                logger.info("Using CV photo: %s", cand.relative_to(root))
                return str(cand.resolve())
        for cand in sorted(folder.iterdir()):
            if cand.is_file() and cand.suffix.lower() in _PHOTO_EXT:
                logger.info("Using CV photo: %s", cand.relative_to(root))
                return str(cand.resolve())
    logger.info("No CV photo found (optional). Set CV_PHOTO_PATH or add photos/photo.jpg")
    return None


def _resolve_cv_and_cover(root: Path) -> tuple[Path, Path]:
    """Require samples/cv.pdf (your real content). Cover: PDF preferred, then .md."""
    cv_pdf = root / "samples" / "cv.pdf"
    if not cv_pdf.is_file():
        raise FileNotFoundError(
            "Missing samples/cv.pdf — export YOUR CV as PDF (name, email, LinkedIn, experience). "
            "samples/cv.md is not used anymore so placeholder text (e.g. old template names) "
            "never gets tailored by mistake."
        )

    cl_pdf = root / "samples" / "cover_letter.pdf"
    cl_md = root / "samples" / "cover_letter.md"
    if cl_pdf.is_file():
        cover = cl_pdf
    elif cl_md.is_file():
        logger.warning(
            "samples/cover_letter.pdf not found — using cover_letter.md; replace with your PDF when ready."
        )
        cover = cl_md
    else:
        raise FileNotFoundError(
            "Missing samples/cover_letter.pdf or samples/cover_letter.md — add your cover letter."
        )

    return cv_pdf, cover


def tailor_cv_from_samples_sync(
    job_description: str = "",
    use_samples_job_file: bool = False,
) -> tuple[int, str]:
    """
    Run CVTailorerAgent on samples/cv.pdf (+ cover PDF or MD) and job description.

    Args:
        job_description: Pasted job text (written to output/telegram_job_*.txt) unless
            use_samples_job_file is True.
        use_samples_job_file: If True, use samples/job_description.txt instead.

    Returns:
        (version_number, agent summary text)
    """
    root = _repo_root()
    cv, cover = _resolve_cv_and_cover(root)
    photo = _find_cv_photo(root)

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
    logger.info(
        "CV tailor v%s (cv=%s, cover=%s, photo=%s)",
        version,
        cv.name,
        cover.name,
        photo or "none",
    )
    summary = agent.tailor(
        cv_path=str(cv.resolve()),
        cover_letter_path=str(cover.resolve()),
        job_desc_path=job_desc_path,
        output_dir=str(out.resolve()),
        photo_path=photo,
    )
    return version, summary.strip()
