import os
import sys
import unittest

from PySide6.QtCore import Qt, QPointF, QPoint, QRect
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from statcraft.modern_app import ModernWindow
from statcraft.modern_charts import ChartWidget


class TestRound2ChartInteractionAndFill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _scatter_entry(self):
        return {
            "title": "Scatterplot of Y vs X",
            "result": {
                "graph": "scatter",
                "xlabel": "X",
                "ylabel": "Y",
                "count": 4,
                "missing": 0,
                "series": [
                    {"label": "Group A", "x": [1.0, 2.0, 3.0, 4.0], "y": [2.0, 4.0, 6.0, 8.0], "connect": True},
                    {"label": "Group B", "x": [1.0, 2.0, 3.0, 4.0], "y": [8.0, 6.0, 4.0, 2.0], "connect": True},
                ],
            },
        }

    def test_2d_chart_zoom_pan_and_reset(self):
        chart = ChartWidget(self._scatter_entry())
        chart.resize(680, 420)
        chart.show()
        chart.grab()
        self.app.processEvents()

        self.assertTrue(hasattr(chart, "_has_2d_zoom"))
        self.assertFalse(chart._has_2d_zoom())
        meta = chart._zoom2d_meta.get(0)
        self.assertIsNotNone(meta)
        plot = meta["plot"]
        orig_x = meta["xb"]
        orig_y = meta["yb"]

        center = QPointF(plot.center())
        wheel = QWheelEvent(
            center,
            center,
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        chart.wheelEvent(wheel)
        chart.grab()
        self.app.processEvents()

        self.assertTrue(chart._has_2d_zoom())
        zlimits = chart._zoom2d_limits[0]
        self.assertLess(zlimits["x"][1] - zlimits["x"][0], orig_x[1] - orig_x[0])
        self.assertLess(zlimits["y"][1] - zlimits["y"][0], orig_y[1] - orig_y[0])

        # Pan right/up should shift limits
        x0_before = zlimits["x"][0]
        chart._pan_2d_panel(0, -40.0, 25.0)
        self.assertGreater(chart._zoom2d_limits[0]["x"][0], x0_before)

        chart.reset_2d_zoom()
        self.assertFalse(chart._has_2d_zoom())
        chart.close()
        chart.deleteLater()

    def test_legend_click_toggles_series_visibility(self):
        chart = ChartWidget(self._scatter_entry())
        chart.resize(680, 420)
        chart.show()
        chart.grab()
        self.app.processEvents()

        # Find legend hit region for series 0 (stored in multi_scatter legend)
        self.assertTrue(hasattr(chart, "_legend_hit_rects"))
        rect_s0 = chart._legend_hit_rects.get((0, 0))
        self.assertIsNotNone(rect_s0)

        pos = QPointF(rect_s0.center())
        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            pos,
            pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        chart.mousePressEvent(press)
        chart.grab()
        self.app.processEvents()

        self.assertTrue(chart.is_series_legend_hidden(0, 0))
        # Clicking the same legend rect again must unhide it (strikethrough label stayed clickable)
        rect_s0_after = chart._legend_hit_rects.get((0, 0))
        self.assertIsNotNone(rect_s0_after)
        pos2 = QPointF(rect_s0_after.center())
        press2 = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            pos2,
            pos2,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        chart.mousePressEvent(press2)
        self.assertFalse(chart.is_series_legend_hidden(0, 0))
        chart.close()
        chart.deleteLater()

    def test_worksheet_drag_fill_handle_numeric_and_text_undoable(self):
        win = ModernWindow(None)
        win.show()
        self.app.processEvents()
        p = win.presenter
        p.set_cell(0, 0, "1")
        p.set_cell(1, 0, "2")
        p.set_column_type(1, "text")
        p.set_cell(0, 1, "Sample 1")
        p.set_cell(1, 1, "Sample 2")
        win.refresh()
        self.app.processEvents()

        # Select (0..1, C1) and verify fill handle rect
        win.table.setRangeSelected(
            win.table.selectedRanges()[0] if win.table.selectedRanges() else None, False
        ) if win.table.selectedRanges() else None
        from PySide6.QtWidgets import QTableWidgetSelectionRange
        win.table.setCurrentCell(0, 0)
        win.table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 0), True)
        self.app.processEvents()

        self.assertTrue(hasattr(win.table, "fill_handle_rect"))
        hrect = win.table.fill_handle_rect()
        self.assertIsInstance(hrect, QRect)
        self.assertFalse(hrect.isNull())

        # Drag fill via real mouse events on fill handle down to row 4
        target_vr = win.table.visualRect(win.table.model().index(4, 0))
        start_pt = QPointF(hrect.center())
        end_pt = QPointF(target_vr.center())
        win.table.mousePressEvent(
            QMouseEvent(QMouseEvent.Type.MouseButtonPress, start_pt, start_pt, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        )
        win.table.mouseMoveEvent(
            QMouseEvent(QMouseEvent.Type.MouseMove, end_pt, end_pt, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        )
        win.table.mouseReleaseEvent(
            QMouseEvent(QMouseEvent.Type.MouseButtonRelease, end_pt, end_pt, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        )
        self.app.processEvents()
        self.assertEqual(p.worksheet.columns[0].values[:5], [1.0, 2.0, 3.0, 4.0, 5.0])
        # Undo in one step
        win.undo()
        self.assertEqual(p.worksheet.columns[0].values[:5], [1.0, 2.0])

        # Text sequence drag fill
        win.fill_range_from_handle(0, 1, 1, 1, 3)
        self.assertEqual(p.worksheet.columns[1].values[:4], ["Sample 1", "Sample 2", "Sample 3", "Sample 4"])

        win.presenter.dirty = False
        win.close()
        win.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
