"""End-to-end attribute capability acceptance in source and frozen builds."""
from pathlib import Path
from .model import Worksheet, Column
from .app import Presenter, format_entry
from .attribute_capability_dialogs import AttributeCapabilityDialog
from .attribute_capability_chart import AttributeCapabilityChartWidget


def verify_attribute_capability(app, p, w, temp, checkpoint):
    checkpoint('Attribute capability dialogs, graphs, source bindings and MPX')
    p.new()
    p.worksheet=Worksheet('Attribute Study',[
        Column('Inspected', values=[100,120,90,100,150,80,100,100]),
        Column('Defectives', values=[4,6,3,7,5,2,None,4]),
        Column('Exposure', values=[2.5,3.0,2.0,2.5,4.0,2.0,3.0,2.0])])
    w.refresh();app.processEvents()
    for method in ('binomial','poisson'):
        dialog=AttributeCapabilityDialog(w,p.worksheet,method)
        dialog.controls['count_index'].setText('C2')
        dialog.controls['size_mode'].setCurrentIndex(1)
        dialog.controls['size_index'].setText('C1' if method=='binomial' else 'C3')
        dialog.controls['target'].setText('1' if method=='binomial' else '0.5')
        assert any('Defectives' in dialog.available.item(i).text() for i in range(dialog.available.count()))
        dialog.validate();assert dialog.result()==1,dialog.error.text()
        entry=p.attribute_capability(**dialog.parameters)
        assert entry['result']['rows']==[1,2,3,4,5,6,8]
        assert 'Summary Statistics' in format_entry(entry)
        w.refresh();w.show_result(entry);app.processEvents()
        assert isinstance(w._active_chart_widget,AttributeCapabilityChartWidget)
        image=w._active_chart_widget.grab().toImage()
        assert not image.isNull() and image.width()>500
        dialog.deleteLater()
    old_entries=list(p.history)
    expected=[e['result']['observed_rate'] for e in old_entries]
    p.move_columns([1],'before_c1');p.rename_column(0,'Count renamed')
    for entry,value in zip(old_entries,expected):
        assert abs(p.rerun_result(entry)['result']['observed_rate']-value)<1e-12
    target=Path(temp)/'attribute-capability.mpx';p.save(target)
    q=Presenter();q.load(target)
    for entry in list(q.history):
        assert q.rerun_result(entry)['result']['observed_rate']==entry['result']['observed_rate']
    q.delete_columns([0])
    try:q.rerun_result(q.history[0])
    except ValueError:pass
    else:raise AssertionError('Deleted source was silently reused')
    q.undo();q.rerun_result(q.history[0])
