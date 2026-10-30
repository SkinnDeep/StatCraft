"""Hand-derived static S/N, response tables, alignment and model availability."""
import copy
import math
import unittest
import numpy as np
from statcraft.model import Column, Worksheet
from statcraft.taguchi_analysis import analyze, row_statistics
from statcraft.taguchi_analysis_report import text_report, sections


def sheet():
    return Worksheet('Static Taguchi',[Column('A','text',['low','low','high','high']),
        Column('B',values=[1,2,1,2]),Column('Y1',values=[1,2,3,4]),Column('Y2',values=[3,4,5,6])])


def analyze_simple(options=None):
    return analyze(sheet(),[2,3],[0,1],dict({'fit_models':False},**(options or {})))


class TaguchiResponseTests(unittest.TestCase):
    def test_larger_smaller_nominal_hand_formulas(self):
        self.assertAlmostEqual(row_statistics([1.,2.],'larger')['sn'],-10*math.log10((1+.25)/2))
        self.assertAlmostEqual(row_statistics([1.,3.],'smaller')['sn'],-10*math.log10(5))
        nominal=row_statistics([1.,3.],'nominal')
        self.assertAlmostEqual(nominal['mean'],2)
        self.assertAlmostEqual(nominal['stdev'],math.sqrt(2))
        self.assertAlmostEqual(nominal['sn'],10*math.log10(2))

    def test_response_tables_average_row_ratios_not_pooled_losses(self):
        result=analyze_simple({'sn_type':'smaller'})
        low=next(entry for entry in result['response_tables']['sn']['factors'][0]['levels'] if entry['level']=='low')
        self.assertAlmostEqual(low['value'],(-10*math.log10(5)-10*math.log10(10))/2)
        self.assertNotAlmostEqual(low['value'],-10*math.log10(7.5))

    def test_means_deltas_ranks_and_actual_level_settings(self):
        result=analyze_simple()
        a,b=result['response_tables']['mean']['factors']
        self.assertEqual([(entry['level'],entry['value']) for entry in a['levels']],[('high',4.5),('low',2.5)])
        self.assertEqual((a['delta'],a['rank'],b['delta'],b['rank']),(2.,1,1.,2))
        self.assertEqual(b['levels'][0]['count'],2)

    def test_equal_deltas_receive_equal_competition_ranks(self):
        ws=sheet();ws.columns[2].values=[1,2,2,3];ws.columns[3].values=[3,4,4,5]
        result=analyze(ws,[2,3],[0,1],{'fit_models':False})
        self.assertEqual([factor['rank'] for factor in result['response_tables']['mean']['factors']],[1,1])

    def test_all_tied_optimum_levels_retained(self):
        ws=sheet();ws.columns[2].values=[1,1,1,1];ws.columns[3].values=[2,2,2,2]
        result=analyze(ws,[2,3],[0,1],{'fit_models':False})
        self.assertEqual(result['optimum_settings'][0]['levels'],['high','low'])
        self.assertEqual(result['optimum_settings'][1]['levels'],[1,2])

    def test_custom_value_order_respected(self):
        ws=sheet();ws.columns[0].metadata['value_order']={'mode':'custom','values':['low','high']}
        result=analyze(ws,[2,3],[0,1],{'fit_models':False})
        self.assertEqual([entry['level'] for entry in result['response_tables']['mean']['factors'][0]['levels']],['low','high'])
        self.assertEqual(result['panels'][0]['x_labels'],['low','high'])

    def test_incomplete_rows_omitted_jointly_without_realignment(self):
        ws=sheet();ws.columns[3].values[1]=None;ws.columns[0].values[2]=None
        result=analyze(ws,[2,3],[0,1],{'fit_models':False})
        self.assertEqual(result['row_indices'],[0,3])
        self.assertEqual(result['omitted_rows'],[1,2])
        self.assertEqual([row['mean'] for row in result['rows']],[2.,5.])
        self.assertEqual(result['panels'][0]['row_indices_by_level'],[[3],[0]])

    def test_trailing_shorter_response_omits_original_row(self):
        ws=sheet();ws.columns[3].values.pop()
        result=analyze(ws,[2,3],[0,1],{'fit_models':False})
        self.assertEqual(result['row_indices'],[0,1,2])
        self.assertEqual(result['omitted_rows'],[3])

    def test_single_response_column_does_not_fabricate_sd_or_nominal_ratio(self):
        ws=sheet()
        nominal=analyze(ws,[2],[0,1],{'sn_type':'nominal','fit_models':False})
        self.assertTrue(all(row['stdev'] is None and row['sn'] is None for row in nominal['rows']))
        self.assertTrue(all(factor['delta'] is None and factor['rank'] is None for factor in nominal['response_tables']['sn']['factors']))
        self.assertFalse(any(item['estimable'] for item in nominal['optimum_settings']))
        larger=analyze(ws,[2],[0,1],{'sn_type':'larger','fit_models':False})
        self.assertAlmostEqual(larger['rows'][1]['sn'],20*math.log10(2))
        self.assertIsNone(larger['rows'][1]['stdev'])

    def test_unbounded_ratios_stay_unavailable_not_infinite(self):
        self.assertIsNone(row_statistics([0.,0.],'smaller')['sn'])
        self.assertIsNone(row_statistics([2.,2.],'nominal')['sn'])
        self.assertEqual(row_statistics([2.,2.],'nominal')['stdev'],0.)
        self.assertAlmostEqual(row_statistics([0.,2.],'smaller')['sn'],-10*math.log10(2))

    def test_unavailable_sn_prevents_misleading_level_optimization(self):
        ws=sheet();ws.columns[2].values[0]=ws.columns[3].values[0]=1.
        result=analyze(ws,[2,3],[0,1],{'sn_type':'nominal','fit_models':False})
        self.assertFalse(result['optimum_settings'][0]['estimable'])
        self.assertIsNone(result['response_tables']['sn']['factors'][0]['delta'])

    def test_sign_and_zero_domain_policies(self):
        for values,goal in [([0.,1.],'larger'),([-1.,1.],'larger'),([-1.,1.],'smaller'),([-1.,1.],'nominal')]:
            with self.subTest(values=values,goal=goal),self.assertRaises(ValueError):
                row_statistics(values,goal)

    def test_log_standard_deviation_output(self):
        result=analyze_simple({'log_stdev':True})
        self.assertAlmostEqual(result['rows'][0]['stdev'],math.log(math.sqrt(2)))
        self.assertAlmostEqual(result['rows'][0]['raw_stdev'],math.sqrt(2))
        self.assertIn('Ln(Standard Deviations)',text_report(result))

    def test_extreme_numeric_values_keep_log_formulas_finite(self):
        for values in ([1e-300,2e-300],[1e300,2e300]):
            for goal in ('larger','smaller','nominal'):
                with self.subTest(goal=goal,values=values):
                    result=row_statistics(values,goal)
                    self.assertTrue(math.isfinite(result['sn']))
                    self.assertTrue(math.isfinite(result['mean']))

    def test_inputs_are_not_modified_and_show_graphs_works(self):
        ws=sheet();options={'show_graphs':False,'fit_models':False};before=copy.deepcopy((ws,options))
        result=analyze(ws,[2,3],[0,1],options)
        self.assertEqual((ws,options),before)
        self.assertFalse(result['show_graphs']);self.assertEqual(result['panels'],[])
        self.assertIn('Response Table for Signal-to-Noise Ratios',text_report(result))
        self.assertTrue(sections(result))

    def test_invalid_selection_and_options_rejected(self):
        ws=sheet()
        for response,factors,options in [([0],[1],{}),([2],[2],{}),([2],[0,0],{}),([2],[99],{}),([2],[0],{'sn_type':'dynamic'}),([2],[0],{'nominal_formula':'adjusted'}),([2],[0],{'fit_models':1})]:
            with self.subTest(response=response,factors=factors),self.assertRaises(ValueError):
                analyze(ws,response,factors,options)

    def test_nonfinite_boolean_and_nonvarying_factor_rejected(self):
        for value in (float('nan'),float('inf'),True):
            ws=sheet();ws.columns[2].values[1]=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'row 2'):
                analyze(ws,[2,3],[0,1])
        ws=sheet();ws.columns[0].values=['same']*4
        with self.assertRaisesRegex(ValueError,'two observed levels'):
            analyze(ws,[2,3],[0,1])


class TaguchiMainEffectsTests(unittest.TestCase):
    def model_sheet(self):
        a=[-1,-1,1,1]*2;b=[-1,1,-1,1]*2
        error=[-.5,.2,.1,.4,.3,-.2,-.1,-.4]
        means=[10+2*x+3*y+e for x,y,e in zip(a,b,error)]
        return Worksheet('Repeated Taguchi',[Column('A',values=a),Column('B',values=b),
            Column('Y1',values=[value-.5 for value in means]),Column('Y2',values=[value+.5 for value in means])])

    def test_main_effects_fit_matches_independent_ols(self):
        ws=self.model_sheet();result=analyze(ws,[2,3],[0,1])
        model=result['models']['mean'];self.assertIsNotNone(model)
        y=np.array([row['mean'] for row in result['rows']])
        x=np.column_stack([np.ones(8),ws.columns[0].values,ws.columns[1].values])
        beta=np.linalg.lstsq(x,y,rcond=None)[0];residual=y-x@beta
        self.assertAlmostEqual(model['ss_error'],float(residual@residual))
        self.assertEqual(model['df_error'],5)
        self.assertEqual(model['source_row_indices'],list(range(8)))
        self.assertTrue(all(row['p_value'] is not None for row in model['anova_terms']))
        self.assertIn('Analysis of Variance',text_report(result))
        self.assertIsNone(result['models']['stdev'])
        self.assertIn('varying response',result['model_unavailable']['stdev'])

    def test_saturated_model_returns_reason_not_fake_inference(self):
        ws=sheet();ws.columns.insert(2,Column('C',values=[1,2,2,1]))
        result=analyze(ws,[3,4],[0,1,2])
        self.assertIsNone(result['models']['mean'])
        self.assertIn('residual degrees of freedom',result['model_unavailable']['mean'])

    def test_aliasing_returns_reason_while_tables_remain_usable(self):
        ws=self.model_sheet();ws.columns[1].values=list(ws.columns[0].values)
        result=analyze(ws,[2,3],[0,1])
        self.assertIsNone(result['models']['mean'])
        self.assertIn('rank deficient',result['model_unavailable']['mean'])
        self.assertTrue(result['response_tables']['mean']['factors'])

    def test_model_source_rows_keep_worksheet_identity_after_omission(self):
        ws=self.model_sheet();ws.columns[3].values[1]=None
        result=analyze(ws,[2,3],[0,1])
        model=result['models']['mean'];self.assertIsNotNone(model)
        self.assertEqual(model['row_indices'],[0,2,3,4,5,6,7])
        self.assertEqual([row['row'] for row in model['diagnostics']],[1,3,4,5,6,7,8])
        self.assertEqual(model['missing'],1)

    def test_no_models_when_not_selected(self):
        result=analyze(self.model_sheet(),[2,3],[0,1],{'fit_models':False})
        self.assertTrue(all(model is None for model in result['models'].values()))
        self.assertTrue(all('not selected' in reason for reason in result['model_unavailable'].values()))


if __name__=='__main__':
    unittest.main()
