"""Unit tests for Capability Sixpack Extensions: Between/Within and Nonnormal."""
import unittest
import numpy as np

from statcraft.sixpack_engine import run_normal_sixpack, run_nonnormal_sixpack
from statcraft.sixpack_report import format_sixpack_report
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry


class TestCapabilitySixpackExtensions(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        # Normal data with subgroups of size 5
        self.normal_data = []
        for i in range(20):
            batch_shift = np.random.normal(0, 0.5)
            self.normal_data.extend(np.random.normal(10.0 + batch_shift, 1.0, 5).tolist())

        # Nonnormal data (Weibull with shape 2, scale 10)
        self.weibull_data = (10.0 * np.random.weibull(2.0, 100)).tolist()

    def test_between_within_sixpack_engine(self):
        settings = {
            "data_mode": "single_column",
            "column_name": "Length",
            "column_data": self.normal_data,
            "subgroup_type": "size",
            "subgroup_size": 5,
            "lsl": 7.0,
            "usl": 13.0,
            "target": 10.0,
            "analysis_mode": "between_within",
            "options": {"analysis_mode": "between_within"},
        }
        res = run_normal_sixpack(settings)
        self.assertEqual(res["analysis"], "capability_sixpack_between_within")
        self.assertEqual(res["analysis_mode"], "between_within")
        self.assertIsNotNone(res["stdev_between_within"])
        self.assertGreater(res["stdev_between_within"], 0.0)
        self.assertIn("panel_summary", res)
        psum = res["panel_summary"]
        self.assertIn("cp_bw", psum)
        self.assertIn("cpk_bw", psum)

        report = format_sixpack_report(res)
        self.assertIn("(Between/Within)", report)
        self.assertIn("StDev(B/W)", report)
        self.assertIn("Between/Within Capability", report)

    def test_nonnormal_sixpack_engine(self):
        settings = {
            "column_name": "Strength",
            "column_data": self.weibull_data,
            "subgroup_size": 1,
            "distribution": "weibull",
            "lsl": 2.0,
            "usl": 20.0,
            "target": 10.0,
        }
        res = run_nonnormal_sixpack(settings)
        self.assertEqual(res["analysis"], "capability_sixpack_nonnormal")
        self.assertEqual(res["distribution"], "weibull")
        self.assertEqual(res["sample_n"], 100)

        # 6 panels
        self.assertIn("panel_xbar", res)
        self.assertIn("panel_disp", res)
        self.assertIn("panel_last25", res)
        self.assertIn("panel_hist", res)
        self.assertIn("panel_norm", res)
        self.assertIn("panel_summary", res)

        psum = res["panel_summary"]
        self.assertIn("pp", psum)
        self.assertIn("ppk", psum)
        self.assertIn("z_bench", psum)

        report = format_sixpack_report(res)
        self.assertIn("(Weibull)", report)
        self.assertIn("Distribution Assessment", report)
        self.assertIn("Overall Capability", report)
        self.assertIn("Ppk", report)

    def test_presenter_between_within_integration(self):
        ws = Worksheet("Quality", [
            Column("Measurement", values=self.normal_data),
        ])
        p = Presenter()
        p.worksheet = ws

        entry = p.between_within_sixpack(settings={
            "column_name": "Measurement",
            "single_column": True,
            "subgroup_spec": 5,
            "lsl": 7.0,
            "usl": 13.0,
        })
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "between_within_sixpack")
        text = format_entry(entry)
        self.assertIn("Process Capability Sixpack Report", text)
        self.assertIn("(Between/Within)", text)
        self.assertIn("StDev(B/W)", text)

    def test_presenter_nonnormal_integration(self):
        ws = Worksheet("Quality", [
            Column("Strength", values=self.weibull_data),
        ])
        p = Presenter()
        p.worksheet = ws

        entry = p.nonnormal_sixpack(settings={
            "column_name": "Strength",
            "single_column": True,
            "subgroup_spec": 1,
            "distribution": "weibull",
            "lsl": 2.0,
            "usl": 20.0,
        })
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "nonnormal_sixpack")
        text = format_entry(entry)
        self.assertIn("Process Capability Sixpack Report", text)
        self.assertIn("(Weibull)", text)
        self.assertIn("Ppk", text)


if __name__ == "__main__":
    unittest.main()
