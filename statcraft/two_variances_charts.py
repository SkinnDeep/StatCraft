"""Qt Chart widgets for Two-Sample Variances (0255-2VARIANCESGRAPHS.MDF)."""
import math
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath
from PySide6.QtWidgets import QWidget
from .chart_theme import chart_painter


class TwoVariancesSummaryPlotWidget(QWidget):
    """StatCraft Two-Sample Variances Summary Plot."""

    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.error = None
        self.setMinimumSize(600, 360)

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        rect = self.rect()
        painter.fillRect(rect, QColor("#FFFFFF"))

        res = self.entry.get("result", {})
        s1 = res.get("sample1", {})
        s2 = res.get("sample2", {})
        name1 = s1.get("name", "Sample 1")
        name2 = s2.get("name", "Sample 2")
        conf = res.get("confidence_level", 95.0)
        use_normal = res.get("use_normal_distribution", True)
        f_test = res.get("f_test", {})

        # Title
        painter.setPen(QColor("#111827"))
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        painter.drawText(QRectF(20, 10, rect.width() - 40, 24), Qt.AlignmentFlag.AlignCenter, f"Test for Two Variances: {name1}, {name2}")

        # Subtitle
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Normal))
        painter.setPen(QColor("#4B5563"))
        sub = f"{conf:g}% CI for StDevs (F Test)" if use_normal else f"{conf:g}% CI for StDevs"
        painter.drawText(QRectF(20, 32, rect.width() - 40, 20), Qt.AlignmentFlag.AlignCenter, sub)

        # Plot area
        left = 90
        plot_w = int((rect.width() - 120) * 0.70)
        right = left + plot_w
        top = 65
        bottom = rect.height() - 50

        # Right box for test results
        box_left = right + 20
        box_right = rect.width() - 20
        box_top = top + 10
        box_bottom = bottom - 20

        # Draw Test box
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.setBrush(QBrush(QColor("#F8FAFC")))
        painter.drawRoundedRect(QRectF(box_left, box_top, box_right - box_left, box_bottom - box_top), 4, 4)

        painter.setPen(QColor("#1E293B"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(box_left + 10, box_top + 10, box_right - box_left - 20, 20), Qt.AlignmentFlag.AlignLeft, "Test")

        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))
        painter.setPen(QColor("#475569"))
        y_cursor = box_top + 34

        f_stat = f_test.get("statistic", 0.0)
        f_p = f_test.get("p_value", 1.0)
        painter.drawText(QRectF(box_left + 10, y_cursor, box_right - box_left - 20, 18), Qt.AlignmentFlag.AlignLeft, f"F-Statistic: {f_stat:.3f}")
        y_cursor += 20
        painter.drawText(QRectF(box_left + 10, y_cursor, box_right - box_left - 20, 18), Qt.AlignmentFlag.AlignLeft, f"P-Value: {f_p:.3f}")
        y_cursor += 20

        bonett = res.get("bonett")
        if bonett and not use_normal:
            b_stat = bonett.get("statistic", 0.0)
            b_p = bonett.get("p_value", 1.0)
            painter.drawText(QRectF(box_left + 10, y_cursor, box_right - box_left - 20, 18), Qt.AlignmentFlag.AlignLeft, f"Bonett Stat: {b_stat:.2f}")
            y_cursor += 20
            painter.drawText(QRectF(box_left + 10, y_cursor, box_right - box_left - 20, 18), Qt.AlignmentFlag.AlignLeft, f"Bonett P: {b_p:.3f}")

        # Samples intervals
        ci1 = s1.get("ci_stdev", (0.0, 1.0))
        ci2 = s2.get("ci_stdev", (0.0, 1.0))
        sd1 = s1.get("stdev", 0.5)
        sd2 = s2.get("stdev", 0.5)

        low1, high1 = ci1
        low2, high2 = ci2
        finite_lows = [v for v in (low1, low2) if isinstance(v, (int, float)) and math.isfinite(v)] or [0.0]
        finite_highs = [v for v in (high1, high2, sd1, sd2) if isinstance(v, (int, float)) and math.isfinite(v)] or [1.0]
        min_v = max(0.0, min(finite_lows) * 0.8)
        max_v = max(finite_highs) * 1.15
        if max_v <= min_v:
            max_v = min_v + 1.0

        def to_x(val):
            if not math.isfinite(val):
                return float(right if val > 0 else left)
            ratio = (val - min_v) / (max_v - min_v)
            return max(float(left), min(float(right), left + ratio * (right - left)))

        # Draw axis
        painter.setPen(QPen(QColor("#94A3B8"), 1))
        painter.drawLine(left, bottom, right, bottom)

        # Draw ticks
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))
        painter.setPen(QColor("#64748B"))
        num_ticks = 5
        for i in range(num_ticks + 1):
            tick_v = min_v + i * (max_v - min_v) / num_ticks
            tx = to_x(tick_v)
            painter.drawLine(int(tx), bottom, int(tx), bottom + 4)
            painter.drawText(QRectF(tx - 25, bottom + 6, 50, 16), Qt.AlignmentFlag.AlignCenter, f"{tick_v:.2f}")

        # Draw two sample lines
        y_spacing = (bottom - top) / 3
        y1 = top + y_spacing
        y2 = top + 2 * y_spacing

        # Sample 1
        painter.setPen(QColor("#0F172A"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.drawText(QRectF(10, y1 - 10, left - 20, 20), Qt.AlignmentFlag.AlignRight, name1)

        painter.setPen(QPen(QColor("#0284C7"), 2))
        x_low1 = to_x(low1)
        x_high1 = to_x(min(high1, max_v))
        x_mid1 = to_x(sd1)
        painter.drawLine(int(x_low1), int(y1), int(x_high1), int(y1))
        painter.drawLine(int(x_low1), int(y1 - 5), int(x_low1), int(y1 + 5))
        painter.drawLine(int(x_high1), int(y1 - 5), int(x_high1), int(y1 + 5))
        painter.setBrush(QBrush(QColor("#0284C7")))
        painter.drawEllipse(QPointF(x_mid1, y1), 4, 4)

        # Sample 2
        painter.setPen(QColor("#0F172A"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.drawText(QRectF(10, y2 - 10, left - 20, 20), Qt.AlignmentFlag.AlignRight, name2)

        painter.setPen(QPen(QColor("#E11D48"), 2))
        x_low2 = to_x(low2)
        x_high2 = to_x(min(high2, max_v))
        x_mid2 = to_x(sd2)
        painter.drawLine(int(x_low2), int(y2), int(x_high2), int(y2))
        painter.drawLine(int(x_low2), int(y2 - 5), int(x_low2), int(y2 + 5))
        painter.drawLine(int(x_high2), int(y2 - 5), int(x_high2), int(y2 + 5))
        painter.setBrush(QBrush(QColor("#E11D48")))
        painter.drawEllipse(QPointF(x_mid2, y2), 4, 4)


def draw_two_variances_panel(painter, rect, entry):
    """Painter delegate for modern_charts rendering."""
    widget = TwoVariancesSummaryPlotWidget(entry)
    widget.setGeometry(rect)
    widget.render(painter)
