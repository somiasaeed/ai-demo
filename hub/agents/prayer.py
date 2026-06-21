"""Prayer Times — Aladhan API (free, no key) with Tahajjud calculation."""

from __future__ import annotations

import logging
from datetime import date

import httpx

logger = logging.getLogger(__name__)

_PRAYER_NAMES = {
    "Fajr": "Fajr",
    "Dhuhr": "Dhuhr",
    "Asr": "Asr",
    "Maghrib": "Maghrib",
    "Isha": "Isha",
}


class PrayerAgent:
    """Fetches daily prayer times for a location using the Aladhan API."""

    async def run(self, query: str = "", *, lat: float | None = None, lng: float | None = None) -> str:
        """Return formatted prayer schedule including Tahajjud."""
        if lat is not None and lng is not None:
            return await self._by_coords(lat, lng)
        q = (query or "").strip()
        if not q:
            return "Please provide a city name or share your location."
        return await self._by_city(q)

    async def get_timings(self, lat: float, lng: float) -> dict | None:
        """Full Aladhan ``data`` block (timings + date + meta) for a location.

        ``meta.timezone`` is an IANA name (e.g. "Europe/Berlin") and is needed by
        the scheduler to compute local time. Returns None on failure.
        """
        try:
            today = date.today().strftime("%d-%m-%Y")
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                r = await client.get(
                    f"https://api.aladhan.com/v1/timings/{today}",
                    params={
                        "latitude": lat,
                        "longitude": lng,
                        "method": 2,
                    },
                )
                logger.info("Aladhan response status: %s", r.status_code)
                r.raise_for_status()
                data = r.json()
            block = data.get("data") or {}
            timings = block.get("timings") or {}
            logger.info("Aladhan timings keys: %s", list(timings.keys())[:6])
            return block or None
        except Exception:
            logger.exception("Aladhan API call failed for lat=%s lng=%s", lat, lng)
            return None

    async def _by_city(self, city: str) -> str:
        lat, lng, resolved = await self._geocode(city)
        if lat is None:
            return f'Could not find "{city}". Try a larger city name.'
        block = await self.get_timings(lat, lng)
        timings = (block or {}).get("timings", {})
        if not timings:
            return "Could not fetch prayer times. Please try again later."
        return self._format(timings, resolved)

    async def _by_coords(self, lat: float, lng: float) -> str:
        block = await self.get_timings(lat, lng)
        timings = (block or {}).get("timings", {})
        if not timings:
            return "Could not fetch prayer times. Please try again later."
        return self._format(timings, f"{lat:.2f}, {lng:.2f}")

    async def _geocode(self, place: str) -> tuple[float | None, float | None, str]:
        """Geocode a city name using Open-Meteo."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": place, "count": 1},
                )
                r.raise_for_status()
                results = r.json().get("results") or []
                if not results:
                    return None, None, place
                r0 = results[0]
                name = r0.get("name", place)
                country = r0.get("country_code", "")
                resolved = f"{name}" + (f", {country}" if country else "")
                return r0["latitude"], r0["longitude"], resolved
        except Exception:
            logger.exception("Geocoding failed for %s", place)
            return None, None, place

    def _format(self, timings: dict, location: str) -> str:
        """Format prayer times into a readable message with Tahajjud."""
        lines = [f"Prayer Times for **{location}**\n"]

        for key, label in _PRAYER_NAMES.items():
            t = timings.get(key, "—")
            lines.append(f"  {label}: **{t}**")

        tahajjud = self._calc_tahajjud(timings)
        if tahajjud:
            lines.append(f"  Tahajjud (last 1/3 of night): **{tahajjud}**")

        lines.append("\n_Tahajjud is the optimal time for Qiyam al-Layl._")
        lines.append("_(Source: Aladhan API)_")
        return "\n".join(lines)

    def calc_tahajjud(self, timings: dict) -> str | None:
        """Public wrapper for Tahajjud calculation."""
        return self._calc_tahajjud(timings)

    def _calc_tahajjud(self, timings: dict) -> str | None:
        """Calculate last third of the night between Maghrib and next Fajr."""
        try:
            maghrib_str = timings.get("Maghrib", "")
            fajr_str = timings.get("Fajr", "")
            if not maghrib_str or not fajr_str:
                return None

            mb = maghrib_str.split(" ")[0]
            fb = fajr_str.split(" ")[0]
            m_h, m_m = map(int, mb.split(":")[:2])
            f_h, f_m = map(int, fb.split(":")[:2])

            maghrib_min = m_h * 60 + m_m
            fajr_min = f_h * 60 + f_m + 24 * 60
            night_duration = fajr_min - maghrib_min

            last_third_start = maghrib_min + (2 * night_duration) // 3

            total_min = last_third_start % (24 * 60)
            th = total_min // 60
            tm = total_min % 60
            return f"{th:02d}:{tm:02d}"
        except Exception:
            logger.exception("Tahajjud calculation failed")
            return None
