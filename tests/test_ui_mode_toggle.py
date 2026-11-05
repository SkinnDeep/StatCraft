"""Unit tests for StatCraft UI Mode toggle between Minitab Classic and JMP Platform."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# Ensure offscreen Qt platform
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["STATCRAFT_TESTING"] = "1"

_root = Path(__file__).resolve().parent.parent
_deps = _root.parent / "statcraft-build-deps"
if _deps.exists() and str(_deps) not in sys.path:
    sys.path.insert(0, str(_deps))
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication
from statcraft.modern_app import ModernWindow
from statcraft.model import Worksheet, Column
from statcraft.jmp_panel import get_jmp_icon, JMPTablePanel


class UIModeToggleTests(unittest.TestCase):
    """Test switching between Minitab Classic and JMP Platform UI modes."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.win = ModernWindow()
        self.ws = Worksheet("Big Class", [
            Column("Name", kind="text", values=["KATIE", "LOUISE", "JANE"], metadata={"modeling_type": "nominal"}),
            Column("Age", kind="number", values=[12, 12, 12], metadata={"modeling_type": "ordinal"}),
            Column("Height", kind="number", values=[59.0, 61.0, 55.0], metadata={"modeling_type": "continuous"}),
        ])
        self.win.presenter.worksheet = self.ws
        self.win.refresh()

    def tearDown(self):
        self.win.close()
        self.win.deleteLater()
        self.app.processEvents()

    def test_default_mode_and_switch_to_jmp(self):
        self.win.set_ui_mode("minitab")
        self.assertEqual(self.win._ui_mode, "minitab")
        self.assertEqual(self.win.sidebar_stack.currentIndex(), 0)
        self.assertTrue(self.win.btn_mode_minitab.isChecked())
        self.assertFalse(self.win.btn_mode_jmp.isChecked())

        # Switch to JMP Platform
        self.win.set_ui_mode("jmp")
        self.assertEqual(self.win._ui_mode, "jmp")
        self.assertEqual(self.win.sidebar_stack.currentIndex(), 1)
        self.assertFalse(self.win.btn_mode_minitab.isChecked())
        self.assertTrue(self.win.btn_mode_jmp.isChecked())

        # Verify JMP Table Panel sync
        self.assertEqual(self.win.jmp_panel.lbl_table_name.text(), "Big Class")
        self.assertEqual(self.win.jmp_panel.list_cols.count(), 3)
        self.assertIn("3 Rows", self.win.jmp_panel.lbl_table_meta.text())

    def test_repeated_toggle(self):
        for _ in range(5):
            self.win.set_ui_mode("jmp")
            self.assertEqual(self.win._ui_mode, "jmp")
            self.assertEqual(self.win.sidebar_stack.currentIndex(), 1)

            self.win.set_ui_mode("minitab")
            self.assertEqual(self.win._ui_mode, "minitab")
            self.assertEqual(self.win.sidebar_stack.currentIndex(), 0)

    def test_jmp_icons_vector(self):
        for kind in ("continuous", "nominal", "ordinal", "play_script", "table"):
            icon = get_jmp_icon(kind)
            self.assertFalse(icon.isNull(), f"Icon {kind} should not be null")
            pm = icon.pixmap(16, 16)
            self.assertEqual(pm.width(), 16)
            self.assertEqual(pm.height(), 16)

    def test_jmp_column_headers_in_table(self):
        self.win.set_ui_mode("jmp")
        headers = [self.win.table.horizontalHeaderItem(i).text() for i in range(self.win.table.columnCount())]
        self.assertTrue(any("▮" in h for h in headers), f"Expected nominal symbol in headers: {headers}")
        self.assertTrue(any("📶" in h for h in headers), f"Expected ordinal symbol in headers: {headers}")
        self.assertTrue(any("▲" in h for h in headers), f"Expected continuous symbol in headers: {headers}")

        self.win.set_ui_mode("minitab")
        headers_m = [self.win.table.horizontalHeaderItem(i).text() for i in range(self.win.table.columnCount())]
        self.assertTrue(all("▲" not in h and "▮" not in h and "📶" not in h for h in headers_m))

    def test_jmp_filter_columns(self):
        self.win.set_ui_mode("jmp")
        self.win.jmp_panel.txt_col_filter.setText("Height")
        self.assertEqual(self.win.jmp_panel.list_cols.count(), 1)
        self.win.jmp_panel.txt_col_filter.setText("")
        self.assertEqual(self.win.jmp_panel.list_cols.count(), 3)


if __name__ == "__main__":
    unittest.main()
