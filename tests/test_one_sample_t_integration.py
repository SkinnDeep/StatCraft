"""GUI integration tests for native One-Sample t dialogs and plot widget."""
import unittest
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.one_sample_t_engine import one_sample_t_settings, run_one_sample_t
from statcraft.one_sample_t_dialogs import (
    OneSampleTDialog,
    OneSampleTOptionsDialog,
    OneSampleTGraphsDialog,
)
from statcraft.one_sample_t_chart import OneSampleTPlotWidget


class TestOneSampleTIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ws = Worksheet("Demo", [
            Column("Score", "number", [10, 12, 11, 14, 13, 15, 12, 16]),
            Column("Rating", "number", [4, 5, 3, 5, 4, 4, 3, 5]),
        ])

    def test_dialog_raw_columns(self):
        dlg = OneSampleTDialog(self.ws)
        self.assertEqual(dlg.combo_data.currentIndex(), 0)
        dlg.sample_cols_edit.setText("C1")
        dlg.hyp_edit.setText("10.0")
        dlg._on_ok()
        self.assertIsNotNone(dlg.result_payload)
        payload = dlg.result_payload
        self.assertEqual(payload["data_format"], 0)
        self.assertEqual(payload["sample_cols"], [0])
        self.assertEqual(payload["hypothesized_mean"], 10.0)

    def test_dialog_summarized(self):
        dlg = OneSampleTDialog(self.ws)
        dlg.combo_data.setCurrentIndex(1)  # Summarized data
        self.assertFalse(dlg.graphs_btn.isEnabled())
        dlg.size_edit.setText("25")
        dlg.mean_edit.setText("102.5")
        dlg.sd_edit.setText("4.2")
        dlg.test_cb.setChecked(True)
        dlg.hyp_edit.setText("100.0")
        dlg._on_ok()
        self.assertIsNotNone(dlg.result_payload)
        payload = dlg.result_payload
        self.assertEqual(payload["data_format"], 2)
        self.assertEqual(payload["summarized"]["n"], 25)
        self.assertEqual(payload["summarized"]["mean"], 102.5)
        self.assertEqual(payload["summarized"]["sd"], 4.2)

    def test_options_and_graphs_dialogs(self):
        opts = {"confidence_level": 95.0, "alternative": "not_equal"}
        opt_dlg = OneSampleTOptionsDialog(opts)
        opt_dlg.conf_edit.setText("99.0")
        opt_dlg.alt_combo.setCurrentIndex(2)  # greater_than
        opt_dlg._accept()
        self.assertEqual(opt_dlg.options["confidence_level"], 99.0)
        self.assertEqual(opt_dlg.options["alternative"], "greater_than")

        graphs = {"histogram": True, "individual_value_plot": True, "boxplot": True}
        grp_dlg = OneSampleTGraphsDialog(graphs)
        grp_dlg.hist_cb.setChecked(False)
        grp_dlg._accept()
        self.assertFalse(grp_dlg.graphs["histogram"])
        self.assertTrue(grp_dlg.graphs["individual_value_plot"])
        self.assertTrue(grp_dlg.graphs["boxplot"])

    def test_chart_widget_render(self):
        st = one_sample_t_settings(data_format=0, sample_cols=[0], hypothesized_mean=10.0)
        res = run_one_sample_t(self.ws, st)
        entry = {"title": "One-Sample T-Test and CI: Score", "result": res}
        widget = OneSampleTPlotWidget(entry)
        widget.resize(560, 380)
        img = QImage(QSize(560, 380), QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.white)
        widget.render(img)
        self.assertFalse(img.isNull())


if __name__ == "__main__":
    unittest.main()
