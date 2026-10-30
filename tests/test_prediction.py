"""Independent closed-form and QR checks of current-worksheet predictions."""
import copy
import itertools
import json
import unittest
import numpy as np
from scipy import stats
from statcraft.model import Column, Worksheet
from statcraft.prediction import predict, settings, model_spec, normalize_recipe
from statcraft.glm import settings as glm_settings, fit as glm_fit
from statcraft.response_surface import fit as rsm_fit, full_terms


class PredictionTests(unittest.TestCase):
    def simple(self, offset=0.):
        x=[offset+v for v in range(8)]; y=[2+3*v+e for v,e in enumerate([1,-1,1,-1,-1,1,-1,1])]
        return Worksheet('test',[Column('Weight',values=x),Column('Yield',values=y)]),dict(action='multiple_regression',parameters=dict(response_index=1,predictor_indices=[0],confidence=.95))

    def test_closed_form_fit_and_intervals(self):
        sheet,recipe=self.simple(); row=predict(sheet,recipe,values=[[3.5]])['rows'][0]
        x=np.arange(8); y=np.array(sheet.columns[1].values); b=np.sum((x-x.mean())*(y-y.mean()))/np.sum((x-x.mean())**2)
        expected=y.mean()+b*(3.5-x.mean()); s=np.sqrt(np.sum((y-y.mean()-b*(x-x.mean()))**2)/6)
        self.assertAlmostEqual(row['fit'],expected);self.assertAlmostEqual(row['se_fit'],s/np.sqrt(8))
        q=stats.t.ppf(.975,6)
        self.assertAlmostEqual(row['ci_low'],expected-q*s/np.sqrt(8));self.assertAlmostEqual(row['pi_high'],expected+q*s*np.sqrt(1+1/8))

    def test_independent_qr_leverage_multiple_predictors(self):
        rng=np.random.default_rng(251);x=rng.normal(size=(35,3));y=4+x@np.array([2,-1,3])+rng.normal(size=35)
        sheet=Worksheet('qr',[Column('Y',values=y.tolist())]+[Column('X'+str(j),values=x[:,j].tolist()) for j in range(3)])
        recipe=dict(action='multiple_regression',parameters=dict(response_index=0,predictor_indices=[1,2,3],confidence=.95))
        new=np.array([.2,-.3,1.]);design=np.column_stack([np.ones(35),x]);q,r=np.linalg.qr(design);beta=np.linalg.solve(r,q.T@y)
        h=np.linalg.norm(np.linalg.solve(r.T,np.r_[1,new]))**2;s=np.linalg.norm(y-design@beta)/np.sqrt(31)
        result=predict(sheet,recipe,values=[new.tolist()]);row=result['rows'][0]
        self.assertAlmostEqual(row['fit'],np.r_[1,new]@beta);self.assertAlmostEqual(row['se_fit'],s*np.sqrt(h))

    def test_large_offset_centered_prediction(self):
        a,r=self.simple();b,_=self.simple(1e12)
        self.assertAlmostEqual(predict(a,r,values=[[2.5]])['rows'][0]['fit'],predict(b,r,values=[[1e12+2.5]])['rows'][0]['fit'],places=10)

    def test_training_fitted_values_reconstruction(self):
        from statcraft.regression import multiple_regression
        sheet,recipe=self.simple();expected=multiple_regression([sheet.columns[0].values],sheet.columns[1].values)['fitted']
        actual=predict(sheet,recipe,values=[[x] for x in sheet.columns[0].values])['rows']
        np.testing.assert_allclose([r['fit'] for r in actual],expected,rtol=0,atol=1e-12)

    def glm(self,coding='effect',standardize='none'):
        rows=list(itertools.product(['A','B','C'],range(5),range(2)))
        y=[5+['A','B','C'].index(f)*2+(.5+['A','B','C'].index(f))*x+(-.2 if rep else .2) for f,x,rep in rows]
        sheet=Worksheet('glm',[Column('Response',values=y),Column('Material',kind='text',values=[r[0] for r in rows]),Column('Time',values=[r[1] for r in rows])])
        opts=glm_settings();opts.update(coding=coding,standardize=standardize)
        recipe=dict(action='general_linear_model',parameters=dict(response_index=0,factor_indices=[1],covariate_indices=[2],terms=[[0],[1],[0,1]],options=opts))
        return sheet,recipe

    def test_glm_all_codings_and_standardizations(self):
        expected=None
        for coding in ('effect','reference'):
            for mode in ('none','center','scale','standardize'):
                sheet,recipe=self.glm(coding,mode);result=predict(sheet,recipe,values=[['A',2],['B',1],['C',3]])
                rows=result['rows']
                np.testing.assert_allclose([r['fit'] for r in rows],[6,8.5,16.5],atol=1e-12)
                uncertainty=[r['se_fit'] for r in rows]
                if expected is None:expected=uncertainty
                np.testing.assert_allclose(uncertainty,expected,atol=1e-12)

    def test_glm_predict_reconstructs_training_fits(self):
        sheet,recipe=self.glm();fit=glm_fit(sheet,**recipe['parameters']);actual=predict(sheet,recipe,values=[[sheet.columns[1].values[r],sheet.columns[2].values[r]] for r in fit['row_indices']])
        np.testing.assert_allclose([r['fit'] for r in actual['rows']],fit['fitted'],atol=1e-12)

    def test_model_spec_named_levels(self):
        sheet,recipe=self.glm();spec=model_spec(sheet,recipe)
        self.assertEqual(spec['predictor_names'],['Material','Time']);self.assertEqual(spec['predictors'][0]['levels'],['A','B','C'])
        self.assertEqual(spec['predictors'][0]['role'],'factor');self.assertEqual(spec['predictors'][1]['kind'],'number')

    def test_unknown_factor_levels_rejected_including_missing_row(self):
        sheet,recipe=self.glm()
        for row in (['D',1],['D',None]):
            with self.assertRaisesRegex(ValueError,'Unknown factor level'):predict(sheet,recipe,values=[row])

    def test_numeric_factor_and_column_type_check(self):
        sheet,recipe=self.glm();sheet.columns[1]=Column('Material',values=[['A','B','C'].index(v) for v in sheet.columns[1].values])
        self.assertIsNotNone(predict(sheet,recipe,values=[[1,2]])['rows'][0]['fit'])
        sheet.columns.append(Column('text',kind='text',values=['1']))
        with self.assertRaisesRegex(ValueError,'types'):predict(sheet,recipe,input_mode='columns',new_indices=[3,2])

    def test_rsm_known_polynomial_and_fits(self):
        rows=list(itertools.product([-1.,0.,1.],repeat=2))*2
        y=[10+2*a-3*b+4*a*a+2*b*b+a*b+(.1 if i<9 else -.1) for i,(a,b) in enumerate(rows)]
        sheet=Worksheet('rsm',[Column('Y',values=y),Column('Temp',values=[10+2*a for a,b in rows]),Column('Pressure',values=[100+10*b for a,b in rows])])
        recipe=dict(action='analyze_response_surface',parameters=dict(response_index=0,factor_indices=[1,2],coding=[dict(low=8,high=12),dict(low=90,high=110)],terms=full_terms(2),options=glm_settings()))
        actual=predict(sheet,recipe,values=[[11,95]])['rows'][0]
        self.assertAlmostEqual(actual['fit'],10+1+1.5+1+.5-.25)
        fit=rsm_fit(sheet,**recipe['parameters']);prediction=predict(sheet,recipe,input_mode='columns',new_indices=[1,2])
        np.testing.assert_allclose([r['fit'] for r in prediction['rows']],fit['fitted'],atol=1e-12)

    def test_missing_new_rows_preserve_original_position(self):
        sheet,recipe=self.simple();result=predict(sheet,recipe,values=[[1],[None],[3]])
        self.assertEqual(result['used'],2);self.assertEqual(result['missing'],1);self.assertEqual(result['rows'][1]['row'],2)
        self.assertEqual(result['rows'][1]['status'],'missing');self.assertIsNone(result['rows'][1]['fit'])

    def test_unequal_length_columns_align_and_missing_training(self):
        sheet,recipe=self.glm();sheet.columns[0].values[2]=None;sheet.columns += [Column('New material',kind='text',values=['A','B','C']),Column('New time',values=[1,2])]
        result=predict(sheet,recipe,input_mode='columns',new_indices=[3,4]);self.assertEqual(result['missing'],1);self.assertEqual(result['rows'][2]['row'],3)
        self.assertIsNone(result['rows'][2]['fit'])

    def test_extrapolation_range_flag(self):
        sheet,recipe=self.simple();result=predict(sheet,recipe,values=[[-1],[0],[7],[8]])
        self.assertEqual([r['extrapolated'] for r in result['rows']],[True,False,False,True]);self.assertTrue(result['warnings'])

    def test_exact_fit_omits_uncertainty(self):
        sheet,recipe=self.simple();sheet.columns[1].values=[2+3*x for x in range(8)]
        result=predict(sheet,recipe,values=[[4]]);row=result['rows'][0]
        self.assertEqual(row['status'],'exact_fit');self.assertAlmostEqual(row['fit'],14)
        for key in ('se_fit','ci_low','ci_high','pi_low','pi_high'):self.assertIsNone(row[key])
        self.assertTrue(result['warnings'])

    def test_bounds_critical_value_and_unused_endpoint(self):
        sheet,recipe=self.simple();base=predict(sheet,recipe,values=[[3]])['rows'][0]
        for side in ('lower','upper'):
            o=settings();o['side']=side;row=predict(sheet,recipe,values=[[3]],options=o)['rows'][0]
            if side=='lower':
                self.assertIsNone(row['ci_high']);self.assertIsNone(row['pi_high']);self.assertGreater(row['ci_low'],base['ci_low'])
                self.assertAlmostEqual(row['ci_low'],row['fit']-stats.t.ppf(.95,6)*row['se_fit'])
            else:self.assertIsNone(row['ci_low']);self.assertIsNone(row['pi_low']);self.assertLess(row['ci_high'],base['ci_high'])

    def test_interval_display_modes(self):
        sheet,recipe=self.simple()
        for mode in ('both','confidence','prediction','none'):
            o=settings();o['intervals']=mode;row=predict(sheet,recipe,values=[[3]],options=o)['rows'][0]
            self.assertEqual(row['ci_low'] is not None,mode in ('both','confidence'));self.assertEqual(row['pi_low'] is not None,mode in ('both','prediction'))
            self.assertIsNotNone(row['se_fit'])

    def test_confidence_width(self):
        sheet,recipe=self.simple();a=settings();a['confidence']=.8;b=settings();b['confidence']=.99
        low=predict(sheet,recipe,values=[[3]],options=a)['rows'][0];high=predict(sheet,recipe,values=[[3]],options=b)['rows'][0]
        self.assertLess(low['ci_high'],high['ci_high'])

    def test_no_state_mutation_and_json_finite(self):
        sheet,recipe=self.simple();snapshot=copy.deepcopy(sheet);rcopy=copy.deepcopy(recipe)
        result=predict(sheet,recipe,values=[[1],[None]]);json.dumps(result,allow_nan=False)
        self.assertEqual(sheet,snapshot);self.assertEqual(recipe,rcopy)

    def test_refits_current_values(self):
        sheet,recipe=self.simple();first=predict(sheet,recipe,values=[[2]])['rows'][0]['fit'];sheet.columns[1].values=[v+8 for v in sheet.columns[1].values]
        self.assertAlmostEqual(predict(sheet,recipe,values=[[2]])['rows'][0]['fit'],first+8)

    def test_settings_validation(self):
        for key,value in [('confidence',True),('confidence',float('nan')),('confidence',0),('intervals','x'),('side','x'),('show_table',1),('show_equation',None)]:
            o=settings();o[key]=value
            with self.assertRaises(ValueError):settings(o)
        for value in ([],{},dict(settings(),extra=True)):
            with self.assertRaises(ValueError):settings(value)

    def test_bad_values_and_column_selection(self):
        sheet,recipe=self.simple()
        for values in ([],[[1,2]],[1],[[True]],[['3']],[[float('inf')]],[[float('nan')]]):
            with self.assertRaises((ValueError,TypeError)):predict(sheet,recipe,values=values)
        for indices in ([],[True],[-1],[99]):
            with self.assertRaises(ValueError):predict(sheet,recipe,input_mode='columns',new_indices=indices)
        with self.assertRaises(ValueError):predict(sheet,recipe,input_mode='invalid',values=[[1]])
        with self.assertRaises(ValueError):predict(sheet,recipe,values=[[1]],new_indices=[0])

    def test_input_and_source_limits(self):
        sheet,recipe=self.simple()
        with self.assertRaisesRegex(ValueError,'20,000'):predict(sheet,recipe,values=[[1]]*20001)
        sheet.columns[0].values=[1]*20001
        with self.assertRaisesRegex(ValueError,'20,000'):model_spec(sheet,recipe)

    def test_invalid_recipe_and_recursion(self):
        sheet,recipe=self.simple()
        for invalid in (None,{},dict(action='predict_model',parameters={}),dict(action='describe_column',parameters=dict(index=0))):
            with self.assertRaises(ValueError):predict(sheet,invalid,values=[[1]])
        invalid=copy.deepcopy(recipe);invalid['parameters']['predictor_indices']=[99]
        with self.assertRaises(ValueError):predict(sheet,invalid,values=[[1]])
        invalid=copy.deepcopy(recipe);invalid['parameters']['predictor_indices']=[1]
        with self.assertRaises(ValueError):predict(sheet,invalid,values=[[1]])

    def test_extreme_extrapolation_fails_helpfully(self):
        sheet,recipe=self.simple()
        with self.assertRaisesRegex(ValueError,'finite numeric range'):predict(sheet,recipe,values=[[1e308]])

    def test_factor_only_group_mean_uncertainty_closed_form(self):
        # Unequal group sizes ensure leverage comes from the selected group,
        # rather than the overall sample size or coefficient standard errors.
        groups=['A']*3+['B']*5+['C']*4
        y=[1,2,3,4,5,6,7,8,8,9,10,11]
        sheet=Worksheet('groups',[Column('Y',values=y),Column('Group',kind='text',values=groups)])
        p=dict(response_index=0,factor_indices=[1],covariate_indices=[],terms=[[0]],options=glm_settings())
        recipe=dict(action='general_linear_model',parameters=p)
        result=predict(sheet,recipe,values=[['A'],['B'],['C']])
        means=[2,6,9.5];sizes=[3,5,4]
        sse=sum((v-means[['A','B','C'].index(g)])**2 for g,v in zip(groups,y));s=(sse/9)**.5
        for row,mean,size in zip(result['rows'],means,sizes):
            self.assertAlmostEqual(row['fit'],mean);self.assertAlmostEqual(row['se_fit'],s/size**.5)

    def test_factor_level_seen_only_in_missing_response_is_unseen(self):
        sheet,recipe=self.glm();sheet.columns[0].values.append(None);sheet.columns[1].values.append('D');sheet.columns[2].values.append(2)
        self.assertEqual(model_spec(sheet,recipe)['predictors'][0]['levels'],['A','B','C'])
        with self.assertRaisesRegex(ValueError,'Unknown factor level'):predict(sheet,recipe,values=[['D',2]])

    def test_three_way_glm_interaction_training_reconstruction(self):
        rows=list(itertools.product(['A','B'],['C','D'],[-1.,0.,1.],[-1.,1.]))
        a=[1 if r[0]=='A' else -1 for r in rows];b=[1 if r[1]=='C' else -1 for r in rows]
        y=[3+aa+2*bb+.3*x+aa*bb+aa*x+bb*x+aa*bb*x+.1*e for (f,g,x,e),aa,bb in zip(rows,a,b)]
        sheet=Worksheet('threeway',[Column('Y',values=y),Column('A',kind='text',values=[r[0] for r in rows]),Column('B',kind='text',values=[r[1] for r in rows]),Column('X',values=[r[2] for r in rows])])
        terms=[[0],[1],[2],[0,1],[0,2],[1,2],[0,1,2]]
        recipe=dict(action='general_linear_model',parameters=dict(response_index=0,factor_indices=[1,2],covariate_indices=[3],terms=terms,options=glm_settings()))
        fitted=glm_fit(sheet,**recipe['parameters']);result=predict(sheet,recipe,input_mode='columns',new_indices=[1,2,3])
        np.testing.assert_allclose([r['fit'] for r in result['rows']],fitted['fitted'],atol=1e-12)

    def test_empty_new_columns_rejected(self):
        sheet,recipe=self.simple();sheet.columns.append(Column('Empty'))
        with self.assertRaisesRegex(ValueError,'20,000'):predict(sheet,recipe,input_mode='columns',new_indices=[2])

    def test_legacy_simple_regression_recipe_equivalence(self):
        sheet,canonical=self.simple()
        legacy=dict(action='inference',parameters=dict(method='linear_regression',indices=[0,1],mu=137.,confidence=.95))
        self.assertEqual(normalize_recipe(legacy),canonical)
        self.assertEqual(model_spec(sheet,legacy),model_spec(sheet,canonical))
        self.assertEqual(predict(sheet,legacy,values=[[3],[None]]),predict(sheet,canonical,values=[[3],[None]]))

    def test_recipe_normalization_copies_and_preserves_confidence(self):
        _,canonical=self.simple();canonical['parameters']['confidence']=.88
        normalized=normalize_recipe(canonical);self.assertEqual(normalized,canonical)
        normalized['parameters']['predictor_indices'].append(9)
        self.assertEqual(canonical['parameters']['predictor_indices'],[0])
        legacy=dict(action='inference',parameters=dict(method='linear_regression',indices=[0,1],mu=0,confidence=.88))
        self.assertEqual(normalize_recipe(legacy)['parameters']['confidence'],.88)

    def test_recipe_normalization_rejects_nonmodels_and_malformed(self):
        for recipe in (dict(action='inference',parameters=dict(method='one_sample_t',indices=[0],mu=0,confidence=.95)),
                       dict(action='inference',parameters=dict(method='linear_regression',indices=[0,0],mu=0,confidence=.95)),
                       dict(action='inference',parameters=dict(method='linear_regression',indices=[0],mu=0,confidence=.95)),
                       dict(action='inference',parameters=dict(method='linear_regression',indices=[0,1],confidence=.95)),
                       dict(action='predict_model',parameters=dict(model_recipe={})),
                       dict(action='inference',parameters=dict(method='linear_regression',indices=[0,1],mu=None,confidence=.95))):
            with self.assertRaises(ValueError):normalize_recipe(recipe)


if __name__ == '__main__':unittest.main()
