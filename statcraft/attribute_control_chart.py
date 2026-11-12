"""High-fidelity Qt/QPainter renderer for Attributes Control Charts (P, NP, C, U).

Matches StatCraft visual styling:
- Single panel layout with high-contrast, clean typography
- Title: "<Chart> Chart of <Variable>"
- Stepped or straight UCL, Center Line, and LCL
- Right-hand margin limit and center callouts
- Blue connected points; red markers with test digits for special cause signals
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
    return (max(0.0, lo - pad) if lo >= 0 else lo - pad, hi + pad)


class AttributeControlChartWidget(GraphInteractionMixin, QWidget):
    """Single-panel control chart widget for P, NP, C, and U attribute charts."""

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

        self.chart_type = str(self.result.get("chart_type", self.result.get("chart", "P"))).upper()
        self.var_name = str(self.result.get("variable_name", "Data"))
        self.hover_point: Optional[Tuple[int, float, float]] = None
        self.panels = [{"name": self.chart_type}]

    def sizeHint(self) -> QSize:
        return QSize(820, 520)

    def _chart_data(self) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]], List[Optional[float]], Dict[int, List[int]]]:
        obs = self.result.get("observations", [])
        center = self.result.get("center_lines", [])
        ucl = self.result.get("ucl", [])
        lcl = self.result.get("lcl", [])
        tests = self.result.get("test_failures", {})
        return obs, center, ucl, lcl, tests

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor("#ffffff"))

        # Main title
        title_font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor(INK))
        raw_type = self.chart_type.replace("′", "'")
        if raw_type in ("P'", "P_PRIME", "LANEY_P"):
            chart_title = f"Laney P' Chart of {self.var_name}"
        elif raw_type in ("U'", "U_PRIME", "LANEY_U"):
            chart_title = f"Laney U' Chart of {self.var_name}"
        else:
            chart_title = f"{self.chart_type} Chart of {self.var_name}"
        painter.drawText(QRectF(20, 10, w - 40, 26), Qt.AlignmentFlag.AlignCenter, chart_title)

        is_const = self.result.get("is_constant_size", False)
        if not is_const:
            sub_font = QFont("Segoe UI", 8, QFont.Weight.Normal)
            painter.setFont(sub_font)
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(20, 32, w - 40, 18), Qt.AlignmentFlag.AlignCenter, "Tests are performed with unequal sample sizes.")

        # Plot area
        margin_left = 65
        margin_right = 110
        margin_top = 56
        margin_bottom = 50

        pw = w - margin_left - margin_right
        ph = h - margin_top - margin_bottom
        if pw <= 10 or ph <= 10:
            return

        plot_rect = QRectF(margin_left, margin_top, pw, ph)
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(plot_rect)

        obs, center, ucl, lcl, tests = self._chart_data()
        n = len(obs)
        if n == 0:
            return

        all_vals: List[float] = []
        for seq in (obs, center, ucl, lcl):
            for v in seq:
                if v is not None and not math.isnan(v) and not math.isinf(v):
                    all_vals.append(v)

        ymin, ymax = _bounds(all_vals)
        if ymax <= ymin:
            ymax = ymin + 1.0

        def to_screen_x(idx: int) -> float:
            if n <= 1:
                return margin_left + pw / 2.0
            return margin_left + (idx / float(n - 1)) * pw

        def to_screen_y(val: float) -> float:
            return margin_top + ph - ((val - ymin) / (ymax - ymin)) * ph

        # Grid lines (horizontal)
        n_ticks = 5
        grid_font = QFont("Segoe UI", 8)
        painter.setFont(grid_font)
        for i in range(n_ticks + 1):
            frac = i / float(n_ticks)
            vy = ymin + frac * (ymax - ymin)
            sy = to_screen_y(vy)
            painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(margin_left, sy), QPointF(margin_left + pw, sy))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(10, sy - 8, margin_left - 15, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, _fmt(vy, 3))

        # X-axis tick marks & labels
        step = max(1, n // 10)
        for i in range(0, n, step):
            sx = to_screen_x(i)
            painter.setPen(QPen(QColor(BORDER), 1))
            painter.drawLine(QPointF(sx, margin_top + ph), QPointF(sx, margin_top + ph + 4))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(sx - 15, margin_top + ph + 6, 30, 16), Qt.AlignmentFlag.AlignCenter, str(i + 1))

        # X-axis label
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(margin_left, margin_top + ph + 24, pw, 20), Qt.AlignmentFlag.AlignCenter, "Sample Number")

        # Stepped or continuous UCL, CL, LCL lines
        # UCL
        painter.setPen(QPen(QColor(RED), 1.5, Qt.PenStyle.DashLine))
        self._draw_limit_line(painter, ucl, to_screen_x, to_screen_y, is_const)

        # Center Line
        painter.setPen(QPen(QColor(GREEN), 1.5, Qt.PenStyle.SolidLine))
        self._draw_limit_line(painter, center, to_screen_x, to_screen_y, is_const)

        # LCL
        painter.setPen(QPen(QColor(RED), 1.5, Qt.PenStyle.DashLine))
        self._draw_limit_line(painter, lcl, to_screen_x, to_screen_y, is_const)

        # Right-hand annotations
        callout_font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(callout_font)

        # Last valid values for labels
        last_ucl = next((u for u in reversed(ucl) if u is not None), None)
        last_cl = next((c for c in reversed(center) if c is not None), None)
        last_lcl = next((l for l in reversed(lcl) if l is not None), None)

        cl_name = "P" if raw_type in ("P", "P'", "LANEY_P") else ("NP" if raw_type == "NP" else ("C" if raw_type == "C" else "U"))
        cl_prefix = f"_{cl_name}" if raw_type in ("P", "P'", "C", "U", "U'") else cl_name

        if last_ucl is not None:
            painter.setPen(QColor(RED))
            sy = to_screen_y(last_ucl)
            lbl = f"UCL={last_ucl:.4f}" if is_const else f"UCL={last_ucl:.4f}"
            painter.drawText(QRectF(margin_left + pw + 6, sy - 8, margin_right - 10, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lbl)

        if last_cl is not None:
            painter.setPen(QColor(GREEN))
            sy = to_screen_y(last_cl)
            lbl = f"{cl_prefix}={last_cl:.4f}"
            painter.drawText(QRectF(margin_left + pw + 6, sy - 8, margin_right - 10, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lbl)

        if last_lcl is not None:
            painter.setPen(QColor(RED))
            sy = to_screen_y(last_lcl)
            lbl = f"LCL={last_lcl:.4f}"
            painter.drawText(QRectF(margin_left + pw + 6, sy - 8, margin_right - 10, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lbl)

        # Data line & points
        line_pen = QPen(QColor(BLUE), 1.2)
        painter.setPen(line_pen)
        valid_points: List[Tuple[int, float, float, bool, List[int]]] = []

        last_pt: Optional[QPointF] = None
        for i in range(n):
            val = obs[i]
            if val is None or math.isnan(val):
                last_pt = None
                continue
            sx = to_screen_x(i)
            sy = to_screen_y(val)
            pt = QPointF(sx, sy)

            if last_pt is not None:
                painter.drawLine(last_pt, pt)
            last_pt = pt

            pt_failures = tests.get(i + 1, [])
            is_fail = bool(pt_failures)
            valid_points.append((i, sx, sy, is_fail, pt_failures))

        # Draw markers
        for idx, sx, sy, is_fail, fails in valid_points:
            if is_fail:
                painter.setPen(QPen(QColor(RED), 1.5))
                painter.setBrush(QColor(RED))
                painter.drawEllipse(QPointF(sx, sy), 4.0, 4.0)

                # Draw test number above point
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.setPen(QColor(RED))
                digit_str = str(fails[0]) if fails else "1"
                painter.drawText(QRectF(sx - 10, sy - 17, 20, 12), Qt.AlignmentFlag.AlignCenter, digit_str)
            else:
                painter.setPen(QPen(QColor(BLUE), 1))
                painter.setBrush(QColor(BLUE))
                painter.drawEllipse(QPointF(sx, sy), 3.0, 3.0)

    def _draw_limit_line(self, painter: QPainter, vals: List[Optional[float]], x_fn, y_fn, is_const: bool):
        n = len(vals)
        if is_const:
            first_val = next((v for v in vals if v is not None), None)
            if first_val is not None:
                sy = y_fn(first_val)
                painter.drawLine(QPointF(x_fn(0), sy), QPointF(x_fn(n - 1), sy))
            return

        # Stepped line for varying limits
        last_y: Optional[float] = None
        for i in range(n):
            v = vals[i]
            if v is None:
                last_y = None
                continue
            sy = y_fn(v)
            x_start = x_fn(max(0, i - 0.5)) if i > 0 else x_fn(0)
            x_end = x_fn(min(n - 1, i + 0.5)) if i < n - 1 else x_fn(n - 1)

            if last_y is not None and abs(last_y - sy) > 0.1:
                painter.drawLine(QPointF(x_start, last_y), QPointF(x_start, sy))
            painter.drawLine(QPointF(x_start, sy), QPointF(x_end, sy))
            last_y = sy

    def mouseMoveEvent(self, event):
        pos = event.position()
        w, h = self.width(), self.height()
        margin_left = 65
        margin_right = 110
        margin_top = 56
        margin_bottom = 50

        pw = w - margin_left - margin_right
        ph = h - margin_top - margin_bottom
        if pw <= 10 or ph <= 10:
            return

        obs, center, ucl, lcl, tests = self._chart_data()
        n = len(obs)
        if n == 0:
            return

        all_vals: List[float] = []
        for seq in (obs, center, ucl, lcl):
            for v in seq:
                if v is not None and not math.isnan(v) and not math.isinf(v):
                    all_vals.append(v)

        ymin, ymax = _bounds(all_vals)
        if ymax <= ymin:
            ymax = ymin + 1.0

        def to_screen_x(idx: int) -> float:
            if n <= 1:
                return margin_left + pw / 2.0
            return margin_left + (idx / float(n - 1)) * pw

        def to_screen_y(val: float) -> float:
            return margin_top + ph - ((val - ymin) / (ymax - ymin)) * ph

        # Find closest point
        closest_idx = -1
        min_dist = 12.0
        for i in range(n):
            val = obs[i]
            if val is None:
                continue
            sx = to_screen_x(i)
            sy = to_screen_y(val)
            dist = math.hypot(pos.x() - sx, pos.y() - sy)
            if dist < min_dist:
                min_dist = dist
                closest_idx = i

        if closest_idx >= 0:
            val = obs[closest_idx]
            sub_sz = self.result.get("subgroup_sizes", [1])[closest_idx]
            fails = tests.get(closest_idx + 1, [])
            tip_lines = [
                f"Subgroup: {closest_idx + 1}",
                f"Sample Size: {sub_sz}",
                f"Value: {_fmt(val, 4)}",
            ]
            if ucl[closest_idx] is not None:
                tip_lines.append(f"UCL: {_fmt(ucl[closest_idx], 4)}")
            if center[closest_idx] is not None:
                tip_lines.append(f"Center: {_fmt(center[closest_idx], 4)}")
            if lcl[closest_idx] is not None:
                tip_lines.append(f"LCL: {_fmt(lcl[closest_idx], 4)}")
            if fails:
                tip_lines.append(f"Failed Tests: {', '.join(str(f) for f in fails)}")

            QToolTip.showText(event.globalPosition().toPoint(), "\n".join(tip_lines), self)
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.objectSelected.emit(f"{self.chart_type} Chart")
