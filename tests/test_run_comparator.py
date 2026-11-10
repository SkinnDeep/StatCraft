"""Unit tests for Side-by-Side Model and Run Comparator."""
import unittest
from statcraft.run_comparator import compare_runs


class TestRunComparator(unittest.TestCase):
    def test_compare_capability_runs(self):
        run_before = {
            "title": "Shift 1 Baseline",
            "result": {"cp": 1.10, "cpk": 0.95, "ppm_total": 4500.0}
        }
        run_after = {
            "title": "Shift 1 Post-Kaizen",
            "result": {"cp": 1.45, "cpk": 1.38, "ppm_total": 45.0}
        }
        diff = compare_runs(run_before, run_after)

        self.assertEqual(diff["improvements"], 3)
        self.assertEqual(diff["degradations"], 0)
        self.assertIn("improvement", diff["verdict"].lower())

        # Check delta metrics
        cpk_delta = [d for d in diff["deltas"] if d.name == "Cpk"][0]
        self.assertAlmostEqual(cpk_delta.delta, 0.43)
        self.assertTrue(cpk_delta.is_improved)

        ppm_delta = [d for d in diff["deltas"] if d.name == "Ppm Total"][0]
        self.assertAlmostEqual(ppm_delta.delta, -4455.0)
        self.assertTrue(ppm_delta.is_improved)  # Lower is better for PPM!

    def test_compare_regression_models(self):
        full_model = {
            "title": "Full Model (10 Predictors)",
            "result": {"r_squared": 0.85, "aic": 450.0, "s": 3.2}
        }
        reduced_model = {
            "title": "Reduced Stepwise Model (4 Predictors)",
            "result": {"r_squared": 0.84, "aic": 410.0, "s": 3.25}
        }
        diff = compare_runs(full_model, reduced_model)
        aic_delta = [d for d in diff["deltas"] if d.name == "Aic"][0]
        self.assertAlmostEqual(aic_delta.delta, -40.0)
        self.assertTrue(aic_delta.is_improved)  # Lower AIC is better!


if __name__ == "__main__":
    unittest.main()
