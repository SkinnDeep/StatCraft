"""Interactive Qt Chart Widget for JMP Fit Y by X (Bivariate, Oneway Means Diamonds, Contingency Mosaic)."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget, QHBoxLayout, QCheckBox

from .graph_interaction import GraphInteractionMixin

INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
GRID = "#eef1f4"
CARD_BG = "#f8f9fa"
LINE_COLOR = "#0284c7"
CI_COLOR = "#38bdf8"
ELLIPSE_95_COLOR = "#e11d48"
ELLIPSE_50_COLOR = "#6366f1"
SMOOTHER_COLOR = "#10b981"
DIAMOND_FILL = "#06b6d4"
DIAMOND_STROKE = "#0891b2"

PALETTE = [
    "#3b82f6", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6",
    "#06b6d4", "#f97316", "#14b8a6", "#6366f1", "#84cc16"
]


class FitYByXChartWidget(GraphInteractionMixin, QWidget):
    """High-fidelity vector visualization for JMP Fit Y by X platform."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(object)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", entry)
        self.platform = self.result.get("platform", "bivariate")
        self.panels: List[Dict[str, Any]] = []
        self.setMouseTracking(True)
        self.setMinimumSize(820, 560)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Interactive overlay toggles
        self.show_line = True
        self.show_ci = True
        self.show_ellipse_95 = True
        self.show_ellipse_50 = True
        self.show_smoother = False
        self.show_diamonds = True
        self.show_quantiles = True

        self._hover_info = ""

    def sizeHint(self) -> QSize:
        return QSize(880, 600)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#ffffff"))

        # Render Header Bar
        header_h = self._draw_header(painter, w)

        # Plot Canvas Area
        if self.platform == "oneway":
            # Reserve space on right for signature JMP Tukey-Kramer comparison circles
            canvas_rect = QRectF(75, header_h + 15, max(200.0, w - 245.0), max(100.0, h - header_h - 75.0))
            circles_rect = QRectF(w - 155, header_h + 15, 135, max(100.0, h - header_h - 75.0))
            self._draw_oneway(painter, canvas_rect, circles_rect)
        elif self.platform == "bivariate":
            canvas_rect = QRectF(75, header_h + 15, max(200.0, w - 105.0), max(100.0, h - header_h - 75.0))
            self._draw_bivariate(painter, canvas_rect)
        elif self.platform == "contingency":
            canvas_rect = QRectF(75, header_h + 15, max(200.0, w - 145.0), max(100.0, h - header_h - 75.0))
            self._draw_contingency(painter, canvas_rect)

    def _draw_header(self, painter: QPainter, w: int) -> int:
        title = self.result.get("title", "Fit Y by X")
        y_name = self.result.get("y_name", "Y")
        x_name = self.result.get("x_name", "X")

        # Signature JMP Red Triangle dropdown indicator
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#dc2626")))
        tri_path = QPainterPath()
        tri_path.moveTo(20, 16)
        tri_path.lineTo(32, 16)
        tri_path.lineTo(26, 26)
        tri_path.closeSubpath()
        painter.drawPath(tri_path)

        painter.setPen(QColor(INK))
        font_title = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(font_title)
        painter.drawText(38, 25, title)

        # Summary Pills
        painter.setFont(QFont("Segoe UI", 9))
        pills = []
        if self.platform == "bivariate":
            r_sq = self.result.get("r_sq", 0.0)
            p_val = self.result.get("anova", {}).get("p_val", 1.0)
            rmse = self.result.get("rmse", 0.0)
            pills = [
                f"R² = {r_sq:.4f}",
                f"RMSE = {rmse:.4f}",
                f"Prob > F = {p_val:.4f}" if p_val >= 0.0001 else "Prob > F < 0.0001",
                self.result.get("equation", "")
            ]
        elif self.platform == "oneway":
            f_ratio = self.result.get("anova", {}).get("f_ratio", 0.0)
            p_val = self.result.get("anova", {}).get("p_val", 1.0)
            s_pooled = self.result.get("s_pooled", 0.0)
            pills = [
                f"F Ratio = {f_ratio:.2f}",
                f"Prob > F = {p_val:.4f}" if p_val >= 0.0001 else "Prob > F < 0.0001",
                f"Pooled SD = {s_pooled:.4f}",
                "Means Diamonds (95% CI)"
            ]
        elif self.platform == "contingency":
            chi2 = self.result.get("chi2", 0.0)
            p_val = self.result.get("p_chi2", 1.0)
            df = self.result.get("df", 1)
            pills = [
                f"Pearson χ² = {chi2:.3f}",
                f"DF = {df}",
                f"Prob > χ² = {p_val:.4f}" if p_val >= 0.0001 else "Prob > χ² < 0.0001",
                "Mosaic Plot"
            ]

        cx = 20
        y_pos = 50
        for p in pills:
            if not p:
                continue
            text_rect = painter.fontMetrics().boundingRect(p)
            pw = text_rect.width() + 16
            ph = 22
            pill_rect = QRectF(cx, y_pos - 15, pw, ph)
            painter.setBrush(QBrush(QColor("#f1f5f9")))
            painter.setPen(QPen(QColor(BORDER), 1))
            painter.drawRoundedRect(pill_rect, 6, 6)

            painter.setPen(QColor(INK))
            painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, p)
            cx += pw + 8

        # Divider line
        painter.setPen(QPen(QColor("#e2e8f0"), 1))
        painter.drawLine(20, y_pos + 18, w - 20, y_pos + 18)
        return y_pos + 22

    def _draw_bivariate(self, painter: QPainter, rect: QRectF):
        pts = self.result.get("points", {})
        xs = pts.get("x", [])
        ys = pts.get("y", [])
        if not xs or not ys:
            return

        # Determine plotting ranges
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        # Include ellipses and line in ranges
        line_fit = self.result.get("line_fit", {})
        if line_fit.get("y"):
            y_min = min(y_min, min(line_fit["y"]))
            y_max = max(y_max, max(line_fit["y"]))

        ellipses = self.result.get("ellipses", {})
        for k in ("ellipse_95", "ellipse_50"):
            e = ellipses.get(k, {})
            if e.get("x") and e.get("y"):
                x_min = min(x_min, min(e["x"]))
                x_max = max(x_max, max(e["x"]))
                y_min = min(y_min, min(e["y"]))
                y_max = max(y_max, max(e["y"]))

        # Margins
        dx = (x_max - x_min) if x_max > x_min else 1.0
        dy = (y_max - y_min) if y_max > y_min else 1.0
        x_min -= 0.05 * dx
        x_max += 0.05 * dx
        y_min -= 0.08 * dy
        y_max += 0.08 * dy

        def map_x(val):
            return rect.left() + (val - x_min) / (x_max - x_min) * rect.width()

        def map_y(val):
            return rect.bottom() - (val - y_min) / (y_max - y_min) * rect.height()

        # Draw Grid & Axes
        self._draw_grid_and_axes(painter, rect, x_min, x_max, y_min, y_max)

        # 0. Grand Mean Line (JMP Fit Mean)
        y_mean = float(np.mean(ys))
        painter.setPen(QPen(QColor("#64748b"), 1.1, Qt.PenStyle.DashLine))
        y_gm = map_y(y_mean)
        painter.drawLine(rect.left(), y_gm, rect.right(), y_gm)
        painter.setFont(QFont("Segoe UI", 7.5))
        painter.setPen(QColor("#64748b"))
        painter.drawText(rect.right() - 78, y_gm - 4, f"Mean: {y_mean:.2f}")

        # 1. Confidence Band Region
        if self.show_ci:
            ci = self.result.get("ci_band", {})
            c_x = ci.get("x", [])
            c_low = ci.get("lower", [])
            c_high = ci.get("upper", [])
            if c_x and c_low and c_high:
                path = QPainterPath()
                path.moveTo(map_x(c_x[0]), map_y(c_high[0]))
                for gx, gy in zip(c_x[1:], c_high[1:]):
                    path.lineTo(map_x(gx), map_y(gy))
                for gx, gy in zip(reversed(c_x), reversed(c_low)):
                    path.lineTo(map_x(gx), map_y(gy))
                path.closeSubpath()
                painter.fillPath(path, QBrush(QColor(56, 189, 248, 45)))

        # 2. Bivariate Density Ellipses
        if self.show_ellipse_95:
            e95 = ellipses.get("ellipse_95", {})
            if e95.get("x") and e95.get("y"):
                path95 = QPainterPath()
                path95.moveTo(map_x(e95["x"][0]), map_y(e95["y"][0]))
                for ex, ey in zip(e95["x"][1:], e95["y"][1:]):
                    path95.lineTo(map_x(ex), map_y(ey))
                path95.closeSubpath()
                painter.setPen(QPen(QColor(ELLIPSE_95_COLOR), 1.8, Qt.PenStyle.DashLine))
                painter.setBrush(QBrush(QColor(225, 29, 72, 20)))
                painter.drawPath(path95)

        if self.show_ellipse_50:
            e50 = ellipses.get("ellipse_50", {})
            if e50.get("x") and e50.get("y"):
                path50 = QPainterPath()
                path50.moveTo(map_x(e50["x"][0]), map_y(e50["y"][0]))
                for ex, ey in zip(e50["x"][1:], e50["y"][1:]):
                    path50.lineTo(map_x(ex), map_y(ey))
                path50.closeSubpath()
                painter.setPen(QPen(QColor(ELLIPSE_50_COLOR), 1.6, Qt.PenStyle.DashDotLine))
                painter.setBrush(QBrush(QColor(99, 102, 241, 25)))
                painter.drawPath(path50)

        # 3. Fitted Regression Line
        if self.show_line and line_fit.get("x") and line_fit.get("y"):
            lx = line_fit["x"]
            ly = line_fit["y"]
            painter.setPen(QPen(QColor(LINE_COLOR), 2.2))
            for i in range(len(lx) - 1):
                painter.drawLine(QPointF(map_x(lx[i]), map_y(ly[i])), QPointF(map_x(lx[i+1]), map_y(ly[i+1])))

        # 4. Smoother (Spline/Kernel)
        if self.show_smoother:
            sm = self.result.get("smoother", {})
            sx = sm.get("x", [])
            sy = sm.get("y", [])
            if sx and sy:
                painter.setPen(QPen(QColor(SMOOTHER_COLOR), 2.0))
                for i in range(len(sx) - 1):
                    painter.drawLine(QPointF(map_x(sx[i]), map_y(sy[i])), QPointF(map_x(sx[i+1]), map_y(sy[i+1])))

        # 5. Scatter Data Points
        painter.setPen(QPen(QColor("#0f172a"), 1.2))
        painter.setBrush(QBrush(QColor("#0284c7")))
        pt_radius = 4.0
        for px, py in zip(xs, ys):
            painter.drawEllipse(QPointF(map_x(px), map_y(py)), pt_radius, pt_radius)

        # 6. Interactive Legend Pill Box at Bottom Right
        leg_w = 260
        leg_h = 28
        leg_rect = QRectF(rect.right() - leg_w, rect.bottom() - leg_h - 8, leg_w, leg_h)
        painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRoundedRect(leg_rect, 6, 6)
        painter.setFont(QFont("Segoe UI", 8))

        # Legend entries
        # Line
        painter.setPen(QPen(QColor(LINE_COLOR), 2))
        painter.drawLine(leg_rect.left() + 10, leg_rect.center().y(), leg_rect.left() + 25, leg_rect.center().y())
        painter.setPen(QColor(INK))
        painter.drawText(leg_rect.left() + 30, leg_rect.center().y() + 4, "Linear Fit")

        # 95% Ellipse
        painter.setPen(QPen(QColor(ELLIPSE_95_COLOR), 1.5, Qt.PenStyle.DashLine))
        painter.drawLine(leg_rect.left() + 90, leg_rect.center().y(), leg_rect.left() + 105, leg_rect.center().y())
        painter.setPen(QColor(INK))
        painter.drawText(leg_rect.left() + 110, leg_rect.center().y() + 4, "95% Ellipse")

        # 50% Ellipse
        painter.setPen(QPen(QColor(ELLIPSE_50_COLOR), 1.5, Qt.PenStyle.DashDotLine))
        painter.drawLine(leg_rect.left() + 175, leg_rect.center().y(), leg_rect.left() + 190, leg_rect.center().y())
        painter.setPen(QColor(INK))
        painter.drawText(leg_rect.left() + 195, leg_rect.center().y() + 4, "50% Ellipse")

    def _draw_oneway(self, painter: QPainter, rect: QRectF, circles_rect: Optional[QRectF] = None):
        g_stats = self.result.get("group_stats", [])
        diamonds = self.result.get("diamonds", [])
        grand_mean = self.result.get("grand_mean", 0.0)
        if not g_stats:
            return

        k = len(g_stats)
        # Determine Y range
        all_vals = []
        for g in g_stats:
            all_vals.extend(g.get("values", []))
            all_vals.append(g.get("ci_lower", g.get("mean", 0.0)))
            all_vals.append(g.get("ci_upper", g.get("mean", 0.0)))

        y_min = min(all_vals)
        y_max = max(all_vals)
        dy = (y_max - y_min) if y_max > y_min else 1.0
        y_min -= 0.1 * dy
        y_max += 0.1 * dy

        def map_y(val):
            return rect.bottom() - (val - y_min) / (y_max - y_min) * rect.height()

        # Draw Grid & Y Axis
        self._draw_grid_and_axes(painter, rect, 0, k, y_min, y_max, is_categorical_x=True)

        col_w = rect.width() / k

        # 1. Grand Mean dashed line
        painter.setPen(QPen(QColor("#64748b"), 1.2, Qt.PenStyle.DashLine))
        y_gm = map_y(grand_mean)
        painter.drawLine(rect.left(), y_gm, rect.right(), y_gm)
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#64748b"))
        painter.drawText(rect.right() - 85, y_gm - 4, f"Grand Mean: {grand_mean:.2f}")

        # 2. Draw Groups: Points and Means Diamonds
        for i, (g, diam) in enumerate(zip(g_stats, diamonds)):
            cx = rect.left() + (i + 0.5) * col_w
            vals = g.get("values", [])

            # Quantile box / span
            if self.show_quantiles:
                q25_y = map_y(g.get("q25", g["mean"]))
                q75_y = map_y(g.get("q75", g["mean"]))
                qmed_y = map_y(g.get("median", g["mean"]))
                qmin_y = map_y(g.get("min", g["mean"]))
                qmax_y = map_y(g.get("max", g["mean"]))

                # Whisker line
                painter.setPen(QPen(QColor("#cbd5e1"), 1.5))
                painter.drawLine(cx, qmin_y, cx, qmax_y)

                # Quantile box
                box_w = min(col_w * 0.35, 40)
                box_rect = QRectF(cx - box_w / 2, q75_y, box_w, q25_y - q75_y)
                painter.setBrush(QBrush(QColor(241, 245, 249, 180)))
                painter.setPen(QPen(QColor("#94a3b8"), 1))
                painter.drawRect(box_rect)

                # Median line
                painter.setPen(QPen(QColor("#475569"), 1.5))
                painter.drawLine(cx - box_w / 2, qmed_y, cx + box_w / 2, qmed_y)

            # Jittered Data Points
            rng = np.random.RandomState(42 + i)
            jitter_span = min(col_w * 0.3, 30)
            painter.setPen(QPen(QColor("#1e293b"), 1))
            painter.setBrush(QBrush(QColor(PALETTE[i % len(PALETTE)])))
            for v in vals:
                jx = cx + (rng.rand() - 0.5) * jitter_span
                jy = map_y(v)
                painter.drawEllipse(QPointF(jx, jy), 3.5, 3.5)

            # Signature JMP Means Diamond
            if self.show_diamonds:
                ci_high_y = map_y(diam["ci_upper"])
                ci_low_y = map_y(diam["ci_lower"])
                mean_y = map_y(diam["mean"])
                dw = min(col_w * 0.55, 65)

                diamond_path = QPainterPath()
                diamond_path.moveTo(cx - dw, mean_y)      # Left tip
                diamond_path.lineTo(cx, ci_high_y)        # Top vertex (95% CI Upper)
                diamond_path.lineTo(cx + dw, mean_y)      # Right tip
                diamond_path.lineTo(cx, ci_low_y)         # Bottom vertex (95% CI Lower)
                diamond_path.closeSubpath()

                # Shaded translucent cyan fill
                painter.setBrush(QBrush(QColor(6, 182, 212, 70)))
                painter.setPen(QPen(QColor(DIAMOND_STROKE), 1.8))
                painter.drawPath(diamond_path)

                # Center mean horizontal line through diamond
                painter.setPen(QPen(QColor("#0e7490"), 2))
                painter.drawLine(cx - dw, mean_y, cx + dw, mean_y)

                # Signature JMP Overlap Lines (at 1/sqrt(2) of CI half-height)
                ci_half = abs(ci_high_y - mean_y)
                overlap_h = ci_half / math.sqrt(2)
                overlap_w = dw * (1.0 - (1.0 / math.sqrt(2)))
                painter.setPen(QPen(QColor("#0891b2"), 1.2, Qt.PenStyle.DashLine))
                painter.drawLine(cx - overlap_w, mean_y - overlap_h, cx + overlap_w, mean_y - overlap_h)
                painter.drawLine(cx - overlap_w, mean_y + overlap_h, cx + overlap_w, mean_y + overlap_h)

            # X Axis Category Label
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            painter.setPen(QColor(INK))
            lvl_text = str(g["level"])
            lbl_rect = QRectF(rect.left() + i * col_w, rect.bottom() + 6, col_w, 20)
            painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, lvl_text)

            # N count label
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QColor(MUTED))
            n_rect = QRectF(rect.left() + i * col_w, rect.bottom() + 26, col_w, 18)
            painter.drawText(n_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, f"N={g['n']}")

        # 3. Signature JMP Comparison Circles (Tukey-Kramer HSD)
        if circles_rect and circles_rect.width() > 50:
            c_center_x = circles_rect.center().x()

            # Comparison Circles Header
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(circles_rect.left(), circles_rect.top() - 14, circles_rect.width(), 16),
                             Qt.AlignmentFlag.AlignCenter, "All Pairs (Tukey)")

            for idx, (g, diam) in enumerate(zip(g_stats, diamonds)):
                cy = map_y(diam["mean"])
                ci_top_y = map_y(diam["ci_upper"])
                radius = max(6.0, abs(cy - ci_top_y))

                # Highlight primary group with horizontal tangent bounds
                is_selected = (idx == 0)
                if is_selected:
                    painter.setPen(QPen(QColor("#dc2626"), 1.8))
                    painter.setBrush(QBrush(QColor(220, 38, 38, 25)))
                    painter.drawEllipse(QPointF(c_center_x, cy), radius, radius)

                    painter.setPen(QPen(QColor("#dc2626"), 1.0, Qt.PenStyle.DotLine))
                    painter.drawLine(rect.left(), cy - radius, circles_rect.right(), cy - radius)
                    painter.drawLine(rect.left(), cy + radius, circles_rect.right(), cy + radius)
                else:
                    painter.setPen(QPen(QColor("#64748b"), 1.2))
                    painter.setBrush(QBrush(QColor(100, 116, 139, 15)))
                    painter.drawEllipse(QPointF(c_center_x, cy), radius, radius)

                painter.setFont(QFont("Segoe UI", 7.5))
                painter.setPen(QColor("#dc2626" if is_selected else MUTED))
                painter.drawText(circles_rect.left() + 2, cy + 4, str(g["level"]))

    def _draw_contingency(self, painter: QPainter, rect: QRectF):
        tiles = self.result.get("mosaic_tiles", [])
        x_levels = self.result.get("x_levels", [])
        y_levels = self.result.get("y_levels", [])
        if not tiles:
            return

        # Color map for Y levels
        y_colors = {lvl: QColor(PALETTE[idx % len(PALETTE)]) for idx, lvl in enumerate(y_levels)}

        # Draw Mosaic Tiles
        for t in tiles:
            tx = rect.left() + t["x0"] * rect.width()
            ty = rect.bottom() - (t["y0"] + t["height"]) * rect.height()
            tw = t["width"] * rect.width()
            th = t["height"] * rect.height()
            tile_rect = QRectF(tx, ty, tw, th)

            fill_c = y_colors.get(t["y_level"], QColor("#3b82f6"))
            painter.setBrush(QBrush(fill_c))
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.drawRoundedRect(tile_rect, 3, 3)

            # Cell text if tile is big enough
            if tw > 45 and th > 28:
                painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                painter.setPen(QColor("#ffffff"))
                cnt_str = f"{t['count']}"
                pct_str = f"{t['col_pct']:.1f}%"
                painter.drawText(tile_rect.adjusted(2, 4, -2, -th/2), Qt.AlignmentFlag.AlignCenter, cnt_str)
                painter.setFont(QFont("Segoe UI", 7))
                painter.drawText(tile_rect.adjusted(2, th/2 - 2, -2, -4), Qt.AlignmentFlag.AlignCenter, pct_str)

        # Draw X Category Axis Labels at bottom
        # Group tiles by x_level to find x positions
        seen_x = set()
        for t in tiles:
            xl = t["x_level"]
            if xl not in seen_x:
                seen_x.add(xl)
                tx = rect.left() + t["x0"] * rect.width()
                tw = t["width"] * rect.width()
                painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
                painter.setPen(QColor(INK))
                painter.drawText(QRectF(tx, rect.bottom() + 6, tw, 20), Qt.AlignmentFlag.AlignCenter, xl)
                painter.setFont(QFont("Segoe UI", 8))
                painter.setPen(QColor(MUTED))
                painter.drawText(QRectF(tx, rect.bottom() + 24, tw, 18), Qt.AlignmentFlag.AlignCenter, f"n={t['col_total']}")

        # Legend on right side for Y categories
        leg_x = rect.right() + 15
        leg_y = rect.top() + 20
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(INK))
        painter.drawText(leg_x, leg_y, self.result.get("y_name", "Y"))
        leg_y += 18

        for idx, yl in enumerate(y_levels):
            c = y_colors.get(yl, QColor("#3b82f6"))
            painter.setBrush(QBrush(c))
            painter.setPen(QPen(QColor(BORDER), 1))
            painter.drawRoundedRect(QRectF(leg_x, leg_y, 14, 14), 3, 3)

            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QColor(INK))
            painter.drawText(leg_x + 22, leg_y + 11, str(yl))
            leg_y += 22

    def _draw_grid_and_axes(self, painter: QPainter, rect: QRectF, x_min: float, x_max: float, y_min: float, y_max: float, is_categorical_x: bool = False):
        # Outer Border
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        # Horizontal Grid Lines & Y Axis Ticks
        n_ticks_y = 6
        y_step = (y_max - y_min) / n_ticks_y if n_ticks_y > 0 else 1.0
        painter.setFont(QFont("Segoe UI", 8))

        for i in range(n_ticks_y + 1):
            val = y_min + i * y_step
            py = rect.bottom() - (val - y_min) / (y_max - y_min) * rect.height()

            # Grid line
            painter.setPen(QPen(QColor(GRID), 1))
            painter.drawLine(rect.left(), py, rect.right(), py)

            # Tick & Label
            painter.setPen(QPen(QColor(BORDER), 1))
            painter.drawLine(rect.left() - 4, py, rect.left(), py)

            painter.setPen(QColor(MUTED))
            val_str = f"{val:.2f}" if abs(val) < 100 else f"{val:.1f}"
            lbl_rect = QRectF(rect.left() - 65, py - 9, 58, 18)
            painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, val_str)

        # Vertical Grid Lines (for numeric X)
        if not is_categorical_x:
            n_ticks_x = 6
            x_step = (x_max - x_min) / n_ticks_x if n_ticks_x > 0 else 1.0
            for i in range(n_ticks_x + 1):
                val = x_min + i * x_step
                px = rect.left() + (val - x_min) / (x_max - x_min) * rect.width()

                painter.setPen(QPen(QColor(GRID), 1))
                painter.drawLine(px, rect.top(), px, rect.bottom())

                painter.setPen(QPen(QColor(BORDER), 1))
                painter.drawLine(px, rect.bottom(), px, rect.bottom() + 4)

                painter.setPen(QColor(MUTED))
                val_str = f"{val:.2f}" if abs(val) < 100 else f"{val:.1f}"
                lbl_rect = QRectF(px - 30, rect.bottom() + 6, 60, 18)
                painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, val_str)

        # Axis Title Labels
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(QColor(INK))

        # X Title positioned cleanly below numeric or category ticks
        x_name = self.result.get("x_name", "X")
        lbl_rect_x = QRectF(rect.left(), rect.bottom() + (44 if is_categorical_x else 26), rect.width(), 20)
        painter.drawText(lbl_rect_x, Qt.AlignmentFlag.AlignCenter, x_name)

        # Y Title (Rotated)
        y_name = self.result.get("y_name", "Y")
        painter.save()
        painter.translate(rect.left() - 50, rect.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-100, -10, 200, 20), Qt.AlignmentFlag.AlignCenter, y_name)
        painter.restore()
