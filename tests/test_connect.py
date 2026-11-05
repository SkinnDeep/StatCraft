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

    def test_connected_response_surface_and_bootstrap(self):
        from statcraft.connect import create_connected_response_surface
        result = {
            "coefficients": [
                {"name": "Constant", "coef": 50.0},
                {"name": "X1 Factor", "coef": 4.5},
                {"name": "X2 Factor", "coef": -2.1},
                {"name": "X1 Factor*X1 Factor", "coef": 1.2},
                {"name": "X2 Factor*X2 Factor", "coef": 0.8},
                {"name": "X1 Factor*X2 Factor", "coef": 0.5},
            ],
            "r_squared": 0.965,
            "adjusted_r_squared": 0.950,
            "f": 85.2,
            "p_value": 0.0001,
            "residual_stdev": 0.35,
            "fitted": [48.5, 52.1, 49.8, 55.0, 53.2],
            "residuals": [0.5, -0.2, 0.1, 0.4, -0.3],
            "coding_information": [
                {"name": "X1 Factor", "low": 1.0, "high": 3.0, "center": 2.0, "half_range": 1.0},
                {"name": "X2 Factor", "low": 10.0, "high": 30.0, "center": 20.0, "half_range": 10.0},
            ],
            "terms": [[0], [1], [0, 0], [1, 1], [0, 1]],
        }

        # Response: Y Response (col 0), Factors: X1 (col 1), X2 (col 2)
        conn = create_connected_response_surface(
            self.ws, 0, [1, 2], result, confidence=0.95
        )
        self.assertEqual(conn.analysis_type, "analyze_response_surface")
        self.assertEqual(conn.response_name, "Y Response")
        self.assertEqual(conn.predictor_names, ["X1 Factor", "X2 Factor"])

        # Check generated R RSM script
        script = conn.r_script
        self.assertIn("formula_obj <- `Y Response` ~ (`X1 Factor` + `X2 Factor`)^2 + I(`X1 Factor`^2) + I(`X2 Factor`^2)", script)
        self.assertIn("contour(", script)
        self.assertIn("persp(", script)
        self.assertIn("Bootstrap Prediction Uncertainty", script)
        self.assertIn("B <- 1000", script)
        self.assertIn("statcraft_export(diagnostics, 'RSM_Diagnostics')", script)

        # Import RSM Diagnostics to worksheet
        export_dict = {
            "RSM_Diagnostics": [
                Column("Row_ID", "text", conn.fitted_row_ids),
                Column("Fitted", "number", [48.6, 52.0, 49.7, 55.1, 53.0]),
                Column("Residuals", "number", [0.4, -0.1, 0.2, 0.3, -0.1]),
            ]
        }
        res = import_r_predictions_to_worksheet(self.ws, export_dict, conn, table_name="RSM_Diagnostics")
        self.assertTrue(res["success"])
        self.assertEqual(res["rows_updated"], len(conn.fitted_row_ids))

    def test_investigate_selected_observations_full_roundtrip(self):
        from statcraft.app import Presenter
        p = Presenter()
        p.worksheet = self.ws
        ensure_worksheet_identities(p.worksheet)
        row_ids = p.worksheet.metadata["row_ids"]

        # Select rows 1, 2, 4 (indices 0, 1, 3)
        target_rows = [1, 2, 4]
        row_indices_0 = [r - 1 for r in target_rows]
        subset_sheet = p.subset_worksheet("Test_Subset", "include", row_indices_0)

        # Verify subset identities & traceability
        self.assertEqual(subset_sheet.name, "Test_Subset")
        self.assertEqual(subset_sheet.row_count, 3)
        self.assertEqual(subset_sheet.metadata.get("source_worksheet"), self.ws.name)
        self.assertEqual(subset_sheet.metadata.get("source_rows"), [1, 2, 4])
        self.assertEqual(subset_sheet.metadata.get("source_row_ids"), [row_ids[0], row_ids[1], row_ids[3]])

        # Verify values preserved correctly
        self.assertEqual(subset_sheet.columns[0].values, [self.ws.columns[0].values[0], self.ws.columns[0].values[1], self.ws.columns[0].values[3]])

    def test_cross_engine_execution_comparison_live(self):
        from statcraft.app import Presenter
        from statcraft.connect import create_connected_regression
        from statcraft.connect_compare_dialog import run_cross_engine_comparison
        from statcraft.r_bridge import is_r_available

        if not is_r_available():
            self.skipTest("R is not installed on this test environment.")

        p = Presenter()
        p.worksheet = Worksheet("CompareTest", [
            Column("Y", values=[10.5, 20.2, 31.0, 40.8, 50.1]),
            Column("X1", values=[1.0, 2.0, 3.0, 4.0, 5.0]),
            Column("X2", values=[2.0, 3.0, 5.0, 7.0, 9.0]),
        ])
        entry = p.multiple_regression(0, [1, 2])
        conn = create_connected_regression(p.worksheet, 0, [1, 2], entry["result"])
        comp_res = run_cross_engine_comparison(conn, p.worksheet)

        self.assertTrue(comp_res.get("success"), f"Comparison failed: {comp_res.get('error')}")
        self.assertTrue(comp_res["comparison"]["aligned"])
        self.assertLessEqual(comp_res["comparison"]["max_diff"], 1e-4)

    def test_connected_workflow_creation_validation_and_replay(self):
        from statcraft.app import Presenter
        from statcraft.connect_workflow import (
            create_workflow_from_entry,
            validate_workflow_compatibility,
            replay_workflow,
            WorkflowValidationError,
        )

        p = Presenter()
        p.worksheet = Worksheet("Batch_1", [
            Column("Strength", "number", [10.2, 12.5, 14.8, 16.2, 18.9]),
            Column("Additive", "number", [1.0, 2.0, 3.0, 4.0, 5.0]),
        ])
        entry = p.multiple_regression(0, [1])

        # 1. Create Workflow from Entry
        wf = create_workflow_from_entry(entry, p.worksheet, title="Strength Prediction Recipe")
        self.assertEqual(wf.title, "Strength Prediction Recipe")
        self.assertEqual(len(wf.steps), 1)
        self.assertIn("r_squared", wf.baseline_metrics)

        # 2. Validate on compatible sheet
        compat, col_map, missing, warns = validate_workflow_compatibility(wf, p.worksheet)
        self.assertTrue(compat)
        self.assertEqual(missing, [])

        # 3. Validate on incompatible sheet (missing predictor column)
        ws_incompat = Worksheet("Bad_Batch", [
            Column("Strength", "number", [10, 20, 30]),
            Column("Wrong_Col", "number", [1, 2, 3]),
        ])
        compat_bad, col_map_bad, missing_bad, warns_bad = validate_workflow_compatibility(wf, ws_incompat)
        self.assertFalse(compat_bad)
        self.assertTrue(len(missing_bad) > 0)

        with self.assertRaises(WorkflowValidationError):
            replay_workflow(wf, ws_incompat, p)

        # 4. Replay on compatible new worksheet Batch_2
        ws_batch2 = Worksheet("Batch_2", [
            Column("Strength", "number", [11.0, 13.1, 15.0, 17.5, 19.8]),
            Column("Additive", "number", [1.0, 2.0, 3.0, 4.0, 5.0]),
        ])
        orig_hist_count = len(p.history)
        replay_res = replay_workflow(wf, ws_batch2, p)

        self.assertTrue(replay_res["success"])
        self.assertEqual(len(p.history), orig_hist_count + 1, "Original history must be preserved!")
        self.assertTrue(len(replay_res["convergence"]["shifts"]) > 0)


if __name__ == "__main__":
    unittest.main()
