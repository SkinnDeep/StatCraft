"""Live multi-response mixture search, profile clicks and MPX source identity."""
import copy,math
from pathlib import Path
from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QToolButton
from .model import Column
from .app import Presenter,format_entry
from .mixture_multi_optimizer_dialog import MixtureMultiOptimizerDialog
from .mixture_multi_chart import MixtureMultiChart


def _click(app,widget,point=None):
    position=QPointF(widget.rect().center() if point is None else point)
    for kind,buttons in ((QEvent.Type.MouseButtonPress,Qt.MouseButton.LeftButton),(QEvent.Type.MouseButtonRelease,Qt.MouseButton.NoButton)):
        event=QMouseEvent(kind,position,QPointF(widget.mapToGlobal(position.toPoint())),Qt.MouseButton.LeftButton,buttons,Qt.KeyboardModifier.NoModifier)
        app.sendEvent(widget,event)


def populate(p):
    p.new();p.create_doe_plan(kind='simplex_lattice',factors=[dict(name=n,low=0,high=1) for n in ('Binder','Resin','Additive')],options={'degree':3},replicates=2,name='Multiple response mixture')
    for label,position in [('Strength',4),('Flexibility',6)]:
        p.worksheet.columns.append(Column(label,values=[10+40*p.worksheet.columns[position].values[row]+5*p.worksheet.columns[5].values[row]+.03*math.sin(row) for row in range(p.worksheet.row_count)]))
    models=[p.analyze_mixture(index,[4,5,6],model='linear') for index in (7,8)]
    responses=[dict(model_recipe=copy.deepcopy(entry['recipe']),goal='maximize',lower=10.,target=50.,upper=None,weight=1.,importance=1.) for entry in models]
    return models,responses


def verify_mixture_multi(app,p,w,temp,checkpoint):
    checkpoint('Multiple response mixture desirability, actual profile clicks/re-optimization and MPX source identity')
    models,specs=populate(p);w.refresh();app.processEvents()
    dialog=MixtureMultiOptimizerDialog(p.worksheet,models,w)
    for row in range(2):
        dialog.response_table.cellWidget(row,1).setCurrentIndex(0)
        for column,value in ((2,'10'),(3,'50'),(5,'1'),(6,'1')):dialog.response_table.item(row,column).setText(value)
    dialog.validate();assert dialog.result()==1,dialog.error.text()
    entry=p.optimize_mixture_multi(**dialog.parameters)
    assert .49<entry['result']['composite_desirability']<.51
    w.show_result(entry);app.processEvents();chart=w._active_chart_widget
    assert isinstance(chart,MixtureMultiChart) and chart.error is None and chart.profile_cells
    assert not chart.grab().isNull() and chart.error is None
    assert w.result_tabs.tabText(w.result_tabs.currentIndex())=='Graph'
    assert w._office_snapshot(entry).png and 'Log composite desirability' in format_entry(entry)
    from .graph_presentation import graph_presentation
    annotation=graph_presentation(entry);annotation['subtitle']='Interactive mixture study';annotation['subtitle_enabled']=True
    p.update_graph_presentation(entry,annotation);w.show_result(entry);app.processEvents();chart=w._active_chart_widget
    rect,profile=chart.profile_cells[0]
    _click(app,chart,QPoint(round(rect.left()+rect.width()*.25),round(rect.center().y())))
    app.processEvents();selected=p.history[-1]
    assert selected['recipe']['action']=='evaluate_mixture_multi' and selected['result']['analysis']=='mixture_multi_evaluation'
    assert abs(sum(selected['result']['components'])-1)<1e-12
    assert selected['graph_presentation']['subtitle']=='Interactive mixture study'
    assert w._active_chart_widget.panels[0]['setting_label']=='Selected Setting'
    button=w._active_graph_frame.findChild(QToolButton,'mixtureReoptimize');assert button is not None
    _click(app,button);app.processEvents();rerun=p.history[-1]
    assert rerun['recipe']['action']=='optimize_mixture_multi'
    assert rerun['result']['composite_desirability']>=selected['result']['composite_desirability']
    assert rerun['recipe']['parameters']['options']['start_values']==selected['result']['components']
    p.move_columns([8],'before_c1');p.rename_column(0,'Flexibility renamed');p.move_columns([5],'after_last')
    assert abs(p.rerun_result(entry)['result']['composite_desirability']-entry['result']['composite_desirability'])<1e-9
    assert abs(p.rerun_result(selected)['result']['composite_desirability']-selected['result']['composite_desirability'])<1e-9
    path=Path(temp)/'mixture-multi.mpx';p.save(path);q=Presenter();q.load(path)
    entries=[item for item in q.history if item.get('recipe',{}).get('action') in ('optimize_mixture_multi','evaluate_mixture_multi')]
    for item in entries:assert q.rerun_result(item)['result']['analysis']==item['result']['analysis']
    q.delete_columns([0])
    for item in entries:
        try:q.rerun_result(item)
        except ValueError:pass
        else:raise AssertionError('Deleted response source was reused')
    q.undo()
    for item in entries:q.rerun_result(item)
    dialog.deleteLater()
