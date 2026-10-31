"""Unit tests for Wheeler's Evaluating the Measurement Process (EMP)."""

import math
import unittest
import numpy as np
from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from statcraft.app import Presenter
from statcraft.emp_engine import evaluate_measurement_process
from statcraft.emp_report import format_emp_report, get_emp_structured_tables
from statcraft.emp_chart import EMPChartWidget
from statcraft.model import Column, Worksheet


class TestEMP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def test_emp_engine_calculations(self):
        # Synthetic gauge dataset: 10 parts, 3 operators, 2 replicates (60 observations)
        parts = []
        operators = []
        measurements = []

        rng = np.random.default_rng(42)
        part_true_means = {p: 100.0 + (p * 5.0) for p in range(1, 11)}
        op_effects = {1: 0.0, 2: 0.3, 3: -0.2}

        for p in range(1, 11):
            for o in (1, 2, 3):
                for _ in range(2):
                    meas = part_true_means[p] + op_effects[o] + rng.normal(0, 0.4)
                    parts.append(f"P{p}")
                    operators.append(f"Op{o}")
                    measurements.append(float(meas))

        res = evaluate_measurement_process(measurements, parts, operators)

        self.assertEqual(res["analysis"], "evaluating_measurement_process")
        self.assertEqual(res["n_obs"], 60)
        self.assertEqual(res["n_parts"], 10)
        self.assertEqual(res["n_operators"], 3)
        self.assertGreater(res["rho"], 0.80)
        self.assertEqual(res["emp_class"], "First Class")
        self.assertLess(res["attenuation"], 0.10)
        self.assertGreater(res["probable_error"], 0.0)
        self.assertGreaterEqual(len(res["components"]), 4)
        self.assertEqual(len(res["shift_table"]), 4)

        # 4σ shift should have very high detection probability (> 80% in subgroup 1, > 95% in subgroup 1-2)
        shift_4 = res["shift_table"][3]
        self.assertGreater(shift_4["p_subgroup_1"], 0.80)
        self.assertGreater(shift_4["p_subgroup_2"], 0.95)

    def test_emp_report_and_tables(self):
        measurements = [10.1, 10.2, 10.0, 10.3, 20.1, 20.2, 20.0, 20.3, 30.1, 30.2, 30.0, 30.4]
        parts = ["A", "A", "A", "A", "B", "B", "B", "B", "C", "C", "C", "C"]
        operators = [1, 1, 2, 2, 1, 1, 2, 2, 1, 1, 2, 2]

        res = evaluate_measurement_process(measurements, parts, operators)
        res["meas_name"] = "Thickness"
        res["part_name"] = "PartID"
        res["op_name"] = "Appraiser"

        text_report = format_emp_report({"result": res})
        self.assertIn("Evaluating the Measurement Process", text_report)
        self.assertIn("Intraclass Correlation", text_report)
        self.assertIn("Probable Error", text_report)
        self.assertIn("Shift Detection Probabilities", text_report)

        tables = get_emp_structured_tables(res)
        self.assertEqual(len(tables), 3)
        self.assertEqual(tables[0]["title"], "Wheeler EMP Classification & Resolution Diagnostics")
        self.assertEqual(tables[1]["title"], "Variance Components Breakdown")
        self.assertEqual(tables[2]["title"], "Shift Detection Probabilities Across Subgroups")

    def test_emp_presenter_integration(self):
        m_col = Column("Val", "number", [10.1, 10.2, 10.0, 10.3, 20.1, 20.2, 20.0, 20.3, 30.1, 30.2, 30.0, 30.4])
        p_col = Column("Part", "text", ["A", "A", "A", "A", "B", "B", "B", "B", "C", "C", "C", "C"])
        o_col = Column("Op", "text", ["O1", "O1", "O2", "O2", "O1", "O1", "O2", "O2", "O1", "O1", "O2", "O2"])

        ws = Worksheet("EMP_Data", [m_col, p_col, o_col])
        p = Presenter()
        p.worksheet = ws

        entry = p.evaluating_measurement_process(measurement_index=0, part_index=1, operator_index=2)
        self.assertIsNotNone(entry)
        self.assertIn("Evaluating the Measurement Process", entry["title"])
        res = entry["result"]
        self.assertEqual(res["analysis"], "evaluating_measurement_process")
        self.assertGreater(res["rho"], 0.90)
        self.assertIn("tables", res)
        self.assertIn("session_text", res)

    def test_emp_chart_rendering(self):
        measurements = [10.1, 10.2, 10.0, 10.3, 20.1, 20.2, 20.0, 20.3, 30.1, 30.2, 30.0, 30.4]
        parts = ["A", "A", "A", "A", "B", "B", "B", "B", "C", "C", "C", "C"]
        operators = [1, 1, 2, 2, 1, 1, 2, 2, 1, 1, 2, 2]

        res = evaluate_measurement_process(measurements, parts, operators)
        res["meas_name"] = "Diameter"
        res["part_name"] = "Shaft"
        res["op_name"] = "Inspector"

        widget = EMPChartWidget({"result": res})
        widget.resize(880, 580)

        pm = QPixmap(880, 580)
        pm.fill()
        widget.render(pm)
        self.assertFalse(pm.isNull())

    def test_emp_dialog_instantiation(self):
        from statcraft.emp_dialogs import EvaluatingMeasurementProcessDialog

        m_col = Column("Val", "number", [10.1, 10.2, 10.0, 10.3, 20.1, 20.2, 20.0, 20.3, 30.1, 30.2, 30.0, 30.4])
        p_col = Column("Part", "text", ["A", "A", "A", "A", "B", "B", "B", "B", "C", "C", "C", "C"])
        o_col = Column("Op", "text", ["O1", "O1", "O2", "O2", "O1", "O1", "O2", "O2", "O1", "O1", "O2", "O2"])
        ws = Worksheet("EMP_Data", [m_col, p_col, o_col])

        dlg = EvaluatingMeasurementProcessDialog(ws)
        self.assertIsNotNone(dlg)


if __name__ == "__main__":
    unittest.main()
