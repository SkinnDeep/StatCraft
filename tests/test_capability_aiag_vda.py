"""Tests for AIAG/VDA Standardized Capability Nomenclature and Machine Capability (Preview 72)."""

import math
import os
import tempfile
import unittest
import numpy as np

from statcraft.capability_engine import run_normal_capability
from statcraft.capability_report import format_capability_report
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft.recipes import run as run_recipe


class TestCapabilityAiagVda(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        # 50 parts from a CNC machine: N(50.0, 0.8)
        self.machine_data = [round(x, 3) for x in np.random.normal(50.0, 0.8, 50)]

        # 20 subgroups of size 5: N(100.0, 1.0) with batch variance
        subgroups = []
        measurements = []
        for g in range(20):
            batch_eff = np.random.normal(0, 0.5)
            for _ in range(5):
                measurements.append(round(100.0 + batch_eff + np.random.normal(0, 0.7), 3))
                subgroups.append(g + 1)
        self.bw_obs = measurements
        self.bw_subs = subgroups

    def test_machine_capability_calculation(self):
        """Test Machine Capability index (Cm, Cmk) calculation using within-sample variation."""
        res = run_normal_capability(
            data=self.machine_data,
            subgroup_spec=1,
            lsl=46.0,
            usl=54.0,
            target=50.0,
            study_type="machine",
            naming_convention="aiag_vda",
            include_ci=True
        )

        self.assertEqual(res["study_type"], "machine")
        self.assertEqual(res["naming_convention"], "aiag_vda")
        self.assertIsNotNone(res["cm"])
        self.assertIsNotNone(res["cmk"])
        self.assertIsNotNone(res["cml"])
        self.assertIsNotNone(res["cmu"])

        sd_within = res["stdev_within"]
        mean = res["mean"]
        expected_cm = (54.0 - 46.0) / (6.0 * sd_within)
        expected_cml = (mean - 46.0) / (3.0 * sd_within)
        expected_cmu = (54.0 - mean) / (3.0 * sd_within)
        expected_cmk = min(expected_cml, expected_cmu)

        self.assertAlmostEqual(res["cm"], expected_cm, places=5)
        self.assertAlmostEqual(res["cmk"], expected_cmk, places=5)
        self.assertAlmostEqual(res["cml"], expected_cml, places=5)
        self.assertAlmostEqual(res["cmu"], expected_cmu, places=5)

        # Confidence intervals
        self.assertIsNotNone(res["ci_cm"])
        self.assertIsNotNone(res["ci_cmk"])
        self.assertLess(res["ci_cm"][0], res["cm"])
        self.assertGreater(res["ci_cm"][1], res["cm"])

    def test_between_within_aiag_vda_nomenclature(self):
        """Test Between/Within capability with AIAG/VDA standard nomenclature (Cbw, Cbwk)."""
        res = run_normal_capability(
            data=self.bw_obs,
            subgroup_spec=self.bw_subs,
            lsl=96.0,
            usl=104.0,
            analysis_mode="between_within",
            naming_convention="aiag_vda",
            include_ci=True
        )

        self.assertEqual(res["analysis_mode"], "between_within")
        self.assertEqual(res["naming_convention"], "aiag_vda")
        self.assertIsNotNone(res["cbw"])
        self.assertIsNotNone(res["cbwk"])
        self.assertIsNotNone(res["cbwl"])
        self.assertIsNotNone(res["cbwu"])

        sd_bw = res["stdev_between_within"]
        mean = res["mean"]
        expected_cbw = (104.0 - 96.0) / (6.0 * sd_bw)
        expected_cbwl = (mean - 96.0) / (3.0 * sd_bw)
        expected_cbwu = (104.0 - mean) / (3.0 * sd_bw)
        expected_cbwk = min(expected_cbwl, expected_cbwu)

        self.assertAlmostEqual(res["cbw"], expected_cbw, places=5)
        self.assertAlmostEqual(res["cbwk"], expected_cbwk, places=5)
        self.assertAlmostEqual(res["cbwl"], expected_cbwl, places=5)
        self.assertAlmostEqual(res["cbwu"], expected_cbwu, places=5)

    def test_capability_report_formatting(self):
        """Verify report text formatting contains proper AIAG/VDA headings and symbols."""
        # 1. Machine report
        res_m = run_normal_capability(
            data=self.machine_data,
            subgroup_spec=1,
            lsl=46.0,
            usl=54.0,
            study_type="machine",
            naming_convention="aiag_vda",
            include_ci=True
        )
        rep_m = format_capability_report(res_m)
        self.assertIn("Machine Capability", rep_m)
        self.assertIn("Cm", rep_m)
        self.assertIn("Cmk", rep_m)
        self.assertIn("Overall Capability", rep_m)
        self.assertIn("Pp", rep_m)
        self.assertIn("Ppk", rep_m)

        # 2. Between/Within AIAG/VDA report
        res_bw = run_normal_capability(
            data=self.bw_obs,
            subgroup_spec=self.bw_subs,
            lsl=96.0,
            usl=104.0,
            analysis_mode="between_within",
            naming_convention="aiag_vda",
            include_ci=True
        )
        rep_bw = format_capability_report(res_bw)
        self.assertIn("Between/Within Capability (AIAG/VDA)", rep_bw)
        self.assertIn("Cbw", rep_bw)
        self.assertIn("Cbwk", rep_bw)
        self.assertIn("StDev(Between/Within)", rep_bw)

    def test_presenter_machine_capability_and_mpx(self):
        """Verify Presenter machine capability execution and MPX persistence."""
        p = Presenter()
        p.worksheet = Worksheet("Milling", [
            Column("Diameter", "number", self.machine_data)
        ])

        settings = {
            "single_column": True,
            "column_name": "Diameter",
            "subgroup_spec": 1,
            "lsl": 46.0,
            "usl": 54.0,
            "study_type": "machine",
            "options": {
                "naming_convention": "aiag_vda",
                "study_type": "machine",
                "include_ci": True,
                "target": 50.0
            }
        }

        entry = p.machine_capability(settings=settings)
        self.assertIsNotNone(entry)
        self.assertIn("Machine Capability", entry["title"])
        res = entry["result"]
        self.assertEqual(res.get("study_type"), "machine")
        self.assertIsNotNone(res.get("cm"))
        self.assertIsNotNone(res.get("cmk"))

        with tempfile.TemporaryDirectory() as td:
            mpx_file = os.path.join(td, "machine_capa.mpx")
            p.save(mpx_file)
            self.assertTrue(os.path.exists(mpx_file))

            p2 = Presenter()
            p2.load(mpx_file)
            self.assertEqual(len(p2.history), 1)
            loaded_entry = p2.history[0]
            self.assertIn("Machine Capability", loaded_entry["title"])
            self.assertEqual(loaded_entry["result"].get("study_type"), "machine")

            # Rerun recipe
            rerun_entry = run_recipe(p2, loaded_entry["recipe"])
            self.assertIsNotNone(rerun_entry)
            self.assertEqual(rerun_entry["result"].get("study_type"), "machine")
            self.assertAlmostEqual(rerun_entry["result"]["cm"], res["cm"])


if __name__ == "__main__":
    unittest.main()
