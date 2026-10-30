"""Original synthetic native-output fixture and packaged saved-output checks."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from .app import Presenter, format_entry


def fixture(path):
    from .model import Worksheet, Column
    from .mpx_create import create_project, _members
    project = create_project([Worksheet('Saved outputs', [Column('X', values=[1, 2, 3]), Column('Y', values=[4, 5, 4])])])
    members, metadata, _ = _members(project, [], {})
    members = {k:v for k,v in members.items() if not k.startswith('/statcraft/')}
    uid = project.worksheet_ids[0]
    metadata['Commands']={'Items':[{'Id':'synthetic-output-command','OutputWorksheet':uid,'Executed':'2026-10-28T00:00:00Z','OutputGroups':[{'Title':'Saved response surface outputs','Uri':'/commands/0/groups/0/group'}]}]}
    outputs=[{'Data':{'Base':'Saved synthetic coefficients: 1, 2, 3'}}]
    grids={'XMesh':[1,2,3],'YMesh':[1,2,3],'ZValues':[1,2,3,2,5,4,3,4,5]}
    for index,kind in enumerate(('scatter','contour','surface')):
        model=({'XCol':{'NumericData':[1,2,3]},'YCol':{'NumericData':[4,5,4]}} if kind=='scatter' else {('ContourGrid' if kind=='contour' else 'RSPlotContourGrid'):grids})
        figure={'GraphModels':[model],'Panels':[{'GraphModels':[0]}],'ContourLevelsC':[2,3,4]}
        uri=f'/commands/0/graphs/{index}/graph'
        members[uri+'.json']=json.dumps({'Graph':{'Title':'Saved '+kind,'FigureList':[{'Figures':[figure]}]}}).encode()
        outputs.append({'GraphDoc':uri})
    members['/commands/0/groups/0/group.json']=json.dumps({'Id':'synthetic-native-group','Outputs':outputs}).encode()
    members['/project_metadata_20.json']=json.dumps(metadata).encode()
    with ZipFile(path,'w',ZIP_DEFLATED) as z:
        for name,data in members.items():z.writestr(name,data)
    return path


def verify_saved_outputs(app,window,path,destination=None):
    source=Path(path);before=hashlib.sha256(source.read_bytes()).hexdigest()
    window.load_path(source);window.show();app.processEvents()
    entries=[e for e in window.presenter.history if e['result'].get('analysis')=='native_saved_output']
    assert entries, 'No native output groups were restored.'
    assert window.selected_entry in entries, 'Saved native output should open automatically.'
    graphs=[]
    for entry in entries:
        assert entry.get('origin')=='native' and 'recipe' not in entry
        assert window.presenter.result_worksheet(entry).name==entry['worksheet_name']
        assert isinstance(format_entry(entry),str)
        window.show_result(entry);app.processEvents()
        if not entry['result'].get('graphs'):continue
        chart=window._active_chart_widget
        assert chart is not None
        for index,g in enumerate(entry['result']['graphs']):
            chart.select_graph(index);app.processEvents()
            captured=window._active_graph_frame.capture()
            assert not captured.isNull() and chart.error is None
            if g.get('panels'):assert chart.rendered_primitives>0, g.get('title')
            graphs.append({'title':g['title'],'kinds':[p['kind'] for p in g['panels']], 'primitives':chart.rendered_primitives})
            if destination and any(p['kind'] in ('contour','surface') for p in g['panels']):
                captured.save(str(Path(destination).with_name(Path(destination).stem+'-'+g['panels'][0]['kind']+'.png')))
    assert before==hashlib.sha256(source.read_bytes()).hexdigest()
    proof={'source_sha256':before,'native_groups':len(entries),'saved_graphs':len(graphs),'graphs':graphs,
           'original_unchanged':True,'ui_rendered':True,'saved_values_sha256':hashlib.sha256(json.dumps(entries,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
    if destination:
        import sys
        proof['frozen']=bool(getattr(sys,'frozen',False))
        Path(destination).write_text(json.dumps(proof,indent=2),encoding='utf-8')
    return proof


def verify_native_outputs(app,p,w,temp,checkpoint):
    checkpoint('Native MPX stored reports and graphs: read without refitting, gallery, Office capture, save-copy')
    path=fixture(Path(temp)/'native-output.mpx')
    from .modern_app import ModernWindow
    viewer=ModernWindow()
    proof=verify_saved_outputs(app,viewer,path)
    assert proof['native_groups']==1 and proof['saved_graphs']==3
    q=viewer.presenter
    copy_path=Path(temp)/'native-output-copy.mpx';q.save(copy_path)
    restored=Presenter();restored.load(copy_path)
    saved=[e for e in restored.history if e['result'].get('analysis')=='native_saved_output']
    assert len(saved)==1 and len(saved[0]['result']['graphs'])==3
    assert restored.native_project.session_records==[]
    with ZipFile(path) as a,ZipFile(copy_path) as b:
        assert all(a.read(n)==b.read(n) for n in a.namelist())
    viewer.presenter.dirty=False;viewer.presenter._results_dirty=False;viewer.close();viewer.deleteLater()
