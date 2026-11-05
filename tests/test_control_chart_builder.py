"""Unit tests for JMP Control Chart Builder platform."""
import unittest
import numpy as np

from statcraft.app import Presenter
from statcraft.model import Column, Worksheet
from statcraft.control_chart_builder_engine import calculate_control_chart_builder
from statcraft.control_chart_builder_report import (
    format_control_chart_builder_report,
    get_control_chart_builder_tables,
)


class TestControlChartBuilder(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        # Synthetic process data with a shift in Phase 2
        p1 = list(np.random.normal(10.0, 1.0, 20))
        p2 = list(np.random.normal(12.5, 1.0, 20))
        # Add an obvious outlier in Phase 2
        p2[10] = 18.0

        y_vals = p1 + p2
        phases = ["Phase 1"] * 20 + ["Phase 2"] * 20
        subgroups = [i // 4 + 1 for i in range(40)]

        self.worksheet = Worksheet("TestQuality", [
            Column("Measurement", values=y_vals),
            Column("Phase", kind="text", values=phases),
            Column("Subgroup", values=subgroups),
        ])
        self.presenter = Presenter()
        self.presenter.worksheet = self.worksheet

    def test_imr_engine_single_phase(self):
        y_vals = [10.1, 10.3, 9.8, 10.2, 10.5, 9.9, 10.0, 10.2, 10.4, 10.1]
        res = calculate_control_chart_builder(y_values=y_vals, chart_type="imr")
        self.assertEqual(res["chart_type"], "imr")
        self.assertEqual(len(res["phases"]), 1)
        p0 = res["phases"][0]
        self.assertAlmostEqual(p0["mean"], 10.15, places=2)
        self.assertTrue(p0["ucl_x"] > p0["mean"] > p0["lcl_x"])
        self.assertEqual(len(res["points"]), 10)
        self.assertEqual(len(res["disp_points"]), 10)

    def test_multiphase_partitioning_and_alarms(self):
        y_col = self.worksheet.columns[0].values
        ph_col = self.worksheet.columns[1].values
        res = calculate_control_chart_builder(
            y_values=y_col,
            phase_values=ph_col,
            chart_type="imr",
        )
        self.assertEqual(len(res["phases"]), 2)
        self.assertEqual(res["phases"][0]["phase"], "Phase 1")
        self.assertEqual(res["phases"][1]["phase"], "Phase 2")
        # Center line in Phase 2 should be higher due to the shifted mean
        self.assertGreater(res["phases"][1]["mean"], res["phases"][0]["mean"])
        # Should detect the outlier alarm point in Phase 2
        self.assertGreater(res["total_alarms"], 0)
        self.assertFalse(res["is_stable"])

    def test_subgrouped_xbar_r(self):
        y_col = self.worksheet.columns[0].values
        sub_col = self.worksheet.columns[2].values
        res = calculate_control_chart_builder(
            y_values=y_col,
            subgroup_values=sub_col,
            chart_type="xbar_r",
        )
        self.assertEqual(res["chart_type"], "xbar_r")
        # 40 items in groups of 4 => 10 subgroups
        self.assertEqual(len(res["points"]), 10)
        self.assertEqual(res["disp_label"], "Sample Range")

    def test_presenter_integration_and_recipe(self):
        entry = self.presenter.control_chart_builder(
            y_indices=[0],
            phase_index=1,
            chart_type="auto",
        )
        self.assertIn("result", entry)
        res = entry["result"]
        self.assertEqual(res["analysis"], "control_chart_builder")
        self.assertIn("recipe", entry)
        self.assertEqual(entry["recipe"]["action"], "control_chart_builder")

        # Test reports and tables
        text = format_control_chart_builder_report(res)
        self.assertIn("Control Chart Builder", text)
        self.assertIn("Phase 1", text)
        self.assertIn("Phase 2", text)

        tables = get_control_chart_builder_tables(res)
        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[0]["title"], "Primary Chart Limits (Individual Value)")

    def test_chart_widget_instantiation(self):
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        entry = self.presenter.control_chart_builder(y_indices=[0], phase_index=1)
        from statcraft.control_chart_builder_chart import ControlChartBuilderWidget
        widget = ControlChartBuilderWidget(entry)
        self.assertIsNotNone(widget)
        self.assertEqual(len(widget.result["phases"]), 2)


if __name__ == "__main__":
    unittest.main()
