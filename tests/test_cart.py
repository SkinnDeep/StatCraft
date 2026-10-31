"""Unit tests for CART® Decision Trees (Regression and Classification)."""

import unittest
import numpy as np
from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from statcraft.app import Presenter
from statcraft.model import Column, Worksheet
from statcraft.tree_chart import DecisionTreeWidget
from statcraft.tree_dialogs import DecisionTreeDialog
from statcraft.tree_engine import DecisionTree, fit_decision_tree
from statcraft.tree_report import format_tree_report, get_tree_structured_tables


class TestCART(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def test_regression_tree(self):
        rng = np.random.default_rng(42)
        n = 100
        x1 = rng.uniform(0, 10, n)
        x2 = rng.uniform(0, 5, n)
        # Step response function
        y = np.where(x1 > 5.0, 50.0 + x2 * 2.0, 10.0 + x2 * 0.5) + rng.normal(0, 0.5, n)

        X = [[x1[i], x2[i]] for i in range(n)]
        res = fit_decision_tree(
            X,
            y.tolist(),
            feature_names=["Feature1", "Feature2"],
            tree_type="regression",
            max_depth=4,
            min_split_size=10,
            min_leaf_size=5,
        )

        self.assertEqual(res["analysis"], "cart_tree")
        self.assertEqual(res["tree_type"], "regression")
        self.assertGreater(res["metrics"]["r2"], 0.80)
        self.assertGreater(res["metrics"]["n_terminal_nodes"], 1)

        # Feature1 should have the highest importance due to the large step
        importances = {item["feature"]: item["importance"] for item in res["importances"]}
        self.assertGreater(importances["Feature1"], importances["Feature2"])

    def test_classification_tree(self):
        rng = np.random.default_rng(101)
        n = 120
        x1 = rng.uniform(0, 10, n)
        x2 = rng.uniform(0, 10, n)
        # 3-class target
        classes = []
        for i in range(n):
            if x1[i] < 3.5:
                classes.append("ClassA")
            elif x2[i] > 5.0:
                classes.append("ClassB")
            else:
                classes.append("ClassC")

        X = [[x1[i], x2[i]] for i in range(n)]
        res = fit_decision_tree(
            X,
            classes,
            feature_names=["Width", "Height"],
            tree_type="classification",
            max_depth=4,
            min_split_size=10,
            min_leaf_size=5,
        )

        self.assertEqual(res["tree_type"], "classification")
        self.assertGreater(res["metrics"]["accuracy"], 0.85)
        self.assertIn("confusion_matrix", res["metrics"])
        self.assertEqual(len(res["classes"]), 3)

    def test_categorical_predictors(self):
        rng = np.random.default_rng(7)
        n = 60
        cat_feature = ["TypeA" if i % 2 == 0 else "TypeB" for i in range(n)]
        num_feature = rng.uniform(10, 50, n).tolist()
        y = [100.0 if cat_feature[i] == "TypeA" else 20.0 for i in range(n)]

        X = [[cat_feature[i], num_feature[i]] for i in range(n)]
        res = fit_decision_tree(
            X,
            y,
            feature_names=["Type", "Score"],
            feature_kinds=["categorical", "numeric"],
            tree_type="regression",
        )

        self.assertGreater(res["metrics"]["r2"], 0.95)
        importances = {item["feature"]: item["importance"] for item in res["importances"]}
        self.assertGreater(importances["Type"], 90.0)

    def test_report_and_card_tables(self):
        X = [[1.0, 2.0], [2.0, 3.0], [8.0, 7.0], [9.0, 8.0]]
        y = [10.0, 12.0, 50.0, 52.0]
        res = fit_decision_tree(X, y, feature_names=["P1", "P2"], tree_type="regression")
        res["response_name"] = "Output"

        report_text = format_tree_report({"result": res})
        self.assertIn("CART® Regression Tree", report_text)
        self.assertIn("Variable Importance", report_text)
        self.assertIn("Terminal Leaves Summary", report_text)

        tables = get_tree_structured_tables(res)
        self.assertGreaterEqual(len(tables), 3)
        self.assertEqual(tables[0]["title"], "CART® Regression Tree Summary")
        self.assertEqual(tables[1]["title"], "Predictor Importance Ranking")

    def test_presenter_integration(self):
        c_y = Column("Yield", "number", [10.0, 11.5, 9.8, 45.0, 47.2, 44.1, 10.2, 46.5])
        c_temp = Column("Temp", "number", [50.0, 52.0, 48.0, 95.0, 98.0, 93.0, 51.0, 96.0])
        c_cat = Column("Catalyst", "text", ["C1", "C1", "C1", "C2", "C2", "C2", "C1", "C2"])
        ws = Worksheet("Reaction_Data", [c_y, c_temp, c_cat])

        p = Presenter()
        p.worksheet = ws

        entry = p.cart_tree(response_index=0, predictor_indices=[1, 2], tree_type="regression")
        self.assertIsNotNone(entry)
        self.assertIn("CART® Regression Tree", entry["title"])
        res = entry["result"]
        self.assertEqual(res["analysis"], "cart_tree")
        self.assertIn("tables", res)
        self.assertIn("session_text", res)

    def test_chart_rendering_and_dialog(self):
        rng = np.random.default_rng(99)
        n = 50
        x1 = rng.uniform(0, 10, n)
        y = (3.0 * x1 + rng.normal(0, 1, n)).tolist()
        X = [[x1[i]] for i in range(n)]

        res = fit_decision_tree(X, y, feature_names=["Pressure"], tree_type="regression")
        res["response_name"] = "Strength"

        widget = DecisionTreeWidget({"result": res})
        widget.resize(920, 600)

        pm = QPixmap(920, 600)
        pm.fill()
        widget.render(pm)
        self.assertFalse(pm.isNull())

        # Test Dialog
        c1 = Column("Strength", "number", y)
        c2 = Column("Pressure", "number", x1.tolist())
        ws = Worksheet("TestWS", [c1, c2])
        dlg = DecisionTreeDialog(ws)
        self.assertIsNotNone(dlg)


if __name__ == "__main__":
    unittest.main()
