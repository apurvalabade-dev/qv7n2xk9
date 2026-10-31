"""Offline sanity check of the raw CSVs. Run: python scripts/inspect_data.py"""
import csv
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "backend" / "data" / "raw"


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load(name: str):
    with open(RAW / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    act = load("actuals_wind.csv")
    print("ACTUALS rows:", len(act), "columns:", list(act[0].keys()))
    starts = sorted(r["startTime"] for r in act)
    print("  range:", starts[0], "->", starts[-1])
    print("  unique startTime:", len(set(starts)), "(Jan alone = 1488)")
    gens = [float(r["generation"]) for r in act]
    print(f"  generation MW: min={min(gens)} median={statistics.median(gens)} max={max(gens)}")

    fc = load("forecasts_wind.csv")
    print("\nFORECASTS rows:", len(fc), "columns:", list(fc[0].keys()))
    for r in fc[:3]:
        print("  ", r)
    pubs = sorted({r["publishTime"] for r in fc})
    print("  publishTime range:", pubs[0], "->", pubs[-1], f"({len(pubs)} distinct)")

    per_target = defaultdict(set)
    horizons = []
    for r in fc:
        per_target[r["startTime"]].add(r["publishTime"])
        horizons.append((ts(r["startTime"]) - ts(r["publishTime"])).total_seconds() / 3600)
    counts = [len(v) for v in per_target.values()]
    print(f"  versions per target: min={min(counts)} median={statistics.median(counts)} max={max(counts)}")
    print(f"  horizon hours: min={min(horizons):.1f} median={statistics.median(horizons):.1f} max={max(horizons):.1f}")

    hours = Counter(ts(p).strftime("%H:%M") for p in pubs)
    print("  most common publish times (UTC):", hours.most_common(8))

    keys = Counter((r["startTime"], r["publishTime"]) for r in fc)
    print("  duplicate (startTime, publishTime) pairs:", sum(1 for v in keys.values() if v > 1))


main()
