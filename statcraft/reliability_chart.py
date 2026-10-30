"""Interactive Qt Chart Widget for Reliability Distribution Analysis (Survival & Hazard Plot)."""

from __future__ import annotations

from .snapshot_chart import SnapshotChartWidget

import math
from typing import Any, Dict, List, Optional
import numpy as np
from scipy import stats

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath
from PySide6.QtWidgets import QWidget


class ReliabilityPlotWidget(SnapshotChartWidget):
    """High-fidelity dual-panel reliability plot: Survival Curve S(t) and Cumulative Hazard H(t)."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(entry, parent)
        self.entry = entry
        self.result = entry.get("result", entry)
        self.setMinimumSize(780, 520)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Fill background
        painter.fillRect(0, 0, w, h, QColor("#FFFFFF"))

        var_name = self.entry.get("variable_name", self.entry.get("title", "Lifetime"))
        dist_name = self.result.get("dist_name", "weibull").capitalize()

        # Title
        painter.setPen(QColor("#0F172A"))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(20, 15, w - 40, 25), Qt.AlignmentFlag.AlignCenter, f"Survival Plot for {var_name}")

        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor("#64748B"))
        painter.drawText(QRectF(20, 38, w - 40, 20), Qt.AlignmentFlag.AlignCenter, f"Distribution: {dist_name}   |   Method: Maximum Likelihood (MLE)")

        # Layout: Left side Survival Curve S(t), Right side Kaplan-Meier & Parameters summary
        side_box_w = min(220, int(w * 0.30))
        plot_rect = QRectF(60, 75, w - side_box_w - 90, h - 120)
        side_rect = QRectF(w - side_box_w - 20, 75, side_box_w, h - 120)

        # Plot frame
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.drawRect(plot_rect)

        times = np.array(self.result.get("times", [1.0, 10.0]), dtype=float)
        max_t = float(np.max(times)) * 1.15
        min_t = 0.0

        def to_sx(t: float) -> float:
            return plot_rect.left() + (t / max_t) * plot_rect.width()

        def to_sy(s: float) -> float:
            # S is probability from 0.0 to 1.0
            return plot_rect.bottom() - s * plot_rect.height()

        # Grid lines (0.25, 0.50, 0.75, 1.0)
        painter.setPen(QPen(QColor("#F1F5F9"), 1, Qt.PenStyle.DashLine))
        for prob in [0.25, 0.50, 0.75, 1.0]:
            py = to_sy(prob)
            painter.drawLine(QPointF(plot_rect.left(), py), QPointF(plot_rect.right(), py))
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(QPointF(plot_rect.left() - 35, py + 4), f"{prob:.2f}")
            painter.setPen(QPen(QColor("#F1F5F9"), 1, Qt.PenStyle.DashLine))

        # 1. Draw Kaplan-Meier step function
        km = self.result.get("kaplan_meier", {})
        km_times = km.get("times", [])
        km_surv = km.get("survival", [])
        if km_times and km_surv:
            km_path = QPainterPath()
            km_path.moveTo(to_sx(0.0), to_sy(1.0))
            cur_s = 1.0
            for t, s in zip(km_times, km_surv):
                # Step horizontal then vertical
                km_path.lineTo(to_sx(t), to_sy(cur_s))
                km_path.lineTo(to_sx(t), to_sy(s))
                cur_s = s
            km_path.lineTo(to_sx(max_t), to_sy(cur_s))

            painter.setPen(QPen(QColor("#94A3B8"), 1.5, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(km_path)

        # 2. Draw Parametric Survival Curve
        params = self.result.get("parameters", {})
        ts = np.linspace(0.0, max_t, 250)
        if dist_name.lower() == "weibull":
            b = params.get("shape", 1.5)
            a = params.get("scale", 10.0)
            surv_vals = np.exp(-(ts / a)**b)
        elif dist_name.lower() == "lognormal":
            mu = params.get("location", 2.0)
            sig = params.get("scale", 0.5)
            surv_vals = 1.0 - stats.norm.cdf((np.log(np.maximum(1e-6, ts)) - mu) / sig)
        elif dist_name.lower() == "exponential":
            th = params.get("scale_mean", 10.0)
            surv_vals = np.exp(-ts / th)
        else:
            surv_vals = stats.norm.sf(ts, loc=params["mean"], scale=params["stdev"])

        curve_path = QPainterPath()
        curve_path.moveTo(to_sx(ts[0]), to_sy(surv_vals[0]))
        for t_val, s_val in zip(ts[1:], surv_vals[1:]):
            curve_path.lineTo(to_sx(t_val), to_sy(s_val))

        painter.setPen(QPen(QColor("#2563EB"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(curve_path)

        # 3. Side Summary Panel
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.setBrush(QBrush(QColor("#F8FAFC")))
        painter.drawRoundedRect(side_rect, 4, 4)

        box_y = side_rect.top() + 20
        lh = 18
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#0F172A"))
        painter.drawText(side_rect.left() + 10, box_y, "Distribution:")
        box_y += lh
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#334155"))
        painter.drawText(side_rect.left() + 15, box_y, f"{dist_name} (MLE)")
        box_y += lh + 6

        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#0F172A"))
        painter.drawText(side_rect.left() + 10, box_y, "Sample Summary:")
        box_y += lh
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#334155"))
        painter.drawText(side_rect.left() + 15, box_y, f"Total: {self.result.get('n_total', 0)}")
        box_y += lh
        painter.drawText(side_rect.left() + 15, box_y, f"Failures: {self.result.get('n_events', 0)}")
        box_y += lh
        painter.drawText(side_rect.left() + 15, box_y, f"Censored: {self.result.get('n_censored', 0)}")
        box_y += lh + 6

        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#0F172A"))
        painter.drawText(side_rect.left() + 10, box_y, "Parameters:")
        box_y += lh
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#334155"))
        for k, v in params.items():
            painter.drawText(side_rect.left() + 15, box_y, f"{k.capitalize()}: {v:.4f}")
            box_y += lh
        painter.drawText(side_rect.left() + 15, box_y, f"MTTF: {self.result.get('mttf', 0.0):.2f}")
        box_y += lh + 6

        # Legend
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QPen(QColor("#2563EB"), 2))
        painter.drawLine(QPointF(side_rect.left() + 15, box_y), QPointF(side_rect.left() + 35, box_y))
        painter.setPen(QColor("#334155"))
        painter.drawText(side_rect.left() + 42, box_y + 4, "Parametric Fit")
        box_y += lh
        painter.setPen(QPen(QColor("#94A3B8"), 1.5, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(side_rect.left() + 15, box_y), QPointF(side_rect.left() + 35, box_y))
        painter.setPen(QColor("#334155"))
        painter.drawText(side_rect.left() + 42, box_y + 4, "Nonparametric (KM)")
