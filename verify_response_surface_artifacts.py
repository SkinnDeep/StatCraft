"""Create original response-surface review artifacts and verify saved models."""
import os,json,hashlib
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter,format_entry
from statcraft.modern_app import ModernWindow
from statcraft.response_surface import create
from statcraft.response_surface_dialogs import CreateSurfaceDialog,AnalyzeSurfaceDialog,CreateSurfaceSettings
from statcraft.response_surface_smoke import add_measurements
from statcraft.glm import settings
from statcraft.verification_fonts import load_verification_fonts
root=Path(__file__).resolve().parents[2];out=root/'outputs';app=QApplication.instance() or QApplication([]);app.setQuitOnLastWindowClosed(False);load_verification_fonts(app)
p=Presenter();p.worksheet=create([dict(name='Heat',low=100.,high=140.),dict(name='Time',low=20.,high=40.)],centers=6,alpha_mode='face',randomize=False,name='Central composite');add_measurements(p.worksheet)
linear=p.analyze_response_surface(6,[4,5],terms=[[0],[1]])
quad=p.analyze_response_surface(6,[4,5],options=dict(settings(),graphs='four',diagnostics='all'))
assert quad['result']['ss_error']<linear['result']['ss_error']
w=ModernWindow(p);w.resize(1440,1000);w.show();w.show_result(quad);app.processEvents()
assert w._active_chart_widget.error is None and w._active_chart_widget.panel_columns==2
w._active_graph_frame.capture().save(str(out/'StatCraft-response-surface-residuals.png'))
w.result_tabs.setCurrentIndex(0);w.grab().save(str(out/'StatCraft-response-surface-report.png'))
d=AnalyzeSurfaceDialog(w);d.show();app.processEvents();d.grab().save(str(out/'StatCraft-response-surface-analysis.png'));d.close()
d=CreateSurfaceDialog(w);d.show();app.processEvents();d.grab().save(str(out/'StatCraft-response-surface-create.png'));d.close()
child=CreateSurfaceSettings(d,'Designs');child.show();app.processEvents();child.grab().save(str(out/'StatCraft-response-surface-designs.png'));child.close()
p.create_response_surface([dict(name=name,low=-1.,high=1.) for name in ['A','B','C']],kind='box_behnken',centers=3,name='Box-Behnken',randomize=False)
p.select_worksheet(0);w.refresh();w.show_result(quad)
path=out/'StatCraft-response-surface-demo.mpx';w.save_path(path);w.load_path(path)
models=[e for e in p.history if e.get('recipe',{}).get('action')=='analyze_response_surface'];assert len(models)==2 and len(p.native_project.worksheets)==2
assert p.native_project.worksheets[1].row_count==15 and all(not p.result_stale(e) for e in models)
(out/'StatCraft-response-surface-report.txt').write_text(format_entry(models[1]),encoding='utf-8')
snapshot=w._office_snapshot(models[1]);assert snapshot.png and 'Lack-of-Fit' in snapshot.report
proof=dict(fixture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),worksheets=2,central_composite_runs=14,box_behnken_runs=15,models=2,mpx_roundtrip=True,residual_panels=4,office_snapshot_graph_and_readable_report=True,linear_error=linear['result']['ss_error'],quadratic_error=quad['result']['ss_error'])
(root/'work/response-surface-artifacts-verified.json').write_text(json.dumps(proof,indent=2),encoding='utf-8');print(json.dumps(proof,indent=2))
p.dirty=False;p._results_dirty=False;w.close();w.deleteLater();app.processEvents()
