"""Headless presenter contracts; no interactive desktop is created by tests."""
import json
import math
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from statcraft.app import Presenter, format_entry, _number_list, histogram_data, boxplot_data
from statcraft.model import Column, Matrix, Worksheet
from statcraft.io import UnsupportedFormatError


class PresenterContractTests(unittest.TestCase):
    def test_transactional_tabular_paste_copy_and_type_adaptation(self):
        p = Presenter()
        p.worksheet.columns[0].metadata["auto_type"] = True
        p.paste(0, 0, '1\t"Ω, text"\n2\t"multi\nline"\n*\t*\n')
        self.assertEqual(p.worksheet.columns[0].values, [1, 2, None])
        self.assertEqual(p.worksheet.columns[1].kind, "text")
        self.assertEqual(p.worksheet.columns[1].values, ["Ω, text", "multi\nline", "*"])
        q = Presenter(); q.paste(0, 0, p.copy_block(0, 2, 0, 1))
        self.assertEqual([c.values for c in p.worksheet.columns], [c.values for c in q.worksheet.columns])
        before = [list(c.values) for c in p.worksheet.columns]
        with self.assertRaises(ValueError):
            p.paste(0, 0, "3\tokay\ninvalid\tno")
        self.assertEqual([c.values for c in p.worksheet.columns], before)
        with self.assertRaises(ValueError):
            p.paste(0, 0, "1\t2\n3")

    def test_automatic_type_for_blank_gui_column_and_type_change_validation(self):
        p = Presenter()
        p.worksheet.columns[0].metadata["auto_type"] = True
        p.paste(0, 0, "alpha\nbeta\n")
        self.assertEqual(p.worksheet.columns[0].kind, "text")
        with self.assertRaises(ValueError):
            p.set_column_type(0, "number")
        self.assertEqual(p.worksheet.columns[0].kind, "text")
        p.set_cell(0, 0, "1"); p.set_cell(1, 0, "2")
        p.set_column_type(0, "number")
        self.assertEqual(p.worksheet.columns[0].values, [1, 2])

    def test_multicolumn_readable_descriptive_table(self):
        p = Presenter()
        p.worksheet = Worksheet("T", [Column("A", values=[1, None, 3]), Column("B", values=[10, 20])])
        entry = p.describe_columns([0, 1]); report = format_entry(entry)
        self.assertIn("Variable", report); self.assertIn("SE Mean", report)
        self.assertIn("StDev", report); self.assertIn("N* counts missing", report)
        self.assertNotIn('"columns"', report)
        self.assertEqual(entry["result"]["columns"][0]["missing"], 1)

    def test_plot_conventions_and_boundaries_without_gui(self):
        edges, counts = histogram_data([0, 1, 2, 3, 4, None], 2)
        self.assertEqual(edges, [0, 2, 4]); self.assertEqual(counts, [2, 3])
        edges, counts = histogram_data([7, 7, 7], 1)
        self.assertEqual(counts, [3]); self.assertEqual(edges, [6.5, 7.5])
        box = boxplot_data([1, 2, 3, 4, 5, 6, 7, 100, None])
        self.assertEqual((box["q1"], box["median"], box["q3"]), (2.25, 4.5, 6.75))
        self.assertEqual((box["low"], box["high"], box["outliers"]), (1, 7, [100]))
        with self.assertRaises(ValueError): histogram_data([])
        with self.assertRaises(ValueError): boxplot_data([None])

    def test_inference_presenter_pairs_preserve_ragged_alignment(self):
        module = types.ModuleType("statcraft.inference")
        received = []
        def paired(x, y, mu, confidence):
            received.append((x, y, mu, confidence)); return {"count": 1, "p_value": .1}
        module.paired_t = paired
        p = Presenter(); p.worksheet = Worksheet("T", [Column("A", values=[1, None, 3]), Column("B", values=[2, 4])])
        import statcraft
        with patch.dict(sys.modules, {"statcraft.inference": module}), patch.object(statcraft, "inference", module, create=True):
            p.inference("paired_t", [0, 1], 0, .95)
        self.assertEqual(received, [([1, None, 3], [2, 4, None], 0, .95)])
        self.assertEqual(len(p.history), 1)

    def test_actual_inference_integration(self):
        p = Presenter(); p.worksheet = Worksheet("T", [Column("A", values=[1, None, 3, 5]), Column("B", values=[2, 4, 4, 7])])
        paired = p.inference("paired_t", [0, 1])["result"]
        self.assertEqual(paired["count"], 3)
        self.assertEqual(paired["row_indices"], [0, 2, 3])
        self.assertTrue(0 <= paired["p_value"] <= 1)
        regression = p.inference("linear_regression", [0, 1])["result"]
        self.assertEqual(regression["count"], 3)
        report = format_entry(p.history[-1])
        self.assertIn("Coefficients", report)
        self.assertIn("SE Coef", report)
        self.assertIn("Regression Equation", report)
        self.assertEqual(report.count("Assumption:"), 1)
        p.worksheet = Worksheet("T", [Column("A", values=[1, 2, 3, 4]), Column("B", values=[4, 5, 8, 9])])
        p.inference("one_way_anova", [0, 1])
        anova = format_entry(p.history[-1])
        self.assertIn("Analysis of Variance", anova)
        self.assertIn("Between groups", anova)
        self.assertIn("Within groups", anova)

    def test_typed_edit_validation_leaves_data_untouched_on_error(self):
        p = Presenter()
        p.set_cell(0, 0, "2.5")
        p.set_cell(1, 0, "*")
        self.assertEqual(p.worksheet.columns[0].values, [2.5, None])
        before = list(p.worksheet.columns[0].values)
        for raw in ("not a number", "NaN", "Infinity"):
            with self.assertRaises(ValueError):
                p.set_cell(0, 0, raw)
            self.assertEqual(p.worksheet.columns[0].values, before)
        p.add_column("Labels", "text")
        p.set_cell(0, 1, "")
        p.set_cell(1, 1, "*")
        self.assertEqual(p.worksheet.columns[1].values, ["", "*"])
        p.add_column("When", "date")
        p.set_cell(0, 2, "2020-01-01")
        self.assertEqual(p.worksheet.columns[2].values[0], 43831)
        self.assertTrue(p.dirty)

    def test_edit_extend_add_rows_and_limits(self):
        p = Presenter(); p.set_cell(2, 0, "7"); p.add_column("B")
        p.set_cell(0, 1, "3"); p.add_rows(2)
        self.assertEqual(p.worksheet.row_count, 5)
        self.assertEqual(len(p.worksheet.columns[1].values), 5)
        p.rename_column(1, "Measurements")
        self.assertEqual(p.worksheet.headers, ["C1", "Measurements"])
        for count in (0, -1, 1.5):
            with self.assertRaises(ValueError):
                p.add_rows(count)
        with patch("statcraft.app.io.MAX_CELLS", 2):
            with self.assertRaises(ValueError):
                p.add_rows(1)

    def test_original_project_save_export_and_failure_transaction(self):
        p = Presenter(); p.set_cell(0, 0, "5")
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            project = Path(tmp) / "worksheet.statcraft"
            p.save(project)
            self.assertFalse(p.dirty)
            p.set_cell(0, 0, "6")
            p.export(Path(tmp) / "table.csv")
            self.assertTrue(p.dirty)
            q = Presenter(); q.load(project)
            self.assertEqual(q.worksheet.columns[0].values, [5])
            old = q.worksheet
            bad = Path(tmp) / "broken.statcraft"; bad.write_text("bad json", encoding="utf8")
            with self.assertRaises(ValueError):
                q.load(bad)
            self.assertIs(q.worksheet, old)
            with self.assertRaises(ValueError):
                q.save(Path(tmp) / "wrong.mwx")

    def test_csv_explicit_types_and_preflight_notices(self):
        p = Presenter()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            path = Path(tmp) / "labels.csv"
            path.write_text("code,value\n001,4\n002,5\n", encoding="utf8")
            p.load(path, column_types=["text", "number"])
            self.assertEqual(p.worksheet.columns[0].values, ["001", "002"])
            self.assertIsNone(p.project_path)
        p.worksheet.constants = [Column("K", values=[2])]
        p.worksheet.matrices = [Matrix("M", 1, 1, [1])]
        p.worksheet.columns.append(Column("D", "date", [43831]))
        notes = p.export_notices()
        self.assertTrue(any("Constants" in n for n in notes))
        self.assertTrue(any("Dates" in n for n in notes))

    def test_describe_contract_keeps_missing_alignment_and_history(self):
        p = Presenter(); p.worksheet = Worksheet("T", [Column("A", values=[1, None, 3])])
        module = types.ModuleType("statcraft.analyses")
        received = []
        def describe(values):
            received.append(values)
            return {"count": 2, "missing": 1, "mean": 2}
        module.describe = describe
        with patch.dict(sys.modules, {"statcraft.analyses": module}):
            result = p.describe_column(0)
        self.assertEqual(received, [[1.0, None, 3.0]])
        self.assertEqual(result["result"]["mean"], 2)
        self.assertEqual(len(p.history), 1)
        self.assertIn("Descriptive statistics", format_entry(result))

    def test_actual_descriptive_summary_integration(self):
        p = Presenter()
        p.worksheet = Worksheet("T", [Column("A", values=[1, None, 3]), Column("S", "text", ["a"])])
        result = p.describe_column(0)["result"]
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["missing"], 1)
        self.assertEqual(result["mean"], 2)
        self.assertAlmostEqual(result["sample_variance"], 2)
        with self.assertRaises(ValueError):
            p.describe_column(1)

    def test_weibull_supported_methods_and_no_history_on_bad_inputs(self):
        p = Presenter()
        cdf = p.weibull("cdf", 1, 2, value=2)
        self.assertAlmostEqual(cdf["result"]["result"], 1 - math.exp(-1))
        pdf = p.weibull("pdf", 1, 2, value=2)
        self.assertAlmostEqual(pdf["result"]["result"], math.exp(-1) / 2)
        mean = p.weibull("mean", 1, 2)
        self.assertAlmostEqual(mean["result"]["result"], 2)
        before = len(p.history)
        for args in [("unknown", 1, 2), ("cdf", -1, 2)]:
            with self.assertRaises(ValueError):
                p.weibull(*args)
        self.assertEqual(len(p.history), before)

    def test_packed_solver_and_singular_system(self):
        p = Presenter()
        self.assertEqual(p.solve([2, 1, 3], [5, 6])["result"]["solution"], [1.5, 2])
        self.assertEqual(p.solve([2, 1, 3], [4, 8], True)["result"]["solution"], [2, 2])
        with self.assertRaisesRegex(ValueError, "Singular"):
            p.solve([0, 1, 3], [5, 6])
        self.assertEqual(len(p.history), 2)
        with self.assertRaises(ValueError):
            _number_list("[true, 3]")
        self.assertEqual(_number_list("2, 1, 3"), [2, 1, 3])

    def test_recent_history_is_bounded_and_new_clears_document_state(self):
        p = Presenter()
        for index in range(105):
            p.weibull("mean", 1, 1 + index)
        self.assertEqual(len(p.history), 100)
        p.set_cell(0, 0, "2"); p.new()
        self.assertFalse(p.dirty)
        self.assertEqual(p.worksheet.row_count, 0)
        self.assertEqual(len(p.history), 0)  # New project must not inherit old saved results.


if __name__ == "__main__":
    unittest.main()
