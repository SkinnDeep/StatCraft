"""Unit tests for Pre-Flight Data Doctor."""
import unittest
from statcraft.model import Column, Worksheet
from statcraft.data_doctor import audit_worksheet, autofix_worksheet_issues


class TestDataDoctor(unittest.TestCase):
    def test_clean_healthy_worksheet(self):
        ws = Worksheet("HealthyData", [
            Column("A", "number", [1.0, 2.0, 3.0, 4.0, 5.0]),
            Column("B", "text", ["Lo", "Med", "Hi", "Lo", "Med"]),
        ])
        report = audit_worksheet(ws)
        self.assertFalse(report.has_warnings)
        self.assertFalse(report.has_critical)
        self.assertEqual(len(report.issues), 0)
        self.assertIn("healthy", report.summary_text.lower())

    def test_detects_leading_trailing_whitespace(self):
        ws = Worksheet("DirtyFactors", [
            Column("Factor", "text", ["Batch 1", "Batch 1 ", " Batch 2", "Batch 2"]),
        ])
        report = audit_worksheet(ws)
        self.assertTrue(report.has_warnings)
        whitespace_issues = [i for i in report.issues if i.category == "whitespace"]
        self.assertGreater(len(whitespace_issues), 0)
        self.assertTrue(any(i.can_autofix for i in whitespace_issues))

        # Test autofix
        fixed_count = autofix_worksheet_issues(ws)
        self.assertEqual(fixed_count, 2)
        self.assertEqual(ws.columns[0].values, ["Batch 1", "Batch 1", "Batch 2", "Batch 2"])

    def test_detects_zero_variance_numeric_column(self):
        ws = Worksheet("ConstantData", [
            Column("ConstantX", "number", [42.0, 42.0, 42.0, 42.0, 42.0]),
            Column("VaryingY", "number", [1.0, 2.0, 3.0, 4.0, 5.0]),
        ])
        report = audit_worksheet(ws)
        self.assertTrue(report.has_critical)
        crit_issues = [i for i in report.issues if i.category == "zero_variance"]
        self.assertEqual(len(crit_issues), 1)
        self.assertEqual(crit_issues[0].column_name, "ConstantX")

    def test_detects_sentinel_missing_codes(self):
        ws = Worksheet("SentinelData", [
            Column("Temperature", "number", [21.5, 22.0, -999.0, 23.1, 9999.0]),
            Column("Status", "text", ["Good", "Good", "N/A", "Good", "null"]),
        ])
        report = audit_worksheet(ws)
        sentinel_issues = [i for i in report.issues if i.category == "sentinel"]
        self.assertGreaterEqual(len(sentinel_issues), 2)

        # Autofix replaces sentinel strings with None
        fixed = autofix_worksheet_issues(ws)
        self.assertGreaterEqual(fixed, 2)
        self.assertIsNone(ws.columns[1].values[2])
        self.assertIsNone(ws.columns[1].values[4])

    def test_detects_severe_collinearity(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        y = [2.01 * val + 0.05 for val in x]
        ws = Worksheet("CollinearData", [
            Column("Var1", "number", x),
            Column("Var2", "number", y),
        ])
        report = audit_worksheet(ws)
        collin_issues = [i for i in report.issues if i.category == "collinearity"]
        self.assertEqual(len(collin_issues), 1)
        self.assertIn("Var1", collin_issues[0].message)


if __name__ == "__main__":
    unittest.main()
