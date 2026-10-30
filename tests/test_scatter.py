import json
from pathlib import Path
import tempfile
import unittest
from statcraft.model import Column,Worksheet
from statcraft.app import Presenter,format_entry
from statcraft.scatter import build,MODES,linear_fit
from statcraft._mpx_fixture import write_scatter_fixture


class ScatterTests(unittest.TestCase):
    def sheet(self):
        return Worksheet('Data',[Column('X',values=[1,2,3,4]),Column('Y',values=[3,5,6,10]),Column('Batch',kind='text',values=['A','A','B','B'])])

    def test_all_six_modes_select_series_and_lines(self):
        for mode in MODES:
            grouped=mode.endswith('groups')
            r=build(self.sheet(),0,1,mode,2 if grouped else None)
            self.assertEqual(len(r['series']),2 if grouped else 1)
            self.assertEqual(len(r['fits']),len(r['series']) if 'regression' in mode else 0)
            self.assertEqual(r['series'][0]['connect'],'connect' in mode)
            self.assertEqual(r['count'],4); json.dumps(r,allow_nan=False)

    def test_independent_group_regression_equations(self):
        r=build(self.sheet(),0,1,'regression_groups',2)
        a,b=r['fits']
        self.assertAlmostEqual(a['slope'],2); self.assertAlmostEqual(a['intercept'],1)
        self.assertAlmostEqual(b['slope'],4); self.assertAlmostEqual(b['intercept'],-6)

    def test_two_point_and_horizontal_fits(self):
        r=linear_fit([[1,4],[2,4]])
        self.assertEqual(r['slope'],0); self.assertEqual(r['intercept'],4)
        self.assertEqual(r['y'],[4,4])

    def test_constant_x_or_singleton_fit_rejected(self):
        for data in ([[1,2]],[[1,2],[1,3]]):
            with self.assertRaises(ValueError): linear_fit(data)

    def test_three_connection_orders(self):
        w=Worksheet('Order',[Column('X',values=[3,1,2]),Column('Y',values=[5,15,10])])
        for order,expected in [('Increasing X',[1,2,3]),('Increasing Y',[3,2,1]),('Worksheet',[3,1,2])]:
            self.assertEqual(build(w,0,1,'connect',order=order)['series'][0]['x'],expected)

    def test_sort_preserves_row_identity_and_stable_ties(self):
        w=Worksheet('Ties',[Column('X',values=[2,1,2]),Column('Y',values=[20,10,21])])
        series=build(w,0,1,'connect')['series'][0]
        self.assertEqual(series['row_indices'],[2,1,3]); self.assertEqual(series['y'],[10,20,21])

    def test_missing_group_and_ragged_rows_omitted_together(self):
        w=Worksheet('Missing',[Column('X',values=[1,2,None,4,5]),Column('Y',values=[2,None,6,8]),Column('G',kind='text',values=['A','A','B','','B','C'])])
        r=build(w,0,1,'groups',2)
        self.assertEqual((r['count'],r['missing']),(1,5))
        self.assertEqual(r['series'][0]['row_indices'],[1])
        r=build(w,0,1); self.assertEqual((r['count'],r['missing']),(2,3))

    def test_group_order_and_close_numeric_labels_remain_distinct(self):
        w=self.sheet(); w.columns[2]=Column('Group',values=[1.00000001,1.00000002,1.00000001,1.00000002])
        series=build(w,0,1,'groups',2)['series']
        self.assertNotEqual(series[0]['label'],series[1]['label']); self.assertEqual(series[0]['row_indices'],[1,3])

    def test_connect_does_not_join_different_groups(self):
        r=build(self.sheet(),0,1,'connect_groups',2)
        self.assertEqual([s['x'] for s in r['series']],[[1,2],[3,4]])

    def test_custom_labels_are_plain_strings(self):
        r=build(self.sheet(),0,1,title='Process <x>',x_label='Speed',y_label='Yield')
        self.assertEqual((r['plot_title'],r['xlabel'],r['ylabel']),('Process <x>','Speed','Yield'))
        with self.assertRaises(ValueError): build(self.sheet(),0,1,title='x'*257)

    def test_invalid_configuration_rejected(self):
        w=self.sheet()
        for kwargs in ({'mode':'exec'},{'order':'random'},{'mode':'groups'},{'group_index':2}):
            with self.assertRaises(ValueError): build(w,0,1,**kwargs)
        for x,y in ((-1,0),(0,99),(2,1),(True,1)):
            with self.assertRaises(ValueError): build(w,x,y)

    def test_group_limit_and_all_missing_fail(self):
        w=Worksheet('Many',[Column('X',values=list(range(21))),Column('Y',values=list(range(21))),Column('G',values=list(range(21)))])
        with self.assertRaises(ValueError): build(w,0,1,'groups',2)
        w=self.sheet(); w.columns[0].values=[None]*4
        with self.assertRaises(ValueError): build(w,0,1)


class ScatterIntegrationTests(unittest.TestCase):
    def test_failed_group_fit_does_not_add_history(self):
        p=Presenter(); p.worksheet=ScatterTests().sheet(); p.worksheet.columns[0].values=[1,1,2,3]
        with self.assertRaises(ValueError): p.scatter_plot(0,1,'regression_groups',2)
        self.assertEqual(p.history,[])

    def test_group_column_dependency_and_rerun(self):
        p=Presenter(); p.worksheet=ScatterTests().sheet(); old=p.scatter_plot(0,1,'groups',2)
        p.set_cell(0,2,'B'); self.assertTrue(p.result_stale(old))
        fresh=p.rerun_result(old); self.assertFalse(p.result_stale(fresh))
        self.assertEqual(old['result']['series'][0]['row_indices'],[1,2])

    def test_fits_appear_in_text_report(self):
        p=Presenter(); p.worksheet=ScatterTests().sheet(); entry=p.scatter_plot(0,1,'regression_groups',2)
        self.assertIn('Y =',format_entry(entry)); self.assertIn('N = 2',format_entry(entry))

    def test_all_variants_save_restore_and_rerun_on_originating_sheet(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            source,target=Path(folder)/'in.mpx',Path(folder)/'copy.mpx'; write_scatter_fixture(source)
            original=source.read_bytes(); p=Presenter(); p.load(source)
            for mode in MODES: p.scatter_plot(2,0,mode,1 if mode.endswith('groups') else None,title='Saved '+mode)
            p.save(target); self.assertEqual(source.read_bytes(),original)
            q=Presenter(); q.load(target); entries=[e for e in q.history if e.get('origin')=='statcraft']
            self.assertEqual(len(entries),6)
            q.select_worksheet(0)
            for entry in entries:
                self.assertEqual(q.rerun_result(entry)['result'],entry['result'])
                self.assertEqual(q.native_project.active_index,1)
