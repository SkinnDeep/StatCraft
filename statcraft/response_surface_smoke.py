"""Source/frozen acceptance for real response-surface dialog workflows."""
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QTableWidgetItem
from .response_surface_dialogs import CreateSurfaceDialog,CreateSurfaceSettings,AnalyzeSurfaceDialog,SurfaceTermsDialog,SurfaceCodingDialog
from .model import Column
from .glm_dialogs import ModelSettingsDialog
from .modern_charts import ChartWidget


def add_measurements(sheet):
    a,b=sheet.columns[4].values,sheet.columns[5].values
    ca,cb=[c['center'] for c in sheet.metadata['doe']['factors']];ha,hb=[c['half_range'] for c in sheet.metadata['doe']['factors']]
    values=[]
    for i,(x,y) in enumerate(zip(a,b)):
        x=(x-ca)/ha;y=(y-cb)/hb;values.append(20+2*x-3*y+4*x*x+2*y*y+x*y+[-.2,.1,.2,-.1,0][i%5])
    sheet.columns.append(Column('Yield',values=values))


def verify_response_surface(app,p,w,temp,checkpoint):
    checkpoint('Response surface creation children, named analysis roles, quadratic terms, lack-of-fit, 2x2 graphs and MPX reruns')
    p.new();w.page=0;w._show_welcome();w.refresh();source=p.worksheet
    d=CreateSurfaceDialog(w);errors=[]
    def creation(section):
        child=QApplication.activeModalWidget()
        if child is None:QTimer.singleShot(10,lambda:creation(section));return
        try:
            assert isinstance(child,CreateSurfaceSettings)
            if section=='Designs':child.controls['centers'].setValue(5);child.controls['alpha_mode'].setCurrentIndex(1)
            elif section=='Factors':
                child.controls['factors'].setItem(0,0,QTableWidgetItem('Heat'));child.controls['factors'].setItem(1,0,QTableWidgetItem('Time'))
            elif section=='Options':child.controls['randomize'].setChecked(False);child.controls['seed'].setText('17')
            elif section=='Results':child.controls['display'].setCurrentIndex(2)
            child.validate();assert not child.error.text(),child.error.text()
        except Exception as exc:errors.append(str(exc));child.reject()
    for section in ['Display Available Designs','Designs','Factors','Options','Results']:
        QTimer.singleShot(0,lambda section=section:creation(section));d.option_buttons[section].click();assert not errors,errors
    d.validate();assert not d.error.text(),d.error.text();assert p.worksheet.row_count==13 and p.native_project.worksheets[0]==source
    assert len(d.entry['result']['design_table'])==13 and p.worksheet.metadata['doe']['alpha']==1
    add_measurements(p.worksheet);w.refresh();analysis=AnalyzeSurfaceDialog(w);assert 'Heat' in analysis.controls['factor_indices'].text();analysis.controls['response_index'].setText('C7')
    def configure(section):
        child=QApplication.activeModalWidget()
        if child is None:QTimer.singleShot(10,lambda:configure(section));return
        try:
            if section=='Terms':assert isinstance(child,SurfaceTermsDialog);child.validate();assert not child.error.text()
            elif section=='Low/High':assert isinstance(child,SurfaceCodingDialog);child.validate();assert not child.error.text()
            else:
                assert isinstance(child,ModelSettingsDialog)
                if section=='Graphs':child.controls['graphs'][0].setCurrentIndex(1)
                elif section=='Options':child.controls['confidence'].setValue(90)
                elif section=='Results':child.controls['diagnostics'][0].setCurrentIndex(2)
                child.validate()
        except Exception as exc:errors.append(str(exc));child.reject()
    for section in ['Terms','Low/High','Options','Graphs','Results']:
        QTimer.singleShot(0,lambda section=section:configure(section));analysis.option_buttons[section].click();assert not errors,errors
    analysis.validate();assert not analysis.error.text(),analysis.error.text();entry=analysis.entry
    assert len(entry['result']['coefficients'])==6 and entry['result']['pure_error']['df']==4
    chart=w.findChildren(ChartWidget)[-1];assert chart.error is None and len(chart.panels)==4 and chart.panel_columns==2 and not chart.grab().isNull()
    path=Path(temp)/'response-surface.mpx';w.save_path(path);w.load_path(path);app.processEvents();entry=next(e for e in p.history if e.get('recipe',{}).get('action')=='analyze_response_surface')
    w.show_result(entry);w.rerun_selected();assert not p.result_stale(w.selected_entry) and w.selected_entry['result']['count']==13
    again=AnalyzeSurfaceDialog(w);assert again.options['confidence']==.9 and len(again.terms)==5 and 'Yield' in again.controls['response_index'].text();again.reject()
