"""High-fidelity Qt/QPainter renderer for Rare Event Control Charts (G Chart & T Chart).

Matches StatCraft visual styling:
- High-contrast, clean typography
- Title: "G Chart of <Variable>" or "T Chart of <Variable>"
- Straight UCL, Center Line (Median), and LCL
- Right-hand margin limit and center callouts
- Blue connected series; red markers with test digits ('1' or 'B') for special cause signals
- Interactive tooltips with Observation number, Value, Limits, and Test Failures
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


class RareEventControlChartWidget(GraphInteractionMixin, QWidget):
    """Single-panel control chart widget for G and T rare event charts."""

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

        self.chart_type = str(self.result.get("chart_type", "G")).upper()
        self.var_name = str(self.result.get("variable_name", "Data"))
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

        # Main graph margin
        top_margin = 60
        bottom_margin = 65
        left_margin = 75
        right_margin = 95

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
        title = f"{self.chart_type} Chart of {self.var_name}"
        painter.drawText(QRectF(left_margin, 15, plot_rect.width(), 30), Qt.AlignmentFlag.AlignCenter, title)

        # Plot Border and Background
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(plot_rect)

        k_obs = self.result.get("k_subgroups", 0)
        if k_obs == 0:
            painter.setPen(QColor(MUTED))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(plot_rect, Qt.AlignmentFlag.AlignCenter, "No observation data available")
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
            if y_max == y_min:
                return plot_rect.center().y()
            frac = (val - y_min) / (y_max - y_min)
            return plot_rect.bottom() - frac * plot_rect.height()

        # Grid and Ticks
        font_axis = QFont("Segoe UI", 9)
        painter.setFont(font_axis)
        painter.setPen(QColor(MUTED))

        # Y Axis Ticks
        n_ticks = 5
        for t in range(n_ticks + 1):
            val = y_min + (t / n_ticks) * (y_max - y_min)
            y_pos = map_y(val)
            painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(plot_rect.left(), y_pos), QPointF(plot_rect.right(), y_pos))
            painter.setPen(QColor(MUTED))
            painter.drawText(
                QRectF(10, y_pos - 10, left_margin - 15, 20),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                _fmt(val, 2),
            )

        # X Axis Ticks
        step = max(1, k_obs // 10)
        for i in range(0, k_obs, step):
            x_pos = map_x(i)
            painter.setPen(QColor(MUTED))
            painter.drawLine(QPointF(x_pos, plot_rect.bottom()), QPointF(x_pos, plot_rect.bottom() + 4))
            painter.drawText(
                QRectF(x_pos - 20, plot_rect.bottom() + 6, 40, 20),
                Qt.AlignmentFlag.AlignCenter,
                str(i + 1),
            )

        # X Axis Label
        painter.drawText(
            QRectF(plot_rect.left(), plot_rect.bottom() + 30, plot_rect.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            "Sample Number",
        )

        # Center Line
        painter.setPen(QPen(QColor(GREEN), 1.5, Qt.PenStyle.SolidLine))
        y_cl = map_y(cl_val)
        painter.drawLine(QPointF(plot_rect.left(), y_cl), QPointF(plot_rect.right(), y_cl))

        # Center Line Callout
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor(GREEN))
        cl_tag = f"Median={_fmt(cl_val, 2)}"
        painter.drawText(
            QRectF(plot_rect.right() + 5, y_cl - 10, right_margin - 8, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            cl_tag,
        )

        # Control Limits
        pen_limit = QPen(QColor(RED), 1.2, Qt.PenStyle.DashLine)
        painter.setPen(pen_limit)
        y_ucl = map_y(ucl_val)
        y_lcl = map_y(lcl_val)
        painter.drawLine(QPointF(plot_rect.left(), y_ucl), QPointF(plot_rect.right(), y_ucl))
        painter.drawLine(QPointF(plot_rect.left(), y_lcl), QPointF(plot_rect.right(), y_lcl))

        # Limit Callouts
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor(RED))
        painter.drawText(
            QRectF(plot_rect.right() + 5, y_ucl - 10, right_margin - 8, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"UCL={_fmt(ucl_val, 2)}",
        )
        painter.drawText(
            QRectF(plot_rect.right() + 5, y_lcl - 10, right_margin - 8, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"LCL={_fmt(lcl_val, 2)}",
        )

        # Series Lines
        path_series = QPainterPath()
        path_series.moveTo(map_x(0), map_y(values[0]))
        for i in range(1, k_obs):
            path_series.lineTo(map_x(i), map_y(values[i]))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(BLUE), 1.5))
        painter.drawPath(path_series)

        # Points
        test1_set = set(self.result.get("test1_signals", []))
        benneyan_set = set(self.result.get("benneyan_signals", []))

        for i in range(k_obs):
            val = values[i]
            pt = QPointF(map_x(i), map_y(val))
            is_test1 = (i + 1) in test1_set
            is_benneyan = (i + 1) in benneyan_set

            if is_test1 or is_benneyan:
                painter.setPen(QPen(QColor(RED), 2))
                painter.setBrush(QColor(RED))
                painter.drawEllipse(pt, 4.5, 4.5)
                painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                digit = "1" if is_test1 else "B"
                painter.drawText(QRectF(pt.x() - 10, pt.y() - 18, 20, 16), Qt.AlignmentFlag.AlignCenter, digit)
            else:
                painter.setPen(QPen(QColor(BLUE), 1.5))
                painter.setBrush(QColor("#ffffff"))
                painter.drawEllipse(pt, 3.5, 3.5)

        # Hover point
        if self.hover_point is not None:
            h_idx, h_x, h_y = self.hover_point
            painter.setPen(QPen(QColor("#ff9900"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(h_x, h_y), 6.5, 6.5)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        k_obs = self.result.get("k_subgroups", 0)
        if k_obs == 0:
            super().mouseMoveEvent(event)
            return

        rect = self.rect()
        top_margin = 60
        bottom_margin = 65
        left_margin = 75
        right_margin = 95
        plot_rect = QRectF(
            left_margin,
            top_margin,
            max(10.0, rect.width() - left_margin - right_margin),
            max(10.0, rect.height() - top_margin - bottom_margin),
        )

        if not plot_rect.contains(pos):
            self.hover_point = None
            self.update()
            super().mouseMoveEvent(event)
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
            if y_max == y_min:
                return plot_rect.center().y()
            frac = (val - y_min) / (y_max - y_min)
            return plot_rect.bottom() - frac * plot_rect.height()

        best_dist = 18.0
        found: Optional[Tuple[int, float, float]] = None
        tooltip_text = ""

        test1_set = set(self.result.get("test1_signals", []))
        benneyan_set = set(self.result.get("benneyan_signals", []))

        for i in range(k_obs):
            px = map_x(i)
            py = map_y(values[i])
            d = math.hypot(px - pos.x(), py - pos.y())
            if d < best_dist:
                best_dist = d
                found = (i, px, py)
                status_parts = []
                if (i + 1) in test1_set:
                    status_parts.append("Test 1 Failed")
                if (i + 1) in benneyan_set:
                    status_parts.append("Benneyan Test Failed")
                stat_str = ", ".join(status_parts) if status_parts else "In Control"

                tooltip_text = (
                    f"Sample: {i + 1}\n"
                    f"Value: {_fmt(values[i], 4)}\n"
                    f"UCL: {_fmt(ucl_val, 4)}\n"
                    f"Median: {_fmt(cl_val, 4)}\n"
                    f"LCL: {_fmt(lcl_val, 4)}\n"
                    f"Status: {stat_str}"
                )

        self.hover_point = found
        self.update()

        if found is not None and tooltip_text:
            QToolTip.showText(event.globalPosition().toPoint(), tooltip_text, self)
        else:
            QToolTip.hideText()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self.hover_point = None
        self.update()
        QToolTip.hideText()
        super().leaveEvent(event)
