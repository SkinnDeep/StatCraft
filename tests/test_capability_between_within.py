"""Unit and integration tests for Between/Within Capability Analysis."""

import unittest
import numpy as np

from statcraft.capability_engine import run_normal_capability
from statcraft.capability_report import format_capability_report
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry
from statcraft.recipes import run as rerun_recipe


class TestCapabilityBetweenWithinEngine(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        # 10 subgroups of size 5: mean varies by subgroup
        self.data = []
        self.subgroups = []
        for i in range(10):
            group_mean = 10.0 + np.random.normal(0, 0.5)
            for j in range(5):
                self.data.append(group_mean + np.random.normal(0, 0.2))
                self.subgroups.append(i + 1)
        self.lsl = 8.0
        self.usl = 12.0

    def test_between_within_decomposition(self):
        res = run_normal_capability(
            data=self.data,
            subgroup_spec=5,
            lsl=self.lsl,
            usl=self.usl,
            analysis_mode="between_within",
        )
        self.assertEqual(res["analysis_mode"], "between_within")
        self.assertEqual(res["sample_n"], 50)
        self.assertEqual(res["subgroup_count"], 10)
        self.assertIsNotNone(res["stdev_between"])
        self.assertIsNotNone(res["stdev_between_within"])
        self.assertIsNotNone(res["stdev_within"])
        self.assertIsNotNone(res["stdev_overall"])

        # stdev_between_within should be >= stdev_within
        self.assertGreaterEqual(res["stdev_between_within"], res["stdev_within"] * 0.99)
        # Cp based on between_within stdev
        expected_cp = (self.usl - self.lsl) / (6.0 * res["stdev_between_within"])
        self.assertAlmostEqual(res["cp"], expected_cp, places=5)

    def test_between_within_subgroup_indicator_column(self):
        res = run_normal_capability(
            data=self.data,
            subgroup_spec=self.subgroups,
            lsl=self.lsl,
            usl=self.usl,
            analysis_mode="between_within",
        )
        self.assertEqual(res["analysis_mode"], "between_within")
        self.assertEqual(res["subgroup_count"], 10)
        self.assertIsNotNone(res["stdev_between_within"])

    def test_between_within_subgroup_across_rows(self):
        # 10 rows, 5 columns
        matrix = []
        for i in range(10):
            matrix.append(self.data[i*5:(i+1)*5])
        res = run_normal_capability(
            data=matrix,
            subgroup_spec=1,
            lsl=self.lsl,
            usl=self.usl,
            analysis_mode="between_within",
        )
        self.assertEqual(res["analysis_mode"], "between_within")
        self.assertEqual(res["subgroup_count"], 10)
        self.assertAlmostEqual(res["subgroup_avg_size"], 5.0)

    def test_between_within_rejects_subgroup_size_one(self):
        with self.assertRaises(ValueError):
            run_normal_capability(
                data=self.data,
                subgroup_spec=1,
                lsl=self.lsl,
                usl=self.usl,
                analysis_mode="between_within",
            )

    def test_between_within_unbalanced_subgroups(self):
        # Create unbalanced subgroups: groups of sizes 3, 4, 5, 6
        unbalanced_data = []
        unbalanced_sub = []
        sizes = [3, 4, 5, 6, 4]
        for g_idx, sz in enumerate(sizes):
            gm = 15.0 + g_idx * 0.2
            for _ in range(sz):
                unbalanced_data.append(gm + np.random.normal(0, 0.1))
                unbalanced_sub.append(g_idx + 1)

        res = run_normal_capability(
            data=unbalanced_data,
            subgroup_spec=unbalanced_sub,
            lsl=12.0,
            usl=18.0,
            analysis_mode="between_within",
        )
        self.assertEqual(res["analysis_mode"], "between_within")
        self.assertEqual(res["subgroup_count"], 5)
        self.assertGreater(res["stdev_between"], 0.0)
        self.assertGreater(res["stdev_between_within"], 0.0)


class TestCapabilityBetweenWithinReport(unittest.TestCase):
    def test_report_formatting(self):
        np.random.seed(123)
        data = np.random.normal(20.0, 1.0, 60).tolist()
        res = run_normal_capability(
            data=data,
            subgroup_spec=5,
            lsl=17.0,
            usl=23.0,
            analysis_mode="between_within",
            variable_name="Width",
        )
        rep = format_capability_report(res)
        self.assertIn("Between/Within Capability Report for Width", rep)
        self.assertIn("StDev(Between/Within)", rep)
        self.assertIn("StDev(Between)", rep)
        self.assertIn("StDev(Within)", rep)
        self.assertIn("StDev(Overall)", rep)
        self.assertIn("Potential (Between/Within) Capability", rep)
        self.assertIn("Exp. \"Between/Within\"", rep)


class TestCapabilityBetweenWithinAppWorkflow(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        measurements = np.random.normal(50.0, 2.0, 40).tolist()
        batches = [i // 4 + 1 for i in range(40)]
        self.p = Presenter()
        self.p.worksheet = Worksheet("BatchStudy", [
            Column("Strength", "number", measurements),
            Column("Batch", "number", batches),
        ])

    def test_presenter_bw_capability_and_rerun(self):
        settings = {
            "analysis_mode": "between_within",
            "single_column": True,
            "column_name": "Strength",
            "subgroup_spec": "Batch",
            "lsl": 45.0,
            "usl": 55.0,
            "options": {"target": 50.0},
        }
        entry = self.p.normal_capability(settings=settings)
        self.assertIn("Between/Within Capability", entry["title"])
        res = entry["result"]
        self.assertEqual(res["analysis_mode"], "between_within")
        self.assertIn("stdev_between_within", res)

        # Report format check via app format_entry
        text_rep = format_entry(entry)
        self.assertIn("Between/Within Capability", text_rep)
        self.assertIn("StDev(Between/Within)", text_rep)

        # Recipe re-run check
        recipe = entry["recipe"]
        rerun_entry = rerun_recipe(self.p, recipe)
        self.assertIsNotNone(rerun_entry)
        self.assertEqual(rerun_entry["result"]["analysis_mode"], "between_within")
        self.assertAlmostEqual(rerun_entry["result"]["cp"], res["cp"], places=5)
