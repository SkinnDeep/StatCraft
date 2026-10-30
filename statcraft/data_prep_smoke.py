"""Source/frozen user-interface acceptance for typed preparation and MPX saving."""
from pathlib import Path
from .model import Worksheet,Column
from .data_prep_dialogs import ReshapeDialog,CombineDialog,destinations,install
from .data_prep import transpose


def verify_data_preparation(app,p,w,temp,checkpoint):
    checkpoint('Named variable transfer, stack/unstack/transpose, worksheet stack/merge and typed MPX persistence')
    p.new();p.worksheet=Worksheet('Measurements',[Column('Before',values=[1,None,3]),Column('After',values=[4,5,6]),Column('Batch','text',['A','B','A']),Column('Recorded','date',[45000,45001,45002])])
    w.page=0;w._show_welcome();w.refresh();source=p.worksheet
    d=ReshapeDialog(w,'stack');d.controls['indices'].setText('C1 C2');d.controls['name'].setText('Stacked');d.validate()
    assert not d.error.text() and p.worksheet.columns[0].values==[1,None,3,4,5,6]
    p.select_worksheet(0);w.refresh()
    d=ReshapeDialog(w,'unstack');d.controls['indices'].setText('C1 C4');d.controls['group_index'].setText('C3');d.controls['name'].setText('Unstacked');d.validate()
    assert not d.error.text() and [c.kind for c in p.worksheet.columns]==['number','number','date','date']
    assert p.worksheet.columns[2].values==[45000,45002]
    p.select_worksheet(0);w.refresh()
    d=ReshapeDialog(w,'transpose');d.controls['indices'].setText('C1 C2');d.controls['name'].setText('Transposed');d.validate()
    assert not d.error.text() and p.worksheet.columns[1].values==[1,4]
    p.select_worksheet(0);w.refresh()
    p.duplicate_worksheet('Second run');p.worksheet.columns[0].values=[7,8,9];w.refresh()
    d=CombineDialog(w,'stack_worksheets');d.selection.item(0).setSelected(True);d.selection.item(4).setSelected(True);d.validate()
    assert not d.error.text() and p.worksheet.columns[0].values==[1,None,3,7,8,9]
    assert p.worksheet.columns[3].kind=='date' and p.worksheet.columns[4].values==['Measurements']*3+['Second run']*3
    d=CombineDialog(w,'merge');d.controls['left'].setCurrentIndex(0);d.controls['right'].setCurrentIndex(4)
    d.controls['left_key'].setCurrentIndex(3);d.controls['right_key'].setCurrentIndex(3);d.validate()
    assert not d.error.text() and p.worksheet.columns[4].values==[7,8,9]
    assert source.columns[0].values==[1,None,3]
    path=Path(temp)/'data-preparation.mpx';w.save_path(path);w.load_path(path);app.processEvents()
    assert len(p.native_project.worksheets)==7 and p.worksheet.columns[7].kind=='date'
    p.select_worksheet(0);w.refresh()
    # An imported native project can supply data to a new independent project.
    native=p.native_project;native.statcraft_owned=False
    assert destinations(p)==['New project']
    derived=install(w,transpose(p.worksheet,[0,1],'Native source prepared'),'New project')
    assert p.native_project is native and p.worksheet.columns[0].values==[1,None,3]
    child=app._prepared_windows[-1];assert child.isMaximized() and derived is child.presenter and derived.dirty
    derived.dirty=False;derived._results_dirty=False;child.close();child.deleteLater();app.processEvents()
    native.statcraft_owned=True
