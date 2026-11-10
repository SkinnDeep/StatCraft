import json
import os
import sys
import unittest

import numpy as np
from PySide6.QtWidgets import QApplication

from statcraft import recipes
from statcraft.app import Presenter, format_entry
from statcraft.assistant_wizard import ASSISTANT_TRACKS, GuidedAssistantDialog, recommend_analysis
from statcraft.guidance_chips import get_smart_guidance_chips
from statcraft.model import Column, Worksheet


def _make_nonlinear_regression_ws(n=120, seed=42):
    rng = np.random.default_rng(seed)
    x1 = rng.uniform(-3.0, 3.0, n)
    x2 = rng.uniform(0.0, 10.0, n)
    noise_x = rng.normal(0.0, 1.0, n)
    grp = ["High" if i % 2 == 0 else "Low" for i in range(n)]
    g_eff = np.array([2.5 if g == "High" else -2.5 for g in grp])
    y = 3.0 * (x1 ** 2) + np.maximum(0.0, x2 - 5.0) * 2.0 + g_eff + rng.normal(0.0, 0.35, n)
    return Worksheet(
        columns=[
            Column("Y", "number", y.tolist()),
            Column("X1", "number", x1.tolist()),
            Column("X2", "number", x2.tolist()),
            Column("Group", "text", grp),
            Column("Noise", "number", noise_x.tolist()),
        ]
    )


def _make_classification_ws(n=120, n_classes=2, seed=7):
    rng = np.random.default_rng(seed)
    x1 = rng.normal(0.0, 1.0, n)
    x2 = rng.normal(0.0, 1.0, n)
    if n_classes == 2:
        score = 2.0 * x1 - 1.5 * x2 + 0.5 * (x1 ** 2)
        y = ["Yes" if s > 0 else "No" for s in score]
    else:
        y = []
        for a, b in zip(x1, x2):
            if a + b > 0.6:
                y.append("ClassC")
            elif a - b > 0.0:
                y.append("ClassB")
            else:
                y.append("ClassA")
    return Worksheet(
        columns=[
            Column("Target", "text", y),
            Column("X1", "number", x1.tolist()),
            Column("X2", "number", x2.tolist()),
        ]
    )


class Phase4PredictiveMLEngineTests(unittest.TestCase):
    def test_random_forest_regression_and_classification(self):
        from statcraft.predictive_ml import format_predictive_ml_report, random_forest_fit

        ws_reg = _make_nonlinear_regression_ws(n=100)
        rf_reg = random_forest_fit(ws_reg, 0, [1, 2, 3, 4], n_trees=60, max_depth=8, seed=11)
        self.assertEqual(rf_reg["analysis"], "random_forest")
        self.assertEqual(rf_reg["task"], "regression")
        self.assertGreater(rf_reg["oob_metrics"]["r2"], 0.70)
        top_pred = rf_reg["variable_importance"][0]["predictor"]
        self.assertIn(top_pred, ("X1", "X2", "Group"))
        self.assertNotEqual(top_pred, "Noise")
        self.assertIn("Random Forests", format_predictive_ml_report(rf_reg))

        ws_cls = _make_classification_ws(n=120, n_classes=3)
        rf_cls = random_forest_fit(ws_cls, 0, [1, 2], n_trees=60, seed=11)
        self.assertEqual(rf_cls["task"], "classification")
        self.assertEqual(len(rf_cls["classes"]), 3)
        self.assertGreater(rf_cls["oob_metrics"]["accuracy"], 0.80)
        self.assertIn("OOB Accuracy", format_predictive_ml_report(rf_cls))

    def test_treenet_gbm_regression_huber_binary_and_multiclass(self):
        from statcraft.predictive_ml import format_predictive_ml_report, treenet_fit

        ws_reg = _make_nonlinear_regression_ws(n=110)
        tn_ls = treenet_fit(ws_reg, 0, [1, 2, 3, 4], n_trees=80, learning_rate=0.1, max_depth=3, loss="ls", seed=5)
        self.assertEqual(tn_ls["analysis"], "treenet_gbm")
        self.assertGreater(tn_ls["val_metrics"]["r2"], 0.75)
        self.assertGreaterEqual(tn_ls["optimal_trees"], 5)
        self.assertTrue(len(tn_ls["history"]) >= 1)
        self.assertIn("TreeNet", format_predictive_ml_report(tn_ls))

        tn_hub = treenet_fit(ws_reg, 0, [1, 2, 3], n_trees=60, loss="huber", seed=5)
        self.assertGreater(tn_hub["val_metrics"]["r2"], 0.70)

        ws_bin = _make_classification_ws(n=110, n_classes=2)
        tn_bin = treenet_fit(ws_bin, 0, [1, 2], n_trees=70, seed=5)
        self.assertGreater(tn_bin["val_metrics"]["accuracy"], 0.80)
        self.assertIsNotNone(tn_bin["val_metrics"]["roc_auc"])
        self.assertGreater(tn_bin["val_metrics"]["roc_auc"], 0.85)

        ws_tri = _make_classification_ws(n=120, n_classes=3)
        tn_tri = treenet_fit(ws_tri, 0, [1, 2], n_trees=50, seed=5)
        self.assertGreater(tn_tri["val_metrics"]["accuracy"], 0.75)

    def test_mars_splines_hinge_recovery_and_classification(self):
        from statcraft.predictive_ml import format_predictive_ml_report, mars_fit

        rng = np.random.default_rng(19)
        x = np.linspace(0.0, 10.0, 90)
        y = 2.0 + 3.0 * np.maximum(0.0, x - 5.0) - 1.5 * np.maximum(0.0, 5.0 - x) + rng.normal(0.0, 0.25, 90)
        ws = Worksheet(columns=[Column("Y", "number", y.tolist()), Column("X", "number", x.tolist())])

        mrs = mars_fit(ws, 0, [1], max_terms=10, max_degree=1, penalty=2.0)
        self.assertEqual(mrs["analysis"], "mars_regression")
        self.assertGreater(mrs["metrics"]["r2"], 0.95)
        self.assertGreater(mrs["metrics"]["gcv_r2"], 0.90)
        self.assertGreaterEqual(mrs["n_basis_terms"], 2)
        self.assertIn("MARS", format_predictive_ml_report(mrs))

        ws_bin = _make_classification_ws(n=100, n_classes=2)
        mrs_cls = mars_fit(ws_bin, 0, [1, 2], max_terms=10, max_degree=2)
        self.assertEqual(mrs_cls["task"], "classification")
        self.assertGreater(mrs_cls["metrics"]["accuracy"], 0.80)

    def test_discover_best_model_leaderboard(self):
        from statcraft.predictive_ml import discover_best_model, format_predictive_ml_report

        ws_reg = _make_nonlinear_regression_ws(n=100)
        res = discover_best_model(ws_reg, 0, [1, 2, 3], validation_fraction=0.25, seed=9)
        self.assertEqual(res["analysis"], "discover_best_model")
        self.assertEqual(res["task"], "regression")
        self.assertGreaterEqual(len(res["leaderboard"]), 4)
        self.assertEqual(res["leaderboard"][0]["rank"], 1)
        # Nonlinear ML model should beat linear regression on x1^2 + hinge(x2)
        self.assertNotEqual(res["champion_model"], "Multiple Linear Regression")
        self.assertIn("Leaderboard", format_predictive_ml_report(res))


class Phase4PresenterWizardAndUITests(unittest.TestCase):
    def test_presenter_json_safety_recipes_and_guidance_chips(self):
        ws = _make_nonlinear_regression_ws(n=60)
        p = Presenter()
        p.worksheet = ws

        entries = [
            p.random_forest(0, [1, 2, 3], n_trees=30, seed=3),
            p.treenet_gbm(0, [1, 2, 3], n_trees=35, seed=3),
            p.mars_regression(0, [1, 2], max_terms=8),
            p.discover_best_model(0, [1, 2, 3], seed=3),
        ]
        for entry in entries:
            # Verify pure JSON serializability for project saving
            dumped = json.dumps(entry)
            self.assertGreater(len(dumped), 50)
            formatted = format_entry(entry)
            self.assertGreater(len(formatted.strip()), 50)

        replayed = recipes.run(p, entries[0]["recipe"])
        self.assertEqual(replayed["result"]["analysis"], "random_forest")

        chips = get_smart_guidance_chips(entries[0])
        self.assertTrue(any(c["action"] == "discover_best_model" for c in chips))

    def test_assistant_wizard_tracks_and_modern_window_wiring(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication(sys.argv)
        from statcraft.modern_app import ModernWindow

        win = ModernWindow(sandbox_mode=True)
        win.show()
        app.processEvents()

        # Verify all assistant tracks & branch choices resolve to existing ModernWindow methods
        for track in ASSISTANT_TRACKS:
            tid = track["id"]
            # Exercise default and non-default option branches
            default_choices = {q_key: opts[0][0] for q_key, _, opts in track["questions"]}
            rec = recommend_analysis(tid, default_choices)
            self.assertTrue(callable(getattr(win, rec["method"], None)), msg=f"Invalid assistant target {rec['method']} on {tid}")
            for q_key, _, opts in track["questions"]:
                for opt_val, _ in opts:
                    mod = dict(default_choices)
                    mod[q_key] = opt_val
                    rec2 = recommend_analysis(tid, mod)
                    self.assertTrue(callable(getattr(win, rec2["method"], None)), msg=f"Invalid assistant target {rec2['method']} on {tid}:{opt_val}")

        # Exercise GuidedAssistantDialog UI widget creation & track switching
        wiz = GuidedAssistantDialog(parent=win, dark_mode=True)
        for row_i in range(wiz.track_list.count()):
            wiz.track_list.setCurrentRow(row_i)
            app.processEvents()
            self.assertTrue(bool(wiz.chosen_method))
        wiz.close()

        # Verify Stat > Predictive Analytics and Assistant menu actions exist
        menu_labels = []

        def collect(menu):
            for a in menu.actions():
                if a.text():
                    menu_labels.append(a.text().replace("&&", "\x00").replace("&", "").replace("\x00", "&"))
                if a.menu():
                    collect(a.menu())

        for top_act in win.menuBar().actions():
            if top_act.menu():
                collect(top_act.menu())
        joined = "\n".join(menu_labels)
        for needle in [
            "Random Forests® (Classification & Regression)",
            "TreeNet® Gradient Boosting",
            "MARS® Regression & Classification",
            "Discover Best Model® (AutoML Leaderboard)",
            "Guided Analysis Assistant Wizard",
        ]:
            self.assertIn(needle, joined)

        win.close()


if __name__ == "__main__":
    unittest.main()
