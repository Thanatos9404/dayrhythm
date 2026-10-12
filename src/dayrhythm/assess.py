"""Compare a (possibly unfinished) day with the baseline and explain every deviation in words."""

from __future__ import annotations

from dataclasses import dataclass, field

from .baseline import Baseline, MarkerStats
from .markers import CountEpisodes, CountEvents, DayMarkers, FirstEvent, LastEvent, LongestGap, MarkerSpec
from .timefmt import clock, duration

SEVERITY_ORDER = {"ok": 0, "info": 1, "watch": 2, "concern": 3}


@dataclass(frozen=True)
class Thresholds:
    watch: float = 2.0  # robust z-score
    concern: float = 3.0
    expected_presence: float = 0.75  # a missing marker only matters if it normally happens this often
    quiet_watch_min: float = 90.0  # never flag a quiet spell shorter than this
    quiet_concern_min: float = 150.0
    night_concern_min_trips: int = 3


@dataclass
class Finding:
    marker: str
    label: str
    severity: str  # info | watch | concern
    direction: str  # late | early | missing | high | low | long
    score: float  # robust z-score (how many usual spreads away)
    observed: float | None
    usual: float | None
    spread: float | None
    explanation: str


@dataclass
class MarkerView:
    """Everything a UI needs to draw "today vs usual" for one marker."""

    marker: str
    label: str
    value_type: str
    observed: float | None
    usual: float | None
    spread: float | None
    status: str  # ok | pending | info | watch | concern | no-baseline
    complete: bool


@dataclass
class Assessment:
    severity: str  # ok | info | watch | concern | learning
    findings: list[Finding] = field(default_factory=list)
    markers: list[MarkerView] = field(default_factory=list)
    learning: bool = False
    days_of_history: int = 0

    @property
    def summary(self) -> str:
        if self.learning:
            return f"Still learning the usual routine ({self.days_of_history} of 7 days so far)."
        notable = [f for f in self.findings if f.severity in ("watch", "concern")]
        if not notable:
            return "Today looks like a usual day."
        return notable[0].explanation


def _sev(z: float, t: Thresholds) -> str | None:
    if z >= t.concern:
        return "concern"
    if z >= t.watch:
        return "watch"
    return None


def _usual(st: MarkerStats) -> str:
    return f"usually {clock(st.median)}, give or take {duration(st.spread)}"


def _first_event(spec: MarkerSpec, st: MarkerStats, value, complete: bool, now_min: float | None, t: Thresholds) -> Finding | None:
    if value is not None:
        z = (value - st.median) / st.spread
        sev = _sev(z, t)
        if sev:
            return Finding(spec.name, spec.label, sev, "late", z, value, st.median, st.spread,
                           f"{spec.label.capitalize()} at {clock(value)}, later than usual ({_usual(st)}).")
        if z <= -t.watch:
            return Finding(spec.name, spec.label, "info", "early", z, value, st.median, st.spread,
                           f"{spec.label.capitalize()} at {clock(value)}, earlier than usual ({_usual(st)}).")
        return None
    if st.presence_rate < t.expected_presence:
        return None
    reference = now_min if (now_min is not None and not complete) else spec.window[1]
    z = (reference - st.median) / st.spread
    sev = _sev(z, t)
    if not sev:
        return None
    when = f"yet by {clock(reference)}" if not complete else "all day"
    return Finding(spec.name, spec.label, sev, "missing", z, None, st.median, st.spread,
                   f"No {spec.label} {when} ({_usual(st)}).")


def _last_event(spec, st, value, complete, t) -> Finding | None:
    if not complete or value is None:
        return None
    z = (value - st.median) / st.spread
    if z >= t.watch:
        return Finding(spec.name, spec.label, "watch" if z < t.concern else "concern", "late", z, value, st.median, st.spread,
                       f"{spec.label.capitalize()} at {clock(value)}, later than usual ({_usual(st)}).")
    return None


def _episodes(spec, st, value, t) -> Finding | None:
    if value is None or value <= (st.p90 or 0):
        return None
    z = (value - st.median) / st.spread
    if z < t.watch or value < 2:
        return None
    sev = "concern" if (z >= t.concern + 0.5 and value >= t.night_concern_min_trips) else "watch"
    start, end = spec.window
    usual = f"usually {int(st.low or 0)} to {int(st.p90 or 0)}" if st.low != st.p90 else f"usually {int(st.median)}"
    return Finding(spec.name, spec.label, sev, "high", z, value, st.median, st.spread,
                   f"{int(value)} {spec.label} between {clock(start)} and {clock(end)} ({usual}).")


def _gap(spec, st, value, extra, t) -> Finding | None:
    if value is None:
        return None
    z = (value - st.median) / st.spread
    sev = _sev(z, t)
    if sev == "concern" and value < t.quiet_concern_min:
        sev = "watch"
    if sev == "watch" and value < t.quiet_watch_min:
        sev = None
    if not sev:
        return None
    since = extra.get("from")
    return Finding(spec.name, spec.label, sev, "long", z, value, st.median, st.spread,
                   f"No movement for {duration(value)} since {clock(since)} (longest usual {spec.label} about {duration(st.p90 or st.median)}).")


def _count(spec, st, value, complete, t) -> Finding | None:
    if not complete or value is None:
        return None
    z = (st.median - value) / st.spread
    if z >= t.watch:
        return Finding(spec.name, spec.label, "watch", "low", z, value, st.median, st.spread,
                       f"Less {spec.label} than usual today: {int(value)} sensor events (usually about {int(st.median)}).")
    return None


def assess(today: DayMarkers, baseline: Baseline, now_min: float | None = None, thresholds: Thresholds | None = None) -> Assessment:
    """`now_min` is minutes after midnight of `today.day` (may exceed 1440 after midnight)."""
    t = thresholds or Thresholds()
    result = Assessment(severity="ok", learning=not baseline.ready, days_of_history=baseline.n_days)
    for spec in baseline.specs:
        st = baseline.get(spec.name)
        value = today.values.get(spec.name)
        complete = today.complete.get(spec.name, True)
        if st is None or st.median is None or not baseline.ready:
            result.markers.append(MarkerView(spec.name, spec.label, spec.value_type, value, None, None, "no-baseline", complete))
            continue
        if isinstance(spec, FirstEvent):
            finding = _first_event(spec, st, value, complete, now_min, t)
        elif isinstance(spec, LastEvent):
            finding = _last_event(spec, st, value, complete, t)
        elif isinstance(spec, CountEpisodes):
            finding = _episodes(spec, st, value, t)
        elif isinstance(spec, LongestGap):
            finding = _gap(spec, st, value, today.extra.get(spec.name, {}), t)
        elif isinstance(spec, CountEvents):
            finding = _count(spec, st, value, complete, t)
        else:
            finding = None
        status = finding.severity if finding else ("pending" if value is None and not complete else "ok")
        result.markers.append(MarkerView(spec.name, spec.label, spec.value_type, value, st.median, st.spread, status, complete))
        if finding:
            result.findings.append(finding)
    result.findings.sort(key=lambda f: (-SEVERITY_ORDER[f.severity], -f.score))
    if result.learning:
        result.severity = "learning"
    elif result.findings:
        result.severity = result.findings[0].severity
    return result
