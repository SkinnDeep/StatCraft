import os
import sys
import unittest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.variable_dialogs import resolve_variables, ProcedureDialog

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestVariableDialogEnhancements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.ws = Worksheet("TestSheet", [
            Column("C1", "number", [1, 2, 3]),
            Column("C2", "number", [4, 5, 6]),
            Column("C3", "number", [7, 8, 9]),
            Column("C4", "number", [10, 11, 12]),
            Column("C5", "number", [13, 14, 15]),
            Column("Group", "text", ["A", "B", "C"]),
        ])

    def test_column_range_expansion(self):
        # C1-C3 -> [0, 1, 2]
        indices = resolve_variables("C1-C3", self.ws)
        self.assertEqual(indices, [0, 1, 2])

        # C2 - C4 -> [1, 2, 3]
        indices2 = resolve_variables("C2 - C4", self.ws)
        self.assertEqual(indices2, [1, 2, 3])

        # Mixed range and single: C1-C2 C5 -> [0, 1, 4]
        indices3 = resolve_variables("C1-C2 C5", self.ws)
        self.assertEqual(indices3, [0, 1, 4])

    def test_dialog_reset_button_and_f3(self):
        dialog = ProcedureDialog(None, "Regression", self.ws,
            selectors=[
                {"key": "y", "label": "Response", "kinds": ("number",)},
                {"key": "x", "label": "Predictors", "multiple": True, "kinds": ("number",)},
            ],
            fields=[
                {"key": "intercept", "label": "Fit intercept", "boolean": True, "default": True},
            ]
        )
        dialog.controls["y"].setText("C1")
        dialog.controls["x"].setText("C2 C3")
        dialog.controls["intercept"].setChecked(False)

        # Trigger reset
        dialog.reset_dialog()

        self.assertEqual(dialog.controls["y"].text(), "")
        self.assertEqual(dialog.controls["x"].text(), "")
        self.assertTrue(dialog.controls["intercept"].isChecked())

        # Test F3 key event triggers reset
        dialog.controls["y"].setText("C1")
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F3, Qt.KeyboardModifier.NoModifier)
        dialog.keyPressEvent(event)
        self.assertEqual(dialog.controls["y"].text(), "")

        dialog.close()

    def test_dialog_filter_variables(self):
        dialog = ProcedureDialog(None, "Test Dialog", self.ws,
            selectors=[{"key": "vars", "label": "Variables", "multiple": True, "kinds": ("number", "text")}],
        )
        self.assertTrue(hasattr(dialog, "var_filter"))
        # Type 'Group' into filter
        dialog.var_filter.setText("Group")

        # C1-C5 should be hidden, Group should be visible
        for i in range(dialog.available.count()):
            item = dialog.available.item(i)
            if "Group" in item.text():
                self.assertFalse(item.isHidden())
            else:
                self.assertTrue(item.isHidden())

        dialog.close()


if __name__ == "__main__":
    unittest.main()
