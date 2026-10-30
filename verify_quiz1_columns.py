"""User fixture regression: preserve original values through structural copies."""
from pathlib import Path
import hashlib,json
from zipfile import ZipFile
from statcraft.app import Presenter
from statcraft.mpx import load_mpx

root=Path(__file__).resolve().parents[2]
source=Path('C:/Users/funny/Downloads/quiz1.mpx')
first=root/'work/quiz1-columns-roundtrip.mpx';second=root/'work/quiz1-columns-roundtrip-again.mpx'
before=hashlib.sha256(source.read_bytes()).hexdigest()
p=Presenter();p.load(source);original=[(c.name,c.kind,list(c.values)) for c in p.worksheet.columns]
p.insert_columns(0,2);p.rename_column(0,'Inserted A');p.set_cell(0,0,'17')
p.move_columns([0],'after_last');p.delete_columns([0]);p.save(first)
q=Presenter();q.load(first)
assert [(c.name,c.kind,c.values) for c in q.worksheet.columns[:-1]]==original
q.insert_columns(1);q.delete_columns([1]);q.move_columns([len(q.worksheet.columns)-1],'before_c1');q.save(second)
r=load_mpx(second);assert [(c.name,c.kind,c.values) for c in r.active_worksheet.columns[1:]]==original
assert r.active_worksheet.columns[0].values==[17]
with ZipFile(source) as a,ZipFile(first) as b,ZipFile(second) as c:
    sheets={uri+'.json' for uri in p.native_project.worksheet_uris}
    preserved=[name for name in a.namelist() if name not in sheets and name!='/statcraft/session-v1.json']
    assert all(a.read(name)==b.read(name)==c.read(name) for name in preserved)
assert hashlib.sha256(source.read_bytes()).hexdigest()==before
report=dict(source_sha256=before,original_unchanged=True,original_rows=p.native_project._baseline[0].row_count,
    all_original_column_values_preserved=True,two_edit_save_reopen_cycles=True,
    unaffected_archive_members_preserved=len(preserved),first_copy=str(first),second_copy=str(second),native_mpx_reopen_verified=False)
(root/'work/quiz1-column-operations-verified.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
