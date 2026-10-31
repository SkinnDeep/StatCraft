"""High-fidelity Qt/QPainter renderer for Pareto Chart of Standardized Effects in Screening Designs.

Matches Minitab & JMP visual styling:
- Horizontal bars sorted descending by absolute standardized effect |t|
- Y-axis with term labels (e.g. 'Temp', 'Catalyst', 'Temp*Catalyst', 'Temp*Temp')
- X-axis with Standardized Effect (|t|)
- Prominent red dashed reference line at critical t-value (alpha = 0.05)
- Active significant terms (|t| >= t_crit) highlighted in vibrant blue/crimson
- Interactive tooltips showing Term, Effect, and P-value
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .graph_interaction import GraphInteractionMixin

BLUE = "#0061a8"
BLUE_ACTIVE = "#1f77b4"
BLUE_INACTIVE = "#a0c4df"
RED = "#d9381e"
INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
GRID = "#f0f2f5"


class DSDParetoEffectsWidget(GraphInteractionMixin, QWidget):
    """Pareto Chart of the Standardized Effects for Screening & DSD models."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", {})
        self.setMouseTracking(True)
        self.setMinimumSize(680, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._hovered_bar_idx: Optional[int] = None
        self._bar_rects: List[Tuple[QRectF, Dict[str, Any]]] = []

    def sizeHint(self) -> QSize:
        effects = self.result.get("pareto_effects", [])
        h = max(420, 100 + len(effects) * 28)
        return QSize(750, h)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor("#ffffff"))

        effects = self.result.get("pareto_effects", [])
        t_crit = float(self.result.get("t_crit", 2.0))
        resp_name = str(self.result.get("response_name", "Response"))

        # Title
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        title_rect = QRectF(20, 15, w - 40, 24)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignHCenter, f"Pareto Chart of the Standardized Effects (response is {resp_name}, α = 0.05)")

        if not effects:
            painter.setFont(QFont("Segoe UI", 10))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(0, 50, w, h - 50), Qt.AlignmentFlag.AlignCenter, "No model terms available.")
            return

        # Margins
        margin_left = 140
        margin_right = 50
        margin_top = 55
        margin_bottom = 60

        plot_w = max(100.0, float(w - margin_left - margin_right))
        plot_h = max(100.0, float(h - margin_top - margin_bottom))

        # Max X value
        max_eff = max(float(eff.get("effect", 0.0)) for eff in effects)
        x_max = max(max_eff * 1.15, t_crit * 1.35, 3.0)

        def x_to_px(val: float) -> float:
            return margin_left + (val / x_max) * plot_w

        # Draw grid lines and X ticks
        painter.setFont(QFont("Segoe UI", 9))
        n_ticks = 5
        x_step = x_max / n_ticks
        # Round x_step nicely
        magnitude = 10 ** math.floor(math.log10(max(1e-4, x_step)))
        nice_steps = [1, 2, 2.5, 5]
        best_step = magnitude
        for s in nice_steps:
            if s * magnitude >= x_step:
                best_step = s * magnitude
                break
        x_step = best_step

        cur_x = 0.0
        while cur_x <= x_max + 1e-6:
            px = x_to_px(cur_x)
            if px <= margin_left + plot_w + 1:
                painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.SolidLine))
                painter.drawLine(QPointF(px, margin_top), QPointF(px, margin_top + plot_h))
                painter.setPen(QPen(QColor(MUTED), 1))
                painter.drawLine(QPointF(px, margin_top + plot_h), QPointF(px, margin_top + plot_h + 4))
                painter.drawText(QRectF(px - 30, margin_top + plot_h + 6, 60, 20), Qt.AlignmentFlag.AlignHCenter, f"{cur_x:.1f}" if cur_x != int(cur_x) else f"{int(cur_x)}")
            cur_x += x_step

        # X Axis Title
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(margin_left, margin_top + plot_h + 30, plot_w, 22), Qt.AlignmentFlag.AlignHCenter, "Standardized Effect (|t|)")

        # Y Axis Line
        painter.setPen(QPen(QColor(BORDER), 1.5))
        painter.drawLine(QPointF(margin_left, margin_top), QPointF(margin_left, margin_top + plot_h))
        painter.drawLine(QPointF(margin_left, margin_top + plot_h), QPointF(margin_left + plot_w, margin_top + plot_h))

        # Bars
        n_bars = len(effects)
        bar_height = min(26.0, (plot_h / n_bars) * 0.72)
        bar_spacing = plot_h / n_bars

        self._bar_rects = []
        for idx, eff in enumerate(effects):
            val = float(eff.get("effect", 0.0))
            term = str(eff.get("term", ""))
            bar_y = margin_top + idx * bar_spacing + (bar_spacing - bar_height) / 2.0
            bar_w = (val / x_max) * plot_w
            rect = QRectF(margin_left, bar_y, bar_w, bar_height)
            self._bar_rects.append((rect, eff))

            # Color: active if >= t_crit
            is_sig = val >= t_crit
            if is_sig:
                fill_color = QColor(BLUE_ACTIVE)
                edge_color = QColor(BLUE)
            else:
                fill_color = QColor(BLUE_INACTIVE)
                edge_color = QColor(MUTED)

            if idx == self._hovered_bar_idx:
                fill_color = fill_color.lighter(115)

            # Draw bar
            painter.fillRect(rect, fill_color)
            painter.setPen(QPen(edge_color, 1.2))
            painter.drawRect(rect)

            # Y-axis term label
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold if is_sig else QFont.Weight.Normal))
            painter.setPen(QColor(INK))
            label_rect = QRectF(10, bar_y, margin_left - 18, bar_height)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, term)

            # Value text right of bar
            painter.setFont(QFont("Segoe UI", 8.5))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(margin_left + bar_w + 6, bar_y, 60, bar_height), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{val:.2f}")

        # Draw red dashed critical line (t_crit)
        px_crit = x_to_px(t_crit)
        if margin_left <= px_crit <= margin_left + plot_w:
            pen_crit = QPen(QColor(RED), 1.8, Qt.PenStyle.DashLine)
            painter.setPen(pen_crit)
            painter.drawLine(QPointF(px_crit, margin_top - 6), QPointF(px_crit, margin_top + plot_h))

            # Critical reference label at top
            painter.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Bold))
            painter.setPen(QColor(RED))
            crit_label = f"Reference = {t_crit:.3f}"
            painter.drawText(QRectF(px_crit - 60, margin_top - 20, 120, 16), Qt.AlignmentFlag.AlignHCenter, crit_label)

    def mouseMoveEvent(self, event):
        pos = event.position()
        found_idx = None
        for idx, (rect, eff) in enumerate(self._bar_rects):
            if rect.contains(pos):
                found_idx = idx
                break

        if found_idx != self._hovered_bar_idx:
            self._hovered_bar_idx = found_idx
            self.update()

        if found_idx is not None:
            _, eff = self._bar_rects[found_idx]
            term = eff.get("term", "")
            val = eff.get("effect", 0.0)
            pval = eff.get("p_val", None)
            p_str = f"{pval:.4f}" if pval is not None else "N/A"
            t_crit = float(self.result.get("t_crit", 2.0))
            status = "Significant (p < 0.05)" if val >= t_crit else "Not significant"
            tip = f"<b>Term:</b> {term}<br/><b>Standardized Effect |t|:</b> {val:.4f}<br/><b>P-Value:</b> {p_str}<br/><b>Status:</b> {status}"
            QToolTip.showText(event.globalPosition().toPoint(), tip, self)
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hovered_bar_idx = None
        self.update()
        super().leaveEvent(event)
