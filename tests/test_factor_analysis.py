"""Unit tests for Factor Analysis."""
import unittest
import numpy as np

from statcraft.factor_analysis import clean_factor_data, fit_factor_analysis
from statcraft.factor_analysis_report import generate_factor_analysis_report
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry


class TestFactorAnalysis(unittest.TestCase):
    def setUp(self):
        # Sample multivariate sensory evaluation data (5 variables, 15 observations)
        np.random.seed(42)
        # 2 underlying latent factors: F1 (Taste) and F2 (Texture)
        f1 = np.random.normal(0, 1, 20)
        f2 = np.random.normal(0, 1, 20)

        # Variables loading on F1
        self.sweet = (0.8 * f1 + 0.1 * f2 + np.random.normal(0, 0.2, 20)).tolist()
        self.flavor = (0.9 * f1 + 0.0 * f2 + np.random.normal(0, 0.2, 20)).tolist()
        self.aftertaste = (0.7 * f1 + 0.2 * f2 + np.random.normal(0, 0.2, 20)).tolist()

        # Variables loading on F2
        self.crisp = (0.1 * f1 + 0.85 * f2 + np.random.normal(0, 0.2, 20)).tolist()
        self.firm = (0.0 * f1 + 0.80 * f2 + np.random.normal(0, 0.2, 20)).tolist()

    def test_clean_data(self):
        col1 = [1.0, 2.0, None, 4.0, 5.0]
        col2 = [5.0, 6.0, 7.0, float('nan'), 9.0]
        x, names = clean_factor_data([col1, col2], ["A", "B"])
        self.assertEqual(len(x), 3)
        self.assertEqual(names, ["A", "B"])

    def test_factor_analysis_varimax(self):
        res = fit_factor_analysis(
            data_columns=[self.sweet, self.flavor, self.aftertaste, self.crisp, self.firm],
            n_factors=2,
            rotation="varimax",
            variable_names=["Sweet", "Flavor", "Aftertaste", "Crisp", "Firm"],
        )
        self.assertEqual(res["analysis"], "factor_analysis")
        self.assertEqual(res["n_factors"], 2)
        self.assertEqual(res["n_vars"], 5)
        self.assertEqual(res["rotation"], "Varimax")

        # Eigenvalues
        eigs = res["eigenvalues"]
        self.assertEqual(len(eigs), 5)
        self.assertAlmostEqual(eigs[-1]["cumulative"], 1.0, places=4)

        # Rotated Loadings
        r_loadings = res["rotated_loadings"]
        self.assertEqual(len(r_loadings), 5)
        for row in r_loadings:
            self.assertIn("communality", row)
            self.assertGreaterEqual(row["communality"], 0.0)
            self.assertLessEqual(row["communality"], 1.0)

        # Factor score coefficients
        scores = res["score_coefficients"]
        self.assertEqual(len(scores), 5)
        self.assertIn("Factor1", scores[0])
        self.assertIn("Factor2", scores[0])

    def test_rotations(self):
        for rot in ["quartimax", "equamax", "none"]:
            res = fit_factor_analysis(
                data_columns=[self.sweet, self.flavor, self.aftertaste, self.crisp, self.firm],
                n_factors=2,
                rotation=rot,
            )
            self.assertEqual(res["analysis"], "factor_analysis")
            self.assertEqual(len(res["rotated_loadings"]), 5)

    def test_report_generation(self):
        res = fit_factor_analysis(
            data_columns=[self.sweet, self.flavor, self.aftertaste, self.crisp, self.firm],
            n_factors=2,
            rotation="varimax",
            variable_names=["Sweet", "Flavor", "Aftertaste", "Crisp", "Firm"],
        )
        report = generate_factor_analysis_report(res)
        self.assertIn("Factor Analysis", report)
        self.assertIn("Extraction Method: Principal Components", report)
        self.assertIn("Rotation:          Varimax", report)
        self.assertIn("Eigenvalues of the Correlation Matrix", report)
        self.assertIn("Unrotated Factor Loadings and Communalities", report)
        self.assertIn("Rotated Factor Loadings and Communalities", report)
        self.assertIn("Factor Score Coefficients", report)

    def test_presenter_integration(self):
        ws = Worksheet("Sensory", [
            Column("Sweet", values=self.sweet),
            Column("Flavor", values=self.flavor),
            Column("Aftertaste", values=self.aftertaste),
            Column("Crisp", values=self.crisp),
            Column("Firm", values=self.firm),
        ])
        p = Presenter()
        p.worksheet = ws

        entry = p.factor_analysis(
            variable_columns=[0, 1, 2, 3, 4],
            n_factors=2,
            rotation="varimax",
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "factor_analysis")
        text = format_entry(entry)
        self.assertIn("Factor Analysis", text)
        self.assertIn("Eigenvalues of the Correlation Matrix", text)
        self.assertIn("Rotated Factor Loadings", text)

    def test_factor_loading_chart_rendering(self):
        from PySide6.QtWidgets import QApplication
        from statcraft.multivariate_chart import MultivariateChartWidget
        app = QApplication.instance() or QApplication([])
        res = fit_factor_analysis(
            data_columns=[self.sweet, self.flavor, self.aftertaste, self.crisp, self.firm],
            n_factors=2,
            rotation="varimax",
            variable_names=["Sweet", "Flavor", "Aftertaste", "Crisp", "Firm"],
        )
        entry = {"title": "Factor Analysis", "result": res}
        widget = MultivariateChartWidget(entry)
        widget.resize(700, 500)
        pixmap = widget.grab()
        self.assertFalse(pixmap.isNull())


if __name__ == "__main__":
    unittest.main()
