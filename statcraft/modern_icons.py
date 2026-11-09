"""Original, multiresolution desktop icons; no external fonts or vendor assets.

Artwork uses a 24-unit drawing grid and is rasterized at several native sizes
so menu, toolbar and high-DPI displays all receive antialiased edges.
"""
from functools import lru_cache
from math import cos, sin, pi

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


ICON_KEYS = (
    'new_project', 'new_sheet', 'open', 'save', 'save_copy', 'print', 'export',
    'cut', 'copy', 'paste', 'undo', 'redo', 'delete', 'find', 'find_next', 'goto', 'calculator',
    'last_dialog', 'cancel', 'assign_formula', 'insert_cells', 'insert_rows',
    'insert_columns', 'delete_columns', 'move_columns', 'prev_brushed', 'next_brushed',
    'erase', 'stop', 'help', 'navigator', 'rerun', 'rotate', 'reset',
    'zoom', 'zoom_in', 'zoom_out', 'summary', 'worksheet', 'rename_sheet',
    'duplicate_sheet', 'delete_sheet', 'constants', 'matrices', 'normality',
    'correlation', 'regression', 'doe',
    'scatter', 'histogram', 'boxplot', 'graph_builder', 'scatter3d', 'surface3d',
    'bar_chart', 'pie_chart', 'heatmap', 'correlogram', 'matrix_plot', 'dotplot',
    'line_plot', 'time_series', 'probability', 'contour', 'interval', 'individual',
    'area', 'parallel', 'stem_leaf', 'ecdf', 'bubble', 'marginal', 'binned_scatter',
    'status_navigator', 'status_split', 'status_data_only', 'status_output_only',
    'status_command_line', 'sheet_menu',
    'delete_red_x', 'format_column', 'send_report', 'copy_graph',
    'make_similar_graph', 'edit_graph', 'panel_graph', 'brush_points', 'layout_tool',
    'chart', 'code_view', 'connect', 'covariance', 'graphical_summary',
    'multivari', 'outlier_test', 'report', 'run_chart', 'select_all',
    'standardize', 'subset', 'table', 'update', 'workflow',
    'sort', 'rank', 'capability', 'control_chart', 'symmetry', 'split', 'merge', 'transpose',
)
_ALIASES = {
    'new': 'new_project', 'save_as': 'save_copy', 'plot': 'scatter',
    '3d_scatterplot': 'scatter3d', '3d_scatter': 'scatter3d',
    '3d_surface': 'surface3d', 'bar': 'bar_chart', 'pie': 'pie_chart',
    'line': 'line_plot', 'time_series_plot': 'time_series',
    'individual_value': 'individual', 'parallel_coordinates': 'parallel',
    'probability_plot': 'probability', 'empirical_cdf': 'ecdf',
    'stem_and_leaf': 'stem_leaf', 'graph': 'graph_builder',
    'delete_worksheet': 'delete_sheet', 'duplicate_worksheet': 'duplicate_sheet',
    'rename_worksheet': 'rename_sheet', 'new_worksheet': 'new_sheet',
    'reset_view': 'reset', 'rotate_view': 'rotate',
    'findnext': 'find_next', 'clear': 'erase', 'eraser': 'erase',
    'insert_column': 'insert_columns', 'delete_column': 'delete_columns',
    'insert_cell': 'insert_cells', 'insert_row': 'insert_rows',
    'edit_last_dialog': 'last_dialog', 'formula': 'assign_formula',
    'previous_brushed': 'prev_brushed', 'next_brushed_row': 'next_brushed',
    'delete_x': 'delete_red_x',
    'distribution': 'graphical_summary', 'check_for_updates': 'update',
    'r_code': 'code_view', 'r_script': 'code_view',
    'sort_columns': 'sort', 'rank_columns': 'rank',
    'change_data_type': 'format_column', 'rename_column': 'rename_sheet',
    'conditional_formatting': 'format_column', 'stack': 'table', 'unstack': 'subset',
    'transpose_columns': 'transpose', 'merge_worksheets': 'merge',
    'split_worksheet': 'split', 'symmetry_plot': 'symmetry',
    'capability_analysis': 'capability', 'control_charts': 'control_chart',
    'gage_rr': 'chart', 'attribute_agreement': 'table',
}


def _draw(p, kind):
    ink, blue, green, amber, purple, red = '#46586b', '#0b5cab', '#388a68', '#c68a1c', '#7a52a3', '#c93b3b'
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    def style(color=ink, width=1.45, fill=None):
        pen = QPen(QColor(color), width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(QColor(fill) if fill else Qt.BrushStyle.NoBrush)

    def line(x1, y1, x2, y2, color=ink, width=1.45):
        style(color, width); p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def poly(points, color=ink, fill=None, width=1.45, closed=False):
        style(color, width, fill)
        q = QPolygonF([QPointF(*point) for point in points])
        p.drawPolygon(q) if closed else p.drawPolyline(q)

    def rect(x, y, w, h, color=ink, fill=None, radius=0):
        style(color, 1.35, fill)
        p.drawRoundedRect(QRectF(x, y, w, h), radius, radius)

    def dot(x, y, radius=1.2, color=blue, filled=True):
        style(color, 1.1, color if filled else None)
        p.drawEllipse(QPointF(x, y), radius, radius)

    def axes():
        poly([(3, 3), (3, 21), (22, 21)], width=1.2)

    def plus(x=18, y=17, color=green):
        line(x-3, y, x+3, y, color, 1.9); line(x, y-3, x, y+3, color, 1.9)

    def page(x=5, y=2, color=ink):
        poly([(x,y), (x+9,y), (x+14,y+5), (x+14,y+19), (x,y+19), (x,y)], color, '#ffffff', closed=True)
        poly([(x+9,y), (x+9,y+5), (x+14,y+5)], color)

    def grid(x=3, y=4, w=18, h=16, color=ink):
        rect(x,y,w,h,color,'#ffffff')
        rect(x,y,w,4,color,'#e5ecf3')
        for k in (1,2): line(x+w*k/3,y+4,x+w*k/3,y+h,color,1)
        for k in (1,2): line(x,y+4+(h-4)*k/3,x+w,y+4+(h-4)*k/3,color,1)

    if kind in ('new_project', 'new_sheet'):
        if kind == 'new_project': page(); plus(15,15)
        else: grid(3,4,16,15); rect(14,13,9,10,'#ffffff','#ffffff'); plus(18,18)
    elif kind == 'open':
        poly([(2,19),(2,6),(9,6),(11,8.5),(20,8.5),(20,19)],amber,'#ffe8a3',closed=True)
        poly([(2,19.5),(5.5,11),(22.5,11),(19,19.5)],amber,'#f5c451',closed=True)
    elif kind in ('save', 'save_copy'):
        if kind=='save_copy': rect(2,2,15,17,purple,'#f2edf7',1)
        x=6 if kind=='save_copy' else 4
        poly([(x,3.5),(x+12.5,3.5),(x+16,7),(x+16,20.5),(x,20.5)],purple,'#8c6bb1',closed=True)
        rect(x+3,3.5,8,6,purple,'#ffffff'); rect(x+2.5,13,11,7.5,purple,'#f3eef8')
        line(x+8.5,4.8,x+8.5,8.2,purple,1.3)
    elif kind=='print':
        rect(6,2.5,12,6.5,ink,'#ffffff'); rect(3,8,18,9.5,ink,'#d9dee4',1.8)
        rect(6,13.5,12,7.5,ink,'#ffffff'); line(8.5,16.5,15.5,16.5,ink,1.1); line(8.5,18.8,15.5,18.8,ink,1.1)
        dot(17.8,10.8,.9,green)
    elif kind=='export':
        page(3,2); rect(11,9,12,10,'#ffffff','#ffffff'); line(11,14,21,14,blue,1.8)
        poly([(17,10),(21,14),(17,18)],blue, width=1.8)
    elif kind=='cut':
        dot(6.5,18,3,ink,False); dot(17.5,18,3,ink,False)
        line(8.2,15.8,18,3.5,ink,1.6); line(15.8,15.8,6,3.5,ink,1.6); dot(12,11,.9,blue)
    elif kind=='copy':
        rect(3,3,11.5,14.5,ink,'#eef3f8',1); rect(8.5,6.5,11.5,14.5,ink,'#ffffff',1)
        line(11,10.5,17.5,10.5,ink,1.1); line(11,13.8,17.5,13.8,ink,1.1); line(11,17,15.5,17,ink,1.1)
    elif kind=='paste':
        rect(4,4.5,13,16.5,amber,'#e6be74',1.2); rect(7.5,2.5,6,3.5,ink,'#dfe5ec',.8)
        rect(9.5,8.5,11,13,ink,'#ffffff',.8)
        line(11.8,12,18,12,ink,1.1); line(11.8,15,18,15,ink,1.1); line(11.8,18,16,18,ink,1.1)
    elif kind in ('undo','redo'):
        if kind=='redo': p.translate(24,0); p.scale(-1,1)
        path=QPainterPath(QPointF(5,9.5)); path.cubicTo(19,3.5,22,18.5,9.5,19.5)
        style(blue,2.0); p.drawPath(path); poly([(6.5,4.5),(4,10),(10,11.2)],blue,width=2.0)
    elif kind=='last_dialog':
        rect(3,4,18,16,ink,'#ffffff',1.5); rect(3,4,18,4.2,ink,'#7890a8',1)
        rect(6,11,7,2.2,ink,'#dce4ec'); rect(6,15,12,2.2,blue,'#bcd6f0')
        dot(17,12,1.1,ink)
    elif kind in ('delete','delete_sheet'):
        if kind=='delete_sheet': grid(2,3,16,16); rect(13,12,11,12,'#ffffff','#ffffff')
        else: rect(6,7,12,14,ink,None,1); line(4,5,20,5); line(9,2,15,2); line(10,10,10,18); line(14,10,14,18)
        if kind=='delete_sheet': line(15,15,21,21,red,2); line(21,15,15,21,red,2)
    elif kind in ('find','find_next'):
        # Binoculars icon (with next-match arrow for find_next)
        y_off = -1.5 if kind=='find_next' else 0
        rect(4.5,5.5+y_off,5.5,4,ink,'#7d8b99',.8); rect(14,5.5+y_off,5.5,4,ink,'#7d8b99',.8)
        line(9.5,7.5+y_off,14.5,7.5+y_off,ink,2.0)
        poly([(4.5,9+y_off),(3,16.5+y_off),(10.5,16.5+y_off),(9.8,9+y_off)],ink,'#5d6d7e',closed=True)
        poly([(14.2,9+y_off),(13.5,16.5+y_off),(21,16.5+y_off),(19.5,9+y_off)],ink,'#5d6d7e',closed=True)
        dot(6.8,15.5+y_off,2.2,'#dce7f3',True); dot(17.2,15.5+y_off,2.2,'#dce7f3',True)
        if kind=='find_next':
            line(12,20.5,21.5,20.5,blue,2.0); poly([(18.2,17.8),(21.5,20.5),(18.2,23.0)],blue,width=2.0)
    elif kind in ('zoom','zoom_in','zoom_out'):
        dot(10,10,6,blue,False); line(14.5,14.5,21,21,ink,2.3)
        line(7,10,13,10,blue)
        if kind!='zoom_out': line(10,7,10,13,blue)
    elif kind=='cancel':
        style(red,2.2,'#fbeaea'); p.drawEllipse(QPointF(12,12),8.5,8.5)
        line(6.3,6.3,17.7,17.7,red,2.2)
    elif kind=='assign_formula':
        font=QFont('Segoe UI',11,QFont.Weight.DemiBold,True)
        p.setFont(font); p.setPen(QColor('#505a64'))
        p.drawText(QRectF(1,2,22,20),Qt.AlignmentFlag.AlignCenter,'fx')
    elif kind=='insert_cells':
        grid(4,3,16,18)
        rect(4,9,8,6,blue,'#bde0fe')
        line(1.5,12,6.5,12,blue,1.8); poly([(4.5,9.5),(7,12),(4.5,14.5)],blue,width=1.8)
    elif kind=='insert_rows':
        grid(3,3,18,18)
        rect(3,10,18,5,blue,'#bde0fe')
        line(1.2,12.5,6,12.5,blue,1.8); poly([(4,10),(6.5,12.5),(4,15)],blue,width=1.8)
    elif kind in ('insert_columns','delete_columns','move_columns'):
        grid(3,4,18,16)
        rect(9,4,6,16,blue,'#bde0fe')
        if kind=='move_columns':
            path=QPainterPath(QPointF(6,3.5)); path.cubicTo(10,0.5,15,0.5,19,3.5)
            style(blue,1.8); p.drawPath(path); poly([(16.5,1.2),(19.2,3.7),(16.2,5.2)],blue,width=1.8)
        elif kind=='insert_columns':
            line(12,1,12,6.5,blue,1.8); poly([(9.5,4.2),(12,6.8),(14.5,4.2)],blue,width=1.8)
        else:
            rect(13,13,11,11,'#ffffff','#ffffff')
            line(15,18,22,18,red,1.8)
    elif kind in ('prev_brushed','next_brushed'):
        for x,y in ((16,6),(19,10),(15,14),(19,18)):
            rect(x-1.4,y-1.4,2.8,2.8,blue if y in (10,14) else ink,'#7cc0f8' if y in (10,14) else '#ffffff')
        if kind=='prev_brushed':
            line(13,17,5,7,ink,2.0); poly([(5,12.5),(5,7),(10.5,7)],ink,width=2.0)
        else:
            line(5,7,13,17,ink,2.0); poly([(7.5,17),(13,17),(13,11.5)],ink,width=2.0)
    elif kind=='goto':
        grid(7,4,15,16); rect(1,8,13,8,'#ffffff','#ffffff')
        line(2,12,12,12,blue,1.8); poly([(8,8),(12,12),(8,16)],blue,width=1.8)
    elif kind=='calculator':
        rect(4,2,16,20,ink,'#edf2f6',2); rect(7,5,10,4,blue,'#dcebf6')
        for x in (7,11,15):
            for y in (12,16,20): dot(x,y,.7,ink)
    elif kind=='erase':
        poly([(4,14.5),(13.5,4),(20.5,10.5),(11,20)],'#b84a62','#f08ca2',closed=True)
        poly([(3,15.5),(6.5,12),(13.5,18.5),(10,21),(5,21)],ink,'#ffffff',closed=True)
    elif kind=='stop':
        points=[(12+9*cos(pi/8+i*pi/4),12+9*sin(pi/8+i*pi/4)) for i in range(8)]
        poly(points,red,'#e4a4a7',closed=True); rect(8,8,8,8,'#ffffff','#ffffff')
    elif kind in ('worksheet','rename_sheet','duplicate_sheet'):
        if kind=='duplicate_sheet': grid(2,2,15,15,blue); grid(7,7,15,15)
        else:
            grid()
            if kind=='rename_sheet':
                poly([(12,20),(14,15),(20,9),(23,12),(17,18),(12,20)],amber,'#f5d58c',closed=True)
                line(19,10,22,13,ink,1)
    elif kind in ('constants','matrices'):
        if kind=='matrices':
            poly([(6,3),(3,3),(3,21),(6,21)],purple)
            poly([(18,3),(21,3),(21,21),(18,21)],purple)
            for x in (9,15):
                for y in (7,12,17): dot(x,y,1,ink)
        else:
            path=QPainterPath(QPointF(18,6)); path.cubicTo(7,0,2,11,7,18); path.cubicTo(10,22,16,20,19,17)
            style(purple,2); p.drawPath(path); line(16,3,20,3,purple); line(18,1,18,5,purple)
    elif kind in ('scatter3d','surface3d'):
        poly([(3,18),(12,22),(22,17)],ink); line(3,18,3,4); line(3,18,12,10)
        if kind=='scatter3d':
            for x,y in ((7,14),(10,17),(12,11),(15,14),(17,8),(20,12)): dot(x,y,1.35,blue)
        else:
            rows=[[(6,15),(10,11),(14,13),(18,16)],[(8,12),(12,6),(16,9),(20,13)],[(10,10),(14,4),(18,7),(22,11)]]
            for r in range(2):
                for c in range(3): poly([rows[r][c],rows[r][c+1],rows[r+1][c+1],rows[r+1][c]],blue,['#a9d9d0','#a6c8e6','#c4b4dd'][c],1,True)
    elif kind in ('scatter','binned_scatter','bubble','regression','correlation','marginal'):
        axes()
        points=[(6,17),(8,12),(12,15),(15,8),(18,10),(21,5)]
        if kind=='binned_scatter':
            for x,y,c in ((6,16,'#bdd5e8'),(10,12,'#78afd2'),(14,12,'#3f89b9'),(18,8,'#236da0'),(18,4,'#a6c9df')): rect(x-2,y-2,3.6,3.6,c,c)
        else:
            for i,(x,y) in enumerate(points): dot(x,y,(1.6+i%3*.5) if kind=='bubble' else 1.1,blue,kind!='bubble')
            if kind in ('regression','correlation'): line(5,19,22,4,green,1.3)
            if kind=='correlation':
                poly([(15,3),(21,3),(21,9)],purple)
            if kind=='marginal':
                for x,h in ((6,2),(10,3),(14,2),(18,4)): rect(x,1,2,h,amber,amber)
                for y,w in ((7,2),(11,3),(15,2)): rect(21,y,w,2,green,green)
    elif kind in ('histogram','bar_chart','area','line_plot','time_series','ecdf','individual','interval','boxplot','dotplot','probability','normality','summary'):
        axes()
        if kind in ('histogram','bar_chart','summary'):
            for i,h in enumerate((6,12,16,10)):
                rect(5+i*4,21-h,3.7 if kind=='histogram' else 2.5,h,blue,'#82b6d7')
            if kind=='summary': line(9,4,21,4,green); line(14,7,21,7,green)
        elif kind=='area': poly([(4,20),(4,17),(8,13),(12,15),(16,6),(21,10),(21,20)],blue,'#b3d3e6',closed=True)
        elif kind in ('line_plot','time_series','ecdf'):
            points=[(5,17),(8,11),(12,15),(16,6),(21,9)]
            if kind=='ecdf': points=[(5,19),(8,19),(8,15),(12,15),(12,10),(17,10),(17,5),(21,5)]
            poly(points,blue,width=1.6)
            if kind=='line_plot':
                for x,y in points: dot(x,y,.9,green)
            elif kind=='time_series':
                for x in (7,12,17): line(x,21,x,23,ink,1)
        elif kind=='boxplot':
            for x,top,bottom,c in ((8,5,19,blue),(17,8,18,green)):
                line(x,top,x,bottom,c); line(x-2,top,x+2,top,c); line(x-2,bottom,x+2,bottom,c)
                rect(x-2.5,top+4,5,bottom-top-7,c,'#e3eff6'); line(x-2.5,top+7,x+2.5,top+7,c)
        elif kind=='interval':
            for x,lo,hi,c in ((7,10,18,blue),(13,4,13,green),(19,7,16,purple)):
                line(x,lo,x,hi,c); line(x-2,lo,x+2,lo,c); line(x-2,hi,x+2,hi,c); dot(x,(lo+hi)/2,1.5,c)
        elif kind in ('individual','dotplot'):
            for x,y in ((7,17),(7,13),(7,9),(13,16),(13,12),(19,14),(19,10),(19,6)): dot(x,y,1.15,blue if x!=13 else green)
            if kind=='dotplot':
                for x in (7,13,19): dot(x,20,1.15,blue)
        elif kind=='probability':
            line(5,19,21,4,green,1.1)
            for x,y in ((5,18),(8,17),(11,13),(14,10),(17,8),(21,4)): dot(x,y,1,blue,False)
        else:
            path=QPainterPath(QPointF(4,20)); path.cubicTo(9,20,7,5,13,5); path.cubicTo(18,5,17,20,22,20)
            style(blue,1.8); p.drawPath(path); line(13,6,13,20,green,1)
    elif kind in ('heatmap','correlogram','matrix_plot'):
        colors=['#d8e9f3','#6aa8ce','#347fab','#c5b0d8','#e2d7eb','#92bdad','#4d947a','#e9cf94','#b8d5e8']
        for r in range(3):
            for c in range(3):
                x,y=3+c*6.3,3+r*6.3
                if kind=='matrix_plot':
                    rect(x,y,5.8,5.8,'#a6b4c1',None)
                    if c!=r:
                        for dx,dy in ((1.3,4),(2.8,2.9),(4.3,1.6)): dot(x+dx,y+dy,.5,blue)
                    else: line(x+1,y+4,x+2,y+2,green,1); line(x+2,y+2,x+4,y+3,green,1)
                elif kind=='correlogram':
                    rect(x,y,5.8,5.8,'#e1e6eb',None); dot(x+2.9,y+2.9,1+(r+c)%3*.5,blue if c>=r else purple)
                else: rect(x,y,5.8,5.8,colors[r*3+c],colors[r*3+c])
    elif kind=='pie_chart':
        style(blue,1.2,'#87b5d5'); p.drawPie(QRectF(3,3,18,18),0,250*16)
        style(amber,1.2,'#edcd88'); p.drawPie(QRectF(5,1,18,18),0,110*16)
    elif kind=='contour':
        axes()
        for x,y,w,h,c in ((6,5,14,14,blue),(9,7,9,10,green),(12,9,4,5,amber)):
            style(c,1.2); p.drawEllipse(QRectF(x,y,w,h))
    elif kind=='parallel':
        for x in (4,12,20): line(x,3,x,22,ink,1)
        for points,c in (([(4,6),(12,15),(20,8)],blue), ([(4,14),(12,7),(20,18)],green), ([(4,19),(12,11),(20,12)],purple)): poly(points,c, width=1.4)
    elif kind=='stem_leaf':
        line(9,3,9,22,ink)
        for y,n in ((6,2),(11,3),(16,2),(21,3)):
            line(4,y,6,y,blue,2)
            for i in range(n): line(12+4*i,y-1,12+4*i,y+1,green,1.8)
    elif kind=='graph_builder':
        rect(2,3,20,18,ink,None,1); line(8,3,8,21,ink,1)
        for y,c in ((7,blue),(12,green),(17,amber)): rect(4,y-1,2,2,c,c)
        poly([(11,17),(14,13),(17,15),(20,8)],blue)
        for x,y in ((11,17),(14,13),(17,15),(20,8)): dot(x,y,.9,green)
    elif kind=='doe':
        poly([(5,7),(15,3),(21,8),(11,12),(5,7),(5,18),(11,22),(21,17),(21,8)],purple)
        line(11,12,11,22,purple); line(15,3,15,14,purple,1)
        line(5,18,15,14,purple,1); line(15,14,21,17,purple,1)
        for x,y in ((5,7),(15,3),(21,8),(11,12),(5,18),(11,22),(21,17)): dot(x,y,1,amber)
    elif kind in ('rerun','rotate','reset'):
        style(blue,1.8); p.drawArc(QRectF(4,4,16,16),30*16,290*16)
        poly([(14,2),(20,4),(18,10)],blue,width=1.8)
        if kind=='rerun': poly([(10,8),(16,12),(10,16)],green,green,1,True)
        elif kind=='rotate': poly([(8,12),(12,8),(16,12),(12,16)],purple,None,1.2,True)
        else: line(9,12,15,12,green); line(12,9,12,15,green)
    elif kind=='navigator':
        rect(2,3,20,18,ink,None,1); rect(3,4,6,16,'#dce7ef','#dce7ef'); line(10,3,10,21)
        for y in (7,12,17): line(4,y,7,y,blue,1.3)
        line(13,7,19,7); line(13,11,17,11)
    elif kind=='help':
        dot(12,12,9,blue,True)
        path=QPainterPath(QPointF(9.3,8.5)); path.cubicTo(9.3,4.8,16.2,5.2,14.8,9.8); path.cubicTo(14,11.6,12,11.2,12,14.2)
        style('#ffffff',2.0); p.drawPath(path); dot(12,17.8,1.1,'#ffffff',True)
    elif kind=='sheet_menu':
        grid(3,4,18,16,'#505a64')
    elif kind=='delete_red_x':
        line(5.5, 5.5, 18.5, 18.5, red, 2.7)
        line(18.5, 5.5, 5.5, 18.5, red, 2.7)
    elif kind=='format_column':
        font = QFont('Segoe UI', 6.5, QFont.Weight.Bold)
        p.setFont(font); p.setPen(QColor(ink))
        p.drawText(QRectF(1, 2, 16, 10), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, '.00')
        p.drawText(QRectF(1, 12, 14, 10), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, '.0')
        line(13, 17, 21, 17, blue, 1.8)
        poly([(18, 14.2), (21.2, 17), (18, 19.8)], blue, width=1.8)
    elif kind=='send_report':
        page(3, 2.5)
        line(6, 9, 13, 9, ink, 1.1); line(6, 12.5, 13, 12.5, ink, 1.1)
        line(11, 16, 21.5, 16, blue, 1.9)
        poly([(17.8, 12.8), (21.5, 16), (17.8, 19.2)], blue, width=1.9)
    elif kind=='copy_graph':
        rect(3, 4, 14, 12, ink, '#eef4fa', 1)
        rect(6, 7, 15, 13, blue, '#ffffff', 1)
        poly([(8, 17), (11.5, 12.5), (14.5, 15), (18.5, 10.5)], blue, width=1.6)
        dot(10, 10.5, 1.1, amber)
    elif kind=='make_similar_graph':
        axes()
        for i, h in enumerate((7, 13, 10)):
            rect(6 + i * 4.5, 21 - h, 3.2, h, blue, '#6fb1e4')
    elif kind=='edit_graph':
        poly([(5, 19), (7, 13.5), (16.5, 4), (20, 7.5), (10.5, 17), (5, 19)], blue, '#90c8f6', closed=True)
        line(14.5, 6, 18, 9.5, blue, 1.3)
        line(4, 21, 19, 21, ink, 1.2)
    elif kind=='panel_graph':
        rect(3, 4, 8, 16, blue, '#e6f1fb')
        rect(13, 4, 8, 16, blue, '#e6f1fb')
        rect(5, 12, 2, 6, blue, blue); rect(8, 8, 2, 10, blue, blue)
        rect(15, 10, 2, 8, green, green); rect(18, 7, 2, 11, green, green)
    elif kind=='brush_points':
        for x, y, c in ((6, 8, blue), (10, 6, blue), (7, 13, ink), (12, 11, blue)):
            dot(x, y, 1.3, c)
        poly([(11, 17), (15, 12), (20.5, 16), (16, 20.5)], amber, '#f4c76b', closed=True)
        line(15, 12, 21, 5, ink, 1.8)
    elif kind=='layout_tool':
        rect(3, 4, 11, 9, ink, '#ffffff')
        rect(6, 4, 8, 2.5, blue, '#6fb1e4')
        rect(10, 10, 11, 10, blue, '#ffffff')
        rect(10, 10, 11, 2.8, blue, '#3a8fd6')
    elif kind in ('status_navigator','status_split','status_data_only','status_output_only','status_command_line'):
        w_col='#ffffff'
        rect(3,4,18,16,w_col,None,1)
        if kind=='status_navigator':
            rect(3,4,6.5,16,w_col,'#ffffff'); line(9.5,4,9.5,20,w_col,1.4)
        elif kind=='status_split':
            line(3,12,21,12,w_col,1.5)
            for x in (9,15): line(x,12,x,20,w_col,1.1)
            line(3,16,21,16,w_col,1.1)
        elif kind=='status_data_only':
            for x in (9,15): line(x,4,x,20,w_col,1.1)
            for y in (9.3,14.6): line(3,y,21,y,w_col,1.1)
        elif kind=='status_output_only':
            line(6.5,9,17.5,9,w_col,1.4); line(6.5,13,17.5,13,w_col,1.4); line(6.5,17,14,17,w_col,1.4)
        elif kind=='status_command_line':
            line(13,4,13,20,w_col,1.3)
            poly([(15.5,8.5),(18.5,11),(15.5,13.5)],w_col,width=1.5)
            line(16,16,19.5,16,w_col,1.5)
    elif kind == 'graphical_summary':
        # Minitab 4-panel thumbnail: histogram + normal curve, boxplot, summary lines
        rect(3, 7, 2, 4, blue, blue); rect(5.5, 4, 2, 7, blue, blue); rect(8, 6, 2, 5, blue, blue)
        poly([(2.5, 10.5), (4.5, 7.5), (6.5, 3.5), (8.5, 6), (10.5, 10.5)], red, width=1.1)
        rect(3.5, 15, 6, 3, ink, '#f1f5f9'); line(6.5, 15, 6.5, 18, red, 1.2)
        line(1.5, 16.5, 3.5, 16.5, ink, 1.0); line(9.5, 16.5, 11.5, 16.5, ink, 1.0)
        line(12.5, 3, 12.5, 21, ink, 0.9)
        line(14.5, 6, 21.5, 6, ink, 1.3); line(14.5, 9, 19.5, 9, ink, 1.1)
        line(14.5, 12, 21, 12, ink, 1.1); line(14.5, 15, 18, 15, ink, 1.1); line(14.5, 18, 20.5, 18, ink, 1.1)
    elif kind == 'run_chart':
        axes(); line(3, 12, 21, 12, green, 1.1)
        poly([(4, 16), (7, 8), (10, 14), (13, 7), (16, 17), (19, 9)], blue, width=1.3)
        for x, y in ((4, 16), (7, 8), (10, 14), (13, 7), (16, 17), (19, 9)): dot(x, y, 1.1, blue)
    elif kind == 'multivari':
        axes()
        for x in (7, 12, 17): line(x, 6, x, 18, ink, 1.0)
        for x, y in ((7, 8), (7, 16), (12, 7), (12, 15), (17, 9), (17, 17)): dot(x, y, 1.1, ink)
        poly([(7, 12), (12, 10.5), (17, 13)], blue, width=1.5)
        for x, y in ((7, 12), (12, 10.5), (17, 13)): dot(x, y, 1.3, blue)
    elif kind == 'outlier_test':
        axes(); rect(6, 9, 8, 6, ink, '#e0f2fe'); line(10, 9, 10, 15, blue, 1.3)
        line(3, 12, 6, 12, ink, 1.1); line(3, 10, 3, 14, ink, 1.1)
        line(14, 12, 17, 12, ink, 1.1); line(17, 10, 17, 14, ink, 1.1)
        dot(20.5, 12, 1.6, red, filled=True)
        line(19.5, 8, 21.5, 6, red, 1.2); line(19.5, 6, 21.5, 8, red, 1.2)
    elif kind == 'chart':
        axes()
        line(4, 7, 21, 7, red, 1.0); line(4, 17, 21, 17, red, 1.0); line(4, 12, 21, 12, green, 1.1)
        poly([(5, 11), (8, 9), (11, 14), (14, 8), (17, 10), (20, 15)], blue, width=1.3)
        for x, y in ((5, 11), (8, 9), (11, 14), (14, 8), (17, 10), (20, 15)): dot(x, y, 1.1, blue)
    elif kind == 'covariance':
        axes()
        p.save(); p.translate(12, 12); p.rotate(-35)
        rect(-7.5, -3.5, 15, 7, blue, '#e0f2fe', radius=3.5)
        p.restore()
        line(6, 16.5, 18, 7.5, red, 1.2)
    elif kind == 'standardize':
        poly([(3, 19), (6, 18), (9, 13), (12, 5), (15, 13), (18, 18), (21, 19)], blue, width=1.4)
        line(12, 5, 12, 21, ink, 1.0); line(2, 19, 22, 19, ink, 1.2)
        line(8, 18, 8, 20, ink, 1.1); line(16, 18, 16, 20, ink, 1.1)
        poly([(14.5, 8.5), (17.5, 8.5), (14.5, 12), (17.5, 12)], amber, width=1.2)
    elif kind == 'select_all':
        for cx, cy in ((3, 3), (18, 3), (3, 18), (18, 18)): rect(cx, cy, 3, 3, blue, '#ffffff')
        line(6, 4.5, 18, 4.5, blue, 1.1); line(4.5, 6, 4.5, 18, blue, 1.1)
        line(6, 19.5, 18, 19.5, blue, 1.1); line(19.5, 6, 19.5, 18, blue, 1.1)
        poly([(8, 12), (11, 15), (16, 8)], green, width=2.0)
    elif kind == 'subset':
        rect(3, 3, 11, 12, ink, '#f8fafc'); line(3, 6, 14, 6, ink, 0.9)
        rect(9, 8, 12, 13, blue, '#ffffff'); rect(9, 8, 12, 4, blue, '#38bdf8')
        line(9, 15, 21, 15, blue, 0.9); line(15, 8, 15, 21, blue, 0.9)
        poly([(6, 10), (9, 13), (7.5, 13)], amber, width=1.2)
    elif kind == 'table':
        rect(3, 4, 18, 16, ink, '#ffffff')
        rect(3, 4, 18, 4.5, blue, '#dbeafe')
        line(9, 4, 9, 20, ink, 1.0); line(15, 4, 15, 20, ink, 1.0)
        line(3, 12.5, 21, 12.5, ink, 1.0); line(3, 16.5, 21, 16.5, ink, 1.0)
    elif kind == 'code_view':
        poly([(7, 8), (4, 12), (7, 16)], blue, width=1.8)
        line(10, 17, 14, 7, amber, 1.8)
        poly([(17, 8), (20, 12), (17, 16)], blue, width=1.8)
    elif kind == 'connect':
        p.save(); p.translate(9, 9); p.rotate(-45); rect(-4.5, -2.5, 9, 5, blue, None, 2.5); p.restore()
        p.save(); p.translate(15, 15); p.rotate(-45); rect(-4.5, -2.5, 9, 5, green, None, 2.5); p.restore()
    elif kind == 'workflow':
        rect(3, 4, 6, 5, blue, '#dbeafe', 1)
        line(9, 6.5, 15, 6.5, ink, 1.2); poly([(13.5, 5), (15.5, 6.5), (13.5, 8)], ink, fill=ink, closed=True)
        rect(15, 4, 6, 5, amber, '#fef3c7', 1)
        line(18, 9, 18, 14, ink, 1.2); poly([(16.5, 12), (18, 14), (19.5, 12)], ink, fill=ink, closed=True)
        rect(14, 14, 7, 6, green, '#dcfce7', 1)
        line(14, 17, 9, 17, ink, 1.2); poly([(11, 15.5), (9, 17), (11, 18.5)], ink, fill=ink, closed=True)
        rect(3, 14, 6, 5, purple, '#f3e8ff', 1)
    elif kind == 'report':
        page(4, 2, ink)
        rect(7, 5, 7, 2, blue, blue)
        line(7, 9, 14, 9, ink, 1.0); line(7, 11, 15, 11, ink, 1.0)
        rect(7, 15, 2, 3, amber, amber); rect(10, 13, 2, 5, blue, blue); rect(13, 16, 2, 2, green, green)
    elif kind == 'update':
        style(blue, 1.6); p.drawArc(QRectF(4, 4, 16, 16), int(35 * 16), int(135 * 16))
        poly([(13, 3), (17, 5.5), (15, 9.5)], blue, fill=blue, closed=True)
        style(green, 1.6); p.drawArc(QRectF(4, 4, 16, 16), int(215 * 16), int(135 * 16))
        poly([(11, 21), (7, 18.5), (9, 14.5)], green, fill=green, closed=True)
    elif kind == 'sort':
        line(5, 5, 5, 18, blue, 1.6)
        poly([(3, 15), (5, 19), (7, 15)], blue, fill=blue, closed=True)
        line(9, 6, 14, 6, ink, 1.8)
        line(9, 11, 17, 11, ink, 1.8)
        line(9, 16, 20, 16, ink, 1.8)
    elif kind == 'rank':
        rect(9.5, 5, 5, 15, blue, '#dbeafe')
        rect(4, 9, 5, 11, amber, '#fef3c7')
        rect(15, 13, 5, 7, green, '#dcfce7')
        line(2, 20, 22, 20, ink, 1.2)
    elif kind == 'capability':
        line(4.5, 3, 4.5, 21, red, 1.1)
        line(19.5, 3, 19.5, 21, red, 1.1)
        poly([(4.5, 20), (7, 19), (9.5, 15), (12, 5), (14.5, 15), (17, 19), (19.5, 20)], blue, width=1.6)
        line(3, 20, 21, 20, ink, 1.0)
    elif kind == 'control_chart':
        line(3, 5, 21, 5, red, 1.0)
        line(3, 12, 21, 12, green, 1.1)
        line(3, 19, 21, 19, red, 1.0)
        poly([(4, 14), (7, 8), (11, 15), (15, 7), (18, 11), (20, 9)], blue, width=1.4)
        for x, y in ((4, 14), (7, 8), (11, 15), (15, 7), (18, 11), (20, 9)): dot(x, y, 1.1, blue)
    elif kind == 'symmetry':
        axes()
        line(4, 20, 20, 4, red, 1.2)
        for x, y in ((7, 16), (9, 14), (12, 11), (15, 8), (17, 6)): dot(x, y, 1.2, blue)
        for x, y in ((10, 15), (14, 9)): dot(x, y, 1.0, ink)
    elif kind == 'split':
        rect(3, 4, 8, 16, ink, '#ffffff')
        rect(13, 4, 8, 16, blue, '#f0f9ff')
        line(11, 3, 11, 21, red, 1.1)
    elif kind == 'merge':
        rect(3, 4, 6, 16, ink, '#ffffff')
        rect(10, 4, 6, 16, ink, '#ffffff')
        line(17, 12, 20.5, 12, blue, 1.4)
        poly([(19, 10), (21.5, 12), (19, 14)], blue, fill=blue, closed=True)
    elif kind == 'transpose':
        rect(3, 6, 18, 12, ink, '#ffffff')
        line(3, 10, 21, 10, blue, 1.0); line(9, 6, 9, 18, ink, 1.0)
        poly([(15, 3), (18, 3), (18, 6)], blue, fill=blue, closed=True)
        poly([(9, 21), (6, 21), (6, 18)], blue, fill=blue, closed=True)
    else:
        # A neutral sheet for unknown action identifiers, never a misleading graph.
        page(); line(8,11,16,11); line(8,15,16,15)


@lru_cache(maxsize=160)
def tool_icon(kind):
    """Return a reusable icon. Call after creating QApplication, on its UI thread."""
    kind = _ALIASES.get(str(kind), str(kind))
    icon = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 96):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.scale(size / 24.0, size / 24.0)
        _draw(painter, kind)
        painter.end()
        icon.addPixmap(pixmap)
    return icon
