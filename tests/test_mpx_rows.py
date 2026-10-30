import copy
import json
from pathlib import Path
import struct
import unittest
from zipfile import ZipFile
from statcraft._mpx_fixture import write_blob_fixture,write_factorial_fixture
from statcraft.app import Presenter
from statcraft.io import UnsupportedFormatError
from statcraft.mpx import load_mpx,save_mpx
from test_mpx import fixture,documents,scratch
import test_mpx_blobs as blob_tests


class MpxRowTests(unittest.TestCase):
    def test_inline_growth_ragged_and_shrink_keep_identities(self):
        with scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'copy.mpx';write_factorial_fixture(source)
            p=Presenter();p.load(source);p.worksheet.columns[0].values.extend([None,1])
            p.save(target);q=load_mpx(target)
            self.assertEqual(q.active_worksheet.columns[0].values,[-1,1,-1,1,-1,1,-1,1,None,1])
            self.assertEqual(len(q.active_worksheet.columns[1].values),8)
            p.worksheet.columns[0].values=[];p.save(target)
            self.assertEqual(load_mpx(target).active_worksheet.columns[0].values,[])

    def test_blob_growth_counts_uri_bytes_and_preserved_members(self):
        with scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'copy.mpx';write_blob_fixture(source)
            original=source.read_bytes();p=Presenter();p.load(source);old=p.describe_column(0)
            p.add_rows(2);p.set_cell(4,0,'7');self.assertTrue(p.result_stale(old));p.save(target)
            q=Presenter();q.load(target);self.assertEqual(q.worksheet.columns[0].values,[1,2,3,None,7])
            entry=next(e for e in q.history if e.get('recipe',{}).get('action')=='describe_column')
            self.assertEqual(q.rerun_result(entry)['result']['count'],4)
            with ZipFile(source) as oldzip,ZipFile(target) as newzip:
                body=json.loads(newzip.read('/sheets/0/sheet.json'))['Data']['Columns'][0]['WorksheetVarBody']['VarData']['VarDataBody']
                self.assertEqual((body['CellCt'],body['NumericData']),(5,'/blobs/blob1?size=5'))
                self.assertEqual(len(newzip.read('/blobs/blob1')),40)
                for name in oldzip.namelist():
                    if name not in ('/sheets/0/sheet.json','/blobs/blob1'):self.assertEqual(oldzip.read(name),newzip.read(name))
            self.assertEqual(source.read_bytes(),original)
            q.worksheet.columns[0].values=[9];q.save(Path(folder)/'short.mpx')
            self.assertEqual(load_mpx(Path(folder)/'short.mpx').active_worksheet.columns[0].values,[9])

    def test_resize_plus_append_and_repeated_save(self):
        with scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'copy.mpx';write_blob_fixture(source)
            p=Presenter();p.load(source);p.add_column('Response');p.add_rows(2);p.set_cell(4,1,'11');p.save(target);p.save(target)
            q=Presenter();q.load(target)
            self.assertEqual(q.worksheet.row_count,5);self.assertEqual(q.worksheet.columns[1].values,[None,None,None,None,11])
            p.undo();p.undo();self.assertEqual(p.worksheet.row_count,3)

    def test_legacy_extent_and_display_range_preserved_or_expanded(self):
        with scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'copy.mpx';write_blob_fixture(source)
            def changes(members,sheet):
                sheet['MaxRows_DEP']=10
                sheet['Data']['Columns'][0]['WorksheetVarBody']['Format']['Value']={'MinValue':0,'MaxValue':8}
            blob_tests.NumericBlobTests().rewrite(source,changes)
            p=Presenter();p.load(source);p.add_rows(1);p.set_cell(3,0,'12');p.save(target)
            with ZipFile(target) as archive:
                sheet=json.loads(archive.read('/sheets/0/sheet.json'))
                self.assertEqual(sheet['MaxRows_DEP'],10)
                settings=sheet['Data']['Columns'][0]['WorksheetVarBody']['Format']['Value']
                self.assertEqual((settings['MinValue'],settings['MaxValue']),(0,12))

    def test_output_json_shared_reference_rejected_before_publication(self):
        for reference in ('/blobs/blob1?size=3','/blobs/blob1','<ref>/blobs/blob1</ref>'):
            with scratch() as folder:
                source,target=Path(folder)/'in.mpx',Path(folder)/'copy.mpx';write_blob_fixture(source)
                blob_tests.NumericBlobTests().rewrite(source,lambda members,sheet:members.update({'/graphs/retained.json':json.dumps({'Ref':reference}).encode()}))
                p=Presenter();p.load(source);p.add_rows(1);target.write_bytes(b'keep destination')
                with self.assertRaisesRegex(UnsupportedFormatError,'shared'):p.save(target)
                self.assertEqual(target.read_bytes(),b'keep destination')

    def test_unknown_json_blocks_blob_edit(self):
        with scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'copy.mpx';write_blob_fixture(source)
            blob_tests.NumericBlobTests().rewrite(source,lambda members,sheet:members.update({'/graphs/unknown.json':b'opaque unknown content'}))
            p=Presenter();p.load(source);p.add_rows(1)
            with self.assertRaisesRegex(UnsupportedFormatError,'unknown JSON'):p.save(target)
            self.assertFalse(target.exists())

    def test_locked_sorted_converted_and_active_model_resizes_rejected(self):
        mutators=[lambda w:w['VarData'].update(Locked=True),
            lambda w:w.update(Ordering={'NumericOrder':[1,2,3]}),
            lambda w:w['Format'].update(Value={'DataToStr':[1]})]
        with scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'copy.mpx'
            for mutate in mutators:
                write_blob_fixture(source)
                blob_tests.NumericBlobTests().rewrite(source,lambda members,sheet:mutate(sheet['Data']['Columns'][0]['WorksheetVarBody']))
                p=Presenter();p.load(source);p.add_rows(1)
                with self.assertRaises(UnsupportedFormatError):p.save(target)
                self.assertFalse(target.exists())

    def test_untyped_placeholders_not_initialized_by_add_rows(self):
        with scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'copy.mpx';write_blob_fixture(source)
            def placeholder(members,sheet):
                column=copy.deepcopy(sheet['Data']['Columns'][0]);column['WorksheetVarBody']['Name']=''
                wrapper=column['WorksheetVarBody'];wrapper['Format']['Key']=0;wrapper['VarData']['Data']=0
                wrapper['VarData']['VarDataBody'].update(CellCt=0,ColCt=0,HasNumericData=False,NumericData=[])
                sheet['Data']['Columns'].append(column)
            blob_tests.NumericBlobTests().rewrite(source,placeholder)
            p=Presenter();p.load(source);p.add_rows(2);self.assertEqual(p.worksheet.columns[1].values,[])
            p.save(target);self.assertEqual(load_mpx(target).active_worksheet.columns[1].values,[])
