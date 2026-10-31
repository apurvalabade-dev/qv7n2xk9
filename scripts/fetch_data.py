"""Fetch wind actuals (FUELHH) and forecasts (WINDFOR) from the Elexon Insights API.

Standard library only (no pandas/requests), so it runs on locked-down machines.
Writes raw CSVs to data/raw/. Run from the repo root:
    python scripts\\fetch_data.py
"""
import csv
import json
import statistics
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
OUT = Path(__file__).resolve().parents[1] / "data" / "raw"
CHUNK_DAYS = 3  # small chunks: stream endpoints may cap the date range


def get_json(url: str, params: dict, retries: int = 3):
    full = f"{url}?{urlencode(params)}"
    for attempt in range(retries):
        try:
            req = Request(
                full,
                headers={"Accept": "application/json", "User-Agent": "wind-forecast-challenge"},
            )
            with urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as e:
            detail = ""
            if isinstance(e, HTTPError):
                detail = e.read().decode("utf-8", "replace")[:300]
            print(f"  attempt {attempt + 1} failed: {e} {detail}")
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def as_rows(payload):
    """Stream endpoints usually return a bare list; be tolerant of {'data': [...]}."""
    if isinstance(payload, dict):
        return payload.get("data", [])
    return payload


def chunks(start: date, end: date, days: int):
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=days), end)
        yield cur, nxt
        cur = nxt


def dedupe(rows):
    seen, out = set(), []
    for r in rows:
        key = json.dumps(r, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def write_csv(path: Path, rows):
    if not rows:
        print(f"  no rows to write for {path.name}")
        return
    cols = sorted({k for r in rows for k in r})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def fetch_actuals(start: date, end: date):
    rows = []
    for a, b in chunks(start, end, CHUNK_DAYS):
        print(f"FUELHH {a} -> {b}")
        params = {
            "settlementDateFrom": a.isoformat(),
            "settlementDateTo": b.isoformat(),
            "fuelType": "WIND",
        }
        rows += as_rows(get_json(f"{BASE}/FUELHH/stream", params))
    return dedupe(rows)


def fetch_forecasts(start: date, end: date):
    rows = []
    for a, b in chunks(start, end, CHUNK_DAYS):
        print(f"WINDFOR {a} -> {b}")
        params = {
            "publishDateTimeFrom": datetime(a.year, a.month, a.day, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "publishDateTimeTo": datetime(b.year, b.month, b.day, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        }
        rows += as_rows(get_json(f"{BASE}/WINDFOR/stream", params))
    return dedupe(rows)


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def summarize(name: str, rows):
    print(f"\n{name}: {len(rows)} rows")
    if rows:
        print("columns:", list(rows[0].keys()))
        for r in rows[:3]:
            print(r)


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # Delivery days: Jan 1-31 2026.
    actuals = fetch_actuals(date(2026, 1, 1), date(2026, 2, 1))
    write_csv(OUT / "actuals_wind.csv", actuals)
    summarize("ACTUALS", actuals)

    # Forecasts for Jan 1 delivery were published in late December, so start early.
    forecasts = fetch_forecasts(date(2025, 12, 25), date(2026, 2, 1))
    write_csv(OUT / "forecasts_wind.csv", forecasts)
    summarize("FORECASTS", forecasts)

    if forecasts and "startTime" in forecasts[0] and "publishTime" in forecasts[0]:
        per_target = defaultdict(set)
        horizons_h = []
        for r in forecasts:
            per_target[r["startTime"]].add(r["publishTime"])
            horizons_h.append((parse_ts(r["startTime"]) - parse_ts(r["publishTime"])).total_seconds() / 3600)
        counts = [len(v) for v in per_target.values()]
        print("\nForecast versions per target half-hour (the publishTime trap):")
        print(f"  min={min(counts)} median={statistics.median(counts)} max={max(counts)}")
        print(f"Forecast horizon (hours ahead): min={min(horizons_h):.1f} "
              f"median={statistics.median(horizons_h):.1f} max={max(horizons_h):.1f}")


if __name__ == "__main__":
    main()