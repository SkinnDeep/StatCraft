"""Unit tests for StatCraft R Integration and Positron-style R Workbench."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from statcraft.app import Presenter
from statcraft.model import Column, Worksheet
from statcraft.r_bridge import (
    execute_r_code,
    export_worksheet_to_r_dataframe_csv,
    find_r_executable,
    get_r_version,
    is_r_available,
)


class TestRIntegration(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet("TestRSheet", [
            Column("X", values=[1.0, 2.0, 3.0, 4.0, 5.0]),
            Column("Y", values=[2.5, 3.5, 5.0, 7.0, 9.0]),
        ])
        self.presenter = Presenter()
        self.presenter.worksheet = self.ws

    def test_discovery_and_version(self):
        # Should gracefully detect or return None without crashing
        exe = find_r_executable()
        avail = is_r_available()
        ver = get_r_version()
        if avail:
            self.assertIsNotNone(exe)
            self.assertIsNotNone(ver)
            self.assertIn("R", ver)

    def test_worksheet_export_to_csv(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        try:
            export_worksheet_to_r_dataframe_csv(self.ws, csv_path)
            lines = Path(csv_path).read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], "X,Y")
            self.assertEqual(lines[1], "1.0,2.5")
            self.assertEqual(len(lines), 6)
        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)

    def test_execute_session_command_rscr(self):
        # Execute an R session command via Minitab-style RSCR
        cmd = 'RSCR print(paste("STATCRAFT", 100 * 2))'
        if is_r_available():
            entry = self.presenter.execute_session_command(cmd)
            self.assertIn("result", entry)
            self.assertIn("STATCRAFT 200", entry["result"]["stdout"])
        else:
            # When R not present, graceful error message
            entry = self.presenter.execute_session_command(cmd)
            self.assertIn("result", entry)
            self.assertIn("R executable", entry["result"]["stderr"])

    def test_r_export_and_environment(self):
        if not is_r_available():
            self.skipTest("R executable not found")
        code = (
            "alpha <- 100\n"
            "beta <- c(1.1, 2.2, 3.3)\n"
            "statcraft_export(data.frame(ID=1:3, Score=c(95, 88, 72)), 'grades')\n"
        )
        res = execute_r_code(code, worksheet=self.ws, persist_session=True)
        self.assertTrue(res.get("success"), res.get("stderr"))
        self.assertIn("grades", res.get("exported_worksheets", {}))
        grades_sheet = res["exported_worksheets"]["grades"]
        self.assertEqual(grades_sheet["row_count"], 3)
        self.assertEqual(grades_sheet["columns"][0]["name"], "ID")
        self.assertEqual(grades_sheet["columns"][1]["name"], "Score")

        # Check environment introspection
        env_names = [e["name"] for e in res.get("environment", [])]
        self.assertIn("alpha", env_names)
        self.assertIn("beta", env_names)

    def test_r_workbench_widget_init(self):
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        from statcraft.modern_app import ModernWindow
        win = ModernWindow(self.presenter)
        win.set_ui_mode("r")
        self.assertEqual(win._ui_mode, "r")
        self.assertEqual(win.work_stack.currentIndex(), 1)
        self.assertIsNotNone(win.r_workbench)
        self.assertEqual(win.r_workbench.env_table.rowCount(), 4)

        # Test Positron-style Ctrl+Enter line runner and advance
        bench = win.r_workbench
        bench.editor.setPlainText("x <- 10\ny <- 20\nx + y\n")
        cursor = bench.editor.textCursor()
        cursor.setPosition(0)
        bench.editor.setTextCursor(cursor)
        self.assertEqual(bench.editor.textCursor().blockNumber(), 0)

        # Execute line 0 (x <- 10)
        bench.run_selection_or_line()
        # Cursor should automatically step down to line 1
        self.assertEqual(bench.editor.textCursor().blockNumber(), 1)

        import time
        deadline = time.monotonic() + 12
        while bench._cancel is not None and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        self.assertIsNone(bench._cancel)

        # Test REPL History navigation
        bench.repl_input.setText("1 + 1")
        bench._run_repl()
        self.assertIn("1 + 1", bench._history)
        bench.history_prev()
        self.assertEqual(bench.repl_input.text(), "1 + 1")

        win.presenter.dirty = win.presenter._results_dirty = False
        win.close()
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
