"""Qt Chart rendering for StatCraft Test for Equal Variances."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath
from PySide6.QtWidgets import QWidget


class EqualVariancesSummaryPlotWidget(QWidget):
    """Dual-section display: horizontal interval comparison bars + right-side test box."""

    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setMinimumSize(620, 380)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        rect = self.rect()
        painter.fillRect(rect, QColor("#FFFFFF"))

        res = self.entry.get("result", {})
        groups = res.get("groups", [])
        if not groups:
            painter.setPen(QColor("#777777"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No group variance data available.")
            return

        conf = res.get("confidence_level", 95.0)
        use_normal = res.get("use_normal_distribution", False)
        resp_name = res.get("response_name", "Response")
        f_names = res.get("factor_names", [])

        # Title
        title_text = f"Test for Equal Variances: {resp_name}"
        if f_names:
            title_text += " vs " + ", ".join(f_names)

        painter.setPen(QColor("#111827"))
        title_font = QFont("Segoe UI", 11, QFont.Weight.DemiBold)
        painter.setFont(title_font)
        painter.drawText(QRectF(20, 10, rect.width() - 40, 24), Qt.AlignmentFlag.AlignCenter, title_text)

        # Subtitle
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Normal))
        painter.setPen(QColor("#4B5563"))
        subtitle = f"{conf:g}% Bonferroni CI for StDevs" if use_normal else f"Multiple comparison intervals for StDev, \u03b1 = {1.0 - conf/100.0:g}"
        painter.drawText(QRectF(20, 32, rect.width() - 40, 20), Qt.AlignmentFlag.AlignCenter, subtitle)

        # Layout boundaries
        top_y = 65
        bottom_y = rect.height() - 55
        plot_left = 90
        # Split width: 72% plot, 28% test stats box
        total_w = rect.width() - plot_left - 30
        plot_right = plot_left + int(total_w * 0.72)
        box_left = plot_right + 20
        box_right = rect.width() - 20

        # Axis scaling
        low_key = "bonf_lower" if use_normal else "mci_lower"
        high_key = "bonf_upper" if use_normal else "mci_upper"

        min_val = min(g[low_key] for g in groups)
        max_val = max(g[high_key] for g in groups)
        span = max(1e-4, max_val - min_val)
        axis_min = max(0.0, min_val - 0.1 * span)
        axis_max = max_val + 0.15 * span

        k = len(groups)
        row_h = (bottom_y - top_y) / max(1, k)

        # Draw left plot axes & grid
        painter.setPen(QPen(QColor("#E5E7EB"), 1, Qt.PenStyle.DashLine))
        num_ticks = 5
        painter.setFont(QFont("Segoe UI", 8))
        for i in range(num_ticks + 1):
            val = axis_min + (axis_max - axis_min) * (i / num_ticks)
            x_pos = plot_left + (val - axis_min) / (axis_max - axis_min) * (plot_right - plot_left)
            painter.drawLine(int(x_pos), int(top_y), int(x_pos), int(bottom_y))
            painter.setPen(QColor("#4B5563"))
            painter.drawText(QRectF(x_pos - 25, bottom_y + 4, 50, 16), Qt.AlignmentFlag.AlignCenter, f"{val:.2f}")
            painter.setPen(QPen(QColor("#E5E7EB"), 1, Qt.PenStyle.DashLine))

        painter.setPen(QPen(QColor("#9CA3AF"), 1.2))
        painter.drawLine(plot_left, bottom_y, plot_right, bottom_y)
        painter.drawLine(plot_left, top_y, plot_left, bottom_y)

        # X-axis label
        painter.setPen(QColor("#111827"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        painter.drawText(QRectF(plot_left, bottom_y + 20, plot_right - plot_left, 18), Qt.AlignmentFlag.AlignCenter, "Standard Deviations")

        # Draw group intervals
        bar_pen = QPen(QColor("#1D4ED8"), 2)
        end_cap_h = 6

        for i, g in enumerate(groups):
            cy = top_y + (i + 0.5) * row_h
            # Group label
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor("#111827"))
            painter.drawText(QRectF(10, cy - 10, plot_left - 15, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(g["level"]))

            # Interval bar
            x_low = plot_left + (g[low_key] - axis_min) / (axis_max - axis_min) * (plot_right - plot_left)
            x_high = plot_left + (g[high_key] - axis_min) / (axis_max - axis_min) * (plot_right - plot_left)
            x_pt = plot_left + (g["stdev"] - axis_min) / (axis_max - axis_min) * (plot_right - plot_left)

            painter.setPen(bar_pen)
            painter.drawLine(int(x_low), int(cy), int(x_high), int(cy))
            painter.drawLine(int(x_low), int(cy - end_cap_h), int(x_low), int(cy + end_cap_h))
            painter.drawLine(int(x_high), int(cy - end_cap_h), int(x_high), int(cy + end_cap_h))

            # Point marker (diamond / circle)
            painter.setPen(QPen(QColor("#1E3A8A"), 1.5))
            painter.setBrush(QBrush(QColor("#3B82F6")))
            painter.drawEllipse(QPointF(x_pt, cy), 4.5, 4.5)

        # Draw Right-Side Test Box (StatCraft signature)
        tests = res.get("tests", [])
        if tests:
            box_rect = QRectF(box_left, top_y + 10, box_right - box_left, min(bottom_y - top_y - 20, len(tests) * 55 + 20))
            painter.setPen(QPen(QColor("#D1D5DB"), 1.2))
            painter.setBrush(QBrush(QColor("#F9FAFB")))
            painter.drawRoundedRect(box_rect, 4, 4)

            curr_y = box_rect.top() + 10
            for t in tests:
                m_name = t.get("method", "Test")
                p_val = t.get("p_value")
                p_text = f"{p_val:.3f}" if p_val is not None else "*"

                painter.setPen(QColor("#111827"))
                painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
                painter.drawText(QRectF(box_left + 10, curr_y, box_rect.width() - 20, 18), Qt.AlignmentFlag.AlignLeft, m_name)

                painter.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Normal))
                painter.setPen(QColor("#374151"))
                stat_str = f"Stat = {t.get('test_statistic', 0.0):.2f}"
                painter.drawText(QRectF(box_left + 10, curr_y + 18, box_rect.width() - 20, 16), Qt.AlignmentFlag.AlignLeft, stat_str)

                painter.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Bold))
                p_color = QColor("#DC2626") if (p_val is not None and p_val < 0.05) else QColor("#111827")
                painter.setPen(p_color)
                painter.drawText(QRectF(box_left + 10, curr_y + 34, box_rect.width() - 20, 16), Qt.AlignmentFlag.AlignLeft, f"P-Value = {p_text}")

                curr_y += 56

        # Bottom interpretive note (StatCraft signature)
        painter.setPen(QColor("#4B5563"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))
        note = "If intervals do not overlap, the corresponding stdevs are significantly different."
        painter.drawText(QRectF(20, rect.height() - 24, rect.width() - 40, 18), Qt.AlignmentFlag.AlignLeft, note)


def draw_equal_variances_panel(painter, rect, entry):
    """Painter delegate for modern_charts rendering."""
    widget = EqualVariancesSummaryPlotWidget(entry)
    widget.setGeometry(rect)
    widget.render(painter)
