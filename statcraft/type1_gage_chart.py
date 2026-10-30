"""High-fidelity Qt/QPainter renderer for Type 1 Gage Study (Stat > Quality Tools > Gage Study > Type 1 Gage Study).

Matches StatCraft visual styling:
- Primary run chart panel displaying run order vs measurements.
- Specification boundary lines:
  - Upper Tolerance limit (Ref + 0.10 * Tol, red dashed)
  - Lower Tolerance limit (Ref - 0.10 * Tol, red dashed)
  - Reference standard line (Ref, dark green dashed)
  - Sample mean line (Mean, blue solid)
- Data points connected with line segments, with points outside tolerance limits highlighted in red.
- Right-hand summary statistics card displaying Reference, Mean, StdDev, 6*StdDev, Tolerance,
  Cg, Cgk, %Var (Repeatability), %Var (Rep & Bias), Bias, T-stat, DF, and P-value.
- Interactive hover tooltips via GraphInteractionMixin.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .graph_interaction import GraphInteractionMixin

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
    return f"{val:.{dec}f}"


class Type1GageChartWidget(GraphInteractionMixin, QWidget):
    """Type 1 Gage Study run chart and capability summary card widget."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", {})
        self.recipe = entry.get("recipe", {})

        self.title_text = (
            self.result.get("title")
            or f"Type 1 Gage Study for {self.recipe.get('measurement_name', 'Measurement')}"
        )
        self.observations: List[float] = self.result.get("observations", [])
        self.reference = float(self.result.get("reference", 0.0))
        self.mean = float(self.result.get("mean", 0.0))
        self.std = float(self.result.get("std", 0.0))
        self.study_variation = float(self.result.get("study_variation", 6.0 * self.std))
        self.tolerance = float(self.result.get("tolerance", 1.0))
        self.upper_tol_limit = float(self.result.get("upper_tol_limit", self.reference + 0.1 * self.tolerance))
        self.lower_tol_limit = float(self.result.get("lower_tol_limit", self.reference - 0.1 * self.tolerance))

        self.cg = self.result.get("cg", 0.0)
        self.cgk = self.result.get("cgk", 0.0)
        self.pct_rep = self.result.get("pct_var_repeatability", 0.0)
        self.pct_rep_bias = self.result.get("pct_var_rep_and_bias", 0.0)
        self.bias = self.result.get("bias", 0.0)
        self.t_stat = self.result.get("t_stat")
        self.df = self.result.get("df", len(self.observations) - 1)
        self.p_value = self.result.get("p_value")

        self.point_coords: List[QPointF] = []
        self.hover_idx: Optional[int] = None
        self.panels = [{"name": "Type1Gage"}]

        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(640, 420)

    def sizeHint(self) -> QSize:
        return QSize(860, 520)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect()
        painter.fillRect(rect, QColor("#ffffff"))

        # Geometry
        top_margin = 50
        bottom_margin = 55
        left_margin = 70
        right_panel_width = 230
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
        painter.drawText(
            QRectF(left_margin, 12, plot_width + right_panel_width, 30),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.title_text
        )

        # Draw Run Chart Plot Box
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(plot_rect)

        n = len(self.observations)
        if n == 0:
            painter.setPen(QColor(MUTED))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(plot_rect, Qt.AlignmentFlag.AlignCenter, "No measurement data available")
            return

        # Determine Y range
        all_vals = list(self.observations) + [self.reference, self.mean, self.upper_tol_limit, self.lower_tol_limit]
        min_v = min(all_vals)
        max_v = max(all_vals)
        span = max_v - min_v
        if span <= 1e-12:
            span = 1.0
        pad = span * 0.15
        y_min = min_v - pad
        y_max = max_v + pad
        y_range = y_max - y_min

        def val_to_y(v: float) -> float:
            return plot_rect.bottom() - ((v - y_min) / y_range) * plot_height

        def run_to_x(idx: int) -> float:
            if n <= 1:
                return plot_rect.left() + plot_width / 2.0
            return plot_rect.left() + (idx / (n - 1)) * plot_width

        # Horizontal grid & Reference Lines
        font_small = QFont("Segoe UI", 8)
        painter.setFont(font_small)

        # Draw limit lines
        # 1. Upper Tol Limit
        y_utl = val_to_y(self.upper_tol_limit)
        if plot_rect.top() <= y_utl <= plot_rect.bottom():
            pen_utl = QPen(QColor(RED), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen_utl)
            painter.drawLine(QPointF(plot_rect.left(), y_utl), QPointF(plot_rect.right(), y_utl))
            painter.setPen(QColor(RED))
            label = f"+0.10*Tol ({self.upper_tol_limit:.4g})"
            painter.drawText(QRectF(plot_rect.right() - 140, y_utl - 16, 135, 14), Qt.AlignmentFlag.AlignRight, label)

        # 2. Lower Tol Limit
        y_ltl = val_to_y(self.lower_tol_limit)
        if plot_rect.top() <= y_ltl <= plot_rect.bottom():
            pen_ltl = QPen(QColor(RED), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen_ltl)
            painter.drawLine(QPointF(plot_rect.left(), y_ltl), QPointF(plot_rect.right(), y_ltl))
            painter.setPen(QColor(RED))
            label = f"-0.10*Tol ({self.lower_tol_limit:.4g})"
            painter.drawText(QRectF(plot_rect.right() - 140, y_ltl + 2, 135, 14), Qt.AlignmentFlag.AlignRight, label)

        # 3. Reference
        y_ref = val_to_y(self.reference)
        if plot_rect.top() <= y_ref <= plot_rect.bottom():
            pen_ref = QPen(QColor(GREEN), 1.5, Qt.PenStyle.DashDotLine)
            painter.setPen(pen_ref)
            painter.drawLine(QPointF(plot_rect.left(), y_ref), QPointF(plot_rect.right(), y_ref))
            painter.setPen(QColor(GREEN))
            label = f"Ref ({self.reference:.4g})"
            painter.drawText(QRectF(plot_rect.left() + 5, y_ref - 16, 120, 14), Qt.AlignmentFlag.AlignLeft, label)

        # 4. Mean
        y_mean = val_to_y(self.mean)
        if plot_rect.top() <= y_mean <= plot_rect.bottom():
            pen_mean = QPen(QColor(BLUE), 1.5, Qt.PenStyle.SolidLine)
            painter.setPen(pen_mean)
            painter.drawLine(QPointF(plot_rect.left(), y_mean), QPointF(plot_rect.right(), y_mean))
            painter.setPen(QColor(BLUE))
            label = f"Mean ({self.mean:.4g})"
            painter.drawText(QRectF(plot_rect.left() + 5, y_mean + 2, 120, 14), Qt.AlignmentFlag.AlignLeft, label)

        # Left Y-axis ticks & labels
        ticks = 5
        painter.setPen(QColor(MUTED))
        for t in range(ticks + 1):
            val = y_min + (t / ticks) * y_range
            yp = val_to_y(val)
            painter.drawLine(QPointF(plot_rect.left() - 4, yp), QPointF(plot_rect.left(), yp))
            painter.drawText(
                QRectF(0, yp - 7, left_margin - 8, 14),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{val:.4g}"
            )

        # Bottom X-axis ticks & Run Order labels
        step = max(1, n // 10)
        for idx in range(0, n, step):
            xp = run_to_x(idx)
            painter.drawLine(QPointF(xp, plot_rect.bottom()), QPointF(xp, plot_rect.bottom() + 4))
            painter.drawText(
                QRectF(xp - 20, plot_rect.bottom() + 6, 40, 16),
                Qt.AlignmentFlag.AlignCenter,
                str(idx + 1)
            )

        # X-axis Title
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        painter.setPen(QColor(INK))
        painter.drawText(
            QRectF(plot_rect.left(), plot_rect.bottom() + 24, plot_width, 24),
            Qt.AlignmentFlag.AlignCenter,
            "Run Order"
        )

        # Plot observations
        self.point_coords.clear()
        path = QPainterPath()
        for idx, val in enumerate(self.observations):
            pt = QPointF(run_to_x(idx), val_to_y(val))
            self.point_coords.append(pt)
            if idx == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)

        # Connecting line
        pen_line = QPen(QColor("#7ba3c7"), 1.2)
        painter.setPen(pen_line)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # Points
        for idx, pt in enumerate(self.point_coords):
            val = self.observations[idx]
            out_of_bounds = (val > self.upper_tol_limit or val < self.lower_tol_limit)
            color = QColor(RED) if out_of_bounds else QColor(BLUE_FILL)
            radius = 4.0 if idx != self.hover_idx else 6.0

            painter.setPen(QPen(QColor("#ffffff"), 1))
            painter.setBrush(color)
            painter.drawEllipse(pt, radius, radius)

        # Draw Right Summary Card
        self._draw_summary_card(painter, card_rect)

    def _draw_summary_card(self, painter: QPainter, rect: QRectF) -> None:
        # Background
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor(BOX_BG))
        painter.drawRoundedRect(rect, 4.0, 4.0)

        # Header banner
        header_h = 26
        header_rect = QRectF(rect.left(), rect.top(), rect.width(), header_h)
        painter.setBrush(QColor("#e9ecef"))
        painter.drawRoundedRect(header_rect, 4.0, 4.0)
        # Rect fill to square lower corners of banner
        painter.fillRect(QRectF(rect.left(), rect.top() + header_h - 4, rect.width(), 4), QColor("#e9ecef"))

        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(header_rect, Qt.AlignmentFlag.AlignCenter, "Summary Statistics")

        # Stats rows
        items = [
            ("Reference", _fmt(self.reference, 4)),
            ("Mean", _fmt(self.mean, 4)),
            ("StdDev (s)", _fmt(self.std, 4)),
            ("6 * StDev", _fmt(self.study_variation, 4)),
            ("Tolerance", _fmt(self.tolerance, 4)),
            ("Cg", _fmt(self.cg, 3)),
            ("Cgk", _fmt(self.cgk, 3)),
            ("%Var (Repeat)", f"{self.pct_rep:.1f}%"),
            ("%Var (R & B)", f"{self.pct_rep_bias:.1f}%"),
            ("Bias", _fmt(self.bias, 4)),
            ("t-Statistic", _fmt(self.t_stat, 3) if self.t_stat is not None else "*"),
            ("DF", str(self.df)),
            ("p-Value", _fmt(self.p_value, 4) if self.p_value is not None else "*"),
        ]

        row_y = rect.top() + header_h + 8
        avail_h = rect.height() - header_h - 16
        row_step = max(18.0, min(24.0, avail_h / len(items)))

        font_label = QFont("Segoe UI", 8, QFont.Weight.Medium)
        font_val = QFont("Segoe UI", 8, QFont.Weight.Normal)

        for label, val in items:
            row_rect = QRectF(rect.left() + 10, row_y, rect.width() - 20, row_step)

            # Cg and Cgk highlight
            if label in ("Cg", "Cgk"):
                try:
                    num_val = float(val)
                    val_color = QColor("#2b8a3e") if num_val >= 1.33 else QColor(RED)
                except ValueError:
                    val_color = QColor(INK)
            else:
                val_color = QColor(INK)

            painter.setFont(font_label)
            painter.setPen(QColor(MUTED))
            painter.drawText(row_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

            painter.setFont(font_val)
            painter.setPen(val_color)
            painter.drawText(row_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, val)

            row_y += row_step

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        old_hover = self.hover_idx
        self.hover_idx = None

        min_dist = 12.0
        for idx, pt in enumerate(self.point_coords):
            dx = pos.x() - pt.x()
            dy = pos.y() - pt.y()
            dist = math.hypot(dx, dy)
            if dist < min_dist:
                min_dist = dist
                self.hover_idx = idx

        if self.hover_idx is not None:
            val = self.observations[self.hover_idx]
            run = self.hover_idx + 1
            dev = val - self.reference
            status = "Within limits"
            if val > self.upper_tol_limit:
                status = "Above +0.10*Tol limit"
            elif val < self.lower_tol_limit:
                status = "Below -0.10*Tol limit"

            tip = (
                f"Run: {run}\n"
                f"Measurement: {val:.6g}\n"
                f"Deviation: {dev:+.6g}\n"
                f"Status: {status}"
            )
            QToolTip.showText(event.globalPosition().toPoint(), tip, self)
        else:
            QToolTip.hideText()

        if self.hover_idx != old_hover:
            self.update()
        super().mouseMoveEvent(event)
