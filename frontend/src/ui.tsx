import type { ReactNode } from "react";

export const COLORS = {
  forecast: "#3b82f6",
  actual: "#f97316",
  over: "#ef4444", // over-forecast: costly direction for a buyer
  under: "#10b981",
};

export const AXIS = { tick: { fontSize: 12, fill: "currentColor" }, stroke: "currentColor" };
export const GRID = { stroke: "currentColor", strokeOpacity: 0.15 };

export const fmtMW = (x: number) => Math.round(x).toLocaleString("en-GB");
export const signedMW = (x: number) => `${x > 0 ? "+" : x < 0 ? "−" : ""}${fmtMW(Math.abs(x))}`;
export const fmtTime = (iso: string) => `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;

export function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

export function ChartBox({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="chart-box">
      <h3>{title}</h3>
      {note && <p className="note">{note}</p>}
      <div className="chart">{children}</div>
    </section>
  );
}

export function Status({ loading, error }: { loading: boolean; error: string | null }) {
  if (loading) return <p className="status">Loading…</p>;
  if (error) return <p className="status error">Could not load data ({error}). Is the API running on port 8000?</p>;
  return null;
}