"""High-fidelity Qt/QPainter renderer for Multivariate Control Charts (T-Squared, GenVar, MEWMA).

Matches StatCraft visual styling:
- High-contrast, clean typography
- Title: "T² Chart of <Variables>", "Generalized Variance Chart of <Variables>", or "MEWMA Chart of <Variables>"
- Center Line (Green), UCL (Red dashed), LCL (Red dashed if > 0)
- Right-hand margin limit and center callouts
- Blue connected series; red markers with test digits ('1') for special cause signals
- Interactive tooltips with Subgroup number, Statistic, Limits, and Test Failures
- Full GraphInteractionMixin integration with objectSelected, objectActivated, brushRowsSelected
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
INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
RED = "#c23934"
GREEN = "#1b7837"
GRID = "#e8ecef"


def _fmt(val: Optional[float], dec: int = 4) -> str:
    if val is None or math.isnan(val):
        return ""
    return f"{val:.{dec}f}"


def _bounds(values: List[float], pad_frac: float = 0.15) -> Tuple[float, float]:
    clean = [v for v in values if v is not None and not math.isnan(v) and not math.isinf(v)]
    if not clean:
        return (0.0, 1.0)
    lo, hi = min(clean), max(clean)
    if lo == hi:
        delta = max(0.05, abs(lo) * 0.1)
        return (max(0.0, lo - delta), hi + delta)
    pad = (hi - lo) * pad_frac
    return (max(0.0, lo - pad), hi + pad)


class MultivariateControlChartWidget(GraphInteractionMixin, QWidget):
    """Single-panel control chart widget for T-Squared, GenVar, and MEWMA multivariate charts."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", entry) if isinstance(entry, dict) else {}
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(QSize(760, 480))

        self.chart_type = str(self.result.get("chart_type", "TSQUARED")).upper()
        var_names = self.result.get("variable_names", [])
        self.var_names_str = ", ".join(var_names) if var_names else "Variables"
        self.hover_point: Optional[Tuple[int, float, float]] = None
        self.panels = [{"name": self.chart_type}]

    def sizeHint(self) -> QSize:
        return QSize(820, 520)

    def paintEvent(self, event) -> None:
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect()
        painter.fillRect(rect, QColor("#ffffff"))

        # Margins
        top_margin = 60
        bottom_margin = 65
        left_margin = 85
        right_margin = 110

        plot_rect = QRectF(
            left_margin,
            top_margin,
            max(10.0, rect.width() - left_margin - right_margin),
            max(10.0, rect.height() - top_margin - bottom_margin),
        )

        # Title
        painter.setPen(QColor(INK))
        font_title = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font_title)
        if self.chart_type == "TSQUARED":
            title = f"T² Control Chart of {self.var_names_str}"
            y_label = "T²"
        elif self.chart_type == "GENVAR":
            title = f"Generalized Variance Chart of {self.var_names_str}"
            y_label = "|S|"
        elif self.chart_type == "MEWMA":
            title = f"Multivariate EWMA Chart of {self.var_names_str}"
            y_label = "MEWMA T²"
        else:
            title = f"Multivariate Chart of {self.var_names_str}"
            y_label = "Statistic"

        painter.drawText(QRectF(left_margin, 15, plot_rect.width(), 30), Qt.AlignmentFlag.AlignCenter, title)

        # Plot Border and Background
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(plot_rect)

        k_obs = self.result.get("k_subgroups", 0)
        if k_obs == 0:
            painter.setPen(QColor(MUTED))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(plot_rect, Qt.AlignmentFlag.AlignCenter, "No multivariate data available")
            return

        values = [float(v) for v in self.result.get("values", [])]
        ucl_val = float(self.result.get("ucl_val", 0.0))
        lcl_val = float(self.result.get("lcl_val", 0.0))
        cl_val = float(self.result.get("center_line", 0.0))

        all_vals = values + [ucl_val, lcl_val, cl_val]
        y_min, y_max = _bounds(all_vals)

        def map_x(idx: int) -> float:
            if k_obs <= 1:
                return plot_rect.left() + plot_rect.width() / 2.0
            return plot_rect.left() + (idx / (k_obs - 1)) * plot_rect.width()

        def map_y(val: float) -> float:
            if y_max <= y_min:
                return plot_rect.top() + plot_rect.height() / 2.0
            ratio = (val - y_min) / (y_max - y_min)
            return plot_rect.bottom() - ratio * plot_rect.height()

        # Grid lines (horizontal)
        font_axis = QFont("Segoe UI", 8)
        painter.setFont(font_axis)
        ticks = 5
        for t in range(ticks + 1):
            t_val = y_min + (y_max - y_min) * (t / ticks)
            y_pos = map_y(t_val)
            painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(plot_rect.left(), y_pos), QPointF(plot_rect.right(), y_pos))
            painter.setPen(QColor(MUTED))
            painter.drawText(
                QRectF(0, y_pos - 8, left_margin - 8, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                _fmt(t_val, 2),
            )

        # Y-Axis label
        painter.save()
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.translate(22, plot_rect.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-80, -10, 160, 20), Qt.AlignmentFlag.AlignCenter, y_label)
        painter.restore()

        # X-Axis ticks and Subgroup numbers
        step_x = max(1, k_obs // 10)
        painter.setFont(font_axis)
        painter.setPen(QColor(MUTED))
        for i in range(0, k_obs, step_x):
            x_pos = map_x(i)
            painter.drawLine(QPointF(x_pos, plot_rect.bottom()), QPointF(x_pos, plot_rect.bottom() + 4))
            painter.drawText(
                QRectF(x_pos - 15, plot_rect.bottom() + 6, 30, 16),
                Qt.AlignmentFlag.AlignCenter,
                str(i + 1),
            )

        # X-Axis label
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.drawText(
            QRectF(plot_rect.left(), plot_rect.bottom() + 28, plot_rect.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            "Subgroup",
        )

        # Center Line (Green)
        if y_min <= cl_val <= y_max:
            y_cl = map_y(cl_val)
            painter.setPen(QPen(QColor(GREEN), 1.5))
            painter.drawLine(QPointF(plot_rect.left(), y_cl), QPointF(plot_rect.right(), y_cl))
            painter.setPen(QColor(GREEN))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(
                QRectF(plot_rect.right() + 6, y_cl - 8, right_margin - 10, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"CL={_fmt(cl_val, 2)}",
            )

        # UCL (Red dashed)
        if y_min <= ucl_val <= y_max:
            y_ucl = map_y(ucl_val)
            painter.setPen(QPen(QColor(RED), 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(plot_rect.left(), y_ucl), QPointF(plot_rect.right(), y_ucl))
            painter.setPen(QColor(RED))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(
                QRectF(plot_rect.right() + 6, y_ucl - 8, right_margin - 10, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"UCL={_fmt(ucl_val, 2)}",
            )

        # LCL (Red dashed, if > 0 or GenVar)
        if lcl_val > 0.0 and y_min <= lcl_val <= y_max:
            y_lcl = map_y(lcl_val)
            painter.setPen(QPen(QColor(RED), 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(plot_rect.left(), y_lcl), QPointF(plot_rect.right(), y_lcl))
            painter.setPen(QColor(RED))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(
                QRectF(plot_rect.right() + 6, y_lcl - 8, right_margin - 10, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"LCL={_fmt(lcl_val, 2)}",
            )

        # Plot Connected Data Points
        signals = set(self.result.get("signals", []))
        points: List[QPointF] = []
        for i, val in enumerate(values):
            points.append(QPointF(map_x(i), map_y(val)))

        # Connected Line
        if len(points) > 1:
            painter.setPen(QPen(QColor(BLUE), 1.5))
            for i in range(len(points) - 1):
                painter.drawLine(points[i], points[i + 1])

        # Point Markers & Alarm Digits
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        for i, pt in enumerate(points):
            subgroup_idx = i + 1
            is_alarm = subgroup_idx in signals

            if is_alarm:
                painter.setBrush(QColor(RED))
                painter.setPen(QPen(QColor(RED), 1))
                painter.drawEllipse(pt, 4.0, 4.0)

                # Draw '1' above point
                painter.drawText(
                    QRectF(pt.x() - 10, pt.y() - 18, 20, 14),
                    Qt.AlignmentFlag.AlignCenter,
                    "1",
                )
            else:
                painter.setBrush(QColor(BLUE))
                painter.setPen(QPen(QColor(BLUE), 1))
                painter.drawEllipse(pt, 3.0, 3.0)

        # Draw Hover Highlight
        if self.hover_point is not None:
            h_idx, h_x, h_y = self.hover_point
            if 0 <= h_idx < len(points):
                pt = points[h_idx]
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#ff9900"), 2))
                painter.drawEllipse(pt, 6.0, 6.0)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        k_obs = self.result.get("k_subgroups", 0)
        if k_obs == 0:
            super().mouseMoveEvent(event)
            return

        values = self.result.get("values", [])
        ucl_val = float(self.result.get("ucl_val", 0.0))
        lcl_val = float(self.result.get("lcl_val", 0.0))
        cl_val = float(self.result.get("center_line", 0.0))
        all_vals = values + [ucl_val, lcl_val, cl_val]
        y_min, y_max = _bounds(all_vals)

        top_margin = 60
        bottom_margin = 65
        left_margin = 85
        right_margin = 110
        plot_rect = QRectF(
            left_margin,
            top_margin,
            max(10.0, self.rect().width() - left_margin - right_margin),
            max(10.0, self.rect().height() - top_margin - bottom_margin),
        )

        def map_x(idx: int) -> float:
            if k_obs <= 1:
                return plot_rect.left() + plot_rect.width() / 2.0
            return plot_rect.left() + (idx / (k_obs - 1)) * plot_rect.width()

        def map_y(val: float) -> float:
            if y_max <= y_min:
                return plot_rect.top() + plot_rect.height() / 2.0
            ratio = (val - y_min) / (y_max - y_min)
            return plot_rect.bottom() - ratio * plot_rect.height()

        found_idx = None
        for i, val in enumerate(values):
            pt_x = map_x(i)
            pt_y = map_y(val)
            dist_sq = (pos.x() - pt_x) ** 2 + (pos.y() - pt_y) ** 2
            if dist_sq <= 100:  # within 10px radius
                found_idx = i
                break

        if found_idx is not None:
            val = values[found_idx]
            subgroup_idx = found_idx + 1
            signals = self.result.get("signals", [])
            is_sig = subgroup_idx in signals

            tip = (
                f"Subgroup: {subgroup_idx}\n"
                f"Value: {_fmt(val, 4)}\n"
                f"Center Line: {_fmt(cl_val, 4)}\n"
                f"UCL: {_fmt(ucl_val, 4)}"
            )
            if lcl_val > 0:
                tip += f"\nLCL: {_fmt(lcl_val, 4)}"

            if is_sig:
                tip += "\n* Test 1: Beyond control limit! *"
                decomps = self.result.get("decompositions", {}).get(subgroup_idx)
                if decomps:
                    tip += "\nUnivariate T Contributions:"
                    for k, v in decomps.items():
                        tip += f"\n  {k}: {_fmt(v, 2)}"

            QToolTip.showText(event.globalPosition().toPoint(), tip, self)
            self.hover_point = (found_idx, map_x(found_idx), map_y(val))
            self.update()
        else:
            if self.hover_point is not None:
                self.hover_point = None
                self.update()
            QToolTip.hideText()

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.objectSelected.emit(self.chart_type)
            if self.hover_point is not None:
                self.brushRowsSelected.emit([self.hover_point[0] + 1])
