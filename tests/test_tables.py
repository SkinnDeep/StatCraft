"""Comprehensive unit tests for Tables and Chi-Square analysis in StatCraft."""

import unittest
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft.tables import (
    cross_tabulation,
    chi_square_goodness_of_fit,
    chi_square_association_table,
    tally_variables,
)
from statcraft.tables_report import (
    format_cross_tabulation_report,
    format_chi_square_goodness_of_fit_report,
    format_chi_square_association_table_report,
    format_tally_variables_report,
)
from statcraft.recipes import columns as recipe_columns


class TestTablesEngine(unittest.TestCase):
    def test_cross_tabulation_basic(self):
        # 2x2 contingency: Gender (M/F) vs Preference (A/B)
        row = ["M", "M", "M", "M", "F", "F", "F", "F"]
        col = ["A", "A", "B", "B", "A", "B", "B", "B"]
        res = cross_tabulation(row, col, row_name="Gender", col_name="Preference")
        self.assertEqual(res["analysis"], "cross_tabulation")
        self.assertEqual(res["grand_total"], 8)
        self.assertEqual(res["df"], 1)
        self.assertIn("pearson_chi_square", res)
        self.assertIn("likelihood_ratio_chi_square", res)
        self.assertIn("expected", res)
        self.assertIn("row_percents", res)
        self.assertIn("col_percents", res)

        rep = format_cross_tabulation_report(res)
        self.assertIn("Tabulated statistics: Gender, Preference", rep)
        self.assertIn("Chi-Square Test", rep)
        self.assertIn("Pearson", rep)

    def test_cross_tabulation_with_frequencies(self):
        # 2x3 table with frequency counts
        rows = ["Control", "Control", "Control", "Treatment", "Treatment", "Treatment"]
        cols = ["Low", "Med", "High", "Low", "Med", "High"]
        freqs = [20, 30, 50, 40, 35, 25]
        res = cross_tabulation(rows, cols, freq_data=freqs, include_total_percents=True)
        self.assertEqual(res["grand_total"], 200)
        self.assertEqual(res["df"], 2)
        self.assertAlmostEqual(sum(sum(r) for r in res["observed"]), 200.0)
        self.assertAlmostEqual(sum(sum(r) for r in res["expected"]), 200.0)

        rep = format_cross_tabulation_report(res)
        self.assertIn("Chi-Square Test", rep)
        self.assertIn("Likelihood Ratio", rep)

    def test_chi_square_goodness_of_fit_equal(self):
        # 4 categories with equal expected proportions
        data = ["A", "B", "C", "D"]
        freqs = [25, 30, 20, 25]
        res = chi_square_goodness_of_fit(data, var_name="Type", freq_data=freqs)
        self.assertEqual(res["analysis"], "chi_square_goodness_of_fit")
        self.assertEqual(res["n_obs"], 100)
        self.assertEqual(res["df"], 3)
        self.assertAlmostEqual(res["rows"][0]["expected"], 25.0)

        rep = format_chi_square_goodness_of_fit_report(res)
        self.assertIn("Chi-Square Goodness-of-Fit Test", rep)
        self.assertIn("Total observations: 100", rep)

    def test_chi_square_goodness_of_fit_specified(self):
        # Specified test proportions (e.g. Mendelian 9:3:3:1)
        data = ["Round-Yellow", "Round-Green", "Wrinkled-Yellow", "Wrinkled-Green"]
        freqs = [315, 108, 101, 32]
        props = {"Round-Yellow": 9/16, "Round-Green": 3/16, "Wrinkled-Yellow": 3/16, "Wrinkled-Green": 1/16}
        res = chi_square_goodness_of_fit(data, var_name="Phenotype", freq_data=freqs, test_proportions=props)
        self.assertEqual(res["n_obs"], 556)
        self.assertEqual(res["df"], 3)
        self.assertGreater(res["p_value"], 0.8)  # Good fit to 9:3:3:1

        rep = format_chi_square_goodness_of_fit_report(res)
        self.assertIn("Chi-Square Goodness-of-Fit Test", rep)
        self.assertIn("Contribution", rep)

    def test_chi_square_association_table(self):
        # 3x2 table given as worksheet columns
        # Columns: Normal, Defective
        # Rows: Machine 1, Machine 2, Machine 3
        table = [
            [100.0, 10.0],
            [120.0, 15.0],
            [90.0, 5.0],
        ]
        r_names = ["Machine 1", "Machine 2", "Machine 3"]
        c_names = ["Normal", "Defective"]
        res = chi_square_association_table(table, row_names=r_names, col_names=c_names)
        self.assertEqual(res["analysis"], "chi_square_association_table")
        self.assertEqual(res["df"], 2)
        self.assertEqual(res["grand_total"], 340.0)

        rep = format_chi_square_association_table_report(res)
        self.assertIn("Chi-Square Test for Association", rep)
        self.assertIn("Pearson", rep)

    def test_tally_variables(self):
        vals = ["Pass", "Fail", "Pass", "Pass", "Pass", "Fail", None]
        res = tally_variables(vals, var_name="Inspection")
        self.assertEqual(res["analysis"], "tally_variables")
        self.assertEqual(res["n_valid"], 6)
        self.assertEqual(res["n_missing"], 1)
        values = [r["value"] for r in res["rows"]]
        counts = [r["count"] for r in res["rows"]]
        self.assertEqual(values, ["Fail", "Pass"])
        self.assertEqual(counts, [2, 4])
        self.assertAlmostEqual(res["rows"][0]["percent"], 33.33, places=1)
        self.assertAlmostEqual(res["rows"][1]["percent"], 66.67, places=1)

        rep = format_tally_variables_report(res)
        self.assertIn("Tally for Discrete Variables: Inspection", rep)
        self.assertIn("Cum Count", rep)
        self.assertIn("Cum Pct", rep)


class TestTablesPresenterAndRecipes(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet()
        self.ws.columns = [
            Column("Machine", "text", ["M1", "M1", "M2", "M2", "M3", "M3"]),
            Column("Status", "text", ["Pass", "Fail", "Pass", "Pass", "Pass", "Fail"]),
            Column("Freq", "number", [10, 2, 12, 1, 9, 3]),
            Column("DefectCol1", "number", [15, 20, 25]),
            Column("DefectCol2", "number", [5, 10, 8]),
        ]
        self.p = Presenter()
        self.p.worksheet = self.ws

    def test_presenter_cross_tabulation(self):
        st = {
            "row_column": 0,
            "col_column": 1,
            "freq_column": 2,
            "include_expected": True,
            "include_row_percents": True,
            "include_col_percents": True,
            "include_total_percents": True,
            "include_chi_square": True,
        }
        entry = self.p.cross_tabulation(st)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["result"]["analysis"], "cross_tabulation")
        self.assertEqual(recipe_columns(entry["recipe"]), [0, 1, 2])

    def test_presenter_goodness_of_fit(self):
        st = {
            "observed_column": 0,
            "freq_column": 2,
            "test_proportions": None,
        }
        entry = self.p.chi_square_goodness_of_fit(st)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["result"]["analysis"], "chi_square_goodness_of_fit")
        self.assertEqual(recipe_columns(entry["recipe"]), [0, 2])

    def test_presenter_association_table(self):
        st = {
            "table_columns": [3, 4],
            "row_labels_column": 0,
        }
        entry = self.p.chi_square_association_table(st)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["result"]["analysis"], "chi_square_association_table")
        self.assertEqual(recipe_columns(entry["recipe"]), [0, 3, 4])

    def test_presenter_tally(self):
        st = {
            "columns": [0, 1],
            "include_counts": True,
            "include_percents": True,
            "include_cumulative_counts": True,
            "include_cumulative_percents": True,
        }
        entry = self.p.tally_variables(st)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["result"]["analysis"], "tally_variables")
        self.assertEqual(recipe_columns(entry["recipe"]), [0, 1])


if __name__ == "__main__":
    unittest.main()
