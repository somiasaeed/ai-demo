"""Weather — Open-Meteo (no API key) with optional OpenWeatherMap if WEATHER_API_KEY is set."""

from __future__ import annotations

import os
from typing import Any

import httpx


class WeatherAgent:
    """Fetches current conditions for a location string."""

    async def run(self, query: str, *, plain_text: bool = False) -> str:
        q = (query or "").strip()
        if not q:
            return "Please provide a city or place name for the weather."

        key = os.environ.get("WEATHER_API_KEY", "").strip()
        if key:
            raw = await self._openweather(q, key)
        else:
            raw = await self._open_meteo(q)
        return _strip_markdown_for_chat(raw) if plain_text else raw

    async def _open_meteo(self, place: str) -> str:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        async with httpx.AsyncClient(timeout=20.0) as client:
            gr = await client.get(geo_url, params={"name": place, "count": 1})
            gr.raise_for_status()
            gdata = gr.json()
            results = gdata.get("results") or []
            if not results:
                return f"Could not find a place named "{place}". Try a larger city name."

            r0 = results[0]
            lat, lon = r0["latitude"], r0["longitude"]
            name = r0.get("name", place)
            country = r0.get("country_code", "")

            fr = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                    "timezone": "auto",
                },
            )
            fr.raise_for_status()
            fdata = fr.json()

        cur = fdata.get("current") or {}
        temp = cur.get("temperature_2m")
        hum = cur.get("relative_humidity_2m")
        code = cur.get("weather_code")
        wind = cur.get("wind_speed_10m")
        desc = _wmo_code_description(code)

        loc = f"{name}" + (f", {country}" if country else "")
        parts = [
            f"**{loc}** — {desc}",
            f"Temperature: **{temp}°C**" if temp is not None else "",
            f"Humidity: {hum}%" if hum is not None else "",
            f"Wind: {wind} km/h" if wind is not None else "",
        ]
        return "\n".join(p for p in parts if p) + "\n\n_(Source: Open-Meteo)_"

    async def _openweather(self, place: str, api_key: str) -> str:
        url = "https://api.openweathermap.org/data/2.5/weather"
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url, params={"q": place, "appid": api_key, "units": "metric"})
            r.raise_for_status()
            data: dict[str, Any] = r.json()

        name = data.get("name", place)
        main = data.get("main") or {}
        w = (data.get("weather") or [{}])[0]
        desc = w.get("description", "unknown")
        temp = main.get("temp")
        feels = main.get("feels_like")
        hum = main.get("humidity")
        return (
            f"**{name}** — {desc}\n"
            f"Temperature: **{temp}°C** (feels like {feels}°C)\n"
            f"Humidity: {hum}%\n\n_(Source: OpenWeatherMap)_"
        )


def _wmo_code_description(code: int | None) -> str:
    if code is None:
        return "Weather data"
    # WMO Weather interpretation codes (Open-Meteo)
    if code == 0:
        return "Clear sky"
    if code in (1, 2, 3):
        return "Mainly clear, partly cloudy, or overcast"
    if code in (45, 48):
        return "Fog"
    if code in (51, 53, 55, 56, 57):
        return "Drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "Rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "Snow"
    if code in (95, 96, 99):
        return "Thunderstorm"
    return f"Conditions (code {code})"


def _strip_markdown_for_chat(text: str) -> str:
    """Telegram default parse mode is plain; remove ** and _ italics markers."""
    s = text.replace("**", "").replace("__", "")
    s = s.replace("_(Source: Open-Meteo)_", "(Source: Open-Meteo)")
    s = s.replace("_(Source: OpenWeatherMap)_", "(Source: OpenWeatherMap)")
    return s.strip()
