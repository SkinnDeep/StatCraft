"""Unit tests for SVG Vector and Clean Standalone HTML Report Exporter."""
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication, QLabel
from statcraft.svg_html_export import export_widget_to_svg_bytes, copy_widget_svg_to_clipboard, export_session_to_html

_app = QApplication.instance() or QApplication([])


class TestSvgAndHtmlExport(unittest.TestCase):
    def test_svg_export_to_bytes(self):
        label = QLabel("Test StatCraft Chart")
        label.resize(300, 200)
        svg_bytes = export_widget_to_svg_bytes(label)
        self.assertGreater(len(svg_bytes), 0)
        svg_text = svg_bytes.decode("utf-8")
        self.assertIn("<svg", svg_text)
        self.assertIn("</svg>", svg_text)

    def test_copy_svg_to_clipboard(self):
        label = QLabel("Clipboard Test")
        label.resize(250, 150)
        success = copy_widget_svg_to_clipboard(label)
        self.assertTrue(success)

    def test_export_session_to_html(self):
        history = [
            {
                "title": "Multiple Regression",
                "result": {"analysis": "multiple_regression", "r_squared": 0.88, "p_value": 0.002}
            },
            {
                "title": "Capability Report",
                "result": {"analysis": "capability", "cp": 1.45, "cpk": 1.38, "ppm_total": 35.0}
            }
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "report.html"
            html_text = export_session_to_html(history, worksheet_name="Production Data", output_path=str(out_file))

            self.assertTrue(out_file.exists())
            self.assertIn("StatCraft Statistical Session Report", html_text)
            self.assertIn("Production Data", html_text)
            self.assertIn("Multiple Regression", html_text)
            self.assertIn("Executive Brief", html_text)
            self.assertIn("1.3800", html_text)


if __name__ == "__main__":
    import os
    runner = unittest.TextTestRunner()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestSvgAndHtmlExport)
    result = runner.run(suite)
    os._exit(0 if result.wasSuccessful() else 1)
