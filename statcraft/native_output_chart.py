"""Display decoded native MPX chart snapshots without fitting or executing commands.

Every coordinate comes from the saved graph. Mesh interpolation only colours
the stored contour samples; it never evaluates a statistical model.
"""
import math
import copy
import re
from statistics import NormalDist
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QComboBox, QSizePolicy
from .graph_hover import point_info,histogram_info,surface_cell_info,summary_info,number
from .snapshot_chart import SnapshotChartWidget
from .plot_ticks import tick_values
from .spatial_view import DEFAULT_VIEW, project_point, view_state, camera_point
from .native_graph_view import resolve_view, graph_index
from .graph_styles import style_for
from .graph_interaction import style_pen,style_color,draw_marker


PALETTE = ('#d4e7ef', '#acd5df', '#7cbac4', '#4aa1a3', '#36937d', '#69aa63', '#a1c450', '#d4d94a', '#e8be43')
INK = '#232a30'


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _fmt(value):
    return '0' if value == 0 else format(value, '.5g')


def _range(values):
    values = [float(v) for v in values if _finite(v)]
    if not values: return (0., 1.)
    low, high = min(values), max(values)
    if low == high:
        delta = max(.5, abs(low) * .05)
        return low - delta, high + delta
    return low, high


def _clip_level(poly, level, above):
    if not poly: return []
    output = []; previous = poly[-1]
    before = previous[2] >= level if above else previous[2] <= level
    for current in poly:
        inside = current[2] >= level if above else current[2] <= level
        if inside != before:
            weight = (level - previous[2]) / (current[2] - previous[2])
            output.append((previous[0] + weight * (current[0] - previous[0]),
                           previous[1] + weight * (current[1] - previous[1]), level))
        if inside: output.append(current)
        previous, before = current, inside
    return output


def _color(value, fallback='#237bb3'):
    # Native RGBA is converted by the decoder; never interpret ARGB as RGBA.
    if isinstance(value,str) and re.fullmatch(r'#[0-9a-fA-F]{8}',value):return style_color(value)
    color = QColor(value) if isinstance(value, str) else QColor(fallback)
    return color if color.isValid() else QColor(fallback)





def _draw_mouse_reference_card(chart, p, ref_rect):
    p.save()
    p.setRenderHint(p.RenderHint.Antialiasing)

    # Card background plate
    p.setPen(QPen(QColor(203, 213, 225, 180), 0.9))
    p.setBrush(QColor(255, 255, 255, 240))
    p.drawRoundedRect(ref_rect, 7.0, 7.0)

    cx = ref_rect.center().x()
    top = ref_rect.top() + 6.0

    # Draw mini mouse vector icon
    mw = 18.0
    mh = 26.0
    mouse_rect = QRectF(cx - mw / 2.0, top, mw, mh)

    mouse_path = QPainterPath()
    mouse_path.addRoundedRect(mouse_rect, 8.0, 8.0)
    p.setPen(QPen(QColor('#64748b'), 1.0))
    p.setBrush(QColor('#f8fafc'))
    p.drawPath(mouse_path)

    # Highlight right button in blue (Right-drag: Orbit)
    clip_p = QPainterPath()
    clip_p.addRect(QRectF(cx, top, mw / 2.0, 11.0))
    r_btn = mouse_path.intersected(clip_p)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor('#2563eb'))
    p.drawPath(r_btn)

    # Divider lines
    btn_divider_y = top + 11.0
    p.setPen(QPen(QColor('#94a3b8'), 0.8))
    p.drawLine(QPointF(cx, top), QPointF(cx, btn_divider_y))
    p.drawLine(QPointF(cx - mw / 2.0, btn_divider_y), QPointF(cx + mw / 2.0, btn_divider_y))

    # Scroll wheel (cyan pill)
    wheel_w = 3.6
    wheel_h = 6.5
    wheel_rect = QRectF(cx - wheel_w / 2.0, top + 3.0, wheel_w, wheel_h)
    p.setPen(QPen(QColor('#0284c7'), 0.8))
    p.setBrush(QColor('#38bdf8'))
    p.drawRoundedRect(wheel_rect, 1.5, 1.5)

    # Mouse instructions
    p.setFont(QFont('Segoe UI', 6, QFont.Weight.DemiBold))
    ty = top + mh + 4.0
    line_h = 10.0
    items = [
        ('R-drag: Orbit', '#1d4ed8'),
        ('Mid: Pan', '#0284c7'),
        ('Wheel: Zoom', '#334155'),
        ('Dbl: Reset', '#64748b'),
    ]
    for text, col in items:
        p.setPen(QColor(col))
        p.drawText(QRectF(ref_rect.left() + 2, ty, ref_rect.width() - 4, line_h),
                   Qt.AlignmentFlag.AlignCenter, text)
        ty += line_h

    p.restore()


def _draw_mouse_tips_pill(chart, p, pill_rect):
    p.save()
    p.setRenderHint(p.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(203, 213, 225, 160), 0.8))
    p.setBrush(QColor(255, 255, 255, 200))
    p.drawRoundedRect(pill_rect, 4.0, 4.0)
    p.setFont(QFont('Segoe UI', 6, QFont.Weight.Medium))
    p.setPen(QColor('#475569'))
    p.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, '🖱 Mouse Tips')
    p.restore()


def handle_viewcube_action(chart, target):
    if not target or not target.startswith('viewcube_'):
        return False
    action = target.replace('viewcube_', '')
    if action in ('tips_card', 'tips_pill'):
        chart._cad_hint_visible = not getattr(chart, '_cad_hint_visible', False)
        chart.update()
        return True
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

    # Super quick reference card / button under the ViewCube
    is_hint_visible = getattr(chart, '_cad_hint_visible', True)
    tip_top = cube_box.bottom() + 6.0
    if is_hint_visible:
        tip_box = QRectF(cube_box.left(), tip_top, box_size, 82.0)
        _draw_mouse_reference_card(chart, p, tip_box)
        path_tips = QPainterPath()
        path_tips.addRoundedRect(tip_box, 7.0, 7.0)
        chart.hit_regions.append(('viewcube_tips_card', path_tips))
    else:
        pill_box = QRectF(cube_box.left(), tip_top, box_size, 16.0)
        _draw_mouse_tips_pill(chart, p, pill_box)
        path_pill = QPainterPath()
        path_pill.addRoundedRect(pill_box, 4.0, 4.0)
        chart.hit_regions.append(('viewcube_tips_pill', path_pill))
        if hasattr(chart, 'remember_hover'):
            chart.remember_hover(path_pill, {'text': 'Click or hover to view mouse CAD controls'})

    p.restore()



class NativeOutputChart(SnapshotChartWidget):
    """Saved geometry with independent, editable StatCraft appearance overlays."""
    graphSelected=Signal(int)
    cameraChanged=Signal(dict)
    def __init__(self, entry, parent=None, graph_index=None):
        super().__init__(entry, parent)
        self.result = self.entry.get('result', {})
        self.graphs = self.result.get('graphs', [])
        from .native_graph_view import graph_index as get_graph_index
        default_index = get_graph_index(self.entry)
        self.graph_index = graph_index if (isinstance(graph_index, int) and 0 <= graph_index < len(self.graphs)) else default_index
        self.surface_camera = dict(DEFAULT_VIEW)
        self._orbit_start = None
        self._rotate_start = None
        self._pan_start = None
        self._is_dragging = False
        self._viewcube_drag_start = None
        self._viewcube_target = None
        self._viewcube_moved = False
        self.active_cad_card = None
        self._last_cube_rect = None
        self._max_pt = None
        self._min_pt = None
        self._surface_vertices = []
        self.title = ''
        self.error = None
        self.graph_selector = QComboBox(self)
        self.graph_selector.setObjectName('nativeSavedGraphSelector')
        for graph in self.graphs:
            self.graph_selector.addItem(graph.get('title') or 'Saved graph')
        self.graph_selector.setToolTip('Choose a graph saved with this analysis')
        self.graph_selector.currentIndexChanged.connect(self.select_graph)
        self.graph_selector.setVisible(len(self.graphs) > 1)
        self.export_controls = [self.graph_selector]
        self.panels = self.graphs[self.graph_index].get('panels', []) if self.graphs else []
        self._loaded_camera_view=copy.deepcopy(self.current_view()['camera'])
        self.surface_camera=copy.deepcopy(self._loaded_camera_view)
        self._cad_hint_visible = True
        from PySide6.QtCore import QTimer
        QTimer.singleShot(4500, self._auto_hide_cad_hint)
        self.graph_selector.blockSignals(True)
        self.graph_selector.setCurrentIndex(self.graph_index)
        self.graph_selector.blockSignals(False)
        self.setMinimumSize(660, 470)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFont(QFont('Segoe UI', 9))
        self._contour_cache = {}
        self.rendered_primitives = 0

    def sizeHint(self):
        return QSize(950, 690 if len(self.panels) > 1 else 570)

    def minimumSizeHint(self):
        return QSize(660, 470)

    def resizeEvent(self, event):
        self.graph_selector.setGeometry(10, 4, max(220, min(650, self.width() - 20)), 28)
        super().resizeEvent(event)

    def select_graph(self, index):
        if not 0 <= index < len(self.graphs): return
        changed=index!=self.graph_index
        self.clear_hover()
        self.selected_object=None;self.hit_regions=[]
        self.graph_index = index
        self.panels = self.graphs[index].get('panels', [])
        if self.graph_selector.currentIndex() != index:
            self.graph_selector.setCurrentIndex(index)
        self._loaded_camera_view=copy.deepcopy(self.current_view()['camera']);self.surface_camera=copy.deepcopy(self._loaded_camera_view)
        if changed:self.graphSelected.emit(index)
        self.update()

    def current_view(self):
        return resolve_view(self.entry,self.graph_index)

    def current_styles(self):
        return self.current_view()['styles']

    def _style(self,name,**defaults):
        return style_for(self.current_styles(),self._target(name),defaults)

    def _palette(self,panel=None):
        return self.current_view()['palette'] or (panel or {}).get('colors') or list(PALETTE)

    def _axis_label(self,panel,axis):
        first=(self.graphs[self.graph_index].get('panels') or [{}])[0]
        key=(('y' if axis=='x' else 'x') if panel.get('horizontal') else axis)+'_label'
        first_key=(('y' if axis=='x' else 'x') if first.get('horizontal') else axis)+'_label'
        value=self.current_view()['presentation'][axis+'_label']
        return panel.get(key,'') if value==str(first.get(first_key,'') or '')[:145] else value

    def _text(self, painter, rect, text, alignment=Qt.AlignmentFlag.AlignCenter):
        painter.setPen(QColor(INK))
        painter.drawText(rect, alignment | Qt.TextFlag.TextWordWrap, str(text))

    def paintEvent(self, event):
        self.reset_hover_regions()
        self.hit_regions=[];self._panel_index=0
        camera=self.current_view()['camera']
        if camera!=self._loaded_camera_view:self._loaded_camera_view=copy.deepcopy(camera);self.surface_camera=copy.deepcopy(camera)
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillRect(self.rect(), QColor('white'))
            self.rendered_primitives = 0
            if not self.graphs:
                self._text(painter, QRectF(self.rect()), 'No supported saved chart geometry.')
                return
            graph = self.graphs[self.graph_index]
            top = 38 if len(self.graphs) > 1 and not getattr(self, '_exporting', False) else 5
            presentation=self.current_view()['presentation']
            managed=getattr(self,'_frame_managed',False)
            if not managed:
                if presentation['title_enabled']:
                    painter.setFont(QFont('Segoe UI', 12, QFont.Weight.DemiBold))
                    self._text(painter,QRectF(12,top,self.width()-24,34),presentation['title']);top+=36
                if presentation['subtitle_enabled']:
                    painter.setFont(QFont('Segoe UI',10));self._text(painter,QRectF(12,top,self.width()-24,26),presentation['subtitle']);top+=28
            bottom=26 if not managed and presentation['footnote_enabled'] else 0
            if bottom:self._text(painter,QRectF(12,self.height()-25,self.width()-24,24),presentation['footnote'])
            panels = graph.get('panels', [])
            if not panels:
                self._text(painter, QRectF(12, top + 42, self.width() - 24, 80), 'This saved chart does not contain supported drawing data.')
                return
            columns = min(len(panels), max(1, int(graph.get('columns', 2 if len(panels) > 1 else 1))))
            rows = math.ceil(len(panels) / columns)
            available = QRectF(4, top + 6, self.width() - 8, self.height() - top - 11-bottom)
            painter.setFont(QFont('Segoe UI', 9))
            for i, panel in enumerate(panels):
                self._panel_index=i
                area = QRectF(available.left() + (i % columns) * available.width() / columns,
                              available.top() + (i // columns) * available.height() / rows,
                              available.width() / columns, available.height() / rows)
                if panel.get('kind') == 'surface': self._surface(painter, area, panel)
                else: self._panel(painter, area, panel, i)
            self.draw_selection(painter)
            self.error = None
        except (ValueError, TypeError, KeyError, IndexError, OverflowError, ZeroDivisionError) as exc:
            self.error = str(exc)
            painter.setPen(QColor('#9f3131'))
            painter.drawText(QRectF(20, 60, self.width()-40, self.height()-80), Qt.TextFlag.TextWordWrap,
                             'The saved chart cannot be drawn: ' + str(exc))
        finally:
            painter.end()

    def _bounds(self, panel):
        limits=self._raw_bounds(panel);presentation=self.current_view()['presentation']
        out=list(limits)
        for offset,axis in ((0,'x'),(2,'y')):
            if presentation[axis+'_min'] is not None:out[offset:offset+2]=[presentation[axis+'_min'],presentation[axis+'_max']]
        return tuple(out)

    def _raw_bounds(self, panel):
        bounds = panel.get('bounds')
        if isinstance(bounds, (list, tuple)) and len(bounds) == 4 and all(_finite(v) for v in bounds) and bounds[1] > bounds[0] and bounds[3] > bounds[2]:
            return tuple(bounds)
        grid = panel.get('grid', {})
        xs = list(grid.get('x', [])); ys = list(grid.get('y', []))
        for series in panel.get('series', []):
            xs.extend(series.get('x', [])); ys.extend(series.get('y', []))
        for poly in panel.get('polygons', []):
            xs.extend(poly.get('x', [])); ys.extend(poly.get('y', []))
        return (*_range(xs), *_range(ys))

    def _axes(self, p, area, panel):
        title = panel.get('title', '')
        if title:
            p.setFont(QFont('Segoe UI', 10, QFont.Weight.DemiBold))
            self._text(p, QRectF(area.left()+10, area.top(), area.width()-20, 24), title)
        p.setFont(QFont('Segoe UI', 9))
        legend_width = 105 if panel.get('kind') == 'contour' else 12
        plot = QRectF(area.left()+67, area.top()+31, max(30, area.width()-82-legend_width), max(30, area.height()-99))
        xmin, xmax, ymin, ymax = self._bounds(panel)
        tx = lambda v: plot.left() + (v-xmin)/(xmax-xmin)*plot.width()
        ty = lambda v: plot.bottom() - (v-ymin)/(ymax-ymin)*plot.height()
        p.fillRect(plot, QColor('#fafafa'))
        presentation=self.current_view()['presentation']
        grid_style=self._style('grid',color='#e3e3e3',line_width=.7,line_style='solid',visible=True,opacity=1.)
        axis_style=self._style('axis',color='#6b6b6b',line_width=.9,line_style='solid',visible=True,opacity=1.)
        show_grid=presentation['grid_enabled'] and grid_style.get('visible',True)
        category_series = next((s for s in panel.get('series', []) if s.get('categories')), {})
        categories = category_series.get('categories')
        horizontal = panel.get('horizontal', False)
        positions = category_series.get('x', list(range(1, len(categories or []) + 1)))
        category_labels = dict(zip(positions, categories or []))
        xticks = positions if categories and not horizontal else (panel.get('x_ticks') if presentation['x_min'] is None else None) or tick_values(xmin,xmax,count=5)
        if panel.get('kind') == 'probability':
            yticks = [(NormalDist().inv_cdf(v/100), f'{v:g}') for v in (.1, 1, 5, 10, 30, 50, 70, 90, 95, 99, 99.9) if ymin <= NormalDist().inv_cdf(v/100) <= ymax]
        elif horizontal and categories:
            yticks = list(zip(positions, categories))
        else:
            yticks = [(v, _fmt(v)) for v in ((panel.get('y_ticks') if presentation['y_min'] is None else None) or tick_values(ymin,ymax,count=5)) if _finite(v)]
        for v in xticks:
            if not _finite(v) or not xmin <= v <= xmax: continue
            x = tx(v)
            if show_grid:p.setPen(style_pen(grid_style));p.drawLine(QPointF(x,plot.top()),QPointF(x,plot.bottom()))
            tick_text = str(category_labels[v]) if categories and not horizontal and v in category_labels else _fmt(v)
            self._text(p, QRectF(x-38, plot.bottom()+5, 76, 20), tick_text)
        for v, label in yticks:
            if not ymin <= v <= ymax: continue
            y = ty(v)
            if show_grid:p.setPen(style_pen(grid_style));p.drawLine(QPointF(plot.left(),y),QPointF(plot.right(),y))
            self._text(p, QRectF(plot.left()-57, y-9, 50, 18), label, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if axis_style.get('visible',True):p.setPen(style_pen(axis_style));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRect(plot)
        if presentation['x_position']!='off':self._text(p,QRectF(plot.left(),plot.top()-28 if presentation['x_position']=='high' else plot.bottom()+28,plot.width(),26),self._axis_label(panel,'x'))
        if presentation['y_position']!='off':
            p.save();p.translate(area.right()-6 if presentation['y_position']=='high' else area.left()+15,plot.center().y());p.rotate(-90)
            self._text(p,QRectF(-plot.height()/2,-13,plot.height(),26),self._axis_label(panel,'y'));p.restore()
        self.remember_axes(plot)
        return plot, tx, ty

    def _panel(self, p, area, panel, panel_index):
        plot, tx, ty = self._axes(p, area, panel)
        point = lambda x,y: QPointF(tx(x), ty(y))
        p.save();p.setClipRect(plot)
        if panel.get('kind') == 'contour': self._contour(p, plot, panel, point, panel_index)
        for series_index,series in enumerate(panel.get('series', [])):
            name='s'+str(series_index)
            x, y = series.get('x', []), series.get('y', [])
            pairs = [(a,b) for a,b in zip(x,y) if _finite(a) and _finite(b)]
            kind = series.get('kind', panel.get('kind', 'scatter'))
            default_color=self._palette(panel)[series_index%len(self._palette(panel))] if self.current_view()['palette'] else series.get('color','#237bb3')
            style=self._style(name,color=default_color,fill=default_color,edge=default_color,line_width=float(series.get('width',1.3)),line_style='solid',opacity=1.,visible=True,marker='none' if kind in ('line','connected','probability_fit','contour_line') else 'circle',marker_size=5.6,legend_visible=True)
            overrides=self.current_styles().get(self._target(name),{})
            if 'color' in overrides:
                if 'fill' not in overrides:style['fill']=style['color']
                if 'edge' not in overrides:style['edge']=style['color']
            if not style.get('visible',True):continue
            color=style_color(style['color'],style.get('opacity',1.))
            p.setPen(style_pen(style))
            if kind in ('line', 'connected', 'probability_fit', 'contour_line'):
                path = QPainterPath(); active = False
                for a,b in zip(x,y):
                    if not (_finite(a) and _finite(b)):active=False;continue
                    if active:path.lineTo(point(a,b))
                    else:path.moveTo(point(a,b));active=True
                p.drawPath(path);self.rendered_primitives += max(0, len(pairs)-1)
                self.remember_path(name,[point(a,b) for a,b in pairs])
                for a,b in pairs:
                    if plot.contains(point(a,b)):draw_marker(p,point(a,b),style)
                if kind in ('line','connected'):
                    for a,b in pairs:self.remember_point_hover(point(a,b),point_info(a,b,panel.get('x_label','X'),panel.get('y_label','Y'),series.get('label','')),clip=plot)
            elif kind in ('bar', 'histogram'):
                width = series.get('bar_width')
                if not _finite(width):
                    positions=sorted(set(a for a,b in pairs));width=min((b-a for a,b in zip(positions,positions[1:])),default=1.)*.9
                base = series.get('baseline', 0.)
                p.setBrush(style_color(style.get('fill',style['color']),style.get('opacity',1.)));p.setPen(style_pen(dict(style,color=style.get('edge',style['color']))))
                edges = series.get('edges', [])
                exact_edges = len(edges) == len(pairs) + 1 and all(_finite(v) for v in edges)
                for index,(a,b) in enumerate(pairs):
                    left,right = (edges[index],edges[index+1]) if exact_edges else (a-width/2,a+width/2)
                    if panel.get('horizontal'):
                        rect=QRectF(point(base,left),point(b,right)).normalized();p.drawRect(rect)
                    else:
                        rect=QRectF(point(left, base), point(right,b)).normalized();p.drawRect(rect)
                    if kind=='histogram':
                        info=histogram_info(left,right,b,panel.get('y_label','Frequency'),series.get('label',''),last=index==len(pairs)-1)
                    else:
                        categories=series.get('categories',[])
                        category=categories[index] if index<len(categories) else a
                        info=point_info(category,b,panel.get('x_label','Category'),panel.get('y_label','Value'),series.get('label',''))
                        info['kind']='bar'
                    self.remember_hover(rect,info,plot)
                    clipped=rect.intersected(plot)
                    if not clipped.isEmpty():self.remember_rect(name,clipped)
                    self.rendered_primitives += 1
            else:
                for a,b in pairs:
                    draw_marker(p,point(a,b),style);self.rendered_primitives += 1
                    if plot.contains(point(a,b)):self.remember_marker(name,point(a,b),style.get('marker_size',5.6))
                    shown_y=100*NormalDist().cdf(b) if panel.get('kind')=='probability' else b
                    self.remember_point_hover(point(a,b),point_info(a,shown_y,panel.get('x_label','X'),panel.get('y_label','Y'),series.get('label','')),clip=plot)
        xmin, xmax, ymin, ymax = self._bounds(panel)
        for ref in panel.get('ref_lines', []):
            pos = ref.get('pos')
            if not _finite(pos): continue
            axis = ref.get('axis', 'x')
            color = QColor(ref.get('color', '#ce0000'))
            pen_style = Qt.PenStyle.DashLine if ref.get('style') == 'dash' else Qt.PenStyle.SolidLine
            pen = QPen(color, 1.3, pen_style)
            p.setPen(pen)
            if axis == 'x' and xmin <= pos <= xmax:
                p.drawLine(QPointF(tx(pos), plot.top()), QPointF(tx(pos), plot.bottom()))
            elif axis == 'y' and ymin <= pos <= ymax:
                p.drawLine(QPointF(plot.left(), ty(pos)), QPointF(plot.right(), ty(pos)))
        p.restore()
        for ref in panel.get('ref_lines', []):
            pos = ref.get('pos')
            if not _finite(pos): continue
            axis = ref.get('axis', 'x')
            lbl = str(ref.get('label', '')).strip()
            if not lbl: continue
            color = QColor(ref.get('color', '#ce0000'))
            p.save()
            p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
            p.setPen(color)
            if axis == 'x' and xmin <= pos <= xmax:
                x = tx(pos)
                self._text(p, QRectF(x - 35, plot.top() - 17, 70, 15), lbl, Qt.AlignmentFlag.AlignCenter)
            elif axis == 'y' and ymin <= pos <= ymax:
                y = ty(pos)
                self._text(p, QRectF(plot.right() - 65, y - 15, 60, 14), lbl, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            p.restore()
        if panel.get('kind') == 'contour': self._legend(p, area, plot, panel)
        else:
            labelled = [(j,s) for j,s in enumerate(panel.get('series',[])) if s.get('label') and self._style('s'+str(j),visible=True,legend_visible=True).get('visible',True) and self._style('s'+str(j),visible=True,legend_visible=True).get('legend_visible',True)]
            for i,(j,series) in enumerate(labelled[:8]):
                y=plot.top()+8+i*20;right=plot.right()-8
                default=self._palette(panel)[j%len(self._palette(panel))] if self.current_view()['palette'] else series.get('color','#237bb3')
                p.setPen(style_pen(self._style('s'+str(j),color=default,line_width=1.5,line_style='solid',opacity=1.)));p.drawLine(QPointF(right-135,y+8),QPointF(right-110,y+8))
                self._text(p,QRectF(right-105,y,105,18),str(series['label']),Qt.AlignmentFlag.AlignLeft)

    def _contour(self, p, plot, panel, point, panel_index):
        polygons = panel.get('polygons', [])
        if polygons:
            p.setPen(Qt.PenStyle.NoPen);p.setRenderHint(QPainter.RenderHint.Antialiasing,False)
            for poly in polygons:
                xy=[(a,b) for a,b in zip(poly.get('x', []),poly.get('y', [])) if _finite(a) and _finite(b)]
                if len(xy) >= 3:
                    colors=panel.get('colors',[]);band=colors.index(poly.get('color')) if poly.get('color') in colors else 0
                    palette=self._palette(panel);paint_color=palette[round(band*(len(palette)-1)/max(1,len(panel.get('levels',[]))))] if self.current_view()['palette'] else poly.get('color',PALETTE[3])
                    p.setBrush(_color(paint_color));p.drawPolygon(QPolygonF([point(a,b) for a,b in xy]));self.rendered_primitives += 1
                    colors=panel.get('colors',[]);levels=panel.get('levels',[])
                    if levels and poly.get('color') in colors:
                        band=colors.index(poly['color']);self._remember_contour_band([point(a,b) for a,b in xy],levels,band,panel,plot)
            p.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        else:
            key=(self.graph_index, panel_index)
            if key not in self._contour_cache:
                grid=panel.get('grid', {});xs=grid.get('x', []);ys=grid.get('y', []);zs=grid.get('z', [])
                levels=[v for v in panel.get('levels', []) if _finite(v)]
                if not levels:
                    lo,hi=_range([v for row in zs for v in row]);levels=[lo+(hi-lo)*i/8 for i in range(1,8)]
                output=[]
                for j in range(min(len(ys)-1,len(zs)-1)):
                    for i in range(min(len(xs)-1,len(zs[j])-1,len(zs[j+1])-1)):
                        cell=[(xs[i],ys[j],zs[j][i]),(xs[i+1],ys[j],zs[j][i+1]),(xs[i+1],ys[j+1],zs[j+1][i+1]),(xs[i],ys[j+1],zs[j+1][i])]
                        if not all(_finite(v) for row in cell for v in row):continue
                        for tri in ((cell[0],cell[1],cell[2]),(cell[0],cell[2],cell[3])):
                            for band in range(len(levels)+1):
                                poly=list(tri)
                                if band:poly=_clip_level(poly,levels[band-1],True)
                                if band<len(levels):poly=_clip_level(poly,levels[band],False)
                                if len(poly)>2:output.append((band,[(v[0],v[1]) for v in poly]))
                self._contour_cache[key]=(levels,output)
            levels,polys=self._contour_cache[key]
            p.setPen(Qt.PenStyle.NoPen);p.setRenderHint(QPainter.RenderHint.Antialiasing,False)
            for band,poly in polys:
                p.setBrush(_color(self._palette(panel)[round(band*(len(self._palette(panel))-1)/max(1,len(levels)))]));p.drawPolygon(QPolygonF([point(a,b) for a,b in poly]));self.rendered_primitives += 1
                self._remember_contour_band([point(a,b) for a,b in poly],levels,band,panel,plot)
            p.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        contour_style=self._style('ref0',color='#576a65',line_width=.6,line_style='solid',visible=True,opacity=1.)
        p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(style_pen(contour_style))
        for line in panel.get('contour_lines', []):
            pairs=[point(a,b) for a,b in zip(line.get('x', []),line.get('y', [])) if _finite(a) and _finite(b)]
            if len(pairs)>1 and contour_style.get('visible',True):
                p.drawPolyline(QPolygonF(pairs));self.rendered_primitives += len(pairs)-1;self.remember_path('ref0',pairs)

    def _remember_contour_band(self,points,levels,band,panel,plot):
        if not levels:return
        band=min(band,len(levels))
        low=levels[band-1] if band else None;high=levels[band] if band<len(levels) else None
        value=('< '+number(high)) if low is None else ('≥ '+number(low)) if high is None else number(low)+' to '+number(high)
        path=QPainterPath();path.addPolygon(QPolygonF(points));path.closeSubpath()
        self.remember_hover(path,summary_info('contour',[(panel.get('z_label') or 'Response',value)],level_range=(low,high)),plot)

    def _legend(self,p,area,plot,panel):
        levels=panel.get('levels', [])
        if not levels:
            cached=self._contour_cache.get((self.graph_index,self.graphs[self.graph_index].get('panels', []).index(panel)))
            levels=cached[0] if cached else []
        if not levels:return
        left=plot.right()+16;top=plot.top()+8
        self._text(p,QRectF(left,top-23,90,20),panel.get('z_label','Response'),Qt.AlignmentFlag.AlignLeft)
        step=min(26.,max(14.,plot.height()/(len(levels)+1)))
        colors=self._palette(panel)
        for band in range(len(levels)+1):
            index=min(band,len(colors)-1) if panel.get('colors') and not self.current_view()['palette'] else round(band*(len(colors)-1)/max(1,len(levels)))
            p.fillRect(QRectF(left,top+band*step,15,15),_color(colors[index]))
            text='< '+_fmt(levels[0]) if band==0 else '≥ '+_fmt(levels[-1]) if band==len(levels) else _fmt(levels[band-1])+' – '+_fmt(levels[band])
            self._text(p,QRectF(left+21,top+band*step-2,80,20),text,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

    def _surface(self, p, area, panel):
        grid = panel.get('grid', {})
        xs = grid.get('x', [])
        ys = grid.get('y', [])
        zs = grid.get('z', [])
        if len(xs) < 2 or len(ys) < 2 or len(zs) < 2:
            self._text(p, area, 'Saved surface mesh is unavailable.')
            return
        zr = _range([v for row in zs for v in row])
        ranges = (_range(xs), _range(ys), zr)
        viewport = (area.left() + 24, area.top() + 10, max(60, area.width() - 48), max(60, area.height() - 20))
        cube_rect = QRectF(*viewport)
        self._last_cube_rect = cube_rect

        # Find Peak (global max) and Trough (global min)
        max_r, max_c = 0, 0
        max_val = -float('inf')
        min_r, min_c = 0, 0
        min_val = float('inf')
        for j in range(len(ys)):
            for i in range(len(xs)):
                zv = float(zs[j][i])
                if zv > max_val:
                    max_val = zv; max_r, max_c = j, i
                if zv < min_val:
                    min_val = zv; min_r, min_c = j, i
        max_pt = (float(xs[max_c]), float(ys[max_r]), max_val)
        min_pt = (float(xs[min_c]), float(ys[min_r]), min_val)
        self._max_pt = max_pt
        self._min_pt = min_pt

        is_dragging = getattr(self, '_is_dragging', False)
        step = 2 if is_dragging else 1

        projected = lambda x, y, z: project_point((x, y, z), ranges, self.surface_camera, viewport)
        proj2d = lambda pt: QPointF(*projected(*pt)[:2])

        # Pre-project vertices once
        grid_proj = {}
        grid_qpt = {}
        surface_vertices = []
        for j in range(len(ys)):
            grid_proj[j] = {}
            grid_qpt[j] = {}
            for i in range(len(xs)):
                pt = (float(xs[i]), float(ys[j]), float(zs[j][i]))
                px, py, depth = projected(*pt)
                grid_proj[j][i] = (px, py, depth)
                qpos = QPointF(px, py)
                grid_qpt[j][i] = qpos
                if not is_dragging:
                    surface_vertices.append({'pt': pt, 'pos': qpos, 'depth': depth, 'r': j, 'c': i})
        if not is_dragging:
            self._surface_vertices = surface_vertices

        surface_style = self._style('bars', line_width=.65, line_style='solid', opacity=1., visible=True)
        palette = self._palette(panel)
        base = [(ranges[0][0], ranges[1][0], zr[0]), (ranges[0][1], ranges[1][0], zr[0]), (ranges[0][1], ranges[1][1], zr[0]), (ranges[0][0], ranges[1][1], zr[0])]
        p.setPen(QPen(QColor('#d0d0d0'), .7))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolygon(QPolygonF([proj2d(v) for v in base]))

        p.save()

        # Surface faces sorted by camera depth
        faces = []
        r_indices = list(range(0, len(ys), step))
        if r_indices[-1] != len(ys) - 1:
            r_indices.append(len(ys) - 1)
        c_indices = list(range(0, len(xs), step))
        if c_indices[-1] != len(xs) - 1:
            c_indices.append(len(xs) - 1)

        for i in range(len(r_indices) - 1):
            r0 = r_indices[i]; r1 = r_indices[i + 1]
            for j in range(len(c_indices) - 1):
                c0 = c_indices[j]; c1 = c_indices[j + 1]
                p0 = grid_proj[r0][c0]
                p1 = grid_proj[r0][c1]
                p2 = grid_proj[r1][c1]
                p3 = grid_proj[r1][c0]
                cam_depth = (p0[2] + p1[2] + p2[2] + p3[2]) * 0.25
                mean = (zs[r0][c0] + zs[r0][c1] + zs[r1][c1] + zs[r1][c0]) * 0.25
                t = max(0., min(1., (mean - zr[0]) / max(1e-12, zr[1] - zr[0])))
                color = _color(surface_style.get('fill', palette[round(t * (len(palette) - 1))]))
                color.setAlphaF(color.alphaF() * surface_style.get('opacity', 1.))
                quad_pts = [(xs[c0], ys[r0], zs[r0][c0]), (xs[c1], ys[r0], zs[r0][c1]), (xs[c1], ys[r1], zs[r1][c1]), (xs[c0], ys[r1], zs[r1][c0])]
                faces.append((cam_depth, [grid_qpt[r0][c0], grid_qpt[r0][c1], grid_qpt[r1][c1], grid_qpt[r1][c0]], color, mean, quad_pts))

        for depth, points, color, mean, quad_pts in sorted(faces, key=lambda v: v[0]):
            if not surface_style.get('visible', True): continue
            poly = QPolygonF(points)
            if is_dragging:
                p.setBrush(QColor(color.red(), color.green(), color.blue(), 190))
                p.setPen(QPen(QColor('#4d6473'), 0.5))
            else:
                edge = surface_style.get('edge', color.darker(125).name())
                p.setPen(style_pen(dict(surface_style, color=edge)))
                p.setBrush(color)
            p.drawPolygon(poly)
            self.rendered_primitives += 1
            if not is_dragging:
                poly_path = QPainterPath()
                poly_path.addPolygon(poly)
                labels = (panel.get('x_label', 'X'), panel.get('y_label', 'Y'), panel.get('z_label', 'Z'))
                self.remember_hover(poly_path, surface_cell_info(quad_pts, labels=labels), clip=cube_rect)

        p.restore()

        if not is_dragging:
            # Subtle, elegant surface markers at Peak Maximum and Trough Minimum
            pos_max = proj2d(max_pt)
            pos_min = proj2d(min_pt)

            # 1. Peak Marker (tasteful glowing ruby dot)
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
            self.hit_regions.append(('cad_peak_3d', path_max))
            self.remember_hover(path_max, {'text': f"▲ Peak Maximum: {_fmt(max_val)}\n{panel.get('x_label','X')}: {_fmt(max_pt[0])}\n{panel.get('y_label','Y')}: {_fmt(max_pt[1])}"})

            # 2. Trough Marker (tasteful glowing cerulean dot)
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
            self.hit_regions.append(('cad_min_3d', path_min))
            self.remember_hover(path_min, {'text': f"▼ Trough Minimum: {_fmt(min_val)}\n{panel.get('x_label','X')}: {_fmt(min_pt[0])}\n{panel.get('y_label','Y')}: {_fmt(min_pt[1])}"})

        # Active Inspection Callout Card (drawn ONLY when user clicks a point/peak)
        active_card = getattr(self, 'active_cad_card', None)
        if not is_dragging and active_card and active_card.get('mode') in ('surface', 'peak_3d', 'min_3d', 'probe_3d'):
            mode = active_card.get('mode')
            fit_val = max_val if mode == 'peak_3d' else min_val if mode == 'min_3d' else active_card.get('fit', 0.0)
            px_val = max_pt[0] if mode == 'peak_3d' else min_pt[0] if mode == 'min_3d' else active_card.get('x', 0.0)
            py_val = max_pt[1] if mode == 'peak_3d' else min_pt[1] if mode == 'min_3d' else active_card.get('y', 0.0)
            pt_3d = (px_val, py_val, fit_val)

            # Drop stem from active probed point down to floor
            stem_bottom = proj2d((px_val, py_val, zr[0]))
            stem_top = proj2d(pt_3d)
            p.save()
            p.setPen(QPen(QColor('#64748b'), 1.0, Qt.PenStyle.DashLine))
            p.drawLine(stem_bottom, stem_top)

            # Compact, elegant floating inspection chip near top-left
            card_w = 175.0
            card_h = 56.0
            card_rect = QRectF(cube_rect.left() + 8.0, cube_rect.top() + 6.0, card_w, card_h)

            p.setPen(QPen(QColor('#cbd5e1'), 0.8))
            p.setBrush(QColor(255, 255, 255, 240))
            p.drawRoundedRect(card_rect, 6.0, 6.0)

            hdr_title = "▲ Peak Maximum" if mode == 'peak_3d' else "▼ Trough Minimum" if mode == 'min_3d' else "✦ Surface Probed Point"
            hdr_color = QColor('#e11d48') if mode == 'peak_3d' else QColor('#0284c7') if mode == 'min_3d' else QColor('#1e293b')
            p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
            p.setPen(hdr_color)
            p.drawText(QRectF(card_rect.left() + 8, card_rect.top() + 5, card_rect.width() - 16, 16),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, hdr_title)

            p.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
            p.setPen(QColor('#0f172a'))
            p.drawText(QRectF(card_rect.left() + 8, card_rect.top() + 21, card_rect.width() - 16, 18),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{panel.get('z_label','Z')}: {_fmt(fit_val)}")

            p.setFont(QFont('Segoe UI', 7))
            p.setPen(QColor('#64748b'))
            p.drawText(QRectF(card_rect.left() + 8, card_rect.top() + 38, card_rect.width() - 16, 14),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       f"{panel.get('x_label','X')}: {_fmt(px_val)}   {panel.get('y_label','Y')}: {_fmt(py_val)}")
            p.restore()

        # Draw ViewCube in top-right
        _draw_viewcube(self, p, cube_rect)

        # Draw Robust 3D Reference Frame & Non-Distorting Outward Axes
        axis_style = self._style('axis', color='#5e5e5e', line_width=1., line_style='solid', opacity=1., visible=True)
        if axis_style.get('visible', True):
            p.save()
            p.setFont(QFont('Segoe UI', 8))
            
            # Floor wireframe polygon
            c00 = (ranges[0][0], ranges[1][0], zr[0])
            c10 = (ranges[0][1], ranges[1][0], zr[0])
            c11 = (ranges[0][1], ranges[1][1], zr[0])
            c01 = (ranges[0][0], ranges[1][1], zr[0])
            floor_pts = [c00, c10, c11, c01]
            floor_qpts = [proj2d(pt) for pt in floor_pts]
            
            p.setPen(QPen(QColor('#cbd5e1'), 0.9))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPolygon(QPolygonF(floor_qpts))

            # Center of bounding box in 2D
            mid_3d = ((ranges[0][0] + ranges[0][1]) * 0.5, (ranges[1][0] + ranges[1][1]) * 0.5, (zr[0] + zr[1]) * 0.5)
            c2d = proj2d(mid_3d)

            # Leftmost floor corner for vertical Z axis
            corners_info = [(pt, proj2d(pt)) for pt in floor_pts]
            corners_info.sort(key=lambda item: item[1].x())
            leftmost_3d, leftmost_2d = corners_info[0]

            # 1. Vertical Z Axis along the leftmost post (never intersects or hides)
            z_top_3d = (leftmost_3d[0], leftmost_3d[1], zr[1])
            z_top_2d = proj2d(z_top_3d)
            p.setPen(QPen(QColor('#475569'), 1.2))
            p.drawLine(leftmost_2d, z_top_2d)

            for zv in tick_values(zr[0], zr[1], count=4):
                zq = proj2d((leftmost_3d[0], leftmost_3d[1], zv))
                p.drawLine(zq, QPointF(zq.x() - 5.0, zq.y()))
                p.drawText(QRectF(zq.x() - 42.0, zq.y() - 8.0, 36.0, 16.0),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, _fmt(zv))

            z_label = panel.get('z_label', 'Z')
            p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
            p.drawText(QRectF(z_top_2d.x() - 50.0, z_top_2d.y() - 20.0, 60.0, 18.0),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, z_label)

            # 2. X and Y Floor Axes along the frontmost floor edges
            # Sort edges by average depth to pick frontmost edges
            p.setFont(QFont('Segoe UI', 8))
            edges_x = [(c00, c10), (c01, c11)]
            edges_y = [(c00, c01), (c10, c11)]

            front_x = max(edges_x, key=lambda e: (projected(*e[0])[2] + projected(*e[1])[2]))
            front_y = max(edges_y, key=lambda e: (projected(*e[0])[2] + projected(*e[1])[2]))

            def _draw_floor_axis(pt_a, pt_b, val_lo, val_hi, label_text):
                pa = proj2d(pt_a)
                pb = proj2d(pt_b)
                p.setPen(QPen(QColor('#475569'), 1.2))
                p.drawLine(pa, pb)

                dx = pb.x() - pa.x()
                dy = pb.y() - pa.y()
                len_axis = math.hypot(dx, dy)
                if len_axis < 1e-3: return

                # Perpendicular normal pointing away from c2d
                ux = dx / len_axis; uy = dy / len_axis
                nx = -uy; ny = ux
                mx = (pa.x() + pb.x()) * 0.5; my = (pa.y() + pb.y()) * 0.5
                if nx * (c2d.x() - mx) + ny * (c2d.y() - my) > 0:
                    nx = -nx; ny = -ny

                for val in tick_values(val_lo, val_hi, count=4):
                    frac = (val - val_lo) / max(1e-12, val_hi - val_lo)
                    qx = pa.x() + frac * dx; qy = pa.y() + frac * dy
                    p.drawLine(QPointF(qx, qy), QPointF(qx + nx * 5.0, qy + ny * 5.0))
                    lbl_c = QPointF(qx + nx * 14.0, qy + ny * 14.0)
                    p.drawText(QRectF(lbl_c.x() - 25.0, lbl_c.y() - 8.0, 50.0, 16.0),
                               Qt.AlignmentFlag.AlignCenter, _fmt(val))

                lbl_title = QPointF(mx + nx * 28.0, my + ny * 28.0)
                p.save()
                p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
                p.drawText(QRectF(lbl_title.x() - 65.0, lbl_title.y() - 10.0, 130.0, 20.0),
                           Qt.AlignmentFlag.AlignCenter, label_text)
                p.restore()

            x_label = self._axis_label(panel, 'x')
            y_label = self._axis_label(panel, 'y')
            _draw_floor_axis(front_x[0], front_x[1], ranges[0][0], ranges[0][1], x_label)
            _draw_floor_axis(front_y[0], front_y[1], ranges[1][0], ranges[1][1], y_label)

            p.restore()
        if panel.get('title'):
            self._text(p, QRectF(area.left() + 10, area.top(), area.width() - 20, 24), panel['title'])
        self.setToolTip('Right-drag: Orbit • Middle-drag: Pan • Scroll: Zoom • Click point: Inspect • Double-click: Reset')

    def editable_objects(self):
        objects = []
        panels = self.graphs[self.graph_index].get('panels', []) if self.graphs else []
        line = ('color', 'line_width', 'line_style', 'opacity', 'visible')
        marker = ('color', 'fill', 'edge', 'marker', 'marker_size', 'opacity', 'visible')
        for i, panel in enumerate(panels):
            prefix = ('Panel ' + str(i + 1) + ' — ') if len(panels) > 1 else ''
            def add(name, label, caps, defaults): objects.append({'target': 'p' + str(i) + ':' + name, 'label': prefix + label, 'capabilities': caps, 'defaults': defaults})
            add('axis', 'Axis border', line, {'color': '#6b6b6b', 'line_width': .9, 'line_style': 'solid', 'visible': True, 'opacity': 1.})
            if panel.get('kind') != 'surface':
                add('grid', 'Grid lines', line, {'color': '#e3e3e3', 'line_width': .7, 'line_style': 'solid', 'visible': True, 'opacity': 1.})
            for j, series in enumerate(panel.get('series', [])):
                kind = series.get('kind', panel.get('kind', 'scatter'))
                color = series.get('color', '#237bb3')
                caps = ('fill', 'edge', 'line_width', 'line_style', 'opacity', 'visible', 'legend_visible') if kind in ('bar', 'histogram') else tuple(set(line + marker + ('legend_visible',))) if kind in ('line', 'connected') else line + ('legend_visible',) if kind in ('probability_fit', 'contour_line') else marker + ('legend_visible',)
                defaults = {'color': color, 'fill': color, 'edge': color, 'line_width': float(series.get('width', 1.3)), 'line_style': 'solid', 'opacity': 1., 'visible': True, 'marker': 'none' if kind in ('line', 'connected', 'probability_fit', 'contour_line') else 'circle', 'marker_size': 5.6, 'legend_visible': True}
                add('s' + str(j), str(series.get('label') or ('Bars' if kind in ('bar', 'histogram') else 'Series ' + str(j + 1))), caps, defaults)
            if panel.get('kind') == 'contour':
                add('ref0', 'Contour lines', line, {'color': '#576a65', 'line_width': .6, 'line_style': 'solid', 'visible': True, 'opacity': 1.})
            if panel.get('kind') == 'surface':
                add('bars', 'Surface fill and mesh', ('fill', 'edge', 'line_width', 'line_style', 'opacity', 'visible'), {'line_width': .65, 'line_style': 'solid', 'opacity': 1., 'visible': True})
        return objects

    def _has_3d_panel(self):
        if not self.graphs or not (0 <= self.graph_index < len(self.graphs)):
            return False
        active_panels = self.graphs[self.graph_index].get('panels', [])
        return any(isinstance(p, dict) and p.get('kind') == 'surface' for p in active_panels)

    def rotate_cad_view(self, dx, dy):
        curr = self.surface_camera
        px = curr.get('pan_x', 0.0)
        py = curr.get('pan_y', 0.0)
        self.surface_camera = view_state(
            curr['azimuth'] + dx,
            curr['elevation'] + dy,
            curr['zoom'],
            pan_x=px,
            pan_y=py,
        )
        self.update()

    def pan_cad_view(self, dx, dy):
        curr = self.surface_camera
        px = curr.get('pan_x', 0.0) + dx
        py = curr.get('pan_y', 0.0) + dy
        self.surface_camera = view_state(
            curr['azimuth'],
            curr['elevation'],
            curr['zoom'],
            pan_x=px,
            pan_y=py,
        )
        self.update()

    def zoom_cad_view(self, steps):
        curr = self.surface_camera
        px = curr.get('pan_x', 0.0)
        py = curr.get('pan_y', 0.0)
        new_zoom = max(0.4, min(2.5, curr['zoom'] * math.exp(max(-20.0, min(20.0, steps)) * 0.12)))
        self.surface_camera = view_state(
            curr['azimuth'],
            curr['elevation'],
            new_zoom,
            pan_x=px,
            pan_y=py,
        )
        self.update()

    def set_cad_orientation(self, azimuth, elevation):
        curr = self.surface_camera
        self.surface_camera = view_state(
            azimuth,
            elevation,
            curr['zoom'],
            pan_x=curr.get('pan_x', 0.0),
            pan_y=curr.get('pan_y', 0.0),
        )
        self.cameraChanged.emit(copy.deepcopy(self.surface_camera))
        self.update()

    def reset_cad_view(self):
        self.surface_camera = dict(DEFAULT_VIEW)
        self.active_cad_card = None
        self.cameraChanged.emit(copy.deepcopy(self.surface_camera))
        self.update()

    def _probe_surface_click(self, pos):
        verts = getattr(self, '_surface_vertices', None)
        if verts:
            best_v = None
            best_dist = 42.0
            for v in verts:
                dist = math.hypot(v['pos'].x() - pos.x(), v['pos'].y() - pos.y())
                if dist < best_dist:
                    best_dist = dist
                    best_v = v
            if best_v is not None:
                pt = best_v['pt']
                self.active_cad_card = {
                    'mode': 'probe_3d',
                    'x': pt[0],
                    'y': pt[1],
                    'fit': pt[2],
                }
                self.update()
                return

    def mousePressEvent(self, event):
        self._hide_hover()
        pos = event.position()
        target = self.object_at(pos)

        if target and target.startswith('viewcube_'):
            self._viewcube_drag_start = pos
            self._viewcube_target = target
            self._viewcube_moved = False
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if target == 'cad_hud_reset_3d':
            self.reset_cad_view()
            event.accept()
            return
        elif target in ('cad_hud_peak_3d', 'cad_peak_3d'):
            self.active_cad_card = {'mode': 'peak_3d'}
            self.update()
            event.accept()
            return
        elif target in ('cad_hud_min_3d', 'cad_min_3d'):
            self.active_cad_card = {'mode': 'min_3d'}
            self.update()
            event.accept()
            return

        if self._has_3d_panel():
            # Standard CAD controls:
            # 1. Left-click: Probing / Extrema selection ONLY (left-click hold never moves the model)
            if event.button() == Qt.MouseButton.LeftButton:
                if target in ('viewcube_tips_card', 'viewcube_tips_pill'):
                    self._cad_hint_visible = not getattr(self, '_cad_hint_visible', True)
                    self.update()
                    event.accept()
                    return
                self._probe_surface_click(pos)
                event.accept()
                return

            # 2. Middle-click drag OR Ctrl + Right-click drag: Pan
            is_pan = (
                event.button() == Qt.MouseButton.MiddleButton
                or (event.button() == Qt.MouseButton.RightButton and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
            )
            if is_pan:
                self._pan_start = pos
                self._is_dragging = True
                self.setFocus(Qt.FocusReason.MouseFocusReason)
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                event.accept()
                return

            # 3. Orbit / Rotate: Right-click drag ONLY
            if event.button() == Qt.MouseButton.RightButton:
                self._orbit_start = pos
                self._rotate_start = pos
                self._is_dragging = True
                self.setFocus(Qt.FocusReason.MouseFocusReason)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        if getattr(self, '_viewcube_drag_start', None) is not None:
            dx = pos.x() - self._viewcube_drag_start.x()
            dy = pos.y() - self._viewcube_drag_start.y()
            if abs(dx) > 1.5 or abs(dy) > 1.5 or getattr(self, '_viewcube_moved', False):
                self._viewcube_moved = True
                self._viewcube_drag_start = pos
                self.rotate_cad_view(-dx * 0.65, dy * 0.65)
                event.accept()
                return
        if self._pan_start is not None:
            delta = pos - self._pan_start
            self._pan_start = pos
            self.pan_cad_view(delta.x(), delta.y())
            event.accept()
            return

        if self._orbit_start is not None or self._rotate_start is not None:
            start = self._orbit_start if self._orbit_start is not None else self._rotate_start
            delta = pos - start
            self._orbit_start = pos
            self._rotate_start = pos
            self.rotate_cad_view(-delta.x() * 0.5, delta.y() * 0.5)
            event.accept()
            return

        # Proximity check for quick reference mouse tips near ViewCube
        if self._has_3d_panel():
            is_near = (pos.x() >= self.width() - 110 and pos.y() <= 200)
            if is_near != getattr(self, '_cad_hint_visible', False):
                self._cad_hint_visible = is_near
                self.update()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        pos = event.position()
        if getattr(self, '_viewcube_drag_start', None) is not None:
            target = self._viewcube_target
            moved = getattr(self, '_viewcube_moved', False)
            self._viewcube_drag_start = None
            self._viewcube_target = None
            self._viewcube_moved = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            if not moved and target:
                handle_viewcube_action(self, target)
            self.cameraChanged.emit(copy.deepcopy(self.surface_camera))
            self.update()
            event.accept()
            return
        if self._pan_start is not None:
            self._pan_start = None
            self._is_dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.cameraChanged.emit(copy.deepcopy(self.surface_camera))
            self.update()
            event.accept()
            return

        if self._orbit_start is not None or self._rotate_start is not None:
            self._orbit_start = None
            self._rotate_start = None
            self._is_dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.cameraChanged.emit(copy.deepcopy(self.surface_camera))
            self.update()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if self._has_3d_panel():
            steps = event.angleDelta().y() / 120.0
            if steps:
                self.zoom_cad_view(steps)
                self.cameraChanged.emit(copy.deepcopy(self.surface_camera))
                event.accept()
                return
        super().wheelEvent(event)

    def contextMenuEvent(self, event):
        if self._has_3d_panel():
            event.accept()
            return
        super().contextMenuEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._has_3d_panel():
            self.reset_cad_view()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
    def _auto_hide_cad_hint(self):
        self._cad_hint_visible = False
        self.update()
