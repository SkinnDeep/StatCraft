"""Unit and integration tests for Preview 104: Two-Way ANOVA & Patterned Data Generation."""
import unittest
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft.twoway_anova_engine import compute_twoway_anova
from statcraft.twoway_anova_report import format_twoway_anova_report
from statcraft.calc_data import make_patterned_arbitrary_numbers, make_patterned_text
from statcraft.recipes import run


class TestPreview104Features(unittest.TestCase):

    def setUp(self):
        # Balanced 2x3 two-factor design with 2 replicates per cell (N = 12)
        # Factor A: "A1", "A2"
        # Factor B: "B1", "B2", "B3"
        self.y = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 15.0, 17.0, 19.0, 21.0, 23.0, 25.0]
        self.fa = ["A1", "A1", "A1", "A1", "A1", "A1", "A2", "A2", "A2", "A2", "A2", "A2"]
        self.fb = ["B1", "B1", "B2", "B2", "B3", "B3", "B1", "B1", "B2", "B2", "B3", "B3"]

        self.ws = Worksheet("ANOVA_Test", [
            Column("Response", "number", self.y),
            Column("FactorA", "text", self.fa),
            Column("FactorB", "text", self.fb)
        ])
        self.p = Presenter()
        self.p.worksheet = self.ws

    def test_twoway_anova_computation(self):
        res = compute_twoway_anova(
            responses=self.y,
            factor_a_vals=self.fa,
            factor_b_vals=self.fb,
            response_name="Response",
            factor_a_name="FactorA",
            factor_b_name="FactorB",
            fit_interaction=True
        )
        self.assertEqual(res["count"], 12)
        self.assertEqual(res["df_a"], 1)
        self.assertEqual(res["df_b"], 2)
        self.assertEqual(res["df_ab"], 2)
        self.assertEqual(res["df_error"], 6)
        self.assertEqual(res["df_total"], 11)

        # Total SS must equal sum of component SS
        ss_sum = res["ss_a"] + res["ss_b"] + res["ss_ab"] + res["ss_error"]
        self.assertAlmostEqual(res["ss_total"], ss_sum, places=4)

        # F and P values exist
        self.assertIsNotNone(res["f_a"])
        self.assertIsNotNone(res["p_a"])
        self.assertIsNotNone(res["f_b"])
        self.assertIsNotNone(res["p_b"])
        self.assertTrue(0.0 <= res["r_squared"] <= 1.0)
        self.assertTrue(res["s"] > 0)

        # Means tables
        self.assertEqual(len(res["factor_a_stats"]), 2)
        self.assertEqual(len(res["factor_b_stats"]), 3)

    def test_twoway_anova_additive(self):
        res = compute_twoway_anova(
            responses=self.y,
            factor_a_vals=self.fa,
            factor_b_vals=self.fb,
            fit_interaction=False
        )
        self.assertFalse(res["fit_interaction"])
        self.assertEqual(res["df_ab"], 0)
        self.assertEqual(res["df_error"], 8)  # 11 - 1 - 2 = 8
        self.assertAlmostEqual(res["ss_total"], res["ss_a"] + res["ss_b"] + res["ss_error"], places=4)

    def test_twoway_anova_report(self):
        res = compute_twoway_anova(self.y, self.fa, self.fb, "Yield", "Temp", "Pressure")
        text = format_twoway_anova_report(res)
        self.assertIn("Two-Way Analysis of Variance: Yield versus Temp, Pressure", text)
        self.assertIn("Temp", text)
        self.assertIn("Pressure", text)
        self.assertIn("Model Summary", text)
        self.assertIn("Means", text)

        entry = {
            "title": "Two-Way ANOVA: Yield versus Temp, Pressure",
            "time": "Test Time",
            "result": res
        }
        output = format_entry(entry)
        self.assertIn("Two-Way Analysis of Variance", output)
        self.assertIn("Model Summary", output)

    def test_twoway_anova_presenter_and_recipe(self):
        entry = self.p.twoway_anova(0, 1, 2, fit_interaction=True)
        self.assertEqual(entry["recipe"]["action"], "twoway_anova")
        self.assertIn("ss_a", entry["result"])

        # Replay via recipe runner
        replayed = run(self.p, entry["recipe"])
        self.assertAlmostEqual(replayed["result"]["ss_total"], entry["result"]["ss_total"], places=4)

    def test_patterned_arbitrary_numbers(self):
        vals = make_patterned_arbitrary_numbers([10.0, 20.0, 50.0], repeat_each=2, repeat_sequence=3)
        self.assertEqual(len(vals), 3 * 2 * 3)  # 18
        self.assertEqual(vals[:4], [10.0, 10.0, 20.0, 20.0])

        # Test presenter
        self.p.make_patterned_arbitrary(-1, [1.0, 2.0], repeat_each=2, repeat_sequence=1)
        self.assertEqual(len(self.ws.columns), 4)
        self.assertEqual(self.ws.columns[3].values, [1.0, 1.0, 2.0, 2.0])

    def test_patterned_text(self):
        texts = make_patterned_text(["Low", "High"], repeat_each=3, repeat_sequence=2)
        self.assertEqual(len(texts), 2 * 3 * 2)  # 12
        self.assertEqual(texts[:6], ["Low", "Low", "Low", "High", "High", "High"])

        # Test presenter
        self.p.make_patterned_text_data(-1, ["A", "B", "C"], repeat_each=1, repeat_sequence=2)
        self.assertEqual(len(self.ws.columns), 4)
        self.assertEqual(self.ws.columns[3].kind, "text")
        self.assertEqual(self.ws.columns[3].values, ["A", "B", "C", "A", "B", "C"])


if __name__ == "__main__":
    unittest.main()
