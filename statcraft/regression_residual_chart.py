"""Minitab-parity 4-in-1 Residual Diagnostic Plots for Regression Models.

Panels:
1. Normal Probability Plot of Residuals (with theoretical normal reference line)
2. Versus Fits (Fitted values vs Standardized Residuals with 0 reference line)
3. Histogram of Residuals (with normal distribution density fit)
4. Versus Order (Observation order vs Standardized Residuals)
"""
import math
import numpy as np
from scipy import stats
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from PySide6.QtWidgets import QWidget, QSizePolicy
from .graph_interaction import GraphInteractionMixin


class RegressionResidualChartWidget(GraphInteractionMixin, QWidget):
    """Publication-grade 4-in-1 residual diagnostic plots for multiple regression."""
    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.entry = entry if isinstance(entry, dict) else {}
        self.result = self.entry.get("result", self.entry)
        self.title = self.entry.get("title", "Residual Plots")
        self.response_name = self.result.get("response_name", "Y")

        self.setMinimumSize(680, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFont(QFont("Segoe UI", 9))

        self.residuals = [float(v) for v in self.result.get("residuals", []) if v is not None]
        self.fitted = [float(v) for v in self.result.get("fitted", []) if v is not None]
        self.std_resids = [float(v) for v in self.result.get("standardized_residuals", []) if v is not None]
        if not self.std_resids and self.residuals:
            s = float(self.result.get("residual_stdev", 1.0)) or 1.0
            self.std_resids = [r / s for r in self.residuals]

        self.n = len(self.residuals)
        self._init_graph_interaction()
        self.hit_regions = []

    def sizeHint(self):
        return QSize(920, 640)

    def minimumSizeHint(self):
        return QSize(680, 480)

    def paintEvent(self, event):
        if self.n < 3:
            p = QPainter(self)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Insufficient observations for residual diagnostics.")
            p.end()
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Detect theme background
        bg_col = QColor("#ffffff")
        text_col = QColor("#0f172a")
        grid_col = QColor("#e2e8f0")
        card_border = QColor("#cbd5e1")
        panel_bg = QColor("#fcfdfd")

        p.fillRect(self.rect(), bg_col)

        w = self.width()
        h = self.height()
        header_h = 36.0
        pad_x = 18.0
        pad_y = 12.0
        gap = 14.0

        # Title
        p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        p.setPen(text_col)
        title_text = f"Residual Plots for {self.response_name}"
        p.drawText(QRectF(pad_x, 6, w - 2 * pad_x, 26), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title_text)

        # 2x2 Grid Layout
        usable_w = w - 2 * pad_x - gap
        usable_h = h - header_h - pad_y - gap
        pw = usable_w / 2.0
        ph = usable_h / 2.0

        r_norm = QRectF(pad_x, header_h, pw, ph)
        r_fits = QRectF(pad_x + pw + gap, header_h, pw, ph)
        r_hist = QRectF(pad_x, header_h + ph + gap, pw, ph)
        r_ordr = QRectF(pad_x + pw + gap, header_h + ph + gap, pw, ph)

        self._draw_normal_plot(p, r_norm, panel_bg, card_border, text_col, grid_col)
        self._draw_versus_fits(p, r_fits, panel_bg, card_border, text_col, grid_col)
        self._draw_histogram(p, r_hist, panel_bg, card_border, text_col, grid_col)
        self._draw_versus_order(p, r_ordr, panel_bg, card_border, text_col, grid_col)

        p.end()

    def _draw_normal_plot(self, p: QPainter, rect: QRectF, bg, border, text_c, grid_c):
        p.setPen(QPen(border, 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 4.0, 4.0)

        # Title
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.setPen(QColor("#0369a1"))
        p.drawText(QRectF(rect.left() + 8, rect.top() + 4, rect.width() - 16, 18),
                   Qt.AlignmentFlag.AlignLeft, "Normal Probability Plot")

        margin_l, margin_r, margin_t, margin_b = 40.0, 16.0, 24.0, 30.0
        plot_rect = QRectF(rect.left() + margin_l, rect.top() + margin_t,
                           rect.width() - margin_l - margin_r, rect.height() - margin_t - margin_b)

        sorted_res = np.sort(np.asarray(self.std_resids, dtype=float))
        n = len(sorted_res)
        prob = (np.arange(1, n + 1) - 0.5) / n
        z_scores = stats.norm.ppf(prob)

        x_min, x_max = float(sorted_res[0]), float(sorted_res[-1])
        span_x = max(1e-4, x_max - x_min)
        x_min -= span_x * 0.08
        x_max += span_x * 0.08

        y_min, y_max = float(z_scores[0]), float(z_scores[-1])
        span_y = max(1e-4, y_max - y_min)
        y_min -= span_y * 0.08
        y_max += span_y * 0.08

        def to_screen(x_val, y_val):
            sx = plot_rect.left() + (x_val - x_min) / (x_max - x_min) * plot_rect.width()
            sy = plot_rect.bottom() - (y_val - y_min) / (y_max - y_min) * plot_rect.height()
            return QPointF(sx, sy)

        # Grid and axes
        p.setPen(QPen(grid_c, 0.8, Qt.PenStyle.DashLine))
        zero_x = to_screen(0.0, 0.0).x()
        if plot_rect.left() <= zero_x <= plot_rect.right():
            p.drawLine(QPointF(zero_x, plot_rect.top()), QPointF(zero_x, plot_rect.bottom()))
        zero_y = to_screen(0.0, 0.0).y()
        if plot_rect.top() <= zero_y <= plot_rect.bottom():
            p.drawLine(QPointF(plot_rect.left(), zero_y), QPointF(plot_rect.right(), zero_y))

        # Reference line (theoretical standard normal)
        p.setPen(QPen(QColor("#dc2626"), 1.2))
        pt1 = to_screen(x_min, x_min)
        pt2 = to_screen(x_max, x_max)
        p.drawLine(pt1, pt2)

        # Points
        p.setPen(QPen(QColor("#1e40af"), 0.8))
        p.setBrush(QColor("#3b82f6"))
        for x_val, y_val in zip(sorted_res, z_scores):
            pt = to_screen(x_val, y_val)
            if plot_rect.contains(pt):
                p.drawEllipse(pt, 3.0, 3.0)

        # Axis labels
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(text_c)
        p.drawText(QRectF(plot_rect.left(), rect.bottom() - 16, plot_rect.width(), 14),
                   Qt.AlignmentFlag.AlignCenter, "Standardized Residual")

    def _draw_versus_fits(self, p: QPainter, rect: QRectF, bg, border, text_c, grid_c):
        p.setPen(QPen(border, 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 4.0, 4.0)

        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.setPen(QColor("#0369a1"))
        p.drawText(QRectF(rect.left() + 8, rect.top() + 4, rect.width() - 16, 18),
                   Qt.AlignmentFlag.AlignLeft, "Versus Fits")

        margin_l, margin_r, margin_t, margin_b = 40.0, 16.0, 24.0, 30.0
        plot_rect = QRectF(rect.left() + margin_l, rect.top() + margin_t,
                           rect.width() - margin_l - margin_r, rect.height() - margin_t - margin_b)

        fits_arr = np.asarray(self.fitted, dtype=float)
        res_arr = np.asarray(self.std_resids, dtype=float)

        x_min, x_max = float(np.min(fits_arr)), float(np.max(fits_arr))
        span_x = max(1e-4, x_max - x_min)
        x_min -= span_x * 0.08
        x_max += span_x * 0.08

        y_min, y_max = float(np.min(res_arr)), float(np.max(res_arr))
        limit = max(2.5, abs(y_min), abs(y_max)) * 1.15
        y_min, y_max = -limit, limit

        def to_screen(x_val, y_val):
            sx = plot_rect.left() + (x_val - x_min) / (x_max - x_min) * plot_rect.width()
            sy = plot_rect.bottom() - (y_val - y_min) / (y_max - y_min) * plot_rect.height()
            return QPointF(sx, sy)

        # Zero reference line
        p.setPen(QPen(QColor("#94a3b8"), 1.0, Qt.PenStyle.DashLine))
        y0 = to_screen(0.0, 0.0).y()
        p.drawLine(QPointF(plot_rect.left(), y0), QPointF(plot_rect.right(), y0))

        # +/- 2.0 reference lines (unusual residual flags)
        p.setPen(QPen(QColor("#fca5a5"), 0.8, Qt.PenStyle.DotLine))
        p.drawLine(QPointF(plot_rect.left(), to_screen(0, 2.0).y()), QPointF(plot_rect.right(), to_screen(0, 2.0).y()))
        p.drawLine(QPointF(plot_rect.left(), to_screen(0, -2.0).y()), QPointF(plot_rect.right(), to_screen(0, -2.0).y()))

        # Scatter points
        for fit_v, res_v in zip(fits_arr, res_arr):
            pt = to_screen(fit_v, res_v)
            if plot_rect.contains(pt):
                if abs(res_v) > 2.0:
                    p.setPen(QPen(QColor("#991b1b"), 1.0))
                    p.setBrush(QColor("#ef4444"))
                    p.drawEllipse(pt, 3.8, 3.8)
                else:
                    p.setPen(QPen(QColor("#1e40af"), 0.8))
                    p.setBrush(QColor("#3b82f6"))
                    p.drawEllipse(pt, 3.0, 3.0)

        # Axis label
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(text_c)
        p.drawText(QRectF(plot_rect.left(), rect.bottom() - 16, plot_rect.width(), 14),
                   Qt.AlignmentFlag.AlignCenter, "Fitted Value")

    def _draw_histogram(self, p: QPainter, rect: QRectF, bg, border, text_c, grid_c):
        p.setPen(QPen(border, 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 4.0, 4.0)

        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.setPen(QColor("#0369a1"))
        p.drawText(QRectF(rect.left() + 8, rect.top() + 4, rect.width() - 16, 18),
                   Qt.AlignmentFlag.AlignLeft, "Histogram of Residuals")

        margin_l, margin_r, margin_t, margin_b = 40.0, 16.0, 24.0, 30.0
        plot_rect = QRectF(rect.left() + margin_l, rect.top() + margin_t,
                           rect.width() - margin_l - margin_r, rect.height() - margin_t - margin_b)

        res_arr = np.asarray(self.std_resids, dtype=float)
        n_bins = max(5, min(25, int(np.ceil(np.sqrt(len(res_arr))))))
        counts, bin_edges = np.histogram(res_arr, bins=n_bins)

        x_min, x_max = float(bin_edges[0]), float(bin_edges[-1])
        span_x = max(1e-4, x_max - x_min)
        x_min -= span_x * 0.08
        x_max += span_x * 0.08

        y_max = float(np.max(counts)) * 1.25 if len(counts) > 0 else 1.0

        def to_screen(x_val, y_val):
            sx = plot_rect.left() + (x_val - x_min) / (x_max - x_min) * plot_rect.width()
            sy = plot_rect.bottom() - (y_val / y_max) * plot_rect.height()
            return QPointF(sx, sy)

        # Draw bars
        p.setPen(QPen(QColor("#1d4ed8"), 0.9))
        p.setBrush(QColor("#93c5fd"))
        for i in range(len(counts)):
            b_left = bin_edges[i]
            b_right = bin_edges[i + 1]
            c = counts[i]
            pt_tl = to_screen(b_left, c)
            pt_br = to_screen(b_right, 0.0)
            bar_rect = QRectF(pt_tl.x(), pt_tl.y(), max(1.0, pt_br.x() - pt_tl.x() - 1.0), pt_br.y() - pt_tl.y())
            p.drawRect(bar_rect)

        # Overlaid normal curve
        mu, sigma = float(np.mean(res_arr)), float(np.std(res_arr)) or 1.0
        bin_width = float(bin_edges[1] - bin_edges[0])
        curve_pts = []
        xs = np.linspace(x_min, x_max, 60)
        for x_val in xs:
            pdf_val = stats.norm.pdf(x_val, mu, sigma)
            # Scale PDF to frequency
            freq_equiv = pdf_val * len(res_arr) * bin_width
            curve_pts.append(to_screen(x_val, freq_equiv))

        p.setPen(QPen(QColor("#dc2626"), 1.4))
        path = QPainterPath()
        if curve_pts:
            path.moveTo(curve_pts[0])
            for pt in curve_pts[1:]:
                path.lineTo(pt)
            p.drawPath(path)

        # Axis label
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(text_c)
        p.drawText(QRectF(plot_rect.left(), rect.bottom() - 16, plot_rect.width(), 14),
                   Qt.AlignmentFlag.AlignCenter, "Residual")

    def _draw_versus_order(self, p: QPainter, rect: QRectF, bg, border, text_c, grid_c):
        p.setPen(QPen(border, 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 4.0, 4.0)

        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.setPen(QColor("#0369a1"))
        p.drawText(QRectF(rect.left() + 8, rect.top() + 4, rect.width() - 16, 18),
                   Qt.AlignmentFlag.AlignLeft, "Versus Order")

        margin_l, margin_r, margin_t, margin_b = 40.0, 16.0, 24.0, 30.0
        plot_rect = QRectF(rect.left() + margin_l, rect.top() + margin_t,
                           rect.width() - margin_l - margin_r, rect.height() - margin_t - margin_b)

        n = len(self.std_resids)
        x_arr = np.arange(1, n + 1)
        res_arr = np.asarray(self.std_resids, dtype=float)

        x_min, x_max = 0.5, n + 0.5
        y_min, y_max = float(np.min(res_arr)), float(np.max(res_arr))
        limit = max(2.5, abs(y_min), abs(y_max)) * 1.15
        y_min, y_max = -limit, limit

        def to_screen(x_val, y_val):
            sx = plot_rect.left() + (x_val - x_min) / (x_max - x_min) * plot_rect.width()
            sy = plot_rect.bottom() - (y_val - y_min) / (y_max - y_min) * plot_rect.height()
            return QPointF(sx, sy)

        # Zero reference line
        p.setPen(QPen(QColor("#94a3b8"), 1.0, Qt.PenStyle.DashLine))
        y0 = to_screen(0.0, 0.0).y()
        p.drawLine(QPointF(plot_rect.left(), y0), QPointF(plot_rect.right(), y0))

        # Connecting line
        p.setPen(QPen(QColor("#60a5fa"), 1.0))
        pts = [to_screen(x_i, r_i) for x_i, r_i in zip(x_arr, res_arr)]
        for i in range(len(pts) - 1):
            p.drawLine(pts[i], pts[i + 1])

        # Points
        for x_i, r_i, pt in zip(x_arr, res_arr, pts):
            if abs(r_i) > 2.0:
                p.setPen(QPen(QColor("#991b1b"), 1.0))
                p.setBrush(QColor("#ef4444"))
                p.drawEllipse(pt, 3.8, 3.8)
            else:
                p.setPen(QPen(QColor("#1e40af"), 0.8))
                p.setBrush(QColor("#3b82f6"))
                p.drawEllipse(pt, 3.0, 3.0)

        # Axis label
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(text_c)
        p.drawText(QRectF(plot_rect.left(), rect.bottom() - 16, plot_rect.width(), 14),
                   Qt.AlignmentFlag.AlignCenter, "Observation Order")
