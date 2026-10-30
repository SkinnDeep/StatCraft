"""End-to-end mixture and static Taguchi analysis in source/frozen windows."""
import copy
import math
from pathlib import Path
from .app import Presenter,format_entry
from .model import Column
from .doe_analysis_dialogs import BuildAnalyzeMixtureDialog,BuildAnalyzeTaguchiDialog
from .mixture_prediction_dialog import MixturePredictionDialog
from .modern_charts import ChartWidget
from .doe_analysis_charts import TaguchiEffectsWidget


def verify_mixture_taguchi(app,p,w,temp,checkpoint):
    checkpoint('Mixture fitting/predictions and static Taguchi: dialogs, real plots, source identity and MPX')
    p.new()
    p.create_doe_plan(kind='simplex_lattice',factors=[{'name':name,'low':0,'high':1} for name in ('Binder','Resin','Additive')],options={'degree':3},replicates=3,name='Mixture study')
    response=[]
    for row in range(p.worksheet.row_count):
        a,b,c=[p.worksheet.columns[index].values[row] for index in (4,5,6)]
        response.append(10*a+20*b+30*c+12*a*b-3*a*c+4*b*c+.1*math.sin(row*1.7))
    response[5]=None;p.worksheet.columns.append(Column('Strength',values=response));w.refresh();app.processEvents()
    dialog=BuildAnalyzeMixtureDialog(p.worksheet,w)
    assert 'Binder' in dialog.controls['component_indices'].text()
    dialog.controls['response_index'].setText('C8');dialog.validate();assert dialog.result()==1,dialog.error.text()
    entry=p.analyze_mixture(**dialog.parameters);assert entry['result']['count']==29
    w.show_result(entry);app.processEvents();chart=w._active_chart_widget
    assert isinstance(chart,ChartWidget) and chart.error is None and len(chart.panels)==4
    assert w.result_tabs.tabText(w.result_tabs.currentIndex())=='Graph'
    assert not chart.grab().isNull() and chart.error is None
    assert w._office_snapshot(entry).png and 'Coefficients' in format_entry(entry)
    prediction=MixturePredictionDialog(p.worksheet,[entry],w)
    from PySide6.QtWidgets import QTableWidgetItem
    for i,value in enumerate((.3,.3,.4)):prediction.table.setItem(0,i,QTableWidgetItem(str(value)))
    prediction.validate();assert prediction.result()==1,prediction.error.text()
    predicted=p.predict_mixture(**prediction.parameters)
    row=predicted['result']['rows'][0];assert row['prediction_low']<row['ci_low']<row['fit']<row['ci_high']<row['prediction_high']
    assert 'Mixture prediction' in format_entry(predicted)
    original=entry['result']['fitted'];p.move_columns([5],'before_c1');p.rename_column(0,'Resin renamed')
    assert max(abs(a-b) for a,b in zip(original,p.rerun_result(entry)['result']['fitted']))<1e-10
    assert abs(p.rerun_result(predicted)['result']['rows'][0]['fit']-row['fit'])<1e-10
    p.create_doe_plan(kind='taguchi',factors=[{'name':name,'kind':'number','levels':[-1,1]} for name in ('Speed','Pressure','Temperature')],replicates=2,options={'array':'L8'},name='Taguchi study')
    for trial in range(3):
        values=[]
        for at in range(p.worksheet.row_count):
            a,b,c=[p.worksheet.columns[index].values[at] for index in (4,5,6)]
            values.append(20+5*a-2*b+3*c+(trial-1)*(.2+.08*b)+.03*math.sin(at+trial))
        p.worksheet.columns.append(Column('Response '+str(trial+1),values=values))
    p.worksheet.columns[8].values[3]=None
    w.refresh();app.processEvents();d=BuildAnalyzeTaguchiDialog(p.worksheet,w)
    assert 'Speed' in d.controls['factor_indices'].text()
    d.controls['response_indices'].setText('C8 C9 C10');d.validate();assert d.result()==1,d.error.text()
    tag=p.analyze_taguchi(**d.parameters);assert tag['result']['n_runs']==15
    assert tag['result']['models']['mean'] is not None
    w.show_result(tag);app.processEvents();chart=w._active_chart_widget
    assert isinstance(chart,TaguchiEffectsWidget) and len(chart.panels)==9
    assert not chart.grab().isNull() and chart.error is None
    assert w._office_snapshot(tag).png and 'Response Table' in format_entry(tag)
    p.move_columns([8],'before_c1');p.rename_column(0,'Trial renamed')
    updated=p.rerun_result(tag)['result']['response_tables']
    for metric,table in updated.items():
        assert [[level['value'] for level in factor['levels']] for factor in table['factors']]==[[level['value'] for level in factor['levels']] for factor in tag['result']['response_tables'][metric]['factors']]
    target=Path(temp)/'mixture-taguchi.mpx';p.save(target);q=Presenter();q.load(target)
    for saved in list(q.history):
        action=saved.get('recipe',{}).get('action')
        if action in ('analyze_mixture','analyze_taguchi','predict_mixture'):
            rerun=q.rerun_result(saved)
            assert rerun['result']['analysis']==saved['result']['analysis']
    affected=next(e for e in q.history if e.get('recipe',{}).get('action')=='analyze_taguchi')
    q.select_worksheet(q.native_project.worksheets.index(q.result_worksheet(affected)))
    q.delete_columns([0])
    try:q.rerun_result(affected)
    except ValueError:pass
    else:raise AssertionError('Deleted Taguchi measurement source was reused')
    q.undo();q.rerun_result(affected)
    dialog.deleteLater();prediction.deleteLater();d.deleteLater()
