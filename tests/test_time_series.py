"""Unit tests for Time Series Analysis and Forecasting module."""
import unittest
import math
import numpy as np

from statcraft.time_series import (
    clean_series,
    compute_accuracy_measures,
    trend_analysis,
    decomposition,
    moving_average,
    single_exp_smoothing,
    double_exp_smoothing,
    autocorrelation,
    partial_autocorrelation,
    compute_differences,
    compute_lag,
)
from statcraft.time_series_report import (
    generate_trend_analysis_report,
    generate_decomposition_report,
    generate_moving_average_report,
    generate_single_exp_smoothing_report,
    generate_double_exp_smoothing_report,
    generate_autocorrelation_report,
    generate_partial_autocorrelation_report,
)
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter
from statcraft.recipes import columns


class TestTimeSeriesCore(unittest.TestCase):
    """Test pure numerical algorithms, formulas, and forecasting accuracy."""

    def setUp(self):
        # Known synthetic trend and seasonal series
        # Trend: 10 + 2*t
        self.trend_series = [10.0 + 2.0 * t for t in range(1, 21)]
        self.quad_series = [5.0 + 1.5 * t + 0.1 * (t ** 2) for t in range(1, 21)]
        self.exp_series = [10.0 * (1.05 ** t) for t in range(1, 21)]

        # 4-quarter seasonal data (3 full cycles = 12 observations)
        self.seasonal_mult = [
            100.0 * 0.8, 105.0 * 1.2, 110.0 * 1.1, 115.0 * 0.9,
            120.0 * 0.8, 125.0 * 1.2, 130.0 * 1.1, 135.0 * 0.9,
            140.0 * 0.8, 145.0 * 1.2, 150.0 * 1.1, 155.0 * 0.9,
        ]

    def test_clean_series_and_accuracy_measures(self):
        raw = [10, "bad", None, float("nan"), 20, 30]
        cleaned = clean_series(raw)
        np.testing.assert_array_equal(cleaned, [10.0, 20.0, 30.0])

        actual = np.array([100.0, 200.0, 300.0])
        fitted = np.array([110.0, 190.0, 300.0])
        acc = compute_accuracy_measures(actual, fitted)
        # diffs: +10, -10, 0
        # MAD = 20 / 3 = 6.6667
        # MSD = (100 + 100 + 0) / 3 = 66.6667
        # MAPE = (10% + 5% + 0%) / 3 = 5%
        self.assertAlmostEqual(acc["mad"], 20.0 / 3.0, places=4)
        self.assertAlmostEqual(acc["msd"], 200.0 / 3.0, places=4)
        self.assertAlmostEqual(acc["mape"], 5.0, places=4)

    def test_trend_linear(self):
        res = trend_analysis(self.trend_series, model="linear", forecasts=5)
        self.assertEqual(res["n"], 20)
        self.assertAlmostEqual(res["parameters"]["b0"], 10.0, places=4)
        self.assertAlmostEqual(res["parameters"]["b1"], 2.0, places=4)
        self.assertAlmostEqual(res["accuracy"]["msd"], 0.0, places=4)
        self.assertAlmostEqual(res["accuracy"]["mape"], 0.0, places=4)
        self.assertEqual(len(res["forecasts"]), 5)
        # Period 21: 10 + 2*21 = 52.0
        self.assertAlmostEqual(res["forecasts"][0]["forecast"], 52.0, places=3)
        self.assertAlmostEqual(res["forecasts"][4]["forecast"], 60.0, places=3)

    def test_trend_quadratic(self):
        res = trend_analysis(self.quad_series, model="quadratic", forecasts=3)
        self.assertEqual(res["n"], 20)
        self.assertAlmostEqual(res["parameters"]["b0"], 5.0, places=3)
        self.assertAlmostEqual(res["parameters"]["b1"], 1.5, places=3)
        self.assertAlmostEqual(res["parameters"]["b2"], 0.1, places=3)
        self.assertAlmostEqual(res["accuracy"]["msd"], 0.0, places=4)
        # Period 21: 5 + 1.5*21 + 0.1*441 = 5 + 31.5 + 44.1 = 80.6
        self.assertAlmostEqual(res["forecasts"][0]["forecast"], 80.6, places=2)

    def test_trend_exponential(self):
        res = trend_analysis(self.exp_series, model="exponential", forecasts=2)
        self.assertEqual(res["n"], 20)
        self.assertAlmostEqual(res["parameters"]["b0"], 10.0, places=3)
        self.assertAlmostEqual(res["parameters"]["b1"], 1.05, places=3)
        self.assertAlmostEqual(res["accuracy"]["mape"], 0.0, places=3)

    def test_trend_scurve(self):
        # Pearl-Reed / logistic curve
        t = np.arange(1, 21)
        s_curve = 100.0 / (1.0 + np.exp(-0.4 * (t - 10.0)))
        res = trend_analysis(s_curve.tolist(), model="scurve", forecasts=3)
        self.assertEqual(res["n"], 20)
        self.assertTrue(res["accuracy"]["mape"] < 5.0)
        self.assertEqual(len(res["forecasts"]), 3)

    def test_decomposition_multiplicative(self):
        res = decomposition(self.seasonal_mult, season_length=4, model="multiplicative", forecasts=4)
        self.assertEqual(res["season_length"], 4)
        self.assertEqual(len(res["seasonal_indices"]), 4)
        # Seasonal indices should sum to 4.0
        self.assertAlmostEqual(sum(res["seasonal_indices"]), 4.0, places=3)
        # Quarter 1 was multiplied by 0.8, quarter 2 by 1.2
        self.assertAlmostEqual(res["seasonal_indices"][0], 0.8, delta=0.05)
        self.assertAlmostEqual(res["seasonal_indices"][1], 1.2, delta=0.05)
        self.assertEqual(len(res["forecasts"]), 4)
        self.assertTrue(all(f["forecast"] > 0 for f in res["forecasts"]))

    def test_decomposition_additive(self):
        data_add = [
            100 + (-5), 105 + 10, 110 + 5, 115 + (-10),
            120 + (-5), 125 + 10, 130 + 5, 135 + (-10),
            140 + (-5), 145 + 10, 150 + 5, 155 + (-10),
        ]
        res = decomposition(data_add, season_length=4, model="additive", forecasts=4)
        self.assertEqual(res["season_length"], 4)
        # Additive indices sum to 0.0
        self.assertAlmostEqual(sum(res["seasonal_indices"]), 0.0, places=3)
        self.assertEqual(len(res["forecasts"]), 4)

    def test_moving_average_uncentered_and_centered(self):
        data = [10, 12, 14, 16, 18, 20]
        # Uncentered length 3: fits start at period 4 (avg of 10, 12, 14 = 12)
        res_u = moving_average(data, ma_length=3, center=False, forecasts=2)
        self.assertIsNone(res_u["fitted"][0])
        self.assertIsNone(res_u["fitted"][1])
        self.assertIsNone(res_u["fitted"][2])
        self.assertAlmostEqual(res_u["fitted"][3], 12.0)
        self.assertAlmostEqual(res_u["fitted"][4], 14.0)
        self.assertAlmostEqual(res_u["fitted"][5], 16.0)
        # Forecast is flat average of last 3: (16+18+20)/3 = 18.0
        self.assertEqual(len(res_u["forecasts"]), 2)
        self.assertAlmostEqual(res_u["forecasts"][0]["forecast"], 18.0)
        self.assertAlmostEqual(res_u["forecasts"][1]["forecast"], 18.0)

        # Centered length 3:
        res_c = moving_average(data, ma_length=3, center=True, forecasts=0)
        self.assertIsNone(res_c["fitted"][0])
        self.assertAlmostEqual(res_c["fitted"][1], 12.0)

    def test_single_exp_smoothing(self):
        data = [100, 102, 104, 108, 107, 110, 115]
        res_custom = single_exp_smoothing(data, alpha=0.3, forecasts=3)
        self.assertEqual(res_custom["alpha"], 0.3)
        self.assertEqual(len(res_custom["fitted"]), 7)
        self.assertEqual(len(res_custom["forecasts"]), 3)
        # Flat forecast
        self.assertEqual(res_custom["forecasts"][0]["forecast"], res_custom["forecasts"][1]["forecast"])

        # Optimal alpha
        res_opt = single_exp_smoothing(data, alpha=None, forecasts=2)
        self.assertTrue(0.0 < res_opt["alpha"] < 1.0)
        self.assertTrue(res_opt["is_optimal"])

    def test_double_exp_smoothing(self):
        data = [10, 12, 15, 17, 20, 22, 25, 27]
        res_custom = double_exp_smoothing(data, alpha=0.2, gamma=0.2, forecasts=3)
        self.assertEqual(res_custom["alpha"], 0.2)
        self.assertEqual(res_custom["gamma"], 0.2)
        self.assertEqual(len(res_custom["forecasts"]), 3)
        # Forecasts have positive slope
        self.assertTrue(res_custom["forecasts"][1]["forecast"] > res_custom["forecasts"][0]["forecast"])

        # Optimal
        res_opt = double_exp_smoothing(data, alpha=None, gamma=None, forecasts=2)
        self.assertTrue(0.0 < res_opt["alpha"] <= 1.0)
        self.assertTrue(0.0 < res_opt["gamma"] <= 1.0)
        self.assertTrue(res_opt["is_optimal"])

    def test_autocorrelation_and_partial_autocorrelation(self):
        # Sine wave with period 4: high lag 4 autocorrelation
        t = np.arange(40)
        sine_series = np.sin(2 * np.pi * t / 4.0)
        acf = autocorrelation(sine_series.tolist(), max_lags=8)
        self.assertEqual(len(acf["lags"]), 8)
        self.assertTrue(acf["sig_limit"] > 0)
        # Lag 4 autocorrelation should be close to 0.9 (since sample ACF = (40-4)/40 = 0.9)
        self.assertAlmostEqual(acf["lags"][3]["correlation"], 0.9, places=2)

        pacf = partial_autocorrelation(sine_series.tolist(), max_lags=6)
        self.assertEqual(len(pacf["lags"]), 6)
        self.assertTrue(pacf["sig_limit"] > 0)

    def test_differences_and_lag(self):
        data = [10, 15, 22, 30]
        diffs = compute_differences(data, lag=1)
        self.assertEqual(diffs, [None, 5.0, 7.0, 8.0])

        lagged = compute_lag(data, lag=1)
        self.assertEqual(lagged, [None, 10.0, 15.0, 22.0])

    def test_report_generators(self):
        res_t = trend_analysis(self.trend_series, model="linear", forecasts=2)
        rep_t = generate_trend_analysis_report(res_t)
        self.assertIn("Trend Analysis", rep_t)
        self.assertIn("Accuracy Measures", rep_t)
        self.assertIn("Forecasts", rep_t)

        res_d = decomposition(self.seasonal_mult, season_length=4, model="multiplicative", forecasts=2)
        rep_d = generate_decomposition_report(res_d)
        self.assertIn("Decomposition", rep_d)
        self.assertIn("Seasonal Indices", rep_d)

        res_ma = moving_average(self.trend_series, ma_length=3, forecasts=2)
        rep_ma = generate_moving_average_report(res_ma)
        self.assertIn("Moving Average", rep_ma)

        res_ses = single_exp_smoothing(self.trend_series, alpha=0.2, forecasts=2)
        rep_ses = generate_single_exp_smoothing_report(res_ses)
        self.assertIn("Single Exponential Smoothing", rep_ses)

        res_des = double_exp_smoothing(self.trend_series, alpha=0.2, gamma=0.2, forecasts=2)
        rep_des = generate_double_exp_smoothing_report(res_des)
        self.assertIn("Double Exponential Smoothing", rep_des)

        res_acf = autocorrelation(self.trend_series, max_lags=4)
        rep_acf = generate_autocorrelation_report(res_acf)
        self.assertIn("Autocorrelation Function", rep_acf)

        res_pacf = partial_autocorrelation(self.trend_series, max_lags=4)
        rep_pacf = generate_partial_autocorrelation_report(res_pacf)
        self.assertIn("Partial Autocorrelation Function", rep_pacf)


class TestTimeSeriesPresenterAndRecipes(unittest.TestCase):
    """Test presenter execution, worksheet column storage, recipe serialization, and rerun."""

    def setUp(self):
        self.ws = Worksheet("TimeSeriesWS")
        # Add sample series column
        series_data = [100.0, 105.0, 110.0, 115.0, 120.0, 125.0, 130.0, 135.0, 140.0, 145.0, 150.0, 155.0]
        self.ws.columns.append(Column("Sales", "number", series_data))
        self.presenter = Presenter()
        self.presenter.worksheet = self.ws

    def test_presenter_trend_analysis_and_storage(self):
        settings = {
            "series_index": 0,
            "series_name": "Sales",
            "model": "linear",
            "forecasts": 3,
            "store_fits": True,
            "store_residuals": True,
            "store_forecasts": True,
        }
        entry = self.presenter.trend_analysis(settings=settings)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["result"]["analysis"], "trend_analysis")
        # Verify columns stored back into worksheet
        col_names = [c.name for c in self.ws.columns]
        self.assertIn("FITS_Sales", col_names)
        self.assertIn("RESI_Sales", col_names)
        self.assertIn("FORE_Sales", col_names)

        # Recipe verification
        rec = entry["recipe"]
        self.assertEqual(rec["action"], "trend_analysis")
        dep_cols = columns(rec)
        self.assertEqual(dep_cols, [0])

    def test_presenter_decomposition(self):
        settings = {
            "series_index": 0,
            "series_name": "Sales",
            "season_length": 4,
            "model": "multiplicative",
            "forecasts": 4,
            "store_fits": True,
            "store_residuals": False,
            "store_forecasts": False,
        }
        entry = self.presenter.decomposition(settings=settings)
        self.assertEqual(entry["result"]["analysis"], "decomposition")
        self.assertEqual(columns(entry["recipe"]), [0])

    def test_presenter_moving_average(self):
        settings = {
            "series_index": 0,
            "series_name": "Sales",
            "ma_length": 3,
            "center": False,
            "forecasts": 2,
            "store_fits": True,
        }
        entry = self.presenter.moving_average(settings=settings)
        self.assertEqual(entry["result"]["analysis"], "moving_average")
        self.assertEqual(columns(entry["recipe"]), [0])

    def test_presenter_single_exp_smoothing(self):
        settings = {
            "series_index": 0,
            "series_name": "Sales",
            "alpha": 0.25,
            "forecasts": 2,
            "store_fits": True,
        }
        entry = self.presenter.single_exp_smoothing(settings=settings)
        self.assertEqual(entry["result"]["analysis"], "single_exp_smoothing")
        self.assertEqual(columns(entry["recipe"]), [0])

    def test_presenter_double_exp_smoothing(self):
        settings = {
            "series_index": 0,
            "series_name": "Sales",
            "alpha": 0.2,
            "gamma": 0.2,
            "forecasts": 2,
        }
        entry = self.presenter.double_exp_smoothing(settings=settings)
        self.assertEqual(entry["result"]["analysis"], "double_exp_smoothing")
        self.assertEqual(columns(entry["recipe"]), [0])

    def test_presenter_autocorrelation(self):
        settings = {
            "series_index": 0,
            "series_name": "Sales",
            "max_lags": 4,
        }
        entry = self.presenter.autocorrelation(settings=settings)
        self.assertEqual(entry["result"]["analysis"], "autocorrelation")
        self.assertEqual(columns(entry["recipe"]), [0])

    def test_presenter_differences_and_lag(self):
        entry_diff = self.presenter.differences(settings={"series_index": 0, "lag": 1, "store_col": "D_Sales"})
        self.assertEqual(entry_diff["result"]["analysis"], "differences")
        self.assertIn("D_Sales", [c.name for c in self.ws.columns])

        entry_lag = self.presenter.lag(settings={"series_index": 0, "lag": 1, "store_col": "L_Sales"})
        self.assertEqual(entry_lag["result"]["analysis"], "lag")
        self.assertIn("L_Sales", [c.name for c in self.ws.columns])


if __name__ == "__main__":
    unittest.main()
