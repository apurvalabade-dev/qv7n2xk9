export interface Gate { id: string; label: string; cutoff: string }

export interface Config {
  default_cutoff: string;
  gates: Gate[];
  first_day: string;
  last_day: string;
  timezone: string;
  error_convention: string;
  limitations: string[];
}

export interface Stats {
  n: number;
  mean_actual_mw: number;
  mae_mw: number;
  mae_pct_of_mean: number | null;
  rmse_mw: number;
  bias_mw: number;
  abs_error_p50_mw: number;
  abs_error_p90_mw: number;
  abs_error_p95_mw: number;
  error_p05_mw: number;
  error_p95_mw: number;
}

export interface DayPoint {
  target: string;
  forecast_mw: number;
  actual_mw: number | null;
  error_mw: number | null;
  publish_time: string;
  horizon_h: number;
  band_low_mw: number;
  band_high_mw: number;
}

export interface DeliveryDayResponse {
  day: string;
  cutoff_utc: string;
  decision_deadline: string;
  band: { level: string; error_p05_mw: number; error_p95_mw: number };
  summary: Stats;
  points: DayPoint[];
}

export interface HourStats extends Stats { hour: number }
export interface DayStats extends Stats { day: string }
export interface HorizonStats extends Stats { horizon_from_h: number; horizon_to_h: number | null }
export interface HistBin { bin_from_mw: number; bin_to_mw: number; count: number }

export interface AccuracyResponse {
  cutoff_utc: string;
  summary: Stats;
  by_hour: HourStats[];
  by_day: DayStats[];
  histogram: HistBin[];
  by_horizon: HorizonStats[];
  limitations: string[];
}