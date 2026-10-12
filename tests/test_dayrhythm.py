from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from dayrhythm import Event, Thresholds, assess, clock, default_specs, duration, extract, extract_days, learn

START = date(2026, 9, 1)


def routine_day(day: date, rng: random.Random, *, wake=465, kitchen_delay=15, night_trip=True) -> list[Event]:
    """A plausible day: up ~07:45, kitchen ~08:00, door ~09:30, quiet afternoon nap, bed ~22:15."""
    base = datetime.combine(day, datetime.min.time())
    at = lambda m: base + timedelta(minutes=m)  # noqa: E731
    w = wake + rng.gauss(0, 12)
    k = w + kitchen_delay + rng.gauss(0, 5)
    evs = [Event(at(w), "hallway"), Event(at(k), "kitchen"), Event(at(k + 12), "kitchen")]
    evs += [Event(at(k + 30 + 40 * i), "living_room") for i in range(4)]
    evs += [Event(at(570 + rng.gauss(0, 20)), "front_door", "contact_open"), Event(at(575), "front_door", "contact_close")]
    evs += [Event(at(m + rng.gauss(0, 10)), z) for m, z in [(750, "kitchen"), (780, "living_room"), (900, "living_room"), (960, "kitchen"),
                                                            (1080, "kitchen"), (1110, "living_room"), (1200, "living_room"), (1320, "hallway")]]
    if night_trip and rng.random() < 0.4:
        evs.append(Event(at(1440 + 150 + rng.gauss(0, 30)), "hallway"))
    return evs


def history(n=21, seed=7):
    rng = random.Random(seed)
    days = [START + timedelta(days=i) for i in range(n)]
    events = [e for d in days for e in routine_day(d, rng)]
    return events, days


def test_markers_from_events():
    rng = random.Random(1)
    day = START
    m = extract(routine_day(day, rng), day)
    assert 440 < m.values["wake"] < 500
    assert m.values["first_kitchen"] > m.values["wake"]
    assert m.values["first_door"] is not None
    assert m.values["activity"] > 10
    assert all(m.complete.values())


def test_baseline_is_robust_and_explains_a_missing_kitchen_morning():
    events, days = history()
    base = learn(extract_days(events, days))
    assert base.ready and base.n_days == 21
    kitchen = base.get("first_kitchen")
    assert 465 < kitchen.median < 500 and kitchen.spread >= 20

    today = days[-1] + timedelta(days=1)
    now = datetime.combine(today, datetime.min.time()) + timedelta(hours=11)
    markers = extract([], today, now=now)  # nothing at all since 04:00
    result = assess(markers, base, now_min=11 * 60)
    assert result.severity == "concern"
    texts = [f.explanation for f in result.findings]
    assert any(t.startswith("No kitchen activity yet by 11:00 (usually 0") for t in texts)
    assert "give or take" in result.summary


def test_a_slightly_late_morning_is_not_an_alarm():
    events, days = history()
    base = learn(extract_days(events, days))
    today = days[-1] + timedelta(days=1)
    rng = random.Random(3)
    evs = [e for e in routine_day(today, rng, wake=490) if e.at < datetime.combine(today, datetime.min.time()) + timedelta(hours=10)]
    result = assess(extract(evs, today, now=datetime.combine(today, datetime.min.time()) + timedelta(hours=10)), base, now_min=600)
    assert result.severity in ("ok", "info")


def test_night_wandering_and_long_quiet_spell():
    events, days = history()
    base = learn(extract_days(events, days))
    today = days[-1] + timedelta(days=1)
    mid = datetime.combine(today, datetime.min.time())
    night = [Event(mid + timedelta(minutes=m), "hallway") for m in (60, 62, 120, 170, 171, 230)]
    night += [Event(mid + timedelta(minutes=125), "front_door", "contact_open")]
    morning = [Event(mid + timedelta(minutes=m), z) for m, z in [(470, "hallway"), (485, "kitchen"), (500, "kitchen"), (540, "living_room")]]
    result = assess(extract(night + morning, today, now=mid + timedelta(hours=15)), base, now_min=900)
    by = {f.marker: f for f in result.findings}
    assert by["night_trips"].severity in ("watch", "concern") and "night-time trips" in by["night_trips"].explanation
    assert by["quiet_daytime"].direction == "long" and "since 09:00" in by["quiet_daytime"].explanation


def test_learning_mode_before_seven_days():
    events, days = history(n=4)
    base = learn(extract_days(events, days))
    today = days[-1] + timedelta(days=1)
    result = assess(extract([], today), base)
    assert result.learning and result.severity == "learning" and "4 of 7" in result.summary


def test_rare_markers_are_not_expected():
    events, days = history()
    events = [e for e in events if not (e.zone == "front_door" and e.at.day % 2)]  # door only every other day
    base = learn(extract_days(events, days))
    assert base.get("first_door").presence_rate < 0.75
    today = days[-1] + timedelta(days=1)
    mid = datetime.combine(today, datetime.min.time())
    evs = [Event(mid + timedelta(minutes=m), z) for m, z in [(465, "hallway"), (480, "kitchen")]]
    result = assess(extract(evs, today, now=mid + timedelta(hours=20)), base, now_min=1200, thresholds=Thresholds())
    assert "first_door" not in {f.marker for f in result.findings}


def test_formatting():
    assert clock(490) == "08:10" and clock(1500) == "01:00" and clock(None) == "--:--"
    assert duration(25) == "25 min" and duration(125) == "2 h 05 min" and duration(120) == "2 h"
    assert [s.name for s in default_specs()][:2] == ["wake", "first_kitchen"]
