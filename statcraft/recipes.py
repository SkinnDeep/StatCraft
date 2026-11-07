"""Original typed analysis recipes and dependency tracking; no command evaluation."""
import hashlib
import json
import math

FIELDS = {
    'evaluate_design': {'factor_indices', 'model_order'},
    'cart_tree': {'response_index', 'predictor_indices', 'tree_type', 'max_depth', 'min_split_size', 'min_leaf_size'},
    'fit_y_by_x': {'y_index', 'x_index', 'platform', 'confidence'},
    'jmp_distribution': {'column_indices', 'confidence'},
    'control_chart_builder': {'y_indices', 'subgroup_index', 'subgroup_size', 'phase_index', 'chart_type', 'k_sigma'},
    'process_screening': {'variable_indices', 'subgroup_size', 'subgroup_index', 'k_sigma'},
    'evaluating_measurement_process': {'measurement_index', 'part_index', 'operator_index', 'alpha_interaction'},
    'definitive_screening_analysis': {'response_index', 'factor_indices', 'selection', 'alpha_enter', 'alpha_leave', 'confidence', 'show_pareto'},
    'accelerated_life_testing': {'time_index', 'stress_index', 'censor_index', 'model', 'distribution', 'use_stress', 'confidence'},
    'predict_mixture': {'model_recipe','component_rows','confidence'},
    'mixture_contour': {'model_recipe','component_positions','hold_values','options'},
    'optimize_mixture': {'model_recipe','goal','target','bounds','options'},
    'optimize_mixture_multi': {'responses','bounds','options'},
    'evaluate_mixture_multi': {'responses','components','bounds','options'},
    'analyze_mixture': {'response_index','component_indices','model','total','options'},
    'analyze_mixture_process': {'response_index','component_indices','process_indices','block_index','covariate_indices','model','total','options'},
    'predict_mixture_process': {'model_recipe','component_rows','process_rows','covariate_rows','block_values','confidence'},
    'mixture_process_contour': {'model_recipe','process_values','covariate_values','block_value','component_positions','hold_values','options'},
    'optimize_mixture_process': {'model_recipe','process_values','covariate_values','block_value','goal','target','bounds','options'},
    'optimize_mixture_joint': {'model_recipe','goal','target','component_bounds','process_bounds','covariate_values','block_value','options'},
    'analyze_taguchi': {'response_indices','factor_indices','options'},
    'analyze_dynamic_taguchi': {'response_indices','signal_values','factor_indices','options'},
    'multiple_capability': {'method', 'variable_indices', 'by_indices', 'subgroup_sizes', 'subgroup_indices', 'lower_specs', 'upper_specs', 'targets', 'distribution', 'options'},
    'attribute_capability': {'method', 'count_index', 'sample_size', 'size_index', 'options'},
    'subgroup_control_chart': {'chart_type', 'stacked', 'response_index', 'factor_index', 'indices', 'subgroup_size', 'options'},
    'oneway_anova': {'stacked', 'response_index', 'factor_index', 'response_indices', 'options'},
    'twoway_anova': {'response_index', 'factor_a_index', 'factor_b_index', 'fit_interaction', 'display_means', 'confidence'},
    'main_effects_plot': {'response_index', 'factor_indices'},
    'interactions_plot': {'response_index', 'factor_a_index', 'factor_b_index'},
    'store_descriptive_stats': {'var_indices', 'by_index', 'selected_stats'},
    'factorial_plots':{'model_recipe','selected_indices','options'},
    'model_contour_plot':{'model_recipe','x_index','y_index','options'},
    'model_surface_plot':{'model_recipe','x_index','y_index','options'},
    'optimize_responses':{'responses','options'},
    'fit_binary_logistic':{'response_index','continuous_indices','categorical_indices','event','trials_index','terms','options'},
    'predict_model':{'model_recipe','input_mode','values','new_indices','options'},
    'gage_rr':{'measurement_index','part_index','operator_index','options'},
    'analyze_response_surface':{'response_index','factor_indices','coding','terms','options'},
    'general_linear_model':{'response_index','factor_indices','covariate_indices','terms','options'},
    'graph_builder':{'graph_type','response_indices','x_index','group_indices','options'},
    'categorical_points':{'response_indices','plot_type','variant','group_indices','variable_position','layout','display','interval_options','jitter','color_levels'},
    'dotplot_graphs':{'response_indices','variant','group_indices','variable_position','layout','stack','intervals','color_levels'},
    'boxplot_graphs':{'response_indices','variant','group_indices','variable_position','layout','display'},
    'histogram_graphs':{'response_indices','variant','group_index','layout','settings'},
    'panel_graph':{'source_recipe','by_indices','shared_x','shared_y','source_appearance'},
    'expanded_graph': {'method','indices','group_index','bins','confidence','distribution','parameters'},
    'analyze_factorial_terms': {'response_index','factor_indices','max_order','confidence','plot_residuals','show_factor_coding','selected_terms'},
    'analyze_factorial': {'response_index','factor_indices','max_order','confidence','plot_residuals','show_factor_coding'},
    'scatter_plot': {'x_index','y_index','mode','group_index','order','title','x_label','y_label'},
    'normality': {'index'},
    'one_variance': {'index','null_stdev','confidence'},
    'covariance': {'indices', 'missing'},
    'stem_and_leaf': {'index'},
    'correlation': {'indices', 'method', 'missing', 'confidence'},
    'one_proportion': {'index', 'null_proportion', 'confidence', 'alternative'},
    'two_proportions': {'first_index', 'second_index', 'confidence'},
    'describe_columns': {'indices'}, 'describe_column': {'index'},
    'inference': {'method', 'indices', 'mu', 'confidence'},
    'multiple_regression': {'response_index', 'predictor_indices', 'confidence'},
    'fitted_line_plot': {'response_index', 'predictor_index', 'model_type', 'confidence', 'options'},
    'anom': {'response_index', 'factor1_index', 'factor2_index', 'distribution', 'sample_size', 'alpha', 'title'},
    'dist_id': {'column_index', 'distributions', 'subgroup_size', 'alpha', 'box_cox_lambda', 'johnson_p_threshold'},
    'cause_and_effect': {'branches', 'effect', 'title', 'no_empty', 'no_labels'},
    'individuals_moving_range': {'index'},
    'xbar_r_rows': {'indices'},
    'xbar_r_stacked': {'response_index', 'factor_index'},
    'normal_capability': {'index', 'lsl', 'usl', 'target'},
    'attribute_chart': {'chart', 'count_index', 'size_index'},
    'stacked_anova': {'response_index', 'factor_index'},
    'equal_variances_columns': {'indices', 'method'},
    'equal_variances_stacked': {'response_index', 'factor_index', 'method'},
    'test_equal_variances': {'stacked', 'response_index', 'factor_indices', 'response_indices', 'options'},
    'two_sample_t': {'settings'},
    'two_sample_proportion': {'settings'},
    'two_sample_poisson': {'settings'},
    'two_variances': {'settings'},
    'one_sample_poisson': {'settings'},
    'one_sample_t': {'settings'},
    'one_sample_z': {'settings'},
    'one_sample_proportion': {'settings'},
    'paired_t': {'settings'},
    'normal_sixpack': {'settings'},
    'acceptance_control_chart': {'settings'},
    'capability_nonnormal': {'settings'},
    'reliability_distribution': {'settings'},
    'capability_nonparametric': {'settings'},
    'capability_automated': {'settings'},
    'nested_gage_rr': {'part_col', 'operator_col', 'measurement_col', 'part_index', 'operator_index', 'measurement_index', 'options'},
    'gage_linearity': {'reference_col', 'measurement_col', 'part_col', 'reference_index', 'measurement_index', 'part_index', 'process_variation'},
    'attribute_agreement': {'attribute_col', 'sample_col', 'appraiser_col', 'standard_col', 'trial_col', 'attribute_index', 'sample_index', 'appraiser_index', 'standard_index', 'trial_index'},
    'imr_chart': {'settings'},
    'attribute_control_chart': {'settings'},
    'time_weighted_control_chart': {'settings'},
    'rare_event_control_chart': {'settings'},
    'multivariate_control_chart': {'settings'},
    'pareto_chart': {'settings'},
    'type1_gage': {'measurement_index', 'measurement_name', 'reference', 'settings'},
    'tolerance_intervals': {'settings'},
    'trend_analysis': {'settings'},
    'decomposition': {'settings'},
    'moving_average': {'settings'},
    'single_exp_smoothing': {'settings'},
    'double_exp_smoothing': {'settings'},
    'autocorrelation': {'settings'},
    'partial_autocorrelation': {'settings'},
    'cross_correlation': {'first_index', 'second_index', 'lags', 'title', 'store_ccf'},
    'differences': {'settings'},
    'lag': {'settings'},
    'sign_test': {'settings'},
    'one_sample_wilcoxon': {'settings'},
    'mann_whitney': {'settings'},
    'kruskal_wallis': {'settings'},
    'moods_median': {'settings'},
    'friedman_test': {'settings'},
    'runs_test': {'settings'},
    'paired_wilcoxon': {'settings'},
    'pca': {'settings'},
    'item_analysis': {'settings'},
    'cluster_observations': {'settings'},
    'cluster_kmeans': {'settings'},
    'cluster_variables': {'settings'},
    'discriminant_analysis': {'settings'},
    'simple_correspondence': {'settings'},
    'one_sample_equivalence': {'settings'},
    'two_sample_equivalence': {'settings'},
    'paired_equivalence': {'settings'},
    'crossover_equivalence': {'settings'},
    'one_sample_z_power': {'settings'},
    'one_sample_t_power': {'settings'},
    'two_sample_t_power': {'settings'},
    'paired_t_power': {'settings'},
    'one_proportion_power': {'settings'},
    'two_proportions_power': {'settings'},
    'oneway_anova_power': {'settings'},
    'factorial_power': {'settings'},
    'cross_tabulation': {'settings'},
    'chi_square_goodness_of_fit': {'settings'},
    'chi_square_association_table': {'settings'},
    'tally_variables': {'settings'},
    'graphical_summary': {'variable_index', 'confidence'},
    'run_chart': {'variable_index', 'subgroup_size'},
    'multivari': {'response_index', 'factor_indices'},
    'outlier_test': {'variable_index', 'alpha', 'alternative'},
    'graph': {'method', 'indices', 'bins'},
}


def columns(recipe):
    if not isinstance(recipe, dict) or set(recipe) != {'action', 'parameters'}:
        raise ValueError('This result has no supported analysis recipe.')
    action, parameters = recipe['action'], recipe['parameters']
    if not isinstance(action, str) or action not in FIELDS or not isinstance(parameters, dict):
        raise ValueError('Unsupported analysis recipe or parameters.')
    keys = set(parameters)
    expected = FIELDS[action]
    if action in ('analyze_factorial', 'analyze_factorial_terms', 'analyze_response_surface'):
        optional = 'block_index' if action=='analyze_response_surface' else 'include_blocks'
        if keys not in (expected, expected | {optional}):
            raise ValueError('Unsupported analysis recipe or parameters.')
    elif action in ('one_variance', 'normal_capability', 'normal_sixpack', 'acceptance_control_chart'):
        if keys not in (expected, {'settings'}):
            raise ValueError('Unsupported analysis recipe or parameters.')
    elif action == 'cross_correlation':
        if not expected - {'title', 'store_ccf'} <= keys <= expected:
            raise ValueError('Unsupported Cross Correlation parameters.')
    elif action == 'dist_id':
        if not expected - {'box_cox_lambda', 'johnson_p_threshold', 'distributions', 'show_ci'} <= keys <= expected:
            raise ValueError('Unsupported analysis recipe or parameters.')
    elif keys != expected:
        raise ValueError('Unsupported analysis recipe or parameters.')
    if action in ('predict_mixture_process','mixture_process_contour','optimize_mixture_process','optimize_mixture_joint'):
        if not isinstance(parameters['model_recipe'],dict) or parameters['model_recipe'].get('action')!='analyze_mixture_process':raise ValueError('Select a fitted mixture/process model.')
        return columns(parameters['model_recipe'])
    if action=='analyze_mixture_process':
        lists=[parameters['component_indices'],parameters['process_indices'],parameters['covariate_indices']]
        if any(not isinstance(values,list) for values in lists) or not 2<=len(lists[0])<=8 or len(lists[1])>3 or len(lists[2])>4:raise ValueError('Select valid component, process and covariate lists.')
        block=parameters['block_index']
        if not lists[1] and not lists[2] and block is None:raise ValueError('Select a process variable, covariate or block, or use Analyze Mixture Design.')
        refs=[parameters['response_index']]+sum(lists,[])+([] if block is None else [block])
        if any(type(index) is not int or index<0 for index in refs) or len(set(refs))!=len(refs):raise ValueError('All response, component, process, block and covariate columns must be distinct.')
        return sorted(refs)
    if action in ('optimize_mixture_multi','evaluate_mixture_multi'):
        responses=parameters['responses']
        if not isinstance(responses,list) or not 2<=len(responses)<=8:raise ValueError('Select two to eight fitted mixture responses.')
        refs=set();shared=None;total=None;seen=set()
        for item in responses:
            if not isinstance(item,dict) or set(item)!={'model_recipe','goal','lower','target','upper','weight','importance'}:raise ValueError('Each mixture response needs its fitted model and desirability settings.')
            model=item['model_recipe']
            if not isinstance(model,dict) or model.get('action')!='analyze_mixture':raise ValueError('Select fitted mixture models.')
            refs.update(columns(model));params=model['parameters'];components=params['component_indices']
            if shared is None:shared=list(components);total=params['total']
            if list(components)!=shared or params['total']!=total:raise ValueError('Response models must use the same component columns in the same order and the same total.')
            if params['response_index'] in seen:raise ValueError('Select distinct response columns.')
            seen.add(params['response_index'])
        if set(shared)&seen:raise ValueError('Response and component columns must be separate.')
        return sorted(refs)
    if action in ('predict_mixture','mixture_contour','optimize_mixture'):
        if not isinstance(parameters['model_recipe'],dict) or parameters['model_recipe'].get('action')!='analyze_mixture':raise ValueError('Select a fitted mixture model.')
        return columns(parameters['model_recipe'])
    if action in ('analyze_mixture','analyze_taguchi','analyze_dynamic_taguchi'):
        responses=[parameters['response_index']] if action=='analyze_mixture' else parameters['response_indices']
        factors=parameters['component_indices'] if action=='analyze_mixture' else parameters['factor_indices']
        if not isinstance(responses,list) or not responses or not isinstance(factors,list) or not factors:
            raise ValueError('Select source response and factor/component columns.')
        refs=responses+factors
        if any(type(index) is not int or index<0 for index in refs) or len(set(refs))!=len(refs):
            raise ValueError('Select distinct valid source columns.')
        return sorted(refs)
    if action == 'multiple_capability':
        from .multiple_capability_engine import recipe_sources
        return recipe_sources(parameters)
    from .analysis_bindings import ACTIONS, binding_columns
    if action in ACTIONS and 'settings' in parameters:
        return binding_columns(action, parameters['settings'])
    if action == 'attribute_capability':
        count, size = parameters['count_index'], parameters['size_index']
        if parameters['method'] not in ('binomial', 'poisson'):
            raise ValueError('Unsupported attribute capability method.')
        if type(count) is not int or count < 0 or (size is not None and (type(size) is not int or size < 0 or size == count)):
            raise ValueError('Select valid distinct count and sample-size columns.')
        return sorted([count] + ([] if size is None else [size]))
    if action in ('one_sample_t', 'one_sample_z', 'one_sample_proportion', 'one_sample_poisson'):
        st = parameters.get('settings', {})
        fmt = st.get('data_format', 0)
        if fmt == 0:
            cols = list(st.get('sample_cols', [])) + list(st.get('freq_cols', []))
            return [c for c in cols if isinstance(c, int) and c >= 0]
        else:
            return []
    if action == 'paired_t':
        st = parameters.get('settings', {})
        fmt = st.get('data_format', 1)
        if fmt == 1:
            cols = [st.get('sample1_col'), st.get('sample2_col')]
            return [c for c in cols if isinstance(c, int) and c >= 0]
        else:
            return []
    if action in ('normal_capability', 'normal_sixpack', 'acceptance_control_chart', 'capability_nonnormal', 'reliability_distribution', 'capability_nonparametric', 'capability_automated'):
        if 'settings' in parameters:
            st = parameters.get('settings', {})
            cols = []
            if isinstance(st.get('column_index'), int) and st['column_index'] >= 0:
                cols.append(st['column_index'])
            if isinstance(st.get('subgroup_col_index'), int) and st['subgroup_col_index'] >= 0:
                cols.append(st['subgroup_col_index'])
            for ca in st.get('cols_across_indices', []):
                if isinstance(ca, int) and ca >= 0:
                    cols.append(ca)
            return cols
        idx = parameters.get('index')
        return [idx] if isinstance(idx, int) and idx >= 0 else []
    if action == 'nested_gage_rr':
        cols = []
        for key in ('part_index', 'operator_index', 'measurement_index'):
            if isinstance(parameters.get(key), int) and parameters[key] >= 0:
                cols.append(parameters[key])
        return cols
    if action == 'gage_linearity':
        cols = []
        for key in ('reference_index', 'measurement_index', 'part_index'):
            if isinstance(parameters.get(key), int) and parameters[key] >= 0:
                cols.append(parameters[key])
        return cols
    if action == 'attribute_agreement':
        cols = []
        for key in ('attribute_index', 'sample_index', 'appraiser_index', 'standard_index', 'trial_index'):
            if isinstance(parameters.get(key), int) and parameters[key] >= 0:
                cols.append(parameters[key])
        return cols
    if action == 'imr_chart':
        st = parameters.get('settings', {})
        vars_list = st.get('variables', [])
        return [c for c in vars_list if isinstance(c, int) and c >= 0]
    if action == 'attribute_control_chart':
        st = parameters.get('settings', {})
        vars_list = st.get('variables', [])
        cols = [c for c in vars_list if isinstance(c, int) and c >= 0]
        if st.get('is_subgroup_col') and isinstance(st.get('subgroup_col_idx'), int) and st.get('subgroup_col_idx') >= 0:
            cols.append(st.get('subgroup_col_idx'))
        return cols
    if action == 'one_variance':
        if 'settings' in parameters:
            st = parameters.get('settings', {})
            if st.get('mode', 0) == 0:
                return [c for c in st.get('columns', []) if isinstance(c, int) and c >= 0]
            return []
        return [parameters['index']]
    if action == 'two_variances':
        st = parameters.get('settings', {})
        mode = st.get('mode', 1)
        if mode == 0:
            cols = [st.get('samples_col'), st.get('subscripts_col')]
            return [c for c in cols if isinstance(c, int) and c >= 0]
        elif mode == 1:
            cols = [st.get('s1_col'), st.get('s2_col')]
            return [c for c in cols if isinstance(c, int) and c >= 0]
        else:
            return []
    if action == 'two_sample_poisson':
        st = parameters.get('settings', {})
        fmt = st.get('data_format', 1)
        if fmt == 0:
            cols = [st.get('samples_col'), st.get('sample_ids_col'), st.get('length_col'), st.get('freq_col')]
            return [c for c in cols if isinstance(c, int) and c >= 0]
        elif fmt == 1:
            cols = [st.get('sample1_col'), st.get('sample2_col'), st.get('length1_col'), st.get('length2_col')] + list(st.get('freq_cols') or [])
            return [c for c in cols if isinstance(c, int) and c >= 0]
        else:
            return []
    if action in ('two_sample_t', 'two_sample_proportion'):
        st = parameters.get('settings', {})
        fmt = st.get('data_format', 1)
        if fmt == 0:
            cols = [st.get('samples_col'), st.get('sample_ids_col')]
            return [c for c in cols if isinstance(c, int) and c >= 0]
        elif fmt == 1:
            cols = [st.get('sample1_col'), st.get('sample2_col')]
            return [c for c in cols if isinstance(c, int) and c >= 0]
        else:
            return []
    if action == 'evaluate_design':
        cols = [f for f in parameters.get('factor_indices', []) if isinstance(f, int) and f >= 0]
        return sorted(set(cols))
    if action == 'cart_tree':
        cols = [parameters['response_index']]
        if parameters.get('predictor_indices'):
            cols.extend([p for p in parameters['predictor_indices'] if isinstance(p, int) and p >= 0])
        return sorted(set(cols))
    if action == 'cross_correlation':
        refs = (parameters['first_index'], parameters['second_index'])
        if refs[0] == refs[1] or any(type(i) is not int or i < 0 for i in refs):
            raise ValueError('Choose two distinct numeric series.')
        return sorted(refs)
    if action == 'fit_y_by_x':
        cols = [parameters['y_index'], parameters['x_index']]
        return sorted(set(cols))
    if action == 'jmp_distribution':
        return sorted(set(parameters['column_indices']))
    if action == 'control_chart_builder':
        cols = list(parameters.get('y_indices', []))
        if parameters.get('subgroup_index') is not None:
            cols.append(parameters['subgroup_index'])
        if parameters.get('phase_index') is not None:
            cols.append(parameters['phase_index'])
        return sorted(set(cols))
    if action == 'process_screening':
        cols = list(parameters.get('variable_indices', []))
        if parameters.get('subgroup_index') is not None:
            cols.append(parameters['subgroup_index'])
        return sorted(set(cols))
    if action == 'evaluating_measurement_process':
        cols = [parameters['measurement_index'], parameters['part_index'], parameters['operator_index']]
        return sorted(set(cols))
    if action == 'definitive_screening_analysis':
        cols = [parameters['response_index']]
        if parameters.get('factor_indices'):
            cols.extend([f for f in parameters['factor_indices'] if isinstance(f, int) and f >= 0])
        return sorted(set(cols))
    if action == 'accelerated_life_testing':
        cols = [parameters['time_index'], parameters['stress_index']]
        if parameters.get('censor_index') is not None and isinstance(parameters['censor_index'], int) and parameters['censor_index'] >= 0:
            cols.append(parameters['censor_index'])
        return sorted(set(cols))
    if action == 'test_equal_variances':
        from .equal_variances_engine import equal_variances_settings
        equal_variances_settings(parameters.get('options'))
        stacked = bool(parameters.get('stacked', True))
        if stacked:
            r = parameters.get('response_index')
            if not isinstance(r, int) or r < 0:
                raise ValueError('Invalid response column index.')
            cols = [r]
            f_inds = parameters.get('factor_indices')
            if not isinstance(f_inds, list) or not (1 <= len(f_inds) <= 9):
                raise ValueError('Test for Equal Variances requires 1 to 9 factor columns.')
            if any(not isinstance(f, int) or f < 0 or f == r for f in f_inds) or len(set(f_inds)) != len(f_inds):
                raise ValueError('Factor columns must be distinct valid indices different from response.')
            cols.extend(f_inds)
            return sorted(set(cols))
        else:
            ris = parameters.get('response_indices')
            if not isinstance(ris, list) or len(ris) < 2 or len(set(ris)) != len(ris) or any(not isinstance(i, int) or i < 0 for i in ris):
                raise ValueError('Unstacked Test for Equal Variances requires at least two distinct response columns.')
            return list(ris)
    if action == 'subgroup_control_chart':
        from .subgroup_control import control_chart_settings
        control_chart_settings(parameters.get('options'))
        stacked = bool(parameters.get('stacked', True))
        if stacked:
            r = parameters.get('response_index')
            if not isinstance(r, int) or r < 0:
                raise ValueError('Invalid response column index.')
            cols = [r]
            f = parameters.get('factor_index')
            if f is not None:
                if not isinstance(f, int) or f < 0 or f == r:
                    raise ValueError('Invalid factor column index.')
                cols.append(f)
            else:
                sz = parameters.get('subgroup_size')
                if not isinstance(sz, int) or sz < 2:
                    raise ValueError('Subgroup size must be at least 2.')
            return sorted(set(cols))
        else:
            inds = parameters.get('indices')
            if not isinstance(inds, (list, tuple)) or len(inds) < 2:
                raise ValueError('Subgroup row arrangement requires at least two columns.')
            if any(not isinstance(i, int) or i < 0 for i in inds) or len(set(inds)) != len(inds):
                raise ValueError('Subgroup columns must be distinct non-negative integers.')
            return sorted(set(inds))
    if action == 'oneway_anova':
        from .oneway import oneway_settings
        oneway_settings(parameters.get('options'))
        stacked = parameters.get('stacked', True)
        if stacked:
            r = parameters.get('response_index')
            f = parameters.get('factor_index')
            if not isinstance(r, int) or not isinstance(f, int) or r == f or r < 0 or f < 0:
                raise ValueError('One-Way ANOVA requires distinct response and factor column indices.')
            return [r, f]
        else:
            ris = parameters.get('response_indices')
            if not isinstance(ris, list) or len(ris) < 2 or len(set(ris)) != len(ris) or any(not isinstance(i, int) or i < 0 for i in ris):
                raise ValueError('Unstacked One-Way ANOVA requires at least two distinct response column indices.')
            return list(ris)
    if action == 'twoway_anova':
        r = parameters.get('response_index')
        fa = parameters.get('factor_a_index')
        fb = parameters.get('factor_b_index')
        if not all(isinstance(x, int) and x >= 0 for x in (r, fa, fb)) or len({r, fa, fb}) != 3:
            raise ValueError('Two-Way ANOVA requires three distinct column indices.')
        return [r, fa, fb]
    if action == 'main_effects_plot':
        r = parameters.get('response_index')
        f = parameters.get('factor_indices')
        if type(r) is not int or r < 0 or not isinstance(f, list) or not f:
            raise ValueError('Main Effects Plot requires valid response and factor column indices.')
        return sorted(set([r] + f))
    if action == 'interactions_plot':
        r = parameters.get('response_index')
        fa = parameters.get('factor_a_index')
        fb = parameters.get('factor_b_index')
        if not all(isinstance(x, int) and x >= 0 for x in (r, fa, fb)) or len({r, fa, fb}) != 3:
            raise ValueError('Interactions Plot requires three distinct column indices.')
        return [r, fa, fb]
    if action == 'store_descriptive_stats':
        vars_ = parameters.get('var_indices', [])
        by_ = parameters.get('by_index')
        idx = list(vars_)
        if by_ is not None and isinstance(by_, int) and by_ >= 0:
            idx.append(by_)
        return sorted(set(idx))
    if action=='optimize_responses':
        from .optimizer import settings,SUPPORTED_MODELS,individual_desirability
        opts=settings(parameters['options'])
        resps=parameters['responses']
        if not isinstance(resps,list) or not 1<=len(resps)<=8:
            raise ValueError('Select 1?8 fitted responses for optimization.')
        indices=[];resp_cols=[];pred_cols=set()
        for item in resps:
            if not isinstance(item,dict) or set(item)!={'model_recipe','goal','lower','target','upper','weight','importance'}:
                raise ValueError('Invalid response optimization specification.')
            src=item['model_recipe']
            if not isinstance(src,dict) or src.get('action') not in SUPPORTED_MODELS:
                raise ValueError('Choose a supported source model for response optimization.')
            src_cols=columns(src);indices.extend(src_cols)
            r_col=src['parameters']['response_index'];resp_cols.append(r_col)
            pred_cols.update(c for c in src_cols if c!=r_col and c!=src['parameters'].get('trials_index'))
            if item['goal'] not in ('minimize','target','maximize'):
                raise ValueError('Optimization goal must be minimize, target or maximize.')
            if type(item['importance']) not in (int,float) or not math.isfinite(item['importance']) or not .1<=item['importance']<=10:
                raise ValueError('Importance must be between 0.1 and 10.')
            individual_desirability(item['target'],item['goal'],item['lower'],item['target'],item['upper'],item['weight'])
        if len(set(resp_cols))!=len(resp_cols):
            raise ValueError('Duplicate response columns in optimization recipe.')
        if set(resp_cols)&pred_cols:
            raise ValueError('A response column cannot also be a predictor in the optimized models.')
        for c in opts['constraints']:
            if c['index'] not in pred_cols:raise ValueError('Constraint references a non-predictor column.')
        for s in opts['starting_values']:
            if s['index'] not in pred_cols:raise ValueError('Starting value references a non-predictor column.')
        return sorted(set(indices))
    if action in ('factorial_plots','model_contour_plot','model_surface_plot'):
        from .model_plots import SUPPORTED_MODELS,factorial_plots_settings,contour_plot_settings,surface_plot_settings
        source=parameters['model_recipe']
        if not isinstance(source,dict) or source.get('action') not in SUPPORTED_MODELS:
            raise ValueError('Choose a supported source model for model plots.')
        src_cols=columns(source)
        r_col=source['parameters']['response_index']
        pred_cols={c for c in src_cols if c!=r_col and c!=source['parameters'].get('trials_index')}
        if action=='factorial_plots':
            opts=factorial_plots_settings(parameters['options'])
            sel=parameters['selected_indices']
            if sel is not None:
                if not isinstance(sel,list) or not sel or any(type(i) is not int or i not in pred_cols for i in sel) or len(set(sel))!=len(sel):
                    raise ValueError('Select one or more distinct model predictors for Factorial Plots.')
        else:
            opts=contour_plot_settings(parameters['options']) if action=='model_contour_plot' else surface_plot_settings(parameters['options'])
            x_idx,y_idx=parameters['x_index'],parameters['y_index']
            if x_idx is not None or y_idx is not None:
                if type(x_idx) is not int or type(y_idx) is not int or x_idx==y_idx or x_idx not in pred_cols or y_idx not in pred_cols:
                    raise ValueError('Choose two distinct model predictors for X and Y axes.')
        for item in opts.get('hold_values',[]):
            if item['index'] not in pred_cols:
                raise ValueError('Hold value references a non-predictor column.')
        return sorted(set(src_cols))
    if action=='predict_model':
        from .prediction import settings,SUPPORTED
        settings(parameters['options'])
        source=parameters['model_recipe']
        if not isinstance(source,dict) or source.get('action') not in SUPPORTED:
            raise ValueError('Choose a supported source model for prediction.')
        if source['action']=='fit_binary_logistic' and parameters['options']['intervals'] not in ('confidence','none'):
            raise ValueError('Binary logistic predictions support probability confidence intervals, not continuous prediction intervals.')
        indices=columns(source)
        if parameters['input_mode']=='values':
            values=parameters['values']
            if parameters['new_indices'] is not None or not isinstance(values,list) or not 1<=len(values)<=20000:
                raise ValueError('Enter 1–20,000 prediction settings rows.')
            p=source['parameters'];width=len(p['predictor_indices']) if source['action']=='multiple_regression' else len(p['continuous_indices'])+len(p['categorical_indices']) if source['action']=='fit_binary_logistic' else len(p['factor_indices'])+len(p.get('covariate_indices',[]))+int(source['action']=='analyze_response_surface' and p.get('block_index') is not None)
            for row in values:
                if not isinstance(row,list) or len(row)!=width:raise ValueError('Each prediction row needs one value per predictor.')
                for value in row:
                    if value is not None and (isinstance(value,bool) or not isinstance(value,(str,int,float)) or isinstance(value,(int,float)) and not math.isfinite(value)):
                        raise ValueError('Prediction settings must be finite numbers, text or missing values.')
        elif parameters['input_mode']=='columns':
            new=parameters['new_indices'];p=source['parameters'];width=len(p['predictor_indices']) if source['action']=='multiple_regression' else len(p['continuous_indices'])+len(p['categorical_indices']) if source['action']=='fit_binary_logistic' else len(p['factor_indices'])+len(p.get('covariate_indices',[]))+int(source['action']=='analyze_response_surface' and p.get('block_index') is not None)
            if parameters['values'] is not None or not isinstance(new,list) or len(new)!=width or any(type(i) is not int or i<0 for i in new):
                raise ValueError('Select a new-data column for each predictor.')
            indices+=new
        else:raise ValueError('Choose individual values or worksheet columns.')
        return sorted(set(indices))
    if action=='fit_binary_logistic':
        from .logistic import settings
        from .glm import validate_terms
        settings(parameters['options'])
        first,second=parameters['continuous_indices'],parameters['categorical_indices']
        if not isinstance(first,list) or not isinstance(second,list) or not 1<=len(first)+len(second)<=8:
            raise ValueError('Choose 1–8 continuous or categorical predictors.')
        validate_terms(parameters['terms'],len(first)+len(second))
        roles=first+second+[parameters['response_index']]+([] if parameters['trials_index'] is None else [parameters['trials_index']])
        if any(type(i) is not int or i<0 for i in roles) or len(set(roles))!=len(roles):raise ValueError('Choose distinct response, trials and predictor columns.')
        event=parameters['event']
        if event is not None and (type(event) not in (str,int,float) or isinstance(event,(int,float)) and not math.isfinite(event)):
            raise ValueError('Choose a valid binary response event.')
    if action=='gage_rr':
        from .gage_rr import settings
        settings(parameters['options'])
        roles=[parameters[key] for key in ('measurement_index','part_index','operator_index')]
        if any(type(i) is not int or i<0 for i in roles) or len(set(roles))!=3:
            raise ValueError('Choose distinct measurement, part and operator columns.')
    if action=='panel_graph':
        from .panel_graphs import source_columns
        from .compositions import validate_appearance
        validate_appearance(parameters['source_appearance'])
        return source_columns(**{key:parameters[key] for key in ('source_recipe','by_indices','shared_x','shared_y')})
    if action=='analyze_response_surface':
        from .response_surface import validate_terms
        from .glm import settings
        settings(parameters['options']);validate_terms(parameters['terms'],len(parameters['factor_indices']))
        block=parameters.get('block_index')
        if block is not None and (type(block) is not int or block<0 or block in parameters['factor_indices']+[parameters['response_index']]):raise ValueError('Choose a separate block column.')
        if not isinstance(parameters['coding'],list) or len(parameters['coding'])!=len(parameters['factor_indices']):raise ValueError('Invalid response surface coding.')
        from .doe import _coding
        for item in parameters['coding']:
            if not isinstance(item,dict) or set(item)!={'low','high'}:raise ValueError('Invalid response surface factor coding.')
            _coding('',item['low'],item['high'])
    if action=='general_linear_model':
        from .glm import settings,validate_terms
        settings(parameters['options']);validate_terms(parameters['terms'],len(parameters['factor_indices'])+len(parameters['covariate_indices']))
    indices = []
    for key, value in parameters.items():
        if key in ('group_indices','response_indices','indices', 'predictor_indices','factor_indices','covariate_indices','continuous_indices','categorical_indices'):
            if not isinstance(value, list) or not value and key!='group_indices' and not (action=='fit_binary_logistic' and key in ('continuous_indices','categorical_indices')) and not (action=='general_linear_model' and key in ('factor_indices','covariate_indices')) and not (action=='expanded_graph' and parameters.get('method')=='distribution_plot'):
                raise ValueError('Recipe must select at least one column.')
            indices.extend(value)
        elif key=='block_index' and value is None and action=='analyze_response_surface':
            continue
        elif key=='trials_index' and value is None and action=='fit_binary_logistic':
            continue
        elif key=='x_index' and value is None and action=='graph_builder':
            continue
        elif key=='group_index' and value is None and action in ('histogram_graphs','scatter_plot','expanded_graph'):
            continue
        elif key == 'factor2_index' and value is None and action == 'anom':
            continue
        elif action == 'dist_id' and key in ('distributions', 'box_cox_lambda', 'johnson_p_threshold', 'alpha'):
            continue
        elif key.endswith('_index') or key == 'index':
            indices.append(value)
        elif key == 'subgroup_size':
            if type(value) is not int or value < 1:
                raise ValueError('Subgroup size must be at least 1.')
        elif key in ('mu', 'confidence', 'lsl', 'usl', 'target', 'null_proportion', 'null_stdev'):
            if value is None and key in ('lsl', 'usl', 'target'):
                continue
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError('Recipe numeric parameters must be finite.')
    if any(type(i) is not int or i < 0 for i in indices):
        raise ValueError('Recipe column indices must be nonnegative integers.')
    if action=='graph_builder':
        from .graph_builder import validate_mapping
        validate_mapping(**parameters)
    if action=='categorical_points':
        from .categorical_points import validate_display,validate_interval,PLOT_TYPES,VARIANTS
        if parameters['plot_type'] not in PLOT_TYPES or parameters['variant'] not in VARIANTS or parameters['variable_position'] not in ('outer','inner') or parameters['layout'] not in ('combined','panels'):raise ValueError('Unsupported categorical graph settings.')
        validate_display(parameters['display'],parameters['plot_type']);validate_interval(parameters['interval_options'])
        if type(parameters['jitter']) not in (int,float) or not math.isfinite(parameters['jitter']) or not 0<=parameters['jitter']<=.4:raise ValueError('Invalid category jitter.')
        levels=parameters['color_levels']
        if not isinstance(levels,list) or len(levels)>4 or any(type(i) is not int or not 0<=i<len(parameters['group_indices']) for i in levels) or len(set(levels))!=len(levels):raise ValueError('Invalid categorical attribute levels.')
    if action=='dotplot_graphs':
        from .dotplot_graphs import VARIANTS
        if parameters['variant'] not in VARIANTS or parameters['variable_position'] not in ('outer','inner') or parameters['layout'] not in ('combined','panels') or type(parameters['stack']) is not bool:raise ValueError('Unsupported dotplot settings.')
        value=parameters['intervals']
        if value is not None and (type(value) is not int or not 1<=value<=200):raise ValueError('Invalid dot intervals.')
        levels=parameters['color_levels']
        if not isinstance(levels,list) or len(levels)>3 or any(type(i) is not int or not 0<=i<len(parameters['group_indices']) for i in levels) or len(set(levels))!=len(levels):raise ValueError('Invalid dotplot attribute levels.')
    if action=='boxplot_graphs':
        from .boxplot_graphs import VARIANTS,validate_display
        validate_display(parameters['display'])
        if parameters['variant'] not in VARIANTS or parameters['variable_position'] not in ('outer','inner') or parameters['layout'] not in ('combined','panels'):raise ValueError('Unsupported boxplot settings.')
    if action=='histogram_graphs':
        from .histogram_options import validate_histogram_settings
        options=validate_histogram_settings(parameters['settings'])
        if parameters['variant'] not in ('simple','fit','groups','fit_groups') or parameters['layout'] not in ('overlay','panels'):
            raise ValueError('Unsupported histogram variant or arrangement.')
        fitted=parameters['variant'] in ('fit','fit_groups');grouped=parameters['variant'] in ('groups','fit_groups')
        if (options['fit']=='Normal')!=fitted or grouped!=(parameters['group_index'] is not None):raise ValueError('Histogram grouping and fit must match the variant.')
    if action == 'inference' and parameters['method'] not in (
            'one_sample_z', 'one_sample_t', 'two_sample_t', 'paired_t', 'linear_regression', 'one_way_anova'):
        raise ValueError('Unsupported inference method.')
    if action == 'attribute_chart' and parameters['chart'] not in ('P', 'U'):
        raise ValueError('Unsupported attribute chart.')
    if action == 'attribute_control_chart':
        st = parameters.get('settings', {})
        if not isinstance(st, dict):
            raise ValueError('Attribute Control Chart settings must be a dictionary.')
        if st.get('chart_type') not in ('P', 'NP', 'C', 'U', "P'", "U'"):
            raise ValueError('Unsupported attribute control chart type.')
    if action == 'time_weighted_control_chart':
        st = parameters.get('settings', {})
        if not isinstance(st, dict):
            raise ValueError('Time-Weighted Control Chart settings must be a dictionary.')
        ct = str(st.get('chart_type', 'EWMA')).upper()
        if ct not in ('EWMA', 'MA', 'MOVING_AVERAGE', 'CUSUM'):
            raise ValueError('Unsupported time-weighted control chart type.')
        v_indices = st.get('variable_indices')
        if v_indices and isinstance(v_indices, list):
            indices.extend([i for i in v_indices if isinstance(i, int) and i >= 0])
    if action == 'rare_event_control_chart':
        st = parameters.get('settings', {})
        if not isinstance(st, dict):
            raise ValueError('Rare Event Control Chart settings must be a dictionary.')
        ct = str(st.get('chart_type', 'G')).upper()
        if ct not in ('G', 'T'):
            raise ValueError('Unsupported rare event control chart type.')
        v_indices = st.get('variable_indices')
        if v_indices and isinstance(v_indices, list):
            indices.extend([i for i in v_indices if isinstance(i, int) and i >= 0])
    if action == 'multivariate_control_chart':
        st = parameters.get('settings', {})
        if not isinstance(st, dict):
            raise ValueError('Multivariate Control Chart settings must be a dictionary.')
        ct = str(st.get('chart_type', 'TSQUARED')).upper()
        if ct not in ('TSQUARED', 'GENVAR', 'MEWMA'):
            raise ValueError('Unsupported multivariate control chart type.')
        v_indices = st.get('variable_indices')
        if v_indices and isinstance(v_indices, list):
            indices.extend([i for i in v_indices if isinstance(i, int) and i >= 0])
    if action == 'pareto_chart':
        st = parameters.get('settings', {})
        if not isinstance(st, dict):
            raise ValueError('Pareto Chart settings must be a dictionary.')
        v_indices = st.get('variable_indices')
        if v_indices and isinstance(v_indices, list):
            indices.extend([i for i in v_indices if isinstance(i, int) and i >= 0])
    if action == 'type1_gage':
        meas_idx = parameters.get('measurement_index')
        if isinstance(meas_idx, int) and meas_idx >= 0:
            indices.append(meas_idx)
    if action == 'tolerance_intervals':
        st = parameters.get('settings', {})
        if not isinstance(st, dict):
            raise ValueError('Tolerance intervals settings must be a dictionary.')
        v_indices = st.get('variable_indices')
        if v_indices and isinstance(v_indices, list):
            indices.extend([i for i in v_indices if isinstance(i, int) and i >= 0])
    if action in ('sign_test', 'one_sample_wilcoxon', 'runs_test'):
        st = parameters.get('settings', {})
        v_indices = st.get('variable_indices')
        if v_indices and isinstance(v_indices, list):
            indices.extend([i for i in v_indices if isinstance(i, int) and i >= 0])
    if action in ('mann_whitney', 'paired_wilcoxon'):
        st = parameters.get('settings', {})
        for k in ('first_index', 'second_index'):
            idx = st.get(k)
            if isinstance(idx, int) and idx >= 0:
                indices.append(idx)
    if action in ('kruskal_wallis', 'moods_median'):
        st = parameters.get('settings', {})
        for k in ('response_index', 'factor_index'):
            idx = st.get(k)
            if isinstance(idx, int) and idx >= 0:
                indices.append(idx)
    if action in ('pca', 'item_analysis', 'cluster_observations', 'cluster_kmeans', 'cluster_variables'):
        st = parameters.get('settings', {})
        v_indices = st.get('variable_indices')
        if v_indices and isinstance(v_indices, list):
            indices.extend([i for i in v_indices if isinstance(i, int) and i >= 0])
    if action == 'discriminant_analysis':
        st = parameters.get('settings', {})
        g_idx = st.get('group_index')
        if isinstance(g_idx, int) and g_idx >= 0:
            indices.append(g_idx)
        p_indices = st.get('predictor_indices', [])
        if isinstance(p_indices, list):
            indices.extend([i for i in p_indices if isinstance(i, int) and i >= 0])
    if action == 'simple_correspondence':
        st = parameters.get('settings', {})
        c_indices = st.get('column_indices', [])
        if isinstance(c_indices, list):
            indices.extend([i for i in c_indices if isinstance(i, int) and i >= 0])
    if action == 'one_sample_equivalence':
        st = parameters.get('settings', {})
        idx = st.get('sample_index')
        if isinstance(idx, int) and idx >= 0:
            indices.append(idx)
    if action in ('two_sample_equivalence', 'paired_equivalence'):
        st = parameters.get('settings', {})
        for k in ('first_index', 'second_index'):
            idx = st.get(k)
            if isinstance(idx, int) and idx >= 0:
                indices.append(idx)
    if action == 'crossover_equivalence':
        st = parameters.get('settings', {})
        for k in ('response_index', 'sequence_index', 'period_index', 'subject_index', 'treatment_index'):
            idx = st.get(k)
            if isinstance(idx, int) and idx >= 0:
                indices.append(idx)
    if action == 'friedman_test':
        st = parameters.get('settings', {})
        for k in ('response_index', 'treatment_index', 'block_index'):
            idx = st.get(k)
            if isinstance(idx, int) and idx >= 0:
                indices.append(idx)
    if action in ('trend_analysis', 'decomposition', 'moving_average', 'single_exp_smoothing', 'double_exp_smoothing', 'autocorrelation', 'partial_autocorrelation', 'differences', 'lag'):
        st = parameters.get('settings', {})
        idx = st.get('series_index') or st.get('variable_index')
        if isinstance(idx, int) and idx >= 0:
            indices.append(idx)
    if action == 'cross_tabulation':
        st = parameters.get('settings', {})
        for k in ('row_column', 'col_column', 'freq_column'):
            idx = st.get(k)
            if isinstance(idx, int) and idx >= 0:
                indices.append(idx)
    if action == 'chi_square_goodness_of_fit':
        st = parameters.get('settings', {})
        for k in ('observed_column', 'freq_column'):
            idx = st.get(k)
            if isinstance(idx, int) and idx >= 0:
                indices.append(idx)
    if action == 'chi_square_association_table':
        st = parameters.get('settings', {})
        cols = st.get('table_columns', [])
        if isinstance(cols, list):
            indices.extend([i for i in cols if isinstance(i, int) and i >= 0])
        idx = st.get('row_labels_column')
        if isinstance(idx, int) and idx >= 0:
            indices.append(idx)
    if action == 'tally_variables':
        st = parameters.get('settings', {})
        cols = st.get('columns', [])
        if isinstance(cols, list):
            indices.extend([i for i in cols if isinstance(i, int) and i >= 0])
    if action == 'covariance' and parameters['missing'] not in ('Pairwise', 'Listwise'):
        raise ValueError('Unsupported covariance missing-value policy.')
    if action == 'correlation' and (parameters['method'] not in ('Pearson','Spearman') or parameters['missing'] not in ('Pairwise','Listwise')):
        raise ValueError('Unsupported correlation method or missing-value policy.')
    if action == 'one_proportion' and parameters['alternative'] not in ('two-sided','less','greater'):
        raise ValueError('Unsupported alternative hypothesis.')
    if action.startswith('equal_variances_') and parameters['method'] not in ('Levene','Bartlett'):
        raise ValueError('Choose Levene or Bartlett.')
    if action=='expanded_graph':
        from .expanded_graphs import METHODS
        if parameters['method'] not in METHODS:raise ValueError('Unsupported expanded graph recipe.')
        if type(parameters['bins']) is not int or not 1<=parameters['bins']<=100:raise ValueError('Bins must lie between 1 and 100.')
        if parameters['distribution'] not in ('Normal','Uniform','Exponential'):raise ValueError('Unsupported graph distribution.')
        options=parameters['parameters']
        if not isinstance(options,dict) or set(options)-{'mean','stdev','lower','upper','rate'} or any(type(v) not in (int,float) or not math.isfinite(v) for v in options.values()):raise ValueError('Invalid graph distribution parameters.')
    if action == 'multivari':
        r = parameters['response_index']
        f = parameters['factor_indices']
        if type(r) is not int or r < 0 or not isinstance(f, list) or not f or any(type(x) is not int or x < 0 for x in f):
            raise ValueError('Invalid Multi-Vari column indices.')
        return sorted(set([r] + f))
    if action == 'stem_and_leaf':
        v = parameters['index']
        if type(v) is not int or v < 0:
            raise ValueError('Invalid variable index.')
        return [v]
    if action == 'outlier_test':
        v = parameters['variable_index']
        if type(v) is not int or v < 0:
            raise ValueError('Invalid variable index.')
        return [v]
    if action == 'graph':
        if parameters['method'] not in ('histogram', 'scatter', 'boxplot'):
            raise ValueError('Unsupported graph recipe.')
        if type(parameters['bins']) is not int or not 1 <= parameters['bins'] <= 200:
            raise ValueError('Histogram bin count must be from 1 to 200.')
        if len(parameters['indices']) != (2 if parameters['method'] == 'scatter' else 1):
            raise ValueError('Select the required number of graph columns.')
    return sorted(set(indices))


def fingerprints(worksheet, indices):
    records = []
    for index in indices:
        if index >= len(worksheet.columns):
            raise ValueError('A source column is no longer available.')
        column = worksheet.columns[index]
        values = [None if v is None else float(v) for v in column.values] if column.kind == 'number' else column.values
        state=[column.name,column.kind,values]
        if column.kind=='text' and 'value_order' in column.metadata:state.append({'value_order':column.metadata['value_order']})
        raw = json.dumps(state, ensure_ascii=False,
                         allow_nan=False, separators=(',', ':')).encode('utf-8')
        records.append({'index': index, 'sha256': hashlib.sha256(raw).hexdigest()})
    return records


def run(presenter, recipe):
    indices = columns(recipe)
    fingerprints(presenter.worksheet, indices)  # Validate before any calculation/state change.
    action, parameters = recipe['action'], recipe['parameters']
    if action != 'graph':
        return getattr(presenter, action)(**parameters)  # action comes only from the fixed map above.
    from .app import histogram_data, boxplot_data
    selected = [presenter.worksheet.columns[i] for i in parameters['indices']]
    if any(c.kind != 'number' for c in selected):
        raise ValueError('Graph recipes require numeric columns.')
    method = parameters['method']
    xlabel, ylabel = selected[0].name, ''
    if method == 'histogram':
        data = histogram_data(selected[0].values, parameters['bins'])
        ylabel, note = 'Frequency', 'Equal-width bins; missing observations excluded.'
    elif method == 'scatter':
        data = presenter.worksheet.complete_rows(parameters['indices'])
        if not data:
            raise ValueError('A scatterplot needs at least one complete pair.')
        ylabel, note = selected[1].name, 'Complete pairs only; no fitted line.'
    else:
        data = boxplot_data(selected[0].values)
        note = 'Clamped (n+1)p quartiles; 1.5 IQR whiskers. Native equivalence unverified.'
    source={}
    if method=='scatter':source['plot_rows']=[row+1 for row in range(presenter.worksheet.row_count) if all(row<len(column.values) and column.values[row] is not None for column in selected)]
    if method=='histogram':
        observations=[v for v in selected[0].values if v is not None]
        if len(observations)<=100000:source['histogram_source']=observations
    return presenter._record(method.title() + ' of ' + xlabel, {
        'graph': method, 'graph_data': data, 'xlabel': xlabel, 'ylabel': ylabel,
        'variables': [c.name for c in selected], 'convention': note,**source}, recipe=recipe)
