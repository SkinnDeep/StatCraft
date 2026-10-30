"""End-to-end multiple-variable capability in source and frozen applications."""
import math
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
from xml.etree import ElementTree as ET
from .model import Worksheet,Column
from .app import Presenter,format_entry
from .multiple_capability_dialogs import MultipleCapabilityDialog,MultipleCapabilityOptionsDialog
from .multiple_capability_chart import MultipleCapabilityChartWidget


def verify_multiple_capability(app,p,w,temp,checkpoint):
    checkpoint('Multiple Variables capability: native roles, real charts, Office, source edits and MPX')
    p.new()
    p.worksheet=Worksheet('Multiple Capability',[
        Column('Length',values=[10+math.sin(i*.7)*.8+i*.001 for i in range(48)]),
        Column('Weight',values=[20+math.cos(i*.6)*1.2+i*.002 for i in range(48)]),
        Column('Machine','text',['A']*24+['B']*24),
        Column('Subgroup','text',[str(i//3) for i in range(48)])])
    w.refresh();app.processEvents()
    entries=[]
    for method in ('normal','nonnormal'):
        d=MultipleCapabilityDialog(p.worksheet,method,w)
        assert any('Length' in d.col_list.item(i).text() for i in range(d.col_list.count()))
        d.edit_variables.setText('C1 C2');d.edit_lower.setText('7 16');d.edit_upper.setText('13 24');d.edit_targets.setText('10 20')
        if method=='normal':
            d.edit_subgroup_sizes.setText('2 3')
            options=MultipleCapabilityOptionsDialog(parent=d)
            options.controls['include_ci'].setChecked(True)
            options.controls['ci_type'].setCurrentIndex(1)
            options._on_ok();assert options.result()==1,options.error.text()
            d.options=options.selected_options;options.deleteLater()
        else:d.distribution.setCurrentIndex(d.distribution.findData('lognormal'))
        d._on_ok();assert d.result()==1,d.error.text()
        entry=p.multiple_capability(**d.parameters);entries.append(entry)
        assert len(entry['result']['series'])==2
        w.show_result(entry);app.processEvents()
        assert isinstance(w._active_chart_widget,MultipleCapabilityChartWidget)
        assert len(w._active_chart_widget.child_charts)==2
        assert w.result_tabs.tabText(w.result_tabs.currentIndex())=='Graph'
        assert not w._active_chart_widget.grab().isNull()
        assert 'Capability Comparison' in format_entry(entry)
        snap=w._office_snapshot(entry);assert snap.png and 'Length' in snap.report and 'Weight' in snap.report
        d.deleteLater()
    grouped=MultipleCapabilityDialog(p.worksheet,'normal',w)
    grouped.edit_variables.setText('C1');grouped.chk_by.setChecked(True);grouped.edit_by.setText('C3')
    grouped.subgroup_mode.setCurrentIndex(1);grouped.edit_subgroup_ids.setText('C4')
    grouped.edit_lower.setText('7');grouped.edit_upper.setText('13');grouped._on_ok()
    assert grouped.result()==1,grouped.error.text()
    entry=p.multiple_capability(**grouped.parameters);entries.append(entry)
    assert len(entry['result']['series'])==2
    w.show_result(entry);app.processEvents()
    assert all('Machine=' in s['label'] for s in entry['result']['series'])
    assert isinstance(w._active_chart_widget,MultipleCapabilityChartWidget)
    for suffix,send,member in [('.docx',w.send_output_to_word,'word/document.xml'),('.pptx',w.send_output_to_powerpoint,'ppt/presentation.xml')]:
        target=Path(temp)/('multiple-capability'+suffix)
        with patch('statcraft.modern_app.QFileDialog.getSaveFileName',return_value=(str(target),'Office')):send(entry)
        with ZipFile(target) as archive:
            ET.fromstring(archive.read(member))
            image='word/media/graph.png' if suffix=='.docx' else 'ppt/media/graph.png'
            assert archive.read(image).startswith(b'\x89PNG\r\n\x1a\n')
    expected=[[s['result']['observations'] for s in e['result']['series']] for e in entries]
    p.move_columns([3],'before_c1');p.rename_column(1,'Length renamed')
    for saved,values in zip(entries,expected):
        assert [s['result']['observations'] for s in p.rerun_result(saved)['result']['series']]==values
    target=Path(temp)/'multiple-capability.mpx';p.save(target)
    q=Presenter();q.load(target)
    for saved in list(q.history):
        actual=q.rerun_result(saved)['result']
        for current,previous in zip(actual['summary'],saved['result']['summary']):
            assert {k:v for k,v in current.items() if k not in ('label','variable_name','group_label')} == {k:v for k,v in previous.items() if k not in ('label','variable_name','group_label')}
    q.delete_columns([0])
    affected=next(e for e in q.history if e['recipe']['parameters']['subgroup_indices'])
    try:q.rerun_result(affected)
    except ValueError:pass
    else:raise AssertionError('Deleted subgroup source was silently replaced')
    q.undo();q.rerun_result(affected)
    grouped.deleteLater()
