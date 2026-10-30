import math
import unittest
from PySide6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])

from statcraft.app import Presenter
from statcraft.rare_event_control_dialogs import RareEventChartDialog, RareEventOptionsDialog
from statcraft.rare_event_control_engine import (
    convert_dates_to_intervals,
    run_g_chart,
    run_t_chart,
)
from statcraft.rare_event_control_report import generate_rare_event_report
from statcraft.model import Column, Worksheet


class TestRareEventControl(unittest.TestCase):
    def test_convert_dates_to_intervals(self):
        dates = ["2026-01-01", "2026-01-03", "2026-01-04"]
        intervals = convert_dates_to_intervals(dates, unit="Days")
        self.assertEqual(len(intervals), 2)
        self.assertAlmostEqual(intervals[0], 2.0, places=4)
        self.assertAlmostEqual(intervals[1], 1.0, places=4)

        intervals_hours = convert_dates_to_intervals(dates, unit="Hours")
        self.assertAlmostEqual(intervals_hours[0], 48.0, places=4)
        self.assertAlmostEqual(intervals_hours[1], 24.0, places=4)

    def test_g_chart_between_events(self):
        # Opportunities between events (0, 1, 2...)
        data = [10, 12, 10, 11, 10, 12, 9, 11]
        res = run_g_chart(data, form_of_data=1, method_of_count=0)
        self.assertEqual(res["chart_type"], "G")
        self.assertEqual(res["k_subgroups"], 8)
        self.assertEqual(res["method_of_count"], 0)
        self.assertGreater(res["p"], 0.0)
        self.assertLess(res["p"], 1.0)
        self.assertGreater(res["center_line"], 0.0)
        self.assertGreater(res["ucl_val"], res["center_line"])
        self.assertLessEqual(res["lcl_val"], res["center_line"])

    def test_g_chart_until_event(self):
        # Opportunities until an event (1, 2, 3...)
        data = [5, 6, 4, 5, 6, 5]
        res = run_g_chart(data, form_of_data=1, method_of_count=1)
        self.assertEqual(res["chart_type"], "G")
        self.assertEqual(res["method_of_count"], 1)
        # For mean ~ 5.16, p_hat = 1/5.16 ~ 0.1935
        self.assertAlmostEqual(res["p"], 1.0 / (31.0 / 6.0), places=5)

    def test_g_chart_benneyan_signal(self):
        # 3 consecutive zeros triggers Benneyan signal
        data = [10, 12, 11, 0, 0, 0, 10]
        res = run_g_chart(data, form_of_data=1, method_of_count=0, options={"benneyan_threshold": 3})
        self.assertTrue(len(res["benneyan_signals"]) > 0)
        self.assertIn(6, res["benneyan_signals"])

    def test_g_chart_omission_and_historical(self):
        data = [10, 100, 10, 10]
        res_user_p = run_g_chart(data, options={"p": 0.08, "omit_subgroups": "2"})
        self.assertAlmostEqual(res_user_p["p"], 0.08, places=5)
        self.assertIn(2, res_user_p["omit_subgroups"])

    def test_t_chart_exponential(self):
        times = [2.5, 3.1, 1.9, 4.0, 2.8, 3.5]
        res = run_t_chart(times, form_of_data=1, distribution="Exponential")
        self.assertEqual(res["chart_type"], "T")
        self.assertEqual(res["shape"], 1.0)
        self.assertGreater(res["center_line"], 0.0)
        self.assertGreater(res["ucl_val"], res["center_line"])

    def test_t_chart_weibull(self):
        times = [10.0, 12.0, 15.0, 11.0, 14.0]
        res = run_t_chart(times, form_of_data=1, distribution="Weibull", options={"shape": 1.5})
        self.assertEqual(res["chart_type"], "T")
        self.assertAlmostEqual(res["shape"], 1.5, places=5)

    def test_t_chart_signals(self):
        times = [5.0]*10 + [50.0]  # Point 11 is an extreme spike
        res = run_t_chart(times, form_of_data=1)
        self.assertIn(11, res["test1_signals"])

    def test_reports(self):
        res_g = run_g_chart([5, 6, 7, 8])
        rep_g = generate_rare_event_report(res_g)
        self.assertIn("G Chart of Opportunities", rep_g)
        self.assertIn("Counting Method:", rep_g)

        res_t = run_t_chart([2.0, 3.0, 4.0])
        rep_t = generate_rare_event_report(res_t)
        self.assertIn("T Chart of Time", rep_t)
        self.assertIn("Distribution:", rep_t)

    def test_dialogs_and_presenter(self):
        ws = Worksheet("REDemo", [
            Column("Counts", "number", [10, 12, 14, 11, 13]),
        ])
        dlg = RareEventChartDialog(ws, chart_type="G")
        dlg.edit_var.setText("Counts")
        dlg._on_ok()
        cfg = dlg.get_configuration()
        self.assertEqual(cfg["chart_type"], "G")
        self.assertEqual(cfg["columns"], ["Counts"])

        p = Presenter()
        p.worksheet = ws
        entry = p.rare_event_control_chart(settings=cfg)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["result"]["k_subgroups"], 5)


if __name__ == "__main__":
    unittest.main()
