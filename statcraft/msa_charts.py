"""Qt Interactive Chart Widgets for Advanced MSA (Nested Gage R&R, Gage Linearity & Bias, Attribute Agreement)."""
from __future__ import annotations

from .snapshot_chart import SnapshotChartWidget

import math
import numpy as np
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget
from .chart_theme import chart_painter


class NestedGageRRChartWidget(SnapshotChartWidget):
    """4-in-1 Diagnostic Plot for Nested Gage R&R."""

    def __init__(self, result: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(result, parent)
        self.result = result.get("result", result)
        self.setMinimumSize(700, 500)
        self.setWindowTitle("Gage R&R (Nested) Report")

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        w = self.width()
        h = self.height()

        # Header Title
        painter.setPen(QPen(QColor("#1F2937"), 1))
        font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(0, 5, w, 25), Qt.AlignmentFlag.AlignCenter, "Gage R&R (Nested) for Measurements")

        # 4 Quadrants:
        # Top-Left: Components of Variation (Bar chart)
        # Top-Right: Measurements by Part(Operator)
        # Bottom-Left: Operator Means
        # Bottom-Right: Summary Stats Box
        margin = 15
        top = 35
        hw = (w - 3 * margin) / 2
        hh = (h - top - 2 * margin) / 2

        r_tl = QRectF(margin, top, hw, hh)
        r_tr = QRectF(margin * 2 + hw, top, hw, hh)
        r_bl = QRectF(margin, top + hh + margin, hw, hh)
        r_br = QRectF(margin * 2 + hw, top + hh + margin, hw, hh)

        self._draw_components_panel(painter, r_tl)
        self._draw_part_panel(painter, r_tr)
        self._draw_operator_panel(painter, r_bl)
        self._draw_summary_panel(painter, r_br)

    def _draw_components_panel(self, painter: QPainter, rect: QRectF):
        painter.setPen(QPen(QColor("#D1D5DB"), 1))
        painter.drawRect(rect)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#374151"), 1))
        painter.drawText(QRectF(rect.left(), rect.top() + 5, rect.width(), 20), Qt.AlignmentFlag.AlignCenter, "Components of Variation")

        comps = self.result.get("variance_components", [])
        # Keys to show: Total Gage R&R, Repeatability, Reproducibility, Part-To-Part
        cats = [c for c in comps if c.get("key") in ("total_grr", "repeatability", "reproducibility", "part_to_part")]
        if not cats:
            return

        plot_rect = QRectF(rect.left() + 45, rect.top() + 30, rect.width() - 55, rect.height() - 55)
        # y axis 0 to 100%
        painter.setPen(QPen(QColor("#E5E7EB"), 1, Qt.PenStyle.DashLine))
        for pct in (0, 25, 50, 75, 100):
            y = plot_rect.bottom() - (pct / 100.0) * plot_rect.height()
            painter.drawLine(QPointF(plot_rect.left(), y), QPointF(plot_rect.right(), y))
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QPen(QColor("#6B7280"), 1))
            painter.drawText(QRectF(rect.left(), y - 8, 40, 16), Qt.AlignmentFlag.AlignRight, f"{pct}%")

        n_cats = len(cats)
        slot_w = plot_rect.width() / n_cats
        bar_w = slot_w * 0.35

        for i, c in enumerate(cats):
            bx = plot_rect.left() + i * slot_w + (slot_w - 2 * bar_w) / 2
            # Bar 1: %Contribution (Blue)
            p_contrib = min(100.0, max(0.0, c.get("percent_contribution", 0.0)))
            bh1 = (p_contrib / 100.0) * plot_rect.height()
            painter.fillRect(QRectF(bx, plot_rect.bottom() - bh1, bar_w, bh1), QColor("#2563EB"))

            # Bar 2: %Study Var (Orange)
            p_sv = min(100.0, max(0.0, c.get("percent_study_variation", 0.0)))
            bh2 = (p_sv / 100.0) * plot_rect.height()
            painter.fillRect(QRectF(bx + bar_w + 2, plot_rect.bottom() - bh2, bar_w, bh2), QColor("#F97316"))

            # Label
            label_text = c.get("source", "").strip().replace(" ", "\n")
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QPen(QColor("#374151"), 1))
            painter.drawText(QRectF(plot_rect.left() + i * slot_w, plot_rect.bottom() + 2, slot_w, 25), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label_text)

    def _draw_part_panel(self, painter: QPainter, rect: QRectF):
        painter.setPen(QPen(QColor("#D1D5DB"), 1))
        painter.drawRect(rect)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#374151"), 1))
        painter.drawText(QRectF(rect.left(), rect.top() + 5, rect.width(), 20), Qt.AlignmentFlag.AlignCenter, "Part (Operator) Measurements")

        plot_data = self.result.get("plot_data", {})
        raw = plot_data.get("raw_points", [])
        if not raw:
            return

        vals = [p["val"] for p in raw]
        min_v = min(vals)
        max_v = max(vals)
        span = max(1e-6, max_v - min_v)
        min_v -= 0.1 * span
        max_v += 0.1 * span

        plot_rect = QRectF(rect.left() + 45, rect.top() + 30, rect.width() - 55, rect.height() - 50)
        painter.setPen(QPen(QColor("#E5E7EB"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(plot_rect.bottomLeft(), plot_rect.bottomRight())
        painter.drawLine(plot_rect.topLeft(), plot_rect.bottomLeft())

        n_pts = len(raw)
        step = plot_rect.width() / max(1, n_pts)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#059669")))

        for idx, pt in enumerate(raw):
            cx = plot_rect.left() + idx * step + step / 2
            cy = plot_rect.bottom() - ((pt["val"] - min_v) / (max_v - min_v)) * plot_rect.height()
            painter.drawEllipse(QPointF(cx, cy), 3, 3)

    def _draw_operator_panel(self, painter: QPainter, rect: QRectF):
        painter.setPen(QPen(QColor("#D1D5DB"), 1))
        painter.drawRect(rect)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#374151"), 1))
        painter.drawText(QRectF(rect.left(), rect.top() + 5, rect.width(), 20), Qt.AlignmentFlag.AlignCenter, "Operator Means")

        plot_data = self.result.get("plot_data", {})
        op_means = plot_data.get("op_means", {})
        if not op_means:
            return

        ops = sorted(op_means.keys())
        means = [op_means[op] for op in ops]
        grand = self.result.get("grand_mean", 0.0)

        min_m = min(min(means), grand)
        max_m = max(max(means), grand)
        span = max(1e-6, max_m - min_m)
        min_m -= 0.15 * span
        max_m += 0.15 * span

        plot_rect = QRectF(rect.left() + 45, rect.top() + 30, rect.width() - 55, rect.height() - 55)

        # Draw Grand Mean dashed line
        gy = plot_rect.bottom() - ((grand - min_m) / (max_m - min_m)) * plot_rect.height()
        painter.setPen(QPen(QColor("#DC2626"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(plot_rect.left(), gy), QPointF(plot_rect.right(), gy))

        # Draw operator points and connecting line
        n_ops = len(ops)
        slot_w = plot_rect.width() / max(1, n_ops)
        pts = []
        for i, op in enumerate(ops):
            x = plot_rect.left() + i * slot_w + slot_w / 2
            y = plot_rect.bottom() - ((op_means[op] - min_m) / (max_m - min_m)) * plot_rect.height()
            pts.append(QPointF(x, y))

            # Op label
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QPen(QColor("#374151"), 1))
            painter.drawText(QRectF(plot_rect.left() + i * slot_w, plot_rect.bottom() + 4, slot_w, 20), Qt.AlignmentFlag.AlignCenter, str(op))

        painter.setPen(QPen(QColor("#2563EB"), 2))
        for i in range(len(pts) - 1):
            painter.drawLine(pts[i], pts[i + 1])

        painter.setBrush(QBrush(QColor("#2563EB")))
        for pt in pts:
            painter.drawEllipse(pt, 4, 4)

    def _draw_summary_panel(self, painter: QPainter, rect: QRectF):
        painter.setPen(QPen(QColor("#D1D5DB"), 1))
        painter.drawRect(rect)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#1F2937"), 1))
        painter.drawText(QRectF(rect.left(), rect.top() + 5, rect.width(), 20), Qt.AlignmentFlag.AlignCenter, "Study Variation & NDC")

        comps = self.result.get("variance_components", [])
        grr = next((c for c in comps if c.get("key") == "total_grr"), {})
        ndc = self.result.get("ndc", "*")

        lines = [
            f"Study Multiplier: {self.result.get('study_multiplier', 6.0):.1f} * SD",
            f"Total Operators: {self.result.get('operators_count')}",
            f"Parts per Operator: {self.result.get('parts_per_operator')}",
            f"Replicates: {self.result.get('replicates_per_part')}",
            "",
            f"Gage R&R %Contribution: {grr.get('percent_contribution', 0.0):.2f}%",
            f"Gage R&R %Study Var: {grr.get('percent_study_variation', 0.0):.2f}%",
            f"Distinct Categories (NDC): {ndc}",
        ]

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QPen(QColor("#374151"), 1))
        sy = rect.top() + 35
        for l in lines:
            if l:
                painter.drawText(QRectF(rect.left() + 20, sy, rect.width() - 40, 18), Qt.AlignmentFlag.AlignLeft, l)
            sy += 18


class GageLinearityChartWidget(SnapshotChartWidget):
    """Linearity and Bias Plot with Regression Line and 95% Confidence Bands."""

    def __init__(self, result: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(result, parent)
        self.result = result.get("result", result)
        self.setMinimumSize(650, 420)
        self.setWindowTitle("Gage Linearity and Bias Report")

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        w = self.width()
        h = self.height()

        # Title
        painter.setPen(QPen(QColor("#1F2937"), 1))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(0, 5, w, 25), Qt.AlignmentFlag.AlignCenter, "Gage Linearity and Bias Plot")

        plot_data = self.result.get("plot_data", {})
        refs = plot_data.get("refs", [])
        biases = plot_data.get("biases", [])
        if not refs:
            return

        margin_left = 60
        margin_right = 160
        margin_top = 40
        margin_bottom = 50

        pw = w - margin_left - margin_right
        ph = h - margin_top - margin_bottom
        plot_rect = QRectF(margin_left, margin_top, pw, ph)

        # Bounds
        min_x = min(refs)
        max_x = max(refs)
        span_x = max(1e-6, max_x - min_x)
        min_x -= 0.05 * span_x
        max_x += 0.05 * span_x

        all_y = list(biases) + plot_data.get("plot_lci", []) + plot_data.get("plot_uci", []) + [0.0]
        min_y = min(all_y)
        max_y = max(all_y)
        span_y = max(1e-6, max_y - min_y)
        min_y -= 0.1 * span_y
        max_y += 0.1 * span_y

        # Draw Axes & Grid
        painter.setPen(QPen(QColor("#E5E7EB"), 1, Qt.PenStyle.DashLine))
        for gy_val in np.linspace(min_y, max_y, 6):
            gy = plot_rect.bottom() - ((gy_val - min_y) / (max_y - min_y)) * ph
            painter.drawLine(QPointF(plot_rect.left(), gy), QPointF(plot_rect.right(), gy))
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QPen(QColor("#6B7280"), 1))
            painter.drawText(QRectF(0, gy - 8, margin_left - 5, 16), Qt.AlignmentFlag.AlignRight, f"{gy_val:.2f}")

        # Zero Bias Line
        zero_y = plot_rect.bottom() - ((0.0 - min_y) / (max_y - min_y)) * ph
        painter.setPen(QPen(QColor("#9CA3AF"), 1.5, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(plot_rect.left(), zero_y), QPointF(plot_rect.right(), zero_y))

        # Axis box
        painter.setPen(QPen(QColor("#9CA3AF"), 1))
        painter.drawRect(plot_rect)

        # Axis labels
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#374151"), 1))
        painter.drawText(QRectF(plot_rect.left(), plot_rect.bottom() + 15, pw, 20), Qt.AlignmentFlag.AlignCenter, "Reference Values")

        # Confidence Band Fill
        px = plot_data.get("plot_x", [])
        lci = plot_data.get("plot_lci", [])
        uci = plot_data.get("plot_uci", [])
        pfit = plot_data.get("plot_fit", [])

        if px and lci and uci:
            band_path = QPainterPath()
            p0_x = plot_rect.left() + ((px[0] - min_x) / (max_x - min_x)) * pw
            p0_y = plot_rect.bottom() - ((uci[0] - min_y) / (max_y - min_y)) * ph
            band_path.moveTo(p0_x, p0_y)
            for x_val, u_val in zip(px[1:], uci[1:]):
                bx = plot_rect.left() + ((x_val - min_x) / (max_x - min_x)) * pw
                by = plot_rect.bottom() - ((u_val - min_y) / (max_y - min_y)) * ph
                band_path.lineTo(bx, by)
            for x_val, l_val in zip(reversed(px), reversed(lci)):
                bx = plot_rect.left() + ((x_val - min_x) / (max_x - min_x)) * pw
                by = plot_rect.bottom() - ((l_val - min_y) / (max_y - min_y)) * ph
                band_path.lineTo(bx, by)
            band_path.closeSubpath()
            painter.fillPath(band_path, QColor(37, 99, 235, 30))

            # Fitted Line
            painter.setPen(QPen(QColor("#2563EB"), 2))
            for i in range(len(px) - 1):
                x1 = plot_rect.left() + ((px[i] - min_x) / (max_x - min_x)) * pw
                y1 = plot_rect.bottom() - ((pfit[i] - min_y) / (max_y - min_y)) * ph
                x2 = plot_rect.left() + ((px[i + 1] - min_x) / (max_x - min_x)) * pw
                y2 = plot_rect.bottom() - ((pfit[i + 1] - min_y) / (max_y - min_y)) * ph
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # Data Scatter Points
        painter.setPen(QPen(QColor("#1D4ED8"), 1))
        painter.setBrush(QBrush(QColor("#60A5FA")))
        for r_val, b_val in zip(refs, biases):
            cx = plot_rect.left() + ((r_val - min_x) / (max_x - min_x)) * pw
            cy = plot_rect.bottom() - ((b_val - min_y) / (max_y - min_y)) * ph
            painter.drawEllipse(QPointF(cx, cy), 3.5, 3.5)

        # Right Summary Panel
        panel_rect = QRectF(w - margin_right + 10, margin_top, margin_right - 20, ph)
        painter.fillRect(panel_rect, QColor("#F9FAFB"))
        painter.setPen(QPen(QColor("#E5E7EB"), 1))
        painter.drawRect(panel_rect)

        reg = self.result.get("regression", {})
        ob = self.result.get("overall_bias", {})

        stats_lines = [
            "Linearity:",
            f"  {self.result.get('linearity', 0.0):.4f}",
            "%Linearity:",
            f"  {self.result.get('pct_linearity', 0.0):.2f}%",
            "",
            "Overall Bias:",
            f"  {ob.get('average_bias', 0.0):.4f}",
            "%Bias:",
            f"  {ob.get('pct_bias', 0.0):.2f}%",
            "  P = " + ("*" if ob.get("p_value") is None else format(ob["p_value"], ".4f")),
            "",
            f"S = {reg.get('s', 0.0):.4f}",
            f"R-Sq = {reg.get('r_squared', 0.0) * 100:.1f}%",
        ]

        painter.setFont(QFont("Segoe UI", 7))
        painter.setPen(QPen(QColor("#374151"), 1))
        sy = panel_rect.top() + 10
        for sl in stats_lines:
            painter.drawText(QRectF(panel_rect.left() + 6, sy, panel_rect.width() - 12, 14), Qt.AlignmentFlag.AlignLeft, sl)
            sy += 14


class AttributeAgreementChartWidget(SnapshotChartWidget):
    """Comparative Bar Chart with 95% Confidence Bars for Attribute Agreement Analysis."""

    def __init__(self, result: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(result, parent)
        self.result = result.get("result", result)
        self.setMinimumSize(600, 380)
        self.setWindowTitle("Attribute Agreement Analysis Report")

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        w = self.width()
        h = self.height()

        # Title
        painter.setPen(QPen(QColor("#1F2937"), 1))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(0, 5, w, 25), Qt.AlignmentFlag.AlignCenter, "Attribute Agreement Analysis: % Agreement with 95% CI")

        within = self.result.get("within_appraiser", [])
        if not within:
            return

        has_std = self.result.get("has_standard") and self.result.get("appraiser_vs_standard")
        std_rows = {r["appraiser"]: r for r in self.result.get("appraiser_vs_standard", [])}

        margin_left = 60
        margin_right = 30
        margin_top = 40
        margin_bottom = 60

        pw = w - margin_left - margin_right
        ph = h - margin_top - margin_bottom
        plot_rect = QRectF(margin_left, margin_top, pw, ph)

        # Grid lines 0 to 100%
        painter.setPen(QPen(QColor("#E5E7EB"), 1, Qt.PenStyle.DashLine))
        for pct in (0, 20, 40, 60, 80, 100):
            gy = plot_rect.bottom() - (pct / 100.0) * ph
            painter.drawLine(QPointF(plot_rect.left(), gy), QPointF(plot_rect.right(), gy))
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QPen(QColor("#6B7280"), 1))
            painter.drawText(QRectF(0, gy - 8, margin_left - 5, 16), Qt.AlignmentFlag.AlignRight, f"{pct}%")

        painter.setPen(QPen(QColor("#9CA3AF"), 1))
        painter.drawRect(plot_rect)

        n_app = len(within)
        slot_w = pw / n_app
        bar_w = slot_w * 0.3 if has_std else slot_w * 0.45

        for i, row in enumerate(within):
            app = row["appraiser"]
            slot_left = plot_rect.left() + i * slot_w

            # Bar 1: Within Appraiser (Blue)
            bx1 = slot_left + slot_w * 0.15
            p1 = row.get("percent", 0.0)
            if p1 is None:
                painter.drawText(QRectF(bx1, plot_rect.center().y(), bar_w + 35, 35), Qt.AlignmentFlag.AlignCenter, '*')
            else:
                bh1 = (p1 / 100.0) * ph
                painter.fillRect(QRectF(bx1, plot_rect.bottom() - bh1, bar_w, bh1), QColor("#3B82F6"))

                # Error bar for Bar 1
                ci_l1 = row.get("ci_lower", 0.0)
                ci_u1 = row.get("ci_upper", 100.0)
                ey_l1 = plot_rect.bottom() - (ci_l1 / 100.0) * ph
                ey_u1 = plot_rect.bottom() - (ci_u1 / 100.0) * ph
                ecx1 = bx1 + bar_w / 2
                painter.setPen(QPen(QColor("#1E3A8A"), 1.5))
                painter.drawLine(QPointF(ecx1, ey_l1), QPointF(ecx1, ey_u1))
                painter.drawLine(QPointF(ecx1 - 4, ey_l1), QPointF(ecx1 + 4, ey_l1))
                painter.drawLine(QPointF(ecx1 - 4, ey_u1), QPointF(ecx1 + 4, ey_u1))

            # Bar 2: Appraiser vs Standard (Green, if available)
            if has_std and app in std_rows:
                srow = std_rows[app]
                bx2 = bx1 + bar_w + 5
                p2 = srow.get("percent", 0.0)
                if p2 is None:
                    painter.drawText(QRectF(bx2, plot_rect.center().y(), bar_w + 35, 35), Qt.AlignmentFlag.AlignCenter, '*')
                else:
                    bh2 = (p2 / 100.0) * ph
                    painter.fillRect(QRectF(bx2, plot_rect.bottom() - bh2, bar_w, bh2), QColor("#10B981"))

                    ci_l2 = srow.get("ci_lower", 0.0)
                    ci_u2 = srow.get("ci_upper", 100.0)
                    ey_l2 = plot_rect.bottom() - (ci_l2 / 100.0) * ph
                    ey_u2 = plot_rect.bottom() - (ci_u2 / 100.0) * ph
                    ecx2 = bx2 + bar_w / 2
                    painter.setPen(QPen(QColor("#065F46"), 1.5))
                    painter.drawLine(QPointF(ecx2, ey_l2), QPointF(ecx2, ey_u2))
                    painter.drawLine(QPointF(ecx2 - 4, ey_l2), QPointF(ecx2 + 4, ey_l2))
                    painter.drawLine(QPointF(ecx2 - 4, ey_u2), QPointF(ecx2 + 4, ey_u2))

            # Label Appraiser
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#374151"), 1))
            painter.drawText(QRectF(slot_left, plot_rect.bottom() + 4, slot_w, 20), Qt.AlignmentFlag.AlignCenter, str(app))

        # Legend at top right
        painter.setFont(QFont("Segoe UI", 7))
        lx = plot_rect.right() - 170
        ly = plot_rect.top() + 10
        painter.fillRect(QRectF(lx, ly, 12, 12), QColor("#3B82F6"))
        painter.setPen(QPen(QColor("#374151"), 1))
        painter.drawText(QRectF(lx + 16, ly - 2, 140, 16), Qt.AlignmentFlag.AlignLeft, "Within Appraiser")

        if has_std:
            painter.fillRect(QRectF(lx, ly + 16, 12, 12), QColor("#10B981"))
            painter.setPen(QPen(QColor("#374151"), 1))
            painter.drawText(QRectF(lx + 16, ly + 14, 140, 16), Qt.AlignmentFlag.AlignLeft, "Appraiser vs Standard")
