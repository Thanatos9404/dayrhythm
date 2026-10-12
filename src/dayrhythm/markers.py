"""Events in, daily markers out.

Windows are minutes relative to midnight of the day being described, so a night window of
(-60, 300) means "23:00 the evening before until 05:00 this morning".
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any


@dataclass(frozen=True, order=True)
class Event:
    """One thing that happened at home. `at` is local wall-clock time."""

    at: datetime
    zone: str
    kind: str = "motion"  # motion | contact_open | contact_close | doorbell


@dataclass(frozen=True)
class MarkerSpec:
    name: str
    label: str
    window: tuple[int, int]
    zones: frozenset[str] | None = None
    kinds: frozenset[str] | None = frozenset({"motion"})

    # What kind of value the marker holds: "time" (minutes after midnight), "count", "duration".
    value_type: str = "time"
    # Highest severity this marker may raise on its own. Optional habits (a morning walk) are
    # worth noting but should never trigger a check-in by themselves.
    cap: str = "concern"

    def matches(self, ev: Event) -> bool:
        return (self.zones is None or ev.zone in self.zones) and (self.kinds is None or ev.kind in self.kinds)

    def compute(self, minutes: list[float], start: float, end: float) -> tuple[float | int | None, dict[str, Any]]:
        raise NotImplementedError


@dataclass(frozen=True)
class FirstEvent(MarkerSpec):
    """Time of the first matching event in the window (e.g. first kitchen motion)."""

    def compute(self, minutes, start, end):
        return (minutes[0] if minutes else None), {}


@dataclass(frozen=True)
class LastEvent(MarkerSpec):
    """Time of the last matching event in the window (e.g. last activity before sleep)."""

    def compute(self, minutes, start, end):
        return (minutes[-1] if minutes else None), {}


@dataclass(frozen=True)
class CountEvents(MarkerSpec):
    value_type: str = "count"

    def compute(self, minutes, start, end):
        return len(minutes), {}


@dataclass(frozen=True)
class CountEpisodes(MarkerSpec):
    """Number of separate episodes: events closer than `merge_gap` minutes belong to one trip."""

    merge_gap: int = 15
    value_type: str = "count"

    def compute(self, minutes, start, end):
        episodes: list[tuple[float, float]] = []
        for m in minutes:
            if episodes and m - episodes[-1][1] <= self.merge_gap:
                episodes[-1] = (episodes[-1][0], m)
            else:
                episodes.append((m, m))
        return len(episodes), {"episodes": episodes}


@dataclass(frozen=True)
class LongestGap(MarkerSpec):
    """Longest stretch with no matching event inside the window (up to `now` for today)."""

    kinds: frozenset[str] | None = None
    value_type: str = "duration"

    def compute(self, minutes, start, end):
        points = [start, *minutes, end]
        best, best_from = 0.0, start
        for a, b in zip(points, points[1:]):
            if b - a > best:
                best, best_from = b - a, a
        return best, {"from": best_from, "to": best_from + best}


@dataclass
class DayMarkers:
    day: date
    values: dict[str, float | int | None] = field(default_factory=dict)
    complete: dict[str, bool] = field(default_factory=dict)
    extra: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get(self, name: str) -> float | int | None:
        return self.values.get(name)


def default_specs() -> list[MarkerSpec]:
    """Markers that work with a few motion detectors and a front-door contact sensor."""
    return [
        FirstEvent("wake", "morning movement", (240, 840)),
        FirstEvent("first_kitchen", "kitchen activity", (240, 840), zones=frozenset({"kitchen"})),
        FirstEvent("first_door", "front door opening", (240, 1200), zones=frozenset({"front_door"}), kinds=frozenset({"contact_open"}), cap="watch"),
        CountEpisodes("night_trips", "night-time trips", (-60, 300)),
        LongestGap("quiet_daytime", "quiet spell", (480, 1260), kinds=frozenset({"motion", "contact_open", "contact_close"})),
        LastEvent("last_activity", "last activity of the evening", (1080, 1560)),
        CountEvents("activity", "movement", (240, 1440)),
    ]


def _midnight(day: date) -> datetime:
    return datetime.combine(day, time(0, 0))


def extract(events: Iterable[Event], day: date, specs: Sequence[MarkerSpec] | None = None, now: datetime | None = None) -> DayMarkers:
    """Markers for one day. With `now`, the day is treated as in progress (today)."""
    specs = list(specs or default_specs())
    base = _midnight(day)
    now_min = (now - base).total_seconds() / 60 if now is not None else None
    evs = sorted(events)
    out = DayMarkers(day)
    for spec in specs:
        start, end = spec.window
        hi = end if now_min is None else min(end, now_min)
        minutes = []
        for ev in evs:
            if not spec.matches(ev):
                continue
            m = (ev.at - base).total_seconds() / 60
            if start <= m < hi:
                minutes.append(m)
        if hi <= start:
            out.values[spec.name], extra = None, {}
        else:
            out.values[spec.name], extra = spec.compute(minutes, start, hi)
        out.complete[spec.name] = now_min is None or now_min >= end
        if extra:
            out.extra[spec.name] = extra
    return out


def extract_days(events: Iterable[Event], days: Iterable[date], specs: Sequence[MarkerSpec] | None = None) -> list[DayMarkers]:
    """Markers for several complete days (history)."""
    specs = list(specs or default_specs())
    evs = sorted(events)
    result = []
    for day in days:
        lo = _midnight(day) + timedelta(minutes=min(s.window[0] for s in specs))
        hi = _midnight(day) + timedelta(minutes=max(s.window[1] for s in specs))
        window = [e for e in evs if lo <= e.at < hi]
        result.append(extract(window, day, specs))
    return result
