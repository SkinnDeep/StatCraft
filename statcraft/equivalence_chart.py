"""High-fidelity Qt/QPainter charts for Equivalence Tests.

Renders authentic StatCraft visual charts:
- Equivalence Interval Plot: Shaded equivalence region, target/zero line, point estimate, and (1 - 2*alpha) CI error bar.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .graph_interaction import GraphInteractionMixin

BLUE = "#0061a8"
BLUE_FILL = "#1f77b4"
RED = "#d9534f"
GREEN = "#2ca02c"
GREEN_BG = "#eafaf1"
RED_BG = "#fdf2f2"
ORANGE = "#ff7f0e"
INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
GRID = "#e8ecef"


def _fmt(val: Optional[float], dec: int = 3) -> str:
    if val is None or math.isnan(val):
        return "*"
    return f"{val:.{dec}f}"


class EquivalenceChartWidget(GraphInteractionMixin, QWidget):
    """High-DPI renderer for Equivalence Analysis charts."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", {})
        self.recipe = entry.get("recipe", {})

        self.analysis = self.result.get("analysis", "one_sample_equivalence")
        self.title_text = self.result.get("title") or "Equivalence Interval Plot"

        self.setMinimumSize(640, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.hover_point: Optional[Tuple[float, float, str]] = None

    def sizeHint(self) -> QSize:
        return QSize(780, 460)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect()
        painter.fillRect(rect, QColor("#ffffff"))

        self._paint_equivalence_plot(painter, rect)

    def _paint_equivalence_plot(self, painter: QPainter, rect: QRectF) -> None:
        lo_m = float(self.result.get("lower_margin", -1.0))
        up_m = float(self.result.get("upper_margin", 1.0))
        est = float(self.result.get("point_estimate", 0.0))
        ci_lo = float(self.result.get("ci_lower", -0.5))
        ci_up = float(self.result.get("ci_upper", 0.5))
        clevel = float(self.result.get("conf_level", 90.0))
        is_equiv = bool(self.result.get("is_equivalent", False))
        is_ratio = self.result.get("hypothesis_type") == "ratio"
        target = float(self.result.get("target", 1.0 if is_ratio else 0.0))

        top = 70.0
        bottom = rect.height() - 70.0
        left = 80.0
        right = rect.width() - 50.0
        plot_w = right - left
        plot_h = bottom - top

        # Title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(left, 15, rect.width() - left - 200, 25), Qt.AlignmentFlag.AlignLeft, self.title_text)

        # Subtitle
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(MUTED))
        scale_txt = "Ratio (log scale transformed)" if is_ratio else "Difference"
        painter.drawText(QRectF(left, 42, rect.width() - left - 200, 20), Qt.AlignmentFlag.AlignLeft, f"{clevel:.1f}% CI for {scale_txt} with Equivalence Bounds ({_fmt(lo_m)}, {_fmt(up_m)})")

        # Status badge at top-right
        badge_w, badge_h = 175.0, 28.0
        badge_x = right - badge_w
        badge_y = 20.0
        badge_color = QColor(GREEN if is_equiv else RED)
        badge_bg = QColor(GREEN_BG if is_equiv else RED_BG)

        painter.setPen(QPen(badge_color, 1))
        painter.setBrush(badge_bg)
        painter.drawRoundedRect(QRectF(badge_x, badge_y, badge_w, badge_h), 4, 4)

        painter.setPen(badge_color)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        badge_text = "Equivalence Claimed" if is_equiv else "Not Equivalent"
        painter.drawText(QRectF(badge_x, badge_y, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, badge_text)

        # Horizontal Scale Bounds
        all_vals = [lo_m, up_m, est, ci_lo, ci_up, target]
        min_v = min(all_vals)
        max_v = max(all_vals)
        span = max_v - min_v if max_v > min_v else 1.0
        pad = span * 0.25
        min_x = min_v - pad
        max_x = max_v + pad

        def x_pos(v: float) -> float:
            return left + (v - min_x) / (max_x - min_x) * plot_w if max_x > min_x else left + plot_w / 2

        # Equivalence Region Shading
        x_lo_m = x_pos(lo_m)
        x_up_m = x_pos(up_m)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(GREEN_BG))
        painter.drawRect(QRectF(x_lo_m, top, x_up_m - x_lo_m, plot_h))

        # Margin lines
        painter.setPen(QPen(QColor(GREEN), 1.5, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(x_lo_m, top), QPointF(x_lo_m, bottom))
        painter.drawLine(QPointF(x_up_m, top), QPointF(x_up_m, bottom))

        # Labels for margin lines
        painter.setPen(QColor(GREEN))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(x_lo_m - 40, top - 18, 80, 16), Qt.AlignmentFlag.AlignCenter, f"Lower: {_fmt(lo_m)}")
        painter.drawText(QRectF(x_up_m - 40, top - 18, 80, 16), Qt.AlignmentFlag.AlignCenter, f"Upper: {_fmt(up_m)}")

        # Target Reference Line
        x_tgt = x_pos(target)
        painter.setPen(QPen(QColor(MUTED), 1, Qt.PenStyle.DotLine))
        painter.drawLine(QPointF(x_tgt, top), QPointF(x_tgt, bottom))
        painter.setPen(QColor(MUTED))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(x_tgt - 35, top + 8, 70, 16), Qt.AlignmentFlag.AlignCenter, f"Target ({_fmt(target)})")

        # Outer border
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        # Y position for CI bar
        y_bar = top + plot_h * 0.55

        # Horizontal error bar line
        x_ci_lo = x_pos(ci_lo)
        x_ci_up = x_pos(ci_up)
        bar_color = QColor(BLUE)

        painter.setPen(QPen(bar_color, 2.5))
        painter.drawLine(QPointF(x_ci_lo, y_bar), QPointF(x_ci_up, y_bar))

        # End caps
        cap_h = 10.0
        painter.drawLine(QPointF(x_ci_lo, y_bar - cap_h), QPointF(x_ci_lo, y_bar + cap_h))
        painter.drawLine(QPointF(x_ci_up, y_bar - cap_h), QPointF(x_ci_up, y_bar + cap_h))

        # Point estimate marker
        x_est = x_pos(est)
        painter.setBrush(QColor(BLUE_FILL))
        painter.setPen(QPen(QColor(BLUE), 1.5))
        painter.drawEllipse(QPointF(x_est, y_bar), 5.0, 5.0)

        # Text labels on CI
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(x_est - 40, y_bar - 22, 80, 18), Qt.AlignmentFlag.AlignCenter, f"Est: {_fmt(est)}")
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(x_ci_lo - 45, y_bar + 14, 90, 18), Qt.AlignmentFlag.AlignCenter, f"[{_fmt(ci_lo)}")
        painter.drawText(QRectF(x_ci_up - 45, y_bar + 14, 90, 18), Qt.AlignmentFlag.AlignCenter, f"{_fmt(ci_up)}]")

        # Horizontal Axis Ticks
        painter.setPen(QColor(MUTED))
        painter.setFont(QFont("Segoe UI", 8))
        n_ticks = 6
        for t in range(n_ticks + 1):
            val = min_x + t * (max_x - min_x) / n_ticks
            x = x_pos(val)
            painter.drawLine(QPointF(x, bottom), QPointF(x, bottom + 5))
            painter.drawText(QRectF(x - 30, bottom + 7, 60, 16), Qt.AlignmentFlag.AlignCenter, f"{val:.2f}")

        # X-axis label
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        x_label = "Ratio" if is_ratio else "Difference"
        painter.drawText(QRectF(left, bottom + 28, plot_w, 20), Qt.AlignmentFlag.AlignCenter, x_label)
