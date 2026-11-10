"""Unit tests for Vectorized Formula Engine."""
import unittest
from statcraft.model import Column, Worksheet
from statcraft.formula_engine import evaluate_formula, preview_formula


class TestFormulaEngine(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet("TestData", [
            Column("Temp", "number", [10.0, 20.0, 30.0, 40.0]),
            Column("Pressure", "number", [100.0, 200.0, 300.0, 400.0]),
            Column("Status", "text", ["Lo", "Med", "Hi", "Hi"]),
        ])

    def test_basic_arithmetic_by_column_ids(self):
        res, err = evaluate_formula("= C1 * 1.5 + C2", self.ws)
        self.assertIsNone(err)
        self.assertEqual(res, [115.0, 230.0, 345.0, 460.0])

    def test_math_functions(self):
        res, err = evaluate_formula("sqrt(C2)", self.ws)
        self.assertIsNone(err)
        self.assertEqual(res, [10.0, 14.142135623730951, 17.320508075688775, 20.0])

    def test_bracketed_column_names(self):
        res, err = evaluate_formula("= [Temp] + 5.0", self.ws)
        self.assertIsNone(err)
        self.assertEqual(res, [15.0, 25.0, 35.0, 45.0])

    def test_where_conditional(self):
        res, err = evaluate_formula("where(C1 > 25, 1, 0)", self.ws)
        self.assertIsNone(err)
        self.assertEqual(res, [0, 0, 1, 1])

    def test_live_preview(self):
        preview, err = preview_formula("= C1 * 2", self.ws, n_preview=2)
        self.assertIsNone(err)
        self.assertEqual(preview, [20.0, 40.0])

    def test_disallows_dangerous_builtins(self):
        res, err = evaluate_formula("import os", self.ws)
        self.assertIsNotNone(err)
        self.assertIn("unauthorized", err.lower())


if __name__ == "__main__":
    unittest.main()
