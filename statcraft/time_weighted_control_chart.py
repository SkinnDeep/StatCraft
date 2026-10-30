"""High-fidelity Qt/QPainter renderer for Time-Weighted Control Charts (EWMA, Moving Average, CUSUM).

Matches StatCraft visual styling:
- High-contrast, clean typography
- Title: "<Chart> Chart of <Variable>"
- Stepped or curved dynamic limits for EWMA / MA
- Dual Upper and Lower CUSUM lines with +/- h decision limits for CUSUM
- Right-hand margin limit and center callouts
- Blue connected series; red markers with test digits for special cause signals
- Interactive tooltips with Subgroup number, Sample Size, Value, and Test Failures
- Full GraphInteractionMixin integration with objectSelected, objectActivated, brushRowsSelected
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .graph_interaction import GraphInteractionMixin

BLUE = "#0061a8"
TEAL = "#008080"
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
        return (lo - delta, hi + delta)
    pad = (hi - lo) * pad_frac
    return (lo - pad, hi + pad)


class TimeWeightedControlChartWidget(GraphInteractionMixin, QWidget):
    """Single-panel control chart widget for EWMA, Moving Average, and CUSUM charts."""

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

        self.chart_type = str(self.result.get("chart_type", "EWMA")).upper()
        self.var_name = str(self.result.get("variable_name", "Data"))
        self.hover_point: Optional[Tuple[int, float, float]] = None
        self.panels = [{"name": self.chart_type}]

    def sizeHint(self) -> QSize:
        return QSize(820, 520)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
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

        # Draw Title
        painter.setPen(QColor(INK))
        font_title = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font_title)
        if self.chart_type == "EWMA":
            title = f"EWMA Chart of {self.var_name}"
        elif self.chart_type in ("MA", "MOVING_AVERAGE"):
            title = f"Moving Average Chart of {self.var_name}"
        elif self.chart_type == "CUSUM":
            title = f"CUSUM Chart of {self.var_name}"
        else:
            title = f"{self.chart_type} Chart of {self.var_name}"
        painter.drawText(QRectF(left_margin, 15, plot_rect.width(), 30), Qt.AlignmentFlag.AlignCenter, title)

        # Plot Border and Background
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(plot_rect)

        k_subgroups = self.result.get("k_subgroups", 0)
        if k_subgroups == 0:
            painter.setPen(QColor(MUTED))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(plot_rect, Qt.AlignmentFlag.AlignCenter, "No subgroup data available")
            return

        is_cusum = self.chart_type == "CUSUM"

        if is_cusum:
            c_plus = self.result.get("c_plus", [])
            c_minus_plotted = self.result.get("c_minus_plotted", [])
            h_val = float(self.result.get("h", 4.0))
            all_vals = c_plus + c_minus_plotted + [h_val, -h_val, 0.0]
            y_min, y_max = _bounds(all_vals)
            cl_val = 0.0
            ucl_list = [h_val] * k_subgroups
            lcl_list = [-h_val] * k_subgroups
        else:
            values = self.result.get("values", [])
            ucl_list = self.result.get("ucl", [])
            lcl_list = self.result.get("lcl", [])
            cl_val = float(self.result.get("center_line", 0.0))
            all_vals = list(values) + list(ucl_list) + list(lcl_list) + [cl_val]
            y_min, y_max = _bounds(all_vals)

        def map_x(idx: int) -> float:
            if k_subgroups <= 1:
                return plot_rect.left() + plot_rect.width() / 2.0
            return plot_rect.left() + (idx / (k_subgroups - 1)) * plot_rect.width()

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
                _fmt(val, 3 if is_cusum else 2),
            )

        # X Axis Subgroup Ticks
        step = max(1, k_subgroups // 10)
        for i in range(0, k_subgroups, step):
            x_pos = map_x(i)
            painter.setPen(QColor(MUTED))
            painter.drawLine(QPointF(x_pos, plot_rect.bottom()), QPointF(x_pos, plot_rect.bottom() + 4))
            painter.drawText(
                QRectF(x_pos - 20, plot_rect.bottom() + 6, 40, 20),
                Qt.AlignmentFlag.AlignCenter,
                str(i + 1),
            )

        # Subgroup Label
        painter.drawText(
            QRectF(plot_rect.left(), plot_rect.bottom() + 30, plot_rect.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            "Sample" if self.result.get("subgroup_size_name") is None else "Subgroup",
        )

        # Center Line
        painter.setPen(QPen(QColor(GREEN), 1.5, Qt.PenStyle.SolidLine))
        y_cl = map_y(cl_val)
        painter.drawLine(QPointF(plot_rect.left(), y_cl), QPointF(plot_rect.right(), y_cl))

        # Center Line Callout
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor(GREEN))
        cl_tag = f"Target={_fmt(self.result.get('target', cl_val), 3)}" if is_cusum else f"_X={_fmt(cl_val, 3)}"
        painter.drawText(
            QRectF(plot_rect.right() + 5, y_cl - 10, right_margin - 8, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            cl_tag,
        )

        # Draw Upper and Lower Control Limits
        pen_limit = QPen(QColor(RED), 1.2, Qt.PenStyle.DashLine)
        painter.setPen(pen_limit)

        path_ucl = QPainterPath()
        path_lcl = QPainterPath()
        path_ucl.moveTo(map_x(0), map_y(ucl_list[0]))
        path_lcl.moveTo(map_x(0), map_y(lcl_list[0]))
        for i in range(1, k_subgroups):
            path_ucl.lineTo(map_x(i), map_y(ucl_list[i]))
            path_lcl.lineTo(map_x(i), map_y(lcl_list[i]))

        painter.drawPath(path_ucl)
        painter.drawPath(path_lcl)

        # Callouts for UCL and LCL on right margin
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor(RED))
        ucl_end = ucl_list[-1]
        lcl_end = lcl_list[-1]
        ucl_tag = f"h={_fmt(ucl_end, 3)}" if is_cusum else f"UCL={_fmt(ucl_end, 3)}"
        lcl_tag = f"-h={_fmt(lcl_end, 3)}" if is_cusum else f"LCL={_fmt(lcl_end, 3)}"
        painter.drawText(
            QRectF(plot_rect.right() + 5, map_y(ucl_end) - 10, right_margin - 8, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            ucl_tag,
        )
        painter.drawText(
            QRectF(plot_rect.right() + 5, map_y(lcl_end) - 10, right_margin - 8, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            lcl_tag,
        )

        # Connect Series and Draw Points
        signals = set(self.result.get("signals", []))

        if is_cusum:
            # Draw Upper CUSUM series (C+) in BLUE
            c_plus = self.result.get("c_plus", [])
            path_cp = QPainterPath()
            path_cp.moveTo(map_x(0), map_y(c_plus[0]))
            for i in range(1, k_subgroups):
                path_cp.lineTo(map_x(i), map_y(c_plus[i]))
            painter.setPen(QPen(QColor(BLUE), 1.5))
            painter.drawPath(path_cp)

            # Draw Lower CUSUM series (C-) in TEAL
            c_minus_p = self.result.get("c_minus_plotted", [])
            path_cm = QPainterPath()
            path_cm.moveTo(map_x(0), map_y(c_minus_p[0]))
            for i in range(1, k_subgroups):
                path_cm.lineTo(map_x(i), map_y(c_minus_p[i]))
            painter.setPen(QPen(QColor(TEAL), 1.5))
            painter.drawPath(path_cm)

            # Points for C+
            for i in range(k_subgroups):
                val = c_plus[i]
                pt = QPointF(map_x(i), map_y(val))
                is_ooc = (i + 1) in signals and val > ucl_list[i]
                if is_ooc:
                    painter.setPen(QPen(QColor(RED), 2))
                    painter.setBrush(QColor(RED))
                    painter.drawEllipse(pt, 4.5, 4.5)
                    painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                    painter.drawText(QRectF(pt.x() - 10, pt.y() - 20, 20, 16), Qt.AlignmentFlag.AlignCenter, "1")
                else:
                    painter.setPen(QPen(QColor(BLUE), 1.5))
                    painter.setBrush(QColor("#ffffff"))
                    painter.drawEllipse(pt, 3.5, 3.5)

            # Points for C-
            for i in range(k_subgroups):
                val = c_minus_p[i]
                pt = QPointF(map_x(i), map_y(val))
                raw_cm = self.result.get("c_minus", [])[i]
                is_ooc = (i + 1) in signals and raw_cm > ucl_list[i]
                if is_ooc:
                    painter.setPen(QPen(QColor(RED), 2))
                    painter.setBrush(QColor(RED))
                    painter.drawEllipse(pt, 4.5, 4.5)
                    painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                    painter.drawText(QRectF(pt.x() - 10, pt.y() + 6, 20, 16), Qt.AlignmentFlag.AlignCenter, "1")
                else:
                    painter.setPen(QPen(QColor(TEAL), 1.5))
                    painter.setBrush(QColor("#ffffff"))
                    painter.drawEllipse(pt, 3.5, 3.5)

        else:
            # EWMA or MA
            values = self.result.get("values", [])
            path_series = QPainterPath()
            path_series.moveTo(map_x(0), map_y(values[0]))
            for i in range(1, k_subgroups):
                path_series.lineTo(map_x(i), map_y(values[i]))

            painter.setPen(QPen(QColor(BLUE), 1.5))
            painter.drawPath(path_series)

            for i in range(k_subgroups):
                val = values[i]
                pt = QPointF(map_x(i), map_y(val))
                is_ooc = (i + 1) in signals

                if is_ooc:
                    painter.setPen(QPen(QColor(RED), 2))
                    painter.setBrush(QColor(RED))
                    painter.drawEllipse(pt, 4.5, 4.5)
                    painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                    painter.drawText(QRectF(pt.x() - 10, pt.y() - 18, 20, 16), Qt.AlignmentFlag.AlignCenter, "1")
                else:
                    painter.setPen(QPen(QColor(BLUE), 1.5))
                    painter.setBrush(QColor("#ffffff"))
                    painter.drawEllipse(pt, 3.5, 3.5)

        # Highlight hover point if active
        if self.hover_point is not None:
            h_idx, h_x, h_y = self.hover_point
            painter.setPen(QPen(QColor("#ff9900"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(h_x, h_y), 6.5, 6.5)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        k_subgroups = self.result.get("k_subgroups", 0)
        if k_subgroups == 0:
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

        is_cusum = self.chart_type == "CUSUM"

        if is_cusum:
            c_plus = self.result.get("c_plus", [])
            c_minus_plotted = self.result.get("c_minus_plotted", [])
            h_val = float(self.result.get("h", 4.0))
            all_vals = c_plus + c_minus_plotted + [h_val, -h_val, 0.0]
            y_min, y_max = _bounds(all_vals)
        else:
            values = self.result.get("values", [])
            ucl_list = self.result.get("ucl", [])
            lcl_list = self.result.get("lcl", [])
            cl_val = float(self.result.get("center_line", 0.0))
            all_vals = list(values) + list(ucl_list) + list(lcl_list) + [cl_val]
            y_min, y_max = _bounds(all_vals)

        def map_x(idx: int) -> float:
            if k_subgroups <= 1:
                return plot_rect.left() + plot_rect.width() / 2.0
            return plot_rect.left() + (idx / (k_subgroups - 1)) * plot_rect.width()

        def map_y(val: float) -> float:
            if y_max == y_min:
                return plot_rect.center().y()
            frac = (val - y_min) / (y_max - y_min)
            return plot_rect.bottom() - frac * plot_rect.height()

        best_dist = 18.0
        found: Optional[Tuple[int, float, float]] = None
        tooltip_text = ""

        sizes = self.result.get("subgroup_sizes", [])
        signals = set(self.result.get("signals", []))

        if is_cusum:
            c_plus = self.result.get("c_plus", [])
            c_minus_p = self.result.get("c_minus_plotted", [])
            c_minus = self.result.get("c_minus", [])
            for i in range(k_subgroups):
                # Check C+
                px = map_x(i)
                py1 = map_y(c_plus[i])
                d1 = math.hypot(px - pos.x(), py1 - pos.y())
                if d1 < best_dist:
                    best_dist = d1
                    found = (i, px, py1)
                    n_i = sizes[i] if i < len(sizes) else 1
                    sig_info = "Yes (Test 1)" if (i + 1) in signals else "No"
                    tooltip_text = (
                        f"Subgroup: {i + 1}\n"
                        f"Sample Size: {n_i}\n"
                        f"Upper CUSUM (C+): {_fmt(c_plus[i], 4)}\n"
                        f"Decision Limit (h): {_fmt(self.result.get('h'), 4)}\n"
                        f"Signal: {sig_info}"
                    )

                # Check C-
                py2 = map_y(c_minus_p[i])
                d2 = math.hypot(px - pos.x(), py2 - pos.y())
                if d2 < best_dist:
                    best_dist = d2
                    found = (i, px, py2)
                    n_i = sizes[i] if i < len(sizes) else 1
                    sig_info = "Yes (Test 1)" if (i + 1) in signals else "No"
                    tooltip_text = (
                        f"Subgroup: {i + 1}\n"
                        f"Sample Size: {n_i}\n"
                        f"Lower CUSUM (C-): {_fmt(c_minus[i], 4)}\n"
                        f"Plotted: {_fmt(c_minus_p[i], 4)}\n"
                        f"Decision Limit (-h): -{_fmt(self.result.get('h'), 4)}\n"
                        f"Signal: {sig_info}"
                    )
        else:
            values = self.result.get("values", [])
            ucl_list = self.result.get("ucl", [])
            lcl_list = self.result.get("lcl", [])
            for i in range(k_subgroups):
                px = map_x(i)
                py = map_y(values[i])
                d = math.hypot(px - pos.x(), py - pos.y())
                if d < best_dist:
                    best_dist = d
                    found = (i, px, py)
                    n_i = sizes[i] if i < len(sizes) else 1
                    sig_info = "Test 1 Failed" if (i + 1) in signals else "In Control"
                    tooltip_text = (
                        f"Subgroup: {i + 1}\n"
                        f"Sample Size: {n_i}\n"
                        f"Value: {_fmt(values[i], 4)}\n"
                        f"UCL: {_fmt(ucl_list[i], 4)}\n"
                        f"Center: {_fmt(self.result.get('center_line'), 4)}\n"
                        f"LCL: {_fmt(lcl_list[i], 4)}\n"
                        f"Status: {sig_info}"
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
