"""Unit tests for Cause-and-Effect (Fishbone / Ishikawa) Diagram matching Minitab 22 specifications."""
import os
import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_deps = _root.parent / "statcraft-build-deps"
if _deps.exists() and str(_deps) not in sys.path:
    sys.path.insert(0, str(_deps))
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Column, Worksheet
from statcraft.cause_and_effect import build_cause_and_effect, DEFAULT_BRANCH_LABELS
from statcraft.cause_and_effect_report import format_cause_and_effect_report
from statcraft.cause_and_effect_chart import CauseAndEffectChartWidget
from statcraft.cause_and_effect_dialog import CauseAndEffectDialog


class TestCauseAndEffect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Sample causes for defect analysis
        self.personnel_causes = ["Training", "Fatigue", "Shift handoff"]
        self.machine_causes = ["Blade wear", "Calibration", "Speed variation"]
        self.material_causes = ["Supplier variance", "Moisture", "Hardness"]
        self.method_causes = ["Angle of cut", "Feed rate"]
        self.measurement_causes = ["Gage error", "Parallax"]
        self.env_causes = ["Humidity", "Temperature swing"]

        self.ws = Worksheet("QualityData", [
            Column("Personnel", "text", self.personnel_causes),
            Column("Machines", "text", self.machine_causes),
            Column("Materials", "text", self.material_causes),
            Column("Methods", "text", self.method_causes + [None]),
            Column("Measurements", "text", self.measurement_causes + [None]),
            Column("Environment", "text", self.env_causes + [None]),
        ])
        self.p = Presenter()
        self.p.worksheet = self.ws

    def tearDown(self):
        self.app.processEvents()

    def test_build_model_basic(self):
        branches = [
            {"label": "Personnel", "causes": self.personnel_causes},
            {"label": "Machines", "causes": self.machine_causes},
            {"label": "Materials", "causes": self.material_causes},
            {"label": "Methods", "causes": self.method_causes},
            {"label": "Measurements", "causes": self.measurement_causes},
            {"label": "Environment", "causes": self.env_causes},
        ]
        res = build_cause_and_effect(branches, effect="Surface Scratches", title="Scratches Analysis")
        self.assertEqual(res["analysis"], "cause_and_effect")
        self.assertEqual(res["effect"], "Surface Scratches")
        self.assertEqual(res["title"], "Scratches Analysis")
        self.assertEqual(res["branch_count"], 6)
        self.assertEqual(res["total_causes"], 3 + 3 + 3 + 2 + 2 + 2)

    def test_no_empty_filtering(self):
        branches = [
            {"label": "Personnel", "causes": ["Fatigue"]},
            {"label": "Machines", "causes": []},  # Empty
            {"label": "Materials", "causes": ["Moisture"]},
            {"label": "Methods", "causes": ["", "  "]},  # Blank strings
        ]
        res = build_cause_and_effect(branches, effect="Defect", no_empty=True)
        self.assertEqual(res["branch_count"], 2)
        labels = [b["label"] for b in res["branches"]]
        self.assertEqual(labels, ["Personnel", "Materials"])

    def test_no_labels_option(self):
        branches = [
            {"label": "Personnel", "causes": ["Fatigue"]},
        ]
        res = build_cause_and_effect(branches, effect="Defect", no_labels=True)
        self.assertEqual(res["branches"][0]["label"], "")

    def test_report_formatting(self):
        branches = [
            {"label": "Personnel", "causes": ["Training", "Fatigue"]},
            {"label": "Machines", "causes": ["Calibration"]},
        ]
        res = build_cause_and_effect(branches, effect="Surface Flaws")
        rep = format_cause_and_effect_report(res)
        self.assertIn("CAUSE-AND-EFFECT DIAGRAM", rep)
        self.assertIn("Effect:                 Surface Flaws", rep)
        self.assertIn("Personnel", rep)
        self.assertIn("Training", rep)
        self.assertIn("Machines", rep)
        self.assertIn("Calibration", rep)

    def test_presenter_integration_and_recipe(self):
        branch_specs = [
            {"column_index": 0, "label": "Personnel"},
            {"column_index": 1, "label": "Machines"},
            {"column_index": 2, "label": "Materials"},
            {"column_index": 3, "label": "Methods"},
            {"column_index": 4, "label": "Measurements"},
            {"column_index": 5, "label": "Environment"},
        ]
        entry = self.p.cause_and_effect(branch_specs, effect="Dimension Out of Spec")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "cause_and_effect")
        self.assertIn("connected_analysis", entry)

        conn = entry["connected_analysis"]
        self.assertEqual(conn["analysis_type"], "cause_and_effect")
        self.assertIn("r_script", conn)
        self.assertIn("cause.and.effect(", conn["r_script"])
        self.assertIn("Dimension Out of Spec", conn["r_script"])

    def test_chart_widget_rendering(self):
        branches = [
            {"label": "Personnel", "causes": self.personnel_causes},
            {"label": "Machines", "causes": self.machine_causes},
            {"label": "Materials", "causes": self.material_causes},
            {"label": "Methods", "causes": self.method_causes},
        ]
        res = build_cause_and_effect(branches, effect="Test Effect")
        entry = {"title": "Test Fishbone", "result": res}
        widget = CauseAndEffectChartWidget(entry)
        widget.resize(800, 500)
        widget.show()
        self.app.processEvents()

        self.assertGreaterEqual(len(widget.hit_regions), 4)  # Branch label + cause hit regions
        widget.close()
        widget.deleteLater()
        self.app.processEvents()

    def test_dialog_lifecycle(self):
        dlg = CauseAndEffectDialog(self.ws)
        # Select first 2 columns
        dlg.branch_table.item(0, 1).setText("Personnel")
        dlg.branch_table.item(1, 1).setText("Machines")
        dlg.txt_effect.setText("Surface Finish")
        dlg._on_ok()

        self.assertIsNotNone(dlg.selected_params)
        self.assertEqual(dlg.selected_params["effect"], "Surface Finish")
        self.assertEqual(len(dlg.selected_params["branches"]), 6)
        self.assertEqual(dlg.selected_params["branches"][0]["causes"], self.personnel_causes)
        self.assertEqual(dlg.selected_params["branches"][1]["causes"], self.machine_causes)
        dlg.close()
        dlg.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
