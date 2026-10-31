"""Unit tests for Definitive Screening Design (DSD) analysis engine."""
import math
import unittest
import numpy as np

from statcraft.dsd import create_definitive_screening_design
from statcraft.dsd_analysis import analyze_definitive_screening_design
from statcraft.model import Column


class TestDSDAnalysis(unittest.TestCase):
    def setUp(self):
        # Create a 6-factor DSD
        factors = [
            {"name": "Temp", "low": 100, "high": 200},
            {"name": "Pressure", "low": 10, "high": 50},
            {"name": "Time", "low": 5, "high": 15},
            {"name": "Catalyst", "low": 1, "high": 5},
            {"name": "Agitation", "low": 200, "high": 400},
            {"name": "Concentration", "low": 0.1, "high": 0.5},
        ]
        self.ws = create_definitive_screening_design(factors, replicates=1, extra_centers=2, randomize=False)

        # Generate synthetic response with known active factors:
        # Y = 50 + 10 * x1 - 5 * x2 + 8 * (x1 * x2) + 6 * (x1^2) + noise
        x1 = np.array(self.ws.columns[4].values)
        x2 = np.array(self.ws.columns[5].values)
        # Coded
        z1 = (x1 - 150.0) / 50.0
        z2 = (x2 - 30.0) / 20.0
        np.random.seed(123)
        noise = np.random.normal(0, 0.5, len(x1))
        y = 50.0 + 10.0 * z1 - 5.0 * z2 + 8.0 * (z1 * z2) + 6.0 * (z1 ** 2) + noise
        self.ws.columns.append(Column("Yield", "number", [float(val) for val in y]))
        self.response_idx = len(self.ws.columns) - 1

    def test_stepwise_analysis_finds_active_terms(self):
        res = analyze_definitive_screening_design(self.ws, response_index=self.response_idx, selection="stepwise")
        self.assertEqual(res["analysis"], "definitive_screening_analysis")
        self.assertEqual(res["response_name"], "Yield")
        self.assertGreater(res["r2"], 0.85)
        self.assertGreater(res["r2_adj"], 0.80)
        self.assertIsNotNone(res["s"])
        self.assertLess(res["s"], 2.0)

        # Check that Temp and Pressure were identified as active factors
        self.assertIn("Temp", res["active_factors"])

        # Check ANOVA table structure
        anova_sources = [row["source"].strip() for row in res["anova"]]
        self.assertIn("Model", anova_sources)
        self.assertIn("Linear", anova_sources)
        self.assertIn("Error", anova_sources)
        self.assertIn("Total", anova_sources)

        # Check Coded Coefficients
        terms = [t["term"] for t in res["terms"]]
        self.assertIn("Constant", terms)
        self.assertIn("Temp", terms)

    def test_pareto_effects_and_critical_t(self):
        res = analyze_definitive_screening_design(self.ws, response_index=self.response_idx)
        pareto = res["pareto_effects"]
        self.assertTrue(len(pareto) >= 2)
        # Check sorted descending
        effects = [p["effect"] for p in pareto]
        self.assertEqual(effects, sorted(effects, reverse=True))

        t_crit = res["t_crit"]
        self.assertTrue(1.5 <= t_crit <= 3.5)

    def test_prediction_profiler_spec(self):
        res = analyze_definitive_screening_design(self.ws, response_index=self.response_idx)
        p_spec = res["profiler_spec"]
        self.assertEqual(p_spec["response"], "Yield")
        self.assertEqual(len(p_spec["factors"]), 6)

        # Test predict_fn evaluation
        mid_settings = {f["name"]: f["current"] for f in p_spec["factors"]}
        pred_mid = p_spec["predict_fn"](mid_settings)
        self.assertTrue(math.isfinite(pred_mid))
        # At midpoints (z=0), Y should be close to constant (50)
        self.assertAlmostEqual(pred_mid, 50.0, delta=8.0)

    def test_main_effects_only_selection(self):
        res = analyze_definitive_screening_design(self.ws, response_index=self.response_idx, selection="main_effects")
        terms = [t["term"] for t in res["terms"]]
        self.assertIn("Temp", terms)
        self.assertIn("Pressure", terms)
        self.assertNotIn("Temp*Pressure", terms)


if __name__ == "__main__":
    unittest.main()
