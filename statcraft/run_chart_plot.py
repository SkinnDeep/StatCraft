"""Quality Run Chart Widget."""
from __future__ import annotations

import math
from PySide6.QtCore import Qt, QRectF, QPointF, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import QWidget, QSizePolicy
from .graph_interaction import GraphInteractionMixin


def _fmt(val, dec=4):
    if val is None:
        return "*"
    return f"{val:.{dec}f}" if isinstance(val, (int, float)) else str(val)


class RunChartWidget(GraphInteractionMixin, QWidget):
    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get('result', {})
        self.title = entry.get('title', 'Run Chart')
        self.setMinimumSize(680, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hit_regions = []

    def sizeHint(self):
        return QSize(820, 560)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('#ffffff'))

        w = self.width()
        h = self.height()
        margin = 25.0

        # Title
        p.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
        p.setPen(QColor('#0f172a'))
        p.drawText(QRectF(margin, 12, w - 2 * margin, 26), Qt.AlignmentFlag.AlignCenter, self.title)

        # Layout: Plot area on top (70% height), Runs test table on bottom (30% height)
        top_y = 45.0
        footer_h = 100.0
        plot_h = h - top_y - footer_h - margin

        plot_rect = QRectF(margin + 40.0, top_y + 10.0, w - 2 * margin - 60.0, plot_h - 20.0)
        footer_rect = QRectF(margin + 10.0, plot_rect.bottom() + 30.0, w - 2 * margin - 20.0, footer_h)

        self._draw_run_plot(p, plot_rect)
        self._draw_runs_footer(p, footer_rect)
        p.end()

    def _draw_run_plot(self, p: QPainter, rect: QRectF):
        points = self.result.get('points', [])
        n = len(points)
        if n < 2:
            return

        min_val = min(points)
        max_val = max(points)
        span = max_val - min_val
        if span <= 0:
            span = 1.0
        y_min = min_val - span * 0.12
        y_max = max_val + span * 0.12

        def to_x(idx):
            return rect.left() + (idx / (n - 1)) * rect.width()

        def to_y(val):
            return rect.bottom() - ((val - y_min) / (y_max - y_min)) * rect.height()

        # Axes borders
        p.setPen(QPen(QColor('#cbd5e1'), 1.0))
        p.drawRect(rect)

        # Center line (Median)
        med_val = self.result.get('median', 0.0)
        med_y = to_y(med_val)
        p.setPen(QPen(QColor('#2563eb'), 1.2, Qt.PenStyle.DashLine))
        p.drawLine(rect.left(), med_y, rect.right(), med_y)

        # Median label
        p.setFont(QFont('Segoe UI', 7, QFont.Weight.Bold))
        p.setPen(QColor('#2563eb'))
        p.drawText(QRectF(rect.right() - 70, med_y - 14, 65, 12), Qt.AlignmentFlag.AlignRight, f"Median: {_fmt(med_val, 2)}")

        # Connect lines
        p.setPen(QPen(QColor('#64748b'), 1.2))
        qpoints = [QPointF(to_x(i), to_y(v)) for i, v in enumerate(points)]
        for i in range(len(qpoints) - 1):
            p.drawLine(qpoints[i], qpoints[i + 1])

        # Plot data points
        for i, qpt in enumerate(qpoints):
            v = points[i]
            col = QColor('#0284c7') if v >= med_val else QColor('#0ea5e9')
            p.setPen(QPen(QColor('#ffffff'), 1.0))
            p.setBrush(col)
            p.drawEllipse(qpt, 3.5, 3.5)

        # Y Axis Ticks
        p.setFont(QFont('Segoe UI', 7))
        p.setPen(QColor('#64748b'))
        for f in [0.0, 0.25, 0.5, 0.75, 1.0]:
            vy = y_min + f * (y_max - y_min)
            sy = to_y(vy)
            p.drawLine(rect.left() - 4, sy, rect.left(), sy)
            p.drawText(QRectF(rect.left() - 42, sy - 7, 36, 14), Qt.AlignmentFlag.AlignRight, _fmt(vy, 2))

        # X Axis Ticks (Observation Index)
        x_steps = min(n, 10)
        step_sz = max(1, n // x_steps)
        for i in range(0, n, step_sz):
            sx = to_x(i)
            p.drawLine(sx, rect.bottom(), sx, rect.bottom() + 4)
            p.drawText(QRectF(sx - 15, rect.bottom() + 6, 30, 14), Qt.AlignmentFlag.AlignCenter, str(i + 1))

        p.setFont(QFont('Segoe UI', 8, QFont.Weight.DemiBold))
        p.setPen(QColor('#334155'))
        p.drawText(QRectF(rect.left(), rect.bottom() + 20, rect.width(), 16), Qt.AlignmentFlag.AlignCenter, "Observation")

    def _draw_runs_footer(self, p: QPainter, rect: QRectF):
        # Background card
        p.setPen(QPen(QColor('#cbd5e1'), 0.8))
        p.setBrush(QColor('#f8fafc'))
        p.drawRoundedRect(rect, 6.0, 6.0)

        rbm = self.result.get('runs_about_median', {})
        rud = self.result.get('runs_up_or_down', {})

        col1_w = rect.width() * 0.48
        col2_w = rect.width() * 0.48
        cx1 = rect.left() + 15.0
        cx2 = rect.left() + rect.width() * 0.52

        # Left Column: Runs About Median
        y = rect.top() + 8.0
        line_h = 15.0
        p.setFont(QFont('Segoe UI', 7, QFont.Weight.Bold))
        p.setPen(QColor('#0369a1'))
        p.drawText(QRectF(cx1, y, col1_w, line_h), Qt.AlignmentFlag.AlignLeft, "Runs About Median")
        y += line_h

        p.setFont(QFont('Segoe UI', 7))
        p.setPen(QColor('#334155'))
        items_left = [
            ("Number of runs about median:", str(rbm.get('number_of_runs', 0))),
            ("Expected number of runs:", _fmt(rbm.get('expected_runs', 0.0), 1)),
            ("Longest run about median:", str(rbm.get('longest_run', 0))),
            ("Approx P-Value for Clustering:", _fmt(rbm.get('p_cluster', 0.0), 3)),
            ("Approx P-Value for Mixtures:", _fmt(rbm.get('p_mixture', 0.0), 3)),
        ]
        for lbl, val in items_left:
            p.drawText(QRectF(cx1, y, col1_w * 0.75, line_h), Qt.AlignmentFlag.AlignLeft, lbl)
            p.drawText(QRectF(cx1 + col1_w * 0.75, y, col1_w * 0.25, line_h), Qt.AlignmentFlag.AlignRight, val)
            y += line_h

        # Right Column: Runs Up or Down
        y = rect.top() + 8.0
        p.setFont(QFont('Segoe UI', 7, QFont.Weight.Bold))
        p.setPen(QColor('#0369a1'))
        p.drawText(QRectF(cx2, y, col2_w, line_h), Qt.AlignmentFlag.AlignLeft, "Runs Up or Down")
        y += line_h

        p.setFont(QFont('Segoe UI', 7))
        p.setPen(QColor('#334155'))
        items_right = [
            ("Number of runs up or down:", str(rud.get('number_of_runs', 0))),
            ("Expected number of runs:", _fmt(rud.get('expected_runs', 0.0), 1)),
            ("Longest run up or down:", str(rud.get('longest_run', 0))),
            ("Approx P-Value for Trends:", _fmt(rud.get('p_trend', 0.0), 3)),
            ("Approx P-Value for Oscillation:", _fmt(rud.get('p_oscillation', 0.0), 3)),
        ]
        for lbl, val in items_right:
            p.drawText(QRectF(cx2, y, col2_w * 0.75, line_h), Qt.AlignmentFlag.AlignLeft, lbl)
            p.drawText(QRectF(cx2 + col2_w * 0.75, y, col2_w * 0.25, line_h), Qt.AlignmentFlag.AlignRight, val)
            y += line_h
