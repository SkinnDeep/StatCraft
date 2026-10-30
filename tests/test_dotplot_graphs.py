import copy,json,tempfile,unittest
from pathlib import Path
from statcraft.app import Presenter,format_entry
from statcraft.dotplot_graphs import build_dotplots,validate_result,VARIANTS
from statcraft.model import Worksheet,Column
from statcraft.recipes import columns
from statcraft.brushing import brushable_rows,validate_brushed_rows
from statcraft import session,io


def document():
    p=Presenter();p.worksheet=Worksheet('Samples',[Column('Strength',values=[1,1,2,2,3,3,None,4]),
        Column('Adjusted',values=[1,2,2,2,3,4,4,4]),Column('Batch','text',['A']*4+['B']*4),
        Column('Shift','text',['Day','Day','Night','Night']*2)])
    return p


class DotplotTests(unittest.TestCase):
    def test_observations_bin_endpoints_and_rows(self):
        r=build_dotplots(document().worksheet,response_indices=[0],intervals=3);s=r['panels'][0]['series'][0]
        self.assertEqual(s['row_indices'],[1,2,3,4,5,6,8]);self.assertEqual([v['x'] for v in s['points']],[1.5,1.5,2.5,2.5,3.5,3.5,3.5])
        self.assertEqual([v['level'] for v in s['points']],[1,2,1,2,1,2,3]);self.assertEqual(r['panels'][0]['heights'],[3]);json.dumps(r,allow_nan=False)

    def test_all_seven_variants_have_real_lanes_or_stack_levels(self):
        p=document();results={}
        for variant in VARIANTS:
            args=dict(response_indices=[0,1] if variant.startswith('multiple') else [0],variant=variant,group_indices=[2,3] if variant.endswith('groups') else [],intervals=1)
            results[variant]=build_dotplots(p.worksheet,**args)['panels'][0]
        self.assertEqual(len(results['one_groups']['lanes']),4);self.assertEqual(len(results['one_stack_groups']['lanes']),2)
        self.assertEqual(len(results['multiple']['lanes']),2);self.assertEqual(len(results['multiple_stack']['lanes']),1)
        self.assertEqual(len(results['multiple_groups']['lanes']),8);self.assertEqual(len(results['multiple_stack_groups']['lanes']),4)
        self.assertEqual(results['multiple_stack']['heights'],[15])

    def test_stack_checkbox_off_separates_groups(self):
        p=document();r=build_dotplots(p.worksheet,response_indices=[0],variant='one_stack_groups',group_indices=[2],stack=False)
        self.assertEqual(len(r['panels'][0]['lanes']),2)

    def test_order_attribute_levels_and_panels(self):
        p=document();p.worksheet.columns[2].metadata['value_order']={'mode':'custom','values':['B','A']}
        args=dict(response_indices=[0,1],variant='multiple_groups',group_indices=[2,3],color_levels=[1])
        outer=build_dotplots(p.worksheet,**args);inner=build_dotplots(p.worksheet,**args,variable_position='inner')
        self.assertTrue(outer['panels'][0]['lanes'][0].startswith('Strength / B'))
        self.assertEqual([s['response_index'] for s in inner['panels'][0]['series']],[0,1]*4)
        self.assertEqual([s['color_index'] for s in outer['panels'][0]['series'][:4]],[0,1,0,1])
        panels=build_dotplots(p.worksheet,**args,layout='panels')['panels'];self.assertEqual(len(panels),2)
        self.assertEqual([s['color_index'] for s in panels[0]['series']],[s['color_index'] for s in panels[1]['series']])

    def test_missing_incomplete_groups_and_constant_values(self):
        p=document();p.worksheet.columns[0].values=[5]*8;p.worksheet.columns[2].values[1]=None
        r=build_dotplots(p.worksheet,response_indices=[0],variant='one_stack_groups',group_indices=[2])
        self.assertEqual(r['panels'][0]['value_range'],[5,5]);self.assertEqual(len(r['panels'][0]['lanes']),1)
        self.assertEqual(sum(len(s['points']) for s in r['panels'][0]['series']),7);self.assertEqual(r['panels'][0]['heights'],[7])

    def test_validation_and_atomic_recording(self):
        p=document()
        for args in (dict(response_indices=[0,1]),dict(response_indices=[2]),dict(response_indices=[0],intervals=True),dict(response_indices=[0],variant='one_groups'),dict(response_indices=[0],color_levels=[0]),dict(response_indices=[0],stack=1),dict(response_indices=[0],variant='multiple_stack',layout='panels')):
            with self.assertRaises(ValueError):p.dotplot_graphs(**args)
        self.assertFalse(p.history)
        p.worksheet.columns[0].values=[1]*10001
        with self.assertRaisesRegex(ValueError,'10000'):p.dotplot_graphs([0])
        self.assertFalse(p.history)

    def test_column_rebinding_undo_and_deletion_guard(self):
        p=document();e=p.dotplot_graphs([0,1],'multiple_stack_groups',[2,3],color_levels=[1]);self.assertEqual(columns(e['recipe']),[0,1,2,3])
        p.insert_columns(0);self.assertEqual(e['recipe']['parameters']['group_indices'],[3,4]);self.assertFalse(p.result_stale(e))
        self.assertEqual(p.rerun_result(e)['recipe']['parameters']['color_levels'],[1]);p.undo();self.assertEqual(e['recipe']['parameters']['response_indices'],[0,1])
        p.delete_columns([2]);self.assertTrue(p.result_stale(e))
        with self.assertRaisesRegex(ValueError,'deleted'):p.rerun_result(e)

    def test_mpx_styles_brushing_and_layout_roundtrip(self):
        p=document();e=p.dotplot_graphs([0,1],'multiple_stack',intervals=3);p.update_graph_styles(e,{'p0:s0':{'fill':'#d000a4','marker':'diamond'}});p.graph_layout([e],1,1)
        self.assertEqual(brushable_rows(e),list(range(1,9)));self.assertEqual(validate_brushed_rows(e,p.worksheet,[8,2]),[2,8])
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'dots.mpx';p.save(path);q=Presenter();q.load(path);saved=q.history[0]
            self.assertEqual(q.rerun_result(saved)['result'],e['result']);self.assertEqual(saved['graph_styles']['p0:s0']['marker'],'diamond');self.assertIn('Category',format_entry(saved))

    def test_invalid_saved_dot_identities_and_compositions_rejected(self):
        p=document();entry=p.dotplot_graphs([0]);entry.update(worksheet_id='sheet')
        for mutate in (lambda r:r['panels'][0]['series'][0]['points'][0].__setitem__('x',float('inf')),lambda r:r['panels'][0]['series'][0]['row_indices'].__setitem__(0,True),lambda r:r['panels'][0].__setitem__('heights',[0]),lambda r:r['panels'][0]['series'][0]['points'][0].__setitem__('level',999)):
            invalid=copy.deepcopy(entry);mutate(invalid['result'])
            with self.assertRaises(io.FormatError):session.validate([invalid],['sheet'])


if __name__=='__main__':unittest.main()
