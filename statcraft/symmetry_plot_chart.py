"""High-fidelity Qt Interactive Chart Widget for Symmetry Plot.

Renders the Minitab-standard Symmetry Plot:
- 45-degree reference line (Y = X) representing theoretical symmetry
- Scatter points for Lower Distance vs Upper Distance from sample median
- Summary KPI Cards: Sample Size, Median, Skewness, Assessment
- Interactive hover tooltips showing rank and exact distances
- One-click "Copy Chart" and "Save PNG" buttons
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from .chart_theme import chart_painter


class SymmetryPlotCanvas(QWidget):
    """Drawing canvas for the Symmetry Plot."""

    def __init__(self, plot_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.plot_data = plot_data
        self.setMouseTracking(True)
        self.hovered_point: Optional[Tuple[int, float, float]] = None
        self.hit_regions: List[Tuple[QRectF, int, float, float]] = []

    def mouseMoveEvent(self, event):
        pos = event.position()
        old_hover = self.hovered_point
        self.hovered_point = None
        for rect, rank, u, v in self.hit_regions:
            if rect.contains(pos):
                self.hovered_point = (rank, u, v)
                break
        if old_hover != self.hovered_point:
            self.update()

    def leaveEvent(self, event):
        if self.hovered_point is not None:
            self.hovered_point = None
            self.update()

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())

        # Clean background
        painter.fillRect(self.rect(), QColor("#ffffff"))

        # Margins for axes
        lm = 75.0
        rm = 40.0
        tm = 30.0
        bm = 60.0

        pw = w - lm - rm
        ph = h - tm - bm
        if pw <= 20 or ph <= 20:
            painter.end()
            return

        # Data limits (both axes use [0, max_coord] with 8% padding to maintain 1:1 aspect)
        max_dist = float(self.plot_data.get("max_dist", 1.0))
        top_val = max_dist * 1.08

        def to_screen(u: float, v: float) -> QPointF:
            sx = lm + (u / top_val) * pw
            sy = tm + (1.0 - (v / top_val)) * ph
            return QPointF(sx, sy)

        # Plot area background
        plot_rect = QRectF(lm, tm, pw, ph)
        painter.setPen(QPen(QColor("#cbd5e1"), 1.0))
        painter.setBrush(QColor("#fafbfc"))
        painter.drawRect(plot_rect)

        # Subtle grid lines
        painter.setPen(QPen(QColor("#f1f5f9"), 1.0, Qt.PenStyle.DashLine))
        n_ticks = 6
        for step in range(1, n_ticks + 1):
            val = (step / n_ticks) * top_val
            # Vertical grid
            pt_v1 = to_screen(val, 0.0)
            pt_v2 = to_screen(val, top_val)
            painter.drawLine(pt_v1, pt_v2)
            # Horizontal grid
            pt_h1 = to_screen(0.0, val)
            pt_h2 = to_screen(top_val, val)
            painter.drawLine(pt_h1, pt_h2)

        # 45-degree reference line Y = X
        if self.plot_data.get("show_line", True):
            p0 = to_screen(0.0, 0.0)
            p1 = to_screen(top_val, top_val)
            painter.setPen(QPen(QColor("#e11d48"), 1.6, Qt.PenStyle.DashLine))
            painter.drawLine(p0, p1)

            # Label on line
            mid_pt = to_screen(top_val * 0.75, top_val * 0.75)
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium))
            painter.setPen(QColor("#be123c"))
            painter.drawText(QRectF(mid_pt.x() - 65, mid_pt.y() - 18, 60, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "Y = X (Symmetry)")

        # Plot observations
        lower_distances = self.plot_data.get("lower_distances", [])
        upper_distances = self.plot_data.get("upper_distances", [])
        ranks = self.plot_data.get("ranks", list(range(1, len(lower_distances) + 1)))

        self.hit_regions = []
        point_r = 4.5

        for rank, u_dist, v_dist in zip(ranks, lower_distances, upper_distances):
            s_pt = to_screen(u_dist, v_dist)

            # Hit region for tooltip
            hit_box = QRectF(s_pt.x() - 7, s_pt.y() - 7, 14, 14)
            self.hit_regions.append((hit_box, rank, u_dist, v_dist))

            # Dot drawing
            is_hov = (self.hovered_point and self.hovered_point[0] == rank)
            painter.setPen(QPen(QColor("#0284c7" if not is_hov else "#e11d48"), 1.8 if not is_hov else 2.4))
            painter.setBrush(QColor("#ffffff" if not is_hov else "#fee2e2"))
            r_draw = point_r if not is_hov else point_r + 2.0
            painter.drawEllipse(s_pt, r_draw, r_draw)

        # Axis ticks and numbers
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#475569"))

        for step in range(n_ticks + 1):
            val = (step / n_ticks) * top_val
            fmt_val = f"{val:.2f}" if top_val < 10 else f"{val:.1f}"

            # X-axis ticks
            px = to_screen(val, 0.0).x()
            painter.drawLine(QPointF(px, tm + ph), QPointF(px, tm + ph + 4))
            painter.drawText(QRectF(px - 25, tm + ph + 6, 50, 16),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, fmt_val)

            # Y-axis ticks
            py = to_screen(0.0, val).y()
            painter.drawLine(QPointF(lm - 4, py), QPointF(lm, py))
            painter.drawText(QRectF(10, py - 8, lm - 16, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, fmt_val)

        # Axis Labels
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.setPen(QColor("#0f172a"))

        # X-Axis label
        painter.drawText(QRectF(lm, h - 28, pw, 22),
                         Qt.AlignmentFlag.AlignCenter, "Lower Distance (Median - Lower Observation)")

        # Y-Axis label (rotated)
        painter.save()
        painter.translate(18, tm + ph / 2.0)
        painter.rotate(-90)
        painter.drawText(QRectF(-ph / 2.0, -12, ph, 24),
                         Qt.AlignmentFlag.AlignCenter, "Upper Distance (Upper Observation - Median)")
        painter.restore()

        # Tooltip for hovered observation
        if self.hovered_point:
            rank, u, v = self.hovered_point
            hov_pt = to_screen(u, v)
            diff = v - u
            tip_text = f"Rank: {rank}\nLower Dist: {u:.4f}\nUpper Dist: {v:.4f}\nDiff: {diff:+.4f}"

            painter.setFont(QFont("Segoe UI", 8.5))
            fm = painter.fontMetrics()
            tip_w = max(fm.horizontalAdvance(line) for line in tip_text.splitlines()) + 16.0
            tip_h = len(tip_text.splitlines()) * 16.0 + 12.0

            # Position tooltip avoiding screen edges
            tx = hov_pt.x() + 10
            if tx + tip_w > w - 10:
                tx = hov_pt.x() - tip_w - 10
            ty = hov_pt.y() - tip_h - 10
            if ty < 10:
                ty = hov_pt.y() + 14

            tip_rect = QRectF(tx, ty, tip_w, tip_h)
            painter.setPen(QPen(QColor("#0284c7"), 1.0))
            painter.setBrush(QColor(15, 23, 42, 230))
            painter.drawRoundedRect(tip_rect, 4.0, 4.0)

            painter.setPen(QColor("#ffffff"))
            text_rect = QRectF(tx + 8, ty + 6, tip_w - 16, tip_h - 12)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tip_text)

        painter.end()


class SymmetryPlotChartWidget(QWidget):
    """Full-featured interactive widget with KPI header cards, canvas, and export buttons."""

    def __init__(self, result: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.result = result
        self.plot_data = result.get("plot_data", {})
        self.settings = result.get("settings", {})
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(10)

        # Header Bar
        top_bar = QHBoxLayout()
        title_text = self.settings.get("title") or "Symmetry Plot"
        lbl_title = QLabel(title_text)
        lbl_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #0f172a;")
        top_bar.addWidget(lbl_title)
        top_bar.addStretch()

        btn_copy = QPushButton("📋 Copy Chart")
        btn_copy.setStyleSheet("padding: 4px 10px; font-size: 8.5pt;")
        btn_copy.clicked.connect(self._copy_to_clipboard)
        top_bar.addWidget(btn_copy)

        btn_save = QPushButton("💾 Save PNG")
        btn_save.setStyleSheet("padding: 4px 10px; font-size: 8.5pt;")
        btn_save.clicked.connect(self._save_png)
        top_bar.addWidget(btn_save)
        layout.addLayout(top_bar)

        # KPI Summary Cards Bar
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)

        def make_kpi(lbl: str, val: str, sub: str = "", highlight: bool = False):
            frame = QFrame()
            bg_col = "#f1f5f9" if not highlight else "#eff6ff"
            border_col = "#cbd5e1" if not highlight else "#93c5fd"
            frame.setStyleSheet(f"background-color: {bg_col}; border: 1px solid {border_col}; border-radius: 6px;")
            flay = QVBoxLayout(frame)
            flay.setContentsMargins(10, 6, 10, 6)
            flay.setSpacing(2)

            l = QLabel(lbl)
            l.setFont(QFont("Segoe UI", 8))
            l.setStyleSheet("color: #64748b; font-weight: 600;")
            flay.addWidget(l)

            v = QLabel(val)
            v.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            v.setStyleSheet("color: #0f172a;" if not highlight else "color: #0284c7;")
            flay.addWidget(v)

            if sub:
                s = QLabel(sub)
                s.setFont(QFont("Segoe UI", 7.5))
                s.setStyleSheet("color: #64748b;")
                flay.addWidget(s)
            return frame

        n_val = self.result.get("n", 0)
        cards_layout.addWidget(make_kpi("Sample Size (N)", f"{n_val}", f"Pairs: {self.result.get('k_pairs', 0)}"))

        med = self.result.get("median", 0.0)
        mean_v = self.result.get("mean", 0.0)
        cards_layout.addWidget(make_kpi("Median", f"{med:.4f}", f"Mean: {mean_v:.4f}"))

        skew = self.result.get("skewness", 0.0)
        s_lbl = self.result.get("skew_label", "Unknown")
        is_skewed = abs(skew) >= 0.2
        cards_layout.addWidget(make_kpi("Skewness", f"{skew:+.4f}", s_lbl, highlight=is_skewed))

        sd = self.result.get("stdev", 0.0)
        cards_layout.addWidget(make_kpi("Std Dev", f"{sd:.4f}", self.result.get("assessment", "")))

        layout.addLayout(cards_layout)

        # Symmetry Canvas
        self.canvas = SymmetryPlotCanvas(self.plot_data, self)
        layout.addWidget(self.canvas, 1)

    def render_chart_pixmap(self, width: int = 800, height: int = 600) -> QPixmap:
        pm = QPixmap(width, height)
        pm.fill(QColor("#ffffff"))
        self.render(pm)
        return pm

    def _copy_to_clipboard(self):
        pixmap = self.canvas.grab()
        QApplication.clipboard().setPixmap(pixmap)

    def _save_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Symmetry Plot", "Symmetry_Plot.png", "PNG Images (*.png)")
        if path:
            pixmap = self.canvas.grab()
            pixmap.save(path, "PNG")
