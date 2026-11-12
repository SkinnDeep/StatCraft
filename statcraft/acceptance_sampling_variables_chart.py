"""High-fidelity Qt/QPainter renderer for Acceptance Sampling by Variables.

Renders authentic curves:
- Operating Characteristic (OC) Curve: Probability of Acceptance vs Percent Defective
- Average Outgoing Quality (AOQ) Curve with AOQL line
- Average Total Inspection (ATI) Curve
- Interactive tab/button switching and cursor tracking
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .snapshot_chart import SnapshotChartWidget
from .chart_theme import chart_painter

BLUE = "#0061a8"
BLUE_FILL = "#1f77b4"
RED = "#d9534f"
GREEN = "#2ca02c"
INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
GRID = "#e8ecef"
BOX_BG = "#f8f9fa"


def _fmt(val: Optional[float], dec: int = 4) -> str:
    if val is None or math.isnan(val):
        return "*"
    return f"{val:.{dec}f}"


class _Canvas(QWidget):
    def __init__(self, owner: AcceptanceSamplingVariablesChartWidget):
        super().__init__(owner)
        self.owner = owner
        self.setMouseTracking(True)
        self.hover_x: Optional[float] = None

    def mouseMoveEvent(self, event):
        self.hover_x = event.position().x()
        self.update()

    def leaveEvent(self, event):
        self.hover_x = None
        self.update()

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        self.owner._render_canvas(painter, self.rect(), self.hover_x)


class AcceptanceSamplingVariablesChartWidget(SnapshotChartWidget):
    """Interactive Acceptance Sampling by Variables Widget with OC, AOQ, and ATI curves."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(entry, parent)
        self.result = entry.get("result", {})
        self.active_curve = "oc"  # 'oc', 'aoq', 'ati'

        self.setMinimumSize(680, 440)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Toolbar switcher
        tb_layout = QHBoxLayout()
        self.btn_oc = QPushButton("Operating Characteristic (OC)")
        self.btn_aoq = QPushButton("Average Outgoing Quality (AOQ)")
        self.btn_ati = QPushButton("Average Total Inspection (ATI)")

        for btn in (self.btn_oc, self.btn_aoq, self.btn_ati):
            btn.setCheckable(True)
            tb_layout.addWidget(btn)

        self.btn_oc.setChecked(True)
        self.btn_oc.clicked.connect(lambda: self._set_curve("oc"))
        self.btn_aoq.clicked.connect(lambda: self._set_curve("aoq"))
        self.btn_ati.clicked.connect(lambda: self._set_curve("ati"))

        tb_layout.addStretch()
        layout.addLayout(tb_layout)

        self.canvas = _Canvas(self)
        layout.addWidget(self.canvas, 1)

    def _set_curve(self, ctype: str):
        self.active_curve = ctype
        self.btn_oc.setChecked(ctype == "oc")
        self.btn_aoq.setChecked(ctype == "aoq")
        self.btn_ati.setChecked(ctype == "ati")
        self.canvas.update()

    def _render_canvas(self, painter: QPainter, rect: QRectF, hover_x: Optional[float]):
        painter.fillRect(rect, QColor("#ffffff"))

        n = self.result.get("n", 0)
        k = self.result.get("k", 0.0)
        aql = self.result.get("aql", 0.0)
        rql = self.result.get("rql", 0.0)

        # Layout
        left_m = 65
        right_panel_w = 175
        top_m = 45
        bottom_m = 50
        plot_w = max(10.0, rect.width() - left_m - right_panel_w - 20)
        plot_h = max(10.0, rect.height() - top_m - bottom_m)
        plot_rect = QRectF(left_m, top_m, plot_w, plot_h)
        card_rect = QRectF(plot_rect.right() + 15, top_m, right_panel_w - 5, plot_h)

        # Title
        curve_titles = {
            "oc": "Operating Characteristic (OC) Curve (Variables)",
            "aoq": "Average Outgoing Quality (AOQ) Curve",
            "ati": "Average Total Inspection (ATI) Curve",
        }
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(left_m, 10, plot_w + 100, 24), Qt.AlignmentFlag.AlignLeft, curve_titles[self.active_curve])

        # Get curve points
        pts = self.result.get(f"{self.active_curve}_curve", [])
        if not pts:
            painter.setPen(QColor(MUTED))
            painter.drawText(plot_rect, Qt.AlignmentFlag.AlignCenter, "No curve data available.")
            return

        x_vals = [p["p"] * 100.0 for p in pts]
        y_key = "pa" if self.active_curve == "oc" else ("aoq" if self.active_curve == "aoq" else "ati")
        y_mult = 100.0 if self.active_curve == "aoq" else 1.0
        y_vals = [p[y_key] * y_mult for p in pts]

        min_x, max_x = 0.0, max(x_vals) if x_vals else 1.0
        min_y, max_y = 0.0, max(y_vals) if y_vals else 1.0
        if self.active_curve == "oc":
            min_y, max_y = 0.0, 1.0
        else:
            max_y = max(0.01, max_y * 1.1)

        # Draw grid & axes
        painter.setPen(QPen(QColor(GRID), 1))
        for gy in [0.0, 0.25, 0.5, 0.75, 1.0] if self.active_curve == "oc" else [0.0, 0.5, 1.0]:
            y_coord = plot_rect.bottom() - (gy if self.active_curve == "oc" else gy) * plot_rect.height()
            painter.drawLine(QPointF(plot_rect.left(), y_coord), QPointF(plot_rect.right(), y_coord))

        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(plot_rect)

        # Plot curve
        curve_path = QPainterPath()
        for i, (xv, yv) in enumerate(zip(x_vals, y_vals)):
            px = plot_rect.left() + ((xv - min_x) / (max_x - min_x if max_x > min_x else 1.0)) * plot_rect.width()
            py = plot_rect.bottom() - ((yv - min_y) / (max_y - min_y if max_y > min_y else 1.0)) * plot_rect.height()
            if i == 0:
                curve_path.moveTo(px, py)
            else:
                curve_path.lineTo(px, py)

        color_hex = BLUE if self.active_curve == "oc" else (GREEN if self.active_curve == "aoq" else RED)
        painter.setPen(QPen(QColor(color_hex), 2))
        painter.drawPath(curve_path)

        # X & Y axis labels
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(INK))
        painter.drawText(
            QRectF(plot_rect.left(), plot_rect.bottom() + 10, plot_rect.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            "Percent Defective (100 * p)",
        )

        y_labels = {
            "oc": "Probability of Acceptance (Pa)",
            "aoq": "Average Outgoing Quality (%)",
            "ati": "Average Total Inspection",
        }
        painter.save()
        painter.translate(plot_rect.left() - 45, plot_rect.top() + plot_rect.height() / 2)
        painter.rotate(-90)
        painter.drawText(QRectF(-120, -10, 240, 20), Qt.AlignmentFlag.AlignCenter, y_labels[self.active_curve])
        painter.restore()

        # Side Card: Plan Details
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor(BOX_BG))
        painter.drawRoundedRect(card_rect, 4, 4)

        cx = card_rect.left() + 10
        cy = card_rect.top() + 14

        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(cx, cy, card_rect.width() - 20, 18), "Plan Parameters")
        cy += 20

        painter.setFont(QFont("Segoe UI", 8))
        for lbl, val in [("Sample Size (n)", str(n)), ("Crit. Dist. (k)", _fmt(k, 4))]:
            painter.drawText(QRectF(cx, cy, 85, 16), lbl)
            painter.drawText(QRectF(cx + 85, cy, card_rect.width() - 95, 16), Qt.AlignmentFlag.AlignRight, val)
            cy += 18

        cy += 4
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawLine(QPointF(cx, cy), QPointF(card_rect.right() - 10, cy))
        cy += 8

        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(cx, cy, card_rect.width() - 20, 18), "Quality Limits")
        cy += 20

        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(cx, cy, 60, 16), "AQL")
        painter.drawText(QRectF(cx + 60, cy, card_rect.width() - 70, 16), Qt.AlignmentFlag.AlignRight, f"{aql*100:.2f}%")
        cy += 18

        painter.drawText(QRectF(cx, cy, 60, 16), "RQL (LTPD)")
        painter.drawText(QRectF(cx + 60, cy, card_rect.width() - 70, 16), Qt.AlignmentFlag.AlignRight, f"{rql*100:.2f}%")
        cy += 18

        if self.active_curve == "aoq":
            cy += 4
            painter.setPen(QPen(QColor(BORDER), 1))
            painter.drawLine(QPointF(cx, cy), QPointF(card_rect.right() - 10, cy))
            cy += 8
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QColor(GREEN))
            painter.drawText(QRectF(cx, cy, card_rect.width() - 20, 18), "AOQL")
            cy += 18
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(cx, cy, card_rect.width() - 20, 16), f"{self.result.get('aoql', 0)*100:.3f}%")
