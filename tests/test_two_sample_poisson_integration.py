"""GUI integration tests for native Two-Sample Poisson Rate dialogs and Presenter."""
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter, format_entry
from statcraft.two_sample_poisson_dialogs import (
    TwoSamplePoissonDialog,
    TwoSamplePoissonOptionsDialog,
)


class TestTwoSamplePoissonIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ws = Worksheet("DemoPoisson", [
            Column("Defects_A", "number", [2, 1, 0, 3, 2, 1, 4, 0, 1, 2]),
            Column("Defects_B", "number", [1, 2, 1, 0, 3, 2, 1, 2, 0, 1]),
        ])

    def test_dialog_unstacked(self):
        dlg = TwoSamplePoissonDialog(self.ws)
        self.assertEqual(dlg.mode_combo.currentIndex(), 1)
        dlg.s1_edit.setText("C1")
        dlg.s2_edit.setText("C2")
        dlg._accept()
        self.assertIsNotNone(dlg.result_payload)
        payload = dlg.result_payload
        self.assertEqual(payload["data_format"], 1)
        self.assertEqual(payload["sample1_col"], 0)
        self.assertEqual(payload["sample2_col"], 1)

    def test_dialog_summarized(self):
        dlg = TwoSamplePoissonDialog(self.ws)
        dlg.mode_combo.setCurrentIndex(2)  # Summarized data
        dlg.sz1_edit.setText("50")
        dlg.tot1_edit.setText("120")
        dlg.sz2_edit.setText("50")
        dlg.tot2_edit.setText("90")
        dlg._accept()
        self.assertIsNotNone(dlg.result_payload)
        payload = dlg.result_payload
        self.assertEqual(payload["data_format"], 2)
        s = payload["summarized"]
        self.assertEqual(s["n1"], 50)
        self.assertEqual(s["total_occurrences1"], 120)
        self.assertEqual(s["n2"], 50)
        self.assertEqual(s["total_occurrences2"], 90)

    def test_options_dialog(self):
        opts = {
            "confidence_level": 95.0,
            "alternative": "not_equal",
            "test_method": "separate",
            "hypothesized_difference": 0.0,
        }
        opt_dlg = TwoSamplePoissonOptionsDialog(opts)
        opt_dlg.conf_edit.setText("90.0")
        opt_dlg.method_combo.setCurrentIndex(1)  # pooled
        opt_dlg._accept()
        self.assertEqual(opt_dlg.options["confidence_level"], 90.0)
        self.assertEqual(opt_dlg.options["test_method"], "pooled")

    def test_presenter_unstacked_execution(self):
        p = Presenter()
        p.worksheet = self.ws
        settings = {
            "data_format": "unstacked",
            "sample1_col": 0,
            "sample2_col": 1,
            "hypothesized_difference": 0.0,
            "confidence_level": 95.0,
            "alternative": "not_equal",
            "test_method": "separate",
        }
        entry = p.two_sample_poisson(**settings)
        self.assertIn("Two-Sample Poisson Rate", entry["title"])
        self.assertEqual(entry["recipe"]["action"], "two_sample_poisson")
        formatted = format_entry(entry)
        self.assertIn("Descriptive Statistics", formatted)
        self.assertIn("Defects_A", formatted)
        self.assertIn("Defects_B", formatted)

    def test_presenter_summarized_execution(self):
        p = Presenter()
        settings = {
            "data_format": "summarized",
            "n1": 30,
            "x1": 45,
            "n2": 30,
            "x2": 30,
            "hypothesized_difference": 0.0,
            "confidence_level": 95.0,
            "alternative": "not_equal",
            "test_method": "pooled",
        }
        entry = p.two_sample_poisson(**settings)
        self.assertIn("Two-Sample Poisson Rate", entry["title"])
        res = entry["result"]
        self.assertAlmostEqual(res["rate1"], 1.5, places=5)
        self.assertAlmostEqual(res["rate2"], 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
