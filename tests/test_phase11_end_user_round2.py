"""Phase 11 Regression Tests: 15 End-User & First-Timer Bugs Round 2 (v116.6.0)."""
from __future__ import annotations

import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QInputDialog, QMessageBox

from statcraft.alt_dialogs import AcceleratedLifeTestingDialog
from statcraft.app import Presenter
from statcraft.capability_engine import run_normal_capability
from statcraft.connect import ConnectedAnalysis
from statcraft.connect_r import generate_dataframe_definition, generate_r_subgroup_spc_script
from statcraft.control_chart_builder_dialog import ControlChartBuilderDialog
from statcraft.data_doctor import audit_worksheet, autofix_worksheet_issues
from statcraft.data_prep import split_worksheet
from statcraft.data_prep_dialogs import SplitWorksheetDialog
from statcraft.fit_y_by_x_dialog import FitYByXDialog
from statcraft.jmp_distribution_dialog import JMPDistributionDialog
from statcraft.model import Column, Worksheet, display_date
from statcraft.modern_app import ModernWindow
from statcraft.process_screening_dialog import ProcessScreeningDialog
from statcraft.r_workbench_widget import RPlotGalleryWidget
from statcraft.two_variances_charts import TwoVariancesSummaryPlotWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestPhase11EndUserRound2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _make_win(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        return win

    def test_01_fit_y_by_x_dialog_initializes_and_validates(self):
        ws = Worksheet("Fyx", [
            Column("Response", "number", [10.0, 12.0, 14.0, 18.0]),
            Column("Factor", "number", [1.0, 2.0, 3.0, 4.0]),
        ])
        dlg = FitYByXDialog(ws)
        try:
            dlg.controls["y_index"].setText("C1")
            dlg.controls["x_index"].setText("C2")
            vals = dlg.values()
            self.assertEqual(vals["y_index"], 0)
            self.assertEqual(vals["x_index"], 1)
        finally:
            dlg.close()

    def test_02_replay_saved_workflow_no_unbound_local_error(self):
        win = self._make_win()
        try:
            win.presenter.worksheet = Worksheet("EmptyWf", [Column("X", "number", [1.0, 2.0])])
            with patch.object(QMessageBox, "information") as mock_info:
                win.replay_saved_workflow_dialog()
                mock_info.assert_called_once()
        finally:
            win.close()

    def test_03_procedure_dialog_multi_and_optional_selectors(self):
        ws = Worksheet("JMP", [
            Column("Y1", "number", [10.0, 11.0, 12.0, 13.0, 14.0]),
            Column("Y2", "number", [20.0, 21.0, 22.0, 23.0, 24.0]),
            Column("Stress", "number", [50.0, 50.0, 75.0, 75.0, 100.0]),
        ])
        d_dist = JMPDistributionDialog(ws)
        try:
            d_dist.controls["column_indices"].setText("C1 C2")
            vals = d_dist.values()
            self.assertEqual(vals["column_indices"], [0, 1])
            d_dist.controls["column_indices"].setText("C1")
            self.assertEqual(d_dist.values()["column_indices"], [0])
        finally:
            d_dist.close()

        d_ccb = ControlChartBuilderDialog(ws)
        try:
            d_ccb.controls["y_indices"].setText("C1")
            vals_ccb = d_ccb.values()
            self.assertEqual(vals_ccb["y_indices"], [0])
            self.assertIsNone(vals_ccb["subgroup_index"])
            self.assertIsNone(vals_ccb["phase_index"])
        finally:
            d_ccb.close()

        d_ps = ProcessScreeningDialog(ws)
        try:
            d_ps.controls["variable_indices"].setText("C1")
            self.assertEqual(d_ps.values()["variable_indices"], [0])
        finally:
            d_ps.close()

        d_alt = AcceleratedLifeTestingDialog(ws)
        try:
            d_alt.controls["time_index"].setText("C1")
            d_alt.controls["stress_index"].setText("C3")
            vals_alt = d_alt.values()
            self.assertIsNone(vals_alt["censor_index"])
        finally:
            d_alt.close()

    def test_04_split_worksheet_and_repeat_subset_do_not_lose_data_or_collide(self):
        win = self._make_win()
        try:
            win.presenter.worksheet = Worksheet("Data", [
                Column("Group", "text", ["Batch", "batch", "Alpha "]),
                Column("Val", "number", [10.0, 20.0, 30.0]),
            ])
            dlg = SplitWorksheetDialog(win)
            try:
                dlg.controls["by_indices"].setText("C1")
                with patch.object(dlg, "accept") as mock_acc:
                    dlg.validate()
                    mock_acc.assert_called_once()
                self.assertIsNotNone(win.presenter.native_project)
                self.assertGreaterEqual(len(win.presenter.native_project.worksheets), 4)
            finally:
                dlg.close()

            # Repeat subset_worksheet_by_condition must disambiguate default "Subset" name
            p = Presenter()
            p.worksheet = Worksheet("Raw", [Column("X", "number", [1.0, 2.0, 3.0, 4.0])])
            e1 = p.subset_worksheet_by_condition("C1 >= 2")
            e2 = p.subset_worksheet_by_condition("C1 >= 3")
            self.assertNotEqual(e1["result"]["worksheet"], e2["result"]["worksheet"])
        finally:
            win.close()

    def test_05_save_graph_as_svg_writes_real_svg_not_plaintext(self):
        win = self._make_win()
        try:
            entry = {
                "title": "Scatter",
                "time": "2026-11-10 22:30:00",
                "result": {"graph": "scatter", "x": [1.0, 2.0, 3.0], "y": [4.0, 5.0, 6.0], "xlabel": "X", "ylabel": "Y"},
            }
            win.presenter.history.append(entry)
            win.show_result(entry)
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
                svg_path = str(Path(tmp) / "out.svg")
                with patch.object(QFileDialog, "getSaveFileName", return_value=(svg_path, "Scalable Vector Graphic (*.svg)")):
                    win.save_graph_as(entry)
                content = Path(svg_path).read_text(encoding="utf-8")
                self.assertIn("<svg", content)
        finally:
            win.close()

    def test_06_rename_column_accepts_explicit_index_from_jmp_panel(self):
        win = self._make_win()
        try:
            win.presenter.worksheet = Worksheet("JMP", [
                Column("A", "number", [1.0]),
                Column("B", "number", [2.0]),
            ])
            with patch.object(QInputDialog, "getText", return_value=("Pressure", True)):
                win.rename_column(1)
            self.assertEqual(win.presenter.worksheet.columns[1].name, "Pressure")
        finally:
            win.close()

    def test_07_paste_middle_blank_row_and_parse_common_date_formats(self):
        p = Presenter()
        p.worksheet = Worksheet("PasteDate", [Column("Val", "number", []), Column("When", "date", [])])
        p.paste(0, 0, "10\r\n\r\n30\r\n")
        self.assertEqual(p.worksheet.columns[0].values, [10.0, None, 30.0])

        p.set_cell(0, 1, "10/12/2026")
        self.assertEqual(display_date(p.worksheet.columns[1].values[0]), "2026-10-12")

    def test_08_multi_column_sort_secondary_missing_and_rank_sparse_col(self):
        p = Presenter()
        p.worksheet = Worksheet("SortRank", [
            Column("Dept", "text", ["Eng", "Eng", "Sales", "Sales"]),
            Column("Score", "number", [90.0, None, 70.0, 80.0]),
        ])
        p.sort_columns([0, 1], [0, 1], descending=False)
        self.assertEqual(p.worksheet.columns[0].values, ["Eng", "Eng", "Sales", "Sales"])
        self.assertEqual(p.worksheet.columns[1].values, [90.0, None, 70.0, 80.0])

        # Sparse rank destination "C5" on 2-column worksheet expands sequentially up to C5 (index 4)
        p.rank_column(1, destination="C5")
        self.assertEqual(len(p.worksheet.columns), 5)
        self.assertEqual([c.name for c in p.worksheet.columns], ["Dept", "Score", "C3", "C4", "C5"])
        self.assertIsNotNone(p.worksheet.columns[4].values[0])

    def test_09_two_variances_chart_handles_infinite_one_sided_limits(self):
        entry = {
            "title": "Two Variances",
            "result": {
                "confidence_level": 95.0,
                "use_normal_distribution": True,
                "sample1": {"name": "S1", "stdev": 1.2, "ci_stdev": (0.8, math.inf)},
                "sample2": {"name": "S2", "stdev": 1.0, "ci_stdev": (0.7, 2.0)},
            },
        }
        w = TwoVariancesSummaryPlotWidget(entry)
        w.resize(620, 380)
        img = QImage(620, 380, QImage.Format.Format_ARGB32)
        w.render(img)
        w.close()

    def test_10_connect_r_subgroup_spc_none_lcl_and_double_quote_escaping(self):
        ws = Worksheet("SPC", [
            Column("Meas", "number", [10.0, 10.1, 10.2, 10.0]),
            Column("Note", "text", ['12" pipe', 'Type "A"']),
        ])
        conn = ConnectedAnalysis(
            analysis_id="id1",
            analysis_type="xbar_r",
            title="Xbar-R",
            engine="statcraft",
            created_at="2026-11-10",
            worksheet_id="ws1",
            worksheet_name="SPC",
            data_fingerprint="fp",
            response_col_id="c1",
            response_name="Meas",
            predictor_col_ids=[],
            predictor_names=[],
            confidence=0.95,
            row_ids=[],
            fitted_row_ids=[],
            omitted_row_ids=[],
            coefficients=[],
            fitted_values=[],
            residuals=[],
            statistics={
                "xbar_center": 10.1, "xbar_lcl": [9.5, 9.5], "xbar_ucl": [10.7, 10.7],
                "disp_center": 0.45, "disp_lcl": [None, None], "disp_ucl": [1.1, 1.1],
            },
            metadata={"chart_type": "xbar_r", "subgroup_size": 3},
        )
        spc_r = generate_r_subgroup_spc_script(conn, ws)
        self.assertIn("0.4500, 1.1000, 0.0000", spc_r)

        df_r = generate_dataframe_definition(ws)
        self.assertIn('\\"pipe', df_r.replace(' ', ''))  # escaped quote present inside R vector string

    def test_11_capability_moving_range_span_gt_2_computes_true_span_ranges(self):
        data = [10.0, 12.0, 11.0, 15.0, 12.0, 16.0, 13.0, 18.0]
        res3 = run_normal_capability(data, subgroup_spec=1, lsl=5.0, usl=25.0, moving_range_len=3)
        # Span-3 ranges: max-min over windows of 3 -> [2, 4, 4, 4, 4, 5], mean=3.8333, / d2(3)=1.693 = ~2.264
        windows = [max(data[i:i + 3]) - min(data[i:i + 3]) for i in range(len(data) - 2)]
        expected_sd = (sum(windows) / len(windows)) / 1.693
        self.assertAlmostEqual(res3["stdev_within"], expected_sd, delta=0.02)

    def test_12_data_doctor_collinearity_alignment_numeric_autofix_and_ui_gate(self):
        ws = Worksheet("Doc", [
            Column("A", "number", [None, 1.0, 2.0, 3.0, 4.0, 5.0]),
            Column("B", "number", [1.0, 2.0, 3.0, 4.0, 5.0, None]),
            Column("C", "number", [10.0, -999.0, 12.0, 9999.0, 14.0, 15.0]),
        ])
        report = audit_worksheet(ws)
        collin = [i for i in report.issues if i.category == "collinearity"]
        self.assertGreaterEqual(len(collin), 1)  # A & B are perfectly correlated on aligned shared rows!

        fixed = autofix_worksheet_issues(ws)
        self.assertGreaterEqual(fixed, 2)
        self.assertIsNone(ws.columns[2].values[1])
        self.assertIsNone(ws.columns[2].values[3])

        # UI dialog must offer autofix when info-level string sentinels exist even without warnings
        win = self._make_win()
        try:
            win.presenter.worksheet = Worksheet("StrSent", [Column("Status", "text", ["Good", "NA", "Good"])])
            with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes) as mock_warn, \
                 patch.object(QMessageBox, "information"):
                win.run_data_doctor_dialog()
                mock_warn.assert_called_once()
        finally:
            win.close()

    def test_13_dark_result_table_copy_tsv_target_and_dialog_error_visible(self):
        win = self._make_win()
        try:
            win._dark_mode = True
            tbl = win._result_table(["Col"], [[1.5]])
            self.assertIn("#18181b", tbl.styleSheet().lower())

            e1 = {"title": "First", "time": "2026-11-10 22:30:00", "result": {"columns": [{"name": "A", "count": 3, "mean": 10.0}]}}
            e2 = {"title": "Second", "time": "2026-11-10 22:30:01", "result": {"columns": [{"name": "B", "count": 5, "mean": 99.0}]}}
            win.show_result(e2)
            with patch.object(win, "show_result") as mock_show:
                win.copy_output_table_tsv(e1)
                mock_show.assert_called_once_with(e1)
        finally:
            win.close()

        from statcraft.data_prep_dialogs import ReshapeDialog
        win2 = self._make_win()
        try:
            dlg = ReshapeDialog(win2, "stack")
            dlg.show()
            try:
                dlg.validate()  # Invalid empty selection
                self.assertTrue(dlg.error.isVisible())
                self.assertTrue(bool(dlg.error.text()))
            finally:
                dlg.close()
        finally:
            win2.close()

    def test_14_assign_formula_dialog_allows_clearing_existing_formula(self):
        win = self._make_win()
        try:
            win.presenter.worksheet = Worksheet("F", [
                Column("X", "number", [1.0, 2.0, 3.0]),
                Column("Y", "number", [2.0, 4.0, 6.0]),
            ])
            win.presenter.assign_formula(1, "C1 * 2")
            win.refresh()
            win.select_worksheet_column(1)
            def _clear_and_accept(self_dlg):
                from PySide6.QtWidgets import QDialogButtonBox, QLineEdit
                self_dlg.findChild(QLineEdit).setText("")
                self_dlg.findChild(QDialogButtonBox).accepted.emit()
                return QDialog.DialogCode.Accepted
            with patch.object(QDialog, "exec", new=_clear_and_accept):
                win.assign_formula_dialog()
            self.assertNotIn("formula", win.presenter.worksheet.columns[1].metadata)
        finally:
            win.close()

    def test_15_r_plot_viewer_save_writes_real_jpeg_and_pdf_not_raw_png(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            src_png = Path(tmp) / "src.png"
            img = QImage(120, 80, QImage.Format.Format_ARGB32)
            img.fill(0xFFFFFFFF)
            img.save(str(src_png), "PNG")

            viewer = RPlotGalleryWidget()
            viewer.plot_history = [str(src_png)]
            viewer.current_idx = 0
            try:
                out_jpg = Path(tmp) / "out.jpg"
                with patch.object(QFileDialog, "getSaveFileName", return_value=(str(out_jpg), "Images (*.png *.jpg *.pdf)")):
                    viewer.save_current_plot()
                self.assertTrue(out_jpg.read_bytes().startswith(b"\xff\xd8\xff"))

                out_pdf = Path(tmp) / "out.pdf"
                with patch.object(QFileDialog, "getSaveFileName", return_value=(str(out_pdf), "Images (*.png *.jpg *.pdf)")):
                    viewer.save_current_plot()
                self.assertTrue(out_pdf.read_bytes().startswith(b"%PDF-"))
            finally:
                viewer.close()


if __name__ == "__main__":
    unittest.main()
