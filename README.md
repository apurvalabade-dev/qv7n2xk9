# UK day-ahead wind forecast review

Live app: https://qv7n2xk9.vercel.app/

A web app for a UK energy utility's day-ahead power buying team. It answers two questions about national-level wind generation:

1. **What was the latest forecast available when the buying decision had to be made?**
2. **How accurate are those forecasts, in numbers, so the error can be priced into the decision?**

Data: Elexon BMRS only. `FUELHH` (actual wind generation) and `WINDFOR` (wind forecasts), for delivery days in January 2026.

## Method and assumptions

- **Decision time.** The day-ahead decision is made on D-1 at a cutoff. Default: 09:20 UTC (EPEX GB 60-minute auction gate closure). The UI also offers 09:50 (N2EX gate closure) and 15:30 (EPEX GB 30-minute auction). In January UK time equals UTC, so there is no DST handling. These gate times are my reading of the exchanges' published schedules and should be treated as an assumption.
- **Which forecast is "the" forecast.** WINDFOR holds many versions of the forecast for each target hour (about 24 per hour in this dataset). For each target hour the app uses the latest version with `publishTime <= cutoff`. Joining on `startTime` alone would silently use forecasts published after the decision.
- **Forecasts published after their target time** (they exist in the data) are never used and are excluded from the lead-time analysis.
- **Error convention.** `error = forecast - actual` (MW). Positive means wind was over-forecast, which is the costly direction for a buyer (they under-procure thermal power).
- **Resolution.** WINDFOR is hourly and FUELHH is half-hourly. Comparisons are made at hourly timestamps only, using the actual with the same `startTime`. Nothing is interpolated.
- **Uncertainty band.** The 5th to 95th percentile of January's signed errors at the chosen cutoff, applied around each forecast. It is asymmetric and in-sample.
- **Metrics.** MAE, RMSE, bias, absolute error P50/P90/P95, error distribution, error by hour of day, by delivery day, and by forecast lead time.

## Headline results (cutoff 09:20 UTC, 744 hourly comparisons)

| Metric | Value |
|---|---|
| Mean actual wind output | 11,581 MW |
| MAE | 2,127 MW (18.4% of mean) |
| RMSE | 2,606 MW |
| Bias (forecast - actual) | +1,852 MW |
| 95th percentile of absolute error | 5,353 MW |
| 90% error range | -1,040 to +5,353 MW |

- The over-forecast is persistent: 27 of 31 days. It does not fall with shorter lead time: bias is +1,548 MW for forecasts made 0-6 h ahead and +1,811 MW for 12-24 h, while MAE improves from 2,372 MW (48 h+) to 1,768 MW (0-6 h).
- Misses cluster in a few days. On 28 January the average error was +5,329 MW with actual output averaging 5,806 MW.
- The cutoff choice matters little: MAE is 2,127 MW at 09:20, 2,107 MW at 09:50 and 1,968 MW at 15:30.

## Repository layout

backend/
app/
analysis.py Core analysis (standard library only, no I/O in the computations)
main.py FastAPI layer over analysis.py
tests/
test_analysis.py 13 unit tests
data/raw/
actuals_wind.csv FUELHH wind actuals (fetched 2026-10-29)
forecasts_wind.csv WINDFOR forecasts, all publish times 2025-12-25 to 2026-01-31
index.py Entrypoint used by Vercel
requirements.txt
Dockerfile
frontend/
src/ React + TypeScript (Vite) and Recharts
Dockerfile, nginx.conf
scripts/
fetch_data.py Downloads the raw data from the Elexon API
inspect_data.py Sanity checks on the raw CSVs
prototype_cutoff.py Early cutoff analysis prototype
diagnose_bias.py Checks behind the over-forecast finding
docker-compose.yml
vercel.json Vercel Services config (frontend + backend in one project)


## Running it

**Docker** (frontend on port 8080, API on port 8000):

docker compose up --build


Open http://localhost:8080.

**Without Docker**, in two terminals:

cd backend
python -m venv ../.venv
../.venv/Scripts/activate # Windows; on macOS/Linux: source ../.venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

cd frontend
npm install
npm run dev


Open http://localhost:5173 (Vite proxies `/api` to port 8000).

**Tests:**

cd backend
python -m unittest -v


or inside the container: `docker compose run --rm backend python -m unittest`.

**Refresh the data** (the app serves the committed CSVs and never calls Elexon at runtime):

python scripts/fetch_data.py


## API

- `GET /api/health`
- `GET /api/config`: gate times, assumptions, limitations
- `GET /api/delivery-day/{YYYY-MM-DD}?cutoff=HH:MM`: forecast available at the cutoff vs actual, with the error band
- `GET /api/accuracy?cutoff=HH:MM`: summary, by hour, by day, histogram, by lead time

Interactive docs when running locally: http://127.0.0.1:8000/docs

## Design decisions

- **Static data snapshot, not live calls.** The January dataset is small (about 22,000 forecast rows), so serving committed CSVs is faster and more reliable than calling Elexon per request, and it makes results reproducible.
- **Analysis separate from HTTP.** `analysis.py` has no framework dependency and is unit-tested, including the cutoff boundary (a version published exactly at the cutoff is included), the error sign and the exclusion of forecasts published after their target.
- **Standard library only for the analysis.** Keeps the Docker image small and the logic easy to review.
- **Deployment.** One Vercel project with two services (Vite frontend, FastAPI backend) behind one domain; `/api/*` routes to the backend.

## Limitations

- One month of data (January 2026) and national-level wind only. Hourly errors within a day are strongly correlated, so the effective sample is closer to 31 days than to 744 points.
- The error band and percentiles are in-sample (computed on the same January data they are shown against). A production tool would use a trailing window.
- The systematic over-forecast is observed, but its cause is not verified. Possible explanations (for example, differences in what the two datasets measure, or curtailment) cannot be tested using only these two datasets.
- Percent errors are unstable on low-wind days, so MW errors are the headline.
- No price data is included, so the app does not say what a given error costs.

## AI tool use

AI tools were used to build this project. I used an AI assistant (Claude, by Anthropic) for planning, writing code, tests and Docker/Vercel configuration, and for debugging. I ran and tested the code and checked the numbers against the raw data myself.
