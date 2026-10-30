"""Source/frozen acceptance for mixture/process fitting and prediction roles."""
import math
from pathlib import Path
from PySide6.QtCore import Qt,QPointF,QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QTableWidgetItem
from .app import Presenter,format_entry
from .model import Column
from .mixture_process_dialogs import MixtureProcessDialog,MixtureProcessPredictionDialog
from .modern_charts import ChartWidget


def _click(app,widget,point=None):
    position=QPointF(widget.rect().center() if point is None else point)
    for kind,buttons in ((QEvent.Type.MouseButtonPress,Qt.MouseButton.LeftButton),(QEvent.Type.MouseButtonRelease,Qt.MouseButton.NoButton)):
        app.sendEvent(widget,QMouseEvent(kind,position,QPointF(widget.mapToGlobal(position.toPoint())),Qt.MouseButton.LeftButton,buttons,Qt.KeyboardModifier.NoModifier))


def populate(p):
    p.new();data=[[] for unused in range(7)];row=0
    for a in range(4):
        for b in range(4-a):
            c=3-a-b
            for temperature in (50.,75.,100.):
                for block in ('Morning','Evening'):
                    for moisture in (4.,6.,8.):
                        aa,bb,cc=a/3,b/3,c/3;z=(temperature-75)/25;v=(moisture-6)/2
                        y=10*aa+20*bb+30*cc+(2*aa-3*bb+4*cc)*z+5*v+(7 if block=='Evening' else 0)+.04*math.sin(row)
                        for column,value in zip(data,[aa*100,bb*100,cc*100,temperature,block,moisture,y]):column.append(value)
                        row+=1
    p.worksheet.columns=[Column(name,'text' if i==4 else 'number',data[i]) for i,name in enumerate(('Binder','Resin','Additive','Temperature','Shift','Moisture','Strength'))]
    p.worksheet.columns[5].values[5]=None


def verify_mixture_process(app,p,w,temp,checkpoint):
    checkpoint('Mixture × process model, fixed block/covariate roles, live residuals/predictions and MPX source identity')
    populate(p);w.refresh();app.processEvents();d=MixtureProcessDialog(p.worksheet,w);d.show();app.processEvents()
    _click(app,d.controls['response_index']);app.processEvents()
    item=next(d.available.item(i) for i in range(d.available.count()) if d.available.item(i).data(Qt.ItemDataRole.UserRole)==6)
    _click(app,d.available.viewport(),d.available.visualItemRect(item).center());_click(app,d.select_button)
    assert 'Strength' in d.controls['response_index'].text()
    for key,value in [('component_indices','C1 C2 C3'),('process_indices','C4'),('block_index','C5'),('covariate_indices','C6')]:d.controls[key].setText(value)
    d.controls['model'].setCurrentText('Linear');d.controls['total'].setText('100');d.validate();assert d.result()==1,d.error.text()
    entry=p.analyze_mixture_process(**d.parameters);assert entry['result']['count']==179
    assert entry['recipe']['parameters']['options']['process_coding']==[{'low':50.,'high':100.}]
    assert entry['recipe']['parameters']['options']['covariate_coding']==[{'low':4.,'high':8.}]
    w.show_result(entry);app.processEvents();chart=w._active_chart_widget
    assert isinstance(chart,ChartWidget) and len(chart.panels)==4 and not chart.grab().isNull() and chart.error is None
    assert w.result_tabs.tabText(w.result_tabs.currentIndex())=='Graph'
    assert 6 not in chart.panels[1]['row_indices'] and w._office_snapshot(entry).png
    assert 'Process coding for Temperature' in format_entry(entry)
    prediction=MixtureProcessPredictionDialog(p.worksheet,[entry],w)
    for i,value in enumerate((20.,30.,50.,80.,6.)):prediction.table.setItem(0,i,QTableWidgetItem(str(value)))
    combo=prediction.table.cellWidget(0,5);combo.setCurrentIndex(combo.findData('Morning'))
    prediction.validate();assert prediction.result()==1,prediction.error.text()
    predicted=p.predict_mixture_process(**prediction.parameters);result=predicted['result']['rows'][0]
    assert result['prediction_low']<result['ci_low']<result['fit']<result['ci_high']<result['prediction_high']
    assert 'Morning' in format_entry(predicted)
    old_fit=entry['result']['fitted'];p.move_columns([3],'before_c1');p.rename_column(0,'Temperature renamed');p.move_columns([5],'after_last')
    assert p.rerun_result(entry)['result']['fitted']==old_fit
    assert abs(p.rerun_result(predicted)['result']['rows'][0]['fit']-result['fit'])<1e-9
    path=Path(temp)/'mixture-process.mpx';p.save(path);q=Presenter();q.load(path)
    entries=[e for e in q.history if e.get('recipe',{}).get('action') in ('analyze_mixture_process','predict_mixture_process')]
    for e in entries:assert q.rerun_result(e)['result']['analysis']==e['result']['analysis']
    q.delete_columns([0])
    for e in entries:
        try:q.rerun_result(e)
        except ValueError:pass
        else:raise AssertionError('Deleted process source was reused')
    q.undo()
    for e in entries:q.rerun_result(e)
    d.deleteLater();prediction.deleteLater()
