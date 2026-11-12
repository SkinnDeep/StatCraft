"""High-fidelity Qt/QPainter charts for Power and Sample Size.

Renders authentic StatCraft Power Curves:
- Plots Power (0.0 to 1.0) versus Sample Size (or Total Runs)
- Horizontal dashed reference lines at Power = 0.80 and 0.90
- Multiple colored curves for different detectable differences / effect sizes
- Interactive Pan/Zoom via GraphInteractionMixin
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .graph_interaction import GraphInteractionMixin
from .chart_theme import chart_painter

CURVE_COLORS = [
    "#1f77b4",  # Blue
    "#ff7f0e",  # Orange
    "#2ca02c",  # Green
    "#d62728",  # Red
    "#9467bd",  # Purple
    "#8c564b",  # Brown
    "#e377c2",  # Pink
]
INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
GRID = "#e8ecef"


class PowerCurveWidget(GraphInteractionMixin, QWidget):
    """High-DPI renderer for Power Curve charts."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", {})
        self.recipe = entry.get("recipe", {})

        self.analysis = self.result.get("analysis", "one_sample_t_power")
        self.title_text = self.result.get("title") or "Power Curve"
        self.curves = self.result.get("curves", [])

        self.setMinimumSize(640, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.hover_point: Optional[Tuple[float, float, str]] = None

    def sizeHint(self) -> QSize:
        return QSize(780, 480)

    def paintEvent(self, event) -> None:
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect()
        painter.fillRect(rect, QColor("#ffffff"))

        self._paint_power_curve(painter, rect)

    def _paint_power_curve(self, painter: QPainter, rect: QRectF) -> None:
        top = 70.0
        bottom = rect.height() - 65.0
        left = 75.0
        right = rect.width() - 170.0  # leave room for right legend
        plot_w = right - left
        plot_h = bottom - top

        # Title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, self.title_text)

        # Subtitle
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(MUTED))
        alpha = self.result.get("alpha", 0.05)
        painter.drawText(QRectF(left, 42, rect.width() - left - 20, 20), Qt.AlignmentFlag.AlignLeft, f"Significance level (alpha) = {alpha:.3f}")

        # Determine X range across curves
        all_xs = []
        for c in self.curves:
            for pt in c.get("points", []):
                all_xs.append(pt[0])

        min_x = min(all_xs) if all_xs else 2
        max_x = max(all_xs) if all_xs else 50
        if max_x <= min_x:
            max_x = min_x + 10

        # Axes box
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        # Y grid lines and labels (0.0 to 1.0)
        y_ticks = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        painter.setFont(QFont("Segoe UI", 8))
        for y_val in y_ticks:
            y_px = bottom - y_val * plot_h
            painter.setPen(QPen(QColor(GRID), 1))
            painter.drawLine(QPointF(left, y_px), QPointF(right, y_px))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(10, y_px - 8, left - 18, 16), Qt.AlignmentFlag.AlignRight, f"{y_val:.1f}")

        # Horizontal Target Power Reference Lines at 0.80 and 0.90
        for target_p in (0.80, 0.90):
            y_target = bottom - target_p * plot_h
            ref_pen = QPen(QColor("#7f8c8d"), 1, Qt.PenStyle.DashLine)
            painter.setPen(ref_pen)
            painter.drawLine(QPointF(left, y_target), QPointF(right, y_target))
            painter.setPen(QColor("#7f8c8d"))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            painter.drawText(QRectF(right - 55, y_target - 15, 50, 14), Qt.AlignmentFlag.AlignRight, f"{target_p:.2f}")

        # X ticks and labels
        x_step = max(1, int(math.ceil((max_x - min_x) / 5)))
        x_ticks = list(range(int(min_x), int(max_x) + 1, x_step))
        if x_ticks[-1] < max_x:
            x_ticks.append(int(max_x))

        for x_val in x_ticks:
            frac = (x_val - min_x) / (max_x - min_x) if max_x > min_x else 0.5
            x_px = left + frac * plot_w
            painter.setPen(QPen(QColor(GRID), 1))
            painter.drawLine(QPointF(x_px, top), QPointF(x_px, bottom))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(x_px - 25, bottom + 6, 50, 16), Qt.AlignmentFlag.AlignCenter, str(x_val))

        # Axis Titles
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.setPen(QColor(INK))
        x_label = "Total Runs" if self.analysis == "factorial_power" else "Sample Size"
        painter.drawText(QRectF(left, bottom + 28, plot_w, 20), Qt.AlignmentFlag.AlignCenter, x_label)

        painter.save()
        painter.translate(22, top + plot_h / 2)
        painter.rotate(-90)
        painter.drawText(QRectF(-100, -10, 200, 20), Qt.AlignmentFlag.AlignCenter, "Power")
        painter.restore()

        # Paint Curves
        legend_items = []
        for idx, curve in enumerate(self.curves):
            color = QColor(CURVE_COLORS[idx % len(CURVE_COLORS)])
            pen = QPen(color, 2)
            painter.setPen(pen)

            pts = curve.get("points", [])
            if not pts:
                continue

            path = QPainterPath()
            first = True
            for x_val, y_val in pts:
                frac_x = (x_val - min_x) / (max_x - min_x) if max_x > min_x else 0.5
                frac_y = y_val  # 0 to 1
                px = left + frac_x * plot_w
                py = bottom - frac_y * plot_h
                if first:
                    path.moveTo(px, py)
                    first = False
                else:
                    path.lineTo(px, py)
            painter.drawPath(path)

            # Curve label for legend
            if "difference" in curve:
                lbl = f"Diff = {curve['difference']:.2f}"
            elif "effect" in curve:
                lbl = f"Effect = {curve['effect']:.2f}"
            elif "comparison_p" in curve:
                lbl = f"p = {curve['comparison_p']:.2f}"
            elif "p1" in curve:
                lbl = f"p1 = {curve['p1']:.2f}"
            elif "max_difference" in curve:
                lbl = f"Max Diff = {curve['max_difference']:.2f}"
            else:
                lbl = f"Curve {idx+1}"
            legend_items.append((color, lbl))

        # Paint Legend at right
        leg_x = right + 18.0
        leg_y = top + 10.0
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(leg_x, leg_y, 140, 20), Qt.AlignmentFlag.AlignLeft, "Parameters")
        leg_y += 24.0

        painter.setFont(QFont("Segoe UI", 8))
        for color, lbl in legend_items:
            painter.setPen(QPen(color, 2))
            painter.drawLine(QPointF(leg_x, leg_y + 8), QPointF(leg_x + 18, leg_y + 8))
            painter.fillRect(QRectF(leg_x + 6, leg_y + 5, 6, 6), color)
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(leg_x + 24, leg_y, 120, 16), Qt.AlignmentFlag.AlignLeft, lbl)
            leg_y += 20.0
