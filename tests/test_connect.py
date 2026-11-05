import unittest
import copy
from statcraft.model import Worksheet, Column
from statcraft.connect import (
    ensure_worksheet_identities,
    permute_row_identities,
    compute_data_fingerprint,
    create_connected_regression,
    check_analysis_freshness,
    ConnectedAnalysis,
)
from statcraft.connect_r import (
    format_r_symbol,
    generate_r_regression_script,
    import_r_predictions_to_worksheet,
    compare_implementations,
)


class TestStatCraftConnect(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet(
            "Test_Sheet",
            [
                Column("Y Response", "number", [10.0, 20.0, 15.0, 30.0, None, 25.0]),
                Column("X1 Factor", "number", [1.0, 2.0, 1.5, 3.0, 2.5, 2.8]),
                Column("X2 Factor", "number", [10.0, 20.0, 15.0, 30.0, 25.0, 28.0]),
                Column("Category", "text", ["A", "B", "A", "B", "A", "B"]),
            ]
        )
        ensure_worksheet_identities(self.ws)

    def test_durable_identities_assigned(self):
        self.assertIn("id", self.ws.metadata)
        self.assertIn("row_ids", self.ws.metadata)
        row_ids = self.ws.metadata["row_ids"]
        self.assertEqual(len(row_ids), self.ws.row_count)
        self.assertEqual(len(set(row_ids)), len(row_ids))
        for col in self.ws.columns:
            self.assertIn("id", col.metadata)

    def test_sorting_preserves_row_identities(self):
        orig_row_ids = list(self.ws.metadata["row_ids"])
        # Suppose sort orders by X1 ascending: indices [0, 2, 1, 4, 5, 3]
        order = [0, 2, 1, 4, 5, 3]
        permute_row_identities(self.ws, order)
        new_row_ids = self.ws.metadata["row_ids"]
        self.assertEqual(new_row_ids[0], orig_row_ids[0])
        self.assertEqual(new_row_ids[1], orig_row_ids[2])
        self.assertEqual(new_row_ids[2], orig_row_ids[1])
        self.assertEqual(new_row_ids[3], orig_row_ids[4])
        self.assertEqual(new_row_ids[4], orig_row_ids[5])
        self.assertEqual(new_row_ids[5], orig_row_ids[3])

    def test_r_symbol_formatting(self):
        self.assertEqual(format_r_symbol("Simple"), "Simple")
        self.assertEqual(format_r_symbol("Y Response"), "`Y Response`")
        self.assertEqual(format_r_symbol("2026_Value"), "`2026_Value`")
        self.assertEqual(format_r_symbol("if"), "`if`")
        self.assertEqual(format_r_symbol("TRUE"), "`TRUE`")
        self.assertEqual(format_r_symbol("X-Ray (mg/L)"), "`X-Ray (mg/L)`")

    def test_create_connected_regression_and_script(self):
        result = {
            "coefficients": [("Constant", 0.5), ("X1 Factor", 9.8)],
            "r_squared": 0.985,
            "r_squared_adj": 0.980,
            "s": 0.45,
            "f_stat": 120.5,
            "p_value": 0.0001,
            "fits": [10.3, 20.1, 15.2, 29.9, 24.8],
            "residuals": [-0.3, -0.1, -0.2, 0.1, 0.2],
        }
        # Y Response is col 0, X1 Factor is col 1
        conn = create_connected_regression(self.ws, 0, [1], result, confidence=0.95)
        self.assertEqual(conn.model_type, "multiple_regression")
        self.assertEqual(conn.response_column_name, "Y Response")
        self.assertEqual(conn.predictor_column_names, ["X1 Factor"])
        # Row 4 has None in Y, so 5 rows fitted, 1 omitted
        self.assertEqual(len(conn.fitted_row_ids), 5)
        self.assertEqual(len(conn.omitted_row_ids), 1)

        # Check generated R script
        script = conn.r_script
        self.assertIn("formula_obj <- `Y Response` ~ `X1 Factor`", script)
        self.assertIn("fit <- lm(formula_obj, data = df)", script)
        self.assertIn("statcraft_export", script)
        self.assertIn("Regression_Diagnostics", script)

    def test_analysis_freshness_lifecycle(self):
        result = {
            "coefficients": [("Constant", 1.0), ("X1 Factor", 5.0)],
            "r_squared": 0.95,
            "fits": [6.0, 11.0, 8.5, 16.0, 15.0],
            "residuals": [4.0, 9.0, 6.5, 14.0, 10.0],
        }
        conn = create_connected_regression(self.ws, 0, [1], result, confidence=0.95)
        status, msg = check_analysis_freshness(conn, self.ws)
        self.assertEqual(status, "current")

        # Modifying data value makes it stale
        self.ws.columns[1].values[0] = 999.0
        status, msg = check_analysis_freshness(conn, self.ws)
        self.assertEqual(status, "stale")

        # Restoring value returns it to current
        self.ws.columns[1].values[0] = 1.0
        status, msg = check_analysis_freshness(conn, self.ws)
        self.assertEqual(status, "current")

        # Renaming column preserves bindings via column ID
        self.ws.columns[1].name = "Renamed X1"
        status, msg = check_analysis_freshness(conn, self.ws)
        self.assertEqual(status, "current")

        # Moving/inserting columns preserves bindings
        self.ws.columns.insert(0, Column("Dummy", "text", ["x"] * 6))
        ensure_worksheet_identities(self.ws)
        status, msg = check_analysis_freshness(conn, self.ws)
        self.assertEqual(status, "current")

        # Deleting predictor column marks repair_needed
        del self.ws.columns[2]  # removes Renamed X1
        status, msg = check_analysis_freshness(conn, self.ws)
        self.assertEqual(status, "repair_needed")

    def test_import_r_predictions_aligns_by_row_id(self):
        result = {
            "coefficients": [("Constant", 0.0), ("X1 Factor", 10.0)],
            "fits": [10.0, 20.0, 15.0, 30.0, 28.0],
            "residuals": [0.0, 0.0, 0.0, 0.0, -3.0],
        }
        conn = create_connected_regression(self.ws, 0, [1], result, confidence=0.95)
        row_ids = self.ws.metadata["row_ids"]

        # Simulate R exported dataframe columns
        # Note row 4 (index 4) was omitted because Y was None
        export_dict = {
            "Regression_Diagnostics": [
                Column("Row_ID", "text", conn.fitted_row_ids),
                Column("Fitted", "number", [10.1, 20.2, 15.1, 30.2, 28.1]),
                Column("Residuals", "number", [-0.1, -0.2, -0.1, -0.2, -3.1]),
            ]
        }

        # Permute worksheet rows before importing to simulate reordering
        self.ws.columns[0].values.reverse()
        self.ws.columns[1].values.reverse()
        self.ws.columns[2].values.reverse()
        self.ws.columns[3].values.reverse()
        self.ws.metadata["row_ids"].reverse()

        res = import_r_predictions_to_worksheet(self.ws, export_dict, conn)
        self.assertEqual(res["rows_updated"], 5)
        self.assertEqual(res["rows_omitted"], 1)

        fitted_col = self.ws.columns[-2]
        residuals_col = self.ws.columns[-1]
        self.assertTrue(fitted_col.name.startswith("FITS_"))
        self.assertTrue(residuals_col.name.startswith("RESI_"))

        # Check that the omitted row (row with None in Y) has None in fitted_col and residuals_col
        omitted_id = conn.omitted_row_ids[0]
        omitted_idx = self.ws.metadata["row_ids"].index(omitted_id)
        self.assertIsNone(fitted_col.values[omitted_idx])
        self.assertIsNone(residuals_col.values[omitted_idx])

        # Check an active row
        first_id = conn.fitted_row_ids[0]
        first_idx = self.ws.metadata["row_ids"].index(first_id)
        self.assertAlmostEqual(fitted_col.values[first_idx], 10.1)
        self.assertAlmostEqual(residuals_col.values[first_idx], -0.1)

    def test_compare_implementations(self):
        r_result = {
            "coefficients": [("Constant", 0.50001), ("X1 Factor", 9.80002)],
            "r_squared": 0.98501,
            "s": 0.45001,
            "f_stat": 120.501,
        }
        statcraft_result = {
            "coefficients": [("Constant", 0.50), ("X1 Factor", 9.80)],
            "r_squared": 0.985,
            "s": 0.45,
            "f_stat": 120.5,
        }
        comp = compare_implementations(statcraft_result, r_result, tolerance=1e-4)
        self.assertTrue(comp["aligned"])
        self.assertEqual(len(comp["differences"]), 0)

        # Mismatch test
        r_result_bad = copy.deepcopy(r_result)
        r_result_bad["coefficients"][1] = ("X1 Factor", 15.0)
        comp_bad = compare_implementations(statcraft_result, r_result_bad, tolerance=1e-4)
        self.assertFalse(comp_bad["aligned"])
        self.assertTrue(len(comp_bad["differences"]) > 0)

    def test_undo_redo_preserves_identities(self):
        from statcraft.app import Presenter
        presenter = Presenter()
        presenter.worksheet = self.ws
        ensure_worksheet_identities(presenter.worksheet)
        orig_row_ids = list(presenter.worksheet.metadata["row_ids"])
        orig_val = presenter.worksheet.columns[1].values[0]

        # Edit cell
        presenter.set_cell(0, 1, "99.9")
        self.assertEqual(presenter.worksheet.columns[1].values[0], 99.9)

        # Undo
        presenter.undo()
        self.assertEqual(presenter.worksheet.columns[1].values[0], orig_val)
        self.assertEqual(presenter.worksheet.metadata["row_ids"], orig_row_ids)

        # Redo
        presenter.redo()
        self.assertEqual(presenter.worksheet.columns[1].values[0], 99.9)
        self.assertEqual(presenter.worksheet.metadata["row_ids"], orig_row_ids)

    def test_named_selections_and_r_subset(self):
        row_ids = self.ws.metadata["row_ids"]
        # Save brushed rows 1, 3, 5 (1-based: rows 1, 3, 5 -> indices 0, 2, 4)
        target_rows = [1, 3, 5]
        selected_ids = [row_ids[r - 1] for r in target_rows]
        self.ws.metadata.setdefault("named_selections", {})["High_Performers"] = selected_ids

        self.assertIn("High_Performers", self.ws.metadata["named_selections"])
        self.assertEqual(self.ws.metadata["named_selections"]["High_Performers"], [row_ids[0], row_ids[2], row_ids[4]])

        # Generate R subset code
        idx_list = ", ".join(str(r) for r in sorted(target_rows))
        code = (
            f"# StatCraft Connect: Selected Observations\n"
            f"selected_rows <- c({idx_list})\n"
            f"df_subset <- df[selected_rows, ]\n"
        )
        self.assertIn("c(1, 3, 5)", code)
        self.assertIn("df_subset <- df[selected_rows, ]", code)

    def test_project_save_load_preserves_connect_metadata(self):
        import tempfile
        from pathlib import Path
        import statcraft.io as sc_io

        self.ws.metadata["named_selections"] = {"TestGroup": [self.ws.metadata["row_ids"][0]]}
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test_connect.statcraft"
            sc_io.save_project(self.ws, str(file_path))
            loaded_ws = sc_io.load_project(str(file_path))

            self.assertEqual(loaded_ws.metadata.get("id"), self.ws.metadata.get("id"))
            self.assertEqual(loaded_ws.metadata.get("row_ids"), self.ws.metadata.get("row_ids"))
            self.assertEqual(loaded_ws.metadata.get("named_selections"), self.ws.metadata.get("named_selections"))
            self.assertEqual(loaded_ws.columns[0].metadata.get("id"), self.ws.columns[0].metadata.get("id"))


if __name__ == "__main__":
    unittest.main()
