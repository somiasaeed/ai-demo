"""Run the full CV tailor pipeline: sample PDFs + job text, optional CV photo."""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
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
    # Prefer the editable cv.md (plain text you can edit); fall back to cv.pdf.
    cv_md = root / "samples" / "cv.md"
    cv_pdf = root / "samples" / "cv.pdf"
    if cv_md.is_file():
        cv = cv_md
        logger.info("Using samples/cv.md as the CV source (editable).")
    elif cv_pdf.is_file():
        logger.info("samples/cv.md not found — using samples/cv.pdf. Add a cv.md to edit details easily.")
        cv = cv_pdf
    else:
        raise FileNotFoundError(
            "Missing samples/cv.md (or samples/cv.pdf) — add your CV."
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

    return cv, cover


def tailor_cv_from_samples_sync(
    job_description: str = "",
    use_samples_job_file: bool = False,
    progress_fn: Callable[[str], None] | None = None,
) -> tuple[int, str]:
    """Run CVTailorAgent on samples/cv.pdf (+ cover PDF or MD) and job description.

    Returns (version_number, agent summary text).
    """
    root = _repo_root()
    cv, cover = _resolve_cv_and_cover(root)
    # Photo is OFF by default (set CV_INCLUDE_PHOTO=true to embed photos/photo.jpg).
    photo = _find_cv_photo(root) if os.environ.get("CV_INCLUDE_PHOTO", "").lower() == "true" else None

    out = root / "output"
    out.mkdir(parents=True, exist_ok=True)

    if use_samples_job_file:
        job_path = root / "samples" / "job_description.txt"
        if not job_path.is_file():
            raise FileNotFoundError(
                f"Missing {job_path.relative_to(root)} — create it or paste a job with \"cv ...\"."
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

    from hub.agents.cv_tailor import CVTailorAgent

    agent = CVTailorAgent()
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
        progress_fn=progress_fn,
    )
    return version, summary.strip()
