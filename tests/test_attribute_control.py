import math
import unittest
from PySide6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])

from statcraft.app import Presenter
from statcraft.attribute_control_dialogs import AttributeChartDialog, AttributeOptionsDialog
from statcraft.attribute_control_engine import parse_subgroup_omission, run_attribute_control
from statcraft.attribute_control_report import format_attribute_control_report
from statcraft.model import Column, Worksheet


class TestAttributeControl(unittest.TestCase):
    def test_parse_subgroup_omission(self):
        self.assertEqual(parse_subgroup_omission(None), set())
        self.assertEqual(parse_subgroup_omission(""), set())
        self.assertEqual(parse_subgroup_omission("3 5:8 12"), {3, 5, 6, 7, 8, 12})
        self.assertEqual(parse_subgroup_omission([1, 2, 5]), {1, 2, 5})
        self.assertEqual(parse_subgroup_omission("8:6"), {6, 7, 8})

    def test_p_chart_constant_size(self):
        # 10 subgroups of size 100
        counts = [5, 4, 6, 5, 3, 7, 5, 4, 6, 5]
        res = run_attribute_control("P", counts, sample_sizes=100)
        self.assertEqual(res["chart"], "P")
        self.assertEqual(res["n_subgroups"], 10)
        self.assertTrue(res["is_constant_size"])
        self.assertEqual(res["constant_size"], 100)

        # Total defectives = 50, total trials = 1000 => p = 0.05
        expected_p = 50.0 / 1000.0
        self.assertAlmostEqual(res["center"], expected_p, places=7)

        sigma = math.sqrt(expected_p * (1.0 - expected_p) / 100.0)
        expected_ucl = expected_p + 3.0 * sigma
        expected_lcl = max(0.0, expected_p - 3.0 * sigma)

        self.assertAlmostEqual(res["ucl"][0], expected_ucl, places=7)
        self.assertAlmostEqual(res["lcl"][0], expected_lcl, places=7)
        self.assertEqual(len(res["test_failures"]), 0)

    def test_p_chart_variable_size(self):
        counts = [10, 20, 15]
        sizes = [100, 200, 150]
        res = run_attribute_control("P", counts, sample_sizes=sizes)
        self.assertFalse(res["is_constant_size"])
        self.assertEqual(res["center"], 45.0 / 450.0)  # 0.10

        p = 0.10
        # UCL for subgroup 0 (n=100) vs subgroup 1 (n=200)
        ucl_0 = p + 3.0 * math.sqrt(p * (1 - p) / 100.0)
        ucl_1 = p + 3.0 * math.sqrt(p * (1 - p) / 200.0)
        self.assertAlmostEqual(res["ucl"][0], ucl_0, places=7)
        self.assertAlmostEqual(res["ucl"][1], ucl_1, places=7)
        self.assertGreater(res["ucl"][0], res["ucl"][1])

    def test_p_chart_omission_and_historical(self):
        counts = [5, 50, 5, 5]  # subgroup 2 is an outlier
        res_omit = run_attribute_control("P", counts, sample_sizes=100, options={"omit_subgroups": "2"})
        # Estimation should be based on subgroups 1, 3, 4: (5 + 5 + 5) / 300 = 0.05
        self.assertAlmostEqual(res_omit["center"], 0.05, places=7)
        self.assertIn(2, res_omit["omitted_subgroups"])
        # Subgroup 2 should fail Test 1
        self.assertIn(2, res_omit["test_failures"])
        self.assertIn(1, res_omit["test_failures"][2])

        # Historical proportion
        res_hist = run_attribute_control("P", counts, sample_sizes=100, options={"historical_p": 0.04})
        self.assertEqual(res_hist["center"], 0.04)
        self.assertTrue(res_hist["is_historical"])

    def test_np_chart(self):
        counts = [5, 4, 6, 5, 3]
        res = run_attribute_control("NP", counts, sample_sizes=100)
        self.assertEqual(res["chart"], "NP")
        # p = 23 / 500 = 0.046; center = 100 * 0.046 = 4.6
        self.assertAlmostEqual(res["center_lines"][0], 4.6, places=7)
        sigma = math.sqrt(100.0 * 0.046 * (1.0 - 0.046))
        self.assertAlmostEqual(res["ucl"][0], 4.6 + 3.0 * sigma, places=7)
        self.assertAlmostEqual(res["lcl"][0], max(0.0, 4.6 - 3.0 * sigma), places=7)

    def test_c_chart(self):
        # Count of defects per unit (sample size fixed at 1)
        counts = [2, 3, 1, 4, 2, 3]
        res = run_attribute_control("C", counts)
        self.assertEqual(res["chart"], "C")
        self.assertTrue(res["is_constant_size"])
        expected_c = sum(counts) / float(len(counts))  # 15 / 6 = 2.5
        self.assertAlmostEqual(res["center"], expected_c, places=7)
        sigma = math.sqrt(expected_c)
        self.assertAlmostEqual(res["ucl"][0], expected_c + 3.0 * sigma, places=7)
        self.assertAlmostEqual(res["lcl"][0], max(0.0, expected_c - 3.0 * sigma), places=7)

        # Historical mean
        res_hist = run_attribute_control("C", counts, options={"historical_mean": 2.0})
        self.assertEqual(res_hist["center"], 2.0)
        self.assertAlmostEqual(res_hist["ucl"][0], 2.0 + 3.0 * math.sqrt(2.0), places=7)

    def test_u_chart(self):
        # Defects per unit with variable units
        defects = [4, 6, 8]
        units = [2.0, 3.0, 4.0]
        res = run_attribute_control("U", defects, sample_sizes=units)
        self.assertEqual(res["chart"], "U")
        # u = 18 / 9.0 = 2.0
        self.assertAlmostEqual(res["center"], 2.0, places=7)
        self.assertEqual(res["observations"], [2.0, 2.0, 2.0])
        ucl_0 = 2.0 + 3.0 * math.sqrt(2.0 / 2.0)
        self.assertAlmostEqual(res["ucl"][0], ucl_0, places=7)

    def test_nelson_tests_attribute(self):
        # 10 subgroups with all 9 above center line for Test 2
        counts = [10] * 10
        opts = {
            "historical_p": 0.05,
            "tests": {
                "test1": {"enabled": True, "k": 3.0},
                "test2": {"enabled": True, "k": 9},
                "test3": {"enabled": False, "k": 6},
                "test4": {"enabled": False, "k": 14},
            },
        }
        res = run_attribute_control("P", counts, sample_sizes=100, options=opts)
        # Subgroup 9 and 10 should fail Test 2
        self.assertIn(9, res["test_failures"])
        self.assertIn(2, res["test_failures"][9])
        self.assertIn(10, res["test_failures"])
        self.assertIn(2, res["test_failures"][10])

    def test_report_formatting(self):
        counts = [5, 40, 5, 5]
        res = run_attribute_control("P", counts, sample_sizes=100, variable_name="Rejects")
        report = format_attribute_control_report(res)
        self.assertIn("P Chart of Rejects", report)
        self.assertIn("Test Results for P Chart of Rejects", report)
        self.assertIn("TEST 1.", report)
        self.assertIn("Test Failed at points: 2", report)
        self.assertIn("Process Information", report)
        self.assertIn("Subgroup size:", report)

    def test_presenter_attribute_control(self):
        p = Presenter()
        p.worksheet = Worksheet(
            "Attributes",
            [
                Column("Defects", values=[2, 4, 3, 1, 5, 2, 4]),
                Column("Size", values=[50, 50, 50, 50, 50, 50, 50]),
            ],
        )
        settings = {
            "chart_type": "P",
            "variables": [0],
            "subgroup_col_idx": 1,
            "is_subgroup_col": True,
            "options": {"k_sigma": 3.0},
        }
        entry = p.attribute_control_chart(settings=settings)
        self.assertIsNotNone(entry)
        self.assertIn("P Chart of Defects", entry["title"])
        self.assertEqual(entry["recipe"]["action"], "attribute_control_chart")
        self.assertEqual(entry["result"]["analysis"], "attribute_control")

    def test_laney_p_prime(self):
        # Overdispersed counts across large subgroups
        counts = [50, 150, 40, 180, 60, 200, 45, 170]
        sizes = [1000] * 8
        res_p = run_attribute_control("P", counts, sample_sizes=sizes)
        res_laney = run_attribute_control("P'", counts, sample_sizes=sizes)

        self.assertEqual(res_laney["chart"], "P'")
        self.assertGreater(res_laney["sigma_z"], 1.0)
        # Control limits should be wider for Laney P' than standard P
        self.assertGreater(res_laney["ucl"][0], res_p["ucl"][0])

        rep = format_attribute_control_report(res_laney)
        self.assertIn("Laney P' Chart", rep)
        self.assertIn("Sigma Z:", rep)

    def test_laney_u_prime(self):
        defects = [20, 60, 15, 80, 25, 90]
        units = [10.0] * 6
        res_u = run_attribute_control("U", defects, sample_sizes=units)
        res_laney = run_attribute_control("U'", defects, sample_sizes=units)

        self.assertEqual(res_laney["chart"], "U'")
        self.assertGreater(res_laney["sigma_z"], 1.0)
        self.assertGreater(res_laney["ucl"][0], res_u["ucl"][0])

        rep = format_attribute_control_report(res_laney)
        self.assertIn("Laney U' Chart", rep)
        self.assertIn("Sigma Z:", rep)

    def test_laney_dialogs(self):
        ws = Worksheet("Test", [Column("C1", values=[10, 20]), Column("C2", values=[100, 100])])
        dlg_p = AttributeChartDialog(ws, chart_type="P'")
        self.assertEqual(dlg_p.windowTitle(), "Laney P' Chart")
        dlg_u = AttributeChartDialog(ws, chart_type="U'")
        self.assertEqual(dlg_u.windowTitle(), "Laney U' Chart")


if __name__ == "__main__":
    unittest.main()
