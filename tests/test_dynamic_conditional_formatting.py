import copy
import unittest

from statcraft.conditional_formatting import (
    effective_highlights, legacy_conditional_candidates, validate_rule, validate_rules,
)
from statcraft.model import Column


def rule(kind, first=None, second=None, color="#f8d7da"):
    return {"type": kind, "param1": first, "param2": second, "color": color}


class DynamicConditionalFormattingTests(unittest.TestCase):
    def test_recomputed_after_value_crosses_threshold_and_returns(self):
        col = Column("Load", values=[40], metadata={"conditional_rules": [rule("greater_than", 50)]})
        self.assertEqual(effective_highlights(col), {})
        col.values[0] = 60
        self.assertEqual(effective_highlights(col), {"0": "#f8d7da"})
        col.values[0] = 40
        self.assertEqual(effective_highlights(col), {})
        self.assertNotIn("cell_highlights", col.metadata)

    def test_rank_cutoff_changes_and_ties_are_included(self):
        col = Column("Load", values=[1, 5, 5, 9])
        rules = [rule("highest", 2)]
        self.assertEqual(effective_highlights(col, rules=rules),
                         {"1": "#f8d7da", "2": "#f8d7da", "3": "#f8d7da"})
        col.values[0] = 7
        self.assertEqual(effective_highlights(col, rules=rules), {"0": "#f8d7da", "3": "#f8d7da"})
        self.assertEqual(effective_highlights(col, rules=[rule("lowest", 1)]),
                         {"1": "#f8d7da", "2": "#f8d7da"})
        self.assertEqual(len(effective_highlights(col, rules=[rule("highest", 99)])), 4)

    def test_missing_includes_worksheet_extent_and_text_empty(self):
        col = Column("Load", values=[1, None])
        self.assertEqual(effective_highlights(col, 4, [rule("missing")]),
                         {"1": "#f8d7da", "2": "#f8d7da", "3": "#f8d7da"})
        text = Column("Group", "text", ["", " ", None, "A"])
        self.assertEqual(effective_highlights(text, rules=[rule("missing")]),
                         {"0": "#f8d7da", "2": "#f8d7da"})

    def test_casefold_contains_equal_and_numeric_scientific_notation(self):
        col = Column("Group", "text", ["PASS", "passed", "FAIL", ""])
        self.assertEqual(effective_highlights(col, rules=[rule("contains", "pass")]),
                         {"0": "#f8d7da", "1": "#f8d7da"})
        self.assertEqual(effective_highlights(col, rules=[rule("equal_to", "pass")]), {"0": "#f8d7da"})
        col = Column("Load", values=[100, -1, None])
        self.assertEqual(effective_highlights(col, rules=[rule("equal_to", "1e2")]), {"0": "#f8d7da"})
        self.assertEqual(effective_highlights(col, rules=[rule("equal_to", "nonsense")]), {})

    def test_between_inclusive_reversed_bounds_and_last_match_wins(self):
        col = Column("Load", values=[0, 1, 2, 3])
        rules = [rule("between", 2, 1), rule("greater_than", 1, color="#D4EDDA")]
        self.assertEqual(effective_highlights(col, rules=rules),
                         {"1": "#f8d7da", "2": "#d4edda", "3": "#d4edda"})
        self.assertEqual(effective_highlights(col, rules=[rule("less_than", 1)]), {"0": "#f8d7da"})

    def test_manual_colors_are_independent_and_migration_does_not_erase(self):
        col = Column("Load", values=[60, 40, 70], metadata={
            "conditional_rules": [rule("greater_than", 50)],
            "cell_highlights": {"0": "#F8D7DA", "1": "#fff3cd", "2": "#d4edda"},
        })
        before = copy.deepcopy(col.metadata)
        self.assertEqual(legacy_conditional_candidates(col), {"0": "#f8d7da"})
        overlay = effective_highlights(col)
        self.assertEqual(overlay, {"0": "#f8d7da", "2": "#f8d7da"})
        col.values[0] = 40
        self.assertEqual(effective_highlights(col), {"2": "#f8d7da"})
        self.assertEqual(col.metadata, before)

    def test_outlier_recomputes_with_new_values_and_small_samples(self):
        col = Column("Load", values=[1, 1, 1, 1, 1, 1, 1, 100])
        self.assertEqual(effective_highlights(col, rules=[rule("outlier")]), {"7": "#f8d7da"})
        col.values[7] = 1
        self.assertEqual(effective_highlights(col, rules=[rule("outlier")]), {})
        self.assertEqual(effective_highlights(Column("Small", values=[1, 2, 100]),
                                             rules=[rule("outlier")]), {})

    def test_rule_validation_atomic_and_detached(self):
        good = rule("between", "10", "2")
        before = copy.deepcopy(good)
        normalized = validate_rule(good)
        self.assertEqual((normalized["param1"], normalized["param2"]), (2, 10))
        normalized["color"] = "#000000"
        self.assertEqual(good, before)
        col = Column("Load", values=[100], metadata={"conditional_rules": [good, rule("greater_than", "bad")]})
        before_col = copy.deepcopy(col)
        with self.assertRaises(ValueError):
            effective_highlights(col)
        self.assertEqual(col, before_col)

    def test_malformed_and_nonfinite_parameters_are_rejected(self):
        bad_rules = [None, [], {}, rule("unknown"), dict(rule("missing"), extra=1),
                     rule("missing", color="red"), rule("contains", ""),
                     rule("equal_to", True), rule("between", 1, None)]
        for val in (float("inf"), float("nan"), "-inf", "nan", "1e999", True, None):
            bad_rules.append(rule("greater_than", val))
        for val in (0, -1, 1.5, "inf", True):
            bad_rules.append(rule("highest", val))
        for bad in bad_rules:
            with self.subTest(rule=bad), self.assertRaises(ValueError):
                validate_rule(bad)
        for bad in ({}, None, "rules"):
            with self.assertRaises(ValueError):
                validate_rules(bad)
        col = Column("Load", values=[1])
        for count in (-1, 1.5, True):
            with self.assertRaises(ValueError):
                effective_highlights(col, count)
        for val in (float("nan"), float("inf"), True):
            col.values = [val]
            with self.assertRaises(ValueError):
                effective_highlights(col, rules=[rule("missing")])


if __name__ == "__main__":
    unittest.main()
