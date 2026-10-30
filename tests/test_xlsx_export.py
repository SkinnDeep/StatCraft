"""Independent Excel-reader and project-preservation checks for native XLSX exports."""
import copy
from datetime import datetime
from pathlib import Path
import unittest
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from openpyxl import load_workbook
from test_mpx import scratch
from statcraft.xlsx_export import write_workbook,convert_mpx
from statcraft.model import Worksheet,Column,datetime_to_serial
from statcraft.app import Presenter

class ExcelExportTests(unittest.TestCase):
    def test_real_workbook_multiple_typed_sheets_dates_missing_and_literal_formulas(self):
        date=datetime(2026,10,27,14,30)
        s=Worksheet('Trial / A',[Column('Value',values=[1.25,None,-3]),Column('Label','text',['=1+1','  padded  ','0012']),Column('When','date',[datetime_to_serial(date),datetime_to_serial(datetime(1900,2,28)),None])])
        other=Worksheet('Trial : A',[Column('Other',values=[4,5])])
        before=copy.deepcopy([s,other])
        with scratch() as tmp:
            path=Path(tmp)/'typed.xlsx';result=write_workbook(path,[s,other])
            w=load_workbook(path,data_only=False)
            try:
                self.assertEqual(w.sheetnames,['Trial _ A','Trial _ A (2)'])
                first=w.worksheets[0]
                self.assertEqual(first['A2'].value,1.25);self.assertIsNone(first['A3'].value)
                self.assertEqual(first['B2'].value,'=1+1');self.assertEqual(first['B2'].data_type,'s')
                self.assertEqual(first['B3'].value,'  padded  ');self.assertEqual(first['B4'].value,'0012')
                self.assertEqual(first['C2'].value,date);self.assertEqual(first['C3'].value,datetime(1900,2,28))
                self.assertEqual(first.freeze_panes,'A2');self.assertEqual(first.auto_filter.ref,'A1:C4')
                self.assertEqual(result['rows'],[3,2])
            finally:w.close()
        self.assertEqual([s,other],before)

    def test_long_names_duplicates_early_dates_and_empty_column(self):
        sheets=[Worksheet('X'*60,[Column('',values=[])]),Worksheet('x'*60,[Column('Early','date',[0,1,2,61])])]
        with scratch() as tmp:
            path=Path(tmp)/'long.xlsx';write_workbook(path,sheets);w=load_workbook(path)
            try:
                self.assertTrue(all(len(name)<=31 for name in w.sheetnames))
                self.assertNotEqual(w.sheetnames[0].casefold(),w.sheetnames[1].casefold())
                self.assertEqual(w.worksheets[1]['A2'].value,'1899-12-30')
                self.assertEqual(w.worksheets[1]['A4'].value,datetime(1900,1,1))
                self.assertEqual(w.worksheets[1]['A5'].value,datetime(1900,3,1))
            finally:w.close()

    def test_bad_cell_does_not_replace_existing_destination(self):
        with scratch() as tmp:
            path=Path(tmp)/'exists.xlsx';path.write_bytes(b'keep')
            with self.assertRaises(ValueError):write_workbook(path,[Worksheet('Data',[Column('Text','text',['x'*32768])])])
            self.assertEqual(path.read_bytes(),b'keep')

    def test_presenter_export_keeps_project_dirty_history_and_path(self):
        p=Presenter();p.worksheet=Worksheet('Data',[Column('Value',values=[1,2,3])]);p.describe_column(0)
        p.add_worksheet('Next');p.worksheet.columns=[Column('Second',values=[9])]
        before=(p.project_path,p.dirty,copy.deepcopy(p.history),p.worksheet)
        with scratch() as tmp:
            a=p.export_excel(Path(tmp)/'all.xlsx');b=p.export_excel(Path(tmp)/'current.xlsx',False)
            self.assertEqual(a['worksheets'],2);self.assertEqual(b['worksheets'],1)
        self.assertEqual((p.project_path,p.dirty,p.history,p.worksheet),before)

    def test_mpx_converter_reads_all_sheets_without_modifying_source(self):
        with scratch() as tmp:
            source=Path(tmp)/'source.mpx';target=Path(tmp)/'data.xlsx'
            p=Presenter();p.worksheet=Worksheet('Measurements',[Column('Strength',values=[12.25,13.5])]);p.add_worksheet('Labels');p.worksheet.columns=[Column('Batch','text',['A','B'])];p.save(source)
            raw=source.read_bytes();result=convert_mpx(source,target)
            self.assertEqual(result['worksheets'],2);self.assertEqual(source.read_bytes(),raw)
            w=load_workbook(target)
            try:self.assertEqual(w['Measurements']['A2'].value,12.25);self.assertEqual(w['Labels']['A3'].value,'B')
            finally:w.close()

    def test_source_path_protected_even_with_excel_extension(self):
        with scratch() as tmp:
            path=Path(tmp)/'original.xlsx';path.write_bytes(b'keep')
            with self.assertRaisesRegex(ValueError,'source project'):write_workbook(path,[Worksheet('Data',[Column('A',values=[1])])],[path])
            self.assertEqual(path.read_bytes(),b'keep')

    def test_xml_control_characters_and_escape_literals_remain_valid_package(self):
        with scratch() as tmp:
            path=Path(tmp)/'escapes.xlsx';write_workbook(path,[Worksheet('Data',[Column('Text','text',['a\x01b','_x0041_','a&<b'])])])
            with ZipFile(path) as z:
                raw=z.read('xl/worksheets/sheet1.xml');ET.fromstring(raw)
                self.assertIn(b'_x0001_',raw);self.assertIn(b'_x005F_x0041_',raw)
                self.assertNotIn(b'<f>',raw)
