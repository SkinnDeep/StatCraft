"""Real mixture contour/optimizer dialogs, graphs, exports and source-bound MPX."""
import math
from pathlib import Path
from .app import Presenter,format_entry
from .model import Column
from .mixture_exploration_dialogs import MixtureContourDialog,MixtureOptimizerDialog
from .mixture_exploration_chart import MixtureExplorationChart


def populate(p):
    p.new();p.create_doe_plan(kind='simplex_lattice',factors=[dict(name=n,low=.1,high=.8) for n in ('Binder','Resin','Additive')],options={'degree':3},replicates=3,name='Mixture exploration')
    values=[]
    for row in range(p.worksheet.row_count):
        a,b,c=[p.worksheet.columns[i].values[row] for i in (4,5,6)]
        values.append(10*a+20*b+30*c+8*a*b-3*b*c+.05*math.sin(row))
    p.worksheet.columns.append(Column('Strength',values=values))
    return p.analyze_mixture(7,[4,5,6],model='quadratic')


def verify_mixture_exploration(app,p,w,temp,checkpoint):
    checkpoint('Mixture ternary slices and constrained optimizer: real dialogs, plots, source identity and MPX')
    fitted=populate(p);w.refresh();app.processEvents()
    d=MixtureContourDialog(p.worksheet,[fitted],w);d.resolution.setValue(16);d.validate()
    assert d.result()==1,d.error.text()
    contour=p.mixture_contour(**d.parameters);w.show_result(contour);app.processEvents()
    chart=w._active_chart_widget
    assert isinstance(chart,MixtureExplorationChart) and chart.band_polygons and chart.error is None
    assert w.result_tabs.tabText(w.result_tabs.currentIndex())=='Graph'
    assert not chart.grab().isNull() and chart.error is None
    assert w._office_snapshot(contour).png and 'Mixture Contour Plot' in format_entry(contour)
    p.update_graph_styles(contour,{'p0:ref0':{'color':'#aa3344','line_width':2.5}})
    optimizer=MixtureOptimizerDialog(p.worksheet,[fitted],w);optimizer.goal.setCurrentIndex(2);optimizer.target.setText('20');optimizer.validate()
    assert optimizer.result()==1,optimizer.error.text()
    optimum=p.optimize_mixture(**optimizer.parameters);assert optimum['result']['target_error']<1e-5
    w.show_result(optimum);app.processEvents();chart=w._active_chart_widget
    assert isinstance(chart,MixtureExplorationChart) and not chart.grab().isNull() and chart.error is None
    assert w._office_snapshot(optimum).png and 'Global optimum certified' in format_entry(optimum)
    expected=contour['result']['value_range'];target_value=optimum['result']['predicted_response']
    p.move_columns([5],'before_c1');p.rename_column(0,'Resin renamed')
    assert p.rerun_result(contour)['result']['value_range']==expected
    assert abs(p.rerun_result(optimum)['result']['predicted_response']-target_value)<1e-9
    path=Path(temp)/'mixture-exploration.mpx';p.save(path);q=Presenter();q.load(path)
    entries=[e for e in q.history if e.get('recipe',{}).get('action') in ('mixture_contour','optimize_mixture')]
    assert entries
    saved_contour=next(e for e in entries if e['recipe']['action']=='mixture_contour')
    assert saved_contour['graph_styles']['p0:ref0']['color']=='#aa3344'
    for e in entries:assert q.rerun_result(e)['result']['analysis']==e['result']['analysis']
    q.delete_columns([0])
    for e in entries:
        try:q.rerun_result(e)
        except ValueError:pass
        else:raise AssertionError('Deleted component source was reused')
    q.undo()
    for e in entries:q.rerun_result(e)
    # Exercise the independently packaged HiGHS path as well as nonlinear SLSQP.
    linear=p.analyze_mixture(fitted['recipe']['parameters']['response_index'],
        list(fitted['recipe']['parameters']['component_indices']),model='linear')
    lp=p.optimize_mixture(linear['recipe'])
    assert lp['result']['global_optimum_proven'] and lp['result']['method']=='Linear programming'
    d.deleteLater();optimizer.deleteLater()
