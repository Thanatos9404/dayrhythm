"""Human-friendly formatting of minute values."""

from __future__ import annotations


def clock(minutes: float | None, twelve_hour: bool = False) -> str:
    """Minutes after midnight -> '08:10' (or '8:10 AM'). Values past midnight wrap ('25:30' -> '01:30')."""
    if minutes is None:
        return "--:--"
    m = int(round(minutes)) % 1440
    h, mm = divmod(m, 60)
    if twelve_hour:
        return f"{h % 12 or 12}:{mm:02d} {'AM' if h < 12 else 'PM'}"
    return f"{h:02d}:{mm:02d}"


def duration(minutes: float | None) -> str:
    """Minutes -> '25 min', '2 h 05 min'."""
    if minutes is None:
        return "-"
    m = int(round(minutes))
    if m < 60:
        return f"{m} min"
    h, rest = divmod(m, 60)
    return f"{h} h" if rest == 0 else f"{h} h {rest:02d} min"
