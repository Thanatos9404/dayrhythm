"""Robust per-marker baselines: median and MAD, so a single unusual day barely moves them."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field

from .markers import DayMarkers, MarkerSpec, default_specs

# Smallest spread we will ever assume, by value type. Stops a very regular person's baseline from
# becoming so tight that a 10-minute lie-in looks alarming.
SPREAD_FLOOR = {"time": 20.0, "count": 1.0, "duration": 20.0}
MAD_TO_SD = 1.4826


@dataclass
class MarkerStats:
    name: str
    label: str
    value_type: str
    n_days: int
    presence_rate: float  # share of days on which the marker happened at all
    median: float | None
    spread: float | None  # robust standard deviation (1.4826 x MAD), floored
    p10: float | None
    p90: float | None
    low: float | None
    high: float | None


@dataclass
class Baseline:
    stats: dict[str, MarkerStats]
    n_days: int
    specs: list[MarkerSpec] = field(default_factory=list)
    min_days: int = 7

    @property
    def ready(self) -> bool:
        return self.n_days >= self.min_days

    def get(self, name: str) -> MarkerStats | None:
        return self.stats.get(name)


def _quantile(sorted_vals: Sequence[float], q: float) -> float:
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def learn(history: Sequence[DayMarkers], specs: Sequence[MarkerSpec] | None = None, *, min_days: int = 7) -> Baseline:
    """Learn a baseline from complete past days. Days are weighted equally."""
    specs = list(specs or default_specs())
    stats: dict[str, MarkerStats] = {}
    for spec in specs:
        observed = [d.values.get(spec.name) for d in history if d.complete.get(spec.name, True)]
        days = len(observed)
        present = sorted(float(v) for v in observed if v is not None)
        if not present:
            stats[spec.name] = MarkerStats(spec.name, spec.label, spec.value_type, days, 0.0, None, None, None, None, None, None)
            continue
        med = statistics.median(present)
        mad = statistics.median([abs(v - med) for v in present])
        spread = max(MAD_TO_SD * mad, SPREAD_FLOOR.get(spec.value_type, 1.0))
        stats[spec.name] = MarkerStats(
            name=spec.name,
            label=spec.label,
            value_type=spec.value_type,
            n_days=days,
            presence_rate=len(present) / days if days else 0.0,
            median=med,
            spread=spread,
            p10=_quantile(present, 0.10),
            p90=_quantile(present, 0.90),
            low=present[0],
            high=present[-1],
        )
    return Baseline(stats=stats, n_days=len(history), specs=specs, min_days=min_days)
