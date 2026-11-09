"""Unit tests for Gage R&R Study (Expanded) engine, report, dialog, and presenter integration."""
import math
import os
import unittest
from PySide6.QtWidgets import QApplication

from statcraft.gage_rr_expanded import (
    analyze_gage_rr_expanded,
    clean_expanded_gage_data,
)
from statcraft.gage_rr_expanded_report import generate_gage_rr_expanded_report
from statcraft.gage_rr_expanded_dialogs import GageRRExpandedDialog
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft.recipes import columns


class TestGageRRExpanded(unittest.TestCase):
    """Test suite for Expanded Gage R&R study."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        # 3-factor benchmark dataset:
        # 3 Parts, 2 Operators, 2 Gages, 2 Replicates = 24 rows
        self.parts = []
        self.operators = []
        self.gages = []
        self.measurements = []

        part_effects = {"P1": 10.0, "P2": 20.0, "P3": 30.0}
        op_effects = {"Op1": 0.0, "Op2": 0.5}
        gage_effects = {"G1": 0.0, "G2": 0.2}

        import random
        rng = random.Random(42)

        for p in ("P1", "P2", "P3"):
            for op in ("Op1", "Op2"):
                for g in ("G1", "G2"):
                    for rep in range(2):
                        noise = rng.gauss(0.0, 0.1)
                        val = part_effects[p] + op_effects[op] + gage_effects[g] + noise
                        self.parts.append(p)
                        self.operators.append(op)
                        self.gages.append(g)
                        self.measurements.append(round(val, 3))

    def test_clean_data(self):
        m_raw = [1.0, 2.0, None, 4.0]
        p_raw = ["P1", "P2", "P3", None]
        op_raw = ["O1", "O2", "O3", "O4"]
        y_c, f_c, idxs = clean_expanded_gage_data(m_raw, [p_raw, op_raw])
        self.assertEqual(len(y_c), 2)
        self.assertEqual(idxs, [0, 1])
        self.assertEqual(y_c.tolist(), [1.0, 2.0])

    def test_analyze_expanded_gage(self):
        res = analyze_gage_rr_expanded(
            measurements=self.measurements,
            part_values=self.parts,
            operator_values=self.operators,
            additional_factors=[self.gages],
            part_name="Part",
            operator_name="Operator",
            additional_factor_names=["Gage"],
            study_multiplier=6.0,
            tolerance=50.0,
            process_stdev=8.0,
        )
        self.assertEqual(res["analysis"], "gage_rr_expanded")
        self.assertEqual(len(res["anova"]), 8)  # Part, Op, Gage, Part*Op, Part*Gage, Op*Gage, Error, Total
        self.assertGreater(res["total_variation"], 0.0)
        self.assertGreater(res["ndc"], 1)

        # Check ANOVA terms presence
        sources = [row["source"] for row in res["anova"]]
        self.assertIn("Part", sources)
        self.assertIn("Operator", sources)
        self.assertIn("Gage", sources)
        self.assertIn("Part * Operator", sources)
        self.assertIn("Repeatability", sources)
        self.assertIn("Total", sources)

        # Check variance components
        vc_sources = [row["source"] for row in res["variance_components"]]
        self.assertIn("Total Gage R&R", vc_sources)
        self.assertIn("  Repeatability", vc_sources)
        self.assertIn("  Reproducibility", vc_sources)
        self.assertIn("Total Variation", vc_sources)

    def test_report_generation(self):
        res = analyze_gage_rr_expanded(
            measurements=self.measurements,
            part_values=self.parts,
            operator_values=self.operators,
            additional_factors=[self.gages],
            part_name="Part",
            operator_name="Operator",
            additional_factor_names=["Gage"],
            tolerance=50.0,
        )
        rep = generate_gage_rr_expanded_report(res)
        self.assertIn("Gage R&R Study (Expanded)", rep)
        self.assertIn("Analysis of Variance", rep)
        self.assertIn("Variance Components", rep)
        self.assertIn("Gage Evaluation", rep)
        self.assertIn("Number of Distinct Categories", rep)
        self.assertIn("%Tolerance", rep)

    def test_dialog_instantiation(self):
        ws = Worksheet(name="ExpandedGage")
        ws.columns.append(Column(name="Measurement", kind="number", values=self.measurements))
        ws.columns.append(Column(name="Part", kind="text", values=self.parts))
        ws.columns.append(Column(name="Operator", kind="text", values=self.operators))
        ws.columns.append(Column(name="Gage", kind="text", values=self.gages))

        pres = Presenter()
        pres.worksheet = ws

        dlg = GageRRExpandedDialog(pres)
        self.assertEqual(dlg.windowTitle(), "Gage R&R Study (Expanded)")
        self.assertEqual(dlg.spin_mult.value(), 6.0)

    def test_presenter_and_recipe(self):
        ws = Worksheet(name="ExpandedGage")
        ws.columns.append(Column(name="Measurement", kind="number", values=self.measurements))
        ws.columns.append(Column(name="Part", kind="text", values=self.parts))
        ws.columns.append(Column(name="Operator", kind="text", values=self.operators))
        ws.columns.append(Column(name="Gage", kind="text", values=self.gages))

        pres = Presenter()
        pres.worksheet = ws

        entry = pres.gage_rr_expanded({
            "measurement_index": 0,
            "part_index": 1,
            "operator_index": 2,
            "additional_factor_indices": [3],
            "study_multiplier": 6.0,
            "tolerance": 50.0,
        })
        self.assertIsNotNone(entry)
        text = format_entry(entry)
        self.assertIn("Gage R&R Study (Expanded)", text)

        # Check recipe columns extraction
        recipe = entry["recipe"]
        cols = columns(recipe)
        self.assertEqual(cols, [0, 1, 2, 3])


if __name__ == "__main__":
    unittest.main()
