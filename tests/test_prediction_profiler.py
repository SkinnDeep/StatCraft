"""Unit and integration tests for StatCraft Prediction Profiler and JMP Compatibility Suite."""
from __future__ import annotations

import unittest
from PySide6.QtWidgets import QApplication

from statcraft.model import Worksheet, Column
from statcraft.prediction_profiler import (
    ProfilerFactor, ProfilerResponse, extract_profiler_specs,
    compute_prediction_profiles, compute_desirability,
    compute_composite_desirability, optimize_profiler_settings
)
from statcraft.prediction_profiler_dialog import PredictionProfilerDialog, ProfilerCellWidget


app = QApplication.instance() or QApplication([])


class TestPredictionProfiler(unittest.TestCase):
    def setUp(self):
        # Create a regression dataset with realistic residuals
        x1 = [10.0, 20.0, 30.0, 10.0, 20.0, 30.0, 15.0, 25.0]
        x2 = [1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 1.5, 1.5]
        y = [67.2, 86.8, 107.1, 63.9, 84.2, 103.8, 75.6, 95.3]

        self.ws = Worksheet("ProfilerStudy", [
            Column("X1", "number", x1),
            Column("X2", "number", x2),
            Column("Yield", "number", y, {"spec_limits": {"lsl": 70.0, "usl": 100.0, "target": 85.0}})
        ])

        self.recipe = {
            "action": "multiple_regression",
            "parameters": {
                "response_index": 2,
                "predictor_indices": [0, 1],
                "confidence": 0.95
            }
        }

    def test_compute_desirability_maximize(self):
        # Maximize: L=50, T=100
        self.assertEqual(compute_desirability(40.0, "maximize", lower=50.0, target=100.0), 0.0)
        self.assertEqual(compute_desirability(110.0, "maximize", lower=50.0, target=100.0), 1.0)
        self.assertAlmostEqual(compute_desirability(75.0, "maximize", lower=50.0, target=100.0), 0.5)

    def test_compute_desirability_minimize(self):
        # Minimize: T=10, U=50
        self.assertEqual(compute_desirability(5.0, "minimize", target=10.0, upper=50.0), 1.0)
        self.assertEqual(compute_desirability(55.0, "minimize", target=10.0, upper=50.0), 0.0)
        self.assertAlmostEqual(compute_desirability(30.0, "minimize", target=10.0, upper=50.0), 0.5)

    def test_compute_desirability_target(self):
        # Target: L=20, T=50, U=80
        self.assertEqual(compute_desirability(15.0, "target", lower=20.0, target=50.0, upper=80.0), 0.0)
        self.assertEqual(compute_desirability(85.0, "target", lower=20.0, target=50.0, upper=80.0), 0.0)
        self.assertEqual(compute_desirability(50.0, "target", lower=20.0, target=50.0, upper=80.0), 1.0)
        self.assertAlmostEqual(compute_desirability(35.0, "target", lower=20.0, target=50.0, upper=80.0), 0.5)

    def test_composite_desirability(self):
        specs = [
            ProfilerResponse("Yield", 2, "target", lower=60.0, target=85.0, upper=110.0, weight=1.0, importance=1.0)
        ]
        comp_d, ind_d = compute_composite_desirability({"Yield": 85.0}, specs)
        self.assertAlmostEqual(comp_d, 1.0)
        self.assertAlmostEqual(ind_d["Yield"], 1.0)

        comp_d_low, _ = compute_composite_desirability({"Yield": 50.0}, specs)
        self.assertEqual(comp_d_low, 0.0)

    def test_extract_profiler_specs(self):
        factors, responses = extract_profiler_specs(self.ws, [self.recipe])
        self.assertEqual(len(factors), 2)
        self.assertEqual(factors[0].name, "X1")
        self.assertEqual(factors[0].min_val, 10.0)
        self.assertEqual(factors[0].max_val, 30.0)
        self.assertEqual(factors[1].name, "X2")
        self.assertEqual(factors[1].min_val, 1.0)
        self.assertEqual(factors[1].max_val, 2.0)

        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0].name, "Yield")
        self.assertEqual(responses[0].goal, "target")
        self.assertEqual(responses[0].lower, 70.0)
        self.assertEqual(responses[0].upper, 100.0)
        self.assertEqual(responses[0].target, 85.0)

    def test_compute_prediction_profiles(self):
        factors, responses = extract_profiler_specs(self.ws, [self.recipe])
        settings = {"X1": 20.0, "X2": 1.5}
        profiles = compute_prediction_profiles(self.ws, [self.recipe], factors, settings, n_points=21, confidence=0.95)

        self.assertIn("Yield", profiles)
        y_prof = profiles["Yield"]
        self.assertAlmostEqual(y_prof["current_fit"], 85.5, places=1)
        self.assertIsNotNone(y_prof["current_ci_low"])
        self.assertIsNotNone(y_prof["current_ci_high"])
        self.assertTrue(y_prof["current_ci_low"] < y_prof["current_fit"] < y_prof["current_ci_high"])

        traces = y_prof["factor_traces"]
        self.assertIn("X1", traces)
        self.assertIn("X2", traces)
        self.assertEqual(len(traces["X1"]["xs"]), 21)
        self.assertEqual(len(traces["X1"]["fits"]), 21)
        self.assertEqual(len(traces["X1"]["ci_low"]), 21)

    def test_optimize_profiler_settings(self):
        factors, responses = extract_profiler_specs(self.ws, [self.recipe])
        # We want Yield to be Target = 85.0
        opt_settings = optimize_profiler_settings(self.ws, [self.recipe], factors, responses)
        self.assertIn("X1", opt_settings)
        self.assertIn("X2", opt_settings)
        self.assertTrue(10.0 <= opt_settings["X1"] <= 30.0)
        self.assertTrue(1.0 <= opt_settings["X2"] <= 2.0)

    def test_dialog_lifecycle_offscreen(self):
        dlg = PredictionProfilerDialog(None, self.ws, [self.recipe])
        self.assertIsNotNone(dlg)

        # Trigger factor change
        dlg.on_factor_value_changed("X1", 25.0)
        self.assertEqual(dlg.current_settings["X1"], 25.0)

        # Test maximize desirability
        dlg.on_maximize_desirability()
        self.assertTrue(10.0 <= dlg.current_settings["X1"] <= 30.0)

        # Test reset midpoints
        dlg.on_reset_midpoints()
        self.assertAlmostEqual(dlg.current_settings["X1"], 20.0)
        self.assertAlmostEqual(dlg.current_settings["X2"], 1.5)

        dlg.close()


if __name__ == "__main__":
    unittest.main()
