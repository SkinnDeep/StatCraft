"""Tests for Nonnormal Process Capability Analysis (Preview 74)."""

import unittest
import numpy as np

from statcraft.capability_nonnormal_engine import (
    fit_nonnormal_distribution,
    fit_box_cox_transformation,
    compute_nonnormal_indices,
    run_nonnormal_capability,
)
from statcraft.capability_nonnormal_report import format_nonnormal_capability_report


class TestNonnormalCapability(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        # Weibull distributed data: shape=1.5, scale=10.0
        self.weibull_data = (np.random.weibull(1.5, 100) * 10.0).tolist()
        # Lognormal data
        self.lognorm_data = np.random.lognormal(2.0, 0.4, 100).tolist()

    def test_weibull_capability(self):
        res = run_nonnormal_capability(
            self.weibull_data,
            dist_or_transform="weibull",
            lsl=1.0,
            usl=25.0
        )
        self.assertEqual(res["method"], "weibull")
        self.assertIn("shape", res["fit_info"]["parameters"])
        self.assertIn("scale", res["fit_info"]["parameters"])
        
        idx = res["indices"]
        self.assertIsNotNone(idx["pp"])
        self.assertIsNotNone(idx["ppk"])
        self.assertGreater(idx["pp"], 0)
        self.assertGreater(idx["ppk"], 0)

        # Check report formatting
        rep = format_nonnormal_capability_report(res)
        self.assertIn("Nonnormal Capability Analysis", rep)
        self.assertIn("Distribution Parameters", rep)
        self.assertIn("Overall Capability", rep)

    def test_box_cox_capability(self):
        res = run_nonnormal_capability(
            self.lognorm_data,
            dist_or_transform="box_cox",
            lsl=3.0,
            usl=20.0
        )
        self.assertEqual(res["method"], "box_cox")
        self.assertIn("lambda", res["fit_info"])
        idx = res["indices"]
        self.assertIsNotNone(idx["pp"])
        self.assertIsNotNone(idx["ppk"])

    def test_aiag_vda_nomenclature(self):
        res = run_nonnormal_capability(
            self.weibull_data,
            dist_or_transform="weibull",
            lsl=1.0,
            usl=25.0,
            naming_convention="aiag_vda"
        )
        idx = res["indices"]
        self.assertIn("cnp", idx)
        self.assertIn("cnpk", idx)
        rep = format_nonnormal_capability_report(res)
        self.assertIn("Cnp:", rep)
        self.assertIn("Cnpk:", rep)


if __name__ == '__main__':
    unittest.main()
