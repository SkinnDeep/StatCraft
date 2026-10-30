import copy,json,math,unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
from statcraft.model import Column,Worksheet
from statcraft.mixture_process_model import fit,predict
from statcraft.mixture_joint_optimizer import optimize


def model(external=False,noise=False):
    data=[[] for _ in range(6 if external else 4)];row=0
    for a in np.linspace(0,1,5):
        for z in (-1.,0.,1.):
            for cov in ((4.,6.,8.) if external else (6.,)):
                for block in (('Morning','Evening') if external else (None,)):
                    y=25-10*(a-.3)**2-4*(z-.25)**2+(2*(cov-6) if external else 0)+(3 if block=='Evening' else 0)+(.015*math.sin(row+1) if noise else 0)
                    values=[a*100,(1-a)*100,100+20*z]+([cov,block] if external else [])+[y]
                    for col,value in zip(data,values):col.append(value)
                    row+=1
    names=['Binder','Resin','Temperature']+(['Moisture','Shift'] if external else [])+['Strength']
    ws=Worksheet('Joint test',[Column(n,'text' if n=='Shift' else 'number',v) for n,v in zip(names,data)])
    return fit(ws,len(data)-1,[0,1],[2],4 if external else None,[3] if external else None,model='quadratic',total=100.,options={'process_order':2}),ws


class JointOptimizerTests(unittest.TestCase):
    def test_known_interior_joint_maximum(self):
        r,ws=model();o=optimize(r,options={'starts':10})
        self.assertAlmostEqual(o['components'][0],30.,delta=.002);self.assertAlmostEqual(o['processes'][0],105.,delta=.002);self.assertAlmostEqual(o['prediction']['fit'],25.,delta=1e-9)
        self.assertAlmostEqual(sum(o['components']),100.);self.assertFalse(o['global_optimum_proven']);json.dumps(o,allow_nan=False)
    def test_minimum_and_target(self):
        r,_=model();o=optimize(r,'minimize',options={'starts':6});self.assertAlmostEqual(o['prediction']['fit'],13.85,places=7)
        t=optimize(r,'target',20.,options={'starts':8});self.assertLess(t['target_error'],1e-5)
    def test_uncertainty_equals_complete_original_model(self):
        r,_=model(True,True);o=optimize(r,covariate_values=[6.],block_value='Morning',options={'starts':8,'confidence':.9})
        expected=predict(r,[o['components']],[o['processes']],[[6.]],['Morning'],.9)['rows'][0]
        self.assertEqual(o['prediction'],expected);self.assertLess(expected['prediction_low'],expected['ci_low']);self.assertLess(expected['ci_low'],expected['fit']);self.assertLess(expected['fit'],expected['ci_high'])
    def test_fixed_external_settings_are_explicit(self):
        r,_=model(True)
        for kw in ({},{'covariate_values':[6.]},{'covariate_values':[6.],'block_value':'Unknown'},{'covariate_values':[True],'block_value':'Morning'}):
            with self.assertRaises(ValueError):optimize(r,**kw)
        a=optimize(r,covariate_values=[6.],block_value='Morning',options={'starts':5});b=optimize(r,covariate_values=[6.],block_value='Evening',options={'starts':5});self.assertAlmostEqual(b['predicted_response']-a['predicted_response'],3.,places=7)
    def test_bounds_and_fixed_components_with_varying_process(self):
        r,_=model();o=optimize(r,component_bounds=[{'low':20.,'high':20.},{'low':80.,'high':80.}],options={'starts':5})
        self.assertEqual(o['components'],[20.,80.]);self.assertAlmostEqual(o['processes'][0],105.,delta=.002)
        locked=optimize(r,process_bounds=[{'low':100.,'high':100.}],options={'starts':5});self.assertAlmostEqual(locked['components'][0],30.,delta=.002);self.assertEqual(locked['processes'],[100.])
    def test_unique_setting_needs_no_solver(self):
        r,_=model()
        with patch('statcraft.mixture_joint_optimizer.minimize',side_effect=AssertionError('solver not needed')):
            o=optimize(r,component_bounds=[{'low':30.,'high':30.},{'low':70.,'high':70.}],process_bounds=[{'low':105.,'high':105.}])
        self.assertTrue(o['global_optimum_proven']);self.assertEqual(o['converged_starts'],1)
    def test_invalid_bounds_and_goals_are_rejected(self):
        r,_=model()
        for kw in ({'goal':'wrong'},{'target':20.},{'goal':'target','target':float('nan')},{'process_bounds':[{'low':70.,'high':120.}]},{'component_bounds':[{'low':60.,'high':100.},{'low':60.,'high':100.}]},{'options':{'starts':True}},{'options':{'unknown':1}},{'options':{'start_components':[20.,20.]}},{'options':{'start_processes':[200.]}}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):optimize(r,**kw)
    def test_better_start_candidate_is_retained_after_solver_converges(self):
        r,_=model();bad=np.asarray([0.,1.,-1.])
        with patch('statcraft.mixture_joint_optimizer.minimize',return_value=SimpleNamespace(success=True,x=bad,nit=1)):
            o=optimize(r,options={'starts':1,'start_components':[30.,70.],'start_processes':[105.]})
        self.assertEqual(o['selected_origin'],'Starting setting candidate');self.assertAlmostEqual(o['predicted_response'],25.,places=9)
    def test_no_solver_convergence_is_not_silently_successful(self):
        r,_=model()
        with patch('statcraft.mixture_joint_optimizer.minimize',return_value=SimpleNamespace(success=False,x=np.asarray([.3,.7,.25]),nit=1)):
            with self.assertRaisesRegex(ValueError,'did not converge'):optimize(r,options={'starts':2})
    def test_profiles_are_conditional_full_model_predictions(self):
        r,_=model();o=optimize(r,options={'starts':5,'profile_points':9});self.assertEqual(len(o['profiles']),3)
        for profile in o['profiles']:
            for i,x in enumerate(profile['x']):
                amounts=o['components'].copy();process=o['processes'].copy()
                if profile['role']=='component':
                    pos=profile['position'];balance=profile['balance_position'];pair=amounts[balance]+amounts[pos];amounts[balance]=max(0.,pair-x);amounts[pos]=x
                else:process[profile['position']]=x
                expected=predict(r,[amounts],[process])['rows'][0]['fit'];self.assertAlmostEqual(profile['fits'][i],expected,places=8)
    def test_inputs_and_saved_model_remain_unchanged(self):
        r,_=model();before=copy.deepcopy(r);kw={'process_bounds':[{'low':90.,'high':110.}],'options':{'starts':5}};saved=copy.deepcopy(kw);optimize(r,**kw);self.assertEqual(r,before);self.assertEqual(kw,saved)
    def test_corrupt_saved_covariance_rejected(self):
        r,_=model(True,True);r['mixture_process_fit']['covariance'][0][0]=-100.
        with self.assertRaisesRegex(ValueError,'positive semidefinite'):optimize(r,covariate_values=[6.],block_value='Morning')

if __name__=='__main__':unittest.main()
