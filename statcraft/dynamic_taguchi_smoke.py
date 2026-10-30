"""End-to-end dynamic Taguchi dialog, plotted signals and saved source contracts."""
import math
from pathlib import Path
from .app import Presenter,format_entry
from .model import Column
from .dynamic_taguchi_dialog import BuildAnalyzeDynamicTaguchiDialog
from .dynamic_taguchi_chart import DynamicTaguchiWidget


def populate(p):
    p.new();a=[-1,-1,1,1]*2;b=[-1,1,-1,1]*2
    p.worksheet.columns=[Column('Material','text',['Steel' if v==1 else 'Brass' for v in a]),Column('Pressure',values=b)]
    signals=[0.,0.,1.,1.,2.,2.];noise=[-.15,.17,.08,-.11,.12,-.09]
    for j,x in enumerate(signals):
        p.worksheet.columns.append(Column('Trial '+str(j+1),values=[2+.05*r+(2+.5*a[r]+.3*b[r]+.04*math.sin(r))*x+noise[j]*(1+.1*a[r]+.05*b[r]) for r in range(8)]))
    return signals


def verify_dynamic_taguchi(app,p,w,temp,checkpoint):
    checkpoint('Dynamic Taguchi slopes/SN, reference controls, actual signal plots and MPX source identity')
    signals=populate(p);w.refresh();app.processEvents()
    d=BuildAnalyzeDynamicTaguchiDialog(p.worksheet,w)
    d.controls['response_indices'].setText('C3 C4 C5 C6 C7 C8');d.controls['factor_indices'].setText('C1 C2')
    d.set_signal_values(signals);d.controls['show_signal_plots'].setChecked(True)
    d.validate();assert d.result()==1,d.error.text()
    entry=p.analyze_dynamic_taguchi(**d.parameters);assert entry['result']['n_runs']==8
    assert entry['result']['models']['slope'] is not None
    w.show_result(entry);app.processEvents();chart=w._active_chart_widget
    assert isinstance(chart,DynamicTaguchiWidget) and chart.signal_panel_count==8
    assert len(chart.panels)==14 and not chart.grab().isNull() and chart.error is None
    assert w.result_tabs.tabText(w.result_tabs.currentIndex())=='Graph'
    assert w._office_snapshot(entry).png and 'Slope' in format_entry(entry)
    expected=[row['slope'] for row in entry['result']['rows']]
    p.move_columns([4],'before_c1');p.rename_column(0,'Signal 1 trial renamed')
    assert p.rerun_result(entry)['result']['signal_values']==signals
    assert [row['slope'] for row in p.rerun_result(entry)['result']['rows']]==expected
    target=Path(temp)/'dynamic-taguchi.mpx';p.save(target);q=Presenter();q.load(target)
    saved=next(e for e in q.history if e.get('recipe',{}).get('action')=='analyze_dynamic_taguchi')
    assert [row['slope'] for row in q.rerun_result(saved)['result']['rows']]==expected
    q.delete_columns([0])
    try:q.rerun_result(saved)
    except ValueError:pass
    else:raise AssertionError('Deleted measurement source was reused')
    q.undo();q.rerun_result(saved);d.deleteLater()
