"""Source/frozen prediction dialogs, dependency remapping and MPX acceptance."""
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QDialog,QTableWidgetItem
from .model import Column,Worksheet
from .prediction_dialogs import PredictDialog,PredictOptionsDialog,PredictResultsDialog
from .prediction import settings
from .app import format_entry


def fixture():
    return Worksheet('Regression predictions',[Column('Time',values=[1,2,3,4,5,6]),Column('Strength',values=[2.1,4.2,5.8,8.1,9.9,12.2]),Column('New time',values=[2.5,None,7.])])


def verify_prediction(app,p,w,temp,checkpoint):
    checkpoint('Predict manual/column inputs, options/results/model, GLM/RSM intervals, MPX and nested source remapping')
    p.new();p.worksheet=fixture();w.page=0;w.refresh()
    assert not any(a.isEnabled() for a in w.predict_actions.values())
    p.inference('linear_regression',[0,1]);w.refresh();assert w.predict_actions['multiple_regression'].isEnabled()
    d=PredictDialog(w,'regression');assert d.model_recipe['action']=='multiple_regression'
    d.values_grid.setItem(0,0,QTableWidgetItem('2.5'));d.values_grid.setItem(1,0,QTableWidgetItem('7'))
    errors=[]
    def child(section):
        c=QApplication.activeModalWidget()
        if c is None:QTimer.singleShot(10,lambda:child(section));return
        try:
            if section=='options':
                assert isinstance(c,PredictOptionsDialog);c.confidence.setText('90');c.side.setCurrentIndex(c.side.findData('lower'));c.validate();assert not c.error.text()
            elif section=='results':assert isinstance(c,PredictResultsDialog);c.equation.setChecked(True);c.validate()
            else:assert isinstance(c,QDialog) and 'Time' in d.model_description();c.reject()
        except Exception as exc:errors.append(str(exc));c.reject()
    for section,button in [('options',d.options_button),('results',d.results_button),('model',d.model_button)]:
        QTimer.singleShot(0,lambda section=section:child(section));button.click();assert not errors,errors
    d.validate();assert not d.error.text(),d.error.text();entry=d.entry
    assert entry['result']['rows'][1]['extrapolated'] and entry['result']['rows'][0]['ci_high'] is None
    assert w.result_tabs.tabText(w.result_tabs.currentIndex())=='Report'
    assert 'Regression Equation' in format_entry(entry) and '90% CI Lower' in format_entry(entry)
    d=PredictDialog(w,'regression');assert d.options['confidence']==.9
    d.input_mode.setCurrentIndex(d.input_mode.findData('columns'));d.columns_grid.setCurrentCell(0,0)
    item=next(d.available.item(i) for i in range(d.available.count()) if 'New time' in d.available.item(i).text());d.available.setCurrentItem(item);d.select_button.click()
    d.validate();assert not d.error.text(),d.error.text();entry=d.entry;assert entry['result']['missing']==1
    path=Path(temp)/'predictions.mpx';w.save_path(path);w.load_path(path);app.processEvents()
    entry=next(e for e in reversed(p.history) if e.get('recipe',{}).get('action')=='predict_model')
    w.show_result(entry);w.rerun_selected();entry=w.selected_entry;assert not p.result_stale(entry)
    p.move_columns([0],destination='after_last');rerun=p.rerun_result(entry);assert rerun['result']['rows']==entry['result']['rows']
    assert entry['recipe']['parameters']['model_recipe']['parameters']['predictor_indices']==[2]
    restored=PredictDialog(w,'regression');assert restored.input_mode.currentData()=='columns' and 'New time' in restored.columns_grid.item(0,0).text();restored.reject()
    from .glm_smoke import model_fixture
    p.new();p.worksheet=model_fixture();model=p.general_linear_model(0,[1,2],[3],[[0],[1],[2],[0,2]])
    glm_entry=p.predict_model(model['recipe'],values=[['A','Low',2.5],['B','High',4.]])
    assert all(row['pi_low']<row['ci_low']<row['fit']<row['ci_high']<row['pi_high'] for row in glm_entry['result']['rows'])
    from .response_surface import create
    from .response_surface_smoke import add_measurements
    p.new();p.worksheet=create([dict(name='Heat',low=100.,high=140.),dict(name='Time',low=20.,high=40.)],alpha_mode='face',randomize=False);add_measurements(p.worksheet)
    model=p.analyze_response_surface(6,[4,5]);surface=p.predict_model(model['recipe'],values=[[120.,30.],[130.,35.]])
    assert len(surface['result']['rows'])==2 and all(row['se_fit']>0 for row in surface['result']['rows'])
    w.refresh();w.show_result(surface);assert w.result_tabs.tabText(w.result_tabs.currentIndex())=='Report'
    snapshot=w._office_snapshot(surface);assert not snapshot.png and 'Predictions' in snapshot.report
    p.dirty=False;p._results_dirty=False
