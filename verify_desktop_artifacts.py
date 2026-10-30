"""Original splash, transformed graph view and genuine heatmap Office examples."""
from pathlib import Path
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow
from statcraft.startup import splash_pixmap
from statcraft.verification_fonts import load_verification_fonts
from statcraft.office_export import export_docx,export_pptx

root=Path(__file__).resolve().parents[2];out=root/'outputs'
app=QApplication([]);load_verification_fonts(app);splash_pixmap().save(str(out/'StatCraft-startup-splash.png'))
p=Presenter();p.worksheet=Worksheet('Strength samples',[Column('Run',values=list(range(1,9))),Column('Strength',values=[573.73,568.96,574.86,581.42,568.24,581.84,575.16,566.48])])
w=ModernWindow(p);w.resize(1400,900);w.show();app.processEvents()
heat=p.expanded_graph('heatmap',[1]);w.show_result(heat);app.processEvents()
snapshot=w._office_snapshot(heat)
export_docx(out/'StatCraft-heatmap-export.docx',snapshot);export_pptx(out/'StatCraft-heatmap-export.pptx',snapshot)
(root/'work/office-graph-image.png').write_bytes(snapshot.png)
w.set_zoom(150);app.processEvents();w.grab().save(str(out/'StatCraft-output-zoom-150.png'))
w.set_zoom(100);app.processEvents();w.grab().save(str(out/'StatCraft-output-zoom-100.png'))
p.dirty=False;p._results_dirty=False;w.close()
print('Splash, zoom and real heatmap Office examples created')
