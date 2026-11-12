"""Interactive Qt Chart Widget for Nonnormal Capability Analysis matching StatCraft."""

from __future__ import annotations

from .snapshot_chart import SnapshotChartWidget

import math
from typing import Any, Dict, List, Optional
import numpy as np
from scipy import stats

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath
from PySide6.QtWidgets import QWidget
from .chart_theme import chart_painter


def fitted_density(result, x_values):
    """Fitted raw-space density, including the Box-Cox transformation Jacobian.

    A nonzero-lambda transformed normal can put mass beyond the transform range.
    This curve follows the engine's CDF without silently renormalizing that fit.
    """
    xs = np.asarray(x_values, dtype=float)
    method = result.get('method')
    fit = result.get('fit_info', {})
    params = fit.get('parameters', {})
    if method == 'box_cox':
        lam, mu, sigma = fit.get('lambda'), fit.get('mean_trans'), fit.get('std_trans')
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in (lam, mu, sigma)) or sigma <= 0:
            raise ValueError('Box-Cox density requires finite fitted lambda, mean and positive standard deviation.')
        result_density = np.zeros_like(xs)
        positive = (xs > 0) & np.isfinite(xs)
        logs = np.log(xs[positive])
        with np.errstate(over='ignore', under='ignore', invalid='ignore', divide='ignore'):
            if abs(lam) < 1e-6:
                transformed = logs
                log_jacobian = -logs
            else:
                transformed = np.expm1(lam * logs) / lam
                log_jacobian = (lam - 1) * logs
            density = np.exp(stats.norm.logpdf(transformed, loc=mu, scale=sigma) + log_jacobian)
        result_density[positive] = np.where(np.isfinite(density), density, 0.)
        return result_density
    if method == 'weibull' and 'shape' in params:
        return stats.weibull_min.pdf(xs, params['shape'], scale=params['scale'])
    if method == 'lognormal' and 'scale_sigma' in params:
        return stats.lognorm.pdf(xs, params['scale_sigma'], scale=math.exp(params['location_mu']))
    if method == 'exponential' and 'scale_mean' in params:
        return stats.expon.pdf(xs, scale=params['scale_mean'])
    if method == 'gamma' and 'shape' in params:
        return stats.gamma.pdf(xs, params['shape'], scale=params['scale'])
    if method == 'normal' and 'mean' in params and 'stdev' in params:
        return stats.norm.pdf(xs, loc=params['mean'], scale=params['stdev'])
    raise ValueError('A density overlay is unavailable for the saved fitted distribution.')


class NonnormalCapabilityPlotWidget(SnapshotChartWidget):
    """Custom high-fidelity capability plot widget with nonnormal density overlay and spec limits."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(entry, parent)
        self.entry = entry
        self.result = entry.get("result", entry)
        self.setMinimumSize(700, 500)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Fill background
        painter.fillRect(0, 0, w, h, QColor("#FFFFFF"))

        # Titles
        var_name = self.entry.get("variable_name", self.entry.get("title", "Measurement"))
        method_name = self.result.get("method", "weibull")
        method = method_name.capitalize()
        subtitle = f"Distribution: {method}"
        if method_name == 'box_cox':
            lam = self.result.get('fit_info', {}).get('lambda')
            subtitle = f"Box-Cox transformation (lambda = {lam:g})" if isinstance(lam, (int, float)) else 'Box-Cox transformation' 
        painter.setPen(QColor("#1A202C"))
        title_font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(QRectF(20, 15, w - 40, 25), Qt.AlignmentFlag.AlignCenter, f"Process Capability Report for {var_name}")

        subtitle_font = QFont("Segoe UI", 9)
        painter.setFont(subtitle_font)
        painter.setPen(QColor("#718096"))
        painter.drawText(QRectF(20, 38, w - 40, 20), Qt.AlignmentFlag.AlignCenter, subtitle)

        # Data observations
        obs = np.array(self.result.get("observations", []), dtype=float)
        if len(obs) == 0:
            return

        lsl = self.result.get("lsl")
        usl = self.result.get("usl")
        target = self.result.get("target")

        # Layout areas:
        # Left side: Histogram & Density curve (70% width)
        # Right side: Capability Statistics Box (30% width)
        stat_box_w = min(220, int(w * 0.32))
        plot_rect = QRectF(50, 70, w - stat_box_w - 70, h - 120)
        stat_rect = QRectF(w - stat_box_w - 15, 70, stat_box_w, h - 120)

        # Draw plot border & grid
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.drawRect(plot_rect)

        # Plot X range
        min_x = float(np.min(obs))
        max_x = float(np.max(obs))
        if lsl is not None:
            min_x = min(min_x, lsl)
        if usl is not None:
            max_x = max(max_x, usl)
        
        span_x = max_x - min_x
        x_lo = min_x - 0.1 * span_x
        x_hi = max_x + 0.1 * span_x
        span_x_full = x_hi - x_lo

        # 1. Draw Histogram
        counts, bin_edges = np.histogram(obs, bins=15, density=True)
        max_density = float(np.max(counts)) if len(counts) > 0 else 1.0

        def to_screen_x(vx: float) -> float:
            return plot_rect.left() + (vx - x_lo) / span_x_full * plot_rect.width()

        def to_screen_y(vy: float) -> float:
            # 1.25 ceiling for aesthetic headspace
            return plot_rect.bottom() - (vy / (max_density * 1.25)) * plot_rect.height()

        painter.setPen(QPen(QColor("#94A3B8"), 1))
        painter.setBrush(QBrush(QColor("#E2E8F0")))
        for i in range(len(counts)):
            bx0 = to_screen_x(bin_edges[i])
            bx1 = to_screen_x(bin_edges[i+1])
            by = to_screen_y(counts[i])
            painter.drawRect(QRectF(bx0, by, bx1 - bx0, plot_rect.bottom() - by))

        # 2. Draw Nonnormal Density Fit Curve
        fit_info = self.result.get("fit_info", {})
        method_name = self.result.get("method", "weibull")
        curve_pts = []
        xs = np.linspace(x_lo, x_hi, 200)

        try:
            ys = fitted_density(self.result, xs)
        except (ValueError, KeyError, TypeError, OverflowError):
            ys = np.full_like(xs, np.nan)

        curve_path = QPainterPath()
        first = True
        for x_val, y_val in zip(xs, ys):
            if not math.isfinite(x_val) or not math.isfinite(y_val):
                first = True
                continue
            sx = to_screen_x(x_val)
            sy = to_screen_y(y_val)
            if first:
                curve_path.moveTo(sx, sy)
                first = False
            else:
                curve_path.lineTo(sx, sy)

        painter.setPen(QPen(QColor("#2563EB"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.save()
        painter.setClipRect(plot_rect)
        painter.drawPath(curve_path)
        painter.restore()

        # 3. Draw Spec Limits (LSL / USL)
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        if lsl is not None:
            lx = to_screen_x(lsl)
            painter.setPen(QPen(QColor("#DC2626"), 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(lx, plot_rect.top()), QPointF(lx, plot_rect.bottom()))
            painter.setPen(QColor("#DC2626"))
            painter.drawText(QPointF(lx - 25, plot_rect.top() - 6), f"LSL: {lsl:.2f}")

        if usl is not None:
            ux = to_screen_x(usl)
            painter.setPen(QPen(QColor("#DC2626"), 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(ux, plot_rect.top()), QPointF(ux, plot_rect.bottom()))
            painter.setPen(QColor("#DC2626"))
            painter.drawText(QPointF(ux - 15, plot_rect.top() - 6), f"USL: {usl:.2f}")

        # 4. Draw Statistics Side Panel
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.setBrush(QBrush(QColor("#F8FAFC")))
        painter.drawRoundedRect(stat_rect, 4, 4)

        # Text in stat box
        idx = self.result.get("indices", {})
        is_vda = (self.result.get("naming_convention") == "aiag_vda")
        
        stat_y = stat_rect.top() + 20
        line_h = 17
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#1E293B"))
        painter.drawText(stat_rect.left() + 10, stat_y, "Process Data:")
        stat_y += line_h

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#475569"))
        painter.drawText(stat_rect.left() + 15, stat_y, f"Sample N: {len(obs)}")
        stat_y += line_h
        painter.drawText(stat_rect.left() + 15, stat_y, f"Median: {float(np.median(obs)):.3f}")
        stat_y += line_h + 8

        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#1E293B"))
        painter.drawText(stat_rect.left() + 10, stat_y, "Overall Capability:")
        stat_y += line_h

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#475569"))
        p_name = "Cnp" if is_vda else "Pp"
        pk_name = "Cnpk" if is_vda else "Ppk"
        pl_name = "Cnpl" if is_vda else "PPL"
        pu_name = "Cnpu" if is_vda else "PPU"

        pp_val = idx.get("cnp" if is_vda else "pp")
        ppk_val = idx.get("cnpk" if is_vda else "ppk")
        ppl_val = idx.get("cnpl" if is_vda else "ppl")
        ppu_val = idx.get("cnpu" if is_vda else "ppu")

        if pp_val is not None:
            painter.drawText(stat_rect.left() + 15, stat_y, f"{p_name}: {pp_val:.2f}")
            stat_y += line_h
        if ppk_val is not None:
            painter.drawText(stat_rect.left() + 15, stat_y, f"{pk_name}: {ppk_val:.2f}")
            stat_y += line_h
        if ppl_val is not None:
            painter.drawText(stat_rect.left() + 15, stat_y, f"{pl_name}: {ppl_val:.2f}")
            stat_y += line_h
        if ppu_val is not None:
            painter.drawText(stat_rect.left() + 15, stat_y, f"{pu_name}: {ppu_val:.2f}")
            stat_y += line_h

        stat_y += 8
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#1E293B"))
        painter.drawText(stat_rect.left() + 10, stat_y, "Expected PPM:")
        stat_y += line_h

        exp_ppm = self.result.get("expected_ppm", {})
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#475569"))
        painter.drawText(stat_rect.left() + 15, stat_y, f"Total: {exp_ppm.get('total', 0.0):.1f}")
        stat_y += line_h
        if lsl is not None:
            painter.drawText(stat_rect.left() + 15, stat_y, f"< LSL: {exp_ppm.get('below', 0.0):.1f}")
            stat_y += line_h
        if usl is not None:
            painter.drawText(stat_rect.left() + 15, stat_y, f"> USL: {exp_ppm.get('above', 0.0):.1f}")
            stat_y += line_h
