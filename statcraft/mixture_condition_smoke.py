"""Live coded holding values, conditional contours/optimization and saved sources."""
from pathlib import Path
from PySide6.QtCore import QPoint
from .app import Presenter,format_entry
from .mixture_process_smoke import populate,_click
from .mixture_condition_dialogs import MixtureProcessContourDialog,MixtureProcessOptimizerDialog
from .mixture_exploration_chart import MixtureExplorationChart
from .modern_charts import ChartWidget


def fitted(p):
    populate(p)
    return p.analyze_mixture_process(6,[0,1,2],[3],4,[5],model='quadratic',total=100.,options={'process_order':2})


def verify_mixture_condition(app,p,w,temp,checkpoint):
    checkpoint('Fixed coded process holds: actual conditional contours/optimizer, full-model CI/PI and MPX source identity')
    model=fitted(p);w.refresh();app.processEvents()
    diagnostic=ChartWidget(model);diagnostic.resize(1100,850);captured=[];original=diagnostic._text
    def text(painter,rect,label,*args,**kwargs):
        try:value=float(label)
        except (TypeError,ValueError):value=None
        if diagnostic._panel_index==3 and rect.width()==84 and value is not None:captured.append(value)
        return original(painter,rect,label,*args,**kwargs)
    diagnostic._text=text;diagnostic._panel_index=0
    assert not diagnostic.grab().isNull() and diagnostic.error is None and captured and all(value>=0 for value in captured)
    diagnostic.deleteLater()
    d=MixtureProcessContourDialog(p.worksheet,[model],w);d.resolution.setValue(16);d.condition_table.item(0,1).setText('.2')
    assert d.coded_process.isChecked() and abs(d.values()['process_values'][0]-80)<1e-12
    d.show();app.processEvents();_click(app,d.coded_process,QPoint(8,d.coded_process.height()//2))
    assert not d.coded_process.isChecked() and abs(float(d.condition_table.item(0,1).text())-80)<1e-12
    _click(app,d.coded_process,QPoint(8,d.coded_process.height()//2));assert d.coded_process.isChecked()
    d.validate();assert d.result()==1,d.error.text()
    contour=p.mixture_process_contour(**d.parameters);w.show_result(contour);app.processEvents();chart=w._active_chart_widget
    assert isinstance(chart,MixtureExplorationChart) and chart.band_polygons and not chart.grab().isNull() and chart.error is None
    assert contour['recipe']['parameters']['process_values']==[80.]
    assert w._office_snapshot(contour).png and 'Temperature' in format_entry(contour)
    o=MixtureProcessOptimizerDialog(p.worksheet,[model],w);o.condition_table.item(0,1).setText('.2');o.validate();assert o.result()==1,o.error.text()
    optimum=p.optimize_mixture_process(**o.parameters);row=optimum['result']['prediction'];fixed=optimum['result']['conditioning']
    direct=p.predict_mixture_process(model['recipe'],[optimum['result']['components']],[fixed['process_values']],[fixed['covariate_values']],[fixed['block_value']],optimum['result']['confidence'])['result']['rows'][0]
    for key in ('fit','standard_error','ci_low','ci_high','prediction_low','prediction_high'):assert abs(row[key]-direct[key])<1e-8
    w.show_result(optimum);app.processEvents();assert isinstance(w._active_chart_widget,MixtureExplorationChart)
    assert not w._active_chart_widget.grab().isNull() and w._active_chart_widget.error is None and w._office_snapshot(optimum).png
    value=optimum['result']['predicted_response'];interval=contour['result']['value_range']
    p.move_columns([3],'before_c1');p.rename_column(0,'Temperature renamed');p.move_columns([5],'after_last')
    assert p.rerun_result(contour)['result']['value_range']==interval
    assert abs(p.rerun_result(optimum)['result']['predicted_response']-value)<1e-9
    path=Path(temp)/'mixture-condition.mpx';p.save(path);q=Presenter();q.load(path)
    entries=[e for e in q.history if e.get('recipe',{}).get('action') in ('mixture_process_contour','optimize_mixture_process')]
    for e in entries:assert q.rerun_result(e)['result']['conditioning']['process_values']==[80.]
    q.delete_columns([0])
    for e in entries:
        try:q.rerun_result(e)
        except ValueError:pass
        else:raise AssertionError('Deleted fixed-process source was reused')
    q.undo()
    for e in entries:q.rerun_result(e)
    d.deleteLater();o.deleteLater()
