import copy,json,math,tempfile,unittest
from pathlib import Path
from statcraft.app import Presenter,format_entry
from statcraft.categorical_points import build_points,validate_interval,validate_result
from statcraft.model import Worksheet,Column
from statcraft.brushing import brushable_rows
from statcraft.recipes import columns
from statcraft import session,io


def document():
    p=Presenter();p.worksheet=Worksheet('Measurements',[Column('Strength',values=[1,2,3,5,5,5,None,9]),Column('Adjusted',values=[2,4,6,8,10,12,14,16]),
        Column('Batch','text',['A']*3+['B']*3+['A','B']),Column('Shift','text',['Day','Night','Day','Day','Night','Day','Night','Night'])])
    return p


class CategoricalPointTests(unittest.TestCase):
    def test_individual_points_preserve_values_rows_and_defaults(self):
        p=document();r=build_points(p.worksheet,response_indices=[0]);item=r['panels'][0]['items'][0]
        self.assertEqual(item['source'],[1,2,3,5,5,5,9]);self.assertEqual(item['row_indices'],[1,2,3,4,5,6,8]);self.assertTrue(r['panels'][0]['display']['individual']);self.assertFalse(r['panels'][0]['display']['interval']);json.dumps(r,allow_nan=False)

    def test_student_t_interval_known_df_two(self):
        p=document();p.worksheet.columns[0].values=[1,2,3]
        r=build_points(p.worksheet,response_indices=[0],plot_type='interval');item=r['panels'][0]['items'][0]
        self.assertEqual(item['mean'],2);self.assertEqual(item['df'],2);self.assertAlmostEqual(item['stdev'],1)
        self.assertAlmostEqual(item['upper'],2+4.302652729911275/math.sqrt(3),places=9);self.assertAlmostEqual(item['lower'],2-4.302652729911275/math.sqrt(3),places=9)

    def test_pooled_variance_is_within_response_not_between_responses(self):
        p=document();p.worksheet.columns[0].values=[1,2,3,5,5,5];p.worksheet.columns[1].values=[2,4,6,10,10,10]
        r=build_points(p.worksheet,response_indices=[0,1],plot_type='interval',variant='multiple_groups',group_indices=[2],interval_options={'pooled':True})
        items=r['panels'][0]['items'];self.assertEqual([i['df'] for i in items],[4]*4)
        self.assertAlmostEqual(items[0]['standard_error'],math.sqrt(.5/3));self.assertAlmostEqual(items[2]['standard_error'],2*items[0]['standard_error'])

    def test_standard_error_multiple(self):
        p=document();p.worksheet.columns[0].values=[1,2,3]
        item=build_points(p.worksheet,response_indices=[0],plot_type='interval',interval_options={'method':'standard_error','multiple':2})['panels'][0]['items'][0]
        self.assertAlmostEqual(item['lower'],2-2/math.sqrt(3));self.assertAlmostEqual(item['upper'],2+2/math.sqrt(3))

    def test_one_sided_and_bonferroni_intervals(self):
        p=document();p.worksheet.columns[0].values=[1,2,3,4,5,6]
        args=dict(response_indices=[0],plot_type='interval',variant='one_groups',group_indices=[2])
        plain=build_points(p.worksheet,**args)['panels'][0]['items'][0]
        adjusted=build_points(p.worksheet,**args,interval_options={'bonferroni':True})['panels'][0]['items'][0]
        self.assertGreater(adjusted['upper'],plain['upper']);self.assertLess(adjusted['lower'],plain['lower'])
        upper=build_points(p.worksheet,**args,interval_options={'side':'upper'})['panels'][0]['items'][0]
        lower=build_points(p.worksheet,**args,interval_options={'side':'lower'})['panels'][0]['items'][0]
        self.assertIsNone(upper['lower']);self.assertIsNone(lower['upper']);self.assertLess(upper['upper'],plain['upper'])

    def test_singleton_groups_and_constants(self):
        p=document();p.worksheet.columns[0].values=[1,2,3,5];p.worksheet.columns[2].values=['A','A','A','B']
        with self.assertRaisesRegex(ValueError,'two observations'):build_points(p.worksheet,response_indices=[0],plot_type='interval',variant='one_groups',group_indices=[2])
        pooled=build_points(p.worksheet,response_indices=[0],plot_type='interval',variant='one_groups',group_indices=[2],interval_options={'pooled':True})
        self.assertEqual(pooled['panels'][0]['items'][1]['df'],2)
        p.worksheet.columns[0].values=[5]*4
        r=build_points(p.worksheet,response_indices=[0],plot_type='interval');self.assertEqual(r['panels'][0]['items'][0]['lower'],5)

    def test_group_order_colors_and_response_panels(self):
        p=document();p.worksheet.columns[2].metadata['value_order']={'mode':'custom','values':['B','A']}
        args=dict(response_indices=[0,1],variant='multiple_groups',group_indices=[2,3],color_levels=[1])
        r=build_points(p.worksheet,**args,variable_position='inner');items=r['panels'][0]['items']
        self.assertEqual([i['response_index'] for i in items],[0,1]*4);self.assertEqual(items[0]['group_values'],['B','Day']);self.assertEqual(items[0]['color_index'],items[4]['color_index'])
        self.assertEqual(len(build_points(p.worksheet,**args,layout='panels')['panels']),2)

    def test_limits_validation_and_atomic_failure(self):
        p=document()
        for args in (dict(response_indices=[0,1]),dict(response_indices=[2]),dict(response_indices=[0],jitter=True),dict(response_indices=[0],display={'bogus':True}),dict(response_indices=[0],color_levels=[0]),dict(response_indices=[0],plot_type='bogus')):
            with self.assertRaises(ValueError):p.categorical_points(**args)
        self.assertFalse(p.history)
        for options in ({'confidence':1},{'method':'standard_error','side':'upper'},{'method':'standard_error','bonferroni':True},{'multiple':0},{'pooled':1},{'confidence':.1,'side':'upper'}):
            with self.assertRaises(ValueError):validate_interval(options)

    def test_column_identity_and_brush_only_individual_symbols(self):
        p=document();e=p.categorical_points([0,1],variant='multiple_groups',group_indices=[2]);self.assertEqual(columns(e['recipe']),[0,1,2])
        self.assertEqual(brushable_rows(e),list(range(1,9)));p.insert_columns(0);self.assertEqual(e['recipe']['parameters']['group_indices'],[3]);self.assertFalse(p.result_stale(e));p.rerun_result(e)
        p.undo();p.delete_columns([0]);self.assertTrue(p.result_stale(e))
        with self.assertRaisesRegex(ValueError,'deleted'):p.rerun_result(e)
        self.assertFalse(brushable_rows(document().categorical_points([1],plot_type='interval')))

    def test_mpx_display_intervals_styles_and_layout(self):
        p=document();e=p.categorical_points([1],plot_type='interval',display={'individual':True,'median_symbol':True},interval_options={'side':'lower'});p.update_graph_styles(e,{'p0:int0':{'color':'#d000a4','line_width':3}});p.graph_layout([e],1,1)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'points.mpx';p.save(path);q=Presenter();q.load(path);saved=q.history[0]
            self.assertEqual(q.rerun_result(saved)['result'],e['result']);self.assertEqual(saved['graph_styles']['p0:int0']['color'],'#d000a4');self.assertIn('SE Mean',format_entry(saved))

    def test_malformed_source_interval_and_display_rejected(self):
        p=document();e=p.categorical_points([0],plot_type='interval');e.update(worksheet_id='sheet')
        for mutate in (lambda r:r['panels'][0]['items'][0].__setitem__('lower',float('inf')),lambda r:r['panels'][0]['items'][0].__setitem__('df',True),lambda r:r['panels'][0]['display'].__setitem__('individual',1),lambda r:r['panels'][0]['items'][0]['row_indices'].__setitem__(0,True)):
            invalid=copy.deepcopy(e);mutate(invalid['result'])
            with self.assertRaises(io.FormatError):session.validate([invalid],['sheet'])


if __name__=='__main__':unittest.main()
