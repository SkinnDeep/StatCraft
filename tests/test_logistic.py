import copy
import json
import math
import unittest
import numpy as np
from scipy import optimize, special, stats
from statcraft.model import Worksheet, Column
from statcraft.logistic import fit, settings, model_spec, predict, residual_panels


def grouped():
    return Worksheet('Grouped', [Column('Events', values=[2, 5, 9, 13, 17]), Column('Trials', values=[20]*5), Column('Dose', values=[-2,-1,0,1,2])])


def recipe(**extra):
    p = dict(response_index=0, continuous_indices=[2], categorical_indices=[], event=None, trials_index=1, terms=None, options=settings())
    p.update(extra)
    return dict(action='fit_binary_logistic', parameters=p)


def coefficient_vector(result):
    return np.asarray([c['estimate'] for c in result['coefficients']])


class BinaryLogisticTests(unittest.TestCase):
    def test_grouped_two_level_closed_form(self):
        s=Worksheet('Two groups',[Column('Y',values=[3,8]),Column('N',values=[10,10]),Column('X',values=[0,1])])
        r=fit(s,0,[2],[],trials_index=1)
        a=math.log(3/7); b=math.log(8/2)-a
        v0=1/3+1/7; v1=1/8+1/2
        self.assertAlmostEqual(r['coefficients'][0]['estimate'],a,11)
        self.assertAlmostEqual(r['coefficients'][1]['estimate'],b,11)
        self.assertAlmostEqual(r['coefficients'][0]['standard_error'],math.sqrt(v0),11)
        self.assertAlmostEqual(r['coefficients'][1]['standard_error'],math.sqrt(v0+v1),11)
        self.assertEqual(r['df_error'],0); self.assertIsNone(r['deviance_p'])
        self.assertAlmostEqual(r['deviance'],0.,10)

    def test_seeded_models_match_independent_bfgs_likelihood(self):
        rng=np.random.default_rng(742)
        for _ in range(10):
            x=rng.normal(size=30); n=rng.integers(10,45,size=30); y=rng.binomial(n,special.expit(-.3+.6*x))
            s=Worksheet('Random',[Column('Y',values=y.tolist()),Column('N',values=n.tolist()),Column('X',values=x.tolist())]); r=fit(s,0,[2],[],trials_index=1)
            design=np.column_stack([np.ones(30),x])
            ref=optimize.minimize(lambda b:np.sum(n*np.logaddexp(0,design@b)-y*(design@b)),np.zeros(2),jac=lambda b:design.T@(n*special.expit(design@b)-y),method='BFGS',options={'gtol':1e-7})
            np.testing.assert_allclose(coefficient_vector(r),ref.x,atol=1e-7)

    def test_grouped_and_expanded_bernoulli_equivalent_coefficients(self):
        s=grouped(); a=fit(s,0,[2],[],trials_index=1); ys=[]; xs=[]
        for y,n,x in zip(*(c.values for c in s.columns)):
            ys.extend([1]*y+[0]*(n-y)); xs.extend([x]*n)
        b=fit(Worksheet('Expanded',[Column('Y',values=ys),Column('X',values=xs)]),0,[1],[],event=1)
        np.testing.assert_allclose(coefficient_vector(a),coefficient_vector(b),atol=1e-10)
        np.testing.assert_allclose([c['standard_error'] for c in a['coefficients']],[c['standard_error'] for c in b['coefficients']],atol=1e-10)
        self.assertNotAlmostEqual(a['log_likelihood'],b['log_likelihood'])
        self.assertAlmostEqual(a['auc'],b['auc'],12)

    def test_loglikelihood_includes_binomial_constant(self):
        s=grouped(); r=fit(s,0,[2],[],trials_index=1)
        expected=float(np.sum(stats.binom.logpmf(s.columns[0].values,s.columns[1].values,r['probabilities'])))
        self.assertAlmostEqual(r['log_likelihood'],expected,11)
        self.assertAlmostEqual(r['aic'],-2*expected+4,10)
        self.assertAlmostEqual(r['bic'],-2*expected+math.log(100)*2,10)

    def test_null_likelihood_likelihood_ratio(self):
        r=fit(grouped(),0,[2],[],trials_index=1)
        p0=46/100
        expected=float(sum(stats.binom.logpmf([2,5,9,13,17],[20]*5,p0)))
        self.assertAlmostEqual(r['null_log_likelihood'],expected,11)
        self.assertAlmostEqual(r['model_lr'],2*(r['log_likelihood']-expected),11)
        self.assertAlmostEqual(r['model_lr_p'],stats.chi2.sf(r['model_lr'],1),12)

    def test_text_response_event_selection_and_flip(self):
        s=Worksheet('Text',[Column('Outcome','text',['yes','no','yes','no','no','yes','yes','no']),Column('X',values=[1,1,2,2,3,3,4,4])])
        a=fit(s,0,[1],[],event='yes'); b=fit(s,0,[1],[],event='no')
        self.assertEqual(a['event'],'yes'); self.assertEqual(a['non_event'],'no')
        np.testing.assert_allclose(a['probabilities'],1-np.asarray(b['probabilities']),atol=1e-12)

    def test_default_event_last_ordered(self):
        s=Worksheet('Text',[Column('Outcome','text',['yes','no']*4),Column('X',values=[1,1,2,2,3,3,4,4])])
        self.assertEqual(fit(s,0,[1],[])['event'],'yes')
        s.columns[0].metadata['value_order']=dict(mode='custom',values=['yes','no'])
        self.assertEqual(fit(s,0,[1],[])['event'],'no')

    def test_unknown_event_rejected(self):
        s=Worksheet('Binary',[Column('Y',values=[0,1]*4),Column('X',values=[1,1,2,2,3,3,4,4])])
        with self.assertRaisesRegex(ValueError,'event'):fit(s,0,[1],[],event=5)

    def test_non_binary_response_rejected(self):
        s=Worksheet('Bad',[Column('Y',values=[0,1,2,0]),Column('X',values=[1,2,3,4])])
        with self.assertRaisesRegex(ValueError,'two'):fit(s,0,[1],[])

    def test_complete_case_rows_and_missing(self):
        s=grouped(); s.columns[0].values[1]=None; s.columns[2].values[3]=None
        r=fit(s,0,[2],[],trials_index=1)
        self.assertEqual(r['row_indices'],[0,2,4]); self.assertEqual(r['missing'],2)
        self.assertEqual([v['row'] for v in r['diagnostics']],[1,3,5])

    def test_counts_require_positive_integer_trials(self):
        for y,n in [(1,0),(1,1.5),(.5,2),(-1,2),(3,2),(1,1e9+1)]:
            s=grouped(); s.columns[0].values[0]=y; s.columns[1].values[0]=n
            with self.subTest(y=y,n=n),self.assertRaises(ValueError):fit(s,0,[2],[],trials_index=1)

    def test_grouped_disallows_event_category(self):
        with self.assertRaises(ValueError):fit(grouped(),0,[2],[],trials_index=1,event=1)

    def test_complete_separation_rejected(self):
        s=Worksheet('Separated',[Column('Y',values=[0,0,0,1,1,1]),Column('X',values=[-3,-2,-1,1,2,3])])
        with self.assertRaisesRegex(ValueError,'separation'):fit(s,0,[1],[])

    def test_quasi_separation_rejected(self):
        s=Worksheet('Quasi',[Column('Y',values=[0,0,1,1]),Column('X',values=[-1,0,0,1])])
        with self.assertRaisesRegex(ValueError,'separation'):fit(s,0,[1],[])

    def test_mixed_group_rows_constrain_separation(self):
        s=Worksheet('Grouped quasi',[Column('Y',values=[0,5,10]),Column('N',values=[10]*3),Column('X',values=[-1,0,1])])
        with self.assertRaisesRegex(ValueError,'separation'):fit(s,0,[2],[],trials_index=1)

    def test_overlap_with_pure_rows_is_finite(self):
        s=Worksheet('Overlap',[Column('Y',values=[0,5,3,10]),Column('N',values=[10]*4),Column('X',values=[-1,0,1,2])])
        self.assertEqual(fit(s,0,[2],[],trials_index=1)['status'],'converged')

    def test_no_events_rejected(self):
        s=grouped(); s.columns[0].values=[0]*5
        with self.assertRaises(ValueError):fit(s,0,[2],[],trials_index=1)

    def test_no_nonevents_rejected(self):
        s=grouped(); s.columns[0].values=[20]*5
        with self.assertRaises(ValueError):fit(s,0,[2],[],trials_index=1)

    def test_rank_deficiency_rejected(self):
        s=grouped(); s.columns.append(Column('Copy',values=list(s.columns[2].values)))
        with self.assertRaisesRegex(ValueError,'rank'):fit(s,0,[2,3],[],trials_index=1)

    def test_constant_predictor_rejected(self):
        s=grouped(); s.columns[2].values=[2]*5
        with self.assertRaisesRegex(ValueError,'variation'):fit(s,0,[2],[],trials_index=1)

    def test_large_offset_scaling_preserves_probabilities(self):
        s=grouped(); a=fit(s,0,[2],[],trials_index=1)
        s.columns[2].values=[1e12+v*1e-2 for v in s.columns[2].values]
        b=fit(s,0,[2],[],trials_index=1)
        # Binary floating point represents this particular evenly spaced scale exactly.
        np.testing.assert_allclose(a['probabilities'],b['probabilities'],atol=1e-11)

    def test_small_predictor_scale_preserves_probability(self):
        s=grouped(); a=fit(s,0,[2],[],trials_index=1)
        s.columns[2].values=[v*1e-100 for v in s.columns[2].values]
        b=fit(s,0,[2],[],trials_index=1)
        np.testing.assert_allclose(a['probabilities'],b['probabilities'],atol=1e-12)

    def test_unrepresentable_coefficient_uncertainty_rejected(self):
        for scale in [1e-250,1e250]:
            s=grouped(); s.columns[2].values=[v*scale for v in s.columns[2].values]
            with self.subTest(scale=scale),self.assertRaisesRegex(ValueError,'rescale'):fit(s,0,[2],[],trials_index=1)

    def test_categorical_reference_last_level(self):
        s=Worksheet('Factors',[Column('Y',values=[3,8]),Column('N',values=[10,10]),Column('Group','text',['a','b'])])
        r=fit(s,0,[],[2],trials_index=1)
        self.assertEqual(r['coding_information'][0]['reference'],'b')
        self.assertAlmostEqual(r['coefficients'][0]['estimate'],math.log(8/2),11)
        self.assertAlmostEqual(r['coefficients'][1]['estimate'],math.log(3/7)-math.log(8/2),11)

    def test_interaction_two_factors_fits_cell_logits(self):
        s=Worksheet('Interaction',[Column('Y',values=[2,4,6,8]),Column('N',values=[10]*4),Column('A','text',['a','a','b','b']),Column('B','text',['l','h','l','h'])])
        r=fit(s,0,[],[2,3],trials_index=1,terms=[[0],[1],[0,1]])
        np.testing.assert_allclose(r['probabilities'],[.2,.4,.6,.8],atol=1e-12)
        self.assertEqual(r['df_error'],0)

    def test_nonhierarchical_terms_rejected(self):
        s=grouped(); s.columns.append(Column('Group','text',['a','a','b','b','b']))
        with self.assertRaisesRegex(ValueError,'hierarchical'):fit(s,0,[2],[3],trials_index=1,terms=[[0],[0,1]])

    def test_unused_selected_predictor_rejected(self):
        s=grouped(); s.columns.append(Column('Group','text',['a','a','b','b','b']))
        with self.assertRaisesRegex(ValueError,'each'):fit(s,0,[2],[3],trials_index=1,terms=[[0]])

    def test_numeric_factor_supported(self):
        s=Worksheet('Numeric factor',[Column('Y',values=[3,8]),Column('N',values=[10,10]),Column('F',values=[2,5])])
        self.assertEqual(fit(s,0,[],[2],trials_index=1)['coding_information'][0]['levels'],[2,5])

    def test_wald_confidence_odds_and_z(self):
        r=fit(grouped(),0,[2],[],trials_index=1)
        for c in r['coefficients']:
            self.assertAlmostEqual(c['ci_low'],c['estimate']-stats.norm.ppf(.975)*c['standard_error'],12)
            self.assertAlmostEqual(c['odds_ratio'],math.exp(c['estimate']),12)
            self.assertAlmostEqual(c['or_high'],math.exp(c['ci_high']),12)
            self.assertAlmostEqual(c['p_value'],2*stats.norm.sf(abs(c['z'])),12)

    def test_confidence_width_increases(self):
        a=fit(grouped(),0,[2],[],trials_index=1,options=dict(settings(),confidence=.8)); b=fit(grouped(),0,[2],[],trials_index=1,options=dict(settings(),confidence=.99))
        self.assertLess(a['coefficients'][1]['ci_high'],b['coefficients'][1]['ci_high'])

    def test_roc_ties_half_credit(self):
        s=Worksheet('Ties',[Column('Y',values=[5,5]),Column('N',values=[10,10]),Column('X',values=[0,1])]); r=fit(s,0,[2],[],trials_index=1)
        self.assertAlmostEqual(r['auc'],.5,12)
        self.assertEqual(r['roc_curve'][-1]['tpr'],1)
        self.assertEqual(r['roc_curve'][-1]['fpr'],1)

    def test_deviance_residuals_square_sum(self):
        r=fit(grouped(),0,[2],[],trials_index=1)
        self.assertAlmostEqual(sum(v*v for v in r['residuals']),r['deviance'],10)
        self.assertAlmostEqual(sum(v*v for v in r['pearson_residuals']),r['pearson_chi_square'],12)

    def test_threshold_changes_confusion_not_fit(self):
        a=fit(grouped(),0,[2],[],trials_index=1); b=fit(grouped(),0,[2],[],trials_index=1,options=dict(settings(),threshold=.8))
        self.assertEqual(a['probabilities'],b['probabilities']); self.assertNotEqual(a['confusion'],b['confusion'])

    def test_result_json_finite_serializable(self):
        r=fit(grouped(),0,[2],[],trials_index=1)
        json.dumps(r,allow_nan=False)

    def test_fit_does_not_mutate_sheet_or_options(self):
        s=grouped(); before=copy.deepcopy(s); o=settings(); prior=copy.deepcopy(o)
        fit(s,0,[2],[],trials_index=1,options=o)
        self.assertEqual(s,before); self.assertEqual(o,prior)

    def test_settings_strict(self):
        for o in [{},dict(settings(),confidence=True),dict(settings(),threshold=0),dict(settings(),graphs='roc'),dict(settings(),method=1),dict(settings(),diagnostics='foo')]:
            with self.subTest(o=o),self.assertRaises(ValueError):settings(o)

    def test_residual_graphs_four(self):
        r=fit(grouped(),0,[2],[],trials_index=1,options=dict(settings(),graphs='four'))
        self.assertEqual(len(residual_panels(r)),4); self.assertEqual(residual_panels(dict(r,options=settings())),[])

    def test_model_spec_order_factors_then_continuous(self):
        s=grouped(); s.columns.append(Column('Group','text',['a','a','b','b','b']))
        spec=model_spec(s,recipe(categorical_indices=[3]))
        self.assertEqual(spec['predictor_indices'],[3,2]); self.assertEqual(spec['predictors'][0]['role'],'factor')

    def test_predict_at_source_equals_fit(self):
        s=grouped(); r=fit(s,0,[2],[],trials_index=1); p=predict(s,recipe(),values=[[x] for x in s.columns[2].values])
        np.testing.assert_allclose([v['probability'] for v in p['rows']],r['probabilities'],atol=1e-12)
        for row in p['rows']:self.assertTrue(0<row['ci_low']<row['probability']<row['ci_high']<1)

    def test_prediction_closed_form_group_probability_uncertainty(self):
        s=Worksheet('Two groups',[Column('Y',values=[3,8]),Column('N',values=[10,10]),Column('X',values=[0,1])])
        p=predict(s,recipe(),values=[[0],[1]])
        self.assertAlmostEqual(p['rows'][0]['se_probability'],math.sqrt(.3*.7/10),11)
        self.assertAlmostEqual(p['rows'][1]['se_probability'],math.sqrt(.8*.2/10),11)

    def test_prediction_missing_rows_retained(self):
        p=predict(grouped(),recipe(),values=[[0],[None],[2]])
        self.assertEqual(p['missing'],1); self.assertEqual(p['rows'][1]['status'],'missing'); self.assertIsNone(p['rows'][1]['probability'])

    def test_prediction_extrapolation(self):
        p=predict(grouped(),recipe(),values=[[0],[5]])
        self.assertFalse(p['rows'][0]['extrapolated']); self.assertTrue(p['rows'][1]['extrapolated'])

    def test_prediction_one_sided_bounds(self):
        from statcraft.prediction import settings as ps
        for side in ['lower','upper']:
            p=predict(grouped(),recipe(),values=[[0]],options=dict(ps(),intervals='confidence',side=side))
            self.assertIsNone(p['rows'][0]['ci_high' if side=='lower' else 'ci_low'])

    def test_prediction_rejects_observation_intervals(self):
        from statcraft.prediction import settings as ps
        for mode in ['both','prediction']:
            with self.assertRaisesRegex(ValueError,'confidence'):predict(grouped(),recipe(),values=[[0]],options=dict(ps(),intervals=mode))

    def test_prediction_no_interval(self):
        from statcraft.prediction import settings as ps
        p=predict(grouped(),recipe(),values=[[0]],options=dict(ps(),intervals='none'))
        self.assertIsNone(p['rows'][0]['ci_low']); self.assertIsNotNone(p['rows'][0]['probability'])

    def test_prediction_columns_and_refit_current_data(self):
        s=grouped(); a=predict(s,recipe(),input_mode='columns',new_indices=[2]); s.columns[0].values[2]=12
        b=predict(s,recipe(),input_mode='columns',new_indices=[2])
        self.assertNotEqual(a['rows'][2]['probability'],b['rows'][2]['probability'])

    def test_prediction_unknown_factor_rejected(self):
        s=Worksheet('Factors',[Column('Y',values=[3,8]),Column('N',values=[10,10]),Column('Group','text',['a','b'])])
        with self.assertRaisesRegex(ValueError,'Unknown'):predict(s,recipe(continuous_indices=[],categorical_indices=[2]),values=[['c']])

    def test_invalid_model_recipe_rejected(self):
        with self.assertRaises(ValueError):model_spec(grouped(),dict(action='other',parameters={}))

    def test_prediction_json_finite(self):
        json.dumps(predict(grouped(),recipe(),values=[[0],[None],[5]]),allow_nan=False)

    def test_reject_duplicate_response_predictor(self):
        with self.assertRaises(ValueError):fit(grouped(),0,[0],[],trials_index=1)

    def test_reject_zero_predictors(self):
        with self.assertRaises(ValueError):fit(grouped(),0,[],[],trials_index=1)

    def test_revalidates_mutated_numeric_response_and_trials(self):
        for index in [0,1,2]:
            for value in ['1',True,float('nan'),float('inf')]:
                s=grouped(); s.columns[index].values[0]=value
                with self.subTest(index=index,value=value),self.assertRaises(ValueError):fit(s,0,[2],[],trials_index=1)

    def test_revalidates_mutated_binary_default_event(self):
        s=Worksheet('Binary',[Column('Y',values=[0,1]*4),Column('X',values=[1,1,2,2,3,3,4,4])]); s.columns[0].values=[False,True]*4
        with self.assertRaises(ValueError):fit(s,0,[1],[])

    def test_revalidates_text_factors(self):
        s=Worksheet('Factor',[Column('Y',values=[3,8]),Column('N',values=[10,10]),Column('F','text',['a','b'])]); s.columns[2].values[1]=2
        with self.assertRaises(ValueError):fit(s,0,[],[2],trials_index=1)

    def test_extreme_representable_confidence_stays_finite(self):
        confidence=math.nextafter(1.,0.)
        r=fit(grouped(),0,[2],[],trials_index=1,options=dict(settings(),confidence=confidence))
        self.assertTrue(all(math.isfinite(c['ci_low']) and math.isfinite(c['ci_high']) for c in r['coefficients']))
        from statcraft.prediction import settings as ps
        p=predict(grouped(),recipe(),values=[[0]],options=dict(ps(),intervals='confidence',confidence=confidence))
        self.assertTrue(0<=p['rows'][0]['ci_low']<p['rows'][0]['ci_high']<=1)
        json.dumps(r,allow_nan=False); json.dumps(p,allow_nan=False)

    def test_recursive_finite_guard_catches_nested_bad_arithmetic(self):
        from statcraft.logistic import _finite_result
        for v in [float('inf'),float('nan'),float('-inf')]:
            with self.assertRaisesRegex(ValueError,'finite precision'):_finite_result({'diagnostics':[{'z':v}]})


if __name__=='__main__':unittest.main()
