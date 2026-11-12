"""High-fidelity Qt Interactive Vector Chart Widget for Cause-and-Effect (Fishbone) Diagrams.

Renders Minitab 22-standard Ishikawa diagrams with:
- Central horizontal spine and Effect terminal box
- Alternating top/bottom angled rib branches
- Horizontal sub-branch cause stems with clean typography
- Category label header boxes
- Interactive hover tooltips and highlight paths
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
    QPolygonF,
)
from PySide6.QtWidgets import QToolTip, QWidget
from .chart_theme import chart_painter


class CauseAndEffectChartWidget(QWidget):
    """Minitab 22 Cause-and-Effect (Ishikawa / Fishbone) interactive diagram widget."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", {})
        self.setMouseTracking(True)
        self.hovered_cause: Optional[Tuple[int, int]] = None  # (branch_idx, cause_idx)
        self.hovered_branch: Optional[int] = None
        self.hit_regions: List[Tuple[QRectF, int, Optional[int]]] = []  # (rect, branch_idx, cause_idx)
        self.setMinimumSize(700, 460)

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width()
        h = self.height()

        # Canvas background
        painter.fillRect(0, 0, w, h, QColor("#ffffff"))

        title = str(self.result.get("title", "Cause-and-Effect Diagram"))
        effect_name = str(self.result.get("effect", "Effect"))
        branches = self.result.get("branches", [])
        no_labels = bool(self.result.get("options", {}).get("no_labels", False))

        # Title
        painter.setPen(QColor("#0f172a"))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(30, 14, w - 60, 26), Qt.AlignmentFlag.AlignLeft, title)

        painter.setPen(QColor("#64748b"))
        painter.setFont(QFont("Segoe UI", 8.5))
        painter.drawText(
            QRectF(30, 40, w - 60, 18),
            Qt.AlignmentFlag.AlignLeft,
            f"Ishikawa Fishbone Analysis  |  {len(branches)} Branches  |  {self.result.get('total_causes', 0)} Total Causes",
        )

        if not branches:
            painter.setPen(QColor("#94a3b8"))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No cause-and-effect branches to display.")
            return

        self.hit_regions.clear()

        # Geometry calculations
        margin_left = 40.0
        margin_right = 160.0  # Room for effect box
        margin_top = 80.0
        margin_bottom = 60.0

        y_spine = (h - margin_top - margin_bottom) * 0.5 + margin_top
        x_spine_start = margin_left + 20.0
        x_spine_end = w - margin_right

        # Separate branches into upper and lower groups
        # In Minitab: 1, 3, 5 are upper; 2, 4, 6 are lower
        upper_branches: List[Tuple[int, Dict[str, Any]]] = []
        lower_branches: List[Tuple[int, Dict[str, Any]]] = []

        for i, b in enumerate(branches):
            if i % 2 == 0:
                upper_branches.append((i, b))
            else:
                lower_branches.append((i, b))

        # Draw Spine
        pen_spine = QPen(QColor("#1e293b"), 3.0, Qt.PenStyle.SolidLine)
        pen_spine.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_spine)
        painter.drawLine(QPointF(x_spine_start, y_spine), QPointF(x_spine_end, y_spine))

        # Spine Arrowhead pointing into Effect box
        arrow_size = 14.0
        arrow_poly = QPolygonF([
            QPointF(x_spine_end, y_spine),
            QPointF(x_spine_end - arrow_size, y_spine - 7),
            QPointF(x_spine_end - arrow_size, y_spine + 7),
        ])
        painter.setBrush(QBrush(QColor("#1e293b")))
        painter.drawPolygon(arrow_poly)

        # Draw Effect Terminal Box
        fm_effect = QFontMetrics(QFont("Segoe UI", 10, QFont.Weight.Bold))
        eff_text_w = fm_effect.horizontalAdvance(effect_name)
        eff_box_w = max(110.0, eff_text_w + 24.0)
        eff_box_h = 44.0
        eff_box_x = x_spine_end + 8.0
        eff_box_y = y_spine - eff_box_h * 0.5

        rect_effect = QRectF(eff_box_x, eff_box_y, eff_box_w, eff_box_h)
        painter.setPen(QPen(QColor("#005a9e"), 2.0))
        painter.setBrush(QBrush(QColor("#f0f9ff")))
        painter.drawRoundedRect(rect_effect, 6, 6)

        painter.setPen(QColor("#005a9e"))
        painter.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        painter.drawText(rect_effect, Qt.AlignmentFlag.AlignCenter, effect_name)

        # Function to render rib and causes
        def draw_rib(b_tuple: Tuple[int, Dict[str, Any]], is_upper: bool, root_x: float):
            orig_idx, b_data = b_tuple
            label_text = b_data.get("label", "")
            causes = b_data.get("causes", [])
            is_branch_hovered = (self.hovered_branch == orig_idx)

            # Angled rib line
            # Rib reaches upward (or downward) and backwards to the left (dx < 0)
            rib_len_y = (y_spine - margin_top - 30) if is_upper else (h - margin_bottom - y_spine - 30)
            dx = -rib_len_y * 0.65
            tip_x = root_x + dx
            tip_y = y_spine - rib_len_y if is_upper else y_spine + rib_len_y

            # Draw rib line
            rib_color = QColor("#0284c7") if not is_branch_hovered else QColor("#0369a1")
            rib_width = 2.2 if not is_branch_hovered else 3.0
            painter.setPen(QPen(rib_color, rib_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(root_x, y_spine), QPointF(tip_x, tip_y))

            # Rib Arrow pointing into spine
            r_dx = root_x - tip_x
            r_dy = y_spine - tip_y
            r_angle = math.atan2(r_dy, r_dx)
            rib_arr_size = 8.0
            p_arr1 = QPointF(
                root_x - rib_arr_size * math.cos(r_angle - 0.45),
                y_spine - rib_arr_size * math.sin(r_angle - 0.45)
            )
            p_arr2 = QPointF(
                root_x - rib_arr_size * math.cos(r_angle + 0.45),
                y_spine - rib_arr_size * math.sin(r_angle + 0.45)
            )
            painter.setBrush(QBrush(rib_color))
            painter.drawPolygon(QPolygonF([QPointF(root_x, y_spine), p_arr1, p_arr2]))

            # Category Label Box at tip of rib
            if not no_labels and label_text:
                fm_lbl = QFontMetrics(QFont("Segoe UI", 8.5, QFont.Weight.DemiBold))
                lbl_w = max(80.0, fm_lbl.horizontalAdvance(label_text) + 16.0)
                lbl_h = 24.0
                lbl_x = tip_x - lbl_w * 0.5
                lbl_y = (tip_y - lbl_h - 4) if is_upper else (tip_y + 4)
                lbl_rect = QRectF(lbl_x, lbl_y, lbl_w, lbl_h)

                painter.setPen(QPen(QColor("#cbd5e1"), 1))
                painter.setBrush(QBrush(QColor("#ffffff") if not is_branch_hovered else QColor("#e0f2fe")))
                painter.drawRoundedRect(lbl_rect, 4, 4)

                painter.setPen(QColor("#0f172a") if not is_branch_hovered else QColor("#0369a1"))
                painter.setFont(QFont("Segoe UI", 8.5, QFont.Weight.DemiBold))
                painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, label_text)

                self.hit_regions.append((lbl_rect, orig_idx, None))

            # Draw Sub-branches (Causes)
            num_causes = len(causes)
            if num_causes > 0:
                cause_font = QFont("Segoe UI", 8)
                fm_cause = QFontMetrics(cause_font)
                step_frac = 0.75 / (num_causes + 1)

                for c_i, cause_text in enumerate(causes):
                    # Interpolate along rib
                    frac = 0.20 + (c_i + 1) * step_frac
                    c_root_x = root_x + frac * dx
                    c_root_y = y_spine - frac * rib_len_y if is_upper else y_spine + frac * rib_len_y

                    # Stem runs horizontally to the left
                    c_text_w = fm_cause.horizontalAdvance(cause_text)
                    c_stem_len = max(55.0, c_text_w + 14.0)
                    c_tip_x = c_root_x - c_stem_len
                    c_tip_y = c_root_y

                    is_c_hovered = (self.hovered_cause == (orig_idx, c_i))
                    stem_color = QColor("#2563eb") if is_c_hovered else QColor("#94a3b8")
                    painter.setPen(QPen(stem_color, 1.2, Qt.PenStyle.SolidLine))
                    painter.drawLine(QPointF(c_root_x, c_root_y), QPointF(c_tip_x, c_tip_y))

                    # Text sits slightly above the horizontal line
                    text_y = c_tip_y - 3
                    painter.setPen(QColor("#0f172a") if not is_c_hovered else QColor("#1d4ed8"))
                    painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal if not is_c_hovered else QFont.Weight.Bold))
                    painter.drawText(QPointF(c_tip_x + 2, text_y), cause_text)

                    c_hit = QRectF(c_tip_x - 2, text_y - 12, c_stem_len + 4, 18)
                    self.hit_regions.append((c_hit, orig_idx, c_i))

        # Distribute upper branches along the spine
        n_up = len(upper_branches)
        if n_up > 0:
            up_step = (x_spine_end - x_spine_start - 60) / (n_up + 0.5)
            for j, b_tuple in enumerate(upper_branches):
                root_x = x_spine_start + 40 + (j + 0.7) * up_step
                draw_rib(b_tuple, is_upper=True, root_x=root_x)

        # Distribute lower branches along the spine
        n_down = len(lower_branches)
        if n_down > 0:
            down_step = (x_spine_end - x_spine_start - 60) / (n_down + 0.5)
            for j, b_tuple in enumerate(lower_branches):
                root_x = x_spine_start + 40 + (j + 0.7) * down_step
                draw_rib(b_tuple, is_upper=False, root_x=root_x)

        # Hover Card / Tooltip HUD
        if self.hovered_cause is not None:
            b_idx, c_idx = self.hovered_cause
            if 0 <= b_idx < len(branches) and 0 <= c_idx < len(branches[b_idx]["causes"]):
                branch_obj = branches[b_idx]
                cause_str = branch_obj["causes"][c_idx]
                cat_str = branch_obj.get("label", f"Branch {b_idx + 1}")

                hud_w = 220.0
                hud_h = 56.0
                hud_x = min(w - hud_w - 20, max(20.0, w * 0.5 - hud_w * 0.5))
                hud_y = h - hud_h - 14

                card_rect = QRectF(hud_x, hud_y, hud_w, hud_h)
                painter.setPen(QPen(QColor("#cbd5e1"), 1))
                painter.setBrush(QBrush(QColor(255, 255, 255, 245)))
                painter.drawRoundedRect(card_rect, 6, 6)

                painter.setPen(QColor("#0369a1"))
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.drawText(QRectF(hud_x + 8, hud_y + 6, hud_w - 16, 16), Qt.AlignmentFlag.AlignLeft, f"Category: {cat_str}")

                painter.setPen(QColor("#0f172a"))
                painter.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Normal))
                painter.drawText(QRectF(hud_x + 8, hud_y + 24, hud_w - 16, 26), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, f"Cause: {cause_str}")

    def mouseMoveEvent(self, event):
        pos = event.position() if hasattr(event, "position") else event.pos()
        old_c_hover = self.hovered_cause
        old_b_hover = self.hovered_branch
        self.hovered_cause = None
        self.hovered_branch = None

        for rect, b_idx, c_idx in self.hit_regions:
            if rect.contains(pos):
                if c_idx is not None:
                    self.hovered_cause = (b_idx, c_idx)
                else:
                    self.hovered_branch = b_idx
                break

        if old_c_hover != self.hovered_cause or old_b_hover != self.hovered_branch:
            self.update()
