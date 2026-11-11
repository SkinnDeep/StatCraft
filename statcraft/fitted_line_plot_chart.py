"""High-fidelity Qt renderer for Fitted Line Plot (Stat > Regression > Fitted Line Plot).

Renders:
- Scatter points with hover tooltips and brushing
- Solid red fitted polynomial regression curve
- Dashed 95% Confidence Interval band with translucent cyan fill
- Dashed 95% Prediction Interval band in purple
- Minitab summary legend card with Model Equation, S, R-Sq, R-Sq(adj), and CI/PI keys
- Axis ticks, labels, and title
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from .graph_interaction import GraphInteractionMixin

INK = "#0f172a"
MUTED = "#64748b"
BORDER = "#cbd5e1"
GRID = "#f1f5f9"
FIT_COLOR = "#dc2626"
CI_COLOR = "#0284c7"
PI_COLOR = "#7c3aed"
POINT_COLOR = "#2563eb"
POINT_FILL = "#3b82f6"


def _fmt(val: Optional[float], dec: int = 4) -> str:
    if val is None or math.isnan(val):
        return ""
    return f"{val:.{dec}f}"


def _nice_ticks(low: float, high: float, count: int = 6) -> List[float]:
    if low >= high:
        return [low]
    span = high - low
    step = 10.0 ** math.floor(math.log10(span / count))
    for mult in (1.0, 2.0, 2.5, 5.0, 10.0):
        test_step = step * mult
        if span / test_step <= count:
            step = test_step
            break
    start = math.ceil(low / step) * step
    ticks = []
    curr = start
    while curr <= high + step * 0.01:
        ticks.append(round(curr, 8))
        curr += step
    return ticks or [low, high]


class FittedLinePlotChartWidget(GraphInteractionMixin, QWidget):
    """Minitab 22-parity Fitted Line Plot renderer."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", entry) if isinstance(entry, dict) else {}
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(QSize(780, 500))

        self.x_name = str(self.result.get("x_name", "X"))
        self.y_name = str(self.result.get("y_name", "Y"))
        self.model_type = str(self.result.get("model_type", "linear")).capitalize()
        self.equation = str(self.result.get("equation", f"{self.y_name} = f({self.x_name})"))
        self.s = float(self.result.get("s", 0.0))
        self.r2 = float(self.result.get("r_squared", 0.0))
        self.r2_adj = float(self.result.get("r_squared_adj", 0.0))
        self.conf_pct = float(self.result.get("confidence", 0.95)) * 100.0

        opts = self.result.get("options", {})
        self.title_text = opts.get("title") or f"Fitted Line Plot: {self.y_name} versus {self.x_name}"
        self.show_ci = bool(opts.get("ci", True))
        self.show_pi = bool(opts.get("pi", True))
        self.shade_ci = bool(opts.get("shade_ci", False))

        pts = self.result.get("points", {})
        self.pts_x = [float(v) for v in pts.get("x", [])]
        self.pts_y = [float(v) for v in pts.get("y", [])]
        self.row_indices = [int(v) for v in pts.get("row_indices", list(range(len(self.pts_x))))]

        crv = self.result.get("curve", {})
        self.curve_x = [float(v) for v in crv.get("x", [])]
        self.curve_fit = [float(v) for v in crv.get("fit", [])]
        self.curve_ci_low = [float(v) for v in crv.get("ci_low", [])]
        self.curve_ci_high = [float(v) for v in crv.get("ci_high", [])]
        self.curve_pi_low = [float(v) for v in crv.get("pi_low", [])]
        self.curve_pi_high = [float(v) for v in crv.get("pi_high", [])]

        self.panels = [{"name": "FittedLinePlot"}]
        self.hover_point_idx: Optional[int] = None

    def sizeHint(self) -> QSize:
        return QSize(840, 520)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#ffffff"))

        self.hit_regions = []
        self.clear_hover()

        # Layout Geometry
        plot_left = 68.0
        plot_top = 48.0
        plot_right = max(plot_left + 220.0, w - 215.0)
        plot_bottom = max(plot_top + 160.0, h - 52.0)
        plot_rect = QRectF(plot_left, plot_top, plot_right - plot_left, plot_bottom - plot_top)

        # 1. Title
        p.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        p.setPen(QColor(INK))
        p.drawText(
            QRectF(plot_left, 12, plot_rect.width(), 26),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.title_text,
        )

        # 2. Compute Ranges with Margin
        all_x = self.pts_x + self.curve_x
        all_y = self.pts_y + self.curve_fit
        if self.show_pi and self.curve_pi_low and self.curve_pi_high:
            all_y += self.curve_pi_low + self.curve_pi_high
        elif self.show_ci and self.curve_ci_low and self.curve_ci_high:
            all_y += self.curve_ci_low + self.curve_ci_high

        if not all_x or not all_y:
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "No valid data for Fitted Line Plot.")
            p.end()
            return

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        if min_x == max_x:
            min_x -= 1.0; max_x += 1.0
        if min_y == max_y:
            min_y -= 1.0; max_y += 1.0

        x_span = max_x - min_x
        y_span = max_y - min_y
        min_x -= 0.04 * x_span; max_x += 0.04 * x_span
        min_y -= 0.04 * y_span; max_y += 0.04 * y_span

        def map_x(val: float) -> float:
            return plot_rect.left() + (val - min_x) / (max_x - min_x) * plot_rect.width()

        def map_y(val: float) -> float:
            return plot_rect.bottom() - (val - min_y) / (max_y - min_y) * plot_rect.height()

        # 3. Grid Lines & Ticks
        x_ticks = _nice_ticks(min_x, max_x, 6)
        y_ticks = _nice_ticks(min_y, max_y, 6)

        p.setPen(QPen(QColor(GRID), 1.0))
        for xt in x_ticks:
            px = map_x(xt)
            if plot_rect.left() <= px <= plot_rect.right():
                p.drawLine(QPointF(px, plot_rect.top()), QPointF(px, plot_rect.bottom()))

        for yt in y_ticks:
            py = map_y(yt)
            if plot_rect.top() <= py <= plot_rect.bottom():
                p.drawLine(QPointF(plot_rect.left(), py), QPointF(plot_rect.right(), py))

        # Plot Bounding Box
        p.setPen(QPen(QColor(BORDER), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(plot_rect)

        # 4. Axis Tick Labels & Titles
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor(MUTED))
        for xt in x_ticks:
            px = map_x(xt)
            if plot_rect.left() - 2 <= px <= plot_rect.right() + 2:
                p.drawLine(QPointF(px, plot_rect.bottom()), QPointF(px, plot_rect.bottom() + 4))
                p.drawText(
                    QRectF(px - 30, plot_rect.bottom() + 6, 60, 16),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                    f"{xt:.2f}".rstrip("0").rstrip("."),
                )

        for yt in y_ticks:
            py = map_y(yt)
            if plot_rect.top() - 2 <= py <= plot_rect.bottom() + 2:
                p.drawLine(QPointF(plot_rect.left() - 4, py), QPointF(plot_rect.left(), py))
                p.drawText(
                    QRectF(0, py - 8, plot_rect.left() - 8, 16),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    f"{yt:.2f}".rstrip("0").rstrip("."),
                )

        # Axis Titles
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        p.setPen(QColor(INK))
        p.drawText(
            QRectF(plot_rect.left(), plot_rect.bottom() + 25, plot_rect.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            self.x_name,
        )

        p.save()
        p.translate(14, plot_rect.center().y())
        p.rotate(-90)
        p.drawText(QRectF(-120, -10, 240, 20), Qt.AlignmentFlag.AlignCenter, self.y_name)
        p.restore()

        # 5. Shaded Confidence Interval Ribbon & Dashed CI Lines
        p.save()
        p.setClipRect(plot_rect)

        if self.show_ci and self.curve_x and self.curve_ci_low and self.curve_ci_high:
            if self.shade_ci:
                ci_poly = []
                for xv, yv in zip(self.curve_x, self.curve_ci_high):
                    ci_poly.append(QPointF(map_x(xv), map_y(yv)))
                for xv, yv in reversed(list(zip(self.curve_x, self.curve_ci_low))):
                    ci_poly.append(QPointF(map_x(xv), map_y(yv)))

                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(2, 132, 199, 20))
                p.drawPolygon(QPolygonF(ci_poly))

            # Dashed CI boundary lines (always reset brush to NoBrush before open paths)
            p.setBrush(Qt.BrushStyle.NoBrush)
            pen_ci = QPen(QColor(CI_COLOR), 1.25, Qt.PenStyle.DashLine)
            p.setPen(pen_ci)
            path_ci_high = QPainterPath()
            path_ci_low = QPainterPath()
            for i, xv in enumerate(self.curve_x):
                pt_hi = QPointF(map_x(xv), map_y(self.curve_ci_high[i]))
                pt_lo = QPointF(map_x(xv), map_y(self.curve_ci_low[i]))
                if i == 0:
                    path_ci_high.moveTo(pt_hi)
                    path_ci_low.moveTo(pt_lo)
                else:
                    path_ci_high.lineTo(pt_hi)
                    path_ci_low.lineTo(pt_lo)
            p.drawPath(path_ci_high)
            p.drawPath(path_ci_low)

        # 6. Dashed Prediction Interval Lines
        if self.show_pi and self.curve_x and self.curve_pi_low and self.curve_pi_high:
            p.setBrush(Qt.BrushStyle.NoBrush)
            pen_pi = QPen(QColor(PI_COLOR), 1.25, Qt.PenStyle.DotLine)
            p.setPen(pen_pi)
            path_pi_high = QPainterPath()
            path_pi_low = QPainterPath()
            for i, xv in enumerate(self.curve_x):
                pt_hi = QPointF(map_x(xv), map_y(self.curve_pi_high[i]))
                pt_lo = QPointF(map_x(xv), map_y(self.curve_pi_low[i]))
                if i == 0:
                    path_pi_high.moveTo(pt_hi)
                    path_pi_low.moveTo(pt_lo)
                else:
                    path_pi_high.lineTo(pt_hi)
                    path_pi_low.lineTo(pt_lo)
            p.drawPath(path_pi_high)
            p.drawPath(path_pi_low)

        # 7. Solid Bold Fitted Polynomial Regression Curve
        if self.curve_x and self.curve_fit:
            p.setBrush(Qt.BrushStyle.NoBrush)
            pen_fit = QPen(QColor(FIT_COLOR), 2.0, Qt.PenStyle.SolidLine)
            p.setPen(pen_fit)
            path_fit = QPainterPath()
            for i, (xv, yv) in enumerate(zip(self.curve_x, self.curve_fit)):
                pt = QPointF(map_x(xv), map_y(yv))
                if i == 0:
                    path_fit.moveTo(pt)
                else:
                    path_fit.lineTo(pt)
            p.drawPath(path_fit)

            # Hit region on curve for tooltip
            path_fit_stroke = QPainterPath()
            path_fit_stroke.addPath(path_fit)
            self.hit_regions.append(("fitted_curve", path_fit_stroke))
            if hasattr(self, "remember_hover"):
                self.remember_hover(path_fit_stroke, {"text": f"Fitted Model:\n{self.equation}"})

        # 8. Observed Data Scatter Points
        r = 3.8
        for i, (xv, yv) in enumerate(zip(self.pts_x, self.pts_y)):
            px = map_x(xv)
            py = map_y(yv)
            pt_center = QPointF(px, py)

            p.setPen(QPen(QColor("#ffffff"), 1.0))
            p.setBrush(QColor(POINT_COLOR))
            p.drawEllipse(pt_center, r, r)

            # Interactive hit region for point
            path_pt = QPainterPath()
            path_pt.addEllipse(pt_center, r + 2.5, r + 2.5)
            self.hit_regions.append((f"point_{i}", path_pt))

            obs_idx = self.row_indices[i] + 1
            tip_text = f"Row: {obs_idx}\n{self.x_name}: {_fmt(xv)}\n{self.y_name}: {_fmt(yv)}"
            if hasattr(self, "remember_hover"):
                self.remember_hover(path_pt, {"text": tip_text})

        p.restore()

        # 9. Top-Right Minitab Legend & Equation Card
        legend_rows = 1 + int(self.show_ci) + int(self.show_pi)
        card_w = 195.0
        card_h = 122.0 + legend_rows * 16.0
        card_left = plot_rect.right() + 10.0
        card_top = plot_rect.top()
        card_rect = QRectF(card_left, card_top, card_w, card_h)

        p.setPen(QPen(QColor(BORDER), 1.0))
        p.setBrush(QColor(255, 255, 255, 245))
        p.drawRoundedRect(card_rect, 6.0, 6.0)

        # Card Content
        p.setFont(QFont("Segoe UI", 7.5, QFont.Weight.Bold))
        p.setPen(QColor(INK))
        p.drawText(
            QRectF(card_left + 8, card_top + 6, card_w - 16, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{self.model_type} Model",
        )

        p.setFont(QFont("Consolas", 7.5))
        p.setPen(QColor("#1e293b"))
        p.drawText(
            QRectF(card_left + 8, card_top + 24, card_w - 16, 30),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            self.equation,
        )

        p.setFont(QFont("Segoe UI", 7.5))
        p.setPen(QColor(MUTED))
        metrics_y = card_top + 58.0
        p.drawText(QRectF(card_left + 8, metrics_y, card_w - 16, 14), f"S = {self.s:.4f}")
        p.drawText(QRectF(card_left + 8, metrics_y + 14, card_w - 16, 14), f"R-Sq = {self.r2 * 100:.1f}%")
        p.drawText(QRectF(card_left + 8, metrics_y + 28, card_w - 16, 14), f"R-Sq(adj) = {self.r2_adj * 100:.1f}%")

        p.setPen(QPen(QColor(BORDER), 0.8))
        p.drawLine(QPointF(card_left + 8, card_top + 108), QPointF(card_left + card_w - 8, card_top + 108))

        # Legend Keys
        legend_y = card_top + 114.0
        line_h = 16.0

        # Fit
        p.setPen(QPen(QColor(FIT_COLOR), 2.0))
        p.drawLine(QPointF(card_left + 10, legend_y + 7), QPointF(card_left + 30, legend_y + 7))
        p.setFont(QFont("Segoe UI", 7.5))
        p.setPen(QColor(INK))
        p.drawText(QRectF(card_left + 36, legend_y, card_w - 44, line_h), "Regression Fit")

        # CI
        if self.show_ci:
            legend_y += line_h
            p.setPen(QPen(QColor(CI_COLOR), 1.3, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(card_left + 10, legend_y + 7), QPointF(card_left + 30, legend_y + 7))
            p.setPen(QColor(INK))
            p.drawText(QRectF(card_left + 36, legend_y, card_w - 44, line_h), f"{self.conf_pct:.0f}% CI")

        # PI
        if self.show_pi:
            legend_y += line_h
            p.setPen(QPen(QColor(PI_COLOR), 1.3, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(card_left + 10, legend_y + 7), QPointF(card_left + 30, legend_y + 7))
            p.setPen(QColor(INK))
            p.drawText(QRectF(card_left + 36, legend_y, card_w - 44, line_h), f"{self.conf_pct:.0f}% PI")

        p.end()
