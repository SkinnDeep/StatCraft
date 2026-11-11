"""Phase 10 Regression Tests: 15 End-User & First-Timer Bugs (v116.5.0)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QInputDialog, QMessageBox, QTreeWidgetItem

from statcraft import calculator
from statcraft.app import Presenter
from statcraft.connect import check_analysis_freshness, create_connected_generic
from statcraft.expanded_graphs import compute as compute_expanded_graph
from statcraft.io import load_csv, parse_delimited
from statcraft.model import Column, Worksheet, datetime_to_serial
from statcraft.modern_app import ModernWindow
from statcraft.modern_charts import ChartWidget
from statcraft.r_universal_translator import generate_dataframe_r_code
from statcraft.svg_html_export import export_widget_to_svg_bytes
from statcraft.variable_dialogs import ProcedureDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestPhase10EndUserBugs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _make_win(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        return win

    def test_01_oneway_anova_dialog_accepts_without_set_entry_crash(self):
        win = self._make_win()
        try:
            fake_entry = {"title": "One-Way ANOVA", "result": {"analysis": "oneway_anova"}, "time": "now"}
            fake_dlg = MagicMock()
            fake_dlg.exec.return_value = QDialog.DialogCode.Accepted
            fake_dlg.entry = fake_entry
            with patch("statcraft.oneway_dialogs.OneWayAnovaDialog", return_value=fake_dlg), \
                 patch.object(win, "show_result") as mock_show:
                win.oneway_anova_dialog()
                mock_show.assert_called_once_with(fake_entry)
        finally:
            win.close()

    def test_02_navigator_f2_rename_sheet_calls_rename_worksheet(self):
        win = self._make_win()
        try:
            item = QTreeWidgetItem(["Worksheet 1"])
            item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "sheet", "index": 0})
            win.navigator.addTopLevelItem(item)
            win.navigator.setCurrentItem(item)
            evt = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F2, Qt.KeyboardModifier.NoModifier)
            with patch.object(win, "rename_worksheet") as mock_ren:
                win.navigator.keyPressEvent(evt)
                mock_ren.assert_called_once()
        finally:
            win.close()

    def test_03_graph_selection_descriptive_stats_no_attribute_error(self):
        win = self._make_win()
        try:
            win.presenter.worksheet = Worksheet("W", [Column("X", "number", [1.0, 2.0, 3.0, 4.0])])
            with patch.object(win, "subset_worksheet_from_selection", return_value=win.presenter.worksheet), \
                 patch.object(win, "describe") as mock_desc:
                win._descriptive_stats_on_selection([1, 2])
                mock_desc.assert_called_once()
        finally:
            win.close()

    def test_04_best_subsets_and_recode_dialogs_no_update_all_crash(self):
        win = self._make_win()
        try:
            fake_entry = {"title": "Best Subsets", "result": {"analysis": "best_subsets"}, "time": "now"}
            bs_dlg = MagicMock()
            bs_dlg.exec.return_value = True
            bs_dlg.best_subsets_settings = {"response_index": 0, "free_indices": [1, 2]}
            with patch("statcraft.best_subsets_dialogs.BestSubsetsDialog", return_value=bs_dlg), \
                 patch.object(win.presenter, "best_subsets", return_value=fake_entry), \
                 patch.object(win, "show_result") as mock_show:
                win.best_subsets_dialog()
                mock_show.assert_called_once_with(fake_entry)

            rec_dlg = MagicMock()
            rec_dlg.exec.return_value = True
            rec_dlg.settings = {"source_indices": [0], "rules": []}
            rec_entry = {"title": "Recode", "result": {"analysis": "recode"}, "time": "now"}
            with patch("statcraft.recode_dialogs.RecodeDialog", return_value=rec_dlg), \
                 patch.object(win.presenter, "recode", return_value=rec_entry), \
                 patch.object(win, "show_result") as mock_show2:
                win.recode_dialog()
                mock_show2.assert_called_once_with(rec_entry)
        finally:
            win.close()

    def test_05_export_worksheet_vroom_no_importerror(self):
        win = self._make_win()
        try:
            win.presenter.worksheet = Worksheet("SensorData", [Column("Temp", "number", [21.5, 22.0])])
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
                out_r = str(Path(tmp) / "sensor_vroom.R")
                with patch.object(QFileDialog, "getSaveFileName", return_value=(out_r, "R Scripts (*.R *.r)")):
                    win.export_worksheet_vroom()
                content = Path(out_r).read_text(encoding="utf-8")
                self.assertIn("vroom", content.lower())
        finally:
            win.close()

    def test_06_view_entry_r_code_opens_dialog_without_r_viewer_module(self):
        win = self._make_win()
        try:
            win.presenter.worksheet = Worksheet("W", [Column("X", "number", [1.0, 2.0, 3.0])])
            entry = {"title": "Histogram of X", "recipe": {"action": "graph", "parameters": {"method": "histogram", "indices": [0]}}}
            with patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Accepted) as mock_exec:
                win.view_entry_r_code(entry)
                mock_exec.assert_called_once()
        finally:
            win.close()

    def test_07_r_translator_handles_date_columns_without_importerror(self):
        from datetime import datetime
        ws = Worksheet("DatesWS", [
            Column("SampleDate", "date", [datetime_to_serial(datetime(2026, 5, 14)), datetime_to_serial(datetime(2026, 5, 15))]),
            Column("Val", "number", [10.0, 12.0]),
        ])
        code = generate_dataframe_r_code(ws)
        self.assertIn("as.Date(", code)
        self.assertIn("2026-05-14", code)

    def test_08_load_csv_cp1252_and_trailing_blank_lines(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            p = Path(tmp) / "excel_export.csv"
            # Write genuine Excel ANSI cp1252 characters (°C, ±, µm) with trailing blank lines
            p.write_bytes("Temp \xb0C,Tol \xb1\xb5m\r\n25.0,1.5\r\n30.0,2.0\r\n\r\n".encode("latin-1"))
            ws = load_csv(p)
            self.assertEqual(ws.row_count, 2)
            self.assertEqual(ws.columns[0].values, [25.0, 30.0])
            self.assertIn("°C", ws.columns[0].name)

        ws2 = parse_delimited("A,B\n1,2\n3,4\n\n")
        self.assertEqual(ws2.row_count, 2)

    def test_09_paste_trailing_blank_lines_and_missing_row0_preserved(self):
        p = Presenter()
        p.worksheet = Worksheet("PasteWS", [Column("X", "number", [])])
        # Trailing blank lines must not crash rectangular width check
        p.paste(0, 0, "1\t2\r\n3\t4\r\n\r\n")
        self.assertEqual(p.worksheet.row_count, 2)
        self.assertEqual(p.worksheet.columns[0].values, [1.0, 3.0])

        # Missing cell '*' or '' in row 0 must NOT trigger Smart Header Detection to eat row 0
        p2 = Presenter()
        p2.worksheet = Worksheet("MissingTop", [Column("Measurement", "number", [])])
        p2.paste(0, 0, "*\n10\n20\n")
        self.assertEqual(p2.worksheet.columns[0].name, "Measurement")
        self.assertEqual(p2.worksheet.columns[0].values, [None, 10.0, 20.0])

    def test_10_copy_single_selected_column_does_not_truncate_at_300_rows(self):
        win = self._make_win()
        try:
            vals = [float(i) for i in range(1, 351)]  # 350 > PAGE_SIZE (300)
            win.presenter.worksheet = Worksheet("Big", [
                Column("A", "number", vals),
                Column("B", "number", vals),
            ])
            win.refresh()
            win.select_worksheet_column(0)  # Select ONLY column A via column header click
            win.copy_cells()
            copied = QApplication.clipboard().text().splitlines()
            self.assertEqual(len(copied), 350)
            self.assertEqual(float(copied[-1]), 350.0)

            win.select_worksheet_column(0)
            win.copy_with_column_names()
            copied_hdr = QApplication.clipboard().text().splitlines()
            self.assertEqual(len(copied_hdr), 351)
            self.assertEqual(copied_hdr[0], "A")
            self.assertEqual(float(copied_hdr[-1]), 350.0)
        finally:
            win.close()

    def test_11_recent_menu_and_welcome_sample_confirm_leave_and_catch_missing_file(self):
        win = self._make_win()
        try:
            missing_path = str(Path(__file__).resolve().parent / "does_not_exist_12345.csv")
            fake_settings = MagicMock()
            fake_settings.value.return_value = [missing_path]
            with patch("PySide6.QtCore.QSettings", return_value=fake_settings):
                win._update_recent_menu()
            act = win.recent_menu.actions()[0]

            # Must respect _confirm_leave() cancel
            win._confirm_leave = lambda: False
            with patch.object(win, "load_path") as mock_load:
                act.trigger()
                mock_load.assert_not_called()

            # Must wrap missing file in _call (showing warning instead of crashing)
            win._confirm_leave = lambda: True
            with patch.object(QMessageBox, "warning") as mock_warn:
                act.trigger()
                mock_warn.assert_called_once()

            # Welcome Sample button action load_connect_sample must also check _confirm_leave()
            win._confirm_leave = lambda: False
            win.presenter.worksheet = Worksheet("KeepMe", [Column("MyCol", "number", [99.0])])
            win.load_connect_sample()
            self.assertEqual(win.presenter.worksheet.name, "KeepMe")
        finally:
            win.close()

    def test_12_autofill_downward_drag_over_blank_cells_extends_without_gaps(self):
        win = self._make_win()
        try:
            win.presenter.worksheet = Worksheet("AutoFill", [Column("Seq", "number", [1.0, 2.0])])
            win.refresh()
            # Simulate selecting rows 0..7 in column 0 (dragging past end of col.values)
            win._range = lambda: (0, 7, 0, 0)
            win.table.setCurrentCell(0, 0)
            with patch.object(QInputDialog, "getInt") as mock_prompt:
                win.autofill_dialog()
                mock_prompt.assert_not_called()
            self.assertEqual(win.presenter.worksheet.columns[0].values, [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        finally:
            win.close()

    def test_13_svg_export_nonzero_viewbox_and_chart_widget_no_keyerror_crash(self):
        # 1. Offscreen unshown ChartWidget (size == 0x0 before layout) must still produce nonzero viewBox
        entry = {
            "title": "Scatter",
            "result": {"graph": "scatter", "x": [1.0, 2.0, 3.0], "y": [2.0, 4.0, 6.0], "xlabel": "X", "ylabel": "Y"},
        }
        w = ChartWidget(entry)
        w.resize(0, 0)
        svg = export_widget_to_svg_bytes(w).decode("utf-8", errors="replace")
        self.assertNotIn('viewBox="0 0 0 0"', svg)
        w.close()

        # 2. ChartWidget.paintEvent must handle missing 'x' panel key gracefully instead of crashing
        from PySide6.QtGui import QImage
        bad_entry = {"title": "Expanded Wafer", "result": {"graph": "expanded", "panels": [{"kind": "unknown_panel", "title": "Unknown"}]}}
        w2 = ChartWidget(bad_entry)
        w2.panels = [{"kind": "unknown_panel", "title": "Unknown"}]
        w2.resize(400, 300)
        img = QImage(400, 300, QImage.Format.Format_ARGB32)
        w2.render(img)  # Should draw fallback error text, not crash KeyError: 'x'
        self.assertIn("x", str(w2.error))
        w2.close()

    def test_14_wafer_plot_min_cols_and_generic_connect_freshness(self):
        ws = Worksheet("Wafer", [Column("X", "number", [1.0, 2.0]), Column("Y", "number", [1.0, 2.0])])
        with self.assertRaisesRegex(ValueError, "Incorrect number of variables"):
            compute_expanded_graph("wafer_plot", ws, [0, 1])

        conn = create_connected_generic({"title": "Descriptives", "recipe": {"action": "descriptives"}}, ws)
        status, msg = check_analysis_freshness(conn, ws)
        self.assertEqual(status, "current", msg)

    def test_15_formula_usability_and_procedure_dialog_filter_sync(self):
        # 1. Lowercase c1 and assign_formula with MEAN(C1) & bracketed [Yield Strength]
        ws = Worksheet("W", [
            Column("Yield Strength", "number", [10.0, 20.0, 30.0]),
            Column("Centered", "number", [0.0, 0.0, 0.0]),
        ])
        self.assertEqual(calculator.evaluate("c1 + 1", ws), [11.0, 21.0, 31.0])
        self.assertEqual(calculator.column_references("c1 * 2"), {0})

        p = Presenter()
        p.worksheet = ws
        p.assign_formula(1, "[Yield Strength] - MEAN(C1)")
        self.assertEqual(p.worksheet.columns[1].values, [-10.0, 0.0, 10.0])

        # 2. Calculate targeting existing column name updates instead of duplicating
        p.calculate("C1 * 2", "Centered")
        self.assertEqual([c.name for c in p.worksheet.columns], ["Yield Strength", "Centered"])
        self.assertEqual(p.worksheet.columns[1].values, [20.0, 40.0, 60.0])

        # 3. ProcedureDialog.activate keeps search filter active across selector switches
        ws2 = Worksheet("Vars", [
            Column("Temp", "number", [1.0]),
            Column("Pressure", "number", [2.0]),
            Column("Speed", "number", [3.0]),
        ])
        dlg = ProcedureDialog(
            None,
            "Test",
            ws2,
            selectors=[
                {"key": "y", "label": "Y", "kinds": ("number",)},
                {"key": "x", "label": "X", "kinds": ("number",)},
            ],
        )
        try:
            dlg.var_filter.setText("temp")
            dlg.activate("x")
            visible = [dlg.available.item(i).text() for i in range(dlg.available.count()) if not dlg.available.item(i).isHidden()]
            self.assertEqual(len(visible), 1)
            self.assertIn("Temp", visible[0])
        finally:
            dlg.close()


if __name__ == "__main__":
    unittest.main()
