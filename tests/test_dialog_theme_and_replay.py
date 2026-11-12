import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STATCRAFT_TESTING", "1")

from PySide6.QtWidgets import QApplication, QWidget, QToolButton, QLabel

from statcraft.model import Worksheet, Column


def _app():
    return QApplication.instance() or QApplication(sys.argv)


class _FakeWindow(QWidget):
    def __init__(self, dark: bool, selected_columns=None):
        super().__init__()
        self._dark_mode = dark
        self._selected_columns = set(selected_columns or ())


class _FakeMainWindow(_FakeWindow):
    def __init__(self, dark: bool, worksheet: Worksheet):
        super().__init__(dark)
        self.presenter = type("_P", (), {"worksheet": worksheet})()


class DialogThemeParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _app()

    def _sheet(self):
        return Worksheet(
            "TestSheet",
            [
                Column("X", "number", [1.0, 2.0, 3.0, 4.0]),
                Column("Y", "number", [2.0, 4.0, 6.0, 8.0]),
                Column("Group", "text", ["A", "A", "B", "B"]),
            ],
        )

    def test_dialog_theme_helper_detects_dark_parent(self):
        from statcraft.dialog_theme import is_dark_active

        dark_win = _FakeWindow(True)
        light_win = _FakeWindow(False)
        self.assertTrue(is_dark_active(dark_win))
        self.assertFalse(is_dark_active(light_win))

    def test_scatter_and_gallery_dialogs_use_dark_theme_in_dark_mode(self):
        from statcraft.variable_dialogs import ScatterDialog, ScatterTypeDialog
        from statcraft.boxplot_dialogs import BoxplotTypeDialog
        from statcraft.dotplot_dialogs import DotplotTypeDialog
        from statcraft.histogram_dialogs import HistogramTypeDialog
        from statcraft.categorical_points_dialogs import CategoricalTypeDialog

        dark_win = _FakeWindow(True)
        ws = self._sheet()

        scatter = ScatterDialog(dark_win, ws, "simple")
        self.assertIn("#18181b", scatter.styleSheet())
        self.assertNotIn("#f8fafc", scatter.styleSheet())
        hints = [lbl for lbl in scatter.findChildren(QLabel) if "Click a Y or X cell" in lbl.text()]
        self.assertTrue(hints and "#a1a1aa" in hints[0].styleSheet())

        for cls, args in (
            (ScatterTypeDialog, (dark_win,)),
            (BoxplotTypeDialog, (dark_win,)),
            (DotplotTypeDialog, (dark_win,)),
            (HistogramTypeDialog, (dark_win,)),
            (CategoricalTypeDialog, ("individual", dark_win)),
        ):
            dlg = cls(*args)
            btns = dlg.findChildren(QToolButton)
            self.assertTrue(btns, f"{cls.__name__} missing tool buttons")
            self.assertIn("#1f1f23", btns[0].styleSheet(), f"{cls.__name__} not dark styled")

    def test_graph_object_dialog_variability_updater_and_frame_footnote_themes(self):
        from statcraft.graph_object_dialog import GraphObjectDialog
        from statcraft.variability_dialog import VariabilityChartDialog
        from statcraft.updater_dialog import CheckForUpdatesDialog
        from statcraft.graph_frame import GraphFrame
        from statcraft.paired_t_dialogs import PairedTOptionsDialog
        from statcraft.two_sample_t_dialogs import TwoSampleTOptionsDialog
        from statcraft.rare_event_control_dialogs import RareEventOptionsDialog

        dark_win = _FakeWindow(True)
        light_win = _FakeWindow(False)
        ws = self._sheet()

        objects = [
            {
                "target": "p0:s0",
                "label": "Points",
                "capabilities": ["color", "marker_size"],
                "defaults": {"color": "#1d4ed8", "marker_size": 5.0},
            }
        ]
        obj_dark = GraphObjectDialog(objects, {}, parent=dark_win)
        self.assertIn("#18181b", obj_dark.styleSheet())
        self.assertIn("#f87171", obj_dark.error.styleSheet())

        var_dark = VariabilityChartDialog(_FakeMainWindow(True, ws), parent=dark_win)
        self.assertIn("#18181b", var_dark.styleSheet())
        self.assertNotIn("background: #f8fafc", var_dark.findChildren(QWidget)[1].styleSheet())

        upd_light = CheckForUpdatesDialog(
            parent=light_win,
            initial_info={"update_available": False, "current_version": "117.0.0"},
        )
        self.assertNotIn("background-color: #0f172a", upd_light.styleSheet())

        # Footnote label in GraphFrame should be themed via _apply_theme_styles
        from statcraft.chart_theme import DARK_THEME, LIGHT_THEME
        chart_dark = QWidget()
        chart_dark.panels = []
        frame_dark = GraphFrame(chart_dark, {"title": "T", "result": {}}, parent=dark_win)
        self.assertIn(DARK_THEME.muted, frame_dark.footnote_label.styleSheet())
        chart_light = QWidget()
        chart_light.panels = []
        frame_light = GraphFrame(chart_light, {"title": "T", "result": {}}, parent=light_win)
        self.assertIn(LIGHT_THEME.muted, frame_light.footnote_label.styleSheet())

        # Subdialog muted headers must not hardcode dark #444 when in dark mode
        p_opt = PairedTOptionsDialog({}, parent=dark_win)
        p_lbl = [l for l in p_opt.findChildren(QLabel) if "Difference =" in l.text()][0]
        self.assertNotIn("#444", p_lbl.styleSheet())

        t_opt = TwoSampleTOptionsDialog({}, parent=dark_win)
        t_lbl = [l for l in t_opt.findChildren(QLabel) if "Difference =" in l.text()][0]
        self.assertNotIn("#444", t_lbl.styleSheet())

        r_opt = RareEventOptionsDialog("G", {}, parent=dark_win)
        r_lbl = [l for l in r_opt.findChildren(QLabel) if "specify a value" in l.text()][0]
        self.assertNotIn("#444", r_lbl.styleSheet())


class DialogReplayAndPreselectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _app()

    def _sheet(self):
        return Worksheet(
            "ReplaySheet",
            [
                Column("Temp", "number", [10.0, 20.0, 30.0, 40.0]),
                Column("Yield", "number", [5.0, 7.0, 9.0, 12.0]),
                Column("Batch", "text", ["A", "A", "B", "B"]),
            ],
        )

    def test_scatter_dialog_filter_reset_and_saved_state(self):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtWidgets import QTableWidgetItem
        from statcraft.variable_dialogs import ScatterDialog, ProcedureDialog

        ProcedureDialog._LAST_DIALOG_STATE.clear()
        ws = self._sheet()
        dlg = ScatterDialog(None, ws, "groups")

        # 1. Variable filter narrows available list
        dlg.var_filter.setText("Yield")
        visible = [
            dlg.available.item(i).text()
            for i in range(dlg.available.count())
            if not dlg.available.item(i).isHidden()
        ]
        self.assertEqual(len(visible), 1)
        self.assertIn("Yield", visible[0])

        # 2. Populate roles/group/labels & validate -> persists across reopen
        dlg.roles.setItem(0, 0, QTableWidgetItem("C2"))
        dlg.roles.setItem(0, 1, QTableWidgetItem("C1"))
        dlg.group_entry.setText("C3-T")
        dlg.labels = {"title": "My Scatter", "x_label": "Temp (C)", "y_label": "Yield (%)"}
        dlg.validate()
        self.assertIsNotNone(dlg.pairs)

        dlg2 = ScatterDialog(None, ws, "groups")
        self.assertEqual(dlg2.roles.item(0, 0).text(), "C2")
        self.assertEqual(dlg2.roles.item(0, 1).text(), "C1")
        self.assertEqual(dlg2.group_entry.text(), "C3-T")
        self.assertEqual(dlg2.labels["title"], "My Scatter")

        # 3. F3 resets roles & labels
        dlg2.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F3, Qt.KeyboardModifier.NoModifier))
        self.assertTrue(dlg2.roles.item(0, 0) is None or not dlg2.roles.item(0, 0).text())
        self.assertEqual(dlg2.group_entry.text(), "")
        self.assertEqual(dlg2.labels["title"], "")

    def test_graph_builder_reset_and_saved_state(self):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeyEvent
        from statcraft.graph_builder_dialog import GraphBuilderDialog
        from statcraft.variable_dialogs import ProcedureDialog

        ProcedureDialog._LAST_DIALOG_STATE.clear()
        ws = self._sheet()
        gb = GraphBuilderDialog(None, ws)
        gb.set_graph_type("scatter")
        gb.assign_columns("response_indices", [1])
        gb.assign_columns("x_index", [0])
        gb.title.setText("Builder Title")
        self.assertTrue(gb.validate())

        gb2 = GraphBuilderDialog(None, ws)
        self.assertEqual(gb2.graph_type, "scatter")
        self.assertEqual(gb2.mapping["response_indices"], [1])
        self.assertEqual(gb2.mapping["x_index"], [0])
        self.assertEqual(gb2.title.text(), "Builder Title")

        gb2.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F3, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(gb2.mapping["response_indices"], [])
        self.assertEqual(gb2.title.text(), "")

    def test_procedure_dialog_preselection_and_clear_validation(self):
        from statcraft.variable_dialogs import ProcedureDialog, resolve_variables

        ProcedureDialog._LAST_DIALOG_STATE.clear()
        ws = self._sheet()
        parent = _FakeWindow(False, selected_columns={0})
        dlg = ProcedureDialog(
            parent,
            "One Sample Test",
            ws,
            [{"key": "vars", "label": "Variables", "multiple": True, "kinds": ("number",)}],
        )
        self.assertIn("C1", dlg.controls["vars"].text())

        with self.assertRaises(ValueError) as ctx:
            resolve_variables("C3", ws, ("number",))
        msg = str(ctx.exception)
        self.assertIn("Batch", msg)
        self.assertIn("numeric", msg.lower())

    def test_edit_last_dialog_preserves_across_find_and_replays_scatter_directly(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QDialog
        from statcraft.modern_app import ModernWindow

        with patch.object(ModernWindow, "find_dialog") as mock_find:
            win = ModernWindow(sandbox_mode=True)
            win._confirm_leave = lambda: True
            sentinel = lambda: None
            win._last_dialog_action = sentinel
            win.find_action.trigger()
            self.assertEqual(mock_find.call_count, 1)
            self.assertEqual(win._last_dialog_action, sentinel)

        with patch("statcraft.modern_app.ScatterTypeDialog") as mock_chooser, \
             patch("statcraft.modern_app.ScatterDialog") as mock_scatter:
            mock_chooser.return_value.exec.return_value = QDialog.DialogCode.Accepted
            mock_chooser.return_value.mode = "regression"
            mock_scatter.return_value.exec.return_value = QDialog.DialogCode.Rejected
            win.graph("scatter")
            self.assertEqual(mock_chooser.call_count, 1)
            self.assertEqual(mock_scatter.call_count, 1)

            win.edit_last_dialog()
            self.assertEqual(mock_chooser.call_count, 1)
            self.assertEqual(mock_scatter.call_count, 2)
        win.close()


if __name__ == "__main__":
    unittest.main()
