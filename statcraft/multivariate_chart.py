"""High-fidelity Qt/QPainter charts for Multivariate Analysis.

Renders authentic StatCraft visual charts:
- Scree Plot (PCA)
- Loading Plot & Score Plot (PCA)
- Biplot (PCA)
- Item-Total Statistics Plot (Item Analysis)
- Dendrogram (Cluster Observations & Cluster Variables)
- Cluster Profile Plot (K-Means)
- Canonical Discriminant Score Plot (Discriminant Analysis)
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .graph_interaction import GraphInteractionMixin

BLUE = "#0061a8"
BLUE_FILL = "#1f77b4"
RED = "#d9534f"
GREEN = "#2ca02c"
ORANGE = "#ff7f0e"
PURPLE = "#9467bd"
BROWN = "#8c564b"
CYAN = "#17becf"
INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
GRID = "#e8ecef"
BOX_BG = "#f8f9fa"

PALETTE = [BLUE_FILL, ORANGE, GREEN, RED, PURPLE, BROWN, CYAN, "#e377c2", "#7f7f7f", "#bcbd22"]


def _fmt(val: Optional[float], dec: int = 3) -> str:
    if val is None or math.isnan(val):
        return "*"
    if val == float("inf"):
        return "Inf"
    if val == float("-inf"):
        return "-Inf"
    return f"{val:.{dec}f}"


class MultivariateChartWidget(GraphInteractionMixin, QWidget):
    """High-DPI renderer for Multivariate Analysis charts."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", {})
        self.recipe = entry.get("recipe", {})

        self.analysis = self.result.get("analysis", "pca")
        self.chart_type = self.result.get("chart_type", "scree" if self.analysis == "pca" else "default")
        self.title_text = self.result.get("title") or "Multivariate Analysis Plot"

        self.setMinimumSize(640, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.hover_point: Optional[Tuple[float, float, str]] = None

    def sizeHint(self) -> QSize:
        return QSize(780, 480)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect()
        painter.fillRect(rect, QColor("#ffffff"))

        if self.analysis == "pca":
            if self.chart_type == "loading":
                self._paint_pca_loading_plot(painter, rect)
            elif self.chart_type == "score":
                self._paint_pca_score_plot(painter, rect)
            elif self.chart_type == "biplot":
                self._paint_pca_biplot(painter, rect)
            else:
                self._paint_pca_scree_plot(painter, rect)
        elif self.analysis == "item_analysis":
            self._paint_item_analysis_plot(painter, rect)
        elif self.analysis in ("cluster_observations", "cluster_variables"):
            self._paint_dendrogram(painter, rect)
        elif self.analysis == "cluster_kmeans":
            self._paint_kmeans_profile(painter, rect)
        elif self.analysis == "discriminant_analysis":
            self._paint_discriminant_score_plot(painter, rect)
        elif self.analysis == "simple_correspondence":
            self._paint_correspondence_plot(painter, rect)
        elif self.analysis == "factor_analysis":
            self._paint_factor_analysis_loading_plot(painter, rect)
        elif self.analysis == "multiple_correspondence":
            self._paint_mca_coordinate_plot(painter, rect)
        else:
            self._paint_pca_scree_plot(painter, rect)

    # --------------------------------------------------------------------------
    # 1. PCA SCREE PLOT
    # --------------------------------------------------------------------------
    def _paint_pca_scree_plot(self, painter: QPainter, rect: QRectF) -> None:
        eigenvalues = self.result.get("eigenvalues", [])
        p = len(eigenvalues)
        if p == 0:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No eigenvalues to display.")
            return

        top = 65.0
        bottom = rect.height() - 55.0
        left = 75.0
        right = rect.width() - 40.0
        plot_w = right - left
        plot_h = bottom - top

        # Title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, self.title_text)

        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(MUTED))
        matrix_title = self.result.get("matrix_title", "Correlation Matrix")
        painter.drawText(QRectF(left, 40, rect.width() - left - 20, 20), Qt.AlignmentFlag.AlignLeft, f"Eigenanalysis of the {matrix_title}")

        # Scales
        max_ev = max(eigenvalues) * 1.15
        min_ev = 0.0

        def x_pos(comp_idx: int) -> float:
            return left + (comp_idx + 0.5) * (plot_w / p)

        def y_pos(val: float) -> float:
            ratio = (val - min_ev) / (max_ev - min_ev) if max_ev > min_ev else 0.5
            return bottom - ratio * plot_h

        # Grid lines
        painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.SolidLine))
        y_ticks = 5
        for t in range(y_ticks + 1):
            val = min_ev + t * (max_ev - min_ev) / y_ticks
            y = y_pos(val)
            painter.drawLine(QPointF(left, y), QPointF(right, y))
            painter.setPen(QColor(MUTED))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(0, y - 9, left - 8, 18), Qt.AlignmentFlag.AlignRight, f"{val:.2f}")
            painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.SolidLine))

        # Kaiser criterion reference line at 1.0 (for correlation matrix)
        if self.result.get("matrix_type") == "correlation" and max_ev > 1.0:
            y_ref = y_pos(1.0)
            painter.setPen(QPen(QColor(RED), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(left, y_ref), QPointF(right, y_ref))
            painter.setPen(QColor(RED))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(right - 140, y_ref - 18, 135, 16), Qt.AlignmentFlag.AlignRight, "Eigenvalue = 1.0")

        # Outer border
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        # Line connecting eigenvalues
        path = QPainterPath()
        points = []
        for i, ev in enumerate(eigenvalues):
            pt = QPointF(x_pos(i), y_pos(ev))
            points.append(pt)
            if i == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)

        painter.setPen(QPen(QColor(BLUE), 2))
        painter.drawPath(path)

        # Draw points
        for i, pt in enumerate(points):
            painter.setPen(QPen(QColor(BLUE), 1.5))
            painter.setBrush(QColor(BLUE_FILL))
            painter.drawEllipse(pt, 4.5, 4.5)

            # X-axis label
            painter.setPen(QColor(INK))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(pt.x() - 25, bottom + 6, 50, 16), Qt.AlignmentFlag.AlignCenter, f"{i+1}")

        # Axis Titles
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(left, bottom + 26, plot_w, 20), Qt.AlignmentFlag.AlignCenter, "Principal Component")

        painter.save()
        painter.translate(20, top + plot_h / 2)
        painter.rotate(-90)
        painter.drawText(QRectF(-plot_h / 2, -15, plot_h, 30), Qt.AlignmentFlag.AlignCenter, "Eigenvalue")
        painter.restore()

    # --------------------------------------------------------------------------
    # 2. PCA LOADING PLOT
    # --------------------------------------------------------------------------
    def _paint_pca_loading_plot(self, painter: QPainter, rect: QRectF) -> None:
        loadings = self.result.get("loadings_table", [])
        if not loadings or len(self.result.get("comp_names", [])) < 2:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "At least 2 components required for Loading Plot.")
            return

        top = 65.0
        bottom = rect.height() - 55.0
        left = 75.0
        right = rect.width() - 40.0
        plot_w = right - left
        plot_h = bottom - top

        # Title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, "Loading Plot of Component 1 and Component 2")

        # Range is typically -1 to +1
        min_v, max_v = -1.1, 1.1

        def x_pos(v: float) -> float:
            return left + (v - min_v) / (max_v - min_v) * plot_w

        def y_pos(v: float) -> float:
            return bottom - (v - min_v) / (max_v - min_v) * plot_h

        # Zero reference axes
        painter.setPen(QPen(QColor(BORDER), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(x_pos(0), top), QPointF(x_pos(0), bottom))
        painter.drawLine(QPointF(left, y_pos(0)), QPointF(right, y_pos(0)))

        # Border
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        origin = QPointF(x_pos(0), y_pos(0))

        # Draw loading vectors and labels
        for row in loadings:
            name = row["variable"]
            l1 = row.get("PC1", 0.0)
            l2 = row.get("PC2", 0.0)
            pt = QPointF(x_pos(l1), y_pos(l2))

            # Ray from origin
            painter.setPen(QPen(QColor(BLUE), 1.5))
            painter.drawLine(origin, pt)

            # Marker
            painter.setBrush(QColor(BLUE_FILL))
            painter.drawEllipse(pt, 3.5, 3.5)

            # Text label
            painter.setPen(QColor(INK))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(pt.x() + 5, pt.y() - 10, 80, 20), Qt.AlignmentFlag.AlignLeft, name)

        # Axis titles
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(left, bottom + 15, plot_w, 20), Qt.AlignmentFlag.AlignCenter, "First Component (PC1)")

        painter.save()
        painter.translate(20, top + plot_h / 2)
        painter.rotate(-90)
        painter.drawText(QRectF(-plot_h / 2, -15, plot_h, 30), Qt.AlignmentFlag.AlignCenter, "Second Component (PC2)")
        painter.restore()

    # --------------------------------------------------------------------------
    # 3. PCA SCORE PLOT
    # --------------------------------------------------------------------------
    def _paint_pca_score_plot(self, painter: QPainter, rect: QRectF) -> None:
        scores = self.result.get("scores", [])
        if not scores or len(scores[0]) < 2:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "At least 2 components required for Score Plot.")
            return

        top = 65.0
        bottom = rect.height() - 55.0
        left = 75.0
        right = rect.width() - 40.0
        plot_w = right - left
        plot_h = bottom - top

        # Title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, "Score Plot of Component 1 and Component 2")

        sc1 = [row[0] for row in scores]
        sc2 = [row[1] for row in scores]
        min_x, max_x = min(sc1) * 1.15, max(sc1) * 1.15
        min_y, max_y = min(sc2) * 1.15, max(sc2) * 1.15

        def x_pos(v: float) -> float:
            return left + (v - min_x) / (max_x - min_x) * plot_w if max_x > min_x else left + plot_w / 2

        def y_pos(v: float) -> float:
            return bottom - (v - min_y) / (max_y - min_y) * plot_h if max_y > min_y else bottom - plot_h / 2

        # Zero reference lines
        painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
        if min_x <= 0 <= max_x:
            painter.drawLine(QPointF(x_pos(0), top), QPointF(x_pos(0), bottom))
        if min_y <= 0 <= max_y:
            painter.drawLine(QPointF(left, y_pos(0)), QPointF(right, y_pos(0)))

        # Border
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        # Points
        painter.setPen(QPen(QColor(BLUE), 1))
        painter.setBrush(QColor(BLUE_FILL))
        for x, y in zip(sc1, sc2):
            painter.drawEllipse(QPointF(x_pos(x), y_pos(y)), 3.5, 3.5)

        # Axis titles
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(left, bottom + 15, plot_w, 20), Qt.AlignmentFlag.AlignCenter, "First Component (PC1)")

        painter.save()
        painter.translate(20, top + plot_h / 2)
        painter.rotate(-90)
        painter.drawText(QRectF(-plot_h / 2, -15, plot_h, 30), Qt.AlignmentFlag.AlignCenter, "Second Component (PC2)")
        painter.restore()

    # --------------------------------------------------------------------------
    # 4. PCA BIPLOT
    # --------------------------------------------------------------------------
    def _paint_pca_biplot(self, painter: QPainter, rect: QRectF) -> None:
        self._paint_pca_score_plot(painter, rect)
        # Overlay loadings scaled to score range
        loadings = self.result.get("loadings_table", [])
        scores = self.result.get("scores", [])
        if not loadings or not scores or len(scores[0]) < 2:
            return

        top = 65.0
        bottom = rect.height() - 55.0
        left = 75.0
        right = rect.width() - 40.0
        plot_w = right - left
        plot_h = bottom - top

        sc1 = [row[0] for row in scores]
        sc2 = [row[1] for row in scores]
        max_scale = max(max(abs(min(sc1)), abs(max(sc1))), max(abs(min(sc2)), abs(max(sc2))))

        min_x, max_x = -max_scale * 1.2, max_scale * 1.2
        min_y, max_y = -max_scale * 1.2, max_scale * 1.2

        def x_pos(v: float) -> float:
            return left + (v - min_x) / (max_x - min_x) * plot_w

        def y_pos(v: float) -> float:
            return bottom - (v - min_y) / (max_y - min_y) * plot_h

        origin = QPointF(x_pos(0), y_pos(0))
        for row in loadings:
            name = row["variable"]
            l1 = row.get("PC1", 0.0) * max_scale
            l2 = row.get("PC2", 0.0) * max_scale
            pt = QPointF(x_pos(l1), y_pos(l2))

            painter.setPen(QPen(QColor(RED), 1.5))
            painter.drawLine(origin, pt)
            painter.setBrush(QColor(RED))
            painter.drawEllipse(pt, 3.0, 3.0)

            painter.setPen(QColor(RED))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(pt.x() + 4, pt.y() - 10, 80, 20), Qt.AlignmentFlag.AlignLeft, name)

    # --------------------------------------------------------------------------
    # 5. ITEM ANALYSIS PLOT
    # --------------------------------------------------------------------------
    def _paint_item_analysis_plot(self, painter: QPainter, rect: QRectF) -> None:
        stats = self.result.get("item_stats", [])
        k = len(stats)
        if k == 0:
            return

        top = 65.0
        bottom = rect.height() - 60.0
        left = 75.0
        right = rect.width() - 40.0
        plot_w = right - left
        plot_h = bottom - top

        # Title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, "Item-Total Statistics Plot")

        # Subtitle
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(MUTED))
        painter.drawText(QRectF(left, 40, rect.width() - left - 20, 20), Qt.AlignmentFlag.AlignLeft, f"Cronbach's alpha = {self.result.get('cronbach_alpha', 0.0):.4f}")

        # Border
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        # Bar chart of Item-Total Correlations
        slot_w = plot_w / k
        bar_w = slot_w * 0.45

        for i, st in enumerate(stats):
            name = st["item"]
            r_val = max(0.0, min(1.0, st["item_adj_total_corr"]))
            bar_h = r_val * plot_h
            bx = left + i * slot_w + (slot_w - bar_w) / 2
            by = bottom - bar_h

            painter.setPen(QPen(QColor(BLUE), 1))
            painter.setBrush(QColor(BLUE_FILL))
            painter.drawRect(QRectF(bx, by, bar_w, bar_h))

            # X-axis label
            painter.setPen(QColor(INK))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(left + i * slot_w, bottom + 5, slot_w, 20), Qt.AlignmentFlag.AlignCenter, name)

        # Overlay Alpha if item deleted line
        overall_alpha = self.result.get("cronbach_alpha", 0.0)
        painter.setPen(QPen(QColor(RED), 1, Qt.PenStyle.DashLine))
        y_overall = bottom - overall_alpha * plot_h
        painter.drawLine(QPointF(left, y_overall), QPointF(right, y_overall))

        line_pts = []
        for i, st in enumerate(stats):
            a_del = max(0.0, min(1.0, st["alpha_deleted"]))
            lx = left + (i + 0.5) * slot_w
            ly = bottom - a_del * plot_h
            line_pts.append(QPointF(lx, ly))

        if line_pts:
            path = QPainterPath()
            path.moveTo(line_pts[0])
            for pt in line_pts[1:]:
                path.lineTo(pt)
            painter.setPen(QPen(QColor(RED), 2))
            painter.drawPath(path)

            for pt in line_pts:
                painter.setPen(QPen(QColor(RED), 1.5))
                painter.setBrush(QColor("#ffffff"))
                painter.drawEllipse(pt, 4.0, 4.0)

        # Legend
        leg_x = right - 220
        leg_y = top + 15
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 8))
        # Blue bar
        painter.setBrush(QColor(BLUE_FILL))
        painter.drawRect(QRectF(leg_x, leg_y, 14, 10))
        painter.drawText(QRectF(leg_x + 20, leg_y - 2, 190, 16), Qt.AlignmentFlag.AlignLeft, "Item-Adj Total Corr")
        # Red line
        painter.setPen(QPen(QColor(RED), 2))
        painter.drawLine(QPointF(leg_x, leg_y + 18), QPointF(leg_x + 14, leg_y + 18))
        painter.setPen(QColor(INK))
        painter.drawText(QRectF(leg_x + 20, leg_y + 10, 190, 16), Qt.AlignmentFlag.AlignLeft, "Alpha if Deleted")

    # --------------------------------------------------------------------------
    # 6. DENDROGRAM (CLUSTER OBSERVATIONS / VARIABLES)
    # --------------------------------------------------------------------------
    def _paint_dendrogram(self, painter: QPainter, rect: QRectF) -> None:
        dendro = self.result.get("dendrogram_data", {})
        icoord = dendro.get("icoord", [])
        dcoord = dendro.get("dcoord", [])
        ivl = dendro.get("ivl", [])

        if not icoord:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No dendrogram data available.")
            return

        top = 65.0
        bottom = rect.height() - 55.0
        left = 75.0
        right = rect.width() - 40.0
        plot_w = right - left
        plot_h = bottom - top

        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, self.title_text)

        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(MUTED))
        link_str = self.result.get("linkage_method", "Average").capitalize()
        painter.drawText(QRectF(left, 40, rect.width() - left - 20, 20), Qt.AlignmentFlag.AlignLeft, f"Dendrogram with {link_str} Linkage")

        # Bounds
        all_x = [x for seg in icoord for x in seg]
        all_y = [y for seg in dcoord for y in seg]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = 0.0, max(all_y) * 1.15 if all_y else 1.0

        def x_pos(x: float) -> float:
            return left + (x - min_x) / (max_x - min_x) * plot_w if max_x > min_x else left + plot_w / 2

        def y_pos(y: float) -> float:
            return bottom - (y - min_y) / (max_y - min_y) * plot_h if max_y > min_y else bottom

        # Border
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        # Draw U-shaped links
        painter.setPen(QPen(QColor(BLUE), 1.5))
        for xs, ys in zip(icoord, dcoord):
            pts = [QPointF(x_pos(x), y_pos(y)) for x, y in zip(xs, ys)]
            for i in range(len(pts) - 1):
                painter.drawLine(pts[i], pts[i + 1])

        # Y-axis ticks
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(MUTED))
        for t in range(5):
            val = min_y + t * (max_y - min_y) / 4.0
            y = y_pos(val)
            painter.drawText(QRectF(0, y - 8, left - 8, 16), Qt.AlignmentFlag.AlignRight, f"{val:.2f}")

        # Axis title
        painter.save()
        painter.translate(20, top + plot_h / 2)
        painter.rotate(-90)
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(-plot_h / 2, -15, plot_h, 30), Qt.AlignmentFlag.AlignCenter, "Distance Level")
        painter.restore()

    # --------------------------------------------------------------------------
    # 7. K-MEANS CLUSTER PROFILE
    # --------------------------------------------------------------------------
    def _paint_kmeans_profile(self, painter: QPainter, rect: QRectF) -> None:
        centroids = self.result.get("centroids", [])
        names = self.result.get("variable_names", [])
        k = len(centroids)
        p = len(names)
        if k == 0 or p == 0:
            return

        top = 65.0
        bottom = rect.height() - 55.0
        left = 75.0
        right = rect.width() - 150.0
        plot_w = right - left
        plot_h = bottom - top

        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, "K-Means Cluster Centroids Profile")

        # Find min and max across all centroids
        all_vals = [val for row in centroids for val in row]
        min_v, max_v = min(all_vals), max(all_vals)
        pad = (max_v - min_v) * 0.1 if max_v > min_v else 1.0
        min_v -= pad
        max_v += pad

        def x_pos(col_idx: int) -> float:
            return left + (col_idx + 0.5) * (plot_w / p)

        def y_pos(val: float) -> float:
            return bottom - (val - min_v) / (max_v - min_v) * plot_h if max_v > min_v else bottom - plot_h / 2

        # Border
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        # Vertical axis lines for each variable
        painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
        for j in range(p):
            x = x_pos(j)
            painter.drawLine(QPointF(x, top), QPointF(x, bottom))
            painter.setPen(QColor(INK))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(x - 35, bottom + 5, 70, 20), Qt.AlignmentFlag.AlignCenter, names[j])
            painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))

        # Draw lines for each cluster centroid
        for c_idx in range(k):
            c_color = QColor(PALETTE[c_idx % len(PALETTE)])
            painter.setPen(QPen(c_color, 2))
            pts = [QPointF(x_pos(j), y_pos(centroids[c_idx][j])) for j in range(p)]
            for j in range(p - 1):
                painter.drawLine(pts[j], pts[j + 1])
            painter.setBrush(c_color)
            for pt in pts:
                painter.drawEllipse(pt, 4.0, 4.0)

        # Legend on right
        leg_x = right + 15
        leg_y = top + 10
        painter.setFont(QFont("Segoe UI", 8))
        for c_idx in range(k):
            c_color = QColor(PALETTE[c_idx % len(PALETTE)])
            painter.setPen(QPen(c_color, 2))
            painter.drawLine(QPointF(leg_x, leg_y + c_idx * 20 + 8), QPointF(leg_x + 16, leg_y + c_idx * 20 + 8))
            painter.setBrush(c_color)
            painter.drawEllipse(QPointF(leg_x + 8, leg_y + c_idx * 20 + 8), 3.0, 3.0)
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(leg_x + 24, leg_y + c_idx * 20, 100, 18), Qt.AlignmentFlag.AlignLeft, f"Cluster {c_idx + 1}")

    # --------------------------------------------------------------------------
    # 8. DISCRIMINANT CANONICAL SCORE PLOT
    # --------------------------------------------------------------------------
    def _paint_discriminant_score_plot(self, painter: QPainter, rect: QRectF) -> None:
        scores = self.result.get("canonical_scores", [])
        groups = self.result.get("group_labels", [])
        unique_groups = self.result.get("unique_groups", [])

        if not scores or len(scores[0]) < 2:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Canonical scores not available.")
            return

        top = 65.0
        bottom = rect.height() - 55.0
        left = 75.0
        right = rect.width() - 140.0
        plot_w = right - left
        plot_h = bottom - top

        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, "Canonical Discriminant Score Plot")

        sc1 = [r[0] for r in scores]
        sc2 = [r[1] for r in scores]
        min_x, max_x = min(sc1) * 1.15, max(sc1) * 1.15
        min_y, max_y = min(sc2) * 1.15, max(sc2) * 1.15

        def x_pos(x: float) -> float:
            return left + (x - min_x) / (max_x - min_x) * plot_w if max_x > min_x else left + plot_w / 2

        def y_pos(y: float) -> float:
            return bottom - (y - min_y) / (max_y - min_y) * plot_h if max_y > min_y else bottom - plot_h / 2

        # Border
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        # Draw observations
        for (x, y), g in zip(scores, groups):
            g_idx = unique_groups.index(g) if g in unique_groups else 0
            c_color = QColor(PALETTE[g_idx % len(PALETTE)])
            painter.setPen(QPen(c_color, 1))
            painter.setBrush(c_color)
            painter.drawEllipse(QPointF(x_pos(x), y_pos(y)), 3.5, 3.5)

        # Legend
        leg_x = right + 15
        leg_y = top + 10
        painter.setFont(QFont("Segoe UI", 8))
        for g_idx, g_name in enumerate(unique_groups):
            c_color = QColor(PALETTE[g_idx % len(PALETTE)])
            painter.setBrush(c_color)
            painter.setPen(QPen(c_color, 1))
            painter.drawEllipse(QPointF(leg_x + 8, leg_y + g_idx * 20 + 8), 4.0, 4.0)
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(leg_x + 20, leg_y + g_idx * 20, 100, 18), Qt.AlignmentFlag.AlignLeft, g_name)

    # --------------------------------------------------------------------------
    # 9. SIMPLE CORRESPONDENCE PLOT
    # --------------------------------------------------------------------------
    def _paint_correspondence_plot(self, painter: QPainter, rect: QRectF) -> None:
        row_coords = self.result.get("row_coordinates", [])
        col_coords = self.result.get("col_coordinates", [])
        if not row_coords or not col_coords:
            return

        top = 65.0
        bottom = rect.height() - 55.0
        left = 75.0
        right = rect.width() - 40.0
        plot_w = right - left
        plot_h = bottom - top

        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, "Simple Correspondence Analysis Biplot")

        all_x = [r["coord1"] for r in row_coords] + [c["coord1"] for c in col_coords]
        all_y = [r["coord2"] for r in row_coords] + [c["coord2"] for c in col_coords]
        max_abs = max(max(abs(min(all_x)), abs(max(all_x))), max(abs(min(all_y)), abs(max(all_y)))) * 1.2
        min_v, max_v = -max_abs, max_abs

        def x_pos(x: float) -> float:
            return left + (x - min_v) / (max_v - min_v) * plot_w

        def y_pos(y: float) -> float:
            return bottom - (y - min_v) / (max_v - min_v) * plot_h

        # Axes at 0
        painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(x_pos(0), top), QPointF(x_pos(0), bottom))
        painter.drawLine(QPointF(left, y_pos(0)), QPointF(right, y_pos(0)))

        # Border
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        # Row points (Blue circles)
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        for r in row_coords:
            pt = QPointF(x_pos(r["coord1"]), y_pos(r["coord2"]))
            painter.setPen(QPen(QColor(BLUE), 1))
            painter.setBrush(QColor(BLUE_FILL))
            painter.drawEllipse(pt, 4.0, 4.0)
            painter.setPen(QColor(BLUE))
            painter.drawText(QRectF(pt.x() + 5, pt.y() - 10, 80, 20), Qt.AlignmentFlag.AlignLeft, r["name"])

        # Col points (Red triangles)
        for c in col_coords:
            pt = QPointF(x_pos(c["coord1"]), y_pos(c["coord2"]))
            painter.setPen(QPen(QColor(RED), 1))
            painter.setBrush(QColor(RED))
            path = QPainterPath()
            path.moveTo(pt.x(), pt.y() - 5)
            path.lineTo(pt.x() - 5, pt.y() + 4)
            path.lineTo(pt.x() + 5, pt.y() + 4)
            path.closeSubpath()
            painter.drawPath(path)
            painter.setPen(QColor(RED))
            painter.drawText(QRectF(pt.x() + 6, pt.y() - 10, 80, 20), Qt.AlignmentFlag.AlignLeft, c["name"])

    # --------------------------------------------------------------------------
    # 10. FACTOR ANALYSIS LOADING PLOT
    # --------------------------------------------------------------------------
    def _paint_factor_analysis_loading_plot(self, painter: QPainter, rect: QRectF) -> None:
        loadings = self.result.get("rotated_loadings") or self.result.get("unrotated_loadings") or []
        labels = self.result.get("factor_labels", [])
        if not loadings or len(labels) < 2:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Factor Analysis Loading Plot requires at least 2 factors.")
            return

        f1_key, f2_key = labels[0], labels[1]
        top = 65.0
        bottom = rect.height() - 55.0
        left = 75.0
        right = rect.width() - 40.0
        plot_w = right - left
        plot_h = bottom - top

        # Title
        rot = self.result.get("rotation", "Unrotated")
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, f"Factor Loading Plot ({rot} Rotation)")

        min_v, max_v = -1.15, 1.15

        def x_pos(v: float) -> float:
            return left + (v - min_v) / (max_v - min_v) * plot_w

        def y_pos(v: float) -> float:
            return bottom - (v - min_v) / (max_v - min_v) * plot_h

        # Communality reference circle (radius 1.0)
        c_center = QPointF(x_pos(0), y_pos(0))
        rx = abs(x_pos(1.0) - x_pos(0))
        ry = abs(y_pos(1.0) - y_pos(0))
        painter.setPen(QPen(QColor("#e2e8f0"), 1.2, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(c_center, rx, ry)

        # Zero reference axes
        painter.setPen(QPen(QColor(BORDER), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(x_pos(0), top), QPointF(x_pos(0), bottom))
        painter.drawLine(QPointF(left, y_pos(0)), QPointF(right, y_pos(0)))

        # Border
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        # Draw loading vectors and labels
        painter.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Bold))
        for idx, row in enumerate(loadings):
            name = str(row.get("variable", f"Var {idx+1}"))
            l1 = float(row.get(f1_key, 0.0))
            l2 = float(row.get(f2_key, 0.0))
            pt = QPointF(x_pos(l1), y_pos(l2))

            # Ray from origin
            col = QColor(PALETTE[idx % len(PALETTE)])
            painter.setPen(QPen(col, 1.8))
            painter.drawLine(c_center, pt)

            # Arrow marker
            painter.setBrush(col)
            painter.drawEllipse(pt, 4.0, 4.0)

            # Text label offset
            painter.setPen(QColor(INK))
            offset_x = 7 if l1 >= 0 else -60
            offset_y = -7 if l2 >= 0 else 7
            painter.drawText(QRectF(pt.x() + offset_x, pt.y() + offset_y, 65, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        # Axis ticks & titles
        painter.setFont(QFont("Segoe UI", 8.5))
        painter.setPen(QColor(MUTED))
        for tick in (-1.0, -0.5, 0.0, 0.5, 1.0):
            painter.drawText(QRectF(x_pos(tick) - 20, bottom + 5, 40, 16), Qt.AlignmentFlag.AlignCenter, f"{tick:.1f}")
            painter.drawText(QRectF(left - 45, y_pos(tick) - 8, 38, 16), Qt.AlignmentFlag.AlignRight, f"{tick:.1f}")

        painter.setFont(QFont("Segoe UI", 9.5, QFont.Weight.DemiBold))
        painter.setPen(QColor(INK))
        p_var = self.result.get("rotated_prop_var") or self.result.get("unrotated_prop_var") or [0.0, 0.0]
        pct1 = (p_var[0] * 100) if len(p_var) > 0 else 0.0
        pct2 = (p_var[1] * 100) if len(p_var) > 1 else 0.0
        painter.drawText(QRectF(left, bottom + 25, plot_w, 20), Qt.AlignmentFlag.AlignCenter, f"{f1_key} ({pct1:.1f}% Variance)")

        painter.save()
        painter.translate(22, top + plot_h / 2)
        painter.rotate(-90)
        painter.drawText(QRectF(-plot_h / 2, -10, plot_h, 20), Qt.AlignmentFlag.AlignCenter, f"{f2_key} ({pct2:.1f}% Variance)")
        painter.restore()

    # --------------------------------------------------------------------------
    # 11. MULTIPLE CORRESPONDENCE ANALYSIS (MCA) COORDINATE PLOT
    # --------------------------------------------------------------------------
    def _paint_mca_coordinate_plot(self, painter: QPainter, rect: QRectF) -> None:
        cat_table = self.result.get("category_table", [])
        if not cat_table:
            painter.setPen(QColor(MUTED))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No MCA category coordinates to display.")
            return

        top = 65.0
        bottom = rect.height() - 55.0
        left = 75.0
        right = rect.width() - 140.0
        plot_w = right - left
        plot_h = bottom - top

        # Title
        painter.setPen(QColor(INK))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(left, 15, rect.width() - left - 20, 25), Qt.AlignmentFlag.AlignLeft, "MCA Category Coordinate Plot")

        all_x = [float(r.get("coord_1", 0.0)) for r in cat_table]
        all_y = [float(r.get("coord_2", 0.0)) for r in cat_table]
        max_abs = max(max(abs(min(all_x, default=0)), abs(max(all_x, default=0))),
                      max(abs(min(all_y, default=0)), abs(max(all_y, default=0))), 0.5) * 1.2
        min_v, max_v = -max_abs, max_abs

        def x_pos(x: float) -> float:
            return left + (x - min_v) / (max_v - min_v) * plot_w

        def y_pos(y: float) -> float:
            return bottom - (y - min_v) / (max_v - min_v) * plot_h

        # Axes at 0
        painter.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(x_pos(0), top), QPointF(x_pos(0), bottom))
        painter.drawLine(QPointF(left, y_pos(0)), QPointF(right, y_pos(0)))

        # Border
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawRect(QRectF(left, top, plot_w, plot_h))

        unique_vars = []
        for r in cat_table:
            v_name = str(r.get("variable", ""))
            if v_name not in unique_vars:
                unique_vars.append(v_name)

        # Plot points
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        for r in cat_table:
            v_name = str(r.get("variable", ""))
            cat_name = str(r.get("category", ""))
            c_idx = unique_vars.index(v_name) if v_name in unique_vars else 0
            col = QColor(PALETTE[c_idx % len(PALETTE)])

            cx = float(r.get("coord_1", 0.0))
            cy = float(r.get("coord_2", 0.0))
            pt = QPointF(x_pos(cx), y_pos(cy))

            painter.setPen(QPen(col, 1.2))
            painter.setBrush(col)
            painter.drawEllipse(pt, 4.0, 4.0)

            # Label
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(pt.x() + 5, pt.y() - 8, 100, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, cat_name)

        # Legend on right
        leg_x = right + 15
        leg_y = top + 10
        painter.setFont(QFont("Segoe UI", 8.5))
        for v_idx, v_name in enumerate(unique_vars):
            col = QColor(PALETTE[v_idx % len(PALETTE)])
            painter.setBrush(col)
            painter.setPen(QPen(col, 1))
            painter.drawEllipse(QPointF(leg_x + 8, leg_y + v_idx * 22 + 8), 4.5, 4.5)
            painter.setPen(QColor(INK))
            painter.drawText(QRectF(leg_x + 20, leg_y + v_idx * 22, 110, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, v_name)

        # Axis ticks & titles
        painter.setFont(QFont("Segoe UI", 9.5, QFont.Weight.DemiBold))
        painter.setPen(QColor(INK))
        in_table = self.result.get("inertia_table", [])
        pct1 = (in_table[0].get("percent", 0.0)) if len(in_table) > 0 else 0.0
        pct2 = (in_table[1].get("percent", 0.0)) if len(in_table) > 1 else 0.0
        painter.drawText(QRectF(left, bottom + 25, plot_w, 20), Qt.AlignmentFlag.AlignCenter, f"Component 1 ({pct1:.1f}% Inertia)")

        painter.save()
        painter.translate(22, top + plot_h / 2)
        painter.rotate(-90)
        painter.drawText(QRectF(-plot_h / 2, -10, plot_h, 20), Qt.AlignmentFlag.AlignCenter, f"Component 2 ({pct2:.1f}% Inertia)")
        painter.restore()
