"""Create synthetic, inspected print examples; never submit a physical job."""
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPageLayout
from PySide6.QtCore import QTimer
from PySide6.QtPrintSupport import QPrinter
from pypdf import PdfReader
from statcraft.app import Presenter
from statcraft.model import Worksheet, Column
from statcraft.modern_app import ModernWindow
from statcraft.verification_fonts import load_verification_fonts

root=Path(__file__).resolve().parents[2];out=root/'outputs'
app=QApplication([]);load_verification_fonts(app)
p=Presenter();p.worksheet=Worksheet('Strength measurements',[
    Column('Run', values=list(range(1,121))),
    Column('Strength (N)', values=[565+(i*7%23)*.7 for i in range(120)]),
    Column('Batch','text',['Day' if i%2 else 'Night' for i in range(120)])])
w=ModernWindow(p);w.resize(1350,850);w.show();app.processEvents();controller=w._printing()
results={}
for kind in ('Worksheet','Graph','Report'):
    if kind=='Graph':w.show_result(p.graph_builder('histogram',[1]));app.processEvents()
    job=controller.snapshot(kind=kind)
    printer=QPrinter();printer.setResolution(144);printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setPageLayout(controller.printer.pageLayout())
    if kind=='Graph':printer.setPageOrientation(QPageLayout.Orientation.Landscape)
    path=out/f'StatCraft-print-{kind.lower()}.pdf';printer.setOutputFileName(str(path));job.render(printer)
    pdf=PdfReader(path);results[kind]={'file':path.name,'pages':len(pdf.pages),'bytes':path.stat().st_size}
    assert len(pdf.pages)==job.last_page_count
    if kind=='Worksheet':
        text=' '.join(' '.join(page.extract_text().split()) for page in pdf.pages)
        assert '119' in text and '120' in text and 'Strength (N)' in text
    if kind=='Graph':assert len(pdf.pages)==1 and bool(pdf.pages[0].images)
    if kind=='Report':assert 'Histogram' in ''.join(page.extract_text() for page in pdf.pages)
w.grab().save(str(out/'StatCraft-print-workspace.png'))
def accept_options():
    QApplication.activeModalWidget().accept()
    QTimer.singleShot(600,close_preview)
def close_preview():
    dialog=QApplication.activeModalWidget()
    assert dialog.windowTitle().startswith('Print Preview')
    dialog.grab().save(str(out/'StatCraft-print-preview.png'))
    results['live_preview_dialog']={'captured':True,'printer_job_submitted':False}
    dialog.reject()
QTimer.singleShot(0,accept_options);controller.run('preview')
(root/'work/printing-artifacts-verified.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
p.dirty=False;p._results_dirty=False;w.close();print(json.dumps(results))
