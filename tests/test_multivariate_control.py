"""Unit tests for Multivariate Control Charts (Hotelling's T-Squared, Generalized Variance, MEWMA)."""

import math
import unittest
import numpy as np

from statcraft.multivariate_control_engine import (
    organize_multivariate_data,
    compute_multivariate_parameters,
    run_tsquared_control,
    run_genvar_control,
    run_mewma_control,
)
from statcraft.multivariate_control_report import generate_multivariate_report


class TestMultivariateControl(unittest.TestCase):
    def test_organize_multivariate_data(self):
        # Require at least 2 variables
        with self.assertRaises(ValueError):
            organize_multivariate_data([[1.0, 2.0, 3.0]])

        col1 = [1.0, 2.0, 3.0, 4.0, "*", 6.0]
        col2 = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]

        # Missing value handling (row 5 omitted)
        subgroups, sizes = organize_multivariate_data([col1, col2], subgroup_size=1)
        self.assertEqual(len(subgroups), 5)
        self.assertTrue(all(s == 1 for s in sizes))

        # Subgroups of size 2
        subgroups2, sizes2 = organize_multivariate_data([col1, col2], subgroup_size=2)
        self.assertEqual(len(subgroups2), 3)
        self.assertEqual(sizes2, [2, 2, 1])

        # Subgroup ID column
        sg_ids = ["A", "A", "B", "B", "B"]
        subgroups3, sizes3 = organize_multivariate_data([[1, 2, 3, 4, 5], [10, 20, 30, 40, 50]], subgroup_size=sg_ids)
        self.assertEqual(len(subgroups3), 2)
        self.assertEqual(sizes3, [2, 3])

    def test_tsquared_individual_obs(self):
        # 2 variables, 25 observations
        np.random.seed(42)
        x1 = np.random.normal(10, 2, 25).tolist()
        x2 = np.random.normal(50, 5, 25).tolist()

        # Outlier at observation 10
        x1[9] = 25.0
        x2[9] = 75.0

        res = run_tsquared_control(
            columns_data=[x1, x2],
            subgroup_size=1,
            alpha=0.0027,
            variable_names=["Length", "Width"],
        )

        self.assertEqual(res["chart_type"], "TSQUARED")
        self.assertEqual(res["k_subgroups"], 25)
        self.assertEqual(res["p_variables"], 2)
        self.assertGreater(res["ucl_val"], 0)
        self.assertIn(10, res["signals"])
        self.assertIn(10, res["decompositions"])
        decomp = res["decompositions"][10]
        self.assertIn("Length", decomp)
        self.assertIn("Width", decomp)
        self.assertTrue(decomp["Length"] > 3.0 or decomp["Width"] > 3.0)

        report = generate_multivariate_report(res)
        self.assertIn("T² Control Chart of Length, Width", report)
        self.assertIn("Individual Variable Contributions", report)

    def test_tsquared_subgroups(self):
        # 2 variables, 10 subgroups of size 3
        np.random.seed(123)
        x1 = np.random.normal(100, 10, 30).tolist()
        x2 = np.random.normal(200, 15, 30).tolist()

        res = run_tsquared_control(
            columns_data=[x1, x2],
            subgroup_size=3,
            alpha=0.01,
            variable_names=["Flow", "Pressure"],
        )

        self.assertEqual(res["chart_type"], "TSQUARED")
        self.assertEqual(res["k_subgroups"], 10)
        self.assertEqual(res["subgroup_sizes"], [3] * 10)
        self.assertGreater(res["ucl_val"], 0)

    def test_generalized_variance(self):
        # Subgroup size 1 should raise error
        with self.assertRaises(ValueError):
            run_genvar_control([[1.0, 2.0], [3.0, 4.0]], subgroup_size=1)

        # 3 variables, 8 subgroups of size 5
        np.random.seed(777)
        x1 = np.random.normal(10, 1, 40).tolist()
        x2 = np.random.normal(20, 2, 40).tolist()
        x3 = np.random.normal(30, 3, 40).tolist()

        res = run_genvar_control(
            columns_data=[x1, x2, x3],
            subgroup_size=5,
            options={"k_sigma": 3.0},
            variable_names=["V1", "V2", "V3"],
        )

        self.assertEqual(res["chart_type"], "GENVAR")
        self.assertEqual(res["k_subgroups"], 8)
        self.assertGreaterEqual(res["center_line"], 0)
        self.assertGreater(res["ucl_val"], res["center_line"])
        self.assertGreater(res["b1"], 0)
        self.assertGreater(res["b2"], 0)

        report = generate_multivariate_report(res)
        self.assertIn("Generalized Variance Chart of V1, V2, V3", report)
        self.assertIn("Center Line (|S|):", report)

    def test_mewma_control(self):
        np.random.seed(999)
        x1 = np.random.normal(50, 5, 20).tolist()
        x2 = np.random.normal(100, 10, 20).tolist()

        # Injected shift starting at observation 15
        for i in range(14, 20):
            x1[i] += 15.0
            x2[i] += 30.0

        res = run_mewma_control(
            columns_data=[x1, x2],
            subgroup_size=1,
            weight=0.2,
            arl=200.0,
            options={"omit_subgroups": "15-20"},
            variable_names=["Weight", "Strength"],
        )

        self.assertEqual(res["chart_type"], "MEWMA")
        self.assertEqual(res["k_subgroups"], 20)
        self.assertEqual(res["weight"], 0.2)
        self.assertEqual(res["arl"], 200.0)
        self.assertGreater(res["ucl_val"], 0)
        self.assertTrue(any(sig >= 15 for sig in res["signals"]))

        report = generate_multivariate_report(res)
        self.assertIn("Multivariate EWMA Chart of Weight, Strength", report)
        self.assertIn("Weight (r):", report)


if __name__ == "__main__":
    unittest.main()
