"""High-fidelity Qt/QPainter renderer for Tolerance Intervals (Normal Distribution).

Matches StatCraft visual styling:
- Primary plot displaying data points, mean marker, and horizontal tolerance interval bars.
- Parametric Normal tolerance interval with distinct bracket ends and labeled bounds.
- Distribution-free Nonparametric tolerance interval with bracket ends and achieved confidence.
- Reference vertical line at the sample mean.
- Right-hand summary statistics card displaying sample statistics, coverage parameters, and numerical interval bounds.
- Interactive hover tooltips via GraphInteractionMixin.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .graph_interaction import GraphInteractionMixin
from .chart_theme import chart_painter

BLUE = "#0061a8"
BLUE_FILL = "#1f77b4"
GREEN = "#2ca02c"
RED = "#d9534f"
INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
GRID = "#e8ecef"
BOX_BG = "#f8f9fa"


def _fmt(val: Optional[float], dec: int = 4) -> str:
    if val is None or math.isnan(val):
        return "*"
    if val == float("inf"):
        return "Inf"
    if val == float("-inf"):
        return "-Inf"
    return f"{val:.{dec}g}"


class ToleranceIntervalChartWidget(GraphInteractionMixin, QWidget):
    """Tolerance intervals comparison plot and summary statistics card widget."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", {})
        self.recipe = entry.get("recipe", {})

        var_name = self.result.get("variable_name") or self.recipe.get("parameters", {}).get("variable_name", "Sample")
        self.title_text = (
            self.result.get("title")
            or f"Tolerance Intervals for {var_name}"
        )

        self.n = int(self.result.get("n", 0))
        self.mean = float(self.result.get("mean", 0.0))
        self.std = float(self.result.get("std", 1.0))
        self.conf = float(self.result.get("conf_level", 95.0))
        self.cov = float(self.result.get("min_percent", 95.0))
        self.itype = self.result.get("interval_type", "two_sided")

        self.nl = self.result.get("normal_lower", self.mean - 2.0 * self.std)
        self.nu = self.result.get("normal_upper", self.mean + 2.0 * self.std)
        self.k = self.result.get("k", 2.0)

        self.np_res = self.result.get("nonparametric")
        self.raw_data: List[float] = self.result.get("raw_observations") or []

        self.point_coords: List[Tuple[QPointF, float]] = []
        self.hover_point_idx: Optional[int] = None
        self.panels = [{"name": "ToleranceIntervals"}]

        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(660, 420)

    def sizeHint(self) -> QSize:
        return QSize(860, 520)

    def paintEvent(self, event) -> None:
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect()
        painter.fillRect(rect, QColor("#ffffff"))

        # Geometry
        top_margin = 55
        bottom_margin = 55
        left_margin = 65
        right_panel_width = 240
        plot_spacing = 15

        plot_width = max(10.0, rect.width() - left_margin - right_panel_width - plot_spacing)
        plot_height = max(10.0, rect.height() - top_margin - bottom_margin)

        plot_rect = QRectF(left_margin, top_margin, plot_width, plot_height)
        card_rect = QRectF(
            plot_rect.right() + plot_spacing,
            top_margin,
            right_panel_width - 15,
            plot_height
        )

        # Title
        painter.setPen(QColor(INK))
        font_title = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font_title)
        sub = f"Normal Distribution (Coverage: {self.cov:g}%, Confidence: {self.conf:g}%)"
        painter.drawText(
            QRectF(left_margin, 10, plot_width + right_panel_width, 24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.title_text
        )
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))
        painter.setPen(QColor(MUTED))
        painter.drawText(
            QRectF(left_margin, 34, plot_width, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            sub
        )

        # Plot Frame
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(plot_rect)

        # Determine horizontal data scale
        ref_points = [self.mean]
        if math.isfinite(self.nl):
            ref_points.append(self.nl)
        if math.isfinite(self.nu):
            ref_points.append(self.nu)
        if self.np_res:
            if math.isfinite(self.np_res.get("lower", float("nan"))):
                ref_points.append(self.np_res["lower"])
            if math.isfinite(self.np_res.get("upper", float("nan"))):
                ref_points.append(self.np_res["upper"])
        if self.raw_data:
            ref_points.extend(self.raw_data)

        x_min = min(ref_points)
        x_max = max(ref_points)
        span = x_max - x_min
        if span <= 1e-12:
            span = 1.0
        pad = span * 0.12
        x_min -= pad
        x_max += pad
        x_span = x_max - x_min

        def val_to_x(v: float) -> float:
            if not math.isfinite(v):
                return plot_rect.left() if v < 0 else plot_rect.right()
            return plot_rect.left() + ((v - x_min) / x_span) * plot_width

        # Draw X-axis ticks & labels
        ticks = 6
        font_axis = QFont("Segoe UI", 8)
        painter.setFont(font_axis)
        painter.setPen(QColor(MUTED))

        for t in range(ticks + 1):
            val = x_min + (t / ticks) * x_span
            xp = val_to_x(val)
            painter.drawLine(QPointF(xp, plot_rect.bottom()), QPointF(xp, plot_rect.bottom() + 4))
            painter.drawText(
                QRectF(xp - 30, plot_rect.bottom() + 6, 60, 16),
                Qt.AlignmentFlag.AlignCenter,
                f"{val:.4g}"
            )

        # Vertical Mean Line
        xp_mean = val_to_x(self.mean)
        pen_mean = QPen(QColor("#6c757d"), 1, Qt.PenStyle.DashDotLine)
        painter.setPen(pen_mean)
        painter.drawLine(QPointF(xp_mean, plot_rect.top()), QPointF(xp_mean, plot_rect.bottom()))
        painter.setPen(QColor("#495057"))
        painter.drawText(QRectF(xp_mean - 40, plot_rect.top() + 6, 80, 14), Qt.AlignmentFlag.AlignCenter, f"Mean ({self.mean:.4g})")

        # Partition plot vertical space:
        # Top 40%: Raw data points (if present)
        # Middle 30%: Normal tolerance interval bar
        # Bottom 30%: Nonparametric tolerance interval bar (if present)
        has_np = bool(self.np_res)
        y_points = plot_rect.top() + plot_height * 0.22
        y_norm = plot_rect.top() + plot_height * (0.55 if has_np else 0.65)
        y_np = plot_rect.top() + plot_height * 0.82

        # 1. Plot raw data points if available
        self.point_coords.clear()
        if self.raw_data:
            painter.setPen(QPen(QColor("#ffffff"), 0.5))
            painter.setBrush(QColor("#4a90e2"))
            for idx, val in enumerate(self.raw_data):
                # Gentle vertical jitter
                offset = ((hash(idx * 17) % 21) - 10) * 1.5
                pt = QPointF(val_to_x(val), y_points + offset)
                self.point_coords.append((pt, val))
                radius = 3.5 if idx != self.hover_point_idx else 5.5
                painter.drawEllipse(pt, radius, radius)

            painter.setPen(QColor(MUTED))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
            painter.drawText(QRectF(plot_rect.left() + 8, plot_rect.top() + 6, 120, 16), Qt.AlignmentFlag.AlignLeft, "Sample Data")

        # 2. Draw Normal Tolerance Interval
        self._draw_interval_bar(
            painter,
            plot_rect,
            y_norm,
            self.nl,
            self.nu,
            val_to_x,
            label="Normal",
            color=QColor(BLUE),
            bracket_height=16
        )

        # 3. Draw Nonparametric Tolerance Interval (if available)
        if has_np and self.np_res:
            self._draw_interval_bar(
                painter,
                plot_rect,
                y_np,
                self.np_res.get("lower"),
                self.np_res.get("upper"),
                val_to_x,
                label=f"Nonparametric ({self.np_res.get('achieved_confidence', 0):.1f}% Conf)",
                color=QColor(GREEN),
                bracket_height=16
            )

        # Summary Card on right
        self._draw_summary_card(painter, card_rect)

    def _draw_interval_bar(
        self,
        painter: QPainter,
        plot_rect: QRectF,
        y: float,
        lower: Optional[float],
        upper: Optional[float],
        val_to_x,
        label: str,
        color: QColor,
        bracket_height: float = 16.0
    ) -> None:
        has_lower = (lower is not None and math.isfinite(lower))
        has_upper = (upper is not None and math.isfinite(upper))

        x_left = val_to_x(lower) if has_lower else plot_rect.left()
        x_right = val_to_x(upper) if has_upper else plot_rect.right()

        # Horizontal bar
        pen_bar = QPen(color, 2.5, Qt.PenStyle.SolidLine)
        painter.setPen(pen_bar)
        painter.drawLine(QPointF(x_left, y), QPointF(x_right, y))

        # End brackets
        half_h = bracket_height / 2.0
        pen_bracket = QPen(color, 2.0, Qt.PenStyle.SolidLine)
        painter.setPen(pen_bracket)

        if has_lower:
            painter.drawLine(QPointF(x_left, y - half_h), QPointF(x_left, y + half_h))
            painter.drawLine(QPointF(x_left, y - half_h), QPointF(x_left + 4, y - half_h))
            painter.drawLine(QPointF(x_left, y + half_h), QPointF(x_left + 4, y + half_h))
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(color)
            painter.drawText(QRectF(x_left - 45, y + half_h + 2, 90, 14), Qt.AlignmentFlag.AlignCenter, f"{lower:.4g}")

        if has_upper:
            painter.setPen(pen_bracket)
            painter.drawLine(QPointF(x_right, y - half_h), QPointF(x_right, y + half_h))
            painter.drawLine(QPointF(x_right, y - half_h), QPointF(x_right - 4, y - half_h))
            painter.drawLine(QPointF(x_right, y + half_h), QPointF(x_right - 4, y + half_h))
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(color)
            painter.drawText(QRectF(x_right - 45, y + half_h + 2, 90, 14), Qt.AlignmentFlag.AlignCenter, f"{upper:.4g}")

        # Label above bar
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(color)
        painter.drawText(QRectF(plot_rect.left() + 8, y - half_h - 14, 250, 14), Qt.AlignmentFlag.AlignLeft, label)

    def _draw_summary_card(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor(BOX_BG))
        painter.drawRoundedRect(rect, 4.0, 4.0)

        header_h = 26
        header_rect = QRectF(rect.left(), rect.top(), rect.width(), header_h)
        painter.setBrush(QColor("#e9ecef"))
        painter.drawRoundedRect(header_rect, 4.0, 4.0)
        painter.fillRect(QRectF(rect.left(), rect.top() + header_h - 4, rect.width(), 4), QColor("#e9ecef"))

        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(header_rect, Qt.AlignmentFlag.AlignCenter, "Tolerance Intervals")

        items = [
            ("Sample Size (N)", str(self.n)),
            ("Mean", _fmt(self.mean, 4)),
            ("StdDev (s)", _fmt(self.std, 4)),
            ("Coverage (%)", f"{self.cov:g}%"),
            ("Confidence", f"{self.conf:g}%"),
            ("k-Factor", _fmt(self.k, 4)),
            ("Normal Lower", _fmt(self.nl, 4)),
            ("Normal Upper", _fmt(self.nu, 4)),
        ]

        if self.np_res:
            items.extend([
                ("NP Lower", _fmt(self.np_res.get("lower"), 4)),
                ("NP Upper", _fmt(self.np_res.get("upper"), 4)),
                ("NP Achieved Conf", f"{self.np_res.get('achieved_confidence', 0):.1f}%"),
            ])

        row_y = rect.top() + header_h + 8
        avail_h = rect.height() - header_h - 16
        row_step = max(18.0, min(24.0, avail_h / len(items)))

        font_label = QFont("Segoe UI", 8, QFont.Weight.Medium)
        font_val = QFont("Segoe UI", 8, QFont.Weight.Normal)

        for label, val in items:
            row_rect = QRectF(rect.left() + 10, row_y, rect.width() - 20, row_step)
            painter.setFont(font_label)
            painter.setPen(QColor(MUTED))
            painter.drawText(row_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

            painter.setFont(font_val)
            painter.setPen(QColor(INK))
            painter.drawText(row_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, val)

            row_y += row_step

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        old_hover = self.hover_point_idx
        self.hover_point_idx = None

        min_dist = 10.0
        for idx, (pt, val) in enumerate(self.point_coords):
            dist = math.hypot(pos.x() - pt.x(), pos.y() - pt.y())
            if dist < min_dist:
                min_dist = dist
                self.hover_point_idx = idx

        if self.hover_point_idx is not None:
            _, val = self.point_coords[self.hover_point_idx]
            tip = f"Observation: {val:.6g}\nMean: {self.mean:.6g}\nDiff from Mean: {val - self.mean:+.6g}"
            QToolTip.showText(event.globalPosition().toPoint(), tip, self)
        else:
            QToolTip.hideText()

        if self.hover_point_idx != old_hover:
            self.update()
        super().mouseMoveEvent(event)
