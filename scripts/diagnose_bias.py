"""Diagnose the systematic over-forecast seen in prototype_cutoff.py.

Run from the repo root:
    python scripts/diagnose_bias.py
Error convention: forecast - actual (positive = wind over-forecast).
"""
import statistics
from collections import defaultdict
from datetime import date, time, timedelta

from prototype_cutoff import evaluate, load_actuals, load_forecast_index

CUTOFF = time(9, 20)
SAMPLE_DAY = date(2026, 1, 15)


def main():
    actuals = load_actuals()
    idx = load_forecast_index()
    rows, _, _ = evaluate(actuals, idx, CUTOFF)  # (target, forecast, actual, horizon_h)
    fc = [r[1] for r in rows]
    ac = [r[2] for r in rows]

    # 1. Shape of the relationship: correlation and a linear fit forecast = slope*actual + intercept
    slope, intercept = statistics.linear_regression(ac, fc)
    print(f"n={len(rows)}  mean actual={statistics.mean(ac):.0f}  mean forecast={statistics.mean(fc):.0f}")
    print(f"correlation={statistics.correlation(fc, ac):.3f}  fit: forecast = {slope:.3f} * actual + {intercept:.0f}")

    # 2. Time-alignment test: compare forecast at t with actual at t + shift
    print("\nTime-alignment test (minimum MAE should be at shift 0):")
    for shift in range(-180, 181, 30):
        diffs = []
        for t, f, _, _ in rows:
            a2 = actuals.get(t + timedelta(minutes=shift))
            if a2 is not None:
                diffs.append(f - a2)
        mae = statistics.mean(abs(d) for d in diffs)
        print(f"  shift {shift:+4d} min: n={len(diffs)} MAE={mae:.0f} bias={statistics.mean(diffs):+.0f}")

    # 3. Bias by actual wind level (does the offset grow with wind?)
    ordered = sorted(rows, key=lambda r: r[2])
    n = len(ordered)
    print("\nBy actual-wind quintile (low -> high):")
    for q in range(5):
        chunk = ordered[q * n // 5:(q + 1) * n // 5]
        mf = statistics.mean(r[1] for r in chunk)
        ma = statistics.mean(r[2] for r in chunk)
        mae = statistics.mean(abs(r[1] - r[2]) for r in chunk)
        print(f"  Q{q + 1}: actual~{ma:6.0f}  forecast~{mf:6.0f}  bias={mf - ma:+6.0f}  MAE={mae:5.0f}")

    # 4. Bias by hour of day (UTC)
    by_hour = defaultdict(list)
    for t, f, a, _ in rows:
        by_hour[t.hour].append(f - a)
    items = [f"{h:02d}h:{statistics.mean(v):+5.0f}" for h, v in sorted(by_hour.items())]
    print("\nMean error by hour of day (UTC):")
    for i in range(0, len(items), 6):
        print("  " + "  ".join(items[i:i + 6]))

    # 5. Is the bias present every day, or driven by a few days?
    by_day = defaultdict(list)
    for t, f, a, _ in rows:
        by_day[t.date()].append(f - a)
    day_means = {d: statistics.mean(v) for d, v in sorted(by_day.items())}
    positive = sum(1 for m in day_means.values() if m > 0)
    print(f"\nDays with positive mean error: {positive} of {len(day_means)}")
    items = [f"{d:%d}:{m:+5.0f}" for d, m in day_means.items()]
    for i in range(0, len(items), 8):
        print("  " + "  ".join(items[i:i + 8]))

    # 6. One day side by side, to eyeball timestamps and units
    print(f"\nSample day {SAMPLE_DAY} (cutoff {CUTOFF:%H:%M} UTC on D-1):")
    for t, f, a, h in rows:
        if t.date() == SAMPLE_DAY:
            print(f"  {t:%H:%M}  forecast={f:7.0f}  actual={a:7.0f}  err={f - a:+6.0f}  horizon={h:4.1f}h")


if __name__ == "__main__":
    main()