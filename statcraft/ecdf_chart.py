"""High-Fidelity Qt Interactive Chart Widget for Empirical Cumulative Distribution Function (ECDF).

Renders Minitab-identical:
- Stepped empirical CDF curves
- Simultaneous Dvoretzky-Kiefer-Wolfowitz (DKW) confidence bands
- Parametric theoretical distribution fit curve overlays
- Multi-group comparisons with distinct series colors
- Interactive crosshairs and hover tooltips
- KPI Summary Cards & One-click Export
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

SERIES_COLORS = [
    ("#0284c7", QColor(2, 132, 199, 50)),   # Blue
    ("#e11d48", QColor(225, 29, 72, 45)),   # Crimson
    ("#16a34a", QColor(22, 163, 74, 45)),   # Green
    ("#d97706", QColor(217, 119, 6, 45)),   # Amber
    ("#9333ea", QColor(147, 51, 234, 45)),  # Purple
    ("#0d9488", QColor(13, 148, 136, 45)),  # Teal
]


class ECDFCanvas(QWidget):
    """Drawing canvas for stepped empirical CDF and confidence bands."""

    def __init__(self, result: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.result = result
        self.setMouseTracking(True)
        self.hovered_x: Optional[float] = None
        self.hover_info: Optional[str] = None
        self.step_segments: List[Tuple[float, float, float, str]] = []

    def mouseMoveEvent(self, event):
        pos = event.position()
        old_hover = self.hovered_x
        self.hovered_x = None
        self.hover_info = None

        for x0, x1, p, grp in self.step_segments:
            if x0 <= pos.x() <= x1:
                self.hovered_x = pos.x()
                self.hover_info = f"Group: {grp}\nX ≈ {pos.x():.4g}\nPercentile ≈ {p*100:.1f}%"
                break

        if old_hover != self.hovered_x:
            self.update()

    def leaveEvent(self, event):
        if self.hovered_x is not None:
            self.hovered_x = None
            self.hover_info = None
            self.update()

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())

        painter.fillRect(self.rect(), QColor("#ffffff"))

        left_m = 65.0
        right_m = 35.0
        top_m = 35.0
        bottom_m = 50.0

        plot_w = max(40.0, w - left_m - right_m)
        plot_h = max(40.0, h - top_m - bottom_m)
        plot_rect = QRectF(left_m, top_m, plot_w, plot_h)

        domain = self.result.get('domain', [0.0, 1.0])
        x_min, x_max = float(domain[0]), float(domain[1])
        x_span = max(1e-6, x_max - x_min)
        x_min -= x_span * 0.05
        x_max += x_span * 0.05

        y_min, y_max = 0.0, 1.0

        def to_screen(x: float, y: float) -> QPointF:
            sx = left_m + (x - x_min) / (x_max - x_min) * plot_w
            sy = top_m + plot_h - (y - y_min) / (y_max - y_min) * plot_h
            return QPointF(sx, sy)

        # Draw Grid
        painter.setPen(QPen(QColor("#f1f5f9"), 1.0))
        num_y_ticks = 5
        for i in range(num_y_ticks + 1):
            y_val = i / num_y_ticks
            sy = to_screen(x_min, y_val).y()
            painter.drawLine(QPointF(left_m, sy), QPointF(left_m + plot_w, sy))

        num_x_ticks = 6
        for i in range(num_x_ticks + 1):
            x_val = x_min + (x_max - x_min) * i / num_x_ticks
            sx = to_screen(x_val, y_min).x()
            painter.drawLine(QPointF(sx, top_m), QPointF(sx, top_m + plot_h))

        series = self.result.get('series', [])

        # 1. Draw Confidence Bands (underneath lines)
        for s_idx, s in enumerate(series):
            color_hex, shade_color = SERIES_COLORS[s_idx % len(SERIES_COLORS)]
            b_low = s.get('band_lower', [])
            b_high = s.get('band_upper', [])
            if len(b_low) >= 2 and len(b_high) >= 2:
                poly_pts = [to_screen(pt[0], pt[1]) for pt in b_low]
                poly_pts.extend([to_screen(pt[0], pt[1]) for pt in reversed(b_high)])
                painter.setBrush(QBrush(shade_color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPolygon(QPolygonF(poly_pts))

        # 2. Draw Parametric Theoretical Fit Curves
        for s_idx, s in enumerate(series):
            fit_pts = s.get('fit_curve', [])
            if len(fit_pts) >= 2:
                c_path = QPainterPath()
                c_path.moveTo(to_screen(fit_pts[0][0], fit_pts[0][1]))
                for pt in fit_pts[1:]:
                    c_path.lineTo(to_screen(pt[0], pt[1]))

                fit_pen = QPen(QColor("#dc2626"), 1.8, Qt.PenStyle.DashLine)
                painter.setPen(fit_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(c_path)

        # 3. Draw Stepped Empirical CDF Lines
        for s_idx, s in enumerate(series):
            color_hex, _ = SERIES_COLORS[s_idx % len(SERIES_COLORS)]
            step_pts = s.get('step_points', [])
            if len(step_pts) >= 2:
                line_path = QPainterPath()
                first = to_screen(step_pts[0][0], step_pts[0][1])
                line_path.moveTo(first)
                for pt in step_pts[1:]:
                    line_path.lineTo(to_screen(pt[0], pt[1]))

                line_pen = QPen(QColor(color_hex), 2.2)
                painter.setPen(line_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(line_path)

        # 4. Axes & Labels
        axis_pen = QPen(QColor("#334155"), 1.2)
        painter.setPen(axis_pen)
        painter.drawRect(plot_rect)

        # Y axis ticks & labels
        painter.setFont(QFont("Segoe UI", 8.5))
        painter.setPen(QColor("#64748b"))
        for i in range(num_y_ticks + 1):
            y_val = i / num_y_ticks
            sy = to_screen(x_min, y_val).y()
            tick_r = QRectF(0, sy - 9, left_m - 8, 18)
            pct_label = f"{int(round(y_val * 100))}%"
            painter.drawText(tick_r, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, pct_label)

        # X axis ticks & labels
        for i in range(num_x_ticks + 1):
            x_val = x_min + (x_max - x_min) * i / num_x_ticks
            sx = to_screen(x_val, y_min).x()
            tick_r = QRectF(sx - 30, top_m + plot_h + 6, 60, 18)
            painter.drawText(tick_r, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, f"{x_val:.3g}")

        # Axis Title labels
        painter.setFont(QFont("Segoe UI", 9.5, QFont.Weight.DemiBold))
        painter.setPen(QColor("#1e293b"))

        x_title = self.result.get('variable_name', 'X')
        painter.drawText(QRectF(left_m, h - 22, plot_w, 20), Qt.AlignmentFlag.AlignCenter, x_title)

        painter.save()
        painter.translate(16, top_m + plot_h / 2)
        painter.rotate(-90)
        painter.drawText(QRectF(-plot_h / 2, -10, plot_h, 20), Qt.AlignmentFlag.AlignCenter, "Cumulative Percent")
        painter.restore()

        # Legend if multiple series
        if len(series) > 1:
            painter.setFont(QFont("Segoe UI", 8.5))
            leg_x = left_m + 15
            leg_y = top_m + 15
            for s_idx, s in enumerate(series):
                color_hex, _ = SERIES_COLORS[s_idx % len(SERIES_COLORS)]
                painter.setPen(QPen(QColor(color_hex), 2.0))
                painter.drawLine(QPointF(leg_x, leg_y + s_idx * 18 + 6), QPointF(leg_x + 18, leg_y + s_idx * 18 + 6))
                painter.setPen(QColor("#1e293b"))
                painter.drawText(QRectF(leg_x + 24, leg_y + s_idx * 18, 120, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, s.get('group', ''))


class EmpiricalCDFChartWidget(QWidget):
    """Container widget providing KPI cards, ECDF canvas, and export buttons."""

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
        title_lbl = QLabel(self.result.get('title', 'Empirical CDF'))
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

        var_name = self.result.get('variable_name', 'X')
        n_tot = self.result.get('n_total', 0)
        cards_layout.addWidget(make_kpi("Variable", var_name, f"Total N: {n_tot}"))

        series = self.result.get('series', [])
        first_s = series[0] if series else {}
        med = first_s.get('median', 0.0)
        mean = first_s.get('mean', 0.0)
        cards_layout.addWidget(make_kpi("Median", f"{med:.4f}", f"Mean: {mean:.4f}"))

        sd = first_s.get('stdev', 0.0)
        dist = self.result.get('distribution', 'None')
        cards_layout.addWidget(make_kpi("Std Dev", f"{sd:.4f}", f"Fit: {dist}"))

        eps = first_s.get('epsilon', 0.0)
        conf = self.result.get('confidence', 0.95)
        cards_layout.addWidget(make_kpi("Confidence Band", f"± {eps*100:.1f}%", f"{conf*100:g}% DKW Simultaneous", highlight=True))

        layout.addLayout(cards_layout)

        # Canvas
        self.canvas = ECDFCanvas(self.result, self)
        layout.addWidget(self.canvas, 1)

    def _copy_to_clipboard(self):
        pixmap = self.canvas.grab()
        QApplication.clipboard().setPixmap(pixmap)

    def _save_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Empirical CDF Plot", "Empirical_CDF.png", "PNG Images (*.png)")
        if path:
            pixmap = self.canvas.grab()
            pixmap.save(path, "PNG")
