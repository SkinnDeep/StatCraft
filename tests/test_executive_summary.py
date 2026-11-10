"""Unit tests for Automated Plain English Executive Summary."""
import unittest
from statcraft.executive_summary import generate_executive_summary


class TestExecutiveSummary(unittest.TestCase):
    def test_regression_summary(self):
        entry = {
            "title": "Multiple Regression: Yield vs Temp, Speed",
            "recipe": {"action": "multiple_regression"},
            "result": {
                "analysis": "multiple_regression",
                "r_squared": 0.865,
                "overall_p": 0.0012,
                "coefficients": [
                    {"term": "Constant", "p_value": 0.001},
                    {"term": "Temp", "p_value": 0.0004},
                    {"term": "Speed", "p_value": 0.245},
                ],
                "unusual_observations": [{"row": 12, "type": "R"}]
            }
        }
        bullets = generate_executive_summary(entry)
        self.assertGreaterEqual(len(bullets), 2)
        self.assertIn("statistically significant", bullets[0].lower())
        self.assertIn("86.5%", bullets[0])
        self.assertIn("Temp", bullets[1])
        self.assertIn("unusual", bullets[2].lower())

    def test_capability_summary_capable(self):
        entry = {
            "title": "Process Capability Analysis for Diameter",
            "recipe": {"action": "capability_analysis"},
            "result": {
                "analysis": "capability_analysis",
                "cp": 1.65,
                "cpk": 1.45,
                "ppm_total": 6.8
            }
        }
        bullets = generate_executive_summary(entry)
        self.assertIn("fully capable", bullets[0].lower())
        self.assertIn("1.45", bullets[0])
        self.assertIn("PPM", bullets[1])

    def test_capability_summary_not_capable(self):
        entry = {
            "title": "Process Capability",
            "recipe": {"action": "capability_analysis"},
            "result": {
                "analysis": "capability_analysis",
                "cp": 0.90,
                "cpk": 0.72,
                "ppm_total": 15400.0
            }
        }
        bullets = generate_executive_summary(entry)
        self.assertIn("not capable", bullets[0].lower())

    def test_anova_summary_significant(self):
        entry = {
            "title": "One-Way ANOVA: Strength by Shift",
            "recipe": {"action": "oneway_anova"},
            "result": {
                "analysis": "oneway_anova",
                "p_value": 0.0045
            }
        }
        bullets = generate_executive_summary(entry)
        self.assertIn("statistically significant", bullets[0].lower())
        self.assertIn("Tukey", bullets[1])

    def test_spc_summary_in_control(self):
        entry = {
            "title": "I-MR Chart of Viscosity",
            "recipe": {"action": "imr"},
            "result": {
                "analysis": "control_chart",
                "rule_violations": []
            }
        }
        bullets = generate_executive_summary(entry)
        self.assertIn("stable statistical control", bullets[0].lower())


if __name__ == "__main__":
    unittest.main()
