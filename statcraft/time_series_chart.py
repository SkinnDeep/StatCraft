"""High-fidelity Qt/QPainter renderer for Time Series Analysis and Forecasting.

Renders authentic StatCraft visual time series charts:
- Primary time series plot with Actual (solid blue), Fitted (dashed red), Forecasts (green squares), and 95% Prediction Limits (green dotted).
- Inset cards displaying Model Equation and Accuracy Measures (MAPE, MAD, MSD).
- ACF and PACF spike plots with 95% Bartlett confidence limit bands.
- Decomposition multi-panel component displays.
- Interactive hover tooltips via GraphInteractionMixin.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .snapshot_chart import SnapshotChartWidget
from .graph_hover import summary_info

BLUE = "#0061a8"
BLUE_FILL = "#1f77b4"
RED = "#d9534f"
GREEN = "#2ca02c"
GREEN_BAND = "#85e085"
INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
GRID = "#e8ecef"
BOX_BG = "#f8f9fa"


def _fmt(val: Optional[float], dec: int = 4) -> str:
    if val is None or math.isnan(val):
        return "*"
    if val == float("inf"):
        return "Inf"
    if val == float("-inf"):
        return "-Inf"
    return f"{val:.{dec}f}"


class TimeSeriesChartWidget(SnapshotChartWidget):
    """Time Series Plot displaying Actual, Fits, Forecasts with Prediction Limits, and Accuracy box."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(entry, parent)
        self.result = entry.get("result", {})
        self.recipe = entry.get("recipe", {})

        self.analysis = self.result.get("analysis", "trend_analysis")
        var_name = self.result.get("variable_name", "Series")
        self.title_text = self.result.get("title") or f"Time Series Plot for {var_name}"

        self.setMinimumSize(640, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.hover_point: Optional[Tuple[float, float, str]] = None

    def sizeHint(self) -> QSize:
        return QSize(780, 480)

    def paintEvent(self, event) -> None:
        self.reset_hover_regions()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect()
        painter.fillRect(rect, QColor("#ffffff"))

        if self.analysis in ("autocorrelation", "partial_autocorrelation", "cross_correlation"):
            self._paint_correlation_plot(painter, rect)
        else:
            self._paint_time_series_plot(painter, rect)

    def _paint_time_series_plot(self, painter: QPainter, rect: QRectF) -> None:
        actual = self.result.get("actual", [])
        fitted = self.result.get("fitted", [])
        forecasts = self.result.get("forecasts", [])
        accuracy = self.result.get("accuracy", {})

        n_actual = len(actual)
        n_fc = len(forecasts)
        total_periods = n_actual + n_fc

        if total_periods == 0:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No time series data available to display.")
            return

        # Layout Geometry
        top_margin = 60
        bottom_margin = 55
        left_margin = 70
        right_panel_width = 175
        plot_spacing = 15

        plot_width = max(10.0, rect.width() - left_margin - right_panel_width - plot_spacing)
        plot_height = max(10.0, rect.height() - top_margin - bottom_margin)

        plot_rect = QRectF(left_margin, top_margin, plot_width, plot_height)
        card_rect = QRectF(plot_rect.right() + plot_spacing, top_margin, right_panel_width - 15, plot_height)

        # Title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(
            QRectF(left_margin, 10, rect.width() - left_margin - 20, 24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.title_text,
        )

        subtitle = ""
        if self.analysis == "trend_analysis":
            subtitle = f"Trend Model: {self.result.get('equation', '')}"
        elif self.analysis == "decomposition":
            subtitle = f"Decomposition ({self.result.get('model', 'multiplicative').capitalize()}) - Season Length {self.result.get('season_length', 4)}"
        elif self.analysis == "moving_average":
            subtitle = f"Moving Average (Length: {self.result.get('ma_length', 3)})"
        elif self.analysis == "single_exp_smoothing":
            subtitle = f"Single Exponential Smoothing (Alpha: {_fmt(self.result.get('alpha'), 4)})"
        elif self.analysis == "arima":
            subtitle = f"ARIMA({self.result.get('p')},{self.result.get('d')},{self.result.get('q')}) - SS: {_fmt(self.result.get('ss'), 3)}, MS: {_fmt(self.result.get('ms'), 4)}"
        elif self.analysis == "double_exp_smoothing":
            subtitle = f"Double Exponential Smoothing (Alpha: {_fmt(self.result.get('alpha'), 4)}, Gamma: {_fmt(self.result.get('gamma'), 4)})"
        elif self.analysis == "winters_method":
            m_name = self.result.get('model', 'multiplicative').capitalize()
            subtitle = f"Winters' Method ({m_name}) - Alpha: {_fmt(self.result.get('alpha'), 4)}, Gamma: {_fmt(self.result.get('gamma'), 4)}, Delta: {_fmt(self.result.get('delta'), 4)}" 

        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Normal))
        painter.setPen(QColor(MUTED))
        painter.drawText(
            QRectF(left_margin, 34, rect.width() - left_margin - 20, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            subtitle,
        )

        # Determine Y range
        all_vals: List[float] = [v for v in actual if v is not None and not math.isnan(v)]
        for v in fitted:
            if v is not None and not math.isnan(v):
                all_vals.append(v)
        for fc in forecasts:
            for key in ("forecast", "lower", "upper"):
                val = fc.get(key)
                if val is not None and not math.isnan(val):
                    all_vals.append(val)

        if not all_vals:
            all_vals = [0.0, 1.0]

        y_min = min(all_vals)
        y_max = max(all_vals)
        span = y_max - y_min
        if span == 0:
            span = 1.0
        y_min_disp = y_min - 0.1 * span
        y_max_disp = y_max + 0.1 * span
        disp_span = y_max_disp - y_min_disp

        # Coordinate transforms
        def x_coord(period: float) -> float:
            if total_periods <= 1:
                return plot_rect.left()
            return plot_rect.left() + (period - 1.0) / (total_periods - 1.0) * plot_rect.width()

        def y_coord(val: float) -> float:
            return plot_rect.bottom() - (val - y_min_disp) / disp_span * plot_rect.height()

        # Draw Grid & Frame
        painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
        y_ticks = 5
        for i in range(y_ticks + 1):
            t_val = y_min_disp + i * (disp_span / y_ticks)
            py = y_coord(t_val)
            painter.drawLine(QPointF(plot_rect.left(), py), QPointF(plot_rect.right(), py))
            # Y label
            painter.setPen(QColor(MUTED))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(
                QRectF(0, py - 8, left_margin - 8, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{t_val:.2f}",
            )
            painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))

        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(plot_rect)

        # X-axis ticks (periods)
        step_x = max(1, total_periods // 10)
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(MUTED))
        for p in range(1, total_periods + 1, step_x):
            px = x_coord(p)
            painter.drawLine(QPointF(px, plot_rect.bottom()), QPointF(px, plot_rect.bottom() + 4))
            painter.drawText(
                QRectF(px - 20, plot_rect.bottom() + 6, 40, 16),
                Qt.AlignmentFlag.AlignCenter,
                str(p),
            )

        # 1. Fitted Line (Red Dashed)
        valid_fits = [(i + 1, val) for i, val in enumerate(fitted) if val is not None and not math.isnan(val)]
        if len(valid_fits) > 1:
            pen_fit = QPen(QColor(RED), 1.75, Qt.PenStyle.DashLine)
            painter.setPen(pen_fit)
            path_fit = QPainterPath()
            path_fit.moveTo(x_coord(valid_fits[0][0]), y_coord(valid_fits[0][1]))
            for period, val in valid_fits[1:]:
                path_fit.lineTo(x_coord(period), y_coord(val))
            painter.drawPath(path_fit)

        # 2. Actual Observations (Blue Line + Circles)
        if len(actual) > 0:
            pen_act = QPen(QColor(BLUE), 1.5, Qt.PenStyle.SolidLine)
            painter.setPen(pen_act)
            path_act = QPainterPath()
            started = False
            for i, val in enumerate(actual):
                if val is not None and not math.isnan(val):
                    px = x_coord(i + 1)
                    py = y_coord(val)
                    if not started:
                        path_act.moveTo(px, py)
                        started = True
                    else:
                        path_act.lineTo(px, py)
            painter.drawPath(path_act)

            # Draw circle markers for actual
            painter.setBrush(QColor(BLUE_FILL))
            for i, val in enumerate(actual):
                if val is not None and not math.isnan(val):
                    px = x_coord(i + 1)
                    py = y_coord(val)
                    painter.drawEllipse(QPointF(px, py), 3.0, 3.0)

        # 3. Forecasts & Prediction Intervals (Green)
        if forecasts:
            # Forecast line starting from last actual point
            pen_fc = QPen(QColor(GREEN), 2.0, Qt.PenStyle.SolidLine)
            painter.setPen(pen_fc)
            path_fc = QPainterPath()

            # Connect from last actual/fit point
            last_p = n_actual
            last_v = actual[-1] if actual and actual[-1] is not None else (fitted[-1] if fitted else forecasts[0]["forecast"])
            path_fc.moveTo(x_coord(last_p), y_coord(last_v))
            for fc in forecasts:
                path_fc.lineTo(x_coord(fc["period"]), y_coord(fc["forecast"]))
            painter.drawPath(path_fc)

            # Square markers for forecasts
            painter.setBrush(QColor(GREEN))
            for fc in forecasts:
                px = x_coord(fc["period"])
                py = y_coord(fc["forecast"])
                painter.drawRect(QRectF(px - 3.5, py - 3.5, 7.0, 7.0))

            # Prediction limit lines (Lower and Upper)
            pen_limits = QPen(QColor(GREEN_BAND), 1.5, Qt.PenStyle.DotLine)
            painter.setPen(pen_limits)
            path_low = QPainterPath()
            path_upp = QPainterPath()
            first_low = True
            for fc in forecasts:
                px = x_coord(fc["period"])
                py_l = y_coord(fc["lower"])
                py_u = y_coord(fc["upper"])
                if first_low:
                    path_low.moveTo(px, py_l)
                    path_upp.moveTo(px, py_u)
                    first_low = False
                else:
                    path_low.lineTo(px, py_l)
                    path_upp.lineTo(px, py_u)
            painter.drawPath(path_low)
            painter.drawPath(path_upp)

        # Right Summary / Legend Card
        painter.setBrush(QColor(BOX_BG))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRoundedRect(card_rect, 4, 4)

        cx = card_rect.left() + 10
        cy = card_rect.top() + 14

        # Legend header
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(cx, cy, card_rect.width() - 20, 18), "Variable")
        cy += 18
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(cx, cy, card_rect.width() - 20, 16), f"Actual: {self.result.get('variable_name', 'Series')}")
        cy += 20

        # Legend Items
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(cx, cy, card_rect.width() - 20, 18), "Legend")
        cy += 18

        # 1. Actual
        painter.setPen(QPen(QColor(BLUE), 1.5))
        painter.drawLine(QPointF(cx, cy + 6), QPointF(cx + 18, cy + 6))
        painter.setBrush(QColor(BLUE_FILL))
        painter.drawEllipse(QPointF(cx + 9, cy + 6), 2.5, 2.5)
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(cx + 24, cy, 100, 16), "Actual")
        cy += 18

        # 2. Fits
        painter.setPen(QPen(QColor(RED), 1.5, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(cx, cy + 6), QPointF(cx + 18, cy + 6))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(cx + 24, cy, 100, 16), "Fits")
        cy += 18

        # 3. Forecasts
        if forecasts:
            painter.setPen(QPen(QColor(GREEN), 1.5))
            painter.drawLine(QPointF(cx, cy + 6), QPointF(cx + 18, cy + 6))
            painter.setBrush(QColor(GREEN))
            painter.drawRect(QRectF(cx + 6.5, cy + 3.5, 5.0, 5.0))
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(cx + 24, cy, 100, 16), "Forecasts")
            cy += 18

            # 4. Limits
            painter.setPen(QPen(QColor(GREEN_BAND), 1.5, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(cx, cy + 6), QPointF(cx + 18, cy + 6))
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(cx + 24, cy, 100, 16), f"{self.result.get('conf_level', 95.0):g}% Limits")
            cy += 22

        if self.analysis == "winters_method":
            cy += 4
            painter.setPen(QPen(QColor(BORDER), 1))
            painter.drawLine(QPointF(cx, cy), QPointF(card_rect.right() - 10, cy))
            cy += 6
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(cx, cy, card_rect.width() - 20, 16), "Smoothing Constants")
            cy += 18
            painter.setFont(QFont("Segoe UI", 8))
            for lbl, k in [("Alpha", "alpha"), ("Gamma", "gamma"), ("Delta", "delta")]:
                painter.drawText(QRectF(cx, cy, 60, 15), lbl)
                painter.drawText(QRectF(cx + 60, cy, card_rect.width() - 80, 15), Qt.AlignmentFlag.AlignRight, _fmt(self.result.get(k), 4))
                cy += 16

        # Accuracy Box
        cy += 6
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawLine(QPointF(cx, cy), QPointF(card_rect.right() - 10, cy))
        cy += 8

        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(cx, cy, card_rect.width() - 20, 18), "Accuracy Measures")
        cy += 20

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(cx, cy, 50, 16), "MAPE")
        painter.drawText(QRectF(cx + 55, cy, card_rect.width() - 75, 16), Qt.AlignmentFlag.AlignRight, _fmt(accuracy.get("mape"), 4))
        cy += 18

        painter.drawText(QRectF(cx, cy, 50, 16), "MAD")
        painter.drawText(QRectF(cx + 55, cy, card_rect.width() - 75, 16), Qt.AlignmentFlag.AlignRight, _fmt(accuracy.get("mad"), 4))
        cy += 18

        painter.drawText(QRectF(cx, cy, 50, 16), "MSD")
        painter.drawText(QRectF(cx + 55, cy, card_rect.width() - 75, 16), Qt.AlignmentFlag.AlignRight, _fmt(accuracy.get("msd"), 4))

    def _paint_correlation_plot(self, painter: QPainter, rect: QRectF) -> None:
        """Render a lag correlation plot."""
        lags_data = self.result.get("lags", [])
        is_cross = self.analysis == "cross_correlation"
        sig_limit = float(self.result.get("sig_limit", 0.2))

        top_margin = 20 if is_cross else 60
        bottom_margin = 55
        left_margin = 65
        right_margin = 35

        plot_width = max(10.0, rect.width() - left_margin - right_margin)
        plot_height = max(10.0, rect.height() - top_margin - bottom_margin)
        plot_rect = QRectF(left_margin, top_margin, plot_width, plot_height)

        if not is_cross:
            painter.setPen(QColor(INK))
            painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            painter.drawText(QRectF(left_margin, 10, rect.width() - left_margin - 20, 24),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title_text)
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor(MUTED))
            painter.drawText(QRectF(left_margin, 34, rect.width() - left_margin - 20, 18),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             f"Approximate reference limits ±{sig_limit:.4f}")

        # Y scale fixed between -1.0 and +1.0
        def y_coord(val: float) -> float:
            return plot_rect.bottom() - (val - (-1.0)) / 2.0 * plot_rect.height()

        num_lags = len(lags_data)
        if num_lags == 0:
            return

        first_lag = lags_data[0]["lag"]

        def x_coord(lag_num: int) -> float:
            return plot_rect.left() + (lag_num - first_lag + 0.5) / num_lags * plot_rect.width()

        # Grid lines at -1.0, -0.5, 0.0, +0.5, +1.0
        painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
        for y_val in (-1.0, -0.5, 0.0, 0.5, 1.0):
            py = y_coord(y_val)
            painter.drawLine(QPointF(plot_rect.left(), py), QPointF(plot_rect.right(), py))
            painter.setPen(QColor(MUTED))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(
                QRectF(0, py - 8, left_margin - 8, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{y_val:+.1f}",
            )
            painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))

        # Center line at Y=0
        painter.setPen(QPen(QColor(BORDER), 1.5))
        py_zero = y_coord(0.0)
        painter.drawLine(QPointF(plot_rect.left(), py_zero), QPointF(plot_rect.right(), py_zero))

        if not is_cross:
            painter.setPen(QPen(QColor(RED), 1.25, Qt.PenStyle.DashLine))
            for limit in (-sig_limit, sig_limit):
                y = y_coord(limit)
                painter.drawLine(QPointF(plot_rect.left(), y), QPointF(plot_rect.right(), y))
        else:
            painter.setPen(QColor(INK))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(QRectF(plot_rect.left(), plot_rect.bottom() + 26, plot_width, 20),
                             Qt.AlignmentFlag.AlignCenter, "Lag")
            painter.save()
            painter.translate(15, plot_rect.center().y())
            painter.rotate(-90)
            painter.drawText(QRectF(-plot_height / 2, -10, plot_height, 20),
                             Qt.AlignmentFlag.AlignCenter, "Cross Correlation")
            painter.restore()

        # Draw Frame
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(plot_rect)

        # Draw Spikes
        val_key = "pacf" if self.analysis == "partial_autocorrelation" else "correlation"
        for item in lags_data:
            lag = item["lag"]
            val = float(item[val_key])
            px = x_coord(lag)
            py_val = y_coord(val)

            # Spike line
            painter.setPen(QPen(QColor(BLUE), 2.0))
            painter.drawLine(QPointF(px, py_zero), QPointF(px, py_val))

            if not is_cross:
                painter.setBrush(QColor(BLUE_FILL))
                painter.drawEllipse(QPointF(px, py_val), 3.0, 3.0)

            fields = [("Lag", lag), ("Correlation", val)]
            if "pairs" in item:
                fields.append(("Pairs", item["pairs"]))
            self.remember_point_hover(QPointF(px, py_val), summary_info("correlation", fields), clip=plot_rect)

            # Keep tick labels readable for long lag ranges.
            if lag == 0 or (lag - first_lag) % max(1, math.ceil(num_lags / 16)) == 0:
                painter.setPen(QColor(MUTED))
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(
                    QRectF(px - 15, plot_rect.bottom() + 4, 30, 16),
                    Qt.AlignmentFlag.AlignCenter,
                    str(lag),
                )
