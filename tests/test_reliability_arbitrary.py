"""Unit tests for Distribution Analysis (Arbitrary Censoring) engine, report, dialog, and presenter integration."""
import math
import os
import unittest
from PySide6.QtWidgets import QApplication

from statcraft.reliability_arbitrary import (
    fit_parametric_arbitrary_censoring,
    clean_arbitrary_censoring_data,
)
from statcraft.reliability_arbitrary_report import generate_reliability_arbitrary_report
from statcraft.reliability_arbitrary_dialogs import ArbitraryCensoringDialog
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft.recipes import columns


class TestReliabilityArbitrary(unittest.TestCase):
    """Test suite for Arbitrary Censoring reliability analysis."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        # Benchmark dataset with exact, left, right, and interval censored failures:
        # 12 observations
        self.starts = [10.0, 20.0, 30.0, 0.0,  50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 120.0, 150.0]
        self.ends   = [10.0, 20.0, 30.0, 25.0, 50.0, None, 90.0, 80.0, None, 130.0, 120.0, None]
        self.freqs  = [1,    1,    2,    1,    1,    2,    1,    1,    2,    1,     1,     1]

    def test_clean_data(self):
        records, counts = clean_arbitrary_censoring_data(self.starts, self.ends, self.freqs)
        self.assertEqual(counts["exact"], 7)      # 10(1), 20(1), 30(2), 50(1), 80(1), 120(1)
        self.assertEqual(counts["left"], 1)       # 0..25(1)
        self.assertEqual(counts["right"], 5)      # 60..(2), 90..(2), 150..(1)
        self.assertEqual(counts["interval"], 2)   # 70..90(1), 100..130(1)
        self.assertEqual(counts["total"], 15)

    def test_fit_weibull(self):
        res = fit_parametric_arbitrary_censoring(
            start_times=self.starts,
            end_times=self.ends,
            frequencies=self.freqs,
            distribution="weibull",
        )
        self.assertEqual(res["analysis"], "reliability_arbitrary")
        self.assertEqual(res["distribution"], "Weibull")
        self.assertEqual(len(res["parameters"]), 2)  # Shape, Scale

        p_dict = {p["parameter"]: p["estimate"] for p in res["parameters"]}
        self.assertGreater(p_dict["Shape"], 0.5)
        self.assertGreater(p_dict["Scale"], 30.0)

        # Percentiles
        self.assertEqual(len(res["percentiles"]), 7)
        pcts = [row["percentile"] for row in res["percentiles"]]
        self.assertTrue(all(pcts[i] < pcts[i + 1] for i in range(len(pcts) - 1)))

    def test_fit_lognormal(self):
        res = fit_parametric_arbitrary_censoring(
            start_times=self.starts,
            end_times=self.ends,
            frequencies=self.freqs,
            distribution="lognormal",
        )
        self.assertEqual(res["distribution"], "Lognormal")
        self.assertEqual(len(res["parameters"]), 2)  # Location, Scale
        p_dict = {p["parameter"]: p["estimate"] for p in res["parameters"]}
        self.assertGreater(p_dict["Location"], 2.0)
        self.assertGreater(p_dict["Scale"], 0.1)

    def test_report_generation(self):
        res = fit_parametric_arbitrary_censoring(
            start_times=self.starts,
            end_times=self.ends,
            frequencies=self.freqs,
            distribution="weibull",
        )
        rep = generate_reliability_arbitrary_report(res)
        self.assertIn("Distribution Analysis (Arbitrary Censoring) - Weibull", rep)
        self.assertIn("Summary of Current Observations", rep)
        self.assertIn("Exact failures", rep)
        self.assertIn("Left censored", rep)
        self.assertIn("Right censored", rep)
        self.assertIn("Interval censored", rep)
        self.assertIn("Table of Parameter Estimates", rep)
        self.assertIn("Table of Percentiles", rep)

    def test_dialog_instantiation(self):
        ws = Worksheet(name="ArbitraryData")
        ws.columns.append(Column(name="Start", kind="number", values=self.starts))
        ws.columns.append(Column(name="End", kind="number", values=self.ends))

        pres = Presenter()
        pres.worksheet = ws

        dlg = ArbitraryCensoringDialog(pres)
        self.assertEqual(dlg.windowTitle(), "Parametric Distribution Analysis (Arbitrary Censoring)")
        self.assertEqual(dlg.spin_conf.value(), 95.0)

    def test_presenter_and_recipe(self):
        ws = Worksheet(name="ArbitraryData")
        ws.columns.append(Column(name="Start", kind="number", values=self.starts))
        ws.columns.append(Column(name="End", kind="number", values=self.ends))

        pres = Presenter()
        pres.worksheet = ws

        entry = pres.reliability_arbitrary({
            "start_index": 0,
            "end_index": 1,
            "distribution": "weibull",
            "confidence": 0.95,
        })
        self.assertIsNotNone(entry)
        text = format_entry(entry)
        self.assertIn("Distribution Analysis (Arbitrary Censoring)", text)

        # Check recipe columns extraction
        recipe = entry["recipe"]
        cols = columns(recipe)
        self.assertEqual(cols, [0, 1])


if __name__ == "__main__":
    unittest.main()
