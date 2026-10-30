"""GUI integration tests for native Paired t dialogs and plot widget."""
import unittest
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.paired_t_engine import paired_t_settings, run_paired_t
from statcraft.paired_t_dialogs import (
    PairedTDialog,
    PairedTOptionsDialog,
    PairedTGraphsDialog,
)
from statcraft.paired_t_chart import PairedTPlotWidget


class TestPairedTIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ws = Worksheet("Demo", [
            Column("Pre", "number", [12.5, 13.0, 14.2, 11.8, 13.5, 12.0]),
            Column("Post", "number", [10.0, 11.5, 12.0, 10.5, 11.0, 10.8]),
        ])

    def test_dialog_unstacked(self):
        dlg = PairedTDialog(self.ws)
        self.assertEqual(dlg.combo_data.currentIndex(), 0)
        dlg.sample1_edit.setText("C1")
        dlg.sample2_edit.setText("C2")
        dlg._on_ok()
        self.assertIsNotNone(dlg.result_payload)
        payload = dlg.result_payload
        self.assertEqual(payload["data_format"], 1)
        self.assertEqual(payload["sample1_col"], 0)
        self.assertEqual(payload["sample2_col"], 1)

    def test_dialog_summarized(self):
        dlg = PairedTDialog(self.ws)
        dlg.combo_data.setCurrentIndex(1)  # Summarized data
        self.assertFalse(dlg.graphs_btn.isEnabled())
        dlg.size_edit.setText("18")
        dlg.mean_edit.setText("4.2")
        dlg.sd_edit.setText("1.1")
        dlg._on_ok()
        self.assertIsNotNone(dlg.result_payload)
        payload = dlg.result_payload
        self.assertEqual(payload["data_format"], 2)
        self.assertEqual(payload["summarized"]["n"], 18)
        self.assertEqual(payload["summarized"]["mean"], 4.2)
        self.assertEqual(payload["summarized"]["sd"], 1.1)

    def test_options_and_graphs_dialogs(self):
        opts = {"confidence_level": 95.0, "hypothesized_difference": 0.0, "alternative": "not_equal"}
        opt_dlg = PairedTOptionsDialog(opts)
        opt_dlg.conf_edit.setText("90.0")
        opt_dlg.hyp_edit.setText("1.0")
        opt_dlg.alt_combo.setCurrentIndex(2)  # greater_than
        opt_dlg._accept()
        self.assertEqual(opt_dlg.options["confidence_level"], 90.0)
        self.assertEqual(opt_dlg.options["hypothesized_difference"], 1.0)
        self.assertEqual(opt_dlg.options["alternative"], "greater_than")

        graphs = {"histogram": True, "individual_value_plot": True, "boxplot": True}
        grp_dlg = PairedTGraphsDialog(graphs)
        grp_dlg.hist_cb.setChecked(False)
        grp_dlg._accept()
        self.assertFalse(grp_dlg.graphs["histogram"])
        self.assertTrue(grp_dlg.graphs["individual_value_plot"])
        self.assertTrue(grp_dlg.graphs["boxplot"])

    def test_chart_widget_render(self):
        st = paired_t_settings(data_format=1, sample1_col=0, sample2_col=1)
        res = run_paired_t(self.ws, st)
        entry = {"title": "Paired T-Test and CI: Pre, Post", "result": res}
        widget = PairedTPlotWidget(entry)
        widget.resize(560, 380)
        img = QImage(QSize(560, 380), QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        widget.render(img)
        self.assertFalse(img.isNull())


if __name__ == "__main__":
    unittest.main()
