"""High-fidelity Qt/QPainter charts for Nonparametric Statistical Tests.

Renders authentic StatCraft visual charts:
- Group Comparison Plots for Mann-Whitney & Kruskal-Wallis
- Mood's Median Confidence Interval Plot with overall median reference
- Sequence Runs Chart with threshold line and runs metrics
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
RED = "#d9534f"
GREEN = "#2ca02c"
ORANGE = "#ff7f0e"
INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
GRID = "#e8ecef"
BOX_BG = "#f8f9fa"


def _fmt(val: Optional[float], dec: int = 3) -> str:
    if val is None or math.isnan(val):
        return "*"
    if val == float("inf"):
        return "Inf"
    if val == float("-inf"):
        return "-Inf"
    return f"{val:.{dec}f}"


class NonparametricChartWidget(GraphInteractionMixin, QWidget):
    """High-DPI renderer for Nonparametric analysis charts."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", {})
        self.recipe = entry.get("recipe", {})

        self.analysis = self.result.get("analysis", "mann_whitney")
        self.title_text = self.result.get("title") or "Nonparametric Analysis Plot"

        self.setMinimumSize(640, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.hover_point: Optional[Tuple[float, float, str]] = None

    def sizeHint(self) -> QSize:
        return QSize(780, 480)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect()
        painter.fillRect(rect, QColor("#ffffff"))

        if self.analysis == "runs_test":
            self._paint_runs_plot(painter, rect)
        elif self.analysis == "moods_median":
            self._paint_moods_median_plot(painter, rect)
        else:
            self._paint_group_comparison_plot(painter, rect)

    def _paint_runs_plot(self, painter: QPainter, rect: QRectF) -> None:
        values = self.result.get("values", [])
        n = len(values)
        if n < 2:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No observations to display for Runs Test.")
            return

        k_val = float(self.result.get("k_threshold", 0.0))
        runs = self.result.get("runs", 1)
        p_val = self.result.get("p_value", 1.0)

        # Plot margins
        top = 65.0
        bottom = rect.height() - 55.0
        left = 75.0
        right = rect.width() - 210.0
        plot_w = right - left
        plot_h = bottom - top

        # Title
        painter.setPen(QColor(INK))
        font_title = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font_title)
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, self.title_text)

        font_sub = QFont("Segoe UI", 9)
        painter.setFont(font_sub)
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(left, 40, rect.width() - left - 20, 20), Qt.AlignmentFlag.AlignLeft, f"Sequence plot around baseline K = {_fmt(k_val, 4)}")

        # Scales
        y_min = min(min(values), k_val)
        y_max = max(max(values), k_val)
        y_range = max(1e-6, y_max - y_min)
        y_pad = y_range * 0.1
        y_min -= y_pad
        y_max += y_pad

        def to_screen(idx: int, val: float) -> QPointF:
            x = left + (idx / float(n - 1)) * plot_w
            y = bottom - ((val - y_min) / (y_max - y_min)) * plot_h
            return QPointF(x, y)

        # Draw grid & axes
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        # Horizontal baseline at K
        y_k = bottom - ((k_val - y_min) / (y_max - y_min)) * plot_h
        pen_k = QPen(QColor(RED), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen_k)
        painter.drawLine(QPointF(left, y_k), QPointF(right, y_k))

        # Baseline label
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(RED))
        painter.drawText(QRectF(left + 5, y_k - 18, 120, 15), Qt.AlignmentFlag.AlignLeft, f"K = {_fmt(k_val, 3)}")

        # Connect data points with line
        pen_line = QPen(QColor(BORDER), 1)
        painter.setPen(pen_line)
        path = QPainterPath()
        for i, v in enumerate(values):
            pt = to_screen(i, v)
            if i == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        painter.drawPath(path)

        # Draw points
        for i, v in enumerate(values):
            pt = to_screen(i, v)
            if v >= k_val:
                painter.setBrush(QColor(BLUE_FILL))
                painter.setPen(QPen(QColor(BLUE), 1.2))
                painter.drawEllipse(pt, 4.0, 4.0)
            else:
                painter.setBrush(QColor("#ffffff"))
                painter.setPen(QPen(QColor(ORANGE), 1.5))
                painter.drawEllipse(pt, 4.0, 4.0)

        # X Axis labels
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(left - 20, bottom + 5, 40, 15), Qt.AlignmentFlag.AlignCenter, "1")
        painter.drawText(QRectF(right - 20, bottom + 5, 40, 15), Qt.AlignmentFlag.AlignCenter, str(n))
        painter.drawText(QRectF(left, bottom + 25, plot_w, 20), Qt.AlignmentFlag.AlignCenter, "Observation Order")

        # Y Axis labels
        painter.drawText(QRectF(left - 70, top - 8, 60, 15), Qt.AlignmentFlag.AlignRight, _fmt(y_max, 2))
        painter.drawText(QRectF(left - 70, bottom - 8, 60, 15), Qt.AlignmentFlag.AlignRight, _fmt(y_min, 2))

        # Inset Summary Box on Right
        panel_x = right + 15.0
        panel_y = top
        panel_w = 180.0
        panel_h = 170.0
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor(BOX_BG))
        painter.drawRoundedRect(QRectF(panel_x, panel_y, panel_w, panel_h), 4, 4)

        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(panel_x + 10, panel_y + 10, panel_w - 20, 20), Qt.AlignmentFlag.AlignLeft, "Runs Test Summary")

        painter.setFont(QFont("Segoe UI", 8))
        stats_rows = [
            ("Baseline K:", _fmt(k_val, 4)),
            ("Observed Runs:", str(runs)),
            ("Expected Runs:", _fmt(self.result.get("expected_runs"), 2)),
            ("N >= K:", str(self.result.get("n_above_or_equal", 0))),
            ("N < K:", str(self.result.get("n_below", 0))),
            ("Z-Value:", _fmt(self.result.get("z"), 2)),
            ("P-Value:", _fmt(p_val, 4)),
        ]
        curr_y = panel_y + 35
        for lbl, val_str in stats_rows:
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(panel_x + 10, curr_y, 95, 16), Qt.AlignmentFlag.AlignLeft, lbl)
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(panel_x + 105, curr_y, 65, 16), Qt.AlignmentFlag.AlignRight, val_str)
            curr_y += 18

    def _paint_moods_median_plot(self, painter: QPainter, rect: QRectF) -> None:
        rows = self.result.get("group_rows", [])
        k = len(rows)
        if k == 0:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No group data available.")
            return

        overall_med = float(self.result.get("overall_median", 0.0))
        chi2 = self.result.get("chi_square", 0.0)
        df = self.result.get("df", 1)
        p_val = self.result.get("p_value", 1.0)
        conf_pct = int(self.result.get("confidence", 0.95) * 100.0)

        # Plot margins
        top = 65.0
        bottom = rect.height() - 60.0
        left = 80.0
        right = rect.width() - 40.0
        plot_w = right - left
        plot_h = bottom - top

        # Title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, self.title_text)

        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(left, 40, rect.width() - left - 20, 20), Qt.AlignmentFlag.AlignLeft,
                         f"Individual {conf_pct}% CIs for Medians | Chi-Square = {_fmt(chi2, 2)}, DF = {df}, P = {_fmt(p_val, 3)}")

        # Range across medians and CIs
        all_vals = [overall_med]
        for r in rows:
            all_vals.append(r["median"])
            ci = r.get("ci", (r["median"], r["median"]))
            all_vals.extend([ci[0], ci[1]])

        y_min = min(all_vals)
        y_max = max(all_vals)
        y_range = max(1e-6, y_max - y_min)
        y_pad = y_range * 0.15
        y_min -= y_pad
        y_max += y_pad

        # Draw frame
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        # Overall median reference line
        y_ov = bottom - ((overall_med - y_min) / (y_max - y_min)) * plot_h
        painter.setPen(QPen(QColor(RED), 1.5, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(left, y_ov), QPointF(right, y_ov))
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(RED))
        painter.drawText(QRectF(left + 8, y_ov - 16, 160, 15), Qt.AlignmentFlag.AlignLeft, f"Overall Median = {_fmt(overall_med, 3)}")

        # Groups spacing
        col_w = plot_w / float(k)
        for i, row in enumerate(rows):
            cx = left + (i + 0.5) * col_w
            med = row["median"]
            ci = row.get("ci", (med, med))

            cy_med = bottom - ((med - y_min) / (y_max - y_min)) * plot_h
            cy_low = bottom - ((ci[0] - y_min) / (y_max - y_min)) * plot_h
            cy_high = bottom - ((ci[1] - y_min) / (y_max - y_min)) * plot_h

            # Draw CI whisker line
            painter.setPen(QPen(QColor(BLUE), 2))
            painter.drawLine(QPointF(cx, cy_low), QPointF(cx, cy_high))
            # Caps
            cap_w = 8.0
            painter.drawLine(QPointF(cx - cap_w, cy_low), QPointF(cx + cap_w, cy_low))
            painter.drawLine(QPointF(cx - cap_w, cy_high), QPointF(cx + cap_w, cy_high))

            # Median marker
            painter.setBrush(QColor(BLUE_FILL))
            painter.setPen(QPen(QColor(BLUE), 1.5))
            painter.drawEllipse(QPointF(cx, cy_med), 5.0, 5.0)

            # Label on X axis
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor(INK))
            lvl_name = str(row["level"])
            painter.drawText(QRectF(cx - col_w * 0.45, bottom + 8, col_w * 0.9, 18), Qt.AlignmentFlag.AlignCenter, lvl_name)

            # N count under name
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(cx - col_w * 0.45, bottom + 26, col_w * 0.9, 15), Qt.AlignmentFlag.AlignCenter, f"N={row['n']}")

        # Y Axis labels
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(left - 75, top - 8, 65, 15), Qt.AlignmentFlag.AlignRight, _fmt(y_max, 2))
        painter.drawText(QRectF(left - 75, bottom - 8, 65, 15), Qt.AlignmentFlag.AlignRight, _fmt(y_min, 2))
        painter.drawText(QRectF(left - 75, (top + bottom) / 2.0 - 8, 65, 15), Qt.AlignmentFlag.AlignRight, _fmt((y_min + y_max) / 2.0, 2))

    def _paint_group_comparison_plot(self, painter: QPainter, rect: QRectF) -> None:
        # Mann-Whitney or Kruskal-Wallis comparison plot
        group_stats = self.result.get("group_stats", [])
        if not group_stats:
            # Fallback for Mann-Whitney 2-sample
            if "median1" in self.result:
                group_stats = [
                    {"level": "Sample 1", "median": self.result.get("median1"), "n": self.result.get("n1", 0)},
                    {"level": "Sample 2", "median": self.result.get("median2"), "n": self.result.get("n2", 0)},
                ]

        k = len(group_stats)
        if k == 0:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No group data to display.")
            return

        # Margins
        top = 65.0
        bottom = rect.height() - 60.0
        left = 80.0
        right = rect.width() - 40.0
        plot_w = right - left
        plot_h = bottom - top

        # Title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, self.title_text)

        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(MUTED))
        sub_text = f"P-Value = {_fmt(self.result.get('p_value'), 4)}"
        if "h_statistic" in self.result:
            sub_text = f"H = {_fmt(self.result.get('h_statistic'), 2)}, DF = {self.result.get('df', 1)}, P = {_fmt(self.result.get('p_value'), 3)}"
        elif "statistic_w" in self.result:
            sub_text = f"W = {_fmt(self.result.get('statistic_w'), 1)}, P = {_fmt(self.result.get('p_value'), 4)}"
        painter.drawText(QRectF(left, 40, rect.width() - left - 20, 20), Qt.AlignmentFlag.AlignLeft, sub_text)

        # Bounds
        meds = [float(g["median"]) for g in group_stats if g.get("median") is not None]
        y_min = min(meds) if meds else 0.0
        y_max = max(meds) if meds else 1.0
        y_range = max(1e-6, y_max - y_min)
        y_pad = y_range * 0.3
        y_min -= y_pad
        y_max += y_pad

        # Draw frame
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        col_w = plot_w / float(k)
        for i, g in enumerate(group_stats):
            cx = left + (i + 0.5) * col_w
            med = float(g.get("median", 0.0))
            cy = bottom - ((med - y_min) / (y_max - y_min)) * plot_h

            # Group column box bar
            box_w = min(60.0, col_w * 0.5)
            painter.setPen(QPen(QColor(BLUE), 1.5))
            painter.setBrush(QColor("#e8f4fd"))
            painter.drawRoundedRect(QRectF(cx - box_w / 2.0, cy - 12, box_w, 24), 3, 3)

            # Center median marker
            painter.setPen(QPen(QColor(BLUE), 2))
            painter.drawLine(QPointF(cx - box_w / 2.0, cy), QPointF(cx + box_w / 2.0, cy))
            painter.setBrush(QColor(BLUE))
            painter.drawEllipse(QPointF(cx, cy), 4.0, 4.0)

            # Value label
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(cx - box_w / 2.0, cy - 28, box_w, 14), Qt.AlignmentFlag.AlignCenter, _fmt(med, 3))

            # X label
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(QRectF(cx - col_w * 0.45, bottom + 8, col_w * 0.9, 18), Qt.AlignmentFlag.AlignCenter, str(g.get("level", "")))
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(cx - col_w * 0.45, bottom + 26, col_w * 0.9, 15), Qt.AlignmentFlag.AlignCenter, f"N={g.get('n', 0)}")

        # Y Axis
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(left - 75, top - 8, 65, 15), Qt.AlignmentFlag.AlignRight, _fmt(y_max, 2))
        painter.drawText(QRectF(left - 75, bottom - 8, 65, 15), Qt.AlignmentFlag.AlignRight, _fmt(y_min, 2))
