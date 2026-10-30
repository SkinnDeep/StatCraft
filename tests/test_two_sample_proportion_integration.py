"""GUI integration tests for native Two-Sample Proportion dialogs."""
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter, format_entry
from statcraft.two_sample_proportion_engine import two_sample_proportion_settings, run_two_sample_proportion
from statcraft.two_sample_proportion_dialogs import (
    TwoSampleProportionDialog,
    TwoSampleProportionOptionsDialog,
)


class TestTwoSampleProportionIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ws = Worksheet("Demo2Prop", [
            Column("A", "number", [1]*20 + [0]*30),
            Column("B", "number", [1]*30 + [0]*20),
            Column("StackedVals", "number", [1]*20 + [0]*30 + [1]*30 + [0]*20),
            Column("StackedGroup", "text", ["Group1"]*50 + ["Group2"]*50),
        ])

    def test_dialog_unstacked(self):
        dlg = TwoSampleProportionDialog(self.ws)
        self.assertEqual(dlg.combo_data.currentIndex(), 1)
        dlg.sample1_edit.setText("C1")
        dlg.sample2_edit.setText("C2")
        dlg._on_ok()
        self.assertIsNotNone(dlg.result_payload)
        payload = dlg.result_payload
        self.assertEqual(payload["data_format"], 1)
        self.assertEqual(payload["sample1_col"], 0)
        self.assertEqual(payload["sample2_col"], 1)

    def test_dialog_stacked(self):
        dlg = TwoSampleProportionDialog(self.ws)
        dlg.combo_data.setCurrentIndex(0)
        dlg.samples_edit.setText("C3")
        dlg.ids_edit.setText("C4")
        dlg._on_ok()
        self.assertIsNotNone(dlg.result_payload)
        payload = dlg.result_payload
        self.assertEqual(payload["data_format"], 0)
        self.assertEqual(payload["samples_col"], 2)
        self.assertEqual(payload["sample_ids_col"], 3)

    def test_dialog_summarized(self):
        dlg = TwoSampleProportionDialog(self.ws)
        dlg.combo_data.setCurrentIndex(2)
        dlg.events1_edit.setText("20")
        dlg.trials1_edit.setText("50")
        dlg.events2_edit.setText("30")
        dlg.trials2_edit.setText("50")
        dlg._on_ok()
        self.assertIsNotNone(dlg.result_payload)
        payload = dlg.result_payload
        self.assertEqual(payload["data_format"], 2)
        self.assertEqual(payload["summarized"]["events1"], 20)
        self.assertEqual(payload["summarized"]["trials1"], 50)
        self.assertEqual(payload["summarized"]["events2"], 30)
        self.assertEqual(payload["summarized"]["trials2"], 50)

    def test_options_dialog(self):
        opts = {"confidence_level": 95.0, "hypothesized_difference": 0.0, "alternative": "not_equal", "test_method": "pooled"}
        opt_dlg = TwoSampleProportionOptionsDialog(opts)
        opt_dlg.conf_edit.setText("99.0")
        opt_dlg.hyp_edit.setText("0.05")
        opt_dlg.alt_combo.setCurrentIndex(2)  # greater_than
        opt_dlg.method_combo.setCurrentIndex(0)  # unpooled
        opt_dlg._accept()
        self.assertEqual(opt_dlg.options["confidence_level"], 99.0)
        self.assertEqual(opt_dlg.options["hypothesized_difference"], 0.05)
        self.assertEqual(opt_dlg.options["alternative"], "greater_than")
        self.assertEqual(opt_dlg.options["test_method"], "unpooled")

    def test_presenter_two_sample_proportion(self):
        p = Presenter()
        p.worksheet = self.ws
        st = {"data_format": 1, "sample1_col": 0, "sample2_col": 1}
        entry = p.two_sample_proportion(settings=st)
        self.assertIsNotNone(entry)
        self.assertIn("Test and CI for Two Proportions", entry["title"])
        self.assertTrue(entry["result"]["two_sample_proportion"])
        rep = format_entry(entry)
        self.assertIn("Test and CI for Two Proportions", rep)
        self.assertIn("Descriptive Statistics", rep)
        self.assertIn("Estimation for Difference", rep)


if __name__ == "__main__":
    unittest.main()
