"""Prototype of the core analysis: the forecast available at the day-ahead cutoff vs actual wind.

Standard library only. Run from the repo root:
    python scripts/prototype_cutoff.py

Error convention: forecast - actual. Positive = wind over-forecast
(buyer would under-procure thermal), negative = under-forecast.
All timestamps are UTC (= UK time in January).
"""
import bisect
import csv
import math
import statistics
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
UTC = timezone.utc
FIRST_DAY = date(2026, 1, 1)
LAST_DAY = date(2026, 1, 31)

CUTOFFS = [
    ("EPEX GB 60-min DA gate (default)", time(9, 20)),
    ("N2EX DA gate", time(9, 50)),
    ("EPEX GB 30-min DA gate", time(15, 30)),
]


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_csv(name: str):
    with open(RAW / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_actuals() -> dict:
    return {ts(r["startTime"]): float(r["generation"]) for r in load_csv("actuals_wind.csv")}


def load_forecast_index() -> dict:
    """startTime -> [(publishTime, MW), ...] sorted by publishTime."""
    idx = defaultdict(list)
    for r in load_csv("forecasts_wind.csv"):
        idx[ts(r["startTime"])].append((ts(r["publishTime"]), float(r["generation"])))
    for versions in idx.values():
        versions.sort()
    return idx


def latest_before(idx: dict, target: datetime, cutoff: datetime):
    """Latest forecast version for `target` published at or before `cutoff`."""
    versions = idx.get(target, [])
    pubs = [p for p, _ in versions]
    i = bisect.bisect_right(pubs, cutoff)
    return versions[i - 1] if i else None


def evaluate(actuals: dict, idx: dict, cutoff_time: time):
    """Returns (rows, counts, per_day) for all January delivery days."""
    rows = []  # (target, forecast, actual, horizon_hours)
    counts = {"half_hours": 0, "no_forecast": 0, "no_actual": 0}
    per_day = {}
    day = FIRST_DAY
    while day <= LAST_DAY:
        cutoff = datetime.combine(day - timedelta(days=1), cutoff_time, tzinfo=UTC)
        midnight = datetime.combine(day, time(0, 0), tzinfo=UTC)
        matched = 0
        for k in range(48):
            target = midnight + timedelta(minutes=30 * k)
            counts["half_hours"] += 1
            picked = latest_before(idx, target, cutoff)
            if picked is None:
                counts["no_forecast"] += 1
                continue
            if target not in actuals:
                counts["no_actual"] += 1
                continue
            pub, fc = picked
            rows.append((target, fc, actuals[target], (target - pub).total_seconds() / 3600))
            matched += 1
        per_day[day] = matched
        day += timedelta(days=1)
    return rows, counts, per_day


def percentile(sorted_vals, p):
    """Nearest-rank percentile."""
    k = max(0, math.ceil(p / 100 * len(sorted_vals)) - 1)
    return sorted_vals[k]


def metrics(rows):
    errs = [f - a for _, f, a, _ in rows]
    abs_sorted = sorted(abs(e) for e in errs)
    n = len(errs)
    mean_actual = statistics.mean(a for _, _, a, _ in rows)
    mae = statistics.mean(abs_sorted)
    return {
        "n": n,
        "mae": mae,
        "rmse": math.sqrt(statistics.mean(e * e for e in errs)),
        "bias": statistics.mean(errs),
        "p90": percentile(abs_sorted, 90),
        "p95": percentile(abs_sorted, 95),
        "mae_pct_mean": 100 * mae / mean_actual,
        "horizon_min": min(r[3] for r in rows),
        "horizon_med": statistics.median(r[3] for r in rows),
        "horizon_max": max(r[3] for r in rows),
    }


def main():
    actuals = load_actuals()
    idx = load_forecast_index()

    # Which publish times exist at all (resolves the open question from the last run).
    pub_times = sorted({p.strftime("%H:%M") for v in idx.values() for p, _ in v})
    print("Distinct publish times of day (UTC):", pub_times)
    minutes = sorted({t.minute for t in idx})
    print("Forecast startTime minutes past the hour:", minutes, "(only [0] => hourly forecasts)")

    for label, cutoff_time in CUTOFFS:
        rows, counts, per_day = evaluate(actuals, idx, cutoff_time)
        print(f"\n=== Cutoff {cutoff_time:%H:%M} UTC on D-1: {label} ===")
        print(f"half-hours in Jan: {counts['half_hours']}, "
              f"no forecast: {counts['no_forecast']}, no actual: {counts['no_actual']}, "
              f"compared: {len(rows)}")
        vals = list(per_day.values())
        print(f"compared points per day: min={min(vals)} median={statistics.median(vals)} max={max(vals)}")
        m = metrics(rows)
        print(f"MAE={m['mae']:.0f} MW ({m['mae_pct_mean']:.1f}% of mean actual)  RMSE={m['rmse']:.0f} MW")
        print(f"bias (fcst-actual)={m['bias']:+.0f} MW  |abs err| P90={m['p90']:.0f}  P95={m['p95']:.0f}")
        print(f"horizon of chosen forecasts (h): min={m['horizon_min']:.1f} "
              f"median={m['horizon_med']:.1f} max={m['horizon_max']:.1f}")


if __name__ == "__main__":
    main()