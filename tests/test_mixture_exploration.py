"""Independent simplex geometry, Scheffe values and constrained search checks."""
import copy,json,math,unittest
from unittest.mock import patch
from itertools import combinations
import numpy as np
from scipy.optimize import OptimizeResult
from statcraft.model import Column,Worksheet
from statcraft.mixture_analysis import fit,predict
from statcraft.mixture_exploration import contour,optimize


def compositions(total,count):
    if count==1:yield (total,)
    else:
        for first in range(total+1):
            for rest in compositions(total-first,count-1):yield (first,)+rest


def model(function=lambda x:10*x[0]+20*x[1]+30*x[2],n=3,total=1.,bounds=None):
    points=[[v/4 for v in row] for row in compositions(4,n)]
    rows=[point for point in points for unused in (0,1)]
    ys=[function(point)+(-.02 if at%2==0 else .02) for at,point in enumerate(rows)]
    ws=Worksheet('Mixture',[Column(chr(65+i),values=[p[i]*total for p in rows]) for i in range(n)]+[Column('Strength',values=ys)])
    result=fit(ws,n,list(range(n)),model='quadratic',total=total)
    if bounds is not None:
        result['component_bounds']=copy.deepcopy(bounds);result['mixture_fit']['component_bounds']=copy.deepcopy(bounds)
    return result


def linear_model(n=3,total=1.,bounds=None):
    terms=[{'name':chr(65+i),'components':[i]} for i in range(n)]
    limits=bounds or [{'low':0.,'high':total} for i in range(n)]
    return {'analysis':'mixture_model','confidence':.95,'response_name':'Yield','mixture_fit':{
        'schema':'statcraft-mixture-fit-v1','terms':terms,'total':total,'component_names':[chr(65+i) for i in range(n)],
        'component_bounds':limits,'centered_coefficient_values':[10.+i*10 for i in range(n)],
        'coefficient_values':[10.+i*10 for i in range(n)],'response_offset':0.,'covariance':None,'mse':0.,'df_error':10}}


class MixtureExplorationTests(unittest.TestCase):
    def test_linear_mesh_predictions_and_barycentric_coordinates(self):
        r=contour(linear_model(),options={'resolution':12,'levels':5})
        self.assertEqual(r['selected_names'],['A','B','C']);self.assertEqual(len(r['levels']),5)
        self.assertGreater(len(r['triangles']),50)
        for p in r['points']:
            a,b,c=p['components'];self.assertAlmostEqual(a+b+c,1.)
            self.assertAlmostEqual(p['x'],b+c/2);self.assertAlmostEqual(p['y'],math.sqrt(3)/2*c)
            self.assertAlmostEqual(p['fit'],10*a+20*b+30*c)
        self.assertEqual({tuple(round(c,12) for c in p) for p in r['polygon']},{(0.,0.),(1.,0.),(.5,round(math.sqrt(3)/2,12))})
        for triangle in r['triangles']:self.assertTrue(all(0<=i<len(r['points']) for i in triangle))

    def test_linear_isolines_satisfy_independent_exact_equation(self):
        r=contour(linear_model(),options={'resolution':14,'levels':6})
        for line in r['contour_lines']:
            self.assertTrue(line['segments'])
            for segment in line['segments']:
                for x,y in (segment[:2],segment[2:]):
                    c=y/(math.sqrt(3)/2);b=x-c/2;a=1-b-c
                    self.assertAlmostEqual(10*a+20*b+30*c,line['level'],places=10)

    def test_quadratic_mesh_matches_polynomial_not_corner_interpolation(self):
        fn=lambda x:10*x[0]+20*x[1]+30*x[2]+80*x[0]*x[1]-15*x[1]*x[2]
        r=contour(model(fn),options={'resolution':16})
        for p in r['points']:self.assertAlmostEqual(p['fit'],fn(p['components']),places=10)
        center=min(r['points'],key=lambda p:sum((v-1/3)**2 for v in p['components']))
        self.assertGreater(abs(center['fit']-sum(v*w for v,w in zip(center['components'],(10,20,30)))),5.)

    def test_clipped_hexagon_every_point_and_triangle_centroid_feasible(self):
        bounds=[{'low':.1,'high':.7}]*3;r=contour(linear_model(bounds=bounds),options={'resolution':16})
        self.assertEqual(len(r['polygon']),6)
        for point in r['points']:
            for v in point['components']:self.assertGreaterEqual(v,.1-1e-12);self.assertLessEqual(v,.7+1e-12)
        for triangle in r['triangles']:
            amounts=np.mean([r['points'][i]['components'] for i in triangle],axis=0)
            self.assertAlmostEqual(float(amounts.sum()),1.);self.assertTrue(np.all(amounts>=.1-1e-12))

    def test_four_components_held_actual_amount_and_selected_order(self):
        fitted=linear_model(4,total=100.)
        r=contour(fitted,[2,0,3],[{'position':1,'value':25.}],{'resolution':10})
        self.assertEqual(r['selected_names'],['C','A','D']);self.assertAlmostEqual(r['display_total'],75.)
        for p in r['points']:
            self.assertEqual(p['components'][1],25.)
            self.assertAlmostEqual(sum(p['components']),100.)
            self.assertAlmostEqual(p['x'],p['components'][0]/75.+.5*p['components'][3]/75.)
            self.assertAlmostEqual(p['fit'],sum(v*w/100 for v,w in zip(p['components'],(10,20,30,40))))

    def test_default_holds_use_saved_lower_bounds(self):
        limits=[{'low':0,'high':1}]*3+[{'low':.2,'high':.8}]
        r=contour(linear_model(4,bounds=limits));self.assertEqual(r['hold_values'][0]['value'],.2)
        self.assertAlmostEqual(r['display_total'],.8)

    def test_narrow_feasible_region_not_lost_between_uniform_grid_nodes(self):
        limits=[{'low':.315,'high':.325},{'low':.315,'high':.325},{'low':.35,'high':.37}]
        r=contour(linear_model(bounds=limits),options={'resolution':8})
        self.assertGreater(len(r['triangles']),2)
        for p in r['points']:
            for value,bound in zip(p['components'],limits):self.assertTrue(bound['low']-1e-12<=value<=bound['high']+1e-12)

    def test_no_positive_area_slice_and_invalid_holds_rejected(self):
        for holds in ([{'position':3,'value':1.}],[{'position':0,'value':.2}],[{'position':3,'value':-1.}],[]):
            with self.assertRaises(ValueError):contour(linear_model(4),[0,1,2],holds)
        with self.assertRaises(ValueError):contour(linear_model(2))
        limits=[{'low':.4,'high':.8},{'low':.4,'high':.8},{'low':.2,'high':.8}]
        with self.assertRaisesRegex(ValueError,'two-dimensional'):contour(linear_model(bounds=limits))

    def test_contour_strict_options_and_selector_identity(self):
        for positions in ([0,0,1],[True,1,2],[-1,1,2],[0,1]):
            with self.assertRaises(ValueError):contour(linear_model(),positions)
        for opts in ({'resolution':True},{'resolution':100},{'levels':1},{'title':123},{'unknown':1}):
            with self.assertRaises(ValueError):contour(linear_model(),options=opts)

    def test_linear_maximum_and_minimum_at_saved_bounds(self):
        limits=[{'low':.1,'high':.7}]*3
        for goal,expected in [('maximize',[.1,.2,.7]),('minimize',[.7,.2,.1])]:
            r=optimize(linear_model(bounds=limits),goal)
            np.testing.assert_allclose(r['components'],expected,atol=1e-10)
            self.assertTrue(r['global_optimum_proven']);self.assertTrue(r['converged'])
            self.assertEqual(r['prediction']['ci_low'],None)

    def test_quadratic_interior_maximum_known_analytic_solution(self):
        fn=lambda x:12*(x[0]*x[1]+x[0]*x[2]+x[1]*x[2])
        fitted=model(fn);r=optimize(fitted,'maximize')
        np.testing.assert_allclose(r['components'],[1/3]*3,atol=1e-6)
        self.assertAlmostEqual(r['predicted_response'],4.,places=9)
        self.assertFalse(r['global_optimum_proven']);self.assertGreaterEqual(r['converged_starts'],1)
        expected=predict(fitted,[r['components']],.95)['rows'][0]
        self.assertEqual(r['prediction'],expected)
        self.assertLess(r['prediction']['prediction_low'],r['prediction']['ci_low'])

    def test_target_goal_reaches_value_or_returns_nearest_feasible_value(self):
        fitted=linear_model()
        r=optimize(fitted,'target',target=22.)
        self.assertAlmostEqual(r['predicted_response'],22.,places=6);self.assertLess(r['target_error'],1e-6)
        outside=optimize(fitted,'target',target=100.)
        self.assertAlmostEqual(outside['predicted_response'],30.,places=6)
        self.assertAlmostEqual(outside['target_error'],70.,places=6)

    def test_tighter_bounds_and_fixed_components_are_respected(self):
        bounds=[{'low':.2,'high':.2},{'low':.1,'high':.7},{'low':.1,'high':.7}]
        r=optimize(linear_model(),bounds=bounds)
        np.testing.assert_allclose(r['components'],[.2,.1,.7],atol=1e-10)
        one=optimize(linear_model(),bounds=[{'low':v,'high':v} for v in (.2,.3,.5)])
        np.testing.assert_allclose(one['components'],[.2,.3,.5]);self.assertTrue(one['global_optimum_proven'])

    def test_infeasible_or_expanded_constraints_are_rejected(self):
        limits=[{'low':.1,'high':.8}]*3
        for bounds in ([{'low':0,'high':1}]*3,[{'low':.5,'high':.8}]*3,[{'low':.1,'high':.2}]*3,[{'low':.1,'high':.8}]):
            with self.assertRaises(ValueError):optimize(linear_model(bounds=limits),bounds=bounds)

    def test_starting_values_and_invalid_search_options_are_rejected(self):
        for opts in ({'start_values':[.5,.5,.5]},{'start_values':[1,-1,1]},{'start_values':[.2,.3]},{'starts':True},{'confidence':1},{'max_iterations':0},{'bogus':1}):
            with self.assertRaises(ValueError):optimize(linear_model(),options=opts)
        r=optimize(model(),'target',20.,options={'start_values':[.2,.3,.5]})
        self.assertAlmostEqual(sum(r['components']),1.)
        with self.assertRaises(ValueError):optimize(linear_model(),'maximize',target=20)
        with self.assertRaises(ValueError):optimize(linear_model(),'target',target=float('inf'))

    def test_nonconverged_search_does_not_claim_success(self):
        failed=OptimizeResult(success=False,x=np.array([.2,.3,.5]),nit=300)
        with patch('statcraft.mixture_exploration.minimize',return_value=failed):
            with self.assertRaisesRegex(ValueError,'did not converge'):optimize(model(),'maximize')

    def test_total_unit_scaling_and_eight_component_linear_solution(self):
        a=optimize(linear_model(),goal='maximize')
        b=optimize(linear_model(total=100),goal='maximize')
        np.testing.assert_allclose(np.array(a['components'])*100,b['components'],atol=1e-10)
        self.assertAlmostEqual(a['predicted_response'],b['predicted_response'])
        many=optimize(linear_model(8));self.assertAlmostEqual(many['components'][-1],1.)
        self.assertAlmostEqual(many['predicted_response'],80.)

    def test_constant_surface_has_no_fake_contours_and_results_are_json_finite(self):
        fitted=linear_model();fitted['mixture_fit']['centered_coefficient_values']=[4.,4.,4.]
        r=contour(fitted);self.assertEqual(r['levels'],[]);self.assertEqual(r['contour_lines'],[])
        json.dumps(r,allow_nan=False);json.dumps(optimize(fitted),allow_nan=False)

    def test_forged_saved_fit_terms_and_nonfinite_data_are_rejected(self):
        for alter in (lambda s:s.update(total=0),lambda s:s.update(centered_coefficient_values=[float('nan')]*3),
                      lambda s:s.update(terms=[{'components':[True]}]*3),lambda s:s.update(component_names=['A'])):
            fitted=linear_model();alter(fitted['mixture_fit'])
            with self.assertRaises(ValueError):contour(fitted)
            with self.assertRaises(ValueError):optimize(fitted)

    def test_special_cubic_interior_peak_and_fixed_component_curved_solution(self):
        fitted=linear_model();saved=fitted['mixture_fit']
        saved['terms'].append({'name':'A*B*C','components':[0,1,2]})
        saved['centered_coefficient_values']=[0.,0.,0.,27.]
        saved['coefficient_values']=[0.,0.,0.,27.]
        r=optimize(fitted)
        np.testing.assert_allclose(r['components'],[1/3]*3,atol=1e-6)
        self.assertAlmostEqual(r['predicted_response'],1.,places=9)
        fn=lambda x:12*(x[0]*x[1]+x[0]*x[2]+x[1]*x[2])
        limits=[{'low':0,'high':1},{'low':0,'high':1},{'low':.1,'high':.1}]
        constrained=optimize(model(fn),bounds=limits)
        np.testing.assert_allclose(constrained['components'],[.45,.45,.1],atol=1e-6)
        self.assertAlmostEqual(constrained['predicted_response'],3.51,places=8)

    def test_requested_confidence_changes_intervals_without_changing_setting(self):
        fitted=model();low=optimize(fitted,options={'confidence':.9});high=optimize(fitted,options={'confidence':.99})
        np.testing.assert_allclose(low['components'],high['components'])
        self.assertGreater(high['prediction']['ci_high']-high['prediction']['ci_low'],low['prediction']['ci_high']-low['prediction']['ci_low'])

    def test_linear_solver_failure_has_no_fabricated_solution(self):
        with patch('statcraft.mixture_exploration.linprog',return_value=OptimizeResult(success=False)):
            with self.assertRaisesRegex(ValueError,'did not converge'):optimize(linear_model())

    def test_better_start_is_retained_after_worse_local_convergence(self):
        fitted=model(lambda x:(x[0]-.7)**2,n=2)
        expected=predict(fitted,[[.7,.3]])['rows'][0]['fit']
        with patch('statcraft.mixture_exploration.minimize',return_value=OptimizeResult(success=True,x=np.asarray([.5,.5]),nit=1)):
            result=optimize(fitted,goal='minimize',options={'starts':1,'start_values':[.7,.3]})
        self.assertLessEqual(result['predicted_response'],expected+1e-12)
        self.assertEqual(result['selected_origin'],'Starting setting candidate')
