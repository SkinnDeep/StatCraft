"""Unit and integration tests for Individuals-Moving Range (I-MR) Chart."""
import math
import unittest
from PySide6.QtWidgets import QApplication

from statcraft.imr_engine import (
    compute_moving_ranges,
    parse_subgroup_omission,
    run_imr_chart,
)
from statcraft.imr_report import format_imr_report
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft import recipes


class IMRChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_basic_imr_calculation(self):
        # 5 observations: [1, 2, 3, 4, 5]
        # Mean = 3.0
        # MR: [None, 1, 1, 1, 1] -> avg_mr = 1.0
        # sigma_within = 1.0 / d2(2) = 1.0 / 1.128379... = 0.8862269...
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        res = run_imr_chart(data, variable_name="Sample")

        self.assertEqual(res["count"], 5)
        self.assertEqual(res["missing"], 0)
        self.assertAlmostEqual(res["i_center"], 3.0)
        self.assertEqual(res["moving_ranges"], [None, 1.0, 1.0, 1.0, 1.0])
        self.assertAlmostEqual(res["mr_center"], 1.0)
        d2_2 = 1.128
        expected_sigma = 1.0 / d2_2
        self.assertAlmostEqual(res["within_stdev"], expected_sigma, places=4)
        self.assertAlmostEqual(res["i_ucl"], 3.0 + 3.0 * expected_sigma, places=4)
        self.assertAlmostEqual(res["i_lcl"], 3.0 - 3.0 * expected_sigma, places=4)
        self.assertEqual(res["mr_lcl"], 0.0)
        self.assertGreater(res["mr_ucl"], 1.0)

    def test_missing_values_gaps_not_bridged(self):
        # Gaps break span
        data = [10.0, None, 20.0, 22.0, None, 30.0]
        res = run_imr_chart(data, options={"span": 2})
        self.assertEqual(res["count"], 4)
        self.assertEqual(res["missing"], 2)
        # MR at idx 3 is |22 - 20| = 2.0; all others involving None are None
        self.assertEqual(res["moving_ranges"], [None, None, None, 2.0, None, None])

    def test_estimation_methods(self):
        data = [10.0, 12.0, 11.0, 15.0, 13.0, 18.0, 14.0]
        # AMR
        res_amr = run_imr_chart(data, options={"estimation_method": "amr"})
        # MMR
        res_mmr = run_imr_chart(data, options={"estimation_method": "mmr"})
        # SRMSSD
        res_srmssd = run_imr_chart(data, options={"estimation_method": "srmssd"})

        self.assertGreater(res_amr["within_stdev"], 0.0)
        self.assertGreater(res_mmr["within_stdev"], 0.0)
        self.assertGreater(res_srmssd["within_stdev"], 0.0)

    def test_span_variation(self):
        data = [1.0, 3.0, 2.0, 6.0, 5.0, 8.0]
        # span 3
        res3 = run_imr_chart(data, options={"span": 3})
        self.assertEqual(res3["span"], 3)
        self.assertIsNone(res3["moving_ranges"][0])
        self.assertIsNone(res3["moving_ranges"][1])
        # window [1, 3, 2] -> ptp = 2
        self.assertEqual(res3["moving_ranges"][2], 2.0)

    def test_omission_subgroups(self):
        data = [10.0, 10.0, 100.0, 10.0, 10.0]  # Point 3 is an extreme outlier
        omit_spec = "3"
        res_clean = run_imr_chart(data, options={"omit_subgroups": omit_spec})
        # When point 3 is omitted, mean should be 10.0
        self.assertAlmostEqual(res_clean["i_center"], 10.0)
        # And point 3 fails Test 1
        self.assertIn(3, res_clean["i_signals"])

    def test_parse_omission(self):
        s1 = parse_subgroup_omission("3 12:15, 20-22")
        self.assertEqual(s1, {3, 12, 13, 14, 15, 20, 21, 22})

    def test_historical_parameters(self):
        data = [10.0, 12.0, 11.0, 13.0]
        res = run_imr_chart(data, options={"historical_mean": 15.0, "historical_sigma": 2.5})
        self.assertEqual(res["i_center"], 15.0)
        self.assertEqual(res["within_stdev"], 2.5)
        self.assertAlmostEqual(res["i_ucl"], 15.0 + 3.0 * 2.5)
        self.assertAlmostEqual(res["i_lcl"], 15.0 - 3.0 * 2.5)

    def test_nelson_tests_detection(self):
        # 1. Test 1: point > 3 sigma
        # 2. Test 2: 9 points in a row on same side of center line
        data = [0.0] * 5 + [10.0] + [0.0] * 5
        res = run_imr_chart(data, options={
            "historical_mean": 0.0,
            "historical_sigma": 1.0,
            "tests": {
                "test1": {"enabled": True, "k": 3.0},
                "test2": {"enabled": True, "k": 9},
            }
        })
        # Point 6 is 10.0 > 3 sigma
        self.assertIn(6, res["test_failures"])
        self.assertIn(1, res["test_failures"][6])

        # Sequence of 9 positive values
        data_pos = [1.0] * 10
        res2 = run_imr_chart(data_pos, options={
            "historical_mean": 0.0,
            "historical_sigma": 1.0,
            "tests": {
                "test2": {"enabled": True, "k": 9},
            }
        })
        self.assertIn(9, res2["test_failures"])
        self.assertIn(2, res2["test_failures"][9])

    def test_report_formatting(self):
        data = [10.0, 11.0, 9.0, 10.5, 45.0]  # Outlier at pt 5
        res = run_imr_chart(data, variable_name="Diameter")
        rep = format_imr_report(res)
        self.assertIn("I-MR Chart of Diameter", rep)
        self.assertIn("Test Results for I Chart", rep)
        self.assertIn("Process Information", rep)
        self.assertIn("Mean (I Center)", rep)

    def test_presenter_integration_and_recipe(self):
        ws = Worksheet(name="TestWS")
        col = Column("Length", "number", [10.2, 10.5, 9.8, 10.1, 10.4, 9.9, 10.3, 10.0])
        ws.columns.append(col)
        presenter = Presenter()
        presenter.worksheet = ws

        entry = presenter.imr_chart(settings={"variables": [0], "options": {"span": 2}})
        self.assertIsNotNone(entry)
        self.assertEqual(entry["title"], "I-MR Chart of Length")
        self.assertEqual(entry["recipe"]["action"], "imr_chart")

        # Test recipe rerun / replay
        replayed = recipes.run(presenter, entry["recipe"])
        self.assertEqual(replayed["title"], "I-MR Chart of Length")
        self.assertAlmostEqual(replayed["result"]["i_center"], entry["result"]["i_center"])

    def test_dialogs_and_widget(self):
        from statcraft.imr_dialogs import IMRChartDialog, IMROptionsDialog
        from statcraft.imr_chart import IMRChartWidget

        ws = Worksheet(name="TestWS")
        col = Column("Weight", "number", [50.1, 51.2, 49.8, 50.4, 52.0, 48.9])
        ws.columns.append(col)

        # Dialog instantiation
        dlg = IMRChartDialog(ws)
        self.assertEqual(dlg.windowTitle(), "Individuals - Moving Range Chart")

        opt_dlg = IMROptionsDialog(dlg, dlg.options)
        self.assertEqual(opt_dlg.windowTitle(), "I-MR Options")

        # Chart Widget instantiation and painting
        res = run_imr_chart(col.values, variable_name="Weight")
        widget = IMRChartWidget({"title": "I-MR Chart of Weight", "result": res})
        self.assertEqual(len(widget.panels), 2)
        widget.resize(800, 600)
        widget.repaint()


if __name__ == "__main__":
    unittest.main()
