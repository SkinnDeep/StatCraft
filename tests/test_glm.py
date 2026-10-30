import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
from scipy import stats
from statcraft.model import Worksheet,Column
from statcraft.glm import fit,settings,validate_terms,residual_panels
from statcraft.app import Presenter,format_entry
from statcraft.recipes import run,columns


def example():
    values=[];a=[];b=[]
    for first,second,sample in [('a','low',[1,3]),('a','high',[4,5,9]),('b','low',[6,7,8,11]),('b','high',[9,10,12,14,15])]:
        values+=sample;a += [first]*len(sample);b += [second]*len(sample)
    return Worksheet('Unbalanced',[Column('Strength',values=values),Column('Material','text',a),Column('Temperature','text',b)])


class GeneralLinearModelTests(unittest.TestCase):
    def test_one_factor_matches_scipy_anova(self):
        sheet=example();r=fit(sheet,0,[1],[])
        groups=[[v for v,a in zip(sheet.columns[0].values,sheet.columns[1].values) if a==level] for level in ['a','b']]
        expected=stats.f_oneway(*groups)
        self.assertAlmostEqual(r['anova_terms'][0]['f'],expected.statistic,10);self.assertAlmostEqual(r['anova_terms'][0]['p_value'],expected.pvalue,12)

    def test_unbalanced_full_two_factor_adjusted_tests_match_cell_mean_contrasts(self):
        s=example();r=fit(s,0,[1,2],[],[[0],[1],[0,1]])
        groups=[[v for v,a,b in zip(s.columns[0].values,s.columns[1].values,s.columns[2].values) if (a,b)==key] for key in [('a','high'),('a','low'),('b','high'),('b','low')]]
        means=[sum(g)/len(g) for g in groups];sse=sum(sum((v-sum(g)/len(g))**2 for v in g) for g in groups)
        expected=[(means[0]+means[1]-means[2]-means[3])/4,(means[0]-means[1]+means[2]-means[3])/4,(means[0]-means[1]-means[2]+means[3])/4]
        contrast_variance=sum(1/len(g) for g in groups)/16
        self.assertAlmostEqual(r['ss_error'],sse,10)
        for coefficient,term in zip(expected,r['anova_terms']):self.assertAlmostEqual(term['adj_ss'],coefficient**2/contrast_variance,9)

    def test_sequential_terms_order_changes_allocation_and_sums_to_model(self):
        a=fit(example(),0,[1,2],[],[[0],[1],[0,1]],dict(settings(),ss_type='sequential'))
        b=fit(example(),0,[1,2],[],[[1],[0],[0,1]],dict(settings(),ss_type='sequential'))
        self.assertNotAlmostEqual(a['anova_terms'][0]['seq_ss'],b['anova_terms'][1]['seq_ss'])
        for r in [a,b]:self.assertAlmostEqual(sum(t['seq_ss'] for t in r['anova_terms']),r['ss_regression'],9)

    def test_continuous_only_matches_scipy_linregress(self):
        s=Worksheet('Covariates',[Column('Y',values=[2,3,5,4,7,8]),Column('X',values=[1,2,3,4,5,6])]);r=fit(s,0,[],[1]);expected=stats.linregress(s.columns[1].values,s.columns[0].values)
        self.assertAlmostEqual(r['coefficients'][1]['estimate'],expected.slope,12);self.assertAlmostEqual(r['coefficients'][1]['p_value'],expected.pvalue,12)

    def test_factor_covariate_interaction_matches_separate_group_regressions(self):
        s=Worksheet('Slopes',[Column('Y',values=[2,3,4,4,6,6,8,9]),Column('Group','text',['a']*4+['b']*4),Column('X',values=[1,2,3,4]*2)])
        r=fit(s,0,[1],[2],[[0],[1],[0,1]])
        for start in [0,4]:
            line=stats.linregress(s.columns[2].values[start:start+4],s.columns[0].values[start:start+4])
            for i in range(start,start+4):self.assertAlmostEqual(r['fitted'][i],line.intercept+line.slope*s.columns[2].values[i],12)

    def test_coding_and_covariate_scaling_preserve_fits(self):
        s=example();s.columns.append(Column('Dose',values=list(range(s.row_count))))
        baseline=fit(s,0,[1,2],[3])
        for coding in ['effect','reference']:
            for scale in ['none','center','scale','standardize']:
                r=fit(s,0,[1,2],[3],options=dict(settings(),coding=coding,standardize=scale));np.testing.assert_allclose(r['fitted'],baseline['fitted'],atol=1e-10)

    def test_missing_complete_cases_keep_original_rows_and_levels(self):
        s=example();s.columns[0].values[1]=None;s.columns[1].values[3]=None;r=fit(s,0,[1,2],[])
        self.assertEqual(r['missing'],2);self.assertNotIn(1,r['row_indices']);self.assertNotIn(3,r['row_indices']);self.assertEqual(r['diagnostics'][1]['row'],3)

    def test_factor_coefficient_coding_does_not_change_adjusted_anova(self):
        a=fit(example(),0,[1,2],[],[[0],[1],[0,1]])
        b=fit(example(),0,[1,2],[],[[0],[1],[0,1]],dict(settings(),coding='reference'))
        np.testing.assert_allclose([t['adj_ss'] for t in a['anova_terms']],[t['adj_ss'] for t in b['anova_terms']],atol=1e-10)
        self.assertNotAlmostEqual(a['coefficients'][0]['estimate'],b['coefficients'][0]['estimate'])

    def test_value_order_controls_reference(self):
        s=example();s.columns[1].metadata['value_order']={'mode':'custom','values':['b','a']};r=fit(s,0,[1],[])
        self.assertEqual(r['factor_information'][0]['reference'],'a');self.assertIn('Material[b]',r['coefficients'][1]['name'])

    def test_diagnostics_leverage_identity_and_residual_sum(self):
        r=fit(example(),0,[1,2],[]);self.assertAlmostEqual(sum(d['leverage'] for d in r['diagnostics']),3,12)
        self.assertAlmostEqual(sum(r['residuals']),0,10);self.assertTrue(all(0<=d['leverage']<=1 for d in r['diagnostics']))

    def test_large_covariate_offset_preserves_anova_and_leverage(self):
        s=Worksheet('Offset',[Column('Y',values=[1,3,2,5,4,7,6,9]),Column('X',values=list(range(8)))])
        a=fit(s,0,[],[1]);s.columns[1].values=[v+1e15 for v in s.columns[1].values];b=fit(s,0,[],[1])
        self.assertAlmostEqual(a['anova_terms'][0]['adj_ss'],b['anova_terms'][0]['adj_ss'],10)
        np.testing.assert_allclose([d['leverage'] for d in a['diagnostics']],[d['leverage'] for d in b['diagnostics']],atol=1e-12)

    def test_exact_fit_omits_inference(self):
        s=Worksheet('Exact',[Column('Y',values=[1,1,1,3,3,3]),Column('F','text',['a']*3+['b']*3)]);r=fit(s,0,[1],[])
        self.assertEqual(r['status'],'exact_fit');self.assertIsNone(r['anova_terms'][0]['p_value']);self.assertIsNone(r['coefficients'][0]['ci_low'])

    def test_invalid_roles_rank_and_saturation_rejected(self):
        s=example()
        for factors,cov in [([],[]),([0],[]),([1],[1]),([],[1]),([True],[])]:
            with self.assertRaises(ValueError):fit(s,0,factors,cov)
        s.columns.append(copy.deepcopy(s.columns[1]))
        with self.assertRaises(ValueError):fit(s,0,[1,3],[])
        with self.assertRaises(ValueError):fit(Worksheet('Tiny',[Column('Y',values=[1,2]),Column('F','text',['a','b'])]),0,[1],[])

    def test_invalid_model_terms_and_options_rejected(self):
        for terms in [[],[[0,1]],[[0],[0]],[[1,0]],[[False]],[[0],[3]]]:
            with self.assertRaises(ValueError):validate_terms(terms,2)
        for key,value in [('coding','execute'),('graphs','unknown'),('confidence',1),('anova','yes')]:
            with self.assertRaises(ValueError):settings(dict(settings(),**{key:value}))

    def test_model_expansion_limit(self):
        s=Worksheet('Wide',[Column('Y',values=list(range(150))),Column('A','text',[str(i%15) for i in range(150)]),Column('B','text',[str(i%16) for i in range(150)])])
        with self.assertRaisesRegex(ValueError,'expansion'):fit(s,0,[1,2],[],[[0],[1],[0,1]])

    def test_report_options_affect_readable_text_and_all_graph_modes(self):
        p=Presenter();p.worksheet=example();e=p.general_linear_model(0,[1,2],[]);text=format_entry(e)
        self.assertIn('Analysis of Variance',text);self.assertIn('Factor Information',text)
        e=p.general_linear_model(0,[1],[],options=dict(settings(),coefficients=False,anova=False));text=format_entry(e)
        self.assertNotIn('Analysis of Variance',text);self.assertNotIn('Coefficients',text)
        for mode,count in [('none',0),('four',4),('normal',1),('histogram',1),('order',1),('fitted',1)]:
            r=fit(example(),0,[1,2],[],options=dict(settings(),graphs=mode));self.assertEqual(len(residual_panels(r)),count)

    def test_mpx_recipe_rerun_and_column_move_identity(self):
        p=Presenter();p.worksheet=example();e=p.general_linear_model(0,[1,2],[],[[0],[1],[0,1]])
        self.assertEqual(columns(e['recipe']),[0,1,2]);before=e['result']['fitted'];p.move_columns([2],'before_column',0)
        self.assertEqual(e['recipe']['parameters']['factor_indices'],[2,0]);np.testing.assert_allclose(run(p,e['recipe'])['result']['fitted'],before)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'glm.mpx';p.save(path);q=Presenter();q.load(path)
            model=q.history[0];self.assertFalse(q.result_stale(model));np.testing.assert_allclose(run(q,model['recipe'])['result']['fitted'],before)

    def test_invalid_fit_does_not_record_result(self):
        p=Presenter();p.worksheet=example()
        with self.assertRaises(ValueError):p.general_linear_model(0,[1,2],[],[[0,1]])
        self.assertEqual(p.history,[]);self.assertFalse(p.dirty)


if __name__=='__main__':unittest.main()
