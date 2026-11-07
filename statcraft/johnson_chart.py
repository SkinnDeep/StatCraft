"""High-fidelity Qt Interactive Chart Widget for Johnson Transformation.

Renders side-by-side Minitab 22-standard Normal Probability plots comparing Original vs. Transformed Data:
- Normal probability grids with percentage ticks (1%, 5%, 10%, 20%, 50%, 80%, 90%, 95%, 99%)
- Fitted normal lines & 95% Confidence Interval bands
- Prominent header card displaying the fitted Johnson transformation equation
- Summary cards with Mean, StDev, N, AD, and P-value
- Interactive hover HUD cards
- Aspect-ratio protected layout
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
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
import numpy as np
import scipy.stats as stats


PERCENTILE_TICKS = [1.0, 5.0, 10.0, 20.0, 50.0, 80.0, 90.0, 95.0, 99.0]


class SingleJohnsonProbabilityCanvas(QWidget):
    """Sub-canvas rendering an individual normal probability plot."""

    def __init__(
        self,
        title: str,
        data: List[float],
        emp_probs: List[float],
        ad_stat: float,
        p_val: float,
        mean: float,
        std: float,
        x_label: str = "Data",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.plot_title = title
        self.s_data = np.asarray(data, dtype=float)
        self.emp_probs = np.asarray(emp_probs, dtype=float)
        self.ad_stat = ad_stat
        self.p_val = p_val
        self.mean = mean
        self.std = max(1e-6, std)
        self.x_label = x_label
        self.n = len(self.s_data)

        self.setMouseTracking(True)
        self.hovered_idx: Optional[int] = None
        self.hit_regions: List[Tuple[QRectF, int]] = []

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#ffffff"))

        pad_left = 50
        pad_right = 14
        pad_top = 32
        pad_bottom = 36

        pw = max(10, w - pad_left - pad_right)
        ph = max(10, h - pad_top - pad_bottom)
        plot_rect = QRectF(pad_left, pad_top, pw, ph)

        painter.setPen(QPen(QColor("#94a3b8"), 1))
        painter.drawRect(plot_rect)

        # Title
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor("#0f172a"))
        painter.drawText(QRectF(pad_left, 6, pw, 20), Qt.AlignmentFlag.AlignCenter, self.plot_title)

        min_x = float(np.min(self.s_data))
        max_x = float(np.max(self.s_data))
        span_x = max(1e-6, max_x - min_x)
        x_low = min_x - 0.05 * span_x
        x_high = max_x + 0.05 * span_x

        z_min = float(stats.norm.ppf(0.005))
        z_max = float(stats.norm.ppf(0.995))
        z_span = z_max - z_min

        def val_to_x(v: float) -> float:
            return pad_left + (v - x_low) / (x_high - x_low) * pw

        def prob_to_y(p: float) -> float:
            p_clamped = max(0.001, min(0.999, p))
            z = float(stats.norm.ppf(p_clamped))
            return pad_top + (1.0 - (z - z_min) / z_span) * ph

        # Percentile horizontal grid lines
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Normal))
        for pt in PERCENTILE_TICKS:
            yp = prob_to_y(pt / 100.0)
            painter.setPen(QPen(QColor("#e2e8f0"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(pad_left, yp), QPointF(pad_left + pw, yp))
            painter.setPen(QColor("#64748b"))
            painter.drawText(QRectF(4, yp - 7, pad_left - 8, 14), Qt.AlignmentFlag.AlignRight, f"{int(pt) if pt.is_integer() else pt}")

        # Y-axis label
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
        painter.setPen(QColor("#334155"))
        painter.drawText(QRectF(4, pad_top - 18, 44, 14), Qt.AlignmentFlag.AlignLeft, "Percent")

        # X ticks
        x_ticks = np.linspace(min_x, max_x, 5)
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Normal))
        for xt in x_ticks:
            xc = val_to_x(xt)
            painter.setPen(QPen(QColor("#f1f5f9"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(xc, pad_top), QPointF(xc, pad_top + ph))
            painter.setPen(QColor("#64748b"))
            painter.drawText(QRectF(xc - 25, pad_top + ph + 4, 50, 14), Qt.AlignmentFlag.AlignCenter, f"{xt:.2f}")

        # X-axis label
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
        painter.setPen(QColor("#334155"))
        painter.drawText(QRectF(pad_left, pad_top + ph + 18, pw, 14), Qt.AlignmentFlag.AlignCenter, self.x_label)

        # Theoretical line & 95% CI bands
        grid_x = np.linspace(min_x, max_x, 50)
        line_points: List[QPointF] = []
        upper_ci_points: List[QPointF] = []
        lower_ci_points: List[QPointF] = []

        for gx in grid_x:
            z_val = (gx - self.mean) / self.std
            theo_p = float(stats.norm.cdf(z_val))
            line_points.append(QPointF(val_to_x(gx), prob_to_y(theo_p)))

            se_x = (self.std / math.sqrt(max(3, self.n))) * math.sqrt(1.0 + (z_val ** 2) / 2.0)
            ci_dx = 1.96 * se_x
            p_upper = float(stats.norm.cdf((gx - ci_dx - self.mean) / self.std))
            p_lower = float(stats.norm.cdf((gx + ci_dx - self.mean) / self.std))
            upper_ci_points.append(QPointF(val_to_x(gx), prob_to_y(p_upper)))
            lower_ci_points.append(QPointF(val_to_x(gx), prob_to_y(p_lower)))

        # Draw CI bands
        painter.setPen(QPen(QColor("#e11d48"), 1, Qt.PenStyle.DashLine))
        for i in range(len(upper_ci_points) - 1):
            painter.drawLine(upper_ci_points[i], upper_ci_points[i + 1])
            painter.drawLine(lower_ci_points[i], lower_ci_points[i + 1])

        # Draw Center Line
        painter.setPen(QPen(QColor("#dc2626"), 1.8, Qt.PenStyle.SolidLine))
        for i in range(len(line_points) - 1):
            painter.drawLine(line_points[i], line_points[i + 1])

        # Draw points
        self.hit_regions = []
        for i in range(self.n):
            vx = float(self.s_data[i])
            vp = float(self.emp_probs[i])
            px = val_to_x(vx)
            py = prob_to_y(vp)

            is_hov = (self.hovered_idx == i)
            pt_radius = 4.0 if is_hov else 2.5
            painter.setBrush(QBrush(QColor("#2563eb") if not is_hov else QColor("#ea580c")))
            painter.setPen(QPen(QColor("#1e3a8a"), 0.8))
            painter.drawEllipse(QPointF(px, py), pt_radius, pt_radius)
            self.hit_regions.append((QRectF(px - 5, py - 5, 10, 10), i))

        # Stat Summary Card
        card_w = 96
        card_h = 70
        card_x = pad_left + pw - card_w - 6
        card_y = pad_top + ph - card_h - 6

        painter.setPen(QPen(QColor("#cbd5e1"), 1))
        painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
        painter.drawRoundedRect(QRectF(card_x, card_y, card_w, card_h), 4, 4)

        p_str = "<0.001" if self.p_val < 0.001 else f"{self.p_val:.3f}"
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
        painter.setPen(QColor("#0f172a"))
        painter.drawText(QRectF(card_x + 6, card_y + 4, card_w - 12, 12), Qt.AlignmentFlag.AlignLeft, f"Mean: {self.mean:.2f}")
        painter.drawText(QRectF(card_x + 6, card_y + 17, card_w - 12, 12), Qt.AlignmentFlag.AlignLeft, f"StDev: {self.std:.2f}")
        painter.drawText(QRectF(card_x + 6, card_y + 30, card_w - 12, 12), Qt.AlignmentFlag.AlignLeft, f"N: {self.n}")
        painter.drawText(QRectF(card_x + 6, card_y + 43, card_w - 12, 12), Qt.AlignmentFlag.AlignLeft, f"AD: {self.ad_stat:.3f}")
        painter.drawText(QRectF(card_x + 6, card_y + 56, card_w - 12, 12), Qt.AlignmentFlag.AlignLeft, f"P-Value: {p_str}")

        # Hover HUD Card
        if self.hovered_idx is not None and 0 <= self.hovered_idx < self.n:
            hx = float(self.s_data[self.hovered_idx])
            hp = float(self.emp_probs[self.hovered_idx])
            h_xc = val_to_x(hx)
            h_yp = prob_to_y(hp)

            hud_w = 110
            hud_h = 42
            hud_x = h_xc + 10
            if hud_x + hud_w > w - 10:
                hud_x = h_xc - hud_w - 10
            hud_y = max(10, min(h_yp - hud_h / 2, h - hud_h - 10))

            painter.setPen(QPen(QColor("#94a3b8"), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255, 245)))
            painter.drawRoundedRect(QRectF(hud_x, hud_y, hud_w, hud_h), 4, 4)

            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
            painter.setPen(QColor("#0f172a"))
            painter.drawText(QRectF(hud_x + 6, hud_y + 4, hud_w - 12, 14), Qt.AlignmentFlag.AlignLeft, f"Value: {hx:.4f}")
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Normal))
            painter.setPen(QColor("#475569"))
            painter.drawText(QRectF(hud_x + 6, hud_y + 20, hud_w - 12, 14), Qt.AlignmentFlag.AlignLeft, f"Percent: {hp * 100:.2f}%")

    def mouseMoveEvent(self, event):
        pos = event.position() if hasattr(event, "position") else event.pos()
        old_hover = self.hovered_idx
        self.hovered_idx = None
        for rect, idx in self.hit_regions:
            if rect.contains(pos):
                self.hovered_idx = idx
                break
        if old_hover != self.hovered_idx:
            self.update()


class JohnsonChartWidget(QWidget):
    """High-fidelity container widget rendering Johnson Transformation before/after plots."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", {})
        self.var_name = self.result.get("variable_name", "Variable")
        self.orig = self.result.get("original", {})
        self.trans = self.result.get("transformed", {})
        self.emp_probs = self.result.get("empirical_probabilities", [])
        self.fn_str = self.result.get("function", "")
        self.family = self.result.get("family", "")

        self._init_ui()

    def _init_ui(self):
        # Aspect ratio bound
        self.setMaximumWidth(920)
        self.setMinimumHeight(480)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Header Info Banner
        hdr = QWidget()
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(8, 6, 8, 6)

        lbl = QLabel(f"<b>Johnson Transformation Function ({self.family}):</b> &nbsp; <code>{self.fn_str}</code>")
        lbl.setStyleSheet("color: #0f172a; font-size: 11px;")
        hdr_layout.addWidget(lbl)
        hdr_layout.addStretch()

        copy_btn = QPushButton("Copy")
        copy_btn.setToolTip("Copy chart image to clipboard")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        hdr_layout.addWidget(copy_btn)

        save_btn = QPushButton("Save PNG")
        save_btn.setToolTip("Save chart image to PNG")
        save_btn.clicked.connect(self._save_image)
        hdr_layout.addWidget(save_btn)

        main_layout.addWidget(hdr)

        # 1x2 Grid comparing Original vs Transformed
        grid_widget = QWidget()
        g_layout = QGridLayout(grid_widget)
        g_layout.setContentsMargins(0, 0, 0, 0)
        g_layout.setSpacing(8)

        canv_orig = SingleJohnsonProbabilityCanvas(
            title=f"Original Data ({self.var_name})",
            data=self.orig.get("sorted_data", []),
            emp_probs=self.emp_probs,
            ad_stat=self.orig.get("ad", 0.0),
            p_val=self.orig.get("p_value", 0.0),
            mean=self.orig.get("mean", 0.0),
            std=self.orig.get("std", 1.0),
            x_label=self.var_name,
            parent=self,
        )
        g_layout.addWidget(canv_orig, 0, 0)

        canv_trans = SingleJohnsonProbabilityCanvas(
            title="Transformed Data",
            data=self.trans.get("sorted_data", []),
            emp_probs=self.emp_probs,
            ad_stat=self.trans.get("ad", 0.0),
            p_val=self.trans.get("p_value", 0.0),
            mean=self.trans.get("mean", 0.0),
            std=self.trans.get("std", 1.0),
            x_label="Transformed Variable (Z)",
            parent=self,
        )
        g_layout.addWidget(canv_trans, 0, 1)

        main_layout.addWidget(grid_widget, 1)

    def _copy_to_clipboard(self):
        pixmap = self.grab()
        QApplication.clipboard().setPixmap(pixmap)

    def _save_image(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Johnson Transformation Plot", f"{self.var_name}_johnson.png", "PNG Images (*.png)")
        if filename:
            pixmap = self.grab()
            pixmap.save(filename, "PNG")
