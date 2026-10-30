"""Tests for Streamlined Reliability Distribution Analysis (Preview 75)."""

import unittest
import numpy as np

from statcraft.reliability_engine import (
    fit_parametric_reliability,
    fit_kaplan_meier,
    run_reliability_analysis,
)
from statcraft.reliability_report import format_reliability_report


class TestReliabilityDistribution(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        # Weibull distributed times: shape=1.6, scale=120.0
        self.raw_times = (np.random.weibull(1.6, 50) * 120.0).tolist()
        # Censoring indicator: 1=failure, 0=censored (approx 20% censored)
        self.censors = [0 if (i % 5 == 0) else 1 for i in range(50)]

    def test_weibull_reliability_mle(self):
        res = run_reliability_analysis(
            time_values=self.raw_times,
            censor_values=self.censors,
            dist_name="weibull"
        )
        self.assertEqual(res["dist_name"], "weibull")
        self.assertIn("shape", res["parameters"])
        self.assertIn("scale", res["parameters"])
        self.assertGreater(res["mttf"], 0.0)
        self.assertEqual(len(res["percentile_table"]), 6)

        # Check Kaplan-Meier survival
        self.assertIn("kaplan_meier", res)
        self.assertGreater(len(res["kaplan_meier"]["times"]), 0)

        # Check report formatting
        rep = format_reliability_report(res)
        self.assertIn("Distribution Analysis", rep)
        self.assertIn("Table of Parameters", rep)
        self.assertIn("Table of Percentiles", rep)

    def test_lognormal_reliability(self):
        res = run_reliability_analysis(
            time_values=self.raw_times,
            dist_name="lognormal"
        )
        self.assertEqual(res["dist_name"], "lognormal")
        self.assertIn("location", res["parameters"])
        self.assertIn("scale", res["parameters"])

    def test_exponential_reliability(self):
        res = run_reliability_analysis(
            time_values=self.raw_times,
            censor_values=self.censors,
            dist_name="exponential"
        )
        self.assertEqual(res["dist_name"], "exponential")
        self.assertIn("scale_mean", res["parameters"])


if __name__ == '__main__':
    unittest.main()
