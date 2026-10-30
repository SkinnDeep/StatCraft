"""GUI integration tests for native One-Sample Poisson Rate dialogs."""
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter, format_entry
from statcraft.one_sample_poisson_engine import one_sample_poisson_settings, run_one_sample_poisson
from statcraft.one_sample_poisson_dialogs import (
    OneSamplePoissonDialog,
    OneSamplePoissonOptionsDialog,
)


class TestOneSamplePoissonIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ws = Worksheet("DemoPoisson", [
            Column("Defects", "number", [2, 1, 0, 3, 2, 1, 4, 0, 1, 2]),
            Column("Freq", "number", [1, 2, 1, 1, 2, 1, 1, 2, 1, 1]),
        ])

    def test_dialog_raw_columns(self):
        dlg = OneSamplePoissonDialog(self.ws)
        self.assertEqual(dlg.mode_combo.currentIndex(), 0)
        dlg.sample_cols_edit.setText("C1")
        dlg.test_check.setChecked(True)
        dlg.test_rate_edit.setText("1.5")
        dlg._accept()
        self.assertIsNotNone(dlg.result_payload)
        payload = dlg.result_payload
        self.assertEqual(payload["mode"], "columns")
        self.assertEqual(payload["sample_columns"], [0])
        self.assertEqual(payload["hypothesized_rate"], 1.5)

    def test_dialog_summarized(self):
        dlg = OneSamplePoissonDialog(self.ws)
        dlg.mode_combo.setCurrentIndex(1)  # Summarized data
        dlg.sample_size_edit.setText("50")
        dlg.total_occurrences_edit.setText("120")
        dlg.test_check.setChecked(True)
        dlg.test_rate_edit.setText("2.0")
        dlg._accept()
        self.assertIsNotNone(dlg.result_payload)
        payload = dlg.result_payload
        self.assertEqual(payload["mode"], "summarized")
        self.assertEqual(payload["n"], 50)
        self.assertEqual(payload["total_occurrences"], 120)
        self.assertEqual(payload["hypothesized_rate"], 2.0)

    def test_options_dialog(self):
        opts = {
            "confidence_level": 95.0,
            "alternative": "not_equal",
            "method": "exact",
            "length_of_observation": 1.0,
        }
        opt_dlg = OneSamplePoissonOptionsDialog(opts)
        opt_dlg.conf_edit.setText("90.0")
        opt_dlg.alt_combo.setCurrentIndex(2)  # greater
        opt_dlg.method_combo.setCurrentIndex(1)  # normal_approx
        opt_dlg.len_edit.setText("2.5")
        opt_dlg._accept()
        self.assertEqual(opt_dlg.options["confidence_level"], 90.0)
        self.assertEqual(opt_dlg.options["alternative"], "greater")
        self.assertEqual(opt_dlg.options["method"], "normal_approx")
        self.assertEqual(opt_dlg.options["length_of_observation"], 2.5)

    def test_presenter_one_sample_poisson(self):
        p = Presenter()
        p.worksheet = self.ws
        st = {
            "mode": "columns",
            "sample_columns": ["Defects"],
            "hypothesized_rate": 1.5,
        }
        entry = p.one_sample_poisson(settings=st)
        self.assertIsNotNone(entry)
        self.assertIn("Test and CI for One-Sample Poisson Rate", entry["title"])
        self.assertTrue(entry["result"]["one_sample_poisson"])
        rep = format_entry(entry)
        self.assertIn("Test and CI for One-Sample Poisson Rate", rep)
        self.assertIn("Descriptive Statistics", rep)
        self.assertIn("1.5", rep)


if __name__ == "__main__":
    unittest.main()
