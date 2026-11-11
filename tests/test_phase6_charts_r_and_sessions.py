import os
import sys
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from statcraft.app import Presenter
from statcraft.model import Column, Worksheet
from statcraft.modern_charts import ChartWidget, supported
from statcraft.r_universal_translator import translate_entry_to_r
from statcraft.session_commands import execute_script


class Phase6ChartsAndEcosystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _make_presenter(self):
        ws = Worksheet(
            columns=[
                Column("Y", "number", [10.1, 12.2, 9.8, 15.1, 18.2, 11.4, 14.8, 19.3, 8.9, 13.7, 16.5, 21.0]),
                Column("X1", "number", [1.0, 2.0, 0.5, 3.5, 4.5, 1.5, 3.0, 5.0, 0.2, 2.5, 4.0, 5.5]),
                Column("X2", "number", [5.0, 4.0, 6.0, 3.0, 2.0, 5.0, 3.5, 1.5, 6.5, 4.0, 2.5, 1.0]),
                Column("Counts", "number", [1, 2, 0, 3, 5, 1, 4, 6, 0, 2, 4, 7]),
                Column("FacA", "text", ["A1", "A1", "A1", "A1", "A2", "A2", "A2", "A2", "A3", "A3", "A3", "A3"]),
                Column("FacB", "text", ["B1", "B1", "B2", "B2"] * 3),
                Column("Time", "number", [2, 3, 5, 6, 8, 9, 11, 14, 15, 18, 20, 24]),
                Column("Event", "number", [1, 1, 1, 1, 0, 1, 1, 0, 1, 1, 0, 0]),
            ]
        )
        p = Presenter()
        p.worksheet = ws
        return p

    def test_native_charts_render_cleanly_for_all_phases_3_to_5(self):
        p = self._make_presenter()
        entries = [
            p.monte_carlo_simulation("X1: Normal(10, 0.5); X2: Uniform(1, 3)", "X1 + 2 * X2", lsl=11.0, usl=17.0, n_sims=1500),
            p.random_forest(0, [1, 2, 4], n_trees=25, seed=3),
            p.treenet_gbm(0, [1, 2, 4], n_trees=25, seed=3),
            p.mars_regression(0, [1, 2], max_terms=6),
            p.discover_best_model(0, [1, 2, 4], seed=3),
            p.bootstrap_1sample(0, n_resamples=250),
            p.randomization_2sample(0, 1, n_resamples=250),
            p.warranty_analysis(6, 3, at_risk_total=500, forecast_horizon=30),
            p.fit_mixed_reml(0, fixed_indices=[1], random_indices=[4]),
            p.fully_nested_anova(0, [4, 5]),
            p.rolled_throughput_yield(step_yields=[99.1, 98.4, 99.3]),
            p.cox_ph_regression(6, 7, [1], event_value=1),
        ]
        for entry in entries:
            self.assertTrue(supported(entry), msg=f"Chart not supported for {entry['title']}")
            widget = ChartWidget(entry)
            self.assertGreaterEqual(len(widget.panels), 1, msg=f"No chart panels built for {entry['title']}")
            self.assertIsNone(widget.error, msg=f"Chart error for {entry['title']}: {widget.error}")
            widget.resize(780, 520)
            pix = widget.grab()
            self.assertFalse(pix.isNull())
            self.assertIsNone(widget.error, msg=f"Paint error for {entry['title']}: {widget.error}")
            widget.close()

    def test_r_universal_translator_covers_phases_3_4_5(self):
        p = self._make_presenter()
        checks = [
            (p.random_forest(0, [1, 2], n_trees=20), "randomForest"),
            (p.treenet_gbm(0, [1, 2], n_trees=20), "gbm"),
            (p.mars_regression(0, [1, 2], max_terms=6), "earth"),
            (p.fit_mixed_reml(0, fixed_indices=[1], random_indices=[4]), "lmer"),
            (p.cox_ph_regression(6, 7, [1]), "coxph"),
            (p.negative_binomial_regression(3, [1]), "glm.nb"),
            (p.bootstrap_1sample(0, n_resamples=200), "boot("),
            (p.oneway_manova([0, 1], 4), "manova("),
            (p.monte_carlo_simulation("X1: Normal(10, 1)", "X1 * 2", n_sims=500), "rnorm(N"),
        ]
        for entry, expected_token in checks:
            base_r, tidy_r, _ = translate_entry_to_r(entry, p.worksheet)
            self.assertIn(expected_token, base_r, msg=f"Missing '{expected_token}' in Base R for {entry['title']}")
            self.assertIn(expected_token, tidy_r, msg=f"Missing '{expected_token}' in Tidy R for {entry['title']}")

    def test_session_commands_phases_3_4_5_end_to_end(self):
        p = self._make_presenter()
        script = """
        BOOTSTRAP C1;
          RESAMPLES 200.
        RANDTEST C1 C2
        PGOF C4
        NBREG C4 = C2 C3
        BANOVA C1 = C5 C6
        NESTED C1 = C5 C6
        MANOVA C1 C2 = C5
        REML C1 = C2;
          RANDOM C5.
        COXPH C7 C8 = C2
        SIXSIGMA C1;
          LSL 5;
          USL 25.
        RANDOMFOREST C1 = C2 C3
        TREENET C1 = C2 C3
        MARS C1 = C2 C3
        BESTMODEL C1 = C2 C3
        MONTECARLO X1: Normal(10, 0.5);
          FORMULA "X1 + 1";
          LSL 8;
          USL 12;
          SIMS 400.
        """
        results = execute_script(p, script)
        self.assertEqual(len(results), 15)
        self.assertEqual(results[-1]["result"]["analysis"], "monte_carlo_simulation")

    def test_pyinstaller_spec_and_release_metadata_sync(self):
        repo = Path(__file__).resolve().parents[1]
        spec = (repo / "StatCraft.spec").read_text(encoding="utf-8")
        for mod in ("statcraft.predictive_ml", "statcraft.monte_carlo", "statcraft.phase6_charts", "statcraft.mixed_reml"):
            self.assertIn(mod, spec)
        self.assertIn("'CFBundleVersion': '116.5.0'", spec)
        self.assertIn("116.5.0.0", (repo / "app_version.txt").read_text(encoding="utf-8"))
        self.assertIn("116.5.0.0", (repo / "installer_version.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
