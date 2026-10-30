"""Unit tests for Process Capability Sixpack (Normal Distribution)."""

import unittest
import numpy as np
import os, sys

from statcraft.sixpack_engine import run_normal_sixpack
from statcraft.sixpack_report import format_sixpack_report
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter, format_entry


class TestCapabilitySixpack(unittest.TestCase):
    def setUp(self):
        np.random.seed(123)
        self.data_subgroups = np.random.normal(loc=10.0, scale=0.5, size=100).tolist()
        self.subgroup_ids = [i // 5 + 1 for i in range(100)]
        self.col_a = [x + 0.1 for x in self.data_subgroups[:50]]
        self.col_b = [x - 0.1 for x in self.data_subgroups[50:]]

    def test_sixpack_single_col_subgroup_size(self):
        settings = {
            "data_mode": "single_column",
            "column_name": "Length",
            "column_data": self.data_subgroups,
            "subgroup_type": "size",
            "subgroup_size": 5,
            "lsl": 8.5,
            "usl": 11.5,
            "target": 10.0,
            "options": {
                "tolerance_k": 6.0,
                "confidence_level": 95.0,
                "within_subgroup_method": "pooled",
                "test1": True,
            }
        }
        res = run_normal_sixpack(settings)
        self.assertEqual(res["analysis"], "capability_sixpack_normal")
        self.assertEqual(res["sample_n"], 100)
        self.assertEqual(res["subgroup_count"], 20)
        self.assertAlmostEqual(res["mean"], 10.0, delta=0.2)

        # Panel 1: Xbar
        px = res["panel_xbar"]
        self.assertEqual(px["title"], "Xbar Chart")
        self.assertEqual(len(px["x"]), 20)
        self.assertEqual(len(px["y"]), 20)
        self.assertIsNotNone(px["ucl_val"])
        self.assertIsNotNone(px["lcl_val"])
        self.assertGreater(px["ucl_val"], px["lcl_val"])

        # Panel 2: R Chart
        pd = res["panel_disp"]
        self.assertEqual(pd["title"], "R Chart")
        self.assertEqual(len(pd["x"]), 20)
        self.assertEqual(len(pd["y"]), 20)
        self.assertIsNotNone(pd["ucl_val"])
        self.assertGreater(pd["ucl_val"], pd["lcl_val"])

        # Panel 3: Last 25
        plast = res["panel_last25"]
        self.assertEqual(plast["title"], "Last 20 Subgroups")
        self.assertEqual(len(plast["subgroup_indices"]), 20)
        self.assertEqual(len(plast["points"]), 100)

        # Panel 4: Histogram
        phist = res["panel_hist"]
        self.assertEqual(phist["title"], "Capability Histogram")
        self.assertIn("observations", phist)
        self.assertEqual(len(phist["observations"]), 100)

        # Panel 5: Normality
        pnorm = res["panel_norm"]
        self.assertEqual(pnorm["title"], "Normal Probability Plot")
        self.assertIsNotNone(pnorm["ad_stat"])
        self.assertIsNotNone(pnorm["p_value"])
        self.assertEqual(len(pnorm["observed"]), 100)
        self.assertEqual(len(pnorm["normal_scores"]), 100)

        # Panel 6: Capability Summary
        psum = res["panel_summary"]
        self.assertEqual(psum["title"], "Capability Plot")
        self.assertIsNotNone(psum["cp"])
        self.assertIsNotNone(psum["cpk"])
        self.assertIsNotNone(psum["pp"])
        self.assertIsNotNone(psum["ppk"])
        self.assertGreater(psum["cp"], 0)
        self.assertGreater(psum["pp"], 0)
        self.assertIn("ppm_observed", psum)
        self.assertIn("ppm_exp_within", psum)
        self.assertIn("ppm_exp_overall", psum)

    def test_sixpack_individual_observations(self):
        # n = 1 -> I Chart and Moving Range Chart
        ind_data = self.data_subgroups[:30]
        settings = {
            "data_mode": "single_column",
            "column_name": "Weight",
            "column_data": ind_data,
            "subgroup_type": "size",
            "subgroup_size": 1,
            "lsl": 8.0,
            "usl": 12.0,
            "options": {"within_subgroup_method": "amr"}
        }
        res = run_normal_sixpack(settings)
        self.assertEqual(res["panel_xbar"]["title"], "I Chart")
        self.assertEqual(res["panel_disp"]["title"], "Moving Range Chart")
        self.assertEqual(res["subgroup_avg_size"], 1.0)
        self.assertEqual(res["subgroup_count"], 30)

    def test_sixpack_large_subgroups_s_chart(self):
        # n = 10 -> S Chart
        big_data = np.random.normal(10.0, 1.0, 50).tolist()
        settings = {
            "data_mode": "single_column",
            "column_name": "Strength",
            "column_data": big_data,
            "subgroup_type": "size",
            "subgroup_size": 10,
            "lsl": 7.0,
            "usl": 13.0,
            "options": {"within_subgroup_method": "sbar"}
        }
        res = run_normal_sixpack(settings)
        self.assertEqual(res["panel_disp"]["title"], "S Chart")
        self.assertEqual(res["subgroup_avg_size"], 10.0)

    def test_sixpack_subgroups_across_rows(self):
        row_data = list(zip(self.col_a, self.col_b))
        settings = {
            "data_mode": "subgroups_across",
            "column_name": "A, B",
            "cols_across": ["A", "B"],
            "cols_across_data": [self.col_a, self.col_b],
            "lsl": 8.0,
            "usl": 12.0,
        }
        res = run_normal_sixpack(settings)
        self.assertEqual(res["subgroup_count"], 50)
        self.assertEqual(res["subgroup_avg_size"], 2.0)
        self.assertEqual(res["sample_n"], 100)

    def test_sixpack_report_formatting(self):
        settings = {
            "data_mode": "single_column",
            "column_name": "Thickness",
            "column_data": self.data_subgroups,
            "subgroup_type": "size",
            "subgroup_size": 5,
            "lsl": 8.5,
            "usl": 11.5,
            "target": 10.0,
        }
        res = run_normal_sixpack(settings)
        report = format_sixpack_report(res)
        self.assertIn("Process Capability Sixpack Report for Thickness", report)
        self.assertIn("Process Data", report)
        self.assertIn("Control Chart Diagnostics", report)
        self.assertIn("Normality Assessment", report)
        self.assertIn("Potential (Within) Capability", report)
        self.assertIn("Overall Capability", report)
        self.assertIn("Performance (parts per million)", report)

    def test_presenter_integration_and_recipe(self):
        p = Presenter()
        p.worksheet = Worksheet("SixpackSheet", [
            Column("Measurement", "number", self.data_subgroups),
            Column("Batch", "number", self.subgroup_ids),
        ])
        settings = {
            "single_column": True,
            "column_name": "Measurement",
            "subgroup_spec": "5",
            "lsl": 8.5,
            "usl": 11.5,
            "options": {"target": 10.0}
        }
        entry = p.normal_sixpack(settings=settings)
        self.assertEqual(entry["recipe"]["action"], "normal_sixpack")
        self.assertFalse(p.result_stale(entry))

        # Check recipe columns
        from statcraft.recipes import columns
        cols = columns(entry["recipe"])
        self.assertEqual(cols, [0])

        # Dirty state
        p.set_cell(0, 0, "99.9")
        self.assertTrue(p.result_stale(entry))

        # Rerun
        rerun_entry = p.rerun_result(entry)
        self.assertFalse(p.result_stale(rerun_entry))

    def test_chart_widget_render(self):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QImage
        from PySide6.QtCore import Qt, QSize
        from statcraft.sixpack_chart import CapabilitySixpackWidget

        app = QApplication.instance() or QApplication(sys.argv)
        p = Presenter()
        p.worksheet = Worksheet("Sheet1", [Column("X", "number", self.data_subgroups)])
        entry = p.normal_sixpack(settings={
            "single_column": True,
            "column_name": "X",
            "subgroup_spec": "5",
            "lsl": 8.5,
            "usl": 11.5,
        })
        widget = CapabilitySixpackWidget(entry)
        widget.resize(950, 650)
        img = QImage(QSize(950, 650), QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.white)
        widget.render(img)
        self.assertFalse(img.isNull())
        self.assertEqual(img.width(), 950)
        self.assertEqual(img.height(), 650)

    def test_sixpack_dialogs(self):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        from statcraft.sixpack_dialogs import CapabilitySixpackDialog, SixpackTestsDialog

        app = QApplication.instance() or QApplication(sys.argv)
        ws = Worksheet("Demo", [
            Column("Diameter", "number", self.data_subgroups),
            Column("Subgroup", "number", self.subgroup_ids),
        ])
        dlg = CapabilitySixpackDialog(ws)
        self.assertEqual(dlg.col_list.count(), 2)
        dlg.rb_single_col.setChecked(True)
        dlg.edit_single_col.setText("Diameter")
        dlg.edit_sub_size.setText("5")
        dlg.edit_lsl.setText("8.5")
        dlg.edit_usl.setText("11.5")
        dlg._accept()

        self.assertIsNotNone(dlg.selected_params)
        self.assertTrue(dlg.selected_params["single_column"])
        self.assertEqual(dlg.selected_params["column_name"], "Diameter")
        self.assertEqual(dlg.selected_params["lsl"], 8.5)
        self.assertEqual(dlg.selected_params["usl"], 11.5)

        # Test subdialog
        tdlg = SixpackTestsDialog(dlg.options)
        tdlg.chk_test1.setChecked(True)
        tdlg.chk_test2.setChecked(True)
        tdlg._accept()
        self.assertTrue(tdlg.options["test1"])
        self.assertTrue(tdlg.options["test2"])


if __name__ == "__main__":
    unittest.main()
