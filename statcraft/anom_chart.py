"""High-fidelity Qt Interactive Chart Widget for Analysis of Means (ANOM).

Renders Minitab 22-standard ANOM charts with:
- Center line (green)
- Upper and Lower Decision Limits (UDL, LDL in crimson dashed lines)
- Level points with connected trajectory line
- Significant deviations highlighted in vibrant red
- Interactive hover cards & tooltips
- Tabbed support for Two-Way ANOM (Factor 1, Factor 2, Interaction)
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)


class SingleANOMCanvas(QWidget):
    """Sub-canvas rendering an individual ANOM chart (1-way or sub-component)."""

    def __init__(self, data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data = data
        self.setMouseTracking(True)
        self.hovered_idx: Optional[int] = None
        self.hit_regions: List[Tuple[QRectF, int]] = []
        self.setMinimumSize(480, 360)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Clean background
        painter.fillRect(0, 0, w, h, QColor("#ffffff"))

        levels = self.data.get("levels", [])
        if not levels:
            painter.setPen(QColor("#64748b"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No ANOM data to display.")
            return

        grand_mean = float(self.data.get("grand_mean", 0.0))
        alpha = float(self.data.get("alpha", 0.05))
        title = str(self.data.get("title", "Analysis of Means"))
        dist_type = str(self.data.get("distribution", "normal")).capitalize()
        factor_name = str(self.data.get("factor_name", "Factor"))

        # Margins & Plot Rect
        left_m = 75
        right_m = 120
        top_m = 65
        bottom_m = 60
        plot_rect = QRectF(left_m, top_m, max(100, w - left_m - right_m), max(100, h - top_m - bottom_m))

        # Value bounds (Y)
        all_vals = [float(l["mean"]) for l in levels]
        all_udl = [float(l["udl"]) for l in levels]
        all_ldl = [float(l["ldl"]) for l in levels]

        min_y = min(min(all_vals), min(all_ldl), grand_mean)
        max_y = max(max(all_vals), max(all_udl), grand_mean)
        y_span = max_y - min_y
        if y_span < 1e-8:
            y_span = 1.0
        y_pad = y_span * 0.15
        val_min = min_y - y_pad
        val_max = max_y + y_pad

        def val_to_y(v: float) -> float:
            return plot_rect.bottom() - ((v - val_min) / (val_max - val_min)) * plot_rect.height()

        # Title
        painter.setPen(QColor("#0f172a"))
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        painter.drawText(QRectF(left_m, 12, plot_rect.width(), 24), Qt.AlignmentFlag.AlignLeft, title)

        painter.setPen(QColor("#64748b"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))
        painter.drawText(
            QRectF(left_m, 36, plot_rect.width(), 18),
            Qt.AlignmentFlag.AlignLeft,
            f"{dist_type} Distribution  |  α = {alpha:g}  |  Center = {grand_mean:.4g}",
        )

        # Plot background and border
        painter.fillRect(plot_rect, QColor("#f8fafc"))
        painter.setPen(QPen(QColor("#cbd5e1"), 1))
        painter.drawRect(plot_rect)

        # X coordinates for levels
        n_levels = len(levels)
        x_step = plot_rect.width() / (n_levels + 1)
        x_coords = [plot_rect.left() + (i + 1) * x_step for i in range(n_levels)]

        # Center line
        y_cl = val_to_y(grand_mean)
        if plot_rect.top() <= y_cl <= plot_rect.bottom():
            pen_cl = QPen(QColor("#16a34a"), 1.8, Qt.PenStyle.SolidLine)
            painter.setPen(pen_cl)
            painter.drawLine(QPointF(plot_rect.left(), y_cl), QPointF(plot_rect.right(), y_cl))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            painter.drawText(QPointF(plot_rect.right() + 6, y_cl + 4), f"Center = {grand_mean:.4g}")

        # Decision Limits (Step or Constant)
        # Check if UDL/LDL are constant
        udl_const = all(abs(u - all_udl[0]) < 1e-6 for u in all_udl)
        ldl_const = all(abs(l - all_ldl[0]) < 1e-6 for l in all_ldl)

        pen_dl = QPen(QColor("#dc2626"), 1.6, Qt.PenStyle.DashLine)
        painter.setPen(pen_dl)

        if udl_const:
            y_u = val_to_y(all_udl[0])
            if plot_rect.top() <= y_u <= plot_rect.bottom():
                painter.drawLine(QPointF(plot_rect.left(), y_u), QPointF(plot_rect.right(), y_u))
                painter.drawText(QPointF(plot_rect.right() + 6, y_u + 4), f"UDL = {all_udl[0]:.4g}")
        else:
            # Step limits
            for i in range(n_levels):
                x_l = plot_rect.left() + i * x_step + (x_step * 0.1)
                x_r = plot_rect.left() + (i + 1) * x_step + (x_step * 0.9)
                y_u = val_to_y(all_udl[i])
                painter.drawLine(QPointF(x_l, y_u), QPointF(x_r, y_u))

        if ldl_const:
            y_l = val_to_y(all_ldl[0])
            if plot_rect.top() <= y_l <= plot_rect.bottom():
                painter.drawLine(QPointF(plot_rect.left(), y_l), QPointF(plot_rect.right(), y_l))
                painter.drawText(QPointF(plot_rect.right() + 6, y_l + 4), f"LDL = {all_ldl[0]:.4g}")
        else:
            for i in range(n_levels):
                x_l = plot_rect.left() + i * x_step + (x_step * 0.1)
                x_r = plot_rect.left() + (i + 1) * x_step + (x_step * 0.9)
                y_l = val_to_y(all_ldl[i])
                painter.drawLine(QPointF(x_l, y_l), QPointF(x_r, y_l))

        # Y Axis labels & ticks
        painter.setPen(QColor("#64748b"))
        painter.setFont(QFont("Segoe UI", 8))
        fm = painter.fontMetrics()
        for tick_idx in range(5):
            frac = tick_idx / 4.0
            tick_v = val_min + frac * (val_max - val_min)
            tick_y = val_to_y(tick_v)
            painter.drawLine(QPointF(plot_rect.left() - 4, tick_y), QPointF(plot_rect.left(), tick_y))
            lbl = f"{tick_v:.3g}"
            painter.drawText(QRectF(0, tick_y - 8, left_m - 8, 16), Qt.AlignmentFlag.AlignRight, lbl)

        # Draw connecting line between points
        painter.setPen(QPen(QColor("#0284c7"), 1.6, Qt.PenStyle.SolidLine))
        path = QPainterPath()
        for i, (xc, l) in enumerate(zip(x_coords, levels)):
            yp = val_to_y(float(l["mean"]))
            if i == 0:
                path.moveTo(xc, yp)
            else:
                path.lineTo(xc, yp)
        painter.drawPath(path)

        # Draw Points and hit regions
        self.hit_regions.clear()
        for i, (xc, l) in enumerate(zip(x_coords, levels)):
            yp = val_to_y(float(l["mean"]))
            is_sig = bool(l.get("significant", False))
            is_hovered = (i == self.hovered_idx)

            r_pt = 6 if is_hovered else 4.5
            hit_box = QRectF(xc - 12, yp - 12, 24, 24)
            self.hit_regions.append((hit_box, i))

            if is_sig:
                # Highlight ring
                painter.setPen(QPen(QColor(220, 38, 38, 120), 4))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(xc, yp), r_pt + 3, r_pt + 3)

                painter.setPen(QPen(QColor("#ffffff"), 1.5))
                painter.setBrush(QBrush(QColor("#dc2626")))
                painter.drawEllipse(QPointF(xc, yp), r_pt, r_pt)
            else:
                painter.setPen(QPen(QColor("#ffffff"), 1.5))
                painter.setBrush(QBrush(QColor("#0284c7")))
                painter.drawEllipse(QPointF(xc, yp), r_pt, r_pt)

            # X Axis Label for factor level
            painter.setPen(QColor("#0f172a"))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Medium if not is_hovered else QFont.Weight.Bold))
            lvl_text = str(l["level"])
            t_w = fm.horizontalAdvance(lvl_text)
            painter.drawText(QPointF(xc - t_w / 2, plot_rect.bottom() + 18), lvl_text)

        # X Axis Title
        painter.setPen(QColor("#475569"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(plot_rect.left(), plot_rect.bottom() + 28, plot_rect.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            factor_name,
        )

        # Hover Tooltip / HUD Card
        if self.hovered_idx is not None and 0 <= self.hovered_idx < len(levels):
            h_lvl = levels[self.hovered_idx]
            xc = x_coords[self.hovered_idx]
            yp = val_to_y(float(h_lvl["mean"]))

            hud_w = 190
            hud_h = 90
            hud_x = xc + 12
            if hud_x + hud_w > w - 10:
                hud_x = xc - hud_w - 12
            hud_y = max(10, min(yp - hud_h / 2, h - hud_h - 10))

            card_rect = QRectF(hud_x, hud_y, hud_w, hud_h)
            painter.setPen(QPen(QColor("#cbd5e1"), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255, 240)))
            painter.drawRoundedRect(card_rect, 6, 6)

            painter.setPen(QColor("#0f172a"))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(hud_x + 8, hud_y + 6, hud_w - 16, 16), Qt.AlignmentFlag.AlignLeft, f"Level: {h_lvl['level']}")

            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))
            painter.setPen(QColor("#334155"))
            diff = float(h_lvl.get("diff", 0.0))
            painter.drawText(QRectF(hud_x + 8, hud_y + 24, hud_w - 16, 14), Qt.AlignmentFlag.AlignLeft, f"Value: {float(h_lvl['mean']):.4f} (N={h_lvl.get('n', 0)})")
            painter.drawText(QRectF(hud_x + 8, hud_y + 39, hud_w - 16, 14), Qt.AlignmentFlag.AlignLeft, f"UDL: {float(h_lvl['udl']):.4f}  LDL: {float(h_lvl['ldl']):.4f}")
            painter.drawText(QRectF(hud_x + 8, hud_y + 54, hud_w - 16, 14), Qt.AlignmentFlag.AlignLeft, f"Diff from Center: {diff:+.4f}")

            status_text = "SIGNIFICANT (Beyond Limits)" if h_lvl.get("significant") else "Normal (In Limits)"
            status_color = QColor("#dc2626") if h_lvl.get("significant") else QColor("#16a34a")
            painter.setPen(status_color)
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            painter.drawText(QRectF(hud_x + 8, hud_y + 70, hud_w - 16, 14), Qt.AlignmentFlag.AlignLeft, status_text)

    def mouseMoveEvent(self, event):
        pos = event.position() if hasattr(event, "position") else event.pos()
        old_hover = self.hovered_idx
        self.hovered_idx = None
        for rect, idx in self.hit_regions:
            if rect.contains(pos):
                self.hovered_idx = idx
                break
        if old_hover != self.hovered_idx:
            self.update()


class ANOMChartWidget(QWidget):
    """Container widget supporting One-Way, Binomial, Poisson, and Two-Way ANOM charts."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", {})
        self.current_canvas: Optional[SingleANOMCanvas] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        is_twoway = self.result.get("type") == "two_way"
        if is_twoway:
            # Add switcher bar for Two-Way components
            bar = QWidget()
            bar_layout = QHBoxLayout(bar)
            bar_layout.setContentsMargins(8, 4, 8, 4)
            bar_layout.setSpacing(6)

            f1_btn = QPushButton(f"Main Effects: {self.result.get('factor1_name', 'Factor 1')}")
            f2_btn = QPushButton(f"Main Effects: {self.result.get('factor2_name', 'Factor 2')}")
            int_btn = QPushButton("Two-Way Interaction")

            for btn in (f1_btn, f2_btn, int_btn):
                btn.setCheckable(True)
                bar_layout.addWidget(btn)
            bar_layout.addStretch()
            layout.addWidget(bar)

            f1_btn.setChecked(True)

            self.container_layout = QVBoxLayout()
            layout.addLayout(self.container_layout, 1)

            def switch_to(comp: str):
                f1_btn.setChecked(comp == "f1")
                f2_btn.setChecked(comp == "f2")
                int_btn.setChecked(comp == "int")
                if self.current_canvas:
                    self.current_canvas.deleteLater()
                if comp == "f1":
                    self.current_canvas = SingleANOMCanvas(self.result.get("factor1", {}), self)
                elif comp == "f2":
                    self.current_canvas = SingleANOMCanvas(self.result.get("factor2", {}), self)
                else:
                    self.current_canvas = SingleANOMCanvas(self.result.get("interaction", {}), self)
                self.container_layout.addWidget(self.current_canvas, 1)

            f1_btn.clicked.connect(lambda: switch_to("f1"))
            f2_btn.clicked.connect(lambda: switch_to("f2"))
            int_btn.clicked.connect(lambda: switch_to("int"))

            # Start with Factor 1
            self.current_canvas = SingleANOMCanvas(self.result.get("factor1", {}), self)
            self.container_layout.addWidget(self.current_canvas, 1)
        else:
            self.current_canvas = SingleANOMCanvas(self.result, self)
            layout.addWidget(self.current_canvas, 1)
