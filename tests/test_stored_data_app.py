import copy
import unittest
from pathlib import Path
from types import SimpleNamespace
from statcraft.app import Presenter
from statcraft.model import Column,Matrix,Worksheet
from statcraft.calculator import evaluate
from test_mpx import scratch


class StoredDataAppTests(unittest.TestCase):
    def test_staged_replace_is_copied_and_undoable(self):
        p=Presenter();constants=[Column('Scale',values=[2])];matrices=[Matrix('Weights',2,2,[1,2,3,None])]
        p.replace_stored_data(constants,matrices);self.assertTrue(p.dirty)
        constants[0].values[0]=99;matrices[0].values[0]=99
        self.assertEqual(p.worksheet.constants[0].values,[2]);self.assertEqual(p.worksheet.matrices[0].cell(0,0),1)
        p.undo();self.assertEqual(p.worksheet.constants,[]);self.assertEqual(p.worksheet.matrices,[])
        p.redo();self.assertEqual(p.worksheet.matrices[0].as_rows(),[[1,3],[2,None]])

    def test_invalid_snapshot_does_not_change_document(self):
        p=Presenter();before=copy.deepcopy(p.worksheet)
        cases=[dict(constants=[Column('Text','text',['x'])]),dict(constants=[Column('A',values=[1]),Column('a',values=[2])]),
            dict(constants=[Column(' ',values=[1])]),dict(constants=[Column('K',values=[1.23456e30])]),
            dict(matrices=[Matrix('M',0,1,[])]),dict(matrices=[Matrix('M',1,1,[1.23456e30])])]
        for case in cases:
            with self.subTest(case=case),self.assertRaises(ValueError):p.replace_stored_data(**case)
            self.assertEqual(p.worksheet,before);self.assertFalse(p.can_undo)

    def test_imported_objects_are_view_only(self):
        p=Presenter();p.native_project=SimpleNamespace(statcraft_owned=False)
        with self.assertRaises(ValueError):p.replace_stored_data(constants=[Column('K',values=[2])])
        self.assertEqual(p.worksheet.constants,[])

    def test_constant_calculator_and_missing_propagation(self):
        sheet=Worksheet('X',[Column('X',values=[1,None,3])],constants=[Column('Scale',values=[2]),Column('Missing',values=[None])])
        self.assertEqual(evaluate('C1 * K1 + 1',sheet),[3,None,7])
        self.assertEqual(evaluate('K1 ^ 2',sheet),[4,4,4])
        self.assertEqual(evaluate('C1 + K2',sheet),[None,None,None])
        for expression in ('K0','K3','K1.__class__','M1','__import__("os")'):
            with self.subTest(expression=expression),self.assertRaises(ValueError):evaluate(expression,sheet)

    def test_stored_data_save_and_formula_after_reopen(self):
        p=Presenter();p.worksheet=Worksheet('X',[Column('X',values=[2,4,6])])
        p.replace_stored_data([Column('Scale',values=[3])],[Matrix('M',2,3,[1,2,3,4,5,6])])
        with scratch() as folder:
            path=Path(folder)/'objects.mpx';p.save(path);q=Presenter();q.load(path)
            self.assertTrue(q.native_project.statcraft_owned)
            q.calculate('C1 * K1','Adjusted');self.assertEqual(q.worksheet.columns[1].values,[6,12,18])
            self.assertEqual(q.worksheet.matrices[0].as_rows(),[[1,3,5],[2,4,6]])

    def test_delete_sheet_removes_bound_results_and_survives_save(self):
        p=Presenter();p.worksheet=Worksheet('First',[Column('X',values=[1,2,3])]);first=p.describe_column(0)
        p.add_worksheet('Second');p.set_cell(0,0,'10');deleted=p.describe_column(0)
        identifier=deleted['worksheet_id'];p.delete_worksheet()
        self.assertEqual(p.worksheet.name,'First');self.assertEqual(len(p.history),1)
        self.assertEqual(p.history[0]['worksheet_id'],first['worksheet_id']);self.assertNotIn(identifier,p.native_project.worksheet_ids)
        self.assertFalse(p.can_undo)
        with scratch() as folder:
            path=Path(folder)/'deleted.mpx';p.save(path);q=Presenter();q.load(path)
            self.assertEqual(len(q.native_project.worksheets),1);self.assertEqual(len(q.history),1)
        with self.assertRaises(ValueError):p.delete_worksheet()

    def test_delete_foreign_sheet_is_blocked(self):
        p=Presenter();p.native_project=SimpleNamespace(statcraft_owned=False,worksheets=[p.worksheet,p.worksheet])
        with self.assertRaises(ValueError):p.delete_worksheet()
