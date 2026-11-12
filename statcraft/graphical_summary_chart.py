"""Graphical Summary 4-in-1 Report Chart Widget."""
from __future__ import annotations

import math
from PySide6.QtCore import Qt, QRectF, QPointF, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPainterPath
from PySide6.QtWidgets import QWidget, QSizePolicy
from .snapshot_chart import SnapshotChartWidget
from .graph_interaction import GraphInteractionMixin
from .chart_theme import chart_painter


def _fmt(val, dec=4):
    if val is None:
        return "*"
    return f"{val:.{dec}f}" if isinstance(val, (int, float)) else str(val)


class GraphicalSummaryChartWidget(GraphInteractionMixin, QWidget):
    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get('result', {})
        self.title = entry.get('title', 'Summary Report')
        self.setMinimumSize(680, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hit_regions = []

    def sizeHint(self):
        return QSize(820, 560)

    def paintEvent(self, event):
        p = chart_painter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('#ffffff'))

        w = self.width()
        h = self.height()
        margin = 20.0

        # Title
        p.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
        p.setPen(QColor('#0f172a'))
        p.drawText(QRectF(margin, 12, w - 2 * margin, 26), Qt.AlignmentFlag.AlignCenter, self.title)

        # Layout: Left side 65% for 4 visual panels; Right side 35% for stats table
        left_w = (w - 2 * margin) * 0.64
        right_w = (w - 2 * margin) * 0.34
        top_y = 45.0
        plot_h = h - top_y - margin

        left_rect = QRectF(margin, top_y, left_w, plot_h)
        right_rect = QRectF(margin + left_w + (w - 2 * margin) * 0.02, top_y, right_w, plot_h)

        self._draw_stats_panel(p, right_rect)
        self._draw_visual_panels(p, left_rect)
        p.end()

    def _draw_stats_panel(self, p: QPainter, rect: QRectF):
        # Background card
        p.setPen(QPen(QColor('#cbd5e1'), 0.9))
        p.setBrush(QColor('#f8fafc'))
        p.drawRoundedRect(rect, 6.0, 6.0)

        p.setFont(QFont('Segoe UI', 8))
        cx = rect.left() + 10.0
        rx = rect.right() - 10.0
        cw = rect.width() - 20.0
        y = rect.top() + 12.0
        line_h = 16.0

        def section_hdr(title):
            nonlocal y
            p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
            p.setPen(QColor('#0369a1'))
            p.drawText(QRectF(cx, y, cw, line_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
            y += line_h + 2.0

        def row(lbl, val_str):
            nonlocal y
            p.setFont(QFont('Segoe UI', 8))
            p.setPen(QColor('#475569'))
            p.drawText(QRectF(cx, y, cw * 0.6, line_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lbl)
            p.setPen(QColor('#0f172a'))
            p.drawText(QRectF(cx + cw * 0.5, y, cw * 0.5, line_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, val_str)
            y += line_h

        # Anderson-Darling
        section_hdr("Anderson-Darling Normality Test")
        ad_stat = self.result.get('ad_stat')
        ad_p = self.result.get('ad_p')
        row("A-Squared", _fmt(ad_stat, 2))
        p_str = _fmt(ad_p, 3) if ad_p is not None else "< 0.005"
        row("P-Value", p_str)
        y += 6.0

        # Descriptive Statistics
        section_hdr("Descriptive Statistics")
        row("Mean", _fmt(self.result.get('mean'), 4))
        row("StDev", _fmt(self.result.get('stdev'), 4))
        row("Variance", _fmt(self.result.get('variance'), 4))
        row("Skewness", _fmt(self.result.get('skewness'), 4))
        row("Kurtosis", _fmt(self.result.get('kurtosis'), 4))
        row("N", str(self.result.get('n', 0)))
        y += 6.0

        # Five-Number Summary
        section_hdr("Five-Number Summary")
        row("Minimum", _fmt(self.result.get('min'), 4))
        row("1st Quartile", _fmt(self.result.get('q1'), 4))
        row("Median", _fmt(self.result.get('median'), 4))
        row("3rd Quartile", _fmt(self.result.get('q3'), 4))
        row("Maximum", _fmt(self.result.get('max'), 4))
        y += 6.0

        # Confidence Intervals
        conf_pct = int(round(self.result.get('confidence', 0.95) * 100))
        section_hdr(f"{conf_pct}% Confidence Intervals")
        ci_mean = self.result.get('ci_mean', (0.0, 0.0))
        ci_med = self.result.get('ci_median', (0.0, 0.0))
        ci_sd = self.result.get('ci_stdev', (0.0, 0.0))
        row("Mean", f"({_fmt(ci_mean[0], 3)}, {_fmt(ci_mean[1], 3)})")
        row("Median", f"({_fmt(ci_med[0], 3)}, {_fmt(ci_med[1], 3)})")
        row("StDev", f"({_fmt(ci_sd[0], 3)}, {_fmt(ci_sd[1], 3)})")

    def _draw_visual_panels(self, p: QPainter, rect: QRectF):
        # Divide into:
        # 1. Histogram (60% height)
        # 2. Boxplot (14% height)
        # 3. CI for Mean (13% height)
        # 4. CI for Median (13% height)
        h_total = rect.height()
        hist_h = h_total * 0.58
        box_h = h_total * 0.14
        ci1_h = h_total * 0.14
        ci2_h = h_total * 0.14

        hist_rect = QRectF(rect.left(), rect.top(), rect.width(), hist_h)
        box_rect = QRectF(rect.left(), hist_rect.bottom(), rect.width(), box_h)
        ci1_rect = QRectF(rect.left(), box_rect.bottom(), rect.width(), ci1_h)
        ci2_rect = QRectF(rect.left(), ci1_rect.bottom(), rect.width(), ci2_h)

        # Common X scale
        min_v = self.result.get('min', 0.0)
        max_v = self.result.get('max', 1.0)
        span = max_v - min_v
        if span <= 0:
            span = 1.0
        x_pad = span * 0.08
        x_min = min_v - x_pad
        x_max = max_v + x_pad

        def to_x(val):
            return hist_rect.left() + 40.0 + ((val - x_min) / (x_max - x_min)) * (hist_rect.width() - 55.0)

        # 1. Histogram with Normal Curve
        hist_data = self.result.get('histogram', {})
        counts = hist_data.get('counts', [])
        bins = hist_data.get('bins', [])
        max_count = max(counts) if counts else 1

        plot_b = hist_rect.bottom() - 25.0
        plot_t = hist_rect.top() + 10.0
        plot_h = plot_b - plot_t

        # Y Axis for counts
        p.setPen(QPen(QColor('#94a3b8'), 0.8))
        p.drawLine(hist_rect.left() + 35.0, plot_b, hist_rect.left() + 35.0, plot_t)
        p.setFont(QFont('Segoe UI', 7))
        p.setPen(QColor('#64748b'))
        p.drawText(QRectF(hist_rect.left(), plot_b - 8, 30, 16), Qt.AlignmentFlag.AlignRight, "0")
        p.drawText(QRectF(hist_rect.left(), plot_t - 8, 30, 16), Qt.AlignmentFlag.AlignRight, str(max_count))

        # Histogram bars
        p.setPen(QPen(QColor('#0284c7'), 0.8))
        p.setBrush(QColor('#bae6fd'))
        for i, c in enumerate(counts):
            if i < len(bins) - 1:
                bx0 = to_x(bins[i])
                bx1 = to_x(bins[i + 1])
                bw = max(1.0, bx1 - bx0)
                bh = (c / max_count) * plot_h
                bar_r = QRectF(bx0, plot_b - bh, bw, bh)
                p.drawRect(bar_r)

        # Super-imposed fitted Normal Curve
        mean_v = self.result.get('mean', 0.0)
        sd_v = self.result.get('stdev', 1.0)
        n_v = self.result.get('n', 1)
        bin_w = hist_data.get('bin_width', 1.0)
        if sd_v > 0:
            curve_path = QPainterPath()
            steps = 80
            for s in range(steps + 1):
                xv = x_min + (s / steps) * (x_max - x_min)
                # Normal pdf * n * bin_width to scale to frequency
                pdf = (1.0 / (sd_v * math.sqrt(2.0 * math.pi))) * math.exp(-0.5 * ((xv - mean_v) / sd_v) ** 2)
                freq_equiv = pdf * n_v * bin_w
                y_norm = plot_b - (freq_equiv / max_count) * plot_h
                x_norm = to_x(xv)
                if s == 0:
                    curve_path.moveTo(x_norm, y_norm)
                else:
                    curve_path.lineTo(x_norm, y_norm)
            p.setPen(QPen(QColor('#dc2626'), 1.3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(curve_path)

        # 2. Boxplot
        p.setPen(QPen(QColor('#94a3b8'), 0.7, Qt.PenStyle.DashLine))
        p.drawLine(rect.left() + 35.0, box_rect.top(), rect.right() - 15.0, box_rect.top())

        bp = self.result.get('boxplot', {})
        mid_y = box_rect.center().y()
        q1_x = to_x(bp.get('q1', min_v))
        med_x = to_x(bp.get('median', min_v))
        q3_x = to_x(bp.get('q3', max_v))
        w_low_x = to_x(bp.get('whisker_low', min_v))
        w_high_x = to_x(bp.get('whisker_high', max_v))

        # Whiskers
        p.setPen(QPen(QColor('#475569'), 1.0))
        p.drawLine(w_low_x, mid_y, q1_x, mid_y)
        p.drawLine(q3_x, mid_y, w_high_x, mid_y)
        p.drawLine(w_low_x, mid_y - 4, w_low_x, mid_y + 4)
        p.drawLine(w_high_x, mid_y - 4, w_high_x, mid_y + 4)

        # Box
        box_h_inner = 14.0
        p.setPen(QPen(QColor('#0f172a'), 1.1))
        p.setBrush(QColor('#e2e8f0'))
        p.drawRect(QRectF(q1_x, mid_y - box_h_inner / 2.0, max(1.0, q3_x - q1_x), box_h_inner))

        # Median line
        p.setPen(QPen(QColor('#dc2626'), 1.8))
        p.drawLine(med_x, mid_y - box_h_inner / 2.0, med_x, mid_y + box_h_inner / 2.0)

        # Outliers (*)
        p.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
        p.setPen(QColor('#dc2626'))
        for out in bp.get('outliers', []):
            ox = to_x(out)
            p.drawText(QRectF(ox - 5, mid_y - 8, 10, 16), Qt.AlignmentFlag.AlignCenter, "*")

        # 3. 95% CI for Mean
        p.setPen(QPen(QColor('#e2e8f0'), 0.8))
        p.drawLine(rect.left() + 35.0, ci1_rect.top(), rect.right() - 15.0, ci1_rect.top())

        ci_m = self.result.get('ci_mean', (min_v, max_v))
        ci1_y = ci1_rect.center().y()
        c1_low = to_x(ci_m[0])
        c1_high = to_x(ci_m[1])
        c1_pt = to_x(mean_v)

        p.setFont(QFont('Segoe UI', 7, QFont.Weight.DemiBold))
        p.setPen(QColor('#475569'))
        p.drawText(QRectF(rect.left(), ci1_y - 7, 35, 14), Qt.AlignmentFlag.AlignRight, "Mean")

        p.setPen(QPen(QColor('#2563eb'), 1.6))
        p.drawLine(c1_low, ci1_y, c1_high, ci1_y)
        p.drawLine(c1_low, ci1_y - 3, c1_low, ci1_y + 3)
        p.drawLine(c1_high, ci1_y - 3, c1_high, ci1_y + 3)
        p.setBrush(QColor('#2563eb'))
        p.drawEllipse(QPointF(c1_pt, ci1_y), 3.0, 3.0)

        # 4. 95% CI for Median
        p.setPen(QPen(QColor('#e2e8f0'), 0.8))
        p.drawLine(rect.left() + 35.0, ci2_rect.top(), rect.right() - 15.0, ci2_rect.top())

        ci_med = self.result.get('ci_median', (min_v, max_v))
        ci2_y = ci2_rect.center().y() - 6.0
        c2_low = to_x(ci_med[0])
        c2_high = to_x(ci_med[1])
        c2_pt = to_x(self.result.get('median', min_v))

        p.setFont(QFont('Segoe UI', 7, QFont.Weight.DemiBold))
        p.setPen(QColor('#475569'))
        p.drawText(QRectF(rect.left(), ci2_y - 7, 35, 14), Qt.AlignmentFlag.AlignRight, "Median")

        p.setPen(QPen(QColor('#0284c7'), 1.6))
        p.drawLine(c2_low, ci2_y, c2_high, ci2_y)
        p.drawLine(c2_low, ci2_y - 3, c2_low, ci2_y + 3)
        p.drawLine(c2_high, ci2_y - 3, c2_high, ci2_y + 3)
        p.setBrush(QColor('#0284c7'))
        p.drawEllipse(QPointF(c2_pt, ci2_y), 3.0, 3.0)

        # Bottom shared X Axis ticks
        ax_y = ci2_rect.bottom() - 10.0
        p.setPen(QPen(QColor('#94a3b8'), 0.8))
        p.drawLine(to_x(x_min), ax_y, to_x(x_max), ax_y)
        p.setFont(QFont('Segoe UI', 7))
        p.setPen(QColor('#64748b'))
        for val in [min_v, self.result.get('q1', 0), self.result.get('median', 0), self.result.get('q3', 0), max_v]:
            vx = to_x(val)
            p.drawLine(vx, ax_y, vx, ax_y + 3)
            p.drawText(QRectF(vx - 25, ax_y + 4, 50, 14), Qt.AlignmentFlag.AlignCenter, _fmt(val, 2))
