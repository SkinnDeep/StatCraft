import os
import sys
import unittest

import numpy as np
from PySide6.QtWidgets import QApplication

from statcraft.app import Presenter, format_entry
from statcraft.model import Column, Worksheet


class Phase3EngineTests(unittest.TestCase):
    def test_resampling_bootstrap_and_randomization(self):
        from statcraft.resampling import (
            bootstrap_1sample,
            bootstrap_2sample,
            format_resampling_report,
            randomization_1sample,
            randomization_2sample,
        )

        x = [10.1, 10.4, 9.8, 10.2, 10.5, 9.9, 10.0, 10.3, 10.1, 10.2]
        y = [12.1, 12.4, 11.9, 12.2, 12.6, 12.0, 12.3, 12.5, 12.1, 12.4]

        b1 = bootstrap_1sample(x, statistic="Mean", n_resamples=800, confidence=0.95, seed=7)
        self.assertEqual(b1["analysis"], "bootstrap_1sample")
        self.assertLess(b1["ci_low"], b1["observed"])
        self.assertGreater(b1["ci_high"], b1["observed"])
        self.assertIn("Bootstrap", format_resampling_report(b1))

        b2 = bootstrap_2sample(x, y, statistic="Mean Difference", n_resamples=800, confidence=0.95, seed=7)
        self.assertEqual(b2["analysis"], "bootstrap_2sample")
        self.assertLess(b2["observed"], -1.5)
        self.assertLess(b2["ci_high"], -1.0)

        r1 = randomization_1sample(x, hypothesized_mean=8.0, n_resamples=800, seed=7)
        self.assertEqual(r1["analysis"], "randomization_1sample")
        self.assertLess(r1["p_value"], 0.01)

        r2 = randomization_2sample(x, y, n_resamples=800, seed=7)
        self.assertEqual(r2["analysis"], "randomization_2sample")
        self.assertLess(r2["p_value"], 0.01)

    def test_count_models_poisson_gof_and_nb2(self):
        from statcraft.count_models import (
            format_count_report,
            goodness_of_fit_poisson,
            negative_binomial_regression,
        )

        rng = np.random.default_rng(42)
        poisson_counts = rng.poisson(lam=3.0, size=120).tolist()
        gof_ok = goodness_of_fit_poisson(poisson_counts, variable_name="Defects")
        self.assertEqual(gof_ok["analysis"], "poisson_gof")
        self.assertGreater(gof_ok["p_value"], 0.05)
        self.assertIn("Poisson", format_count_report(gof_ok))

        overdispersed = ([0] * 40) + ([1] * 20) + ([2] * 10) + ([8] * 15) + ([14] * 15)
        gof_over = goodness_of_fit_poisson(overdispersed)
        self.assertGreater(gof_over["dispersion_ratio"], 2.0)
        self.assertLess(gof_over["p_value"], 0.01)

        n = 60
        x1 = np.linspace(0.0, 2.0, n)
        mu_true = np.exp(0.5 + 0.8 * x1)
        alpha_nb = 0.6
        rates = rng.gamma(1.0 / alpha_nb, alpha_nb * mu_true)
        y_nb = rng.poisson(rates)

        ws = Worksheet(
            columns=[
                Column("Counts", "number", y_nb.tolist()),
                Column("X1", "number", x1.tolist()),
                Column("Exposure", "number", [2.0] * n),
            ]
        )
        nb_res = negative_binomial_regression(ws, 0, [1], exposure_index=2)
        self.assertEqual(nb_res["analysis"], "negative_binomial_regression")
        self.assertGreater(nb_res["alpha"], 0.05)
        self.assertLess(nb_res["lr_dispersion_p"], 0.05)
        self.assertIn("Negative Binomial", format_count_report(nb_res))

    def test_extended_power_all_seven_calculators(self):
        from statcraft.power_extended import (
            equivalence_tost_power,
            format_power_extended_report,
            one_poisson_rate_power,
            one_variance_power,
            sample_size_estimation,
            sample_size_tolerance_interval,
            two_poisson_rates_power,
            two_variances_power,
        )

        ov_n = one_variance_power(ratio=1.5, target_power=0.80, alpha=0.05)
        self.assertGreater(ov_n["sample_size"], 10)
        ov_p = one_variance_power(ratio=1.5, sample_size=ov_n["sample_size"], target_power=None, alpha=0.05)
        self.assertGreaterEqual(ov_p["actual_power"], 0.79)
        self.assertIn("One Variance", format_power_extended_report(ov_n))

        tv_n = two_variances_power(ratio=1.8, target_power=0.80)
        self.assertGreater(tv_n["sample_size_per_group"], 10)
        self.assertGreaterEqual(tv_n["actual_power"], 0.80)

        p1 = one_poisson_rate_power(baseline_rate=2.0, comparison_rate=3.0, target_power=0.80)
        self.assertGreater(p1["sample_size"], 5)

        p2 = two_poisson_rates_power(rate1=4.0, rate2=2.0, target_power=0.85)
        self.assertGreater(p2["sample_size_per_group"], 3)

        eq = equivalence_tost_power(design="2-Sample", lower_limit=-1.0, upper_limit=1.0, difference=0.0, stdev=1.0, target_power=0.80)
        self.assertGreater(eq["sample_size"], 10)
        self.assertGreaterEqual(eq["actual_power"], 0.80)

        est_mean = sample_size_estimation(parameter="Mean (Normal)", planning_value=2.0, margin_of_error=0.5, confidence=0.95)
        self.assertGreater(est_mean["sample_size"], 50)
        est_prop = sample_size_estimation(parameter="Proportion (Binomial)", planning_value=0.5, margin_of_error=0.05, confidence=0.95)
        self.assertEqual(est_prop["sample_size"], 385)

        tol = sample_size_tolerance_interval(coverage=0.95, confidence=0.95, margin_ratio=1.25)
        self.assertGreater(tol["sample_size"], 20)

    def test_advanced_anova_balanced_nested_and_manova(self):
        from statcraft.advanced_anova import (
            balanced_anova,
            format_advanced_anova_report,
            fully_nested_anova,
            oneway_manova,
        )

        a = ["A1"] * 6 + ["A2"] * 6
        b = (["B1"] * 3 + ["B2"] * 3) * 2
        y = [10.0, 10.2, 9.8, 12.1, 11.9, 12.0, 15.0, 15.1, 14.9, 18.2, 17.8, 18.0]
        ws_bal = Worksheet(columns=[Column("Y", "number", y), Column("A", "text", a), Column("B", "text", b)])
        bal = balanced_anova(ws_bal, 0, [1, 2], include_interactions=True)
        self.assertEqual(bal["analysis"], "balanced_anova")
        self.assertGreater(bal["r_sq"], 0.95)
        self.assertIn("Balanced ANOVA", format_advanced_anova_report(bal))

        batch = ["M1"] * 4 + ["M2"] * 4 + ["M3"] * 4
        sample = ["S1", "S1", "S2", "S2"] * 3
        yn = [5.1, 4.9, 5.5, 5.4, 8.0, 8.2, 8.8, 8.7, 11.0, 11.2, 11.9, 12.1]
        ws_nest = Worksheet(columns=[Column("Y", "number", yn), Column("Batch", "text", batch), Column("Sample", "text", sample)])
        nest = fully_nested_anova(ws_nest, 0, [1, 2])
        self.assertEqual(nest["analysis"], "fully_nested_anova")
        pct_sum = sum(r["pct_total"] for r in nest["rows"]) + nest["error"]["pct_total"]
        self.assertAlmostEqual(pct_sum, 100.0, places=2)
        self.assertIn("Nested", format_advanced_anova_report(nest))

        grp = ["G1"] * 5 + ["G2"] * 5 + ["G3"] * 5
        y1 = [1.0, 1.1, 0.9, 1.2, 1.0, 5.0, 5.1, 4.9, 5.2, 5.0, 9.0, 9.1, 8.9, 9.2, 9.0]
        y2 = [2.0, 2.2, 1.9, 2.1, 2.0, 4.0, 3.8, 4.1, 3.9, 4.2, 6.0, 6.1, 5.9, 6.2, 6.0]
        ws_man = Worksheet(columns=[Column("Y1", "number", y1), Column("Y2", "number", y2), Column("Grp", "text", grp)])
        man = oneway_manova(ws_man, [0, 1], 2)
        self.assertEqual(man["analysis"], "oneway_manova")
        self.assertEqual(len(man["criteria"]), 4)
        self.assertLess(man["criteria"][0]["p_value"], 0.001)
        self.assertIn("Wilks", format_advanced_anova_report(man))

    def test_mixed_reml_converges_and_recovers_variance_components(self):
        from statcraft.mixed_reml import fit_mixed_reml, format_mixed_reml_report

        batch = ["B1"] * 4 + ["B2"] * 4 + ["B3"] * 4 + ["B4"] * 4
        x = [1, 2, 3, 4] * 4
        y = [
            10 + 2 * 1 + 0.1, 10 + 2 * 2 - 0.1, 10 + 2 * 3 + 0.05, 10 + 2 * 4 - 0.05,
            13 + 2 * 1 - 0.1, 13 + 2 * 2 + 0.1, 13 + 2 * 3 - 0.05, 13 + 2 * 4 + 0.05,
            7 + 2 * 1 + 0.08, 7 + 2 * 2 - 0.08, 7 + 2 * 3 + 0.02, 7 + 2 * 4 - 0.02,
            11 + 2 * 1 - 0.04, 11 + 2 * 2 + 0.04, 11 + 2 * 3 - 0.01, 11 + 2 * 4 + 0.01,
        ]
        ws = Worksheet(columns=[Column("Y", "number", y), Column("X", "number", x), Column("Batch", "text", batch)])
        reml = fit_mixed_reml(ws, 0, fixed_indices=[1], random_indices=[2])
        self.assertEqual(reml["analysis"], "mixed_reml")
        vc_map = {vc["source"]: vc["var_comp"] for vc in reml["variance_components"]}
        self.assertGreater(vc_map["Error"], 0.0)
        self.assertGreater(vc_map["Batch"], 1.0)
        x_coeff = next(row["coef"] for row in reml["fixed_effects"] if row["term"] == "X")
        self.assertAlmostEqual(x_coeff, 2.0, delta=0.1)
        self.assertEqual(len(reml["blups"]["Batch"]), 4)
        self.assertIn("REML", format_mixed_reml_report(reml))

    def test_survival_advanced_cox_ph_and_warranty(self):
        from statcraft.survival_advanced import (
            cox_ph_regression,
            format_survival_advanced_report,
            warranty_analysis,
        )

        t = [2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 20, 24]
        ev = [1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 0, 0]
        risk = [5.0, 4.5, 4.2, 3.8, 3.5, 3.0, 2.5, 2.2, 1.5, 1.8, 1.1, 0.9]
        ws = Worksheet(columns=[Column("Time", "number", t), Column("Event", "number", ev), Column("Risk", "number", risk)])
        cox = cox_ph_regression(ws, 0, 1, [2], event_value=1)
        self.assertEqual(cox["analysis"], "cox_ph_regression")
        self.assertGreater(cox["coefficients"][0]["hazard_ratio"], 1.5)
        self.assertGreater(cox["concordance"], 0.7)
        self.assertIn("Cox", format_survival_advanced_report(cox))

        warr = warranty_analysis([1, 2, 3, 6, 9, 12], [2, 3, 4, 7, 9, 12], at_risk_total=1000, forecast_horizon=24)
        self.assertEqual(warr["analysis"], "warranty_analysis")
        self.assertGreater(warr["weibull_shape"], 0.5)
        self.assertGreaterEqual(warr["forecasts"][-1]["expected_total_claims"], warr["observed_claims"])
        self.assertIn("Warranty", format_survival_advanced_report(warr))

    def test_six_sigma_process_and_product_rty(self):
        from statcraft.six_sigma import (
            format_six_sigma_report,
            rolled_throughput_yield,
            six_sigma_process_report,
        )

        vals = [10.0, 10.1, 9.9, 10.05, 9.95, 10.02, 9.98, 10.01, 9.99, 10.03] * 3
        proc = six_sigma_process_report(vals, lsl=9.5, usl=10.5, subgroup_size=3)
        self.assertEqual(proc["analysis"], "six_sigma_process_report")
        self.assertGreater(proc["cpk"], 1.5)
        self.assertGreater(proc["z_bench_st"], 4.0)
        self.assertIn("Six Sigma Process Report", format_six_sigma_report(proc))

        rty = rolled_throughput_yield([99.0, 98.0, 99.0], process_name="Widget Line")
        self.assertEqual(rty["analysis"], "six_sigma_product_report")
        self.assertAlmostEqual(rty["rty_pct"], 0.99 * 0.98 * 0.99 * 100.0, places=4)
        self.assertIn("Product", format_six_sigma_report(rty))


class Phase3PresenterAndUIIntegrationTests(unittest.TestCase):
    def test_presenter_methods_and_format_entry_end_to_end(self):
        ws = Worksheet(
            columns=[
                Column("Val1", "number", [10.1, 10.3, 9.9, 10.2, 10.4, 9.8, 10.1, 10.0]),
                Column("Val2", "number", [12.0, 12.2, 11.8, 12.1, 12.3, 11.9, 12.0, 12.4]),
                Column("Counts", "number", [1, 2, 0, 3, 1, 2, 4, 2]),
                Column("FacA", "text", ["A1", "A1", "A1", "A1", "A2", "A2", "A2", "A2"]),
                Column("FacB", "text", ["B1", "B1", "B2", "B2", "B1", "B1", "B2", "B2"]),
                Column("Time", "number", [2, 4, 6, 8, 10, 12, 15, 20]),
                Column("Event", "number", [1, 1, 1, 0, 1, 1, 0, 0]),
            ]
        )
        p = Presenter()
        p.worksheet = ws

        entries = [
            p.bootstrap_1sample(0, n_resamples=300),
            p.bootstrap_2sample(0, 1, n_resamples=300),
            p.randomization_1sample(0, hypothesized_mean=9.0, n_resamples=300),
            p.randomization_2sample(0, 1, n_resamples=300),
            p.goodness_of_fit_poisson(2),
            p.negative_binomial_regression(2, [0]),
            p.extended_power("one_variance", ratio=1.5, target_power=0.8),
            p.extended_power("two_variances", ratio=1.5, target_power=0.8),
            p.extended_power("one_poisson_rate", baseline_rate=2.0, comparison_rate=3.0, target_power=0.8),
            p.extended_power("two_poisson_rates", rate1=3.0, rate2=2.0, target_power=0.8),
            p.extended_power("equivalence_tost", target_power=0.8),
            p.extended_power("estimation", planning_value=1.0, margin_of_error=0.2),
            p.extended_power("tolerance_interval", coverage=0.95, confidence=0.95, margin_ratio=1.25),
            p.balanced_anova(0, [3, 4], include_interactions=True),
            p.fully_nested_anova(0, [3, 4]),
            p.oneway_manova([0, 1], 3),
            p.fit_mixed_reml(0, fixed_indices=[1], random_indices=[3]),
            p.cox_ph_regression(5, 6, [0], event_value=1),
            p.warranty_analysis(5, 2, at_risk_total=500, forecast_horizon=24),
            p.six_sigma_process_report(0, lsl=9.0, usl=11.0, subgroup_size=2),
            p.rolled_throughput_yield(step_yields=[99.0, 98.5, 99.2], process_name="Line 1"),
        ]
        for entry in entries:
            txt = format_entry(entry)
            self.assertTrue(len(txt.strip()) > 30, msg=f"Formatted entry too short: {entry['title']}")
        from statcraft import recipes
        replayed = recipes.run(p, entries[0]["recipe"])
        self.assertIn("Bootstrap", replayed["title"])

    def test_modern_window_has_all_phase3_menus_and_handlers(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication.instance() or QApplication(sys.argv)
        from statcraft.modern_app import ModernWindow

        win = ModernWindow(sandbox_mode=True)
        win.show()
        app.processEvents()

        expected_handlers = [
            "bootstrap_1sample_dialog",
            "bootstrap_2sample_dialog",
            "randomization_1sample_dialog",
            "randomization_2sample_dialog",
            "goodness_of_fit_poisson_dialog",
            "negative_binomial_regression_dialog",
            "balanced_anova_dialog",
            "fully_nested_anova_dialog",
            "oneway_manova_dialog",
            "mixed_reml_dialog",
            "cox_ph_dialog",
            "warranty_analysis_dialog",
            "six_sigma_process_dialog",
            "six_sigma_product_dialog",
            "one_variance_power_dialog",
            "two_variances_power_dialog",
            "one_poisson_rate_power_dialog",
            "two_poisson_rates_power_dialog",
            "equivalence_tost_power_dialog",
            "sample_size_estimation_dialog",
            "sample_size_tolerance_dialog",
        ]
        for name in expected_handlers:
            self.assertTrue(callable(getattr(win, name, None)), msg=f"Missing handler {name}")

        stat_menu = next(
            act.menu() for act in win.menuBar().actions() if act.menu() and act.text().replace("&", "") == "Stat"
        )
        labels = []

        def collect(menu):
            for a in menu.actions():
                if a.text():
                    labels.append(a.text().replace("&", ""))
                if a.menu():
                    collect(a.menu())

        collect(stat_menu)
        joined = "\n".join(labels)
        for needle in [
            "Resampling",
            "1-Sample Bootstrap",
            "Balanced ANOVA",
            "Fully Nested ANOVA",
            "General MANOVA (One-Way)",
            "Mixed Effects Model (REML)",
            "Fit Negative Binomial Model",
            "Goodness-of-Fit Test for Poisson",
            "Cox Proportional Hazards Regression",
            "Warranty Analysis",
            "Six Sigma Process Report",
            "Six Sigma Product Report (RTY)",
            "Sample Size for Estimation",
            "Sample Size for Tolerance Intervals",
        ]:
            self.assertIn(needle, joined)

        win.close()


if __name__ == "__main__":
    unittest.main()
