"""Interactive Qt Chart Widget for Evaluating the Measurement Process (Wheeler EMP).

Matches JMP EMP Gauge and Dr. Donald Wheeler's SPC methodology:
- Wheeler Classification Spectrum meter (First, Second, Third, Fourth Class monitors)
- Intraclass Correlation (ICC / rho) needle and signal attenuation meter
- Shift Detection Power curves (Subgroup 1 to 4 shift detection vs true process shift)
- Embedded diagnostics card with Probable Error (PE), Smallest Effective Unit (SEU), and Resolution chunkiness check
- Variance Components breakdown bar
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .graph_interaction import GraphInteractionMixin
from .chart_theme import chart_painter

INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
GRID = "#f0f2f5"
CARD_BG = "#f8f9fa"


class EMPChartWidget(GraphInteractionMixin, QWidget):
    """High-fidelity vector Wheeler EMP Evaluation and Classification Chart."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", entry)
        self.setMouseTracking(True)
        self.setMinimumSize(840, 560)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:
        return QSize(880, 580)

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#ffffff"))

        res = self.result
        meas_name = str(res.get("meas_name", "Measurement"))
        part_name = str(res.get("part_name", "Part"))
        op_name = str(res.get("op_name", "Operator"))
        rho = float(res.get("rho", 0.0))
        attenuation = float(res.get("attenuation", 0.0))
        emp_class = str(res.get("emp_class", "First Class"))
        pe = float(res.get("probable_error", 0.0))
        res_val = float(res.get("resolution", 0.0))
        res_status = str(res.get("resolution_status", ""))

        # 1. Header
        painter.setPen(QColor(INK))
        font_title = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font_title)
        painter.drawText(24, 30, f"Evaluating the Measurement Process (EMP) — {meas_name}")

        font_sub = QFont("Segoe UI", 9)
        painter.setFont(font_sub)
        painter.setPen(QColor(MUTED))
        painter.drawText(24, 48, f"Part: {part_name}   |   Operator: {op_name}   |   Dr. Donald J. Wheeler SPC Model")

        # 2. Wheeler Spectrum Gauge Bar
        # Width spans from x=24 to w-24
        gauge_x = 24.0
        gauge_y = 66.0
        gauge_w = w - 48.0
        gauge_h = 44.0

        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.drawText(int(gauge_x), int(gauge_y - 6), "Wheeler Monitor Classification & Signal Attenuation Spectrum")

        # Zones: Fourth Class (0.00 to 0.20), Third Class (0.20 to 0.50), Second Class (0.50 to 0.80), First Class (0.80 to 1.00)
        zones = [
            ("Fourth Class (< 0.20)\nAtten > 55%", 0.00, 0.20, QColor("#ef4444"), "Fourth Class"),
            ("Third Class (0.20–0.50)\nAtten 30–55%", 0.20, 0.50, QColor("#f97316"), "Third Class"),
            ("Second Class (0.50–0.80)\nAtten 10–30%", 0.50, 0.80, QColor("#f59e0b"), "Second Class"),
            ("First Class (0.80–1.00)\nAtten < 10%", 0.80, 1.00, QColor("#10b981"), "First Class"),
        ]

        for label_text, z_start, z_end, z_col, z_name in zones:
            zx = gauge_x + z_start * gauge_w
            zw = (z_end - z_start) * gauge_w
            is_active = (z_name == emp_class)

            # Shaded bar
            fill_col = QColor(z_col)
            fill_col.setAlpha(190 if is_active else 80)
            painter.fillRect(QRectF(zx, gauge_y, zw, gauge_h), fill_col)

            # Border
            painter.setPen(QPen(z_col if is_active else QColor(BORDER), 2 if is_active else 1))
            painter.drawRect(QRectF(zx, gauge_y, zw, gauge_h))

            # Text inside zone
            painter.setPen(QColor(INK if not is_active else "#000000"))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold if is_active else QFont.Weight.Normal))
            rect_text = QRectF(zx + 4, gauge_y + 4, zw - 8, gauge_h - 8)
            painter.drawText(rect_text, Qt.AlignmentFlag.AlignCenter, label_text)

        # Draw needle / cursor at rho
        needle_x = gauge_x + max(0.0, min(1.0, rho)) * gauge_w
        needle_pen = QPen(QColor("#1e293b"), 3)
        painter.setPen(needle_pen)
        painter.drawLine(QPointF(needle_x, gauge_y - 4), QPointF(needle_x, gauge_y + gauge_h + 8))

        # Needle pointer triangle on top
        triangle = QPainterPath()
        triangle.moveTo(needle_x, gauge_y - 2)
        triangle.lineTo(needle_x - 6, gauge_y - 10)
        triangle.lineTo(needle_x + 6, gauge_y - 10)
        triangle.closeSubpath()
        painter.fillPath(triangle, QBrush(QColor("#1e293b")))

        # Value label under needle
        needle_label = f"ρ = {rho:.3f} ({emp_class})"
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(needle_x - 60, gauge_y + gauge_h + 10, 120, 20), Qt.AlignmentFlag.AlignCenter, needle_label)

        # 3. Main layout below gauge: Left side = Shift Detection Power Curves; Right side = Diagnostics & Variance Cards
        body_y = gauge_y + gauge_h + 38.0
        body_h = h - body_y - 20.0
        card_w = 310.0
        plot_w = w - card_w - 60.0

        # Draw Left Plot: Shift Detection Power Curves
        plot_rect = QRectF(gauge_x, body_y, plot_w, body_h)
        painter.fillRect(plot_rect, QColor("#ffffff"))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(plot_rect)

        # Plot title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(int(plot_rect.left() + 14), int(plot_rect.top() + 22), "Shift Detection Probabilities Across Subgroups")

        # Plot margins
        px_left = plot_rect.left() + 50.0
        px_right = plot_rect.right() - 25.0
        px_top = plot_rect.top() + 45.0
        px_bottom = plot_rect.bottom() - 40.0
        pw = px_right - px_left
        ph = px_bottom - px_top

        # Grid lines and Y-axis (0 to 100%)
        painter.setFont(QFont("Segoe UI", 8))
        for y_pct in (0, 25, 50, 75, 100):
            yy = px_bottom - (y_pct / 100.0) * ph
            painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(px_left, yy), QPointF(px_right, yy))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(px_left - 45, yy - 8, 40, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{y_pct}%")

        # X-axis ticks (1σ, 2σ, 3σ, 4σ)
        shifts = [1.0, 2.0, 3.0, 4.0]
        for s in shifts:
            xx = px_left + ((s - 1.0) / 3.0) * pw
            painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(xx, px_top), QPointF(xx, px_bottom))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(xx - 20, px_bottom + 6, 40, 18), Qt.AlignmentFlag.AlignCenter, f"{s:g}σ")

        painter.drawText(QRectF(px_left, px_bottom + 22, pw, 18), Qt.AlignmentFlag.AlignCenter, "True Process Mean Shift Size")

        # Y axis label
        painter.save()
        painter.translate(px_left - 36, px_top + ph / 2)
        painter.rotate(-90)
        painter.drawText(QRectF(-80, -10, 160, 20), Qt.AlignmentFlag.AlignCenter, "Detection Probability")
        painter.restore()

        # Draw Curves for Subgroup 1, 1-2, 1-3, 1-4
        curve_colors = [
            (QColor("#2563eb"), "Subgroup 1"),
            (QColor("#0d9488"), "Subgroups 1–2"),
            (QColor("#d97706"), "Subgroups 1–3"),
            (QColor("#7c3aed"), "Subgroups 1–4"),
        ]

        shift_tbl = res.get("shift_table", [])
        if len(shift_tbl) >= 4:
            for s_idx, (c_col, c_name) in enumerate(curve_colors):
                key = f"p_subgroup_{s_idx+1}"
                path = QPainterPath()
                points = []
                for idx, row in enumerate(shift_tbl):
                    s_val = float(idx + 1.0)
                    prob = float(row.get(key, 0.0))
                    cx = px_left + ((s_val - 1.0) / 3.0) * pw
                    cy = px_bottom - prob * ph
                    points.append(QPointF(cx, cy))
                    if idx == 0:
                        path.moveTo(cx, cy)
                    else:
                        path.lineTo(cx, cy)

                # Draw smooth curve
                painter.setPen(QPen(c_col, 2.2))
                painter.drawPath(path)

                # Draw dots
                painter.setBrush(QBrush(c_col))
                for pt in points:
                    painter.drawEllipse(pt, 3.5, 3.5)

        # Legend inside plot
        leg_x = px_left + 15
        leg_y = px_top + 10
        painter.setFont(QFont("Segoe UI", 8))
        for c_col, c_name in curve_colors:
            painter.setPen(QPen(c_col, 2))
            painter.drawLine(QPointF(leg_x, leg_y + 5), QPointF(leg_x + 18, leg_y + 5))
            painter.setBrush(QBrush(c_col))
            painter.drawEllipse(QPointF(leg_x + 9, leg_y + 5), 2.5, 2.5)
            painter.setPen(QColor(INK))
            painter.drawText(int(leg_x + 24), int(leg_y + 9), c_name)
            leg_x += 105

        # 4. Draw Right Side: Diagnostics & Variance Card
        card_x = w - card_w - 24.0
        card_rect = QRectF(card_x, body_y, card_w, body_h)
        painter.fillRect(card_rect, QColor(CARD_BG))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(card_rect)

        # Card header
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(int(card_x + 14), int(body_y + 22), "Wheeler EMP Diagnostics")

        # Diagnostics items
        items = [
            ("Monitor Status", emp_class, res.get("color_code", "#10b981")),
            ("Intraclass Corr (ρ)", f"{rho:.4f} ({rho*100:.1f}%)", "#2563eb"),
            ("Signal Attenuation", f"{attenuation*100:.1f}%", "#d97706" if attenuation > 0.1 else "#10b981"),
            ("Probable Error (PE)", f"{pe:.4f}", INK),
            ("Smallest Effective Unit", f"{0.2*pe:.4f} – {2.0*pe:.4f}", INK),
            ("Observed Resolution", f"{res_val:.4f}", INK),
        ]

        cy = body_y + 46.0
        painter.setFont(QFont("Segoe UI", 8))
        for lbl, val, col in items:
            painter.setPen(QColor(MUTED))
            painter.drawText(int(card_x + 14), int(cy), lbl)
            painter.setPen(QColor(col))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(card_x + 150, cy - 12, card_w - 164, 16), Qt.AlignmentFlag.AlignRight, val)
            painter.setFont(QFont("Segoe UI", 8))
            cy += 22.0

        # Chunkiness status badge
        cy += 4.0
        badge_rect = QRectF(card_x + 14, cy, card_w - 28, 44)
        badge_bg = QColor("#ecfdf5") if "Appropriate" in res_status else (QColor("#fffbeb") if "Too Fine" in res_status else QColor("#fef2f2"))
        badge_border = QColor("#10b981") if "Appropriate" in res_status else (QColor("#f59e0b") if "Too Fine" in res_status else QColor("#ef4444"))
        painter.fillRect(badge_rect, badge_bg)
        painter.setPen(QPen(badge_border, 1))
        painter.drawRect(badge_rect)

        painter.setPen(badge_border)
        painter.setFont(QFont("Segoe UI", 7.5, QFont.Weight.Bold))
        painter.drawText(QRectF(badge_rect.left() + 6, badge_rect.top() + 4, badge_rect.width() - 12, badge_rect.height() - 8),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                         res_status)

        # Variance Components Bar
        cy += 56.0
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Bold))
        painter.drawText(int(card_x + 14), int(cy), "Variance Breakdown")

        cy += 10.0
        bar_w = card_w - 28.0
        bar_h = 20.0
        var_total = float(res.get("var_total", 1.0))
        var_part = float(res.get("var_part", 0.0))
        var_meas = float(res.get("var_measurement", 0.0))

        if var_total > 1e-12:
            pct_part = max(0.0, min(1.0, var_part / var_total))
            pct_meas = max(0.0, min(1.0, var_meas / var_total))

            # Part bar (Blue)
            w_part = pct_part * bar_w
            painter.fillRect(QRectF(card_x + 14, cy, w_part, bar_h), QColor("#3b82f6"))
            # Measurement bar (Orange)
            painter.fillRect(QRectF(card_x + 14 + w_part, cy, bar_w - w_part, bar_h), QColor("#f97316"))
            painter.setPen(QPen(QColor(BORDER), 1))
            painter.drawRect(QRectF(card_x + 14, cy, bar_w, bar_h))

            # Bar labels
            cy += 28.0
            painter.setFont(QFont("Segoe UI", 7.5))
            painter.setPen(QColor("#2563eb"))
            painter.drawText(int(card_x + 14), int(cy), f"■ Part: {pct_part*100:.1f}%")
            painter.setPen(QColor("#ea580c"))
            painter.drawText(QRectF(card_x + 14, cy - 10, bar_w, 14), Qt.AlignmentFlag.AlignRight, f"■ Error: {pct_meas*100:.1f}%")

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
