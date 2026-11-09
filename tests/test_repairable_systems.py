"""Unit tests for Repairable Systems Analysis (Nonparametric MCF and Parametric Growth Curve)."""
import unittest
import numpy as np

from statcraft.repairable_systems import (
    clean_repairable_data,
    fit_nonparametric_mcf,
    fit_parametric_growth_curve,
)
from statcraft.repairable_systems_report import generate_repairable_systems_report
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry


class TestRepairableSystems(unittest.TestCase):
    def setUp(self):
        # Classic Nelson / Minitab sample data for 3 locomotive engines (systems)
        # System, Time, Event (1=repair, 0=censored end of observation)
        self.systems = [
            "Engine1", "Engine1", "Engine1", "Engine1",
            "Engine2", "Engine2", "Engine2", "Engine2",
            "Engine3", "Engine3", "Engine3",
        ]
        self.times = [
            25.0, 48.0, 85.0, 100.0,
            18.0, 60.0, 92.0, 100.0,
            33.0, 71.0, 95.0,
        ]
        self.events = [
            1, 1, 1, 0,  # Engine1 has 3 repairs, censored at 100
            1, 1, 1, 0,  # Engine2 has 3 repairs, censored at 100
            1, 1, 0,     # Engine3 has 2 repairs, censored at 95
        ]

    def test_clean_data(self):
        sys_raw = ["A", None, "B", "B"]
        t_raw = [10.0, 20.0, None, 30.0]
        ev_raw = [1, 1, 1, 0]
        s, t, ev, c = clean_repairable_data(sys_raw, t_raw, ev_raw)
        self.assertEqual(len(s), 2)
        self.assertEqual(list(s), ["A", "B"])
        self.assertEqual(list(t), [10.0, 30.0])
        self.assertEqual(list(ev), [1, 0])

    def test_nonparametric_mcf_basic(self):
        res = fit_nonparametric_mcf(
            system=self.systems,
            time=self.times,
            event=self.events,
            system_name="Engine",
            time_name="Hours",
        )
        self.assertEqual(res["analysis"], "nonparametric_growth_curve")
        self.assertEqual(res["n_systems"], 3)
        self.assertEqual(res["total_events"], 8)

        table = res["mcf_table"]
        self.assertGreater(len(table), 5)

        # First event is at 18.0 (Engine2). All 3 engines at risk.
        first_row = table[0]
        self.assertAlmostEqual(first_row["time"], 18.0)
        self.assertEqual(first_row["at_risk"], 3)
        self.assertAlmostEqual(first_row["mcf"], 1.0 / 3.0)
        self.assertGreater(first_row["se"], 0.0)
        self.assertLessEqual(first_row["ci_lower"], first_row["mcf"])
        self.assertGreaterEqual(first_row["ci_upper"], first_row["mcf"])

        # MCF should be monotonically non-decreasing
        mcfs = [r["mcf"] for r in table]
        for i in range(1, len(mcfs)):
            self.assertGreaterEqual(mcfs[i], mcfs[i - 1])

    def test_parametric_growth_curve_basic(self):
        res = fit_parametric_growth_curve(
            system=self.systems,
            time=self.times,
            event=self.events,
            system_name="Engine",
            time_name="Hours",
        )
        self.assertEqual(res["analysis"], "parametric_growth_curve")
        self.assertEqual(res["n_systems"], 3)
        self.assertEqual(res["total_events"], 8)

        # Parameters
        p = res["parameters"]
        self.assertIn("shape_beta_mle", p)
        self.assertIn("scale_lambda_mle", p)
        self.assertGreater(p["shape_beta_mle"], 0.0)
        self.assertGreater(p["scale_lambda_mle"], 0.0)
        self.assertGreater(p["se_beta"], 0.0)

        # Trend tests
        tt = res["trend_tests"]
        self.assertIn("mil_hdbk_stat", tt)
        self.assertIn("mil_hdbk_p", tt)
        self.assertIn("laplace_z", tt)
        self.assertIn("laplace_p", tt)
        self.assertIn("trend_description", tt)

        # Predictions / Horizons Table
        preds = res["predictions"]
        self.assertGreaterEqual(len(preds), 4)
        for row in preds:
            self.assertGreater(row["time"], 0.0)
            self.assertGreater(row["cumulative_events"], 0.0)
            self.assertGreater(row["failure_rate"], 0.0)
            self.assertGreater(row["mtbf"], 0.0)

    def test_report_generation(self):
        res_mcf = fit_nonparametric_mcf(self.systems, self.times, self.events)
        rep_mcf = generate_repairable_systems_report(res_mcf)
        self.assertIn("Nonparametric Growth Curve (MCF)", rep_mcf)
        self.assertIn("Mean Cumulative Function (MCF) Table", rep_mcf)
        self.assertIn("Number of Systems: 3", rep_mcf)

        res_param = fit_parametric_growth_curve(self.systems, self.times, self.events)
        rep_param = generate_repairable_systems_report(res_param)
        self.assertIn("Parametric Growth Curve (Power Law / Crow-AMSAA)", rep_param)
        self.assertIn("Parameter Estimates", rep_param)
        self.assertIn("Shape (beta, MLE)", rep_param)
        self.assertIn("Tests for Constant Failure Rate", rep_param)
        self.assertIn("MIL-HDBK-189", rep_param)
        self.assertIn("MTBF Horizons", rep_param)

    def test_presenter_integration(self):
        ws = Worksheet("Reliability", [
            Column("System", kind="text", values=self.systems),
            Column("Time", values=self.times),
            Column("Event", values=self.events),
        ])
        p = Presenter()
        p.worksheet = ws

        # 1. Nonparametric
        entry_np = p.nonparametric_growth_curve(time_column=1, system_column=0, event_column=2)
        self.assertIsNotNone(entry_np)
        self.assertEqual(entry_np["recipe"]["action"], "nonparametric_growth_curve")
        text_np = format_entry(entry_np)
        self.assertIn("Nonparametric Growth Curve (MCF)", text_np)
        self.assertIn("Mean Cumulative Function (MCF) Table", text_np)

        # 2. Parametric
        entry_param = p.parametric_growth_curve(time_column=1, system_column=0, event_column=2)
        self.assertIsNotNone(entry_param)
        self.assertEqual(entry_param["recipe"]["action"], "parametric_growth_curve")
        text_param = format_entry(entry_param)
        self.assertIn("Parametric Growth Curve", text_param)
        self.assertIn("Shape (beta, MLE)", text_param)
        self.assertIn("MTBF Horizons", text_param)


if __name__ == "__main__":
    unittest.main()
