"""Chart renderer for Two-Way ANOVA: Main Effects Plots and Interaction Plots."""
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

SERIES_COLORS = [BLUE, RED, GREEN, PURPLE, ORANGE, TEAL, '#555555']


def supported(result: dict[str, Any]) -> bool:
    if not isinstance(result, dict) or result.get('analysis') != 'twoway_anova':
        return False
    return bool(result.get('factor_a_stats') and result.get('factor_b_stats'))


def prepare(chart, result: dict[str, Any]) -> None:
    chart.panels = []
    chart.panel_columns = 2
    chart.note = f"Two-Way ANOVA: {result.get('response_name')} vs {result.get('factor_a_name')}, {result.get('factor_b_name')}"

    # Panel 1: Main Effects Plot
    chart.panels.append({
        'kind': 'twoway_main_effects',
        'title': 'Main Effects Plot for ' + result.get('response_name', 'Response'),
        'result': result
    })

    # Panel 2: Interaction Plot
    chart.panels.append({
        'kind': 'twoway_interaction',
        'title': 'Interaction Plot for ' + result.get('response_name', 'Response'),
        'result': result
    })


def draw_panel(chart, p: QPainter, area: QRectF, panel: dict[str, Any]) -> None:
    kind = panel['kind']
    if kind == 'twoway_main_effects':
        _draw_main_effects(chart, p, area, panel['result'])
    elif kind == 'twoway_interaction':
        _draw_interaction(chart, p, area, panel['result'])


def _draw_main_effects(chart, p: QPainter, area: QRectF, r: dict[str, Any]) -> None:
    title_rect = QRectF(area.left(), area.top() + 4, area.width(), 22)
    chart._text(p, title_rect, "Main Effects Plot (Fitted Means)", INK, Qt.AlignmentFlag.AlignCenter, bold=True)

    plot_rect = area.adjusted(45, 32, -20, -35)
    p.setPen(QPen(QColor(BORDER), 1.0))
    p.drawRect(plot_rect)

    # Collect all means to determine Y range
    all_means = [s['mean'] for s in r.get('factor_a_stats', [])] + [s['mean'] for s in r.get('factor_b_stats', [])]
    grand_mean = r.get('grand_mean', 0.0)
    all_means.append(grand_mean)

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

    # Draw grand mean reference line
    gm_y = y_to_px(grand_mean)
    p.setPen(QPen(QColor(MUTED), 1.0, Qt.PenStyle.DashLine))
    p.drawLine(QPointF(plot_rect.left(), gm_y), QPointF(plot_rect.right(), gm_y))

    # Split plot horizontally into two factor regions
    half_w = plot_rect.width() / 2.0
    r_a = QRectF(plot_rect.left(), plot_rect.top(), half_w, plot_rect.height())
    r_b = QRectF(plot_rect.left() + half_w, plot_rect.top(), half_w, plot_rect.height())

    # Divider line
    p.setPen(QPen(QColor(BORDER), 1.0, Qt.PenStyle.DotLine))
    p.drawLine(QPointF(r_a.right(), plot_rect.top()), QPointF(r_a.right(), plot_rect.bottom()))

    # Factor A Plot
    stats_a = r.get('factor_a_stats', [])
    pts_a = []
    if stats_a:
        spacing = r_a.width() / (len(stats_a) + 1)
        for idx, s in enumerate(stats_a):
            cx = r_a.left() + (idx + 1) * spacing
            cy = y_to_px(s['mean'])
            pts_a.append(QPointF(cx, cy))
            chart._text(p, QRectF(cx - spacing / 2.0, plot_rect.bottom() + 4, spacing, 18),
                        str(s['level']), SLATE, Qt.AlignmentFlag.AlignCenter)

        p.setPen(QPen(QColor(BLUE), 2.0))
        for i in range(len(pts_a) - 1):
            p.drawLine(pts_a[i], pts_a[i + 1])
        p.setBrush(QColor(BLUE))
        for pt in pts_a:
            p.drawEllipse(pt, 4.0, 4.0)

    chart._text(p, QRectF(r_a.left(), plot_rect.bottom() + 20, r_a.width(), 16),
                r.get('factor_a_name', 'Factor A'), INK, Qt.AlignmentFlag.AlignCenter, bold=True)

    # Factor B Plot
    stats_b = r.get('factor_b_stats', [])
    pts_b = []
    if stats_b:
        spacing = r_b.width() / (len(stats_b) + 1)
        for idx, s in enumerate(stats_b):
            cx = r_b.left() + (idx + 1) * spacing
            cy = y_to_px(s['mean'])
            pts_b.append(QPointF(cx, cy))
            chart._text(p, QRectF(cx - spacing / 2.0, plot_rect.bottom() + 4, spacing, 18),
                        str(s['level']), SLATE, Qt.AlignmentFlag.AlignCenter)

        p.setPen(QPen(QColor(RED), 2.0))
        for i in range(len(pts_b) - 1):
            p.drawLine(pts_b[i], pts_b[i + 1])
        p.setBrush(QColor(RED))
        for pt in pts_b:
            p.drawEllipse(pt, 4.0, 4.0)

    chart._text(p, QRectF(r_b.left(), plot_rect.bottom() + 20, r_b.width(), 16),
                r.get('factor_b_name', 'Factor B'), INK, Qt.AlignmentFlag.AlignCenter, bold=True)


def _draw_interaction(chart, p: QPainter, area: QRectF, r: dict[str, Any]) -> None:
    title_rect = QRectF(area.left(), area.top() + 4, area.width(), 22)
    chart._text(p, title_rect, "Interaction Plot for " + r.get('response_name', 'Response'), INK, Qt.AlignmentFlag.AlignCenter, bold=True)

    plot_rect = area.adjusted(45, 32, -90, -35)
    p.setPen(QPen(QColor(BORDER), 1.0))
    p.drawRect(plot_rect)

    levels_a = r.get('levels_a', [])
    levels_b = r.get('levels_b', [])
    cell_stats = r.get('cell_stats', [])

    all_means = []
    for row in cell_stats:
        for c in row:
            if c.get('count', 0) > 0:
                all_means.append(c['mean'])

    if not all_means:
        return

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

    spacing = plot_rect.width() / (len(levels_a) + 1)
    x_coords = [plot_rect.left() + (i + 1) * spacing for i in range(len(levels_a))]

    # Draw X axis tick labels
    for i, lvl_a in enumerate(levels_a):
        chart._text(p, QRectF(x_coords[i] - spacing / 2.0, plot_rect.bottom() + 4, spacing, 18),
                    str(lvl_a), SLATE, Qt.AlignmentFlag.AlignCenter)

    chart._text(p, QRectF(plot_rect.left(), plot_rect.bottom() + 20, plot_rect.width(), 16),
                r.get('factor_a_name', 'Factor A'), INK, Qt.AlignmentFlag.AlignCenter, bold=True)

    # For each level of Factor B, plot line across Factor A levels
    for b_idx, lvl_b in enumerate(levels_b):
        color = QColor(SERIES_COLORS[b_idx % len(SERIES_COLORS)])
        pts = []
        for a_idx in range(len(levels_a)):
            c = cell_stats[a_idx][b_idx]
            if c.get('count', 0) > 0:
                pts.append(QPointF(x_coords[a_idx], y_to_px(c['mean'])))

        p.setPen(QPen(color, 2.0))
        for i in range(len(pts) - 1):
            p.drawLine(pts[i], pts[i + 1])
        p.setBrush(color)
        for pt in pts:
            p.drawEllipse(pt, 4.0, 4.0)

    # Legend on right side
    legend_rect = QRectF(plot_rect.right() + 10, plot_rect.top() + 10, 75, len(levels_b) * 22 + 25)
    chart._text(p, QRectF(legend_rect.left(), legend_rect.top(), legend_rect.width(), 18),
                r.get('factor_b_name', 'Factor B'), INK, Qt.AlignmentFlag.AlignLeft, bold=True)
    for b_idx, lvl_b in enumerate(levels_b):
        color = QColor(SERIES_COLORS[b_idx % len(SERIES_COLORS)])
        ly = legend_rect.top() + 22 + b_idx * 20
        p.setPen(QPen(color, 2.0))
        p.drawLine(QPointF(legend_rect.left(), ly + 5), QPointF(legend_rect.left() + 14, ly + 5))
        p.setBrush(color)
        p.drawEllipse(QPointF(legend_rect.left() + 7, ly + 5), 3.0, 3.0)
        chart._text(p, QRectF(legend_rect.left() + 18, ly, 55, 18), str(lvl_b), SLATE, Qt.AlignmentFlag.AlignLeft)
