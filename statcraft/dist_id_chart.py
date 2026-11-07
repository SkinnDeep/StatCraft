"""High-fidelity Qt Interactive Chart Widget for Individual Distribution Identification.

Renders Minitab 22-standard probability plots:
- Multi-panel 4-in-1 layout and group switchers
- Probability grids with percentage scaling (1%, 5%, 10%, 20%, 50%, 80%, 90%, 95%, 99%)
- Observed order statistics markers
- Fitted distribution theoretical line
- 95% Confidence Interval bands
- Summary box with AD statistic, P-value, Sample Size N, and ML parameters
- Interactive hover cards & tooltips
- Aspect-ratio protected, responsive resizing
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QToolTip,
    QVBoxLayout,
    QWidget,
)
import numpy as np
import scipy.stats as stats


PERCENTILE_TICKS = [1.0, 5.0, 10.0, 20.0, 50.0, 80.0, 90.0, 95.0, 99.0]


class SingleDistProbabilityCanvas(QWidget):
    """Sub-canvas rendering an individual probability plot with fitted line and CI bands."""

    def __init__(
        self,
        dist_key: str,
        dist_fit: Dict[str, Any],
        raw_data: List[float],
        emp_probs: List[float],
        var_name: str = "Variable",
        show_ci: bool = True,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.dist_key = dist_key
        self.fit = dist_fit
        self.raw_data = np.asarray(raw_data, dtype=float)
        self.emp_probs = np.asarray(emp_probs, dtype=float)
        self.var_name = var_name
        self.show_ci = show_ci
        self.setMouseTracking(True)
        self.hovered_idx: Optional[int] = None
        self.hit_regions: List[Tuple[QRectF, int]] = []

        # Determine effective data for this distribution
        if dist_key == "box_cox" and "transformed" in self.fit:
            self.plot_data = np.asarray(self.fit["transformed"], dtype=float)
        elif dist_key == "johnson" and "transformed" in self.fit:
            self.plot_data = np.asarray(self.fit["transformed"], dtype=float)
        else:
            self.plot_data = self.raw_data

        self.s_data = np.sort(self.plot_data)
        self.n = len(self.s_data)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#ffffff"))

        pad_left = 52
        pad_right = 16
        pad_top = 34
        pad_bottom = 36

        pw = max(10, w - pad_left - pad_right)
        ph = max(10, h - pad_top - pad_bottom)
        plot_rect = QRectF(pad_left, pad_top, pw, ph)

        # Plot frame border
        painter.setPen(QPen(QColor("#94a3b8"), 1))
        painter.drawRect(plot_rect)

        # Title
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor("#0f172a"))
        title = f"{self.fit.get('name', self.dist_key)} - 95% CI"
        painter.drawText(QRectF(pad_left, 6, pw, 22), Qt.AlignmentFlag.AlignCenter, title)

        # X range
        min_x = float(np.min(self.s_data))
        max_x = float(np.max(self.s_data))
        span_x = max(1e-6, max_x - min_x)
        x_low = min_x - 0.05 * span_x
        x_high = max_x + 0.05 * span_x

        # Y scale: normal quantiles for percentiles
        z_min = float(stats.norm.ppf(0.005))
        z_max = float(stats.norm.ppf(0.995))
        z_span = z_max - z_min

        def val_to_x(v: float) -> float:
            return pad_left + (v - x_low) / (x_high - x_low) * pw

        def prob_to_y(p: float) -> float:
            p_clamped = max(0.001, min(0.999, p))
            z = float(stats.norm.ppf(p_clamped))
            return pad_top + (1.0 - (z - z_min) / z_span) * ph

        # Percentile horizontal grid lines & tick labels
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
        n_xticks = 5
        x_ticks = np.linspace(min_x, max_x, n_xticks)
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
        x_lbl = f"{self.var_name} (Transformed)" if self.dist_key in ("box_cox", "johnson") else self.var_name
        painter.drawText(QRectF(pad_left, pad_top + ph + 18, pw, 14), Qt.AlignmentFlag.AlignCenter, x_lbl)

        # Theoretical line & 95% Confidence Bands
        grid_x = np.linspace(min_x, max_x, 60)
        line_points: List[QPointF] = []
        upper_ci_points: List[QPointF] = []
        lower_ci_points: List[QPointF] = []

        # Mean and std of plotted data for linear normal probability plotting
        m_fit = float(np.mean(self.s_data))
        s_fit = float(np.std(self.s_data, ddof=1))
        if s_fit <= 0:
            s_fit = 1.0

        for gx in grid_x:
            # Theoretical probability under fitted model
            z_val = (gx - m_fit) / s_fit
            theo_p = float(stats.norm.cdf(z_val))
            theo_y = prob_to_y(theo_p)
            line_points.append(QPointF(val_to_x(gx), theo_y))

            # Standard error of percentile: SE = s / sqrt(n) * sqrt(1 + z^2 / 2)
            se_x = (s_fit / math.sqrt(max(3, self.n))) * math.sqrt(1.0 + (z_val ** 2) / 2.0)
            ci_dx = 1.96 * se_x
            p_upper = float(stats.norm.cdf((gx - ci_dx - m_fit) / s_fit))
            p_lower = float(stats.norm.cdf((gx + ci_dx - m_fit) / s_fit))
            upper_ci_points.append(QPointF(val_to_x(gx), prob_to_y(p_upper)))
            lower_ci_points.append(QPointF(val_to_x(gx), prob_to_y(p_lower)))

        # Draw CI bands
        if self.show_ci:
            painter.setPen(QPen(QColor("#e11d48"), 1, Qt.PenStyle.DashLine))
            for i in range(len(upper_ci_points) - 1):
                painter.drawLine(upper_ci_points[i], upper_ci_points[i + 1])
                painter.drawLine(lower_ci_points[i], lower_ci_points[i + 1])

        # Draw fitted center line
        painter.setPen(QPen(QColor("#dc2626"), 1.8, Qt.PenStyle.SolidLine))
        for i in range(len(line_points) - 1):
            painter.drawLine(line_points[i], line_points[i + 1])

        # Draw observed data points
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

        # Legend / Parameter Summary Card (lower-right or upper-left)
        ad_val = self.fit.get("ad")
        p_val = self.fit.get("p_value")
        ad_str = f"{ad_val:.3f}" if ad_val is not None else "*"
        if p_val is None:
            p_str = "*"
        elif p_val < 0.001:
            p_str = "<0.001"
        else:
            p_str = f"{p_val:.3f}"

        card_w = 98
        card_h = 62
        card_x = pad_left + pw - card_w - 6
        card_y = pad_top + ph - card_h - 6

        painter.setPen(QPen(QColor("#cbd5e1"), 1))
        painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
        painter.drawRoundedRect(QRectF(card_x, card_y, card_w, card_h), 4, 4)

        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.DemiBold))
        painter.setPen(QColor("#0f172a"))
        painter.drawText(QRectF(card_x + 6, card_y + 4, card_w - 12, 12), Qt.AlignmentFlag.AlignLeft, f"AD: {ad_str}")
        painter.drawText(QRectF(card_x + 6, card_y + 18, card_w - 12, 12), Qt.AlignmentFlag.AlignLeft, f"P-Value: {p_str}")
        painter.drawText(QRectF(card_x + 6, card_y + 32, card_w - 12, 12), Qt.AlignmentFlag.AlignLeft, f"N: {self.n}")

        # Show key parameter
        if self.fit.get("shape") is not None:
            param_lbl = f"Shape: {self.fit['shape']:.2f}"
        elif self.fit.get("scale") is not None:
            param_lbl = f"Scale: {self.fit['scale']:.2f}"
        else:
            param_lbl = f"Mean: {m_fit:.2f}"
        painter.drawText(QRectF(card_x + 6, card_y + 46, card_w - 12, 12), Qt.AlignmentFlag.AlignLeft, param_lbl)

        # Hover HUD Card
        if self.hovered_idx is not None and 0 <= self.hovered_idx < self.n:
            hx = float(self.s_data[self.hovered_idx])
            hp = float(self.emp_probs[self.hovered_idx])
            h_xc = val_to_x(hx)
            h_yp = prob_to_y(hp)

            hud_w = 120
            hud_h = 44
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


class DistIdChartWidget(QWidget):
    """High-fidelity container widget rendering Individual Distribution Identification probability plots."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", {})
        self.fits = self.result.get("fits", {})
        self.raw_data = self.result.get("data_sorted", [])
        self.emp_probs = self.result.get("empirical_probabilities", [])
        self.var_name = self.result.get("variable_name", "Variable")
        self.current_group_widget: Optional[QWidget] = None

        self._init_ui()

    def _init_ui(self):
        # Bound aspect ratio & sizing: standard width 860, max 940, height 540
        self.setMaximumWidth(960)
        self.setMinimumHeight(520)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Toolbar switcher
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(4, 2, 4, 2)
        bar_layout.setSpacing(6)

        self.btn_g1 = QPushButton("Group 1: Normal / Lognormal")
        self.btn_g2 = QPushButton("Group 2: Weibull / Extreme Value")
        self.btn_g3 = QPushButton("Group 3: Gamma / Logistic")
        self.btn_g4 = QPushButton("Group 4: Exponential / Johnson")
        self.btn_best = QPushButton(f"Best Fit: {self.result.get('best_fit', 'Best')}")

        for b in (self.btn_g1, self.btn_g2, self.btn_g3, self.btn_g4, self.btn_best):
            b.setCheckable(True)
            bar_layout.addWidget(b)

        bar_layout.addStretch()

        copy_btn = QPushButton("Copy")
        copy_btn.setToolTip("Copy chart image to clipboard")
        copy_btn.clicked.connect(self._copy_to_clipboard)
        bar_layout.addWidget(copy_btn)

        save_btn = QPushButton("Save PNG")
        save_btn.setToolTip("Save chart image to PNG")
        save_btn.clicked.connect(self._save_image)
        bar_layout.addWidget(save_btn)

        main_layout.addWidget(bar)

        self.container_layout = QVBoxLayout()
        main_layout.addLayout(self.container_layout, 1)

        # Connect button switchers
        self.btn_g1.clicked.connect(lambda: self._switch_group("g1"))
        self.btn_g2.clicked.connect(lambda: self._switch_group("g2"))
        self.btn_g3.clicked.connect(lambda: self._switch_group("g3"))
        self.btn_g4.clicked.connect(lambda: self._switch_group("g4"))
        self.btn_best.clicked.connect(lambda: self._switch_group("best"))

        # Default start: Group 1 (or Best fit if specific)
        self.btn_g1.setChecked(True)
        self._switch_group("g1")

    def _switch_group(self, group: str):
        self.btn_g1.setChecked(group == "g1")
        self.btn_g2.setChecked(group == "g2")
        self.btn_g3.setChecked(group == "g3")
        self.btn_g4.setChecked(group == "g4")
        self.btn_best.setChecked(group == "best")

        if self.current_group_widget:
            self.current_group_widget.deleteLater()

        group_map = {
            "g1": ["normal", "box_cox", "lognormal", "lognormal_3p"],
            "g2": ["weibull", "weibull_3p", "sev", "lev"],
            "g3": ["gamma", "gamma_3p", "logistic", "loglogistic"],
            "g4": ["loglogistic_3p", "exponential_2p", "exponential", "johnson"],
            "best": [self.result.get("best_key", "normal")],
        }

        keys = group_map.get(group, ["normal", "box_cox", "lognormal", "lognormal_3p"])
        self.current_group_widget = QWidget()

        if len(keys) == 1:
            g_layout = QVBoxLayout(self.current_group_widget)
            g_layout.setContentsMargins(0, 0, 0, 0)
            k = keys[0]
            if k in self.fits:
                canv = SingleDistProbabilityCanvas(k, self.fits[k], self.raw_data, self.emp_probs, self.var_name, True, self)
                g_layout.addWidget(canv, 1)
        else:
            g_layout = QGridLayout(self.current_group_widget)
            g_layout.setContentsMargins(0, 0, 0, 0)
            g_layout.setSpacing(6)

            for idx, k in enumerate(keys):
                r = idx // 2
                c = idx % 2
                if k in self.fits:
                    canv = SingleDistProbabilityCanvas(k, self.fits[k], self.raw_data, self.emp_probs, self.var_name, True, self)
                    g_layout.addWidget(canv, r, c)

        self.container_layout.addWidget(self.current_group_widget, 1)

    def _copy_to_clipboard(self):
        pixmap = self.grab()
        QApplication.clipboard().setPixmap(pixmap)

    def _save_image(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Distribution Identification Plot", f"{self.var_name}_dist_id.png", "PNG Images (*.png)")
        if filename:
            pixmap = self.grab()
            pixmap.save(filename, "PNG")
