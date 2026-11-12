"""Qt visual chart widget for native StatCraft Two-Sample t test."""
from __future__ import annotations
import math
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PySide6.QtWidgets import QWidget
import numpy as np
from .chart_theme import chart_painter


class TwoSampleTPlotWidget(QWidget):
    """Renders Individual Value Plot and/or Boxplot for Two-Sample t."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", {})
        self.setMinimumSize(560, 380)

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_two_sample_t_panel(painter, self.rect(), self.result, self.entry.get("title"))
        painter.end()


def draw_two_sample_t_panel(
    p: QPainter,
    rect: QRectF,
    res: Dict[str, Any],
    title: Optional[str] = None,
):
    """Draw two-sample comparative individual value plot or boxplot."""
    # Background
    p.fillRect(rect, QColor("#ffffff"))

    if not res:
        return

    s1 = res.get("sample1", {})
    s2 = res.get("sample2", {})
    raw1 = s1.get("raw") or []
    raw2 = s2.get("raw") or []
    graphs = res.get("graphs", {})
    show_ivp = graphs.get("individual_value_plot", True)
    show_box = graphs.get("boxplot", True)

    # Title
    t_text = title or f"Two-Sample t Test: {s1.get('name', 'Sample 1')} vs {s2.get('name', 'Sample 2')}"
    p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
    p.setPen(QColor("#000000"))
    p.drawText(QRectF(rect.left(), rect.top() + 8, rect.width(), 26), Qt.AlignmentFlag.AlignCenter, t_text)

    # Subtitle with test info
    p.setFont(QFont("Segoe UI", 9))
    p.setPen(QColor("#555555"))
    t_val = res.get("t_statistic", 0.0)
    p_val = res.get("p_value", 1.0)
    diff = res.get("difference", 0.0)
    df = res.get("df", 0)
    sub = f"Diff = {diff:.4f}   T-Value = {t_val:.2f}   DF = {df}   P-Value = {p_val:.3f}"
    p.drawText(QRectF(rect.left(), rect.top() + 32, rect.width(), 20), Qt.AlignmentFlag.AlignCenter, sub)

    # Plot area
    margin_l = 70.0
    margin_r = 50.0
    margin_t = 65.0
    margin_b = 60.0
    plot_rect = QRectF(rect.left() + margin_l, rect.top() + margin_t,
                       max(100.0, rect.width() - margin_l - margin_r),
                       max(80.0, rect.height() - margin_t - margin_b))

    # Y limits
    all_vals = list(raw1) + list(raw2)
    if not all_vals:
        # If summarized, construct bounds from mean and stdev
        m1, sd1 = s1.get("mean", 0.0), s1.get("stdev", 1.0)
        m2, sd2 = s2.get("mean", 0.0), s2.get("stdev", 1.0)
        y_min = min(m1 - 2 * sd1, m2 - 2 * sd2)
        y_max = max(m1 + 2 * sd1, m2 + 2 * sd2)
    else:
        y_min = min(all_vals)
        y_max = max(all_vals)

    y_span = max(1e-6, y_max - y_min)
    y_min -= 0.1 * y_span
    y_max += 0.1 * y_span
    y_span = y_max - y_min

    def y_to_px(val: float) -> float:
        return plot_rect.bottom() - ((val - y_min) / y_span) * plot_rect.height()

    # Draw grid and axes
    p.setPen(QPen(QColor("#e0e0e0"), 1, Qt.PenStyle.DashLine))
    ticks = 5
    p.setFont(QFont("Segoe UI", 8))
    for i in range(ticks + 1):
        y_val = y_min + (y_span * i / ticks)
        py = y_to_px(y_val)
        p.drawLine(QPointF(plot_rect.left(), py), QPointF(plot_rect.right(), py))
        p.setPen(QColor("#333333"))
        p.drawText(QRectF(rect.left(), py - 9, margin_l - 8, 18),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{y_val:.2f}")
        p.setPen(QPen(QColor("#e0e0e0"), 1, Qt.PenStyle.DashLine))

    # Outer border
    p.setPen(QPen(QColor("#888888"), 1))
    p.drawRect(plot_rect)

    # 2 sample columns: center x1 and x2
    cx1 = plot_rect.left() + plot_rect.width() * 0.3
    cx2 = plot_rect.left() + plot_rect.width() * 0.7

    samples_data = [
        (s1.get("name", "Sample 1"), raw1, s1.get("mean", 0.0), s1.get("stdev", 1.0), cx1, QColor("#1f77b4")),
        (s2.get("name", "Sample 2"), raw2, s2.get("mean", 0.0), s2.get("stdev", 1.0), cx2, QColor("#ff7f0e")),
    ]

    for name, raw, mean, stdev, cx, col in samples_data:
        # X label
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.setPen(QColor("#000000"))
        p.drawText(QRectF(cx - 70, plot_rect.bottom() + 8, 140, 22), Qt.AlignmentFlag.AlignCenter, name)

        if raw:
            # Boxplot if requested
            if show_box:
                q1, med, q3 = np.percentile(raw, [25, 50, 75])
                iqr = q3 - q1
                w_low = min([v for v in raw if v >= q1 - 1.5 * iqr] or [min(raw)])
                w_high = max([v for v in raw if v <= q3 + 1.5 * iqr] or [max(raw)])

                bw = 48.0
                # Whisker line
                p.setPen(QPen(QColor("#444444"), 1.2))
                p.drawLine(QPointF(cx, y_to_px(w_low)), QPointF(cx, y_to_px(q1)))
                p.drawLine(QPointF(cx, y_to_px(q3)), QPointF(cx, y_to_px(w_high)))
                p.drawLine(QPointF(cx - 8, y_to_px(w_low)), QPointF(cx + 8, y_to_px(w_low)))
                p.drawLine(QPointF(cx - 8, y_to_px(w_high)), QPointF(cx + 8, y_to_px(w_high)))

                # Box
                box_top = y_to_px(q3)
                box_bot = y_to_px(q1)
                box_h = abs(box_bot - box_top)
                box_r = QRectF(cx - bw / 2, box_top, bw, box_h)
                p.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), 45)))
                p.setPen(QPen(col.darker(120), 1.5))
                p.drawRect(box_r)

                # Median line
                p.setPen(QPen(QColor("#cc0000"), 2))
                p.drawLine(QPointF(cx - bw / 2, y_to_px(med)), QPointF(cx + bw / 2, y_to_px(med)))

            # Individual value points if requested
            if show_ivp:
                p.setBrush(QBrush(col))
                p.setPen(QPen(col.darker(140), 1))
                np.random.seed(42)
                for val in raw:
                    jitter = (np.random.rand() - 0.5) * 16.0
                    px = cx + jitter
                    py = y_to_px(val)
                    p.drawEllipse(QPointF(px, py), 3.5, 3.5)

        # Mean point with cross
        py_mean = y_to_px(mean)
        p.setPen(QPen(QColor("#000000"), 2))
        p.drawLine(QPointF(cx - 6, py_mean), QPointF(cx + 6, py_mean))
        p.drawLine(QPointF(cx, py_mean - 6), QPointF(cx, py_mean + 6))
