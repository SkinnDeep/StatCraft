"""Original painter hit regions and appearance primitives for graph editing."""
import math
import html
from PySide6.QtCore import Qt,QPointF,QRectF,QEvent
from PySide6.QtGui import QColor,QPen,QPolygonF,QPainterPath,QPainterPathStroker
from PySide6.QtWidgets import QToolTip
from .graph_styles import validate_styles


PALETTE=('#3e739b','#b46e39','#53856e','#9266a5','#b6485a','#628d9a','#858446','#766459')


def style_color(value,opacity=1):
    color=QColor(value[:7])
    if len(value)==9:color.setAlpha(int(value[7:],16))
    color.setAlphaF(color.alphaF()*opacity);return color


def style_pen(style,default='#3e739b'):
    if style.get('line_style')=='none' or style.get('line_width',1.5)==0:return QPen(Qt.PenStyle.NoPen)
    pen=QPen(style_color(style.get('edge',style.get('color',default)),style.get('opacity',1)),style.get('line_width',1.5))
    pen.setStyle({'solid':Qt.PenStyle.SolidLine,'dash':Qt.PenStyle.DashLine,'dot':Qt.PenStyle.DotLine}.get(style.get('line_style'),Qt.PenStyle.SolidLine))
    return pen


def draw_marker(painter,point,style,default_shape='circle',default_size=6.4):
    shape=style.get('marker',default_shape)
    if shape=='none' or not style.get('visible',True):return
    radius=style.get('marker_size',default_size)/2
    color=style.get('color','#3e739b');opacity=style.get('opacity',1)
    painter.setPen(QPen(style_color(style.get('edge',color),opacity),1))
    painter.setBrush(style_color(style.get('fill',color),opacity))
    x,y=point.x(),point.y()
    if shape=='circle':painter.drawEllipse(point,radius,radius)
    elif shape=='square':painter.drawRect(QRectF(x-radius,y-radius,2*radius,2*radius))
    elif shape in ('triangle','diamond'):
        vertices=[QPointF(x,y-radius),QPointF(x-radius,y+radius),QPointF(x+radius,y+radius)] if shape=='triangle' else [QPointF(x,y-radius),QPointF(x+radius,y),QPointF(x,y+radius),QPointF(x-radius,y)]
        painter.drawPolygon(QPolygonF(vertices))
    elif shape=='plus':
        painter.drawLine(QPointF(x-radius,y),QPointF(x+radius,y));painter.drawLine(QPointF(x,y-radius),QPointF(x,y+radius))
    else:
        painter.drawLine(QPointF(x-radius,y-radius),QPointF(x+radius,y+radius));painter.drawLine(QPointF(x-radius,y+radius),QPointF(x+radius,y-radius))


class GraphInteractionMixin:
    def _init_graph_interaction(self):
        self.graph_styles=validate_styles(self.entry.get('graph_styles',{}))
        self.selected_object=None;self.hit_regions=[];self._panel_index=0
        self.is_brushing=False;self.brushed_rows=set();self.brush_regions=[]
        self._brush_start=None;self._brush_end=None
        self.hover_regions=[];self._hover_text="";self.setMouseTracking(True)

    def clear_hover(self):
        self.hover_regions=[]
        self._hide_hover()

    def reset_hover_regions(self):
        self.hover_regions=[]
        if getattr(self,'_exporting',False):self._hide_hover()

    def _hide_hover(self):
        if getattr(self,'_hover_text',''):QToolTip.hideText()
        self._hover_text=''

    def remember_hover(self,region,information,clip=None):
        if getattr(self,'_exporting',False) or not isinstance(information,dict) or not information.get('text'):return
        if isinstance(region,QRectF):
            rect=region.normalized()
            if clip is None:clip=getattr(self,'_current_plot',None)
            if clip is not None:rect=rect.intersected(clip)
            if rect.isEmpty():return
            path=QPainterPath();path.addRect(rect)
        else:
            path=QPainterPath(region)
            if clip is not None:
                boundary=QPainterPath();boundary.addRect(clip);path=path.intersected(boundary)
        self.hover_regions.append((path,dict(information)))

    def remember_point_hover(self,point,information,size=10,clip=None):
        radius=max(5.,float(size)/2)
        self.remember_hover(QRectF(point.x()-radius,point.y()-radius,radius*2,radius*2),information,clip)

    def hover_info_at(self,position):
        if getattr(self,'_exporting',False) or self.is_brushing:return None
        return next((dict(info) for path,info in reversed(self.hover_regions) if path.contains(position)),None)

    def hover_text_at(self,position):
        info=self.hover_info_at(position)
        if not info:return ''
        text=info.get('text','')
        id_info=getattr(self,'id_column_info',None)
        row=info.get('row')
        if id_info and isinstance(row,int) and row>=1:
            col_name,vals=id_info
            if row-1<len(vals) and vals[row-1] is not None:
                text+=f"\nID ({col_name}): {vals[row-1]}"
        return text

    def resizeEvent(self,event):
        self.clear_hover()
        super().resizeEvent(event)

    def leaveEvent(self,event):
        self._hide_hover()
        super().leaveEvent(event)

    def event(self,event):
        if event.type()==QEvent.Type.ToolTip:
            text=self.hover_text_at(QPointF(event.pos()))
            if text:
                self._hover_text=text
                QToolTip.showText(event.globalPos(),'<qt>'+html.escape(text).replace('\n','<br>')+'</qt>',self)
            else:self._hide_hover()
            event.accept();return True
        return super().event(event)

    def set_brushing(self,enabled):
        from .brushing import brushable_rows
        if enabled and not brushable_rows(self.entry):raise ValueError('This graph has no row-linked points. Rerun a scatter or row-aligned XY graph.')
        self._hide_hover()
        self.is_brushing=bool(enabled);self._brush_start=self._brush_end=None
        self.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor);self.update()

    def _target(self,name):return 'p'+str(self._panel_index)+':'+name

    def graph_style(self,name,**defaults):
        return dict(defaults,**self.graph_styles.get(self._target(name),{}))

    def remember_rect(self,name,rect):
        path=QPainterPath();path.addRect(rect.normalized());self.hit_regions.append((self._target(name),path))

    def remember_marker(self,name,point,size=6,row=None):
        self.remember_rect(name,QRectF(point.x()-max(5,size/2),point.y()-max(5,size/2),max(10,size),max(10,size)))
        if type(row) is int and row>0 and (getattr(self,'_current_plot',None) is None or self._current_plot.contains(point)):
            self.brush_regions.append((row,QRectF(point.x()-5,point.y()-5,10,10)))

    def remember_bar_brush(self, rect, rows):
        if not rows: return
        r = rect.normalized()
        for row in rows:
            if type(row) is int and row > 0:
                self.brush_regions.append((row, r))

    def remember_path(self,name,points):
        path=QPainterPath();active=False
        for point in points:
            if point is None:active=False;continue
            if active:path.lineTo(point)
            else:path.moveTo(point);active=True
        stroke=QPainterPathStroker();stroke.setWidth(8)
        self.hit_regions.append((self._target(name),stroke.createStroke(path)))

    def remember_axes(self,plot):
        self._current_plot=plot
        self.remember_rect('grid',plot)
        self.remember_rect('axis',QRectF(plot.left()-65,plot.top(),65,plot.height()+25))
        self.remember_rect('axis',QRectF(plot.left(),plot.bottom(),plot.width(),48))

    def object_at(self,position):
        return next((target for target,path in reversed(self.hit_regions) if path.contains(position)),None)

    def mousePressEvent(self,event):
        self._hide_hover()
        if event.button()==Qt.MouseButton.LeftButton:
            if self.is_brushing:
                self._brush_start=self._brush_end=event.position();self._brush_add=bool(event.modifiers()&Qt.KeyboardModifier.ControlModifier)
                event.accept();self.update();return
            pos = event.position()
            clicked_rows = {row for row, region in self.brush_regions if region.contains(pos)}
            if clicked_rows:
                is_ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                if is_ctrl:
                    self.brushed_rows = self.brushed_rows | clicked_rows
                else:
                    self.brushed_rows = clicked_rows
                self.brushRowsSelected.emit(sorted(self.brushed_rows))
                self.update()
                event.accept()
                return
            elif self.brushed_rows and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self.brushed_rows = set()
                self.brushRowsSelected.emit([])
                self.update()
            self.selected_object=self.object_at(event.position());self.update()
            if self.selected_object:self.objectSelected.emit(self.selected_object)
            event.accept();return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.is_brushing and self._brush_start is not None:
            self._brush_end=event.position();self.update();event.accept();return
        text=self.hover_text_at(event.position())
        if text!=self._hover_text:
            self._hover_text=text
            if text:QToolTip.showText(event.globalPosition().toPoint(),'<qt>'+html.escape(text).replace('\n','<br>')+'</qt>',self)
            else:QToolTip.hideText()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if self.is_brushing and self._brush_start is not None and event.button()==Qt.MouseButton.LeftButton:
            rect=QRectF(self._brush_start,event.position()).normalized()
            if rect.width()<4 and rect.height()<4:rect=rect.adjusted(-5,-5,5,5)
            rows={row for row,region in self.brush_regions if rect.intersects(region) or rect.contains(region.center())}
            if self._brush_add:rows|=self.brushed_rows
            self.brushed_rows=rows;self._brush_start=self._brush_end=None
            self.brushRowsSelected.emit(sorted(rows));self.update();event.accept();return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self,event):
        if self.is_brushing and event.key()==Qt.Key.Key_Escape:
            self.set_brushing(False);event.accept();return
        super().keyPressEvent(event)

    def mouseDoubleClickEvent(self,event):
        if self.is_brushing:event.accept();return
        if event.button()==Qt.MouseButton.LeftButton:
            target=self.object_at(event.position())
            if target:
                self.selected_object=target;self.objectActivated.emit(target);event.accept();return
        super().mouseDoubleClickEvent(event)

    def draw_selection(self,painter):
        if getattr(self,'_exporting',False):return
        painter.save()
        painter.setPen(QPen(QColor('#bd2870'),2))
        painter.setBrush(QColor(189,40,112,35))
        drawn_bounds = set()
        for row,region in self.brush_regions:
            if row in self.brushed_rows:
                key = (round(region.x(), 1), round(region.y(), 1), round(region.width(), 1), round(region.height(), 1))
                if key not in drawn_bounds:
                    drawn_bounds.add(key)
                    painter.drawRect(region.adjusted(-2,-2,2,2))
        if self._brush_start is not None:
            painter.setPen(QPen(QColor('#087fbd'),1,Qt.PenStyle.DashLine));painter.setBrush(QColor(8,127,189,25))
            painter.drawRect(QRectF(self._brush_start,self._brush_end).normalized())
        painter.restore()
        regions=[path.boundingRect() for target,path in self.hit_regions if target==self.selected_object]
        if not regions:return
        rect=regions[0]
        for region in regions[1:]:rect=rect.united(region)
        painter.save();painter.setPen(QPen(QColor('#087fbd'),1,Qt.PenStyle.DashLine));painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect.adjusted(-3,-3,3,3));painter.restore()

    def editable_objects(self):
        objects=[]
        palette=getattr(self,'palette_colors',PALETTE)
        def add(panel,name,label,capabilities,defaults):
            objects.append({'target':'p'+str(panel)+':'+name,'label':label,'capabilities':capabilities,'defaults':defaults})
        line=('color','line_width','line_style','opacity','visible')
        marker=('color','fill','edge','marker','marker_size','opacity','visible')
        for index,panel in enumerate(self.panels):
            kind=panel['kind'];prefix=('Panel '+str(index+1)+' — ') if len(self.panels)>1 else ''
            if kind=='mixture_contour':
                add(index,'ref0',prefix+'Contour lines',line,{'color':'#45515b','line_width':.9,'line_style':'solid','visible':True})
                add(index,'axis',prefix+'Mixture boundary and labels',line,{'color':'#52616d','line_width':1.1,'line_style':'solid','visible':True})
                add(index,'grid',prefix+'Mixture grid',line,{'color':'#b5bfc6','line_width':.7,'line_style':'dot','visible':True})
            if kind=='mixture_optimum':
                add(index,'bars',prefix+'Component amounts',('fill','edge','opacity','line_width','line_style','visible'),{'fill':'#79add8','edge':'#466a85','opacity':1,'line_width':1,'line_style':'solid','visible':True})
                add(index,'axis',prefix+'Amount scale and labels',line,{'color':'#52616d','line_width':1,'line_style':'solid','visible':True})
                add(index,'grid',prefix+'Amount grid',line,{'color':'#e6ebef','line_width':1,'line_style':'solid','visible':True})
            if kind in ('multi_scatter','xy'):
                for series_index,series in enumerate(panel['series']):
                    color=palette[series_index%len(palette)]
                    defaults={'color':color,'marker':'circle','marker_size':6.4,'line_width':1.5,'line_style':'solid','opacity':1,'visible':True,'legend_visible':True}
                    caps=list(marker)+['legend_visible']+(list(line) if series.get('connect') else [])
                    add(index,'s'+str(series_index),prefix+'Series: '+str(series.get('label',series.get('name','')) or series_index+1),set(caps),defaults)
                    if series.get('fit'):add(index,'fit'+str(series_index),prefix+'Fitted line '+str(series_index+1),line,{'color':color,'line_width':1.7,'line_style':'solid','visible':True})
            elif kind in ('scatter','normal_probability','line','xyz','intervals'):
                add(index,'s0',prefix+'Data symbols'+(' and line' if kind=='line' else ''),set(marker+line if kind=='line' else marker),{'color':palette[0],'marker':'circle','marker_size':6.4,'line_width':1.6,'line_style':'solid','visible':True,'opacity':1})
            if kind=='categorical_points':
                for item_index,item in enumerate(panel['items']):
                    color=palette[item['color_index']%len(palette)];suffix=str(item_index);caption=item['label'].replace('\n',' / ')
                    for option,target,label,shape in (('individual','s','Individual values','circle'),('mean_symbol','mean','Mean','diamond'),('median_symbol','median','Median','cross')):
                        if panel['display'][option]:add(index,target+suffix,prefix+label+': '+caption,marker,{'color':color,'fill':color,'edge':color,'marker':shape,'marker_size':5 if option=='individual' else 9,'opacity':.8 if option=='individual' else 1,'visible':True})
                    if panel['display']['interval']:add(index,'int'+suffix,prefix+'Interval: '+caption,line,{'color':color,'line_width':1.6,'line_style':'solid','visible':True,'opacity':1})
                    if panel['display']['bar']:add(index,'bar'+suffix,prefix+'Mean bar: '+caption,('fill','edge','line_width','line_style','opacity','visible'),{'fill':color,'edge':color,'line_width':1,'line_style':'solid','opacity':.3,'visible':True})
                for option,target,label in (('median_connect','ref0','Median connect line'),('mean_connect','ref1','Mean connect line')):
                    if panel['display'][option]:add(index,target,prefix+label,line,{'color':'#555555','line_width':1.5,'line_style':'solid','visible':True})
            if kind=='dotplot_groups':
                for series_index,series in enumerate(panel['series']):
                    color=palette[series['color_index']%len(palette)]
                    add(index,'s'+str(series_index),prefix+'Dots: '+series['label'],marker,{'color':color,'fill':color,'edge':color,'marker':'circle','marker_size':6,'opacity':1,'visible':True})
            if kind=='boxplot_groups':
                for item_index,item in enumerate(panel['items']):
                    color=palette[item['color_index']%len(palette)]
                    add(index,'s'+str(item_index),prefix+'Box: '+item['label'].replace('\n',' / '),set(marker+line),{'color':color,'fill':color,'edge':color,'line_width':1.5,'opacity':.65,'marker':'circle','marker_size':5,'visible':True})
                for name,target,label in (('median_connect','ref0','Median connect line'),('mean_connect','ref1','Mean connect line')):
                    if panel['display'][name]:add(index,target,prefix+label,line,{'color':'#555555','line_width':1.4,'line_style':'solid','visible':True})
            if kind=='histogram_groups':
                for series_index,series in enumerate(panel['series']):
                    color=palette[series.get('color_index',series_index)%len(palette)]
                    add(index,'s'+str(series_index),prefix+'Bars: '+series['label'],('fill','edge','line_width','line_style','opacity','visible','legend_visible'),{'fill':color,'edge':color,'line_width':.7,'line_style':'solid','opacity':.45 if len(panel['series'])>1 else .8,'visible':True,'legend_visible':True})
                    if series['curves']:add(index,'fit'+str(series_index),prefix+'Normal fit: '+series['label'],line,{'color':color,'line_width':2,'line_style':'solid','visible':True})
            if kind in ('histogram','bars','binbars'):
                add(index,'bars',prefix+'Bars',('fill','edge','line_width','line_style','opacity','visible'),{'fill':'#a7bfd2' if kind=='histogram' else '#326b9b','edge':'#ffffff','line_width':1,'line_style':'solid','opacity':1,'visible':True})
            if kind=='boxplot':add(index,'box',prefix+'Box and whiskers',set(marker+line),{'color':PALETTE[0],'fill':'#c2d4e1','line_width':1.7,'line_style':'solid','visible':True})
            for curve_index,curve in enumerate(panel.get('curves',[])):
                add(index,'fit'+str(curve_index),prefix+str(curve[0]),line,{'color':curve[3],'line_width':2,'line_style':'solid','visible':True})
            for ref_index,reference in enumerate(panel.get('lines',[])):
                add(index,'ref'+str(ref_index),prefix+str(reference[0]),line,{'color':reference[2],'line_width':1.2,'line_style':'dash','visible':True})
            if kind=='normal_probability':add(index,'fit0',prefix+'Reference line',line,{'color':'#bb4147','line_width':1.5,'line_style':'solid','visible':True})
            if kind in ('categorical_points','dotplot_groups','boxplot_groups','histogram_groups','histogram','bars','binbars','boxplot','scatter','normal_probability','line','multi_scatter','xy','intervals'):
                add(index,'axis',prefix+'Axes',line,{'color':'#66737d','line_width':1,'line_style':'solid','visible':True})
                add(index,'grid',prefix+'Gridlines',line,{'color':'#dfe4e8','line_width':1,'line_style':'solid','visible':True})
        return objects
