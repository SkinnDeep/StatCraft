"""Unit tests for Stability Study (Shelf Life Estimation per ICH Q1E)."""
import unittest
import numpy as np

from statcraft.stability_study import clean_stability_data, fit_stability_study
from statcraft.stability_study_report import generate_stability_study_report
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry


class TestStabilityStudy(unittest.TestCase):
    def setUp(self):
        # Pharmaceutical stability dataset: 3 batches, testing at 0, 3, 6, 9, 12, 18, 24 months
        # Nominal potency starts at ~100%, degrades at ~0.25% per month. LSL = 90.0%
        self.months = [0.0, 3.0, 6.0, 9.0, 12.0, 18.0, 24.0] * 3
        self.batches = ["B1"] * 7 + ["B2"] * 7 + ["B3"] * 7
        self.potency = [
            # Batch 1
            100.2, 99.4, 98.5, 97.8, 97.1, 95.5, 94.0,
            # Batch 2
            99.8, 99.1, 98.3, 97.4, 96.8, 95.1, 93.7,
            # Batch 3
            100.5, 99.7, 98.9, 98.1, 97.4, 95.9, 94.4,
        ]

    def test_clean_data(self):
        y_raw = [100.0, None, 98.0, 97.0]
        x_raw = [0.0, 3.0, None, 9.0]
        b_raw = ["B1", "B1", "B1", "B1"]
        y, x, b, u = clean_stability_data(y_raw, x_raw, b_raw)
        self.assertEqual(len(y), 2)
        self.assertEqual(list(x), [0.0, 9.0])
        self.assertEqual(u, ["B1"])

    def test_stability_common_slopes(self):
        # In this dataset, slopes are very similar (~ -0.26 / month)
        res = fit_stability_study(
            response=self.potency,
            time=self.months,
            batch=self.batches,
            lsl=90.0,
            alpha_pool=0.25,
            confidence=0.95,
        )
        self.assertEqual(res["analysis"], "stability_study")
        self.assertEqual(res["n_batches"], 3)
        self.assertEqual(res["n_obs"], 21)

        # Equal slopes should not be rejected at alpha=0.25
        ancova = res["ancova_tests"]
        slope_test = ancova[0]
        self.assertGreater(slope_test["p_value"], 0.25)
        self.assertTrue(slope_test["poolable"])

        # Shelf lives should be calculated around 30 to 45 months
        self.assertIsNotNone(res["overall_shelf_life"])
        self.assertGreater(res["overall_shelf_life"], 24.0)
        self.assertLess(res["overall_shelf_life"], 60.0)

        for br in res["batch_results"]:
            self.assertIsNotNone(br["shelf_life"])
            self.assertGreaterEqual(br["shelf_life"], res["overall_shelf_life"])

    def test_stability_separate_slopes(self):
        # Create dataset with distinctly different degradation rates
        diff_potency = [
            # Batch 1 degrades slowly (-0.1 / month)
            100.0, 99.7, 99.4, 99.1, 98.8, 98.2, 97.6,
            # Batch 2 degrades rapidly (-0.5 / month)
            100.0, 98.5, 97.0, 95.5, 94.0, 91.0, 88.0,
            # Batch 3 degrades moderately (-0.3 / month)
            100.0, 99.1, 98.2, 97.3, 96.4, 94.6, 92.8,
        ]
        res = fit_stability_study(
            response=diff_potency,
            time=self.months,
            batch=self.batches,
            lsl=90.0,
            alpha_pool=0.25,
        )
        self.assertEqual(res["selected_model_idx"], 1)  # Separate slopes
        self.assertIn("Separate Slopes", res["selected_model"])
        # Batch 2 crosses LSL 90.0 around month 20-22
        br_b2 = next(br for br in res["batch_results"] if br["batch"] == "B2")
        self.assertLess(br_b2["shelf_life"], 24.0)
        self.assertEqual(res["overall_shelf_life"], br_b2["shelf_life"])

    def test_report_generation(self):
        res = fit_stability_study(
            response=self.potency,
            time=self.months,
            batch=self.batches,
            lsl=90.0,
        )
        report = generate_stability_study_report(res)
        self.assertIn("Stability Study: Potency versus Time, Batch", report)
        self.assertIn("Model Selection (ICH Q1E Decision Rule)", report)
        self.assertIn("Analysis of Variance (Tests for Pooling Batches)", report)
        self.assertIn("Poolable", report)
        self.assertIn("Regression Equations", report)
        self.assertIn("Batch Parameter Estimates", report)
        self.assertIn("Estimated Shelf Life", report)
        self.assertIn("Overall Product Shelf Life:", report)

    def test_presenter_integration(self):
        ws = Worksheet("Stability", [
            Column("Potency", values=self.potency),
            Column("Month", values=self.months),
            Column("Batch", kind="text", values=self.batches),
        ])
        p = Presenter()
        p.worksheet = ws

        entry = p.stability_study(
            response_column=0,
            time_column=1,
            batch_column=2,
            lsl=90.0,
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "stability_study")
        text = format_entry(entry)
        self.assertIn("Stability Study", text)
        self.assertIn("Estimated Shelf Life", text)
        self.assertIn("Overall Product Shelf Life:", text)


if __name__ == "__main__":
    unittest.main()
