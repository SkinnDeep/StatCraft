import math
import unittest
from PySide6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication([])

from statcraft.app import Presenter
from statcraft.time_weighted_control_dialogs import TimeWeightedChartDialog, TimeWeightedOptionsDialog
from statcraft.time_weighted_control_engine import (
    organize_subgroups,
    estimate_within_sigma,
    run_ewma_control,
    run_moving_average_control,
    run_cusum_control,
)
from statcraft.time_weighted_control_report import generate_time_weighted_report
from statcraft.model import Column, Worksheet


class TestTimeWeightedControl(unittest.TestCase):
    def test_organize_subgroups_constant(self):
        data = [1, 2, 3, 4, 5, 6]
        groups, sizes = organize_subgroups(data, subgroup_size=2)
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups[0], [1.0, 2.0])
        self.assertEqual(groups[1], [3.0, 4.0])
        self.assertEqual(groups[2], [5.0, 6.0])
        self.assertEqual(sizes, [2, 2, 2])

    def test_organize_subgroups_ids(self):
        data = [10, 11, 20, 21, 22]
        ids = ["A", "A", "B", "B", "B"]
        groups, sizes = organize_subgroups(data, subgroup_size=ids)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0], [10.0, 11.0])
        self.assertEqual(groups[1], [20.0, 21.0, 22.0])
        self.assertEqual(sizes, [2, 3])

    def test_organize_subgroups_rows(self):
        c1 = [1, 2]
        c2 = [3, 4]
        c3 = [5, 6]
        groups, sizes = organize_subgroups([], rows_are_subgroups=True, data_columns=[c1, c2, c3])
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0], [1.0, 3.0, 5.0])
        self.assertEqual(groups[1], [2.0, 4.0, 6.0])
        self.assertEqual(sizes, [3, 3])

    def test_ewma_control_computation(self):
        # 5 subgroups of size 1 with data [10, 10, 10, 10, 10]
        data = [10.0, 10.0, 10.0, 10.0, 10.0]
        res = run_ewma_control(data, subgroup_size=1, weight=0.2, options={"historical_sigma": 1.0, "historical_mean": 10.0})
        self.assertEqual(res["chart_type"], "EWMA")
        self.assertEqual(res["k_subgroups"], 5)
        self.assertEqual(res["center_line"], 10.0)
        # With identical data at mean, all z_i should equal 10.0
        for z in res["values"]:
            self.assertAlmostEqual(z, 10.0, places=5)
        # Limits should expand with i
        self.assertLess(res["ucl"][0], res["ucl"][1])
        self.assertLess(res["ucl"][1], res["ucl"][2])
        self.assertEqual(len(res["signals"]), 0)

    def test_ewma_out_of_control_signal(self):
        # 10 values with sudden jump at end
        data = [10.0]*8 + [18.0, 20.0]
        res = run_ewma_control(data, subgroup_size=1, weight=0.4, options={"historical_mean": 10.0, "historical_sigma": 1.0})
        self.assertTrue(len(res["signals"]) > 0)
        self.assertIn(10, res["signals"])

    def test_moving_average_computation(self):
        # 6 values with span 3
        data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        res = run_moving_average_control(data, subgroup_size=1, span=3, options={"historical_mean": 3.5, "historical_sigma": 1.0})
        self.assertEqual(res["chart_type"], "MA")
        self.assertEqual(res["span"], 3)
        # i=0: [1.0] -> 1.0
        # i=1: [1.0, 2.0] -> 1.5
        # i=2: [1.0, 2.0, 3.0] -> 2.0
        # i=3: [2.0, 3.0, 4.0] -> 3.0
        # i=4: [3.0, 4.0, 5.0] -> 4.0
        # i=5: [4.0, 5.0, 6.0] -> 5.0
        expected_ma = [1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
        for val, exp in zip(res["values"], expected_ma):
            self.assertAlmostEqual(val, exp, places=5)

    def test_cusum_control_computation(self):
        # Data with shift above target
        # Target = 0, sigma = 1
        data = [0.0, 0.0, 1.0, 1.5, 2.0, 2.5]
        res = run_cusum_control(data, subgroup_size=1, target=0.0, h=4.0, k=0.5, options={"historical_sigma": 1.0})
        self.assertEqual(res["chart_type"], "CUSUM")
        self.assertEqual(res["h"], 4.0)
        self.assertEqual(res["k"], 0.5)
        # C+ calculation:
        # i=0: y=0, cp = max(0, 0 - 0.5 + 0) = 0
        # i=1: y=0, cp = max(0, 0 - 0.5 + 0) = 0
        # i=2: y=1, cp = max(0, 1 - 0.5 + 0) = 0.5
        # i=3: y=1.5, cp = max(0, 1.5 - 0.5 + 0.5) = 1.5
        # i=4: y=2.0, cp = max(0, 2.0 - 0.5 + 1.5) = 3.0
        # i=5: y=2.5, cp = max(0, 2.5 - 0.5 + 3.0) = 5.0 (exceeds h=4.0)
        self.assertAlmostEqual(res["c_plus"][0], 0.0, places=5)
        self.assertAlmostEqual(res["c_plus"][2], 0.5, places=5)
        self.assertAlmostEqual(res["c_plus"][3], 1.5, places=5)
        self.assertAlmostEqual(res["c_plus"][4], 3.0, places=5)
        self.assertAlmostEqual(res["c_plus"][5], 5.0, places=5)
        self.assertIn(6, res["signals"])

    def test_cusum_with_fir(self):
        data = [1.0, 1.0]
        # With FIR = 2.0
        res = run_cusum_control(data, subgroup_size=1, target=0.0, h=4.0, k=0.5, options={"historical_sigma": 1.0, "use_fir": True, "fir": 2.0})
        # i=0: y=1, cp = max(0, 1 - 0.5 + 2.0) = 2.5
        self.assertAlmostEqual(res["c_plus"][0], 2.5, places=5)

    def test_reports(self):
        res_ewma = run_ewma_control([10, 11, 10, 12], subgroup_size=1, weight=0.2)
        rep = generate_time_weighted_report(res_ewma)
        self.assertIn("EWMA Chart of Data", rep)
        self.assertIn("Process Information", rep)
        self.assertIn("Weight of EWMA:", rep)

        res_cusum = run_cusum_control([10, 11, 10, 12], subgroup_size=1, target=10.0)
        rep_c = generate_time_weighted_report(res_cusum)
        self.assertIn("CUSUM Chart of Data", rep_c)
        self.assertIn("h (Decision Int):", rep_c)

    def test_dialogs_and_presenter(self):
        ws = Worksheet("TWTest", [
            Column("X", "number", [10.1, 9.9, 10.2, 10.0, 10.1, 10.3, 11.5, 11.8]),
            Column("Grp", "number", [1, 1, 1, 1, 2, 2, 2, 2]),
        ])
        dlg = TimeWeightedChartDialog(ws, chart_type="EWMA")
        dlg.edit_var.setText("X")
        dlg.edit_subgroup.setText("Grp")
        dlg._on_ok()
        cfg = dlg.get_configuration()
        self.assertEqual(cfg["chart_type"], "EWMA")
        self.assertEqual(cfg["columns"], ["X"])

        p = Presenter()
        p.worksheet = ws
        entry = p.time_weighted_control_chart(settings=cfg)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["result"]["k_subgroups"], 2)


if __name__ == "__main__":
    unittest.main()
