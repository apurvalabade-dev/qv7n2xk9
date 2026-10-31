import math
import unittest
from datetime import date, datetime, time, timezone

from app import analysis as a

UTC = timezone.utc


def dt(day: int, hh: int, mm: int = 0) -> datetime:
    return datetime(2026, 1, day, hh, mm, tzinfo=UTC)


class CutoffSelectionTests(unittest.TestCase):
    def setUp(self):
        self.target = dt(2, 12)
        self.index = {
            self.target: [(dt(1, 7, 30), 100.0), (dt(1, 9, 30), 200.0), (dt(1, 11, 30), 300.0)]
        }

    def test_picks_latest_version_published_before_cutoff(self):
        self.assertEqual(a.latest_forecast_before(self.index, self.target, dt(1, 9, 20)), (dt(1, 7, 30), 100.0))
        self.assertEqual(a.latest_forecast_before(self.index, self.target, dt(1, 9, 50)), (dt(1, 9, 30), 200.0))

    def test_version_published_exactly_at_cutoff_is_included(self):
        self.assertEqual(a.latest_forecast_before(self.index, self.target, dt(1, 9, 30)), (dt(1, 9, 30), 200.0))

    def test_returns_none_when_nothing_published_yet(self):
        self.assertIsNone(a.latest_forecast_before(self.index, self.target, dt(1, 7, 0)))

    def test_day_points_use_decision_time_forecast_not_the_latest(self):
        pts = a.day_points(self.index, {self.target: 90.0}, date(2026, 1, 2), time(9, 20))
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts[0].forecast, 100.0)
        self.assertEqual(pts[0].publish_time, dt(1, 7, 30))
        self.assertEqual(pts[0].error, 10.0)
        self.assertAlmostEqual(pts[0].horizon_h, 28.5)

    def test_missing_actual_gives_no_error(self):
        pts = a.day_points(self.index, {}, date(2026, 1, 2), time(9, 20))
        self.assertIsNone(pts[0].error)


class StatsTests(unittest.TestCase):
    @staticmethod
    def pts(errors, actual=1000.0):
        return [a.Point(dt(1, 0), actual + e, actual, dt(1, 0)) for e in errors]

    def test_error_sign_is_forecast_minus_actual(self):
        self.assertEqual(a.Point(dt(1, 0), 120.0, 100.0, dt(1, 0)).error, 20.0)

    def test_summarize_known_values(self):
        s = a.summarize(self.pts([100, -100, 300]))
        self.assertEqual(s["n"], 3)
        self.assertAlmostEqual(s["bias_mw"], 100.0)
        self.assertAlmostEqual(s["mae_mw"], 500 / 3)
        self.assertAlmostEqual(s["rmse_mw"], math.sqrt(110000 / 3))
        self.assertAlmostEqual(s["mae_pct_of_mean"], 100 * (500 / 3) / 1000)

    def test_summarize_empty(self):
        self.assertEqual(a.summarize([]), {"n": 0})

    def test_summarize_ignores_points_without_actual(self):
        pts = self.pts([50]) + [a.Point(dt(1, 1), 999.0, None, dt(1, 0))]
        self.assertEqual(a.summarize(pts)["n"], 1)

    def test_percentile_nearest_rank(self):
        vals = [float(i) for i in range(1, 11)]
        self.assertEqual(a.percentile(vals, 50), 5.0)
        self.assertEqual(a.percentile(vals, 90), 9.0)
        self.assertEqual(a.percentile(vals, 95), 10.0)
        self.assertEqual(a.percentile(vals, 0), 1.0)

    def test_histogram_bins_negative_errors_correctly(self):
        hist = a.error_histogram(self.pts([10, 510, -10]), bin_mw=500)
        self.assertEqual([h["bin_from_mw"] for h in hist], [-500, 0, 500])
        self.assertTrue(all(h["count"] == 1 for h in hist))


class HorizonTests(unittest.TestCase):
    def test_bucket_edges(self):
        self.assertIsNone(a.horizon_bucket_index(-0.1))
        self.assertEqual(a.horizon_bucket_index(0), 0)
        self.assertEqual(a.horizon_bucket_index(5.99), 0)
        self.assertEqual(a.horizon_bucket_index(6), 1)
        self.assertEqual(a.horizon_bucket_index(12), 2)
        self.assertEqual(a.horizon_bucket_index(47.9), 4)
        self.assertEqual(a.horizon_bucket_index(48), 5)
        self.assertEqual(a.horizon_bucket_index(200), 5)

    def test_forecasts_published_after_target_are_excluded(self):
        target = dt(2, 12)
        index = {target: [(dt(1, 12), 150.0), (dt(2, 13), 999.0)]}  # 2nd is published 1h after target
        res = a.horizon_accuracy(index, {target: 100.0}, date(2026, 1, 2), date(2026, 1, 2))
        self.assertEqual(len(res), 1)
        self.assertEqual((res[0]["horizon_from_h"], res[0]["horizon_to_h"]), (24, 36))
        self.assertEqual(res[0]["n"], 1)
        self.assertAlmostEqual(res[0]["bias_mw"], 50.0)


if __name__ == "__main__":
    unittest.main()