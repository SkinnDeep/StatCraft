"""Exercise the packaged print pipeline without submitting printer jobs."""
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtPrintSupport import QPrinter
from .printing import PrintJob
from .model import Worksheet, Column


def verify_printing(app, p, w, temp, checkpoint):
    checkpoint('Print snapshots, all worksheet rows, graph/report PDF, native cancellation')
    p.new(); p.worksheet=Worksheet('Printing measurements',[
        Column('Run', values=list(range(1,1201))),
        Column('Strength', values=[560+(i%25) for i in range(1200)]),
        Column('Batch','text',['A' if i%2 else 'B' for i in range(1200)])])
    w.page=0; w._show_welcome(); w.refresh(); app.processEvents()
    controller=w._printing();before=p.worksheet.to_dict() if hasattr(p.worksheet,'to_dict') else repr(p.worksheet)
    def pdf(job, name):
        printer=QPrinter(); printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        path=Path(temp)/name; printer.setOutputFileName(str(path));job.render(printer)
        assert path.read_bytes().startswith(b'%PDF-') and path.stat().st_size>3000
        return job.last_page_count
    assert pdf(controller.snapshot(kind='Worksheet'),'print-worksheet.pdf')>10
    assert (p.worksheet.to_dict() if hasattr(p.worksheet,'to_dict') else repr(p.worksheet))==before
    entry=p.graph_builder('histogram',[1]); w.show_result(entry);app.processEvents()
    menu=w.build_output_context_menu(entry)
    with patch.object(w,'print_current') as callback:
        next(a for a in menu.actions() if a.text().startswith('Print...')).trigger()
        callback.assert_called_once_with(entry)
    assert pdf(controller.snapshot(kind='Graph'),'print-graph.pdf')==1
    assert pdf(controller.snapshot(kind='Report'),'print-report.pdf')>=1
    dirty=p.dirty;history=len(p.history)
    with patch('statcraft.printing.QPrintDialog.exec',return_value=QDialog.DialogCode.Rejected), patch.object(PrintJob,'render') as render:
        QTimer.singleShot(0,lambda:QApplication.activeModalWidget().accept())
        controller.run('print'); assert not render.called
    with patch('statcraft.printing.QPageSetupDialog.exec',return_value=QDialog.DialogCode.Rejected):controller.page_setup()
    with patch('statcraft.printing.QFileDialog.getSaveFileName',return_value=('', '')) ,patch.object(PrintJob,'render') as render:
        QTimer.singleShot(0,lambda:QApplication.activeModalWidget().accept())
        controller.run('pdf');assert not render.called
    QTimer.singleShot(0,lambda:QApplication.activeModalWidget().reject())
    controller.run('preview')
    paints=[]
    def show_preview(dialog):
        # Emit the real preview paint request into a PDF sink. No driver job.
        printer=QPrinter();printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        path=Path(temp)/'preview-paint.pdf';printer.setOutputFileName(str(path))
        dialog.paintRequested.emit(printer)
        assert path.read_bytes().startswith(b'%PDF-');paints.append(True)
        return QDialog.DialogCode.Rejected
    with patch('statcraft.printing.QPrintPreviewDialog.exec',new=show_preview):
        QTimer.singleShot(0,lambda:QApplication.activeModalWidget().accept())
        controller.run('preview');assert paints==[True]
    assert p.dirty==dirty and len(p.history)==history and w.selected_entry is entry
