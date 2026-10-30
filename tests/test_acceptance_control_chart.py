"""Unit and integration tests for Acceptance Control Charts (AIAG/VDA SPC)."""

import math
import unittest
import numpy as np
from scipy.stats import norm

from statcraft.acceptance_chart_engine import run_acceptance_control_chart
from statcraft.acceptance_chart_report import format_acceptance_chart_report
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft.recipes import run as rerun_recipe


class TestAcceptanceChartEngine(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        # 20 subgroups of size 5 from N(50, 1.0)
        # Spec limits: LSL = 40, USL = 60 (high capability Cp = (60-40)/6 = 3.33)
        self.data = np.random.normal(50.0, 1.0, 100).tolist()
        self.subgroups = [i // 5 + 1 for i in range(100)]
        self.lsl = 40.0
        self.usl = 60.0

    def test_acceptance_limits_calculation(self):
        delta = 0.001
        alpha = 0.05
        res = run_acceptance_control_chart(
            data=self.data,
            subgroup_spec=5,
            lsl=self.lsl,
            usl=self.usl,
            delta=delta,
            alpha=alpha,
            historical_stdev=1.0,
        )
        self.assertEqual(res["sample_n"], 100)
        self.assertEqual(res["subgroup_count"], 20)
        self.assertEqual(res["stdev"], 1.0)
        self.assertAlmostEqual(res["center_line"], 50.0, places=4)

        z_delta = norm.ppf(1.0 - delta)
        z_alpha = norm.ppf(1.0 - alpha)
        expected_offset = (z_delta + z_alpha / math.sqrt(5)) * 1.0
        expected_uacl = 60.0 - expected_offset
        expected_lacl = 40.0 + expected_offset

        self.assertAlmostEqual(res["uacl"], expected_uacl, places=4)
        self.assertAlmostEqual(res["lacl"], expected_lacl, places=4)
        self.assertAlmostEqual(res["apl_upper"], 60.0 - z_delta * 1.0, places=4)
        self.assertAlmostEqual(res["apl_lower"], 40.0 + z_delta * 1.0, places=4)
        self.assertGreater(res["cp"], 2.0)

    def test_one_sided_upper_spec(self):
        res = run_acceptance_control_chart(
            data=self.data,
            subgroup_spec=5,
            usl=55.0,
            delta=0.001,
            alpha=0.05,
            historical_stdev=1.0,
        )
        self.assertIsNotNone(res["uacl"])
        self.assertIsNotNone(res["apl_upper"])
        self.assertIsNone(res["lacl"])
        self.assertIsNone(res["apl_lower"])

    def test_one_sided_lower_spec(self):
        res = run_acceptance_control_chart(
            data=self.data,
            subgroup_spec=5,
            lsl=45.0,
            delta=0.001,
            alpha=0.05,
            historical_stdev=1.0,
        )
        self.assertIsNone(res["uacl"])
        self.assertIsNone(res["apl_upper"])
        self.assertIsNotNone(res["lacl"])
        self.assertIsNotNone(res["apl_lower"])

    def test_insufficient_capability_error(self):
        # Narrow specs: LSL = 49, USL = 51 -> Cp = 2 / 6 = 0.33, insufficient for ACC
        with self.assertRaises(ValueError) as ctx:
            run_acceptance_control_chart(
                data=self.data,
                subgroup_spec=5,
                lsl=49.0,
                usl=51.0,
                delta=0.001,
                alpha=0.05,
                historical_stdev=1.0,
            )
        self.assertIn("too narrow", str(ctx.exception))

    def test_test1_signal_detection(self):
        # Insert out of acceptance limit subgroup
        modified_data = list(self.data)
        # Subgroup 1 gets mean shifted above UACL
        for i in range(5):
            modified_data[i] = 59.5  # UACL is ~56.17
        res = run_acceptance_control_chart(
            data=modified_data,
            subgroup_spec=5,
            lsl=self.lsl,
            usl=self.usl,
            historical_stdev=1.0,
        )
        self.assertIn(1, res["test1_signals"])


class TestAcceptanceChartReport(unittest.TestCase):
    def test_report_formatting(self):
        np.random.seed(123)
        data = np.random.normal(100.0, 2.0, 50).tolist()
        res = run_acceptance_control_chart(
            data=data,
            subgroup_spec=5,
            lsl=80.0,
            usl=120.0,
            variable_name="Diameter",
        )
        rep = format_acceptance_chart_report(res)
        self.assertIn("Acceptance Control Chart for Diameter", rep)
        self.assertIn("Process Parameters", rep)
        self.assertIn("Acceptance Control Limits", rep)
        self.assertIn("UACL", rep)
        self.assertIn("LACL", rep)
        self.assertIn("Test Results for Acceptance Control Chart", rep)


class TestAcceptanceChartAppWorkflow(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        measurements = np.random.normal(75.0, 1.5, 50).tolist()
        batches = [i // 5 + 1 for i in range(50)]
        self.p = Presenter()
        self.p.worksheet = Worksheet("ProductionLot", [
            Column("Dimension", "number", measurements),
            Column("Lot", "number", batches),
        ])

    def test_presenter_workflow_and_rerun(self):
        settings = {
            "single_column": True,
            "column_name": "Dimension",
            "subgroup_spec": "Lot",
            "lsl": 65.0,
            "usl": 85.0,
            "delta": 0.001,
            "alpha": 0.05,
            "options": {"target": 75.0},
        }
        entry = self.p.acceptance_control_chart(settings=settings)
        self.assertIn("Acceptance Control Chart", entry["title"])
        res = entry["result"]
        self.assertEqual(res["analysis"], "acceptance_control")
        self.assertIsNotNone(res["uacl"])
        self.assertIsNotNone(res["lacl"])

        # Format report
        rep = format_entry(entry)
        self.assertIn("Acceptance Control Chart", rep)
        self.assertIn("UACL", rep)

        # Rerun recipe
        rerun_res = rerun_recipe(self.p, entry["recipe"])
        self.assertIsNotNone(rerun_res)
        self.assertEqual(rerun_res["result"]["analysis"], "acceptance_control")
        self.assertAlmostEqual(rerun_res["result"]["uacl"], res["uacl"], places=5)
