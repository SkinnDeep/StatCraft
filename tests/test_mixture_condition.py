"""Independent conditional-basis and full-fit uncertainty comparisons."""
import copy,json,math,unittest
from unittest.mock import patch
import numpy as np
from scipy.optimize import OptimizeResult
from statcraft.model import Column,Worksheet
from statcraft.mixture_process_model import fit,predict as full_predict
from statcraft.mixture_analysis import predict as mixture_predict
from statcraft.mixture_condition import condition,contour,optimize
from test_mixture_process_model import fitted,fixture,manual_matrix


def two_component():
    rows=[]
    for a in (0.,.25,.5,.75,1.):
        for z in (-1.,0.,1.):
            for noise in (-.01,.01):rows.append((a,1-a,100+20*z,5*a+10*(1-a)+z*(10*a-10*(1-a))+noise))
    ws=Worksheet('Two-component process',[Column(name,values=[r[i] for r in rows]) for i,name in enumerate(('A','B','Temperature','Yield'))])
    return fit(ws,3,[0,1],[2],model='linear',options={'process_coding':[{'low':80.,'high':120.}]})


def multi_process(model='quadratic'):
    mixes=[(1.,0.,0.),(0.,1.,0.),(0.,0.,1.),(.5,.5,0.),(.5,0.,.5),(0.,.5,.5)]
    if model=='special_cubic':mixes.append((1/3,1/3,1/3))
    rows=[];rng=np.random.default_rng(8611)
    for a,b,c in mixes:
        for z in (-1.,0.,1.):
            for w in (-1.,0.,1.):
                for block in ('A','B'):
                    cov=float(rng.uniform(-.8,.8))
                    mean=10*a+20*b+30*c+8*a*b+15*a*b*c+z*(3*a+4*b*c)+w*(2*b+5*a*b*c)+z*w*(a-b)+z*z*(2*c)+1.2*cov+(2 if block=='A' else 0)
                    for noise in (-.02,.02):rows.append((a,b,c,50+10*z,100+20*w,3+cov,block,mean+noise))
    names=('A','B','C','Temperature','Speed','Covariate','Block','Yield')
    ws=Worksheet('Two processes',[Column(name,'text' if i==6 else 'number',[r[i] for r in rows]) for i,name in enumerate(names)])
    return fit(ws,7,[0,1,2],[3,4],6,[5],model=model,options={'process_order':2,'process_coding':[{'low':40.,'high':60.},{'low':80.,'high':120.}],'covariate_coding':[{'low':2.,'high':4.}]})


class MixtureConditionTests(unittest.TestCase):
    def test_conditional_predictions_match_full_model_at_many_points_and_confidence_levels(self):
        r=fitted();rng=np.random.default_rng(8601);points=rng.dirichlet([1,1,1],12).tolist()
        c=condition(r,[110.],[41.],'Day1')
        for confidence in (.8,.95,.99):
            full=full_predict(r,points,[[110.]]*12,[[41.]]*12,['Day1']*12,confidence)['rows']
            sliced=mixture_predict(c,points,confidence)['rows']
            for a,b in zip(full,sliced):
                for key in ('fit','standard_error','ci_low','ci_high','prediction_low','prediction_high'):self.assertAlmostEqual(a[key],b[key],places=11)
        self.assertEqual(c['conditioning']['process_coded_values'],[.5]);self.assertIn('Day1',c['conditioning']['summary'])
        self.assertNotIn('mixture_process_fit',c);json.dumps(c,allow_nan=False)

    def test_conditional_means_match_independent_known_polynomial(self):
        r=fitted();z=.5;cov=.2
        c=condition(r,[110.],[41.],'Day1')
        for a,b,cval in ((.2,.3,.5),(.8,.1,.1),(0.,1.,0.)):
            expected=10*a+20*b+30*cval+4*a*b-2*a*cval+3*b*cval+z*(2*a-3*b+4*cval+5*a*b+a*cval-2*b*cval)+1.75*cov+2.5
            self.assertAlmostEqual(mixture_predict(c,[[a,b,cval]])['rows'][0]['fit'],expected,places=11)

    def test_random_full_covariance_matches_independent_full_vector_quadratic_form(self):
        r=fitted();p=len(r['mixture_process_fit']['terms']);rng=np.random.default_rng(8602);a=rng.normal(size=(p,p));cov=a@a.T*.003
        r['mixture_process_fit']['covariance']=cov.tolist();s=condition(r,[110.],[41.],'Day1')
        point=np.asarray([.2,.3,.5,.06,.1,.15]);full=np.r_[point,point*.5,.2,1.]
        projected=np.asarray(s['mixture_fit']['covariance'])
        self.assertAlmostEqual(float(point@projected@point),float(full@cov@full),places=13)
        expected=math.sqrt(float(full@cov@full))
        self.assertAlmostEqual(mixture_predict(s,[[.2,.3,.5]])['rows'][0]['standard_error'],expected,places=13)

    def test_additive_covariates_and_blocks_change_conditional_constant_with_covariance(self):
        r=fitted();a=condition(r,[100.],[40.],'Day2');b=condition(r,[100.],[41.],'Day1')
        expected=2.5+1.75*.2
        for point in ([1,0,0],[0,1,0],[.2,.3,.5]):
            self.assertAlmostEqual(mixture_predict(b,[point])['rows'][0]['fit']-mixture_predict(a,[point])['rows'][0]['fit'],expected,places=11)
        self.assertFalse(np.allclose(a['mixture_fit']['covariance'],b['mixture_fit']['covariance']))

    def test_two_process_quadratic_and_special_cubic_interactions_preserve_full_predictions(self):
        for model in ('quadratic','special_cubic'):
            r=multi_process(model);s=condition(r,[55.,90.],[3.2],'A');points=[[.2,.3,.5],[1/3]*3,[.7,.2,.1]]
            expected=full_predict(r,points,[[55.,90.]]*3,[[3.2]]*3,['A']*3)['rows']
            actual=mixture_predict(s,points)['rows']
            for a,b in zip(expected,actual):
                for key in ('fit','standard_error','ci_low','ci_high','prediction_low','prediction_high'):self.assertAlmostEqual(a[key],b[key],places=10)

    def test_process_only_covariate_only_and_block_only_roles(self):
        ws=fixture()
        for params,held in [({'process_indices':[3]},([100.],None,None)),({'covariate_indices':[4]},(None,[40.],None)),({'block_index':5},(None,None,'Day2'))]:
            r=fit(ws,6,[0,1,2],**params);s=condition(r,*held)
            expected=full_predict(r,[[.2,.3,.5]],None if held[0] is None else [held[0]],None if held[1] is None else [held[1]],None if held[2] is None else [held[2]])['rows'][0]
            actual=mixture_predict(s,[[.2,.3,.5]])['rows'][0]
            self.assertAlmostEqual(actual['fit'],expected['fit'],places=11);self.assertAlmostEqual(actual['standard_error'],expected['standard_error'],places=11)

    def test_holding_values_are_explicit_and_known_block_types_are_preserved(self):
        r=fitted()
        for args in ((None,[40.],'Day1'),([100.],None,'Day1'),([100.],[40.],None),([100.],[40.],True),([100.],[40.],'unknown')):
            with self.assertRaises(ValueError):condition(r,*args)
        ws=fixture();ws.columns[5]=Column('Block',values=[1 if value=='Day1' else 2 for value in ws.columns[5].values]);r=fit(ws,6,[0,1,2],[3],5,[4])
        self.assertEqual(condition(r,[100.],[40.],1)['conditioning']['block_value'],1)
        with self.assertRaises(ValueError):condition(r,[100.],[40.],'1')

    def test_unselected_roles_reject_extra_values(self):
        r=two_component()
        with self.assertRaises(ValueError):condition(r,[100.],[1.])
        with self.assertRaises(ValueError):condition(r,[100.],None,'Day1')
        self.assertEqual(condition(r,[100.],(),None)['conditioning']['covariate_values'],[])

    def test_extrapolation_is_reported_without_treating_coding_range_as_hard_constraint(self):
        r=fitted();s=condition(r,[140.],[50.],'Day1')
        self.assertTrue(any('extrapolate' in warning for warning in s['warnings']))
        self.assertEqual(s['conditioning']['process_values'],[140.]);self.assertEqual(s['conditioning']['process_coded_values'],[2.])
        actual=mixture_predict(s,[[.2,.3,.5]])['rows'][0]
        expected=full_predict(r,[[.2,.3,.5]],[[140.]],[[50.]],['Day1'])['rows'][0]
        self.assertAlmostEqual(actual['fit'],expected['fit'],places=10)

    def test_total_unit_scaling_preserves_conditional_mean_and_uncertainty(self):
        a=condition(fitted(),[100.],[40.],'Day2');b=condition(fitted(fixture(100.),total=100.),[100.],[40.],'Day2')
        x=mixture_predict(a,[[.2,.3,.5]])['rows'][0];y=mixture_predict(b,[[20.,30.,50.]])['rows'][0]
        for key in ('fit','standard_error','ci_low','ci_high','prediction_low','prediction_high'):self.assertAlmostEqual(x[key],y[key],places=11)

    def test_exact_fit_keeps_uncertainty_unavailable(self):
        r=fitted(fixture(noise=0));s=condition(r,[100.],[40.],'Day1');p=mixture_predict(s,[[.2,.3,.5]])['rows'][0]
        self.assertIsNone(s['mixture_fit']['covariance']);self.assertIsNone(p['standard_error']);self.assertIsNone(p['prediction_low'])

    def test_contour_is_feasible_and_every_value_matches_original_process_prediction(self):
        r=fitted();out=contour(r,[110.],[41.],'Day1',options={'resolution':8,'levels':4})
        self.assertEqual(out['analysis'],'mixture_contour');self.assertEqual(out['conditioning']['block_value'],'Day1')
        rows=out['points'];expected=full_predict(r,[row['components'] for row in rows],[[110.]]*len(rows),[[41.]]*len(rows),['Day1']*len(rows))['rows']
        for point,p in zip(rows,expected):self.assertAlmostEqual(sum(point['components']),1.);self.assertAlmostEqual(point['fit'],p['fit'],places=11)

    def test_process_holding_level_changes_optimized_composition_and_retains_intervals(self):
        r=two_component();low=optimize(r,[80.]);high=optimize(r,[120.])
        np.testing.assert_allclose(low['components'],[0.,1.],atol=1e-10);np.testing.assert_allclose(high['components'],[1.,0.],atol=1e-10)
        for out,held in ((low,80.),(high,120.)):
            self.assertTrue(out['global_optimum_proven']);expected=full_predict(r,[out['components']],[[held]])['rows'][0]
            self.assertAlmostEqual(out['prediction']['fit'],expected['fit'],places=11);self.assertAlmostEqual(out['prediction']['standard_error'],expected['standard_error'],places=11)
            self.assertFalse(any('process/block effects are not implemented' in warning for warning in out['warnings']))

    def test_contour_and_optimizer_require_all_external_holds(self):
        r=fitted()
        for call in (lambda:contour(r,[100.],None,'Day1'),lambda:optimize(r,[100.],[40.],None)):
            with self.assertRaises(ValueError):call()

    def test_saved_state_incomplete_terms_and_bad_covariance_are_rejected(self):
        r=fitted()
        changes=[('terms',r['mixture_process_fit']['terms'][:-1]),('centered_coefficient_values',[1.]),('covariance',[[1.]]),('df_error',True),('mse',-1.),('covariance',None)]
        for key,value in changes:
            bad=copy.deepcopy(r);bad['mixture_process_fit'][key]=value
            with self.assertRaises(ValueError,msg=key):condition(bad,[100.],[40.],'Day1')
        for key in ('process_coding','block_reference','covariance'):
            bad=copy.deepcopy(r);del bad['mixture_process_fit'][key]
            with self.assertRaises(ValueError):condition(bad,[100.],[40.],'Day1')

    def test_nonsymmetric_nonfinite_indefinite_and_bool_term_state_are_rejected(self):
        r=fitted();size=len(r['mixture_process_fit']['terms'])
        for badcov in (np.eye(size)*-1,np.full((size,size),math.inf)):
            bad=copy.deepcopy(r);bad['mixture_process_fit']['covariance']=badcov.tolist()
            with self.assertRaises(ValueError):condition(bad,[100.],[40.],'Day1')
        bad=copy.deepcopy(r);bad['mixture_process_fit']['covariance'][0][1]+=.2
        with self.assertRaises(ValueError):condition(bad,[100.],[40.],'Day1')
        bad=copy.deepcopy(r);bad['mixture_process_fit']['terms'][1]['components']=[True]
        with self.assertRaises(ValueError):condition(bad,[100.],[40.],'Day1')

    def test_nonfinite_or_wrong_width_holds_do_not_get_silently_defaulted(self):
        r=fitted()
        for args in (([float('nan')],[40.],'Day1'),([True],[40.],'Day1'),([100.,110.],[40.],'Day1'),([100.],[float('inf')],'Day1')):
            with self.assertRaises(ValueError):condition(r,*args)

    def test_inputs_are_not_mutated_by_condition_contour_or_optimization(self):
        r=fitted();before=copy.deepcopy(r);z=[100.];cov=[40.];opts={'resolution':8}
        condition(r,z,cov,'Day2');contour(r,z,cov,'Day2',options=opts);optimize(r,z,cov,'Day2',options={'starts':2})
        self.assertEqual(r,before);self.assertEqual(z,[100.]);self.assertEqual(opts,{'resolution':8})

    def test_better_explicit_start_survives_worse_local_result_through_wrapper(self):
        rows=[]
        for a in (0.,.25,.5,.75,1.):
            for z in (-1.,0.,1.):
                for noise in (-.01,.01):rows.append((a,1-a,100+20*z,(a-.7)**2+z*a+noise))
        ws=Worksheet('Curved mixture',[Column(name,values=[row[i] for row in rows]) for i,name in enumerate(('A','B','Temperature','Y'))])
        r=fit(ws,3,[0,1],[2],model='quadratic')
        expected=full_predict(r,[[.7,.3]],[[100.]])['rows'][0]['fit']
        with patch('statcraft.mixture_exploration.minimize',return_value=OptimizeResult(success=True,x=np.asarray([.5,.5]),nit=1)):
            result=optimize(r,[100.],goal='minimize',options={'starts':1,'start_values':[.7,.3]})
        self.assertLessEqual(result['predicted_response'],expected+1e-12)
        self.assertEqual(result['selected_origin'],'Starting setting candidate')

    def test_failed_search_remains_an_error_even_with_valid_start_and_boundary_points(self):
        r=fitted()
        with patch('statcraft.mixture_exploration.minimize',return_value=OptimizeResult(success=False)):
            with self.assertRaisesRegex(ValueError,'did not converge'):optimize(r,[100.],[40.],'Day1',options={'starts':1,'start_values':[.2,.3,.5]})

    def test_four_component_contour_preserves_extra_component_hold_and_full_model_values(self):
        rows=[]
        for a in range(3):
            for b in range(3-a):
                for c in range(3-a-b):
                    d=2-a-b-c
                    for z in (-1.,0.,1.):
                        for noise in (-.02,.02):
                            aa,bb,cc,dd=[v/2 for v in (a,b,c,d)]
                            rows.append((aa,bb,cc,dd,100+20*z,10*aa+20*bb+30*cc+40*dd+z*(aa-dd)+noise))
        ws=Worksheet('Four mixture components',[Column(name,values=[row[i] for row in rows]) for i,name in enumerate(('A','B','C','D','Temperature','Y'))])
        r=fit(ws,5,[0,1,2,3],[4]);out=contour(r,[110.],component_positions=[0,1,2],hold_values=[{'position':3,'value':.2}],options={'resolution':8})
        self.assertAlmostEqual(out['display_total'],.8)
        expected=full_predict(r,[point['components'] for point in out['points']],[[110.]]*len(out['points']))['rows']
        for point,prediction in zip(out['points'],expected):
            self.assertAlmostEqual(point['components'][3],.2);self.assertAlmostEqual(sum(point['components']),1.)
            self.assertAlmostEqual(point['fit'],prediction['fit'],places=11)
