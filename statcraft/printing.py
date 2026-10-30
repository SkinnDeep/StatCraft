"""Detached print snapshots shared by preview, PDF and the system printer dialog."""
from dataclasses import dataclass
from html import escape

from PySide6.QtCore import QRectF, QSizeF, QMarginsF, Qt
from PySide6.QtGui import QPainter, QFont, QTextDocument, QTextOption, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog, QPageSetupDialog
from PySide6.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QComboBox, QDialogButtonBox, QFileDialog, QMessageBox
from .app import format_entry
from .model import display_date


@dataclass(frozen=True)
class WorksheetOptions:
    row_labels: bool = True
    column_labels: bool = True
    column_names: bool = True
    grid_lines: bool = True


def cell_text(column, row):
    if row >= len(column.values): return ''
    value = column.values[row]
    if value is None: return '' if column.kind == 'text' else '*'
    if column.kind == 'date': return display_date(value)
    fmt = column.metadata.get('format')
    if column.kind == 'number' and isinstance(fmt, dict) and isinstance(value, (int, float)):
        decimals = max(0, min(15, int(fmt.get('decimals', 2))))
        mode = fmt.get('mode', 'fixed')
        if mode == 'currency': return f'${value:,.{decimals}f}'
        if mode == 'percent': return f'{value * 100:.{decimals}f}%'
        if mode == 'scientific': return f'{value:.{decimals}E}'
        return f'{value:.{decimals}f}'
    return str(value)


def worksheet_html(sheet, options=WorksheetOptions(), band_size=6):
    """Horizontal bands retain every used column; QTextDocument paginates rows."""
    if band_size < 1: raise ValueError('At least one column per band is required.')
    indices = [i for i, c in enumerate(sheet.columns) if c.values or c.name not in ('', f'C{i+1}')]
    if not indices: indices = list(range(min(len(sheet.columns), band_size)))
    if sheet.row_count * len(indices) > 500000:
        raise ValueError('Print up to 500,000 worksheet cells at a time. Export larger worksheets as data.')
    bands = []
    border = '1' if options.grid_lines else '0'
    for start in range(0, len(indices), band_size):
        cols = indices[start:start+band_size]
        headers = []
        for i in cols:
            c = sheet.columns[i]
            parts = ([f'C{i+1}' + ('-T' if c.kind == 'text' else '-D' if c.kind == 'date' else '')] if options.column_labels else [])
            if options.column_names: parts.append(escape(c.name))
            headers.append('<th>' + '<br>'.join(parts) + '</th>')
        head = ('<th>Row</th>' if options.row_labels else '') + ''.join(headers)
        rows = []
        for row in range(sheet.row_count):
            cells = ('<td>' + str(row+1) + '</td>') if options.row_labels else ''
            cells += ''.join('<td>' + escape(cell_text(sheet.columns[i], row)).replace('\n', '<br>') + '</td>' for i in cols)
            rows.append('<tr>' + cells + '</tr>')
        bands.append(f'<table width="100%" border="{border}" cellspacing="0" cellpadding="3"><thead><tr>{head}</tr></thead>' + ''.join(rows) + '</table>')
    return bands or ['<p>Empty worksheet</p>']


class PrintJob:
    def __init__(self, title, documents=(), image=None):
        self.title = str(title)
        self.documents = list(documents)
        self.image = image
        self.last_page_count = 0

    @classmethod
    def worksheet(cls, sheet, options=WorksheetOptions()):
        return cls(sheet.name, worksheet_html(sheet, options))

    @classmethod
    def report(cls, entry):
        return cls(entry.get('title', 'Report'), ['<pre style="white-space: pre-wrap; font-family: Consolas">' + escape(format_entry(entry)) + '</pre>'])

    def render(self, printer):
        layout = printer.pageLayout()
        area = layout.paintRect(QPageLayout.Unit.Point)
        body = QRectF(area.left(), area.top()+24, area.width(), area.height()-44)
        if body.width() < 72 or body.height() < 72: raise ValueError('Page margins leave too little printable space.')
        docs, pages = [], []
        for html in self.documents:
            doc = QTextDocument()
            font = QFont('Segoe UI'); font.setPixelSize(9)
            doc.setDefaultFont(font); doc.setDocumentMargin(0)
            option=doc.defaultTextOption(); option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere); doc.setDefaultTextOption(option)
            doc.setHtml(html); doc.setPageSize(QSizeF(body.width(), body.height()))
            docs.append(doc)
            pages.extend((doc, i) for i in range(doc.pageCount()))
        if self.image is not None: pages = [(None, 0)]
        if len(pages) > 2000: raise ValueError('Print job exceeds 2,000 pages.')
        self.last_page_count = len(pages)
        first = max(1, printer.fromPage() or 1)
        last = min(len(pages), printer.toPage() or len(pages))
        order = list(range(first-1, last))
        if printer.pageOrder() == QPrinter.PageOrder.LastPageFirst: order.reverse()
        copies = 1 if printer.supportsMultipleCopies() else max(1, printer.copyCount())
        order = order * copies if printer.collateCopies() else [i for i in order for _ in range(copies)]
        if not order: raise ValueError('The selected page range is outside this document.')
        old_full = printer.fullPage()
        printer.setFullPage(True)
        painter = QPainter()
        try:
            if not painter.begin(printer): raise ValueError('Unable to open the printer or PDF destination.')
            for output_index, page_index in enumerate(order):
                if output_index and not printer.newPage(): raise ValueError('Unable to create the next print page.')
                painter.save(); painter.scale(printer.resolution()/72, printer.resolution()/72)
                font = QFont('Segoe UI'); font.setPixelSize(10); painter.setFont(font)
                painter.drawText(QRectF(area.left(), area.top(), area.width(), 20), Qt.AlignmentFlag.AlignLeft, self.title)
                painter.drawText(QRectF(area.left(), area.bottom()-16, area.width(), 16), Qt.AlignmentFlag.AlignRight, f'Page {page_index+1} of {len(pages)}')
                doc, offset = pages[page_index]
                if doc is None:
                    size = QSizeF(self.image.size()); size.scale(body.size(), Qt.AspectRatioMode.KeepAspectRatio)
                    target = QRectF(body.center().x()-size.width()/2, body.center().y()-size.height()/2, size.width(), size.height())
                    painter.drawImage(target, self.image)
                else:
                    painter.setClipRect(body)
                    painter.translate(body.left(), body.top()-offset*body.height())
                    # Exclude the next page boundary: Qt otherwise emits the next
                    # paragraph into the PDF stream even though it is clipped.
                    doc.drawContents(painter, QRectF(0, offset*body.height()+0.01, body.width(), body.height()-0.02))
                painter.restore()
        finally:
            if painter.isActive(): painter.end()
            printer.setFullPage(old_full)
            printer.setPageLayout(layout)


class PrintController:
    def __init__(self, window):
        self.window = window
        self.printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        self.printer.setResolution(144)
        self.printer.setPageSize(QPageSize(QPageSize.PageSizeId.Letter))
        self.printer.setPageMargins(QMarginsF(12.7,12.7,12.7,12.7), QPageLayout.Unit.Millimeter)
        self.options = WorksheetOptions()

    def page_setup(self):
        layout = self.printer.pageLayout()
        if QPageSetupDialog(self.printer, self.window).exec() != QDialog.DialogCode.Accepted:
            self.printer.setPageLayout(layout)

    def snapshot(self, entry=None, kind=None):
        w = self.window
        w._commit_editor()
        if not w.graph_options_pane.flush(): return None
        if kind=='ReportPad' or (kind is None and w.result_tabs.currentWidget() is getattr(w,'_report_pad_editor',None)):
            return PrintJob('ReportPad',['<pre style="white-space: pre-wrap; font-family: Consolas">'+escape(w._report_pad_editor.toPlainText())+'</pre>'])
        entry = entry if isinstance(entry, dict) else w.selected_entry
        if kind == 'Worksheet': return PrintJob.worksheet(w.presenter.worksheet, self.options)
        if entry is not None:
            if entry is not w.selected_entry: w.show_result(entry)
            if w._active_graph_frame is not None and kind != 'Report':
                return PrintJob(entry.get('title', 'Graph'), image=w._active_graph_frame.capture().toImage())
            return PrintJob.report(entry)
        return PrintJob.worksheet(w.presenter.worksheet, self.options)

    def run(self, mode='print', entry=None):
        try:
            self.window._commit_editor()
            if not self.window.graph_options_pane.flush(): return
            d = QDialog(self.window); box = QVBoxLayout(d)
            d.setWindowTitle('Print Options')
            source = QComboBox(); source.addItem('Worksheet')
            pad=getattr(self.window,'_report_pad_editor',None)
            if pad is not None and pad.toPlainText():source.addItem('ReportPad')
            target = entry if isinstance(entry, dict) else self.window.selected_entry
            if target is not None:
                source.addItem('Report')
                if target is not self.window.selected_entry: self.window.show_result(target)
                if self.window._active_graph_frame is not None: source.addItem('Graph')
                source.setCurrentIndex(source.count()-1)
                tabs=self.window.result_tabs
                if tabs.currentIndex()>=0 and tabs.tabText(tabs.currentIndex())=='Report': source.setCurrentText('Report')
            if self.window.result_tabs.currentWidget() is pad:source.setCurrentText('ReportPad')
            box.addWidget(source)
            checks = []
            for text, value in zip(('Print row labels', 'Print column labels (e.g., C1)', 'Print column names', 'Print grid lines'), self.options.__dict__.values()):
                check = QCheckBox(text); check.setChecked(value); box.addWidget(check); checks.append(check)
            def enable_options():
                for check in checks: check.setEnabled(source.currentText() == 'Worksheet')
            source.currentTextChanged.connect(enable_options); enable_options()
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(d.accept); buttons.rejected.connect(d.reject); box.addWidget(buttons)
            if d.exec() != QDialog.DialogCode.Accepted: return
            self.options = WorksheetOptions(*(c.isChecked() for c in checks))
            job = self.snapshot(entry, source.currentText())
            if job is None: return
            if mode == 'preview':
                d = QPrintPreviewDialog(self.printer, self.window); d.setWindowTitle('Print Preview — '+job.title)
                errors = []
                def paint(printer):
                    try: job.render(printer)
                    except (ValueError, OSError, RuntimeError) as exc:
                        errors.append(str(exc)); d.reject()
                d.paintRequested.connect(paint); d.resize(1000, 780); d.exec()
                if errors: raise ValueError(errors[0])
            elif mode == 'pdf':
                path, _ = QFileDialog.getSaveFileName(self.window, 'Export PDF', '', 'PDF documents (*.pdf)')
                if not path: return
                if not path.lower().endswith('.pdf'): path += '.pdf'
                pdf = QPrinter(QPrinter.PrinterMode.HighResolution); pdf.setResolution(144)
                pdf.setPageLayout(self.printer.pageLayout()); pdf.setOutputFormat(QPrinter.OutputFormat.PdfFormat); pdf.setOutputFileName(path)
                job.render(pdf); self.window.statusBar().showMessage(f'Exported {job.last_page_count} PDF pages', 6000)
            else:
                d = QPrintDialog(self.printer, self.window)
                d.setOption(QPrintDialog.PrintDialogOption.PrintPageRange, True)
                if d.exec() == QDialog.DialogCode.Accepted: job.render(self.printer)
        except (ValueError, OSError, RuntimeError) as exc:
            QMessageBox.warning(self.window, 'Printing', str(exc))
