# dayrhythm

Explainable daily-routine baselines from timestamped home events.

Give it events such as *motion in the kitchen at 08:07* or *front door opened at 09:40*. It extracts
a few daily markers, learns a robust per-home baseline, and explains today in plain words:

```
No kitchen activity yet by 11:00 (usually 08:10, give or take 25 min).
3 night-time trips between 23:00 and 05:00 (usually 0 to 1).
No movement for 3 h 40 min since 13:20 (longest usual quiet spell about 1 h 50 min).
```

Built for ageing-in-place and care-taking tools where false alarms erode trust and every alert has
to say *why*. No dependencies, no machine learning, no audio or video: only timestamps and zones.

## Install

```bash
pip install ./packages/dayrhythm        # from this repository
```

## Use

```python
from datetime import date, datetime
from dayrhythm import Event, extract, extract_days, learn, assess

history = [Event(datetime(2026, 9, 1, 7, 46), "hallway"), Event(datetime(2026, 9, 1, 8, 3), "kitchen"), ...]
baseline = learn(extract_days(history, days=[date(2026, 9, d) for d in range(1, 22)]))

now = datetime(2026, 9, 22, 11, 0)
today = extract(todays_events, now.date(), now=now)       # an unfinished day
result = assess(today, baseline, now_min=11 * 60)

result.severity      # "ok" | "info" | "watch" | "concern" | "learning"
result.summary       # the most important explanation, in words
result.findings      # every deviation with its z-score, observed and usual values
result.markers       # today vs usual for each marker, ready to chart
```

## Markers (defaults)

| Marker | Meaning | Window |
|---|---|---|
| `wake` | first movement of the morning | 04:00 to 14:00 |
| `first_kitchen` | first kitchen motion | 04:00 to 14:00 |
| `first_door` | first front-door opening (contact sensor) | 04:00 to 20:00 |
| `night_trips` | separate night-time movement episodes (events within 15 min merge) | 23:00 to 05:00 |
| `quiet_daytime` | longest stretch with no movement (counted up to *now* for today) | 08:00 to 21:00 |
| `last_activity` | last movement of the evening | 18:00 to 02:00 |
| `activity` | number of motion events | 04:00 to 24:00 |

Define your own with `FirstEvent`, `LastEvent`, `CountEpisodes`, `CountEvents` and `LongestGap`.

## How it decides

* Baselines use the **median** and a robust spread (1.4826 x median absolute deviation) so one
  unusual day barely moves them. Spreads have floors (20 min for times) so a very regular person is
  not flagged for a small lie-in.
* A marker that is still missing is only flagged if it normally happens on at least 75% of days.
* `watch` starts at 2 spreads, `concern` at 3. Quiet spells are never flagged under 90 minutes
  (`watch`) or 150 minutes (`concern`).
* Fewer than 7 days of history returns `learning` instead of guesses.

## Test

```bash
pip install pytest && pytest packages/dayrhythm/tests
```

MIT licensed. Originally written for [Hearthbeat](../../README.md), a privacy-first care companion
for older adults who live alone.
