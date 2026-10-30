"""Independent desirability algebra and constrained multiresponse mixture tests."""
import copy,json,math,unittest
from unittest.mock import patch
import numpy as np
from scipy.optimize import OptimizeResult
from statcraft.mixture_multi_optimizer import optimize,evaluate,profiles,normalize,normalize_responses,settings
from test_mixture_exploration import model


def linear(coefficients,total=1.,bounds=None,name='Response'):
    n=len(coefficients);limits=bounds or [{'low':0.,'high':total} for unused in coefficients]
    return {'analysis':'mixture_model','confidence':.95,'response_name':name,'component_indices':list(range(n)),
        'mixture_fit':{'schema':'statcraft-mixture-fit-v1','total':total,'component_names':[chr(65+i) for i in range(n)],
        'component_bounds':copy.deepcopy(limits),'terms':[{'name':chr(65+i),'components':[i]} for i in range(n)],
        'centered_coefficient_values':list(coefficients),'coefficient_values':list(coefficients),'response_offset':0.,
        'covariance':None,'mse':0.,'df_error':10}}


def spec(goal='maximize',lower=0.,target=1.,upper=None,weight=1.,importance=1.):
    return dict(goal=goal,lower=lower,target=target,upper=upper,weight=weight,importance=importance)


def pair(total=1.):return [linear([1.,0.],total,name='Yield A'),linear([0.,1.],total,name='Yield B')]


class MixtureMultiOptimizerTests(unittest.TestCase):
    def test_equal_importance_independent_symmetric_geometric_mean_optimum(self):
        r=optimize(pair(),[spec(),spec()])
        self.assertAlmostEqual(r['components'][0],.5,places=6)
        self.assertAlmostEqual(r['composite_desirability'],.5,places=7)
        self.assertFalse(r['global_optimum_proven']);self.assertTrue(r['converged'])
        self.assertAlmostEqual(r['responses'][0]['desirability'],.5,places=6)
        json.dumps(r,allow_nan=False)

    def test_relative_importance_shifts_known_beta_tradeoff_optimum(self):
        r=optimize(pair(),[spec(importance=3.),spec()])
        self.assertAlmostEqual(r['components'][0],.75,places=5)
        self.assertAlmostEqual(r['composite_desirability'],(.75**3*.25)**.25,places=7)

    def test_response_weight_shapes_transfer_separately_from_importance(self):
        r=optimize(pair(),[spec(weight=2.),spec()])
        self.assertAlmostEqual(r['components'][0],2/3,places=5)
        self.assertAlmostEqual(r['responses'][0]['desirability'],(2/3)**2,places=5)
        self.assertAlmostEqual(r['composite_desirability'],math.sqrt((2/3)**2*(1/3)),places=7)

    def test_goal_minimize_and_target_transfer_functions_at_manual_settings(self):
        models=[linear([10.,0.]),linear([0.,10.])]
        specs=[spec('minimize',None,2.,8.),spec('target',1.,5.,9.)]
        r=evaluate(models,specs,[.4,.6])
        self.assertAlmostEqual(r['responses'][0]['desirability'],(8-4)/(8-2))
        self.assertAlmostEqual(r['responses'][1]['desirability'],(9-6)/(9-5))
        self.assertAlmostEqual(r['composite_desirability'],math.sqrt(.5))
        for amounts,expected in [([0.,1.],0.),([1.,0.],0.),([.5,.5],math.sqrt(.5))]:
            self.assertAlmostEqual(evaluate(models,specs,amounts)['composite_desirability'],expected)

    def test_boundary_saturation_and_unacceptable_bounds_are_exact(self):
        models=[linear([1.,0.]),linear([0.,1.])]
        specs=[spec(lower=.2,target=.6),spec('minimize',None,.2,.8)]
        r=evaluate(models,specs,[.8,.2]);self.assertEqual(r['composite_desirability'],1.)
        self.assertEqual(evaluate(models,specs,[.2,.8])['composite_desirability'],0.)
        r=optimize(models,specs);self.assertEqual(r['composite_desirability'],1.);self.assertTrue(r['global_optimum_proven'])

    def test_continuation_escapes_zero_desirability_start_and_narrow_positive_region(self):
        r=optimize(pair(),[spec(lower=.510,target=.511),spec(lower=.489,target=.490)],
                   options={'starts':1,'start_values':[.9,.1]})
        self.assertTrue(r['positive_desirability']);self.assertAlmostEqual(r['components'][0],.5105,places=5)
        self.assertAlmostEqual(r['composite_desirability'],.5,places=4)

    def test_no_positive_solution_found_is_not_a_claim_of_infeasibility(self):
        r=optimize(pair(),[spec(lower=.9,target=1.),spec(lower=.9,target=1.)])
        self.assertEqual(r['composite_desirability'],0.);self.assertFalse(r['positive_desirability'])
        self.assertEqual(r['status'],'no_positive_solution_found')
        self.assertTrue(any('does not prove' in warning for warning in r['warnings']))
        self.assertTrue(r['converged']);self.assertFalse(r['global_optimum_proven'])

    def test_unit_scaling_preserves_composition_and_desirability(self):
        baseline=optimize(pair(),[spec(),spec()])
        for total in (100.,1e-50,1e50):
            r=optimize(pair(total),[spec(),spec()])
            np.testing.assert_allclose(np.asarray(r['components'])/total,baseline['components'],rtol=1e-6)
            self.assertAlmostEqual(r['composite_desirability'],baseline['composite_desirability'],places=7)

    def test_response_unit_scaling_including_extremes_preserves_tradeoff(self):
        for scale in (1e-100,1e100):
            models=[linear([scale,0.]),linear([0.,scale])]
            r=optimize(models,[spec(target=scale),spec(target=scale)])
            self.assertAlmostEqual(r['components'][0],.5,places=6)
            self.assertAlmostEqual(r['composite_desirability'],.5,places=7)

    def test_intersection_and_tighter_bounds_are_retained_in_original_units(self):
        models=[linear([1.,0.],100.,[{'low':10.,'high':90.}]*2),linear([0.,1.],100.,[{'low':20.,'high':70.}]*2)]
        r=optimize(models,[spec(),spec()],bounds=[{'low':60.,'high':65.},{'low':35.,'high':40.}])
        self.assertAlmostEqual(r['components'][0],60.,places=5)
        self.assertEqual(r['component_bounds'],[{'low':60.,'high':65.},{'low':35.,'high':40.}])
        with self.assertRaises(ValueError):optimize(models,[spec(),spec()],bounds=[{'low':0.,'high':100.}]*2)

    def test_fixed_components_and_unique_feasible_setting(self):
        r=optimize(pair(),[spec(),spec()],bounds=[{'low':.3,'high':.3},{'low':.7,'high':.7}])
        self.assertEqual(r['components'],[.3,.7]);self.assertTrue(r['global_optimum_proven'])
        self.assertAlmostEqual(r['composite_desirability'],math.sqrt(.21))

    def test_intersected_regions_with_no_common_blend_fail(self):
        a=linear([1.,0.],bounds=[{'low':0.,'high':.3},{'low':0.,'high':1.}])
        b=linear([0.,1.],bounds=[{'low':.8,'high':1.},{'low':0.,'high':1.}])
        with self.assertRaisesRegex(ValueError,'common'):normalize([a,b],[spec(),spec()])
        with self.assertRaisesRegex(ValueError,'fixed-total'):optimize(pair(),[spec(),spec()],bounds=[{'low':.6,'high':.9}]*2)

    def test_model_order_names_totals_and_source_coordinate_mismatch_fail(self):
        for field,value in [('component_names',['B','A']),('total',100.)]:
            models=pair();models[1]['mixture_fit'][field]=value
            with self.assertRaises(ValueError):normalize(models,[spec(),spec()])
        models=pair();models[1]['component_indices']=[1,0]
        with self.assertRaisesRegex(ValueError,'physical'):normalize(models,[spec(),spec()])

    def test_invalid_specs_settings_and_components_raise(self):
        for specs in ([spec()], [spec(weight=0),spec()], [spec(importance=True),spec()], [spec(upper=2.),spec()],
                      [spec(goal='target',lower=1.,target=1.,upper=2.),spec()]):
            with self.assertRaises(ValueError):normalize_responses(specs)
        for opts in ({'starts':True},{'max_iterations':3},{'confidence':1.},{'typo':1}):
            with self.assertRaises(ValueError):settings(opts)
        for point in ([.2,.2],[-.1,1.1],[float('nan'),.5],[True,False]):
            with self.assertRaises(ValueError):evaluate(pair(),[spec(),spec()],point)
        with self.assertRaises(ValueError):optimize(pair(),[spec(),spec()],options={'start_values':[.2,.2]})

    def test_failed_solver_does_not_manufacture_success_from_boundary_candidates(self):
        with patch('statcraft.mixture_multi_optimizer.minimize',return_value=OptimizeResult(success=False,x=np.asarray([.5,.5]),nit=1)):
            with self.assertRaisesRegex(ValueError,'did not converge'):optimize(pair(),[spec(),spec()])

    def test_exact_fit_uncertainty_is_missing_and_estimated_models_have_intervals(self):
        r=evaluate(pair(),[spec(),spec()],[.4,.6])
        self.assertTrue(all(row['prediction']['ci_low'] is None for row in r['responses']))
        models=[model(lambda x:10*x[0]+20*x[1],n=2),model(lambda x:20*x[0]+10*x[1],n=2)]
        r=optimize(models,[spec(lower=5.,target=25.),spec(lower=5.,target=25.)],options={'confidence':.9})
        for row in r['responses']:
            self.assertLess(row['prediction']['ci_low'],row['fit']);self.assertGreater(row['prediction']['ci_high'],row['fit'])
            self.assertLess(row['prediction']['prediction_low'],row['prediction']['ci_low'])

    def test_curved_three_component_search_compares_with_independent_dense_grid(self):
        fn1=lambda x:1-2*(x[0]-.25)**2-(x[1]-.4)**2
        fn2=lambda x:1-(x[0]-.55)**2-2*(x[1]-.2)**2
        models=[model(fn1),model(fn2)];specs=[spec(),spec()]
        r=optimize(models,specs)
        grid=[]
        for a in np.linspace(0,1,101):
            for b in np.linspace(0,1-a,101):grid.append(math.sqrt(max(0,fn1([a,b,1-a-b]))*max(0,fn2([a,b,1-a-b]))))
        self.assertGreaterEqual(r['composite_desirability'],max(grid)-1e-5)
        self.assertAlmostEqual(sum(r['components']),1.)

    def test_profiles_preserve_closure_and_match_manual_predictions(self):
        result=profiles(pair(),[spec(),spec()],[.4,.6],options={'points':11})
        self.assertEqual(len(result),1);p=result[0];self.assertEqual(p['balance_position'],1)
        for x,d,y1,y2 in zip(p['x'],p['composite_desirability'],p['responses'][0]['fits'],p['responses'][1]['fits']):
            self.assertAlmostEqual(y1,x);self.assertAlmostEqual(y2,1-x);self.assertAlmostEqual(d,math.sqrt(max(0,x*(1-x))))
        self.assertEqual(p['current'],.4)

    def test_fixed_profile_is_one_point_and_bounds_are_exact(self):
        p=profiles(pair(),[spec(),spec()],[.3,.7],bounds=[{'low':.3,'high':.3},{'low':.7,'high':.7}])[0]
        self.assertEqual(p['x'],[.3]);self.assertEqual(len(p['responses'][0]['fits']),1)
        with self.assertRaises(ValueError):profiles(pair(),[spec(),spec()],[.5,.5],options={'balance_position':True})

    def test_eight_responses_and_eight_components_remain_finite(self):
        models=[linear([1. if i==j else .1 for i in range(8)],name='R'+str(j)) for j in range(8)]
        r=optimize(models,[spec() for i in range(8)],options={'starts':4})
        self.assertEqual(len(r['responses']),8);self.assertTrue(r['positive_desirability'])
        np.testing.assert_allclose(r['components'],[1/8]*8,atol=1e-5)
        json.dumps(r,allow_nan=False)

    def test_log_composite_retains_tiny_positive_individual_desirability(self):
        models=[linear([1e-100,1e-100]),linear([1.,1.])]
        r=evaluate(models,[spec(weight=10.,importance=.1),spec(importance=10.)],[.5,.5])
        self.assertEqual(r['responses'][0]['desirability'],0.)
        self.assertLess(r['responses'][0]['log_desirability'],-2000)
        expected=math.exp(.1/10.1*10*math.log(1e-100))
        self.assertGreater(r['composite_desirability'],0.)
        self.assertAlmostEqual(r['composite_desirability']/expected,1.)
        self.assertTrue(any('individual desirabilities' in w for w in r['warnings']))

    def test_caller_models_specs_bounds_and_options_are_not_mutated(self):
        models=pair();specs=[spec(),spec()];bounds=[{'low':.2,'high':.8}]*2
        options={'starts':2,'start_values':[.3,.7]};before=copy.deepcopy((models,specs,bounds,options))
        optimize(models,specs,bounds,options)
        self.assertEqual((models,specs,bounds,options),before)

    def test_better_user_start_is_retained_if_local_search_converges_to_worse_point(self):
        models=pair();specs=[spec(importance=2.),spec()];initial=[2/3,1/3]
        expected=evaluate(models,specs,initial)['composite_desirability']
        with patch('statcraft.mixture_multi_optimizer.minimize',return_value=OptimizeResult(success=True,x=np.asarray([.5,.5]),nit=1)):
            result=optimize(models,specs,options={'starts':1,'start_values':initial})
        self.assertGreaterEqual(result['composite_desirability'],expected-1e-14)
        self.assertEqual(result['selected_origin'],'Starting setting candidate')
        self.assertTrue(result['converged'])
