"""Unit tests for Definitive Screening Designs (DSD) generator and conference matrices."""
import unittest
import numpy as np

from statcraft.dsd import (
    _CONFERENCE_CATALOG,
    get_conference_matrix,
    generate_dsd_coded_matrix,
    create_definitive_screening_design,
)
from statcraft.model import Worksheet


class TestDSDGenerator(unittest.TestCase):
    def test_conference_matrices_catalog_orthogonality(self):
        """Every conference matrix C in the catalog must satisfy C^T C = (m - 1) I."""
        for m, C in _CONFERENCE_CATALOG.items():
            self.assertEqual(C.shape, (m, m))
            np.testing.assert_array_equal(np.diag(C), np.zeros(m))
            off_diag_mask = ~np.eye(m, dtype=bool)
            self.assertTrue(np.all(np.isin(C[off_diag_mask], [-1, 1])))
            XtX = C.T @ C
            expected = (m - 1) * np.eye(m)
            np.testing.assert_allclose(XtX, expected, atol=1e-12, err_msg=f"Conference matrix order {m} failed orthogonality.")

    def test_dsd_coded_matrix_orthogonality_properties(self):
        """Standard DSD properties:
        1. Main effects are orthogonal to each other (X_i . X_j = 0 for i != j).
        2. Main effects are orthogonal to all 2FI (X_i . (X_j * X_k) = 0).
        3. Main effects are orthogonal to all quadratics (X_i . X_j^2 = 0).
        """
        for k in [4, 5, 6, 7, 8, 10, 12]:
            X = generate_dsd_coded_matrix(k)
            n_runs, n_cols = X.shape
            self.assertEqual(n_cols, k)

            # Property 1: Main effects orthogonal
            XtX = X.T @ X
            off_diag = XtX - np.diag(np.diag(XtX))
            np.testing.assert_allclose(off_diag, 0.0, atol=1e-12, err_msg=f"k={k} main effects not orthogonal.")

            # Property 2: Main effects orthogonal to 2FI
            for i in range(k):
                for j in range(k):
                    for l in range(j + 1, k):
                        prod = X[:, j] * X[:, l]
                        dot = np.dot(X[:, i], prod)
                        self.assertAlmostEqual(dot, 0.0, places=10, msg=f"k={k}: X_{i} not orthogonal to X_{j}*X_{l}")

            # Property 3: Main effects orthogonal to quadratics
            for i in range(k):
                for j in range(k):
                    quad = X[:, j] ** 2
                    dot = np.dot(X[:, i], quad)
                    self.assertAlmostEqual(dot, 0.0, places=10, msg=f"k={k}: X_{i} not orthogonal to X_{j}^2")

    def test_categorical_factor_support(self):
        """2-level categorical factors replace 0 with +1/-1 in fold pairs."""
        factors = [
            {"name": "Temp", "type": "continuous", "low": 50, "high": 100},
            {"name": "Pressure", "type": "continuous", "low": 10, "high": 30},
            {"name": "Catalyst", "type": "categorical", "low": "CatA", "high": "CatB"},
            {"name": "Time", "type": "continuous", "low": 1, "high": 5},
        ]
        ws = create_definitive_screening_design(factors, replicates=1, extra_centers=1, randomize=False)
        self.assertIsInstance(ws, Worksheet)
        self.assertEqual(ws.columns[0].name, "StdOrder")
        self.assertEqual(ws.columns[1].name, "RunOrder")
        self.assertEqual(ws.columns[2].name, "PtType")
        self.assertEqual(ws.columns[3].name, "Blocks")
        self.assertEqual(ws.columns[6].name, "Catalyst")
        self.assertEqual(ws.columns[6].kind, "text")

        # Check categorical levels present
        cat_vals = ws.columns[6].values
        self.assertTrue(all(v in ("CatA", "CatB") for v in cat_vals))
        self.assertIn("CatA", cat_vals)
        self.assertIn("CatB", cat_vals)

    def test_replicates_and_extra_centers(self):
        factors = [{"name": f"X{i}", "low": 0, "high": 10} for i in range(5)]
        # For 5 factors, order m=6 => base runs = 2*6 + 1 + 2 = 15 runs per replicate
        ws = create_definitive_screening_design(factors, replicates=2, extra_centers=2, randomize=False)
        self.assertEqual(ws.row_count, 30)
        # Blocks column has 1 and 2
        blocks = [int(b) for b in ws.columns[3].values]
        self.assertEqual(blocks[:15], [1] * 15)
        self.assertEqual(blocks[15:], [2] * 15)

    def test_randomization_seed_reproducibility(self):
        factors = [{"name": f"X{i}", "low": 0, "high": 10} for i in range(4)]
        ws1 = create_definitive_screening_design(factors, randomize=True, seed=42)
        ws2 = create_definitive_screening_design(factors, randomize=True, seed=42)
        ws3 = create_definitive_screening_design(factors, randomize=True, seed=99)
        self.assertEqual(ws1.columns[1].values, ws2.columns[1].values)
        self.assertNotEqual(ws1.columns[1].values, ws3.columns[1].values)

    def test_doe_metadata(self):
        factors = [{"name": "A", "low": 10, "high": 20}, {"name": "B", "low": 100, "high": 200}, {"name": "C", "low": 1, "high": 2}]
        ws = create_definitive_screening_design(factors)
        self.assertIn("doe", ws.metadata)
        meta = ws.metadata["doe"]
        self.assertEqual(meta["design"], "definitive_screening")
        self.assertEqual(meta["schema"], "statcraft-dsd-v1")
        self.assertEqual(len(meta["factors"]), 3)


if __name__ == "__main__":
    unittest.main()
