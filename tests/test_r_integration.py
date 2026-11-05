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
        win.close()


if __name__ == "__main__":
    unittest.main()
