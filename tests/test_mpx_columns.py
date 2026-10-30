"""Structural MPX edits retain object identity and unknown archive members."""
import copy
import json
from pathlib import Path
import unittest
from zipfile import ZipFile
from test_mpx import fixture, scratch, documents
from statcraft.app import Presenter
from statcraft.model import Column
from statcraft.mpx import load_mpx, save_mpx
from statcraft.io import UnsupportedFormatError
from statcraft._mpx_fixture import write_blob_fixture


class MpxColumnTests(unittest.TestCase):
    def test_insert_move_delete_repeated_save_and_undo(self):
        with scratch() as folder:
            source,target,again=[Path(folder)/n for n in ('in.mpx','out.mpx','again.mpx')]
            fixture(source); original=source.read_bytes()
            p=Presenter();p.load(source);p.insert_columns(0,2)
            p.rename_column(0,'Inserted');p.set_cell(0,0,'17')
            p.move_columns([3],'before_c1');p.delete_columns([2]);p.save(target)
            self.assertEqual([(c.name,c.values) for c in load_mpx(target).active_worksheet.columns],
                             [(c.name,c.values) for c in p.worksheet.columns])
            with ZipFile(target) as z:
                doc=json.loads(z.read('/sheets/0/sheet.json'))
                identifier=doc['Data']['Columns'][1]['Id']
            p.move_columns([1],'after_last');p.save(again)
            with ZipFile(again) as z:
                doc=json.loads(z.read('/sheets/0/sheet.json'))
                self.assertEqual(doc['Data']['Columns'][-1]['Id'],identifier)
            p.undo();p.undo();p.redo();p.save(again)
            self.assertEqual(source.read_bytes(),original)
            with ZipFile(source) as old,ZipFile(again) as new:
                for name in old.namelist():
                    if name not in ('/sheets/0/sheet.json','/statcraft/session-v1.json'):
                        self.assertEqual(old.read(name),new.read(name))

    def test_move_blob_column_then_edit_keeps_member_identity(self):
        with scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'out.mpx';write_blob_fixture(source)
            p=Presenter();p.load(source);p.insert_columns(0);p.set_cell(0,0,'7')
            p.set_cell(0,1,'9');p.save(target)
            q=load_mpx(target)
            self.assertEqual(q.active_worksheet.columns[1].values,[9,2,3])
            with ZipFile(target) as z:
                doc=json.loads(z.read('/sheets/0/sheet.json'))
                self.assertEqual(doc['Data']['Columns'][1]['WorksheetVarBody']['VarData']['VarDataBody']['NumericData'],'/blobs/blob1?size=3')

    def test_native_dependencies_reject_before_mutation(self):
        for key,value in [('HasDOE',True),('FormulaManager',{'SetNodes':[1]}),('RegressionModel',[{'a':1}])]:
            with scratch() as folder:
                source=Path(folder)/'in.mpx';_,first,_=documents();first['Data'][key]=value;fixture(source,first=first)
                p=Presenter();p.load(source);before=copy.deepcopy(p.worksheet)
                for operation in (lambda:p.insert_columns(0),lambda:p.move_columns([0]),lambda:p.delete_columns([0])):
                    with self.assertRaises(UnsupportedFormatError):operation()
                    self.assertEqual(p.worksheet,before);self.assertFalse(p._undo_stack)

    def test_deleted_native_objects_and_blobs_are_retained_without_reference(self):
        with scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'out.mpx';write_blob_fixture(source)
            p=Presenter();p.load(source);p.delete_columns([0]);p.save(target)
            self.assertEqual(load_mpx(target).active_worksheet.columns,[])
            with ZipFile(source) as a,ZipFile(target) as b:
                self.assertEqual(a.read('/blobs/blob1'),b.read('/blobs/blob1'))

    def test_moving_equal_columns_uses_identity_and_used_extent(self):
        p=Presenter();p.worksheet.columns=[Column("C"+str(i+1),metadata={"auto_type":True}) for i in range(16)]
        p.set_cell(0,0,'1');p.set_cell(0,1,'2');p.set_cell(0,2,'3')
        p.move_columns([0],'after_last')
        self.assertEqual([c.values for c in p.worksheet.columns[:3]],[[2.0],[3.0],[1.0]])
        p.move_columns([4],'before_column',5)
        self.assertEqual(len(p.worksheet.columns),16)

    def test_writer_rejects_type_or_native_metadata_tampering(self):
        with scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'out.mpx';fixture(source)
            p=load_mpx(source);p.active_worksheet.columns[0].metadata['unknown']=1
            target.write_bytes(b'old')
            with self.assertRaises(UnsupportedFormatError):save_mpx(p,target)
            self.assertEqual(target.read_bytes(),b'old')
