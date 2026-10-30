"""Column structure edits retain tracked inputs across reruns and undo."""
import copy
from pathlib import Path
import unittest
from test_mpx import scratch
from statcraft.app import Presenter
from statcraft.model import Column
from statcraft.recipe_columns import remap_recipe


def presenter():
    p=Presenter();p.worksheet.columns=[Column('A',values=[1,2,3]),Column('B',values=[10,20,30]),Column('C',values=[100,200,300])]
    return p


class RecipeColumnTests(unittest.TestCase):
    def test_insert_move_remaps_recipe_and_hashes_without_new_data(self):
        p=presenter();entry=p.describe_column(1);original=copy.deepcopy(entry['result'])
        p.insert_columns(0,2)
        self.assertEqual(entry['recipe']['parameters']['index'],3)
        self.assertFalse(p.result_stale(entry));self.assertEqual(p.rerun_result(entry)['result'],original)
        p.move_columns([3],'before_c1')
        self.assertEqual(entry['recipe']['parameters']['index'],0)
        self.assertFalse(p.result_stale(entry));self.assertEqual(p.rerun_result(entry)['result'],original)
        p.undo();self.assertEqual(entry['recipe']['parameters']['index'],3)
        p.undo();self.assertEqual(entry['recipe']['parameters']['index'],1)
        p.redo();p.redo();self.assertEqual(entry['recipe']['parameters']['index'],0)

    def test_delete_blocks_index_reuse_until_undo(self):
        p=presenter();entry=p.describe_column(1);original=copy.deepcopy(entry['result'])
        p.delete_columns([1]);self.assertTrue(p.result_stale(entry));self.assertIn('source_unavailable',entry)
        with self.assertRaisesRegex(ValueError,'deleted'):p.rerun_result(entry)
        p.insert_columns(1)
        with self.assertRaisesRegex(ValueError,'deleted'):p.rerun_result(entry)
        p.undo();p.undo();self.assertNotIn('source_unavailable',entry)
        self.assertEqual(p.rerun_result(entry)['result'],original)
        p.redo()
        with self.assertRaises(ValueError):p.rerun_result(entry)

    def test_result_created_after_insert_is_also_remapped_on_undo(self):
        p=presenter();p.insert_columns(0);entry=p.describe_column(2)
        p.undo();self.assertEqual(entry['recipe']['parameters']['index'],1)
        self.assertFalse(p.result_stale(entry));self.assertEqual(p.rerun_result(entry)['result']['mean'],20)
        p.redo();self.assertEqual(entry['recipe']['parameters']['index'],2)
        self.assertFalse(p.result_stale(entry))

    def test_result_on_inserted_column_unavailable_during_undo(self):
        p=presenter();p.insert_columns(0)
        # Give the inserted column data without adding another edit command.
        p.worksheet.columns[0].values=[7,8]
        entry=p.describe_column(0);p.undo()
        with self.assertRaises(ValueError):p.rerun_result(entry)
        p.redo();self.assertNotIn('source_unavailable',entry)
        self.assertEqual(entry['recipe']['parameters']['index'],0)

    def test_result_created_after_undo_is_remapped_on_redo(self):
        p=presenter();p.insert_columns(0);p.undo();entry=p.describe_column(1)
        p.redo();self.assertEqual(entry['recipe']['parameters']['index'],2)
        self.assertFalse(p.result_stale(entry));self.assertEqual(p.rerun_result(entry)['result']['mean'],20)
        p.undo();self.assertEqual(entry['recipe']['parameters']['index'],1)

    def test_other_worksheet_recipe_is_not_touched(self):
        p=presenter();entry=p.describe_column(1);p.add_worksheet('Other')
        before=copy.deepcopy(entry);p.insert_columns(0);self.assertEqual(entry,before)

    def test_panel_nested_recipe_and_factor_term_ordinals(self):
        p=presenter();p.worksheet.columns.append(Column('Group','text',['x','y','x']))
        source=p.scatter_plot(0,1)
        entry=p.panel_graph(source['recipe'],[3]);p.insert_columns(1)
        params=entry['recipe']['parameters'];self.assertEqual(params['by_indices'],[4])
        self.assertEqual(params['source_recipe']['parameters']['y_index'],2)
        self.assertFalse(p.result_stale(entry));p.rerun_result(entry)
        recipe={'action':'analyze_factorial_terms','parameters':{'response_index':0,'factor_indices':[1,2],
            'max_order':2,'confidence':.95,'plot_residuals':False,'show_factor_coding':False,'selected_terms':[[0],[1],[0,1]]}}
        remapped=remap_recipe(recipe,{0:2,1:0,2:1})
        self.assertEqual(remapped['parameters']['selected_terms'],[[0],[1],[0,1]])
        self.assertEqual(remapped['parameters']['factor_indices'],[0,1])

    def test_mpx_roundtrip_preserves_remap_and_deleted_guard(self):
        with scratch() as folder:
            p=presenter();entry=p.describe_column(1);p.insert_columns(0);p.move_columns([2],'before_c1')
            target=Path(folder)/'saved.mpx';p.save(target)
            q=Presenter();q.load(target);saved=next(e for e in q.history if e.get('recipe',{}).get('action')=='describe_column')
            self.assertEqual(saved['recipe']['parameters']['index'],0);self.assertFalse(q.result_stale(saved))
            self.assertEqual(q.rerun_result(saved)['result']['mean'],20)
            q.delete_columns([0]);q.save(target)
            r=Presenter();r.load(target);deleted=r.history[0]
            with self.assertRaises(ValueError):r.rerun_result(deleted)
