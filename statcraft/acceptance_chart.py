"""Qt Interactive Chart Widget for Acceptance Control Charts."""

import math
from typing import Any, Dict, List
import numpy as np

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PySide6.QtWidgets import QWidget


class AcceptanceControlChartWidget(QWidget):
    """StatCraft Acceptance Control Chart Plot Widget."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.entry = entry
        self.error = None
        self.panels = []
        self.setMinimumSize(780, 520)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        rect = self.rect()
        painter.fillRect(rect, QColor("#FFFFFF"))

        res = self.entry.get("result", {})
        if not res:
            return

        var_name = res.get("variable_name", "Data")
        title = res.get("title") or f"Acceptance Control Chart of {var_name}"
        means = res.get("subgroup_means", [])
        if not means:
            return

        w = rect.width()
        h = rect.height()

        # Title
        painter.setPen(QColor("#111827"))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(20, 10, w - 40, 26), Qt.AlignmentFlag.AlignCenter, title)

        # Plot margins
        margin_left = 65
        margin_right = 145
        margin_top = 45
        margin_bottom = 75

        plot_left = margin_left
        plot_right = w - margin_right
        plot_top = margin_top
        plot_bottom = h - margin_bottom
        plot_w = plot_right - plot_left
        plot_h = plot_bottom - plot_top

        if plot_w < 80 or plot_h < 80:
            return

        # Reference values
        lsl = res.get("lsl")
        usl = res.get("usl")
        uacl = res.get("uacl")
        lacl = res.get("lacl")
        apl_u = res.get("apl_upper")
        apl_l = res.get("apl_lower")
        cl = res.get("center_line", 0.0)
        signals = set(res.get("test1_signals", []))

        # Y scale range
        vals_to_bound = list(means) + [cl]
        if lsl is not None:
            vals_to_bound.append(lsl)
        if usl is not None:
            vals_to_bound.append(usl)
        if uacl is not None:
            vals_to_bound.append(uacl)
        if lacl is not None:
            vals_to_bound.append(lacl)
        if apl_u is not None:
            vals_to_bound.append(apl_u)
        if apl_l is not None:
            vals_to_bound.append(apl_l)

        min_val = min(vals_to_bound)
        max_val = max(vals_to_bound)
        span = max_val - min_val
        if span <= 0:
            span = 1.0
        y_min = min_val - 0.10 * span
        y_max = max_val + 0.10 * span

        k = len(means)
        x_min = 0.5
        x_max = k + 0.5

        def to_screen_x(xv):
            return plot_left + (xv - x_min) / (x_max - x_min) * plot_w

        def to_screen_y(yv):
            return plot_bottom - (yv - y_min) / (y_max - y_min) * plot_h

        # Axes
        painter.setPen(QPen(QColor("#94A3B8"), 1))
        painter.drawLine(QPointF(plot_left, plot_bottom), QPointF(plot_right, plot_bottom))
        painter.drawLine(QPointF(plot_left, plot_top), QPointF(plot_left, plot_bottom))

        # Reference Lines
        ref_lines = []
        if usl is not None:
            ref_lines.append((usl, "USL", QColor("#DC2626"), Qt.PenStyle.DashLine, 1.5))
        if uacl is not None:
            ref_lines.append((uacl, "UACL", QColor("#DC2626"), Qt.PenStyle.SolidLine, 1.5))
        if apl_u is not None:
            ref_lines.append((apl_u, "APL", QColor("#9333EA"), Qt.PenStyle.DashDotLine, 1.0))
        ref_lines.append((cl, "Center", QColor("#16A34A"), Qt.PenStyle.SolidLine, 1.5))
        if apl_l is not None:
            ref_lines.append((apl_l, "APL", QColor("#9333EA"), Qt.PenStyle.DashDotLine, 1.0))
        if lacl is not None:
            ref_lines.append((lacl, "LACL", QColor("#DC2626"), Qt.PenStyle.SolidLine, 1.5))
        if lsl is not None:
            ref_lines.append((lsl, "LSL", QColor("#DC2626"), Qt.PenStyle.DashLine, 1.5))

        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        for y_val, label, color, style, width in ref_lines:
            sy = to_screen_y(y_val)
            painter.setPen(QPen(color, width, style))
            painter.drawLine(QPointF(plot_left, sy), QPointF(plot_right, sy))
            # Margin label
            painter.setPen(color)
            painter.drawText(QRectF(plot_right + 6, sy - 8, 130, 16), Qt.AlignmentFlag.AlignLeft, f"{label}={y_val:.4g}")

        # Connect points with line
        pts = [QPointF(to_screen_x(i + 1), to_screen_y(means[i])) for i in range(k)]
        painter.setPen(QPen(QColor("#2563EB"), 1.5, Qt.PenStyle.SolidLine))
        for i in range(k - 1):
            painter.drawLine(pts[i], pts[i + 1])

        # Draw Points
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        for i, pt in enumerate(pts, start=1):
            is_out = (i in signals)
            if is_out:
                painter.setPen(QPen(QColor("#DC2626"), 2))
                painter.setBrush(QBrush(QColor("#EF4444")))
                painter.drawEllipse(pt, 4.5, 4.5)
                # Draw flag '1'
                painter.setPen(QColor("#DC2626"))
                painter.drawText(QRectF(pt.x() - 10, pt.y() - 18, 20, 14), Qt.AlignmentFlag.AlignCenter, "1")
            else:
                painter.setPen(QPen(QColor("#1E40AF"), 1.5))
                painter.setBrush(QBrush(QColor("#3B82F6")))
                painter.drawEllipse(pt, 3.5, 3.5)

        # X-axis ticks
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))
        painter.setPen(QColor("#475569"))
        step = max(1, k // 10)
        for i in range(1, k + 1, step):
            sx = to_screen_x(i)
            painter.drawLine(QPointF(sx, plot_bottom), QPointF(sx, plot_bottom + 4))
            painter.drawText(QRectF(sx - 15, plot_bottom + 5, 30, 16), Qt.AlignmentFlag.AlignCenter, str(i))

        # X-axis label
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.drawText(QRectF(plot_left, plot_bottom + 22, plot_w, 20), Qt.AlignmentFlag.AlignCenter, "Subgroup")

        # Y-axis label
        painter.save()
        painter.translate(18, plot_top + plot_h / 2)
        painter.rotate(-90)
        painter.drawText(QRectF(-plot_h / 2, -12, plot_h, 24), Qt.AlignmentFlag.AlignCenter, "Sample Mean")
        painter.restore()

        # Bottom summary strip
        summary_y = h - 28
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))
        painter.setPen(QColor("#64748B"))
        summary_text = (
            f"Subgroup Size: {res.get('avg_subgroup_size', 0):.3g}  |  "
            f"σ: {res.get('stdev', 0.0):.4g} ({res.get('sigma_source', '')})  |  "
            f"δ (Acceptable Nonconforming): {res.get('delta', 0.001):g}  |  "
            f"α (Producer Risk): {res.get('alpha', 0.05):g}"
        )
        if res.get("cp") is not None:
            summary_text += f"  |  Cp: {res['cp']:.2f}"
        if res.get("cpk") is not None:
            summary_text += f"  |  Cpk: {res['cpk']:.2f}"
        painter.drawText(QRectF(margin_left, summary_y, w - margin_left - 20, 20), Qt.AlignmentFlag.AlignLeft, summary_text)
