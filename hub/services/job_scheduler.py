"""Background job-alert scheduler.

Polls Adzuna every JOB_SEARCH_INTERVAL_MINUTES, dedups against seen jobs, and for
each NEW job sends a Telegram message with the link — auto-generating the EN/DE
CV + cover letter for the newest matches via the existing CV-tailor.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from hub.config import get_settings
from hub.services.cv_pipeline import tailor_cv_from_samples_sync
from hub.services.job_search import search_jobs
from hub.services.telegram_outbound import send_telegram_document, send_telegram_message

logger = logging.getLogger(__name__)

# Persisted on the host via the output/ bind mount → survives rebuilds.
DATA_DIR = Path("output")
SEEN_FILE = DATA_DIR / "seen_jobs.json"
SUBS_FILE = DATA_DIR / "job_subs.json"

_task: asyncio.Task | None = None
_job_subscribers: set[int] = set()


# ── persistence helpers ────────────────────────────────────────────────────
def _load_json(path: Path, default):
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("failed to load %s", path)
    return default


def _save_json(path: Path, data) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        logger.exception("failed to save %s", path)


def register_job_subscriber(chat_id: int) -> None:
    """Subscribe a chat to job alerts (periodic + manual /jobs)."""
    _job_subscribers.add(chat_id)
    _save_json(SUBS_FILE, sorted(_job_subscribers))
    logger.info("Registered chat_id=%s for job alerts", chat_id)


def _load_subscribers() -> None:
    global _job_subscribers
    _job_subscribers = set(_load_json(SUBS_FILE, []))


def get_job_subscribers() -> set[int]:
    return set(_job_subscribers)


# ── core ───────────────────────────────────────────────────────────────────
async def process_new_jobs(chat_id: int | None = None) -> int:
    """Search + notify. If chat_id given, notify only that chat; else all subscribers.

    Returns the number of new jobs found.
    """
    settings = get_settings()
    has_adzuna = bool(settings.adzuna_app_id and settings.adzuna_app_key)
    has_jooble = bool(settings.jooble_api_key)
    if not has_adzuna and not has_jooble:
        logger.info("No job source configured — job search skipped.")
        return 0
    targets = [chat_id] if chat_id is not None else sorted(_job_subscribers)
    if not targets:
        return 0

    jobs = await search_jobs(settings)
    seen = set(_load_json(SEEN_FILE, []))
    new_jobs = [j for j in jobs if j.get("signature") not in seen]
    if not new_jobs:
        return 0

    max_cvs = settings.job_search_max_cvs
    # Process a few jobs per cycle — each gets its link + all 4 PDFs together,
    # then the next job. No flood of link-only messages. Remaining new jobs are
    # NOT marked seen, so they come back next cycle (nothing is missed).
    to_process = new_jobs[:max_cvs]
    for cid in targets:
        for job in to_process:
            try:
                await send_telegram_message(
                    settings.telegram_bot_token,
                    cid,
                    f"🆕 {job['title']}\n{job['company']} — {job['location']}\n{job['url']}\n\n"
                    "Generating your tailored CV + cover letter (EN + DE)…",
                )
                await _generate_and_send_cv(cid, job)
            except Exception:
                logger.exception("Failed to notify job %s", job.get("id"))

    seen.update(j["signature"] for j in to_process if j.get("signature"))
    _save_json(SEEN_FILE, sorted(seen)[-2000:])
    return len(to_process)


async def _generate_and_send_cv(chat_id: int, job: dict) -> None:
    settings = get_settings()
    token = settings.telegram_bot_token
    desc = (job.get("description") or "").strip()
    if not desc:
        await send_telegram_message(
            token, chat_id, "⚠️ This job has no description to tailor to — skipping CV."
        )
        return
    # Truncate very long postings so the prompt fits the model's context window.
    desc = desc[:4000]
    try:
        version, _summary = await asyncio.to_thread(
            tailor_cv_from_samples_sync, desc, False, None
        )
    except Exception as e:
        logger.exception("CV generation failed for job %s", job.get("id"))
        await send_telegram_message(
            token, chat_id, f"⚠️ CV generation failed: {str(e)[:200]}"
        )
        return

    out = Path("output")
    sent = 0
    for prefix in ("tailored_cv", "tailored_cv_de", "tailored_cover_letter", "tailored_cover_letter_de"):
        pdf = out / f"{prefix}_v{version}.pdf"
        if pdf.is_file():
            try:
                await send_telegram_document(token, chat_id, str(pdf), caption=f"{prefix} v{version}")
                sent += 1
            except Exception:
                logger.exception("Failed to send %s", pdf)
    await send_telegram_message(token, chat_id, f"✅ Sent {sent} files for: {job['title']}")


async def _loop() -> None:
    settings = get_settings()
    interval = max(60, settings.job_search_interval_minutes * 60)
    while True:
        try:
            await process_new_jobs()
        except Exception:
            logger.exception("Job scheduler cycle error")
        await asyncio.sleep(interval)


async def start_job_scheduler() -> None:
    """Start the background job-alert loop (only if Adzuna is configured)."""
    global _task
    if _task is not None:
        return
    _load_subscribers()
    settings = get_settings()
    if not (settings.adzuna_app_id and settings.adzuna_app_key) and not settings.jooble_api_key:
        logger.info("No job source configured — job scheduler disabled.")
        return
    _task = asyncio.create_task(_loop())
    logger.info("Job scheduler started (interval=%s min)", settings.job_search_interval_minutes)
