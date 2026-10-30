"""Qt 6-Panel Process Capability Sixpack Chart Widget.

Provides full 6-panel StatCraft Process Capability Sixpack visual parity:
- Top-Left: Xbar Chart (or I Chart)
- Bottom-Left: R Chart (or S Chart, MR Chart)
- Top-Middle: Last 25 Subgroups Plot
- Bottom-Middle: Capability Histogram with Within & Overall normal curves
- Top-Right: Capability Plot / Capability Metrics summary
- Bottom-Right: Normal Probability Plot with Anderson-Darling test
"""

from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy import stats

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath
from PySide6.QtWidgets import QWidget


class CapabilitySixpackWidget(QWidget):
    """StatCraft Process Capability Sixpack 6-Panel Widget."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.entry = entry
        self.error = None
        self.panels = []
        self.setMinimumSize(950, 650)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        
        rect = self.rect()
        painter.fillRect(rect, QColor("#FFFFFF"))

        res = self.entry.get("result", {})
        if not res or res.get("analysis") != "capability_sixpack_normal":
            return

        col_name = res.get("column_name", "Data")
        title = f"Process Capability Sixpack of {col_name}"

        w = rect.width()
        h = rect.height()

        # Main Header Title
        painter.setPen(QColor("#0F172A"))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(15, 6, w - 30, 24), Qt.AlignmentFlag.AlignCenter, title)

        # 2 rows x 3 columns layout
        margin_left = 12
        margin_right = 12
        margin_top = 34
        margin_bottom = 12
        gap_x = 10
        gap_y = 10

        avail_w = w - margin_left - margin_right - 2 * gap_x
        avail_h = h - margin_top - margin_bottom - gap_y

        cell_w = avail_w / 3.0
        cell_h = avail_h / 2.0

        p_xbar = res.get("panel_xbar", {})
        p_disp = res.get("panel_disp", {})
        p_last = res.get("panel_last25", {})
        p_hist = res.get("panel_hist", {})
        p_norm = res.get("panel_norm", {})
        p_sum = res.get("panel_summary", {})

        # Col 0: (0,0) Xbar, (1,0) Dispersion
        rect_xbar = QRectF(margin_left, margin_top, cell_w, cell_h)
        rect_disp = QRectF(margin_left, margin_top + cell_h + gap_y, cell_w, cell_h)

        # Col 1: (0,1) Last 25 Subgroups, (1,1) Capability Histogram
        rect_last = QRectF(margin_left + cell_w + gap_x, margin_top, cell_w, cell_h)
        rect_hist = QRectF(margin_left + cell_w + gap_x, margin_top + cell_h + gap_y, cell_w, cell_h)

        # Col 2: (0,2) Capability Plot, (1,2) Normal Probability Plot
        rect_sum = QRectF(margin_left + 2 * (cell_w + gap_x), margin_top, cell_w, cell_h)
        rect_norm = QRectF(margin_left + 2 * (cell_w + gap_x), margin_top + cell_h + gap_y, cell_w, cell_h)

        self._draw_panel_box(painter, rect_xbar, p_xbar.get("title", "Xbar Chart"))
        self._draw_control_chart(painter, rect_xbar, p_xbar)

        self._draw_panel_box(painter, rect_disp, p_disp.get("title", "R Chart"))
        self._draw_control_chart(painter, rect_disp, p_disp)

        self._draw_panel_box(painter, rect_last, p_last.get("title", "Last 25 Subgroups"))
        self._draw_last25_chart(painter, rect_last, p_last)

        self._draw_panel_box(painter, rect_hist, p_hist.get("title", "Capability Histogram"))
        self._draw_histogram_chart(painter, rect_hist, p_hist)

        self._draw_panel_box(painter, rect_sum, p_sum.get("title", "Capability Plot"))
        self._draw_summary_panel(painter, rect_sum, p_sum, res)

        self._draw_panel_box(painter, rect_norm, p_norm.get("title", "Normal Probability Plot"))
        self._draw_norm_plot(painter, rect_norm, p_norm)

    def _draw_panel_box(self, painter: QPainter, rect: QRectF, title: str):
        painter.save()
        painter.setPen(QPen(QColor("#CBD5E1"), 1.0))
        painter.setBrush(QColor("#F8FAFC"))
        painter.drawRoundedRect(rect, 4.0, 4.0)

        # Header title
        painter.setPen(QColor("#1E293B"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(QRectF(rect.left(), rect.top() + 3, rect.width(), 16), Qt.AlignmentFlag.AlignCenter, title)
        painter.restore()

    def _draw_control_chart(self, painter: QPainter, rect: QRectF, data: Dict[str, Any]):
        x_vals = data.get("x", [])
        y_vals = data.get("y", [])
        if not x_vals or not y_vals:
            return

        clean_y = [v for v in y_vals if v is not None]
        if not clean_y:
            return

        ucl_val = data.get("ucl_val")
        lcl_val = data.get("lcl_val")
        center_val = data.get("center", 0.0)

        all_y = clean_y[:]
        if ucl_val is not None: all_y.append(ucl_val)
        if lcl_val is not None: all_y.append(lcl_val)
        if center_val is not None: all_y.append(center_val)

        min_y, max_y = min(all_y), max(all_y)
        pad_y = max(1e-5, (max_y - min_y) * 0.15)
        min_y -= pad_y
        max_y += pad_y

        min_x, max_x = min(x_vals), max(x_vals)
        if min_x == max_x:
            min_x -= 1; max_x += 1

        plot_rect = QRectF(rect.left() + 32, rect.top() + 20, rect.width() - 85, rect.height() - 36)

        def to_screen(x, y):
            sx = plot_rect.left() + (x - min_x) / (max_x - min_x) * plot_rect.width()
            sy = plot_rect.bottom() - (y - min_y) / (max_y - min_y) * plot_rect.height()
            return QPointF(sx, sy)

        painter.save()
        painter.fillRect(plot_rect, QColor("#FFFFFF"))
        painter.setPen(QPen(QColor("#E2E8F0"), 1.0))
        painter.drawRect(plot_rect)

        # Draw Center Line
        if center_val is not None and min_y <= center_val <= max_y:
            p1 = to_screen(min_x, center_val)
            p2 = to_screen(max_x, center_val)
            painter.setPen(QPen(QColor("#16A34A"), 1.2, Qt.PenStyle.SolidLine))
            painter.drawLine(p1, p2)
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor("#16A34A"))
            painter.drawText(QRectF(plot_rect.right() + 3, p2.y() - 7, 50, 14), Qt.AlignmentFlag.AlignLeft, f"_X={center_val:.2f}")

        # Draw UCL
        if ucl_val is not None and min_y <= ucl_val <= max_y:
            p1 = to_screen(min_x, ucl_val)
            p2 = to_screen(max_x, ucl_val)
            painter.setPen(QPen(QColor("#DC2626"), 1.2, Qt.PenStyle.DashLine))
            painter.drawLine(p1, p2)
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor("#DC2626"))
            painter.drawText(QRectF(plot_rect.right() + 3, p2.y() - 7, 50, 14), Qt.AlignmentFlag.AlignLeft, f"UCL={ucl_val:.2f}")

        # Draw LCL
        if lcl_val is not None and min_y <= lcl_val <= max_y:
            p1 = to_screen(min_x, lcl_val)
            p2 = to_screen(max_x, lcl_val)
            painter.setPen(QPen(QColor("#DC2626"), 1.2, Qt.PenStyle.DashLine))
            painter.drawLine(p1, p2)
            painter.setFont(QFont("Segoe UI", 7))
            painter.setPen(QColor("#DC2626"))
            painter.drawText(QRectF(plot_rect.right() + 3, p2.y() - 7, 50, 14), Qt.AlignmentFlag.AlignLeft, f"LCL={lcl_val:.2f}")

        # Draw Connected Points
        test1_fails = set(data.get("test1_failures", []))
        pts = []
        for x, y in zip(x_vals, y_vals):
            if y is not None:
                pts.append((x, to_screen(x, y)))

        painter.setPen(QPen(QColor("#1D4ED8"), 1.2))
        for i in range(len(pts) - 1):
            painter.drawLine(pts[i][1], pts[i + 1][1])

        for x_idx, pt in pts:
            if x_idx in test1_fails:
                painter.setPen(QPen(QColor("#DC2626"), 1.0))
                painter.setBrush(QColor("#DC2626"))
                painter.drawRect(QRectF(pt.x() - 2.5, pt.y() - 2.5, 5, 5))
                painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
                painter.drawText(QRectF(pt.x() - 8, pt.y() - 11, 16, 10), Qt.AlignmentFlag.AlignCenter, "1")
            else:
                painter.setPen(QPen(QColor("#1D4ED8"), 1.0))
                painter.setBrush(QColor("#1D4ED8"))
                painter.drawEllipse(pt, 2.0, 2.0)

        # Axis ticks
        painter.setFont(QFont("Segoe UI", 6))
        painter.setPen(QColor("#64748B"))
        painter.drawText(QRectF(plot_rect.left() - 30, plot_rect.top() - 5, 26, 12), Qt.AlignmentFlag.AlignRight, f"{max_y:.2f}")
        painter.drawText(QRectF(plot_rect.left() - 30, plot_rect.bottom() - 7, 26, 12), Qt.AlignmentFlag.AlignRight, f"{min_y:.2f}")
        painter.drawText(QRectF(plot_rect.left() - 10, plot_rect.bottom() + 2, 20, 10), Qt.AlignmentFlag.AlignCenter, f"{min_x}")
        painter.drawText(QRectF(plot_rect.right() - 10, plot_rect.bottom() + 2, 20, 10), Qt.AlignmentFlag.AlignCenter, f"{max_x}")

        painter.restore()

    def _draw_last25_chart(self, painter: QPainter, rect: QRectF, data: Dict[str, Any]):
        pts = data.get("points", [])
        means = data.get("means", [])
        if not pts:
            return

        all_y = [p[1] for p in pts]
        min_y, max_y = min(all_y), max(all_y)
        pad_y = max(1e-5, (max_y - min_y) * 0.15)
        min_y -= pad_y; max_y += pad_y

        sub_indices = data.get("subgroup_indices", [1])
        min_x, max_x = min(sub_indices), max(sub_indices)
        if min_x == max_x:
            min_x -= 1; max_x += 1

        plot_rect = QRectF(rect.left() + 32, rect.top() + 20, rect.width() - 48, rect.height() - 36)

        def to_screen(x, y):
            sx = plot_rect.left() + (x - min_x) / (max_x - min_x) * plot_rect.width()
            sy = plot_rect.bottom() - (y - min_y) / (max_y - min_y) * plot_rect.height()
            return QPointF(sx, sy)

        painter.save()
        painter.fillRect(plot_rect, QColor("#FFFFFF"))
        painter.setPen(QPen(QColor("#E2E8F0"), 1.0))
        painter.drawRect(plot_rect)

        # Process Mean Line
        proc_mean = data.get("process_mean")
        if proc_mean is not None and min_y <= proc_mean <= max_y:
            p1 = to_screen(min_x, proc_mean)
            p2 = to_screen(max_x, proc_mean)
            painter.setPen(QPen(QColor("#16A34A"), 1.2, Qt.PenStyle.SolidLine))
            painter.drawLine(p1, p2)

        # Means connecting line
        screen_means = [to_screen(m[0], m[1]) for m in means]
        painter.setPen(QPen(QColor("#0284C7"), 1.2))
        for i in range(len(screen_means) - 1):
            painter.drawLine(screen_means[i], screen_means[i + 1])

        # Individual observation points
        painter.setPen(QPen(QColor("#64748B"), 0.8))
        painter.setBrush(QColor("#94A3B8"))
        for sg_idx, v in pts:
            s_pt = to_screen(sg_idx, v)
            painter.drawEllipse(s_pt, 1.8, 1.8)

        # Subgroup mean squares
        painter.setPen(QPen(QColor("#0284C7"), 1.0))
        painter.setBrush(QColor("#0284C7"))
        for sm in screen_means:
            painter.drawRect(QRectF(sm.x() - 2.0, sm.y() - 2.0, 4.0, 4.0))

        # Y axis ticks
        painter.setFont(QFont("Segoe UI", 6))
        painter.setPen(QColor("#64748B"))
        painter.drawText(QRectF(plot_rect.left() - 30, plot_rect.top() - 5, 26, 12), Qt.AlignmentFlag.AlignRight, f"{max_y:.2f}")
        painter.drawText(QRectF(plot_rect.left() - 30, plot_rect.bottom() - 7, 26, 12), Qt.AlignmentFlag.AlignRight, f"{min_y:.2f}")
        painter.drawText(QRectF(plot_rect.left() - 10, plot_rect.bottom() + 2, 20, 10), Qt.AlignmentFlag.AlignCenter, f"{min_x}")
        painter.drawText(QRectF(plot_rect.right() - 10, plot_rect.bottom() + 2, 20, 10), Qt.AlignmentFlag.AlignCenter, f"{max_x}")

        painter.restore()

    def _draw_histogram_chart(self, painter: QPainter, rect: QRectF, data: Dict[str, Any]):
        obs = data.get("observations", [])
        if not obs:
            return

        plot_rect = QRectF(rect.left() + 32, rect.top() + 20, rect.width() - 48, rect.height() - 36)

        mean = data.get("mean", 0.0)
        sd_within = data.get("stdev_within", 1.0)
        sd_overall = data.get("stdev_overall", 1.0)
        lsl = data.get("lsl")
        usl = data.get("usl")
        target = data.get("target")

        data_min = min(obs)
        data_max = max(obs)
        x_min = min(data_min, lsl if lsl is not None else data_min, target if target is not None else data_min)
        x_max = max(data_max, usl if usl is not None else data_max, target if target is not None else data_max)

        span = x_max - x_min
        if span <= 0:
            span = 1.0
        x_min -= 0.10 * span
        x_max += 0.10 * span

        n_bins = max(5, int(math.ceil(math.log2(len(obs)) + 1)) + 2)
        counts, bin_edges = np.histogram(obs, bins=n_bins, range=(x_min, x_max))
        bin_width = bin_edges[1] - bin_edges[0]
        scale_factor = len(obs) * bin_width

        def curve_y_val(x, sd):
            if sd <= 0:
                return 0.0
            return scale_factor * stats.norm.pdf(x, mean, sd)

        max_hist = max(counts) if len(counts) > 0 else 1
        max_curve_within = curve_y_val(mean, sd_within)
        max_curve_overall = curve_y_val(mean, sd_overall)
        y_max = max(max_hist, max_curve_within, max_curve_overall) * 1.15

        def to_screen_x(xv):
            return plot_rect.left() + (xv - x_min) / (x_max - x_min) * plot_rect.width()

        def to_screen_y(yv):
            return plot_rect.bottom() - (yv / y_max) * plot_rect.height()

        painter.save()
        painter.fillRect(plot_rect, QColor("#FFFFFF"))
        painter.setPen(QPen(QColor("#E2E8F0"), 1.0))
        painter.drawRect(plot_rect)

        # Draw Bins
        painter.setPen(QPen(QColor("#60A5FA"), 0.8))
        painter.setBrush(QColor("#DBEAFE"))
        for i in range(len(counts)):
            bx1 = to_screen_x(bin_edges[i])
            bx2 = to_screen_x(bin_edges[i + 1])
            by = to_screen_y(counts[i])
            painter.drawRect(QRectF(bx1, by, max(1.0, bx2 - bx1), plot_rect.bottom() - by))

        # Fitted curves
        x_grid = np.linspace(x_min, x_max, 100)
        if sd_within > 0:
            path_w = QPainterPath()
            path_w.moveTo(to_screen_x(x_grid[0]), to_screen_y(curve_y_val(x_grid[0], sd_within)))
            for xv in x_grid[1:]:
                path_w.lineTo(to_screen_x(xv), to_screen_y(curve_y_val(xv, sd_within)))
            painter.setPen(QPen(QColor("#1E3A8A"), 1.5, Qt.PenStyle.SolidLine))
            painter.drawPath(path_w)

        if sd_overall > 0:
            path_o = QPainterPath()
            path_o.moveTo(to_screen_x(x_grid[0]), to_screen_y(curve_y_val(x_grid[0], sd_overall)))
            for xv in x_grid[1:]:
                path_o.lineTo(to_screen_x(xv), to_screen_y(curve_y_val(xv, sd_overall)))
            painter.setPen(QPen(QColor("#64748B"), 1.3, Qt.PenStyle.DashLine))
            painter.drawPath(path_o)

        # Spec lines
        painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
        if lsl is not None and x_min <= lsl <= x_max:
            sx = to_screen_x(lsl)
            painter.setPen(QPen(QColor("#DC2626"), 1.2, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(sx, plot_rect.top()), QPointF(sx, plot_rect.bottom()))
            painter.setPen(QColor("#DC2626"))
            painter.drawText(QRectF(sx - 15, plot_rect.top() - 11, 30, 10), Qt.AlignmentFlag.AlignCenter, "LSL")

        if usl is not None and x_min <= usl <= x_max:
            sx = to_screen_x(usl)
            painter.setPen(QPen(QColor("#DC2626"), 1.2, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(sx, plot_rect.top()), QPointF(sx, plot_rect.bottom()))
            painter.setPen(QColor("#DC2626"))
            painter.drawText(QRectF(sx - 15, plot_rect.top() - 11, 30, 10), Qt.AlignmentFlag.AlignCenter, "USL")

        painter.restore()

    def _draw_norm_plot(self, painter: QPainter, rect: QRectF, data: Dict[str, Any]):
        obs = data.get("observed", [])
        norm_scores = data.get("normal_scores", [])
        if not obs or not norm_scores:
            return

        mean = data.get("mean", 0.0)
        stdev = data.get("stdev", 1.0)
        if stdev <= 0: stdev = 1.0

        min_x, max_x = min(obs), max(obs)
        pad_x = (max_x - min_x) * 0.1 if max_x > min_x else 1.0
        min_x -= pad_x; max_x += pad_x

        min_y, max_y = -3.0, 3.0  # Normal score range approx -3 to +3 (0.1% to 99.9%)

        plot_rect = QRectF(rect.left() + 32, rect.top() + 20, rect.width() - 48, rect.height() - 36)

        def to_screen(x, y):
            sx = plot_rect.left() + (x - min_x) / (max_x - min_x) * plot_rect.width()
            sy = plot_rect.bottom() - (y - min_y) / (max_y - min_y) * plot_rect.height()
            return QPointF(sx, sy)

        painter.save()
        painter.fillRect(plot_rect, QColor("#FFFFFF"))
        painter.setPen(QPen(QColor("#E2E8F0"), 1.0))
        painter.drawRect(plot_rect)

        # Draw Probability Reference Grid
        pct_ticks = [(1, stats.norm.ppf(0.01)), (10, stats.norm.ppf(0.10)), (50, 0.0), (90, stats.norm.ppf(0.90)), (99, stats.norm.ppf(0.99))]
        painter.setFont(QFont("Segoe UI", 6))
        for pct, score in pct_ticks:
            py = to_screen(min_x, score).y()
            painter.setPen(QPen(QColor("#F1F5F9"), 1.0))
            painter.drawLine(QPointF(plot_rect.left(), py), QPointF(plot_rect.right(), py))
            painter.setPen(QColor("#64748B"))
            painter.drawText(QRectF(plot_rect.left() - 25, py - 5, 22, 10), Qt.AlignmentFlag.AlignRight, f"{pct}%")

        # Fitted Normal Line: y = (x - mean) / stdev
        p1 = to_screen(min_x, (min_x - mean) / stdev)
        p2 = to_screen(max_x, (max_x - mean) / stdev)
        painter.setPen(QPen(QColor("#DC2626"), 1.2))
        painter.drawLine(p1, p2)

        # Observations
        painter.setPen(QPen(QColor("#1E40AF"), 1.0))
        painter.setBrush(QColor("#3B82F6"))
        for x_val, score_val in zip(obs, norm_scores):
            pt = to_screen(x_val, score_val)
            painter.drawEllipse(pt, 1.8, 1.8)

        # AD and P-value box
        ad_stat = data.get("ad_stat")
        p_val = data.get("p_value")
        ad_str = f"{ad_stat:.3f}" if ad_stat is not None else "*"
        p_str = f"{p_val:.3f}" if p_val is not None else ("< 0.005" if ad_stat and ad_stat > 1.5 else "> 0.100")

        box_w = 68; box_h = 24
        box_r = QRectF(plot_rect.right() - box_w - 4, plot_rect.bottom() - box_h - 4, box_w, box_h)
        painter.setBrush(QColor("#FFFFFF"))
        painter.setPen(QPen(QColor("#CBD5E1"), 0.8))
        painter.drawRect(box_r)
        painter.setFont(QFont("Segoe UI", 6))
        painter.setPen(QColor("#0F172A"))
        painter.drawText(QRectF(box_r.left() + 2, box_r.top() + 2, box_w - 4, 10), Qt.AlignmentFlag.AlignLeft, f"AD: {ad_str}")
        painter.drawText(QRectF(box_r.left() + 2, box_r.top() + 12, box_w - 4, 10), Qt.AlignmentFlag.AlignLeft, f"P:  {p_str}")

        painter.restore()

    def _draw_summary_panel(self, painter: QPainter, rect: QRectF, data: Dict[str, Any], res: Dict[str, Any]):
        painter.save()
        box_rect = QRectF(rect.left() + 6, rect.top() + 20, rect.width() - 12, rect.height() - 26)
        painter.fillRect(box_rect, QColor("#FFFFFF"))
        painter.setPen(QPen(QColor("#CBD5E1"), 1.0))
        painter.drawRect(box_rect)

        # Two columns: Potential Within vs Overall
        mid_x = box_rect.left() + box_rect.width() * 0.5
        painter.drawLine(QPointF(mid_x, box_rect.top()), QPointF(mid_x, box_rect.bottom()))

        # Column 1: Potential Within
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.setPen(QColor("#0F172A"))
        painter.drawText(QRectF(box_rect.left() + 6, box_rect.top() + 4, mid_x - box_rect.left() - 12, 14), Qt.AlignmentFlag.AlignLeft, "Within Capability")

        painter.setFont(QFont("Segoe UI", 7))
        y = box_rect.top() + 20
        line_h = 13
        stdev_w = data.get("stdev_within", 0.0)
        cp = data.get("cp")
        cpk = data.get("cpk")
        cpm = data.get("cpm")

        painter.drawText(QRectF(box_rect.left() + 6, y, 50, line_h), Qt.AlignmentFlag.AlignLeft, "StDev")
        painter.drawText(QRectF(box_rect.left() + 50, y, 45, line_h), Qt.AlignmentFlag.AlignRight, f"{stdev_w:.4g}")
        y += line_h
        if cp is not None:
            painter.drawText(QRectF(box_rect.left() + 6, y, 50, line_h), Qt.AlignmentFlag.AlignLeft, "Cp")
            painter.drawText(QRectF(box_rect.left() + 50, y, 45, line_h), Qt.AlignmentFlag.AlignRight, f"{cp:.2f}")
            y += line_h
        if cpk is not None:
            painter.drawText(QRectF(box_rect.left() + 6, y, 50, line_h), Qt.AlignmentFlag.AlignLeft, "Cpk")
            painter.drawText(QRectF(box_rect.left() + 50, y, 45, line_h), Qt.AlignmentFlag.AlignRight, f"{cpk:.2f}")
            y += line_h
        if cpm is not None:
            painter.drawText(QRectF(box_rect.left() + 6, y, 50, line_h), Qt.AlignmentFlag.AlignLeft, "Cpm")
            painter.drawText(QRectF(box_rect.left() + 50, y, 45, line_h), Qt.AlignmentFlag.AlignRight, f"{cpm:.2f}")
            y += line_h

        # Column 2: Overall Capability
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.drawText(QRectF(mid_x + 6, box_rect.top() + 4, box_rect.right() - mid_x - 12, 14), Qt.AlignmentFlag.AlignLeft, "Overall Capability")

        painter.setFont(QFont("Segoe UI", 7))
        y_o = box_rect.top() + 20
        stdev_o = data.get("stdev_overall", 0.0)
        pp = data.get("pp")
        ppk = data.get("ppk")

        painter.drawText(QRectF(mid_x + 6, y_o, 50, line_h), Qt.AlignmentFlag.AlignLeft, "StDev")
        painter.drawText(QRectF(mid_x + 50, y_o, 45, line_h), Qt.AlignmentFlag.AlignRight, f"{stdev_o:.4g}")
        y_o += line_h
        if pp is not None:
            painter.drawText(QRectF(mid_x + 6, y_o, 50, line_h), Qt.AlignmentFlag.AlignLeft, "Pp")
            painter.drawText(QRectF(mid_x + 50, y_o, 45, line_h), Qt.AlignmentFlag.AlignRight, f"{pp:.2f}")
            y_o += line_h
        if ppk is not None:
            painter.drawText(QRectF(mid_x + 6, y_o, 50, line_h), Qt.AlignmentFlag.AlignLeft, "Ppk")
            painter.drawText(QRectF(mid_x + 50, y_o, 45, line_h), Qt.AlignmentFlag.AlignRight, f"{ppk:.2f}")
            y_o += line_h

        # Horizontal partition for PPM Performance
        y_perf = box_rect.bottom() - 48
        painter.setPen(QPen(QColor("#E2E8F0"), 1.0))
        painter.drawLine(QPointF(box_rect.left(), y_perf), QPointF(box_rect.right(), y_perf))

        painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
        painter.setPen(QColor("#0F172A"))
        painter.drawText(QRectF(box_rect.left() + 6, y_perf + 2, box_rect.width() - 12, 12), Qt.AlignmentFlag.AlignLeft, "Defect Rate (PPM Total)")

        painter.setFont(QFont("Segoe UI", 6))
        painter.setPen(QColor("#334155"))
        y_perf += 14
        ppm_obs = data.get("ppm_observed", 0.0)
        ppm_w = data.get("ppm_exp_within", 0.0)
        ppm_o = data.get("ppm_exp_overall", 0.0)

        painter.drawText(QRectF(box_rect.left() + 6, y_perf, 70, 10), Qt.AlignmentFlag.AlignLeft, f"Observed:")
        painter.drawText(QRectF(box_rect.left() + 65, y_perf, 60, 10), Qt.AlignmentFlag.AlignRight, f"{ppm_obs:.1f}")

        y_perf += 11
        painter.drawText(QRectF(box_rect.left() + 6, y_perf, 70, 10), Qt.AlignmentFlag.AlignLeft, f"Exp. Within:")
        painter.drawText(QRectF(box_rect.left() + 65, y_perf, 60, 10), Qt.AlignmentFlag.AlignRight, f"{ppm_w:.1f}")

        painter.drawText(QRectF(mid_x + 6, y_perf, 70, 10), Qt.AlignmentFlag.AlignLeft, f"Exp. Overall:")
        painter.drawText(QRectF(mid_x + 65, y_perf, 60, 10), Qt.AlignmentFlag.AlignRight, f"{ppm_o:.1f}")

        painter.restore()
