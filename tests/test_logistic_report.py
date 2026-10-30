import copy
import unittest
from statcraft.logistic_report import sections, text_report, prediction_sections


def fixture():
    return dict(analysis='binary_logistic', response_name='Accepted', event='Yes', non_event='No',
        options={}, n=4, missing=1, events=6, non_events=10, deviance=2.1, aic=15., bic=17., auc=.76,
        model_lr=4.5, model_lr_df=1, model_lr_p=.034, df_error=2, deviance_p=.35,
        pearson_chi_square=2.2, pearson_p=.33, iterations=5, log_likelihood=-5.5,
        null_log_likelihood=-7.75, bic_sample_size=16,
        coefficients=[dict(name='Constant', estimate=-1., standard_error=.4, z=-2.5, p_value=.012, ci_low=-1.78, ci_high=-.22, odds_ratio=None, or_low=None, or_high=None),
            dict(name='Temperature', estimate=.2, standard_error=.08, z=2.5, p_value=.012, ci_low=.043, ci_high=.357, odds_ratio=1.2214, or_low=1.044, or_high=1.429)],
        diagnostics=[dict(row=1, response=1, trials=4, probability=.25, deviance_residual=-.2, pearson_residual=-.1, standardized_residual=-.22, leverage=.2, flag=''),
            dict(row=4, response=3, trials=4, probability=.45, deviance_residual=2.3, pearson_residual=2.1, standardized_residual=2.5, leverage=.3, flag='R')],
        coding_information=[dict(name='Machine', kind='factor', levels=['A', 'B'], reference='B')],
        methodnotes='Wald coefficient and odds-ratio intervals.', warnings=['Small expected counts can invalidate approximations.'])


def prediction():
    return dict(analysis='logistic_prediction', response_name='Accepted', event='Yes', options={},
        predictor_names=['Temperature', 'Machine'], used=1, missing=1, coefficients=fixture()['coefficients'],
        rows=[dict(row=1, inputs=[25, 'A'], probability=.55, se_probability=.1, eta=.2, ci_low=.35, ci_high=.73, status='converged', extrapolated=True),
            dict(row=2, inputs=[None, 'B'], probability=None, se_probability=None, eta=None, ci_low=None, ci_high=None, status='missing', extrapolated=False)], warnings=[])


class LogisticReportTests(unittest.TestCase):
    def table(self, result, name):
        return next(a for a in sections(result) if a[0]==name)

    def test_answer_leads_supporting_method(self):
        r=fixture();self.assertEqual(sections(r)[0][0], 'Model Summary');self.assertEqual(sections(r)[-1][0], 'Method')
        self.assertLess(text_report(r).index('Coefficients'),text_report(r).index('Method'))

    def test_all_cells_scalar_and_rectangular(self):
        for r in (fixture(), prediction()):
            for title, headers, rows in sections(r):
                self.assertTrue(all(len(a)==len(headers) for a in rows),title)
                self.assertTrue(all(not isinstance(a,(dict,list,tuple)) for row in rows for a in row),title)

    def test_response_identifies_event_and_counts(self):
        self.assertEqual(self.table(fixture(),'Response Information')[2],[['Accepted','Yes',6],['Accepted','No',10]])
        self.assertEqual(self.table(fixture(),'Event')[2],[['Yes']])

    def test_coefficient_and_odds_intervals_are_explicit_wald(self):
        r=fixture();r['options']['confidence']=.9
        self.assertIn('90% Wald Lower',self.table(r,'Coefficients')[1]);self.assertIn('90% Wald Upper',self.table(r,'Odds Ratios')[1])
        self.assertEqual(len(self.table(r,'Odds Ratios')[2]),1);self.assertEqual(self.table(r,'Odds Ratios')[2][0][0],'Temperature')

    def test_likelihood_and_goodness_are_distinct(self):
        self.assertEqual(self.table(fixture(),'Likelihood Ratio Test')[2],[['Model',1,4.5,.034]])
        self.assertEqual(self.table(fixture(),'Goodness-of-Fit')[2],[['Deviance',2,2.1,.35],['Pearson',2,2.2,.33]])

    def test_all_fit_display_flags_hide_related_sections(self):
        r=fixture();r['options'].update({a:False for a in ('method','response_information','model_summary','coefficients','odds_ratios','equation')});r['options']['diagnostics']='none'
        self.assertEqual(sections(r),[])

    def test_individual_display_flags(self):
        pairs={'method':['Method'],'response_information':['Response Information','Event'],
               'model_summary':['Model Summary','Likelihood Ratio Test','Goodness-of-Fit'],
               'coefficients':['Coefficients'],'odds_ratios':['Odds Ratios'],'equation':['Regression Equation']}
        for flag, titles in pairs.items():
            r=fixture();r['options'][flag]=False;actual=[a[0] for a in sections(r)]
            self.assertTrue(all(a not in actual for a in titles),flag)

    def test_diagnostics_filter_source_row_numbers(self):
        r=fixture();t=next(a for a in sections(r) if a[0].startswith('Fits and Diagnostics'));self.assertEqual(t[2][0][0],4);self.assertEqual(len(t[2]),1)
        r['options']['diagnostics']='all';self.assertEqual(len(self.table(r,'Fits and Diagnostics')[2]),2)
        r['options']['diagnostics']='none';self.assertNotIn('Fits and Diagnostics',text_report(r));self.assertNotIn('R: |',text_report(r))

    def test_equation_event_and_predictor_names(self):
        text=text_report(fixture());self.assertIn('logit(P(Accepted = Yes))',text);self.assertIn('Temperature',text);self.assertIn('Machine reference',text)

    def test_no_raw_payload_or_input_mutation(self):
        r=fixture();r['probabilities']=[.3,.4];r['_covariance']=[[1]];before=copy.deepcopy(r);text=text_report(r)
        self.assertEqual(r,before);self.assertNotIn('_covariance',text);self.assertNotIn('[0.3',text)

    def test_prediction_leads_and_named_inputs(self):
        r=prediction();self.assertEqual(sections(r)[0][0],'Probability Predictions');self.assertEqual(self.table(r,'New Predictor Values')[1],['Row','Temperature','Machine'])
        self.assertEqual(sections(r),prediction_sections(r))

    def test_probability_prediction_no_observation_interval(self):
        text=text_report(prediction());self.assertIn('Probability',text);self.assertIn('95% CI Lower',text);self.assertNotIn(' PI ',text);self.assertNotIn('SE Fit',text)

    def test_one_sided_probability_bounds(self):
        for side, present, absent in [('lower','CI Lower','CI Upper'),('upper','CI Upper','CI Lower')]:
            r=prediction();r['options'].update(side=side,confidence=.9);text=text_report(r)
            self.assertIn('90% '+present,text);self.assertNotIn(absent,text)

    def test_prediction_flags_and_missing(self):
        r=prediction();text=text_report(r);self.assertIn('Missing predictor settings',text);self.assertIn('X: continuous',text)
        r['options'].update(show_table=False,show_equation=False)
        self.assertEqual([a[0] for a in sections(r)],['Method']);self.assertNotIn('X: continuous',text_report(r))

    def test_no_intervals_hides_bounds(self):
        r=prediction();r['options']['intervals']='none';headers=sections(r)[0][1]
        self.assertEqual(headers,['Row','Probability','SE Probability','X','Status'])

    def test_warning_and_undefined_value_visible(self):
        r=fixture();r['deviance_p']=None;text=text_report(r)
        self.assertIn('Small expected counts',text);self.assertIn('*',text);self.assertNotIn('nan',text.lower())

    def test_grouped_counts_use_readable_event_labels(self):
        r=fixture();r.update(grouped=True,event=None,non_event=None)
        rows=self.table(r,'Response Information')[2];self.assertEqual(rows[0][1],'Event');self.assertEqual(rows[1][1],'Non-event')
        self.assertNotIn('= None',text_report(r))

    def test_actual_engine_fit_and_probability_prediction_report(self):
        from statcraft.model import Worksheet,Column
        from statcraft.logistic import fit,predict,settings
        sheet=Worksheet('Study',[Column('Events',values=[1,2,4,5,7,8]),Column('Trials',values=[10]*6),Column('Dose',values=[1.,2.,3.,4.,5.,6.])])
        options=settings();options['graphs']='four';r=fit(sheet,0,[2],[],trials_index=1,options=options)
        text=text_report(r);self.assertIn('Dose',text);self.assertIn('Odds Ratios',text);self.assertIn('Events',text);self.assertNotIn('= None',text)
        recipe=dict(action='fit_binary_logistic',parameters=dict(response_index=0,continuous_indices=[2],categorical_indices=[],event=None,trials_index=1,terms=[[0]],options=options))
        p=predict(sheet,recipe,values=[[2.5]])
        self.assertIn('Probability Predictions',text_report(p));self.assertGreater(p['rows'][0]['probability'],0.)
