"""Unit tests for D-Optimal Custom Designs and Design Diagnostics (Color Map on Correlations)."""

import math
import unittest
import numpy as np
from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from statcraft.app import Presenter
from statcraft.model import Column, Worksheet
from statcraft.optimal_design import (
    FactorSpec,
    build_candidate_set,
    expand_model_matrix,
    evaluate_design_matrix,
    generate_d_optimal_design,
    create_optimal_design_worksheet,
)
from statcraft.optimal_report import format_optimal_design_report, get_optimal_structured_tables
from statcraft.design_eval_chart import DesignEvaluationChartWidget
from statcraft.optimal_dialogs import CreateDOptimalDesignDialog, EvaluateDesignDialog


class TestOptimalDesign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def test_d_optimal_generation_linear_and_interactions(self):
        factors = [
            FactorSpec(name="Temp", kind="continuous", low=100.0, high=200.0),
            FactorSpec(name="Pressure", kind="continuous", low=1.0, high=5.0),
            FactorSpec(name="Catalyst", kind="categorical", levels=["CatA", "CatB"]),
        ]

        # 3 factors with interactions requires 1 + 3 + 3 = 7 parameters
        # Generate 12 runs
        best_coded, best_actual, eval_res, term_names = generate_d_optimal_design(
            factors=factors,
            n_runs=12,
            model_order="interactions",
            num_restarts=5,
            seed=42,
        )

        self.assertEqual(len(best_coded), 12)
        self.assertEqual(len(best_actual), 12)
        self.assertTrue(eval_res["is_full_rank"])
        self.assertGreater(eval_res["d_efficiency"], 70.0)
        self.assertGreater(eval_res["a_efficiency"], 50.0)
        self.assertEqual(len(term_names), 7)
        self.assertIn("Intercept", term_names)

    def test_quadratic_model_design(self):
        factors = [
            FactorSpec(name="A", kind="continuous", low=-1.0, high=1.0),
            FactorSpec(name="B", kind="continuous", low=-1.0, high=1.0),
        ]
        # 2 factors quadratic: Intercept, A, B, A*B, A^2, B^2 (6 terms)
        # 10 runs
        best_coded, best_actual, eval_res, term_names = generate_d_optimal_design(
            factors=factors,
            n_runs=10,
            model_order="quadratic",
            num_restarts=5,
            seed=123,
        )
        self.assertEqual(len(term_names), 6)
        self.assertTrue(eval_res["is_full_rank"])
        self.assertGreater(eval_res["d_efficiency"], 40.0)

    def test_worksheet_creation_and_report(self):
        factors = [
            FactorSpec(name="Speed", kind="continuous", low=10.0, high=50.0),
            FactorSpec(name="Feed", kind="continuous", low=0.1, high=0.5),
        ]
        ws, res = create_optimal_design_worksheet(
            factors=factors,
            n_runs=8,
            model_order="interactions",
            randomize=True,
            seed=7,
            name="Machining_Study",
        )

        self.assertEqual(ws.name, "Machining_Study")
        self.assertEqual(ws.row_count, 8)
        self.assertEqual(len(ws.columns), 4)  # StdOrder, RunOrder, Speed, Feed
        self.assertIn("eval", res)

        text_report = format_optimal_design_report({"result": res})
        self.assertIn("Custom Design (D-Optimal)", text_report)
        self.assertIn("D-Efficiency", text_report)

        tables = get_optimal_structured_tables(res)
        self.assertGreaterEqual(len(tables), 2)
        self.assertEqual(tables[0]["title"], "Design Diagnostics & Efficiency Summary")

    def test_presenter_integration(self):
        factors = [
            FactorSpec(name="F1", kind="continuous", low=-1.0, high=1.0),
            FactorSpec(name="F2", kind="continuous", low=-1.0, high=1.0),
            FactorSpec(name="F3", kind="continuous", low=-1.0, high=1.0),
        ]
        p = Presenter()
        entry = p.create_optimal_design(factors=factors, n_runs=10, model_order="linear", seed=99)

        self.assertIsNotNone(entry)
        self.assertIn("Custom D-Optimal Design", entry["title"])
        self.assertEqual(p.worksheet.row_count, 10)

        # Evaluate the generated design
        eval_entry = p.evaluate_design(factor_indices=[2, 3, 4], model_order="interactions")
        self.assertIsNotNone(eval_entry)
        self.assertIn("Design Evaluation", eval_entry["title"])
        self.assertEqual(eval_entry["result"]["analysis"], "design_evaluation")

    def test_chart_rendering_and_dialogs(self):
        factors = [
            FactorSpec(name="X1", kind="continuous", low=-1.0, high=1.0),
            FactorSpec(name="X2", kind="continuous", low=-1.0, high=1.0),
        ]
        ws, res = create_optimal_design_worksheet(factors, n_runs=8, model_order="interactions")

        widget = DesignEvaluationChartWidget({"result": res})
        widget.resize(920, 600)

        pm = QPixmap(920, 600)
        pm.fill()
        widget.render(pm)
        self.assertFalse(pm.isNull())

        # Test Dialogs
        dlg_create = CreateDOptimalDesignDialog()
        self.assertIsNotNone(dlg_create)

        dlg_eval = EvaluateDesignDialog(ws)
        self.assertIsNotNone(dlg_eval)


if __name__ == "__main__":
    unittest.main()
