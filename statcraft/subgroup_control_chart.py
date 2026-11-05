"""Chart renderer for Subgroup Control Charts (Xbar-R and Xbar-S).

Draws native dual-panel control charts matching StatCraft:
- Top panel: Sample Mean (Xbar)
- Bottom panel: Sample Range (R) or Sample StDev (S)
- Stepped or constant control limits (LCL, Center Line, UCL)
- Right-hand limit and center annotations (e.g. UCL=12.34, Xbar=10.00, LCL=7.66)
- Test failure markers in RED with Nelson test failure digits (e.g. '1', '2')
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
GREEN = '#1b7837'


def supported(result: dict[str, Any]) -> bool:
    if not isinstance(result, dict) or result.get('analysis') != 'subgroup_control':
        return False
    return bool(result.get('means') and (result.get('ranges') or result.get('stdevs')))


def _fmt(val: float | None, dec: int = 3) -> str:
    if val is None or math.isnan(val):
        return ''
    return f'{val:.{dec}f}'


def _bounds(values: list[float], pad_frac: float = 0.12) -> tuple[float, float]:
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

    chart_type = result.get('chart_type', 'xbar_r')
    var_name = result.get('variable_name', 'Data')
    means = result.get('means', [])
    disp_vals = result.get('disp_values', [])
    k_sub = result.get('k_subgroups', len(means))

    xbar_center = result.get('xbar_center', 0.0)
    xbar_lcls = result.get('xbar_lcl', [])
    xbar_ucls = result.get('xbar_ucl', [])
    test_failures = result.get('test_failures', {})

    disp_name = "R" if chart_type == 'xbar_r' else "S"
    disp_label = "Sample Range" if chart_type == 'xbar_r' else "Sample StDev"
    disp_center = result.get('disp_center')
    disp_lcls = result.get('disp_lcl', [])
    disp_ucls = result.get('disp_ucl', [])
    disp_signals = {pt: [1] for pt in result.get('disp_signals', [])}

    xbar_uwls = result.get('xbar_uwl', [])
    xbar_lwls = result.get('xbar_lwl', [])
    disp_uwls = result.get('disp_uwl', [])
    disp_lwls = result.get('disp_lwl', [])

    # Panel 1: Xbar
    chart.panels.append({
        'kind': 'subgroup_control',
        'subpanel': 'xbar',
        'title': f'Xbar Chart of {var_name}',
        'k_subgroups': k_sub,
        'values': means,
        'center': xbar_center,
        'center_label': f'__\nX={xbar_center:.3f}',
        'lcls': xbar_lcls,
        'ucls': xbar_ucls,
        'uwls': xbar_uwls,
        'lwls': xbar_lwls,
        'signals': test_failures,
        'xlabel': 'Subgroup',
        'ylabel': 'Sample Mean',
    })

    # Panel 2: Dispersion (R or S)
    chart.panels.append({
        'kind': 'subgroup_control',
        'subpanel': 'disp',
        'title': f'{disp_name} Chart of {var_name}',
        'k_subgroups': k_sub,
        'values': disp_vals,
        'center': disp_center,
        'center_label': f'_\n{disp_name}={disp_center:.3f}' if disp_center is not None else '',
        'lcls': disp_lcls,
        'ucls': disp_ucls,
        'uwls': disp_uwls,
        'lwls': disp_lwls,
        'signals': disp_signals,
        'xlabel': 'Subgroup',
        'ylabel': disp_label,
    })

    chart.setMinimumWidth(740)
    chart.setMinimumHeight(680)
    chart.note = f"Tests performed: Nelson rules. Points violating tests are labeled in red."


def draw_panel(chart, p: QPainter, area: QRectF, d: dict[str, Any]) -> None:
    """Draw one control chart panel (Xbar or R/S)."""
    p.save()

    k_sub = d['k_subgroups']
    if k_sub <= 0:
        p.restore()
        return

    values = d['values']
    center = d.get('center')
    lcls = d.get('lcls', [])
    ucls = d.get('ucls', [])
    signals = d.get('signals', {})

    # Collect all Y values for bounds
    all_y = [v for v in values if v is not None]
    if center is not None:
        all_y.append(center)
    for l in lcls:
        if l is not None:
            all_y.append(l)
    for u in ucls:
        if u is not None:
            all_y.append(u)

    xb = (0.5, k_sub + 0.5)
    yb = _bounds(all_y, pad_frac=0.15)

    plot, x, y = chart._axes(
        p, area, xb, yb,
        xlabel=d.get('xlabel', 'Subgroup'),
        ylabel=d.get('ylabel', ''),
        integer=True
    )

    p.save()
    p.setClipRect(plot.adjusted(-1, -1, 1, 1))

    # 1. Draw Center Line (green solid/dash)
    if center is not None and yb[0] <= center <= yb[1]:
        pen_cl = QPen(QColor(GREEN), 1.3, Qt.PenStyle.DashLine)
        p.setPen(pen_cl)
        p.drawLine(QPointF(plot.left(), y(center)), QPointF(plot.right(), y(center)))

    # 2. Draw Control Limits (red dashed lines)
    pen_limit = QPen(QColor(RED), 1.2, Qt.PenStyle.DashLine)
    p.setPen(pen_limit)

    # Check if UCL is constant
    valid_ucl = [u for u in ucls if u is not None]
    if valid_ucl:
        if len(set(round(u, 5) for u in valid_ucl)) == 1:
            u_val = valid_ucl[0]
            if yb[0] <= u_val <= yb[1]:
                p.drawLine(QPointF(plot.left(), y(u_val)), QPointF(plot.right(), y(u_val)))
        else:
            # Stepped limit
            path_u = QPainterPath()
            first = True
            for i, u in enumerate(ucls, 1):
                if u is None:
                    continue
                x_left = x(i - 0.5)
                x_right = x(i + 0.5)
                y_pos = y(u)
                if first:
                    path_u.moveTo(QPointF(x_left, y_pos))
                    first = False
                else:
                    path_u.lineTo(QPointF(x_left, y_pos))
                path_u.lineTo(QPointF(x_right, y_pos))
            p.drawPath(path_u)

    # Check if LCL is constant
    valid_lcl = [l for l in lcls if l is not None]
    if valid_lcl:
        if len(set(round(l, 5) for l in valid_lcl)) == 1:
            l_val = valid_lcl[0]
            if yb[0] <= l_val <= yb[1]:
                p.drawLine(QPointF(plot.left(), y(l_val)), QPointF(plot.right(), y(l_val)))
        else:
            # Stepped limit
            path_l = QPainterPath()
            first = True
            for i, l in enumerate(lcls, 1):
                if l is None:
                    continue
                x_left = x(i - 0.5)
                x_right = x(i + 0.5)
                y_pos = y(l)
                if first:
                    path_l.moveTo(QPointF(x_left, y_pos))
                    first = False
                else:
                    path_l.lineTo(QPointF(x_left, y_pos))
                path_l.lineTo(QPointF(x_right, y_pos))
            p.drawPath(path_l)

    # 2b. Draw Warning Limits (amber dashed lines)
    uwls = d.get('uwls', [])
    lwls = d.get('lwls', [])
    AMBER = '#D97706'
    pen_warn = QPen(QColor(AMBER), 1.1, Qt.PenStyle.DashLine)
    p.setPen(pen_warn)

    valid_uwl = [u for u in uwls if u is not None]
    if valid_uwl:
        if len(set(round(u, 5) for u in valid_uwl)) == 1:
            uw_val = valid_uwl[0]
            if yb[0] <= uw_val <= yb[1]:
                p.drawLine(QPointF(plot.left(), y(uw_val)), QPointF(plot.right(), y(uw_val)))
        else:
            path_uw = QPainterPath()
            first = True
            for i, u in enumerate(uwls, 1):
                if u is None: continue
                x_left = x(i - 0.5); x_right = x(i + 0.5); y_pos = y(u)
                if first: path_uw.moveTo(QPointF(x_left, y_pos)); first = False
                else: path_uw.lineTo(QPointF(x_left, y_pos))
                path_uw.lineTo(QPointF(x_right, y_pos))
            p.drawPath(path_uw)

    valid_lwl = [l for l in lwls if l is not None]
    if valid_lwl:
        if len(set(round(l, 5) for l in valid_lwl)) == 1:
            lw_val = valid_lwl[0]
            if yb[0] <= lw_val <= yb[1]:
                p.drawLine(QPointF(plot.left(), y(lw_val)), QPointF(plot.right(), y(lw_val)))
        else:
            path_lw = QPainterPath()
            first = True
            for i, l in enumerate(lwls, 1):
                if l is None: continue
                x_left = x(i - 0.5); x_right = x(i + 0.5); y_pos = y(l)
                if first: path_lw.moveTo(QPointF(x_left, y_pos)); first = False
                else: path_lw.lineTo(QPointF(x_left, y_pos))
                path_lw.lineTo(QPointF(x_right, y_pos))
            p.drawPath(path_lw)

    # 3. Connect points with blue line
    pen_line = QPen(QColor(BLUE), 1.4, Qt.PenStyle.SolidLine)
    p.setPen(pen_line)
    path_points = QPainterPath()
    has_started = False
    for i, v in enumerate(values, 1):
        if v is None:
            has_started = False
            continue
        pt = QPointF(x(i), y(v))
        if not has_started:
            path_points.moveTo(pt)
            has_started = True
        else:
            path_points.lineTo(pt)
    p.drawPath(path_points)

    # 4. Draw markers and test failure flags
    font_test = QFont('Segoe UI', 8, QFont.Weight.Bold)
    for i, v in enumerate(values, 1):
        if v is None:
            continue
        pt = QPointF(x(i), y(v))
        is_signal = (i in signals)
        if is_signal:
            # Highlighted RED marker
            p.setPen(QPen(QColor(RED), 1.5))
            p.setBrush(QColor(RED))
            p.drawEllipse(pt, 3.8, 3.8)

            # Draw test number above or below marker
            test_nums = signals[i]
            test_str = ",".join(str(t) for t in test_nums)
            p.setFont(font_test)
            p.setPen(QColor(RED))
            y_offset = -14 if (center is None or v >= center) else 14
            p.drawText(QRectF(pt.x() - 20, pt.y() + y_offset - 6, 40, 14), Qt.AlignmentFlag.AlignCenter, test_str)
        else:
            # Normal BLUE marker
            p.setPen(QPen(QColor(BLUE), 1.2))
            p.setBrush(QColor('white'))
            p.drawEllipse(pt, 3.2, 3.2)

    p.restore()  # restore clipping

    # 5. Right-side margin limit labels
    p.setFont(QFont('Segoe UI', 8))
    right_x = plot.right() + 6
    if valid_ucl:
        u_val = valid_ucl[-1]
        p.setPen(QColor(RED))
        lbl = f"UCL={u_val:.3f}" if len(set(round(u, 5) for u in valid_ucl)) == 1 else "UCL=varies"
        p.drawText(QRectF(right_x, y(u_val) - 8, 75, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lbl)

    if valid_uwl:
        uw_val = valid_uwl[-1]
        p.setPen(QColor(AMBER))
        lbl_uw = f"UWL={uw_val:.3f}" if len(set(round(u, 5) for u in valid_uwl)) == 1 else "UWL=varies"
        p.drawText(QRectF(right_x, y(uw_val) - 8, 75, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lbl_uw)

    if center is not None:
        p.setPen(QColor(GREEN))
        c_lbl = d.get('center_label', f"CL={center:.3f}").replace('\n', ' ')
        p.drawText(QRectF(right_x, y(center) - 8, 75, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, c_lbl)

    if valid_lwl:
        lw_val = valid_lwl[-1]
        p.setPen(QColor(AMBER))
        lbl_lw = f"LWL={lw_val:.3f}" if len(set(round(l, 5) for l in valid_lwl)) == 1 else "LWL=varies"
        p.drawText(QRectF(right_x, y(lw_val) - 8, 75, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lbl_lw)

    if valid_lcl:
        l_val = valid_lcl[-1]
        p.setPen(QColor(RED))
        lbl = f"LCL={l_val:.3f}" if len(set(round(l, 5) for l in valid_lcl)) == 1 else "LCL=varies"
        p.drawText(QRectF(right_x, y(l_val) - 8, 75, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lbl)

    p.restore()
