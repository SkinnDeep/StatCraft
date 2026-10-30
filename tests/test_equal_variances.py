"""Unit tests for native StatCraft Test for Equal Variances (equal_variances_engine)."""
import unittest
import math
from statcraft.model import Column, Worksheet
from statcraft.equal_variances_engine import (
    equal_variances_settings,
    run_test_equal_variances,
    store_equal_variances_columns,
)
from statcraft.equal_variances_report import format_equal_variances_report


class TestEqualVariancesEngine(unittest.TestCase):
    def setUp(self):
        # Reference dataset: 3 groups with known properties
        # Group 1: [10, 12, 11, 13, 9] (mean=11, var=2.5, stdev=1.5811)
        # Group 2: [14, 15, 13, 16, 17] (mean=15, var=2.5, stdev=1.5811)
        # Group 3: [20, 25, 18, 30, 22] (mean=23, var=21.5, stdev=4.6368)
        self.ws_stacked = Worksheet("StackedData", [
            Column("Response", "number", [10, 12, 11, 13, 9, 14, 15, 13, 16, 17, 20, 25, 18, 30, 22]),
            Column("Factor", "text", ["A"] * 5 + ["B"] * 5 + ["C"] * 5),
            Column("SubFactor", "text", ["Low", "High", "Low", "High", "Low"] * 3),
        ])

        self.ws_unstacked = Worksheet("UnstackedData", [
            Column("GroupA", "number", [10, 12, 11, 13, 9]),
            Column("GroupB", "number", [14, 15, 13, 16, 17]),
            Column("GroupC", "number", [20, 25, 18, 30, 22]),
        ])

    def test_settings_validation(self):
        opts = equal_variances_settings()
        self.assertEqual(opts["confidence_level"], 95.0)
        self.assertFalse(opts["use_normal_distribution"])
        self.assertTrue(opts["graphs"]["summary_plot"])
        self.assertTrue(opts["results"]["method"])
        self.assertFalse(opts["storage"]["stdevs"])

        # Invalid confidence level
        with self.assertRaises(ValueError):
            equal_variances_settings({"confidence_level": 150.0})
        with self.assertRaises(ValueError):
            equal_variances_settings({"confidence_level": -5.0})

    def test_stacked_single_factor_non_normal(self):
        res = run_test_equal_variances(
            self.ws_stacked,
            stacked=True,
            response_index=0,
            factor_indices=[1],
            options={"use_normal_distribution": False, "confidence_level": 95.0},
        )
        self.assertTrue(res["stacked"])
        self.assertEqual(res["response_name"], "Response")
        self.assertEqual(res["factor_names"], ["Factor"])
        self.assertEqual(len(res["groups"]), 3)

        # Check group calculations
        g1, g2, g3 = res["groups"]
        self.assertEqual(g1["level"], "A")
        self.assertEqual(g1["count"], 5)
        self.assertAlmostEqual(g1["stdev"], 1.5811388, places=4)
        self.assertAlmostEqual(g3["stdev"], 4.6904158, places=4)

        # Bonferroni intervals exist and are positive
        for g in res["groups"]:
            self.assertGreater(g["bonf_lower"], 0.0)
            self.assertGreater(g["bonf_upper"], g["bonf_lower"])
            self.assertGreater(g["mci_upper"], g["mci_lower"])

        # Test statistics
        self.assertIn("levene", res)
        self.assertIn("multiple_comparisons", res)
        self.assertGreater(res["levene"]["test_statistic"], 0.0)
        self.assertLessEqual(res["levene"]["p_value"], 1.0)
        self.assertGreaterEqual(res["levene"]["p_value"], 0.0)

    def test_stacked_multi_factor(self):
        res = run_test_equal_variances(
            self.ws_stacked,
            stacked=True,
            response_index=0,
            factor_indices=[1, 2],
        )
        self.assertTrue(res["stacked"])
        self.assertEqual(res["factor_names"], ["Factor", "SubFactor"])
        # Should have crossed group combinations like "A * High", "A * Low", etc.
        self.assertGreaterEqual(len(res["groups"]), 4)
        for g in res["groups"]:
            self.assertIn(" * ", g["level"])

    def test_unstacked_normal_distribution(self):
        res = run_test_equal_variances(
            self.ws_unstacked,
            stacked=False,
            response_indices=[0, 1, 2],
            options={"use_normal_distribution": True, "confidence_level": 90.0},
        )
        self.assertFalse(res["stacked"])
        self.assertTrue(res["use_normal_distribution"])
        self.assertEqual(len(res["groups"]), 3)
        self.assertIsNotNone(res["bartlett"])
        self.assertGreater(res["bartlett"]["test_statistic"], 0.0)
        self.assertLessEqual(res["bartlett"]["p_value"], 1.0)

    def test_missing_value_omission(self):
        ws_missing = Worksheet("WithMissing", [
            Column("Y", "number", [10, None, 11, 13, 9, 14, 15, 13, None, 17, 20, 25, 18, 30, 22]),
            Column("X", "text", ["A", "A", "A", "A", "A", "B", "B", "B", "B", None, "C", "C", "C", "C", "C"]),
        ])
        res = run_test_equal_variances(
            ws_missing,
            stacked=True,
            response_index=0,
            factor_indices=[1],
        )
        self.assertGreater(len(res["missing_rows"]), 0)
        # Groups should have remaining counts
        counts = [g["count"] for g in res["groups"]]
        self.assertEqual(counts[0], 4)
        self.assertEqual(counts[1], 3)
        self.assertEqual(counts[2], 5)

    def test_column_storage(self):
        ws = Worksheet("StorageTest", [
            Column("Y", "number", [1, 2, 3, 4, 10, 20, 30, 40]),
            Column("G", "text", ["L1", "L1", "L1", "L1", "L2", "L2", "L2", "L2"]),
        ])
        res = run_test_equal_variances(
            ws,
            stacked=True,
            response_index=0,
            factor_indices=[1],
            options={
                "storage": {
                    "stdevs": True,
                    "variances": True,
                    "bonferroni_ci": True,
                    "mci": True,
                }
            },
        )
        stored = store_equal_variances_columns(ws, res, res["options"])
        self.assertEqual(stored, ["STDEV", "VARIANCES", "BONF1", "BONF2", "MCI1", "MCI2"])
        col_names = [c.name for c in ws.columns]
        for name in stored:
            self.assertIn(name, col_names)

    def test_report_formatting(self):
        res = run_test_equal_variances(
            self.ws_stacked,
            stacked=True,
            response_index=0,
            factor_indices=[1],
        )
        entry = {"title": "Test for Equal Variances", "time": "2026-10-20T10:00:00", "result": res}
        report = format_equal_variances_report(entry)
        self.assertIn("Test for Equal Variances: Response versus Factor", report)
        self.assertIn("Method", report)
        self.assertIn("Bonferroni Confidence Intervals", report)
        self.assertIn("Tests", report)
        self.assertIn("Levene", report)


if __name__ == "__main__":
    unittest.main()
