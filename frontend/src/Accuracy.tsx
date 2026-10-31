import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { AccuracyResponse, HorizonStats } from "./types";
import { AXIS, ChartBox, COLORS, fmtMW, GRID, signedMW, Stat } from "./ui";

const tipMW = (v: unknown) => `${fmtMW(Number(v))} MW`;
const horizonLabel = (h: HorizonStats) =>
  h.horizon_to_h === null ? `${h.horizon_from_h}+ h` : `${h.horizon_from_h}–${h.horizon_to_h} h`;

export default function Accuracy({ data }: { data: AccuracyResponse }) {
  const s = data.summary;
  const horizon = data.by_horizon.map((h) => ({ label: horizonLabel(h), mae: h.mae_mw, bias: h.bias_mw }));
  const days = data.by_day.map((d) => ({ day: d.day.slice(8), bias: d.bias_mw }));
  const hours = data.by_hour.map((h) => ({ hour: String(h.hour).padStart(2, "0"), mae: h.mae_mw, bias: h.bias_mw }));
  const hist = data.histogram.map((b) => ({ bin: String(b.bin_from_mw), count: b.count, from: b.bin_from_mw }));

  return (
    <div>
      <p className="headline">
        Across {s.n} hourly comparisons in January, the forecast available at {data.cutoff_utc} UTC the day before was on
        average <strong>{fmtMW(Math.abs(s.bias_mw))} MW {s.bias_mw >= 0 ? "higher" : "lower"}</strong> than actual wind output.
        Over-forecasting wind is the costly direction: a buyer trusting the forecast at face value would under-procure
        thermal power.
      </p>
      <div className="stats">
        <Stat label="Average miss (MAE)" value={`${fmtMW(s.mae_mw)} MW`} hint={s.mae_pct_of_mean === null ? undefined : `${s.mae_pct_of_mean.toFixed(1)}% of mean output`} />
        <Stat label="RMSE" value={`${fmtMW(s.rmse_mw)} MW`} hint="penalises large misses" />
        <Stat label="Average error (bias)" value={`${signedMW(s.bias_mw)} MW`} hint="forecast − actual" />
        <Stat label="95th percentile |error|" value={`${fmtMW(s.abs_error_p95_mw)} MW`} hint="1 hour in 20 is worse" />
        <Stat label="90% error range" value={`${signedMW(s.error_p05_mw)} to ${signedMW(s.error_p95_mw)} MW`} hint="in-sample, January only" />
      </div>

      <div className="grid">
        <ChartBox
          title="Error by forecast lead time"
          note="All published forecast versions, grouped by how far ahead they were made. At the cutoff the buyer typically holds forecasts 15 to 40 hours ahead."
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={horizon} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="label" {...AXIS} />
              <YAxis {...AXIS} tickFormatter={fmtMW} width={64} />
              <Tooltip formatter={tipMW} />
              <Legend />
              <Bar dataKey="mae" name="Average miss (MAE)" fill={COLORS.forecast} />
              <Bar dataKey="bias" name="Bias (forecast − actual)" fill={COLORS.over} />
            </BarChart>
          </ResponsiveContainer>
        </ChartBox>

        <ChartBox
          title="Average error per delivery day"
          note="Forecast − actual, in MW. Red days: wind came in below forecast. The misses cluster in a handful of days."
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={days} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="day" {...AXIS} interval={1} />
              <YAxis {...AXIS} tickFormatter={fmtMW} width={64} />
              <Tooltip formatter={tipMW} labelFormatter={(l) => `January ${l}`} />
              <ReferenceLine y={0} stroke="currentColor" />
              <Bar dataKey="bias" name="Average error">
                {days.map((d) => (
                  <Cell key={d.day} fill={d.bias >= 0 ? COLORS.over : COLORS.under} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartBox>

        <ChartBox title="Error by hour of day (UTC)" note="Average miss and average error for each delivery hour.">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={hours} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="hour" {...AXIS} />
              <YAxis {...AXIS} tickFormatter={fmtMW} width={64} />
              <Tooltip formatter={tipMW} labelFormatter={(l) => `${l}:00 UTC`} />
              <Legend />
              <Line dataKey="mae" name="Average miss (MAE)" stroke={COLORS.forecast} strokeWidth={2} dot={false} />
              <Line dataKey="bias" name="Average error (bias)" stroke={COLORS.over} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartBox>

        <ChartBox title="Distribution of errors" note="Count of hours by error size (500 MW bins, forecast − actual). Right of zero is over-forecast.">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={hist} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="bin" {...AXIS} interval={2} />
              <YAxis {...AXIS} width={40} />
              <Tooltip labelFormatter={(l) => `${l} MW and up (500 MW bin)`} />
              <ReferenceLine x="0" stroke="currentColor" />
              <Bar dataKey="count" name="Hours">
                {hist.map((b) => (
                  <Cell key={b.bin} fill={b.from >= 0 ? COLORS.over : COLORS.under} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartBox>
      </div>
    </div>
  );
}