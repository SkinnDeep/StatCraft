"""High-fidelity Qt/QPainter renderer for Pareto Chart (Stat > Quality Tools > Pareto Chart).

Matches StatCraft visual styling:
- Primary left Y-axis for Count
- Secondary right Y-axis for Percent (0% to 100%)
- Blue vertical bars sorted descending
- Red cumulative percentage curve with data point markers
- Characteristic StatCraft bottom summary table beneath the bars displaying:
  - Category Label
  - Count
  - Percent
  - Cum %
- Interactive hover tooltips and selection via GraphInteractionMixin
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
INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
RED = "#c23934"
GRID = "#e8ecef"
TABLE_BG = "#f8f9fa"


def _fmt(val: Optional[float], dec: int = 1) -> str:
    if val is None or math.isnan(val):
        return ""
    return f"{val:.{dec}f}"


class ParetoChartWidget(GraphInteractionMixin, QWidget):
    """Pareto chart widget with dual Y-axes, cumulative curve, and embedded bottom data table."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", entry) if isinstance(entry, dict) else {}
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(QSize(780, 520))

        self.title_text = str(self.result.get("title", "Pareto Chart"))
        self.categories = [str(c) for c in self.result.get("categories", [])]
        self.counts = [float(c) for c in self.result.get("counts", [])]
        self.percents = [float(p) for p in self.result.get("percents", [])]
        self.cum_percents = [float(cp) for cp in self.result.get("cum_percents", [])]
        self.total_count = float(self.result.get("total_count", sum(self.counts) if self.counts else 1.0))
        self.show_cumulative = bool(self.result.get("show_cumulative", True))

        self.hover_bar_idx: Optional[int] = None
        self.panels = [{"name": "Pareto"}]

    def sizeHint(self) -> QSize:
        return QSize(840, 540)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect()
        painter.fillRect(rect, QColor("#ffffff"))

        # Layout Geometry
        top_margin = 55
        bottom_table_height = 80
        bottom_margin = bottom_table_height + 25
        left_margin = 75
        right_margin = 75

        plot_width = max(10.0, rect.width() - left_margin - right_margin)
        plot_height = max(10.0, rect.height() - top_margin - bottom_margin)

        plot_rect = QRectF(left_margin, top_margin, plot_width, plot_height)

        # Title
        painter.setPen(QColor(INK))
        font_title = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font_title)
        painter.drawText(QRectF(left_margin, 12, plot_width, 30), Qt.AlignmentFlag.AlignCenter, self.title_text)

        # Plot Background and Border
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(plot_rect)

        k = len(self.categories)
        if k == 0:
            painter.setPen(QColor(MUTED))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(plot_rect, Qt.AlignmentFlag.AlignCenter, "No defect data available")
            return

        # Axis scaling
        # Left Y-axis: Count (0 to total_count, or rounded ceiling)
        y_count_max = self.total_count if self.total_count > 0 else 1.0
        # Right Y-axis: Percent (0 to 100)

        # Grid lines (5 ticks)
        font_axis = QFont("Segoe UI", 8)
        painter.setFont(font_axis)
        ticks = 5
        for t in range(ticks + 1):
            ratio = t / ticks
            y_pos = plot_rect.bottom() - ratio * plot_height

            # Horizontal grid line
            painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(plot_rect.left(), y_pos), QPointF(plot_rect.right(), y_pos))

            # Left tick label (Count)
            c_val = ratio * y_count_max
            cnt_str = f"{int(round(c_val))}" if y_count_max >= 5 else f"{c_val:.1f}"
            painter.setPen(QColor(MUTED))
            painter.drawText(
                QRectF(0, y_pos - 8, left_margin - 8, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                cnt_str,
            )

            # Right tick label (Percent)
            pct_val = ratio * 100.0
            painter.drawText(
                QRectF(plot_rect.right() + 8, y_pos - 8, right_margin - 10, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{int(round(pct_val))}%",
            )

        # Axis Titles
        painter.save()
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        # Left axis title: "Count"
        painter.translate(20, plot_rect.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-50, -10, 100, 20), Qt.AlignmentFlag.AlignCenter, "Count")
        painter.restore()

        painter.save()
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        # Right axis title: "Percent"
        painter.translate(rect.width() - 15, plot_rect.center().y())
        painter.rotate(90)
        painter.drawText(QRectF(-50, -10, 100, 20), Qt.AlignmentFlag.AlignCenter, "Percent")
        painter.restore()

        # Slot calculations
        slot_width = plot_width / k
        bar_pad = slot_width * 0.15
        bar_width = max(4.0, slot_width - 2 * bar_pad)

        # Draw Bars
        for i in range(k):
            cnt = self.counts[i]
            bar_height = (cnt / y_count_max) * plot_height if y_count_max > 0 else 0.0
            bar_x = plot_rect.left() + i * slot_width + bar_pad
            bar_y = plot_rect.bottom() - bar_height

            is_hover = (i == self.hover_bar_idx)
            fill_col = QColor("#ff9900") if is_hover else QColor(BLUE_FILL)
            border_col = QColor("#cc7a00") if is_hover else QColor(BLUE)

            painter.setPen(QPen(border_col, 1))
            painter.setBrush(fill_col)
            painter.drawRect(QRectF(bar_x, bar_y, bar_width, bar_height))

        # Draw Cumulative Line
        if self.show_cumulative and k > 0:
            cum_points: List[QPointF] = []
            for i in range(k):
                cp = self.cum_percents[i]
                pt_x = plot_rect.left() + (i + 0.5) * slot_width
                pt_y = plot_rect.bottom() - (cp / 100.0) * plot_height
                cum_points.append(QPointF(pt_x, pt_y))

            # Connected red line
            painter.setPen(QPen(QColor(RED), 2))
            for i in range(len(cum_points) - 1):
                painter.drawLine(cum_points[i], cum_points[i + 1])

            # Circle markers on cumulative line
            painter.setBrush(QColor("#ffffff"))
            painter.setPen(QPen(QColor(RED), 2))
            for pt in cum_points:
                painter.drawEllipse(pt, 3.5, 3.5)

        # Draw Bottom Data Table
        tbl_top = plot_rect.bottom() + 4
        tbl_rect = QRectF(plot_rect.left(), tbl_top, plot_width, bottom_table_height)
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor(TABLE_BG))
        painter.drawRect(tbl_rect)

        # Row headers on the left
        row_height = bottom_table_height / 4.0
        row_labels = ["Defect", "Count", "Percent", "Cum %"]
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        for r_idx, lbl in enumerate(row_labels):
            y_r = tbl_top + r_idx * row_height
            # Draw row separator line
            if r_idx > 0:
                painter.setPen(QPen(QColor(BORDER), 1))
                painter.drawLine(QPointF(tbl_rect.left(), y_r), QPointF(tbl_rect.right(), y_r))

            # Header text in left margin
            painter.setPen(QColor(MUTED))
            painter.drawText(
                QRectF(0, y_r, left_margin - 6, row_height),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                lbl,
            )

        # Draw columns in bottom table
        painter.setFont(QFont("Segoe UI", 8))
        for i in range(k):
            col_x = plot_rect.left() + i * slot_width
            # Vertical column separator
            if i > 0:
                painter.setPen(QPen(QColor(BORDER), 1))
                painter.drawLine(QPointF(col_x, tbl_top), QPointF(col_x, tbl_top + bottom_table_height))

            cell_rect = QRectF(col_x, tbl_top, slot_width, row_height)

            # Row 0: Category Name
            cat_name = self.categories[i]
            painter.setPen(QColor(INK))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(cell_rect, Qt.AlignmentFlag.AlignCenter, cat_name)

            # Row 1: Count
            painter.setFont(QFont("Segoe UI", 8))
            cnt_val = self.counts[i]
            c_str = f"{int(cnt_val)}" if cnt_val == int(cnt_val) else f"{cnt_val:.1f}"
            cell_rect.moveTop(tbl_top + row_height)
            painter.drawText(cell_rect, Qt.AlignmentFlag.AlignCenter, c_str)

            # Row 2: Percent
            cell_rect.moveTop(tbl_top + 2 * row_height)
            painter.drawText(cell_rect, Qt.AlignmentFlag.AlignCenter, _fmt(self.percents[i], 1))

            # Row 3: Cum %
            cell_rect.moveTop(tbl_top + 3 * row_height)
            painter.drawText(cell_rect, Qt.AlignmentFlag.AlignCenter, _fmt(self.cum_percents[i], 1))

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        k = len(self.categories)
        if k == 0:
            super().mouseMoveEvent(event)
            return

        top_margin = 55
        bottom_table_height = 80
        bottom_margin = bottom_table_height + 25
        left_margin = 75
        right_margin = 75

        plot_width = max(10.0, self.rect().width() - left_margin - right_margin)
        plot_height = max(10.0, self.rect().height() - top_margin - bottom_margin)
        plot_rect = QRectF(left_margin, top_margin, plot_width, plot_height)

        slot_width = plot_width / k

        found_idx = None
        if plot_rect.left() <= pos.x() <= plot_rect.right() and top_margin <= pos.y() <= (plot_rect.bottom() + bottom_table_height):
            idx = int((pos.x() - plot_rect.left()) // slot_width)
            if 0 <= idx < k:
                found_idx = idx

        if found_idx is not None:
            cat = self.categories[found_idx]
            cnt = self.counts[found_idx]
            pct = self.percents[found_idx]
            cum_pct = self.cum_percents[found_idx]

            tip = (
                f"Category: {cat}\n"
                f"Count: {int(cnt) if cnt == int(cnt) else cnt:.1f}\n"
                f"Percent: {pct:.1f}%\n"
                f"Cum %: {cum_pct:.1f}%"
            )
            QToolTip.showText(event.globalPosition().toPoint(), tip, self)
            if self.hover_bar_idx != found_idx:
                self.hover_bar_idx = found_idx
                self.update()
        else:
            if self.hover_bar_idx is not None:
                self.hover_bar_idx = None
                self.update()
            QToolTip.hideText()

        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.objectSelected.emit("Pareto")
            if self.hover_bar_idx is not None:
                self.brushRowsSelected.emit([self.hover_bar_idx + 1])
