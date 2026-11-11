"""Phase 12 Tests: Excel .xlsx Import, Sample Library & Guided Tour, Crash GitHub Dialog, & v117.0.0 Sync."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from statcraft.app import Presenter
from statcraft.model import Column, Worksheet, datetime_to_serial, display_date
from statcraft.modern_app import ModernWindow, WelcomeWatermarkWidget
from statcraft.xlsx_export import write_workbook

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestPhase12V117Features(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _make_win(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        return win

    def test_01_xlsx_import_single_sheet_shared_strings_dates_and_missing(self):
        from statcraft.xlsx_import import load_xlsx

        ws = Worksheet("LabData", [
            Column("Temp", "number", [21.5, None, 25.0]),
            Column("Batch", "text", ["B1", "B2", "B3"]),
            Column("RunDate", "date", [
                datetime_to_serial(datetime(2026, 5, 14)),
                datetime_to_serial(datetime(2026, 5, 15)),
                None,
            ]),
        ])
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            xlsx_path = Path(tmp) / "roundtrip.xlsx"
            write_workbook(xlsx_path, [ws])

            # Presenter.load must auto-handle .xlsx seamlessly
            p = Presenter()
            notices = p.load(xlsx_path)
            self.assertIsNone(p.native_project)
            self.assertEqual([c.name for c in p.worksheet.columns], ["Temp", "Batch", "RunDate"])
            self.assertEqual(p.worksheet.columns[0].values, [21.5, None, 25.0])
            self.assertEqual(p.worksheet.columns[1].values, ["B1", "B2", "B3"])
            self.assertEqual(p.worksheet.columns[2].kind, "date")
            self.assertEqual(display_date(p.worksheet.columns[2].values[0]), "2026-05-14")
            self.assertIsInstance(notices, list)

            # Synthetic Excel sharedStrings + built-in date numFmtId=14 XML
            shared_xlsx = Path(tmp) / "excel_shared.xlsx"
            with ZipFile(shared_xlsx, "w") as z:
                z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
                z.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
                z.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sales" sheetId="1" r:id="rId1"/></sheets></workbook>')
                z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
                z.writestr("xl/sharedStrings.xml", '<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Region</t></si><si><t>Day</t></si><si><t>North</t></si></sst>')
                z.writestr("xl/styles.xml", '<?xml version="1.0"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>')
                # Excel serial 46156 = 2026-05-14
                z.writestr("xl/worksheets/sheet1.xml", '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row><row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" s="1"><v>46156</v></c></row></sheetData></worksheet>')
            loaded_sheets = load_xlsx(shared_xlsx)
            self.assertEqual(len(loaded_sheets), 1)
            self.assertEqual(loaded_sheets[0].columns[0].values, ["North"])
            self.assertEqual(loaded_sheets[0].columns[1].kind, "date")
            self.assertEqual(display_date(loaded_sheets[0].columns[1].values[0]), "2026-05-14")

    def test_02_xlsx_import_multi_sheet_loads_project(self):
        s1 = Worksheet("LineA", [Column("X", "number", [1.0, 2.0])])
        s2 = Worksheet("LineB", [Column("Y", "text", ["OK", "NG"])])
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            xlsx_path = Path(tmp) / "multi.xlsx"
            write_workbook(xlsx_path, [s1, s2])
            p = Presenter()
            p.load(xlsx_path)
            self.assertIsNotNone(p.native_project)
            self.assertEqual([w.name for w in p.native_project.worksheets], ["LineA", "LineB"])
            self.assertEqual(p.native_project.worksheets[1].columns[0].values, ["OK", "NG"])

    def test_03_welcome_screen_buttons_and_chemical_sample_populated(self):
        win = self._make_win()
        try:
            welcome = win.result_tabs.widget(0)
            self.assertIsInstance(welcome, WelcomeWatermarkWidget)
            btn_texts = [b.text() for b in welcome.findChildren(QPushButton)]
            self.assertTrue(any("Chemical" in t or "Sample" in t for t in btn_texts))
            self.assertTrue(any("Tour" in t for t in btn_texts))
            # Links must NOT look like disabled faint #64748b flat gray text in light stylesheet
            self.assertNotIn("color: #64748b", win.styleSheet().split("watermarkLink")[1].split("}")[0])

            # Loading Chemical Yield Sample clears stale state and populates table visibly
            win.load_connect_sample()
            self.assertIsNone(win.presenter.native_project)
            self.assertGreaterEqual(win.presenter.worksheet.row_count, 25)
            self.assertEqual(win.presenter.worksheet.columns[0].name, "Yield")
            self.assertIsNotNone(win.table.item(0, 0))
            self.assertTrue(bool(win.table.item(0, 0).text().strip()))
            self.assertGreaterEqual(len(win.presenter.history), 1)
        finally:
            win.close()

    def test_04_sample_library_and_interactive_guided_tour(self):
        from statcraft.onboarding import GuidedTourDialog, SAMPLE_DATASETS, SampleLibraryDialog, build_sample_worksheet

        self.assertGreaterEqual(len(SAMPLE_DATASETS), 4)
        for spec in SAMPLE_DATASETS:
            ws = build_sample_worksheet(spec["key"])
            ws.validate()
            self.assertGreaterEqual(ws.row_count, 15)

        win = self._make_win()
        try:
            dlg = SampleLibraryDialog(win)
            try:
                self.assertGreaterEqual(dlg.dataset_list.count(), 4)
            finally:
                dlg.close()

            tour = GuidedTourDialog(win)
            try:
                self.assertGreaterEqual(len(tour.steps), 5)
                tour.next_step()
                self.assertEqual(tour.current_step, 1)
                tour.prev_step()
                self.assertEqual(tour.current_step, 0)
            finally:
                tour.close()

            # Load Six Sigma sample via ModernWindow helper
            win.load_sample_dataset("six_sigma_shafts")
            self.assertIn("Shaft", win.presenter.worksheet.name)
            self.assertGreaterEqual(win.presenter.worksheet.row_count, 20)
        finally:
            win.close()

    def test_05_crash_dialog_github_link_scrubbed_and_zero_telemetry(self):
        from statcraft.crash_dialog import (
            CrashReportDialog,
            build_github_issue_url,
            format_crash_report,
            install_crash_hook,
            write_crash_log,
        )

        # Raise real traceback including fake home directory path to test scrubbing
        try:
            raise ZeroDivisionError("division by zero in regression solver")
        except ZeroDivisionError:
            exc_type, exc_val, exc_tb = sys.exc_info()
            report = format_crash_report(exc_type, exc_val, exc_tb, context="Regression Solver")

        self.assertIn("ZeroDivisionError", report)
        self.assertIn("division by zero", report)
        self.assertIn("Regression Solver", report)
        home_str = str(Path.home())
        if len(home_str) > 4:
            self.assertNotIn(home_str, report)

        url = build_github_issue_url("Crash: ZeroDivisionError", report)
        self.assertTrue(url.startswith("https://github.com/SkinnDeep/StatCraft/issues/new?"))
        self.assertLessEqual(len(url), 2400)

        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            log_path = write_crash_log(report, directory=Path(tmp))
            self.assertTrue(log_path.is_file())
            self.assertIn("ZeroDivisionError", log_path.read_text(encoding="utf-8"))

        dlg = CrashReportDialog(report, url)
        try:
            with patch("statcraft.crash_dialog.QDesktopServices.openUrl", return_value=True) as mock_open:
                dlg.open_github_issue()
                mock_open.assert_called_once()
                self.assertEqual(bytes(mock_open.call_args[0][0].toEncoded()).decode("ascii"), url)

            dlg.copy_details()
            self.assertIn("ZeroDivisionError", QApplication.clipboard().text())
        finally:
            dlg.close()

        # Verify GitHub bug report template & crash hook installation
        template = Path(__file__).resolve().parents[1] / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml"
        self.assertTrue(template.is_file())

        prev_hook = sys.excepthook
        try:
            with patch("statcraft.crash_dialog.show_crash_dialog") as mock_show:
                install_crash_hook(force=True)
                sys.excepthook(exc_type, exc_val, exc_tb)
                mock_show.assert_called_once()
        finally:
            sys.excepthook = prev_hook

    def test_06_readme_and_version_synced_to_v117_0_0(self):
        from statcraft import __version__, updater
        repo = Path(__file__).resolve().parents[1]
        readme = (repo / "README.md").read_text(encoding="utf-8")
        self.assertEqual(__version__, "117.0.0")
        self.assertEqual(updater.STATCRAFT_VERSION, "117.0.0")
        self.assertIn("v117.0.0", readme)
        self.assertNotIn("v115.0.0", readme)
        self.assertIn("117.0.0", (repo / "pyproject.toml").read_text(encoding="utf-8"))

    def test_07_excel_ctrl_v_paste_from_inline_editors_splits_rows_and_columns(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QLineEdit

        QApplication.clipboard().setText("Yield\tTemp\r\n80.5\t120\r\n82.1\t130\r\n")

        # 1. Double-clicked inline editor in WorksheetTable must paste multi-row grid cleanly
        win1 = self._make_win()
        try:
            win1.show()
            win1.table.setCurrentCell(0, 0)
            win1.table.editItem(win1.table.item(0, 0))
            ed = win1.table.findChild(QLineEdit)
            self.assertIsNotNone(ed)
            QTest.keyClick(ed, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
            self.app.processEvents()
            self.assertEqual(win1.presenter.worksheet.row_count, 2)
            self.assertEqual(win1.presenter.worksheet.columns[0].name, "Yield")
            self.assertEqual(win1.presenter.worksheet.columns[1].name, "Temp")
            self.assertEqual(win1.presenter.worksheet.columns[0].values[:2], [80.5, 82.1])
            self.assertEqual(win1.presenter.worksheet.columns[1].values[:2], [120.0, 130.0])
        finally:
            win1.close()

        # 2. Inline editor in ColumnNamesTable must split multi-row Excel clipboard into headers + rows
        win2 = self._make_win()
        try:
            win2.show()
            win2.column_names.setCurrentCell(0, 0)
            win2.column_names.editItem(win2.column_names.item(0, 0))
            ed2 = win2.column_names.findChild(QLineEdit)
            self.assertIsNotNone(ed2)
            QTest.keyClick(ed2, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
            self.app.processEvents()
            self.assertEqual(win2.presenter.worksheet.row_count, 2)
            self.assertEqual(win2.presenter.worksheet.columns[0].name, "Yield")
            self.assertEqual(win2.presenter.worksheet.columns[1].name, "Temp")
            self.assertEqual(win2.presenter.worksheet.columns[0].values[:2], [80.5, 82.1])
        finally:
            win2.close()

    def test_08_repeated_fitted_line_plot_and_regression_and_clean_band_render(self):
        from statcraft.fitted_line_plot_dialog import FittedLinePlotDialog
        from statcraft.fitted_line_plot_chart import FittedLinePlotChartWidget
        from statcraft.regression_dialog import FitRegressionModelDialog

        win = self._make_win()
        try:
            win.load_sample_dataset("chemical_process")

            # 1st Fitted Line Plot (Quadratic, CI & PI visible, no shaded bow-tie by default)
            d1 = FittedLinePlotDialog(win)
            try:
                d1.controls["response_index"].setText("C1")
                d1.controls["predictor_index"].setText("C2")
                d1.rdo_quad.setChecked(True)
                d1.validate()
                self.assertIsNotNone(d1.entry)
                win.show_result(d1.entry)
            finally:
                d1.close()

            # 2nd Fitted Line Plot MUST open without TypeError and obey new settings (Linear, CI=False, PI=False)
            d2 = FittedLinePlotDialog(win)
            try:
                d2.rdo_lin.setChecked(True)
                d2.chk_show_ci.setChecked(False)
                d2.chk_show_pi.setChecked(False)
                d2.validate()
                self.assertIsNotNone(d2.entry)
                self.assertEqual(d2.entry["result"]["model_type"], "linear")
                self.assertFalse(d2.entry["result"]["options"]["ci"])
                self.assertFalse(d2.entry["result"]["options"]["pi"])
                win.show_result(d2.entry)
            finally:
                d2.close()

            # Verify FittedLinePlotChartWidget paints clean white plot center without giant diagonal blue slab
            chart = FittedLinePlotChartWidget(win.presenter.history[0])
            chart.resize(840, 520)
            pix = chart.grab()
            img = pix.toImage()
            # Top-left inside plot above quadratic curve was previously polluted by dark chord fill
            sample_rgb = img.pixelColor(95, 70)
            self.assertEqual((sample_rgb.red(), sample_rgb.green(), sample_rgb.blue()), (255, 255, 255))

            # Repeat FitRegressionModelDialog obeys and surfaces errors visibly
            r1 = FitRegressionModelDialog(win)
            try:
                r1.controls["response_index"].setText("C1")
                r1.controls["predictor_indices"].setText("C2")
                r1.validate()
                self.assertIsNotNone(r1.entry)
            finally:
                r1.close()

            r2 = FitRegressionModelDialog(win)
            try:
                r2.controls["response_index"].setText("C1")
                r2.controls["predictor_indices"].setText("C1")  # invalid overlap -> visible error
                r2.validate()
                self.assertFalse(r2.error.isHidden())
                self.assertTrue(bool(r2.error.text()))
                r2.controls["predictor_indices"].setText("C2 C3")
                r2.validate()
                self.assertIsNotNone(r2.entry)
                self.assertEqual(r2.entry["result"]["predictor_names"], ["Temperature", "Pressure"])
            finally:
                r2.close()
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
