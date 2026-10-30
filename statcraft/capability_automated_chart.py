"""Interactive Qt Chart Widget for Nonparametric Capability Analysis matching StatCraft."""

from __future__ import annotations

from .snapshot_chart import SnapshotChartWidget

import math
from typing import Any, Dict, List, Optional
import numpy as np

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PySide6.QtWidgets import QWidget


class NonparametricCapabilityPlotWidget(SnapshotChartWidget):
    """High-fidelity capability plot widget for Nonparametric (Distribution-Free) Analysis."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(entry, parent)
        self.entry = entry
        self.result = entry.get("result", entry)
        self.setMinimumSize(720, 500)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Fill background
        painter.fillRect(0, 0, w, h, QColor("#FFFFFF"))

        var_name = self.entry.get("variable_name", self.entry.get("title", "Measurement"))
        is_auto = (self.result.get("analysis") == "capability_automated")
        mode_title = "Automated Capability Analysis" if is_auto else "Nonparametric Capability Analysis"

        painter.setPen(QColor("#0F172A"))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(20, 15, w - 40, 25), Qt.AlignmentFlag.AlignCenter, f"{mode_title} for {var_name}")

        sub = f"Best Fit: {self.result.get('best_fit', {}).get('distribution')}" if is_auto else "Method: Empirical Percentiles (ISO 21747)"
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor("#64748B"))
        painter.drawText(QRectF(20, 38, w - 40, 20), Qt.AlignmentFlag.AlignCenter, sub)

        obs = np.array(self.result.get("observations", []), dtype=float)
        if len(obs) == 0:
            return

        lsl = self.result.get("lsl")
        usl = self.result.get("usl")

        side_box_w = min(220, int(w * 0.32))
        plot_rect = QRectF(50, 70, w - side_box_w - 70, h - 120)
        stat_rect = QRectF(w - side_box_w - 15, 70, side_box_w, h - 120)

        # Draw plot border
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.drawRect(plot_rect)

        min_x = float(np.min(obs))
        max_x = float(np.max(obs))
        if lsl is not None: min_x = min(min_x, lsl)
        if usl is not None: max_x = max(max_x, usl)

        span = max_x - min_x
        x_lo = min_x - 0.1 * span
        x_hi = max_x + 0.1 * span
        span_full = x_hi - x_lo

        # 1. Histogram
        counts, bin_edges = np.histogram(obs, bins=16, density=True)
        max_d = float(np.max(counts)) if len(counts) > 0 else 1.0

        def to_sx(vx: float) -> float:
            return plot_rect.left() + (vx - x_lo) / span_full * plot_rect.width()

        def to_sy(vy: float) -> float:
            return plot_rect.bottom() - (vy / (max_d * 1.25)) * plot_rect.height()

        painter.setPen(QPen(QColor("#94A3B8"), 1))
        painter.setBrush(QBrush(QColor("#E2E8F0")))
        for i in range(len(counts)):
            bx0 = to_sx(bin_edges[i])
            bx1 = to_sx(bin_edges[i+1])
            by = to_sy(counts[i])
            painter.drawRect(QRectF(bx0, by, bx1 - bx0, plot_rect.bottom() - by))

        # 2. Spec limits
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        if lsl is not None:
            lx = to_sx(lsl)
            painter.setPen(QPen(QColor("#DC2626"), 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(lx, plot_rect.top()), QPointF(lx, plot_rect.bottom()))
            painter.setPen(QColor("#DC2626"))
            painter.drawText(QPointF(lx - 25, plot_rect.top() - 6), f"LSL: {lsl:.2f}")

        if usl is not None:
            ux = to_sx(usl)
            painter.setPen(QPen(QColor("#DC2626"), 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(ux, plot_rect.top()), QPointF(ux, plot_rect.bottom()))
            painter.setPen(QColor("#DC2626"))
            painter.drawText(QPointF(ux - 15, plot_rect.top() - 6), f"USL: {usl:.2f}")

        # 3. Side summary box
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.setBrush(QBrush(QColor("#F8FAFC")))
        painter.drawRoundedRect(stat_rect, 4, 4)

        stat_y = stat_rect.top() + 20
        lh = 17
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#0F172A"))
        painter.drawText(stat_rect.left() + 10, stat_y, "Process Percentiles:")
        stat_y += lh

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#334155"))
        painter.drawText(stat_rect.left() + 15, stat_y, f"Sample N: {len(obs)}")
        stat_y += lh
        painter.drawText(stat_rect.left() + 15, stat_y, f"0.135%: {self.result.get('p_lower', 0.0):.2f}")
        stat_y += lh
        painter.drawText(stat_rect.left() + 15, stat_y, f"50.0%:  {self.result.get('p_median', 0.0):.2f}")
        stat_y += lh
        painter.drawText(stat_rect.left() + 15, stat_y, f"99.865%: {self.result.get('p_upper', 0.0):.2f}")
        stat_y += lh + 8

        idx = self.result.get("indices", {})
        is_vda = (self.result.get("naming_convention") == "aiag_vda")
        p_name = "Cnp" if is_vda else "Pp"
        pk_name = "Cnpk" if is_vda else "Ppk"

        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#0F172A"))
        painter.drawText(stat_rect.left() + 10, stat_y, "Capability:")
        stat_y += lh

        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#334155"))
        pp = idx.get("cnp" if is_vda else "pp")
        ppk = idx.get("cnpk" if is_vda else "ppk")
        if pp is not None:
            painter.drawText(stat_rect.left() + 15, stat_y, f"{p_name}: {pp:.2f}")
            stat_y += lh
        if ppk is not None:
            painter.drawText(stat_rect.left() + 15, stat_y, f"{pk_name}: {ppk:.2f}")
            stat_y += lh
