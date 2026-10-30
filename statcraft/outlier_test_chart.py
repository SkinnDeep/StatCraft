"""High-DPI Outlier Test Chart Qt Widget.

Renders observation scatter/dot plot with mean reference line, upper/lower outlier threshold bounds,
and highlighted outlier marker in prominent red.
"""
from __future__ import annotations

import math
from PySide6.QtCore import Qt, QRectF, QPointF, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import QWidget, QSizePolicy
from .graph_interaction import GraphInteractionMixin


def _fmt(val, dec=3):
    if val is None:
        return ""
    return f"{val:.{dec}f}" if isinstance(val, (int, float)) else str(val)


class OutlierTestChartWidget(GraphInteractionMixin, QWidget):
    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get('result', {})
        self.title = entry.get('title', 'Outlier Plot')
        self.setMinimumSize(660, 440)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hit_regions = []

    def sizeHint(self):
        return QSize(820, 520)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('#ffffff'))

        w = self.width()
        h = self.height()
        margin = 35.0

        # Title
        p.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
        p.setPen(QColor('#0f172a'))
        p.drawText(QRectF(margin, 12, w - 2 * margin, 26), Qt.AlignmentFlag.AlignCenter, self.title)

        values = self.result.get('values', [])
        rows = self.result.get('rows', [])
        n = len(values)
        if n < 2:
            p.end()
            return

        mean_val = self.result.get('mean', 0.0)
        stdev_val = self.result.get('stdev', 1.0)
        g_crit = self.result.get('g_crit', 2.5)

        upper_thresh = mean_val + g_crit * stdev_val
        lower_thresh = mean_val - g_crit * stdev_val

        # Y scale
        all_y = list(values) + [upper_thresh, lower_thresh, mean_val]
        y_min = min(all_y)
        y_max = max(all_y)
        span = y_max - y_min
        if span <= 0:
            span = 1.0
        y_low = y_min - span * 0.08
        y_high = y_max + span * 0.08

        # Plot rectangle
        plot_left = margin + 55.0
        plot_top = 50.0
        plot_right = w - margin - 150.0
        plot_bottom = h - margin - 35.0
        plot_w = plot_right - plot_left
        plot_h = plot_bottom - plot_top
        plot_rect = QRectF(plot_left, plot_top, plot_w, plot_h)

        # Draw plot area
        p.setPen(QPen(QColor('#e2e8f0'), 1.0))
        p.setBrush(QColor('#fafafa'))
        p.drawRect(plot_rect)

        def to_x(row_num):
            return plot_left + (row_num / (max(rows) + 1)) * plot_w

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

        # Mean Center Line
        my = to_y(mean_val)
        p.setPen(QPen(QColor('#10b981'), 1.5))
        p.drawLine(QPointF(plot_left, my), QPointF(plot_right, my))

        # Upper & Lower Critical Threshold Lines
        p.setPen(QPen(QColor('#ef4444'), 1.2, Qt.PenStyle.DashLine))
        uy = to_y(upper_thresh)
        ly = to_y(lower_thresh)
        p.drawLine(QPointF(plot_left, uy), QPointF(plot_right, uy))
        p.drawLine(QPointF(plot_left, ly), QPointF(plot_right, ly))

        # Data Points
        out_val = self.result.get('outlier_value')
        out_row = self.result.get('outlier_row')
        is_out = self.result.get('is_outlier', False)

        for r_num, v in zip(rows, values):
            px = to_x(r_num)
            py = to_y(v)

            if is_out and r_num == out_row and abs(v - out_val) < 1e-7:
                # Outlier: red star/diamond
                p.setPen(QPen(QColor('#b91c1c'), 2.0))
                p.setBrush(QColor('#ef4444'))
                p.drawEllipse(QPointF(px, py), 6.5, 6.5)

                # Annotation label
                p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
                p.setPen(QColor('#b91c1c'))
                p.drawText(QRectF(px + 8, py - 10, 100, 20), Qt.AlignmentFlag.AlignLeft, f"Outlier: {_fmt(v, 2)}")
            else:
                p.setPen(QPen(QColor('#2563eb'), 1.0))
                p.setBrush(QColor('#60a5fa'))
                p.drawEllipse(QPointF(px, py), 3.5, 3.5)

        # Legend / Info Card on the right
        card_rect = QRectF(plot_right + 15, plot_top, w - plot_right - margin - 20, plot_h)
        p.setPen(QPen(QColor('#cbd5e1'), 0.8))
        p.setBrush(QColor('#ffffff'))
        p.drawRoundedRect(card_rect, 4.0, 4.0)

        p.setFont(QFont('Segoe UI', 8.5, QFont.Weight.Bold))
        p.setPen(QColor('#0f172a'))
        card_top = card_rect.top() + 10.0
        p.drawText(QRectF(card_rect.left() + 8, card_top, card_rect.width() - 16, 18), "Grubbs' Test")

        p.setFont(QFont('Segoe UI', 8))
        lines = [
            f"N: {n}",
            f"Mean: {_fmt(mean_val, 3)}",
            f"StDev: {_fmt(stdev_val, 3)}",
            f"G: {_fmt(self.result.get('g_stat'), 3)}",
            f"Crit G: {_fmt(g_crit, 3)}",
            f"P-Value: {_fmt(self.result.get('p_value'), 3)}",
            f"α: {self.result.get('alpha', 0.05)}",
        ]
        card_y = card_top + 24.0
        for l in lines:
            p.drawText(QRectF(card_rect.left() + 8, card_y, card_rect.width() - 16, 16), l)
            card_y += 18.0

        card_y += 6.0
        p.setPen(QPen(QColor('#10b981'), 1.5))
        p.drawLine(QPointF(card_rect.left() + 8, card_y + 8), QPointF(card_rect.left() + 25, card_y + 8))
        p.setPen(QColor('#334155'))
        p.drawText(QRectF(card_rect.left() + 30, card_y, card_rect.width() - 38, 16), "Mean")
        card_y += 18.0

        p.setPen(QPen(QColor('#ef4444'), 1.2, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(card_rect.left() + 8, card_y + 8), QPointF(card_rect.left() + 25, card_y + 8))
        p.setPen(QColor('#334155'))
        p.drawText(QRectF(card_rect.left() + 30, card_y, card_rect.width() - 38, 16), "Critical Bound")

        # X Axis Label
        p.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
        p.setPen(QColor('#0f172a'))
        p.drawText(QRectF(plot_left, h - margin - 15, plot_w, 20), Qt.AlignmentFlag.AlignCenter, "Row Index")

        # Y Axis Label
        p.save()
        p.translate(14, plot_top + plot_h / 2)
        p.rotate(-90)
        p.drawText(QRectF(-plot_h / 2, -10, plot_h, 20), Qt.AlignmentFlag.AlignCenter, self.result.get('variable_name', 'Value'))
        p.restore()

        p.end()
