"""Unit tests for Pareto Chart (Stat > Quality Tools > Pareto Chart)."""

import unittest

from statcraft.pareto_engine import run_pareto_chart
from statcraft.pareto_report import generate_pareto_report


class TestParetoChart(unittest.TestCase):
    def test_raw_observations(self):
        # 10 raw defect occurrences
        raw_defects = [
            "Scratch", "Dent", "Scratch", "Burr", "Scratch",
            "Dent", "Crack", "Scratch", "Blemish", "Dent",
        ]
        res = run_pareto_chart(defect_data=raw_defects, combine_percent=None, variable_name="DefectType")

        self.assertEqual(res["analysis"], "pareto_chart")
        self.assertEqual(res["total_count"], 10.0)
        self.assertFalse(res["is_summarized"])
        # Top category should be Scratch with 4 counts (40%)
        self.assertEqual(res["categories"][0], "Scratch")
        self.assertEqual(res["counts"][0], 4.0)
        self.assertEqual(res["percents"][0], 40.0)
        self.assertEqual(res["cum_percents"][0], 40.0)

        # Second should be Dent with 3 counts (30%)
        self.assertEqual(res["categories"][1], "Dent")
        self.assertEqual(res["counts"][1], 3.0)
        self.assertEqual(res["cum_percents"][1], 70.0)

        # Cumulative percent at end must be 100%
        self.assertEqual(res["cum_percents"][-1], 100.0)

        report = generate_pareto_report(res)
        self.assertIn("Pareto Chart of DefectType", report)
        self.assertIn("Scratch", report)
        self.assertIn("Total", report)

    def test_summarized_table(self):
        labels = ["Contamination", "Misalignment", "Leakage", "Packaging", "Electrical"]
        counts = [85, 42, 18, 12, 5]

        res = run_pareto_chart(
            defect_data=labels,
            count_data=counts,
            combine_percent=None,
            variable_name="AuditIssues",
        )

        self.assertTrue(res["is_summarized"])
        self.assertEqual(res["total_count"], 162.0)
        self.assertEqual(res["categories"][0], "Contamination")
        self.assertEqual(res["counts"][0], 85.0)
        expected_pct = (85.0 / 162.0) * 100.0
        self.assertAlmostEqual(res["percents"][0], expected_pct, places=2)
        self.assertEqual(res["cum_percents"][-1], 100.0)

    def test_combining_into_other(self):
        labels = ["A", "B", "C", "D", "E", "F", "G", "H"]
        counts = [100, 50, 20, 10, 5, 3, 2, 1]  # Total 191
        # A: 100 (52.4%), B: 50 (26.2%, cum 78.5%), C: 20 (10.5%, cum 89.0%), D: 10 (5.2%, cum 94.2%), E: 5 (cum 96.9%)
        # With combine_percent=95.0, E, F, G, H should be combined into 'Other'

        res = run_pareto_chart(
            defect_data=labels,
            count_data=counts,
            combine_percent=95.0,
            variable_name="PartDefects",
        )

        self.assertIn("Other", res["categories"])
        self.assertEqual(res["categories"][-1], "Other")
        # Categories F (3), G (2), H (1) combined into Other after E crosses 95%
        self.assertEqual(res["counts"][-1], 6.0)
        self.assertEqual(res["other_count"], 6.0)
        self.assertEqual(res["other_subcategories"], 3)
        self.assertEqual(res["cum_percents"][-1], 100.0)

        report = generate_pareto_report(res)
        self.assertIn("Other", report)
        self.assertIn("3 categories with cumulative counts beyond threshold", report)

    def test_error_handling(self):
        with self.assertRaises(ValueError):
            run_pareto_chart([])

        with self.assertRaises(ValueError):
            run_pareto_chart(["A", "B"], count_data=[0, 0])


if __name__ == "__main__":
    unittest.main()
