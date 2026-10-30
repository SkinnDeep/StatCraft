"""GUI integration tests for native Two-Sample t dialogs and plot widget."""
import unittest
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.two_sample_t_engine import two_sample_t_settings, run_two_sample_t
from statcraft.two_sample_t_dialogs import (
    TwoSampleTDialog,
    TwoSampleTOptionsDialog,
    TwoSampleTGraphsDialog,
)
from statcraft.two_sample_t_chart import TwoSampleTPlotWidget


class TestTwoSampleTIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ws = Worksheet("Demo", [
            Column("A", "number", [10, 12, 11, 14, 13]),
            Column("B", "number", [7, 8, 9, 8, 8]),
            Column("Y", "number", [10, 12, 11, 14, 13, 7, 8, 9, 8, 8]),
            Column("Grp", "text", ["G1"] * 5 + ["G2"] * 5),
        ])

    def test_dialog_unstacked(self):
        dlg = TwoSampleTDialog(self.ws)
        self.assertEqual(dlg.combo_data.currentIndex(), 1)
        dlg.sample1_edit.setText("C1")
        dlg.sample2_edit.setText("C2")
        dlg._on_ok()
        self.assertIsNotNone(dlg.result_payload)
        payload = dlg.result_payload
        self.assertEqual(payload["sample1_col"], 0)
        self.assertEqual(payload["sample2_col"], 1)

    def test_options_and_graphs_dialogs(self):
        opts = {"confidence_level": 95.0, "hypothesized_difference": 0.0, "alternative": "not_equal", "assume_equal_variances": False}
        opt_dlg = TwoSampleTOptionsDialog(opts)
        opt_dlg.conf_edit.setText("99.0")
        opt_dlg.hyp_edit.setText("2.5")
        opt_dlg.alt_combo.setCurrentIndex(2)  # greater_than
        opt_dlg.pooled_cb.setChecked(True)
        opt_dlg._accept()
        self.assertEqual(opt_dlg.options["confidence_level"], 99.0)
        self.assertEqual(opt_dlg.options["hypothesized_difference"], 2.5)
        self.assertEqual(opt_dlg.options["alternative"], "greater_than")
        self.assertTrue(opt_dlg.options["assume_equal_variances"])

        graphs = {"individual_value_plot": True, "boxplot": True}
        grp_dlg = TwoSampleTGraphsDialog(graphs)
        grp_dlg.ivp_cb.setChecked(False)
        grp_dlg._accept()
        self.assertFalse(grp_dlg.graphs["individual_value_plot"])
        self.assertTrue(grp_dlg.graphs["boxplot"])

    def test_chart_widget_render(self):
        st = two_sample_t_settings(data_format=1, sample1_col=0, sample2_col=1)
        res = run_two_sample_t(self.ws, st)
        entry = {"title": "Two-Sample T-Test and CI: A, B", "result": res}
        widget = TwoSampleTPlotWidget(entry)
        widget.resize(560, 380)
        img = QImage(QSize(560, 380), QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        widget.render(img)
        self.assertFalse(img.isNull())


if __name__ == "__main__":
    unittest.main()
