"""Multiple capability broadcasting, grouping, row alignment and estimator fixtures."""
import copy
import json
import unittest
import numpy as np
from statcraft.model import Worksheet,Column
from statcraft.multiple_capability_engine import analyze_multiple_capability,recipe_sources
from statcraft.multiple_capability_report import format_multiple_capability_report,sections
from statcraft.capability_engine import run_normal_capability
from statcraft.capability_nonnormal_engine import run_nonnormal_capability


def fixture():
    return Worksheet('Measurements',[
        Column('Width',values=[9,10,11,10.5,12,13,12.5,11]),
        Column('Length',values=[19,20,None,22,23,21,20,19]),
        Column('Batch','text',['A','A','B','B','C','C','D','D']),
        Column('Shift','text',['B','A','B','A','B','A','B','A']),
        Column('Machine',values=[2,2,2,2,1,1,1,1]),
        Column('Other batch','text',['a','a','a','a','b','b','b','b'])])


class MultipleCapabilityTests(unittest.TestCase):
    def test_independent_columns_and_specs_match_individual_calls(self):
        sheet=fixture()
        result=analyze_multiple_capability(sheet,'normal',[0,1],subgroup_sizes=[2,4],lower_specs=[7,15],upper_specs=[16,28],targets=[11,21])
        self.assertEqual([row['variable_name'] for row in result['summary']],['Width','Length'])
        for at,(index,size,lsl,usl,target) in enumerate([(0,2,7,16,11),(1,4,15,28,21)]):
            data=sheet.columns[index].values
            groups=[[value for value in data[start:start+size] if value is not None] for start in range(0,len(data),size)]
            expected=run_normal_capability(groups,lsl=lsl,usl=usl,target=target)
            actual=result['series'][at]['result']
            self.assertAlmostEqual(actual['cpk'],expected['cpk'])
            self.assertAlmostEqual(actual['ppk'],expected['ppk'])
            self.assertEqual(result['summary'][at]['n'],len([value for value in data if value is not None]))
        self.assertEqual(result['series'][1]['missing_rows'],[3])
        self.assertEqual(result['series'][0]['missing_rows'],[])
        json.dumps(result,allow_nan=False)

    def test_shared_scalar_and_single_item_array_broadcast(self):
        a=analyze_multiple_capability(fixture(),'normal',[0,1],lower_specs=5,upper_specs=30,subgroup_sizes=2)
        b=analyze_multiple_capability(fixture(),'normal',[0,1],lower_specs=[5],upper_specs=[30],subgroup_sizes=[2])
        self.assertEqual(a,b)
        self.assertEqual([row['lsl'] for row in a['summary']],[5,5])

    def test_custom_text_group_order_controls_spec_mapping(self):
        sheet=fixture()
        sheet.columns[3].metadata['value_order']={'mode':'custom','values':['B','A']}
        result=analyze_multiple_capability(sheet,'normal',[0],by_indices=[3],lower_specs=[6,7],upper_specs=[15,16])
        self.assertEqual([item['group_values'] for item in result['series']],[['B'],['A']])
        self.assertEqual([item['rows'] for item in result['series']],[[1,3,5,7],[2,4,6,8]])
        self.assertEqual([row['lsl'] for row in result['summary']],[6,7])
        self.assertIn('Shift=B',format_multiple_capability_report(result))

    def test_default_text_order_and_numeric_combination_order(self):
        result=analyze_multiple_capability(fixture(),'normal',[0],by_indices=[3,4],lower_specs=0,upper_specs=30)
        self.assertEqual([item['group_values'] for item in result['series']], [['A',1],['A',2],['B',1],['B',2]])
        self.assertEqual([item['rows'] for item in result['series']],[[6,8],[2,4],[5,7],[1,3]])

    def test_occurrence_order_and_missing_by_rows(self):
        sheet=fixture()
        sheet.columns[3].metadata['value_order']={'mode':'occurrence','values':[]}
        sheet.columns[3].values[0]=None
        result=analyze_multiple_capability(sheet,'normal',[0],by_indices=[3],lower_specs=0,upper_specs=30)
        self.assertEqual([item['group_values'] for item in result['series']],[['A'],['B']])
        self.assertEqual(result['omitted_by_rows'],[1])
        self.assertEqual(result['series'][1]['rows'],[3,5,7])

    def test_subgroup_id_broadcast_and_per_variable_id_columns(self):
        result=analyze_multiple_capability(fixture(),'normal',[0,1],subgroup_indices=[2,5],lower_specs=0,upper_specs=30)
        self.assertEqual([len(item['result']['subgroups']) for item in result['series']],[4,2])
        shared=analyze_multiple_capability(fixture(),'normal',[0,1],subgroup_indices=[2],lower_specs=0,upper_specs=30)
        self.assertEqual([len(item['result']['subgroups']) for item in shared['series']],[4,4])

    def test_missing_subgroup_ids_omit_paired_response_only(self):
        sheet=fixture()
        sheet.columns[2].values[2]=None
        result=analyze_multiple_capability(sheet,'normal',[0],subgroup_indices=[2],lower_specs=0,upper_specs=30)
        item=result['series'][0]
        self.assertEqual(item['missing_rows'],[3])
        self.assertNotIn(11,item['result']['subgroups'][1])
        self.assertNotIn(3,item['rows'])

    def test_missing_cells_do_not_shift_constant_subgroup_boundaries(self):
        sheet=Worksheet(columns=[Column('Measure',values=[1,None,10,12,21,23])])
        result=analyze_multiple_capability(sheet,'normal',[0],subgroup_sizes=2,lower_specs=0,upper_specs=30)
        self.assertEqual(result['series'][0]['result']['subgroups'],[[1],[10,12],[21,23]])
        self.assertEqual(result['series'][0]['rows'],[1,3,4,5,6])

    def test_nonnormal_columns_match_actual_family_calls(self):
        sheet=fixture()
        result=analyze_multiple_capability(sheet,'nonnormal',[0,1],lower_specs=[5,15],upper_specs=[17,29],distribution='lognormal')
        for item,lower,upper in zip(result['series'],[5,15],[17,29]):
            expected=run_nonnormal_capability(sheet.columns[item['variable_index']].values,dist_or_transform='lognormal',lsl=lower,usl=upper)
            self.assertEqual(item['result']['indices'],expected['indices'])
            self.assertEqual(item['result']['fit_info']['parameters'],expected['fit_info']['parameters'])
            self.assertEqual(item['result']['analysis'],'capability_nonnormal')
        self.assertEqual([row['cp'] for row in result['summary']],[None,None])
        json.dumps(result,allow_nan=False)

    def test_nonnormal_by_groups(self):
        result=analyze_multiple_capability(fixture(),'nonnormal',[0],by_indices=[3],lower_specs=5,upper_specs=17,distribution='weibull')
        self.assertEqual(len(result['series']),2)
        self.assertEqual([row['n'] for row in result['summary']],[4,4])
        self.assertIn('Multiple Variables Capability Analysis (Nonnormal)',format_multiple_capability_report(result))

    def test_one_sided_missing_specs_are_per_series(self):
        result=analyze_multiple_capability(fixture(),'normal',[0,1],lower_specs=[5,None],upper_specs=[None,30])
        self.assertIsNone(result['summary'][0]['pp'])
        self.assertIsNone(result['summary'][1]['pp'])
        self.assertIsNotNone(result['summary'][0]['ppk'])
        self.assertIsNotNone(result['summary'][1]['ppk'])
        self.assertIn('*',format_multiple_capability_report(result))

    def test_percent_summary_normalizes_to_ppm(self):
        a=analyze_multiple_capability(fixture(),'normal',[0],lower_specs=10,upper_specs=12)
        b=analyze_multiple_capability(fixture(),'normal',[0],lower_specs=10,upper_specs=12,options={'display_unit':'percent'})
        self.assertAlmostEqual(a['summary'][0]['expected_ppm'],b['summary'][0]['expected_ppm'])
        self.assertAlmostEqual(a['summary'][0]['observed_ppm'],b['summary'][0]['observed_ppm'])

    def test_sources_are_schema_limited_and_shared_subgroup_allowed(self):
        self.assertEqual(recipe_sources({'variable_indices':[1,0],'by_indices':None,'subgroup_indices':[2,2],'lower_specs':[50,100]}),[0,1,2])
        self.assertEqual(recipe_sources({'variable_indices':[0],'by_indices':[3],'subgroup_indices':[None]}),[0,3])
        for params in ({'variable_indices':[True]}, {'variable_indices':[0,0]}, {'variable_indices':[-1]}, {'variable_indices':[0],'by_indices':[0]},
                       {'variable_indices':[0],'subgroup_indices':[0]}, {'variable_indices':[0],'by_indices':[2],'subgroup_indices':[2]},
                       {'variable_indices':[0,1],'by_indices':[2]}, {'variable_indices':[0],'subgroup_indices':[False]}):
            with self.subTest(params=params),self.assertRaises(ValueError):recipe_sources(params)

    def test_invalid_specs_options_and_subgroup_shapes(self):
        for changes in ({'lower_specs':[1,2,3]}, {'lower_specs':[None,None],'upper_specs':None},
                        {'lower_specs':50,'upper_specs':1}, {'lower_specs':float('nan')},
                        {'subgroup_sizes':[2,3,4]}, {'subgroup_sizes':1.5}, {'subgroup_sizes':True},
                        {'subgroup_indices':[2,5,4]}, {'variable_indices':[3]}, {'variable_indices':[20]},
                        {'options':{'unknown':1}}, {'options':{'columns':True}}, {'options':{'columns':0}},
                        {'options':{'show_graphs':1}}, {'options':{'confidence_level':100}}, {'options':{'tolerance_k':4}},
                        {'options':{'moving_range_len':3}}):
            kwargs={'variable_indices':[0,1],'lower_specs':0,'upper_specs':30};kwargs.update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):analyze_multiple_capability(fixture(),'normal',**kwargs)

    def test_nonnormal_does_not_silently_accept_normal_only_options(self):
        for extra in ({'subgroup_sizes':2},{'subgroup_indices':[2]}, {'distribution':'box_cox'},
                      {'options':{'include_ci':True}},{'options':{'analysis_mode':'between_within'}}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):
                analyze_multiple_capability(fixture(),'nonnormal',[0],lower_specs=1,upper_specs=30,**extra)

    def test_no_mutation_and_graph_preference_persisted(self):
        sheet=fixture();before=copy.deepcopy(sheet)
        options={'show_graphs':False,'title':'Comparison','columns':1}
        saved=copy.deepcopy(options)
        result=analyze_multiple_capability(sheet,'normal',[0,1],lower_specs=0,upper_specs=30,options=options)
        self.assertEqual(sheet,before);self.assertEqual(options,saved)
        self.assertEqual(result['title'],'Comparison')
        self.assertFalse(result['options']['show_graphs'])
        self.assertEqual(len(sections(result)),1)

    def test_stable_nonnormal_tail_z_and_unbounded_json_endpoint(self):
        from scipy import stats
        data=[9,11,12,12]
        r=run_nonnormal_capability(data,lsl=5,usl=17)
        p=r['fit_info']['parameters']
        expected=stats.norm.isf(stats.weibull_min.sf(17,p['shape'],scale=p['scale']))
        self.assertAlmostEqual(r['benchmark_z']['z_usl'],expected)
        self.assertGreater(r['benchmark_z']['z_usl'],8)
        r=run_nonnormal_capability(data,lsl=0,usl=1e6)
        self.assertIsNone(r['benchmark_z']['z_lsl'])
        self.assertIsNone(r['benchmark_z']['z_usl'])
        json.dumps(r,allow_nan=False)

    def test_aiag_summary_keeps_correct_numeric_indices(self):
        r=analyze_multiple_capability(fixture(),'nonnormal',[0],lower_specs=5,upper_specs=17,options={'naming_convention':'aiag_vda'})
        self.assertEqual(r['summary'][0]['pp'],r['series'][0]['result']['indices']['cnp'])
        self.assertEqual(r['summary'][0]['ppk'],r['series'][0]['result']['indices']['cnpk'])

    def test_zero_within_variation_and_insufficient_group_fail_safely(self):
        with self.assertRaisesRegex(ValueError,'within-subgroup'):
            analyze_multiple_capability(Worksheet(columns=[Column('Measure',values=[1,1,2,2])]),'normal',[0],subgroup_sizes=2,lower_specs=0,upper_specs=3)
        sheet=fixture();sheet.columns[0].values=[1]*8
        with self.assertRaisesRegex(ValueError,'variation'):
            analyze_multiple_capability(sheet,'normal',[0],lower_specs=0,upper_specs=2)


if __name__=='__main__':unittest.main()
