"""Background prayer reminder scheduler — sends Telegram messages at prayer times."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from hub.agents.prayer import PrayerAgent
from hub.config import get_settings
from hub.services.telegram_outbound import send_telegram_message

logger = logging.getLogger(__name__)

# In-memory store: chat_id -> {lat, lng, city, tz_offset}
_registered_users: dict[int, dict] = {}

# Track which prayers have been sent today to avoid duplicates
_sent_today: dict[int, set[str]] = {}  # chat_id -> set of prayer names sent

# Reference to running task
_task: asyncio.Task | None = None

PRAYER_REMINDER_TEMPLATE = (
    "Assalamu Alaikum! It's time for **{prayer}** prayer. ({time})\n"
    "May Allah accept your prayers."
)

TAHAJJUD_REMINDER = (
    "Assalamu Alaikum! The time for **Tahajjud** has begun ({time}).\n"
    "The Prophet (PBUH) said: The best prayer after the obligatory prayers "
    "is the night prayer. (Sahih Muslim)"
)


def register_user(chat_id: int, lat: float, lng: float, city: str = "") -> None:
    """Register or update a user's location for prayer reminders."""
    _registered_users[chat_id] = {
        "lat": lat,
        "lng": lng,
        "city": city,
    }
    # Reset sent prayers for this user so they get reminders with new location
    _sent_today.pop(chat_id, None)
    logger.info(
        "Registered chat_id=%s for prayer reminders at %s (%s, %s)",
        chat_id, city or "unknown", lat, lng,
    )


def get_registered_users() -> dict[int, dict]:
    return _registered_users


async def start_prayer_scheduler() -> None:
    """Start the background prayer reminder loop."""
    global _task
    if _task is not None:
        return
    _task = asyncio.create_task(_scheduler_loop())
    logger.info("Prayer reminder scheduler started")


async def _scheduler_loop() -> None:
    """Main loop — checks every 30 seconds if a prayer time has arrived."""
    agent = PrayerAgent()
    # Cache timings per user per day: {chat_id: {"date": str, "timings": dict}}
    cache: dict[int, dict] = {}

    while True:
        try:
            settings = get_settings()
            if not settings.telegram_bot_token or not _registered_users:
                await asyncio.sleep(30)
                continue

            now = datetime.now(timezone.utc)
            today_str = now.strftime("%Y-%m-%d")

            for chat_id, info in list(_registered_users.items()):
                lat = info["lat"]
                lng = info["lng"]

                # Refresh timings once per day
                user_cache = cache.get(chat_id, {})
                if user_cache.get("date") != today_str:
                    block = await agent.get_timings(lat, lng)
                    if block:
                        cache[chat_id] = {"date": today_str, "block": block}
                        _sent_today.pop(chat_id, None)
                    else:
                        continue

                block = cache[chat_id]["block"]
                timings = block.get("timings", {})
                sent_set = _sent_today.setdefault(chat_id, set())

                # Local time at the prayer location. Aladhan returns an IANA
                # timezone name in meta.timezone (e.g. "Europe/Berlin"); the
                # prayer times themselves are local to that zone.
                tz_name = (block.get("meta") or {}).get("timezone") or "UTC"
                try:
                    local_now = datetime.now(ZoneInfo(tz_name))
                except Exception:
                    logger.warning("Unknown timezone %r; falling back to UTC", tz_name)
                    local_now = now
                current_time = local_now.strftime("%H:%M")

                # Check each prayer
                for prayer_name in ("Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"):
                    prayer_time = (timings.get(prayer_name) or "").split(" ")[0]
                    if not prayer_time:
                        continue

                    # Trigger if within 1 minute of prayer time
                    if _is_time_match(current_time, prayer_time) and prayer_name not in sent_set:
                        try:
                            msg = PRAYER_REMINDER_TEMPLATE.format(
                                prayer=prayer_name, time=prayer_time
                            )
                            await send_telegram_message(
                                settings.telegram_bot_token, chat_id, msg
                            )
                            sent_set.add(prayer_name)
                            logger.info(
                                "Sent %s reminder to chat_id=%s", prayer_name, chat_id
                            )
                        except Exception:
                            logger.exception(
                                "Failed to send %s reminder to chat_id=%s",
                                prayer_name, chat_id,
                            )

                # Tahajjud: send at Isha time (reminder for the night)
                isha_time = (timings.get("Isha") or "").split(" ")[0]
                tahajjud_time = agent._calc_tahajjud(timings)
                if (
                    tahajjud_time
                    and _is_time_match(current_time, isha_time)
                    and "tahajjud_reminder" not in sent_set
                ):
                    try:
                        msg = TAHAJJUD_REMINDER.format(time=tahajjud_time)
                        await send_telegram_message(
                            settings.telegram_bot_token, chat_id, msg
                        )
                        sent_set.add("tahajjud_reminder")
                    except Exception:
                        logger.exception("Failed to send Tahajjud reminder")

        except Exception:
            logger.exception("Prayer scheduler error")

        await asyncio.sleep(30)


def _is_time_match(current: str, target: str) -> bool:
    """Check if current HH:MM is within 1 minute of target HH:MM."""
    try:
        c_h, c_m = map(int, current.split(":"))
        t_h, t_m = map(int, target.split(":"))
        return c_h == t_h and abs(c_m - t_m) <= 1
    except (ValueError, IndexError):
        return False
