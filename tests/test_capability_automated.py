"""Tests for Nonparametric and Automated Capability Analysis (Preview 76)."""

import unittest
import numpy as np

from statcraft.capability_automated_engine import (
    run_nonparametric_capability,
    run_automated_capability_tournament,
    compute_empirical_percentiles,
)
from statcraft.capability_automated_report import (
    format_nonparametric_capability_report,
    format_automated_capability_report,
)


class TestNonparametricAutomatedCapability(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        # 100 skewed positive values
        self.data = (np.random.weibull(1.7, 100) * 15.0 + 1.0).tolist()

    def test_nonparametric_capability(self):
        res = run_nonparametric_capability(
            self.data,
            lsl=2.0,
            usl=35.0,
            naming_convention="aiag_vda"
        )
        self.assertEqual(res["analysis"], "capability_nonparametric")
        self.assertGreater(res["p_upper"], res["p_median"])
        self.assertGreater(res["p_median"], res["p_lower"])
        
        idx = res["indices"]
        self.assertIn("cnp", idx)
        self.assertIn("cnpk", idx)
        self.assertGreater(idx["cnp"], 0)

        rep = format_nonparametric_capability_report(res)
        self.assertIn("Nonparametric Capability Analysis", rep)
        self.assertIn("Empirical Percentiles", rep)
        self.assertIn("Cnp:", rep)

    def test_automated_capability_tournament(self):
        res = run_automated_capability_tournament(
            self.data,
            lsl=2.0,
            usl=35.0
        )
        self.assertEqual(res["analysis"], "capability_automated")
        self.assertIn("tournament", res)
        self.assertGreaterEqual(len(res["tournament"]), 3)
        self.assertIn("best_fit", res)

        rep = format_automated_capability_report(res)
        self.assertIn("Automated Capability Analysis", rep)
        self.assertIn("Goodness-of-Fit Tournament Summary", rep)


if __name__ == '__main__':
    unittest.main()
