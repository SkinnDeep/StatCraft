import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
from statcraft._mpx_fixture import write_blob_fixture
from statcraft.mpx import load_mpx, save_mpx
from statcraft.io import FormatError, UnsupportedFormatError
from statcraft.app import Presenter


class NumericBlobTests(unittest.TestCase):
    def scratch(self): return tempfile.TemporaryDirectory(dir=Path(__file__).parent)

    def rewrite(self,path,change):
        with zipfile.ZipFile(path) as archive: members={info.filename:archive.read(info) for info in archive.infolist()}
        sheet=json.loads(members['/sheets/0/sheet.json'])
        change(members,sheet)
        members['/sheets/0/sheet.json']=json.dumps(sheet).encode()
        with zipfile.ZipFile(path,'w') as archive:
            for name,raw in members.items(): archive.writestr(name,raw)

    def test_load_and_unchanged_copy_byte_identical(self):
        with self.scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'out.mpx'; write_blob_fixture(source)
            project=load_mpx(source)
            self.assertEqual(project.active_worksheet.columns[0].values,[1,2,3])
            save_mpx(project,target); self.assertEqual(source.read_bytes(),target.read_bytes())

    def test_edit_keeps_blob_reference_and_other_parts(self):
        with self.scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'out.mpx'; write_blob_fixture(source)
            original=source.read_bytes(); p=Presenter(); p.load(source); p.set_cell(0,0,'9'); p.save(target)
            self.assertEqual(load_mpx(target).active_worksheet.columns[0].values,[9,2,3])
            with zipfile.ZipFile(target) as out,zipfile.ZipFile(source) as old:
                doc=json.loads(out.read('/sheets/0/sheet.json'))
                self.assertEqual(doc['Data']['Columns'][0]['WorksheetVarBody']['VarData']['VarDataBody']['NumericData'],'/blobs/blob1?size=3')
                self.assertEqual(struct.unpack('<3d',out.read('/blobs/blob1')),(9,2,3))
                for name in old.namelist():
                    if name not in ('/sheets/0/sheet.json','/blobs/blob1'): self.assertEqual(old.read(name),out.read(name))
            self.assertEqual(source.read_bytes(),original)

    def test_rename_does_not_reencode_blob(self):
        with self.scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'out.mpx'; write_blob_fixture(source)
            p=Presenter(); p.load(source); p.rename_column(0,'Renamed'); p.save(target)
            with zipfile.ZipFile(source) as old,zipfile.ZipFile(target) as out: self.assertEqual(old.read('/blobs/blob1'),out.read('/blobs/blob1'))

    def test_missing_and_wrong_sized_blob_rejected(self):
        for change in (lambda members,sheet:members.pop('/blobs/blob1'), lambda members,sheet:members.update({'/blobs/blob1':b'bad'})):
            with self.scratch() as folder:
                source=Path(folder)/'in.mpx'; write_blob_fixture(source); self.rewrite(source,change)
                with self.assertRaises(FormatError): load_mpx(source)

    def test_external_unsafe_mismatched_references_rejected(self):
        for reference in ('https://example.com/data','../blob1','/blobs/blob1?size=4','/blobs/blob1?size=3&x=1'):
            with self.scratch() as folder:
                source=Path(folder)/'in.mpx'; write_blob_fixture(source)
                def mutate(members,sheet): sheet['Data']['Columns'][0]['WorksheetVarBody']['VarData']['VarDataBody']['NumericData']=reference
                self.rewrite(source,mutate)
                with self.assertRaises(FormatError): load_mpx(source)

    def test_shared_blob_edit_fails_before_publication(self):
        with self.scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'out.mpx'; write_blob_fixture(source)
            self.rewrite(source,lambda members,sheet:sheet['Data']['Columns'].append(copy.deepcopy(sheet['Data']['Columns'][0])))
            p=Presenter(); p.load(source); p.set_cell(0,0,'9')
            with self.assertRaises(UnsupportedFormatError): p.save(target)
            self.assertFalse(target.exists())

    def test_missing_numeric_sentinel_decoded_and_preserved(self):
        with self.scratch() as folder:
            source=Path(folder)/'in.mpx'; write_blob_fixture(source)
            self.rewrite(source,lambda members,sheet:members.update({'/blobs/blob1':struct.pack('<3d',1,1.23456e30,3)}))
            self.assertEqual(load_mpx(source).active_worksheet.columns[0].values,[1,None,3])
