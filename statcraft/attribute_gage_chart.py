"""High-fidelity Qt Interactive Chart Widget for Attribute Gage Study (Analytic Method).

Renders the Minitab-standard Gage Performance Curve:
- Fitted S-curve for Probability of Acceptance P(Acceptance) = Phi(b0 + b1 * X)
- Individual observed part data points (Reference vs Adjusted Probability)
- Vertical reference line at Target / Reference standard
- Horizontal reference line at P = 0.50 (50% Acceptance Point)
- Lower & Upper specification limit lines if provided
- Interactive hover tooltips
- KPI Summary Cards: Bias, P-Value, Adjusted Repeatability, R-Squared
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
    QPen,
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


class AttributeGageCanvas(QWidget):
    """Drawing canvas for the Gage Performance Curve."""

    def __init__(self, plot_data: Dict[str, Any], bias_metrics: Dict[str, Any], rep_metrics: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.plot_data = plot_data
        self.bias_metrics = bias_metrics
        self.rep_metrics = rep_metrics
        self.setMouseTracking(True)
        self.hovered_point: Optional[Tuple[float, float, str]] = None
        self.hit_regions: List[Tuple[QRectF, float, float, str]] = []

    def mouseMoveEvent(self, event):
        pos = event.position()
        old_hover = self.hovered_point
        self.hovered_point = None
        for rect, rx, rp, label in self.hit_regions:
            if rect.contains(pos):
                self.hovered_point = (rx, rp, label)
                break
        if old_hover != self.hovered_point:
            self.update()

    def leaveEvent(self, _event):
        if self.hovered_point is not None:
            self.hovered_point = None
            self.update()

    def paintEvent(self, _event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect()
        w = rect.width()
        h = rect.height()

        # Canvas Background
        painter.fillRect(rect, QColor("#ffffff"))

        # Margins
        left_m = 65
        right_m = 40
        top_m = 35
        bot_m = 50

        pw = w - left_m - right_m
        ph = h - top_m - bot_m
        if pw <= 10 or ph <= 10:
            return

        curve_x = self.plot_data.get("curve_x", [])
        curve_p = self.plot_data.get("curve_p", [])
        points_x = self.plot_data.get("points_x", [])
        points_p = self.plot_data.get("points_p", [])
        raw_p = self.plot_data.get("points_raw_p", points_p)
        target = self.plot_data.get("target")
        x_half = self.plot_data.get("x_half")
        lsl = self.plot_data.get("lsl")
        usl = self.plot_data.get("usl")

        if not curve_x or not curve_p:
            return

        min_x = curve_x[0]
        max_x = curve_x[-1]
        span_x = max(1e-6, max_x - min_x)

        def map_x(val: float) -> float:
            return left_m + ((val - min_x) / span_x) * pw

        def map_y(prob: float) -> float:
            # Prob goes from 0.0 at bottom to 1.0 at top
            return top_m + ph - (max(0.0, min(1.0, prob)) * ph)

        # Plot Area Background
        plot_rect = QRectF(left_m, top_m, pw, ph)
        painter.fillRect(plot_rect, QColor("#f8fafc"))
        painter.setPen(QPen(QColor("#cbd5e1"), 1))
        painter.drawRect(plot_rect)

        # Horizontal Grid lines for Probability (0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0)
        grid_pen = QPen(QColor("#e2e8f0"), 1, Qt.PenStyle.DashLine)
        label_font = QFont("Segoe UI", 8)
        painter.setFont(label_font)

        prob_ticks = [0.0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0]
        for pt in prob_ticks:
            y_pos = map_y(pt)
            if pt == 0.5:
                # 50% acceptance reference line (prominent dotted slate)
                p50_pen = QPen(QColor("#64748b"), 1.2, Qt.PenStyle.DotLine)
                painter.setPen(p50_pen)
            else:
                painter.setPen(grid_pen)
            painter.drawLine(QPointF(left_m, y_pos), QPointF(left_m + pw, y_pos))

            # Y-axis tick label
            painter.setPen(QColor("#475569"))
            pct_txt = f"{pt * 100:.0f}%" if pt != 0.5 else "50% (P=0.5)"
            painter.drawText(QRectF(0, y_pos - 8, left_m - 8, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, pct_txt)

        # X-axis ticks (5-6 intervals)
        painter.setPen(grid_pen)
        x_steps = 6
        step_val = span_x / x_steps
        for i in range(x_steps + 1):
            xv = min_x + i * step_val
            xp = map_x(xv)
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(xp, top_m), QPointF(xp, top_m + ph))
            painter.setPen(QColor("#475569"))
            painter.drawText(QRectF(xp - 35, top_m + ph + 6, 70, 16), Qt.AlignmentFlag.AlignCenter, f"{xv:.3g}")

        # Vertical Reference Line: Target (Standard)
        if target is not None and min_x <= target <= max_x:
            tx = map_x(target)
            target_pen = QPen(QColor("#ef4444"), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(target_pen)
            painter.drawLine(QPointF(tx, top_m), QPointF(tx, top_m + ph))
            painter.setPen(QColor("#dc2626"))
            painter.drawText(QRectF(tx - 30, top_m - 18, 60, 14), Qt.AlignmentFlag.AlignCenter, "Target")

        # Vertical Reference Line: 50% Acceptance Point (X_0.5)
        if x_half is not None and min_x <= x_half <= max_x:
            hx = map_x(x_half)
            half_pen = QPen(QColor("#0284c7"), 1.2, Qt.PenStyle.DotLine)
            painter.setPen(half_pen)
            painter.drawLine(QPointF(hx, top_m), QPointF(hx, top_m + ph))

        # Specification Limits if provided
        for spec_val, spec_name in [(lsl, "LSL"), (usl, "USL")]:
            if spec_val is not None and min_x <= float(spec_val) <= max_x:
                sx = map_x(float(spec_val))
                s_pen = QPen(QColor("#d97706"), 1.2, Qt.PenStyle.DashDotLine)
                painter.setPen(s_pen)
                painter.drawLine(QPointF(sx, top_m), QPointF(sx, top_m + ph))
                painter.setPen(QColor("#b45309"))
                painter.drawText(QRectF(sx - 20, top_m - 18, 40, 14), Qt.AlignmentFlag.AlignCenter, spec_name)

        # Draw the Fitted Performance Curve (S-curve)
        curve_pen = QPen(QColor("#0284c7"), 2.2)
        painter.setPen(curve_pen)
        pts = [QPointF(map_x(cx), map_y(cp)) for cx, cp in zip(curve_x, curve_p)]
        for i in range(len(pts) - 1):
            painter.drawLine(pts[i], pts[i + 1])

        # Draw Data Points & Record Hit Regions
        self.hit_regions = []
        point_pen = QPen(QColor("#0f172a"), 1.5)
        point_brush = QBrush(QColor("#38bdf8"))
        painter.setPen(point_pen)
        painter.setBrush(point_brush)

        radius = 4.5
        for idx, (px, py, raw) in enumerate(zip(points_x, points_p, raw_p)):
            cx = map_x(px)
            cy = map_y(py)
            painter.drawEllipse(QPointF(cx, cy), radius, radius)
            rect_hit = QRectF(cx - 8, cy - 8, 16, 16)
            self.hit_regions.append((rect_hit, px, py, f"Part {idx + 1}: Ref={px:.4f}, Raw={raw * 100:.1f}%, Adj={py * 100:.1f}%"))

        # Axis Titles
        title_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor("#0f172a"))
        # X-axis Title
        painter.drawText(QRectF(left_m, top_m + ph + 26, pw, 20), Qt.AlignmentFlag.AlignCenter, "Reference Value")
        # Y-axis Title
        painter.save()
        painter.translate(16, top_m + ph / 2)
        painter.rotate(-90)
        painter.drawText(QRectF(-ph / 2, -10, ph, 20), Qt.AlignmentFlag.AlignCenter, "Probability of Acceptance")
        painter.restore()

        # Tooltip HUD if hovering over a point
        if self.hovered_point:
            _, _, hud_text = self.hovered_point
            hud_font = QFont("Segoe UI", 8.5)
            painter.setFont(hud_font)
            hud_rect = QRectF(left_m + 10, top_m + 10, 240, 24)
            painter.setPen(QPen(QColor("#334155"), 1))
            painter.setBrush(QBrush(QColor("#0f172a")))
            painter.drawRoundedRect(hud_rect, 4, 4)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(hud_rect, Qt.AlignmentFlag.AlignCenter, hud_text)


class AttributeGageChartWidget(QWidget):
    """Container widget with top KPI cards, interactive canvas, and action bar."""

    def __init__(self, result: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.result = result
        self.plot_data = result.get("plot_data", {})
        self.bias = result.get("bias_metrics", {})
        self.rep = result.get("repeatability", {})
        self.reg = result.get("regression", {})

        self.setMinimumSize(680, 480)
        self.setMaximumWidth(960)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header Title and Action Bar
        top_bar = QHBoxLayout()
        title_lbl = QLabel(self.result.get("settings", {}).get("title") or "Gage Performance Curve (Analytic Method)")
        title_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #0f172a;")
        top_bar.addWidget(title_lbl)
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

        b_val = self.bias.get("bias", 0.0)
        p_val = self.bias.get("p_value", 1.0)
        cards_layout.addWidget(make_kpi("Bias", f"{b_val:+.4f}", f"P-Value: {p_val:.4f}", highlight=self.bias.get("is_significant", False)))

        adj_rep = self.rep.get("adjusted", 0.0)
        mult = self.rep.get("study_multiplier", 5.15)
        cards_layout.addWidget(make_kpi("Repeatability", f"{adj_rep:.4f}", f"Study Multiplier: {mult:g}"))

        r2 = self.reg.get("r_squared", 0.0)
        cards_layout.addWidget(make_kpi("Fitted Line R-Sq", f"{r2 * 100.0:.1f}%", f"Slope: {self.reg.get('slope', 0.0):.4f}"))

        pct_rep = self.rep.get("pct_repeatability")
        if pct_rep is not None:
            cards_layout.addWidget(make_kpi("% Repeatability", f"{pct_rep:.2f}%", f"Tolerance: {self.rep.get('tolerance', 0.0):.4g}"))

        layout.addLayout(cards_layout)

        # Performance Curve Canvas
        self.canvas = AttributeGageCanvas(self.plot_data, self.bias, self.rep, self)
        layout.addWidget(self.canvas, 1)

    def render_chart_pixmap(self, width: int = 800, height: int = 600):
        from PySide6.QtGui import QPixmap
        pm = QPixmap(width, height)
        pm.fill(QColor("#ffffff"))
        self.render(pm)
        return pm

    def _copy_to_clipboard(self):
        pixmap = self.canvas.grab()
        QApplication.clipboard().setPixmap(pixmap)

    def _save_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Gage Performance Curve", "Gage_Performance_Curve.png", "PNG Images (*.png)")
        if path:
            pixmap = self.canvas.grab()
            pixmap.save(path, "PNG")
