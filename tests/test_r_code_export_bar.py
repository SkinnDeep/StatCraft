import unittest
import os
import sys

# Configure headless PySide6
os.environ["QT_QPA_PLATFORM"] = "offscreen"
try:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
except ImportError:
    app = None

from statcraft.connect import ConnectedAnalysis, create_connected_analysis_from_entry
from statcraft.connect_hub import StatCraftAnalysisBar
from statcraft.model import Worksheet, Column


class TestRCodeExportBar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if app is None:
            raise unittest.SkipTest("PySide6 not installed")

    def setUp(self):
        self.ws = Worksheet(name="TestSheet")
        self.ws.columns.append(Column("A", values=[1.0, 2.0, 3.0, 4.0, 5.0]))
        self.ws.columns.append(Column("B", values=[2.0, 4.0, 6.0, 8.0, 10.0]))

    def test_analysis_bar_has_r_translator_elements(self):
        conn_dict = {
            "title": "Linear Model Test",
            "r_script": "# test r script\ndata.frame(x=1:5)",
            "analysis_type": "linear_regression",
        }
        entry = {"title": "Linear Model Test", "recipe": {"action": "test_stat"}}
        bar = StatCraftAnalysisBar(None, entry, conn_dict)

        # Check badge
        self.assertIn("R TRANSLATOR", bar.badge.text())

        # Check prominent Copy R button
        self.assertIsNotNone(bar.btn_copy_r)
        self.assertIn("Copy R Script", bar.btn_copy_r.text())

        # Check View R Code and Export R buttons
        self.assertIsNotNone(bar.btn_view_r)
        self.assertIsNotNone(bar.btn_export_r)

        # Ensure JMP / residual Connect buttons were purged
        self.assertFalse(hasattr(bar, "btn_profiler"))
        self.assertFalse(hasattr(bar, "btn_sync"))

    def test_universal_r_generation_for_non_recipe_entries(self):
        """Entries without recipes must generate valid R scripts."""
        generic_entry = {
            "title": "Two-Sample T-Test",
            "result": {
                "analysis": "two_sample_t",
                "sample1": "A",
                "sample2": "B",
                "t_stat": 2.5,
                "p_value": 0.045,
            },
        }
        conn = create_connected_analysis_from_entry(generic_entry, self.ws)
        self.assertIsNotNone(conn)
        self.assertIn("r_script", conn.to_dict())
        r_script = conn.to_dict()["r_script"]
        self.assertIn("StatCraft", r_script)
        self.assertIn("t.test", r_script)

        # Unmapped custom entries still produce generic summary(sub_df) script
        unmapped = {"title": "Custom Procedure", "result": {"analysis": "custom_summary_proc"}}
        conn2 = create_connected_analysis_from_entry(unmapped, self.ws)
        self.assertIn("summary(sub_df)", conn2.to_dict()["r_script"])

    def test_modern_window_r_translator_ui(self):
        from statcraft.modern_app import ModernWindow
        win = ModernWindow()

        try:
            # 1. Main Toolbar has prominent Copy R and View R buttons
            self.assertTrue(hasattr(win, "btn_tb_copy_r"))
            self.assertTrue(hasattr(win, "btn_tb_view_r"))
            self.assertIn("Copy R Script", win.btn_tb_copy_r.text())
            self.assertIn("View R Code", win.btn_tb_view_r.text())

            # 2. Tab corner widget has [📋 Copy R] button
            self.assertTrue(hasattr(win, "tab_copy_r_btn"))
            self.assertIn("Copy R", win.tab_copy_r_btn.text())

            # 3. Legacy mode toggle buttons exist programmatically for backward compatibility
            self.assertTrue(hasattr(win, "btn_mode_minitab"))
            self.assertTrue(hasattr(win, "btn_mode_jmp"))
            self.assertTrue(hasattr(win, "btn_mode_r"))

            # 4. Menubar has Stat -> R Translator and no &Connect top-level menu
            menubar = win.menuBar()
            actions = menubar.actions()
            menu_titles = [a.text() for a in actions]
            self.assertNotIn("&Connect", menu_titles)
            self.assertIn("&Stat", menu_titles)
            self.assertIn("&File", menu_titles)

            # 5. Helper methods are functional
            code, title = win._get_entry_r_script()
            self.assertTrue(len(code) > 0)
            self.assertIn("data.frame", code)
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
