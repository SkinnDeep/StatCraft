import unittest
from statcraft.autofill_engine import autofill_sequence


class TestAutofillEngine(unittest.TestCase):
    def test_numeric_linear_progression(self):
        # 1, 2, 3 -> 4, 5, 6
        res = autofill_sequence([1, 2, 3], count=3)
        self.assertEqual(res, [4, 5, 6])

        # 10, 25, 40 -> 55, 70
        res2 = autofill_sequence([10.0, 25.0, 40.0], count=2)
        self.assertEqual(res2, [55.0, 70.0])

    def test_single_numeric_increments_by_one(self):
        # 5 -> 6, 7, 8
        res = autofill_sequence([5], count=3)
        self.assertEqual(res, [6, 7, 8])

    def test_prefixed_numeric_strings(self):
        # Batch_01, Batch_02 -> Batch_03, Batch_04
        res = autofill_sequence(["Batch_01", "Batch_02"], count=2)
        self.assertEqual(res, ["Batch_03", "Batch_04"])

        # Run 1, Run 2, Run 3 -> Run 4, Run 5
        res2 = autofill_sequence(["Run 1", "Run 2", "Run 3"], count=2)
        self.assertEqual(res2, ["Run 4", "Run 5"])

    def test_repeating_cycles(self):
        # A, B, A, B -> A, B, A
        res = autofill_sequence(["A", "B", "A", "B"], count=3)
        self.assertEqual(res, ["A", "B", "A"])

        # Low, Med, High -> Low, Med, High
        res2 = autofill_sequence(["Low", "Med", "High"], count=3)
        self.assertEqual(res2, ["Low", "Med", "High"])

    def test_single_string_repeats(self):
        res = autofill_sequence(["Control"], count=3)
        self.assertEqual(res, ["Control", "Control", "Control"])


if __name__ == "__main__":
    unittest.main()
