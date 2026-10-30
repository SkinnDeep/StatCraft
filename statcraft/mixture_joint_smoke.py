"""Source/frozen acceptance for complete joint mixture/process optimization."""
from pathlib import Path
from PySide6.QtWidgets import QTableWidgetItem
from .app import Presenter,format_entry
from .mixture_process_smoke import populate
from .mixture_process_model import predict
from .mixture_joint_dialog import MixtureJointOptimizerDialog
from .mixture_joint_chart import MixtureJointChart


def verify_mixture_joint(app,p,w,temp,checkpoint):
    checkpoint('Joint mixture/process optimizer: live bounds and fixed roles, original-model CI/PI, profiles, Office and source-bound MPX')
    from .modern_app import ModernWindow
    q=Presenter();populate(q);fit=q.analyze_mixture_process(6,[0,1,2],[3],4,[5],model='quadratic',total=100.,options={'process_order':2})
    viewer=ModernWindow(q);viewer.show();viewer.refresh();d=MixtureJointOptimizerDialog(q.worksheet,[fit],viewer);d.show();app.processEvents()
    assert 'Temperature' in d.process_table.item(0,0).text() and 'Binder' in d.component_table.item(0,0).text()
    d.process_table.setItem(0,1,QTableWidgetItem('60'));d.process_table.setItem(0,2,QTableWidgetItem('90'));d.starts.setValue(6);d.validate();assert d.result()==1,d.error.text()
    entry=q.optimize_mixture_joint(**d.parameters);r=entry['result'];assert r['converged'] and abs(sum(r['components'])-100)<1e-8 and abs(r['processes'][0]-90)<.01
    expected=predict(fit['result'],[r['components']],[r['processes']],[r['covariate_values']],[r['block_value']],r['confidence'])['rows'][0]
    assert r['prediction']==expected and expected['prediction_low']<expected['ci_low']<expected['fit']<expected['ci_high']<expected['prediction_high']
    viewer.show_result(entry);app.processEvents();chart=viewer._active_chart_widget
    assert isinstance(chart,MixtureJointChart) and not viewer._active_graph_frame.capture().isNull() and chart.error is None
    chart.grab();assert chart.hover_regions and viewer._office_snapshot(entry).png and 'Held block' in format_entry(entry)
    old=r['predicted_response'];q.move_columns([3],'before_c1');q.rename_column(0,'Temperature revised')
    assert entry['recipe']['parameters']['model_recipe']['parameters']['process_indices']==[0]
    assert abs(q.rerun_result(entry)['result']['predicted_response']-old)<1e-8
    path=Path(temp)/'mixture-joint.mpx';q.save(path);restored=Presenter();restored.load(path)
    saved=next(e for e in reversed(restored.history) if e.get('recipe',{}).get('action')=='optimize_mixture_joint')
    assert not restored.result_stale(saved) and abs(restored.rerun_result(saved)['result']['predicted_response']-old)<1e-8
    process=saved['recipe']['parameters']['model_recipe']['parameters']['process_indices'][0];restored.delete_columns([process])
    try:restored.rerun_result(saved)
    except ValueError:pass
    else:raise AssertionError('Deleted joint optimizer source was reused.')
    restored.undo();restored.rerun_result(saved)
    viewer.presenter.dirty=False;viewer.presenter._results_dirty=False;viewer.close();viewer.deleteLater();d.deleteLater()
