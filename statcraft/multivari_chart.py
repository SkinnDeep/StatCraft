"""High-DPI Multi-Vari Chart Qt Widget.

Renders factor level means, connected lines, and individual observations across nested factor levels.
"""
from __future__ import annotations

import math
from PySide6.QtCore import Qt, QRectF, QPointF, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import QWidget, QSizePolicy
from .graph_interaction import GraphInteractionMixin
from .chart_theme import chart_painter


def _fmt(val, dec=2):
    if val is None:
        return ""
    return f"{val:.{dec}f}" if isinstance(val, (int, float)) else str(val)


class MultiVariChartWidget(GraphInteractionMixin, QWidget):
    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get('result', {})
        self.title = entry.get('title', 'Multi-Vari Chart')
        self.setMinimumSize(680, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hit_regions = []

    def sizeHint(self):
        return QSize(860, 560)

    def paintEvent(self, event):
        p = chart_painter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('#ffffff'))

        w = self.width()
        h = self.height()
        margin = 35.0

        # Title
        p.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
        p.setPen(QColor('#0f172a'))
        p.drawText(QRectF(margin, 12, w - 2 * margin, 26), Qt.AlignmentFlag.AlignCenter, self.title)

        cells = self.result.get('cells', [])
        if not cells:
            p.setFont(QFont('Segoe UI', 10))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "No Multi-Vari data available.")
            p.end()
            return

        # Y scale calculation
        all_vals = []
        for c in cells:
            all_vals.extend(c['values'])
        y_min = min(all_vals)
        y_max = max(all_vals)
        span = y_max - y_min
        if span <= 0:
            span = 1.0
        y_low = y_min - span * 0.1
        y_high = y_max + span * 0.1

        # Plot rectangle
        plot_left = margin + 55.0
        plot_top = 55.0
        plot_right = w - margin - 30.0
        plot_bottom = h - margin - 60.0
        plot_w = plot_right - plot_left
        plot_h = plot_bottom - plot_top
        plot_rect = QRectF(plot_left, plot_top, plot_w, plot_h)

        # Draw plot border & grid
        p.setPen(QPen(QColor('#e2e8f0'), 1.0))
        p.setBrush(QColor('#fafafa'))
        p.drawRect(plot_rect)

        # Coordinate transforms
        def to_y(val):
            return plot_bottom - ((val - y_low) / (y_high - y_low)) * plot_h

        # Y Axis Ticks
        p.setFont(QFont('Segoe UI', 8))
        p.setPen(QColor('#64748b'))
        n_ticks = 5
        for i in range(n_ticks + 1):
            t_val = y_low + (y_high - y_low) * (i / n_ticks)
            t_y = to_y(t_val)
            p.drawLine(QPointF(plot_left - 5, t_y), QPointF(plot_left, t_y))
            p.drawText(QRectF(margin, t_y - 8, 48, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, _fmt(t_val, 2))
            p.setPen(QPen(QColor('#f1f5f9'), 1.0))
            p.drawLine(QPointF(plot_left, t_y), QPointF(plot_right, t_y))
            p.setPen(QColor('#64748b'))

        # Grand Mean Line
        grand_mean = self.result.get('grand_mean')
        if grand_mean is not None:
            gm_y = to_y(grand_mean)
            p.setPen(QPen(QColor('#94a3b8'), 1.2, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(plot_left, gm_y), QPointF(plot_right, gm_y))
            p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
            p.setPen(QColor('#64748b'))
            p.drawText(QRectF(plot_right - 80, gm_y - 18, 75, 14), Qt.AlignmentFlag.AlignRight, f"GM: {_fmt(grand_mean, 2)}")

        # Draw Cells & Means
        n_cells = len(cells)
        cell_step = plot_w / (n_cells + 1)

        cell_points = []
        for ci, c in enumerate(cells):
            cx = plot_left + (ci + 1) * cell_step
            # Plot individual observations
            p.setPen(QPen(QColor('#93c5fd'), 1.0))
            p.setBrush(QColor('#bfdbfe'))
            for val in c['values']:
                vy = to_y(val)
                p.drawEllipse(QPointF(cx, vy), 3.0, 3.0)

            # Cell Mean point
            my = to_y(c['mean'])
            cell_points.append(QPointF(cx, my))

            # Vertical bar from min to max in cell
            if len(c['values']) > 1:
                p.setPen(QPen(QColor('#3b82f6'), 1.2))
                p.drawLine(QPointF(cx, to_y(c['min'])), QPointF(cx, to_y(c['max'])))

            # Cell label at bottom
            p.setFont(QFont('Segoe UI', 7.5))
            p.setPen(QColor('#334155'))
            lbl = " / ".join(c['factors'])
            p.save()
            p.translate(cx, plot_bottom + 12)
            p.rotate(35)
            p.drawText(0, 0, lbl)
            p.restore()

        # Connect cell means with colored line
        if len(cell_points) > 1:
            p.setPen(QPen(QColor('#1d4ed8'), 2.0))
            for i in range(1, len(cell_points)):
                p.drawLine(cell_points[i - 1], cell_points[i])

        # Draw Cell Mean markers (squares)
        p.setPen(QPen(QColor('#1e40af'), 1.5))
        p.setBrush(QColor('#2563eb'))
        for pt in cell_points:
            p.drawRect(QRectF(pt.x() - 4, pt.y() - 4, 8, 8))

        # Factors label below
        factor_names = self.result.get('factor_names', [])
        p.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
        p.setPen(QColor('#0f172a'))
        p.drawText(QRectF(plot_left, h - margin - 15, plot_w, 20), Qt.AlignmentFlag.AlignCenter, f"Factors: {' > '.join(factor_names)}")

        # Y Axis Label
        p.save()
        p.translate(14, plot_top + plot_h / 2)
        p.rotate(-90)
        p.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
        p.setPen(QColor('#0f172a'))
        resp_name = self.result.get('response_name', 'Response')
        p.drawText(QRectF(-plot_h / 2, -10, plot_h, 20), Qt.AlignmentFlag.AlignCenter, resp_name)
        p.restore()

        p.end()
