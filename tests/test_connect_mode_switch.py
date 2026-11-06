import unittest
from PySide6.QtWidgets import QApplication

from statcraft.model import Worksheet, Column
from statcraft.app import Presenter

app = QApplication.instance() or QApplication([])


class TestConnectModeSwitch(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet("YieldData", [
            Column("Yield", "number", [70.0, 75.0, 80.0, 85.0, 90.0]),
            Column("Temp", "number", [100.0, 110.0, 120.0, 130.0, 140.0]),
        ])
        self.presenter = Presenter()
        self.presenter.worksheet = self.ws

    def test_mode_switch_to_r_translates_active_analysis(self):
        from statcraft.modern_app import ModernWindow
        win = ModernWindow()
        win.presenter = self.presenter
        win.refresh()

        # Run regression
        entry = self.presenter.multiple_regression(0, [1])
        win.show_result(entry)
        self.assertIsNotNone(win.selected_entry)

        # Switch to R Mode
        win.set_ui_mode("r")

        # R workbench should be loaded with the translated script
        editor_text = win.r_workbench.editor.toPlainText()
        self.assertIn("StatCraft Connect — R Translation", editor_text)
        self.assertIn("lm(formula_obj", editor_text)
        self.assertIn("Yield", editor_text)
        self.assertIn("Temp", editor_text)
        win.close()


if __name__ == "__main__":
    unittest.main()
