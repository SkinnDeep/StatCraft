"""Crossed Gage R&R desktop and frozen-package acceptance."""
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from .model import Column,Worksheet
from .gage_rr_dialogs import GageRRDialog,GageRROptionsDialog
from .modern_charts import ChartWidget


def fixture():
    measurements=[];parts=[];operators=[]
    for part in range(1,11):
        for op_index,operator in enumerate(['Alex','Blair','Casey']):
            for repeat,error in enumerate([-.12,.02,.1]):
                measurements.append(20+part*.45+op_index*.08+error+((part+op_index)%3-1)*.015)
                parts.append(part);operators.append(operator)
    return Worksheet('Crossed gage study',[Column('Part',values=parts),Column('Operator','text',operators),Column('Diameter',values=measurements)])


def verify_gage_rr(app,p,w,temp,checkpoint):
    checkpoint('Crossed Gage R&R roles, options, six graphs, row links, MPX and column moves')
    p.new();p.worksheet=fixture();w.page=0;w.refresh()
    d=GageRRDialog(w)
    for key,value in dict(part_index='C1',operator_index='C2',measurement_index='C3').items():d.controls[key].setText(value)
    assert 'Part' in d.available.item(0).text()
    errors=[]
    def options():
        child=QApplication.activeModalWidget()
        if child is None:QTimer.singleShot(10,options);return
        try:
            assert isinstance(child,GageRROptionsDialog)
            child.controls['tolerance'].setText('3.0');child.controls['study_multiplier'].setText('5.15')
            child.validate();assert not child.error.text(),child.error.text()
        except Exception as exc:errors.append(str(exc));child.reject()
    QTimer.singleShot(0,options);d.options_button.click();assert not errors,errors
    d.validate();assert not d.error.text(),d.error.text();entry=d.entry
    assert entry['result']['n']==90 and entry['result']['options']['tolerance']==3
    assert w.result_tabs.tabText(w.result_tabs.currentIndex())=='Graph'
    chart=w._active_chart_widget;assert isinstance(chart,ChartWidget) and chart.error is None and len(chart.panels)==6 and chart.panel_columns==2
    chart.resize(1250,1120);assert not chart.grab().isNull()
    assert {row for row,_ in chart.brush_regions}==set(range(1,91))
    from .app import format_entry
    text=format_entry(entry);assert 'Variance Components' in text and 'Gage Evaluation' in text and 'plot_data' not in text
    path=Path(temp)/'gage-rr.mpx';w.save_path(path);w.load_path(path);app.processEvents()
    entry=next(e for e in p.history if e.get('recipe',{}).get('action')=='gage_rr')
    w.show_result(entry);w.rerun_selected();assert w.selected_entry['result']['n']==90 and not p.result_stale(w.selected_entry)
    entry=w.selected_entry;p.move_columns([2],destination='before_c1')
    assert entry['recipe']['parameters']['measurement_index']==0 and entry['recipe']['parameters']['part_index']==1
    rerun=p.rerun_result(entry);assert rerun['result']['variance_components']==entry['result']['variance_components']
    again=GageRRDialog(w);assert 'Diameter' in again.controls['measurement_index'].text() and again.options['study_multiplier']==5.15;again.reject()
    p.dirty=False;p._results_dirty=False
