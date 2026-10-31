import { useState } from "react";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApi } from "./api";
import type { DayStats, DeliveryDayResponse } from "./types";
import { AXIS, ChartBox, COLORS, fmtMW, fmtTime, GRID, signedMW, Stat, Status } from "./ui";

interface Row {
  hour: string;
  forecast: number;
  actual: number | null;
  bandBase: number;
  bandSpan: number;
  low: number;
  high: number;
}

function DayTip({ active, payload }: { active?: boolean; payload?: ReadonlyArray<{ payload: Row }> }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return (
    <div className="tip">
      <strong>{r.hour} UTC</strong>
      <div>Forecast: {fmtMW(r.forecast)} MW</div>
      <div>Actual: {r.actual === null ? "n/a" : `${fmtMW(r.actual)} MW`}</div>
      {r.actual !== null && <div>Error: {signedMW(r.forecast - r.actual)} MW</div>}
      <div>
        90% range: {fmtMW(r.low)} to {fmtMW(r.high)} MW
      </div>
    </div>
  );
}

interface Props {
  cutoff: string;
  first: string;
  last: string;
  byDay?: DayStats[];
}

export default function DeliveryDay({ cutoff, first, last, byDay }: Props) {
  const [day, setDay] = useState("2026-01-15");
  const { data, error, loading } = useApi<DeliveryDayResponse>(`/api/delivery-day/${day}?cutoff=${cutoff}`);

  const worst = byDay?.length ? byDay.reduce((a, b) => (b.mae_mw > a.mae_mw ? b : a)) : null;
  const best = byDay?.length ? byDay.reduce((a, b) => (b.mae_mw < a.mae_mw ? b : a)) : null;

  let body = null;
  if (data) {
    const rows: Row[] = data.points.map((p) => ({
      hour: p.target.slice(11, 16),
      forecast: p.forecast_mw,
      actual: p.actual_mw,
      bandBase: p.band_low_mw,
      bandSpan: p.band_high_mw - p.band_low_mw,
      low: p.band_low_mw,
      high: p.band_high_mw,
    }));
    const errs = data.points.flatMap((p) => (p.error_mw === null ? [] : [p.error_mw]));
    const net = errs.reduce((a, b) => a + b, 0);
    const maxOver = errs.length ? Math.max(...errs) : 0;
    const pubs = [...new Set(data.points.map((p) => fmtTime(p.publish_time)))];

    body = (
      <>
        <p className="note">
          Decision deadline: <strong>{fmtTime(data.decision_deadline)}</strong>. Forecast version(s) used, by publish time:{" "}
          {pubs.join(", ")}.
        </p>
        <div className="stats">
          <Stat label="Average miss (MAE)" value={`${fmtMW(data.summary.mae_mw)} MW`} />
          <Stat label="Average error" value={`${signedMW(data.summary.bias_mw)} MW`} hint="positive = less wind than forecast" />
          <Stat label="Net error over the day" value={`${signedMW(net)} MWh`} hint="sum of hourly errors" />
          <Stat label="Worst over-forecast hour" value={`${signedMW(maxOver)} MW`} />
        </div>
        <ChartBox
          title="Forecast available at the cutoff vs actual wind output"
          note={`Wind output in MW, by hour of the delivery day. Shaded area: 90% error range from January's errors (${signedMW(
            data.band.error_p05_mw,
          )} to ${signedMW(data.band.error_p95_mw)} MW around the forecast, in-sample).`}
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="hour" {...AXIS} />
              <YAxis {...AXIS} tickFormatter={fmtMW} width={64} />
              <Tooltip content={<DayTip />} />
              <Legend />
              <Area dataKey="bandBase" stackId="band" stroke="none" fill="transparent" legendType="none" isAnimationActive={false} />
              <Area
                dataKey="bandSpan"
                stackId="band"
                stroke="none"
                fill={COLORS.forecast}
                fillOpacity={0.15}
                name="90% error range"
                isAnimationActive={false}
              />
              <Line dataKey="forecast" name="Forecast at cutoff" stroke={COLORS.forecast} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line dataKey="actual" name="Actual" stroke={COLORS.actual} strokeWidth={2} dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </ChartBox>
      </>
    );
  }

  return (
    <div>
      <div className="controls">
        <label>
          Delivery day
          <input
            type="date"
            value={day}
            min={first}
            max={last}
            onChange={(e) => e.target.value && setDay(e.target.value)}
          />
        </label>
        {worst && <button onClick={() => setDay(worst.day)}>Largest miss: {worst.day}</button>}
        {best && <button onClick={() => setDay(best.day)}>Smallest miss: {best.day}</button>}
      </div>
      <Status loading={loading} error={error} />
      {body}
    </div>
  );
}