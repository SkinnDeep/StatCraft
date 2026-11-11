import json
import os
import sys
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

import statcraft
from statcraft import recipes, updater
from statcraft.app import Presenter, format_entry
from statcraft.executive_summary import generate_executive_summary
from statcraft.monte_carlo import (
    format_monte_carlo_report,
    monte_carlo_simulation,
    parse_input_specs,
)


class Phase5MonteCarloTests(unittest.TestCase):
    def test_monte_carlo_analytical_normal_sum_and_tornado(self):
        inputs = parse_input_specs("X1: Normal(10, 3); X2: Normal(5, 4)")
        res = monte_carlo_simulation(inputs, "X1 + X2", lsl=0.0, usl=30.0, n_sims=15000, seed=42)
        self.assertEqual(res["analysis"], "monte_carlo_simulation")
        # Theoretical mean = 15.0, theoretical stdev = sqrt(9 + 16) = 5.0
        self.assertAlmostEqual(res["summary"]["mean"], 15.0, delta=0.2)
        self.assertAlmostEqual(res["summary"]["stdev"], 5.0, delta=0.2)
        # +/- 3 sigma -> Pp = 1.00, Ppk = 1.00, OOS ~ 0.27% (2700 DPMO)
        self.assertAlmostEqual(res["capability"]["pp"], 1.0, delta=0.05)
        self.assertAlmostEqual(res["capability"]["ppk"], 1.0, delta=0.06)
        self.assertAlmostEqual(res["capability"]["pct_out_of_spec"], 0.27, delta=0.18)

        # Variance contribution: X2 (var=16, 64%) > X1 (var=9, 36%)
        self.assertEqual(res["sensitivity"][0]["input"], "X2")
        self.assertGreater(res["sensitivity"][0]["variance_contribution_pct"], 55.0)
        self.assertIn("Sensitivity Tornado", format_monte_carlo_report(res))

    def test_monte_carlo_all_distributions_and_safe_ast(self):
        spec = (
            "U: Uniform(1, 3); "
            "T: Triangular(0, 2, 4); "
            "L: Lognormal(0, 0.2); "
            "E: Exponential(2); "
            "W: Weibull(2.0, 5.0)"
        )
        inputs = parse_input_specs(spec)
        res = monte_carlo_simulation(inputs, "U + T + L + E + sqrt(W)", n_sims=2000, seed=7)
        self.assertEqual(len(res["sensitivity"]), 5)
        self.assertGreater(res["summary"]["mean"], 5.0)

        with self.assertRaises(ValueError):
            monte_carlo_simulation(inputs, "__import__('os').system('echo hi')", n_sims=200)


class Phase5ExecutiveSummaryAndReleaseTests(unittest.TestCase):
    def test_executive_summary_covers_phases_3_4_5(self):
        samples = [
            {"title": "Discover Best", "result": {"analysis": "discover_best_model", "task": "regression", "champion_model": "TreeNet", "leaderboard": [{"val_r2": 0.91, "val_rmse": 0.4}]}, "recipe": {}},
            {"title": "Random Forest", "result": {"analysis": "random_forest", "task": "regression", "n_trees": 80, "oob_metrics": {"r2": 0.85}, "variable_importance": [{"predictor": "Temp"}]}, "recipe": {}},
            {"title": "Six Sigma", "result": {"analysis": "six_sigma_process_report", "sigma_level_est": 4.8, "z_bench_lt": 3.3, "dpmo_expected_lt": 483.0, "cpk": 1.62}, "recipe": {}},
            {"title": "RTY", "result": {"analysis": "six_sigma_product_report", "steps": 3, "rty_pct": 95.1, "dpmo_total": 49000.0, "equivalent_sigma_level": 3.15}, "recipe": {}},
            {"title": "REML", "result": {"analysis": "mixed_reml", "n": 24, "variance_components": [{"source": "Batch", "pct_total": 72.0}]}, "recipe": {}},
            {"title": "Monte Carlo", "result": {"analysis": "monte_carlo_simulation", "n_sims": 10000, "summary": {"mean": 15.0, "stdev": 1.2}, "capability": {"pct_out_of_spec": 0.5, "dpmo": 5000}, "sensitivity": [{"input": "X2", "variance_contribution_pct": 64.0}]}, "recipe": {}},
        ]
        for entry in samples:
            bullets = generate_executive_summary(entry)
            self.assertGreaterEqual(len(bullets), 1)
            self.assertNotIn("Analysis evaluated", bullets[0])

    def test_presenter_replay_ui_and_v116_major_release_consistency(self):
        self.assertEqual(statcraft.__version__, "116.3.0")
        self.assertEqual(updater.STATCRAFT_VERSION, "116.3.0")
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        self.assertIn('version = "116.3.0"', pyproject.read_text(encoding="utf-8"))

        p = Presenter()
        entry = p.monte_carlo_simulation("X1: Normal(10, 0.4); X2: Uniform(4.5, 5.5)", "X1 + 2 * X2", lsl=18.0, usl=22.0, n_sims=3000, seed=5)
        self.assertGreater(len(json.dumps(entry)), 100)
        self.assertIn("Sensitivity Tornado", format_entry(entry))
        replayed = recipes.run(p, entry["recipe"])
        self.assertEqual(replayed["result"]["analysis"], "monte_carlo_simulation")

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication(sys.argv)
        from statcraft.modern_app import ModernWindow

        win = ModernWindow(sandbox_mode=True)
        win.show()
        app.processEvents()
        self.assertTrue(callable(getattr(win, "monte_carlo_dialog", None)))

        menu_labels = []

        def collect(menu):
            for a in menu.actions():
                if a.text():
                    menu_labels.append(a.text().replace("&&", "\x00").replace("&", "").replace("\x00", "&"))
                if a.menu():
                    collect(a.menu())

        for act in win.menuBar().actions():
            if act.menu():
                collect(act.menu())
        self.assertIn("Monte Carlo Process Simulation…", "\n".join(menu_labels))
        win.close()


if __name__ == "__main__":
    unittest.main()
