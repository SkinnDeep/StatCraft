"""Unit and integration tests for Process Capability Analysis (Normal Distribution)."""

import unittest
import numpy as np

from statcraft.capability_engine import (
    c4,
    d2,
    d4,
    compute_capability_indices,
    compute_ppm_and_z,
    compute_confidence_intervals,
    run_normal_capability,
)
from statcraft.capability_report import format_capability_report
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter


class TestCapabilityConstants(unittest.TestCase):
    def test_c4_constants(self):
        # Known c4 values
        self.assertAlmostEqual(c4(2), 0.79788, places=4)
        self.assertAlmostEqual(c4(3), 0.88623, places=4)
        self.assertAlmostEqual(c4(4), 0.92132, places=4)
        self.assertAlmostEqual(c4(5), 0.93999, places=4)
        self.assertAlmostEqual(c4(10), 0.97266, places=4)

    def test_d2_constants(self):
        self.assertEqual(d2(2), 1.128)
        self.assertEqual(d2(5), 2.326)
        self.assertEqual(d2(10), 3.078)

    def test_d4_constants(self):
        self.assertEqual(d4(2), 0.954)
        self.assertEqual(d4(5), 2.257)


class TestCapabilityEngine(unittest.TestCase):
    def setUp(self):
        # Standard reproducible dataset: 100 observations from N(15, 1)
        np.random.seed(42)
        self.obs = np.random.normal(15.0, 1.0, 100).tolist()
        self.lsl = 12.0
        self.usl = 18.0
        self.target = 15.0

    def test_run_normal_capability_individuals(self):
        res = run_normal_capability(
            data=self.obs,
            subgroup_spec=1,
            lsl=self.lsl,
            usl=self.usl,
            target=self.target,
            estimate_method_eq1="amr",
            moving_range_len=2,
            include_ci=True
        )
        self.assertEqual(res["sample_n"], 100)
        self.assertAlmostEqual(res["mean"], np.mean(self.obs), places=4)
        self.assertGreater(res["stdev_within"], 0)
        self.assertGreater(res["stdev_overall"], 0)
        self.assertIsNotNone(res["cp"])
        self.assertIsNotNone(res["cpk"])
        self.assertIsNotNone(res["pp"])
        self.assertIsNotNone(res["ppk"])
        self.assertIsNotNone(res["cpm"])

        # Check CI
        self.assertIsNotNone(res["ci_cp"][0])
        self.assertIsNotNone(res["ci_cp"][1])
        self.assertIsNotNone(res["ci_cpk"][0])
        self.assertIsNotNone(res["ci_cpk"][1])

    def test_run_normal_capability_subgroups_size(self):
        # 20 subgroups of size 5
        res = run_normal_capability(
            data=self.obs,
            subgroup_spec=5,
            lsl=self.lsl,
            usl=self.usl,
            estimate_method_gt1="pooled",
            unbiased_within=True
        )
        self.assertEqual(res["sample_n"], 100)
        self.assertEqual(res["subgroup_count"], 20)
        self.assertAlmostEqual(res["subgroup_avg_size"], 5.0)
        self.assertIsNotNone(res["cp"])
        self.assertIsNotNone(res["cpk"])

    def test_run_normal_capability_subgroups_rbar_sbar(self):
        res_r = run_normal_capability(
            data=self.obs,
            subgroup_spec=5,
            lsl=self.lsl,
            usl=self.usl,
            estimate_method_gt1="rbar"
        )
        res_s = run_normal_capability(
            data=self.obs,
            subgroup_spec=5,
            lsl=self.lsl,
            usl=self.usl,
            estimate_method_gt1="sbar"
        )
        self.assertGreater(res_r["stdev_within"], 0)
        self.assertGreater(res_s["stdev_within"], 0)

    def test_run_normal_capability_subgroup_column(self):
        sub_col = [i // 5 for i in range(100)]
        res = run_normal_capability(
            data=self.obs,
            subgroup_spec=sub_col,
            lsl=self.lsl,
            usl=self.usl
        )
        self.assertEqual(res["subgroup_count"], 20)

    def test_run_normal_capability_across_rows(self):
        # 20 rows across 5 columns
        data_2d = [self.obs[i*5:(i+1)*5] for i in range(20)]
        res = run_normal_capability(
            data=data_2d,
            lsl=self.lsl,
            usl=self.usl
        )
        self.assertEqual(res["sample_n"], 100)
        self.assertEqual(res["subgroup_count"], 20)

    def test_one_sided_specs(self):
        res_l = run_normal_capability(data=self.obs, lsl=self.lsl)
        self.assertIsNone(res_l["cp"])
        self.assertIsNotNone(res_l["cpl"])
        self.assertEqual(res_l["cpk"], res_l["cpl"])

        res_u = run_normal_capability(data=self.obs, usl=self.usl)
        self.assertIsNone(res_u["cp"])
        self.assertIsNotNone(res_u["cpu"])
        self.assertEqual(res_u["cpk"], res_u["cpu"])

    def test_historical_parameters(self):
        res = run_normal_capability(
            data=self.obs,
            lsl=self.lsl,
            usl=self.usl,
            historical_mean=14.5,
            historical_stdev=1.2
        )
        self.assertEqual(res["mean"], 14.5)
        self.assertEqual(res["stdev_overall"], 1.2)

    def test_report_formatting(self):
        res = run_normal_capability(
            data=self.obs,
            lsl=self.lsl,
            usl=self.usl,
            target=self.target,
            include_ci=True
        )
        report = format_capability_report(res)
        self.assertIn("Process Capability Report", report)
        self.assertIn("Process Data", report)
        self.assertIn("Potential (Within) Capability", report)
        self.assertIn("Overall Capability", report)
        self.assertIn("Performance (parts per million)", report)


class TestCapabilityPresenter(unittest.TestCase):
    def test_presenter_normal_capability(self):
        p = Presenter()
        p.worksheet = Worksheet("CapabilityWS", [Column("Diameter", values=[10.1, 9.9, 10.2, 10.0, 9.8, 10.3, 10.1, 9.9, 10.0, 10.2])])

        entry = p.normal_capability(index=0, lsl=9.5, usl=10.5, target=10.0)
        self.assertIn("Normal Capability", entry["title"])
        self.assertIn("cpk", entry["result"])
        self.assertIn("ppk", entry["result"])
        self.assertIn("observed_perf", entry["result"])

    def test_presenter_normal_capability_settings(self):
        p = Presenter()
        p.worksheet = Worksheet("CapabilityWS", [
            Column("Diameter", values=[10.1, 9.9, 10.2, 10.0, 9.8, 10.3, 10.1, 9.9, 10.0, 10.2]),
            Column("Subgroup", values=[1, 1, 1, 1, 1, 2, 2, 2, 2, 2])
        ])

        settings = {
            "single_column": True,
            "column_name": "Diameter",
            "subgroup_spec": "Subgroup",
            "lsl": 9.5,
            "usl": 10.5,
            "options": {"target": 10.0, "include_ci": True, "stats_type": "capability"}
        }
        entry = p.normal_capability(settings=settings)
        self.assertIn("Normal Capability", entry["title"])
        self.assertEqual(entry["result"]["subgroup_count"], 2)
        self.assertIsNotNone(entry["result"]["cpk"])


class TestCapabilityUIAndChart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_dialogs_and_chart(self):
        from statcraft.capability_dialogs import (
            CapabilityOptionsDialog,
            CapabilityEstimateDialog,
            CapabilityDialog,
        )
        from statcraft.capability_chart import CapabilityPlotWidget

        # Options dialog
        opt_dlg = CapabilityOptionsDialog({"tolerance_k": 6.0, "include_ci": True})
        self.assertEqual(opt_dlg.edit_k.text(), "6.0")

        # Estimate dialog
        est_dlg = CapabilityEstimateDialog({"estimate_method_gt1": "pooled", "moving_range_len": 2})
        self.assertTrue(est_dlg.rb_pooled.isChecked())
        self.assertEqual(est_dlg.edit_mr_len.text(), "2")

        # Main dialog
        main_dlg = CapabilityDialog(["Col1", "Col2", "Subgroup"])
        self.assertEqual(main_dlg.col_list.count(), 3)
        self.assertTrue(main_dlg.rb_single_col.isChecked())

        # Chart widget
        np.random.seed(42)
        res = run_normal_capability(
            data=np.random.normal(10, 1, 50).tolist(),
            subgroup_spec=1,
            lsl=7.0,
            usl=13.0,
            target=10.0,
            include_ci=True
        )
        entry = {"title": "Process Capability Test", "result": res}
        chart = CapabilityPlotWidget(entry)
        chart.resize(800, 600)
        chart.repaint()
        self.assertEqual(chart.panels, [])


if __name__ == "__main__":
    unittest.main()
