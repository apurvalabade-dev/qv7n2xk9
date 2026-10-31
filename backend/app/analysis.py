"""HTTP API: a thin layer over app.analysis. All computation lives in analysis.py.

Run locally from the backend folder:
    uvicorn app.main:app --reload --port 8000
Interactive docs: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import os
from datetime import date, time
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import analysis as an

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[2] / "data" / "raw"))
DEFAULT_CUTOFF = "09:20"

GATES = [
    {"id": "epex_60", "label": "EPEX GB 60-min day-ahead gate closure", "cutoff": "09:20"},
    {"id": "n2ex", "label": "N2EX day-ahead gate closure", "cutoff": "09:50"},
    {"id": "epex_30", "label": "EPEX GB 30-min day-ahead gate closure", "cutoff": "15:30"},
]

LIMITATIONS = [
    "One month of data (January 2026), national-level wind only.",
    "Forecasts are hourly and actuals half-hourly; comparisons are made at hourly timestamps only.",
    "Uncertainty bands use in-sample error quantiles from January itself, not a trailing window.",
    "The sizeable systematic over-forecast is observed but its cause is unverified within the data scope.",
]

app = FastAPI(title="Wind forecast accuracy API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def data():
    actuals = an.load_actuals(DATA_DIR / "actuals_wind.csv")
    index = an.load_forecast_index(DATA_DIR / "forecasts_wind.csv")
    return actuals, index


@lru_cache(maxsize=16)
def month_points(cutoff_time: time):
    actuals, index = data()
    return an.month_points(index, actuals, cutoff_time=cutoff_time)


@lru_cache(maxsize=1)
def horizon_table():
    actuals, index = data()
    return an.horizon_accuracy(index, actuals)


def parse_cutoff(value: str) -> time:
    try:
        hh, mm = value.split(":")
        return time(int(hh), int(mm))
    except ValueError:
        raise HTTPException(status_code=422, detail="cutoff must be HH:MM in UTC, e.g. 09:20")


def parse_day(value: str) -> date:
    try:
        d = date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="day must be YYYY-MM-DD")
    if not (an.JAN_FIRST <= d <= an.JAN_LAST):
        raise HTTPException(status_code=404, detail="Only delivery days in January 2026 are available")
    return d


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config():
    return {
        "default_cutoff": DEFAULT_CUTOFF,
        "gates": GATES,
        "first_day": an.JAN_FIRST.isoformat(),
        "last_day": an.JAN_LAST.isoformat(),
        "timezone": "UTC (equal to UK time in January)",
        "error_convention": "error = forecast - actual (MW); positive = wind over-forecast",
        "limitations": LIMITATIONS,
    }


@app.get("/api/delivery-day/{day}")
def delivery_day(day: str, cutoff: str = Query(DEFAULT_CUTOFF)):
    """The forecast the buyer had at the cutoff for one delivery day, vs actual output."""
    d = parse_day(day)
    ct = parse_cutoff(cutoff)
    actuals, index = data()
    month = an.summarize(month_points(ct))
    e05, e95 = month["error_p05_mw"], month["error_p95_mw"]
    points = an.day_points(index, actuals, d, ct)
    return {
        "day": d.isoformat(),
        "cutoff_utc": cutoff,
        "decision_deadline": an.cutoff_datetime(d, ct).isoformat(),
        "band": {
            "level": "90% (5th to 95th percentile of January forecast errors)",
            "error_p05_mw": e05,
            "error_p95_mw": e95,
        },
        "summary": an.summarize(points),
        "points": [
            {
                "target": p.target.isoformat(),
                "forecast_mw": p.forecast,
                "actual_mw": p.actual,
                "error_mw": p.error,
                "publish_time": p.publish_time.isoformat(),
                "horizon_h": round(p.horizon_h, 2),
                "band_low_mw": max(0.0, p.forecast - e95),
                "band_high_mw": p.forecast - e05,
            }
            for p in points
        ],
    }


@app.get("/api/accuracy")
def accuracy(cutoff: str = Query(DEFAULT_CUTOFF)):
    """Accuracy over all January delivery days for the forecasts available at the cutoff."""
    ct = parse_cutoff(cutoff)
    pts = month_points(ct)
    by_hour = an.summarize_by(pts, lambda p: p.target.hour)
    by_day = an.summarize_by(pts, lambda p: p.target.date())
    return {
        "cutoff_utc": cutoff,
        "summary": an.summarize(pts),
        "by_hour": [{"hour": h, **s} for h, s in by_hour.items()],
        "by_day": [{"day": d.isoformat(), **s} for d, s in by_day.items()],
        "histogram": an.error_histogram(pts),
        # Independent of the cutoff: every published forecast version, grouped by lead time.
        "by_horizon": horizon_table(),
        "limitations": LIMITATIONS,
    }