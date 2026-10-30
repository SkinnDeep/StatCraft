import copy
import tempfile
import unittest
from pathlib import Path
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.value_order import ordered_values,validate_order
from statcraft.expanded_graphs import compute
from statcraft.scatter import build


def document():
    p=Presenter();p.worksheet=Worksheet('Order',[Column('X',values=[1,2,3,4,5,6]),Column('Y',values=[1,2,3,4,5,6]),Column('Grade','text',['B','A','C','B','A','C'])]);return p


class ValueOrderTests(unittest.TestCase):
    def test_alphabetical_occurrence_and_custom(self):
        p=document();col=p.worksheet.columns[2]
        self.assertEqual(ordered_values(col,['B','A','C']),['A','B','C'])
        p.set_column_value_order(2,'occurrence');self.assertEqual(ordered_values(col,['A','C','B']),['B','A','C'])
        p.set_column_value_order(2,'custom',['C','C','A','unused'])
        self.assertEqual(ordered_values(col,['B','A','C']),['C','A','B'])
        self.assertEqual(col.metadata['value_order']['values'],['C','A','unused'])

    def test_occurrence_uses_full_column_before_omission(self):
        col=Column('Group','text',['B','A','B'],{'value_order':{'mode':'occurrence','values':[]}})
        self.assertEqual(ordered_values(col,['A','B']),['B','A'])

    def test_numeric_values_sort_numerically(self):
        col=Column('Group',values=[10,2,-1]);self.assertEqual(ordered_values(col,['10','2','-1']),['-1','2','10'])

    def test_bar_and_pie_keep_count_alignment(self):
        p=document();p.set_column_value_order(2,'custom',['C','B','A']);p.worksheet.columns[2].values.append('C')
        for method in ('bar_chart','pie_chart'):
            panel=compute(method,p.worksheet,[2])['panels'][0]
            self.assertEqual(panel['categories'],['C','B','A']);self.assertEqual(panel['values'],[3,2,2])

    def test_grouped_graph_series_and_point_identity(self):
        p=document();p.set_column_value_order(2,'custom',['C','B','A'])
        panel=compute('line_plot',p.worksheet,[0,1],group_index=2)['panels'][0]
        self.assertEqual([s['name'] for s in panel['series']],['C','B','A'])
        self.assertEqual(panel['series'][0]['points'],[[3,3],[6,6]])
        result=build(p.worksheet,0,1,'groups',2)
        self.assertEqual([s['label'] for s in result['series']],['C','B','A'])
        self.assertEqual(result['series'][0]['row_indices'],[3,6])

    def test_tables_reorder_without_changing_anova(self):
        p=document();original=p.stacked_anova(1,2)['result'];p.set_column_value_order(2,'custom',['C','B','A'])
        result=p.stacked_anova(1,2)['result']
        self.assertEqual(result['variables'],['C','B','A']);self.assertAlmostEqual(original['f'],result['f'])
        self.assertEqual(result['used_rows'],original['used_rows'])

    def test_order_edit_marks_snapshot_stale_and_undo_restores(self):
        p=document();entry=p.expanded_graph('bar_chart',[2]);self.assertFalse(p.result_stale(entry))
        p.set_column_value_order(2,'occurrence');self.assertTrue(p.result_stale(entry))
        p.undo();self.assertFalse(p.result_stale(entry));p.redo();self.assertTrue(p.result_stale(entry))
        self.assertEqual(p.rerun_result(entry)['result']['panels'][0]['categories'],['B','A','C'])

    def test_mpx_roundtrip_preserves_order_and_rerun(self):
        p=document();p.set_column_value_order(2,'custom',['C','B','A']);entry=p.expanded_graph('bar_chart',[2])
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/'order.mpx';p.save(file);q=Presenter();q.load(file)
            saved=next(e for e in q.history if e.get('recipe',{}).get('action')=='expanded_graph')
            self.assertFalse(q.result_stale(saved));self.assertEqual(q.rerun_result(saved)['result']['panels'][0]['categories'],['C','B','A'])

    def test_invalid_settings_reject_atomically(self):
        p=document();before=copy.deepcopy(p.worksheet)
        for args in ((2,'custom',[]),(0,'alphabetical',[]),(2,'bad',[])):
            with self.assertRaises(ValueError):p.set_column_value_order(*args)
            self.assertEqual(p.worksheet,before)
        self.assertEqual(validate_order('custom',[' A ','A','A'])['values'],[' A ','A'])


if __name__=='__main__':unittest.main()
