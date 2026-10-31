"""Core analysis: wind forecasts as available at the day-ahead cutoff vs actual output.

Standard library only; the computation functions do no I/O, so they are easy to unit test.

Conventions
- All timestamps are UTC (equal to UK time in January, so no DST handling is needed).
- error = forecast - actual, in MW. Positive error = wind over-forecast, which is the
  costly direction for a buyer (they under-procure thermal generation).
- Forecasts are hourly; actuals are half-hourly. Comparisons are made only at timestamps
  where a forecast exists, using the actual with the same startTime (no interpolation).
"""
from __future__ import annotations

import bisect
import csv
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable

UTC = timezone.utc
JAN_FIRST = date(2026, 1, 1)
JAN_LAST = date(2026, 1, 31)
DEFAULT_CUTOFF = time(9, 20)  # EPEX GB 60-min day-ahead gate closure on D-1, UTC
# Horizon buckets in hours: [0,6) [6,12) [12,24) [24,36) [36,48) [48,inf)
HORIZON_EDGES_H = (0, 6, 12, 24, 36, 48)

# target startTime -> [(publishTime, MW), ...] sorted by publishTime
ForecastIndex = dict[datetime, list[tuple[datetime, float]]]


@dataclass(frozen=True)
class Point:
    target: datetime
    forecast: float
    actual: float | None
    publish_time: datetime

    @property
    def horizon_h(self) -> float:
        return (self.target - self.publish_time).total_seconds() / 3600

    @property
    def error(self) -> float | None:
        return None if self.actual is None else self.forecast - self.actual


# ---------------------------------------------------------------- loading

def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_actuals(path: Path) -> dict[datetime, float]:
    with open(path, newline="", encoding="utf-8") as f:
        return {parse_ts(r["startTime"]): float(r["generation"]) for r in csv.DictReader(f)}


def load_forecast_index(path: Path) -> ForecastIndex:
    idx: dict[datetime, list[tuple[datetime, float]]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            idx[parse_ts(r["startTime"])].append((parse_ts(r["publishTime"]), float(r["generation"])))
    for versions in idx.values():
        versions.sort()
    return dict(idx)


# ---------------------------------------------------------------- cutoff selection

def cutoff_datetime(delivery_day: date, cutoff_time: time) -> datetime:
    """Decision deadline: cutoff_time (UTC) on the day before delivery."""
    return datetime.combine(delivery_day - timedelta(days=1), cutoff_time, tzinfo=UTC)


def latest_forecast_before(index: ForecastIndex, target: datetime, cutoff: datetime):
    """Latest version of the forecast for `target` published at or before `cutoff`.

    Returns (publish_time, MW) or None if nothing had been published yet.
    """
    versions = index.get(target, [])
    pubs = [p for p, _ in versions]
    i = bisect.bisect_right(pubs, cutoff)
    return versions[i - 1] if i else None


def day_points(index: ForecastIndex, actuals: dict[datetime, float], delivery_day: date,
               cutoff_time: time = DEFAULT_CUTOFF) -> list[Point]:
    """For one delivery day: the forecast the buyer had at the cutoff, with the actual."""
    cutoff = cutoff_datetime(delivery_day, cutoff_time)
    midnight = datetime.combine(delivery_day, time(0, 0), tzinfo=UTC)
    points = []
    for k in range(48):
        target = midnight + timedelta(minutes=30 * k)
        picked = latest_forecast_before(index, target, cutoff)
        if picked is None:
            continue  # no forecast at this time (e.g. the half-hour between hourly forecasts)
        publish, mw = picked
        points.append(Point(target, mw, actuals.get(target), publish))
    return points


def month_points(index: ForecastIndex, actuals: dict[datetime, float],
                 first_day: date = JAN_FIRST, last_day: date = JAN_LAST,
                 cutoff_time: time = DEFAULT_CUTOFF) -> list[Point]:
    points: list[Point] = []
    day = first_day
    while day <= last_day:
        points.extend(day_points(index, actuals, day, cutoff_time))
        day += timedelta(days=1)
    return points


# ---------------------------------------------------------------- statistics

def percentile(sorted_vals: list[float], p: float) -> float:
    """Nearest-rank percentile of an already sorted list."""
    if not sorted_vals:
        raise ValueError("empty data")
    k = max(0, math.ceil(p / 100 * len(sorted_vals)) - 1)
    return sorted_vals[k]


def summarize(points: Iterable[Point]) -> dict:
    """Accuracy metrics over points that have an actual. Errors are forecast - actual (MW)."""
    scored = [p for p in points if p.actual is not None]
    if not scored:
        return {"n": 0}
    errs = [p.forecast - p.actual for p in scored]
    abs_sorted = sorted(abs(e) for e in errs)
    signed_sorted = sorted(errs)
    mean_actual = statistics.fmean(p.actual for p in scored)
    mae = statistics.fmean(abs_sorted)
    return {
        "n": len(errs),
        "mean_actual_mw": mean_actual,
        "mae_mw": mae,
        "mae_pct_of_mean": 100 * mae / mean_actual if mean_actual else None,
        "rmse_mw": math.sqrt(statistics.fmean(e * e for e in errs)),
        "bias_mw": statistics.fmean(errs),
        "abs_error_p50_mw": percentile(abs_sorted, 50),
        "abs_error_p90_mw": percentile(abs_sorted, 90),
        "abs_error_p95_mw": percentile(abs_sorted, 95),
        "error_p05_mw": percentile(signed_sorted, 5),
        "error_p95_mw": percentile(signed_sorted, 95),
    }


def summarize_by(points: Iterable[Point], key: Callable[[Point], object]) -> dict:
    groups: dict[object, list[Point]] = defaultdict(list)
    for p in points:
        groups[key(p)].append(p)
    return {k: summarize(v) for k, v in sorted(groups.items())}


def error_histogram(points: Iterable[Point], bin_mw: int = 500) -> list[dict]:
    counts = Counter(
        math.floor(p.error / bin_mw) * bin_mw for p in points if p.error is not None
    )
    return [
        {"bin_from_mw": b, "bin_to_mw": b + bin_mw, "count": counts[b]}
        for b in sorted(counts)
    ]


# ---------------------------------------------------------------- accuracy by horizon

def horizon_bucket_index(horizon_h: float) -> int | None:
    """Bucket index for a horizon in hours; None for forecasts published after their target."""
    if horizon_h < HORIZON_EDGES_H[0]:
        return None
    return bisect.bisect_right(HORIZON_EDGES_H, horizon_h) - 1


def horizon_accuracy(index: ForecastIndex, actuals: dict[datetime, float],
                     first_day: date = JAN_FIRST, last_day: date = JAN_LAST) -> list[dict]:
    """Accuracy of ALL published forecast versions, grouped by how far ahead they were made."""
    start = datetime.combine(first_day, time(0, 0), tzinfo=UTC)
    end = datetime.combine(last_day + timedelta(days=1), time(0, 0), tzinfo=UTC)
    groups: dict[int, list[Point]] = defaultdict(list)
    for target, versions in index.items():
        if not (start <= target < end):
            continue
        actual = actuals.get(target)
        for publish, mw in versions:
            b = horizon_bucket_index((target - publish).total_seconds() / 3600)
            if b is not None:
                groups[b].append(Point(target, mw, actual, publish))
    out = []
    for b in sorted(groups):
        hi = HORIZON_EDGES_H[b + 1] if b + 1 < len(HORIZON_EDGES_H) else None
        out.append({"horizon_from_h": HORIZON_EDGES_H[b], "horizon_to_h": hi, **summarize(groups[b])})
    return out