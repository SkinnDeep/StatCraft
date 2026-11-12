"""High-Fidelity Qt Interactive Chart Widget for Marginal Plot.

Renders Minitab-identical:
- Bottom-left Scatterplot with complete pairs and regression line
- Top Marginal Plot aligned with X axis (Histogram, Boxplot, or Dotplot)
- Right Marginal Plot aligned with Y axis (Histogram, Boxplot, or Dotplot)
- Normal density curve overlay on marginal histograms
- Interactive crosshair alignment and point hover
- KPI Cards & One-click Export
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
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from .chart_theme import chart_painter


class MarginalPlotCanvas(QWidget):
    """Unified canvas rendering aligned scatterplot and marginal distributions."""

    def __init__(self, result: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.result = result
        self.setMouseTracking(True)
        self.hovered_point: Optional[Tuple[int, float, float]] = None
        self.hit_points: List[Tuple[QRectF, int, float, float]] = []

    def mouseMoveEvent(self, event):
        pos = event.position()
        old_hover = self.hovered_point
        self.hovered_point = None

        for rect, row, x, y in self.hit_points:
            if rect.contains(pos):
                self.hovered_point = (row, x, y)
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

        painter.fillRect(self.rect(), QColor("#ffffff"))

        # Geometry dimensions
        left_margin = 65.0
        right_margin = 25.0
        top_margin = 30.0
        bottom_margin = 55.0

        top_marginal_h = 95.0
        right_marginal_w = 95.0
        gap = 14.0

        plot_w = max(40.0, w - left_margin - right_margin - right_marginal_w - gap)
        plot_h = max(40.0, h - top_margin - bottom_margin - top_marginal_h - gap)

        scatter_rect = QRectF(left_margin, top_margin + top_marginal_h + gap, plot_w, plot_h)
        top_rect = QRectF(left_margin, top_margin, plot_w, top_marginal_h)
        right_rect = QRectF(left_margin + plot_w + gap, top_margin + top_marginal_h + gap, right_marginal_w, plot_h)

        x_st = self.result.get('x_stats', {})
        y_st = self.result.get('y_stats', {})

        x_min, x_max = float(x_st.get('min', 0.0)), float(x_st.get('max', 1.0))
        y_min, y_max = float(y_st.get('min', 0.0)), float(y_st.get('max', 1.0))

        # Pad 5% on margins
        x_span = max(1e-6, x_max - x_min)
        y_span = max(1e-6, y_max - y_min)
        x_min -= x_span * 0.05
        x_max += x_span * 0.05
        y_min -= y_span * 0.05
        y_max += y_span * 0.05

        def to_scatter(x: float, y: float) -> QPointF:
            sx = scatter_rect.left() + (x - x_min) / (x_max - x_min) * scatter_rect.width()
            sy = scatter_rect.bottom() - (y - y_min) / (y_max - y_min) * scatter_rect.height()
            return QPointF(sx, sy)

        def to_top_x(x: float) -> float:
            return top_rect.left() + (x - x_min) / (x_max - x_min) * top_rect.width()

        def to_right_y(y: float) -> float:
            return right_rect.bottom() - (y - y_min) / (y_max - y_min) * right_rect.height()

        # Grid lines in scatter area
        painter.setPen(QPen(QColor("#f1f5f9"), 1.0))
        num_ticks = 5
        for i in range(num_ticks + 1):
            y_val = y_min + (y_max - y_min) * i / num_ticks
            sy = to_scatter(x_min, y_val).y()
            painter.drawLine(QPointF(scatter_rect.left(), sy), QPointF(scatter_rect.right(), sy))

            x_val = x_min + (x_max - x_min) * i / num_ticks
            sx = to_scatter(x_val, y_min).x()
            painter.drawLine(QPointF(sx, scatter_rect.top()), QPointF(sx, scatter_rect.bottom()))

        # --- 1. Top Marginal Plot (X variable) ---
        m_type = self.result.get('marginal_type', 'histogram')
        show_norm = self.result.get('show_normal_curve', False)

        if m_type == 'histogram':
            x_edges = x_st.get('edges', [])
            x_counts = x_st.get('counts', [])
            max_c = max(x_counts) if x_counts else 1
            if max_c <= 0:
                max_c = 1

            for i in range(len(x_counts)):
                e0 = x_edges[i]
                e1 = x_edges[i + 1]
                cnt = x_counts[i]
                bx0 = to_top_x(e0)
                bx1 = to_top_x(e1)
                bw = max(1.0, bx1 - bx0)
                bh = (cnt / max_c) * (top_rect.height() - 10)
                by = top_rect.bottom() - bh

                painter.setPen(QPen(QColor("#38bdf8"), 1.0))
                painter.setBrush(QBrush(QColor("#bae6fd")))
                painter.drawRect(QRectF(bx0, by, bw, bh))

            if show_norm and x_st.get('normal_curve'):
                n_curve = x_st['normal_curve']
                max_curve_y = max((pt[1] for pt in n_curve), default=1.0)
                if max_curve_y > 0:
                    scale_factor = (top_rect.height() - 10) / max(max_c, max_curve_y)
                    c_path = QPainterPath()
                    first_pt = n_curve[0]
                    c_path.moveTo(to_top_x(first_pt[0]), top_rect.bottom() - first_pt[1] * scale_factor)
                    for pt in n_curve[1:]:
                        c_path.lineTo(to_top_x(pt[0]), top_rect.bottom() - pt[1] * scale_factor)
                    painter.setPen(QPen(QColor("#e11d48"), 1.8))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(c_path)

        elif m_type == 'boxplot':
            box = x_st.get('box', {})
            mid_y = top_rect.center().y()
            q1_x = to_top_x(box.get('q1', x_min))
            q3_x = to_top_x(box.get('q3', x_max))
            med_x = to_top_x(box.get('median', (x_min + x_max) / 2))
            w_lo_x = to_top_x(box.get('low_whisker', x_min))
            w_hi_x = to_top_x(box.get('high_whisker', x_max))
            box_h = 32.0

            # Whiskers
            painter.setPen(QPen(QColor("#0284c7"), 1.4))
            painter.drawLine(QPointF(w_lo_x, mid_y), QPointF(q1_x, mid_y))
            painter.drawLine(QPointF(q3_x, mid_y), QPointF(w_hi_x, mid_y))
            painter.drawLine(QPointF(w_lo_x, mid_y - 8), QPointF(w_lo_x, mid_y + 8))
            painter.drawLine(QPointF(w_hi_x, mid_y - 8), QPointF(w_hi_x, mid_y + 8))

            # IQR Box
            painter.setBrush(QBrush(QColor("#e0f2fe")))
            painter.drawRect(QRectF(q1_x, mid_y - box_h / 2, max(1.0, q3_x - q1_x), box_h))

            # Median Line
            painter.setPen(QPen(QColor("#0369a1"), 2.2))
            painter.drawLine(QPointF(med_x, mid_y - box_h / 2), QPointF(med_x, mid_y + box_h / 2))

            # Outliers
            for out in box.get('outliers', []):
                ox = to_top_x(out)
                painter.setPen(QPen(QColor("#dc2626"), 1.2))
                painter.setBrush(QBrush(QColor("#fee2e2")))
                painter.drawEllipse(QPointF(ox, mid_y), 3.5, 3.5)

        elif m_type == 'dotplot':
            dots = x_st.get('dots', [])
            dot_r = 3.0
            for d in dots:
                dx = to_top_x(d['val'])
                for k in range(d['count']):
                    dy = top_rect.bottom() - (k + 1) * (dot_r * 2 + 2)
                    painter.setPen(QPen(QColor("#0284c7"), 1.0))
                    painter.setBrush(QBrush(QColor("#38bdf8")))
                    painter.drawEllipse(QPointF(dx, dy), dot_r, dot_r)

        # Baseline for top marginal
        painter.setPen(QPen(QColor("#94a3b8"), 1.0))
        painter.drawLine(top_rect.bottomLeft(), top_rect.bottomRight())

        # --- 2. Right Marginal Plot (Y variable) ---
        if m_type == 'histogram':
            y_edges = y_st.get('edges', [])
            y_counts = y_st.get('counts', [])
            max_c = max(y_counts) if y_counts else 1
            if max_c <= 0:
                max_c = 1

            for i in range(len(y_counts)):
                e0 = y_edges[i]
                e1 = y_edges[i + 1]
                cnt = y_counts[i]
                by0 = to_right_y(e0)
                by1 = to_right_y(e1)
                bh = max(1.0, abs(by0 - by1))
                by_top = min(by0, by1)
                bw = (cnt / max_c) * (right_rect.width() - 10)

                painter.setPen(QPen(QColor("#38bdf8"), 1.0))
                painter.setBrush(QBrush(QColor("#bae6fd")))
                painter.drawRect(QRectF(right_rect.left(), by_top, bw, bh))

            if show_norm and y_st.get('normal_curve'):
                n_curve = y_st['normal_curve']
                max_curve_x = max((pt[0] for pt in n_curve), default=1.0)
                if max_curve_x > 0:
                    scale_factor = (right_rect.width() - 10) / max(max_c, max_curve_x)
                    c_path = QPainterPath()
                    first_pt = n_curve[0]
                    c_path.moveTo(right_rect.left() + first_pt[0] * scale_factor, to_right_y(first_pt[1]))
                    for pt in n_curve[1:]:
                        c_path.lineTo(right_rect.left() + pt[0] * scale_factor, to_right_y(pt[1]))
                    painter.setPen(QPen(QColor("#e11d48"), 1.8))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(c_path)

        elif m_type == 'boxplot':
            box = y_st.get('box', {})
            mid_x = right_rect.center().x()
            q1_y = to_right_y(box.get('q1', y_min))
            q3_y = to_right_y(box.get('q3', y_max))
            med_y = to_right_y(box.get('median', (y_min + y_max) / 2))
            w_lo_y = to_right_y(box.get('low_whisker', y_min))
            w_hi_y = to_right_y(box.get('high_whisker', y_max))
            box_w = 32.0

            # Whiskers
            painter.setPen(QPen(QColor("#0284c7"), 1.4))
            painter.drawLine(QPointF(mid_x, w_lo_y), QPointF(mid_x, q1_y))
            painter.drawLine(QPointF(mid_x, q3_y), QPointF(mid_x, w_hi_y))
            painter.drawLine(QPointF(mid_x - 8, w_lo_y), QPointF(mid_x + 8, w_lo_y))
            painter.drawLine(QPointF(mid_x - 8, w_hi_y), QPointF(mid_x + 8, w_hi_y))

            # IQR Box
            box_top = min(q1_y, q3_y)
            box_h = abs(q1_y - q3_y)
            painter.setBrush(QBrush(QColor("#e0f2fe")))
            painter.drawRect(QRectF(mid_x - box_w / 2, box_top, box_w, max(1.0, box_h)))

            # Median Line
            painter.setPen(QPen(QColor("#0369a1"), 2.2))
            painter.drawLine(QPointF(mid_x - box_w / 2, med_y), QPointF(mid_x + box_w / 2, med_y))

            # Outliers
            for out in box.get('outliers', []):
                oy = to_right_y(out)
                painter.setPen(QPen(QColor("#dc2626"), 1.2))
                painter.setBrush(QBrush(QColor("#fee2e2")))
                painter.drawEllipse(QPointF(mid_x, oy), 3.5, 3.5)

        elif m_type == 'dotplot':
            dots = y_st.get('dots', [])
            dot_r = 3.0
            for d in dots:
                dy = to_right_y(d['val'])
                for k in range(d['count']):
                    dx = right_rect.left() + (k + 1) * (dot_r * 2 + 2)
                    painter.setPen(QPen(QColor("#0284c7"), 1.0))
                    painter.setBrush(QBrush(QColor("#38bdf8")))
                    painter.drawEllipse(QPointF(dx, dy), dot_r, dot_r)

        # Baseline for right marginal
        painter.setPen(QPen(QColor("#94a3b8"), 1.0))
        painter.drawLine(right_rect.topLeft(), right_rect.bottomLeft())

        # --- 3. Central Scatterplot ---
        # Fitted Line
        slope = float(self.result.get('slope', 0.0))
        intercept = float(self.result.get('intercept', 0.0))
        if math.isfinite(slope) and math.isfinite(intercept):
            fit_p0 = to_scatter(x_min, intercept + slope * x_min)
            fit_p1 = to_scatter(x_max, intercept + slope * x_max)
            painter.setPen(QPen(QColor("#dc2626"), 1.6, Qt.PenStyle.DashLine))
            painter.drawLine(fit_p0, fit_p1)

        # Scatter points
        xs = self.result.get('xs', [])
        ys = self.result.get('ys', [])
        rows = self.result.get('row_indices', [])
        self.hit_points = []

        for row, x, y in zip(rows, xs, ys):
            sp = to_scatter(x, y)
            is_hovered = (self.hovered_point is not None and self.hovered_point[0] == row)

            if is_hovered:
                # Crosshairs projecting to top and right marginals
                cross_pen = QPen(QColor("#f43f5e"), 1.2, Qt.PenStyle.DotLine)
                painter.setPen(cross_pen)
                painter.drawLine(QPointF(sp.x(), top_rect.top()), QPointF(sp.x(), scatter_rect.bottom()))
                painter.drawLine(QPointF(scatter_rect.left(), sp.y()), QPointF(right_rect.right(), sp.y()))

                painter.setPen(QPen(QColor("#be123c"), 2.0))
                painter.setBrush(QBrush(QColor("#f43f5e")))
                painter.drawEllipse(sp, 5.0, 5.0)
            else:
                painter.setPen(QPen(QColor("#0369a1"), 1.0))
                painter.setBrush(QBrush(QColor("#38bdf8")))
                painter.drawEllipse(sp, 3.2, 3.2)

            r_hit = QRectF(sp.x() - 5, sp.y() - 5, 10, 10)
            self.hit_points.append((r_hit, row, x, y))

        # Scatterplot frame/axes
        axis_pen = QPen(QColor("#334155"), 1.2)
        painter.setPen(axis_pen)
        painter.drawRect(scatter_rect)

        # Ticks & labels
        painter.setFont(QFont("Segoe UI", 8.5))
        painter.setPen(QColor("#64748b"))

        # Y axis ticks
        for i in range(num_ticks + 1):
            y_val = y_min + (y_max - y_min) * i / num_ticks
            sy = to_scatter(x_min, y_val).y()
            tick_r = QRectF(0, sy - 9, left_margin - 8, 18)
            painter.drawText(tick_r, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{y_val:.3g}")

        # X axis ticks
        for i in range(num_ticks + 1):
            x_val = x_min + (x_max - x_min) * i / num_ticks
            sx = to_scatter(x_val, y_min).x()
            tick_r = QRectF(sx - 30, scatter_rect.bottom() + 6, 60, 18)
            painter.drawText(tick_r, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, f"{x_val:.3g}")

        # Axis Title labels
        painter.setFont(QFont("Segoe UI", 9.5, QFont.Weight.DemiBold))
        painter.setPen(QColor("#1e293b"))

        # X label
        x_title = self.result.get('x_name', 'X')
        painter.drawText(QRectF(scatter_rect.left(), h - 22, scatter_rect.width(), 20), Qt.AlignmentFlag.AlignCenter, x_title)

        # Y label (rotated)
        y_title = self.result.get('y_name', 'Y')
        painter.save()
        painter.translate(16, scatter_rect.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-scatter_rect.height() / 2, -10, scatter_rect.height(), 20), Qt.AlignmentFlag.AlignCenter, y_title)
        painter.restore()

        # Tooltip on hovered point
        if self.hovered_point is not None:
            row, hx, hy = self.hovered_point
            sp = to_scatter(hx, hy)
            txt = f"Row: {row}\n{x_title}: {hx:.4f}\n{y_title}: {hy:.4f}"
            painter.setFont(QFont("Segoe UI", 8.5))
            fm = painter.fontMetrics()
            lines = txt.split('\n')
            tw = max(fm.horizontalAdvance(l) for l in lines) + 16
            th = len(lines) * 16 + 10
            tx = min(w - tw - 10, max(left_margin + 5, sp.x() + 10))
            ty = max(scatter_rect.top() + 5, sp.y() - th - 5)

            t_rect = QRectF(tx, ty, tw, th)
            painter.setPen(QPen(QColor("#0f172a"), 1.0))
            painter.setBrush(QBrush(QColor(15, 23, 42, 225)))
            painter.drawRoundedRect(t_rect, 5.0, 5.0)

            painter.setPen(QColor("#ffffff"))
            for idx, line in enumerate(lines):
                painter.drawText(QRectF(tx + 8, ty + 5 + idx * 16, tw - 16, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, line)


class MarginalPlotChartWidget(QWidget):
    """Container widget providing KPI cards, marginal plot canvas, and export buttons."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get('result', entry)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(640, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Top Bar: Title & Action buttons
        top_bar = QHBoxLayout()
        title_lbl = QLabel(self.result.get('title', 'Marginal Plot'))
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #0f172a;")
        top_bar.addWidget(title_lbl)
        top_bar.addStretch()

        btn_copy = QPushButton("📋 Copy Chart")
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.setStyleSheet(
            "QPushButton { background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 10px; font-size: 8.5pt; font-weight: 500; color: #334155; }"
            "QPushButton:hover { background-color: #f1f5f9; border-color: #94a3b8; }"
        )
        btn_copy.clicked.connect(self._copy_to_clipboard)
        top_bar.addWidget(btn_copy)

        btn_save = QPushButton("💾 Save PNG")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet(
            "QPushButton { background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 10px; font-size: 8.5pt; font-weight: 500; color: #334155; }"
            "QPushButton:hover { background-color: #f1f5f9; border-color: #94a3b8; }"
        )
        btn_save.clicked.connect(self._save_png)
        top_bar.addWidget(btn_save)

        layout.addLayout(top_bar)

        # KPI Cards Row
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(8)

        def make_kpi(label: str, val: str, sub: str = "", highlight: bool = False) -> QFrame:
            frame = QFrame()
            frame.setStyleSheet(
                "QFrame { background-color: #ffffff; border: 1px solid "
                + ("#cbd5e1" if not highlight else "#0284c7")
                + "; border-radius: 6px; padding: 4px 8px; }"
            )
            flay = QVBoxLayout(frame)
            flay.setContentsMargins(6, 4, 6, 4)
            flay.setSpacing(1)

            lbl = QLabel(label.upper())
            lbl.setFont(QFont("Segoe UI", 7.5, QFont.Weight.DemiBold))
            lbl.setStyleSheet("color: #64748b;")
            flay.addWidget(lbl)

            v = QLabel(val)
            v.setFont(QFont("Segoe UI", 10.5, QFont.Weight.Bold))
            v.setStyleSheet("color: #0f172a;" if not highlight else "color: #0369a1;")
            flay.addWidget(v)

            if sub:
                s = QLabel(sub)
                s.setFont(QFont("Segoe UI", 7.5))
                s.setStyleSheet("color: #64748b;")
                flay.addWidget(s)
            return frame

        y_name = self.result.get('y_name', 'Y')
        x_name = self.result.get('x_name', 'X')
        cards_layout.addWidget(make_kpi("Variables", f"{y_name} vs {x_name}", f"Complete N: {self.result.get('n', 0)}"))

        r = self.result.get('correlation', 0.0)
        p_val = self.result.get('p_value', 1.0)
        cards_layout.addWidget(make_kpi("Pearson Correlation", f"r = {r:+.4f}", f"P-value = {p_val:.4f}", highlight=True))

        slope = self.result.get('slope', 0.0)
        intercept = self.result.get('intercept', 0.0)
        cards_layout.addWidget(make_kpi("Fitted Line", f"Slope: {slope:+.4f}", f"Intercept: {intercept:.4f}"))

        m_type = self.result.get('marginal_type', 'histogram').capitalize()
        fit_sub = "Normal Curve" if self.result.get('show_normal_curve') else "No Curve"
        cards_layout.addWidget(make_kpi("Marginal Type", m_type, fit_sub))

        layout.addLayout(cards_layout)

        # Canvas
        self.canvas = MarginalPlotCanvas(self.result, self)
        layout.addWidget(self.canvas, 1)

    def _copy_to_clipboard(self):
        pixmap = self.canvas.grab()
        QApplication.clipboard().setPixmap(pixmap)

    def _save_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Marginal Plot", "Marginal_Plot.png", "PNG Images (*.png)")
        if path:
            pixmap = self.canvas.grab()
            pixmap.save(path, "PNG")
