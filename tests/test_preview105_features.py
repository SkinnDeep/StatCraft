"""Unit and integration tests for Preview 105: Main Effects & Interaction Plots, Store Descriptive Statistics, and Patterned DateTime Generation."""
import unittest
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft.anova_plots_engine import compute_main_effects, compute_interactions
from statcraft.anova_plots_report import format_main_effects_report, format_interactions_report
from statcraft.store_descriptive import compute_store_descriptive_columns
from statcraft.calc_data import make_patterned_datetime
from statcraft.recipes import run


class TestPreview105Features(unittest.TestCase):

    def setUp(self):
        # Sample data: 12 observations across 2 factors
        # Response: Yield
        # Factor 1: Temperature ("Low", "High")
        # Factor 2: Pressure (10, 20, 30)
        self.y = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 15.0, 17.0, 19.0, 21.0, 23.0, 25.0]
        self.temp = ["Low", "Low", "Low", "Low", "Low", "Low", "High", "High", "High", "High", "High", "High"]
        self.press = [10, 10, 20, 20, 30, 30, 10, 10, 20, 20, 30, 30]

        self.ws = Worksheet("Study105", [
            Column("Yield", "number", self.y),
            Column("Temperature", "text", self.temp),
            Column("Pressure", "number", self.press)
        ])
        self.p = Presenter()
        self.p.worksheet = self.ws

    def test_main_effects_computation(self):
        res = compute_main_effects(
            responses=self.y,
            factors_data=[self.temp, self.press],
            response_name="Yield",
            factor_names=["Temperature", "Pressure"]
        )
        self.assertEqual(res["count"], 12)
        self.assertAlmostEqual(res["grand_mean"], sum(self.y) / 12, places=4)
        self.assertEqual(len(res["factor_summaries"]), 2)

        # Factor 1: Temperature
        f1 = res["factor_summaries"][0]
        self.assertEqual(f1["factor_name"], "Temperature")
        self.assertEqual(f1["levels"], ["High", "Low"])
        self.assertEqual(len(f1["level_stats"]), 2)
        # Low mean = (10+12+14+16+18+20)/6 = 15.0
        low_stat = next(s for s in f1["level_stats"] if s["level"] == "Low")
        self.assertAlmostEqual(low_stat["mean"], 15.0, places=4)
        self.assertEqual(low_stat["count"], 6)

        # High mean = (15+17+19+21+23+25)/6 = 20.0
        high_stat = next(s for s in f1["level_stats"] if s["level"] == "High")
        self.assertAlmostEqual(high_stat["mean"], 20.0, places=4)

        # Factor 2: Pressure (10, 20, 30)
        f2 = res["factor_summaries"][1]
        self.assertEqual(f2["factor_name"], "Pressure")
        self.assertEqual(f2["levels"], ["10", "20", "30"])
        self.assertEqual(len(f2["level_stats"]), 3)

    def test_interactions_computation(self):
        res = compute_interactions(
            responses=self.y,
            factor_a_vals=self.temp,
            factor_b_vals=self.press,
            response_name="Yield",
            factor_a_name="Temperature",
            factor_b_name="Pressure"
        )
        self.assertEqual(res["count"], 12)
        self.assertEqual(len(res["levels_a"]), 2)
        self.assertEqual(len(res["levels_b"]), 3)
        self.assertEqual(len(res["curves"]), 3)  # One curve per Pressure level

        # Cell (Low, 10) -> [10.0, 12.0] -> mean 11.0
        cell_10_low = res["cell_stats"]["Low"]["10"]
        self.assertEqual(cell_10_low["count"], 2)
        self.assertAlmostEqual(cell_10_low["mean"], 11.0, places=4)

    def test_anova_plots_reports(self):
        res_me = compute_main_effects(self.y, [self.temp, self.press], "Yield", ["Temp", "Press"])
        report_me = format_main_effects_report(res_me)
        self.assertIn("Main Effects Plot for Yield", report_me)
        self.assertIn("Temp", report_me)
        self.assertIn("Press", report_me)

        res_ia = compute_interactions(self.y, self.temp, self.press, "Yield", "Temp", "Press")
        report_ia = format_interactions_report(res_ia)
        self.assertIn("Interaction Plot for Yield", report_ia)
        self.assertIn("Data Means: Temp by Press", report_ia)

        # format_entry integration
        entry_me = {"title": "Main Effects Plot", "time": "T", "result": res_me}
        self.assertIn("Main Effects Plot", format_entry(entry_me))

        entry_ia = {"title": "Interaction Plot", "time": "T", "result": res_ia}
        self.assertIn("Interaction Plot", format_entry(entry_ia))

    def test_presenter_and_recipe_replay(self):
        # 1. Main Effects Plot
        entry_me = self.p.main_effects_plot(0, [1, 2])
        self.assertEqual(entry_me["recipe"]["action"], "main_effects_plot")
        replayed_me = run(self.p, entry_me["recipe"])
        self.assertAlmostEqual(replayed_me["result"]["grand_mean"], entry_me["result"]["grand_mean"], places=4)

        # 2. Interactions Plot
        entry_ia = self.p.interactions_plot(0, 1, 2)
        self.assertEqual(entry_ia["recipe"]["action"], "interactions_plot")
        replayed_ia = run(self.p, entry_ia["recipe"])
        self.assertAlmostEqual(replayed_ia["result"]["grand_mean"], entry_ia["result"]["grand_mean"], places=4)

    def test_store_descriptive_stats_ungrouped(self):
        cols = compute_store_descriptive_columns(
            self.ws,
            var_indices=[0],
            by_index=None,
            selected_stats=["mean", "stdev", "minimum", "median", "maximum", "n"]
        )
        self.assertEqual(len(cols), 6)
        mean_col = next(c for c in cols if c.name == "Mean_Yield")
        self.assertAlmostEqual(mean_col.values[0], sum(self.y) / 12, places=4)

        n_col = next(c for c in cols if c.name == "N_Yield")
        self.assertEqual(n_col.values[0], 12)

    def test_store_descriptive_stats_grouped(self):
        # Group Yield by Temperature (Low vs High)
        cols = compute_store_descriptive_columns(
            self.ws,
            var_indices=[0],
            by_index=1,
            selected_stats=["mean", "n"]
        )
        # Should produce: By_Temperature, Mean_Yield, N_Yield
        self.assertEqual(len(cols), 3)
        by_col = cols[0]
        self.assertEqual(by_col.name, "By_Temperature")
        self.assertEqual(set(by_col.values), {"Low", "High"})

        mean_col = cols[1]
        self.assertEqual(len(mean_col.values), 2)

    def test_presenter_store_descriptive_and_undo(self):
        init_col_count = len(self.p.worksheet.columns)
        self.p.store_descriptive_stats(var_indices=[0], by_index=1, selected_stats=["mean"])
        self.assertEqual(len(self.p.worksheet.columns), init_col_count + 2)  # By_Temp + Mean_Yield

        # Undo
        self.p.undo()
        self.assertEqual(len(self.p.worksheet.columns), init_col_count)

    def test_make_patterned_datetime_daily(self):
        # Generate daily sequence from 2026-01-01 to 2026-01-05
        seq = make_patterned_datetime("2026-01-01", "2026-01-05", step=1, unit="days")
        self.assertEqual(seq, ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"])

    def test_make_patterned_datetime_weekly_and_repetitions(self):
        seq = make_patterned_datetime("2026-01-01", count=3, step=1, unit="weeks", repeat_each=2, repeat_sequence=2)
        # 3 weekly dates: 2026-01-01, 2026-01-08, 2026-01-15
        # repeat_each=2 -> 6 items
        # repeat_sequence=2 -> 12 items
        self.assertEqual(len(seq), 12)
        self.assertEqual(seq[:4], ["2026-01-01", "2026-01-01", "2026-01-08", "2026-01-08"])

    def test_presenter_patterned_datetime_and_undo(self):
        init_col_count = len(self.p.worksheet.columns)
        self.p.make_patterned_datetime_data(-1, "2026-10-01", count=5, step=1, unit="days")
        self.assertEqual(len(self.p.worksheet.columns), init_col_count + 1)
        added_col = self.p.worksheet.columns[-1]
        self.assertEqual(added_col.kind, "date")
        self.assertEqual(len(added_col.values), 5)

        # Undo
        self.p.undo()
        self.assertEqual(len(self.p.worksheet.columns), init_col_count)

    def test_charts_render_offscreen(self):
        from PySide6.QtWidgets import QApplication
        from statcraft.modern_charts import ChartWidget
        app = QApplication.instance() or QApplication([])

        entry_me = self.p.main_effects_plot(0, [1, 2])
        w_me = ChartWidget(entry_me)
        w_me.resize(800, 500)
        pix_me = w_me.grab()
        self.assertFalse(pix_me.isNull())

        entry_ia = self.p.interactions_plot(0, 1, 2)
        w_ia = ChartWidget(entry_ia)
        w_ia.resize(800, 500)
        pix_ia = w_ia.grab()
        self.assertFalse(pix_ia.isNull())


if __name__ == '__main__':
    unittest.main()
