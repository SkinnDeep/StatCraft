import unittest

from statcraft.model import Worksheet, Column
from statcraft.app import Presenter
from statcraft.connect import create_connected_analysis_from_entry


class TestConnectUniversal(unittest.TestCase):
    def test_two_sample_t_connected_contract_and_r_script_separate_cols(self):
        ws = Worksheet("TwoSampleStudy", [
            Column("Strength_A", "number", [19.8, 20.4, 19.5, 21.2]),
            Column("Strength_B", "number", [22.1, 23.0, 22.5, 23.8]),
        ])
        p = Presenter()
        p.worksheet = ws
        p.two_sample_t({"data_format": 1, "sample1_col": 0, "sample2_col": 1})
        entry = p.history[-1]

        conn = create_connected_analysis_from_entry(entry, ws)
        self.assertIsNotNone(conn)
        self.assertEqual(conn.analysis_type, "two_sample_t")
        self.assertIn("t.test(", conn.r_script)
        self.assertIn("Strength_A", conn.r_script)
        self.assertIn("Strength_B", conn.r_script)

    def test_two_sample_t_connected_contract_and_r_script_stacked(self):
        ws = Worksheet("TwoSampleStacked", [
            Column("Strength", "number", [19.8, 20.4, 22.1, 23.0]),
            Column("Group", "text", ["G1", "G1", "G2", "G2"]),
        ])
        p = Presenter()
        p.worksheet = ws
        p.two_sample_t({"data_format": 2, "samples_col": 0, "sample_ids_col": 1})
        entry = p.history[-1]

        conn = create_connected_analysis_from_entry(entry, ws)
        self.assertIsNotNone(conn)
        self.assertEqual(conn.analysis_type, "two_sample_t")
        self.assertIn("t.test(", conn.r_script)
        self.assertIn("Strength", conn.r_script)
        self.assertIn("Group", conn.r_script)

    def test_one_sample_t_connected_contract_and_r_script(self):
        ws = Worksheet("OneSampleStudy", [
            Column("Weight", "number", [100.2, 99.8, 100.5, 101.0, 99.5]),
        ])
        p = Presenter()
        p.worksheet = ws
        p.one_sample_t({"data_format": 0, "sample_cols": [0], "perform_test": True, "hypothesized_mean": 100.0})
        entry = p.history[-1]

        conn = create_connected_analysis_from_entry(entry, ws)
        self.assertIsNotNone(conn)
        self.assertEqual(conn.analysis_type, "one_sample_t")
        self.assertIn("t.test(", conn.r_script)
        self.assertIn("Weight", conn.r_script)
        self.assertIn("mu = 100", conn.r_script)

    def test_paired_t_connected_contract_and_r_script(self):
        ws = Worksheet("PairedStudy", [
            Column("Before", "number", [120.0, 125.0, 130.0, 128.0]),
            Column("After", "number", [115.0, 122.0, 124.0, 123.0]),
        ])
        p = Presenter()
        p.worksheet = ws
        p.paired_t({"data_format": 1, "sample1_col": 0, "sample2_col": 1})
        entry = p.history[-1]

        conn = create_connected_analysis_from_entry(entry, ws)
        self.assertIsNotNone(conn)
        self.assertEqual(conn.analysis_type, "paired_t")
        self.assertIn("paired = TRUE", conn.r_script)

    def test_correlation_connected_contract_and_r_script(self):
        ws = Worksheet("CorrelStudy", [
            Column("X1", "number", [1.0, 2.0, 3.0, 4.0, 5.0]),
            Column("X2", "number", [2.1, 3.9, 6.2, 8.0, 9.9]),
        ])
        p = Presenter()
        p.worksheet = ws
        p.correlation([0, 1])
        entry = p.history[-1]

        conn = create_connected_analysis_from_entry(entry, ws)
        self.assertIsNotNone(conn)
        self.assertEqual(conn.analysis_type, "correlation")
        self.assertIn("cor(", conn.r_script)

    def test_descriptives_connected_contract_and_r_script(self):
        ws = Worksheet("DescStudy", [
            Column("Measurements", "number", [12.0, 15.0, 14.0, 18.0, 22.0]),
        ])
        p = Presenter()
        p.worksheet = ws
        p.describe_columns([0])
        entry = p.history[-1]

        conn = create_connected_analysis_from_entry(entry, ws)
        self.assertIsNotNone(conn)
        self.assertIn("descript", conn.analysis_type)
        self.assertIn("Measurements", conn.r_script)
        self.assertIn("summary(", conn.r_script)


if __name__ == "__main__":
    unittest.main()
