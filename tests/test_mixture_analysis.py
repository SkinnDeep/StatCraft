"""Analytic Scheffe polynomial, constrained fit and prediction regressions."""
import copy
import json
import math
import unittest
from itertools import combinations
import numpy as np
from scipy import stats

from statcraft.model import Column,Worksheet
from statcraft.mixture_analysis import fit,predict
from statcraft.mixture_report import format_mixture_report,sections


def blends():
    return [(a/4,b/4,(4-a-b)/4) for a in range(5) for b in range(5-a)]


def polynomial(point,special=True):
    a,b,c=point
    return 10*a+20*b+30*c+4*a*b-6*a*c+8*b*c+(12*a*b*c if special else 0)


def worksheet(points=None,noise=True,total=1.,special=True):
    points=blends() if points is None else points
    rows=[];ys=[]
    for point in points:
        for delta in (-.1,.1) if noise else (0.,):
            rows.append(tuple(value*total for value in point));ys.append(polynomial(point,special)+delta)
    return Worksheet('Blend',[Column('A',values=[row[0] for row in rows]),Column('B',values=[row[1] for row in rows]),
        Column('C',values=[row[2] for row in rows]),Column('Strength',values=ys)])


class MixtureAnalysisTests(unittest.TestCase):
    def test_known_special_cubic_coefficients_and_independent_covariance(self):
        sheet=worksheet()
        r=fit(sheet,3,[0,1,2],model='special_cubic')
        expected=[10,20,30,4,-6,8,12]
        np.testing.assert_allclose([row['estimate'] for row in r['coefficients']],expected,atol=1e-10)
        self.assertNotIn('Constant',[row['name'] for row in r['coefficients']])
        x=np.array(list(zip(*(column.values for column in sheet.columns[:3]))))
        design=np.column_stack([x[:,0],x[:,1],x[:,2],x[:,0]*x[:,1],x[:,0]*x[:,2],x[:,1]*x[:,2],np.prod(x,axis=1)])
        y=np.array(sheet.columns[3].values)
        beta=np.linalg.lstsq(design,y,rcond=None)[0]
        residual=y-design@beta
        mse=float(residual@residual)/(len(y)-7)
        covariance=mse*np.linalg.inv(design.T@design)
        np.testing.assert_allclose(r['mixture_fit']['covariance'],covariance,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(r['fitted'],design@beta,atol=1e-10)
        self.assertEqual(r['df_regression'],6)
        self.assertEqual(r['df_error'],23)
        self.assertEqual(r['df_total'],29)
        for row,variance in zip(r['coefficients'],np.diag(covariance)):
            self.assertAlmostEqual(row['standard_error'],math.sqrt(variance))
            self.assertAlmostEqual(row['p_value'],2*stats.t.sf(abs(row['estimate']/row['standard_error']),23))

    def test_normalized_total_100_and_total_1_invariant(self):
        a=fit(worksheet(total=1),3,[0,1,2],model='special_cubic',total=1)
        b=fit(worksheet(total=100),3,[0,1,2],model='special_cubic',total=100)
        np.testing.assert_allclose(a['fitted'],b['fitted'],atol=1e-12)
        np.testing.assert_allclose([row['estimate'] for row in a['coefficients']],[row['estimate'] for row in b['coefficients']],atol=1e-11)
        self.assertAlmostEqual(a['ss_error'],b['ss_error'])

    def test_centered_anova_constant_null_and_ordinary_nointercept_distinction(self):
        sheet=worksheet(special=False)
        r=fit(sheet,3,[0,1,2],model='quadratic')
        y=sheet.columns[3].values
        centered=sum((value-sum(y)/len(y))**2 for value in y)
        self.assertAlmostEqual(r['ss_total'],centered)
        self.assertAlmostEqual(r['ss_regression']+r['ss_error'],centered)
        self.assertEqual(r['df_regression'],5)
        expected=(r['ss_regression']/5)/(r['ss_error']/(len(y)-6))
        self.assertAlmostEqual(r['f'],expected)
        self.assertAlmostEqual(r['p_value'],stats.f.sf(expected,5,len(y)-6))
        self.assertNotAlmostEqual(r['ss_total'],sum(value*value for value in y))

    def test_pure_error_and_lack_of_fit_are_actual_replication(self):
        sheet=worksheet()
        r=fit(sheet,3,[0,1,2],model='linear')
        anova={row['source']:row for row in r['anova']}
        pe=anova['Pure error'];lof=anova['Lack-of-fit']
        self.assertEqual(pe['df'],15)
        self.assertEqual(lof['df'],12)
        self.assertAlmostEqual(pe['ss'],.3)
        self.assertAlmostEqual(pe['ss']+lof['ss'],r['ss_error'])
        self.assertAlmostEqual(lof['f'],(lof['ss']/12)/(.3/15))
        self.assertLess(lof['p_value'],.05)

    def test_exact_fit_never_fabricates_pvalues_or_intervals(self):
        r=fit(worksheet(noise=False),3,[0,1,2],model='special_cubic')
        self.assertEqual(r['status'],'exact_fit')
        self.assertEqual(r['ss_error'],0)
        self.assertIsNone(r['f']);self.assertIsNone(r['p_value'])
        for row in r['coefficients']:
            self.assertEqual(row['standard_error'],0)
            self.assertIsNone(row['t']);self.assertIsNone(row['p_value']);self.assertIsNone(row['ci_low'])
        prediction=predict(r,[[.2,.3,.5]])
        self.assertAlmostEqual(prediction['rows'][0]['fit'],polynomial([.2,.3,.5]))
        self.assertIsNone(prediction['rows'][0]['ci_low'])
        json.dumps(r,allow_nan=False)

    def test_prediction_mean_and_individual_intervals(self):
        r=fit(worksheet(),3,[0,1,2],model='special_cubic')
        points=[[.2,.3,.5],[0,1,0]]
        prediction=predict(r,points)
        covariance=np.asarray(r['mixture_fit']['covariance'])
        for point,row in zip(points,prediction['rows']):
            a,b,c=point;vector=np.array([a,b,c,a*b,a*c,b*c,a*b*c])
            expected_se=math.sqrt(float(vector@covariance@vector))
            self.assertAlmostEqual(row['fit'],polynomial(point))
            self.assertAlmostEqual(row['standard_error'],expected_se)
            half=stats.t.isf(.025,r['df_error'])*expected_se
            self.assertAlmostEqual(row['ci_low'],row['fit']-half)
            self.assertGreater(row['prediction_high']-row['prediction_low'],row['ci_high']-row['ci_low'])
        wider=predict(r,[points[0]],confidence=.99)['rows'][0]
        self.assertGreater(wider['ci_high'],prediction['rows'][0]['ci_high'])

    def test_missing_rows_are_aligned_and_keep_original_numbers(self):
        sheet=worksheet()
        sheet.columns[0].values[1]=None
        sheet.columns[3].values[4]=None
        r=fit(sheet,3,[0,1,2],model='quadratic')
        self.assertEqual(r['missing_rows'],[2,5])
        self.assertEqual(r['count'],28)
        self.assertNotIn(2,r['used_rows']);self.assertNotIn(5,r['used_rows'])
        self.assertEqual(r['row_indices'],[row-1 for row in r['used_rows']])

    def test_fixed_sum_nonnegative_and_column_validation(self):
        for update in ({'response_index':True},{'component_indices':[0,0,1]}, {'component_indices':[0,1,3]},
                       {'component_indices':[0]},{'total':0},{'total':True},{'options':{'confidence':95}},
                       {'options':{'show_graphs':1}},{'options':{'other':1}}):
            kwargs={'response_index':3,'component_indices':[0,1,2]};kwargs.update(update)
            with self.subTest(update=update),self.assertRaises(ValueError):fit(worksheet(),**kwargs)
        for value in (-.1,2):
            sheet=worksheet();sheet.columns[0].values[0]=value
            with self.assertRaises(ValueError):fit(sheet,3,[0,1,2])
        sheet=worksheet();sheet.columns[0].kind='text';sheet.columns[0].values=list(map(str,sheet.columns[0].values))
        with self.assertRaises(ValueError):fit(sheet,3,[0,1,2])

    def test_rank_deficient_and_saturated_fail_before_inference(self):
        sheet=worksheet(points=[(x,1-x,0) for x in (0,.25,.5,.75,1)])
        with self.assertRaisesRegex(ValueError,'rank deficient'):fit(sheet,3,[0,1,2],model='quadratic')
        sheet=worksheet(points=[(1,0,0),(0,1,0),(0,0,1)],noise=False)
        with self.assertRaisesRegex(ValueError,'more than 3'):fit(sheet,3,[0,1,2],model='linear')

    def test_bounds_from_active_metadata_and_prediction_constraints(self):
        points=[(.1,.2,.7),(.2,.2,.6),(.1,.4,.5),(.3,.2,.5),(.2,.4,.4),(.3,.3,.4)]
        sheet=worksheet(points=points)
        sheet.metadata={'doe':{'schema':'statcraft-special-design-v1','kind':'extreme_vertices','options':{'total':1.},
            'factors':[{'name':name,'kind':'number','low':.1,'high':.8,'column_index':i} for i,name in enumerate(('A','B','C'))]}}
        r=fit(sheet,3,[0,1,2],model='linear')
        self.assertEqual(r['bounds_source'],'worksheet_design')
        with self.assertRaisesRegex(ValueError,'bounds'):predict(r,[[0,.5,.5]])
        self.assertEqual(len(predict(r,[[.2,.3,.5]])['rows']),1)
        sheet.metadata['doe']['factors'][0]['column_index']=9
        fallback=fit(sheet,3,[0,1,2],model='linear')
        self.assertEqual(fallback['bounds_source'],'simplex')
        self.assertEqual(fallback['component_bounds'][0],{'low':0.,'high':1.})
        self.assertTrue(any('could not be matched' in warning for warning in fallback['warnings']))

    def test_constant_response_has_no_false_model_significance(self):
        sheet=worksheet();sheet.columns[3].values=[7.]*sheet.row_count
        r=fit(sheet,3,[0,1,2],model='quadratic')
        self.assertIsNone(r['r_squared']);self.assertIsNone(r['p_value'])
        self.assertEqual(r['residual_stdev'],0)
        np.testing.assert_allclose([row['estimate'] for row in r['coefficients'][:3]],[7,7,7])

    def test_large_constant_offset_does_not_overflow_group_mean(self):
        sheet=worksheet();sheet.columns[3].values=[1e308]*sheet.row_count
        r=fit(sheet,3,[0,1,2],model='linear')
        self.assertEqual(r['ss_error'],0)
        self.assertIsNone(r['p_value'])
        json.dumps(r,allow_nan=False)

    def test_prediction_invalid_mixtures_and_explicit_bounds(self):
        r=fit(worksheet(),3,[0,1,2],model='linear')
        for points in ([[-.1,.6,.5]],[[.1,.2,.3]],[[.1,.2]],[[True,0,0]],[[float('nan'),0,0]],[]):
            with self.subTest(points=points),self.assertRaises(ValueError):predict(r,points)
        with self.assertRaises(ValueError):
            fit(worksheet(),3,[0,1,2],options={'bounds':[{'low':.5,'high':1.}]*3})
        with self.assertRaises(ValueError):
            predict(r,[[.2,.3,.5]],confidence=95)

    def test_options_report_and_source_data_are_independent(self):
        sheet=worksheet();before=copy.deepcopy(sheet)
        options={'show_graphs':False,'title':'Blend strength'};saved=copy.deepcopy(options)
        r=fit(sheet,3,[0,1,2],options=options)
        self.assertEqual(sheet,before);self.assertEqual(options,saved)
        self.assertFalse(r['plot_residuals']);self.assertEqual(r['title'],'Blend strength')
        report=format_mixture_report(r)
        self.assertIn('No independent intercept',report)
        self.assertIn('Pure error',report)
        self.assertNotIn('centered_coefficient_values',report)
        self.assertEqual(len(list(sections(r))),3)


if __name__=='__main__':unittest.main()
