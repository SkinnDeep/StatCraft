import math
import os
import sys
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.calculator import evaluate_advanced
from statcraft.calc_data import (
    compute_column_statistics,
    compute_row_statistics,
    generate_random_distribution,
    sample_from_columns,
)
from statcraft.conditional_formatting import effective_highlights, validate_rule
from statcraft.data_prep import make_indicator_variables, subset_by_condition
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.probability import DEFAULTS, PARAMETERS, calculate as prob_calc

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestPhase1CalcDataPower(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_all_24_probability_distributions(self):
        self.assertGreaterEqual(len(PARAMETERS), 24)
        for dist, params in DEFAULTS.items():
            q75 = prob_calc(dist, "Inverse CDF", 0.75, params)["result"]
            cdf_val = prob_calc(dist, "CDF", q75, params)["result"]
            self.assertGreaterEqual(cdf_val, 0.749)
            pdf_val = prob_calc(dist, "PDF/PMF", q75, params)["result"]
            self.assertTrue(math.isfinite(pdf_val))

    def test_advanced_calculator_functions(self):
        ws = Worksheet("CalcTest", [
            Column("Temp Value", "number", [10.0, 20.0, 30.0, None]),
            Column("Pressure", "number", [1.0, 2.0, 3.0, 4.0]),
            Column("Status", "text", ["pass", "fail", "pass", "pass"]),
        ], constants=[Column("Factor", "number", [2.5])])

        self.assertEqual(evaluate_advanced("ROUND(MEAN(C1) / 3, 2)", ws), [6.67, 6.67, 6.67, 6.67])
        self.assertEqual(evaluate_advanced("IF(C1 > MEAN(C1), 'High', 'Low')", ws), ["Low", "Low", "High", "Low"])
        self.assertEqual(evaluate_advanced("ROWMEAN(C1, C2)", ws), [5.5, 11.0, 16.5, 4.0])
        self.assertEqual(evaluate_advanced("ROWSUM(C1, C2)", ws), [11.0, 22.0, 33.0, 4.0])
        self.assertEqual(evaluate_advanced("[Temp Value] * K1", ws), [25.0, 50.0, 75.0, None])
        self.assertEqual(evaluate_advanced("UPPER(Status)", ws), ["PASS", "FAIL", "PASS", "PASS"])
        self.assertEqual(evaluate_advanced("CONCAT(UPPER(Status), '-', ROUND(C2, 0))", ws), ["PASS-1.0", "FAIL-2.0", "PASS-3.0", "PASS-4.0"])
        self.assertEqual(evaluate_advanced("ISMISS(C1)", ws), [0.0, 0.0, 0.0, 1.0])

        for unsafe in ['__import__("os")', 'C1.__class__', 'C1[0]']:
            with self.assertRaises(ValueError):
                evaluate_advanced(unsafe, ws)

    def test_random_distributions_and_sampling(self):
        w_vals = generate_random_distribution("Weibull", 40, (2.0, 10.0), seed=42)
        self.assertEqual(len(w_vals), 40)
        self.assertTrue(all(v > 0 for v in w_vals))

        g_vals = generate_random_distribution("Geometric", 30, (0.35,), seed=42)
        self.assertEqual(len(g_vals), 30)
        self.assertTrue(all(isinstance(v, int) and v >= 1 for v in g_vals))

        cols = [[1, 2, 3, 4], ["A", "B", "C", "D"]]
        s_cols = sample_from_columns(cols, n=6, replace=True, seed=7)
        self.assertEqual(len(s_cols[0]), 6)
        self.assertEqual(len(s_cols[1]), 6)
        for num, txt in zip(s_cols[0], s_cols[1]):
            self.assertEqual({1: "A", 2: "B", 3: "C", 4: "D"}[num], txt)

        with self.assertRaises(ValueError):
            sample_from_columns(cols, n=10, replace=False)

    def test_row_and_column_statistics(self):
        cols = [[10.0, 20.0, None], [20.0, 40.0, 5.0]]
        self.assertEqual(compute_row_statistics(cols, "Mean"), [15.0, 30.0, 5.0])
        self.assertEqual(compute_row_statistics(cols, "Sum"), [30.0, 60.0, 5.0])
        self.assertEqual(compute_row_statistics(cols, "Range"), [10.0, 20.0, 0.0])
        self.assertAlmostEqual(compute_column_statistics([2.0, 4.0, 6.0, 8.0, None], "Mean"), 5.0)
        self.assertAlmostEqual(compute_column_statistics([2.0, 4.0, 6.0, 8.0, None], "IQR"), 3.0)

    def test_make_indicators_and_subset_condition(self):
        ws = Worksheet("Prod", [
            Column("Shift", "text", ["Day", "Night", "Day", None]),
            Column("Yield", "number", [95.0, 88.0, 99.0, 91.0]),
        ])
        ind_cols = make_indicator_variables(ws, 0)
        self.assertEqual([c.name for c in ind_cols], ["Shift_Day", "Shift_Night"])
        self.assertEqual(ind_cols[0].values, [1.0, 0.0, 1.0, None])
        self.assertEqual(ind_cols[1].values, [0.0, 1.0, 0.0, None])

        sub = subset_by_condition(ws, "C2 >= 95 and C1 == 'Day'", "HighDay")
        self.assertEqual(sub.name, "HighDay")
        self.assertEqual(sub.row_count, 2)
        self.assertEqual(sub.columns[1].values, [95.0, 99.0])

    def test_statistical_conditional_formatting(self):
        # 10 items around 10, plus 100 as extreme > 3 sigma
        vals = [10.0] * 12 + [100.0]
        col = Column("Measure", "number", vals)
        r3s = validate_rule({"type": "outside_3sigma", "color": "#f8d7da"})
        self.assertEqual(effective_highlights(col, rules=[r3s]), {"12": "#f8d7da"})

        specs = validate_rule({"type": "outside_specs", "param1": 9.0, "param2": 15.0, "color": "#fff3cd"})
        self.assertEqual(effective_highlights(col, rules=[specs]), {"12": "#fff3cd"})

        top20 = validate_rule({"type": "top_percent", "param1": 10.0, "color": "#d4edda"})
        self.assertEqual(effective_highlights(col, rules=[top20]), {"12": "#d4edda"})

    def test_presenter_and_ui_integration(self):
        p = Presenter()
        p.worksheet = Worksheet("Main", [
            Column("Val", "number", [10.0, 20.0, 30.0]),
            Column("Grp", "text", ["A", "B", "A"]),
        ])
        p.calculate("IF(C1 >= 20, 'OK', 'LOW')", "Flag")
        self.assertEqual(p.worksheet.columns[-1].kind, "text")
        self.assertEqual(p.worksheet.columns[-1].values, ["LOW", "OK", "OK"])

        p.column_statistics(0, "Mean", "MyMean")
        self.assertEqual(len(p.worksheet.constants), 1)
        self.assertEqual(p.worksheet.constants[0].values, [20.0])

        p.make_indicator_variables(1, "Ind")
        self.assertIn("Ind_A", [c.name for c in p.worksheet.columns])

        p.subset_worksheet_by_condition("C1 > 15", "Filtered")
        self.assertEqual(p.worksheet.name, "Filtered")
        self.assertEqual(p.worksheet.row_count, 2)

        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        self.assertTrue(hasattr(win, "column_statistics_dialog"))
        self.assertTrue(hasattr(win, "row_statistics_dialog"))
        self.assertTrue(hasattr(win, "sample_from_columns_dialog"))
        self.assertTrue(hasattr(win, "random_all_distributions_dialog"))
        self.assertTrue(hasattr(win, "make_indicator_variables_dialog"))
        self.assertTrue(hasattr(win, "subset_by_condition_dialog"))
        win.close()


if __name__ == "__main__":
    unittest.main()
