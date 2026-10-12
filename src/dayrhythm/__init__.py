"""dayrhythm: explainable daily-routine baselines from timestamped home events.

Feed it events such as "motion in the kitchen at 08:07" or "front door opened at 09:40". It
extracts a handful of daily markers (first kitchen activity, wake time, night-time trips, the
longest quiet spell), learns a robust per-home baseline (median and MAD, so one odd day does not
move it), and explains today in plain words:

    "No kitchen activity yet by 11:00 (usually 08:10, give or take 25 min)."

No dependencies, no machine learning, no audio or video: just timestamps and zones.
"""

from .assess import Assessment, Finding, MarkerView, Thresholds, assess
from .baseline import Baseline, MarkerStats, learn
from .markers import (
    CountEpisodes,
    CountEvents,
    DayMarkers,
    Event,
    FirstEvent,
    LastEvent,
    LongestGap,
    MarkerSpec,
    default_specs,
    extract,
    extract_days,
)
from .timefmt import clock, duration

__version__ = "0.1.0"

__all__ = [
    "Assessment",
    "Baseline",
    "CountEpisodes",
    "CountEvents",
    "DayMarkers",
    "Event",
    "Finding",
    "FirstEvent",
    "LastEvent",
    "LongestGap",
    "MarkerSpec",
    "MarkerStats",
    "MarkerView",
    "Thresholds",
    "assess",
    "clock",
    "default_specs",
    "duration",
    "extract",
    "extract_days",
    "learn",
]
