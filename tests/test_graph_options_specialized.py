import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STATCRAFT_TESTING", "1")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(sys.argv)


def _render_image(widget, w=640, h=420) -> QImage:
    widget.resize(w, h)
    img = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.white)
    widget.render(img)
    return img


class TestGraphOptionsSpecialized(unittest.TestCase):
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
        self.win.presenter._results_dirty = False
        self.win.presenter.dirty = False
        self.win.close()

    def test_specialized_charts_apply_limits_grid_and_ref_lines(self):
        from statcraft.fitted_line_plot_chart import FittedLinePlotChartWidget
        from statcraft.graph_frame import GraphFrame
        from statcraft.imr_chart import IMRChartWidget
        from statcraft.run_chart_plot import RunChartWidget
        from statcraft.time_series_chart import TimeSeriesChartWidget

        flp_entry = self.win.presenter.fitted_line_plot(response_index=1, predictor_index=0)
        flp = FittedLinePlotChartWidget(flp_entry, parent=self.win)
        frame = GraphFrame(flp, flp_entry, parent=self.win)
        img_default = _render_image(flp)

        # Apply Y reference line + custom Y limits + hide grid -> inner chart pixels must change visibly
        frame.apply({
            "x_min": 0.0,
            "x_max": 12.0,
            "y_min": -10.0,
            "y_max": 30.0,
            "y_ref_line": "10",
            "x_ref_line": "5",
            "grid_enabled": False,
        })
        img_custom = _render_image(flp)
        self.assertNotEqual(
            bytes(img_default.constBits()),
            bytes(img_custom.constBits()),
            "FittedLinePlotChartWidget ignored GraphFrame axis limits / grid / ref lines!",
        )

        # Same check directly on TimeSeriesChartWidget, IMRChartWidget, and RunChartWidget
        ts_entry = self.win.presenter.trend_analysis({"series_index": 2, "model": "linear"})
        ts = TimeSeriesChartWidget(ts_entry, parent=self.win)
        ts_frame = GraphFrame(ts, ts_entry, parent=self.win)
        ts_a = _render_image(ts)
        ts_frame.apply({"y_min": 5.0, "y_max": 15.0, "y_ref_line": "10.0", "grid_enabled": False})
        ts_b = _render_image(ts)
        self.assertNotEqual(bytes(ts_a.constBits()), bytes(ts_b.constBits()), "TimeSeriesChartWidget ignored GraphFrame options!")

        imr_entry = self.win.presenter.imr_chart({"variables": [2]})
        imr = IMRChartWidget(imr_entry, parent=self.win)
        imr_frame = GraphFrame(imr, imr_entry, parent=self.win)
        imr_a = _render_image(imr)
        imr_frame.apply({"y_min": 8.0, "y_max": 12.0, "y_ref_line": "10.0"})
        imr_b = _render_image(imr)
        self.assertNotEqual(bytes(imr_a.constBits()), bytes(imr_b.constBits()), "IMRChartWidget ignored GraphFrame options!")

        rc_entry = self.win.presenter.run_chart(2, subgroup_size=2)
        rc = RunChartWidget(rc_entry, parent=self.win)
        rc_frame = GraphFrame(rc, rc_entry, parent=self.win)
        rc_a = _render_image(rc)
        rc_frame.apply({"y_min": 5.0, "y_max": 15.0, "y_ref_line": "10.1"})
        rc_b = _render_image(rc)
        self.assertNotEqual(bytes(rc_a.constBits()), bytes(rc_b.constBits()), "RunChartWidget ignored GraphFrame options!")

    def test_graph_options_pane_disables_cartesian_scales_for_non_cartesian_analyses(self):
        cap_entry = self.win.presenter.normal_sixpack({
            "single_column": True,
            "column_name": 2,
            "subgroup_size": 2,
            "lsl": 9.0,
            "usl": 11.0,
        })
        self.win.graph_options_pane.load_entry(cap_entry)
        # Normal capability sixpack has multiple non-shared panels -> X/Y scale limits must be disabled cleanly
        self.assertFalse(self.win.graph_options_pane.controls["x_min"].isEnabled())
        self.assertFalse(self.win.graph_options_pane.controls["y_min"].isEnabled())
        self.assertTrue(self.win.graph_options_pane.controls["title"].isEnabled())

        # While Fitted Line Plot keeps X/Y scale limits enabled
        flp_entry = self.win.presenter.fitted_line_plot(response_index=1, predictor_index=0)
        self.win.graph_options_pane.load_entry(flp_entry)
        self.assertTrue(self.win.graph_options_pane.controls["x_min"].isEnabled())
        self.assertTrue(self.win.graph_options_pane.controls["y_min"].isEnabled())


if __name__ == "__main__":
    unittest.main()
