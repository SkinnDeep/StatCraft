"""Statistical multi-response Optimization Plot for ChartWidget."""
import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainterPath, QPen

RED = '#bb4147'
BLUE = '#056eb2'
SLATE = '#263440'
MUTED = '#5e6d78'
GRID_BG = '#fafafa'
BORDER = '#c6cfd6'


def _fmt(val):
    if val is None:
        return '*'
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if abs(val) < 1e-12:
            return '0'
        return format(float(val), '.4g')
    return str(val)


def prepare(chart, result):
    chart.panels = []
    chart.panel_columns = 1
    chart.note = ''
    if not result.get('options', {}).get('optimization_plot', True):
        return
    profiles = result.get('profiles', [])
    predictions = result.get('predictions', [])
    if not profiles or not predictions:
        raise ValueError('Optimization plot requires at least one predictor profile and one response prediction.')
    comp_d = result.get('optimal_composite_desirability')
    if type(comp_d) not in (int, float) or not math.isfinite(comp_d) or not 0.0 <= comp_d <= 1.0:
        raise ValueError('Optimal composite desirability must be a finite number in [0, 1].')
    for prof in profiles:
        xs = prof.get('x', [])
        cd = prof.get('composite_desirability', [])
        if not xs or len(xs) != len(cd):
            raise ValueError('Predictor profile coordinates and composite desirabilities must be aligned.')
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in cd):
            raise ValueError('Profile composite desirability values must be finite.')
        for rc in prof.get('responses', []):
            fits = rc.get('fits', [])
            ds = rc.get('desirabilities', [])
            if len(fits) != len(xs) or len(ds) != len(xs):
                raise ValueError('Response profile curves must match predictor grid length.')
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in fits + ds):
                raise ValueError('Response profile values must be finite.')

    # Compute y-bounds for each response row across all predictor sweeps
    resp_bounds = []
    for r_i, pred in enumerate(predictions):
        all_y = [pred['fit']]
        for prof in profiles:
            all_y.extend(prof['responses'][r_i]['fits'])
        lo, hi = min(all_y), max(all_y)
        if lo == hi:
            delta = max(0.5, abs(lo) * 0.05)
            lo, hi = lo - delta, hi + delta
        else:
            pad = (hi - lo) * 0.1
            lo, hi = lo - pad, hi + pad
        resp_bounds.append((float(lo), float(hi)))

    chart.panels = [dict(
        kind='optimization_plot',
        title='',
        profiles=profiles,
        predictions=predictions,
        composite_desirability=float(comp_d),
        resp_bounds=resp_bounds,
    )]
    n_rows = 1 + len(predictions)
    chart.setMinimumHeight(max(420, 120 + n_rows * 125))
    chart.setMinimumWidth(max(640, 190 + len(profiles) * 165))
    chart.note = (
        'Red vertical lines mark optimal predictor settings [Cur]; '
        'blue dashed horizontal lines mark predicted response fits and composite desirability D.'
    )


def draw_panel(chart, p, area, panel):
    profiles = panel['profiles']
    predictions = panel['predictions']
    comp_d = panel['composite_desirability']
    resp_bounds = panel['resp_bounds']

    n_cols = len(profiles)
    n_rows = 1 + len(predictions)

    left_w = min(190.0, max(145.0, area.width() * 0.23))
    header_h = 74.0
    grid_left = area.left() + left_w + 8.0
    grid_top = area.top() + header_h + 6.0
    grid_w = max(80.0, area.width() - left_w - 22.0)
    grid_h = max(80.0, area.height() - header_h - 24.0)

    col_w = grid_w / max(1, n_cols)
    row_h = grid_h / max(1, n_rows)

    # Top-left summary box: Optimal D
    opt_box = QRectF(area.left() + 8.0, area.top() + 4.0, left_w - 6.0, header_h - 4.0)
    p.fillRect(opt_box, QColor('#f3f6f8'))
    p.setPen(QPen(QColor(BORDER), 1.0))
    p.drawRect(opt_box)
    p.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
    chart._text(p, QRectF(opt_box.left() + 8, opt_box.top() + 6, opt_box.width() - 16, 20),
                panel.get('setting_label','Optimal Setting'), SLATE, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    p.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
    chart._text(p, QRectF(opt_box.left() + 8, opt_box.top() + 28, opt_box.width() - 16, 20),
                f'D: {comp_d:.4f}', BLUE, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    p.setFont(QFont('Segoe UI', 8))
    chart._text(p, QRectF(opt_box.left() + 8, opt_box.top() + 48, opt_box.width() - 16, 18),
                'Composite Desirability', MUTED, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    # Predictor column headers (High / [Cur] / Low)
    for c_i, prof in enumerate(profiles):
        cx = grid_left + c_i * col_w
        hbox = QRectF(cx + 3.0, area.top() + 4.0, col_w - 6.0, header_h - 4.0)
        p.fillRect(hbox, QColor('#f8fafb'))
        p.setPen(QPen(QColor(BORDER), 1.0))
        p.drawRect(hbox)

        p.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
        name_txt = p.fontMetrics().elidedText(str(prof['name']), Qt.TextElideMode.ElideRight, int(hbox.width() - 10))
        chart._text(p, QRectF(hbox.left() + 5, hbox.top() + 3, hbox.width() - 10, 18),
                    name_txt, SLATE, Qt.AlignmentFlag.AlignCenter)

        p.setFont(QFont('Segoe UI', 8))
        chart._text(p, QRectF(hbox.left() + 6, hbox.top() + 22, hbox.width() - 12, 15),
                    f"High  {_fmt(prof['high'])}", MUTED, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
        chart._text(p, QRectF(hbox.left() + 6, hbox.top() + 37, hbox.width() - 12, 16),
                    f"Cur  [{_fmt(prof['current'])}]", RED, Qt.AlignmentFlag.AlignCenter)
        p.setFont(QFont('Segoe UI', 8))
        chart._text(p, QRectF(hbox.left() + 6, hbox.top() + 53, hbox.width() - 12, 15),
                    f"Low  {_fmt(prof['low'])}", MUTED, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    # Row labels on left + cells across columns
    for r_i in range(n_rows):
        ry = grid_top + r_i * row_h
        lbox = QRectF(area.left() + 8.0, ry + 3.0, left_w - 6.0, row_h - 6.0)
        p.fillRect(lbox, QColor('#ffffff'))
        p.setPen(QPen(QColor(BORDER), 1.0))
        p.drawRect(lbox)

        if r_i == 0:
            p.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
            chart._text(p, QRectF(lbox.left() + 8, lbox.top() + 8, lbox.width() - 16, 18),
                        'Composite', SLATE, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            chart._text(p, QRectF(lbox.left() + 8, lbox.top() + 26, lbox.width() - 16, 18),
                        'Desirability', SLATE, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            p.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
            chart._text(p, QRectF(lbox.left() + 8, lbox.top() + 48, lbox.width() - 16, 20),
                        f'D = {comp_d:.4f}', BLUE, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            yb = (-0.04, 1.04)
            y_ref = comp_d
        else:
            pred = predictions[r_i - 1]
            goal_str = {'minimize': 'Minimum', 'target': f"Target = {_fmt(pred['target'])}", 'maximize': 'Maximum'}.get(pred['goal'], str(pred['goal']).title())
            p.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
            r_name = p.fontMetrics().elidedText(str(pred['response_name']), Qt.TextElideMode.ElideRight, int(lbox.width() - 16))
            chart._text(p, QRectF(lbox.left() + 8, lbox.top() + 6, lbox.width() - 16, 18),
                        r_name, SLATE, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            p.setFont(QFont('Segoe UI', 8))
            chart._text(p, QRectF(lbox.left() + 8, lbox.top() + 24, lbox.width() - 16, 16),
                        goal_str, MUTED, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            p.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
            chart._text(p, QRectF(lbox.left() + 8, lbox.top() + 42, lbox.width() - 16, 18),
                        f"y = {_fmt(pred['fit'])}", BLUE, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            p.setFont(QFont('Segoe UI', 8))
            chart._text(p, QRectF(lbox.left() + 8, lbox.top() + 60, lbox.width() - 16, 16),
                        f"d = {pred['desirability']:.4f}", SLATE, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            yb = resp_bounds[r_i - 1]
            y_ref = float(pred['fit'])

        for c_i, prof in enumerate(profiles):
            cx = grid_left + c_i * col_w
            cell = QRectF(cx + 3.0, ry + 3.0, col_w - 6.0, row_h - 6.0)
            p.fillRect(cell, QColor(GRID_BG))
            p.setPen(QPen(QColor(BORDER), 1.0))
            p.drawRect(cell)
            chart.remember_rect(f's{r_i}', cell)

            pad_x, pad_y = 10.0, 10.0
            inner = cell.adjusted(pad_x, pad_y, -pad_x, -pad_y)
            if inner.width() <= 4 or inner.height() <= 4:
                continue

            xs = prof['x']
            ys = prof['composite_desirability'] if r_i == 0 else prof['responses'][r_i - 1]['fits']

            if prof['role'] == 'factor':
                n_lvl = len(xs)
                x_map = lambda idx_v: inner.left() + (idx_v / max(1, n_lvl - 1)) * inner.width() if n_lvl > 1 else inner.center().x()
                pts = [QPointF(x_map(i), inner.bottom() - ((ys[i] - yb[0]) / (yb[1] - yb[0])) * inner.height()) for i in range(n_lvl)]
                cur_idx = xs.index(prof['current']) if prof['current'] in xs else 0
                cur_px = x_map(cur_idx)
            else:
                x_lo, x_hi = float(min(xs)), float(max(xs))
                if x_hi <= x_lo:
                    x_lo -= 0.5
                    x_hi += 0.5
                x_map = lambda xv: inner.left() + ((float(xv) - x_lo) / (x_hi - x_lo)) * inner.width()
                pts = [QPointF(x_map(xv), inner.bottom() - ((yv - yb[0]) / (yb[1] - yb[0])) * inner.height()) for xv, yv in zip(xs, ys)]
                cur_px = x_map(prof['current'])

            y_ref_px = inner.bottom() - ((y_ref - yb[0]) / (yb[1] - yb[0])) * inner.height()

            p.save()
            p.setClipRect(cell.adjusted(1, 1, -1, -1))

            # Horizontal blue dashed line at current y / D
            p.setPen(QPen(QColor(BLUE), 1.2, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(inner.left(), y_ref_px), QPointF(inner.right(), y_ref_px))

            # Vertical red solid line at current setting
            p.setPen(QPen(QColor(RED), 1.3, Qt.PenStyle.SolidLine))
            p.drawLine(QPointF(cur_px, inner.top()), QPointF(cur_px, inner.bottom()))

            # Profile curve
            if len(pts) > 1:
                path = QPainterPath(pts[0])
                for pt in pts[1:]:
                    path.lineTo(pt)
                p.setPen(QPen(QColor(SLATE), 1.8))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(path)
                chart.remember_path(f's{r_i}', pts)

            if prof['role'] == 'factor':
                p.setPen(QPen(QColor(SLATE), 1.2))
                p.setBrush(QColor(BLUE))
                for pt in pts:
                    p.drawEllipse(pt, 3.5, 3.5)

            # Intersection marker at (cur_px, y_ref_px)
            p.setPen(QPen(QColor(RED), 1.2))
            p.setBrush(QColor('#ffffff'))
            p.drawEllipse(QPointF(cur_px, y_ref_px), 3.6, 3.6)
            p.restore()
