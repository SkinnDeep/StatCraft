import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STATCRAFT_TESTING", "1")

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from statcraft.graph_frame import GraphFrame
from statcraft.modern_charts import ChartWidget
from statcraft.svg_html_export import export_widget_to_svg_bytes


def _app():
    return QApplication.instance() or QApplication(sys.argv)


class ExportAndClipboardFidelityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _app()

    def tearDown(self):
        cb = QApplication.clipboard()
        if cb is not None:
            cb.clear()
        QApplication.processEvents()

    def _sample_frame(self):
        entry = {
            "title": "Scatterplot of Yield vs Temp",
            "graph_presentation": {
                "title": "Yield vs Temp",
                "title_enabled": True,
                "subtitle": "Batch A Calibration",
                "subtitle_enabled": True,
                "footnote": "Source: Lab Log",
                "footnote_enabled": True,
            },
            "result": {
                "analysis": "scatter",
                "title": "Yield vs Temp",
                "xlabel": "Temp",
                "ylabel": "Yield",
                "series": [
                    {
                        "label": "Data",
                        "x": [10.0, 20.0, 30.0],
                        "y": [4.0, 7.0, 9.0],
                        "mode": "markers",
                    }
                ],
            },
        }
        chart = ChartWidget(entry)
        chart.resize(520, 320)
        frame = GraphFrame(chart, entry)
        frame.resize(560, 400)
        return frame

    def test_graph_frame_capture_is_hidpi_2x(self):
        frame = self._sample_frame()
        pix = frame.capture()
        self.assertGreaterEqual(pix.devicePixelRatio(), 2.0)
        expected_w = int(round(frame.width() * pix.devicePixelRatio()))
        expected_h = int(round(frame.height() * pix.devicePixelRatio()))
        self.assertEqual(pix.size(), QSize(expected_w, expected_h))

    def test_graph_frame_svg_export_includes_title_subtitle_and_footnote(self):
        frame = self._sample_frame()
        svg_text = export_widget_to_svg_bytes(frame).decode("utf-8")
        self.assertIn("<svg", svg_text)
        self.assertIn("Yield vs Temp", svg_text)
        self.assertIn("Batch A Calibration", svg_text)
        self.assertIn("Source: Lab Log", svg_text)

    def test_table_clipboard_sets_both_tsv_and_html_mime_data(self):
        from statcraft.modern_app import set_table_clipboard

        set_table_clipboard(["Factor", "Value"], [["Temp", "25.4"], ["Yield", "88.2"]])
        mime = QApplication.clipboard().mimeData()
        self.assertTrue(mime.hasText())
        self.assertIn("Factor\tValue", mime.text())
        self.assertIn("Temp\t25.4", mime.text())
        self.assertTrue(mime.hasHtml())
        html_payload = mime.html()
        self.assertIn("<table", html_payload)
        self.assertIn("<th", html_payload)
        self.assertIn("Factor", html_payload)
        self.assertIn("<td", html_payload)
        self.assertIn("88.2", html_payload)


if __name__ == "__main__":
    unittest.main()
