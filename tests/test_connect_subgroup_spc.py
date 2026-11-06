import unittest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication, QPushButton

from statcraft.model import Worksheet, Column
from statcraft.app import Presenter
from statcraft.connect import create_connected_analysis_from_entry, create_connected_subgroup_spc
from statcraft.connect_hub import StatCraftAnalysisBar


class TestConnectSubgroupSPC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # 4 subgroups of size 3 = 12 observations
        measurements = [
            10.2, 10.5, 10.3,
            12.0, 11.8, 12.2,
            10.0, 10.1, 10.2,
            11.5, 11.6, 11.4
        ]
        subgroups = ["SG1", "SG1", "SG1", "SG2", "SG2", "SG2", "SG3", "SG3", "SG3", "SG4", "SG4", "SG4"]
        self.ws = Worksheet("SPCStudy", [
            Column("User's Measurement", "number", measurements),
            Column("Subgroup Batch", "text", subgroups),
        ])
        self.presenter = Presenter()
        self.presenter.worksheet = self.ws

    def test_xbar_r_connected_contract_and_r_script(self):
        # Run Xbar-R chart stacked with subgroup factor
        self.presenter.subgroup_control_chart(chart_type="xbar_r", stacked=True, response_index=0, factor_index=1)
        entry = self.presenter.history[-1]

        conn = create_connected_analysis_from_entry(entry, self.ws)
        self.assertIsNotNone(conn)
        self.assertEqual(conn.analysis_type, "xbar_r")
        self.assertEqual(conn.response_name, "User's Measurement")
        self.assertIn("Subgroup Batch", conn.predictor_names)

        # Verify pure Base R script content
        r_script = conn.r_script
        self.assertIn('df[["User\'s Measurement"]]', r_script)
        self.assertIn("X-bar Chart", r_script)
        self.assertIn("R Chart", r_script)
        self.assertIn("UCL", r_script)
        self.assertIn("LCL", r_script)
        self.assertIn("par(mfrow = c(2, 1))", r_script)

        # Verify NO raw python lists like '[74.029, ...]' appear in R code
        self.assertNotIn("UCL: [", r_script)
        self.assertNotIn("abline(h = [", r_script)
        self.assertIn("levels = unique(", r_script)

    def test_xbar_s_connected_contract_and_r_script(self):
        # Run Xbar-S chart with constant subgroup size
        self.presenter.subgroup_control_chart(chart_type="xbar_s", stacked=True, response_index=0, subgroup_size=3)
        entry = self.presenter.history[-1]

        conn = create_connected_analysis_from_entry(entry, self.ws)
        self.assertIsNotNone(conn)
        self.assertEqual(conn.analysis_type, "xbar_s")
        self.assertEqual(conn.response_name, "User's Measurement")

        # Verify pure Base R script content
        r_script = conn.r_script
        self.assertIn('df[["User\'s Measurement"]]', r_script)
        self.assertIn("X-bar Chart", r_script)
        self.assertIn("S Chart", r_script)
        self.assertIn("UCL", r_script)
        self.assertNotIn("UCL: [", r_script)
        self.assertNotIn("abline(h = [", r_script)

    def test_connect_bridge_widget_label(self):
        self.presenter.subgroup_control_chart(chart_type="xbar_r", stacked=True, response_index=0, factor_index=1)
        entry = self.presenter.history[-1]
        conn = create_connected_analysis_from_entry(entry, self.ws)
        entry["connected_analysis"] = conn.to_dict()

        mock_window = MagicMock()
        mock_window.presenter = self.presenter

        bridge = StatCraftAnalysisBar(mock_window, entry, conn.to_dict())
        buttons = bridge.findChildren(QPushButton)
        labels = [b.text() for b in buttons]
        self.assertTrue(any("Minitab Dialog" in text for text in labels), f"Got labels: {labels}")
        self.assertTrue(any("Copy R Script" in text for text in labels), f"Got labels: {labels}")
        self.assertTrue(any("View R Code" in text for text in labels), f"Got labels: {labels}")


if __name__ == "__main__":
    unittest.main()
