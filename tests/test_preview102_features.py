"""Tests for Preview 102: Covariance Matrix, Stem-and-Leaf, and Extended Random Data."""
import unittest
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft.covariance import compute_covariance
from statcraft.covariance_report import format_covariance_report
from statcraft.stem_leaf import compute_stem_leaf
from statcraft.stem_leaf_report import format_stem_leaf_report
from statcraft.calc_data import (
    generate_random_normal, generate_random_uniform,
    generate_random_exponential, generate_random_poisson, generate_random_binomial
)
from statcraft.recipes import run, columns


class TestPreview102Features(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet(name="TestSheet")
        self.p = Presenter()
        self.p.worksheet = self.ws

    def test_compute_covariance_pairwise_and_listwise(self):
        c1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        c2 = [2.0, 4.0, 5.0, 4.0, 5.0]
        c3 = [5.0, 4.0, 3.0, 2.0, 1.0]

        res = compute_covariance([c1, c2, c3], ["X1", "X2", "X3"], missing="Pairwise")
        self.assertEqual(res['analysis'], 'covariance')
        self.assertEqual(res['variables'], ["X1", "X2", "X3"])

        # Var(X1) = 2.5
        self.assertAlmostEqual(res['matrix'][0][0], 2.5, places=5)
        # Var(X3) = 2.5
        self.assertAlmostEqual(res['matrix'][2][2], 2.5, places=5)
        # Cov(X1, X3) = -2.5
        self.assertAlmostEqual(res['matrix'][0][2], -2.5, places=5)
        self.assertAlmostEqual(res['matrix'][2][0], -2.5, places=5)

        # Report format check
        rep = format_covariance_report(res)
        self.assertIn("Covariances", rep)
        self.assertIn("Missing Value Policy: Pairwise deletion", rep)
        self.assertIn("X1", rep)
        self.assertIn("X2", rep)
        self.assertIn("X3", rep)

    def test_covariance_presenter_and_recipe(self):
        col1 = Column("A", "number", [10, 20, 30, 40])
        col2 = Column("B", "number", [15, 25, 35, 45])
        self.ws.columns.extend([col1, col2])

        entry = self.p.covariance([0, 1], missing="Pairwise")
        self.assertIn('result', entry)
        self.assertEqual(entry['result']['analysis'], 'covariance')
        self.assertEqual(entry['recipe']['action'], 'covariance')

        # Replay recipe
        replayed = run(self.p, entry['recipe'])
        self.assertEqual(replayed['result']['matrix'], entry['result']['matrix'])
        self.assertEqual(columns(entry['recipe']), [0, 1])

    def test_compute_stem_leaf(self):
        data = [12, 15, 22, 23, 23, 28, 33, 34, 35, 41, 45, 52]
        res = compute_stem_leaf(data, "Score")
        self.assertEqual(res['analysis'], 'stem_leaf')
        self.assertEqual(res['n'], 12)
        self.assertEqual(res['n_missing'], 0)
        self.assertTrue(len(res['lines']) > 4)

        rep = format_stem_leaf_report(res)
        self.assertIn("Stem-and-Leaf Display: Score", rep)
        self.assertIn("Leaf Unit =", rep)
        self.assertIn("N = 12", rep)

    def test_stem_leaf_presenter_and_recipe(self):
        col = Column("Scores", "number", [72, 75, 78, 81, 85, 88, 92, 95, 99])
        self.ws.columns.append(col)

        entry = self.p.stem_and_leaf(0)
        self.assertEqual(entry['result']['analysis'], 'stem_leaf')
        self.assertEqual(entry['recipe']['action'], 'stem_and_leaf')

        replayed = run(self.p, entry['recipe'])
        self.assertEqual(replayed['result']['n'], 9)
        self.assertEqual(columns(entry['recipe']), [0])

    def test_extended_random_distributions(self):
        # Exponential
        exp_data = generate_random_exponential(100, scale=2.5, seed=42)
        self.assertEqual(len(exp_data), 100)
        self.assertTrue(all(v >= 0 for v in exp_data))

        # Poisson
        poi_data = generate_random_poisson(100, mean=4.0, seed=42)
        self.assertEqual(len(poi_data), 100)
        self.assertTrue(all(isinstance(v, int) and v >= 0 for v in poi_data))

        # Binomial
        bin_data = generate_random_binomial(100, trials=20, prob=0.3, seed=42)
        self.assertEqual(len(bin_data), 100)
        self.assertTrue(all(isinstance(v, int) and 0 <= v <= 20 for v in bin_data))

    def test_presenter_generate_random_distributions(self):
        # Normal
        self.p.generate_random_data(-1, dist='normal', n=50, param1=10.0, param2=2.0, seed=123)
        self.assertEqual(len(self.ws.columns), 1)
        self.assertEqual(len(self.ws.columns[0].values), 50)

        # Exponential
        self.p.generate_random_data(-1, dist='exponential', n=40, param1=3.0, seed=123)
        self.assertEqual(len(self.ws.columns), 2)
        self.assertEqual(len(self.ws.columns[1].values), 40)

        # Poisson
        self.p.generate_random_data(-1, dist='poisson', n=30, param1=5.0, seed=123)
        self.assertEqual(len(self.ws.columns), 3)
        self.assertEqual(len(self.ws.columns[2].values), 30)

        # Binomial
        self.p.generate_random_data(-1, dist='binomial', n=25, param1=15, param2=0.4, seed=123)
        self.assertEqual(len(self.ws.columns), 4)
        self.assertEqual(len(self.ws.columns[3].values), 25)


if __name__ == '__main__':
    unittest.main()
