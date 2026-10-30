import tempfile
from pathlib import Path
import unittest
from statcraft.app import Presenter
from statcraft.model import Column,Worksheet
from statcraft._mpx_fixture import write_fixture


class WorkbookAppTests(unittest.TestCase):
    def scratch(self):return tempfile.TemporaryDirectory(dir=Path(__file__).parent)

    def test_new_mpx_save_edit_overwrite_and_result_rerun(self):
        p=Presenter();p.worksheet=Worksheet('Measurements',[Column('X',values=[1,2,3])])
        entry=p.describe_column(0)
        with self.scratch() as folder:
            path=Path(folder)/'new.mpx';p.save(path)
            self.assertTrue(p.native_project.statcraft_owned)
            self.assertIs(p.worksheet,p.native_project.active_worksheet)
            self.assertIs(p.result_worksheet(entry),p.worksheet);self.assertFalse(p.result_stale(entry))
            p.set_cell(0,0,'9');p.save(path);q=Presenter();q.load(path)
            self.assertTrue(q.native_project.statcraft_owned);self.assertEqual(q.worksheet.columns[0].values,[9,2,3])
            self.assertEqual(q.project_path,str(path))
            entry=q.history[0];self.assertTrue(q.result_stale(entry))
            self.assertFalse(q.result_stale(q.rerun_result(entry)))

    def test_tabs_source_identity_after_save_and_sheet_switch(self):
        p=Presenter();p.worksheet=Worksheet('First',[Column('X',values=[2,4,6])]);entry=p.describe_column(0)
        p.add_worksheet('Second');p.set_cell(0,0,'12')
        self.assertEqual(p.result_worksheet(entry).name,'First')
        with self.scratch() as folder:
            path=Path(folder)/'two.mpx';p.save(path);q=Presenter();q.load(path)
            self.assertEqual([s.name for s in q.native_project.worksheets],['First','Second'])
            self.assertEqual(q.native_project.active_index,1)
            entry=q.history[0];self.assertEqual(q.rerun_result(entry)['result']['mean'],4)
            self.assertEqual(q.native_project.active_index,0)

    def test_duplicate_is_independent_and_rename_keeps_result_binding(self):
        p=Presenter();p.worksheet=Worksheet('Runs',[Column('X',values=[1,2,3])],metadata={'doe':{'test':'metadata'}})
        entry=p.describe_column(0);p.duplicate_worksheet('Replicate');p.set_cell(0,0,'8')
        self.assertEqual(p.native_project.worksheets[0].columns[0].values,[1,2,3])
        self.assertEqual(p.worksheet.metadata,{'doe':{'test':'metadata'}})
        p.select_worksheet(0);p.rename_worksheet('Original runs')
        self.assertEqual(entry['worksheet_name'],'Original runs');self.assertFalse(p.result_stale(entry))
        with self.assertRaises(ValueError):p.rename_worksheet('Replicate')

    def test_imported_native_structure_remains_protected(self):
        with self.scratch() as folder:
            path=Path(folder)/'native.mpx';write_fixture(path);p=Presenter();p.load(path)
            names=[s.name for s in p.native_project.worksheets]
            for action in (lambda:p.add_worksheet('New'),lambda:p.rename_worksheet('Changed'),lambda:p.duplicate_worksheet('Copy')):
                with self.assertRaises(ValueError):action()
                self.assertEqual([s.name for s in p.native_project.worksheets],names)

    def test_generated_design_metadata_and_analysis_persist_in_new_mpx(self):
        p=Presenter();p.create_factorial([dict(name=x,low=-1,high=1) for x in 'AB'],replicates=2,randomize=False)
        p.add_column('Response')
        for row in range(8):
            a,b=p.worksheet.row(row)[4:6];p.set_cell(row,6,str(10+2*a-3*b+1.5*a*b+(1 if row<4 else -1)))
        result=p.analyze_factorial(6,[4,5])['result']
        with self.scratch() as folder:
            path=Path(folder)/'design.mpx';p.save(path);q=Presenter();q.load(path)
            self.assertEqual(q.worksheet.metadata['doe'],p.worksheet.metadata['doe'])
            entry=next(e for e in q.history if e.get('recipe',{}).get('action')=='analyze_factorial')
            self.assertEqual(q.rerun_result(entry)['result'],result)

    def test_unsupported_numeric_writer_failure_keeps_original_document(self):
        p=Presenter();p.worksheet=Worksheet('Dates',[Column('Dates','date',[-1,45001])]);old=p.worksheet
        with self.scratch() as folder:
            path=Path(folder)/'new.mpx';path.write_bytes(b'unchanged destination')
            with self.assertRaises(ValueError):p.save(path)
            self.assertIs(p.worksheet,old);self.assertIsNone(p.native_project)
            self.assertEqual(path.read_bytes(),b'unchanged destination')
