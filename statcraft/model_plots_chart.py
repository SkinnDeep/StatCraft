"""Standard statistical Factorial Plots, Model Contour Plot, and 3D Surface Plot for ChartWidget."""
import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainterPath, QPen, QPolygonF
from .spatial_view import DEFAULT_VIEW, project_point, camera_point, view_state

BLUE = '#056eb2'
RED = '#bb4147'
GREEN = '#2e8555'
ORANGE = '#c86d24'
PURPLE = '#7e52a0'
TEAL = '#268391'
SLATE = '#263440'
MUTED = '#5e6d78'
GRID_BG = '#fafafa'
BORDER = '#c6cfd6'

TRACE_COLORS = [BLUE, RED, GREEN, PURPLE, ORANGE, TEAL, '#7b6457', '#557a2b']
CONTOUR_PALETTE = [
    '#d0e1f2',
    '#a6c8e6',
    '#79add8',
    '#4d91c6',
    '#2b7bba',
    '#41998c',
    '#66b37d',
    '#94ca69',
    '#c2df58',
]


def _fmt(val):
    if val is None:
        return '*'
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if abs(val) < 1e-12:
            return '0'
        return format(float(val), '.4g')
    return str(val)


def _pad_bounds(vals):
    finite = [float(v) for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)]
    if not finite:
        return (0.0, 1.0)
    lo, hi = min(finite), max(finite)
    if lo == hi:
        delta = max(0.5, abs(lo) * 0.05)
        return (lo - delta, hi + delta)
    pad = (hi - lo) * 0.08
    return (lo - pad, hi + pad)


def _band_color(val, levels, z_min, z_max):
    if not levels:
        t = 0.5 if z_max <= z_min else max(0.0, min(1.0, (val - z_min) / (z_max - z_min)))
        idx = min(len(CONTOUR_PALETTE) - 1, int(t * len(CONTOUR_PALETTE)))
        return QColor(CONTOUR_PALETTE[idx])
    band = 0
    for lv in levels:
        if val >= lv:
            band += 1
        else:
            break
    n_bands = len(levels) + 1
    if n_bands <= 1:
        return QColor(CONTOUR_PALETTE[0])
    palette_idx = min(
        len(CONTOUR_PALETTE) - 1,
        round(band * (len(CONTOUR_PALETTE) - 1) / max(1, n_bands - 1)),
    )
    return QColor(CONTOUR_PALETTE[palette_idx])


def _surface_color(val, z_min, z_max):
    t = 0.5 if z_max <= z_min else max(0.0, min(1.0, (val - z_min) / (z_max - z_min)))
    if t < 0.5:
        u = t * 2.0
        r = int(54 + u * (63 - 54))
        g = int(112 + u * (160 - 112))
        b = int(160 + u * (140 - 160))
    else:
        u = (t - 0.5) * 2.0
        r = int(63 + u * (155 - 63))
        g = int(160 + u * (200 - 160))
        b = int(140 + u * (90 - 140))
    return QColor(r, g, b)


def _hold_note(holds):
    if not holds:
        return ''
    parts = [f"{h['name']} = {_fmt(h.get('value', h.get('display')))}" for h in holds]
    return 'Hold values: ' + ', '.join(parts)


def prepare(chart, result):
    chart.panels = []
    chart.panel_columns = 1
    chart.note = ''
    analysis = result.get('analysis')

    resp_name = result.get('response_name', 'Response')
    if result.get('is_probability') and result.get('event') is not None:
        y_label = f"Fitted Probability ({result['event']})"
    else:
        y_label = 'Fitted Mean'

    if analysis == 'factorial_plots':
        main_effects = result.get('main_effects', [])
        interactions = result.get('interactions', [])
        holds = result.get('hold_summary', [])
        options = result.get('options', {})

        if main_effects:
            all_y = []
            for me in main_effects:
                all_y.extend(me.get('fits', me.get('y', [])))
                if 'reference_mean' in me:
                    all_y.append(me['reference_mean'])
            ref_y = float(main_effects[0].get('reference_mean', 0.0))
            chart.panels.append(dict(
                kind='model_main_effects',
                title=f'Main Effects Plot for {resp_name} ({y_label})',
                items=main_effects,
                reference_y=ref_y,
                y_bounds=_pad_bounds(all_y),
                y_label=y_label,
                holds=holds,
            ))

        if interactions:
            all_iy = []
            for inter in interactions:
                for tr in inter.get('series', inter.get('traces', [])):
                    all_iy.extend(tr.get('fits', tr.get('y', [])))
            chart.panels.append(dict(
                kind='model_interaction',
                title=f'Interaction Plot for {resp_name} ({y_label})',
                items=interactions,
                y_bounds=_pad_bounds(all_iy),
                y_label=y_label,
                interaction_matrix=options.get('matrix_display', 'lower_left'),
                holds=holds,
            ))

        if not chart.panels:
            raise ValueError('Factorial Plots require at least one Main Effects or Interaction panel.')

        n_panels = len(chart.panels)
        inter_cols = min(3, max(1, len(interactions)))
        inter_rows = math.ceil(len(interactions) / inter_cols) if interactions else 0
        chart.setMinimumWidth(max(680, 240 * min(3, max(len(main_effects), len(interactions), 2))))
        chart.setMinimumHeight(max(440, 270 * n_panels + max(0, inter_rows - 1) * 180))
        chart.note = _hold_note(holds) or f'Fitted model: {result.get("model_title", "")}'
        return

    if analysis == 'model_contour_plot':
        raw_panels = result.get('panels', [])
        if not raw_panels:
            raise ValueError('Model Contour Plot requires at least one continuous predictor pair.')
        options = result.get('options', {})
        for rp in raw_panels:
            x_name = rp.get('x_name') or rp.get('x_var', {}).get('name', 'X')
            y_name = rp.get('y_name') or rp.get('y_var', {}).get('name', 'Y')
            p_title = rp.get('title') or f"Contour Plot of {resp_name} vs {y_name}, {x_name}"
            chart.panels.append(dict(
                kind='model_contour',
                title=p_title,
                x_name=x_name,
                y_name=y_name,
                x_grid=rp['x_grid'],
                y_grid=rp['y_grid'],
                z_grid=rp['z_grid'],
                z_min=float(rp['z_min']),
                z_max=float(rp['z_max']),
                levels=[float(v) for v in rp.get('levels', [])],
                holds=rp.get('held_predictors', rp.get('holds', [])),
                design_points=rp.get('design_points', []),
                show_area=bool(options.get('show_area', True)),
                show_lines=bool(options.get('show_lines', True)),
                show_design_points=bool(options.get('show_design_points', False)),
                y_label=resp_name,
            ))
        chart.panel_columns = 2 if len(chart.panels) > 1 else 1
        rows = math.ceil(len(chart.panels) / chart.panel_columns)
        chart.setMinimumWidth(780 if chart.panel_columns > 1 else 660)
        chart.setMinimumHeight(max(430, rows * 380))
        chart.note = _hold_note(raw_panels[0].get('held_predictors', [])) or f'Fitted {resp_name}'
        return

    if analysis == 'model_surface_plot':
        raw_panels = result.get('panels', [])
        if not raw_panels:
            raise ValueError('Model Surface Plot requires at least one continuous predictor pair.')
        options = result.get('options', {})
        for rp in raw_panels:
            x_name = rp.get('x_name') or rp.get('x_var', {}).get('name', 'X')
            y_name = rp.get('y_name') or rp.get('y_var', {}).get('name', 'Y')
            p_title = rp.get('title') or f"Surface Plot of {resp_name} vs {y_name}, {x_name}"
            chart.panels.append(dict(
                kind='model_surface',
                title=p_title,
                x_name=x_name,
                y_name=y_name,
                x_grid=rp['x_grid'],
                y_grid=rp['y_grid'],
                z_grid=rp['z_grid'],
                z_min=float(rp['z_min']),
                z_max=float(rp['z_max']),
                holds=rp.get('held_predictors', rp.get('holds', [])),
                surface_style=options.get('surface_style', 'shaded'),
                y_label=resp_name,
            ))
        chart.panel_columns = 2 if len(chart.panels) > 1 else 1
        rows = math.ceil(len(chart.panels) / chart.panel_columns)
        chart.setMinimumWidth(780 if chart.panel_columns > 1 else 660)
        chart.setMinimumHeight(max(440, rows * 390))
        chart.note = _hold_note(raw_panels[0].get('held_predictors', [])) or f'3D Surface ({options.get("surface_style", "shaded")})'
        return


def _draw_main_effects(chart, p, area, panel):
    items = panel['items']
    yb = panel['y_bounds']
    ref_y = panel['reference_y']
    y_label = panel['y_label']

    n = len(items)
    cols = min(3, max(1, n))
    rows = math.ceil(n / cols)

    left_margin = 64.0
    right_margin = 16.0
    top_margin = 28.0
    bottom_margin = 20.0

    grid_w = max(120.0, area.width() - left_margin - right_margin)
    grid_h = max(100.0, area.height() - top_margin - bottom_margin)
    cell_w = grid_w / cols
    cell_h = grid_h / rows

    p.save()
    p.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
    p.translate(area.left() + 14, area.top() + top_margin + grid_h / 2)
    p.rotate(-90)
    chart._text(p, QRectF(-grid_h / 2, -10, grid_h, 20), y_label, SLATE, Qt.AlignmentFlag.AlignCenter)
    p.restore()

    for idx, item in enumerate(items):
        r_i = idx // cols
        c_i = idx % cols
        cell = QRectF(
            area.left() + left_margin + c_i * cell_w + 6.0,
            area.top() + top_margin + r_i * cell_h + 4.0,
            cell_w - 12.0,
            cell_h - 34.0,
        )
        if cell.width() <= 20 or cell.height() <= 20:
            continue

        hdr = QRectF(cell.left(), cell.top(), cell.width(), 22.0)
        p.fillRect(hdr, QColor('#eef3f7'))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(BORDER), 1.0))
        p.drawRect(hdr)
        p.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
        chart._text(p, hdr, str(item['name']), SLATE, Qt.AlignmentFlag.AlignCenter)

        plot = QRectF(cell.left(), hdr.bottom(), cell.width(), cell.height() - 22.0)
        p.fillRect(plot, QColor('#ffffff'))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(BORDER), 1.0))
        p.drawRect(plot)
        chart.remember_rect(f'me_{idx}', plot)

        if c_i == 0:
            p.setFont(QFont('Segoe UI', 8))
            for t_i in range(5):
                frac = t_i / 4.0
                yv = yb[0] + frac * (yb[1] - yb[0])
                py = plot.bottom() - frac * plot.height()
                p.setPen(QPen(QColor('#e5eaee'), 1.0))
                p.drawLine(QPointF(plot.left(), py), QPointF(plot.right(), py))
                chart._text(
                    p,
                    QRectF(area.left() + 20, py - 8, left_margin - 24, 16),
                    _fmt(yv),
                    MUTED,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                )

        inner = plot.adjusted(14.0, 10.0, -14.0, -10.0)
        if inner.width() <= 4 or inner.height() <= 4:
            continue

        y_map = lambda v: inner.bottom() - ((float(v) - yb[0]) / (yb[1] - yb[0])) * inner.height()

        item_ref = float(item.get('reference_mean', ref_y))
        ref_py = y_map(item_ref)
        if plot.top() <= ref_py <= plot.bottom():
            p.setPen(QPen(QColor('#8795a1'), 1.1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(plot.left() + 2, ref_py), QPointF(plot.right() - 2, ref_py))

        xs = item.get('x_values', item.get('x', []))
        ys = item.get('fits', item.get('y', []))
        labels = [_fmt(v) for v in xs]
        if item.get('role') == 'factor' or any(not isinstance(v, (int, float)) for v in xs):
            n_pts = len(xs)
            x_map = lambda i: inner.left() + (i / max(1, n_pts - 1)) * inner.width() if n_pts > 1 else inner.center().x()
            pts = [QPointF(x_map(i), y_map(ys[i])) for i in range(n_pts)]
            tick_indices = list(range(n_pts))
            tick_positions = [x_map(i) for i in tick_indices]
        else:
            x_lo, x_hi = float(min(xs)), float(max(xs))
            if x_hi <= x_lo:
                x_lo -= 0.5
                x_hi += 0.5
            x_map = lambda xv: inner.left() + ((float(xv) - x_lo) / (x_hi - x_lo)) * inner.width()
            pts = [QPointF(x_map(xv), y_map(yv)) for xv, yv in zip(xs, ys)]
            tick_indices = [0, len(xs) // 2, len(xs) - 1] if len(xs) >= 3 else list(range(len(xs)))
            tick_positions = [x_map(xs[i]) for i in tick_indices]

        if len(pts) > 1:
            path = QPainterPath(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
            p.setPen(QPen(QColor(BLUE), 2.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
            chart.remember_path(f'me_{idx}', pts)

        marker_pts = pts if len(pts) <= 8 else [pts[0], pts[len(pts) // 2], pts[-1]]
        p.setPen(QPen(QColor('#ffffff'), 1.0))
        p.setBrush(QColor(BLUE))
        for pt in marker_pts:
            p.drawEllipse(pt, 3.8, 3.8)

        p.setFont(QFont('Segoe UI', 8))
        for ti, px in zip(tick_indices, tick_positions):
            lbl = str(labels[ti])[:10]
            chart._text(
                p,
                QRectF(px - 28, plot.bottom() + 2, 56, 16),
                lbl,
                MUTED,
                Qt.AlignmentFlag.AlignCenter,
            )


def _draw_interaction(chart, p, area, panel):
    items = panel['items']
    yb = panel['y_bounds']
    y_label = panel['y_label']

    n = len(items)
    cols = min(3, max(1, n))
    rows = math.ceil(n / cols)

    left_margin = 62.0
    right_margin = 14.0
    top_margin = 28.0
    bottom_margin = 20.0

    grid_w = max(140.0, area.width() - left_margin - right_margin)
    grid_h = max(100.0, area.height() - top_margin - bottom_margin)
    cell_w = grid_w / cols
    cell_h = grid_h / rows

    p.save()
    p.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
    p.translate(area.left() + 14, area.top() + top_margin + grid_h / 2)
    p.rotate(-90)
    chart._text(p, QRectF(-grid_h / 2, -10, grid_h, 20), y_label, SLATE, Qt.AlignmentFlag.AlignCenter)
    p.restore()

    for idx, inter in enumerate(items):
        r_i = idx // cols
        c_i = idx % cols
        cell = QRectF(
            area.left() + left_margin + c_i * cell_w + 6.0,
            area.top() + top_margin + r_i * cell_h + 4.0,
            cell_w - 12.0,
            cell_h - 24.0,
        )
        if cell.width() <= 40 or cell.height() <= 24:
            continue

        legend_w = min(105.0, max(72.0, cell.width() * 0.27))
        hdr = QRectF(cell.left(), cell.top(), cell.width() - legend_w - 4.0, 20.0)
        p.fillRect(hdr, QColor('#eef3f7'))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(BORDER), 1.0))
        p.drawRect(hdr)
        p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
        pair_title = f"{inter['x_name']} * {inter['trace_name']}"
        chart._text(p, hdr, pair_title, SLATE, Qt.AlignmentFlag.AlignCenter)

        plot = QRectF(hdr.left(), hdr.bottom(), hdr.width(), cell.height() - 20.0)
        p.fillRect(plot, QColor('#ffffff'))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(BORDER), 1.0))
        p.drawRect(plot)
        chart.remember_rect(f'inter_{idx}', plot)

        if c_i == 0:
            p.setFont(QFont('Segoe UI', 8))
            n_ticks = 3 if plot.height() < 105 else 5
            for t_i in range(n_ticks):
                frac = t_i / max(1.0, float(n_ticks - 1))
                yv = yb[0] + frac * (yb[1] - yb[0])
                py = plot.bottom() - frac * plot.height()
                p.setPen(QPen(QColor('#e5eaee'), 1.0))
                p.drawLine(QPointF(plot.left(), py), QPointF(plot.right(), py))
                chart._text(
                    p,
                    QRectF(area.left() + 20, py - 8, left_margin - 24, 16),
                    _fmt(yv),
                    MUTED,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                )

        inner = plot.adjusted(14.0, 8.0, -14.0, -8.0)
        y_map = lambda v: inner.bottom() - ((float(v) - yb[0]) / (yb[1] - yb[0])) * inner.height()

        traces = inter.get('series', inter.get('traces', []))
        if not traces:
            continue
        xs = traces[0].get('x_values', inter.get('x', []))
        labels = [_fmt(v) for v in xs]
        if inter.get('x_role') == 'factor' or any(not isinstance(v, (int, float)) for v in xs):
            n_pts = len(xs)
            x_map = lambda i: inner.left() + (i / max(1, n_pts - 1)) * inner.width() if n_pts > 1 else inner.center().x()
            x_coords = [x_map(i) for i in range(n_pts)]
            tick_indices = list(range(n_pts))
        else:
            x_lo, x_hi = float(min(xs)), float(max(xs))
            if x_hi <= x_lo:
                x_lo -= 0.5
                x_hi += 0.5
            x_map = lambda xv: inner.left() + ((float(xv) - x_lo) / (x_hi - x_lo)) * inner.width()
            x_coords = [x_map(xv) for xv in xs]
            tick_indices = [0, len(xs) // 2, len(xs) - 1] if len(xs) >= 3 else list(range(len(xs)))

        leg_box = QRectF(plot.right() + 4.0, cell.top(), legend_w, cell.height())
        p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
        chart._text(
            p,
            QRectF(leg_box.left() + 2, leg_box.top() + 2, leg_box.width() - 4, 16),
            str(inter['trace_name'])[:16],
            SLATE,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

        step_y = min(16.0, max(12.0, (cell.height() - 18.0) / max(1, len(traces))))
        for t_i, trace in enumerate(traces):
            color = TRACE_COLORS[t_i % len(TRACE_COLORS)]
            pen_style = Qt.PenStyle.SolidLine if t_i % 2 == 0 else Qt.PenStyle.DashLine
            ys = trace.get('fits', trace.get('y', []))
            pts = [QPointF(x_coords[i], y_map(ys[i])) for i in range(len(ys))]
            if len(pts) > 1:
                path = QPainterPath(pts[0])
                for pt in pts[1:]:
                    path.lineTo(pt)
                p.setPen(QPen(QColor(color), 1.9, pen_style))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
                chart.remember_path(f'inter_{idx}_{t_i}', pts)

            marker_pts = pts if len(pts) <= 8 else [pts[0], pts[len(pts) // 2], pts[-1]]
            p.setPen(QPen(QColor('#ffffff'), 1.0))
            p.setBrush(QColor(color))
            for pt in marker_pts:
                p.drawEllipse(pt, 3.4, 3.4)

            ly = leg_box.top() + 18.0 + t_i * step_y
            p.setPen(QPen(QColor(color), 1.8, pen_style))
            p.drawLine(QPointF(leg_box.left() + 4, ly + 7), QPointF(leg_box.left() + 20, ly + 7))
            p.setBrush(QColor(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(leg_box.left() + 12, ly + 7), 2.8, 2.8)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setFont(QFont('Segoe UI', 7.5))
            chart._text(
                p,
                QRectF(leg_box.left() + 24, ly, leg_box.width() - 26, 14),
                str(trace['label'])[:14],
                SLATE,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )

        p.setFont(QFont('Segoe UI', 8))
        for ti in tick_indices:
            px = x_coords[ti]
            chart._text(
                p,
                QRectF(px - 28, plot.bottom() + 2, 56, 16),
                str(labels[ti])[:10],
                MUTED,
                Qt.AlignmentFlag.AlignCenter,
            )



def interpolate_contour_grid(x_grid, y_grid, z_grid, x_val, y_val):
    x_val = max(float(x_grid[0]), min(float(x_grid[-1]), float(x_val)))
    y_val = max(float(y_grid[0]), min(float(y_grid[-1]), float(y_val)))

    c = 0
    for j in range(len(x_grid) - 1):
        if x_grid[j] <= x_val <= x_grid[j + 1]:
            c = j
            break
        elif x_val > x_grid[j + 1]:
            c = j + 1
    c = min(c, len(x_grid) - 2)

    r = 0
    for i in range(len(y_grid) - 1):
        if y_grid[i] <= y_val <= y_grid[i + 1]:
            r = i
            break
        elif y_val > y_grid[i + 1]:
            r = i + 1
    r = min(r, len(y_grid) - 2)

    dx = float(x_grid[c + 1]) - float(x_grid[c])
    dy = float(y_grid[r + 1]) - float(y_grid[r])
    u = 0.0 if abs(dx) < 1e-12 else (x_val - float(x_grid[c])) / dx
    v = 0.0 if abs(dy) < 1e-12 else (y_val - float(y_grid[r])) / dy

    z00 = float(z_grid[r][c])
    z01 = float(z_grid[r][c + 1])
    z10 = float(z_grid[r + 1][c])
    z11 = float(z_grid[r + 1][c + 1])

    return (1.0 - u) * (1.0 - v) * z00 + u * (1.0 - v) * z01 + (1.0 - u) * v * z10 + u * v * z11


def _draw_cad_card(chart, p, card_rect, title, title_color, fit_val, x_name, x_val, y_name, y_val, holds=None):
    p.save()
    p.setPen(QPen(QColor('#37474f'), 1.2))
    p.setBrush(QColor(255, 255, 255, 248))
    p.drawRoundedRect(card_rect, 6.0, 6.0)

    hdr_rect = QRectF(card_rect.left(), card_rect.top(), card_rect.width(), 24.0)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(title_color))
    p.drawRoundedRect(hdr_rect, 6.0, 6.0)
    p.fillRect(QRectF(hdr_rect.left(), hdr_rect.bottom() - 4.0, hdr_rect.width(), 4.0), QColor(title_color))

    p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
    chart._text(p, hdr_rect.adjusted(8, 0, -8, 0), title, '#ffffff', Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    p.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
    chart._text(p, QRectF(card_rect.left() + 10, card_rect.top() + 27, card_rect.width() - 20, 18),
                f"Fit (Y): {_fmt(fit_val)}", SLATE, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    p.setFont(QFont('Segoe UI', 8))
    chart._text(p, QRectF(card_rect.left() + 10, card_rect.top() + 46, card_rect.width() - 20, 16),
                f"{x_name} = {_fmt(x_val)}", MUTED, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    chart._text(p, QRectF(card_rect.left() + 10, card_rect.top() + 62, card_rect.width() - 20, 16),
                f"{y_name} = {_fmt(y_val)}", MUTED, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    if holds:
        cur_y = card_rect.top() + 79.0
        for h in holds[:3]:
            chart._text(p, QRectF(card_rect.left() + 10, cur_y, card_rect.width() - 20, 15),
                        f"{h['name']} = {_fmt(h.get('value', h.get('display')))}", MUTED, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            cur_y += 15.0
    p.restore()

def _draw_contour(chart, p, area, panel):
    x_grid = panel['x_grid']
    y_grid = panel['y_grid']
    z_grid = panel['z_grid']
    z_min = panel['z_min']
    z_max = panel['z_max']
    levels = panel['levels']
    x_name = panel['x_name']
    y_name = panel['y_name']
    holds = panel.get('holds', [])

    # Find Peak (global max) and Trough (global min) on the grid
    max_r, max_c = 0, 0
    max_val = -float('inf')
    min_r, min_c = 0, 0
    min_val = float('inf')
    for r in range(len(y_grid)):
        for c in range(len(x_grid)):
            zv = float(z_grid[r][c])
            if zv > max_val:
                max_val = zv
                max_r, max_c = r, c
            if zv < min_val:
                min_val = zv
                min_r, min_c = r, c

    max_pt = (float(x_grid[max_c]), float(y_grid[max_r]), max_val)
    min_pt = (float(x_grid[min_c]), float(y_grid[min_r]), min_val)
    panel['max_pt'] = max_pt
    panel['min_pt'] = min_pt

    legend_w = min(165.0, max(125.0, area.width() * 0.25))
    plot = QRectF(
        area.left() + 62.0,
        area.top() + 28.0,
        max(120.0, area.width() - 78.0 - legend_w),
        max(120.0, area.height() - 74.0),
    )
    chart.remember_axes(plot)
    panel['plot_rect'] = plot

    x_lo, x_hi = float(x_grid[0]), float(x_grid[-1])
    y_lo, y_hi = float(y_grid[0]), float(y_grid[-1])
    panel['x_lo'] = x_lo
    panel['x_hi'] = x_hi
    panel['y_lo'] = y_lo
    panel['y_hi'] = y_hi

    x_map = lambda xv: plot.left() + ((float(xv) - x_lo) / max(1e-12, x_hi - x_lo)) * plot.width()
    y_map = lambda yv: plot.bottom() - ((float(yv) - y_lo) / max(1e-12, y_hi - y_lo)) * plot.height()
    pt_map = lambda xv, yv: QPointF(x_map(xv), y_map(yv))

    p.fillRect(plot, QColor('#ffffff'))

    if panel.get('show_area', True):
        for r in range(len(y_grid) - 1):
            for c in range(len(x_grid) - 1):
                cell_val = 0.25 * (
                    z_grid[r][c] + z_grid[r][c + 1] + z_grid[r + 1][c] + z_grid[r + 1][c + 1]
                )
                cell_rect = QRectF(pt_map(x_grid[c], y_grid[r]), pt_map(x_grid[c + 1], y_grid[r + 1])).normalized()
                p.fillRect(cell_rect, _band_color(cell_val, levels, z_min, z_max))

    if panel.get('show_lines', True) and z_max > z_min and levels:
        p.save()
        p.setClipRect(plot.adjusted(1, 1, -1, -1))
        for lv in levels:
            p.setPen(QPen(QColor('#283c4c'), 1.15))
            labeled = False
            for r in range(len(y_grid) - 1):
                for c in range(len(x_grid) - 1):
                    corners = [
                        (x_grid[c], y_grid[r], z_grid[r][c]),
                        (x_grid[c + 1], y_grid[r], z_grid[r][c + 1]),
                        (x_grid[c + 1], y_grid[r + 1], z_grid[r + 1][c + 1]),
                        (x_grid[c], y_grid[r + 1], z_grid[r + 1][c]),
                    ]
                    hits = []
                    for a, b in zip(corners, corners[1:] + corners[:1]):
                        if (a[2] <= lv < b[2]) or (b[2] <= lv < a[2]):
                            t = (lv - a[2]) / (b[2] - a[2])
                            hits.append(pt_map(a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
                    for j in range(0, len(hits) - 1, 2):
                        p.drawLine(hits[j], hits[j + 1])
                        if not labeled and plot.adjusted(26, 16, -26, -16).contains(hits[j]):
                            lbl_rect = QRectF(hits[j].x() - 22, hits[j].y() - 9, 44, 18)
                            p.fillRect(lbl_rect, QColor(255, 255, 255, 195))
                            p.setFont(QFont('Segoe UI', 7, QFont.Weight.DemiBold))
                            chart._text(p, lbl_rect, _fmt(lv), SLATE, Qt.AlignmentFlag.AlignCenter)
                            labeled = True
        p.restore()

    if panel.get('show_design_points', False):
        p.save()
        p.setClipRect(plot)
        p.setPen(QPen(QColor('#ffffff'), 1.2))
        p.setBrush(QColor(RED))
        for dx, dy in panel.get('design_points', []):
            p.drawEllipse(pt_map(dx, dy), 3.6, 3.6)
        p.restore()

    # Peak & Trough 2D Reticles & Badges
    p.save()
    p.setClipRect(plot)
    max_px = pt_map(max_pt[0], max_pt[1])
    min_px = pt_map(min_pt[0], min_pt[1])

    # 1. Peak Reticle (Coral Red)
    p.setPen(QPen(QColor('#e53935'), 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(max_px, 8.0, 8.0)
    p.setPen(QPen(QColor('#ffffff'), 1.0))
    p.drawEllipse(max_px, 4.5, 4.5)
    p.setPen(QPen(QColor('#e53935'), 1.5))
    p.drawLine(QPointF(max_px.x() - 11.0, max_px.y()), QPointF(max_px.x() + 11.0, max_px.y()))
    p.drawLine(QPointF(max_px.x(), max_px.y() - 11.0), QPointF(max_px.x(), max_px.y() + 11.0))
    p.fillRect(QRectF(max_px.x() - 1.5, max_px.y() - 1.5, 3.0, 3.0), QColor('#e53935'))

    # Peak Badge Pill
    badge_max_rect = QRectF(max_px.x() - 36.0, max_px.y() - 25.0, 72.0, 18.0)
    badge_max_rect.moveLeft(max(plot.left() + 4.0, min(plot.right() - 76.0, badge_max_rect.left())))
    badge_max_rect.moveTop(max(plot.top() + 4.0, min(plot.bottom() - 22.0, badge_max_rect.top())))
    p.setPen(QPen(QColor('#ffffff'), 1.0))
    p.setBrush(QColor('#c62828'))
    p.drawRoundedRect(badge_max_rect, 9.0, 9.0)
    p.setFont(QFont('Segoe UI', 7, QFont.Weight.Bold))
    chart._text(p, badge_max_rect, f"▲ MAX: {_fmt(max_val)}", '#ffffff', Qt.AlignmentFlag.AlignCenter)

    # 2. Trough Reticle (Cyan / Blue)
    p.setPen(QPen(QColor('#0288d1'), 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(min_px, 8.0, 8.0)
    p.setPen(QPen(QColor('#ffffff'), 1.0))
    p.drawEllipse(min_px, 4.5, 4.5)
    p.setPen(QPen(QColor('#0288d1'), 1.5))
    p.drawLine(QPointF(min_px.x() - 11.0, min_px.y()), QPointF(min_px.x() + 11.0, min_px.y()))
    p.drawLine(QPointF(min_px.x(), min_px.y() - 11.0), QPointF(min_px.x(), min_px.y() + 11.0))
    p.fillRect(QRectF(min_px.x() - 1.5, min_px.y() - 1.5, 3.0, 3.0), QColor('#0288d1'))

    # Trough Badge Pill
    badge_min_rect = QRectF(min_px.x() - 36.0, min_px.y() - 25.0, 72.0, 18.0)
    badge_min_rect.moveLeft(max(plot.left() + 4.0, min(plot.right() - 76.0, badge_min_rect.left())))
    badge_min_rect.moveTop(max(plot.top() + 4.0, min(plot.bottom() - 22.0, badge_min_rect.top())))
    p.setPen(QPen(QColor('#ffffff'), 1.0))
    p.setBrush(QColor('#0277bd'))
    p.drawRoundedRect(badge_min_rect, 9.0, 9.0)
    p.setFont(QFont('Segoe UI', 7, QFont.Weight.Bold))
    chart._text(p, badge_min_rect, f"▼ MIN: {_fmt(min_val)}", '#ffffff', Qt.AlignmentFlag.AlignCenter)
    p.restore()

    # Register hit regions and hover tooltips for Peak & Min
    path_max = QPainterPath()
    path_max.addRoundedRect(badge_max_rect, 9.0, 9.0)
    path_max.addEllipse(max_px, 12.0, 12.0)
    chart.hit_regions.append(('cad_peak_2d', path_max))
    chart.remember_point_hover(
        badge_max_rect,
        f"Peak Maximum: {_fmt(max_val)}\n{x_name}: {_fmt(max_pt[0])}\n{y_name}: {_fmt(max_pt[1])}"
    )

    path_min = QPainterPath()
    path_min.addRoundedRect(badge_min_rect, 9.0, 9.0)
    path_min.addEllipse(min_px, 12.0, 12.0)
    chart.hit_regions.append(('cad_min_2d', path_min))
    chart.remember_point_hover(
        badge_min_rect,
        f"Trough Minimum: {_fmt(min_val)}\n{x_name}: {_fmt(min_pt[0])}\n{y_name}: {_fmt(min_pt[1])}"
    )

    # Active CAD Callout Card for 2D Contour
    active_card = getattr(chart, 'active_cad_card', None)
    if active_card and active_card.get('mode') in ('contour', 'peak_2d', 'min_2d', 'probe_2d'):
        mode = active_card.get('mode')
        card_w = min(210.0, plot.width() * 0.42)
        card_h = 98.0 if holds else 84.0
        card_rect = QRectF(plot.right() - card_w - 8.0, plot.top() + 6.0, card_w, card_h)

        if mode == 'peak_2d':
            _draw_cad_card(chart, p, card_rect, "▲ Global Maximum (Peak)", '#c62828',
                           max_val, x_name, max_pt[0], y_name, max_pt[1], holds)
        elif mode == 'min_2d':
            _draw_cad_card(chart, p, card_rect, "▼ Global Minimum (Trough)", '#0277bd',
                           min_val, x_name, min_pt[0], y_name, min_pt[1], holds)
        elif mode == 'probe_2d':
            pr_x = active_card['x']
            pr_y = active_card['y']
            pr_fit = active_card['fit']
            # Draw crosshair target at probed location
            pr_pt = pt_map(pr_x, pr_y)
            if plot.contains(pr_pt):
                p.save()
                p.setPen(QPen(QColor('#ffb300'), 2.0))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(pr_pt, 7.0, 7.0)
                p.setPen(QPen(QColor('#263238'), 1.2))
                p.drawLine(QPointF(pr_pt.x() - 10, pr_pt.y()), QPointF(pr_pt.x() + 10, pr_pt.y()))
                p.drawLine(QPointF(pr_pt.x(), pr_pt.y() - 10), QPointF(pr_pt.x(), pr_pt.y() + 10))
                p.restore()
            _draw_cad_card(chart, p, card_rect, "✦ Probed Contour Point", '#37474f',
                           pr_fit, x_name, pr_x, y_name, pr_y, holds)

    p.setPen(QPen(QColor(SLATE), 1.1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(plot)

    p.setFont(QFont('Segoe UI', 8))
    for i in range(5):
        frac = i / 4.0
        xv = x_lo + frac * (x_hi - x_lo)
        px = plot.left() + frac * plot.width()
        p.setPen(QPen(QColor(SLATE), 1.0))
        p.drawLine(QPointF(px, plot.bottom()), QPointF(px, plot.bottom() + 4))
        chart._text(p, QRectF(px - 32, plot.bottom() + 5, 64, 16), _fmt(xv), MUTED, Qt.AlignmentFlag.AlignCenter)

        yv = y_lo + frac * (y_hi - y_lo)
        py = plot.bottom() - frac * plot.height()
        p.setPen(QPen(QColor(SLATE), 1.0))
        p.drawLine(QPointF(plot.left() - 4, py), QPointF(plot.left(), py))
        chart._text(
            p,
            QRectF(area.left() + 16, py - 8, 42, 16),
            _fmt(yv),
            MUTED,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

    p.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
    chart._text(
        p,
        QRectF(plot.left(), plot.bottom() + 22, plot.width(), 20),
        str(x_name),
        SLATE,
        Qt.AlignmentFlag.AlignCenter,
    )
    p.save()
    p.translate(area.left() + 12, plot.center().y())
    p.rotate(-90)
    chart._text(p, QRectF(-plot.height() / 2, -9, plot.height(), 18), str(y_name), SLATE, Qt.AlignmentFlag.AlignCenter)
    p.restore()

    leg = QRectF(plot.right() + 10.0, plot.top(), legend_w - 6.0, plot.height())
    p.fillRect(leg, QColor('#f8fafb'))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(BORDER), 1.0))
    p.drawRect(leg)

    p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
    chart._text(
        p,
        QRectF(leg.left() + 8, leg.top() + 6, leg.width() - 16, 18),
        str(panel.get('y_label', 'Response'))[:20],
        SLATE,
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    )

    bands = []
    if levels:
        bands.append((f'< {_fmt(levels[0])}', levels[0] - 1e-6))
        for i in range(len(levels) - 1):
            bands.append((f'{_fmt(levels[i])} – {_fmt(levels[i + 1])}', 0.5 * (levels[i] + levels[i + 1])))
        bands.append((f'> {_fmt(levels[-1])}', levels[-1] + 1e-6))
    else:
        bands.append((_fmt(z_min), z_min))

    p.setFont(QFont('Segoe UI', 8))
    cur_y = leg.top() + 26.0
    for label, mid_val in bands[:9]:
        swatch = QRectF(leg.left() + 8, cur_y + 2, 14, 12)
        p.fillRect(swatch, _band_color(mid_val, levels, z_min, z_max))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(BORDER), 0.8))
        p.drawRect(swatch)
        chart._text(
            p,
            QRectF(swatch.right() + 6, cur_y, leg.width() - 32, 16),
            label,
            SLATE,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        cur_y += 17.0

    if holds and cur_y + 28 < leg.bottom():
        cur_y += 6.0
        p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
        chart._text(
            p,
            QRectF(leg.left() + 8, cur_y, leg.width() - 16, 16),
            'Hold Values',
            SLATE,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        cur_y += 16.0
        p.setFont(QFont('Segoe UI', 8))
        for h in holds[:5]:
            if cur_y + 14 > leg.bottom():
                break
            chart._text(
                p,
                QRectF(leg.left() + 8, cur_y, leg.width() - 16, 15),
                f"{h['name']}: {_fmt(h.get('value', h.get('display')))}",
                MUTED,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
            cur_y += 15.0

def handle_viewcube_action(chart, target):
    if not target or not target.startswith('viewcube_'):
        return False
    action = target.replace('viewcube_', '')
    if action == 'body':
        return False

    face_map = {
        'top': (0.0, 89.0),
        'bottom': (0.0, -89.0),
        'front': (0.0, 0.0),
        'back': (180.0, 0.0),
        'right': (90.0, 0.0),
        'left': (-90.0, 0.0),
        'iso': (-35.0, 25.0),
    }
    if action in face_map:
        chart.set_cad_orientation(*face_map[action])
        return True

    corner_map = {
        'corner_tfr': (45.0, 35.3),
        'corner_tfl': (-45.0, 35.3),
        'corner_tbr': (135.0, 35.3),
        'corner_tbl': (-135.0, 35.3),
        'corner_bfr': (45.0, -35.3),
        'corner_bfl': (-45.0, -35.3),
        'corner_bbr': (135.0, -35.3),
        'corner_bbl': (-135.0, -35.3),
    }
    if action in corner_map:
        chart.set_cad_orientation(*corner_map[action])
        return True

    edge_map = {
        'edge_tf': (0.0, 45.0),
        'edge_tb': (180.0, 45.0),
        'edge_tr': (90.0, 45.0),
        'edge_tl': (-90.0, 45.0),
        'edge_bf': (0.0, -45.0),
        'edge_bb': (180.0, -45.0),
        'edge_br': (90.0, -45.0),
        'edge_bl': (-90.0, -45.0),
        'edge_fr': (45.0, 0.0),
        'edge_fl': (-45.0, 0.0),
        'edge_br_mid': (135.0, 0.0),
        'edge_bl_mid': (-135.0, 0.0),
    }
    if action in edge_map:
        chart.set_cad_orientation(*edge_map[action])
        return True
    return False


def _draw_viewcube(chart, p, cube_rect):
    state = getattr(chart, 'surface_camera', getattr(chart, 'view_state', DEFAULT_VIEW))
    box_size = 68.0
    cube_box = QRectF(cube_rect.right() - box_size - 10.0, cube_rect.top() + 8.0, box_size, box_size)
    cx = cube_box.center().x()
    cy = cube_box.center().y()
    s = 17.5

    p.save()
    p.setRenderHint(p.RenderHint.Antialiasing)

    # 1. Elegant translucent card backdrop & circular gimbal/compass ring
    p.setPen(QPen(QColor(203, 213, 225, 160), 0.9))
    p.setBrush(QColor(255, 255, 255, 180))
    p.drawRoundedRect(cube_box, 8.0, 8.0)

    ring_r = box_size * 0.44
    p.setPen(QPen(QColor(148, 163, 184, 110), 0.8, Qt.PenStyle.DashLine))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(cx, cy), ring_r, ring_r)

    path_box = QPainterPath()
    path_box.addRoundedRect(cube_box, 8.0, 8.0)
    chart.hit_regions.append(('viewcube_body', path_box))
    if hasattr(chart, 'remember_hover'):
        chart.remember_hover(path_box, {'text': 'ViewCube: Click and drag to rotate view'})
    elif hasattr(chart, 'remember_point_hover'):
        chart.remember_point_hover(cube_box, 'ViewCube: Click and drag to rotate view')

    # 2. 3D Faces
    cube_faces = [
        ('TOP', (0, 0, 1), [(-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)], QColor('#f8fafc'), QColor('#1e293b')),
        ('BOTTOM', (0, 0, -1), [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1)], QColor('#94a3b8'), QColor('#ffffff')),
        ('FRONT', (0, 1, 0), [(-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1)], QColor('#e2e8f0'), QColor('#0f172a')),
        ('BACK', (0, -1, 0), [(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)], QColor('#64748b'), QColor('#ffffff')),
        ('RIGHT', (1, 0, 0), [(1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1)], QColor('#cbd5e1'), QColor('#1e293b')),
        ('LEFT', (-1, 0, 0), [(-1, -1, -1), (-1, 1, -1), (-1, 1, 1), (-1, -1, 1)], QColor('#e2e8f0'), QColor('#0f172a')),
    ]

    visible_faces = []
    for name, norm, verts, fill_col, text_col in cube_faces:
        _, _, norm_depth = camera_point(norm, state)
        if norm_depth > 0.02:
            proj_pts = [camera_point(v, state) for v in verts]
            avg_depth = sum(pt[2] for pt in proj_pts) * 0.25
            screen_poly = QPolygonF([QPointF(cx + pt[0] * s, cy - pt[1] * s) for pt in proj_pts])
            visible_faces.append((avg_depth, name, screen_poly, fill_col, text_col))

    visible_faces.sort(key=lambda item: item[0])

    p.setFont(QFont('Segoe UI', 6, QFont.Weight.Bold))
    for _, name, poly, fill_col, text_col in visible_faces:
        path_face = QPainterPath()
        path_face.addPolygon(poly)

        p.setBrush(fill_col)
        p.setPen(QPen(QColor(100, 116, 139, 210), 1.0))
        p.drawPolygon(poly)

        chart.hit_regions.append(('viewcube_' + name.lower(), path_face))
        tip = f'ViewCube: Snap to {name} face (or drag to rotate)'
        if hasattr(chart, 'remember_hover'):
            chart.remember_hover(path_face, {'text': tip})
        elif hasattr(chart, 'remember_point_hover'):
            chart.remember_point_hover(poly.boundingRect(), tip)

        br = poly.boundingRect()
        if br.width() >= 18.0 and br.height() >= 10.0:
            p.save()
            p.setClipPath(path_face)
            p.setPen(text_col)
            p.drawText(br, Qt.AlignmentFlag.AlignCenter, name)
            p.restore()

    # 3. 3D Edges (midpoints)
    cube_edges = [
        ('tf', 'Top-Front', (0, 1, 1)),
        ('tb', 'Top-Back', (0, -1, 1)),
        ('tr', 'Top-Right', (1, 0, 1)),
        ('tl', 'Top-Left', (-1, 0, 1)),
        ('bf', 'Bottom-Front', (0, 1, -1)),
        ('bb', 'Bottom-Back', (0, -1, -1)),
        ('br', 'Bottom-Right', (1, 0, -1)),
        ('bl', 'Bottom-Left', (-1, 0, -1)),
        ('fr', 'Front-Right', (1, 1, 0)),
        ('fl', 'Front-Left', (-1, 1, 0)),
        ('br_mid', 'Back-Right', (1, -1, 0)),
        ('bl_mid', 'Back-Left', (-1, -1, 0)),
    ]
    for code, label, pt in cube_edges:
        proj = camera_point(pt, state)
        if proj[2] > 0.08:
            sx = cx + proj[0] * s
            sy = cy - proj[1] * s
            path_edge = QPainterPath()
            path_edge.addEllipse(QPointF(sx, sy), 5.0, 5.0)
            chart.hit_regions.append(('viewcube_edge_' + code, path_edge))
            tip = f'ViewCube: Snap to {label} edge'
            if hasattr(chart, 'remember_hover'):
                chart.remember_hover(path_edge, {'text': tip})
            elif hasattr(chart, 'remember_point_hover'):
                chart.remember_point_hover(QRectF(sx - 5.0, sy - 5.0, 10.0, 10.0), tip)

    # 4. 3D Corners
    cube_corners = [
        ('tfr', 'Top-Front-Right', (1, 1, 1)),
        ('tfl', 'Top-Front-Left', (-1, 1, 1)),
        ('tbr', 'Top-Back-Right', (1, -1, 1)),
        ('tbl', 'Top-Back-Left', (-1, -1, 1)),
        ('bfr', 'Bottom-Front-Right', (1, 1, -1)),
        ('bfl', 'Bottom-Front-Left', (-1, 1, -1)),
        ('bbr', 'Bottom-Back-Right', (1, -1, -1)),
        ('bbl', 'Bottom-Back-Left', (-1, -1, -1)),
    ]
    for code, label, pt in cube_corners:
        proj = camera_point(pt, state)
        if proj[2] > -0.05:
            sx = cx + proj[0] * s
            sy = cy - proj[1] * s
            p.setPen(QPen(QColor('#ffffff'), 1.0))
            p.setBrush(QColor('#475569'))
            p.drawEllipse(QPointF(sx, sy), 3.2, 3.2)

            path_corner = QPainterPath()
            path_corner.addEllipse(QPointF(sx, sy), 7.0, 7.0)
            chart.hit_regions.append(('viewcube_corner_' + code, path_corner))
            tip = f'ViewCube: Snap to {label} corner'
            if hasattr(chart, 'remember_hover'):
                chart.remember_hover(path_corner, {'text': tip})
            elif hasattr(chart, 'remember_point_hover'):
                chart.remember_point_hover(QRectF(sx - 7.0, sy - 7.0, 14.0, 14.0), tip)

    # 5. Sleek ISO Home button
    iso_w = 20.0
    iso_h = 13.0
    iso_rect = QRectF(cube_box.right() - iso_w - 3.0, cube_box.bottom() - iso_h - 3.0, iso_w, iso_h)
    p.setPen(QPen(QColor('#cbd5e1'), 0.7))
    p.setBrush(QColor(255, 255, 255, 220))
    p.drawRoundedRect(iso_rect, 3.0, 3.0)
    p.setFont(QFont('Segoe UI', 5, QFont.Weight.Bold))
    p.setPen(QColor('#475569'))
    p.drawText(iso_rect, Qt.AlignmentFlag.AlignCenter, 'ISO')

    path_iso = QPainterPath()
    path_iso.addRoundedRect(iso_rect, 3.0, 3.0)
    chart.hit_regions.append(('viewcube_iso', path_iso))
    tip_iso = 'ViewCube: Reset to Isometric View'
    if hasattr(chart, 'remember_hover'):
        chart.remember_hover(path_iso, {'text': tip_iso})
    elif hasattr(chart, 'remember_point_hover'):
        chart.remember_point_hover(iso_rect, tip_iso)

    p.restore()



def _draw_cad_hint_pill(chart, p, cube_rect):
    pass


def _draw_surface(chart, p, area, panel):
    x_grid = panel['x_grid']
    y_grid = panel['y_grid']
    z_grid = panel['z_grid']
    z_min = panel['z_min']
    z_max = panel['z_max']
    x_name = panel['x_name']
    y_name = panel['y_name']
    holds = panel.get('holds', [])
    surface_style = panel.get('surface_style', 'shaded')

    # Find Peak (global max) and Trough (global min)
    max_r, max_c = 0, 0
    max_val = -float('inf')
    min_r, min_c = 0, 0
    min_val = float('inf')
    for r in range(len(y_grid)):
        for c in range(len(x_grid)):
            zv = float(z_grid[r][c])
            if zv > max_val:
                max_val = zv
                max_r, max_c = r, c
            if zv < min_val:
                min_val = zv
                min_r, min_c = r, c

    max_pt = (float(x_grid[max_c]), float(y_grid[max_r]), max_val)
    min_pt = (float(x_grid[min_c]), float(y_grid[min_r]), min_val)
    panel['max_pt'] = max_pt
    panel['min_pt'] = min_pt

    legend_w = min(160.0, max(120.0, area.width() * 0.24))
    cube_rect = QRectF(
        area.left() + 18.0,
        area.top() + 24.0,
        max(140.0, area.width() - 34.0 - legend_w),
        max(140.0, area.height() - 42.0),
    )
    chart.remember_axes(cube_rect)
    panel['cube_rect'] = cube_rect

    x_bounds = _pad_bounds(x_grid)
    y_bounds = _pad_bounds(y_grid)
    z_bounds = _pad_bounds([z_min, z_max])
    ranges = [x_bounds, y_bounds, z_bounds]
    panel['ranges'] = ranges
    state = getattr(chart, 'view_state', DEFAULT_VIEW)
    viewport = (cube_rect.left(), cube_rect.top(), cube_rect.width(), cube_rect.height())
    panel['viewport'] = viewport

    def projected(pt):
        return project_point(pt, ranges, state, viewport)

    def proj2d(pt):
        px, py, _ = projected(pt)
        return QPointF(px, py)

    is_dragging = getattr(chart, '_is_dragging', False)
    step = 2 if is_dragging else 1

    # Pre-project vertices once
    grid_proj = {}
    grid_qpt = {}
    surface_vertices = []
    for r in range(len(y_grid)):
        grid_proj[r] = {}
        grid_qpt[r] = {}
        for c in range(len(x_grid)):
            pt = (float(x_grid[c]), float(y_grid[r]), float(z_grid[r][c]))
            px, py, depth = projected(pt)
            grid_proj[r][c] = (px, py, depth)
            qpos = QPointF(px, py)
            grid_qpt[r][c] = qpos
            if not is_dragging:
                surface_vertices.append({
                    'pt': pt,
                    'pos': qpos,
                    'depth': depth,
                    'r': r,
                    'c': c,
                })
    if not is_dragging:
        panel['surface_vertices'] = surface_vertices

    lows = [r[0] for r in ranges]
    highs = [r[1] for r in ranges]
    corners = [[highs[i] if bits & (1 << i) else lows[i] for i in range(3)] for bits in range(8)]

    # Draw bounding cube wireframe
    p.setPen(QPen(QColor('#dce3e9'), 1.0))
    for bits, corner in enumerate(corners):
        for axis in range(3):
            if not bits & (1 << axis):
                p.drawLine(proj2d(corner), proj2d(corners[bits | (1 << axis)]))

    p.save()

    # Surface faces sorted by camera depth
    faces = []
    r_indices = list(range(0, len(y_grid), step))
    if r_indices[-1] != len(y_grid) - 1:
        r_indices.append(len(y_grid) - 1)
    c_indices = list(range(0, len(x_grid), step))
    if c_indices[-1] != len(x_grid) - 1:
        c_indices.append(len(x_grid) - 1)

    for i in range(len(r_indices) - 1):
        r0 = r_indices[i]; r1 = r_indices[i + 1]
        for j in range(len(c_indices) - 1):
            c0 = c_indices[j]; c1 = c_indices[j + 1]
            p0 = grid_proj[r0][c0]
            p1 = grid_proj[r0][c1]
            p2 = grid_proj[r1][c1]
            p3 = grid_proj[r1][c0]
            cam_depth = (p0[2] + p1[2] + p2[2] + p3[2]) * 0.25
            mean_z = (z_grid[r0][c0] + z_grid[r0][c1] + z_grid[r1][c1] + z_grid[r1][c0]) * 0.25
            faces.append((cam_depth, mean_z, [grid_qpt[r0][c0], grid_qpt[r0][c1], grid_qpt[r1][c1], grid_qpt[r1][c0]]))

    for _, mean_z, qpts in sorted(faces, key=lambda item: item[0]):
        poly = QPolygonF(qpts)
        col = _surface_color(mean_z, z_min, z_max)
        if surface_style == 'wireframe':
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(col.darker(115), 1.15))
        elif is_dragging:
            p.setBrush(QColor(col.red(), col.green(), col.blue(), 190))
            p.setPen(QPen(QColor('#4d6473'), 0.5))
        else:
            p.setBrush(col)
            p.setPen(QPen(QColor('#4d6473'), 0.65))
        p.drawPolygon(poly)

    if not is_dragging:
        # Subtle surface markers at Peak Maximum and Trough Minimum
        pos_max = proj2d(max_pt)
        pos_min = proj2d(min_pt)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(225, 29, 72, 50))
        p.drawEllipse(pos_max, 7.0, 7.0)
        p.setBrush(QColor('#e11d48'))
        p.setPen(QPen(QColor('#ffffff'), 1.2))
        p.drawEllipse(pos_max, 3.5, 3.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#ffffff'))
        p.drawEllipse(pos_max, 1.2, 1.2)

        path_max = QPainterPath()
        path_max.addEllipse(pos_max, 9.0, 9.0)
        chart.hit_regions.append(('cad_peak_3d', path_max))
        chart.remember_point_hover(
            QRectF(pos_max.x() - 10, pos_max.y() - 10, 20, 20),
            f"▲ Peak Maximum: {_fmt(max_val)}\n{x_name}: {_fmt(max_pt[0])}\n{y_name}: {_fmt(max_pt[1])}"
        )

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(2, 132, 199, 50))
        p.drawEllipse(pos_min, 7.0, 7.0)
        p.setBrush(QColor('#0284c7'))
        p.setPen(QPen(QColor('#ffffff'), 1.2))
        p.drawEllipse(pos_min, 3.5, 3.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#ffffff'))
        p.drawEllipse(pos_min, 1.2, 1.2)

        path_min = QPainterPath()
        path_min.addEllipse(pos_min, 9.0, 9.0)
        chart.hit_regions.append(('cad_min_3d', path_min))
        chart.remember_point_hover(
            QRectF(pos_min.x() - 10, pos_min.y() - 10, 20, 20),
            f"▼ Trough Minimum: {_fmt(min_val)}\n{x_name}: {_fmt(min_pt[0])}\n{y_name}: {_fmt(min_pt[1])}"
        )

    # Active CAD Inspection Callout Card for 3D Surface (drawn ONLY when user clicks a point/peak)
    active_card = getattr(chart, 'active_cad_card', None)
    if not is_dragging and active_card and active_card.get('mode') in ('surface', 'peak_3d', 'min_3d', 'probe_3d'):
        mode = active_card.get('mode')
        card_w = min(200.0, cube_rect.width() * 0.42)
        card_h = 92.0 if holds else 76.0
        card_rect = QRectF(cube_rect.left() + 8.0, cube_rect.top() + 6.0, card_w, card_h)

        if mode == 'peak_3d':
            _draw_cad_card(chart, p, card_rect, "▲ Peak Maximum", '#e11d48',
                           max_val, x_name, max_pt[0], y_name, max_pt[1], holds)
        elif mode == 'min_3d':
            _draw_cad_card(chart, p, card_rect, "▼ Trough Minimum", '#0284c7',
                           min_val, x_name, min_pt[0], y_name, min_pt[1], holds)
        elif mode == 'probe_3d':
            pr_x = active_card['x']
            pr_y = active_card['y']
            pr_fit = active_card['fit']
            pr_pos = proj2d((pr_x, pr_y, pr_fit))
            p.save()
            p.setPen(QPen(QColor('#38bdf8'), 1.8))
            p.setBrush(QColor(56, 189, 248, 70))
            p.drawEllipse(pr_pos, 6.0, 6.0)
            p.restore()
            _draw_cad_card(chart, p, card_rect, "✦ Surface Point", '#1e293b',
                           pr_fit, x_name, pr_x, y_name, pr_y, holds)

    # Draw ViewCube in top-right of 3D viewport
    _draw_viewcube(chart, p, cube_rect)

    # Draw 3D Axes
    origin = proj2d(lows)
    axis_names = [str(x_name), str(y_name), str(panel.get('y_label', 'Fit'))]
    p.setFont(QFont('Segoe UI', 8, QFont.Weight.DemiBold))
    for i, label in enumerate(axis_names):
        vals = lows[:]
        vals[i] = highs[i]
        end = proj2d(vals)
        p.setPen(QPen(QColor('#536573'), 1.3))
        p.drawLine(origin, end)
        delta = end - origin
        length = math.hypot(delta.x(), delta.y())
        ux, uy = (delta.x() / length, delta.y() / length) if length > 1 else (0.0, -1.0)
        lbl_center = end + QPointF(ux * 22, uy * 18)
        lbl_rect = QRectF(lbl_center.x() - 60, lbl_center.y() - 10, 120, 20)
        p.fillRect(lbl_rect, QColor(255, 255, 255, 215))
        chart._text(p, lbl_rect, label[:18], SLATE, Qt.AlignmentFlag.AlignCenter)

    # Legend & Info panel
    leg = QRectF(cube_rect.right() + 8.0, cube_rect.top() + 6.0, legend_w - 8.0, cube_rect.height() - 12.0)
    p.fillRect(leg, QColor('#f8fafb'))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(BORDER), 1.0))
    p.drawRect(leg)

    p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
    chart._text(
        p,
        QRectF(leg.left() + 8, leg.top() + 8, leg.width() - 16, 18),
        'Surface Range',
        SLATE,
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    )
    p.setFont(QFont('Segoe UI', 8))
    chart._text(
        p,
        QRectF(leg.left() + 8, leg.top() + 28, leg.width() - 16, 16),
        f'Min: {_fmt(z_min)}',
        MUTED,
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    )
    chart._text(
        p,
        QRectF(leg.left() + 8, leg.top() + 45, leg.width() - 16, 16),
        f'Max: {_fmt(z_max)}',
        MUTED,
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    )
    chart._text(
        p,
        QRectF(leg.left() + 8, leg.top() + 62, leg.width() - 16, 16),
        f'Style: {surface_style.title()}',
        MUTED,
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    )

    if holds:
        cur_y = leg.top() + 86.0
        p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
        chart._text(
            p,
            QRectF(leg.left() + 8, cur_y, leg.width() - 16, 16),
            'Hold Values',
            SLATE,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        cur_y += 18.0
        p.setFont(QFont('Segoe UI', 8))
        for h in holds[:6]:
            if cur_y + 15 > leg.bottom():
                break
            chart._text(
                p,
                QRectF(leg.left() + 8, cur_y, leg.width() - 16, 15),
                f"{h['name']}: {_fmt(h.get('value', h.get('display')))}",
                MUTED,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
            cur_y += 15.0

def draw_panel(chart, p, area, panel):
    kind = panel['kind']
    if kind == 'model_main_effects':
        _draw_main_effects(chart, p, area, panel)
    elif kind == 'model_interaction':
        _draw_interaction(chart, p, area, panel)
    elif kind == 'model_contour':
        _draw_contour(chart, p, area, panel)
    elif kind == 'model_surface':
        _draw_surface(chart, p, area, panel)
    else:
        raise ValueError(f'Unsupported model plot panel kind: {kind}')
