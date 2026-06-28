"""Job search across free APIs (Adzuna + Jooble), Germany.

Adzuna: category filter (it-jobs = all IT). Jooble: keyword search. Results are
merged and de-duplicated by a title+company signature so the same job appearing
on both sources is counted once.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from hub.config import Settings

logger = logging.getLogger(__name__)

_ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


def _signature(title: str, company: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").strip().lower())
    c = re.sub(r"\s+", " ", (company or "").strip().lower())
    return f"{t}|{c}"


def _parse_adzuna_item(item: dict) -> dict:
    area = (item.get("location") or {}).get("area") or []
    return {
        "id": str(item.get("id")),
        "title": (item.get("title") or "").strip(),
        "company": (item.get("company") or {}).get("display_name", ""),
        "location": ", ".join(area),
        "url": item.get("redirect_url") or "",
        "description": (item.get("description") or "").strip(),
        "created": item.get("created") or "",
    }


async def _search_adzuna(settings: Settings) -> list[dict[str, Any]]:
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        return []
    queries: list[dict[str, str]] = []
    if settings.job_search_category:
        queries.append({"category": settings.job_search_category})
    for term in [t.strip() for t in settings.job_search_keywords.split(",") if t.strip()]:
        queries.append({"what": term})
    if not queries:
        queries.append({})

    jobs: list[dict[str, Any]] = []
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
                    jobs.append(_parse_adzuna_item(item))
            except Exception:
                logger.exception("Adzuna search failed for %r", q)
    return jobs


async def _search_jooble(settings: Settings) -> list[dict[str, Any]]:
    if not settings.jooble_api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"https://jooble.org/api/{settings.jooble_api_key}",
                json={"keywords": "IT", "location": "Germany"},
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        logger.exception("Jooble search failed")
        return []

    jobs: list[dict[str, Any]] = []
    for item in data.get("jobs", []) or []:
        jobs.append(
            {
                "id": f"jooble-{item.get('id') or item.get('link')}",
                "title": (item.get("title") or "").strip(),
                "company": (item.get("company") or item.get("name") or "").strip(),
                "location": (item.get("location") or "").strip(),
                "url": item.get("link") or "",
                "description": (item.get("snippet") or "").strip(),
                "created": item.get("updated") or "",
            }
        )
    return jobs


async def search_jobs(settings: Settings) -> list[dict[str, Any]]:
    """Merge Adzuna + Jooble, de-duplicate by title+company, newest first."""
    jobs = await _search_adzuna(settings)
    jobs += await _search_jooble(settings)

    seen_sig: set[str] = set()
    unique: list[dict[str, Any]] = []
    for j in jobs:
        j["signature"] = _signature(j["title"], j["company"])
        if not j["signature"] or j["signature"] in seen_sig:
            continue
        seen_sig.add(j["signature"])
        unique.append(j)

    unique.sort(key=lambda j: j.get("created", ""), reverse=True)
    return unique
