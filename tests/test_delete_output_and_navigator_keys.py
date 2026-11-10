import os
import sys
import unittest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QMessageBox
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestDeleteOutputAndNavigatorKeys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_delete_output_entry(self):
        ws = Worksheet("Sheet1", [Column("C1", "number", [10, 20])])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws

        entry = {"title": "Test Regression", "time": "12:00:00", "result": {"analysis": "regression", "text": "OK"}}
        win.presenter.history.append(entry)
        win.refresh()
        self.assertIn(entry, win.presenter.history)

        old_question = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
        try:
            win.delete_output_entry(entry)
            self.assertNotIn(entry, win.presenter.history)
        finally:
            QMessageBox.question = old_question

        win.close()

    def test_navigator_delete_key(self):
        ws = Worksheet("Sheet1", [Column("C1", "number", [10, 20])])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws

        entry = {"title": "Test ANOVA", "time": "12:00:00", "result": {"analysis": "anova", "text": "OK"}}
        win.presenter.history.append(entry)
        win.refresh()

        top = win.navigator.topLevelItem(0)
        item = top.child(0) if top.childCount() > 0 else top
        win.navigator.setCurrentItem(item)

        old_question = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
        try:
            event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
            win.navigator.keyPressEvent(event)
            self.assertNotIn(entry, win.presenter.history)
        finally:
            QMessageBox.question = old_question

        win.close()


if __name__ == "__main__":
    unittest.main()
