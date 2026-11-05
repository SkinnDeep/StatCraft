"""Unit tests for JMP Distribution Platform (Univariate analysis)."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["STATCRAFT_TESTING"] = "1"

_root = Path(__file__).resolve().parent.parent
_deps = _root.parent / "statcraft-build-deps"
if _deps.exists() and str(_deps) not in sys.path:
    sys.path.insert(0, str(_deps))
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter
from statcraft.jmp_distribution_engine import (
    compute_continuous_distribution, compute_categorical_distribution, compute_jmp_distribution
)
from statcraft.jmp_distribution_report import (
    format_jmp_distribution_report, get_jmp_distribution_structured_tables
)
from statcraft.jmp_distribution_chart import JMPDistributionWidget


class JMPDistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.ws = Worksheet("Big Class", [
            Column("Name", kind="text", values=["KATIE", "LOUISE", "JANE", "JACLYN", "TIM", "ROBERT"], metadata={"modeling_type": "nominal"}),
            Column("Age", kind="number", values=[12, 12, 12, 13, 14, 15], metadata={"modeling_type": "ordinal"}),
            Column("Height", kind="number", values=[59.0, 61.0, 55.0, 66.0, 52.0, 67.0], metadata={"modeling_type": "continuous"}),
            Column("Weight", kind="number", values=[95.0, 123.0, 74.0, 145.0, 64.0, 115.0], metadata={"modeling_type": "continuous"}),
        ])
        self.p = Presenter()
        self.p.worksheet = self.ws

    def test_continuous_distribution_metrics(self):
        col = self.ws.columns[2]  # Height
        res = compute_continuous_distribution(col, conf=0.95)

        self.assertEqual(res["variable"], "Height")
        self.assertEqual(res["type"], "continuous")
        self.assertEqual(res["n"], 6)
        self.assertAlmostEqual(res["mean"], 60.0, places=4)
        self.assertGreater(res["std_dev"], 0.0)
        self.assertGreater(res["std_err"], 0.0)
        self.assertLess(res["ci_lower"], res["mean"])
        self.assertGreater(res["ci_upper"], res["mean"])

        # Check all 11 JMP Quantiles are present
        quantiles = res["quantiles"]
        for q_key in ("100.0%", "99.5%", "97.5%", "90.0%", "75.0%", "50.0%", "25.0%", "10.0%", "2.5%", "0.5%", "0.0%"):
            self.assertIn(q_key, quantiles)

        self.assertAlmostEqual(quantiles["100.0%"], 67.0)
        self.assertAlmostEqual(quantiles["0.0%"], 52.0)
        self.assertAlmostEqual(quantiles["50.0%"], 60.0)

        # Check Outlier Box Plot metrics
        self.assertEqual(res["q25"], quantiles["25.0%"])
        self.assertEqual(res["q75"], quantiles["75.0%"])
        self.assertGreaterEqual(res["upper_whisker"], res["lower_whisker"])

        # Check histogram and curve
        self.assertTrue(len(res["bin_counts"]) > 0)
        self.assertEqual(len(res["bin_edges"]), len(res["bin_counts"]) + 1)
        self.assertTrue(len(res["curve_x"]) > 0)

    def test_categorical_distribution_frequencies(self):
        col = self.ws.columns[0]  # Name
        res = compute_categorical_distribution(col)

        self.assertEqual(res["variable"], "Name")
        self.assertEqual(res["type"], "categorical")
        self.assertEqual(res["n"], 6)
        self.assertEqual(res["num_levels"], 6)

        freqs = res["frequencies"]
        self.assertEqual(len(freqs), 6)
        total_prob = sum(f["prob"] for f in freqs)
        self.assertAlmostEqual(total_prob, 1.0, places=4)
        self.assertEqual(freqs[-1]["cum_count"], 6)
        self.assertAlmostEqual(freqs[-1]["cum_prob"], 1.0, places=4)

    def test_multi_column_jmp_distribution(self):
        # Run across both Continuous (Height) and Categorical (Name)
        res = compute_jmp_distribution(self.ws, column_indices=[0, 2], confidence=0.95)
        self.assertEqual(res["analysis"], "jmp_distribution")
        self.assertEqual(len(res["variables"]), 2)
        self.assertEqual(res["variables"][0]["type"], "categorical")
        self.assertEqual(res["variables"][1]["type"], "continuous")

        # Test report formatting
        report = format_jmp_distribution_report({"result": res})
        self.assertIn("JMP Distribution Platform", report)
        self.assertIn("Quantiles", report)
        self.assertIn("Summary Statistics", report)
        self.assertIn("Frequencies", report)

        # Test structured tables
        tables = get_jmp_distribution_structured_tables(res)
        self.assertTrue(len(tables) >= 3)
        titles = [t["title"] for t in tables]
        self.assertTrue(any("Frequencies: Name" in t for t in titles))
        self.assertTrue(any("Quantiles: Height" in t for t in titles))
        self.assertTrue(any("Summary Statistics: Height" in t for t in titles))

    def test_presenter_integration(self):
        entry = self.p.jmp_distribution(column_indices=[2, 3], confidence=0.95)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "jmp_distribution")
        self.assertIn("tables", entry["result"])
        self.assertIn("session_text", entry["result"])

    def test_chart_widget_offscreen_grab(self):
        res = compute_jmp_distribution(self.ws, column_indices=[0, 2], confidence=0.95)
        widget = JMPDistributionWidget(res)
        widget.resize(700, 420)
        widget.show()
        self.app.processEvents()
        pix = widget.grab()
        self.assertFalse(pix.isNull())
        self.assertGreater(pix.width(), 0)
        self.assertGreater(pix.height(), 0)
        widget.close()
        widget.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
