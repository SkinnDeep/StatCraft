"""Unit tests for Smart Next Steps Statistical Guidance Chips."""
import unittest
from statcraft.guidance_chips import get_smart_guidance_chips


class TestGuidanceChips(unittest.TestCase):
    def test_normality_failure_suggestions(self):
        entry = {
            "title": "Graphical Summary",
            "result": {"analysis": "graphical_summary", "normality_p": 0.008}
        }
        chips = get_smart_guidance_chips(entry)
        actions = [c["action"] for c in chips]
        self.assertIn("johnson_transformation", actions)
        self.assertIn("capability_nonparametric", actions)

    def test_significant_anova_suggestions(self):
        entry = {
            "title": "One-Way ANOVA",
            "result": {"analysis": "oneway_anova", "p_value": 0.001}
        }
        chips = get_smart_guidance_chips(entry)
        actions = [c["action"] for c in chips]
        self.assertIn("tukey_comparisons", actions)

    def test_multicollinearity_regression_suggestions(self):
        entry = {
            "title": "Multiple Regression",
            "result": {
                "analysis": "multiple_regression",
                "coefficients": [{"term": "X1", "vif": 8.5}]
            }
        }
        chips = get_smart_guidance_chips(entry)
        actions = [c["action"] for c in chips]
        self.assertIn("stepwise_regression", actions)


if __name__ == "__main__":
    unittest.main()
