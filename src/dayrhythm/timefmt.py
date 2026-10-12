"""Human-friendly formatting of minute values."""

from __future__ import annotations


def clock(minutes: float | None) -> str:
    """Minutes after midnight -> '08:10'. Values past midnight wrap ('25:30' -> '01:30')."""
    if minutes is None:
        return "--:--"
    m = int(round(minutes)) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def duration(minutes: float | None) -> str:
    """Minutes -> '25 min', '2 h 05 min'."""
    if minutes is None:
        return "-"
    m = int(round(minutes))
    if m < 60:
        return f"{m} min"
    h, rest = divmod(m, 60)
    return f"{h} h" if rest == 0 else f"{h} h {rest:02d} min"
