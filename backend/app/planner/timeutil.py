"""Time and geometry helpers for deterministic scheduling (Asia/Kolkata)."""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def tz(name: str = "Asia/Kolkata") -> timezone:
    return IST  # Phase 1: Indian trips only; other zones rejected upstream.


def at(day: date, t: time, zone: timezone = IST) -> datetime:
    return datetime.combine(day, t, tzinfo=zone)


def hm(minutes: int) -> str:
    h, m = divmod(int(minutes), 60)
    return f"{h:02d}:{m:02d}"


def minutes_of(t: time) -> int:
    return t.hour * 60 + t.minute


def time_of(minutes: int) -> time:
    minutes = max(0, min(minutes, 24 * 60 - 1))
    return time(minutes // 60, minutes % 60)


def add_minutes(dt: datetime, minutes: int) -> datetime:
    return dt + timedelta(minutes=minutes)


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))
