"""Unit tests for JMP-style Variability / Attribute Gauge Chart analytical engine and UI."""
from __future__ import annotations

import unittest
from statcraft.variability_engine import calculate_variability_analysis


class TestVariabilityEngine(unittest.TestCase):
    def setUp(self):
        # Classic 10 parts x 3 operators x 2 replications standard Gauge R&R dataset
        self.parts = [f"Part-{p}" for p in range(1, 11) for _ in range(6)]
        self.operators = [f"Op-{o}" for _ in range(10) for o in (1, 2, 3) for _ in range(2)]
        
        # Synthetic measurement: Part effect + Operator effect + error
        import random
        rng = random.Random(42)
        self.measurements = []
        for i in range(len(self.parts)):
            p_val = int(self.parts[i].split("-")[1]) * 2.5
            o_val = int(self.operators[i].split("-")[1]) * 0.4
            noise = rng.gauss(0, 0.15)
            self.measurements.append(100.0 + p_val + o_val + noise)

    def test_variability_calculation_structure(self):
        res = calculate_variability_analysis(
            y_values=self.measurements,
            x_groupings=[("Part", self.parts), ("Operator", self.operators)],
            lsl=95.0,
            usl=135.0,
        )

        self.assertEqual(res["n"], 60)
        self.assertAlmostEqual(res["grand_mean"], sum(self.measurements) / 60, places=4)
        self.assertEqual(len(res["cell_summaries"]), 30)  # 10 parts x 3 operators = 30 cells
        self.assertIn("std_repeatability", res)
        self.assertGreater(res["std_repeatability"], 0.0)

        # Gauge R&R breakdown
        grr = res["gauge_rr"]
        self.assertIsNotNone(grr)
        self.assertEqual(grr["num_parts"], 10)
        self.assertEqual(grr["num_operators"], 3)
        self.assertGreater(grr["var_part_to_part"], 0.0)
        self.assertGreater(grr["var_repeatability"], 0.0)
        self.assertGreater(grr["ndc"], 1)
        self.assertIn("%", grr["aiag_status"])
        self.assertIn(grr["aiag_badge"], ("Excellent", "Marginal", "Unacceptable"))

    def test_variability_tolerance_metrics(self):
        res = calculate_variability_analysis(
            y_values=self.measurements,
            x_groupings=[("Part", self.parts), ("Operator", self.operators)],
            lsl=90.0,
            usl=140.0,
        )
        grr = res["gauge_rr"]
        self.assertEqual(grr["tolerance"], 50.0)
        self.assertIsNotNone(grr["pct_tol_grr"])
        self.assertGreater(grr["pct_tol_grr"], 0.0)

    def test_variability_missing_data_filtering(self):
        y_with_none = list(self.measurements)
        y_with_none[5] = None
        y_with_none[12] = float("nan")

        res = calculate_variability_analysis(
            y_values=y_with_none,
            x_groupings=[("Part", self.parts), ("Operator", self.operators)],
        )
        self.assertEqual(res["n"], 58)

    def test_variability_validation_errors(self):
        with self.assertRaises(ValueError):
            calculate_variability_analysis([], [("X", [])])

        with self.assertRaises(ValueError):
            calculate_variability_analysis([1.0, 2.0], [("X", [1.0])])

    def test_variability_widget_init(self):
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        from statcraft.variability_chart import VariabilityPlatformWidget

        res = calculate_variability_analysis(
            y_values=self.measurements,
            x_groupings=[("Part", self.parts), ("Operator", self.operators)],
            lsl=95.0,
            usl=135.0,
        )
        w = VariabilityPlatformWidget(res, title="Test Variability Analysis")
        self.assertEqual(w.windowTitle(), "Test Variability Analysis")
        self.assertIsNotNone(w.canvas)
        w.close()


if __name__ == "__main__":
    unittest.main()
