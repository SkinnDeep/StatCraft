from pathlib import Path
import hashlib,json
from statcraft.app import Presenter
from statcraft import data_prep as d
source=Path('C:/Users/funny/Downloads/quiz1.mpx');original=hashlib.sha256(source.read_bytes()).hexdigest()
p=Presenter();p.load(source);before=p.worksheet
prepared=d.transpose(p.worksheet,[0],'Transposed quiz')
try:d.store_prepared(p,prepared)
except ValueError:pass
else:raise AssertionError('Native structural rewrite should be blocked')
q=d.store_prepared(p,prepared,'project');destination=Path('work/quiz1-preparation-copy.mpx');q.save(destination)
r=Presenter();r.load(destination)
assert r.worksheet.row_count==1 and len(r.worksheet.columns)==1201
assert [c.values[0] for c in r.worksheet.columns[1:]]==before.columns[0].values
assert p.worksheet is before and hashlib.sha256(source.read_bytes()).hexdigest()==original
report={'source_sha256':original,'source_unchanged':True,'input_rows':before.row_count,'prepared_columns':len(r.worksheet.columns),'prepared_rows':r.worksheet.row_count,'native_structure_write_rejected':True,'independent_mpx_roundtrip':True}
Path('work/quiz1-data-preparation-verified.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
