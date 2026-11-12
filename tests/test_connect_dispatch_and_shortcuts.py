import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STATCRAFT_TESTING", "1")

from PySide6.QtWidgets import QApplication

from statcraft.modern_app import ModernWindow


def _app():
    return QApplication.instance() or QApplication(sys.argv)


class ConnectDispatchAndShortcutsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _app()

    def test_connect_open_dialog_routes_regressions_t_tests_and_graphs_accurately(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True

        routes = [
            ("fit_y_by_x", "fit_y_by_x_dialog", ()),
            ("fitted_line_plot", "fitted_line_plot_dialog", ()),
            ("best_subsets", "best_subsets_dialog", ()),
            ("stepwise_regression", "stepwise_regression_dialog", ()),
            ("two_sample_t", "two_sample_t_dialog", ()),
            ("one_sample_t", "one_sample_t_dialog", ()),
            ("paired_t", "paired_t_dialog", ()),
            ("scatter_plot", "graph", ("scatter",)),
            ("graph_builder", "graph", ("builder",)),
        ]
        for action_name, method_name, expected_args in routes:
            entry = {"recipe": {"action": action_name, "parameters": {}}}
            with patch.object(win, method_name) as mock_fn:
                win.connect_open_dialog(entry)
                mock_fn.assert_called_once_with(*expected_args)
        win.close()

    def test_connect_menu_empty_selection_shows_status_guidance(self):
        from PySide6.QtWidgets import QMenu

        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.selected_entry = None
        win.statusBar().clearMessage()

        menu = QMenu(win)
        win._populate_connect_menu(menu)
        target_act = next((a for a in menu.actions() if "Open in Statistical Dialog" in a.text()), None)
        self.assertIsNotNone(target_act)
        target_act.trigger()
        self.assertIn("Navigator", win.statusBar().currentMessage())
        win.close()

    def test_menubar_has_no_duplicate_tab_shortcuts_and_ctrl_m_command_line(self):
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True

        for bar_act in win.menuBar().actions():
            sub = bar_act.menu()
            if not sub:
                continue
            for act in sub.actions():
                if not act.shortcut().isEmpty():
                    self.assertNotIn("\t", act.text(), f"Action {act.text()!r} duplicates shortcut with \\t")

        self.assertEqual(win.view_cmd_action.shortcut().toString(), "Ctrl+M")
        win.close()


if __name__ == "__main__":
    unittest.main()
