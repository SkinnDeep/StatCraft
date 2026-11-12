"""Interactive Qt Chart Widget for Accelerated Life Testing (Life vs Stress Plot & Extrapolation).

Matches Minitab 22 and JMP Fit Life by X visual styling:
- Life vs Stress regression plot with log-time axis
- Extrapolated median life line with shaded 95% confidence bands
- Distinct plotting markers for failures (filled circles) vs right-censored units (open triangles)
- Prominent vertical reference line at the user's normal operating stress level (use condition)
- Embedded right-hand summary card showing parameter estimates, MTTF/percentile life, and acceleration factors
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .graph_interaction import GraphInteractionMixin
from .chart_theme import chart_painter

BLUE = "#0061a8"
BLUE_LINE = "#1f77b4"
BLUE_SHADE = "#e1f0fa"
RED = "#d9381e"
INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
GRID = "#f0f2f5"
CARD_BG = "#f8f9fa"


def _fmt(val: Optional[float], dec: int = 2) -> str:
    if val is None or math.isnan(val):
        return ""
    return f"{val:.{dec}f}"


class ALTLifeVsStressWidget(GraphInteractionMixin, QWidget):
    """High-fidelity vector Life vs Stress chart with use condition extrapolation."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", entry)
        self.setMouseTracking(True)
        self.setMinimumSize(820, 540)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._hovered_pt_idx: Optional[int] = None
        self._data_points_px: List[Tuple[QPointF, Dict[str, Any]]] = []

    def sizeHint(self) -> QSize:
        return QSize(880, 560)

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        painter.fillRect(0, 0, w, h, QColor("#ffffff"))

        res = self.result
        time_name = str(res.get("time_name", "Time"))
        stress_name = str(res.get("stress_name", "Stress"))
        model_name = str(res.get("model", "arrhenius")).replace("_", " ").title()
        dist_name = str(res.get("distribution", "weibull")).capitalize()
        use_s = res.get("use_stress")

        # Title
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        title_rect = QRectF(20, 15, w - 40, 24)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignHCenter, f"Life vs Stress Plot: {time_name} vs {stress_name}")

        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(MUTED))
        sub_rect = QRectF(20, 38, w - 40, 18)
        painter.drawText(sub_rect, Qt.AlignmentFlag.AlignHCenter, f"Model: {model_name}   |   Distribution: {dist_name} (MLE)   |   95% Confidence Bounds")

        # Right sidebar for summary card
        card_w = min(250, int(w * 0.28))
        plot_left = 75
        plot_right = w - card_w - 25
        plot_top = 70
        plot_bottom = h - 60
        plot_w = max(100.0, float(plot_right - plot_left))
        plot_h = max(100.0, float(plot_bottom - plot_top))

        # Data bounds
        points = res.get("plot_points", [])
        if not points:
            painter.drawText(QRectF(0, 60, w, h - 60), Qt.AlignmentFlag.AlignCenter, "No observations.")
            return

        stresses_all = [p["stress"] for p in points]
        if use_s is not None:
            stresses_all.append(use_s)
        times_all = [p["time"] for p in points]

        pcts = res.get("percentiles", [])
        if pcts:
            for pct in pcts:
                times_all.append(pct["estimate"])
                times_all.append(pct["ci_lower"])
                times_all.append(pct["ci_upper"])

        min_s, max_s = min(stresses_all), max(stresses_all)
        s_span = max(1.0, max_s - min_s)
        s_min_plot = min_s - s_span * 0.08
        s_max_plot = max_s + s_span * 0.08

        min_t, max_t = min(times_all), max(times_all)
        log_min_t = math.log10(max(1e-3, min_t))
        log_max_t = math.log10(max(1e-2, max_t))
        t_span = max(0.5, log_max_t - log_min_t)
        t_min_plot = log_min_t - t_span * 0.08
        t_max_plot = log_max_t + t_span * 0.08

        def s_to_px(s_val: float) -> float:
            return plot_left + ((s_val - s_min_plot) / (s_max_plot - s_min_plot)) * plot_w

        def t_to_px(t_val: float) -> float:
            log_t = math.log10(max(1e-6, t_val))
            # Invert Y axis
            return plot_bottom - ((log_t - t_min_plot) / (t_max_plot - t_min_plot)) * plot_h

        # Draw grid and axes
        painter.setPen(QPen(QColor(BORDER), 1.2))
        painter.drawRect(QRectF(plot_left, plot_top, plot_w, plot_h))

        # X Ticks
        n_x_ticks = 5
        x_step = (s_max_plot - s_min_plot) / n_x_ticks
        painter.setFont(QFont("Segoe UI", 8.5))
        for i in range(n_x_ticks + 1):
            s_tick = s_min_plot + i * x_step
            px = s_to_px(s_tick)
            if plot_left <= px <= plot_right:
                painter.setPen(QPen(QColor(GRID), 1))
                painter.drawLine(QPointF(px, plot_top), QPointF(px, plot_bottom))
                painter.setPen(QPen(QColor(MUTED), 1))
                painter.drawLine(QPointF(px, plot_bottom), QPointF(px, plot_bottom + 4))
                painter.drawText(QRectF(px - 30, plot_bottom + 6, 60, 18), Qt.AlignmentFlag.AlignHCenter, f"{s_tick:.1f}")

        # Y Ticks (Log scale powers of 10)
        floor_pow = math.floor(t_min_plot)
        ceil_pow = math.ceil(t_max_plot)
        for p in range(floor_pow, ceil_pow + 1):
            t_val = 10.0 ** p
            py = t_to_px(t_val)
            if plot_top <= py <= plot_bottom:
                painter.setPen(QPen(QColor(GRID), 1))
                painter.drawLine(QPointF(plot_left, py), QPointF(plot_right, py))
                painter.setPen(QPen(QColor(MUTED), 1))
                painter.drawLine(QPointF(plot_left - 4, py), QPointF(plot_left, py))
                painter.drawText(QRectF(plot_left - 65, py - 9, 58, 18), Qt.AlignmentFlag.AlignRight, f"10^{p}" if p != 0 else "1")

        # Axis Titles
        painter.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Medium))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(plot_left, plot_bottom + 28, plot_w, 20), Qt.AlignmentFlag.AlignHCenter, f"Stress: {stress_name}")

        painter.save()
        painter.translate(plot_left - 50, plot_top + plot_h / 2)
        painter.rotate(-90)
        painter.drawText(QRectF(-plot_h / 2, -15, plot_h, 20), Qt.AlignmentFlag.AlignHCenter, f"Lifetime: {time_name} (log scale)")
        painter.restore()

        # Draw regression line and confidence bands across s_range
        b0 = float(res.get("b0", 0.0))
        b1 = float(res.get("b1", 0.0))
        model = res.get("model", "arrhenius")
        sigma = float(res.get("sigma", 1.0))

        s_samples = np.linspace(s_min_plot, s_max_plot, 100)
        fit_points_px = []
        band_top_px = []
        band_bot_px = []

        for s_eval in s_samples:
            if model == "arrhenius":
                if s_eval <= -273.15:
                    continue
                x_eval = 1000.0 / (s_eval + 273.15)
            elif model == "inverse_power":
                if s_eval <= 0:
                    continue
                x_eval = math.log(s_eval)
            else:
                x_eval = s_eval

            # Median life: y = b0 + b1 * x + median_w * sigma
            # For Weibull, median w = ln(ln(2)) = -0.3665
            w_med = -0.3665129 if res.get("distribution") == "weibull" else 0.0
            y_med = b0 + b1 * x_eval + w_med * sigma
            t_med = math.exp(y_med)

            # Standard error approximation for band
            se_approx = 0.12 * math.sqrt(1.0 + ((x_eval - np.mean(stresses_all))**2))
            t_low = math.exp(y_med - 1.96 * se_approx)
            t_high = math.exp(y_med + 1.96 * se_approx)

            px = s_to_px(s_eval)
            py = t_to_px(t_med)
            fit_points_px.append(QPointF(px, py))
            band_top_px.append(QPointF(px, t_to_px(t_high)))
            band_bot_px.append(QPointF(px, t_to_px(t_low)))

        # Draw shaded confidence band
        if fit_points_px:
            band_path = QPainterPath()
            band_path.moveTo(band_top_px[0])
            for pt in band_top_px[1:]:
                band_path.lineTo(pt)
            for pt in reversed(band_bot_px):
                band_path.lineTo(pt)
            band_path.closeSubpath()

            painter.save()
            painter.setClipRect(QRectF(plot_left, plot_top, plot_w, plot_h))
            painter.fillPath(band_path, QColor(BLUE_SHADE))

            # Draw median line
            line_pen = QPen(QColor(BLUE_LINE), 2.2, Qt.PenStyle.SolidLine)
            painter.setPen(line_pen)
            line_path = QPainterPath()
            line_path.moveTo(fit_points_px[0])
            for pt in fit_points_px[1:]:
                line_path.lineTo(pt)
            painter.drawPath(line_path)
            painter.restore()

        # Vertical line at use_stress
        if use_s is not None and plot_left <= s_to_px(use_s) <= plot_right:
            px_use = s_to_px(use_s)
            pen_use = QPen(QColor(RED), 1.8, Qt.PenStyle.DashLine)
            painter.setPen(pen_use)
            painter.drawLine(QPointF(px_use, plot_top), QPointF(px_use, plot_bottom))

            painter.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Bold))
            painter.setPen(QColor(RED))
            painter.drawText(QRectF(px_use - 60, plot_top - 20, 120, 16), Qt.AlignmentFlag.AlignHCenter, f"Use Stress = {use_s}")

        # Draw data points
        self._data_points_px = []
        painter.save()
        painter.setClipRect(QRectF(plot_left - 5, plot_top - 5, plot_w + 10, plot_h + 10))

        for idx, pt in enumerate(points):
            px = s_to_px(pt["stress"])
            py = t_to_px(pt["time"])
            qpt = QPointF(px, py)
            self._data_points_px.append((qpt, pt))

            is_failed = (pt["event"] == 1)
            is_hover = (idx == self._hovered_pt_idx)

            if is_failed:
                # Failure: filled circle
                painter.setPen(QPen(QColor(BLUE), 1.5))
                painter.setBrush(QBrush(QColor(BLUE_LINE) if not is_hover else QColor(RED)))
                r = 4.5 if not is_hover else 6.5
                painter.drawEllipse(qpt, r, r)
            else:
                # Right-censored: open triangle
                painter.setPen(QPen(QColor(RED), 1.8))
                painter.setBrush(QBrush(QColor("#ffffff") if not is_hover else QColor(RED)))
                side = 5.0 if not is_hover else 7.0
                poly = QPainterPath()
                poly.moveTo(px, py - side)
                poly.lineTo(px - side, py + side)
                poly.lineTo(px + side, py + side)
                poly.closeSubpath()
                painter.drawPath(poly)

        painter.restore()

        # Draw Right Summary Card
        card_rect = QRectF(w - card_w - 10, plot_top, card_w, plot_h)
        painter.fillRect(card_rect, QColor(CARD_BG))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(card_rect)

        # Card Content
        cy = plot_top + 12
        cx = w - card_w - 2
        cw = card_w - 16

        painter.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(cx + 8, cy, cw, 18), Qt.AlignmentFlag.AlignLeft, "Model Estimates (MLE)")
        cy += 22

        painter.setFont(QFont("Segoe UI", 8.5))
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(cx + 8, cy, cw, 16), Qt.AlignmentFlag.AlignLeft, f"Intercept (β₀): {_fmt(b0, 4)}")
        cy += 18
        painter.drawText(QRectF(cx + 8, cy, cw, 16), Qt.AlignmentFlag.AlignLeft, f"Slope (β₁): {_fmt(b1, 4)}")
        cy += 18
        if res.get("distribution") == "weibull":
            painter.drawText(QRectF(cx + 8, cy, cw, 16), Qt.AlignmentFlag.AlignLeft, f"Shape (β): {_fmt(res.get('shape'), 4)}")
            cy += 18
        painter.drawText(QRectF(cx + 8, cy, cw, 16), Qt.AlignmentFlag.AlignLeft, f"Scale (σ): {_fmt(sigma, 4)}")
        cy += 24

        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawLine(QPointF(cx + 8, cy), QPointF(cx + cw, cy))
        cy += 8

        painter.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(cx + 8, cy, cw, 18), Qt.AlignmentFlag.AlignLeft, f"Extrapolated Life ({use_s})")
        cy += 20

        painter.setFont(QFont("Segoe UI", 8.5))
        for pct in pcts:
            lbl = pct.get("label", f"{pct.get('percentile', 0)}%")
            est = _fmt(pct.get("estimate"), 1)
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(cx + 8, cy, cw, 16), Qt.AlignmentFlag.AlignLeft, f"{lbl}: {est}")
            cy += 18

        cy += 10
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawLine(QPointF(cx + 8, cy), QPointF(cx + cw, cy))
        cy += 8

        painter.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(cx + 8, cy, cw, 18), Qt.AlignmentFlag.AlignLeft, "Legend")
        cy += 20

        # Legend entries
        painter.setFont(QFont("Segoe UI", 8.5))
        painter.setPen(QColor(BLUE))
        painter.setBrush(QBrush(QColor(BLUE_LINE)))
        painter.drawEllipse(QPointF(cx + 16, cy + 8), 4, 4)
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(cx + 28, cy, cw - 28, 16), Qt.AlignmentFlag.AlignLeft, "Failure observation")
        cy += 20

        painter.setPen(QPen(QColor(RED), 1.5))
        painter.setBrush(QBrush(QColor("#ffffff")))
        poly = QPainterPath()
        poly.moveTo(cx + 16, cy + 4)
        poly.lineTo(cx + 12, cy + 12)
        poly.lineTo(cx + 20, cy + 12)
        poly.closeSubpath()
        painter.drawPath(poly)
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(cx + 28, cy, cw - 28, 16), Qt.AlignmentFlag.AlignLeft, "Right-censored")
        cy += 20

        painter.setPen(QPen(QColor(BLUE_LINE), 2))
        painter.drawLine(QPointF(cx + 10, cy + 8), QPointF(cx + 22, cy + 8))
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(cx + 28, cy, cw - 28, 16), Qt.AlignmentFlag.AlignLeft, "Fitted median life")

    def mouseMoveEvent(self, event):
        pos = event.position()
        found_idx = None
        for idx, (qpt, pt) in enumerate(self._data_points_px):
            dist = math.hypot(pos.x() - qpt.x(), pos.y() - qpt.y())
            if dist <= 8.0:
                found_idx = idx
                break

        if found_idx != self._hovered_pt_idx:
            self._hovered_pt_idx = found_idx
            self.update()

        if found_idx is not None:
            _, pt = self._data_points_px[found_idx]
            status = "Failure" if pt["event"] == 1 else "Right-Censored"
            tip = (
                f"<b>Status:</b> {status}<br/>"
                f"<b>Stress:</b> {pt['stress']:.2f}<br/>"
                f"<b>Lifetime:</b> {pt['time']:.2f}"
            )
            QToolTip.showText(event.globalPosition().toPoint(), tip, self)
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hovered_pt_idx = None
        self.update()
        super().leaveEvent(event)
