"""Adzuna job search (free API, Germany endpoint).

Primary filter is the configured category (default 'it-jobs' = ALL IT/software/
data roles in a single call). Optional extra keywords can narrow further.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from hub.config import Settings

logger = logging.getLogger(__name__)

_ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


async def search_jobs(settings: Settings) -> list[dict[str, Any]]:
    """Search Adzuna. Returns merged, newest-first job dicts.

    Each job dict: id, title, company, location, url, description, created.
    """
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        logger.warning("Adzuna credentials not set; skipping job search.")
        return []

    # Build the list of queries: the category (broad) + any extra keywords (narrow).
    queries: list[dict[str, str]] = []
    if settings.job_search_category:
        queries.append({"category": settings.job_search_category})
    for term in [t.strip() for t in settings.job_search_keywords.split(",") if t.strip()]:
        queries.append({"what": term})
    if not queries:
        queries.append({})

    jobs: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient(timeout=30.0) as client:
        for q in queries:
            try:
                r = await client.get(
                    _ADZUNA_URL.format(country=settings.job_search_country, page=1),
                    params={
                        "app_id": settings.adzuna_app_id,
                        "app_key": settings.adzuna_app_key,
                        "results_per_page": 20,
                        "sort_by": "date",
                        "content-type": "application/json",
                        **q,
                    },
                )
                r.raise_for_status()
                for item in r.json().get("results", []):
                    jid = str(item.get("id"))
                    if not jid or jid in seen_ids:
                        continue
                    seen_ids.add(jid)
                    area = (item.get("location") or {}).get("area") or []
                    jobs.append(
                        {
                            "id": jid,
                            "title": (item.get("title") or "").strip(),
                            "company": (item.get("company") or {}).get("display_name", ""),
                            "location": ", ".join(area),
                            "url": item.get("redirect_url") or "",
                            "description": (item.get("description") or "").strip(),
                            "created": item.get("created") or "",
                        }
                    )
            except Exception:
                logger.exception("Adzuna search failed for %r", q)

    jobs.sort(key=lambda j: j.get("created", ""), reverse=True)
    return jobs
