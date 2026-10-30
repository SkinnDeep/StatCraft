import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from statcraft.grouped import stacked_anova
from statcraft.app import Presenter, format_entry
from statcraft.model import Column, Worksheet


class GroupedTests(unittest.TestCase):
    def test_interleaved_groups_hand_calculated_anova(self):
        result = stacked_anova([1, 4, 2, 5, 3, 6], ["A", "B", "A", "B", "A", "B"])
        self.assertEqual(result["variables"], ["A", "B"])
        self.assertAlmostEqual(result["ss_between"], 13.5)
        self.assertEqual(result["ss_within"], 4)
        self.assertAlmostEqual(result["f"], 13.5)
        self.assertEqual(result["used_rows"], list(range(1, 7)))

    def test_numeric_factors_pairwise_missing_and_unequal_lengths(self):
        result = stacked_anova([1, 4, None, 2, 5, 3, 6, 100], [2, 1, 2, 2, 1, 2, 1])
        self.assertEqual(result["factor_levels"], [2, 1])
        self.assertEqual(result["missing_rows"], [3, 8])
        self.assertEqual(result["count"], 6)
        self.assertAlmostEqual(result["f"], 13.5)

    def test_empty_and_case_sensitive_text_factors(self):
        result = stacked_anova([1, 4, 2, 5, 3, 6, 99], ["a", "A", "a", "A", "a", "A", ""])
        self.assertEqual(result["factor_levels"], ["a", "A"])
        self.assertEqual(result["missing_rows"], [7])
        for factor in ([True]*6, [float("inf")]*6, ["A"]*6):
            with self.assertRaises(ValueError): stacked_anova([1, 4, 2, 5, 3, 6], factor)

    def test_presenter_uses_text_factor_and_report_labels(self):
        presenter = Presenter()
        presenter.worksheet = Worksheet("Grouped", [Column("Group", "text", ["A", "B"]*3), Column("Y", values=[1,4,2,5,3,6])])
        entry = presenter.stacked_anova(1, 0)
        report = format_entry(entry)
        self.assertIn("Group Summaries", report)
        self.assertIn("A                   3", report)
        self.assertEqual(len(presenter.history), 1)
        self.assertFalse(presenter.dirty)
        with self.assertRaises(ValueError): presenter.stacked_anova(1, 1)
