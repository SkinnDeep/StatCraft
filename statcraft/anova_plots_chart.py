"""Chart renderers for Main Effects Plots and Interactions Plots.

Delivers publication-quality vector charts with shared axes, multi-factor panels,
grand mean reference lines, and factor level legends.
"""
from __future__ import annotations

import math
from typing import Any
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

BLUE = '#0061a8'
INK = '#1a2b38'
MUTED = '#5b6b77'
BORDER = '#ced6dc'
RED = '#c23934'
SLATE = '#2e4354'
TEAL = '#0b827e'
GREEN = '#1b7837'
PURPLE = '#7e3878'
ORANGE = '#d96b27'

SERIES_COLORS = [BLUE, RED, GREEN, PURPLE, ORANGE, TEAL, '#555555', '#a0522d', '#4682b4']


def supported(result: dict[str, Any]) -> bool:
    if not isinstance(result, dict):
        return False
    return result.get('analysis') in ('main_effects_plot', 'interactions_plot')


def prepare(chart, result: dict[str, Any]) -> None:
    chart.panels = []
    chart.panel_columns = 1
    analysis = result.get('analysis')

    if analysis == 'main_effects_plot':
        chart.note = f"Main Effects Plot for {result.get('response_name', 'Response')}"
        chart.panels.append({
            'kind': 'main_effects_plot',
            'title': f"Main Effects Plot for {result.get('response_name', 'Response')}",
            'result': result
        })
    elif analysis == 'interactions_plot':
        fa = result.get('factor_a_name', 'Factor A')
        fb = result.get('factor_b_name', 'Factor B')
        chart.note = f"Interaction Plot for {result.get('response_name', 'Response')} ({fa} by {fb})"
        chart.panels.append({
            'kind': 'interactions_plot',
            'title': f"Interaction Plot for {result.get('response_name', 'Response')}",
            'result': result
        })


def draw_panel(chart, p: QPainter, area: QRectF, panel: dict[str, Any]) -> None:
    kind = panel['kind']
    if kind == 'main_effects_plot':
        _draw_main_effects(chart, p, area, panel['result'])
    elif kind == 'interactions_plot':
        _draw_interactions(chart, p, area, panel['result'])


def _draw_main_effects(chart, p: QPainter, area: QRectF, r: dict[str, Any]) -> None:
    title_rect = QRectF(area.left(), area.top() + 4, area.width(), 22)
    chart._text(p, title_rect, f"Main Effects Plot for {r.get('response_name', 'Response')} (Data Means)", INK, Qt.AlignmentFlag.AlignCenter, bold=True)

    factor_summaries = r.get('factor_summaries', [])
    if not factor_summaries:
        return

    n_factors = len(factor_summaries)
    plot_rect = area.adjusted(55, 34, -20, -38)

    # Compute global Y bounds
    all_means: list[float] = [r.get('grand_mean', 0.0)]
    for summ in factor_summaries:
        all_means.extend([s['mean'] for s in summ.get('level_stats', [])])

    min_y = min(all_means)
    max_y = max(all_means)
    if min_y == max_y:
        min_y -= 1.0
        max_y += 1.0
    pad = (max_y - min_y) * 0.15
    min_y -= pad
    max_y += pad

    def y_to_px(val: float) -> float:
        ratio = (val - min_y) / (max_y - min_y)
        return plot_rect.bottom() - ratio * plot_rect.height()

    # Draw Y axis ticks and labels on left
    p.setPen(QPen(QColor(BORDER), 1.0))
    p.drawLine(QPointF(plot_rect.left(), plot_rect.top()), QPointF(plot_rect.left(), plot_rect.bottom()))

    n_y_ticks = 5
    for i in range(n_y_ticks + 1):
        frac = i / n_y_ticks
        val = min_y + frac * (max_y - min_y)
        y_pos = y_to_px(val)
        p.setPen(QPen(QColor(BORDER), 1.0))
        p.drawLine(QPointF(plot_rect.left() - 4, y_pos), QPointF(plot_rect.left(), y_pos))
        lbl_rect = QRectF(area.left(), y_pos - 8, 48, 16)
        chart._text(p, lbl_rect, f"{val:.2f}", MUTED, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    # Divide horizontal space for factors
    sub_width = plot_rect.width() / n_factors

    grand_mean = r.get('grand_mean', 0.0)
    gm_y = y_to_px(grand_mean)

    for f_idx, summ in enumerate(factor_summaries):
        sub_left = plot_rect.left() + f_idx * sub_width
        sub_rect = QRectF(sub_left, plot_rect.top(), sub_width, plot_rect.height())

        # Sub-panel border
        p.setPen(QPen(QColor(BORDER), 1.0))
        p.drawRect(sub_rect)

        # Factor name label at bottom
        f_name_rect = QRectF(sub_rect.left(), plot_rect.bottom() + 18, sub_rect.width(), 16)
        chart._text(p, f_name_rect, summ.get('factor_name', ''), INK, Qt.AlignmentFlag.AlignCenter, bold=True)

        # Dashed Grand Mean line across each sub-panel
        pen_dash = QPen(QColor(MUTED), 1.0, Qt.PenStyle.DashLine)
        p.setPen(pen_dash)
        p.drawLine(QPointF(sub_rect.left(), gm_y), QPointF(sub_rect.right(), gm_y))

        # Level stats
        stats = summ.get('level_stats', [])
        n_levels = len(stats)
        if n_levels == 0:
            continue

        step_x = sub_rect.width() / (n_levels + 1)
        pts: list[QPointF] = []

        for l_idx, s in enumerate(stats):
            x_pos = sub_rect.left() + (l_idx + 1) * step_x
            y_pos = y_to_px(s['mean'])
            pts.append(QPointF(x_pos, y_pos))

            # Level tick mark and label
            p.setPen(QPen(QColor(BORDER), 1.0))
            p.drawLine(QPointF(x_pos, sub_rect.bottom()), QPointF(x_pos, sub_rect.bottom() + 4))
            lvl_lbl_rect = QRectF(x_pos - 25, sub_rect.bottom() + 4, 50, 14)
            chart._text(p, lvl_lbl_rect, str(s['level']), MUTED, Qt.AlignmentFlag.AlignCenter)

        # Connecting line
        if len(pts) > 1:
            p.setPen(QPen(QColor(BLUE), 2.0))
            path = QPainterPath()
            path.moveTo(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
            p.drawPath(path)

        # Data markers
        p.setPen(QPen(QColor(INK), 1.0))
        p.setBrush(QColor(BLUE))
        for pt in pts:
            p.drawEllipse(pt, 4.0, 4.0)

    # Label for grand mean on far right
    chart._text(p, QRectF(plot_rect.right() - 80, gm_y - 14, 75, 12), f"Mean={grand_mean:.2f}", MUTED, Qt.AlignmentFlag.AlignRight)


def _draw_interactions(chart, p: QPainter, area: QRectF, r: dict[str, Any]) -> None:
    fa_name = r.get('factor_a_name', 'Factor A')
    fb_name = r.get('factor_b_name', 'Factor B')
    resp_name = r.get('response_name', 'Response')

    title_rect = QRectF(area.left(), area.top() + 4, area.width(), 22)
    chart._text(p, title_rect, f"Interaction Plot for {resp_name} (Data Means)", INK, Qt.AlignmentFlag.AlignCenter, bold=True)

    plot_rect = area.adjusted(55, 34, -135, -38)
    p.setPen(QPen(QColor(BORDER), 1.0))
    p.drawRect(plot_rect)

    levels_a = r.get('levels_a', [])
    levels_b = r.get('levels_b', [])
    curves = r.get('curves', [])
    if not levels_a or not curves:
        return

    # Y bounds
    min_mean = r.get('min_mean', 0.0)
    max_mean = r.get('max_mean', 0.0)
    if min_mean == max_mean:
        min_mean -= 1.0
        max_mean += 1.0
    pad = (max_mean - min_mean) * 0.15
    min_y = min_mean - pad
    max_y = max_mean + pad

    def y_to_px(val: float) -> float:
        ratio = (val - min_y) / (max_y - min_y)
        return plot_rect.bottom() - ratio * plot_rect.height()

    # Draw Y axis ticks and labels
    p.setPen(QPen(QColor(BORDER), 1.0))
    n_y_ticks = 5
    for i in range(n_y_ticks + 1):
        frac = i / n_y_ticks
        val = min_y + frac * (max_y - min_y)
        y_pos = y_to_px(val)
        p.drawLine(QPointF(plot_rect.left() - 4, y_pos), QPointF(plot_rect.left(), y_pos))
        lbl_rect = QRectF(area.left(), y_pos - 8, 48, 16)
        chart._text(p, lbl_rect, f"{val:.2f}", MUTED, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    # X axis mapping
    n_a = len(levels_a)
    step_x = plot_rect.width() / (n_a + 1)
    a_x_map: dict[str, float] = {}

    for i, a in enumerate(levels_a):
        x_pos = plot_rect.left() + (i + 1) * step_x
        a_x_map[a] = x_pos
        p.setPen(QPen(QColor(BORDER), 1.0))
        p.drawLine(QPointF(x_pos, plot_rect.bottom()), QPointF(x_pos, plot_rect.bottom() + 4))
        lbl_rect = QRectF(x_pos - 35, plot_rect.bottom() + 5, 70, 14)
        chart._text(p, lbl_rect, str(a), MUTED, Qt.AlignmentFlag.AlignCenter)

    # X axis factor name label
    fa_lbl_rect = QRectF(plot_rect.left(), plot_rect.bottom() + 20, plot_rect.width(), 16)
    chart._text(p, fa_lbl_rect, fa_name, INK, Qt.AlignmentFlag.AlignCenter, bold=True)

    # Draw curves for each Factor B level
    for idx, curve in enumerate(curves):
        color_hex = SERIES_COLORS[idx % len(SERIES_COLORS)]
        color = QColor(color_hex)
        pts: list[QPointF] = []

        for pt in curve.get('points', []):
            a_lvl = pt.get('factor_a_level')
            m = pt.get('mean')
            if m is not None and a_lvl in a_x_map:
                pts.append(QPointF(a_x_map[a_lvl], y_to_px(m)))

        if len(pts) > 1:
            p.setPen(QPen(color, 2.0))
            path = QPainterPath()
            path.moveTo(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
            p.drawPath(path)

        p.setPen(QPen(QColor(INK), 1.0))
        p.setBrush(color)
        for pt in pts:
            p.drawEllipse(pt, 4.0, 4.0)

    # Legend on right side
    legend_rect = QRectF(plot_rect.right() + 15, plot_rect.top() + 10, 110, 20 + len(levels_b) * 20)
    p.setPen(QPen(QColor(BORDER), 1.0))
    p.setBrush(QColor('#ffffff'))
    p.drawRect(legend_rect)

    p.setBrush(Qt.BrushStyle.NoBrush)
    chart._text(p, QRectF(legend_rect.left() + 6, legend_rect.top() + 4, legend_rect.width() - 12, 14), fb_name, INK, Qt.AlignmentFlag.AlignLeft, bold=True)

    for idx, b_lvl in enumerate(levels_b):
        y_item = legend_rect.top() + 22 + idx * 20
        color_hex = SERIES_COLORS[idx % len(SERIES_COLORS)]
        color = QColor(color_hex)

        # Line sample and marker
        p.setPen(QPen(color, 2.0))
        p.drawLine(QPointF(legend_rect.left() + 8, y_item + 6), QPointF(legend_rect.left() + 24, y_item + 6))
        p.setBrush(color)
        p.setPen(QPen(QColor(INK), 1.0))
        p.drawEllipse(QPointF(legend_rect.left() + 16, y_item + 6), 3.5, 3.5)

        # Text
        chart._text(p, QRectF(legend_rect.left() + 30, y_item, legend_rect.width() - 34, 16), str(b_lvl), MUTED, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
