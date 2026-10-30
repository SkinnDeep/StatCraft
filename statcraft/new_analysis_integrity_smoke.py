"""Real-window acceptance for the repaired preview70–77 integrations."""
from pathlib import Path
from .model import Worksheet,Column
from .app import Presenter,format_entry
from .msa_dialogs import GageRRNestedDialog


def verify_new_analysis_integrity(app,p,w,temp,checkpoint):
    checkpoint('New quality/reliability: actual charts, source identity, valid statistics and MPX')
    p.new()
    parts=['P1']*3+['P2']*3+['P3']*3+['P4']*3
    operators=['A']*6+['B']*6
    values=[10.1,10.2,10.05,12.2,12.3,12.1,14.3,14.4,14.2,16.3,16.5,16.4]
    truth=['Pass']*3+['Fail']*3+['Pass']*3+['Fail']*3
    p.worksheet=Worksheet('Advanced Quality',[
        Column('Parts','text',parts),Column('Operator','text',operators),Column('Measured',values=values),
        Column('Reference',values=[10.]*3+[12.]*3+[14.]*3+[16.]*3),Column('Rating','text',truth),
        Column('Standard','text',truth),Column('Lifetime',values=[12,18,None,25,29,33,41,46,52,64,75,91]),
        Column('Samples','text',['S1']*3+['S2']*3+['S1']*3+['S2']*3),
        Column('Event',values=[1,0,1,1,1,1,0,1,1,1,1,0])])
    w.refresh();app.processEvents()
    dialog=GageRRNestedDialog(p.worksheet,w)
    dialog.edit_part.setText('C1');dialog.edit_op.setText('C2');dialog.edit_meas.setText('C3')
    dialog._on_ok();assert dialog.selected_params['measurement_col']==2
    entries=[
      (p.nested_gage_rr(**dialog.selected_params),'NestedGageRRChartWidget'),
      (p.gage_linearity(reference_col=3,measurement_col=2,process_variation=12),'GageLinearityChartWidget'),
      (p.attribute_agreement(attribute_col=4,sample_col=7,appraiser_col=1,standard_col=5),'AttributeAgreementChartWidget'),
      (p.reliability_distribution(settings={'column_index':6,'censor_index':8,'dist_name':'exponential'}),'ReliabilityPlotWidget'),
      (p.capability_nonparametric(settings={'column_index':2,'lsl':8,'usl':19}),'NonparametricCapabilityPlotWidget'),
      (p.capability_automated(settings={'column_index':2,'lsl':8,'usl':19}),'NonparametricCapabilityPlotWidget'),
      (p.capability_nonnormal(settings={'column_index':2,'lsl':8,'usl':19,'dist_or_transform':'lognormal'}),'NonnormalCapabilityPlotWidget')]
    for entry,name in entries:
        w.show_result(entry);app.processEvents()
        assert type(w._active_chart_widget).__name__==name
        assert w.result_tabs.tabText(w.result_tabs.currentIndex())=='Graph'
        assert not w._active_chart_widget.grab().isNull()
        assert format_entry(entry)
        snapshot=w._office_snapshot(entry);assert snapshot.png and snapshot.report
    reliability=entries[3][0]['result'];assert reliability['n_total']==11 and reliability['n_events']==8
    assert reliability['row_indices']==[0,1,3,4,5,6,7,8,9,10,11]
    assert reliability['ad_stat'] is None
    assert all(row['p_val'] is None for row in entries[5][0]['result']['tournament'])
    source_entries=[entry for entry,_ in entries]
    p.move_columns([2],'before_c1');p.rename_column(0,'Measured renamed')
    for entry in source_entries:assert p.rerun_result(entry)['result']['analysis']==entry['result']['analysis']
    p.move_columns([8],'before_c1')
    assert p.rerun_result(source_entries[3])['result']['n_events']==8
    target=Path(temp)/'advanced-integrity.mpx';p.save(target)
    q=Presenter();q.load(target)
    for entry in list(q.history):q.rerun_result(entry)
    q.delete_columns([0])
    affected=next(entry for entry in q.history if entry.get('recipe',{}).get('action')=='reliability_distribution')
    try:q.rerun_result(affected)
    except ValueError:pass
    else:raise AssertionError('A deleted censor column was silently reused')
    q.undo();q.rerun_result(affected)
    dialog.deleteLater()
