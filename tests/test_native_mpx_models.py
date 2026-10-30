"""Authored declarative native model fragments; no external data redistributed."""
import copy
import json
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from statcraft.model import Column
from statcraft.response_surface import create,fit
from statcraft.native_mpx_models import read_native_models,resolve_model_recipe,compare_native_model


def fixture(blocked=True):
    sheet=create([dict(name='Heat',low=100.,high=200.),dict(name='Speed',low=.2,high=.8)],centers=6 if blocked else 5,blocks=2 if blocked else 1,center_cube=3 if blocked else 5,center_axial=3 if blocked else 0,alpha_mode='default',randomize=False)
    x=(np.asarray(sheet.columns[4].values)-150)/50;y=(np.asarray(sheet.columns[5].values)-.5)/.3
    b=np.asarray(sheet.columns[3].values);bc=np.where(b==1,1.,-1.)
    matrix=np.column_stack([np.ones(len(x))]+([bc] if blocked else [])+[x,y,x*x,y*y,x*y])
    beta=np.asarray([20.]+([2.] if blocked else [])+[3.,-2.,1.1,-.7,.5]);response=matrix@beta+.13*np.sin(np.arange(len(x))+1)
    sheet.columns.append(Column('Yield',values=response.tolist()))
    for index,column in enumerate(sheet.columns):column.metadata['imported_variable_metadata']={'Id':'column'+str(index),'VarId':index+1}
    def var(index,role='continuous'):
        return {'id':'column'+str(index),'variable_id':float(index+1),'name':sheet.columns[index].name,'type':role,'data_type':'numeric'}
    factors=[var(4),var(5)];block=var(3,'categorical') if blocked else None
    if block:block['classes']=[1.,2.]
    variables={'target':var(6),'predictors':factors}
    if block:variables['block']=block
    terms=[[4],[5],[4,4],[5,5],[4,5]]
    input_terms=([{'term_columns':[var(3)]}] if blocked else [])+[{'term_columns':[var(i) for i in term]} for term in terms]
    # The term reference's role labels are immaterial; UUID/internal IDs define it.
    pred=[{'predictor_type':'constant','predictor_id':-1.,'column_id':0.}]
    if blocked:pred.append({'predictor_type':'block','predictor_id':0.,'column_id':4.,'numeric_levels':[1.,2.],'was_predictor_fit':True,'is_random':False,'is_hard_to_change':False,'nesting_predictor_ids':[]})
    start=1 if blocked else 0
    pred += [dict(predictor_type='continuous',predictor_id=float(start+i),column_id=float(5+i),numeric_levels=levels,was_predictor_fit=True,is_random=False,is_hard_to_change=False,nesting_predictor_ids=[]) for i,levels in enumerate(([100.,200.],[.2,.8]))]
    coef=np.linalg.lstsq(matrix,response,rcond=None)[0];res=response-matrix@coef;df=len(x)-matrix.shape[1];mse=float(res@res/df);se=np.sqrt(np.diag(np.linalg.inv(matrix.T@matrix))*mse)
    post=[{'predictor_ids':[-1.],'coefficients':[float(coef[0])],'standard_error_coefficients':[float(se[0])]}]
    if blocked:post.append({'predictor_ids':[0.],'coefficients':[float(coef[1]),float(-coef[1])],'standard_error_coefficients':[float(se[1]),float(se[1])]})
    pterms=[[0],[1],[0,0],[1,1],[0,1]]
    for i,term in enumerate(pterms):post.append({'predictor_ids':[float(t+start) for t in term],'coefficients':[float(coef[1+int(blocked)+i])],'standard_error_coefficients':[float(se[1+int(blocked)+i])]})
    obj=dict(model_object_type='response_surface',model_analysis_type='response_surface',link_function_type='none',lambda_=1.,has_weights=False,weights_column_id=0.,is_categorical_response=False,is_event_trial=False,is_mle=False,confidence=.95,model_term_list={'model_predictors':pred,'model_terms':post},rows_to_use={'rows':{'use_all_rows':True,'row_count':float(len(x))}},mean_square_error=mse,error_degrees_of_freedom=float(df))
    obj['lambda']=obj.pop('lambda_')
    state=dict(include_constant_term=True,coding='effects',standardized=False,link_function_type='none',confidence_interval='two_sided',selection_method='none',validation_type='none',confidence=.95,continuous_response_model_data={'box_cox':False,'sequential_sum_of_squares':False},termlist={'fixed_factor_columns':([] if block is None else [block])+factors,'model_terms':input_terms})
    model={'metadata':{'command_id':'command','worksheet_id':'worksheet','model_id':1.,'model_type':'response_surface_regression','tables':{},'graphs':{}},'variables':variables,'model_information':{'input_state':state},'post_analysis_data':{'model_object':obj}}
    project=SimpleNamespace(metadata={'Models':{'Items':[{'Type':'ResponseSurfaceRegression','Items':[{'Id':1,'Data':'/models/1/'}]}]},'Commands':{'Items':[{'Id':'command','InputWorksheet':'worksheet','OutputWorksheet':'worksheet'}]}},retained_members={},worksheets=[sheet],worksheet_ids=['worksheet'])
    update(project,model)
    return project,model


def update(project,model):project.retained_members['/models/1/.json']=json.dumps({'Model':model}).encode()


class NativeModelRecoveryTests(unittest.TestCase):
    def decode(self,mutate=None,blocked=True):
        p,m=fixture(blocked)
        if mutate:mutate(m)
        update(p,m)
        return p,m,read_native_models(p)['command']
    def test_actual_low_high_coding_not_axial_extrema(self):
        p,m,d=self.decode();self.assertTrue(d['supported']);v=d['recipe']['parameters']
        self.assertEqual(v['coding'],[{'low':100.,'high':200.},{'low':.2,'high':.8}])
        self.assertLess(min(p.worksheets[0].columns[4].values),v['coding'][0]['low']);self.assertEqual(v['block_index'],3)
    def test_explicit_model_and_worksheet_identity(self):
        p,m,d=self.decode();self.assertEqual(d['command_id'],'command');self.assertEqual(d['worksheet_id'],'worksheet');self.assertEqual(d['model_id'],1)
        self.assertEqual(d['source_column_map']['4'],'column4')
    def test_no_calculation_or_mutation_on_read(self):
        p,m=fixture();before=copy.deepcopy(p)
        with patch('statcraft.response_surface.fit',side_effect=AssertionError('unexpected fit')):d=read_native_models(p)
        self.assertTrue(d['command']['supported']);self.assertEqual(p.__dict__,before.__dict__)
    def test_no_name_or_current_position_fallback(self):
        p,m=fixture();p.worksheets[0].columns[4].metadata['imported_variable_metadata']['Id']='new-same-name'
        self.assertFalse(read_native_models(p)['command']['supported'])
    def test_resolve_moves_and_renames_without_mutation(self):
        p,m,d=self.decode();sheet=p.worksheets[0];column=sheet.columns.pop(4);column.name='Renamed heat';sheet.columns.insert(0,column)
        before=copy.deepcopy(d);r=resolve_model_recipe(p,d)
        self.assertEqual(r['parameters']['factor_indices'],[0,5]);self.assertEqual(r['parameters']['block_index'],4);self.assertEqual(d,before)
        r2=read_native_models(p)['command']['recipe'];self.assertEqual(r2,r)
    def test_deleted_column_rejects_resolution(self):
        p,m,d=self.decode();del p.worksheets[0].columns[4]
        with self.assertRaisesRegex(ValueError,'deleted'):resolve_model_recipe(p,d)
    def test_deleted_worksheet_rejects_resolution(self):
        p,m,d=self.decode();p.worksheet_ids=[]
        with self.assertRaisesRegex(ValueError,'worksheet'):resolve_model_recipe(p,d)
    def test_duplicate_current_identity_is_ambiguous(self):
        p,m=fixture();p.worksheets[0].columns[0].metadata['imported_variable_metadata']['Id']='column4'
        self.assertFalse(read_native_models(p)['command']['supported'])
    def test_declared_model_identity_mismatch(self):
        p,m=fixture();p.metadata['Models']['Items'][0]['Items'][0]['Id']=2
        self.assertFalse(read_native_models(p)['command']['supported'])
    def test_command_wrong_worksheet_rejected(self):
        p,m=fixture();p.metadata['Commands']['Items'][0]['InputWorksheet']='other';p.metadata['Commands']['Items'][0]['OutputWorksheet']='other'
        self.assertFalse(read_native_models(p)['command']['supported'])
    def test_duplicate_command_model_is_ambiguous(self):
        p,m=fixture();p.metadata['Models']['Items'][0]['Items']*=2
        self.assertFalse(read_native_models(p)['command']['supported'])
    def test_missing_member_keeps_unsupported_reason(self):
        p,m=fixture();p.retained_members={};d=read_native_models(p)['/models/1/']
        self.assertFalse(d['supported']);self.assertIn('error',d)
    def test_rejects_transforms_weights_and_non_ols(self):
        for field,value in [('lambda',.5),('has_weights',True),('is_categorical_response',True),('is_event_trial',True),('is_mle',True),('link_function_type','log')]:
            with self.subTest(field=field):
                p,m,d=self.decode(lambda m:m['post_analysis_data']['model_object'].__setitem__(field,value));self.assertFalse(d['supported'])
    def test_rejects_subset_no_intercept_selection_and_standardization(self):
        cases=[('include_constant_term',False),('coding','reference'),('standardized',True),('selection_method','stepwise'),('validation_type','test'),('confidence_interval','lower')]
        for key,value in cases:
            with self.subTest(key=key):p,m,d=self.decode(lambda m:m['model_information']['input_state'].__setitem__(key,value));self.assertFalse(d['supported'])
        p,m,d=self.decode(lambda m:m['post_analysis_data']['model_object']['rows_to_use']['rows'].__setitem__('use_all_rows',False));self.assertFalse(d['supported'])
    def test_rejects_wrong_internal_predictor_identity(self):
        p,m,d=self.decode(lambda m:m['post_analysis_data']['model_object']['model_term_list']['model_predictors'][2].__setitem__('column_id',999))
        self.assertFalse(d['supported'])
    def test_rejects_invalid_coding(self):
        for values in ([1.],[2.,1.],[1.,float('nan')],[1.,1e30]):
            with self.subTest(values=values):p,m,d=self.decode(lambda m:m['post_analysis_data']['model_object']['model_term_list']['model_predictors'][2].__setitem__('numeric_levels',values));self.assertFalse(d['supported'])
    def test_rejects_mismatched_input_and_saved_terms(self):
        p,m,d=self.decode(lambda m:m['post_analysis_data']['model_object']['model_term_list']['model_terms'].pop())
        self.assertFalse(d['supported'])
    def test_rejects_block_interactions(self):
        p,m,d=self.decode(lambda m:m['model_information']['input_state']['termlist']['model_terms'][0]['term_columns'].append(copy.deepcopy(m['variables']['predictors'][0])))
        self.assertFalse(d['supported'])
    def test_rejects_corrupt_coefficients_and_inference(self):
        p,m,d=self.decode(lambda m:m['post_analysis_data']['model_object']['model_term_list']['model_terms'][0].__setitem__('coefficients',[float('nan')]))
        self.assertFalse(d['supported'])
        p,m,d=self.decode(lambda m:m['post_analysis_data']['model_object'].__setitem__('error_degrees_of_freedom',-1));self.assertFalse(d['supported'])
    def test_unblocked_recipe_and_independent_saved_calculation(self):
        p,m,d=self.decode(blocked=False);self.assertTrue(d['supported']);self.assertNotIn('block_index',d['recipe']['parameters'])
        r=fit(p.worksheets[0],**d['recipe']['parameters']);comparison=compare_native_model(r,d);self.assertTrue(comparison['matches_saved_native'])
    def test_blocked_fresh_fit_matches_independent_saved_calculation(self):
        p,m,d=self.decode();r=fit(p.worksheets[0],**d['recipe']['parameters']);comparison=compare_native_model(r,d)
        self.assertTrue(comparison['matches_saved_native']);self.assertTrue(all(v['matches'] for v in comparison['comparisons']))
    def test_changed_data_is_a_fresh_fit_with_reported_disagreement(self):
        p,m,d=self.decode();p.worksheets[0].columns[6].values[0]+=10
        r=fit(p.worksheets[0],**resolve_model_recipe(p,d)['parameters']);self.assertFalse(compare_native_model(r,d)['matches_saved_native'])
        self.assertNotEqual(r['ms_error'],d['verification_reference']['mse'])
    def test_comparison_checks_standard_errors_and_df(self):
        p,m,d=self.decode();r=fit(p.worksheets[0],**d['recipe']['parameters']);r['coefficients'][0]['standard_error']*=2;r['df_error']+=1
        comparison=compare_native_model(r,d);self.assertFalse(comparison['matches_saved_native']);self.assertFalse(next(v for v in comparison['comparisons'] if v['label']=='Error DF')['matches'])
    def test_malformed_top_collections_are_inert(self):
        p,m=fixture();p.metadata['Models']=None;self.assertEqual(read_native_models(p),{})
        p,m=fixture();p.metadata['Models']['Items']=3;self.assertEqual(read_native_models(p),{})
        p,m=fixture();p.metadata['Commands']=None;self.assertFalse(read_native_models(p)['command']['supported'])
    def test_unrelated_model_families_and_none_project_are_ignored(self):
        p,m=fixture();p.metadata['Models']['Items'][0]['Type']='BinaryLogisticRegression'
        self.assertEqual(read_native_models(p),{});self.assertEqual(read_native_models(None),{})
    def test_rejects_unsafe_member_references(self):
        p,m=fixture();p.metadata['Models']['Items'][0]['Items'][0]['Data']='/models/../unrelated/'
        self.assertEqual(read_native_models(p),{})
    def test_confidence_and_sequential_settings_preserved(self):
        p,m=fixture();m['model_information']['input_state']['confidence']=.9;m['post_analysis_data']['model_object']['confidence']=.9;m['model_information']['input_state']['continuous_response_model_data']['sequential_sum_of_squares']=True;update(p,m)
        d=read_native_models(p)['command'];self.assertEqual(d['recipe']['parameters']['options']['confidence'],.9);self.assertEqual(d['recipe']['parameters']['options']['ss_type'],'sequential')

    def test_resolve_entry_recipe_native_and_statcraft(self):
        from statcraft.native_mpx_models import resolve_entry_recipe
        p, m, d = self.decode()
        sheet = p.worksheets[0]
        native_entry = {'origin': 'native', 'worksheet_name': sheet.name, 'native_model': d}
        resolved = resolve_entry_recipe(native_entry, sheet)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved['action'], 'analyze_response_surface')
        self.assertEqual(resolved['parameters']['response_index'], 6)
        
        # Test column move
        col = sheet.columns.pop(4)
        sheet.columns.insert(0, col)
        resolved_moved = resolve_entry_recipe(native_entry, sheet)
        self.assertEqual(resolved_moved['parameters']['factor_indices'][0], 0)
        
        # Restore sheet
        sheet.columns.pop(0)
        sheet.columns.insert(4, col)
        
        # Test wrong worksheet name
        wrong_entry = {'origin': 'native', 'worksheet_name': 'Other Worksheet', 'native_model': d}
        self.assertIsNone(resolve_entry_recipe(wrong_entry, sheet))
        
        # Test StatCraft entry
        sc_entry = {'origin': 'statcraft', 'recipe': {'action': 'multiple_regression', 'parameters': {}}}
        self.assertEqual(resolve_entry_recipe(sc_entry, sheet), sc_entry['recipe'])

    def test_native_model_discovery_optimizer_and_plots(self):
        from statcraft.optimizer import discover_models as discover_opt_models
        from statcraft.model_plots import discover_models as discover_plot_models
        p, m, d = self.decode()
        sheet = p.worksheets[0]
        native_entry = {'origin': 'native', 'worksheet_name': sheet.name, 'native_model': d}
        history = [native_entry]
        
        opt_models = discover_opt_models(sheet, history)
        self.assertEqual(len(opt_models), 1)
        self.assertEqual(opt_models[0]['response_index'], 6)
        self.assertEqual(opt_models[0]['model_title'], 'Response Surface Regression')
        
        plot_models = discover_plot_models(sheet, history, require_two_continuous=True)
        self.assertEqual(len(plot_models), 1)
        self.assertEqual(plot_models[0]['response_index'], 6)
        self.assertEqual(plot_models[0]['continuous_count'], 2)

    def test_native_model_downstream_analyses_execution(self):
        from statcraft.app import Presenter
        p_proj, m, d = self.decode()
        sheet = p_proj.worksheets[0]
        pres = Presenter()
        pres.worksheet = sheet
        native_entry = {'origin': 'native', 'worksheet_name': sheet.name, 'native_model': d}
        pres.history = [native_entry]
        
        # 1. predict_model
        rec = d['recipe']
        res_pred = pres.predict_model(rec, input_mode='values', values=[[1.0, 150.0, 0.5]])
        self.assertEqual(res_pred['origin'], 'statcraft')
        self.assertIn('rows', res_pred['result'])
        
        # 2. factorial_plots
        res_fact = pres.factorial_plots(rec, selected_indices=[4, 5])
        self.assertEqual(res_fact['origin'], 'statcraft')
        
        # 3. model_contour_plot
        res_contour = pres.model_contour_plot(rec, x_index=4, y_index=5)
        self.assertEqual(res_contour['origin'], 'statcraft')
        
        # 4. model_surface_plot
        res_surf = pres.model_surface_plot(rec, x_index=4, y_index=5)
        self.assertEqual(res_surf['origin'], 'statcraft')
        
        # 5. optimize_responses
        spec = {'model_recipe': rec, 'goal': 'maximize', 'lower': 10, 'target': 25, 'weight': 1.0, 'importance': 1.0}
        res_opt = pres.optimize_responses([spec])
        self.assertEqual(res_opt['origin'], 'statcraft')
        self.assertIn('solutions', res_opt['result'])

if __name__=='__main__':unittest.main()
