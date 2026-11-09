"""Unit tests for Multiple Correspondence Analysis (MCA)."""
import unittest
import numpy as np

from statcraft.multiple_correspondence import clean_mca_data, fit_multiple_correspondence
from statcraft.multiple_correspondence_report import generate_multiple_correspondence_report
from statcraft.model import Worksheet, Column
from statcraft.app import Presenter, format_entry


class TestMultipleCorrespondence(unittest.TestCase):
    def setUp(self):
        # Survey dataset: Car preference study
        # AgeGroup (Young, Middle, Senior)
        # CarType (Sedan, SUV, Sports)
        # Purpose (Commute, Family, Leisure)
        self.age = ["Young", "Young", "Middle", "Middle", "Senior", "Senior", "Young", "Middle", "Senior", "Young"]
        self.car = ["Sports", "Sedan", "SUV", "Sedan", "Sedan", "SUV", "Sports", "SUV", "Sedan", "Sedan"]
        self.purpose = ["Leisure", "Commute", "Family", "Commute", "Commute", "Family", "Leisure", "Family", "Commute", "Commute"]

    def test_clean_data(self):
        c1 = ["A", "B", None, "A", "B"]
        c2 = ["X", "Y", "Z", "X", "Y"]
        rows, names, levels, total_k = clean_mca_data([c1, c2], ["V1", "V2"])
        self.assertEqual(len(rows), 4)
        self.assertEqual(names, ["V1", "V2"])
        self.assertEqual(levels[0], ["A", "B"])
        self.assertEqual(total_k, 4)

    def test_multiple_correspondence_fit(self):
        res = fit_multiple_correspondence(
            data_columns=[self.age, self.car, self.purpose],
            n_components=2,
            variable_names=["AgeGroup", "CarType", "Purpose"],
        )
        self.assertEqual(res["analysis"], "multiple_correspondence")
        self.assertEqual(res["n_obs"], 10)
        self.assertEqual(res["n_vars"], 3)
        self.assertGreater(res["total_inertia"], 0.0)

        # Inertia table
        ine_tab = res["inertia_table"]
        self.assertGreater(len(ine_tab), 1)
        self.assertAlmostEqual(ine_tab[-1]["cumulative"], 1.0, places=4)

        # Category coordinates table
        cat_tab = res["category_table"]
        self.assertEqual(len(cat_tab), res["n_categories"])
        for row in cat_tab:
            self.assertIn("mass", row)
            self.assertIn("quality", row)
            self.assertIn("relative_inertia", row)
            self.assertIn("coord_1", row)
            self.assertIn("coord_2", row)
            self.assertGreaterEqual(row["quality"], 0.0)
            self.assertLessEqual(row["quality"], 1.0)

    def test_report_generation(self):
        res = fit_multiple_correspondence(
            data_columns=[self.age, self.car, self.purpose],
            n_components=2,
            variable_names=["AgeGroup", "CarType", "Purpose"],
        )
        report = generate_multiple_correspondence_report(res)
        self.assertIn("Multiple Correspondence Analysis: AgeGroup, CarType, Purpose", report)
        self.assertIn("Principal Inertias", report)
        self.assertIn("Axis 1", report)
        self.assertIn("Category Coordinates", report)
        self.assertIn("AgeGroup", report)
        self.assertIn("CarType", report)
        self.assertIn("Purpose", report)

    def test_presenter_integration(self):
        ws = Worksheet("Survey", [
            Column("AgeGroup", kind="text", values=self.age),
            Column("CarType", kind="text", values=self.car),
            Column("Purpose", kind="text", values=self.purpose),
        ])
        p = Presenter()
        p.worksheet = ws

        entry = p.multiple_correspondence(
            variable_columns=[0, 1, 2],
            n_components=2,
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["recipe"]["action"], "multiple_correspondence")
        text = format_entry(entry)
        self.assertIn("Multiple Correspondence Analysis", text)
        self.assertIn("Principal Inertias", text)
        self.assertIn("Category Coordinates", text)


if __name__ == "__main__":
    unittest.main()
