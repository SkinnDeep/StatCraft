import unittest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication, QPushButton

from statcraft.model import Worksheet, Column
from statcraft.app import Presenter
from statcraft.connect import create_connected_analysis_from_entry
from statcraft.connect_hub import StatCraftAnalysisBar, ViewRCodeDialog


class TestRCodeExportBar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ws = Worksheet("YieldStudy", [
            Column("Yield", "number", [80.0, 85.0, 88.0, 92.0, 78.0, 82.0]),
            Column("Temp", "number", [150.0, 160.0, 170.0, 180.0, 145.0, 155.0]),
        ])
        self.presenter = Presenter()
        self.presenter.worksheet = self.ws
        self.presenter.multiple_regression(0, [1])
        self.entry = self.presenter.history[-1]
        self.conn = create_connected_analysis_from_entry(self.entry, self.ws)
        self.entry["connected_analysis"] = self.conn.to_dict()

    def test_analysis_bar_contains_r_export_buttons(self):
        mock_window = MagicMock()
        mock_window.presenter = self.presenter

        bar = StatCraftAnalysisBar(mock_window, self.entry, self.conn.to_dict())
        buttons = bar.findChildren(QPushButton)
        labels = [b.text() for b in buttons]

        self.assertTrue(any("Minitab Dialog" in t for t in labels), f"Labels: {labels}")
        self.assertTrue(any("Copy R Script" in t for t in labels), f"Labels: {labels}")
        self.assertTrue(any("View R Code" in t for t in labels), f"Labels: {labels}")
        self.assertTrue(any("ReportPad" in t for t in labels), f"Labels: {labels}")

    def test_copy_r_script_to_clipboard(self):
        mock_window = MagicMock()
        mock_window.presenter = self.presenter

        bar = StatCraftAnalysisBar(mock_window, self.entry, self.conn.to_dict())
        bar.copy_r_script()

        clipboard_text = QApplication.clipboard().text()
        self.assertIn("lm(", clipboard_text)
        self.assertIn('df[["Yield"]]', clipboard_text)

    def test_view_r_code_dialog(self):
        dlg = ViewRCodeDialog(None, self.conn.r_script, title="Regression R Script")
        self.assertTrue(dlg.isSizeGripEnabled())
        self.assertIn("lm(", dlg.code_view.toPlainText())
        dlg.close()


if __name__ == "__main__":
    unittest.main()
