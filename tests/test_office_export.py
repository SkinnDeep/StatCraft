import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from statcraft.office_export import OfficeSnapshot, export_docx, export_pptx, report_pages, clean, png_size, fit_image


class OfficeExportTests(unittest.TestCase):
    def test_docx_is_native_editable_text_and_title_style(self):
        from docx import Document
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'report.docx';snapshot=OfficeSnapshot('Strength report','N = 120\nMean = 572.4\nA&B <literal> Ω')
            export_docx(path,snapshot);doc=Document(path)
            self.assertEqual(doc.paragraphs[0].style.name,'Title')
            self.assertEqual([p.text for p in doc.paragraphs][1:],snapshot.report.splitlines())
            self.assertEqual(len(doc.inline_shapes),0)

    def test_pptx_retains_every_report_line_and_native_slide_geometry(self):
        from pptx import Presentation
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'report.pptx';text='\n'.join(f'Observation {i:04d}  {i*.125}' for i in range(160))
            count=export_pptx(path,OfficeSnapshot('Measurements',text));deck=Presentation(path)
            self.assertEqual(len(deck.slides),count);self.assertEqual(count,7)
            self.assertEqual((deck.slide_width,deck.slide_height),(12192000,6858000))
            extracted='\n'.join(s.text for slide in deck.slides for s in slide.shapes if s.has_text_frame)
            for i in range(160):self.assertEqual(extracted.count(f'Observation {i:04d}'),1)

    def test_all_relationship_targets_exist(self):
        import posixpath
        with tempfile.TemporaryDirectory() as folder:
            for suffix,writer in [('docx',export_docx),('pptx',export_pptx)]:
                path=Path(folder)/('out.'+suffix);writer(path,OfficeSnapshot('Title','Report'))
                with ZipFile(path) as z:
                    names=set(z.namelist())
                    for name in names:
                        if not name.endswith('.rels'):continue
                        base=posixpath.dirname(posixpath.dirname(name)) if name!='_rels/.rels' else ''
                        for rel in ET.fromstring(z.read(name)):
                            target=rel.get('Target')
                            self.assertNotEqual(rel.get('TargetMode'),'External')
                            destination=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(base,target))
                            self.assertIn(destination,names,(name,target))

    def test_literal_markup_and_invalid_xml_characters(self):
        self.assertEqual(clean('A\x00B\ud800C\nΩ'),'ABC\nΩ')
        with tempfile.TemporaryDirectory() as folder:
            for suffix,writer in [('docx',export_docx),('pptx',export_pptx)]:
                path=Path(folder)/('out.'+suffix);writer(path,OfficeSnapshot('A&B <literal>','Keep <tag>\x00 & "quotes"'))
                with ZipFile(path) as z:
                    for name in z.namelist():
                        if name.endswith(('.xml','.rels')):ET.fromstring(z.read(name))

    def test_pagination_wrap_preserves_characters_and_long_tokens(self):
        text='value '+('X'*350)+'\nend'
        pages=report_pages(text,width=100,lines_per_page=2)
        self.assertEqual(''.join(line for page in pages for line in page),text.replace('\n',''))
        self.assertTrue(all(len(line)<=100 for page in pages for line in page))

    def test_limits_and_invalid_images_fail_before_replacing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'existing.docx';path.write_bytes(b'keep')
            for snapshot in [OfficeSnapshot('',''),OfficeSnapshot('T','text',b'bad image'),OfficeSnapshot('T','x'*2000001)]:
                with self.assertRaises(ValueError):export_docx(path,snapshot)
                self.assertEqual(path.read_bytes(),b'keep')
            with self.assertRaisesRegex(ValueError,'200 slides'):report_pages('line\n'*5001)

    def test_atomic_failure_retains_existing_destination_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'report.docx';path.write_bytes(b'original')
            with patch('statcraft.office_export.os.replace',side_effect=PermissionError('in use')):
                with self.assertRaises(PermissionError):export_docx(path,OfficeSnapshot('Title','Report'))
            self.assertEqual(path.read_bytes(),b'original');self.assertEqual(list(Path(folder).iterdir()),[path])

    def test_image_aspect_ratio_and_limits(self):
        import struct
        data=b'\x89PNG\r\n\x1a\n'+b'\x00\x00\x00\rIHDR'+struct.pack('>II',1600,800)
        self.assertEqual(png_size(data),(1600,800));self.assertEqual(fit_image(data,1000,300),(600,300))

    def test_wide_report_uses_landscape_without_changing_text(self):
        from docx import Document
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'wide.docx';line='Column'.ljust(130)+'Mean'
            export_docx(path,OfficeSnapshot('Wide statistics',line))
            doc=Document(path);self.assertGreater(doc.sections[0].page_width,doc.sections[0].page_height)
            self.assertEqual(doc.paragraphs[1].text,line)

    def test_heatmap_report_is_human_readable_without_renderer_arrays(self):
        from statcraft.office_export import report_text
        text=report_text({'title':'Heatmap','result':{'graph':'expanded','panels':[{'kind':'heatmap','title':'Complete observations','x_labels':['Strength'],'values':[[573.73],[568.96]]}]}})
        self.assertIn('Rows: 2',text);self.assertIn('Strength',text)
        for internal in ('values=','panels','native-product','573.73'):self.assertNotIn(internal,text)
