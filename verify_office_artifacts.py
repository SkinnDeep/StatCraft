"""Synthetic native Office examples for independent import/render validation."""
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow
from statcraft.verification_fonts import load_verification_fonts
from statcraft.office_export import export_docx,export_pptx

root=Path(__file__).resolve().parents[2];out=root/'outputs'
app=QApplication([]);load_verification_fonts(app)
p=Presenter();p.worksheet=Worksheet('Strength measurements',[Column('Run',values=list(range(1,25))),Column('Strength (N)',values=[565+i*.4+(i%3)*2 for i in range(24)])])
w=ModernWindow(p);w.resize(1350,850);w.show();app.processEvents()
entry=p.graph_builder('scatter',[1],0,options={'title':'Strength versus run','fit':True});w.show_result(entry);app.processEvents()
snapshot=w._office_snapshot(entry)
(root/'work/office-graph-image.png').write_bytes(snapshot.png)
export_docx(out/'StatCraft-office-example.docx',snapshot)
count=export_pptx(out/'StatCraft-office-example.pptx',snapshot)
report=p.describe_columns([1]);w.show_result(report);app.processEvents()
export_docx(out/'StatCraft-office-report.docx',w._office_snapshot(report))
(root/'work/office-artifacts-created.json').write_text(json.dumps({'graph_docx':'StatCraft-office-example.docx','graph_pptx':'StatCraft-office-example.pptx','report_docx':'StatCraft-office-report.docx','slides':count},indent=2),encoding='utf-8')
p.dirty=False;p._results_dirty=False;w.close();print('Office samples created:',count,'slides')
