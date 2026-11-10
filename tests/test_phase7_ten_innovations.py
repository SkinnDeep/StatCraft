import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from statcraft.app import Presenter
from statcraft.assistant_wizard import GuidedAssistantDialog
from statcraft.command_palette import CommandPaletteDialog, collect_menu_actions
from statcraft.model import Column, Worksheet
from statcraft.modern_charts import ChartWidget
from statcraft.r_universal_translator import translate_entry_to_r
from statcraft.svg_html_export import export_session_to_markdown


class Phase7TenInnovationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _make_presenter(self):
        ws = Worksheet(
            columns=[
                Column("Y", "number", [10.0, 12.0, 15.0, 18.0, 20.0, 11.0, 13.0, 17.0, 19.0, 22.0, 9.5, 24.0]),
                Column("X1", "number", [1.0, 2.0, 3.0, 4.0, 5.0, 1.5, 2.5, 3.5, 4.5, 5.5, 0.8, 6.0]),
                Column("Bin", "text", ["No", "No", "Yes", "Yes", "Yes", "No", "No", "Yes", "Yes", "Yes", "No", "Yes"]),
                Column("Counts", "number", [1, 2, 0, 3, 2, 1, 4, 2, 1, 3, 0, 2]),
                Column("Time", "number", [2, 3, 5, 6, 8, 9, 11, 14, 15, 18, 20, 24]),
            ]
        )
        p = Presenter()
        p.worksheet = ws
        return p

    def test_stored_fits_replicates_mc_draws_mars_eq_and_sweep(self):
        p = self._make_presenter()
        start_cols = len(p.worksheet.columns)

        rf_e = p.random_forest(0, [1], n_trees=20, store_fits=True)
        tn_e = p.treenet_gbm(0, [1], n_trees=25, store_fits=True)
        mrs_e = p.mars_regression(0, [1], max_terms=8, store_fits=True)
        self.assertIn("equation", mrs_e["result"])
        self.assertGreater(len(mrs_e["result"]["equation"]), 3)
        self.assertEqual(len(p.worksheet.columns), start_cols + 6)  # Fit + Res for each of 3 models
        self.assertIn("RF_Fit", [c.name for c in p.worksheet.columns])
        self.assertIn("MARS_Res", [c.name for c in p.worksheet.columns])
        json.dumps(rf_e)

        mc_e = p.monte_carlo_simulation("X1: Normal(10, 1.0); X2: Normal(5, 0.2)", "X1 + X2", lsl=11.0, usl=19.0, n_sims=2000, store_column=True)
        self.assertIn("MC_Output", [c.name for c in p.worksheet.columns])
        sweep = mc_e["result"]["tolerance_sweep"]
        self.assertEqual(len(sweep), 3)
        self.assertLess(sweep[2]["output_stdev"], sweep[0]["output_stdev"])
        self.assertGreater(sweep[2]["ppk"], sweep[0]["ppk"])

        boot_e = p.bootstrap_1sample(0, n_resamples=250, store_replicates=True)
        self.assertIn("Boot_Y", [c.name for c in p.worksheet.columns])
        json.dumps(boot_e)

    def test_roc_pdp_charts_and_hover_hitboxes(self):
        p = self._make_presenter()
        rf_cls = p.random_forest(2, [1], task="classification", n_trees=20)
        tn_cls = p.treenet_gbm(2, [1], task="classification", n_trees=25)
        mrs_cls = p.mars_regression(2, [1], task="classification", max_terms=6)
        for e in (rf_cls, tn_cls, mrs_cls):
            self.assertGreater(len(e["result"]["roc_curve"]), 5)
            w = ChartWidget(e)
            w.resize(780, 520)
            w.grab()
            self.assertGreater(len(w.hover_regions), 2, msg=f"No hover hitboxes registered for {e['title']}")
            self.assertGreaterEqual(len(w.panels), 2)
            w.close()

    def test_remaining_r_translators_and_markdown_svg_export(self):
        p = self._make_presenter()
        checks = [
            (p.randomization_1sample(0, n_resamples=200), "perm_stats"),
            (p.goodness_of_fit_poisson(3), "dpois"),
            (p.warranty_analysis(4, 3, at_risk_total=500), "Weibull Warranty"),
            (p.six_sigma_process_report(0, lsl=5.0, usl=25.0), "Six Sigma Process"),
            (p.rolled_throughput_yield(step_yields=[99.0, 98.5]), "prod(yields)"),
            (p.extended_power("one_variance", ratio=1.5, target_power=0.8), "library(pwr)"),
        ]
        for e, tok in checks:
            b, t, _ = translate_entry_to_r(e, p.worksheet)
            self.assertIn(tok, b)
            self.assertIn(tok, t)

        rf_e = p.random_forest(0, [1], n_trees=15)
        w = ChartWidget(rf_e)
        w.resize(640, 420)
        with tempfile.TemporaryDirectory() as tmp:
            md_path = Path(tmp) / "audit_report.md"
            md = export_session_to_markdown([rf_e], "ProcessData", str(md_path), chart_widgets={0: w})
            self.assertTrue(md_path.exists())
            self.assertIn("# StatCraft Session Report", md)
            svg_file = Path(tmp) / "audit_report_assets" / "chart_1.svg"
            self.assertTrue(svg_file.exists())
            self.assertGreater(svg_file.stat().st_size, 100)
        w.close()

    def test_command_palette_and_wizard_worksheet_awareness(self):
        from statcraft.modern_app import ModernWindow

        win = ModernWindow(sandbox_mode=True)
        win.show()
        self.app.processEvents()

        acts = collect_menu_actions(win.menuBar())
        self.assertGreater(len(acts), 60)
        pal = CommandPaletteDialog(win, acts, dark_mode=True)
        pal.query_edit.setText("treenet")
        self.app.processEvents()
        self.assertGreaterEqual(pal.results_list.count(), 1)
        self.assertIn("TreeNet", pal.results_list.item(0).text())
        pal.close()

        wiz = GuidedAssistantDialog(win, dark_mode=False, worksheet_summary="Active Worksheet 'Test': 12 rows")
        self.assertEqual(wiz.worksheet_summary, "Active Worksheet 'Test': 12 rows")
        wiz.close()
        win.close()


if __name__ == "__main__":
    unittest.main()
