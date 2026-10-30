"""GUI integration tests for native One-Sample Proportion dialogs."""
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter, format_entry
from statcraft.one_sample_proportion_engine import one_sample_proportion_settings, run_one_sample_proportion
from statcraft.one_sample_proportion_dialogs import (
    OneSampleProportionDialog,
    OneSampleProportionOptionsDialog,
)


class TestOneSampleProportionIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ws = Worksheet("DemoProp", [
            Column("Defects", "number", [1]*15 + [0]*35),
            Column("PassFail", "text", ["Pass"]*40 + ["Fail"]*10),
        ])

    def test_dialog_raw_columns(self):
        dlg = OneSampleProportionDialog(self.ws)
        self.assertEqual(dlg.combo_data.currentIndex(), 0)
        dlg.sample_cols_edit.setText("C1")
        dlg.test_cb.setChecked(True)
        dlg.hyp_edit.setText("0.25")
        dlg._on_ok()
        self.assertIsNotNone(dlg.result_payload)
        payload = dlg.result_payload
        self.assertEqual(payload["data_format"], 0)
        self.assertEqual(payload["sample_cols"], [0])
        self.assertEqual(payload["hypothesized_proportion"], 0.25)

    def test_dialog_summarized(self):
        dlg = OneSampleProportionDialog(self.ws)
        dlg.combo_data.setCurrentIndex(1)  # Summarized data
        dlg.events_edit.setText("45")
        dlg.trials_edit.setText("100")
        dlg.test_cb.setChecked(True)
        dlg.hyp_edit.setText("0.5")
        dlg._on_ok()
        self.assertIsNotNone(dlg.result_payload)
        payload = dlg.result_payload
        self.assertEqual(payload["data_format"], 2)
        self.assertEqual(payload["summarized"]["events"], 45)
        self.assertEqual(payload["summarized"]["trials"], 100)

    def test_options_dialog(self):
        opts = {"confidence_level": 95.0, "alternative": "not_equal", "method": "exact"}
        opt_dlg = OneSampleProportionOptionsDialog(opts)
        opt_dlg.conf_edit.setText("90.0")
        opt_dlg.alt_combo.setCurrentIndex(2)  # greater_than
        opt_dlg.method_combo.setCurrentIndex(1)  # normal
        opt_dlg._accept()
        self.assertEqual(opt_dlg.options["confidence_level"], 90.0)
        self.assertEqual(opt_dlg.options["alternative"], "greater_than")
        self.assertEqual(opt_dlg.options["method"], "normal")

    def test_presenter_one_sample_proportion(self):
        p = Presenter()
        p.worksheet = self.ws
        st = {"data_format": 0, "sample_cols": [0], "hypothesized_proportion": 0.3}
        entry = p.one_sample_proportion(settings=st)
        self.assertIsNotNone(entry)
        self.assertIn("Test and CI for One Proportion", entry["title"])
        self.assertTrue(entry["result"]["one_sample_proportion"])
        rep = format_entry(entry)
        self.assertIn("Test and CI for One Proportion: Defects", rep)
        self.assertIn("Descriptive Statistics", rep)
        self.assertIn("H0: p = 0.3", rep)


if __name__ == "__main__":
    unittest.main()
