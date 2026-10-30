"""Unit tests for Advanced MSA (Nested Gage R&R, Gage Linearity & Bias, Attribute Agreement)."""
import math
import unittest
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft.msa_nested_engine import analyze_nested_gage_rr
from statcraft.msa_linearity_engine import analyze_gage_linearity_and_bias
from statcraft.msa_attribute_engine import analyze_attribute_agreement
from statcraft.msa_reports import (
    format_nested_gage_rr_report,
    format_gage_linearity_report,
    format_attribute_agreement_report,
)


class TestMSAAdvanced(unittest.TestCase):
    def test_nested_gage_rr_engine(self):
        # 2 operators, 2 parts per operator, 3 replicates per part = 12 observations
        # Operator 1: Parts P1, P2
        # Operator 2: Parts P3, P4
        ops = ["Op1"] * 6 + ["Op2"] * 6
        parts = ["P1", "P1", "P1", "P2", "P2", "P2", "P3", "P3", "P3", "P4", "P4", "P4"]
        meas = [
            10.1, 10.2, 10.1,  # Op1, P1
            12.0, 12.1, 11.9,  # Op1, P2
            10.5, 10.4, 10.6,  # Op2, P3
            12.5, 12.6, 12.4,  # Op2, P4
        ]

        res = analyze_nested_gage_rr(
            measurements=meas,
            parts=parts,
            operators=ops,
            study_multiplier=6.0,
            tolerance=5.0,
        )

        self.assertEqual(res["n_total"], 12)
        self.assertEqual(res["operators_count"], 2)
        self.assertEqual(res["parts_per_operator"], 2)
        self.assertEqual(res["replicates_per_part"], 3)

        anova = {row["source"]: row for row in res["anova"]}
        self.assertEqual(anova["Operator"]["df"], 1)
        self.assertEqual(anova["Part (Operator)"]["df"], 2)
        self.assertEqual(anova["Repeatability"]["df"], 8)
        self.assertEqual(anova["Total"]["df"], 11)

        self.assertGreater(anova["Part (Operator)"]["f"], 1.0)
        self.assertIsNotNone(res["ndc"])
        self.assertGreaterEqual(res["ndc"], 1)

        # Variance components
        comps = {c["key"]: c for c in res["variance_components"]}
        self.assertIn("total_grr", comps)
        self.assertIn("repeatability", comps)
        self.assertIn("reproducibility", comps)
        self.assertIn("part_to_part", comps)
        self.assertIn("total", comps)

        self.assertAlmostEqual(comps["total"]["percent_contribution"], 100.0, places=1)
        self.assertIsNotNone(comps["total_grr"]["percent_tolerance"])

        # Format report
        rep = format_nested_gage_rr_report(res)
        self.assertIn("Gage R&R Study (Nested)", rep)
        self.assertIn("Analysis of Variance for Nested Design", rep)
        self.assertIn("Number of Distinct Categories", rep)

    def test_gage_linearity_and_bias_engine(self):
        # 5 reference standards, each measured 5 times = 25 observations
        ref_unique = [2.0, 4.0, 6.0, 8.0, 10.0]
        refs = []
        meas = []
        for r in ref_unique:
            for rep in range(5):
                refs.append(r)
                # Introduce slight bias: bias = 0.1 + 0.05 * r + noise
                meas.append(r + 0.1 + 0.05 * r + (rep - 2) * 0.01)

        res = analyze_gage_linearity_and_bias(
            reference_values=refs,
            measurements=meas,
            process_variation=10.0,
            alpha=0.05,
        )

        self.assertEqual(res["n_total"], 25)
        self.assertAlmostEqual(res["regression"]["slope"], 0.05, places=2)
        self.assertAlmostEqual(res["regression"]["intercept"], 0.10, places=2)
        self.assertGreater(res["pct_linearity"], 0.0)
        self.assertEqual(len(res["bias_table"]), 5)
        self.assertIn("overall_bias", res)
        self.assertGreater(res["overall_bias"]["t_statistic"], 0.0)

        rep = format_gage_linearity_report(res)
        self.assertIn("Gage Linearity and Bias Study", rep)
        self.assertIn("Regression Equation", rep)
        self.assertIn("Gage Bias Table by Reference Value", rep)
        self.assertIn("Overall Gage Bias", rep)

    def test_attribute_agreement_engine(self):
        # 3 appraisers, 5 samples, 2 trials each = 30 ratings
        apps = []
        samples = []
        ratings = []
        standards = []

        sample_truth = {1: "Pass", 2: "Fail", 3: "Pass", 4: "Pass", 5: "Fail"}
        for app in ["Alice", "Bob", "Charlie"]:
            for s in [1, 2, 3, 4, 5]:
                for trial in [1, 2]:
                    apps.append(app)
                    samples.append(s)
                    standards.append(sample_truth[s])
                    # High agreement with truth, Charlie has 1 mistake on sample 2 trial 2
                    if app == "Charlie" and s == 2 and trial == 2:
                        ratings.append("Pass")
                    else:
                        ratings.append(sample_truth[s])

        res = analyze_attribute_agreement(
            attribute_data=ratings,
            samples=samples,
            appraisers=apps,
            standard=standards,
        )

        self.assertEqual(res["n_samples"], 5)
        self.assertEqual(res["n_appraisers"], 3)
        self.assertTrue(res["has_standard"])

        # Alice & Bob should have 100% agreement
        within = {row["appraiser"]: row for row in res["within_appraiser"]}
        self.assertEqual(within["Alice"]["percent"], 100.0)
        self.assertEqual(within["Alice"]["kappa"], 1.0)
        self.assertEqual(within["Bob"]["percent"], 100.0)
        self.assertAlmostEqual(within["Charlie"]["percent"], 80.0)

        # Appraiser vs standard
        vs_std = {row["appraiser"]: row for row in res["appraiser_vs_standard"]}
        self.assertEqual(vs_std["Alice"]["percent"], 100.0)
        self.assertAlmostEqual(vs_std["Charlie"]["percent"], 80.0)

        # Between appraisers
        bet = res["between_appraisers"]
        self.assertEqual(bet["matched"], 4)
        self.assertAlmostEqual(bet["percent"], 80.0)

        rep = format_attribute_agreement_report(res)
        self.assertIn("Attribute Agreement Analysis", rep)
        self.assertIn("Within Appraiser Agreement", rep)
        self.assertIn("Each Appraiser vs Standard", rep)
        self.assertIn("Between Appraisers Agreement", rep)

    def test_presenter_and_recipe_replay(self):
        # Build worksheet with test data
        ws = Worksheet()
        ws.columns.append(Column("Part", "text", ["P1", "P1", "P2", "P2", "P3", "P3", "P4", "P4"]))
        ws.columns.append(Column("Operator", "text", ["Op1", "Op1", "Op1", "Op1", "Op2", "Op2", "Op2", "Op2"]))
        ws.columns.append(Column("Measure", "number", [10.1, 10.2, 12.0, 11.9, 10.5, 10.4, 12.5, 12.6]))
        ws.columns.append(Column("Ref", "number", [10.0, 10.0, 12.0, 12.0, 10.0, 10.0, 12.0, 12.0]))
        ws.columns.append(Column("Attrib", "text", ["Pass", "Pass", "Fail", "Fail", "Pass", "Pass", "Fail", "Fail"]))
        ws.columns.append(Column("Std", "text", ["Pass", "Pass", "Fail", "Fail", "Pass", "Pass", "Fail", "Fail"]))

        p = Presenter()
        p.worksheet = ws

        # 1. Nested Gage R&R
        e1 = p.nested_gage_rr(part_col="Part", operator_col="Operator", measurement_col="Measure", tolerance=4.0)
        self.assertEqual(e1["result"]["analysis"], "nested_gage_rr")
        rep1 = format_entry(e1)
        self.assertIn("Gage R&R Study (Nested)", rep1)

        # 2. Linearity and Bias
        e2 = p.gage_linearity(reference_col="Ref", measurement_col="Measure", process_variation=5.0)
        self.assertEqual(e2["result"]["analysis"], "gage_linearity_and_bias")
        rep2 = format_entry(e2)
        self.assertIn("Gage Linearity and Bias Study", rep2)

        # 3. Attribute Agreement
        e3 = p.attribute_agreement(attribute_col="Attrib", sample_col="Part", appraiser_col="Operator", standard_col="Std")
        self.assertEqual(e3["result"]["analysis"], "attribute_agreement_analysis")
        rep3 = format_entry(e3)
        self.assertIn("Attribute Agreement Analysis", rep3)

        # Verify recipe rerun
        from statcraft.recipes import run as rerun_recipe
        r1 = rerun_recipe(p, e1["recipe"])
        self.assertEqual(r1["result"]["analysis"], "nested_gage_rr")

        r2 = rerun_recipe(p, e2["recipe"])
        self.assertEqual(r2["result"]["analysis"], "gage_linearity_and_bias")

        r3 = rerun_recipe(p, e3["recipe"])
        self.assertEqual(r3["result"]["analysis"], "attribute_agreement_analysis")


if __name__ == "__main__":
    unittest.main()
