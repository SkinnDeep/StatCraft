"""Integration tests for native StatCraft Test for Equal Variances (MPX roundtrip, recipes, Qt window)."""
import os
import tempfile
import unittest
from pathlib import Path
from statcraft.app import Presenter, format_entry
from statcraft.model import Column, Worksheet
from statcraft.recipes import columns, run


class TestEqualVariancesIntegration(unittest.TestCase):
    def setUp(self):
        self.p = Presenter()
        self.p.worksheet = Worksheet("EqualVariancesDemo", [
            Column("Response", "number", [10, 12, 11, 13, 9, 14, 15, 13, 16, 17, 20, 25, 18, 30, 22]),
            Column("Factor", "text", ["Low", "Low", "Low", "Low", "Low", "Med", "Med", "Med", "Med", "Med", "High", "High", "High", "High", "High"]),
        ])

    def test_presenter_execution_and_recipe(self):
        entry = self.p.test_equal_variances(
            stacked=True,
            response_index=0,
            factor_indices=[1],
            options={"use_normal_distribution": False, "confidence_level": 95.0},
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["title"], "Test for Equal Variances: Response versus Factor")
        self.assertIn("Null hypothesis", format_entry(entry))
        self.assertIn("Levene", format_entry(entry))

        # Check recipe
        recipe = entry["recipe"]
        self.assertEqual(recipe["action"], "test_equal_variances")
        cols = columns(recipe)
        self.assertEqual(cols, [0, 1])

        # Rerun recipe
        re_entry = run(self.p, recipe)
        self.assertIsNotNone(re_entry)
        self.assertAlmostEqual(
            re_entry["result"]["levene"]["test_statistic"],
            entry["result"]["levene"]["test_statistic"],
        )

    def test_mpx_persistence_and_rerun(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "equal_var_test.mpx"
            entry = self.p.test_equal_variances(
                stacked=True,
                response_index=0,
                factor_indices=[1],
                options={"use_normal_distribution": True, "confidence_level": 90.0},
            )
            self.p.save(file_path)

            # Reopen in new presenter
            p2 = Presenter()
            p2.load(file_path)
            self.assertEqual(len(p2.history), 1)
            loaded_entry = p2.history[0]
            self.assertEqual(loaded_entry["title"], entry["title"])
            self.assertAlmostEqual(
                loaded_entry["result"]["test_statistic"],
                entry["result"]["test_statistic"],
            )

            # Mark stale after modifying data
            p2.set_cell(0, 0, "99.0")
            self.assertTrue(p2.result_stale(loaded_entry))

            # Rerun
            rerun_entry = p2.rerun_result(loaded_entry)
            self.assertFalse(p2.result_stale(rerun_entry))
            self.assertNotEqual(
                rerun_entry["result"]["test_statistic"],
                loaded_entry["result"]["test_statistic"],
            )

    def test_unstacked_recipe(self):
        ws_unstacked = Worksheet("UnstackedWS", [
            Column("C1", "number", [10, 12, 11, 13, 9]),
            Column("C2", "number", [14, 15, 13, 16, 17]),
            Column("C3", "number", [20, 25, 18, 30, 22]),
        ])
        self.p.worksheet = ws_unstacked
        entry = self.p.test_equal_variances(
            stacked=False,
            response_indices=[0, 1, 2],
        )
        recipe = entry["recipe"]
        cols = columns(recipe)
        self.assertEqual(cols, [0, 1, 2])
        re_entry = run(self.p, recipe)
        self.assertEqual(re_entry["result"]["count"], 15)


if __name__ == "__main__":
    unittest.main()
