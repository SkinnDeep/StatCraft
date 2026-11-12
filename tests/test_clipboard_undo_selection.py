import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STATCRAFT_TESTING", "1")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetSelectionRange, QTextEdit

_app = QApplication.instance() or QApplication(sys.argv)


class TestClipboardUndoSelection(unittest.TestCase):
    def setUp(self):
        from statcraft.modern_app import ModernWindow

        self.win = ModernWindow()
        ws = self.win.presenter.worksheet
        ws.columns[0].name = "X"
        ws.columns[0].kind = "number"
        ws.columns[0].values = [1.0, 2.0, 3.0, 4.0, 5.0]
        ws.columns[1].name = "Y"
        ws.columns[1].kind = "number"
        ws.columns[1].values = [10.0, 20.0, 30.0, 40.0, 50.0]
        self.win.refresh()

    def tearDown(self):
        self.win.presenter._results_dirty = False
        self.win.presenter.dirty = False
        self.win.close()

    def test_paste_currency_percent_dates_headers_and_ragged_gui(self):
        from statcraft.app import Presenter

        p = Presenter()
        # Strict Presenter.paste default still raises on ragged input
        with self.assertRaises(ValueError):
            p.paste(0, 0, "1\t2\n3")

        # Formatted currency, commas, percentages, and ISO dates with headers
        p.paste(0, 0, "Revenue\tShare\tDay\n$1,234.50\t45.2%\t2026-01-15\n$2,000\t54.8%\t2026-01-16\n")
        self.assertEqual(p.worksheet.columns[0].name, "Revenue")
        self.assertEqual(p.worksheet.columns[0].kind, "number")
        self.assertAlmostEqual(p.worksheet.columns[0].values[0], 1234.5, places=4)
        self.assertAlmostEqual(p.worksheet.columns[1].values[0], 0.452, places=4)
        self.assertEqual(p.worksheet.columns[2].name, "Day")
        self.assertEqual(p.worksheet.columns[2].kind, "date")

        # GUI paste_cells allows ragged rows by padding missing trailing cells
        QApplication.clipboard().setText("1\t2\n3\n")
        self.win.table.setFocus()
        self.win.table.setCurrentCell(0, 0)
        self.win.paste_cells()
        self.assertEqual(self.win.presenter.worksheet.columns[0].values[:2], [1.0, 3.0])
        self.assertEqual(self.win.presenter.worksheet.columns[1].values[0], 2.0)

    def test_copy_cells_respects_output_text_table_focus_and_multi_range(self):
        # Multi-range selection copy does not raise
        self.win.table.clearSelection()
        self.win.table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 0), True)
        self.win.table.setRangeSelected(QTableWidgetSelectionRange(3, 1, 4, 1), True)
        self.win.table.setFocus()
        QApplication.clipboard().setText("")
        self.win.copy_cells()
        clip_txt = QApplication.clipboard().text()
        self.assertIn("1", clip_txt)
        self.assertIn("50", clip_txt)

        # Simulated Report QTextEdit focus even when _active_graph_frame exists
        editor = QTextEdit(self.win)
        editor.setPlainText("Regression Report Summary")
        editor.selectAll()
        self.win._active_graph_frame = object()
        QApplication.clipboard().setText("")
        with patch.object(QApplication, "focusWidget", return_value=editor):
            with patch.object(self.win, "copy_output_graph") as mock_copy_graph:
                self.win.copy_cells()
                mock_copy_graph.assert_not_called()
        self.assertEqual(QApplication.clipboard().text(), "Regression Report Summary")

        # Simulated Report QTableWidget focus copies selected cells as TSV
        tbl = QTableWidget(2, 2, self.win)
        from PySide6.QtWidgets import QTableWidgetItem
        tbl.setItem(0, 0, QTableWidgetItem("Term"))
        tbl.setItem(0, 1, QTableWidgetItem("Coef"))
        tbl.setItem(1, 0, QTableWidgetItem("X"))
        tbl.setItem(1, 1, QTableWidgetItem("10.0"))
        tbl.selectAll()
        QApplication.clipboard().setText("")
        with patch.object(QApplication, "focusWidget", return_value=tbl):
            with patch.object(self.win, "copy_output_graph") as mock_copy_graph:
                self.win.copy_cells()
                mock_copy_graph.assert_not_called()
        self.assertEqual(QApplication.clipboard().text().strip(), "Term\tCoef\nX\t10.0")
        self.win._active_graph_frame = None

    def test_procedure_dialog_deduplicates_repeated_transfers(self):
        from statcraft.variable_dialogs import ProcedureDialog, format_variable_reference, resolve_variables

        dlg = ProcedureDialog(
            self.win,
            "Test Multi",
            self.win.presenter.worksheet,
            [dict(key="vars", label="Variables", multiple=True)],
        )
        dlg.available.setCurrentRow(0)
        dlg.transfer()
        dlg.available.setCurrentRow(0)
        dlg.transfer()
        expected = format_variable_reference(0, self.win.presenter.worksheet)
        self.assertEqual(dlg.controls["vars"].text().strip(), expected)
        self.assertEqual(resolve_variables(dlg.controls["vars"].text(), self.win.presenter.worksheet), [0])

    def test_duplicate_column_name_is_disambiguated_and_notified(self):
        p = self.win.presenter
        p.rename_column(0, "Score")
        p.rename_column(1, "Score")
        self.assertNotEqual(
            p.worksheet.columns[0].name.casefold(),
            p.worksheet.columns[1].name.casefold(),
        )
        self.assertTrue(any("Score" in n for n in p.notices))

    def test_missing_undo_decorators_work_for_lag_differences_and_sheet_ops(self):
        p = self.win.presenter
        orig_cols = len(p.worksheet.columns)
        p.lag({"series_index": 0, "lag": 1})
        self.assertEqual(len(p.worksheet.columns), orig_cols + 1)
        self.assertTrue(p.undo())
        self.assertEqual(len(p.worksheet.columns), orig_cols)

        p.differences({"series_index": 0, "lag": 1})
        self.assertEqual(len(p.worksheet.columns), orig_cols + 1)
        self.assertTrue(p.undo())
        self.assertEqual(len(p.worksheet.columns), orig_cols)

        # Subset & reorder worksheets are undoable
        orig_sheets = len(p.worksheets)
        p.subset_worksheet("Sub1", "include", [0, 1])
        self.assertEqual(len(p.worksheets), orig_sheets + 1)
        self.assertTrue(p.undo())
        self.assertEqual(len(p.worksheets), orig_sheets)

        p.add_worksheet("Second")
        names_before = [s.name for s in p.worksheets]
        p.reorder_worksheets(0, len(names_before) - 1)
        self.assertNotEqual([s.name for s in p.worksheets], names_before)
        self.assertTrue(p.undo())
        self.assertEqual([s.name for s in p.worksheets], names_before)

    def test_typing_equals_formula_shows_helpful_status_hint(self):
        from PySide6.QtWidgets import QTableWidgetItem
        self.win.table.setItem(0, 0, QTableWidgetItem("=X*2"))
        self.assertIn("formula", self.win.statusBar().currentMessage().lower())

    def test_standalone_dialogs_persist_settings_per_worksheet(self):
        from statcraft.fitted_line_plot_dialog import FittedLinePlotDialog
        from statcraft.regression_dialog import FitRegressionModelDialog

        d1 = FittedLinePlotDialog(self.win)
        d1.controls["response_index"].setText("Y")
        d1.controls["predictor_index"].setText("X")
        d1.rdo_quad.setChecked(True)
        d1._save_dialog_state()

        d2 = FittedLinePlotDialog(self.win)
        self.assertEqual(d2.controls["response_index"].text(), "Y")
        self.assertEqual(d2.controls["predictor_index"].text(), "X")
        self.assertTrue(d2.rdo_quad.isChecked())

        r1 = FitRegressionModelDialog(self.win)
        r1.controls["response_index"].setText("Y")
        r1.controls["predictor_indices"].setText("X")
        r1._save_dialog_state()

        r2 = FitRegressionModelDialog(self.win)
        self.assertEqual(r2.controls["response_index"].text(), "Y")
        self.assertEqual(r2.controls["predictor_indices"].text(), "X")


if __name__ == "__main__":
    unittest.main()
