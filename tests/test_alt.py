"""Unit tests for Accelerated Life Testing (ALT) Maximum Likelihood Estimation engine."""
import math
import unittest
import numpy as np

from statcraft.alt_engine import fit_accelerated_life_test
from statcraft.alt_report import format_alt_report, get_alt_structured_tables


class TestAcceleratedLifeTesting(unittest.TestCase):
    def setUp(self):
        # Arrhenius simulation:
        # Temperatures: 60, 80, 100 °C
        # Normal operating condition: 25 °C
        np.random.seed(42)
        temps = [60.0] * 12 + [80.0] * 12 + [100.0] * 12
        x = 1000.0 / (np.array(temps) + 273.15)
        true_b0 = -9.0
        true_b1 = 4.5
        true_sigma = 0.5  # Weibull shape = 2.0
        mu = true_b0 + true_b1 * x

        # Gumbel random variates
        gumbel = np.random.gumbel(0, 1, len(x))
        log_t = mu + true_sigma * gumbel
        times = np.exp(log_t)

        # Right-censor items exceeding 1200 hours
        self.events = [1 if t <= 1200.0 else 0 for t in times]
        self.times = [min(float(t), 1200.0) for t in times]
        self.stresses = temps
        self.use_stress = 25.0

    def test_arrhenius_weibull_fit(self):
        res = fit_accelerated_life_test(
            times=self.times,
            events=self.events,
            stresses=self.stresses,
            model="arrhenius",
            distribution="weibull",
            use_stress=self.use_stress,
            percentiles=[1.0, 5.0, 10.0, 50.0],
            confidence=95.0,
        )

        self.assertEqual(res["analysis"], "accelerated_life_testing")
        self.assertEqual(res["model"], "arrhenius")
        self.assertEqual(res["distribution"], "weibull")
        self.assertEqual(res["n_total"], 36)
        self.assertGreater(res["n_failed"], 25)

        # Check positive slope b1 (higher 1000/T => lower temp => longer life)
        self.assertGreater(res["b1"], 2.0)
        self.assertLess(res["b1"], 7.0)

        # Check Weibull shape close to true 2.0
        self.assertGreater(res["shape"], 1.0)
        self.assertLess(res["shape"], 3.5)

        # Check percentiles at use stress (25 °C)
        pcts = res["percentiles"]
        self.assertEqual(len(pcts), 4)
        b10 = next(p for p in pcts if p["percentile"] == 10.0)
        b50 = next(p for p in pcts if p["percentile"] == 50.0)
        self.assertGreater(b50["estimate"], b10["estimate"])
        self.assertGreater(b10["estimate"], 0.0)
        self.assertLess(b10["ci_lower"], b10["estimate"])
        self.assertGreater(b10["ci_upper"], b10["estimate"])

        # Check acceleration factors
        afs = res["acceleration_factors"]
        self.assertTrue(len(afs) >= 3)
        # Acceleration factor at 100 °C must be significantly higher than at 60 °C
        af_60 = next(a["acceleration_factor"] for a in afs if a["stress"] == 60.0)
        af_100 = next(a["acceleration_factor"] for a in afs if a["stress"] == 100.0)
        self.assertGreater(af_100, af_60)

    def test_inverse_power_law_lognormal_fit(self):
        # Inverse power law with voltages: 5V, 10V, 15V
        np.random.seed(99)
        voltages = [5.0] * 10 + [10.0] * 10 + [15.0] * 10
        x = np.log(voltages)
        # Higher voltage => shorter life => negative b1
        mu = 8.0 - 2.0 * x
        times = np.exp(np.random.normal(mu, 0.4))
        events = [1] * len(times)

        res = fit_accelerated_life_test(
            times=times,
            events=events,
            stresses=voltages,
            model="inverse_power",
            distribution="lognormal",
            use_stress=3.3,
        )
        self.assertEqual(res["model"], "inverse_power")
        self.assertEqual(res["distribution"], "lognormal")
        self.assertLess(res["b1"], -1.0)
        self.assertGreater(res["log_likelihood"], -500.0)

    def test_report_formatting_and_cards(self):
        res = fit_accelerated_life_test(
            times=self.times,
            events=self.events,
            stresses=self.stresses,
            model="arrhenius",
            distribution="weibull",
            use_stress=self.use_stress,
        )
        res["time_name"] = "Hours"
        res["stress_name"] = "Temp_C"

        text = format_alt_report({"result": res})
        self.assertIn("Accelerated Life Testing", text)
        self.assertIn("Arrhenius", text)
        self.assertIn("Weibull", text)
        self.assertIn("Parameter Estimates", text)
        self.assertIn("Table of Percentiles", text)

        tables = get_alt_structured_tables(res)
        self.assertTrue(len(tables) >= 3)
        titles = [t["title"] for t in tables]
        self.assertTrue(any("Model Summary" in title for title in titles))
        self.assertTrue(any("Parameter Estimates" in title for title in titles))
        self.assertTrue(any("Percentiles" in title for title in titles))


if __name__ == "__main__":
    unittest.main()
