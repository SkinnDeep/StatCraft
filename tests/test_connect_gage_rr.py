import unittest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication, QPushButton

from statcraft.model import Worksheet, Column
from statcraft.app import Presenter
from statcraft.connect import create_connected_analysis_from_entry, create_connected_gage_rr
from statcraft.connect_hub import StatCraftAnalysisBar


class TestConnectGageRR(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # 3 parts, 2 operators, 2 replicates each = 12 rows
        parts = ["P1", "P1", "P2", "P2", "P3", "P3"] * 2
        operators = ["A"] * 6 + ["B"] * 6
        measurements = [
            10.2, 10.3, 12.1, 12.0, 15.4, 15.6,
            10.1, 10.4, 12.3, 12.1, 15.2, 15.5
        ]
        self.ws = Worksheet("GageStudy", [
            Column("Measurement", "number", measurements),
            Column("Part", "text", parts),
            Column("Operator", "text", operators),
        ])
        self.presenter = Presenter()
        self.presenter.worksheet = self.ws

    def test_gage_rr_connected_contract_and_r_script(self):
        # Run standard crossed Gage R&R via presenter
        self.presenter.gage_rr(0, 1, 2)
        entry = self.presenter.history[-1]

        conn = create_connected_analysis_from_entry(entry, self.ws)
        self.assertIsNotNone(conn)
        self.assertEqual(conn.analysis_type, "gage_rr")
        self.assertEqual(conn.response_name, "Measurement")
        self.assertIn("Part", conn.predictor_names)
        self.assertIn("Operator", conn.predictor_names)

        # Verify pure Base R script content
        r_script = conn.r_script
        self.assertIn("aov(", r_script)
        self.assertIn('df[["Measurement"]]', r_script)
        self.assertIn('df[["Part"]]', r_script)
        self.assertIn('df[["Operator"]]', r_script)
        self.assertIn("Gage R&R", r_script)
        self.assertIn("VarComp", r_script)
        self.assertIn("%Contribution", r_script)

    def test_connect_bridge_widget_label(self):
        self.presenter.gage_rr(0, 1, 2)
        entry = self.presenter.history[-1]
        conn = create_connected_analysis_from_entry(entry, self.ws)
        entry["connected_analysis"] = conn.to_dict()

        mock_window = MagicMock()
        mock_window.presenter = self.presenter

        # Check analysis bar reflects Minitab Dialog and R export actions
        bridge = StatCraftAnalysisBar(mock_window, entry, conn.to_dict())
        buttons = bridge.findChildren(QPushButton)
        labels = [b.text() for b in buttons]
        self.assertTrue(any("Minitab Dialog" in text for text in labels), f"Got labels: {labels}")
        self.assertTrue(any("Copy R Script" in text for text in labels), f"Got labels: {labels}")
        self.assertTrue(any("View R Code" in text for text in labels), f"Got labels: {labels}")


if __name__ == "__main__":
    unittest.main()
