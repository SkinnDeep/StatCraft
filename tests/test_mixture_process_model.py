"""Independent OLS algebra for crossed mixture/process, covariate and block fits."""
import copy,json,math,unittest
import numpy as np
from scipy import stats
from statcraft.model import Column,Worksheet
from statcraft.mixture_process_model import fit,predict
from statcraft.mixture_process_report import text_report


def fixture(total=1.,noise=.02):
    mixes=[(1,0,0),(0,1,0),(0,0,1),(.5,.5,0),(.5,0,.5),(0,.5,.5)]
    rng=np.random.default_rng(8501);rows=[]
    for a,b,c in mixes:
        for z in (-1.,0.,1.):
            for block in ('Day1','Day2'):
                cov=float(rng.uniform(-.9,.9))
                base=10*a+20*b+30*c+4*a*b-2*a*c+3*b*c
                interaction=z*(2*a-3*b+4*c+5*a*b+a*c-2*b*c)
                mean=base+interaction+1.75*cov+(2.5 if block=='Day1' else 0.)
                for rep in (-1.,1.):rows.append((a*total,b*total,c*total,100+20*z,40+5*cov,block,mean+rep*noise))
    names=['A','B','C','Temperature','Humidity','Day','Strength']
    ws=Worksheet('Crossed experiment',[Column(name,'text' if i==5 else 'number',[row[i] for row in rows]) for i,name in enumerate(names)])
    return ws


def fitted(ws=None,**kwargs):
    return fit(fixture() if ws is None else ws,6,[0,1,2],[3],5,[4],options={'process_coding':[{'low':80.,'high':120.}],'covariate_coding':[{'low':35.,'high':45.}]},**kwargs)


def manual_matrix(ws):
    data=[]
    for row in range(ws.row_count):
        a,b,c=[ws.columns[i].values[row] for i in (0,1,2)];z=(ws.columns[3].values[row]-100)/20;cov=(ws.columns[4].values[row]-40)/5
        mixture=[a,b,c,a*b,a*c,b*c]
        data.append(mixture+[v*z for v in mixture]+[cov,float(ws.columns[5].values[row]=='Day1')])
    return np.asarray(data)


class MixtureProcessModelTests(unittest.TestCase):
    def test_known_tensor_coefficients_covariate_and_fixed_block(self):
        result=fitted();expected=[10,20,30,4,-2,3,2,-3,4,5,1,-2,1.75,2.5]
        np.testing.assert_allclose([c['estimate'] for c in result['coefficients']],expected,atol=2e-12)
        self.assertEqual(result['block_reference'],'Day2');self.assertEqual(result['df_error'],72-14)
        self.assertNotIn('mixture_fit',result);self.assertEqual(result['mixture_process_fit']['schema'],'statcraft-mixture-process-fit-v1')
        self.assertEqual(result['options']['process_coding'],[{'low':80.,'high':120.}]);json.dumps(result,allow_nan=False)

    def test_fitted_sse_covariance_and_anova_match_independent_numpy_ols(self):
        ws=fixture();x=manual_matrix(ws);y=np.asarray(ws.columns[6].values);beta=np.linalg.lstsq(x,y,rcond=None)[0];residual=y-x@beta;sse=float(residual@residual);mse=sse/(len(y)-x.shape[1]);cov=mse*np.linalg.inv(x.T@x)
        result=fitted(ws)
        np.testing.assert_allclose(result['fitted'],x@beta,atol=2e-12)
        self.assertAlmostEqual(result['ss_error'],sse,places=12);self.assertAlmostEqual(result['ms_error'],mse,places=14)
        np.testing.assert_allclose(result['mixture_process_fit']['covariance'],cov,rtol=2e-11,atol=1e-14)
        total=float(np.sum((y-y.mean())**2));f=((total-sse)/(x.shape[1]-1))/mse
        self.assertAlmostEqual(result['f']/f,1.,places=10);self.assertAlmostEqual(result['p_value'],stats.f.sf(f,x.shape[1]-1,len(y)-x.shape[1]))
        self.assertAlmostEqual(sum(result['leverage']),x.shape[1])

    def test_prediction_fit_se_and_intervals_match_manual_matrix(self):
        result=fitted();point=[.2,.3,.5];z=.5;cov=.2;vector=np.asarray(point+[.06,.1,.15]+[v*z for v in point+[.06,.1,.15]]+[cov,1.])
        expected=float(vector@np.asarray([c['estimate'] for c in result['coefficients']]))
        p=predict(result,[point],[[110.]],[[41.]],['Day1'],.9);row=p['rows'][0]
        variance=float(vector@np.asarray(result['mixture_process_fit']['covariance'])@vector);critical=stats.t.isf(.05,result['df_error'])
        self.assertAlmostEqual(row['fit'],expected,places=12);self.assertAlmostEqual(row['standard_error'],math.sqrt(variance))
        self.assertAlmostEqual(row['ci_low'],expected-critical*math.sqrt(variance));self.assertAlmostEqual(row['prediction_high'],expected+critical*math.sqrt(variance+result['ms_error']))
        self.assertLess(row['prediction_low'],row['ci_low']);self.assertGreater(row['prediction_high'],row['ci_high'])
        self.assertIn('Prediction',text_report(p));self.assertIn('Reference block level: Day2',text_report(result))

    def test_amount_unit_scaling_does_not_change_model_or_prediction(self):
        one=fitted();hundred=fitted(fixture(100.),total=100.)
        np.testing.assert_allclose(one['fitted'],hundred['fitted'],atol=1e-12)
        a=predict(one,[[.2,.3,.5]],[[100.]],[[40.]],['Day2'])['rows'][0]
        b=predict(hundred,[[20.,30.,50.]],[[100.]],[[40.]],['Day2'])['rows'][0]
        self.assertAlmostEqual(a['fit'],b['fit']);self.assertAlmostEqual(a['standard_error'],b['standard_error'])

    def test_joint_missing_rows_keep_original_identity(self):
        ws=fixture();ws.columns[3].values[0]=None;ws.columns[4].values[3]=None;ws.columns[5].values[7]=None;ws.columns[6].values[10]=None
        result=fitted(ws)
        self.assertEqual(result['missing_rows'],[1,4,8,11]);self.assertEqual(result['count'],68);self.assertEqual(result['row_indices'][:3],[1,2,4]);self.assertEqual(result['used_rows'][0],2)

    def test_exact_replicates_define_pure_error_and_all_role_grouping(self):
        result=fitted();pure=next(r for r in result['anova'] if r['source']=='Pure error');lack=next(r for r in result['anova'] if r['source']=='Lack-of-fit')
        self.assertEqual(pure['df'],36);self.assertEqual(lack['df'],36-14)
        self.assertAlmostEqual(pure['ss'],72*.02**2,places=12);self.assertAlmostEqual(lack['ss'],0.,places=11)

    def test_exact_fit_has_no_fabricated_inference(self):
        result=fitted(fixture(noise=0.));self.assertEqual(result['status'],'exact_fit');self.assertIsNone(result['f'])
        self.assertTrue(all(row['p_value'] is None for row in result['coefficients']))
        row=predict(result,[[.2,.3,.5]],[[100.]],[[40.]],['Day2'])['rows'][0]
        self.assertIsNone(row['ci_low']);self.assertIsNone(row['standard_error'])

    def test_order_two_process_terms_recover_known_curvature(self):
        ws=fixture();base=[(ws.columns[3].values[row]-100)/20 for row in range(ws.row_count)]
        for row,z in enumerate(base):
            a,b,c=[ws.columns[i].values[row] for i in (0,1,2)]
            ws.columns[6].values[row]+=z*z*(3*a+5*b-2*c+6*a*b+2*a*c-4*b*c)
        result=fit(ws,6,[0,1,2],[3],5,[4],options={'process_order':2,'process_coding':[{'low':80.,'high':120.}],'covariate_coding':[{'low':35.,'high':45.}]})
        self.assertEqual(len(result['coefficients']),20)
        np.testing.assert_allclose([c['estimate'] for c in result['coefficients'][12:18]],[3,5,-2,6,2,-4],atol=2e-12)

    def test_two_process_interactions_are_crossed_with_components(self):
        rng=np.random.default_rng(44);rows=[]
        for a in (0.,.5,1.):
            for z1 in (-1.,0.,1.):
                for z2 in (-1.,0.,1.):
                    for rep in (-1.,1.):rows.append([a,1-a,z1,z2,10*a+20*(1-a)+2*a*z1+3*(1-a)*z2+4*a*z1*z2+5*(1-a)*z1*z2+.01*rep])
        ws=Worksheet('Two processes',[Column(n,values=[r[i] for r in rows]) for i,n in enumerate(('A','B','P1','P2','Y'))])
        result=fit(ws,4,[0,1],[2,3],model='linear',options={'process_order':2})
        terms={r['name']:r['estimate'] for r in result['coefficients']};self.assertAlmostEqual(terms['A*P1*P2'],4.);self.assertAlmostEqual(terms['B*P1*P2'],5.)

    def test_block_only_and_covariate_only_models_work(self):
        ws=fixture()
        block=fit(ws,6,[0,1,2],block_index=5,model='linear');self.assertEqual(len(block['coefficients']),4)
        cov=fit(ws,6,[0,1,2],covariate_indices=[4],model='linear');self.assertEqual(len(cov['coefficients']),4)
        self.assertEqual(predict(cov,[[.2,.3,.5]],covariate_rows=[[40.]])['rows'][0]['block'],None)

    def test_aliases_constant_variables_and_insufficient_df_are_rejected(self):
        ws=fixture();ws.columns[4].values=list(ws.columns[3].values)
        with self.assertRaisesRegex(ValueError,'rank deficient|confounded'):fitted(ws)
        ws=fixture();ws.columns[3].values=[100.]*ws.row_count
        with self.assertRaisesRegex(ValueError,'coding range|rank deficient'):fit(ws,6,[0,1,2],[3])
        ws=fixture();ws.columns=[Column(c.name,c.kind,c.values[:8]) for c in ws.columns]
        with self.assertRaisesRegex(ValueError,'terms|block'):fitted(ws)

    def test_distinct_roles_missing_all_rows_and_no_additional_roles(self):
        ws=fixture()
        with self.assertRaisesRegex(ValueError,'separate'):fit(ws,6,[0,1,2],[2])
        with self.assertRaisesRegex(ValueError,'Select a process'):fit(ws,6,[0,1,2])
        ws.columns[3].values=[None]*ws.row_count
        with self.assertRaisesRegex(ValueError,'No complete'):fit(ws,6,[0,1,2],[3])

    def test_prediction_requires_every_role_and_known_blocks(self):
        result=fitted()
        for args in ({},{'process_rows':[[100.]],'covariate_rows':[[40.]]},{'process_rows':[[100.]],'covariate_rows':[[40.]],'block_values':['NewDay']}):
            with self.assertRaises(ValueError):predict(result,[[.2,.3,.5]],**args)
        with self.assertRaisesRegex(ValueError,'sum'):predict(result,[[.2,.3,.4]],[[100.]],[[40.]],['Day1'])
        with self.assertRaises(ValueError):predict(result,[[.2,.3,.5]],[[float('nan')]],[[40.]],['Day1'])

    def test_extrapolation_is_explicit_and_training_coding_does_not_trim_data(self):
        result=fitted();p=predict(result,[[.2,.3,.5]],[[130.]],[[50.]],['Day1'])
        self.assertTrue(any('extrapolation' in warning for warning in p['warnings']))
        ws=fixture();r=fit(ws,6,[0,1,2],[3],5,[4],options={'process_coding':[{'low':90.,'high':110.}]})
        self.assertEqual(r['count'],72);self.assertEqual(r['process_coding'],[{'low':90.,'high':110.}])

    def test_invalid_options_coding_and_block_limits_rejected(self):
        ws=fixture()
        for opts in ({'process_order':True},{'process_order':3},{'process_coding':[]},{'covariate_coding':[{'low':1,'high':1}]},{'extra':True}):
            with self.assertRaises(ValueError):fit(ws,6,[0,1,2],[3],5,[4],options=opts)
        ws.columns[5].values=['Single']*ws.row_count
        with self.assertRaisesRegex(ValueError,'2 to 16'):fit(ws,6,[0,1,2],block_index=5)

    def test_caller_inputs_not_mutated_and_constant_response_safe(self):
        ws=fixture();opts={'process_coding':[{'low':80.,'high':120.}]};before=copy.deepcopy((ws,opts))
        r=fit(ws,6,[0,1,2],[3],options=opts);self.assertEqual(opts,before[1]);self.assertEqual(ws.columns[6].values,before[0].columns[6].values)
        ws.columns[6].values=[15.]*ws.row_count;r=fit(ws,6,[0,1,2],[3]);self.assertIsNone(r['r_squared']);self.assertEqual(r['status'],'exact_fit')

    def test_huge_constant_offset_stays_finite_and_unsupported_sums_reject_cleanly(self):
        ws=fixture();ws.columns[6].values=[1e308]*ws.row_count
        result=fit(ws,6,[0,1,2],[3],model='linear')
        self.assertEqual(result['status'],'exact_fit');self.assertTrue(all(math.isfinite(v) for v in result['fitted']))
        prediction=predict(result,[[.2,.3,.5]],[[100.]])['rows'][0]
        self.assertEqual(prediction['fit'],1e308)
        ws=fixture();ws.columns[6].values=[value*1e160 for value in ws.columns[6].values]
        with self.assertRaisesRegex(ValueError,'finite|arithmetic'):fit(ws,6,[0,1,2],[3])

    def test_block_value_order_changes_reference_without_changing_fitted_values(self):
        ws=fixture();first=fitted(ws)
        ws.columns[5].metadata['value_order']={'mode':'custom','values':['Day2','Day1']}
        second=fitted(ws)
        self.assertEqual(second['block_reference'],'Day1')
        np.testing.assert_allclose(first['fitted'],second['fitted'],atol=2e-12)
        for label in ('Day1','Day2'):
            one=predict(first,[[.2,.3,.5]],[[100.]],[[40.]],[label])['rows'][0]['fit']
            two=predict(second,[[.2,.3,.5]],[[100.]],[[40.]],[label])['rows'][0]['fit']
            self.assertAlmostEqual(one,two,places=12)
