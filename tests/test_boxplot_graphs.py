import copy,json,tempfile,unittest
from pathlib import Path
from statcraft.app import Presenter,boxplot_data,format_entry
from statcraft.boxplot_graphs import build_boxplots,validate_parameters,validate_result
from statcraft.model import Worksheet,Column
from statcraft.recipes import columns
from statcraft import session,io


def document():
    p=Presenter();p.worksheet=Worksheet('Measurements',[
        Column('Strength',values=[1,2,3,4,8,10,None,100]),Column('Adjusted',values=[2,4,6,8,12,16,20,200]),
        Column('Batch','text',['A','A','A','A','B','B','B','B']),Column('Shift','text',['Day','Day','Night','Night','Day','Day','Night','Night'])])
    return p


class BoxplotGraphTests(unittest.TestCase):
    def test_one_box_uses_existing_quartile_and_whisker_contract(self):
        p=document();r=build_boxplots(p.worksheet,response_indices=[0]);item=r['panels'][0]['items'][0]
        self.assertEqual(item['box'],boxplot_data(p.worksheet.columns[0].values));self.assertEqual(item['row_indices'],[1,2,3,4,5,6,8])
        self.assertEqual(item['n'],7);self.assertIs(validate_result(r),r);json.dumps(r,allow_nan=False)

    def test_observed_groups_missing_rows_and_custom_order(self):
        p=document();p.worksheet.columns[2].metadata['value_order']={'mode':'custom','values':['B','A']}
        r=build_boxplots(p.worksheet,response_indices=[0],variant='one_groups',group_indices=[2,3])
        items=r['panels'][0]['items'];self.assertEqual([i['group_values'] for i in items],[['B','Day'],['B','Night'],['A','Day'],['A','Night']])
        self.assertEqual(items[1]['source'],[100]);self.assertEqual(items[1]['row_indices'],[8]);self.assertEqual(items[0]['box']['median'],9)

    def test_multiple_response_outer_inner_order_and_panels(self):
        p=document();args=dict(response_indices=[0,1],variant='multiple_groups',group_indices=[2])
        outer=build_boxplots(p.worksheet,**args);inner=build_boxplots(p.worksheet,**args,variable_position='inner')
        self.assertEqual([i['response_index'] for i in outer['panels'][0]['items']],[0,0,1,1])
        self.assertEqual([i['response_index'] for i in inner['panels'][0]['items']],[0,1,0,1])
        panels=build_boxplots(p.worksheet,**args,layout='panels')['panels'];self.assertEqual(len(panels),2)
        self.assertEqual([i['color_index'] for i in panels[0]['items']],[i['color_index'] for i in panels[1]['items']])

    def test_limits_types_and_atomic_failure(self):
        p=document();before=copy.deepcopy(p.worksheet)
        for args in (dict(response_indices=[0,1]),dict(response_indices=[2]),dict(response_indices=[0],variant='one_groups'),dict(response_indices=[0],group_indices=[2]),dict(response_indices=[0],variant='one_groups',group_indices=[0])):
            with self.assertRaises(ValueError):build_boxplots(p.worksheet,**args)
        p.worksheet.columns[0].values=list(range(40));p.worksheet.columns[2].values=[str(i) for i in range(40)]
        with self.assertRaisesRegex(ValueError,'32'):p.boxplot_graphs([0],variant='one_groups',group_indices=[2])
        self.assertFalse(p.history)

    def test_data_display_boolean_contract_and_constant_groups(self):
        p=document();p.worksheet.columns[0].values=[3]*8
        r=build_boxplots(p.worksheet,response_indices=[0],variant='one_groups',group_indices=[2],display={'individual':True,'mean_connect':True})
        self.assertTrue(r['panels'][0]['display']['individual']);self.assertEqual(r['panels'][0]['items'][0]['box']['low'],3)
        with self.assertRaises(ValueError):build_boxplots(p.worksheet,response_indices=[0],display={'individual':1})

    def test_recipe_dependencies_column_identity_and_deleted_guard(self):
        p=document();entry=p.boxplot_graphs([0,1],'multiple_groups',[2,3]);self.assertEqual(columns(entry['recipe']),[0,1,2,3])
        p.insert_columns(0);self.assertEqual(entry['recipe']['parameters']['group_indices'],[3,4]);self.assertFalse(p.result_stale(entry))
        p.move_columns([2],'before_c1');self.assertFalse(p.result_stale(entry));self.assertEqual(len(p.rerun_result(entry)['result']['panels'][0]['items']),8)
        p.undo();p.undo();self.assertEqual(entry['recipe']['parameters']['response_indices'],[0,1])
        p.delete_columns([0]);self.assertTrue(p.result_stale(entry))
        with self.assertRaisesRegex(ValueError,'deleted'):p.rerun_result(entry)

    def test_mpx_snapshot_display_styles_rerun_and_layout(self):
        p=document();entry=p.boxplot_graphs([0,1],'multiple_groups',[2],display={'mean_symbol':True});p.update_graph_styles(entry,{'p0:s0':{'fill':'#d000a4'}})
        p.graph_layout([entry],1,1)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'boxplots.mpx';p.save(path);q=Presenter();q.load(path);saved=q.history[0]
            self.assertTrue(q.rerun_result(saved)['result']['panels'][0]['display']['mean_symbol']);self.assertEqual(saved['graph_styles']['p0:s0']['fill'],'#d000a4')
            self.assertIn('Median',format_entry(saved))

    def test_malformed_saved_boxplots_reject(self):
        p=document();entry=p.boxplot_graphs([0]);entry.update(worksheet_id='sheet')
        for mutate in (lambda r:r['panels'][0]['items'][0]['box'].__setitem__('median',float('inf')),lambda r:r['panels'][0]['items'][0]['row_indices'].__setitem__(0,True),lambda r:r['panels'][0]['display'].__setitem__('mean_symbol',1)):
            invalid=copy.deepcopy(entry);mutate(invalid['result'])
            with self.assertRaises(io.FormatError):session.validate([invalid],['sheet'])


if __name__=='__main__':unittest.main()
