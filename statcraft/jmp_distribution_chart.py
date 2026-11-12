"""Interactive visual chart widget for JMP Distribution platform."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygonF
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame

from .jmp_panel import get_jmp_icon


from .snapshot_chart import SnapshotChartWidget
from .chart_theme import chart_painter


class SingleVariableDistributionCanvas(QWidget):
    """Canvas rendering combined Outlier Box Plot + Histogram + Normal Curve for one variable."""

    def __init__(self, var_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.var_data = var_data
        self.setMinimumSize(320, 360)
        self.setFont(QFont("Segoe UI", 9))

    def paintEvent(self, event):
        p = chart_painter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Clean background card
        p.fillRect(0, 0, w, h, QColor("#ffffff"))

        # Header strip
        p.fillRect(0, 0, w, 28, QColor("#f8fafc"))
        p.setPen(QPen(QColor("#e2e8f0"), 1))
        p.drawLine(0, 28, w, 28)

        # Red triangle icon
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#dc2626"))
        tri = QPolygonF([QPointF(10, 10), QPointF(18, 10), QPointF(14, 18)])
        p.drawPolygon(tri)

        # Variable title & modeling type badge
        p.setPen(QPen(QColor("#0f172a"), 1))
        font_hdr = QFont("Segoe UI", 9, QFont.Weight.Bold)
        p.setFont(font_hdr)
        v_name = self.var_data.get("variable", "Variable")
        v_type = self.var_data.get("type", "continuous")
        p.drawText(24, 19, v_name)

        font_norm = QFont("Segoe UI", 8.5)
        p.setFont(font_norm)

        margin_top = 40
        margin_bottom = 25
        margin_left = 65
        margin_right = 20

        plot_w = w - margin_left - margin_right
        plot_h = h - margin_top - margin_bottom

        if v_type == "continuous":
            self._paint_continuous(p, margin_left, margin_top, plot_w, plot_h)
        else:
            self._paint_categorical(p, margin_left, margin_top, plot_w, plot_h)

        p.end()

    def _paint_continuous(self, p: QPainter, x0: float, y0: float, pw: float, ph: float):
        var = self.var_data
        bin_counts = var.get("bin_counts", [])
        bin_edges = var.get("bin_edges", [])
        if not bin_edges or not bin_counts:
            return

        y_min = bin_edges[0]
        y_max = bin_edges[-1]
        y_span = y_max - y_min if (y_max - y_min) > 1e-9 else 1.0

        def val_to_y(val):
            # Higher value near top
            ratio = (val - y_min) / y_span
            return y0 + ph - (ratio * ph)

        max_count = max(bin_counts) if bin_counts else 1
        if max_count == 0:
            max_count = 1

        # Layout width division:
        # Tick numbers on far left [0..x0-8], Box plot [x0..x0+45], Histogram [x0+50..x0+pw]
        box_w = 38.0
        box_center_x = x0 + box_w / 2.0
        hist_x0 = x0 + box_w + 14.0
        hist_w = max(50.0, pw - box_w - 20.0)

        # Draw Y-Axis Ticks & Labels (left of axis line at x0)
        p.setPen(QPen(QColor("#cbd5e1"), 1))
        p.drawLine(int(x0), int(y0), int(x0), int(y0 + ph))

        num_ticks = 5
        p.setPen(QPen(QColor("#64748b"), 1))
        for i in range(num_ticks + 1):
            tv = y_min + (i / num_ticks) * y_span
            ty = val_to_y(tv)
            p.drawLine(int(x0 - 4), int(ty), int(x0), int(ty))
            txt = f"{tv:.2f}" if abs(tv) < 1000 else f"{tv:.1e}"
            p.drawText(QRectF(0, ty - 8, x0 - 8, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, txt)

        # 1. OUTLIER BOX PLOT (Vertical)
        q25 = var.get("q25", y_min)
        median = var.get("median", y_min)
        q75 = var.get("q75", y_max)
        lower_whisk = var.get("lower_whisker", y_min)
        upper_whisk = var.get("upper_whisker", y_max)

        y_q25 = val_to_y(q25)
        y_q75 = val_to_y(q75)
        y_med = val_to_y(median)
        y_lw = val_to_y(lower_whisk)
        y_uw = val_to_y(upper_whisk)

        # Whiskers line
        p.setPen(QPen(QColor("#0f172a"), 1.2))
        p.drawLine(int(box_center_x), int(y_lw), int(box_center_x), int(y_q25))
        p.drawLine(int(box_center_x), int(y_q75), int(box_center_x), int(y_uw))
        # Whisker caps
        cap_w = 8.0
        p.drawLine(int(box_center_x - cap_w), int(y_lw), int(box_center_x + cap_w), int(y_lw))
        p.drawLine(int(box_center_x - cap_w), int(y_uw), int(box_center_x + cap_w), int(y_uw))

        # IQR Box
        bw = 20.0
        p.setPen(QPen(QColor("#005a9e"), 1.5))
        p.setBrush(QColor("#e0f2fe"))
        p.drawRect(QRectF(box_center_x - bw / 2.0, y_q75, bw, y_q25 - y_q75))

        # Median Line
        p.setPen(QPen(QColor("#0369a1"), 2.0))
        p.drawLine(int(box_center_x - bw / 2.0), int(y_med), int(box_center_x + bw / 2.0), int(y_med))

        # Mean Diamond in Box Plot
        mean_v = var.get("mean", median)
        ci_l = var.get("ci_lower", q25)
        ci_u = var.get("ci_upper", q75)
        y_mean = val_to_y(mean_v)
        y_ci_l = val_to_y(ci_l)
        y_ci_u = val_to_y(ci_u)
        diamond = QPolygonF([
            QPointF(box_center_x, y_ci_u),
            QPointF(box_center_x + bw / 2.0 - 2, y_mean),
            QPointF(box_center_x, y_ci_l),
            QPointF(box_center_x - bw / 2.0 + 2, y_mean),
        ])
        p.setPen(QPen(QColor("#2563eb"), 1.2))
        p.setBrush(QColor(37, 99, 235, 40))
        p.drawPolygon(diamond)

        # Outlier points
        p.setPen(QPen(QColor("#dc2626"), 1))
        p.setBrush(QColor("#dc2626"))
        for out in var.get("outliers", []):
            oy = val_to_y(out)
            p.drawEllipse(QPointF(box_center_x, oy), 2.5, 2.5)

        # 2. HISTOGRAM BARS (Horizontal bars aligned to Y scale)
        p.setPen(QPen(QColor("#0284c7"), 1))
        p.setBrush(QColor("#e0f2fe"))

        for i, count in enumerate(bin_counts):
            edge_lo = bin_edges[i]
            edge_hi = bin_edges[i + 1]
            y_bar_top = val_to_y(edge_hi)
            y_bar_bot = val_to_y(edge_lo)
            bar_height = max(1.0, y_bar_bot - y_bar_top)
            bar_len = (count / max_count) * hist_w
            rect = QRectF(hist_x0, y_bar_top, bar_len, bar_height)
            p.drawRect(rect)

        # 3. OVERLAID FITTED NORMAL CURVE
        curve_x = var.get("curve_x", [])
        curve_y = var.get("curve_y", [])
        if curve_x and curve_y:
            p.setPen(QPen(QColor("#2563eb"), 2))
            pts = []
            for vx, count_est in zip(curve_x, curve_y):
                cy = val_to_y(vx)
                cx = hist_x0 + (count_est / max_count) * hist_w
                pts.append(QPointF(cx, cy))
            if len(pts) > 1:
                p.drawPolyline(pts)

        # Bottom Count Axis
        p.setPen(QPen(QColor("#64748b"), 1))
        p.drawText(QRectF(hist_x0, y0 + ph + 4, hist_w, 16), Qt.AlignmentFlag.AlignCenter, f"Count (Max: {max_count})")

    def _paint_categorical(self, p: QPainter, x0: float, y0: float, pw: float, ph: float):
        var = self.var_data
        freqs = var.get("frequencies", [])
        if not freqs:
            return

        total_n = var.get("n", 1)
        num_items = min(15, len(freqs))
        row_h = ph / num_items

        max_prob = max(f.get("prob", 0.0) for f in freqs[:num_items])
        if max_prob == 0:
            max_prob = 1.0

        label_w = 70.0
        bar_x0 = x0 + label_w + 10.0
        bar_max_w = pw - label_w - 60.0

        for i, f in enumerate(freqs[:num_items]):
            ry = y0 + i * row_h
            lvl = str(f.get("level", ""))
            cnt = f.get("count", 0)
            prob = f.get("prob", 0.0)

            # Level Label
            p.setPen(QPen(QColor("#0f172a"), 1))
            p.drawText(QRectF(x0, ry, label_w, row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, lvl[:12])

            # Bar
            bar_w = (prob / max_prob) * bar_max_w
            p.setPen(QPen(QColor("#0284c7"), 1))
            p.setBrush(QColor("#e0f2fe"))
            rect = QRectF(bar_x0, ry + 4, bar_w, max(4.0, row_h - 8))
            p.drawRect(rect)

            # Count & Prob text
            p.setPen(QPen(QColor("#475569"), 1))
            txt = f"{cnt} ({prob*100:.1f}%)"
            p.drawText(QRectF(bar_x0 + bar_w + 6, ry, 60, row_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, txt)


class JMPDistributionWidget(SnapshotChartWidget):
    """Container widget presenting one or more variable distribution cards side-by-side."""

    def __init__(self, entry_or_result: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(entry_or_result, parent)
        self.result = self.entry["result"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header title
        hdr = QWidget()
        hdr.setFixedHeight(34)
        hdr.setStyleSheet("background-color: #f1f5f9; border-bottom: 1px solid #cbd5e1;")
        h_layout = QHBoxLayout(hdr)
        h_layout.setContentsMargins(12, 4, 12, 4)
        lbl_title = QLabel(f"▼ Distributions - {self.result.get('title', '')}")
        lbl_title.setStyleSheet("font-size: 10pt; font-weight: bold; color: #005a9e;")
        h_layout.addWidget(lbl_title)
        h_layout.addStretch()
        layout.addWidget(hdr)

        # Horizontal Scroll Area for multi-column panels
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        container = QWidget()
        c_layout = QHBoxLayout(container)
        c_layout.setContentsMargins(12, 12, 12, 12)
        c_layout.setSpacing(16)

        for var in self.result.get("variables", []):
            card = QWidget()
            card.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px;")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(1, 1, 1, 1)
            canvas = SingleVariableDistributionCanvas(var, card)
            card_layout.addWidget(canvas)
            c_layout.addWidget(card)

        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
