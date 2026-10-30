from pathlib import Path
import tempfile
import unittest
from statcraft.app import Presenter, format_entry
from statcraft.model import Worksheet, Column
from statcraft._mpx_fixture import write_fixture, write_subgroup_fixture


class SubgroupAppTests(unittest.TestCase):
    def test_rows_and_interleaved_stacked_layouts_agree(self):
        p=Presenter()
        p.worksheet=Worksheet('Rows',[Column('A',values=[1,4,7]),Column('B',values=[3,6,9])])
        rows=p.xbar_r_rows([0,1])['result']
        p.worksheet=Worksheet('Stacked',[Column('Y',values=[1,4,7,3,6,9]),Column('Group','text',['A','B','C','A','B','C'])])
        stacked=p.xbar_r_stacked(0,1)['result']
        for key in ('means','ranges','within_stdev','xbar_center','xbar_lcl','xbar_ucl','r_center','r_lcl','r_ucl'):
            self.assertEqual(rows[key],stacked[key])
        self.assertEqual(stacked['subgroup_labels'],['A','B','C'])
        self.assertEqual(rows['means'],[2,5,8])
        self.assertEqual(rows['ranges'],[2,2,2])

    def test_missing_gaps_and_partially_missing_rows(self):
        p=Presenter(); p.worksheet=Worksheet('Rows',[Column('A',values=[1,None,4]),Column('B',values=[3,None,8])])
        result=p.xbar_r_rows([0,1])['result']
        self.assertEqual(result['means'],[2,None,6])
        self.assertIn('Xbar-R',format_entry(p.history[-1]))
        p.set_cell(1,0,'1'); before=len(p.history)
        with self.assertRaises(ValueError): p.xbar_r_rows([0,1])
        self.assertEqual(len(p.history),before)

    def test_changed_structure_is_not_saved_after_rerun(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source,target=Path(folder)/'source.mpx',Path(folder)/'copy.mpx'
            write_fixture(source)
            p=Presenter(); p.load(source)
            # One measurement column with consecutive subgroup-ID blocks.
            p.worksheet.columns[0].values=[1,3,4,6,7,9]
            p.worksheet.columns.append(Column('Group','text',['A','A','B','B','C','C']))
            entry=p.xbar_r_stacked(0,1)
            self.assertFalse(p.result_stale(entry))
            p.set_cell(0,0,'5'); updated=p.rerun_result(entry)
            self.assertEqual(updated['result']['means'],[4,5,8])
            self.assertEqual(entry['result']['means'],[2,5,8])
            # Structural writes remain deliberately unsupported for this synthetic source.
            with self.assertRaises(ValueError): p.save(target)
            self.assertTrue(p.dirty)

    def test_invalid_selection_and_unknown_measurement_types(self):
        p=Presenter(); p.worksheet=Worksheet('Rows',[Column('Y',values=[1,2]),Column('Group','text',['A','A'])])
        for indices in ([0],[0,0],[0,1]):
            with self.assertRaises(ValueError): p.xbar_r_rows(indices)
        with self.assertRaises(ValueError): p.xbar_r_stacked(0,0)
        self.assertEqual(p.history,[])

    def test_subgroup_snapshot_recipe_roundtrip_in_mpx_copy(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source,target=Path(folder)/'source.mpx',Path(folder)/'copy.mpx'
            write_subgroup_fixture(source)
            p=Presenter(); p.load(source); old=p.xbar_r_stacked(0,1)
            p.save(target)
            q=Presenter(); q.load(target)
            restored=next(e for e in q.history if e['origin']=='statcraft')
            self.assertEqual(restored['result']['means'],[2,5,8])
            self.assertFalse(q.result_stale(restored))
            q.set_cell(0,0,'5'); fresh=q.rerun_result(restored)
            self.assertEqual(fresh['result']['means'],[4,5,8])
            self.assertEqual(restored['result']['means'],old['result']['means'])
