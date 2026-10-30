from pathlib import Path
import tempfile
import unittest
from statcraft.app import Presenter, format_entry
from statcraft.model import Column, Worksheet
from statcraft._mpx_fixture import write_subgroup_fixture


class VarianceAppTests(unittest.TestCase):
    def test_stacked_and_separate_groups_match_both_methods(self):
        p=Presenter()
        for method in ('Levene','Bartlett'):
            p.worksheet=Worksheet('Separate',[Column('A',values=[1,2,4,5]),Column('B',values=[2,4,8,10])])
            separate=p.equal_variances_columns([0,1],method)['result']
            p.worksheet=Worksheet('Stacked',[Column('Y',values=[1,2,2,4,4,8,5,10]),Column('Group','text',['A','B']*4)])
            stacked=p.equal_variances_stacked(0,1,method)['result']
            self.assertAlmostEqual(separate['test_statistic'],stacked['test_statistic'])
            self.assertAlmostEqual(separate['p_value'],stacked['p_value'])
            self.assertEqual(stacked['variables'],['A','B'])
            self.assertIn('H0:',format_entry(p.history[-1]))

    def test_incomplete_stacked_pairs_and_invalid_selection(self):
        p=Presenter(); p.worksheet=Worksheet('Stacked',[Column('Y',values=[1,2,2,4,4,8,5,10,None,99]),Column('Group','text',['A','B']*4+['A',''])])
        result=p.equal_variances_stacked(0,1)['result']
        self.assertEqual(result['missing_rows'],[9,10])
        self.assertEqual(result['count'],8)
        self.assertEqual(result['missing'],2)
        before=len(p.history)
        with self.assertRaises(ValueError): p.equal_variances_columns([0,0])
        with self.assertRaises(ValueError): p.equal_variances_stacked(0,0)
        self.assertEqual(len(p.history),before)

    def test_mpx_persistence_and_rerun_keeps_old_test(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source,target=Path(folder)/'source.mpx',Path(folder)/'copy.mpx'
            write_subgroup_fixture(source)
            p=Presenter(); p.load(source)
            entry=p.equal_variances_stacked(0,1,'Bartlett')
            p.save(target)
            q=Presenter(); q.load(target)
            old=next(e for e in q.history if e['origin']=='statcraft')
            self.assertEqual(old['result']['test_statistic'],entry['result']['test_statistic'])
            q.set_cell(0,0,'10')
            self.assertTrue(q.result_stale(old))
            fresh=q.rerun_result(old)
            self.assertFalse(q.result_stale(fresh))
            self.assertNotEqual(fresh['result']['test_statistic'],old['result']['test_statistic'])
            self.assertEqual(fresh['recipe']['parameters']['method'],'Bartlett')
