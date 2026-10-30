import copy
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPageLayout, QImage, QColor
from PySide6.QtPrintSupport import QPrinter
from statcraft.printing import PrintJob, WorksheetOptions, worksheet_html, cell_text
from statcraft.model import Worksheet, Column
from statcraft.verification_fonts import load_verification_fonts


class PrintingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        load_verification_fonts(cls.app)

    def test_horizontal_bands_cover_every_column_and_row_without_mutation(self):
        sheet = Worksheet('Wide', [Column('Measurement '+str(i), values=list(range(65))) for i in range(14)])
        before = copy.deepcopy(sheet)
        bands = worksheet_html(sheet)
        self.assertEqual(len(bands), 3)
        self.assertEqual(''.join(bands).count('<td>65</td>'), 3)
        for i in range(14): self.assertEqual(''.join(bands).count('Measurement '+str(i)+'</th>'), 1)
        self.assertEqual(sheet, before)

    def test_options_and_escaping(self):
        sheet = Worksheet('Text', [Column('<script>', 'text', ['A&B', None])])
        html = worksheet_html(sheet, WorksheetOptions(False, False, False, False))[0]
        self.assertIn('border="0"', html); self.assertIn('A&amp;B', html)
        self.assertNotIn('Row', html); self.assertNotIn('C1', html); self.assertNotIn('script', html)
        self.assertIn('&lt;script&gt;', worksheet_html(sheet)[0])

    def test_cell_formats_and_missing(self):
        for mode, expected in [('percent','12.50%'),('currency','$0.13'),('scientific','1.25E-01'),('fixed','0.13')]:
            col = Column('Amount',values=[.125, None],metadata={'format': {'mode':mode,'decimals':2}})
            # Python uses ties-to-even rounding.
            if mode in ('currency','fixed'): expected = expected.replace('13','12')
            self.assertEqual(cell_text(col,0),expected); self.assertEqual(cell_text(col,1),'*')
            self.assertEqual(cell_text(col,9),'')
        self.assertEqual(cell_text(Column('Date','date',[45000]),0),'2023-03-15')

    def test_pdf_pagination_orientation_range_and_layout_restoration(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("pypdf not installed")
        sheet = Worksheet('Print acceptance', [Column('Identifier','text',[f'ROW_{r:04d}' for r in range(1,1201)])])
        job = PrintJob.worksheet(sheet)
        with tempfile.TemporaryDirectory() as folder:
            printer = QPrinter(); printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(str(Path(folder)/'rows.pdf'))
            printer.setPageOrientation(QPageLayout.Orientation.Landscape)
            layout = printer.pageLayout(); old_full = printer.fullPage()
            job.render(printer)
            pdf = PdfReader(printer.outputFileName())
            self.assertGreater(len(pdf.pages),10)
            self.assertEqual(len(pdf.pages),job.last_page_count)
            text = ''.join(page.extract_text() for page in pdf.pages)
            for row in range(1,1201): self.assertEqual(text.count(f'ROW_{row:04d}'),1)
            self.assertGreater(float(pdf.pages[0].mediabox.width),float(pdf.pages[0].mediabox.height))
            self.assertEqual(printer.pageLayout(),layout); self.assertEqual(printer.fullPage(),old_full)
            printer.setFromTo(2,3); printer.setOutputFileName(str(Path(folder)/'range.pdf'));job.render(printer)
            selected=PdfReader(printer.outputFileName());self.assertEqual(len(selected.pages),2)
            self.assertIn('Page 2 of', ' '.join(selected.pages[0].extract_text().split()))

    def test_graph_one_page_and_report_all_text(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("pypdf not installed")
        with tempfile.TemporaryDirectory() as folder:
            printer = QPrinter(); printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            image=QImage(1600,800,QImage.Format.Format_RGB32); image.fill(QColor('blue'))
            job=PrintJob('Graph',image=image);printer.setOutputFileName(str(Path(folder)/'graph.pdf'));job.render(printer)
            self.assertEqual(len(PdfReader(printer.outputFileName()).pages),1)
            text=''.join(f'<p>Line_{i:04d}</p>' for i in range(600))
            job=PrintJob('Long report',[text]);printer.setOutputFileName(str(Path(folder)/'report.pdf'));job.render(printer)
            pages=PdfReader(printer.outputFileName()).pages
            self.assertGreater(len(pages),1)
            extracted=''.join(p.extract_text() for p in pages)
            for i in range(600): self.assertEqual(extracted.count(f'Line_{i:04d}'),1)

    def test_print_range_outside_document_fails_before_opening_destination(self):
        printer=QPrinter();printer.setFromTo(20,25)
        with self.assertRaisesRegex(ValueError,'page range'):
            PrintJob('Short',['<p>One page</p>']).render(printer)

    def test_invalid_bands_and_oversized_jobs_fail_explicitly(self):
        sheet=Worksheet('Empty',[Column('C1')])
        with self.assertRaises(ValueError):worksheet_html(sheet,band_size=0)
        sheet.columns=[Column('Big',values=[0]*500001)]
        with self.assertRaisesRegex(ValueError,'500,000'):worksheet_html(sheet)

    def test_report_snapshot_escapes_markup_and_is_detached(self):
        entry={'title':'<Important>','time':'Now','result':{'count':3}}
        job=PrintJob.report(entry);before=list(job.documents)
        self.assertIn('&lt;Important&gt;',job.documents[0])
        entry['title']='Changed';entry['result']['count']=9
        self.assertEqual(job.documents,before);self.assertEqual(job.title,'<Important>')
