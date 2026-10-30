import copy,json,tempfile,unittest
from pathlib import Path
from statcraft.app import Presenter
from statcraft.graph_builder import compute_builder,validate_mapping,TYPES
from statcraft.model import Worksheet,Column
from statcraft.recipes import columns
from statcraft.brushing import brushable_rows
from statcraft import session,io


def document():
    p=Presenter();p.worksheet=Worksheet('Builder samples',[Column('Time',values=list(range(1,13))),Column('Strength',values=[1,2,3,3,4,5,5,6,7,7,8,9]),
        Column('Adjusted',values=[2,4,6,4,6,8,6,8,10,8,10,12]),Column('Batch','text',['A']*6+['B']*6),Column('Shift','text',['Day']*3+['Night']*3+['Day']*3+['Night']*3),Column('When','date',list(range(45000,45012)))])
    return p


class BuilderTests(unittest.TestCase):
    def test_custom_title_is_used_by_initial_graph_annotation(self):
        from statcraft.graph_presentation import graph_presentation
        p=document();entry=p.graph_builder('scatter',[1],0,options={'title':'Strength over time'})
        self.assertEqual(graph_presentation(entry)['title'],'Strength over time')

    def test_nine_families_compile_to_existing_calculations(self):
        p=document()
        for kind in TYPES:
            responses=[3] if kind=='bar_chart' else [1,2] if kind=='matrix_plot' else [1]
            groups=[] if kind in ('matrix_plot','bar_chart') else [3]
            args=dict(graph_type=kind,response_indices=responses,group_indices=groups,x_index=0 if kind=='scatter' else 5 if kind=='time_series' else None)
            params,title,result=compute_builder(p.worksheet,**args)
            self.assertEqual(result['builder_graph_type'],kind);self.assertTrue(title);json.dumps(result,allow_nan=False)
            self.assertFalse(p.history)

    def test_preview_does_not_mutate_worksheet_history_or_dirty_state(self):
        p=document();before=copy.deepcopy(p.worksheet);history=list(p.history);dirty=p.dirty
        compute_builder(p.worksheet,graph_type='interval_plot',response_indices=[1,2],group_indices=[3,4],options={'pooled':True,'bonferroni':True})
        self.assertEqual(p.worksheet,before);self.assertEqual(p.history,history);self.assertEqual(p.dirty,dirty)

    def test_scatter_mapping_fit_and_brushing(self):
        p=document();e=p.graph_builder('scatter',[1],0,[3],{'fit':True,'title':'Strength versus time'})
        self.assertEqual(e['title'],'Strength versus time');self.assertEqual(e['result']['scatter_mode'],'regression_groups');self.assertEqual(brushable_rows(e),list(range(1,13)))
        self.assertEqual(columns(e['recipe']),[0,1,3])

    def test_histogram_normal_fit_panels_and_explicit_intervals(self):
        e=document().graph_builder('histogram',[1],group_indices=[3],options={'fit':True,'bins':6,'layout':'panels'})
        self.assertEqual(len(e['result']['panels']),2);self.assertEqual(len(e['result']['panels'][0]['edges']),7)

    def test_stack_and_interval_options_reach_engines(self):
        p=document();dots=p.graph_builder('dotplot',[1,2],group_indices=[3,4],options={'stack':True,'variable_position':'inner'})
        self.assertEqual(dots['result']['parameters']['variant'],'multiple_stack_groups')
        e=p.graph_builder('interval_plot',[1,2],group_indices=[3],options={'confidence':.9,'pooled':True,'bonferroni':True,'layout':'panels'})
        self.assertEqual(e['result']['parameters']['interval_options']['confidence'],.9);self.assertTrue(e['result']['parameters']['interval_options']['pooled']);self.assertEqual(len(e['result']['panels']),2)

    def test_wrong_role_kinds_counts_overlap_and_atomic_failure(self):
        p=document()
        for args in (dict(graph_type='scatter',response_indices=[1]),dict(graph_type='scatter',response_indices=[1],x_index=1),dict(graph_type='histogram',response_indices=[3]),dict(graph_type='histogram',response_indices=[1],group_indices=[3,4]),dict(graph_type='boxplot',response_indices=[1],x_index=0),dict(graph_type='matrix_plot',response_indices=[1]),dict(graph_type='scatter',response_indices=[1],x_index=5)):
            with self.assertRaises(ValueError):p.graph_builder(**args)
        self.assertFalse(p.history)

    def test_invalid_options_and_unused_switch_normalization(self):
        for options in ({'bins':True},{'fit':1},{'confidence':1},{'title':'x'*146},{'bogus':True}):
            with self.assertRaises(ValueError):validate_mapping('histogram',[1],options=options)
        p=validate_mapping('bar_chart',[3],options={'fit':True,'stack':True,'pooled':True,'bonferroni':True,'layout':'panels'})
        self.assertFalse(p['options']['fit']);self.assertFalse(p['options']['pooled']);self.assertEqual(p['options']['layout'],'combined')

    def test_column_identity_null_x_and_deleted_source_guard(self):
        p=document();e=p.graph_builder('histogram',[1],group_indices=[3]);self.assertEqual(columns(e['recipe']),[1,3]);p.insert_columns(0)
        self.assertIsNone(e['recipe']['parameters']['x_index']);self.assertEqual(e['recipe']['parameters']['response_indices'],[2]);self.assertFalse(p.result_stale(e));p.rerun_result(e)
        p.undo();p.delete_columns([1]);self.assertTrue(p.result_stale(e))
        with self.assertRaisesRegex(ValueError,'deleted'):p.rerun_result(e)

    def test_x_role_moves_and_mpx_styles_layout_roundtrip(self):
        p=document();e=p.graph_builder('scatter',[1],0,[3]);p.update_graph_styles(e,{'p0:s0':{'fill':'#d000a4'}});p.move_columns([0],'after_last')
        self.assertEqual(e['recipe']['parameters']['x_index'],5);self.assertFalse(p.result_stale(e));p.graph_layout([e],1,1)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'builder.mpx';p.save(path);q=Presenter();q.load(path);saved=q.history[0];r=q.rerun_result(saved)
            self.assertEqual(r['result'],e['result']);self.assertEqual(saved['graph_styles']['p0:s0']['fill'],'#d000a4')

    def test_malformed_saved_builder_options_reject(self):
        e=document().graph_builder('boxplot',[1]);e.update(worksheet_id='sheet');e['recipe']['parameters']['options']['bins']=True
        with self.assertRaises(ValueError):columns(e['recipe'])


if __name__=='__main__':unittest.main()
