"""High-Fidelity Qt Interactive Chart Widget for Probability Distribution Plot.

Renders Minitab-identical:
- Smooth continuous probability density function (PDF) curves
- Discrete probability mass function (PMF) needle/bar charts
- Exact shaded probability tails and intervals with translucent fills
- Cutoff vertical dashed reference lines with bold cutoff labels
- Floating probability badges above shaded regions
- Summary KPI Cards and export tools (Copy Chart, Save PNG)
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
    QPolygonF,
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


class ProbDistCanvas(QWidget):
    """Drawing canvas for continuous curves and discrete distributions."""

    def __init__(self, result: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.result = result
        self.setMouseTracking(True)
        self.hovered_point: Optional[Tuple[float, float]] = None
        self.hover_text: Optional[str] = None
        self.hit_regions: List[Tuple[QRectF, float, float, str]] = []

    def mouseMoveEvent(self, event):
        pos = event.position()
        old_hover = self.hovered_point
        self.hovered_point = None
        self.hover_text = None

        for rect, x, y, txt in self.hit_regions:
            if rect.contains(pos):
                self.hovered_point = (x, y)
                self.hover_text = txt
                break

        if old_hover != self.hovered_point:
            self.update()

    def leaveEvent(self, event):
        if self.hovered_point is not None:
            self.hovered_point = None
            self.hover_text = None
            self.update()

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())

        # Clean background
        painter.fillRect(self.rect(), QColor("#ffffff"))

        # Margin layout
        left_m = 65.0
        right_m = 35.0
        top_m = 45.0
        bottom_m = 55.0

        plot_w = max(50.0, w - left_m - right_m)
        plot_h = max(50.0, h - top_m - bottom_m)
        plot_rect = QRectF(left_m, top_m, plot_w, plot_h)

        domain = self.result.get('domain', [0.0, 1.0])
        x_min, x_max = float(domain[0]), float(domain[1])
        if x_max <= x_min:
            x_max = x_min + 1.0

        y_max = float(self.result.get('y_max', 1.0))
        if y_max <= 0:
            y_max = 1.0
        y_min = 0.0

        def to_screen(x: float, y: float) -> QPointF:
            sx = left_m + (x - x_min) / (x_max - x_min) * plot_w
            sy = top_m + plot_h - (y - y_min) / (y_max - y_min) * plot_h
            return QPointF(sx, sy)

        # Draw grid
        painter.setPen(QPen(QColor("#f1f5f9"), 1.0, Qt.PenStyle.SolidLine))
        num_y_ticks = 5
        for i in range(num_y_ticks + 1):
            y_val = y_min + (y_max - y_min) * i / num_y_ticks
            p_tick = to_screen(x_min, y_val)
            painter.drawLine(QPointF(left_m, p_tick.y()), QPointF(left_m + plot_w, p_tick.y()))

        num_x_ticks = 6
        for i in range(num_x_ticks + 1):
            x_val = x_min + (x_max - x_min) * i / num_x_ticks
            p_tick = to_screen(x_val, y_min)
            painter.drawLine(QPointF(p_tick.x(), top_m), QPointF(p_tick.x(), top_m + plot_h))

        # Reset hit regions
        self.hit_regions = []
        is_discrete = self.result.get('is_discrete', False)

        if not is_discrete:
            # --- 1. Continuous Distribution Rendering ---
            # Draw Shaded Regions first (underneath the curve)
            shaded_regions = self.result.get('shaded_regions', [])
            for region in shaded_regions:
                poly_pts = region.get('polygon', [])
                if len(poly_pts) >= 3:
                    screen_poly = [to_screen(pt[0], pt[1]) for pt in poly_pts]
                    poly_path = QPainterPath()
                    poly_path.moveTo(screen_poly[0])
                    for pt in screen_poly[1:]:
                        poly_path.lineTo(pt)
                    poly_path.closeSubpath()

                    shade_brush = QBrush(QColor(225, 29, 72, 85))  # Soft translucent crimson
                    painter.fillPath(poly_path, shade_brush)

            # Draw Main Density Curve
            curve_pts = self.result.get('curve_points', [])
            if len(curve_pts) >= 2:
                path = QPainterPath()
                first = to_screen(curve_pts[0][0], curve_pts[0][1])
                path.moveTo(first)
                for pt in curve_pts[1:]:
                    path.lineTo(to_screen(pt[0], pt[1]))

                curve_pen = QPen(QColor("#0284c7"), 2.2)  # Refined Minitab blue
                painter.setPen(curve_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

            # Draw Cutoff Lines and Labels
            cutoffs = self.result.get('cutoffs', [])
            for c in cutoffs:
                cx = float(c.get('x', 0.0))
                # Compute height of curve at cutoff
                curve_y = 0.0
                for pt in curve_pts:
                    if pt[0] >= cx:
                        curve_y = pt[1]
                        break

                p_base = to_screen(cx, 0.0)
                p_top = to_screen(cx, curve_y)

                # Vertical dashed line
                cut_pen = QPen(QColor("#dc2626"), 1.8, Qt.PenStyle.DashLine)
                painter.setPen(cut_pen)
                painter.drawLine(p_base, p_top)

                # Cutoff marker on X axis
                painter.setPen(QPen(QColor("#dc2626"), 1.0))
                painter.setBrush(QBrush(QColor("#dc2626")))
                painter.drawEllipse(p_base, 3.5, 3.5)

                # Cutoff X label below axis
                painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                val_str = f"{cx:.4g}"
                lbl_rect = QRectF(p_base.x() - 40, p_base.y() + 4, 80, 20)
                painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, val_str)

            # Floating probability badges above shaded regions
            for region in shaded_regions:
                prob = region.get('prob', 0.0)
                pos_x = region.get('pos', (x_min + x_max) / 2.0)
                # Height roughly at 1/3 of y_max
                p_badge = to_screen(pos_x, y_max * 0.40)

                badge_str = f"{prob:.4f}"
                painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                fm = painter.fontMetrics()
                bw = fm.horizontalAdvance(badge_str) + 12
                bh = fm.height() + 4
                badge_rect = QRectF(p_badge.x() - bw / 2, p_badge.y() - bh / 2, bw, bh)

                painter.setPen(QPen(QColor("#fecdd3"), 1.0))
                painter.setBrush(QBrush(QColor("#fff1f2")))
                painter.drawRoundedRect(badge_rect, 4.0, 4.0)

                painter.setPen(QColor("#9f1239"))
                painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_str)

            # Build hit regions along the continuous curve for tooltip
            for pt in curve_pts[::3]:
                sp = to_screen(pt[0], pt[1])
                r = QRectF(sp.x() - 6, sp.y() - 6, 12, 12)
                txt = f"X = {pt[0]:.4f}\nDensity = {pt[1]:.5f}"
                self.hit_regions.append((r, pt[0], pt[1], txt))

        else:
            # --- 2. Discrete Distribution (Needle / Bar) ---
            bars = self.result.get('discrete_bars', [])
            bar_w = max(3.0, min(16.0, plot_w / (len(bars) + 5)))

            for bar in bars:
                k = float(bar['x'])
                prob = float(bar['prob'])
                shaded = bool(bar['shaded'])

                sp_base = to_screen(k, 0.0)
                sp_top = to_screen(k, prob)

                b_rect = QRectF(sp_top.x() - bar_w / 2, sp_top.y(), bar_w, sp_base.y() - sp_top.y())

                if shaded:
                    fill_col = QColor("#e11d48")
                    edge_col = QColor("#be123c")
                else:
                    fill_col = QColor("#93c5fd")
                    edge_col = QColor("#2563eb")

                painter.setPen(QPen(edge_col, 1.2))
                painter.setBrush(QBrush(fill_col))
                painter.drawRoundedRect(b_rect, 2.0, 2.0)

                txt = f"K = {int(k)}\nP(X = {int(k)}) = {prob:.5f}"
                self.hit_regions.append((b_rect, k, prob, txt))

        # --- 3. Axes and Labels ---
        axis_pen = QPen(QColor("#334155"), 1.2)
        painter.setPen(axis_pen)
        # Y axis
        painter.drawLine(QPointF(left_m, top_m), QPointF(left_m, top_m + plot_h))
        # X axis
        painter.drawLine(QPointF(left_m, top_m + plot_h), QPointF(left_m + plot_w, top_m + plot_h))

        # Tick labels
        painter.setFont(QFont("Segoe UI", 8.5))
        painter.setPen(QColor("#64748b"))

        # Y ticks
        for i in range(num_y_ticks + 1):
            y_val = y_min + (y_max - y_min) * i / num_y_ticks
            p_tick = to_screen(x_min, y_val)
            tick_rect = QRectF(0, p_tick.y() - 9, left_m - 8, 18)
            painter.drawText(tick_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{y_val:.3g}")

        # X ticks
        for i in range(num_x_ticks + 1):
            x_val = x_min + (x_max - x_min) * i / num_x_ticks
            p_tick = to_screen(x_val, y_min)
            tick_rect = QRectF(p_tick.x() - 30, p_tick.y() + 24, 60, 18)
            painter.drawText(tick_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, f"{x_val:.3g}")

        # Axis Title labels
        painter.setFont(QFont("Segoe UI", 9.5, QFont.Weight.DemiBold))
        painter.setPen(QColor("#1e293b"))
        # X axis title
        painter.drawText(QRectF(left_m, h - 22, plot_w, 20), Qt.AlignmentFlag.AlignCenter, "X")

        # Y axis title (rotated)
        painter.save()
        painter.translate(16, top_m + plot_h / 2)
        painter.rotate(-90)
        y_title = "Probability" if is_discrete else "Density"
        painter.drawText(QRectF(-plot_h / 2, -10, plot_h, 20), Qt.AlignmentFlag.AlignCenter, y_title)
        painter.restore()

        # Tooltip on hover
        if self.hovered_point is not None and self.hover_text:
            sp = to_screen(self.hovered_point[0], self.hovered_point[1])
            painter.setFont(QFont("Segoe UI", 8.5))
            fm = painter.fontMetrics()
            lines = self.hover_text.split('\n')
            tw = max(fm.horizontalAdvance(l) for l in lines) + 16
            th = len(lines) * 16 + 10
            tx = min(w - tw - 10, max(left_m + 5, sp.x() - tw / 2))
            ty = max(top_m + 5, sp.y() - th - 10)

            t_rect = QRectF(tx, ty, tw, th)
            painter.setPen(QPen(QColor("#0f172a"), 1.0))
            painter.setBrush(QBrush(QColor(15, 23, 42, 225)))
            painter.drawRoundedRect(t_rect, 5.0, 5.0)

            painter.setPen(QColor("#ffffff"))
            for idx, line in enumerate(lines):
                painter.drawText(QRectF(tx + 8, ty + 5 + idx * 16, tw - 16, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, line)


class ProbabilityDistributionChartWidget(QWidget):
    """Container widget providing KPI cards, canvas, and export buttons."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get('result', entry)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(600, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Top Bar: Title & Action buttons
        top_bar = QHBoxLayout()
        title_lbl = QLabel(self.result.get('title', 'Probability Distribution Plot'))
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
                + ("#cbd5e1" if not highlight else "#fca5a5")
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
            v.setStyleSheet("color: #0f172a;" if not highlight else "color: #e11d48;")
            flay.addWidget(v)

            if sub:
                s = QLabel(sub)
                s.setFont(QFont("Segoe UI", 7.5))
                s.setStyleSheet("color: #64748b;")
                flay.addWidget(s)
            return frame

        dist_name = self.result.get('distribution', 'Normal')
        params = self.result.get('parameters', {})
        p_strs = [f"{k}={v:g}" if isinstance(v, (int, float)) else f"{k}={v}" for k, v in params.items()]
        cards_layout.addWidget(make_kpi("Distribution", dist_name, ", ".join(p_strs)))

        mode = self.result.get('mode', 'single')
        tail = self.result.get('tail', 'both')
        tail_map = {'right': 'Right Tail', 'left': 'Left Tail', 'both': 'Both Tails', 'middle': 'Middle'}
        mode_str = tail_map.get(tail, 'Single Curve') if mode == 'probability' else 'View Single'
        cards_layout.addWidget(make_kpi("Display Mode", mode_str, f"Mean: {self.result.get('mean', 0.0):.4f}"))

        if mode == 'probability':
            cutoffs = self.result.get('cutoffs', [])
            if len(cutoffs) == 1:
                c_str = f"X = {cutoffs[0].get('x', 0.0):.4f}"
            elif len(cutoffs) >= 2:
                c_str = f"X1={cutoffs[0].get('x', 0.0):.3g}, X2={cutoffs[1].get('x', 0.0):.3g}"
            else:
                c_str = "None"
            cards_layout.addWidget(make_kpi("Cutoff Value(s)", c_str, f"StDev: {self.result.get('stdev', 1.0):.4f}"))

            p_tot = self.result.get('total_shaded_prob', 0.0)
            cards_layout.addWidget(make_kpi("Shaded Probability", f"P = {p_tot:.5f}", f"α = {p_tot:.4f}", highlight=True))
        else:
            cards_layout.addWidget(make_kpi("Standard Deviation", f"{self.result.get('stdev', 1.0):.4f}", f"Var: {self.result.get('variance', 1.0):.4f}"))

        layout.addLayout(cards_layout)

        # Main Canvas
        self.canvas = ProbDistCanvas(self.result, self)
        layout.addWidget(self.canvas, 1)

    def _copy_to_clipboard(self):
        pixmap = self.canvas.grab()
        QApplication.clipboard().setPixmap(pixmap)

    def _save_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Probability Distribution Plot", "Distribution_Plot.png", "PNG Images (*.png)")
        if path:
            pixmap = self.canvas.grab()
            pixmap.save(path, "PNG")
