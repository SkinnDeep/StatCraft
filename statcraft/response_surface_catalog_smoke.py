"""Real catalog selection, blocked RSM inference and source-bound persistence."""
import math
from pathlib import Path
from PySide6.QtCore import Qt
from .response_surface_catalog import catalog
from .response_surface import create
from .response_surface_dialogs import CreateSurfaceDialog,CreateSurfaceSettings,AnalyzeSurfaceDialog
from .mixture_process_smoke import _click
from .model import Column
from .app import Presenter
from .prediction import model_spec


def verify_surface_catalog(app,p,w,temp,checkpoint):
    checkpoint('58 real response-surface catalog choices, matrix mouse selection, fixed-block fits, prediction, contours and MPX')
    for spec in catalog():
        factors=[dict(name=chr(65+i),low=-1.,high=1.) for i in range(spec['factors'])]
        s=create(factors,kind=spec['kind'],fraction=spec['fraction'],blocks=spec['blocks'],centers=spec['centers'],center_cube=spec['center_cube'],center_axial=spec['center_axial'],alpha_mode='default',randomize=False)
        assert s.row_count==spec['runs'] and len(set(s.columns[3].values))==spec['blocks']
    from .modern_app import ModernWindow
    viewer=ModernWindow();viewer.show();d=CreateSurfaceDialog(viewer);c=CreateSurfaceSettings(d,'Display Available Designs');c.show();app.processEvents()
    table=c.available_table;item=table.item(5,5);_click(app,table.viewport(),table.visualItemRect(item).center());c.validate()
    spec=c.changes['selected_design'];assert spec['fraction']==2 and spec['factors']==5 and spec['blocks']==2 and spec['runs']==33
    d.apply_design(spec);d.name.setText('Blocked response surface catalog');d.validate();assert not d.error.text(),d.error.text()
    q=viewer.presenter;s=q.worksheet;assert s.row_count==33 and len(s.columns)==9
    data=list(zip(*(col.values for col in s.columns[4:])))
    s.columns.append(Column('Yield',values=[40+sum((j+1)*x+.2*x*x for j,x in enumerate(row))+.5*row[0]*row[1]+3*s.columns[3].values[i]+.05*math.sin(i+1) for i,row in enumerate(data)]))
    viewer.refresh();analysis=AnalyzeSurfaceDialog(viewer);analysis.controls['response_index'].setText('C10');analysis.validate();assert not analysis.error.text(),analysis.error.text()
    fit=analysis.entry;assert fit['recipe']['parameters']['block_index']==3 and fit['result']['anova_terms'][0]['source']=='Blocks'
    preds=model_spec(s,fit['recipe']);assert preds['predictor_indices']==[3,4,5,6,7,8]
    prediction=q.predict_model(fit['recipe'],values=[[1,0.,0.,0.,0.,0.],[2,0.,0.,0.,0.,0.]])
    assert abs(prediction['result']['rows'][1]['fit']-prediction['result']['rows'][0]['fit']-3)<.05
    contour=q.model_contour_plot(fit['recipe'],4,5);surface=q.model_surface_plot(fit['recipe'],4,5)
    for entry in (contour,surface):
        viewer.show_result(entry);app.processEvents();assert not viewer._active_graph_frame.capture().isNull()
        assert any(h['name']=='Blocks' for h in entry['result']['hold_summary'])
    original=list(fit['result']['fitted']);q.move_columns([3],'before_column',0)
    assert fit['recipe']['parameters']['block_index']==0 and not q.result_stale(fit)
    assert max(abs(a-b) for a,b in zip(q.rerun_result(fit)['result']['fitted'],original))<1e-9
    q.undo();path=Path(temp)/'surface-catalog.mpx';q.save(path);restored=Presenter();restored.load(path)
    source=next(e for e in restored.history if e.get('recipe',{}).get('action')=='analyze_response_surface')
    assert source['recipe']['parameters']['block_index']==3 and not restored.result_stale(source)
    restored.rerun_result(source)
    viewer.presenter.dirty=False;viewer.presenter._results_dirty=False;viewer.close();viewer.deleteLater();d.deleteLater();c.deleteLater();analysis.deleteLater()
