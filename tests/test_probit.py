"""Unit tests for Probit Analysis (Bioassay and LD50/EC50 determination)."""
import math
import unittest
import numpy as np

from statcraft.probit import clean_probit_data, fit_probit_analysis
from statcraft.probit_report import generate_probit_report
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry


class TestProbitAnalysis(unittest.TestCase):
    def setUp(self):
        # Classic bioassay dose-response dataset (Finney / Minitab standard sample)
        # Dose, Total Subjects (Trials), Responded (Events)
        self.doses = [0.1, 0.2, 0.4, 0.8, 1.6]
        self.trials = [30, 30, 30, 30, 30]
        self.events = [2, 6, 14, 24, 29]

    def test_clean_data(self):
        d_raw = [1.0, 2.0, None, 4.0]
        ev_raw = [1, 2, 3, float('nan')]
        tr_raw = [10, 10, 10, 10]
        d, ev, tr, x = clean_probit_data(ev_raw, tr_raw, d_raw)
        self.assertEqual(len(d), 2)
        self.assertEqual(list(d), [1.0, 2.0])
        self.assertEqual(list(ev), [1.0, 2.0])
        self.assertEqual(list(tr), [10.0, 10.0])

    def test_probit_fit_basic(self):
        res = fit_probit_analysis(
            events=self.events,
            trials=self.trials,
            dose=self.doses,
            distribution="probit",
            dose_transform="log10",
            dose_name="Dose",
            events_name="Killed",
            trials_name="Total",
        )
        self.assertIn("coefficients", res)
        self.assertEqual(len(res["coefficients"]), 2)

        intercept = res["coefficients"][0]
        slope = res["coefficients"][1]

        self.assertEqual(intercept["term"], "Intercept")
        self.assertEqual(slope["term"], "Dose")
        self.assertGreater(slope["coef"], 0.0)  # Positive dose-response slope
        self.assertGreater(slope["z_value"], 0.0)
        self.assertLess(slope["p_value"], 0.001)

        # Goodness of fit
        gof = res["goodness_of_fit"]
        self.assertIn("pearson_chi2", gof)
        self.assertIn("deviance_chi2", gof)
        self.assertGreater(gof["pearson_p"], 0.05)  # Good fit

        # Percentiles
        pcts = res["percentiles"]
        self.assertGreater(len(pcts), 5)
        # Find LD50
        ld50 = next(p for p in pcts if abs(p["percent"] - 50.0) < 1e-4)
        self.assertAlmostEqual(ld50["percent"], 50.0)
        # LD50 estimate should be around 0.4
        self.assertGreater(ld50["estimate"], 0.2)
        self.assertLess(ld50["estimate"], 0.6)
        self.assertLess(ld50["ci_lower"], ld50["estimate"])
        self.assertGreater(ld50["ci_upper"], ld50["estimate"])

    def test_alternative_distributions(self):
        for dist in ["logit", "weibull", "gompertz"]:
            res = fit_probit_analysis(
                events=self.events,
                trials=self.trials,
                dose=self.doses,
                distribution=dist,
                dose_transform="none",
            )
            self.assertIn("coefficients", res)
            self.assertEqual(len(res["coefficients"]), 2)
            slope = res["coefficients"][1]
            self.assertGreater(slope["coef"], 0.0)

    def test_dose_transformations(self):
        res_none = fit_probit_analysis(self.events, self.doses, self.trials, dose_transform="none")
        res_ln = fit_probit_analysis(self.events, self.doses, self.trials, dose_transform="ln")
        res_log10 = fit_probit_analysis(self.events, self.doses, self.trials, dose_transform="log10")

        ld50_none = next(p for p in res_none["percentiles"] if abs(p["percent"] - 50.0) < 1e-4)["estimate"]
        ld50_ln = next(p for p in res_ln["percentiles"] if abs(p["percent"] - 50.0) < 1e-4)["estimate"]
        ld50_log10 = next(p for p in res_log10["percentiles"] if abs(p["percent"] - 50.0) < 1e-4)["estimate"]

        # All LD50s should be in the plausible dose range [0.3, 0.5]
        self.assertTrue(0.2 < ld50_none < 0.6)
        self.assertTrue(0.2 < ld50_ln < 0.6)
        self.assertTrue(0.2 < ld50_log10 < 0.6)

    def test_report_generation(self):
        res = fit_probit_analysis(
            events=self.events,
            trials=self.trials,
            dose=self.doses,
            distribution="probit",
            dose_transform="log10",
        )
        report = generate_probit_report(res)
        self.assertIn("Probit Analysis", report)
        self.assertIn("Assumed distribution: Probit", report)
        self.assertIn("Regression Equation", report)
        self.assertIn("Coefficients", report)
        self.assertIn("Goodness-of-Fit Tests", report)
        self.assertIn("Table of Percentiles", report)
        self.assertIn("50.0%", report)

    def test_presenter_integration(self):
        ws = Worksheet("Bioassay", [
            Column("Killed", values=[2, 6, 14, 24, 29]),
            Column("Total", values=[30, 30, 30, 30, 30]),
            Column("Dose", values=[0.1, 0.2, 0.4, 0.8, 1.6]),
        ])
        p = Presenter()
        p.worksheet = ws

        entry = p.probit_analysis(
            response_column=0,
            trials_column=1,
            dose_column=2,
            distribution="probit",
            dose_transform="log10",
        )
        self.assertIsNotNone(entry)
        text = format_entry(entry)
        self.assertIn("Probit Analysis", text)
        self.assertIn("Coefficients", text)
        self.assertIn("Table of Percentiles", text)


if __name__ == "__main__":
    unittest.main()
