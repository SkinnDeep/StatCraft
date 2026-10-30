import copy
import json
from pathlib import Path
import unittest
from zipfile import ZipFile
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.mpx import load_mpx,save_mpx
from statcraft.mpx_create import create_project,save_owned,MEMBER,SCHEMA,TEXT_SCHEMA
from test_mpx import scratch
from test_mpx_create import rewrite


class TextWorkbookTests(unittest.TestCase):
    def test_native_string_envelope_and_original_missing_semantics(self):
        values=['',None,'*','Ω','line1\nline2','"quoted", value','🧪']
        p=create_project([Worksheet('Mixed',[Column('Group','text',values),Column('X',values=[1,2])])])
        with scratch() as folder:
            path=Path(folder)/'mixed.mpx';save_owned(p,path);q=load_mpx(path)
            self.assertTrue(q.statcraft_owned);self.assertEqual(q.active_worksheet.columns[0].values,values)
            with ZipFile(path) as archive:
                sheet=json.loads(archive.read('/sheets/0/sheet.json'))
                wrapper=sheet['Data']['Columns'][0]['WorksheetVarBody'];body=wrapper['VarData']['VarDataBody']
                self.assertEqual((wrapper['Format']['Key'],wrapper['Format']['Value']['ClassId'],wrapper['VarData']['Data']),(3,18,2))
                self.assertEqual(body['TextData'],['' if v is None else v for v in values])
                self.assertNotIn('NumericData',body);self.assertFalse(body['HasNumericData']);self.assertTrue(body['HasTextData'])
                self.assertEqual(body['CharCt'],max(len(v.encode('utf-16-le'))//2 for v in values if v is not None))
                metadata=json.loads(archive.read(MEMBER));self.assertEqual(metadata['schema'],TEXT_SCHEMA)
                self.assertEqual(metadata['sheets'][0]['missing_text'],{'0':[1]})

    def test_blank_text_sheet_and_growth_save_overwrite(self):
        p=Presenter();p.worksheet=Worksheet('Labels',[Column('Label','text',[])])
        with scratch() as folder:
            path=Path(folder)/'labels.mpx';p.save(path);p.add_rows(3);p.set_cell(1,0,'A');p.save(path)
            q=Presenter();q.load(path);self.assertEqual(q.worksheet.columns[0].values,[None,'A',None])
            q.set_cell(2,0,'');q.save(path);r=Presenter();r.load(path)
            self.assertEqual(r.worksheet.columns[0].values,[None,'A',''])

    def test_previous_v1_archive_remains_editable_and_upgrades(self):
        source=Path(__file__).parent/'fixtures/statcraft-profile-v1.mpx';p=Presenter();p.load(source)
        self.assertTrue(p.native_project.statcraft_owned);self.assertEqual(p.native_project._owned_schema,SCHEMA)
        p.add_column('Group','text');p.set_cell(0,2,'Batch A')
        with scratch() as folder:
            path=Path(folder)/'upgraded.mpx';p.save(path);q=Presenter();q.load(path)
            self.assertTrue(q.native_project.statcraft_owned);self.assertEqual(q.native_project._owned_schema,TEXT_SCHEMA)
            self.assertEqual(q.worksheet.columns[2].values,['Batch A',None,None,None,None])

    def test_grouped_scatter_text_recipe_roundtrip_and_missing_alignment(self):
        p=Presenter();p.worksheet=Worksheet('Grouped',[Column('X',values=[1,2,3,4,5,6]),
            Column('Y',values=[2,4,7,9,10,12]),Column('Group','text',['A','A','B','B',None,''])])
        entry=p.scatter_plot(0,1,'regression_groups',2);self.assertEqual(entry['result']['count'],4)
        with scratch() as folder:
            path=Path(folder)/'groups.mpx';p.save(path);q=Presenter();q.load(path)
            entry=q.history[0];self.assertEqual(q.rerun_result(entry)['result'],entry['result'])
            q.set_cell(0,2,'Renamed');self.assertTrue(q.result_stale(entry))

    def test_missing_map_cannot_hide_nonempty_native_text(self):
        with scratch() as folder:
            path=Path(folder)/'tampered.mpx';save_owned(create_project([Worksheet('T',[Column('T','text',['A'])])]),path)
            def mutate(members):
                sidecar=json.loads(members[MEMBER]);sidecar['sheets'][0]['missing_text']={'0':[0]};members[MEMBER]=json.dumps(sidecar).encode()
            rewrite(path,mutate);q=load_mpx(path)
            self.assertFalse(getattr(q,'statcraft_owned',False));self.assertEqual(q.active_worksheet.columns[0].values,['A'])

    def test_invalid_missing_maps_do_not_grant_profile(self):
        for missing in ({'0':[0,0]},{'0':[-1]},{'0':[True]},{'00':[0]},{'1':[0]},{'0':'all'}):
            with scratch() as folder:
                path=Path(folder)/'invalid.mpx';save_owned(create_project([Worksheet('T',[Column('T','text',[None])])]),path)
                def mutate(members):
                    sidecar=json.loads(members[MEMBER]);sidecar['sheets'][0]['missing_text']=missing;members[MEMBER]=json.dumps(sidecar).encode()
                rewrite(path,mutate);self.assertFalse(getattr(load_mpx(path),'statcraft_owned',False))

    def test_first_text_entry_auto_type_and_undo(self):
        p=Presenter();p.worksheet=Worksheet('New',[Column('C1',metadata={'auto_type':True})])
        p.set_cell(0,0,'Batch A');self.assertEqual(p.worksheet.columns[0].kind,'text')
        self.assertEqual(p.worksheet.columns[0].values,['Batch A']);p.undo()
        self.assertEqual(p.worksheet.columns[0].kind,'number');self.assertEqual(p.worksheet.columns[0].values,[])
        with self.assertRaises(ValueError):p.set_cell(0,0,'NaN')
        self.assertEqual(p.worksheet.columns[0].kind,'number')

    def test_invalid_unicode_leaves_existing_file_unchanged(self):
        with scratch() as folder:
            path=Path(folder)/'keep.mpx';path.write_bytes(b'unchanged')
            p=Presenter();p.worksheet=Worksheet('Invalid',[Column('T','text',['\ud800'])])
            with self.assertRaises(ValueError):p.save(path)
            self.assertEqual(path.read_bytes(),b'unchanged');self.assertIsNone(p.native_project)
