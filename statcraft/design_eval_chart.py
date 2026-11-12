"""Interactive Qt Chart Widget for Design Evaluation (Color Map on Correlations).

Matches JMP Pro "Color Map on Correlations" and Minitab 22 Design Diagnostics:
- Full matrix heatmap of absolute correlations between all estimated model terms.
- Diagonal shown in solid blue (r = 1.0); off-diagonal shows term confounding/aliasing.
- Color scale: White (0.0, Orthogonal) -> Cyan -> Yellow -> Orange -> Crimson (1.0, Aliased).
- Embedded right-hand diagnostics card displaying D-Efficiency, A-Efficiency, G-Efficiency, and Prediction Variance.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .graph_interaction import GraphInteractionMixin
from .chart_theme import chart_painter

INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
CARD_BG = "#f8f9fa"


def _get_corr_color(r: float, is_diag: bool) -> QColor:
    """Return color for correlation cell matching JMP Color Map on Correlations."""
    if is_diag:
        return QColor("#1d4ed8")  # Solid Royal Blue for self-correlation 1.0

    r_abs = min(1.0, max(0.0, abs(r)))
    if r_abs < 0.01:
        return QColor("#ffffff")  # White: Orthogonal (ideal)
    elif r_abs < 0.20:
        # Very light cyan/blue
        alpha = int((r_abs / 0.20) * 120) + 30
        c = QColor("#38bdf8")
        c.setAlpha(alpha)
        return c
    elif r_abs < 0.50:
        # Amber / Yellow
        alpha = int(((r_abs - 0.20) / 0.30) * 180) + 60
        c = QColor("#f59e0b")
        c.setAlpha(alpha)
        return c
    else:
        # High correlation / Aliasing (Orange to Crimson)
        alpha = int(((r_abs - 0.50) / 0.50) * 190) + 65
        c = QColor("#ef4444")
        c.setAlpha(alpha)
        return c


class DesignEvaluationChartWidget(GraphInteractionMixin, QWidget):
    """High-fidelity vector Color Map on Correlations for DOE Evaluation."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", entry)
        self.setMouseTracking(True)
        self.setMinimumSize(880, 580)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:
        return QSize(920, 600)

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#ffffff"))

        res = self.result
        eval_res = res.get("eval", {})
        design_name = str(res.get("design_name", "Design Evaluation"))
        model_order = str(res.get("model_order", "interactions")).capitalize()
        term_names = res.get("term_names", [])
        # Exclude Intercept for the effects correlation matrix
        active_terms = [t for t in term_names if t != "Intercept"]
        corr_mat = eval_res.get("correlation_matrix", [])

        # 1. Header
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(24, 30, f"Color Map on Correlations — {design_name}")

        d_eff = float(eval_res.get("d_efficiency", 0.0))
        n_runs = int(res.get("n_runs", 0))
        p_terms = int(eval_res.get("n_terms", 0))

        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(MUTED))
        painter.drawText(24, 48, f"Runs: {n_runs}   |   Terms: {p_terms}   |   Model: {model_order}   |   D-Efficiency: {d_eff:.1f}%")

        # 2. Main layout: Left = Heatmap Matrix; Right = Diagnostics Card
        card_w = 260.0
        plot_w = w - card_w - 50.0
        plot_h = h - 70.0
        plot_x = 24.0
        plot_y = 60.0

        # Draw Right Side Panel (Diagnostics)
        card_x = w - card_w - 20.0
        card_rect = QRectF(card_x, plot_y, card_w, plot_h)
        painter.fillRect(card_rect, QColor(CARD_BG))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(card_rect)

        # Card Title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        painter.drawText(int(card_x + 14), int(plot_y + 24), "Design Diagnostics")

        # Efficiency Score Badge
        badge_rect = QRectF(card_x + 14, plot_y + 36, card_w - 28, 50)
        badge_bg = QColor("#ecfdf5") if d_eff >= 80.0 else (QColor("#fffbeb") if d_eff >= 60.0 else QColor("#fef2f2"))
        badge_border = QColor("#10b981") if d_eff >= 80.0 else (QColor("#f59e0b") if d_eff >= 60.0 else QColor("#ef4444"))
        painter.fillRect(badge_rect, badge_bg)
        painter.setPen(QPen(badge_border, 1.5))
        painter.drawRoundedRect(badge_rect, 6, 6)

        painter.setPen(badge_border)
        painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        painter.drawText(QRectF(badge_rect.left(), badge_rect.top() + 6, badge_rect.width(), 24), Qt.AlignmentFlag.AlignCenter, f"{d_eff:.1f}%")
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(badge_rect.left(), badge_rect.top() + 30, badge_rect.width(), 16), Qt.AlignmentFlag.AlignCenter, "D-Efficiency (Optimality)")

        # Diagnostics items
        diag_items = [
            ("A-Efficiency", f"{eval_res.get('a_efficiency', 0.0):.1f}%"),
            ("G-Efficiency", f"{eval_res.get('g_efficiency', 0.0):.1f}%"),
            ("Average Pred Var", f"{eval_res.get('average_variance', 0.0):.3f}"),
            ("Maximum Pred Var", f"{eval_res.get('max_variance', 0.0):.3f}"),
            ("Degrees of Freedom", f"{max(0, n_runs - p_terms)} (Error)"),
            ("Design Rank", f"{eval_res.get('rank', p_terms)} / {p_terms}"),
        ]

        cy = plot_y + 110.0
        painter.setFont(QFont("Segoe UI", 8))
        for lbl, val in diag_items:
            painter.setPen(QColor(MUTED))
            painter.drawText(int(card_x + 14), int(cy), lbl)
            painter.setPen(QColor(INK))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(card_x + 120, cy - 12, card_w - 134, 16), Qt.AlignmentFlag.AlignRight, val)
            painter.setFont(QFont("Segoe UI", 8))
            cy += 22.0

        # Color Scale Legend in Card Bottom
        cy += 10.0
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Bold))
        painter.drawText(int(card_x + 14), int(cy), "Absolute Correlation Legend")

        cy += 14.0
        legend_w = card_w - 28.0
        legend_h = 14.0
        painter.drawRect(QRectF(card_x + 14, cy, legend_w, legend_h))

        # Draw gradient steps
        n_steps = 20
        step_w = legend_w / n_steps
        for s in range(n_steps):
            r_val = s / float(n_steps - 1)
            c = _get_corr_color(r_val, is_diag=False)
            painter.fillRect(QRectF(card_x + 14 + s * step_w, cy, step_w + 1, legend_h), c)

        cy += 20.0
        painter.setFont(QFont("Segoe UI", 7))
        painter.setPen(QColor(MUTED))
        painter.drawText(int(card_x + 14), int(cy), "0.0 (Orthogonal)")
        painter.drawText(QRectF(card_x + 14, cy - 8, legend_w, 14), Qt.AlignmentFlag.AlignCenter, "0.5")
        painter.drawText(QRectF(card_x + 14, cy - 8, legend_w, 14), Qt.AlignmentFlag.AlignRight, "1.0 (Aliased)")

        # 3. Draw Left Heatmap Grid
        n_m = len(active_terms)
        if n_m == 0 or not corr_mat:
            return

        heat_rect = QRectF(plot_x, plot_y, plot_w, plot_h)
        painter.fillRect(heat_rect, QColor("#ffffff"))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(heat_rect)

        # Margins for labels
        margin_left = 65.0
        margin_top = 45.0
        margin_right = 20.0
        margin_bottom = 45.0

        grid_w = plot_w - margin_left - margin_right
        grid_h = plot_h - margin_top - margin_bottom
        grid_size = min(grid_w, grid_h)

        gx_start = plot_x + margin_left
        gy_start = plot_y + margin_top
        cell_size = grid_size / n_m

        # Draw Cells
        # Note: corr_mat indices 1..p correspond to active_terms 0..n_m-1
        for i in range(n_m):
            # Row label on left
            t_row = active_terms[i]
            disp_row = t_row if len(t_row) <= 8 else t_row[:7] + "…"
            painter.setFont(QFont("Segoe UI", 7.5, QFont.Weight.DemiBold))
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(plot_x + 4, gy_start + i * cell_size, margin_left - 8, cell_size),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, disp_row)

            # Column label on top (rotated 45 deg or vertical)
            t_col = active_terms[i]
            disp_col = t_col if len(t_col) <= 8 else t_col[:7] + "…"
            painter.save()
            painter.translate(gx_start + (i + 0.5) * cell_size, gy_start - 6)
            painter.rotate(-45)
            painter.drawText(0, 0, disp_col)
            painter.restore()

            for j in range(n_m):
                cx = gx_start + j * cell_size
                cy = gy_start + i * cell_size
                cell_rect = QRectF(cx, cy, cell_size, cell_size)

                # Correlation value from matrix (offset by 1 to skip intercept)
                r_val = float(corr_mat[i + 1][j + 1]) if (i + 1 < len(corr_mat) and j + 1 < len(corr_mat[i + 1])) else 0.0
                cell_col = _get_corr_color(r_val, is_diag=(i == j))

                painter.fillRect(cell_rect, cell_col)
                painter.setPen(QPen(QColor("#cbd5e1"), 0.8))
                painter.drawRect(cell_rect)

                # Draw text inside cell if big enough
                if cell_size >= 24:
                    painter.setFont(QFont("Segoe UI", 7))
                    txt_col = "#ffffff" if (i == j or abs(r_val) > 0.6) else INK
                    painter.setPen(QColor(txt_col))
                    painter.drawText(cell_rect, Qt.AlignmentFlag.AlignCenter, f"{abs(r_val):.2f}" if i != j else "1")
