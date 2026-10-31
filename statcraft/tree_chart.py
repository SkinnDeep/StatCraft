"""Interactive Qt Chart Widget for CART® Decision Trees (Partition Diagrams).

Matches Minitab 22 and JMP Pro Partition Tree visual layout:
- Hierarchical binary tree layout with branch splitting conditions.
- Color-coded node boxes showing Node ID, observation count N, response mean/class, and purity/SD.
- Right-hand summary panel featuring horizontal Predictor Importance bar chart and key model fit metrics.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .graph_interaction import GraphInteractionMixin

INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
GRID = "#f0f2f5"
CARD_BG = "#f8f9fa"
BLUE = "#2563eb"
EMERALD = "#10b981"
AMBER = "#f59e0b"


class DecisionTreeWidget(GraphInteractionMixin, QWidget):
    """High-fidelity vector CART Decision Tree diagram with Variable Importance."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", entry)
        self.setMouseTracking(True)
        self.setMinimumSize(920, 600)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:
        return QSize(960, 620)

    def _assign_positions(self, node: Dict[str, Any], left_bound: float, right_bound: float, y_start: float, y_step: float, pos_dict: Dict[int, Tuple[float, float]]):
        """Recursively calculate (x, y) coordinates for all nodes in the tree."""
        if not node:
            return

        node_id = node.get("node_id", 1)
        depth = node.get("depth", 0)
        y = y_start + depth * y_step

        if node.get("is_leaf", False) or not node.get("left") or not node.get("right"):
            x = (left_bound + right_bound) / 2.0
            pos_dict[node_id] = (x, y)
        else:
            mid = (left_bound + right_bound) / 2.0
            self._assign_positions(node["left"], left_bound, mid, y_start, y_step, pos_dict)
            self._assign_positions(node["right"], mid, right_bound, y_start, y_step, pos_dict)
            left_x, _ = pos_dict[node["left"]["node_id"]]
            right_x, _ = pos_dict[node["right"]["node_id"]]
            x = (left_x + right_x) / 2.0
            pos_dict[node_id] = (x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#ffffff"))

        res = self.result
        resp_name = str(res.get("response_name", "Response"))
        tree_type = str(res.get("tree_type", "regression")).capitalize()
        metrics = res.get("metrics", {})
        root = res.get("tree_structure", {})

        # 1. Header
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(24, 30, f"CART® {tree_type} Tree — {resp_name}")

        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(MUTED))
        r2_or_acc = f"R² = {metrics.get('r2', 0.0)*100:.1f}%" if tree_type.lower() == "regression" else f"Accuracy = {metrics.get('accuracy', 0.0)*100:.1f}%"
        painter.drawText(24, 48, f"Leaves: {metrics.get('n_terminal_nodes', 0)}   |   Depth: {metrics.get('max_depth_reached', 0)}   |   {r2_or_acc}")

        # 2. Main layout: Left = Tree Diagram; Right = Predictor Importance & Model Summary
        card_w = 280.0
        plot_w = w - card_w - 48.0
        plot_h = h - 70.0
        plot_x = 24.0
        plot_y = 60.0

        # Draw Right Side Panel (Predictor Importance)
        card_x = w - card_w - 20.0
        card_rect = QRectF(card_x, plot_y, card_w, plot_h)
        painter.fillRect(card_rect, QColor(CARD_BG))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(card_rect)

        # Card Title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        painter.drawText(int(card_x + 14), int(plot_y + 24), "Predictor Importance")

        # Horizontal Importance Bars
        importances = res.get("importances", [])
        top_importances = importances[:8]  # Show top 8
        bar_y = plot_y + 44.0
        max_bar_w = card_w - 90.0

        painter.setFont(QFont("Segoe UI", 8))
        for item in top_importances:
            feat_name = item.get("feature", "")
            imp_val = float(item.get("importance", 0.0))

            painter.setPen(QColor(INK))
            # Truncate long feature names
            disp_name = feat_name if len(feat_name) <= 12 else feat_name[:11] + "…"
            painter.drawText(int(card_x + 14), int(bar_y + 12), disp_name)

            # Bar
            bw = (imp_val / 100.0) * max_bar_w
            painter.fillRect(QRectF(card_x + 95, bar_y + 2, bw, 12), QColor("#3b82f6"))
            painter.setPen(QPen(QColor(BORDER), 1))
            painter.drawRect(QRectF(card_x + 95, bar_y + 2, bw, 12))

            # % Label
            painter.setPen(QColor(MUTED))
            painter.drawText(int(card_x + 100 + bw), int(bar_y + 12), f"{imp_val:.1f}%")
            bar_y += 24.0

        # Model Summary Stats in Card Bottom
        div_y = bar_y + 10.0
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawLine(QPointF(card_x + 10, div_y), QPointF(card_x + card_w - 10, div_y))

        stat_y = div_y + 20.0
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(int(card_x + 14), int(stat_y), "Fit Summary")

        stats_items = [
            ("Sample Size (N)", str(metrics.get("n_samples", 0))),
            ("Terminal Leaves", str(metrics.get("n_terminal_nodes", 0))),
            ("Max Tree Depth", str(metrics.get("max_depth_reached", 0))),
        ]
        if tree_type.lower() == "regression":
            stats_items.extend([
                ("R² (R-squared)", f"{metrics.get('r2', 0.0)*100:.2f}%"),
                ("RMSE", f"{metrics.get('rmse', 0.0):.4f}"),
                ("Mean Abs Error", f"{metrics.get('mae', 0.0):.4f}"),
            ])
        else:
            stats_items.extend([
                ("Accuracy", f"{metrics.get('accuracy', 0.0)*100:.2f}%"),
                ("Misclass Rate", f"{metrics.get('misclassification_rate', 0.0)*100:.2f}%"),
            ])

        stat_y += 18.0
        painter.setFont(QFont("Segoe UI", 8))
        for lbl, val in stats_items:
            painter.setPen(QColor(MUTED))
            painter.drawText(int(card_x + 14), int(stat_y), lbl)
            painter.setPen(QColor(INK))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(card_x + 130, stat_y - 12, card_w - 144, 16), Qt.AlignmentFlag.AlignRight, val)
            painter.setFont(QFont("Segoe UI", 8))
            stat_y += 20.0

        # 3. Draw Left Tree Diagram
        if not root:
            return

        tree_rect = QRectF(plot_x, plot_y, plot_w, plot_h)
        painter.fillRect(tree_rect, QColor("#ffffff"))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(tree_rect)

        # Compute node layout positions
        pos_dict: Dict[int, Tuple[float, float]] = {}
        max_d = max(1, metrics.get("max_depth_reached", 1))
        y_step = min(110.0, (plot_h - 100.0) / max(1, max_d))
        self._assign_positions(root, plot_x + 40.0, plot_x + plot_w - 40.0, plot_y + 45.0, y_step, pos_dict)

        # Draw branches first (so lines are behind node boxes)
        self._draw_branches(painter, root, pos_dict)

        # Draw node boxes on top
        self._draw_nodes(painter, root, pos_dict, tree_type.lower() == "regression")

    def _draw_branches(self, painter: QPainter, node: Dict[str, Any], pos_dict: Dict[int, Tuple[float, float]]):
        if not node or node.get("is_leaf", False):
            return

        curr_id = node.get("node_id", 1)
        if curr_id not in pos_dict:
            return

        cx, cy = pos_dict[curr_id]
        box_h = 50.0

        # Left branch
        left_child = node.get("left")
        if left_child and left_child.get("node_id") in pos_dict:
            lx, ly = pos_dict[left_child["node_id"]]
            painter.setPen(QPen(QColor("#64748b"), 1.8))
            painter.drawLine(QPointF(cx, cy + box_h / 2), QPointF(lx, ly - box_h / 2))

            # Split text on left branch
            feat = node.get("feature_name", "X")
            if node.get("feature_kind") == "numeric":
                thresh = node.get("split_threshold", 0.0)
                txt = f"≤ {thresh:.2f}"
            else:
                cats = node.get("split_categories", [])
                txt = f"in {','.join(cats[:2])}"

            painter.setFont(QFont("Segoe UI", 7.5, QFont.Weight.DemiBold))
            painter.setPen(QColor("#0284c7"))
            mx, my = (cx + lx) / 2.0 - 22.0, (cy + ly) / 2.0 - 6.0
            painter.drawText(QRectF(mx, my, 60, 16), Qt.AlignmentFlag.AlignCenter, txt)

            self._draw_branches(painter, left_child, pos_dict)

        # Right branch
        right_child = node.get("right")
        if right_child and right_child.get("node_id") in pos_dict:
            rx, ry = pos_dict[right_child["node_id"]]
            painter.setPen(QPen(QColor("#64748b"), 1.8))
            painter.drawLine(QPointF(cx, cy + box_h / 2), QPointF(rx, ry - box_h / 2))

            # Split text on right branch
            feat = node.get("feature_name", "X")
            if node.get("feature_kind") == "numeric":
                thresh = node.get("split_threshold", 0.0)
                txt = f"> {thresh:.2f}"
            else:
                txt = "other"

            painter.setFont(QFont("Segoe UI", 7.5, QFont.Weight.DemiBold))
            painter.setPen(QColor("#ea580c"))
            mx, my = (cx + rx) / 2.0 - 22.0, (cy + ry) / 2.0 - 6.0
            painter.drawText(QRectF(mx, my, 60, 16), Qt.AlignmentFlag.AlignCenter, txt)

            self._draw_branches(painter, right_child, pos_dict)

    def _draw_nodes(self, painter: QPainter, node: Dict[str, Any], pos_dict: Dict[int, Tuple[float, float]], is_regression: bool):
        if not node:
            return

        curr_id = node.get("node_id", 1)
        if curr_id not in pos_dict:
            return

        cx, cy = pos_dict[curr_id]
        box_w = 90.0
        box_h = 50.0
        bx = cx - box_w / 2.0
        by = cy - box_h / 2.0
        rect = QRectF(bx, by, box_w, box_h)

        is_leaf = node.get("is_leaf", False)

        # Background color: Leaves get pleasant emerald/green tint, internal nodes get crisp white/slate
        bg_col = QColor("#ecfdf5") if is_leaf else QColor("#ffffff")
        border_col = QColor("#10b981") if is_leaf else QColor("#94a3b8")

        painter.fillRect(rect, bg_col)
        painter.setPen(QPen(border_col, 1.8 if is_leaf else 1.2))
        painter.drawRoundedRect(rect, 5.0, 5.0)

        # Header bar with Node ID & N
        hdr_rect = QRectF(bx, by, box_w, 18)
        hdr_bg = QColor("#d1fae5") if is_leaf else QColor("#f1f5f9")
        painter.fillRect(hdr_rect, hdr_bg)
        painter.setPen(QPen(border_col, 1))
        painter.drawLine(QPointF(bx, by + 18), QPointF(bx + box_w, by + 18))

        painter.setFont(QFont("Segoe UI", 7.5, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        n_txt = f"Node {curr_id} (n={node.get('n_samples', 0)})"
        painter.drawText(hdr_rect, Qt.AlignmentFlag.AlignCenter, n_txt)

        # Body text
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold if is_leaf else QFont.Weight.Normal))
        if is_regression:
            mean_val = float(node.get("mean", 0.0))
            sd_val = float(node.get("sd", 0.0))
            painter.setPen(QColor("#047857" if is_leaf else INK))
            painter.drawText(QRectF(bx + 4, by + 21, box_w - 8, 14), Qt.AlignmentFlag.AlignCenter, f"μ = {mean_val:.3g}")
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(bx + 4, by + 34, box_w - 8, 14), Qt.AlignmentFlag.AlignCenter, f"s = {sd_val:.2g}")
        else:
            cls_val = str(node.get("predicted_class", ""))
            painter.setPen(QColor("#047857" if is_leaf else INK))
            painter.drawText(QRectF(bx + 4, by + 21, box_w - 8, 14), Qt.AlignmentFlag.AlignCenter, cls_val)
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(bx + 4, by + 34, box_w - 8, 14), Qt.AlignmentFlag.AlignCenter, f"Imp = {node.get('impurity', 0.0):.2f}")

        # Recurse
        if node.get("left"):
            self._draw_nodes(painter, node["left"], pos_dict, is_regression)
        if node.get("right"):
            self._draw_nodes(painter, node["right"], pos_dict, is_regression)
