import copy
import json
from pathlib import Path
import unittest
from zipfile import ZipFile
from test_mpx import fixture,scratch,documents
from statcraft.mpx import load_mpx,save_mpx
from statcraft.model import Column
from statcraft.io import UnsupportedFormatError,MISSING_SENTINEL
from statcraft.app import Presenter


class MpxAppendTests(unittest.TestCase):
    def test_numeric_append_identity_counts_and_original_members(self):
        with scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'out.mpx'
            metadata,first,_=documents(); first['MaxColumns_DEP']=1
            first['Data']['Columns'][0]['VarId']={'ClassId':440,'VarId':9}
            first['Data']['Columns'][1]['VarId']={'ClassId':440,'VarId':12}
            fixture(source,first=first); original=source.read_bytes()
            project=load_mpx(source); project.active_worksheet.columns.append(Column('Response',values=[3,None]))
            save_mpx(project,target); reopened=load_mpx(target)
            self.assertEqual(reopened.active_worksheet.columns[-1].values,[3,None])
            with ZipFile(source) as old,ZipFile(target) as new:
                for name in old.namelist():
                    if name!='/sheets/0/sheet.json':self.assertEqual(old.read(name),new.read(name))
                document=json.loads(new.read('/sheets/0/sheet.json'))
                self.assertEqual(document['MaxColumns_DEP'],3)
                self.assertEqual(document['Data']['Columns'][:2],first['Data']['Columns'])
                new_column=document['Data']['Columns'][-1]
                self.assertEqual(new_column['VarId']['VarId'],13)
                self.assertTrue(new_column['Id'])
                identity=new_column['Id']
            save_mpx(project,target)
            with ZipFile(target) as archive:self.assertEqual(json.loads(archive.read('/sheets/0/sheet.json'))['Data']['Columns'][-1]['Id'],identity)
            self.assertEqual(source.read_bytes(),original)

    def test_presenter_appended_response_analysis_and_rerun(self):
        with scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'copy.mpx'; fixture(source)
            p=Presenter();p.load(source);p.add_column('Response');p.set_cell(0,2,'8');p.set_cell(1,2,'9')
            entry=p.describe_column(2);p.save(target);q=Presenter();q.load(target)
            self.assertEqual(q.worksheet.columns[2].values,[8,9])
            entry=next(e for e in q.history if e.get('recipe',{}).get('action')=='describe_column')
            self.assertEqual(q.rerun_result(entry)['result'],entry['result'])
            q.set_cell(0,2,'10');q.save(Path(folder)/'again.mpx')
            self.assertEqual(load_mpx(Path(folder)/'again.mpx').active_worksheet.columns[2].values,[10,9])

    def test_unsupported_append_leaves_destination_intact(self):
        with scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'copy.mpx';fixture(source)
            columns=[Column('Text','text',['a']),Column('Long',values=[1,2,3]),
                Column('Date','date',[1]),Column('Metadata',metadata={'native':'unknown'}),Column('Reserved',values=[MISSING_SENTINEL])]
            for column in columns:
                project=load_mpx(source);project.active_worksheet.columns.append(column);target.write_bytes(b'existing destination')
                with self.assertRaises(UnsupportedFormatError):save_mpx(project,target)
                self.assertEqual(target.read_bytes(),b'existing destination')

    def test_active_native_model_formula_or_identity_rejected(self):
        with scratch() as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'copy.mpx'
            for key,value in [('HasDOE',True),('RegressionModel',[{'native':'unknown'}]),('FormulaManager',{'SetNodes':[1]})]:
                _,first,_=documents();first['Data'][key]=value;fixture(source,first=first)
                project=load_mpx(source);project.active_worksheet.columns.append(Column('Y',values=[2,3]))
                with self.assertRaises(UnsupportedFormatError):save_mpx(project,target)
                self.assertFalse(target.exists())
