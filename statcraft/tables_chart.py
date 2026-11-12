"""High-fidelity Qt/QPainter charts for Tables and Chi-Square analysis.

Renders authentic StatCraft contingency and goodness-of-fit charts:
- Clustered Bar Chart: Observed counts across row and column categories
- Goodness-of-Fit Comparison Chart: Side-by-side Observed vs Expected frequencies
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

PALETTE = [
    "#1f77b4",  # Blue
    "#ff7f0e",  # Orange
    "#2ca02c",  # Green
    "#d62728",  # Red
    "#9467bd",  # Purple
    "#8c564b",  # Brown
    "#e377c2",  # Pink
    "#17becf",  # Cyan
]
INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
GRID = "#e8ecef"


class TablesChartWidget(GraphInteractionMixin, QWidget):
    """High-DPI renderer for Tables and Chi-Square charts."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", {})
        self.recipe = entry.get("recipe", {})

        self.analysis = self.result.get("analysis", "cross_tabulation")
        self.title_text = self.result.get("title") or "Contingency Chart"

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

        if self.analysis in ("cross_tabulation", "chi_square_association_table"):
            self._paint_contingency_bars(painter, rect)
        elif self.analysis == "chi_square_goodness_of_fit":
            self._paint_goodness_of_fit_bars(painter, rect)
        else:
            self._paint_tally_bars(painter, rect)

    def _paint_contingency_bars(self, painter: QPainter, rect: QRectF) -> None:
        top = 70.0
        bottom = rect.height() - 70.0
        left = 70.0
        right = rect.width() - 170.0  # leave room for legend
        plot_w = right - left
        plot_h = bottom - top

        # Title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        r_name = self.result.get("row_name", "Row")
        c_name = self.result.get("col_name", "Column")
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, f"Clustered Bar Chart: {r_name} by {c_name}")

        # Subtitle: Chi-Square stats
        chi = self.result.get("pearson_chi_square", 0.0)
        df = self.result.get("df", 1)
        pval = self.result.get("pearson_p_value", 1.0)
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(left, 42, rect.width() - left - 20, 20), Qt.AlignmentFlag.AlignLeft, f"Pearson Chi-Square = {chi:.3f}, DF = {df}, P-Value = {pval:.4f}")

        row_labels = self.result.get("row_labels") or self.result.get("row_names") or []
        col_labels = self.result.get("col_labels") or self.result.get("col_names") or []
        obs = self.result.get("observed", [])

        if not row_labels or not col_labels or not obs:
            return

        # Determine Max Y
        max_val = max(max(r) for r in obs) if obs else 10.0
        max_y = max_val * 1.15 if max_val > 0 else 10.0

        # Axes
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        # Y grid
        y_ticks = 5
        painter.setFont(QFont("Segoe UI", 8))
        for step in range(y_ticks + 1):
            val = (step / y_ticks) * max_y
            y_px = bottom - (step / y_ticks) * plot_h
            painter.setPen(QPen(QColor(GRID), 1))
            painter.drawLine(QPointF(left, y_px), QPointF(right, y_px))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(10, y_px - 8, left - 18, 16), Qt.AlignmentFlag.AlignRight, f"{val:.0f}")

        # X clusters
        n_clusters = len(row_labels)
        cluster_w = plot_w / n_clusters
        n_cols = len(col_labels)
        bar_w = min(36.0, (cluster_w * 0.75) / n_cols)

        for i, rl in enumerate(row_labels):
            cx = left + i * cluster_w + cluster_w / 2.0
            # Cluster label
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(cx - cluster_w / 2, bottom + 8, cluster_w, 20), Qt.AlignmentFlag.AlignCenter, rl)

            cluster_start_x = cx - (n_cols * bar_w) / 2.0
            for j, cl in enumerate(col_labels):
                val = obs[i][j]
                bh = (val / max_y) * plot_h if max_y > 0 else 0
                bx = cluster_start_x + j * bar_w
                by = bottom - bh

                color = QColor(PALETTE[j % len(PALETTE)])
                painter.setBrush(color)
                painter.setPen(QPen(color.darker(120), 1))
                painter.drawRect(QRectF(bx + 1, by, bar_w - 2, bh))

        # Y Axis Title
        painter.save()
        painter.translate(22, top + plot_h / 2)
        painter.rotate(-90)
        painter.drawText(QRectF(-100, -10, 200, 20), Qt.AlignmentFlag.AlignCenter, "Count")
        painter.restore()

        # Legend
        leg_x = right + 18.0
        leg_y = top + 10.0
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(leg_x, leg_y, 140, 20), Qt.AlignmentFlag.AlignLeft, c_name)
        leg_y += 24.0

        painter.setFont(QFont("Segoe UI", 8))
        for j, cl in enumerate(col_labels):
            color = QColor(PALETTE[j % len(PALETTE)])
            painter.fillRect(QRectF(leg_x, leg_y + 2, 12, 12), color)
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(leg_x + 18, leg_y, 130, 16), Qt.AlignmentFlag.AlignLeft, cl)
            leg_y += 20.0

    def _paint_goodness_of_fit_bars(self, painter: QPainter, rect: QRectF) -> None:
        top = 70.0
        bottom = rect.height() - 70.0
        left = 70.0
        right = rect.width() - 170.0
        plot_w = right - left
        plot_h = bottom - top

        # Title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        v_name = self.result.get("var_name", "Category")
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, f"Goodness-of-Fit Chart: {v_name}")

        chi = self.result.get("chi_square", 0.0)
        df = self.result.get("df", 1)
        pval = self.result.get("p_value", 1.0)
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(left, 42, rect.width() - left - 20, 20), Qt.AlignmentFlag.AlignLeft, f"Chi-Square = {chi:.3f}, DF = {df}, P-Value = {pval:.4f}")

        rows = self.result.get("rows", [])
        if not rows:
            return

        max_val = max(max(r["observed"], r["expected"]) for r in rows)
        max_y = max_val * 1.15 if max_val > 0 else 10.0

        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        y_ticks = 5
        painter.setFont(QFont("Segoe UI", 8))
        for step in range(y_ticks + 1):
            val = (step / y_ticks) * max_y
            y_px = bottom - (step / y_ticks) * plot_h
            painter.setPen(QPen(QColor(GRID), 1))
            painter.drawLine(QPointF(left, y_px), QPointF(right, y_px))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(10, y_px - 8, left - 18, 16), Qt.AlignmentFlag.AlignRight, f"{val:.0f}")

        n_cats = len(rows)
        cat_w = plot_w / n_cats
        bar_w = min(32.0, (cat_w * 0.75) / 2.0)

        for i, r in enumerate(rows):
            cx = left + i * cat_w + cat_w / 2.0
            cat = r["category"]
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(cx - cat_w / 2, bottom + 8, cat_w, 20), Qt.AlignmentFlag.AlignCenter, cat)

            obs_h = (r["observed"] / max_y) * plot_h
            exp_h = (r["expected"] / max_y) * plot_h

            # Observed Bar (Blue)
            painter.setBrush(QColor("#1f77b4"))
            painter.setPen(QPen(QColor("#1f77b4").darker(120), 1))
            painter.drawRect(QRectF(cx - bar_w, bottom - obs_h, bar_w - 2, obs_h))

            # Expected Bar (Orange)
            painter.setBrush(QColor("#ff7f0e"))
            painter.setPen(QPen(QColor("#ff7f0e").darker(120), 1))
            painter.drawRect(QRectF(cx, bottom - exp_h, bar_w - 2, exp_h))

        # Legend
        leg_x = right + 18.0
        leg_y = top + 10.0
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(leg_x, leg_y, 140, 20), Qt.AlignmentFlag.AlignLeft, "Legend")
        leg_y += 24.0

        for col, lbl in [(QColor("#1f77b4"), "Observed"), (QColor("#ff7f0e"), "Expected")]:
            painter.fillRect(QRectF(leg_x, leg_y + 2, 12, 12), col)
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(leg_x + 18, leg_y, 130, 16), Qt.AlignmentFlag.AlignLeft, lbl)
            leg_y += 20.0

    def _paint_tally_bars(self, painter: QPainter, rect: QRectF) -> None:
        self._paint_goodness_of_fit_bars(painter, rect)
