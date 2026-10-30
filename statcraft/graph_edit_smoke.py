"""Desktop/frozen acceptance checks for original graph-object editing."""
import copy
from pathlib import Path
from PySide6.QtCore import Qt,QEvent,QPointF,QTimer
from PySide6.QtGui import QMouseEvent,QImage
from PySide6.QtWidgets import QApplication,QDialogButtonBox
from .model import Worksheet,Column
from .recipes import run


def verify_graph_editing(app,p,w,temp,checkpoint):
    checkpoint('graph object selection and double-click attributes')
    p.new();p.worksheet=Worksheet('Graph editing',[
        Column('X',values=[1,2,3,4,5,6,7,8]),Column('Y',values=[2,5,4,9,8,13,12,17]),
        Column('Batch','text',['A','A','A','A','B','B','B','B']),Column('Z',values=[8,1,7,2,6,3,5,4])])
    w.page=0;w._show_welcome();w.refresh()
    scatter=p.scatter_plot(0,1,'connect_groups',2);w.show_result(scatter);app.processEvents()
    chart=w._active_chart_widget;chart.grab();original=copy.deepcopy(scatter['result'])
    def position(target,small=False):
        return next(path.boundingRect().center() for name,path in chart.hit_regions if name==target and (not small or path.boundingRect().width()<40))
    def mouse(widget,kind,pos):
        event=QMouseEvent(kind,pos,QPointF(widget.mapToGlobal(pos.toPoint())),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(widget,event);app.processEvents()
    point=position('p0:s1',True);mouse(chart,QEvent.Type.MouseButtonPress,point)
    assert chart.selected_object=='p0:s1'
    def style_dialog():
        dialog=QApplication.activeModalWidget()
        assert dialog.object_combo.currentData()=='p0:s1'
        dialog.controls['color'].setText('#f000b8')
        dialog.controls['marker'].setCurrentIndex(dialog.controls['marker'].findData('square'))
        dialog.controls['marker_size'].setValue(16)
        dialog.controls['line_width'].setValue(3)
        dialog.controls['line_style'].setCurrentIndex(dialog.controls['line_style'].findData('dash'))
        dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    QTimer.singleShot(0,style_dialog);mouse(chart,QEvent.Type.MouseButtonDblClick,point)
    assert scatter['graph_styles']['p0:s1']['marker']=='square'
    assert scatter['result']==original and chart.error is None
    def has_pink():
        image=chart.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        return bytes((240,0,184,255)) in bytes(image.bits())
    assert has_pink()
    w.undo();app.processEvents();assert 'graph_styles' not in scatter and not has_pink()
    w.redo();app.processEvents();assert has_pink()
    frame=w._active_graph_frame;selected=chart.selected_object
    assert frame.capture().save(str(Path(temp)/'edited-scatter.png'))
    assert chart.selected_object==selected
    # Axis double-click opens scale controls; title double-click edits the title.
    mouse(chart,QEvent.Type.MouseButtonDblClick,position('p0:axis'))
    assert w.graph_options_pane.isVisible() and w.graph_options_pane.more_button.isChecked()
    mouse(frame.title_label,QEvent.Type.MouseButtonDblClick,QPointF(10,10))
    assert w.graph_options_pane.controls['title'].selectedText()==frame.title_label.text()
    w.close_graph_options()
    checkpoint('histogram scale and Normal fit editing')
    hist=run(p,{'action':'graph','parameters':{'method':'histogram','indices':[1],'bins':3}})
    w.show_result(hist);app.processEvents();hist_before=copy.deepcopy(hist['result'])
    def histogram_dialog():
        dialog=QApplication.activeModalWidget();dialog.bins.setValue(6)
        dialog.scale.setCurrentText('Percent');dialog.fit.setCurrentText('Normal')
        dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    QTimer.singleShot(0,histogram_dialog)
    next(a for a in w.build_output_context_menu(hist).actions() if a.text()=='Histogram Scales and Fits...').trigger()
    chart=w._active_chart_widget;chart.grab();panel=chart.panels[0]
    assert hist['result']==hist_before and len(panel['edges'])==7 and abs(sum(panel['counts'])-100)<1e-8 and len(panel['curves'])==1
    assert panel['ylabel']=='Percent' and chart.error is None
    w.undo();assert 'histogram_settings' not in hist and len(chart.panels[0]['counts'])==3
    w.redo();assert hist['histogram_settings']['scale']=='Percent'
    p.update_graph_styles(hist,{'p0:bars':{'fill':'#0088aa','edge':'#003344'},'p0:fit0':{'color':'#cc3311','line_width':3}});w.refresh()
    p.update_histogram_settings(hist,{'bins':6,'scale':'Density','fit':'Normal'});w.refresh()
    panel=chart.panels[0];assert abs(sum(panel['counts'])*(panel['edges'][1]-panel['edges'][0])-1)<1e-8
    p.update_histogram_settings(hist,{'bins':6,'scale':'Percent','cumulative':True,'fit':'Normal'});w.refresh()
    assert abs(chart.panels[0]['counts'][-1]-100)<1e-8
    assert chart.error is None and not w._active_graph_frame.capture().isNull()
    target=Path(temp)/'styled-objects-and-histogram.mpx';w.save_path(target);w.load_path(target)
    saved=next(e for e in p.history if 'histogram_settings' in e)
    assert saved['graph_styles']['p0:bars']['fill']=='#0088aa'
    rerun=p.rerun_result(saved);assert rerun['histogram_settings']==saved['histogram_settings'] and rerun['graph_styles']==saved['graph_styles']
    w.show_result(saved);app.processEvents();assert w._active_chart_widget.error is None
    checkpoint('graph appearance renderer coverage and 3D preservation')
    # Each implemented object descriptor must be usable by its renderer.
    for method,indices in (('line_plot',[0,1]),('bubble',[0,1,3]),('bar_chart',[2]),('interval_plot',[1]),('dotplot',[1])):
        entry=p.expanded_graph(method,indices);w.show_result(entry);app.processEvents()
        chart=w._active_chart_widget;objects=chart.editable_objects();assert objects
        styles={}
        for item in objects:
            style={};caps=item['capabilities']
            if 'color' in caps:style['color']='#0e7258'
            if 'fill' in caps:style['fill']='#96c7b1'
            if 'marker' in caps:style['marker']='diamond'
            if 'marker_size' in caps:style['marker_size']=10
            if 'line_style' in caps:style['line_style']='dot'
            styles[item['target']]=style
        p.update_graph_styles(entry,styles);w.refresh();chart.grab();assert chart.error is None
    xyz=p.expanded_graph('scatter3d',[0,1,3]);w.show_result(xyz);chart=w._active_chart_widget
    chart.rotate_view(20,-10);camera=dict(chart.view_state)
    p.update_graph_styles(xyz,{'p0:s0':{'color':'#bb2266','marker':'square','marker_size':9,'opacity':.7}})
    w.refresh();chart.grab();assert chart.view_state==camera and chart.error is None
