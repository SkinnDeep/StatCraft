from pathlib import Path
import copy
import tempfile
import unittest
from statcraft.app import Presenter, histogram_data
from statcraft.model import Column
from statcraft._mpx_fixture import write_fixture


class ResultUpdateTests(unittest.TestCase):
    def scratch(self):
        return tempfile.TemporaryDirectory(dir=Path(__file__).parent)

    def test_changed_inputs_rerun_source_sheet_and_preserve_previous_snapshot(self):
        with self.scratch() as folder:
            source=Path(folder)/'source.mpx'; write_fixture(source)
            p=Presenter(); p.load(source)
            old=p.describe_column(0)
            self.assertFalse(p.result_stale(old))
            p.set_cell(0,0,'9'); p.select_worksheet(0)
            self.assertTrue(p.result_stale(old))
            new=p.rerun_result(old)
            self.assertEqual(p.native_project.active_index,1)
            self.assertEqual(old['result']['mean'],2)
            self.assertAlmostEqual(new['result']['mean'],14/3)
            self.assertFalse(p.result_stale(new))
            self.assertTrue(p.dirty)

    def test_irrelevant_column_edits_do_not_invalidate_and_undo_restores_inputs(self):
        p=Presenter(); p.set_cell(0,0,'1'); p.set_cell(1,0,'3')
        p.worksheet.columns.append(Column('Other', values=[10,20]))
        result=p.describe_column(0)
        p.set_cell(0,1,'100')
        self.assertFalse(p.result_stale(result))
        p.set_cell(0,0,'8')
        self.assertTrue(p.result_stale(result))
        p.undo(); self.assertFalse(p.result_stale(result))
        p.rename_column(0,'Renamed'); self.assertTrue(p.result_stale(result))

    def test_recipe_and_fingerprints_survive_mpx_roundtrip_without_execution(self):
        with self.scratch() as folder:
            source,target=Path(folder)/'source.mpx',Path(folder)/'copy.mpx'
            write_fixture(source); p=Presenter(); p.load(source)
            original=p.inference('one_sample_t',[0],mu=2,confidence=.9)
            p.set_cell(0,0,'6'); p.save(target)
            q=Presenter(); q.load(target)
            old=next(e for e in q.history if e['origin']=='statcraft')
            self.assertEqual(old['recipe'],original['recipe'])
            self.assertTrue(q.result_stale(old)); self.assertFalse(q.dirty)
            fresh=q.rerun_result(old)
            self.assertAlmostEqual(fresh['result']['mean'],11/3)
            self.assertEqual(fresh['result']['confidence'],.9)
            self.assertEqual(old['result']['mean'],2)

    def test_failed_rerun_restores_selection_and_does_not_record_result(self):
        with self.scratch() as folder:
            source=Path(folder)/'source.mpx'; write_fixture(source)
            p=Presenter(); p.load(source); result=p.individuals_moving_range(0)
            for row in range(3): p.set_cell(row,0,'*')
            p.select_worksheet(0)
            before=copy.deepcopy(p.history); previous=p.worksheet
            with self.assertRaises(ValueError): p.rerun_result(result)
            self.assertIs(p.worksheet,previous)
            self.assertEqual(p.native_project.active_index,0)
            self.assertEqual(p.history,before)

    def test_legacy_and_untrusted_actions_are_not_executed(self):
        p=Presenter(); p.set_cell(0,0,'2')
        old=p._record('Legacy',{'command':'arbitrary inert text'})
        self.assertIsNone(p.result_stale(old))
        with self.assertRaises(ValueError): p.rerun_result(old)
        for recipe in (
                {'action':'save','parameters':{'path':'unwanted'}},
                {'action':'describe_column','parameters':{'index':-1}},
                {'action':'describe_column','parameters':{'index':True}},
                {'action':'inference','parameters':{'indices':[0],'method':'__import__','mu':0,'confidence':.95}}):
            altered=copy.deepcopy(old); altered['recipe']=recipe
            with self.assertRaises(ValueError): p.rerun_result(altered)
        self.assertEqual(len(p.history),1)

    def test_graph_rerun_uses_current_data_and_saved_bin_count(self):
        p=Presenter()
        for row,value in enumerate([1,2,3]): p.set_cell(row,0,str(value))
        recipe={'action':'graph','parameters':{'method':'histogram','indices':[0],'bins':3}}
        old=p._record('Histogram',{'graph':'histogram','graph_data':histogram_data([1,2,3],3)},recipe=recipe)
        before=copy.deepcopy(old['result']['graph_data'])
        p.set_cell(0,0,'9'); updated=p.rerun_result(old)
        self.assertEqual(updated['result']['graph_data'][1],[2,0,1])
        self.assertEqual(old['result']['graph_data'],before)
        self.assertTrue(p.result_stale(old)); self.assertFalse(p.result_stale(updated))
