"""Schema-defined source bindings; statistical constants are never column indices."""
import copy
import math

KEY = '_source_bindings'
ACTIONS = frozenset({'normal_capability', 'normal_sixpack', 'acceptance_control_chart', 'capability_nonnormal', 'capability_nonparametric', 'capability_automated', 'reliability_distribution', 'imr_chart',
    'attribute_control_chart', 'time_weighted_control_chart',
    'rare_event_control_chart', 'multivariate_control_chart',
    'pareto_chart', 'tolerance_intervals', 'trend_analysis', 'decomposition', 'moving_average', 'single_exp_smoothing', 'double_exp_smoothing', 'winters_method', 'autocorrelation', 'partial_autocorrelation', 'differences', 'lag', 'sign_test', 'one_sample_wilcoxon', 'mann_whitney', 'kruskal_wallis', 'moods_median', 'friedman_test', 'runs_test', 'paired_wilcoxon', 'pca', 'item_analysis', 'cluster_observations', 'cluster_kmeans', 'cluster_variables', 'discriminant_analysis', 'simple_correspondence', 'one_sample_equivalence', 'two_sample_equivalence', 'paired_equivalence', 'crossover_equivalence', 'one_sample_z_power', 'one_sample_t_power', 'two_sample_t_power', 'paired_t_power', 'one_proportion_power', 'two_proportions_power', 'oneway_anova_power', 'factorial_power', 'cross_tabulation', 'chi_square_goodness_of_fit', 'chi_square_association_table', 'tally_variables'})


def _constant(value):
    if isinstance(value, bool) or value is None or isinstance(value, (list, dict)):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _preferred(settings, index_key, name_key):
    value = settings.get(index_key)
    return settings.get(name_key) if value is None else value


def _plan(action, settings):
    """Active selector roles: (reference, is_list, allowed kinds)."""
    number, any_kind = ('number',), ('number', 'text', 'date')
    roles = {}
    if action in ('normal_capability', 'normal_sixpack', 'acceptance_control_chart', 'capability_nonnormal', 'capability_nonparametric', 'capability_automated'):
        if settings.get('single_column', True):
            roles['column_name'] = (_preferred(settings, 'column_index', 'column_name'), False, number)
            sub = settings.get('subgroup_spec', 1)
            if settings.get('subgroup_col_index') is not None or (isinstance(sub, str) and not _constant(sub)):
                roles['subgroup_spec'] = (_preferred(settings, 'subgroup_col_index', 'subgroup_spec'), False, any_kind)
        else:
            roles['cols_across'] = (_preferred(settings, 'cols_across_indices', 'cols_across'), True, number)
    elif action == 'reliability_distribution':
        reference = _preferred(settings, 'column_index', 'column_name')
        if reference is None:
            reference = settings.get('variable_index')
        roles['column_name'] = (reference, False, number)
        censor = _preferred(settings, 'censor_index', 'censor_name')
        if censor is not None and censor != '':
            roles['censor_index'] = (censor, False, ('number', 'text'))
    elif action in ('imr_chart', 'attribute_control_chart'):
        roles['variables'] = (settings.get('variables', []), True, number)
        if action == 'attribute_control_chart' and settings.get('is_subgroup_col', False):
            roles['subgroup_col_idx'] = (settings.get('subgroup_col_idx'), False, number)
    elif action in ('time_weighted_control_chart', 'rare_event_control_chart'):
        allowed = any_kind if action == 'rare_event_control_chart' and settings.get('form_of_data', 1) == 0 else number
        roles['columns'] = (settings.get('columns', settings.get('variable_indices')), True, allowed)
        if action == 'time_weighted_control_chart' and settings.get('arranged_mode', 0) == 0:
            sub = settings.get('subgroup_text')
            if 'subgroup_text' in (settings.get(KEY) or {}) or (sub is not None and str(sub).strip() and not _constant(sub)):
                roles['subgroup_text'] = (sub, False, any_kind)
            elif isinstance(settings.get('subgroup_spec'), list):
                raise ValueError('Subgroup data require a bound source column, not saved values.')
    elif action == 'multivariate_control_chart':
        values = settings.get('variables') or settings.get('columns', [])
        roles['variables'] = (values if values else settings.get('variable_indices'), True, number)
        sub = settings.get('subgroup_size', 1)
        if 'subgroup_size' in (settings.get(KEY) or {}) or (isinstance(sub, str) and not _constant(sub)):
            roles['subgroup_size'] = (sub, False, any_kind)
    elif action == 'pareto_chart':
        roles['defect_column'] = (settings.get('defect_column'), False, any_kind)
        if settings.get('is_summarized', False):
            roles['count_column'] = (settings.get('count_column'), False, number)
        if settings.get('by_column') is not None and settings.get('by_column') != '':
            roles['by_column'] = (settings['by_column'], False, any_kind)
    elif action == 'tolerance_intervals' and not settings.get('is_summarized', False):
        roles['variable_indices'] = (settings.get('variable_indices', []), True, number)
    elif action in ('trend_analysis', 'decomposition', 'moving_average', 'single_exp_smoothing', 'double_exp_smoothing', 'winters_method', 'autocorrelation', 'partial_autocorrelation', 'differences', 'lag'):
        roles['series_index'] = (_preferred(settings, 'series_index', 'series_name'), False, number)
    elif action in ('sign_test', 'one_sample_wilcoxon', 'runs_test'):
        roles['variable_indices'] = (settings.get('variable_indices', []), True, number)
    elif action in ('mann_whitney', 'paired_wilcoxon'):
        roles['first_index'] = (settings.get('first_index'), False, number)
        roles['second_index'] = (settings.get('second_index'), False, number)
    elif action in ('kruskal_wallis', 'moods_median'):
        roles['response_index'] = (settings.get('response_index'), False, number)
        roles['factor_index'] = (settings.get('factor_index'), False, any_kind)
    elif action == 'friedman_test':
        roles['response_index'] = (settings.get('response_index'), False, number)
        roles['treatment_index'] = (settings.get('treatment_index'), False, any_kind)
        roles['block_index'] = (settings.get('block_index'), False, any_kind)
    elif action in ('pca', 'item_analysis', 'cluster_observations', 'cluster_kmeans', 'cluster_variables'):
        roles['variable_indices'] = (settings.get('variable_indices', []), True, number)
    elif action == 'discriminant_analysis':
        roles['group_index'] = (settings.get('group_index'), False, any_kind)
        roles['predictor_indices'] = (settings.get('predictor_indices', []), True, number)
    elif action == 'simple_correspondence':
        roles['column_indices'] = (settings.get('column_indices', []), True, number)
    elif action == 'one_sample_equivalence':
        roles['sample_index'] = (settings.get('sample_index'), False, number)
    elif action in ('two_sample_equivalence', 'paired_equivalence'):
        roles['first_index'] = (settings.get('first_index'), False, number)
        roles['second_index'] = (settings.get('second_index'), False, number)
    elif action == 'crossover_equivalence':
        roles['response_index'] = (settings.get('response_index'), False, number)
        roles['sequence_index'] = (settings.get('sequence_index'), False, any_kind)
        roles['period_index'] = (settings.get('period_index'), False, any_kind)
        roles['subject_index'] = (settings.get('subject_index'), False, any_kind)
        roles['treatment_index'] = (settings.get('treatment_index'), False, any_kind)
    elif action == 'cross_tabulation':
        roles['row_column'] = (settings.get('row_column'), False, any_kind)
        roles['col_column'] = (settings.get('col_column'), False, any_kind)
        if settings.get('freq_column') is not None:
            roles['freq_column'] = (settings.get('freq_column'), False, number)
    elif action == 'chi_square_goodness_of_fit':
        roles['observed_column'] = (settings.get('observed_column'), False, any_kind)
        if settings.get('freq_column') is not None:
            roles['freq_column'] = (settings.get('freq_column'), False, number)
    elif action == 'chi_square_association_table':
        roles['table_columns'] = (settings.get('table_columns', []), True, number)
        if settings.get('row_labels_column') is not None:
            roles['row_labels_column'] = (settings.get('row_labels_column'), False, any_kind)
    elif action == 'tally_variables':
        roles['columns'] = (settings.get('columns', []), True, any_kind)
    return roles


def _index(value, worksheet, kinds):
    if type(value) is int:
        index = value
        if not 0 <= index < len(worksheet.columns):
            raise ValueError('A bound source column no longer exists.')
    elif isinstance(value, str):
        matches = [i for i, column in enumerate(worksheet.columns) if column.name == value]
        if len(matches) > 1:
            raise ValueError('Source column name is ambiguous: ' + value)
        if matches:
            index = matches[0]
        elif value.upper().startswith('C') and value[1:].isdigit():
            index = int(value[1:]) - 1
            if not 0 <= index < len(worksheet.columns):
                raise ValueError('Source column was not found: ' + value)
        else:
            raise ValueError('Source column was not found: ' + value)
    else:
        raise ValueError('A source column must be an index or an unambiguous name.')
    if worksheet.columns[index].kind not in kinds:
        raise ValueError('Source column has an unsupported data type.')
    return index


def _validate_binding(value, many):
    values = value if many else [value]
    if many and (not isinstance(values, list) or not values):
        raise ValueError('Select at least one source column.')
    if any(type(index) is not int or index < 0 for index in values):
        raise ValueError('Invalid saved source-column binding.')
    if len(values) != len(set(values)):
        raise ValueError('Select distinct source columns.')
    return values


def normalize(action, worksheet, settings):
    """Bind newly entered settings. Existing bindings remain authoritative."""
    if action not in ACTIONS or not isinstance(settings, dict):
        raise ValueError('Unsupported settings-based analysis.')
    result = copy.deepcopy(settings)
    if KEY not in result:
        bindings = {}
        for role, (reference, many, kinds) in _plan(action, result).items():
            if many:
                if not isinstance(reference, (list, tuple)) or not reference:
                    raise ValueError('Select at least one source column.')
                bindings[role] = [_index(value, worksheet, kinds) for value in reference]
            else:
                bindings[role] = _index(reference, worksheet, kinds)
        result[KEY] = bindings
    return resolve(action, worksheet, result)


def binding_columns(action, settings):
    """Dependencies from selectors. Legacy names need verified migration."""
    if action not in ACTIONS:
        return None
    if not isinstance(settings, dict):
        raise ValueError('Analysis settings must be an object.')
    plan = _plan(action, settings)
    bindings = settings.get(KEY)
    if KEY in settings:
        if not isinstance(bindings, dict) or set(bindings) != set(plan):
            raise ValueError('Saved bindings do not match the active data arrangement.')
        values = []
        for role, (_, many, _) in plan.items():
            values.extend(_validate_binding(bindings[role], many))
        return sorted(set(values))
    values = []
    for _, (reference, many, _) in plan.items():
        values.extend(_validate_binding(reference, many))
    return sorted(set(values))


def _name(worksheet, index):
    name = worksheet.columns[index].name
    if not name or sum(column.name == name for column in worksheet.columns) != 1:
        raise ValueError('This analysis requires uniquely named source columns.')
    return name


def resolve(action, worksheet, settings):
    """Refresh execution selectors from verified indices, never stale names."""
    if action not in ACTIONS or not isinstance(settings, dict) or KEY not in settings:
        raise ValueError('Analysis has no verified source bindings. Select its columns again.')
    result = copy.deepcopy(settings)
    binding_columns(action, result)
    bindings = result[KEY]
    for role, (_, many, kinds) in _plan(action, result).items():
        for index in _validate_binding(bindings[role], many):
            _index(index, worksheet, kinds)
    if action in ('normal_capability', 'normal_sixpack', 'acceptance_control_chart', 'capability_nonnormal', 'capability_nonparametric', 'capability_automated'):
        if 'column_name' in bindings:
            i = bindings['column_name']
            result['column_name'] = i
            result['column_index'] = i
        if 'subgroup_spec' in bindings:
            i = bindings['subgroup_spec']
            result['subgroup_spec'] = _name(worksheet, i)
            result['subgroup_col_index'] = i
        if 'cols_across' in bindings:
            result['cols_across'] = [_name(worksheet, i) for i in bindings['cols_across']]
            result['cols_across_indices'] = list(bindings['cols_across'])
    elif action == 'reliability_distribution':
        result['column_index'] = bindings['column_name']
        result['variable_index'] = bindings['column_name']
        result['column_name'] = worksheet.columns[bindings['column_name']].name
        if 'censor_index' in bindings:
            result['censor_index'] = bindings['censor_index']
            result['censor_name'] = worksheet.columns[bindings['censor_index']].name
    elif action in ('imr_chart', 'attribute_control_chart'):
        result['variables'] = list(bindings['variables'])
        if 'subgroup_col_idx' in bindings:
            result['subgroup_col_idx'] = bindings['subgroup_col_idx']
    elif action in ('time_weighted_control_chart', 'rare_event_control_chart'):
        result['columns'] = [_name(worksheet, i) for i in bindings['columns']]
        result['variable_indices'] = list(bindings['columns'])
        if 'subgroup_text' in bindings:
            i = bindings['subgroup_text']
            result['subgroup_text'] = _name(worksheet, i)
            result['subgroup_spec'] = list(worksheet.columns[i].values)
    elif action == 'multivariate_control_chart':
        names = [_name(worksheet, i) for i in bindings['variables']]
        result.update(variables=names, columns=list(names), variable_names=list(names), variable_indices=list(bindings['variables']))
        if 'subgroup_size' in bindings:
            result['subgroup_size'] = _name(worksheet, bindings['subgroup_size'])
    elif action == 'pareto_chart':
        for role, index in bindings.items():
            result[role] = index
    elif action == 'tolerance_intervals' and 'variable_indices' in bindings:
        result['variable_indices'] = list(bindings['variable_indices'])
    elif action in ('trend_analysis', 'decomposition', 'moving_average', 'single_exp_smoothing', 'double_exp_smoothing', 'winters_method', 'autocorrelation', 'partial_autocorrelation', 'differences', 'lag') and 'series_index' in bindings:
        result['series_index'] = bindings['series_index']
        result['series_name'] = worksheet.columns[bindings['series_index']].name
    elif action in ('sign_test', 'one_sample_wilcoxon', 'runs_test') and 'variable_indices' in bindings:
        result['variable_indices'] = list(bindings['variable_indices'])
    elif action in ('mann_whitney', 'paired_wilcoxon'):
        for role in ('first_index', 'second_index'):
            if role in bindings:
                result[role] = bindings[role]
    elif action in ('kruskal_wallis', 'moods_median'):
        for role in ('response_index', 'factor_index'):
            if role in bindings:
                result[role] = bindings[role]
    elif action == 'friedman_test':
        for role in ('response_index', 'treatment_index', 'block_index'):
            if role in bindings:
                result[role] = bindings[role]
    elif action in ('pca', 'item_analysis', 'cluster_observations', 'cluster_kmeans', 'cluster_variables') and 'variable_indices' in bindings:
        result['variable_indices'] = list(bindings['variable_indices'])
    elif action == 'discriminant_analysis':
        if 'group_index' in bindings:
            result['group_index'] = bindings['group_index']
        if 'predictor_indices' in bindings:
            result['predictor_indices'] = list(bindings['predictor_indices'])
    elif action == 'simple_correspondence' and 'column_indices' in bindings:
        result['column_indices'] = list(bindings['column_indices'])
    elif action == 'one_sample_equivalence' and 'sample_index' in bindings:
        result['sample_index'] = bindings['sample_index']
    elif action in ('two_sample_equivalence', 'paired_equivalence'):
        for role in ('first_index', 'second_index'):
            if role in bindings:
                result[role] = bindings[role]
    elif action == 'crossover_equivalence':
        for role in ('response_index', 'sequence_index', 'period_index', 'subject_index', 'treatment_index'):
            if role in bindings:
                result[role] = bindings[role]
    elif action == 'cross_tabulation':
        for role in ('row_column', 'col_column', 'freq_column'):
            if role in bindings:
                result[role] = bindings[role]
    elif action == 'chi_square_goodness_of_fit':
        for role in ('observed_column', 'freq_column'):
            if role in bindings:
                result[role] = bindings[role]
    elif action == 'chi_square_association_table':
        if 'table_columns' in bindings:
            result['table_columns'] = list(bindings['table_columns'])
        if 'row_labels_column' in bindings:
            result['row_labels_column'] = bindings['row_labels_column']
    elif action == 'tally_variables':
        if 'columns' in bindings:
            result['columns'] = list(bindings['columns'])
    return result


def remap_settings(action, settings, mapping):
    """Move declared selectors only, preserving statistical constants."""
    result = copy.deepcopy(settings)
    binding_columns(action, result)
    plan = _plan(action, result)
    bindings = result.get(KEY)
    if bindings is None:
        bindings = {role: copy.deepcopy(reference) for role, (reference, _, _) in plan.items()}
    updated = {}
    for role, (_, many, _) in plan.items():
        mapped = [mapping[index] for index in _validate_binding(bindings[role], many)]
        updated[role] = mapped if many else mapped[0]
    result[KEY] = updated
    if action in ('normal_capability', 'normal_sixpack', 'acceptance_control_chart', 'capability_nonnormal', 'capability_nonparametric', 'capability_automated'):
        if 'column_name' in updated:
            result['column_index'] = updated['column_name']
            if type(result.get('column_name')) is int:
                result['column_name'] = updated['column_name']
        if 'subgroup_spec' in updated:
            result['subgroup_col_index'] = updated['subgroup_spec']
        if 'cols_across' in updated:
            result['cols_across_indices'] = list(updated['cols_across'])
    elif action == 'reliability_distribution':
        result['column_index'] = updated['column_name']
        result['variable_index'] = updated['column_name']
        if 'censor_index' in updated:
            result['censor_index'] = updated['censor_index']
    elif action in ('imr_chart', 'attribute_control_chart'):
        result['variables'] = list(updated['variables'])
        if 'subgroup_col_idx' in updated:
            result['subgroup_col_idx'] = updated['subgroup_col_idx']
    elif action in ('time_weighted_control_chart', 'rare_event_control_chart'):
        result['variable_indices'] = list(updated['columns'])
    elif action == 'multivariate_control_chart':
        result['variable_indices'] = list(updated['variables'])
    elif action == 'tolerance_intervals' and 'variable_indices' in updated:
        result['variable_indices'] = list(updated['variable_indices'])
    elif action == 'cross_tabulation':
        for role in ('row_column', 'col_column', 'freq_column'):
            if role in updated:
                result[role] = updated[role]
    elif action == 'chi_square_goodness_of_fit':
        for role in ('observed_column', 'freq_column'):
            if role in updated:
                result[role] = updated[role]
    elif action == 'chi_square_association_table':
        if 'table_columns' in updated:
            result['table_columns'] = list(updated['table_columns'])
        if 'row_labels_column' in updated:
            result['row_labels_column'] = updated['row_labels_column']
    elif action == 'tally_variables':
        if 'columns' in updated:
            result['columns'] = list(updated['columns'])
    binding_columns(action, result)
    return result

# Earlier Gemini inference dialogs use numeric selectors nested under settings.
# Their own analysis engines already execute indices, so no name binding is needed.
NUMERIC_ACTIONS = frozenset({'one_sample_t', 'one_sample_z', 'one_sample_proportion',
    'one_sample_poisson', 'paired_t', 'two_sample_t', 'two_sample_proportion',
    'two_sample_poisson', 'one_variance', 'two_variances'})


def _numeric_roles(action, settings):
    fields = []
    if action in ('one_sample_t', 'one_sample_z', 'one_sample_proportion', 'one_sample_poisson'):
        if settings.get('data_format', 0) == 0:
            fields = [('sample_cols', True), ('freq_cols', True)]
    elif action == 'paired_t':
        if settings.get('data_format', 1) == 1:
            fields = [('sample1_col', False), ('sample2_col', False)]
    elif action in ('two_sample_t', 'two_sample_proportion', 'two_sample_poisson'):
        mode = settings.get('data_format', 1)
        if mode == 0:
            fields = [('samples_col', False), ('sample_ids_col', False)]
            if action == 'two_sample_poisson':
                fields += [('length_col', False), ('freq_col', False)]
        elif mode == 1:
            fields = [('sample1_col', False), ('sample2_col', False)]
            if action == 'two_sample_poisson':
                fields += [('length1_col', False), ('length2_col', False), ('freq_cols', True)]
    elif action == 'one_variance' and settings.get('mode', 0) == 0:
        fields = [('columns', True)]
    elif action == 'two_variances':
        mode = settings.get('mode', 1)
        if mode == 0:
            fields = [('samples_col', False), ('subscripts_col', False)]
        elif mode == 1:
            fields = [('s1_col', False), ('s2_col', False)]
    return fields


def remap_numeric_settings(action, settings, mapping):
    """Remap active inference inputs, leaving summarized values and defaults alone."""
    result = copy.deepcopy(settings)
    for key, many in _numeric_roles(action, result):
        value = result.get(key)
        if value is None:
            continue
        if many:
            if not isinstance(value, list):
                raise ValueError('Invalid source column list.')
            result[key] = [mapping[index] if type(index) is int and index >= 0 else index for index in value]
        elif type(value) is int and value >= 0:
            result[key] = mapping[value]
    return result
