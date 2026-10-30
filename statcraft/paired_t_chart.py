"""Qt visual chart widget for native StatCraft Paired t test."""
from __future__ import annotations
import math
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PySide6.QtWidgets import QWidget
import numpy as np


class PairedTPlotWidget(QWidget):
    """Renders Individual Value Plot, Boxplot, and CI intervals for Paired t differences."""

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", {})
        self.setMinimumSize(560, 380)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_paired_t_panel(painter, self.rect(), self.result, self.entry.get("title"))
        painter.end()


def draw_paired_t_panel(
    p: QPainter,
    rect: QRectF,
    res: Dict[str, Any],
    title: Optional[str] = None,
):
    """Draw paired t plot showing differences distribution, CI, and H0 reference line."""
    p.fillRect(rect, QColor("#ffffff"))

    if not res:
        return

    diffs = res.get("differences", {})
    raw_diffs = diffs.get("raw") or []
    hyp_diff = res.get("hypothesized_difference", 0.0)
    conf_level = res.get("confidence_level", 95.0)
    conf_str = f"{int(conf_level) if conf_level.is_integer() else conf_level}%"

    graphs = res.get("graphs", {})
    show_ivp = graphs.get("individual_value_plot", True)
    show_box = graphs.get("boxplot", True)

    s1_name = res.get("sample1_name", "Sample 1")
    s2_name = res.get("sample2_name", "Sample 2")

    # Title
    t_text = title or f"Paired t: {s1_name} vs {s2_name}"
    p.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
    p.setPen(QColor("#000000"))
    p.drawText(QRectF(rect.left(), rect.top() + 8, rect.width(), 26), Qt.AlignmentFlag.AlignCenter, t_text)

    # Subtitle with test info
    p.setFont(QFont("Segoe UI", 9))
    p.setPen(QColor("#555555"))
    t_val = res.get("t_statistic", 0.0)
    p_val = res.get("p_value", 1.0)
    df_val = res.get("df", 0)
    mean_d = diffs.get("mean", 0.0)
    sub = f"Mean Diff = {mean_d:.4f}   Null Diff = {hyp_diff}   T = {t_val:.2f}   DF = {df_val}   P-Value = {p_val:.3f}"
    p.drawText(QRectF(rect.left(), rect.top() + 32, rect.width(), 20), Qt.AlignmentFlag.AlignCenter, sub)

    # Plot area
    margin_l = 70.0
    margin_r = 50.0
    margin_t = 65.0
    margin_b = 60.0
    plot_rect = QRectF(
        rect.left() + margin_l,
        rect.top() + margin_t,
        max(100.0, rect.width() - margin_l - margin_r),
        max(80.0, rect.height() - margin_t - margin_b)
    )

    # Calculate Y limits
    all_vals: List[float] = list(raw_diffs)
    all_vals.append(mean_d)
    all_vals.append(hyp_diff)
    if diffs.get("ci_lower") is not None:
        all_vals.append(diffs["ci_lower"])
    if diffs.get("ci_upper") is not None:
        all_vals.append(diffs["ci_upper"])

    if all_vals:
        min_v = min(all_vals)
        max_v = max(all_vals)
        span = max_v - min_v
        if span == 0:
            span = 1.0
        y_min = min_v - 0.20 * span
        y_max = max_v + 0.20 * span
    else:
        y_min, y_max = -5.0, 5.0

    def val_to_y(val: float) -> float:
        ratio = (val - y_min) / (y_max - y_min)
        return float(plot_rect.bottom() - ratio * plot_rect.height())

    # Bounding box & grid
    p.setPen(QPen(QColor("#cccccc"), 1))
    p.drawRect(plot_rect)

    p.setFont(QFont("Segoe UI", 8))
    for i in range(5):
        y_val = y_min + i * (y_max - y_min) / 4.0
        yp = val_to_y(y_val)
        p.setPen(QPen(QColor("#eeeeee"), 1))
        p.drawLine(QPointF(plot_rect.left(), yp), QPointF(plot_rect.right(), yp))
        p.setPen(QColor("#555555"))
        p.drawText(
            QRectF(rect.left(), yp - 10, margin_l - 8, 20),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{y_val:.2f}"
        )

    # Hypothesized difference reference line
    if y_min <= hyp_diff <= y_max:
        hyp_y = val_to_y(hyp_diff)
        pen_hyp = QPen(QColor("#d9534f"), 1.5, Qt.PenStyle.DashLine)
        p.setPen(pen_hyp)
        p.drawLine(QPointF(plot_rect.left(), hyp_y), QPointF(plot_rect.right(), hyp_y))
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        p.setPen(QColor("#d9534f"))
        p.drawText(
            QRectF(plot_rect.right() - 110, hyp_y - 18, 105, 16),
            Qt.AlignmentFlag.AlignRight,
            f"H0: μ_diff = {hyp_diff}"
        )

    slot_center_x = plot_rect.left() + 0.5 * plot_rect.width()
    mean_y = val_to_y(mean_d)
    ci_low = diffs.get("ci_lower")
    ci_high = diffs.get("ci_upper")

    # 1. Boxplot of differences
    if show_box and len(raw_diffs) >= 4:
        sorted_v = sorted(raw_diffs)
        q1 = float(np.percentile(sorted_v, 25))
        med = float(np.percentile(sorted_v, 50))
        q3 = float(np.percentile(sorted_v, 75))
        iqr = q3 - q1
        whisker_low = max(min(sorted_v), q1 - 1.5 * iqr)
        whisker_high = min(max(sorted_v), q3 + 1.5 * iqr)

        bx_center = slot_center_x - (40.0 if show_ivp else 0.0)
        bw = 50.0

        p.setPen(QPen(QColor("#2c3e50"), 1.2))
        p.drawLine(QPointF(bx_center, val_to_y(q3)), QPointF(bx_center, val_to_y(whisker_high)))
        p.drawLine(QPointF(bx_center - bw * 0.25, val_to_y(whisker_high)),
                   QPointF(bx_center + bw * 0.25, val_to_y(whisker_high)))

        p.drawLine(QPointF(bx_center, val_to_y(q1)), QPointF(bx_center, val_to_y(whisker_low)))
        p.drawLine(QPointF(bx_center - bw * 0.25, val_to_y(whisker_low)),
                   QPointF(bx_center + bw * 0.25, val_to_y(whisker_low)))

        b_top = val_to_y(q3)
        b_bot = val_to_y(q1)
        box_r = QRectF(bx_center - bw / 2, b_top, bw, b_bot - b_top)
        p.setBrush(QBrush(QColor(230, 240, 250, 200)))
        p.setPen(QPen(QColor("#2980b9"), 1.5))
        p.drawRect(box_r)

        p.setPen(QPen(QColor("#c0392b"), 2))
        med_y = val_to_y(med)
        p.drawLine(QPointF(bx_center - bw / 2, med_y), QPointF(bx_center + bw / 2, med_y))

    # 2. Individual Value Points (jitter)
    if show_ivp and raw_diffs:
        pt_center = slot_center_x + (30.0 if show_box and len(raw_diffs) >= 4 else 0.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(41, 128, 185, 200)))
        np.random.seed(99)
        for v in raw_diffs:
            jitter_x = pt_center + (np.random.rand() - 0.5) * 36.0
            py = val_to_y(v)
            p.drawEllipse(QPointF(jitter_x, py), 4.5, 4.5)

    # 3. Mean Difference marker and CI error bar
    ci_x = slot_center_x + (70.0 if show_ivp and show_box and len(raw_diffs) >= 4 else (35.0 if show_ivp else 0.0))
    if not show_ivp and not show_box:
        ci_x = slot_center_x

    if ci_low is not None and ci_high is not None:
        p.setPen(QPen(QColor("#27ae60"), 2))
        p.drawLine(QPointF(ci_x, val_to_y(ci_low)), QPointF(ci_x, val_to_y(ci_high)))
        p.drawLine(QPointF(ci_x - 6, val_to_y(ci_low)), QPointF(ci_x + 6, val_to_y(ci_low)))
        p.drawLine(QPointF(ci_x - 6, val_to_y(ci_high)), QPointF(ci_x + 6, val_to_y(ci_high)))
    elif ci_low is not None:
        p.setPen(QPen(QColor("#27ae60"), 2))
        p.drawLine(QPointF(ci_x, val_to_y(ci_low)), QPointF(ci_x, plot_rect.top()))
        p.drawLine(QPointF(ci_x - 6, val_to_y(ci_low)), QPointF(ci_x + 6, val_to_y(ci_low)))
    elif ci_high is not None:
        p.setPen(QPen(QColor("#27ae60"), 2))
        p.drawLine(QPointF(ci_x, plot_rect.bottom()), QPointF(ci_x, val_to_y(ci_high)))
        p.drawLine(QPointF(ci_x - 6, val_to_y(ci_high)), QPointF(ci_x + 6, val_to_y(ci_high)))

    # Sample Mean Difference Diamond
    p.setPen(QPen(QColor("#1b4f72"), 1.5))
    p.setBrush(QBrush(QColor("#f39c12")))
    pts = [
        QPointF(ci_x, mean_y - 6),
        QPointF(ci_x + 6, mean_y),
        QPointF(ci_x, mean_y + 6),
        QPointF(ci_x - 6, mean_y),
    ]
    p.drawPolygon(pts)

    # X axis label
    p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
    p.setPen(QColor("#333333"))
    lbl_r = QRectF(plot_rect.left(), plot_rect.bottom() + 8, plot_rect.width(), 24)
    p.drawText(lbl_r, Qt.AlignmentFlag.AlignCenter, f"Differences ({s1_name} - {s2_name})" if res.get("data_format") != 2 else "Differences")

    p.setFont(QFont("Segoe UI", 8))
    p.setPen(QColor("#666666"))
    n_r = QRectF(plot_rect.left(), plot_rect.bottom() + 28, plot_rect.width(), 18)
    p.drawText(n_r, Qt.AlignmentFlag.AlignCenter, f"N = {diffs.get('n', 0)}")
