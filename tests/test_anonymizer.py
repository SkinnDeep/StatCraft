"""Unit tests for 'Clean for Audit' Dataset Anonymizer."""
import math
import unittest
from statcraft.model import Column, Worksheet
from statcraft.anonymizer import anonymize_worksheet


def pearson_corr(x, y):
    min_len = min(len(x), len(y))
    vx, vy = x[:min_len], y[:min_len]
    mx, my = sum(vx) / min_len, sum(vy) / min_len
    sx = math.sqrt(sum((v - mx)**2 for v in vx))
    sy = math.sqrt(sum((v - my)**2 for v in vy))
    return sum((a - mx) * (b - my) for a, b in zip(vx, vy)) / (sx * sy)


class TestAnonymizer(unittest.TestCase):
    def test_text_category_anonymization(self):
        ws = Worksheet("ProprietaryData", [
            Column("Operator_Name", "text", ["Dr. John Smith", "Dr. Jane Doe", "Dr. John Smith"]),
            Column("Secret_Batch", "text", ["Batch-Alpha-99", "Batch-Beta-01", "Batch-Alpha-99"]),
            Column("Yield", "number", [95.2, 88.4, 96.1]),
        ])
        anon_ws = anonymize_worksheet(ws, mask_numeric=False)

        # Names anonymized with prefix Operator_
        self.assertEqual(len(anon_ws.columns), 3)
        self.assertNotIn("Dr. John Smith", anon_ws.columns[0].values)
        self.assertEqual(anon_ws.columns[0].values[0], anon_ws.columns[0].values[2])
        self.assertNotEqual(anon_ws.columns[0].values[0], anon_ws.columns[0].values[1])
        self.assertTrue(anon_ws.columns[0].values[0].startswith("Operator_"))

        # Batch anonymized with prefix Lot_
        self.assertTrue(anon_ws.columns[1].values[0].startswith("Lot_"))
        self.assertEqual(anon_ws.columns[1].values[0], anon_ws.columns[1].values[2])

        # Yield unchanged when mask_numeric=False
        self.assertEqual(anon_ws.columns[2].values, [95.2, 88.4, 96.1])

    def test_numeric_masking_preserves_exact_correlation(self):
        x = [10.0, 15.0, 20.0, 25.0, 30.0, 35.0]
        y = [45.0, 52.0, 68.0, 71.0, 89.0, 95.0]
        orig_r = pearson_corr(x, y)

        ws = Worksheet("ConfidentialMetrics", [
            Column("CostUSD", "number", x),
            Column("RevenueUSD", "number", y),
        ])
        anon_ws = anonymize_worksheet(ws, mask_numeric=True, numeric_scale=2.75, numeric_offset=100.0)

        # Values changed
        self.assertNotEqual(anon_ws.columns[0].values, x)
        self.assertNotEqual(anon_ws.columns[1].values, y)

        # But Pearson correlation r is mathematically invariant!
        anon_r = pearson_corr(anon_ws.columns[0].values, anon_ws.columns[1].values)
        self.assertAlmostEqual(orig_r, anon_r, places=9)


if __name__ == "__main__":
    unittest.main()
