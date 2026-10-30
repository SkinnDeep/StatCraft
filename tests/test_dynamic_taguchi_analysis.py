"""Independent dynamic line algebra, S/N formulas, alignment and degeneracy."""
import copy
import json
import math
import unittest
import numpy as np
from statcraft.model import Column, Worksheet
from statcraft.dynamic_taguchi_analysis import analyze, row_statistics, settings
from statcraft.dynamic_taguchi_report import text_report, sections


def sheet():
    return Worksheet('Dynamic experiment', [Column('Tool', 'text', ['A','A','B','B','A','A','B','B']),
        Column('Speed', values=[1,2,1,2,1,2,1,2]),
        Column('Low noise 1', values=[1,2,3,4,1.2,2.1,3.2,4.1]),
        Column('Low noise 2', values=[2,2.5,3.8,5,2.1,2.9,4,5.2]),
        Column('High noise 1', values=[5,7,8,10,5.1,7.3,8.2,10.1]),
        Column('High noise 2', values=[6,8,10,11,6.2,8.1,10.3,11.3])])


def run(options=None):
    return analyze(sheet(), [2,3,4,5], [1,1,3,3], [0,1], options)


class DynamicTaguchiTests(unittest.TestCase):
    def test_free_line_matches_independent_numpy_ols(self):
        x=np.asarray([1.,1.,3.,3.]); y=np.asarray([1.,2.,5.,6.])
        expected=np.linalg.lstsq(np.column_stack([np.ones(4),x]),y,rcond=None)[0]
        errors=y-(expected[0]+expected[1]*x)
        mse=float(errors@errors/2)
        result=row_statistics(x.tolist(),y.tolist())
        self.assertAlmostEqual(result['intercept'],expected[0])
        self.assertAlmostEqual(result['slope'],expected[1])
        self.assertAlmostEqual(result['mse'],mse)
        self.assertAlmostEqual(result['residual_sd'],math.sqrt(mse))
        self.assertAlmostEqual(result['sn'],10*math.log10(expected[1]**2/mse))
        self.assertEqual(result['df_error'],2)
        np.testing.assert_allclose(result['fitted'],expected[0]+expected[1]*x)
        np.testing.assert_allclose(result['residuals'],errors)
        self.assertAlmostEqual(result['r'],4)

    def test_fixed_nonzero_point_independent_formula(self):
        x=[1.,1.,3.,3.];y=[1.,2.,5.,6.];xr=.5;yr=2.
        d=[value-xr for value in x]
        slope=sum(a*(b-yr) for a,b in zip(d,y))/sum(a*a for a in d)
        fitted=[yr+slope*a for a in d]
        mse=sum((a-b)**2 for a,b in zip(y,fitted))/3
        result=row_statistics(x,y,{'reference_method':'fixed','reference_signal':xr,'reference_response':yr})
        self.assertAlmostEqual(result['slope'],slope)
        self.assertAlmostEqual(result['intercept']+result['slope']*xr,yr)
        self.assertEqual(result['df_error'],3)
        self.assertAlmostEqual(result['mse'],mse)
        self.assertAlmostEqual(result['r'],sum(a*a for a in d))

    def test_adjusted_formula_uses_reference_signal_or_mean_signal(self):
        x=[0.,1.,2.,3.];y=[1.,3.,4.,8.]
        for options in ({},{'reference_method':'fixed','reference_signal':.5,'reference_response':1.}):
            normal=row_statistics(x,y,options)
            adjusted=row_statistics(x,y,dict(options,adjusted=True))
            expected=10*math.log10(normal['slope']**2/normal['mse']-1/normal['r'])
            self.assertAlmostEqual(adjusted['sn'],expected)
            self.assertLess(adjusted['sn'],normal['sn'])

    def test_adjusted_nonpositive_argument_is_unavailable(self):
        result=row_statistics([0.,1.,2.,3.],[0.,2.,-2.,0.],{'adjusted':True})
        self.assertIsNone(result['sn'])
        self.assertIn('nonpositive',result['sn_note'])

    def test_zero_slope_and_exact_lines_do_not_fabricate_finite_sn(self):
        exact=row_statistics([0.,1.,2.,3.],[1.,3.,5.,7.])
        self.assertIsNone(exact['sn']);self.assertEqual(exact['mse'],0.)
        self.assertEqual(exact['residual_sd'],0.)
        zero=row_statistics([-2.,-1.,1.,2.],[1.,-1.,-1.,1.])
        self.assertEqual(zero['slope'],0.)
        self.assertIsNone(zero['sn']);self.assertIn('Zero slope',zero['sn_note'])

    def test_negative_slope_is_allowed_and_sn_uses_square(self):
        positive=row_statistics([1.,1.,3.,3.],[1.,2.,5.,6.])
        negative=row_statistics([1.,1.,3.,3.],[-1.,-2.,-5.,-6.])
        self.assertAlmostEqual(negative['slope'],-positive['slope'])
        self.assertAlmostEqual(negative['sn'],positive['sn'])

    def test_exact_data_and_reference_are_not_mutated(self):
        ws=sheet();options={'fit_models':False};before=copy.deepcopy((ws,options))
        signals=[1,1,3,3];result=analyze(ws,[2,3,4,5],signals,[0,1],options)
        self.assertEqual((ws,options),before)
        result['signal_values'][0]=9
        self.assertEqual(signals,[1,1,3,3])
        self.assertEqual(ws.columns[2].values,before[0].columns[2].values)

    def test_response_tables_average_per_run_statistics_not_pooled_measurements(self):
        result=run({'fit_models':False})
        table=result['response_tables']['sn']['factors'][0]
        a=next(level for level in table['levels'] if level['level']=='A')
        values=[row['sn'] for row in result['rows'] if row['factor_values'][0]=='A']
        self.assertAlmostEqual(a['value'],sum(values)/len(values))
        self.assertEqual(a['row_indices'],[0,1,4,5])
        self.assertEqual(table['rank'],1 if table['delta']>=result['response_tables']['sn']['factors'][1]['delta'] else 2)

    def test_custom_value_order_and_named_report(self):
        ws=sheet();ws.columns[0].metadata['value_order']={'mode':'custom','values':['B','A']}
        result=analyze(ws,[2,3,4,5],[1,1,3,3],[0,1],{'fit_models':False})
        self.assertEqual(result['panels'][0]['x_labels'],['B','A'])
        report=text_report(result)
        for expected in ('Dynamic Taguchi','Dynamic Run Fits','Signal values','Low noise 1','Response Table for Slopes','Worksheet row'):
            self.assertIn(expected,report)
        self.assertTrue(sections(result))

    def test_incomplete_run_omitted_jointly_retains_original_identity(self):
        ws=sheet();ws.columns[3].values[1]=None;ws.columns[0].values[5]=None;ws.columns[5].values.pop()
        result=analyze(ws,[2,3,4,5],[1,1,3,3],[0,1])
        self.assertEqual(result['row_indices'],[0,2,3,4,6])
        self.assertEqual(result['omitted_rows'],[1,5,7])
        self.assertEqual(result['rows'][1]['responses'],[3.,3.8,8.,10.])
        for model in result['models'].values():
            if model is not None:self.assertEqual(model['row_indices'],result['row_indices'])

    def test_zero_variation_affects_level_summaries_and_models(self):
        ws=sheet()
        for index,value in zip([2,3,4,5],[1.,1.,5.,5.]):ws.columns[index].values[0]=value
        result=analyze(ws,[2,3,4,5],[1,1,3,3],[0,1])
        a=next(level for level in result['response_tables']['sn']['factors'][0]['levels'] if level['level']=='A')
        self.assertIsNone(a['value'])
        self.assertFalse(result['optimum_settings'][0]['estimable'])
        self.assertIsNone(result['models']['sn'])
        self.assertIn('partial-run',result['model_unavailable']['sn'])

    def test_log_sd_does_not_change_residual_sd_or_sn(self):
        plain=run({'fit_models':False});logged=run({'fit_models':False,'log_stdev':True})
        for a,b in zip(plain['rows'],logged['rows']):
            self.assertEqual(a['sn'],b['sn']);self.assertEqual(a['residual_sd'],b['residual_sd'])
            self.assertAlmostEqual(b['stdev'],math.log(a['stdev']))
        self.assertIn('Ln(Standard Deviations)',text_report(logged))

    def test_main_effects_model_matches_independent_least_squares(self):
        result=run()
        slopes=np.asarray([row['slope'] for row in result['rows']])
        design=np.asarray([[1,1 if row['factor_values'][0]=='A' else -1,1 if row['factor_values'][1]==1 else -1] for row in result['rows']])
        fitted=design@np.linalg.lstsq(design,slopes,rcond=None)[0]
        model=result['models']['slope']
        self.assertIsNotNone(model)
        self.assertEqual(model['df_error'],5)
        self.assertAlmostEqual(model['ss_error'],float(sum((slopes-fitted)**2)))
        np.testing.assert_allclose(model['fitted'],fitted)

    def test_saturated_model_is_unavailable_but_response_tables_remain(self):
        ws=sheet()
        for column in ws.columns:column.values=column.values[:4]
        ws.columns[0].values=['a','b','c','d']
        result=analyze(ws,[2,3,4,5],[1,1,3,3],[0])
        self.assertIsNone(result['models']['slope'])
        self.assertTrue(result['response_tables']['slope']['factors'])

    def test_display_flags_and_json_are_finite(self):
        result=run({'show_graphs':False,'fit_models':False,'show_signal_plots':True})
        self.assertEqual(result['panels'],[]);self.assertTrue(result['show_signal_plots'])
        self.assertTrue(all(model is None for model in result['models'].values()))
        json.dumps(result,allow_nan=False)

    def test_signal_unit_change_changes_slope_and_sn_by_known_scale(self):
        original=row_statistics([1.,1.,3.,3.],[1.,2.,5.,6.])
        scaled=row_statistics([10.,10.,30.,30.],[1.,2.,5.,6.])
        self.assertAlmostEqual(scaled['slope'],original['slope']/10)
        self.assertAlmostEqual(scaled['sn'],original['sn']-20)
        self.assertAlmostEqual(scaled['residual_sd'],original['residual_sd'])

    def test_extreme_response_scales_keep_slope_sd_sn_finite(self):
        for scale in (1e-300,1e300):
            result=row_statistics([1.,1.,3.,3.],[value*scale for value in [1.,2.,5.,6.]])
            self.assertTrue(math.isfinite(result['slope']))
            self.assertTrue(math.isfinite(result['residual_sd']))
            self.assertAlmostEqual(result['sn'],10*math.log10(8))
            self.assertIsNone(result['mse'])
            json.dumps(result,allow_nan=False)

    def test_invalid_geometry_degrees_of_freedom_and_selectors(self):
        for signals,responses in [([1,1,1],[1,2,3]),([1,2],[1,2]),([1,2,3],[1,2]),([True,2,3],[1,2,3]),([1,float('inf'),3],[1,2,3])]:
            with self.subTest(signals=signals),self.assertRaises(ValueError):row_statistics(signals,responses)
        fixed=row_statistics([1,2],[1,3],{'reference_method':'fixed'})
        self.assertEqual(fixed['df_error'],1)
        for responses,factors,signals in [([2,2,4],[0],[1,2,3]),([2,3,4],[2],[1,2,3]),([True,3,4],[0],[1,2,3]),([2,3,4],[0],[1,2])]:
            with self.subTest(responses=responses,factors=factors),self.assertRaises(ValueError):analyze(sheet(),responses,signals,factors)

    def test_large_fixed_response_reference_does_not_invent_geometry_overflow(self):
        ws=Worksheet('Large reference',[Column('Factor','text',['A','B']),
            Column('Y1',values=[1e308,1e308]),Column('Y2',values=[1e308,1e308])])
        result=analyze(ws,[1,2],[1e-300,2e-300],[0],
            {'reference_method':'fixed','reference_response':1e308,'fit_models':False})
        self.assertEqual(result['rows'][0]['slope'],0.)
        self.assertIsNone(result['rows'][0]['sn'])
        json.dumps(result,allow_nan=False)

    def test_invalid_factor_levels_after_missing_omission_are_rejected(self):
        ws=sheet()
        for row in (2,3,6,7):ws.columns[2].values[row]=None
        with self.assertRaisesRegex(ValueError,'at least two observed levels'):
            analyze(ws,[2,3,4,5],[1,1,3,3],[0,1])

    def test_unknown_options_and_nonfinite_references_rejected(self):
        for options in ({'unknown':True},{'reference_method':'mean'},{'reference_signal':True},{'reference_response':float('nan')},{'adjusted':1},{'confidence':0},{'confidence':1}):
            with self.subTest(options=options),self.assertRaises(ValueError):settings(options)

    def test_repeated_control_rows_are_separate_runs(self):
        result=run({'fit_models':False})
        self.assertEqual(result['n_runs'],8)
        self.assertNotEqual(result['rows'][0]['sn'],result['rows'][4]['sn'])


if __name__=='__main__':unittest.main()
