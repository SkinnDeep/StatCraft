"""Review artifacts and persisted crossed Gage R&R acceptance."""
import os,json,hashlib
from pathlib import Path
from zipfile import ZipFile
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter,format_entry
from statcraft.modern_app import ModernWindow
from statcraft.gage_rr_smoke import fixture
from statcraft.gage_rr_dialogs import GageRRDialog,GageRROptionsDialog
from statcraft.verification_fonts import load_verification_fonts
from statcraft.office_export import export_docx,export_pptx

root=Path(__file__).resolve().parents[2];out=root/'outputs'
app=QApplication.instance() or QApplication([]);app.setQuitOnLastWindowClosed(False);load_verification_fonts(app)
p=Presenter();p.worksheet=fixture();entry=p.gage_rr(2,0,1,dict(tolerance=3))
w=ModernWindow(p);w.resize(1500,1050);w.show();w.show_result(entry);app.processEvents()
chart=w._active_chart_widget;assert chart.error is None and len(chart.panels)==6
frame=w._active_graph_frame;frame.capture().save(str(out/'StatCraft-gage-rr-graphs.png'))
d=GageRRDialog(w);d.show();app.processEvents();d.grab().save(str(out/'StatCraft-gage-rr-dialog.png'));d.reject()
child=GageRROptionsDialog(w,entry['result']['options']);child.show();app.processEvents();child.grab().save(str(out/'StatCraft-gage-rr-options.png'));child.reject()
w.result_tabs.setCurrentIndex(0);w.grab().save(str(out/'StatCraft-gage-rr-report.png'))
path=out/'StatCraft-gage-rr-demo.mpx';w.save_path(path);w.load_path(path);app.processEvents()
entry=next(e for e in p.history if e.get('recipe',{}).get('action')=='gage_rr');assert not p.result_stale(entry)
rerun=p.rerun_result(entry);assert rerun['result']==entry['result']
(out/'StatCraft-gage-rr-report.txt').write_text(format_entry(entry),encoding='utf-8')
snapshot=w._office_snapshot(entry);assert snapshot.png and 'Variance Components' in snapshot.report and 'plot_data' not in snapshot.report
for ext,writer in [('docx',export_docx),('pptx',export_pptx)]:
    target=out/('StatCraft-gage-rr-example.'+ext);writer(target,snapshot)
    with ZipFile(target) as z:assert any(n.endswith('.png') for n in z.namelist())
proof=dict(fixture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),observations=90,parts=10,operators=3,repeats=3,graphs=6,mpx_roundtrip=True,rerun_unchanged=True,office_graph_and_readable_report=True)
(root/'work/gage-rr-artifacts-verified.json').write_text(json.dumps(proof,indent=2),encoding='utf-8');print(json.dumps(proof,indent=2))
p.dirty=False;p._results_dirty=False;w.close();w.deleteLater();app.processEvents()
