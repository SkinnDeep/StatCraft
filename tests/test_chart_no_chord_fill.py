import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STATCRAFT_TESTING", "1")

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication(sys.argv)


def _render_image(widget, width=820, height=580):
    widget.resize(width, height)
    img = QImage(width, height, QImage.Format.Format_ARGB32)
    img.fill(QColor("#ffffff"))
    widget.render(img)
    return img


def _count_matching_pixels(img: QImage, target_hex: str, x0=0, y0=0, x1=None, y1=None, tol=8):
    target = QColor(target_hex)
    tr, tg, tb = target.red(), target.green(), target.blue()
    x1 = img.width() if x1 is None else min(img.width(), x1)
    y1 = img.height() if y1 is None else min(img.height(), y1)
    count = 0
    for y in range(max(0, y0), y1):
        for x in range(max(0, x0), x1):
            c = img.pixelColor(x, y)
            if abs(c.red() - tr) <= tol and abs(c.green() - tg) <= tol and abs(c.blue() - tb) <= tol:
                count += 1
    return count


class TestChartNoChordFill(unittest.TestCase):
    def test_regression_residual_histogram_curve_does_not_fill_chord(self):
        from statcraft.regression_residual_chart import RegressionResidualChartWidget

        # Tight cluster near 0 with a symmetric peak so the red normal PDF curve arches
        # well above some side bins; without NoBrush before drawPath(), the curve path
        # gets chord-filled solid #93c5fd!
        resids = [-2.5, -1.5, -0.5, -0.1, 0.0, 0.0, 0.1, 0.5, 1.5, 2.5]
        entry = {
            "title": "Residuals",
            "result": {
                "analysis": "multiple_regression",
                "response_name": "Y",
                "residuals": resids,
                "fitted": list(range(len(resids))),
                "standardized_residuals": [v / 1.4 for v in resids],
                "residual_stdev": 1.4,
            },
        }
        w = RegressionResidualChartWidget(entry)
        img = _render_image(w, 800, 600)
        # Histogram panel is bottom-left quadrant (x: 20..380, y: 310..570).
        # Inspect high in the curve arch above empty space or compare upper area vs expected.
        # Specifically inspect the line between endpoints of the normal curve (bottom area):
        # if filled with #93c5fd, huge regions inside the normal arch fill with #93c5fd.
        # Let's count #93c5fd pixels in the middle-upper region of the Histogram panel
        # where bars are tall ONLY near 0, yet the arch spans wider: actually test an asymmetric bimodal
        # residual distribution where middle bin is 0 so the peak arch bridges an empty gap!
        bimodal = [-3.0] * 8 + [-2.9] * 4 + [0.0] * 1 + [2.9] * 4 + [3.0] * 8
        entry["result"]["residuals"] = bimodal
        entry["result"]["fitted"] = list(range(len(bimodal)))
        entry["result"]["standardized_residuals"] = [v / 2.5 for v in bimodal]
        w2 = RegressionResidualChartWidget(entry)
        img2 = _render_image(w2, 800, 600)
        # In the empty gap around residual 0 in the bottom-left quadrant, bar count is low/zero,
        # whereas normal PDF bell peaks in the middle -> chord fill paints #93c5fd across empty gap!
        mid_x0, mid_x1 = 165, 235
        mid_y0, mid_y1 = 440, 520
        blue_fill_pixels = _count_matching_pixels(img2, "#93c5fd", mid_x0, mid_y0, mid_x1, mid_y1, tol=10)
        # Normal bars around 0 are at most ~12px high near bottom (550), so middle band y=440..520
        # should have virtually zero #93c5fd pixels (only empty space + red curve + bar outline if any).
        self.assertLess(blue_fill_pixels, 150, f"Detected unexpected #93c5fd chord-fill in histogram gap: {blue_fill_pixels} pixels")

    def test_capability_sixpack_curves_do_not_fill_chord(self):
        from statcraft.sixpack_chart import CapabilitySixpackWidget

        # Bimodal data creates empty center bins below the fitted normal curves -> chord fill
        # paints #DBEAFE under the Within/Overall curves across empty mid-histogram!
        obs = [9.0] * 15 + [11.0] * 15
        entry = {
            "result": {
                "analysis": "capability_sixpack_normal",
                "column_name": "Yield",
                "observations": obs,
                "subgroup_size": 5,
                "subgroup_means": [9.0, 9.0, 9.0, 11.0, 11.0, 11.0],
                "subgroup_ranges": [0.2] * 6,
                "xbar_cl": 10.0,
                "xbar_ucl": 11.5,
                "xbar_lcl": 8.5,
                "r_cl": 0.2,
                "r_ucl": 0.5,
                "r_lcl": 0.0,
                "mean": 10.0,
                "stdev_within": 0.4,
                "stdev_overall": 1.0,
                "lsl": 7.0,
                "usl": 13.0,
                "target": 10.0,
            }
        }
        w = CapabilitySixpackWidget(entry)
        img = _render_image(w, 960, 660)
        # Bottom-middle panel is Capability Histogram (~x: 340..620, y: 360..620).
        # The empty center around mean=10 has 0-count bars, but the normal curve peaks right above it!
        center_fill = _count_matching_pixels(img, "#DBEAFE", 455, 440, 505, 560, tol=10)
        self.assertLess(center_fill, 120, f"Detected #DBEAFE chord-fill under sixpack normal curve: {center_fill} pixels")

    def test_multivariate_item_analysis_overlay_line_does_not_fill_blue(self):
        from statcraft.multivariate_chart import MultivariateChartWidget

        entry = {
            "result": {
                "analysis": "item_analysis",
                "title": "Item Analysis",
                "cronbach_alpha": 0.75,
                "item_stats": [
                    {"item": "Q1", "item_adj_total_corr": 0.2, "alpha_deleted": 0.85},
                    {"item": "Q2", "item_adj_total_corr": 0.2, "alpha_deleted": 0.65},
                    {"item": "Q3", "item_adj_total_corr": 0.2, "alpha_deleted": 0.90},
                    {"item": "Q4", "item_adj_total_corr": 0.2, "alpha_deleted": 0.85},
                ],
            }
        }
        w = MultivariateChartWidget(entry)
        img = _render_image(w, 800, 560)
        # Upper portion of plot (y: 110..260, where item corr bars=0.2 stay near bottom!)
        # should have zero BLUE_FILL (#1f77b4) pixels except legend box (right - 220).
        fill_pixels = _count_matching_pixels(img, "#1f77b4", 120, 120, 480, 260, tol=10)
        self.assertEqual(fill_pixels, 0, f"Detected BLUE_FILL chord fill on alpha_deleted line: {fill_pixels} pixels")

    def test_source_resets_no_brush_before_open_drawpath(self):
        # Verify structural fix across all 6 files for open polyline drawPath calls.
        targets = [
            ("statcraft/regression_residual_chart.py", "p.drawPath(path)"),
            ("statcraft/sixpack_chart.py", "painter.drawPath(path_w)"),
            ("statcraft/sixpack_chart.py", "painter.drawPath(path_o)"),
            ("statcraft/control_chart_builder_chart.py", "p.drawPath(path)"),
            ("statcraft/rare_event_control_chart.py", "painter.drawPath(path_series)"),
            ("statcraft/time_weighted_control_chart.py", "painter.drawPath(path_cp)"),
            ("statcraft/time_weighted_control_chart.py", "painter.drawPath(path_cm)"),
            ("statcraft/multivariate_chart.py", "painter.drawPath(path)"),
        ]
        for rel_path, call in targets:
            with open(rel_path, encoding="utf-8") as fh:
                lines = fh.readlines()
            found = False
            for idx, line in enumerate(lines):
                if call in line:
                    window = "".join(lines[max(0, idx - 8):idx + 1])
                    # Note: multivariate_chart line 742 is closed triangle (closeSubpath)
                    if "closeSubpath" in window:
                        continue
                    found = True
                    self.assertIn(
                        "NoBrush",
                        window,
                        f"{rel_path}:{idx+1} calls `{call}` without resetting Qt.BrushStyle.NoBrush nearby",
                    )
            self.assertTrue(found, f"Did not find `{call}` in {rel_path}")


if __name__ == "__main__":
    unittest.main()
