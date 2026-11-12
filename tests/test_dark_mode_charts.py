import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STATCRAFT_TESTING", "1")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(sys.argv)


def _render_corner_color(widget, x=2, y=2) -> QColor:
    widget.resize(480, 320)
    img = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    widget.render(img)
    return QColor(img.pixel(x, y))


class TestDarkModeCharts(unittest.TestCase):
    def setUp(self):
        from statcraft.modern_app import ModernWindow

        self.win = ModernWindow()
        ws = self.win.presenter.worksheet
        ws.columns[0].name = "X"
        ws.columns[0].kind = "number"
        ws.columns[0].values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        ws.columns[1].name = "Y"
        ws.columns[1].kind = "number"
        ws.columns[1].values = [2.1, 3.9, 6.2, 8.0, 10.3, 12.1, 14.0, 15.8, 18.2, 19.9]
        ws.columns[2].name = "M"
        ws.columns[2].kind = "number"
        ws.columns[2].values = [10.1, 10.2, 9.9, 10.0, 10.3, 10.4, 9.8, 10.1, 10.2, 9.7]
        self.win.refresh()

    def tearDown(self):
        self.win.set_dark_mode(False)
        self.win.presenter._results_dirty = False
        self.win.presenter.dirty = False
        self.win.close()

    def test_dark_mode_renders_dark_canvas_across_chart_widgets(self):
        from statcraft.capability_chart import CapabilityPlotWidget
        from statcraft.fitted_line_plot_chart import FittedLinePlotChartWidget
        from statcraft.graph_frame import GraphFrame
        from statcraft.modern_charts import ChartWidget
        from statcraft.regression_residual_chart import RegressionResidualChartWidget
        from statcraft.run_chart_plot import RunChartWidget
        from statcraft.sixpack_chart import CapabilitySixpackWidget
        from statcraft.svg_html_export import export_widget_to_svg_bytes
        from statcraft.time_series_chart import TimeSeriesChartWidget

        hist_entry = self.win.presenter.histogram_graphs([0])
        flp_entry = self.win.presenter.fitted_line_plot(response_index=1, predictor_index=0)
        cap_entry = self.win.presenter.normal_capability(index=2, lsl=9.0, usl=11.0)
        ts_entry = self.win.presenter.trend_analysis({"series_index": 2, "model": "linear"})
        rc_entry = self.win.presenter.run_chart(2, subgroup_size=2)
        ctrl_entry = self.win.presenter.subgroup_control_chart(chart_type="xbar_r", stacked=True, response_index=2, subgroup_size=2)

        widgets = [
            ChartWidget(hist_entry, parent=self.win),
            FittedLinePlotChartWidget(flp_entry, parent=self.win),
            RegressionResidualChartWidget(flp_entry, parent=self.win),
            CapabilityPlotWidget(cap_entry, parent=self.win),
            CapabilitySixpackWidget(cap_entry, parent=self.win),
            TimeSeriesChartWidget(ts_entry, parent=self.win),
            RunChartWidget(rc_entry, parent=self.win),
            ChartWidget(ctrl_entry, parent=self.win),
        ]

        # Check Dark Mode ON
        self.win.set_dark_mode(True)
        for w in widgets:
            c = _render_corner_color(w)
            self.assertLess(
                c.lightness(),
                80,
                f"{type(w).__name__} stayed bright ({c.name()}) in Dark Mode!",
            )

        # SVG export still produces valid non-empty SVG bytes
        svg_bytes = export_widget_to_svg_bytes(widgets[1])
        self.assertIn(b"<svg", svg_bytes)

        # GraphFrame + GraphOptionsPane dark mode
        frame = GraphFrame(widgets[0], hist_entry, parent=self.win)
        frame.update_selection_strip(3)
        self.win.graph_options_pane.load_entry(hist_entry)
        self.assertIn("#18181b", self.win.graph_options_pane.styleSheet().lower())
        self.assertIn("#1f1f23", frame.selection_strip.styleSheet().lower())

        # Toggle back to Light Mode -> white canvas restored
        self.win.set_dark_mode(False)
        for w in widgets[:3]:
            c = _render_corner_color(w)
            self.assertGreater(
                c.lightness(),
                220,
                f"{type(w).__name__} did not restore light canvas ({c.name()})!",
            )


if __name__ == "__main__":
    unittest.main()
