"""Chart renderer for One-Way ANOVA: Means Interval Plot, Differences of Means Interval Plots, and Residual Plots."""
from __future__ import annotations

import math
from typing import Any
import numpy as np
from scipy import stats
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


def supported(result: dict[str, Any]) -> bool:
    if not isinstance(result, dict) or result.get('analysis') != 'oneway_anova':
        return False
    return bool(result.get('means') or result.get('residuals') or result.get('comparisons'))


def _fmt(val: float | None, dec: int = 3) -> str:
    if val is None or math.isnan(val):
        return ''
    return f'{val:.{dec}f}'


def _bounds(values: list[float], pad_frac: float = 0.08) -> tuple[float, float]:
    clean = [v for v in values if v is not None and not math.isnan(v) and not math.isinf(v)]
    if not clean:
        return (0.0, 1.0)
    lo, hi = min(clean), max(clean)
    if lo == hi:
        delta = max(0.5, abs(lo) * 0.05)
        return (lo - delta, hi + delta)
    pad = (hi - lo) * pad_frac
    return (lo - pad, hi + pad)


def prepare(chart, result: dict[str, Any]) -> None:
    chart.panels = []
    chart.panel_columns = 1
    chart.note = ''

    opts = result.get('options', {})
    graphs = opts.get('graphs', {})
    resp_name = result.get('response_name', 'Response')
    factor_name = result.get('factor_name', 'Factor')
    means_data = result.get('means', [])

    # 1. Means Interval Plot (default on)
    if graphs.get('interval_plot', True) and means_data:
        chart.panels.append({
            'kind': 'oneway_interval',
            'title': f'Interval Plot of {resp_name} vs {factor_name}',
            'response_name': resp_name,
            'factor_name': factor_name,
            'means': means_data,
            'grand_mean': result.get('grand_mean', 0.0),
            's_pooled': result.get('s_pooled'),
            'equal_variances': opts.get('assume_equal_variances', True),
            'confidence': opts.get('confidence', 0.95),
        })

    # 2. Differences of Means Interval Plots (if comparisons selected)
    comps = result.get('comparisons', {})
    for comp_key, comp_name in [
        ('tukey', 'Tukey'),
        ('fisher', 'Fisher'),
        ('dunnett', 'Dunnett'),
        ('games_howell', 'Games-Howell'),
    ]:
        if comp_key in comps and opts.get('comparisons', {}).get('interval_plot', True):
            c_data = comps[comp_key]
            tests = c_data.get('tests', [])
            if tests:
                chart.panels.append({
                    'kind': 'oneway_differences',
                    'title': f'{comp_name} Simultaneous Differences of Means ({resp_name})',
                    'method_name': comp_name,
                    'response_name': resp_name,
                    'factor_name': factor_name,
                    'tests': tests,
                    'confidence': opts.get('confidence', 0.95),
                })

    # 3. Individual value plot
    if graphs.get('individual_value_plot', False):
        raw_pairs = result.get('raw_pairs', [])
        chart.panels.append({
            'kind': 'oneway_individual_values',
            'title': f'Individual Value Plot of {resp_name} vs {factor_name}',
            'response_name': resp_name,
            'factor_name': factor_name,
            'raw_pairs': raw_pairs,
            'levels': result.get('factor_info', {}).get('values', []),
        })

    # 4. Boxplot
    if graphs.get('boxplot', False):
        chart.panels.append({
            'kind': 'oneway_boxplot',
            'title': f'Boxplot of {resp_name} vs {factor_name}',
            'response_name': resp_name,
            'factor_name': factor_name,
            'raw_pairs': result.get('raw_pairs', []),
            'levels': result.get('factor_info', {}).get('values', []),
        })

    # 5. Residual plots
    res_mode = graphs.get('residual_mode', 'none')
    residuals = result.get('residuals', [])
    fits = result.get('fits', [])
    orders = result.get('observation_order', list(range(1, len(residuals) + 1)))

    if res_mode == 'four_in_one' and residuals:
        chart.panels.append({
            'kind': 'oneway_four_in_one',
            'title': f'Residual Plots for {resp_name}',
            'residuals': residuals,
            'fits': fits,
            'orders': orders,
        })
    elif res_mode == 'individual' and residuals:
        if graphs.get('res_normal', False):
            chart.panels.append({
                'kind': 'oneway_res_normal',
                'title': f'Normal Probability Plot of Residuals for {resp_name}',
                'residuals': residuals,
            })
        if graphs.get('res_fits', False):
            chart.panels.append({
                'kind': 'oneway_res_fits',
                'title': f'Residuals Versus Fits for {resp_name}',
                'residuals': residuals,
                'fits': fits,
            })
        if graphs.get('res_histogram', False):
            chart.panels.append({
                'kind': 'oneway_res_hist',
                'title': f'Histogram of Residuals for {resp_name}',
                'residuals': residuals,
            })
        if graphs.get('res_order', False):
            chart.panels.append({
                'kind': 'oneway_res_order',
                'title': f'Residuals Versus Order for {resp_name}',
                'residuals': residuals,
                'orders': orders,
            })

    if not chart.panels:
        # Fallback to means interval plot
        chart.panels.append({
            'kind': 'oneway_interval',
            'title': f'Interval Plot of {resp_name} vs {factor_name}',
            'response_name': resp_name,
            'factor_name': factor_name,
            'means': means_data,
            'grand_mean': result.get('grand_mean', 0.0),
            's_pooled': result.get('s_pooled'),
            'equal_variances': opts.get('assume_equal_variances', True),
            'confidence': opts.get('confidence', 0.95),
        })

    chart.panel_columns = 1
    chart.setMinimumWidth(720)
    chart.setMinimumHeight(max(440, 380 * len(chart.panels)))
    note_parts = []
    if opts.get('assume_equal_variances', True):
        note_parts.append('The pooled standard deviation is used to calculate the intervals.')
    else:
        note_parts.append('Individual standard deviations are used to calculate the intervals.')
    chart.note = '   '.join(note_parts)


def _draw_interval_plot(chart, p: QPainter, area: QRectF, panel: dict[str, Any]) -> None:
    means_data = panel['means']
    k = len(means_data)
    if k == 0:
        return

    all_y = []
    for r in means_data:
        all_y.append(r['mean'])
        if r.get('ci_low') is not None:
            all_y.append(r['ci_low'])
        if r.get('ci_high') is not None:
            all_y.append(r['ci_high'])
    all_y.append(panel.get('grand_mean', 0.0))

    y_min, y_max = _bounds(all_y, pad_frac=0.12)

    plot = QRectF(
        area.left() + 66.0,
        area.top() + 32.0,
        max(120.0, area.width() - 84.0),
        max(100.0, area.height() - 76.0),
    )
    chart.remember_axes(plot)

    p.fillRect(plot, QColor('#ffffff'))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(BORDER), 1.0))
    p.drawRect(plot)

    y_map = lambda v: plot.bottom() - ((float(v) - y_min) / max(1e-12, y_max - y_min)) * plot.height()

    # Y-axis grid and ticks
    p.setFont(QFont('Segoe UI', 8))
    for i in range(5):
        frac = i / 4.0
        y_val = y_min + frac * (y_max - y_min)
        py = plot.bottom() - frac * plot.height()
        p.setPen(QPen(QColor('#eef2f5'), 1.0))
        p.drawLine(QPointF(plot.left(), py), QPointF(plot.right(), py))
        chart._text(
            p,
            QRectF(area.left() + 10, py - 8, 52, 16),
            _fmt(y_val, 2),
            MUTED,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

    # Grand mean line
    gm = panel.get('grand_mean')
    if gm is not None and y_min <= gm <= y_max:
        g_py = y_map(gm)
        p.setPen(QPen(QColor('#8c9ba5'), 1.1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(plot.left() + 2, g_py), QPointF(plot.right() - 2, g_py))

    # X positions for each level
    x_step = plot.width() / (k + 1)
    for idx, r in enumerate(means_data):
        px = plot.left() + (idx + 1) * x_step
        m = r['mean']
        py_m = y_map(m)

        ci_l = r.get('ci_low')
        ci_h = r.get('ci_high')

        if ci_l is not None and ci_h is not None:
            py_l = y_map(ci_l)
            py_h = y_map(ci_h)
            # Vertical error bar
            p.setPen(QPen(QColor(BLUE), 1.8))
            p.drawLine(QPointF(px, py_l), QPointF(px, py_h))
            # Caps
            p.drawLine(QPointF(px - 5, py_l), QPointF(px + 5, py_l))
            p.drawLine(QPointF(px - 5, py_h), QPointF(px + 5, py_h))

        # Mean marker
        p.setPen(QPen(QColor('#ffffff'), 1.2))
        p.setBrush(QColor(BLUE))
        p.drawEllipse(QPointF(px, py_m), 4.2, 4.2)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # X tick label
        p.setFont(QFont('Segoe UI', 8.5))
        chart._text(
            p,
            QRectF(px - 40, plot.bottom() + 4, 80, 18),
            str(r['level'])[:16],
            SLATE,
            Qt.AlignmentFlag.AlignCenter,
        )

    # X axis label
    p.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
    chart._text(
        p,
        QRectF(plot.left(), plot.bottom() + 24, plot.width(), 20),
        str(panel.get('factor_name', 'Factor')),
        SLATE,
        Qt.AlignmentFlag.AlignCenter,
    )

    # Y axis label
    p.save()
    p.translate(area.left() + 14, plot.center().y())
    p.rotate(-90)
    chart._text(
        p,
        QRectF(-plot.height() / 2, -10, plot.height(), 20),
        str(panel.get('response_name', 'Response')),
        SLATE,
        Qt.AlignmentFlag.AlignCenter,
    )
    p.restore()


def _draw_differences_plot(chart, p: QPainter, area: QRectF, panel: dict[str, Any]) -> None:
    tests = panel.get('tests', [])
    m = len(tests)
    if m == 0:
        return

    all_x = [0.0]
    for t in tests:
        all_x.append(t['difference'])
        if t.get('ci_low') is not None:
            all_x.append(t['ci_low'])
        if t.get('ci_high') is not None:
            all_x.append(t['ci_high'])

    x_min, x_max = _bounds(all_x, pad_frac=0.15)

    left_w = min(180.0, max(120.0, area.width() * 0.28))
    plot = QRectF(
        area.left() + left_w,
        area.top() + 32.0,
        max(120.0, area.width() - left_w - 24.0),
        max(100.0, area.height() - 72.0),
    )
    chart.remember_axes(plot)

    p.fillRect(plot, QColor('#ffffff'))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(BORDER), 1.0))
    p.drawRect(plot)

    x_map = lambda v: plot.left() + ((float(v) - x_min) / max(1e-12, x_max - x_min)) * plot.width()

    # Zero reference line
    if x_min <= 0.0 <= x_max:
        p0 = x_map(0.0)
        p.setPen(QPen(QColor(RED), 1.2, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(p0, plot.top() + 2), QPointF(p0, plot.bottom() - 2))

    # X axis grid and ticks
    p.setFont(QFont('Segoe UI', 8))
    for i in range(5):
        frac = i / 4.0
        x_val = x_min + frac * (x_max - x_min)
        px = plot.left() + frac * plot.width()
        p.setPen(QPen(QColor('#eef2f5'), 1.0))
        p.drawLine(QPointF(px, plot.top()), QPointF(px, plot.bottom()))
        chart._text(
            p,
            QRectF(px - 32, plot.bottom() + 4, 64, 16),
            _fmt(x_val, 2),
            MUTED,
            Qt.AlignmentFlag.AlignCenter,
        )

    # Horizontal difference intervals
    y_step = plot.height() / (m + 1)
    for idx, t in enumerate(tests):
        py = plot.top() + (idx + 1) * y_step
        diff = t['difference']
        px_diff = x_map(diff)

        ci_l = t.get('ci_low')
        ci_h = t.get('ci_high')

        sig = t.get('significant', False)
        line_col = RED if sig else BLUE

        if ci_l is not None and ci_h is not None:
            px_l = x_map(ci_l)
            px_h = x_map(ci_h)
            p.setPen(QPen(QColor(line_col), 1.8))
            p.drawLine(QPointF(px_l, py), QPointF(px_h, py))
            p.drawLine(QPointF(px_l, py - 4), QPointF(px_l, py + 4))
            p.drawLine(QPointF(px_h, py - 4), QPointF(px_h, py + 4))

        # Diff marker
        p.setPen(QPen(QColor('#ffffff'), 1.1))
        p.setBrush(QColor(line_col))
        p.drawEllipse(QPointF(px_diff, py), 4.0, 4.0)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # Pair label on the left
        p.setFont(QFont('Segoe UI', 8.5))
        chart._text(
            p,
            QRectF(area.left() + 8, py - 9, left_w - 14, 18),
            str(t['pair_label']),
            SLATE,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

    # X axis label
    p.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
    chart._text(
        p,
        QRectF(plot.left(), plot.bottom() + 22, plot.width(), 20),
        f'Differences of Means ({panel.get("response_name", "")})',
        SLATE,
        Qt.AlignmentFlag.AlignCenter,
    )


def _draw_four_in_one(chart, p: QPainter, area: QRectF, panel: dict[str, Any]) -> None:
    residuals = panel['residuals']
    fits = panel['fits']
    orders = panel['orders']
    n = len(residuals)
    if n == 0:
        return

    mid_x = area.left() + area.width() / 2.0
    mid_y = area.top() + area.height() / 2.0

    cells = [
        QRectF(area.left() + 4, area.top() + 22, area.width() / 2.0 - 8, area.height() / 2.0 - 26),
        QRectF(mid_x + 4, area.top() + 22, area.width() / 2.0 - 8, area.height() / 2.0 - 26),
        QRectF(area.left() + 4, mid_y + 4, area.width() / 2.0 - 8, area.height() / 2.0 - 26),
        QRectF(mid_x + 4, mid_y + 4, area.width() / 2.0 - 8, area.height() / 2.0 - 26),
    ]

    titles = [
        'Normal Probability Plot',
        'Versus Fits',
        'Histogram',
        'Versus Order',
    ]

    for cell, title in zip(cells, titles):
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(BORDER), 0.9))
        p.drawRect(cell)
        hdr = QRectF(cell.left(), cell.top(), cell.width(), 18)
        p.fillRect(hdr, QColor('#f4f7f9'))
        p.setPen(QPen(QColor(BORDER), 0.9))
        p.drawRect(hdr)
        p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
        chart._text(p, hdr, title, SLATE, Qt.AlignmentFlag.AlignCenter)

    # 1. Normal Probability Plot (top-left)
    p1 = cells[0].adjusted(36, 24, -12, -22)
    s_res = sorted(residuals)
    probs = [(i + 0.5) / n for i in range(n)]
    norm_scores = [float(stats.norm.ppf(pr)) for pr in probs]
    rx_min, rx_max = _bounds(s_res)
    ry_min, ry_max = _bounds(norm_scores)
    p.fillRect(p1, QColor('#ffffff'))
    p.setPen(QPen(QColor(BORDER), 0.8))
    p.drawRect(p1)
    x_m = lambda v: p1.left() + ((v - rx_min) / max(1e-12, rx_max - rx_min)) * p1.width()
    y_m = lambda v: p1.bottom() - ((v - ry_min) / max(1e-12, ry_max - ry_min)) * p1.height()
    # Line
    p.setPen(QPen(QColor(RED), 1.0, Qt.PenStyle.DashLine))
    p.drawLine(QPointF(x_m(rx_min), y_m(ry_min)), QPointF(x_m(rx_max), y_m(ry_max)))
    p.setPen(QPen(QColor('#ffffff'), 0.8))
    p.setBrush(QColor(BLUE))
    for r_val, z_val in zip(s_res, norm_scores):
        p.drawEllipse(QPointF(x_m(r_val), y_m(z_val)), 2.8, 2.8)
    p.setBrush(Qt.BrushStyle.NoBrush)

    # 2. Versus Fits (top-right)
    p2 = cells[1].adjusted(36, 24, -12, -22)
    fx_min, fx_max = _bounds(fits)
    fy_min, fy_max = _bounds(residuals)
    p.fillRect(p2, QColor('#ffffff'))
    p.setPen(QPen(QColor(BORDER), 0.8))
    p.drawRect(p2)
    x2_m = lambda v: p2.left() + ((v - fx_min) / max(1e-12, fx_max - fx_min)) * p2.width()
    y2_m = lambda v: p2.bottom() - ((v - fy_min) / max(1e-12, fy_max - fy_min)) * p2.height()
    if fy_min <= 0.0 <= fy_max:
        p.setPen(QPen(QColor('#92a0ac'), 1.0, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(p2.left(), y2_m(0.0)), QPointF(p2.right(), y2_m(0.0)))
    p.setPen(QPen(QColor('#ffffff'), 0.8))
    p.setBrush(QColor(BLUE))
    for f_val, r_val in zip(fits, residuals):
        p.drawEllipse(QPointF(x2_m(f_val), y2_m(r_val)), 2.8, 2.8)
    p.setBrush(Qt.BrushStyle.NoBrush)

    # 3. Histogram (bottom-left)
    p3 = cells[2].adjusted(36, 24, -12, -22)
    p.fillRect(p3, QColor('#ffffff'))
    p.setPen(QPen(QColor(BORDER), 0.8))
    p.drawRect(p3)
    counts, bin_edges = np.histogram(residuals, bins=max(5, min(12, int(math.sqrt(n)))))
    max_c = max(counts) if len(counts) else 1
    bx_m = lambda v: p3.left() + ((v - rx_min) / max(1e-12, rx_max - rx_min)) * p3.width()
    by_m = lambda c: p3.bottom() - (c / max(1, max_c)) * p3.height()
    for bi in range(len(counts)):
        b_rect = QRectF(bx_m(bin_edges[bi]), by_m(counts[bi]), bx_m(bin_edges[bi + 1]) - bx_m(bin_edges[bi]), p3.bottom() - by_m(counts[bi]))
        p.fillRect(b_rect, QColor('#b0cde5'))
        p.setPen(QPen(QColor(BLUE), 1.0))
        p.drawRect(b_rect)

    # 4. Versus Order (bottom-right)
    p4 = cells[3].adjusted(36, 24, -12, -22)
    p.fillRect(p4, QColor('#ffffff'))
    p.setPen(QPen(QColor(BORDER), 0.8))
    p.drawRect(p4)
    ox_min, ox_max = _bounds(orders)
    x4_m = lambda v: p4.left() + ((v - ox_min) / max(1e-12, ox_max - ox_min)) * p4.width()
    y4_m = lambda v: p4.bottom() - ((v - fy_min) / max(1e-12, fy_max - fy_min)) * p4.height()
    if fy_min <= 0.0 <= fy_max:
        p.setPen(QPen(QColor('#92a0ac'), 1.0, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(p4.left(), y4_m(0.0)), QPointF(p4.right(), y4_m(0.0)))
    pts4 = [QPointF(x4_m(o), y4_m(r)) for o, r in zip(orders, residuals)]
    if len(pts4) > 1:
        path = QPainterPath(pts4[0])
        for pt in pts4[1:]:
            path.lineTo(pt)
        p.setPen(QPen(QColor(SLATE), 1.0))
        p.drawPath(path)
    p.setPen(QPen(QColor('#ffffff'), 0.8))
    p.setBrush(QColor(BLUE))
    for pt in pts4:
        p.drawEllipse(pt, 2.8, 2.8)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _draw_individual_values(chart, p: QPainter, area: QRectF, panel: dict[str, Any]) -> None:
    raw_pairs = panel.get('raw_pairs', [])
    levels = panel.get('levels', [])
    if not raw_pairs or not levels:
        return
    k = len(levels)
    plot_rect = area.adjusted(65, 35, -30, -55)
    p.fillRect(plot_rect, QColor('#ffffff'))
    p.setPen(QPen(QColor(BORDER), 1.0))
    p.drawRect(plot_rect)

    all_y = [y for y, _, _ in raw_pairs]
    y_min, y_max = _bounds(all_y)
    y_to_px = lambda y: plot_rect.bottom() - ((y - y_min) / max(1e-12, y_max - y_min)) * plot_rect.height()
    col_w = plot_rect.width() / max(1, k)

    # Grid & ticks
    p.setFont(QFont('Segoe UI', 8))
    for i in range(5):
        val = y_min + (y_max - y_min) * (i / 4.0)
        y_px = y_to_px(val)
        p.setPen(QPen(QColor('#eef2f5'), 1.0))
        p.drawLine(QPointF(plot_rect.left(), y_px), QPointF(plot_rect.right(), y_px))
        lbl = _fmt(val, 2)
        chart._text(p, QRectF(area.left(), y_px - 8, 60, 16), lbl, MUTED, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    p.setPen(QPen(QColor('#ffffff'), 0.8))
    p.setBrush(QColor(BLUE))
    for y, lv, _ in raw_pairs:
        if lv in levels:
            c_idx = levels.index(lv)
            cx = plot_rect.left() + (c_idx + 0.5) * col_w
            # slight jitter based on hash
            jit = ((hash(str(y)) % 100) / 100.0 - 0.5) * min(20.0, col_w * 0.4)
            p.drawEllipse(QPointF(cx + jit, y_to_px(y)), 3.2, 3.2)
    p.setBrush(Qt.BrushStyle.NoBrush)

    for i, lv in enumerate(levels):
        cx = plot_rect.left() + (i + 0.5) * col_w
        lbl_rect = QRectF(cx - col_w / 2.0, plot_rect.bottom() + 4, col_w, 20)
        chart._text(p, lbl_rect, str(lv), INK, Qt.AlignmentFlag.AlignCenter)

    chart._text(p, QRectF(area.left(), plot_rect.bottom() + 24, area.width(), 20), panel.get('factor_name', 'Factor'), SLATE, Qt.AlignmentFlag.AlignCenter)


def _draw_boxplot(chart, p: QPainter, area: QRectF, panel: dict[str, Any]) -> None:
    raw_pairs = panel.get('raw_pairs', [])
    levels = panel.get('levels', [])
    if not raw_pairs or not levels:
        return
    k = len(levels)
    plot_rect = area.adjusted(65, 35, -30, -55)
    p.fillRect(plot_rect, QColor('#ffffff'))
    p.setPen(QPen(QColor(BORDER), 1.0))
    p.drawRect(plot_rect)

    all_y = [y for y, _, _ in raw_pairs]
    y_min, y_max = _bounds(all_y)
    y_to_px = lambda y: plot_rect.bottom() - ((y - y_min) / max(1e-12, y_max - y_min)) * plot_rect.height()
    col_w = plot_rect.width() / max(1, k)

    # Grid & ticks
    p.setFont(QFont('Segoe UI', 8))
    for i in range(5):
        val = y_min + (y_max - y_min) * (i / 4.0)
        y_px = y_to_px(val)
        p.setPen(QPen(QColor('#eef2f5'), 1.0))
        p.drawLine(QPointF(plot_rect.left(), y_px), QPointF(plot_rect.right(), y_px))
        lbl = _fmt(val, 2)
        chart._text(p, QRectF(area.left(), y_px - 8, 60, 16), lbl, MUTED, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    for i, lv in enumerate(levels):
        vals = sorted([y for y, x, _ in raw_pairs if x == lv])
        if not vals:
            continue
        cx = plot_rect.left() + (i + 0.5) * col_w
        bw = min(36.0, col_w * 0.5)
        n = len(vals)
        q1 = vals[int(0.25 * (n - 1))]
        med = vals[int(0.5 * (n - 1))]
        q3 = vals[int(0.75 * (n - 1))]
        iqr = q3 - q1
        lo_fence = q1 - 1.5 * iqr
        hi_fence = q3 + 1.5 * iqr
        inliers = [v for v in vals if lo_fence <= v <= hi_fence]
        outliers = [v for v in vals if v < lo_fence or v > hi_fence]
        lo_whisker = min(inliers) if inliers else vals[0]
        hi_whisker = max(inliers) if inliers else vals[-1]

        # Whisker lines
        p.setPen(QPen(QColor(SLATE), 1.0))
        p.drawLine(QPointF(cx, y_to_px(lo_whisker)), QPointF(cx, y_to_px(q1)))
        p.drawLine(QPointF(cx, y_to_px(q3)), QPointF(cx, y_to_px(hi_whisker)))
        p.drawLine(QPointF(cx - bw * 0.3, y_to_px(lo_whisker)), QPointF(cx + bw * 0.3, y_to_px(lo_whisker)))
        p.drawLine(QPointF(cx - bw * 0.3, y_to_px(hi_whisker)), QPointF(cx + bw * 0.3, y_to_px(hi_whisker)))

        # Box
        b_rect = QRectF(cx - bw / 2.0, y_to_px(q3), bw, y_to_px(q1) - y_to_px(q3))
        p.fillRect(b_rect, QColor('#e6f0fa'))
        p.setPen(QPen(QColor(BLUE), 1.2))
        p.drawRect(b_rect)

        # Median
        p.setPen(QPen(QColor(RED), 1.8))
        p.drawLine(QPointF(cx - bw / 2.0, y_to_px(med)), QPointF(cx + bw / 2.0, y_to_px(med)))

        # Outliers
        if outliers:
            p.setPen(QPen(QColor(RED), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for ov in outliers:
                p.drawEllipse(QPointF(cx, y_to_px(ov)), 3.0, 3.0)

        lbl_rect = QRectF(cx - col_w / 2.0, plot_rect.bottom() + 4, col_w, 20)
        chart._text(p, lbl_rect, str(lv), INK, Qt.AlignmentFlag.AlignCenter)

    chart._text(p, QRectF(area.left(), plot_rect.bottom() + 24, area.width(), 20), panel.get('factor_name', 'Factor'), SLATE, Qt.AlignmentFlag.AlignCenter)


def draw_panel(chart, p: QPainter, area: QRectF, panel: dict[str, Any]) -> None:
    kind = panel['kind']
    if kind == 'oneway_interval':
        _draw_interval_plot(chart, p, area, panel)
    elif kind == 'oneway_differences':
        _draw_differences_plot(chart, p, area, panel)
    elif kind == 'oneway_four_in_one':
        _draw_four_in_one(chart, p, area, panel)
    elif kind == 'oneway_individual_values':
        _draw_individual_values(chart, p, area, panel)
    elif kind == 'oneway_boxplot':
        _draw_boxplot(chart, p, area, panel)
    elif kind in ('oneway_res_normal', 'oneway_res_fits', 'oneway_res_hist', 'oneway_res_order'):
        # Pass through single residual plot
        _draw_four_in_one(chart, p, area, {
            'residuals': panel.get('residuals', []),
            'fits': panel.get('fits', [0.0] * len(panel.get('residuals', []))),
            'orders': panel.get('orders', list(range(1, len(panel.get('residuals', [])) + 1))),
        })
    else:
        # Default interval plot fallback
        _draw_interval_plot(chart, p, area, panel)
