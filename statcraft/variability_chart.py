"""High-resolution vector chart for JMP-style Variability / Gauge Chart platform.

Renders:
- Hierarchical multi-tier nested categorical X-axis (e.g. Part within Operator).
- Upper canvas: individual observation points, connected cell means, grand mean line, spec limits.
- Lower canvas: subgroup standard deviation (S) chart with pooled repeatability line.
- JMP-style red disclosure headers, interactive hover tooltips, and collapsible Variance Components.
- 100% native DirectWrite/GDI typography with zero tofu glyphs.
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
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from .chart_theme import chart_painter


class VariabilityCanvas(QWidget):
    """Vector canvas rendering the dual Variability and Subgroup S charts."""

    def __init__(self, data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data = data
        self.setMinimumSize(640, 500)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._hover_text: Optional[str] = None
        self._hover_pos: Optional[QPointF] = None

    def paintEvent(self, event) -> None:
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = self.width()
        h = self.height()

        # Canvas background
        painter.fillRect(0, 0, w, h, QBrush(QColor("#ffffff")))

        cells = self.data.get("cell_summaries", [])
        if not cells:
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No variability data available.")
            return

        factor_names = self.data.get("factor_names", [])
        grand_mean = self.data.get("grand_mean", 0.0)
        std_repeat = self.data.get("std_repeatability", 0.0)
        specs = self.data.get("specs", {})
        lsl = specs.get("lsl")
        usl = specs.get("usl")

        # Dimensions & margins
        left_m = 75
        right_m = 35
        top_m = 35
        bottom_tier_height = 22 * len(factor_names)
        bottom_m = max(55, bottom_tier_height + 25)

        available_h = h - top_m - bottom_m
        # Split vertical space: Upper variability plot (65%), Lower S-plot (35%)
        gap = 30
        upper_h = int((available_h - gap) * 0.65)
        lower_h = available_h - gap - upper_h
        plot_w = w - left_m - right_m

        upper_top = top_m
        upper_bottom = upper_top + upper_h
        lower_top = upper_bottom + gap
        lower_bottom = lower_top + lower_h

        # Compute Y-ranges for upper plot (observations)
        all_y = [v for c in cells for v in c["values"]]
        if lsl is not None:
            all_y.append(lsl)
        if usl is not None:
            all_y.append(usl)

        min_y = min(all_y)
        max_y = max(all_y)
        y_span = max(1e-6, max_y - min_y)
        y_pad = y_span * 0.12
        y_axis_min = min_y - y_pad
        y_axis_max = max_y + y_pad
        y_axis_range = y_axis_max - y_axis_min

        # Compute Y-ranges for lower plot (Subgroup S)
        all_s = [c["std"] for c in cells]
        max_s = max(all_s) if all_s else 1.0
        s_axis_max = max(1e-6, max_s * 1.25)
        s_axis_min = 0.0
        s_axis_range = s_axis_max - s_axis_min

        # Background grid fills
        painter.fillRect(QRectF(left_m, upper_top, plot_w, upper_h), QBrush(QColor("#f8fafc")))
        painter.fillRect(QRectF(left_m, lower_top, plot_w, lower_h), QBrush(QColor("#f8fafc")))

        # Draw grid borders
        border_pen = QPen(QColor("#cbd5e1"), 1)
        painter.setPen(border_pen)
        painter.drawRect(QRectF(left_m, upper_top, plot_w, upper_h))
        painter.drawRect(QRectF(left_m, lower_top, plot_w, lower_h))

        # Title for Upper Plot
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor("#334155"))
        painter.drawText(QRectF(left_m, upper_top - 24, plot_w, 20), Qt.AlignmentFlag.AlignLeft, "Variability Chart for Response")

        # Title for Lower Plot
        painter.drawText(QRectF(left_m, lower_top - 22, plot_w, 20), Qt.AlignmentFlag.AlignLeft, "Standard Deviation Chart (Within Subgroups)")

        # Y-ticks Upper Plot
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#64748b"))
        n_ticks = 5
        grid_pen = QPen(QColor("#e2e8f0"), 1, Qt.PenStyle.DashLine)
        for t in range(n_ticks + 1):
            t_val = y_axis_min + (y_axis_range * t / n_ticks)
            t_y = upper_bottom - ((t_val - y_axis_min) / y_axis_range) * upper_h
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(left_m, t_y), QPointF(left_m + plot_w, t_y))
            painter.setPen(QColor("#64748b"))
            painter.drawText(QRectF(left_m - 68, t_y - 8, 60, 16), Qt.AlignmentFlag.AlignRight, f"{t_val:.2f}")

        # Y-ticks Lower Plot (S)
        for t in range(4):
            t_val = s_axis_min + (s_axis_range * t / 3)
            t_y = lower_bottom - ((t_val - s_axis_min) / s_axis_range) * lower_h
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(left_m, t_y), QPointF(left_m + plot_w, t_y))
            painter.setPen(QColor("#64748b"))
            painter.drawText(QRectF(left_m - 68, t_y - 8, 60, 16), Qt.AlignmentFlag.AlignRight, f"{t_val:.2f}")

        # Draw Grand Mean dashed line (Upper)
        g_y = upper_bottom - ((grand_mean - y_axis_min) / y_axis_range) * upper_h
        g_pen = QPen(QColor("#6366f1"), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(g_pen)
        painter.drawLine(QPointF(left_m, g_y), QPointF(left_m + plot_w, g_y))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#4f46e5"))
        painter.drawText(QRectF(left_m + plot_w - 95, g_y - 16, 90, 14), Qt.AlignmentFlag.AlignRight, f"Mean: {grand_mean:.2f}")

        # Draw Pooled S line (Lower)
        if std_repeat > 0:
            s_y = lower_bottom - ((std_repeat - s_axis_min) / s_axis_range) * lower_h
            s_pen = QPen(QColor("#6366f1"), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(s_pen)
            painter.drawLine(QPointF(left_m, s_y), QPointF(left_m + plot_w, s_y))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#4f46e5"))
            painter.drawText(QRectF(left_m + plot_w - 95, s_y - 16, 90, 14), Qt.AlignmentFlag.AlignRight, f"S-bar: {std_repeat:.2f}")

        # Draw Spec Limits if provided
        if lsl is not None:
            l_y = upper_bottom - ((lsl - y_axis_min) / y_axis_range) * upper_h
            painter.setPen(QPen(QColor("#ef4444"), 1, Qt.PenStyle.DashDotLine))
            painter.drawLine(QPointF(left_m, l_y), QPointF(left_m + plot_w, l_y))
            painter.setPen(QColor("#ef4444"))
            painter.drawText(QRectF(left_m + 6, l_y - 14, 80, 14), Qt.AlignmentFlag.AlignLeft, f"LSL: {lsl:.2f}")

        if usl is not None:
            u_y = upper_bottom - ((usl - y_axis_min) / y_axis_range) * upper_h
            painter.setPen(QPen(QColor("#ef4444"), 1, Qt.PenStyle.DashDotLine))
            painter.drawLine(QPointF(left_m, u_y), QPointF(left_m + plot_w, u_y))
            painter.setPen(QColor("#ef4444"))
            painter.drawText(QRectF(left_m + 6, u_y - 14, 80, 14), Qt.AlignmentFlag.AlignLeft, f"USL: {usl:.2f}")

        # Calculate cell X positions
        num_cells = len(cells)
        col_w = plot_w / num_cells
        cell_centers: List[float] = []

        for c_idx in range(num_cells):
            cx = left_m + (c_idx + 0.5) * col_w
            cell_centers.append(cx)

        # Draw Cell Mean connector lines
        mean_points_upper: List[QPointF] = []
        std_points_lower: List[QPointF] = []

        for c_idx, cell in enumerate(cells):
            cx = cell_centers[c_idx]
            cy_mean = upper_bottom - ((cell["mean"] - y_axis_min) / y_axis_range) * upper_h
            mean_points_upper.append(QPointF(cx, cy_mean))

            cy_std = lower_bottom - ((cell["std"] - s_axis_min) / s_axis_range) * lower_h
            std_points_lower.append(QPointF(cx, cy_std))

        # Polyline connecting means
        painter.setPen(QPen(QColor("#0284c7"), 2))
        for i in range(len(mean_points_upper) - 1):
            painter.drawLine(mean_points_upper[i], mean_points_upper[i + 1])

        # Polyline connecting standard deviations
        painter.setPen(QPen(QColor("#059669"), 1.8))
        for i in range(len(std_points_lower) - 1):
            painter.drawLine(std_points_lower[i], std_points_lower[i + 1])

        # Draw individual data points and mean diamonds/markers
        for c_idx, cell in enumerate(cells):
            cx = cell_centers[c_idx]

            # Range bars (Min to Max)
            cy_min = upper_bottom - ((cell["min"] - y_axis_min) / y_axis_range) * upper_h
            cy_max = upper_bottom - ((cell["max"] - y_axis_min) / y_axis_range) * upper_h
            painter.setPen(QPen(QColor("#94a3b8"), 1))
            painter.drawLine(QPointF(cx, cy_min), QPointF(cx, cy_max))
            # Caps on min/max
            painter.drawLine(QPointF(cx - 3, cy_min), QPointF(cx + 3, cy_min))
            painter.drawLine(QPointF(cx - 3, cy_max), QPointF(cx + 3, cy_max))

            # Individual data points (dots with slight horizontal jitter if overlapping)
            val_counts: Dict[float, int] = {}
            for v in cell["values"]:
                val_counts[v] = val_counts.get(v, 0) + 1
            drawn_counts: Dict[float, int] = {}

            for v in cell["values"]:
                cnt = drawn_counts.get(v, 0)
                drawn_counts[v] = cnt + 1
                total_cnt = val_counts[v]
                jitter = (cnt - (total_cnt - 1) / 2.0) * 5.0 if total_cnt > 1 else 0.0

                py = upper_bottom - ((v - y_axis_min) / y_axis_range) * upper_h
                painter.setBrush(QBrush(QColor("#38bdf8")))
                painter.setPen(QPen(QColor("#0369a1"), 1))
                painter.drawEllipse(QPointF(cx + jitter, py), 3.5, 3.5)

            # Mean marker (Diamond)
            mean_pt = mean_points_upper[c_idx]
            d_path = QPainterPath()
            d_path.moveTo(mean_pt.x(), mean_pt.y() - 5.5)
            d_path.lineTo(mean_pt.x() + 5.5, mean_pt.y())
            d_path.lineTo(mean_pt.x(), mean_pt.y() + 5.5)
            d_path.lineTo(mean_pt.x() - 5.5, mean_pt.y())
            d_path.closeSubpath()
            painter.setBrush(QBrush(QColor("#0284c7")))
            painter.setPen(QPen(QColor("#0369a1"), 1.5))
            painter.drawPath(d_path)

            # Std Dev marker (Lower plot)
            std_pt = std_points_lower[c_idx]
            painter.setBrush(QBrush(QColor("#10b981")))
            painter.setPen(QPen(QColor("#047857"), 1.5))
            painter.drawRect(QRectF(std_pt.x() - 3.5, std_pt.y() - 3.5, 7, 7))

        # Draw Multi-Tier Hierarchical Categorical Axis Labels
        painter.setFont(QFont("Segoe UI", 8))
        num_factors = len(factor_names)

        for f_idx in range(num_factors):
            tier_y = lower_bottom + 12 + (f_idx * 20)
            fname = factor_names[num_factors - 1 - f_idx]  # Innermost first

            # Axis Factor Name Label on the left
            painter.setPen(QColor("#475569"))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(10, tier_y - 2, left_m - 15, 18), Qt.AlignmentFlag.AlignRight, fname)
            painter.setFont(QFont("Segoe UI", 8))

            # Group contiguous spans for this factor
            spans: List[Tuple[str, int, int]] = []
            curr_val = None
            span_start = 0

            for c_idx, cell in enumerate(cells):
                val = cell["labels"].get(fname, "")
                if val != curr_val:
                    if curr_val is not None:
                        spans.append((curr_val, span_start, c_idx - 1))
                    curr_val = val
                    span_start = c_idx
            if curr_val is not None:
                spans.append((curr_val, span_start, len(cells) - 1))

            for val, start_i, end_i in spans:
                x1 = left_m + start_i * col_w
                x2 = left_m + (end_i + 1) * col_w
                painter.setPen(QColor("#334155"))
                painter.drawText(QRectF(x1, tier_y - 2, x2 - x1, 18), Qt.AlignmentFlag.AlignCenter, str(val))

                # Vertical separator line between groups
                if start_i > 0:
                    sep_pen = QPen(QColor("#cbd5e1"), 1 if f_idx == 0 else 1.5)
                    painter.setPen(sep_pen)
                    painter.drawLine(QPointF(x1, upper_top), QPointF(x1, lower_bottom + bottom_tier_height))


class VariabilityPlatformWidget(QWidget):
    """Full JMP-style Variability / Gauge Chart platform with side report cards."""

    def __init__(self, analysis_result: Dict[str, Any], title: str = "Variability / Gauge Analysis", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.result = analysis_result
        self.setWindowTitle(title)
        self.resize(1140, 680)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # JMP Disclosure Header
        hdr = QFrame()
        hdr.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 12px;")
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(4, 4, 4, 4)

        icon_lbl = QLabel("▼")
        icon_lbl.setStyleSheet("color: #dc2626; font-size: 13px; font-weight: bold;")
        title_lbl = QLabel(f"Variability Gauge Analysis — {title}")
        title_lbl.setStyleSheet("font-size: 13.5px; font-weight: bold; color: #0f172a;")
        hdr_layout.addWidget(icon_lbl)
        hdr_layout.addWidget(title_lbl)
        hdr_layout.addStretch()

        grr = self.result.get("gauge_rr")
        if grr:
            badge_text = grr.get("aiag_badge", "Gage R&R")
            badge_color = "#10b981" if badge_text == "Excellent" else ("#f59e0b" if badge_text == "Marginal" else "#ef4444")
            badge = QLabel(f"AIAG: {badge_text} ({grr.get('pct_study_grr', 0):.1f}%)")
            badge.setFixedHeight(24)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(f"background: {badge_color}; color: #ffffff; font-weight: bold; font-size: 11px; padding: 2px 10px; border-radius: 12px;")
            hdr_layout.addWidget(badge)

        main_layout.addWidget(hdr)

        # Splitter: Canvas on Left, Reporting Tables on Right
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: #e2e8f0; width: 3px; }")

        # Left: Interactive Canvas
        self.canvas = VariabilityCanvas(self.result, self)
        splitter.addWidget(self.canvas)

        # Right: Report Tables inside ScrollArea
        report_scroll = QScrollArea()
        report_scroll.setWidgetResizable(True)
        report_scroll.setStyleSheet("QScrollArea { border: 1px solid #e2e8f0; border-radius: 6px; background: #ffffff; }")

        report_widget = QWidget()
        report_widget.setStyleSheet("background: #ffffff;")
        report_layout = QVBoxLayout(report_widget)
        report_layout.setContentsMargins(12, 12, 12, 12)
        report_layout.setSpacing(12)

        table_qss = (
            "QTableWidget { background: #ffffff; color: #1e293b; gridline-color: #f1f5f9; font-size: 11px; border: 1px solid #e2e8f0; border-radius: 4px; }"
            "QHeaderView::section { background: #f8fafc; color: #334155; font-weight: bold; border: none; border-bottom: 1px solid #e2e8f0; padding: 4px; }"
        )

        def make_section_hdr(text: str) -> QWidget:
            box = QWidget()
            h_lay = QHBoxLayout(box)
            h_lay.setContentsMargins(0, 0, 0, 0)
            h_lay.setSpacing(6)
            tri = QLabel("▼")
            tri.setStyleSheet("color: #dc2626; font-size: 11px; font-weight: bold;")
            lbl = QLabel(text)
            lbl.setStyleSheet("font-weight: bold; font-size: 12px; color: #0f172a;")
            h_lay.addWidget(tri)
            h_lay.addWidget(lbl)
            h_lay.addStretch()
            return box

        # 1. Variance Components Table
        if grr:
            report_layout.addWidget(make_section_hdr("Variance Components (ANOVA Method)"))

            v_table = QTableWidget()
            v_table.verticalHeader().setVisible(False)
            v_table.setColumnCount(4)
            v_table.setHorizontalHeaderLabels(["Component", "Var Comp", "% Contrib", "StdDev (σ)"])
            v_table.horizontalHeader().setStretchLastSection(True)
            v_table.setStyleSheet(table_qss)

            comp_rows = [
                ("Total Gage R&R", grr["var_grr"], grr["pct_contrib_grr"], grr["std_grr"]),
                ("  Repeatability", grr["var_repeatability"], grr["pct_contrib_repeat"], grr["std_repeatability"]),
                ("  Reproducibility", grr["var_reproducibility"], grr["pct_contrib_repro"], grr["std_reproducibility"]),
                ("Part-to-Part", grr["var_part_to_part"], grr["pct_contrib_part"], grr["std_part_to_part"]),
                ("Total Variation", grr["var_total"], 100.0, grr["std_total"]),
            ]
            v_table.setRowCount(len(comp_rows))
            for r_idx, (cname, vc, pc, sd) in enumerate(comp_rows):
                v_table.setItem(r_idx, 0, QTableWidgetItem(cname))
                v_table.setItem(r_idx, 1, QTableWidgetItem(f"{vc:.4f}"))
                v_table.setItem(r_idx, 2, QTableWidgetItem(f"{pc:.2f}%"))
                v_table.setItem(r_idx, 3, QTableWidgetItem(f"{sd:.4f}"))
                if "Total" in cname:
                    for col in range(4):
                        font = v_table.item(r_idx, col).font()
                        font.setBold(True)
                        v_table.item(r_idx, col).setFont(font)
            v_table.setFixedHeight(150)
            report_layout.addWidget(v_table)

            # 2. Gage Evaluation / AIAG Table
            report_layout.addWidget(make_section_hdr("Gage Evaluation (% Study Variation)"))

            g_table = QTableWidget()
            g_table.verticalHeader().setVisible(False)
            g_table.setColumnCount(4)
            g_table.setHorizontalHeaderLabels(["Source", "Study Var (6σ)", "% Study Var", "% Tolerance"])
            g_table.horizontalHeader().setStretchLastSection(True)
            g_table.setStyleSheet(table_qss)

            eval_rows = [
                ("Total Gage R&R", grr["study_var_grr"], grr["pct_study_grr"], grr.get("pct_tol_grr")),
                ("  Repeatability", grr["study_var_repeat"], grr["pct_study_repeat"], grr.get("pct_tol_repeat")),
                ("  Reproducibility", grr["study_var_repro"], grr["pct_study_repro"], grr.get("pct_tol_repro")),
                ("Part-to-Part", grr["study_var_part"], grr["pct_study_part"], grr.get("pct_tol_part")),
            ]
            g_table.setRowCount(len(eval_rows))
            for r_idx, (sname, sv, psv, ptol) in enumerate(eval_rows):
                g_table.setItem(r_idx, 0, QTableWidgetItem(sname))
                g_table.setItem(r_idx, 1, QTableWidgetItem(f"{sv:.4f}"))
                g_table.setItem(r_idx, 2, QTableWidgetItem(f"{psv:.2f}%"))
                g_table.setItem(r_idx, 3, QTableWidgetItem(f"{ptol:.2f}%" if ptol is not None else "—"))
                if "Total" in sname:
                    for col in range(4):
                        font = g_table.item(r_idx, col).font()
                        font.setBold(True)
                        g_table.item(r_idx, col).setFont(font)
            g_table.setFixedHeight(125)
            report_layout.addWidget(g_table)

            # 3. Discrimination / Summary Card
            card = QFrame()
            card.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px;")
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)
            card_layout.setContentsMargins(8, 8, 8, 8)

            ndc_lbl = QLabel(f"Number of Distinct Categories (ndc): <b>{grr['ndc']}</b>")
            ndc_lbl.setStyleSheet("font-size: 11px; color: #1e293b;")
            status_lbl = QLabel(f"AIAG Evaluation: <i>{grr['aiag_status']}</i>")
            status_lbl.setStyleSheet("font-size: 11px; color: #475569;")
            card_layout.addWidget(ndc_lbl)
            card_layout.addWidget(status_lbl)
            report_layout.addWidget(card)

        # 4. Overall Cell Means Summary
        report_layout.addWidget(make_section_hdr("Group Means and Dispersion Summary"))

        c_table = QTableWidget()
        c_table.verticalHeader().setVisible(False)
        headers = list(self.result.get("factor_names", [])) + ["N", "Mean", "StdDev", "Range"]
        c_table.setColumnCount(len(headers))
        c_table.setHorizontalHeaderLabels(headers)
        c_table.horizontalHeader().setStretchLastSection(True)
        c_table.setStyleSheet(table_qss)

        cells = self.result.get("cell_summaries", [])
        c_table.setRowCount(len(cells))
        for r_idx, cell in enumerate(cells):
            fnames = self.result.get("factor_names", [])
            for c_col, fn in enumerate(fnames):
                c_table.setItem(r_idx, c_col, QTableWidgetItem(str(cell["labels"].get(fn, ""))))
            base_col = len(fnames)
            c_table.setItem(r_idx, base_col, QTableWidgetItem(str(cell["count"])))
            c_table.setItem(r_idx, base_col + 1, QTableWidgetItem(f"{cell['mean']:.3f}"))
            c_table.setItem(r_idx, base_col + 2, QTableWidgetItem(f"{cell['std']:.3f}"))
            c_table.setItem(r_idx, base_col + 3, QTableWidgetItem(f"{cell['range']:.3f}"))
        c_table.setFixedHeight(180)
        report_layout.addWidget(c_table)

        report_layout.addStretch()
        report_scroll.setWidget(report_widget)
        splitter.addWidget(report_scroll)
        splitter.setSizes([650, 450])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)
