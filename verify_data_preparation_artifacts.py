"""Create original typed fixtures and review screenshots for preview38."""
import os,json,copy,hashlib
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.mpx_create import create_project
from statcraft.modern_app import ModernWindow
from statcraft.verification_fonts import load_verification_fonts
from statcraft import data_prep as d
from statcraft.data_prep_dialogs import ReshapeDialog,CombineDialog

root=Path(__file__).resolve().parents[2];out=root/'outputs'
app=QApplication.instance() or QApplication([]);load_verification_fonts(app)
app.setQuitOnLastWindowClosed(False)
left=Worksheet('First run',[Column('Before',values=[12,15,None,18,21,20,23,26]),Column('After',values=[14,16,19,20,22,24,25,28]),Column('Batch','text',['A','A','B','B','A','A','B','B']),Column('Recorded','date',list(range(45000,45008)))])
right=copy.deepcopy(left);right.name='Second run';right.columns[0].values=[15,18,21,24,27,26,29,32]
p=Presenter();p.native_project=create_project([left,right]);p.worksheet=p.native_project.active_worksheet
before=copy.deepcopy(p.native_project.worksheets)
for result in [d.stack_columns(left,[0,1]),d.unstack_columns(left,[0,3],2),d.transpose(left,[0,1]),d.stack_worksheets([left,right]),d.merge_worksheets(left,right,3,3)]:d.store_prepared(p,result)
assert p.native_project.worksheets[:2]==before
path=out/'StatCraft-data-preparation-demo.mpx';p.select_worksheet(2);p.save(path);q=Presenter();q.load(path)
assert len(q.native_project.worksheets)==7 and q.native_project.worksheets[-1].columns[7].kind=='date'
w=ModernWindow(q);w.resize(1440,900);w.show();app.processEvents()
q.select_worksheet(0);w.refresh()
dialog=ReshapeDialog(w,'unstack');dialog.controls['indices'].setText('C1: "Before" C4-D: "Recorded"');dialog.controls['group_index'].setText('C3-T: "Batch"')
dialog.show();app.processEvents();w.grab().save(str(out/'StatCraft-data-preparation.png'))
dialog.grab().save(str(out/'StatCraft-unstack-dialog.png'));dialog.close()
merge=CombineDialog(w,'merge');merge.controls['left'].setCurrentIndex(0);merge.controls['right'].setCurrentIndex(1)
merge.controls['left_key'].setCurrentIndex(3);merge.controls['right_key'].setCurrentIndex(3);merge.show();app.processEvents()
merge.grab().save(str(out/'StatCraft-merge-dialog.png'));merge.close()
q.dirty=False;q._results_dirty=False;w.close();w.deleteLater();app.processEvents()
report={'source_unchanged':True,'worksheets':len(q.native_project.worksheets),'typed_mpx_roundtrip':True,'operations':['stack_columns','unstack_columns','transpose','stack_worksheets','merge_worksheets'],'fixture_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'screenshots':['StatCraft-data-preparation.png','StatCraft-unstack-dialog.png','StatCraft-merge-dialog.png']}
(root/'work/data-preparation-artifacts-verified.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
