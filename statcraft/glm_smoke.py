"""Source/frozen acceptance for GLM menus, child dialogs, graphs and MPX reruns."""
from pathlib import Path
from PySide6.QtWidgets import QApplication,QTableWidget
from PySide6.QtCore import QTimer
from .model import Worksheet,Column
from .glm_dialogs import GeneralLinearModelDialog,ModelTermsDialog,ModelSettingsDialog
from .modern_charts import ChartWidget


def model_fixture():
    y=[];first=[];second=[];dose=[]
    for a in ['A','B']:
        for b in ['Low','High']:
            for x,error in zip([1,2,3,4,5],[-.3,.4,-.2,.2,-.1]):
                y.append(10+(3 if a=='B' else 0)+(2 if b=='High' else 0)+x*.7+(x*.3 if a=='B' else 0)+error)
                first.append(a);second.append(b);dose.append(x)
    return Worksheet('GLM measurements',[Column('Strength',values=y),Column('Material','text',first),Column('Temperature','text',second),Column('Dose',values=dose)])


def verify_general_linear_model(app,p,w,temp,checkpoint):
    checkpoint('GLM named roles, Model/Options/Coding/Graphs/Results, report tables, residual plots and MPX reruns')
    p.new();p.worksheet=model_fixture();w.page=0;w._show_welcome();w.refresh()
    dialog=GeneralLinearModelDialog(w);dialog.controls['response_index'].setText('C1');dialog.controls['factor_indices'].setText('C2 C3');dialog.controls['covariate_indices'].setText('C4')
    errors=[]
    def child(section):
        current=QApplication.activeModalWidget()
        if current is None:QTimer.singleShot(10,lambda:child(section));return
        try:
            if section=='Model':
                assert isinstance(current,ModelTermsDialog);current.order.setValue(2);current.add_order()
                current.selected.setCurrentRow(0);current.move(1);current.validate();assert not current.error.text()
            else:
                assert isinstance(current,ModelSettingsDialog)
                if section=='Options':current.controls['confidence'].setValue(90);current.controls['ss_type'][0].setCurrentIndex(1)
                elif section=='Coding':current.controls['coding'][0].setCurrentIndex(1);current.controls['standardize'][0].setCurrentIndex(1)
                elif section=='Graphs':current.controls['graphs'][0].setCurrentIndex(1)
                elif section=='Results':current.controls['diagnostics'][0].setCurrentIndex(2)
                current.validate()
        except Exception as exc:errors.append(str(exc));current.reject()
    for section in ['Model','Options','Coding','Graphs','Results']:
        QTimer.singleShot(0,lambda section=section:child(section));dialog.option_buttons[section].click();assert not errors,errors
    assert len(dialog.terms)==6 and dialog.options['confidence']==.9 and dialog.options['ss_type']=='sequential'
    dialog.validate();assert not dialog.error.text(),dialog.error.text();entry=dialog.entry
    assert entry and len(entry['result']['anova_terms'])==6 and len(entry['result']['diagnostics'])==20
    chart=w.findChildren(ChartWidget)[-1];assert chart.error is None and len(chart.panels)==4 and not chart.grab().isNull()
    areas=chart.panel_areas();assert areas[0].top()==areas[1].top() and areas[0].left()<areas[1].left() and areas[2].top()>areas[0].top() and areas[0].height()>250
    w.result_tabs.setCurrentIndex(0)
    tables=[t for t in w.findChildren(QTableWidget) if t.horizontalHeaderItem(0) and t.horizontalHeaderItem(0).text()=='Source']
    assert tables and any(t.rowCount()==8 for t in tables)
    again=GeneralLinearModelDialog(w);assert again.options==dialog.options and again.terms==dialog.terms and 'Material' in again.controls['factor_indices'].text();again.reject()
    path=Path(temp)/'glm-model.mpx';w.save_path(path);w.load_path(path);app.processEvents()
    own=[e for e in p.history if e.get('recipe',{}).get('action')=='general_linear_model'];assert len(own)==1 and not p.result_stale(own[0])
    w.show_result(own[0]);w.rerun_selected();assert p.history[-1]['result']['options']['graphs']=='four' and p.history[-1]['result']['count']==20
    chart=w.findChildren(ChartWidget)[-1];assert chart.error is None and len(chart.panels)==4
