"""Original QPainter rendering for expanded graph result panels."""
import copy
import math
import numbers

from PySide6.QtCore import QPointF, QRectF, QSize, Qt,Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget
from .model import display_date
from .spatial_view import DEFAULT_VIEW, view_state, project_point, depth_order
from .graph_hover import point_info,histogram_info,number,summary_info,surface_cell_info
from .graph_interaction import GraphInteractionMixin,style_pen,style_color,draw_marker
from .chart_theme import chart_painter


COLORS = ('#326b9b', '#b64d45', '#438064', '#9273a6', '#bc8835', '#478b96', '#8b6549', '#7a8491')
INK = '#263440'
MUTED = '#62717d'


def _num(value):
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
        raise ValueError('Graph coordinates must be finite numbers.')
    return float(value)


def _nums(values):
    if not isinstance(values, (list, tuple)):
        raise ValueError('Graph values must be a numeric sequence.')
    return [_num(v) for v in values]


def _bounds(values, zero=False):
    if not values:
        raise ValueError('A graph panel has no observations.')
    low, high = min(values), max(values)
    if zero:
        low, high = min(low, 0), max(high, 0)
    span = high - low
    pad = max(.5, abs(low) * .04) if span == 0 else span * .06
    low, high = low if zero and low==0 else low-pad, high+pad
    if not all(math.isfinite(x) for x in (low, high, high-low)) or high <= low:
        raise ValueError('The numeric range exceeds supported plotting precision.')
    return low, high


def _fmt(v):
    return '0' if v == 0 else f'{v:.4g}'


def _color(value, low, high):
    position = .5 if high == low else min(1, max(0, (value-low)/(high-low)))
    if low < 0 < high:
        center = -low/(high-low)
        if position <= center:
            t = position/center
            a, b = QColor('#356c9d'), QColor('#f7f7f7')
        else:
            t = (position-center)/(1-center)
            a, b = QColor('#f7f7f7'), QColor('#b74a45')
    else:
        t = position
        a, b = QColor('#edf3f8'), QColor('#275d8a')
    return QColor(*(round(ca*(1-t)+cb*t) for ca,cb in zip(a.getRgb()[:3],b.getRgb()[:3])))


class ExpandedChartWidget(GraphInteractionMixin,QWidget):
    objectSelected=Signal(str)
    objectActivated=Signal(str)
    brushRowsSelected=Signal(list)
    palette_colors=COLORS
    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self._init_graph_interaction()
        self.panels = []
        self.error = None
        self.title = 'Graph'
        self.view_state = dict(DEFAULT_VIEW)
        self._orbit_position = None
        self._pan_position = None
        self.setMinimumSize(520, 350)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFont(QFont('Segoe UI', 10))
        try:
            result = entry.get('result', entry)
            if not isinstance(result, dict) or result.get('graph') != 'expanded':
                raise ValueError('This graph requires an expanded result record.')
            self.title = str(result.get('title', entry.get('title', result.get('label', 'Graph'))))
            panels = result['panels']
            if not isinstance(panels, list) or not 1 <= len(panels) <= 100:
                raise ValueError('An expanded graph requires 1 to 100 panels.')
            self.panels = [self._validate(copy.deepcopy(p)) for p in panels]
        except (ValueError, TypeError, KeyError, IndexError, OverflowError, AttributeError) as exc:
            self.panels = []
            self.error = str(exc)
        self._interactive_3d = any(p['kind'] == 'xyz' or (p['kind'] == 'surface' and not p.get('contour')) for p in self.panels)
        if self._interactive_3d:
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.setToolTip('Drag to rotate. Scroll to zoom. Arrow keys rotate; +/- zoom. Double-click or Home resets the view.')

    def rotate_view(self, dx, dy):
        current = self.view_state
        px = current.get('pan_x', 0.0)
        py = current.get('pan_y', 0.0)
        self.view_state = view_state(current['azimuth'] + dx, current['elevation'] + dy, current['zoom'], pan_x=px, pan_y=py)
        self.update()

    def pan_view(self, dx, dy):
        current = self.view_state
        px = current.get('pan_x', 0.0) + dx
        py = current.get('pan_y', 0.0) + dy
        self.view_state = view_state(current['azimuth'], current['elevation'], current['zoom'], pan_x=px, pan_y=py)
        self.update()

    def zoom_view(self, steps):
        if isinstance(steps, bool) or not isinstance(steps, numbers.Real) or not math.isfinite(steps):
            raise ValueError('3D zoom steps must be finite numbers.')
        current = self.view_state
        px = current.get('pan_x', 0.0)
        py = current.get('pan_y', 0.0)
        self.view_state = view_state(current['azimuth'], current['elevation'], current['zoom'] * math.exp(max(-20, min(20, steps)) * .12), pan_x=px, pan_y=py)
        self.update()

    def reset_view(self):
        self.view_state = dict(DEFAULT_VIEW)
        self.update()

    def contextMenuEvent(self, event):
        if self._interactive_3d:
            event.accept()
            return
        super().contextMenuEvent(event)

    def mousePressEvent(self, event):
        self._hide_hover()
        if self._interactive_3d:
            is_pan = (
                event.button() == Qt.MouseButton.MiddleButton
                or (event.button() == Qt.MouseButton.RightButton and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
                or (event.button() == Qt.MouseButton.LeftButton and bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
            )
            if is_pan:
                self._pan_position = event.position()
                self.setFocus(Qt.FocusReason.MouseFocusReason)
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                event.accept()
                return

            if event.button() == Qt.MouseButton.RightButton:
                self._orbit_position = event.position()
                self.setFocus(Qt.FocusReason.MouseFocusReason)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._pan_position is not None:
            delta = event.position() - self._pan_position
            self._pan_position = event.position()
            self.pan_view(delta.x(), delta.y())
            event.accept()
            return
        if self._orbit_position is not None:
            delta = event.position() - self._orbit_position
            self._orbit_position = event.position()
            self.rotate_view(-delta.x() * .5, -delta.y() * .5)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pan_position is not None:
            self._pan_position = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        if self._orbit_position is not None:
            self._orbit_position = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._interactive_3d:
            self._orbit_position = None
            self._pan_position = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.reset_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        if self._interactive_3d:
            steps = event.angleDelta().y() / 120 or event.pixelDelta().y() / 60
            self.zoom_view(steps)
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event):
        if self._interactive_3d:
            key = event.key()
            rotations = {Qt.Key.Key_Left: (-5, 0), Qt.Key.Key_Right: (5, 0), Qt.Key.Key_Up: (0, 5), Qt.Key.Key_Down: (0, -5)}
            if key in rotations:
                self.rotate_view(*rotations[key])
            elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self.zoom_view(1)
            elif key == Qt.Key.Key_Minus:
                self.zoom_view(-1)
            elif key == Qt.Key.Key_Home:
                self.reset_view()
            else:
                super().keyPressEvent(event)
                return
            event.accept()
            return
        super().keyPressEvent(event)

    def minimumSizeHint(self):
        return QSize(560, 440 if len(self.panels) > 1 else 360)

    def sizeHint(self):
        return QSize(900, 680 if len(self.panels) > 1 else 540)

    def _validate(self, p):
        if not isinstance(p, dict):
            raise ValueError('Graph panels must be objects.')
        kind = p['kind']
        if kind == 'xy':
            if not p.get('series'):
                raise ValueError('An XY graph requires a series.')
            xs, ys = [], []
            for series in p['series']:
                pts = series['points']
                if not pts:
                    raise ValueError('An XY series has no points.')
                for pt in pts:
                    if not isinstance(pt, (list, tuple)) or len(pt) not in (2, 3):
                        raise ValueError('XY points require two coordinates and an optional bubble size.')
                    vals = _nums(pt)
                    if len(vals) == 3 and vals[2] < 0:
                        raise ValueError('Bubble sizes must be nonnegative.')
                    xs.append(vals[0]); ys.append(vals[1])
            p['_xb'], p['_yb'] = _bounds(xs), _bounds(ys,zero=any(s.get('fill') for s in p['series']))
        elif kind in ('bars', 'pie', 'binbars'):
            values = _nums(p['values'])
            if not values:
                raise ValueError('A graph requires nonempty values.')
            if kind == 'binbars' or 'edges' in p:
                edges = _nums(p['edges'])
                if len(edges) != len(values)+1 or any(b <= a for a, b in zip(edges, edges[1:])):
                    raise ValueError('Bin edges must increase and match the values.')
                p['_xb'] = _bounds(edges)
            elif len(p['categories']) != len(values):
                raise ValueError('Category labels must match values.')
            if kind == 'pie' and (min(values) < 0 or sum(values) <= 0 or not math.isfinite(sum(values))):
                raise ValueError('Pie values must be nonnegative with a positive finite total.')
            p['_yb'] = _bounds(values, True)
        elif kind == 'heatmap':
            values = [_nums(row) for row in p['values']]
            if not values or not values[0] or any(len(row) != len(values[0]) for row in values):
                raise ValueError('A heatmap requires a rectangular numeric grid.')
            if len(values) != len(p['y_labels']) or len(values[0]) != len(p['x_labels']):
                raise ValueError('Heatmap labels must match the grid dimensions.')
            _bounds([v for row in values for v in row])
            p['_range'] = min(v for row in values for v in row), max(v for row in values for v in row)
        elif kind == 'intervals':
            if not p['items']:
                raise ValueError('An interval plot requires observations.')
            vals = []
            for item in p['items']:
                lo, mean, hi = [_num(item[k]) for k in ('lower', 'mean', 'upper')]
                if not lo <= mean <= hi:
                    raise ValueError('Interval bounds must contain the mean.')
                vals += [lo, hi]
            p['_yb'] = _bounds(vals)
        elif kind == 'parallel':
            rows = [_nums(row) for row in p['rows']]
            if not rows or not p['axes'] or any(len(row) != len(p['axes']) for row in rows):
                raise ValueError('Parallel-coordinate axes must match the data rows.')
            p['_ranges'] = [_bounds([row[c] for row in rows]) for c in range(len(p['axes']))]
        elif kind == 'xyz':
            if not p['points'] or any(len(pt) != 3 for pt in p['points']):
                raise ValueError('A 3D scatterplot requires triples.')
            pts = [_nums(pt) for pt in p['points']]
            p['_ranges'] = [_bounds([pt[c] for pt in pts]) for c in range(3)]
        elif kind == 'surface':
            x, y = _nums(p['x']), _nums(p['y'])
            z = [_nums(row) for row in p['z']]
            if len(x) < 2 or len(y) < 2 or len(z) != len(y) or any(len(row) != len(x) for row in z):
                raise ValueError('A surface needs increasing X/Y axes and a matching Z grid.')
            if any(b <= a for axis in (x, y) for a, b in zip(axis, axis[1:])):
                raise ValueError('Surface axes must increase.')
            p['_ranges'] = [_bounds(x), _bounds(y), _bounds([v for row in z for v in row])]
        elif kind == 'wafer':
            dies = p.get('dies', [])
            if not dies:
                raise ValueError('Wafer plot requires die coordinate and measurement rows.')
            xs = _nums([d['x'] for d in dies]); ys = _nums([d['y'] for d in dies]); vs = _nums([d['val'] for d in dies])
            p['_xrange'] = (min(xs), max(xs))
            p['_yrange'] = (min(ys), max(ys))
            p['_range'] = (min(vs), max(vs))
        elif kind == 'stem_leaf':
            if not isinstance(p['lines'], list) or not all(isinstance(line, str) for line in p['lines']):
                raise ValueError('Stem-and-leaf lines must be text.')
        else:
            raise ValueError('Unsupported expanded panel: ' + str(kind))
        return p

    @staticmethod
    def _text(q, rect, text, align=Qt.AlignmentFlag.AlignCenter, color=MUTED):
        q.setPen(QColor(color))
        q.drawText(rect, align, str(text))

    def _axes(self, q, bounds, xb, yb, xlabel='', ylabel='', categories=None,x_date=False):
        labels=getattr(self,'annotation_axes',{});positions=getattr(self,'annotation_positions',{})
        limits=getattr(self,'annotation_limits',{})
        limits=dict(limits,**getattr(self,'panel_annotation_limits',{}).get(self._panel_index,{}))
        xb=limits.get('x',xb);yb=limits.get('y',yb)
        xlabel=labels.get('x',xlabel);ylabel=labels.get('y',ylabel)
        plot = bounds.adjusted(56, 18, -18, -53)
        self.remember_axes(plot)
        axis=self.graph_style('axis',color='#66737d',line_width=1,visible=True)
        grid=self.graph_style('grid',color='#dfe4e8',line_width=1,visible=True)
        for i in range(5):
            t = i/4
            yy = plot.bottom()-t*plot.height()
            if getattr(self,'annotation_grid',True) and grid['visible']:
                q.setPen(style_pen(grid));q.drawLine(QPointF(plot.left(), yy), QPointF(plot.right(), yy))
            if axis['visible']:self._text(q, QRectF(bounds.left(), yy-9, 49, 18), _fmt(yb[0]+t*(yb[1]-yb[0])), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,color=axis['color'])
        if axis['visible']:
            q.setPen(style_pen(axis));q.drawLine(plot.bottomLeft(), plot.bottomRight());q.drawLine(plot.bottomLeft(), plot.topLeft())
        if categories is None and axis['visible']:
            for i in range(5):
                t = i/4
                value=xb[0]+t*(xb[1]-xb[0])
                text=display_date(value).split(' ')[0] if x_date else _fmt(value)
                self._text(q, QRectF(plot.left()+t*plot.width()-45, plot.bottom()+5, 90, 19),text)
        elif axis['visible']:
            step = max(1, math.ceil(len(categories)/10))
            for i, label in enumerate(categories):
                if i % step == 0:
                    xx = plot.left()+((i+1)-xb[0])/(xb[1]-xb[0])*plot.width()
                    self._text(q, QRectF(xx-42, plot.bottom()+4, 84, 24), str(label)[:16])
        if axis['visible'] and positions.get('x')!='off':self._text(q, QRectF(plot.left(), bounds.top()-2 if positions.get('x')=='high' else bounds.bottom()-23, plot.width(), 20), xlabel,color=axis['color'])
        q.save()
        q.translate(bounds.right()-4 if positions.get('y')=='high' else bounds.left()+12, plot.center().y())
        q.rotate(-90)
        if axis['visible'] and positions.get('y')!='off':self._text(q, QRectF(-plot.height()/2, -10, plot.height(), 20), ylabel,color=axis['color'])
        q.restore()
        x_log = bool(getattr(self, 'annotation_x_log', False)) and categories is None and not x_date and xb[0] > 0 and xb[1] > 0
        y_log = bool(getattr(self, 'annotation_y_log', False)) and yb[0] > 0 and yb[1] > 0
        _lx0, _lx1 = (math.log10(xb[0]), math.log10(xb[1])) if x_log else (0.0, 1.0)
        _ly0, _ly1 = (math.log10(yb[0]), math.log10(yb[1])) if y_log else (0.0, 1.0)
        def point(x, y):
            if x_log:
                px = plot.left() + (math.log10(max(x, 1e-12)) - _lx0) / max(1e-12, _lx1 - _lx0) * plot.width()
            else:
                px = plot.left() + (x - xb[0]) / max(1e-12, xb[1] - xb[0]) * plot.width()
            if y_log:
                py = plot.bottom() - (math.log10(max(y, 1e-12)) - _ly0) / max(1e-12, _ly1 - _ly0) * plot.height()
            else:
                py = plot.bottom() - (y - yb[0]) / max(1e-12, yb[1] - yb[0]) * plot.height()
            return QPointF(px, py)
        for xv in (getattr(self, 'annotation_x_ref', []) or []):
            try:
                px = point(xv, yb[0]).x()
                if plot.left() - 2 <= px <= plot.right() + 2:
                    q.setPen(QPen(QColor('#0284c7'), 1.3, Qt.PenStyle.DashLine))
                    q.drawLine(QPointF(px, plot.top()), QPointF(px, plot.bottom()))
            except Exception:
                pass
        for yv in (getattr(self, 'annotation_y_ref', []) or []):
            try:
                py = point(xb[0], yv).y()
                if plot.top() - 2 <= py <= plot.bottom() + 2:
                    q.setPen(QPen(QColor('#dc2626'), 1.3, Qt.PenStyle.DashLine))
                    q.drawLine(QPointF(plot.left(), py), QPointF(plot.right(), py))
            except Exception:
                pass
        return plot, point

    def _legend(self, q, area, labels):
        if not labels:
            return area
        labels = labels[:20]
        q.setFont(QFont('Segoe UI', 8))
        width = min(170, max(85, area.width()*.23))
        for i, label in enumerate(labels):
            style=self.graph_style('s'+str(i),color=COLORS[i%len(COLORS)],line_width=3)
            if not style.get('legend_visible',True):continue
            yy = area.top()+i*19
            q.setPen(style_pen(style))
            q.drawLine(QPointF(area.right()-width+6, yy+9), QPointF(area.right()-width+20, yy+9))
            if self.panels[self._panel_index]['kind']=='xy':draw_marker(q,QPointF(area.right()-width+13,yy+9),style)
            self._text(q, QRectF(area.right()-width+26, yy, width-28, 18), str(label)[:24], Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if self.panels[self._panel_index]['kind']=='xy':self.remember_rect('s'+str(i),QRectF(area.right()-width,yy,width,18))
        return area.adjusted(0, 0, -width, 0)

    def _panel(self, q, bounds, p):
        q.setFont(QFont('Segoe UI', 10, QFont.Weight.DemiBold))
        self._text(q, QRectF(bounds.left(), bounds.top(), bounds.width(), 23), p.get('title', ''), color=INK)
        bounds = bounds.adjusted(0, 26, 0, 0)
        q.setFont(QFont('Segoe UI', 8))
        kind = p['kind']
        if kind == 'stem_leaf':
            q.setFont(QFont('Consolas', 10))
            self._text(q, bounds.adjusted(18, 4, -10, -4), '\n'.join(p['lines']), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, INK)
            return
        if kind == 'pie':
            vals = p['values']; total = sum(vals)
            bounds = self._legend(q, bounds, [f'{name}: {_fmt(value)} ({value/total:.1%})' for name, value in zip(p['categories'], vals)])
            side = max(1, min(bounds.width()-20, bounds.height()-20))
            pie = QRectF(bounds.center().x()-side/2, bounds.center().y()-side/2, side, side)
            angle = 90*16
            for i, value in enumerate(vals):
                span = round(-value/total*360*16)
                q.setPen(QPen(QColor('white'), 1)); q.setBrush(QColor(COLORS[i % len(COLORS)]))
                q.drawPie(pie, angle, span)
                path=QPainterPath();path.moveTo(pie.center());path.arcTo(pie,angle/16,span/16);path.closeSubpath()
                self.remember_hover(path,summary_info('pie',[('Category',p['categories'][i]),('Value',value),('Percent',100*value/total)]),pie)
                angle += span
            return
        if kind == 'wafer':
            dies = p['dies']
            x0, x1 = p['_xrange']; y0, y1 = p['_yrange']; low, high = p['_range']
            ux = sorted({d['x'] for d in dies}); uy = sorted({d['y'] for d in dies})
            dx = min((b - a for a, b in zip(ux, ux[1:])), default=1.0)
            dy = min((b - a for a, b in zip(uy, uy[1:])), default=1.0)
            rect = bounds.adjusted(30, 8, -70, -24)
            side = max(40.0, min(rect.width(), rect.height()))
            wafer_rect = QRectF(rect.center().x() - side / 2, rect.center().y() - side / 2, side, side)
            inner = wafer_rect.adjusted(side * 0.08, side * 0.08, -side * 0.08, -side * 0.08)
            q.setPen(QPen(QColor('#475569'), 1.6))
            q.setBrush(QColor('#f8fafc'))
            q.drawEllipse(wafer_rect)
            span_x = max(dx, (x1 - x0) + dx)
            span_y = max(dy, (y1 - y0) + dy)
            die_w = max(4.0, (dx / span_x) * inner.width() * 0.9)
            die_h = max(4.0, (dy / span_y) * inner.height() * 0.9)
            axes = p.get('axes', ['Die X', 'Die Y', 'Metric'])
            for d in dies:
                cx = inner.left() + ((d['x'] - x0 + dx * 0.5) / span_x) * inner.width()
                cy = inner.bottom() - ((d['y'] - y0 + dy * 0.5) / span_y) * inner.height()
                die_box = QRectF(cx - die_w / 2, cy - die_h / 2, die_w, die_h)
                fill_c = _color(d['val'], low, high)
                q.setPen(QPen(QColor('#ffffff'), 0.8))
                q.setBrush(fill_c)
                q.drawRect(die_box)
                if getattr(self, 'annotation_data_labels', False) and len(dies) <= 64:
                    self._text(q, die_box, _fmt(d['val']), color=INK)
                self.remember_hover(die_box, summary_info('wafer', [(axes[0], d['x']), (axes[1], d['y']), (axes[2], d['val'])], row=d.get('row')), wafer_rect)
            for i in range(100):
                q.fillRect(QRectF(wafer_rect.right() + 14, wafer_rect.top() + i * wafer_rect.height() / 100, 12, wafer_rect.height() / 100 + 1), _color(high - (high - low) * i / 99, low, high))
            self._text(q, QRectF(wafer_rect.right() + 10, wafer_rect.top() - 16, 48, 16), _fmt(high))
            self._text(q, QRectF(wafer_rect.right() + 10, wafer_rect.bottom() + 1, 48, 16), _fmt(low))
            return
        if kind == 'heatmap':
            rows, cols = len(p['values']), len(p['values'][0])
            rect = bounds.adjusted(65, 12, -58, -45)
            low, high = p['_range']
            for r, row in enumerate(p['values']):
                for c, value in enumerate(row):
                    cell = QRectF(rect.left()+c*rect.width()/cols, rect.top()+r*rect.height()/rows, rect.width()/cols, rect.height()/rows)
                    q.fillRect(cell, _color(value, low, high))
                    self.remember_hover(cell,summary_info('heatmap',[('Column',p['x_labels'][c]),('Row',p['y_labels'][r]),('Value',value)],value=value),rect)
                    if rows <= 10 and cols <= 10:
                        self._text(q, cell, _fmt(value), color=INK)
            for c, label in enumerate(p['x_labels']):
                if c % max(1, math.ceil(cols/12)) == 0:
                    self._text(q, QRectF(rect.left()+c*rect.width()/cols-30+rect.width()/cols/2, rect.bottom()+5, 60, 30), str(label)[:12])
            for r, label in enumerate(p['y_labels']):
                if r % max(1, math.ceil(rows/16)) == 0:
                    self._text(q, QRectF(bounds.left(), rect.top()+r*rect.height()/rows, 60, rect.height()/rows), str(label)[:12], Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            for i in range(100):
                q.fillRect(QRectF(rect.right()+13, rect.top()+i*rect.height()/100, 12, rect.height()/100+1), _color(high-(high-low)*i/99, low, high))
            self._text(q, QRectF(rect.right()+10, rect.top()-17, 48, 16), _fmt(high))
            self._text(q, QRectF(rect.right()+10, rect.bottom()+1, 48, 16), _fmt(low))
            return
        if kind == 'parallel':
            rect = bounds.adjusted(40, 28, -25, -45)
            axes = p['axes']; n = len(axes)
            def pt(c, value):
                lo, hi = p['_ranges'][c]
                return QPointF(rect.left()+c*rect.width()/max(1,n-1), rect.bottom()-(value-lo)/(hi-lo)*rect.height())
            for c, name in enumerate(axes):
                lo, hi = p['_ranges'][c]
                q.setPen(QPen(QColor('#b6c0c8'), 1)); q.drawLine(pt(c, lo), pt(c, hi))
                xx = pt(c, lo).x()
                self._text(q, QRectF(xx-36, rect.bottom()+4, 72, 32), str(name)[:18])
                self._text(q, QRectF(xx-32, rect.top()-19, 64, 17), _fmt(hi))
                self._text(q, QRectF(xx-32, rect.bottom()-18, 64, 17), _fmt(lo))
            for i, row in enumerate(p['rows']):
                color = QColor(COLORS[i % len(COLORS)]); color.setAlpha(110)
                q.setPen(QPen(color, 1)); q.setBrush(Qt.BrushStyle.NoBrush)
                q.drawPolyline(QPolygonF([pt(c, v) for c, v in enumerate(row)]))
            return
        if kind in ('xyz', 'surface'):
            self._spatial(q, bounds, p)
            return
        if kind == 'xy':
            series = p['series']
            labels = [s.get('name', '') for s in series]
            if len(series) > 1 or any(labels):
                bounds = self._legend(q, bounds, labels)
            plot, point = self._axes(q, bounds, p['_xb'], p['_yb'], p.get('x_label', ''), p.get('y_label', ''),x_date=p.get('x_date',False))
            q.save(); q.setClipRect(plot.adjusted(-8,-8,8,8))
            for i, s in enumerate(series):
                style=self.graph_style('s'+str(i),color=COLORS[i%len(COLORS)],line_width=1.5)
                if not style.get('visible',True):continue
                color = style_color(style['color'],style.get('opacity',1))
                q.setPen(style_pen(dict(style,edge=style['color']))); q.setBrush(color)
                points = [point(v[0], v[1]) for v in s['points']]
                if s.get('fill'):
                    polygon=[point(s['points'][0][0],0)]+points+[point(s['points'][-1][0],0)]
                    shade=QColor(color);shade.setAlpha(round(75*style.get('opacity',1)));q.setBrush(shade);q.setPen(Qt.PenStyle.NoPen)
                    q.drawPolygon(QPolygonF(polygon));q.setPen(QPen(color,1.5));q.setBrush(color)
                if s.get('connect'):
                    q.drawPolyline(QPolygonF(points))
                    if style.get('line_style')!='none':self.remember_path('s'+str(i),points)
                maxsize = max((v[2] for v in s['points'] if len(v) == 3), default=1)
                for point_index,(pos, raw) in enumerate(zip(points, s['points'])):
                    radius = 3 if len(raw) < 3 else (2+12*math.sqrt(raw[2]/maxsize) if maxsize else 2)
                    fill = QColor(color); fill.setAlpha(130 if len(raw) == 3 else 220)
                    draw_marker(q,pos,style,default_size=radius*2)
                    if getattr(self, 'annotation_data_labels', False) and style.get('visible', True):
                        self._text(q, QRectF(pos.x() - 24, pos.y() - 18, 48, 14), _fmt(raw[1]), color=INK)
                    if style.get('marker')!='none':
                        rows=s.get('row_indices',[]);row=rows[point_index] if point_index<len(rows) else None
                        self.remember_marker('s'+str(i),pos,style.get('marker_size',radius*2),row)
                        info=point_info(raw[0],raw[1],p.get('x_label','X'),p.get('y_label','Y'),s.get('name',''),row)
                        if p.get('x_date'):info['text']=info['text'].replace(number(raw[0]),display_date(raw[0]),1)
                        if len(raw)>2:info['size']=raw[2];info['text']+='\nSize: '+number(raw[2])
                        self.remember_point_hover(pos,info,style.get('marker_size',radius*2),plot)
            q.restore()
            return
        if kind == 'intervals':
            labels = [it['name'] for it in p['items']]
            xb = (.25, len(labels)+.75)
            plot, point = self._axes(q, bounds, xb, p['_yb'], p.get('x_label', ''), p.get('y_label', 'Mean and confidence interval'), labels)
            style=self.graph_style('s0',color=COLORS[0],line_width=1.7)
            if not style.get('visible',True):return
            q.setPen(style_pen(style)); q.setBrush(style_color(style['color'],style.get('opacity',1)))
            for i, item in enumerate(p['items'], 1):
                lo, hi = point(i, item['lower']), point(i, item['upper'])
                q.drawLine(lo, hi)
                for pos in (lo, hi):
                    q.drawLine(pos-QPointF(5,0), pos+QPointF(5,0))
                draw_marker(q,point(i,item['mean']),style,default_size=8)
                self.remember_path('s0',[lo,hi]);self.remember_marker('s0',point(i,item['mean']),style.get('marker_size',8))
                self.remember_hover(QRectF(lo,hi).normalized().adjusted(-6,-3,6,3),summary_info('interval',[('Group',item['name']),('Mean',item['mean']),('Lower',item['lower']),('Upper',item['upper'])]),plot)
            return
        if kind in ('bars', 'binbars'):
            vals = p['values']; edges = p.get('edges')
            xb = p['_xb'] if edges else (.25, len(vals)+.75)
            labels = None if edges else p['categories']
            plot, point = self._axes(q, bounds, xb, p['_yb'], p.get('x_label', ''), p.get('y_label', 'Value'), labels)
            style=self.graph_style('bars',fill=COLORS[0],edge='#ffffff',line_width=1)
            if not style.get('visible',True):return
            q.setPen(style_pen(style)); q.setBrush(style_color(style['fill'],style.get('opacity',1)))
            for i, value in enumerate(vals):
                left, right = (edges[i], edges[i+1]) if edges else (i+.65, i+1.35)
                a, b = point(left, 0), point(right, value)
                rect=QRectF(a,b).normalized();q.drawRect(rect);self.remember_rect('bars',rect)
                if getattr(self, 'annotation_data_labels', False):
                    self._text(q, QRectF(rect.left(), rect.top() - 16, rect.width(), 15), _fmt(value), color=INK)
                info=histogram_info(left,right,value,p.get('y_label','Value')) if edges else point_info(p['categories'][i],value,p.get('x_label','Category'),p.get('y_label','Value'))
                if not edges:info['kind']='bar'
                self.remember_hover(rect,info,plot)

    def _spatial(self, q, bounds, p):
        if p['kind'] == 'surface' and p.get('contour'):
            self._contour(q, bounds, p)
            return
        rect = bounds.adjusted(15, 4, -15, -36)
        ranges = p['_ranges']
        viewport = (rect.left(), rect.top(), rect.width(), rect.height())
        def projected(point):
            return project_point(point, ranges, self.view_state, viewport)
        def project(point):
            x, y, _ = projected(point)
            return QPointF(x, y)
        lows, highs = [r[0] for r in ranges], [r[1] for r in ranges]
        corners = [[highs[i] if bits & (1 << i) else lows[i] for i in range(3)] for bits in range(8)]
        q.setPen(QPen(QColor('#dce3e9'), 1))
        for bits, corner in enumerate(corners):
            for axis in range(3):
                if not bits & (1 << axis):
                    q.drawLine(project(corner), project(corners[bits | (1 << axis)]))
        q.save()
        q.setClipRect(rect.adjusted(-4, -4, 4, 4))
        if p['kind'] == 'xyz':
            style=self.graph_style('s0',color=COLORS[0],edge='#ffffff')
            for index in depth_order(p['points'], ranges, self.view_state):
                px, py, depth = projected(p['points'][index])
                radius = 3.8 * 6 / (6 - depth)
                draw_marker(q,QPointF(px,py),style,default_size=radius*2)
                if style.get('visible',True) and style.get('marker')!='none':
                    self.remember_marker('s0',QPointF(px,py),style.get('marker_size',radius*2))
                    raw=p['points'][index];axes=p.get('axes',['X','Y','Z'])
                    self.remember_point_hover(QPointF(px,py),point_info(raw[0],raw[1],axes[0],axes[1],z=raw[2],zlabel=axes[2]),style.get('marker_size',radius*2),rect)
        else:
            x, y, z = p['x'], p['y'], p['z']
            low, high = min(v for row in z for v in row), max(v for row in z for v in row)
            faces = []
            for r in range(len(y)-1):
                for c in range(len(x)-1):
                    vertices = [(x[c], y[r], z[r][c]), (x[c+1], y[r], z[r][c+1]),
                                (x[c+1], y[r+1], z[r+1][c+1]), (x[c], y[r+1], z[r+1][c])]
                    camera_depth = sum(projected(v)[2] for v in vertices) / 4
                    faces.append((camera_depth, vertices))
            for _, vertices in sorted(faces, key=lambda face: face[0]):
                q.setBrush(_color(sum(v[2] for v in vertices)/4, low, high))
                q.setPen(QPen(QColor('#6d8493'), .7))
                q.drawPolygon(QPolygonF([project(v) for v in vertices]))
                path=QPainterPath();path.addPolygon(QPolygonF([project(v) for v in vertices]));path.closeSubpath()
                self.remember_hover(path,surface_cell_info(vertices,p.get('axes',['X','Y','Z'])),rect)
        q.restore()
        # Named axes stay above the depth-sorted data rather than disappearing behind it.
        origin = project(lows)
        axis_labels = p.get('axes', [p.get('x_label', 'X'), p.get('y_label', 'Y'), p.get('z_label', 'Z')])
        for i, label in enumerate(axis_labels[:3]):
            vals = lows[:]
            vals[i] = highs[i]
            end = project(vals)
            q.setPen(QPen(QColor('#627484'), 1.3))
            q.drawLine(origin, end)
            delta = end - origin
            length = math.hypot(delta.x(), delta.y())
            ux, uy = (delta.x()/length, delta.y()/length) if length > 1 else (0, -1)
            label_center = end + QPointF(ux * 28, uy * 28)
            label_rect = QRectF(label_center.x()-75, label_center.y()-11, 150, 22)
            label_rect.moveLeft(max(bounds.left(), min(bounds.right()-150, label_rect.left())))
            label_rect.moveTop(max(bounds.top(), min(bounds.bottom()-44, label_rect.top())))
            q.fillRect(label_rect, QColor(255, 255, 255, 225))
            self._text(q, label_rect, str(label), color=INK)
            for t in (0, .5, 1):
                vals[i] = ranges[i][0] + t*(ranges[i][1]-ranges[i][0])
                pos = project(vals)
                normal = QPointF(-uy*4, ux*4)
                q.setPen(QPen(QColor('#627484'), 1))
                q.drawLine(pos-normal, pos+normal)
                tick = QRectF(pos.x()-27-uy*12, pos.y()-8+ux*12, 54, 16)
                q.fillRect(tick, QColor(255, 255, 255, 210))
                self._text(q, tick, _fmt(vals[i]))
        self._text(q, QRectF(bounds.left(), bounds.bottom()-25, bounds.width(), 22),
                   'Drag to rotate | Scroll to zoom | Double-click to reset | Arrow keys / + / - / Home')

    def _contour(self, q, bounds, p):
        x,y,z = p['x'],p['y'],p['z']
        ranges = p['_ranges']
        axes=p.get('axes',[p.get('x_label','X'),p.get('y_label','Y')])
        plot, point = self._axes(q,bounds,ranges[0],ranges[1],axes[0],axes[1])
        low,high = min(v for row in z for v in row),max(v for row in z for v in row)
        for r in range(len(y)-1):
            for c in range(len(x)-1):
                value = (z[r][c]+z[r][c+1]+z[r+1][c]+z[r+1][c+1])/4
                q.fillRect(QRectF(point(x[c],y[r]),point(x[c+1],y[r+1])).normalized(),_color(value,low,high))
        if high == low:
            return
        for index in range(1,9):
            level = low+(high-low)*index/9
            q.setPen(QPen(QColor('#344c5e'),1))
            labeled=False
            for r in range(len(y)-1):
                for c in range(len(x)-1):
                    corners=[(x[c],y[r],z[r][c]),(x[c+1],y[r],z[r][c+1]),(x[c+1],y[r+1],z[r+1][c+1]),(x[c],y[r+1],z[r+1][c])]
                    hits=[]
                    for a,b in zip(corners,corners[1:]+corners[:1]):
                        if (a[2] <= level < b[2]) or (b[2] <= level < a[2]):
                            t=(level-a[2])/(b[2]-a[2])
                            hits.append(point(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])))
                    for j in range(0,len(hits)-1,2):
                        q.drawLine(hits[j],hits[j+1])
                        if not labeled:
                            pos=hits[j]
                            self._text(q,QRectF(pos.x()-25,pos.y()-10,50,20),_fmt(level),color=INK)
                            labeled=True

    def paintEvent(self, event):
        self.reset_hover_regions()
        self.hit_regions=[]
        self.brush_regions=[]
        q = chart_painter(self)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        q.fillRect(self.rect(), QColor('white'))
        q.setFont(QFont('Segoe UI', 12, QFont.Weight.DemiBold))
        self._text(q, QRectF(14, 10, self.width()-28, 27), self.title, color=INK)
        if self.error:
            q.setFont(QFont('Segoe UI', 10))
            self._text(q, QRectF(25, 55, self.width()-50, self.height()-80), 'Graph unavailable: '+self.error, color='#a32020')
            q.end()
            return
        try:
            n = len(self.panels)
            cols = 1 if n <= 2 else math.ceil(math.sqrt(n))
            rows = math.ceil(n/cols)
            top=45 if self.title else 6
            width, height = (self.width()-20)/cols, (self.height()-top-5)/rows
            for i,panel in enumerate(self.panels):
                self._panel_index=i
                area = QRectF(10+(i%cols)*width, top+(i//cols)*height, width-7, height-7)
                self._panel(q, area, panel)
            self.draw_selection(q)
        except (ValueError, TypeError, KeyError, IndexError, OverflowError, AttributeError) as exc:
            self.error = str(exc)
            q.fillRect(self.rect(), QColor('white'))
            self._text(q, QRectF(25, 30, self.width()-50, self.height()-60), 'Graph unavailable: '+self.error, color='#a32020')
        finally:
            q.end()
