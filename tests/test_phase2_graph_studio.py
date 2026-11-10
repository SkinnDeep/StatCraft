import os
import sys
import unittest
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainterPath
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.expanded_graphs import compute as compute_expanded_graph
from statcraft.graph_builder import ALL_TYPES, TYPES, compute_builder
from statcraft.graph_builder_dialog import GraphBuilderDialog
from statcraft.graph_frame import GraphFrame
from statcraft.graph_options_pane import GraphOptionsPane
from statcraft.graph_presentation import parse_ref_lines, validate_presentation
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.modern_charts import ChartWidget
from statcraft.modern_expanded_charts import ExpandedChartWidget

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestPhase2GraphStudio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_presentation_overlays_and_validation(self):
        self.assertEqual(parse_ref_lines("5, 10; 15.5"), [5.0, 10.0, 15.5])
        with self.assertRaises(ValueError):
            validate_presentation({"y_ref_line": "10, bad"})
        with self.assertRaises(ValueError):
            validate_presentation({"x_log": "yes"})

        valid = validate_presentation({
            "x_ref_line": "2, 4",
            "y_ref_line": "50, 75",
            "x_log": True,
            "y_log": True,
            "show_data_labels": True,
            "show_mean_line": True,
        })
        self.assertTrue(valid["x_log"])
        self.assertTrue(valid["show_mean_line"])

    def test_graph_options_pane_and_chart_render_overlays(self):
        ws = Worksheet("GraphTest", [
            Column("X", "number", [1.0, 2.0, 5.0, 10.0]),
            Column("Y", "number", [10.0, 25.0, 50.0, 100.0]),
        ])
        p = Presenter()
        p.worksheet = ws
        entry = p.scatter_plot(0, 1, "simple")
        entry["graph_presentation"] = {
            "x_ref_line": "3.0",
            "y_ref_line": "40.0",
            "x_log": True,
            "y_log": True,
            "show_mean_line": True,
            "show_data_labels": True,
        }

        chart = ChartWidget(entry)
        frame = GraphFrame(chart, entry)
        self.assertEqual(chart.annotation_x_ref, [3.0])
        self.assertEqual(chart.annotation_y_ref, [40.0])
        self.assertTrue(chart.annotation_x_log)
        self.assertTrue(chart.annotation_y_log)
        self.assertTrue(chart.annotation_data_labels)
        self.assertTrue(chart.annotation_mean_line)

        pane = GraphOptionsPane()
        pane.load_entry(entry)
        self.assertEqual(pane.controls["x_ref_line"].text(), "3.0")
        self.assertTrue(pane.controls["show_mean_line"].isChecked())
        self.assertTrue(pane.controls["show_data_labels"].isChecked())
        self.assertFalse(frame.capture().isNull())

    def test_wafer_plot_catalog_and_render(self):
        ws = Worksheet("Wafer", [
            Column("DieX", "number", [1.0, 2.0, 1.0, 2.0]),
            Column("DieY", "number", [1.0, 1.0, 2.0, 2.0]),
            Column("Yield", "number", [99.1, 84.5, 92.0, 76.4]),
        ])
        res = compute_expanded_graph("wafer_plot", ws, [0, 1, 2])
        self.assertEqual(res["panels"][0]["kind"], "wafer")
        self.assertEqual(len(res["panels"][0]["dies"]), 4)

        chart = ExpandedChartWidget({"title": "Wafer Map", "result": res})
        frame = GraphFrame(chart, {"title": "Wafer Map", "result": res})
        self.assertIsNone(chart.error)
        self.assertFalse(frame.capture().isNull())

    def test_extended_graph_builder_gallery_and_preview(self):
        ws = Worksheet("Extended", [
            Column("DieX", "number", [1.0, 2.0, 3.0, 1.0, 2.0, 3.0]),
            Column("DieY", "number", [1.0, 1.0, 1.0, 2.0, 2.0, 2.0]),
            Column("Yield", "number", [95.0, 88.0, 91.0, 85.0, 97.0, 79.0]),
            Column("Lot", "text", ["A", "A", "B", "B", "C", "C"]),
        ])
        self.assertEqual(len(TYPES), 9)
        self.assertGreaterEqual(len(ALL_TYPES), 21)

        _, _, wafer_res = compute_builder(ws, graph_type="wafer_plot", x_index=0, response_indices=[1, 2])
        self.assertEqual(wafer_res["panels"][0]["kind"], "wafer")

        _, _, pie_res = compute_builder(ws, graph_type="pie_chart", response_indices=[3])
        self.assertEqual(pie_res["panels"][0]["kind"], "pie")

        dlg = GraphBuilderDialog(None, ws)
        self.assertEqual(dlg.gallery.count(), 9)
        dlg.show_all_check.setChecked(True)
        self.assertEqual(dlg.gallery.count(), len(ALL_TYPES))
        dlg.set_graph_type("pie_chart")
        dlg.assign_columns("response_indices", [3])
        self.assertTrue(dlg.update_preview())
        self.assertFalse(dlg.preview_frame.capture().isNull())
        dlg.close()

    def test_brushing_indicator_id_hover_and_context_menu(self):
        ws = Worksheet("Brush", [
            Column("Temp", "number", [10.0, 20.0, 30.0]),
            Column("Yield", "number", [80.0, 90.0, 95.0]),
            Column("Batch", "text", ["Lot-01", "Lot-02", "Lot-03"]),
        ])
        win = ModernWindow(sandbox_mode=True)
        win._confirm_leave = lambda: True
        win.presenter.worksheet = ws
        entry = win.presenter.scatter_plot(0, 1, "simple")
        win.refresh()
        win.show_result(entry)

        # Hover with ID column attached
        chart = win._active_chart_widget
        chart.id_column_info = ("Batch", ws.columns[2].values)
        path = QPainterPath()
        path.addRect(QRectF(0, 0, 20, 20))
        chart.hover_regions.append((path, {"text": "Temp: 20\nYield: 90", "row": 2}))
        tooltip = chart.hover_text_at(QPointF(10, 10))
        self.assertIn("ID (Batch): Lot-02", tooltip)

        # Brushing indicator creation & context menu actions
        win._brushed_rows = [1, 3]
        win.create_indicator_from_brushed_dialog(rows=[1, 3], name="Outlier_Flag")
        self.assertEqual(win.presenter.worksheet.columns[-1].name, "Outlier_Flag")
        self.assertEqual(win.presenter.worksheet.columns[-1].values, [1.0, 0.0, 1.0])

        menu = win.build_output_context_menu(entry)
        labels = [a.text() for a in menu.actions()]
        self.assertIn("Set ID Column for Hover…", labels)
        self.assertIn("Rename Graph…", labels)
        self.assertIn("Create Indicator Variable from Selection…", labels)
        self.assertIn("wafer_plot", win.graph_actions)

        win.close()


if __name__ == "__main__":
    unittest.main()
