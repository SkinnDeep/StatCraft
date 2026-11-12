import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STATCRAFT_TESTING", "1")

from PySide6.QtWidgets import QApplication, QDialog, QLineEdit

_app = QApplication.instance() or QApplication(sys.argv)


class TestSubgroupModesAndDialogWiring(unittest.TestCase):
    def setUp(self):
        from statcraft.modern_app import ModernWindow

        self.win = ModernWindow()
        ws = self.win.presenter.worksheet
        ws.columns[0].name = "X"
        ws.columns[0].kind = "number"
        ws.columns[0].values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        ws.columns[1].name = "Y"
        ws.columns[1].kind = "number"
        ws.columns[1].values = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
        ws.columns[2].name = "M"
        ws.columns[2].kind = "number"
        ws.columns[2].values = [10.1, 10.2, 9.9, 10.0, 10.3, 10.4, 9.8, 10.1, 10.2, 9.7]
        self.win.refresh()

    def tearDown(self):
        self.win.presenter._results_dirty = False
        self.win.presenter.dirty = False
        self.win.close()

    def test_subgroup_single_chart_modes_and_panels(self):
        from statcraft.subgroup_control_chart import prepare

        for mode, expected_title_prefix, expected_panels, expected_subpanel in [
            ("xbar", "Xbar Chart:", 1, "xbar"),
            ("r", "R Chart:", 1, "disp"),
            ("s", "S Chart:", 1, "disp"),
            ("xbar_r", "Xbar-R Chart:", 2, "xbar"),
            ("xbar_s", "Xbar-S Chart:", 2, "xbar"),
        ]:
            entry = self.win.presenter.subgroup_control_chart(
                chart_type=mode, stacked=True, response_index=2, subgroup_size=2
            )
            self.assertTrue(
                entry["title"].startswith(expected_title_prefix),
                f"Expected title starting with {expected_title_prefix!r}, got {entry['title']!r}",
            )

            class DummyChart:
                panels = []
                panel_columns = 1
                note = ""
                def setMinimumWidth(self, w): pass
                def setMinimumHeight(self, h): pass

            dummy = DummyChart()
            prepare(dummy, entry["result"])
            self.assertEqual(len(dummy.panels), expected_panels, f"Mode {mode} panel count mismatch")
            self.assertEqual(dummy.panels[0]["subpanel"], expected_subpanel)

    def test_menu_actions_record_last_dialog_and_open_distinct_titles(self):
        # Find Control Charts -> Variables Charts for Subgroups actions
        sub_menu = None
        for act in self.win.menuBar().actions():
            if "Stat" in act.text().replace("&", ""):
                for sub in act.menu().actions():
                    if "Control Charts" in sub.text().replace("&", ""):
                        for sub2 in sub.menu().actions():
                            if "Subgroups" in sub2.text():
                                sub_menu = sub2.menu()
        self.assertIsNotNone(sub_menu)
        actions = {a.text().replace("&", ""): a for a in sub_menu.actions() if a.text()}
        seen_titles = {}
        from statcraft.subgroup_control_dialogs import BaseSubgroupChartDialog

        for label in ("Xbar-R…", "Xbar-S…", "Xbar…", "R…", "S…"):
            self.assertIn(label, actions)
            self.win._last_dialog_action = None
            captured_title = []
            orig_exec = BaseSubgroupChartDialog.exec

            def fake_exec(dlg_self):
                captured_title.append(dlg_self.windowTitle())
                return QDialog.DialogCode.Rejected

            with patch.object(BaseSubgroupChartDialog, "exec", fake_exec):
                actions[label].trigger()
            self.assertIsNotNone(self.win._last_dialog_action, f"{label} did not record _last_dialog_action")
            seen_titles[label] = captured_title[0]

        self.assertIn("Xbar Chart", seen_titles["Xbar…"])
        self.assertIn("R Chart", seen_titles["R…"])
        self.assertIn("S Chart", seen_titles["S…"])
        self.assertNotEqual(seen_titles["Xbar…"], seen_titles["Xbar-R…"])
        self.assertNotEqual(seen_titles["R…"], seen_titles["Xbar-R…"])
        self.assertNotEqual(seen_titles["S…"], seen_titles["Xbar-S…"])

    def test_simple_regression_dialog_uses_response_then_predictor(self):
        # Test via mock ProcedureDialog execution on inference_dialog("linear_regression")
        from statcraft.variable_dialogs import ProcedureDialog

        def fake_exec(dlg_self):
            dlg_self.controls["response_index"].setText("Y")
            dlg_self.controls["predictor_index"].setText("X")
            dlg_self.accept_clicked = True
            # Call validate()
            dlg_self.validate()
            return QDialog.DialogCode.Accepted

        with patch.object(ProcedureDialog, "exec", fake_exec):
            self.win.inference_dialog("linear_regression")

        last = self.win.presenter.history[-1]["result"]
        # Y = 2*X -> slope ~ 2.0 (if reversed X vs Y it would be 0.5!)
        slope = last["slope"]
        self.assertAlmostEqual(slope, 2.0, places=5)

    def test_custom_dialogs_commit_active_editor_and_set_last_dialog_action(self):
        from statcraft.subgroup_control_dialogs import BaseSubgroupChartDialog

        item = self.win.table.item(0, 0)
        self.win.table.setCurrentCell(0, 0)
        self.win.table.openPersistentEditor(item)
        editor = next((e for e in self.win.table.findChildren(QLineEdit) if e.parent() is self.win.table.viewport()), None)
        self.assertIsNotNone(editor)
        editor.setText("99")

        with patch.object(BaseSubgroupChartDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            self.win.xbar_r_dialog()
        self.assertIsNotNone(self.win._last_dialog_action)
        self.assertEqual(self.win.presenter.worksheet.columns[0].values[0], 99.0)


if __name__ == "__main__":
    unittest.main()
