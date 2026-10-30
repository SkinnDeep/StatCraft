"""Model-driven Factorial Plots (Main Effects & Interaction), Contour Plot and Surface Plot.

Scope: existing continuous OLS (`multiple_regression`), fixed GLM (`general_linear_model`),
two-level factorial (`analyze_factorial`, `analyze_factorial_terms`), response-surface
(`analyze_response_surface`) and binary logistic (`fit_binary_logistic`) recipes on the
active worksheet.
Native-product numerical equivalence is unverified.
"""
import copy
import itertools
import math
import numpy as np
from .model import finite_number
from .optimizer import (
    SUPPORTED_MODELS,
    MODEL_TITLES,
    normalize_model_recipe,
    _fit_model_bundle,
    _predict_bundle_rows,
    _finite_result,
)

HOLD_CONTINUOUS_MODES = ('mean', 'min', 'max', 'custom')
HOLD_CATEGORICAL_MODES = ('first', 'last', 'custom')
CONTOUR_GRID_SIZE = 41
SURFACE_GRID_SIZE = 25
MAX_PAIR_PANELS = 6

FACTORIAL_PLOT_DEFAULTS = dict(
    terms_to_display='model',
    show_main_effects=True,
    show_interaction_plot=True,
    matrix_display='lower_left',
    hold_continuous='mean',
    hold_categorical='first',
    hold_values=[],
    title='',
)

CONTOUR_PLOT_DEFAULTS = dict(
    pair_mode='single',
    level_mode='auto',
    level_count=7,
    custom_levels=[],
    show_area=True,
    show_lines=True,
    show_design_points=False,
    hold_continuous='mean',
    hold_categorical='first',
    hold_values=[],
    title='',
)

SURFACE_PLOT_DEFAULTS = dict(
    pair_mode='single',
    surface_style='shaded',
    hold_continuous='mean',
    hold_categorical='first',
    hold_values=[],
    title='',
)


def _normalize_hold_values(items):
    if not isinstance(items, list):
        raise ValueError('Hold values must be a list of predictor setting objects.')
    seen = set()
    out = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {'index', 'value'}:
            raise ValueError('Each hold value entry must specify index and value.')
        idx = item['index']
        val = item['value']
        if type(idx) is not int or idx < 0:
            raise ValueError('Hold value column index must be a nonnegative integer.')
        if idx in seen:
            raise ValueError(f'Duplicate hold value entry for column index {idx}.')
        seen.add(idx)
        if val is None or isinstance(val, bool) or not isinstance(val, (str, int, float)):
            raise ValueError('Hold value must be a finite number or factor level.')
        if isinstance(val, (int, float)):
            val = finite_number(val)
        out.append(dict(index=idx, value=val))
    return out


def factorial_plots_settings(options=None):
    if options is None:
        return copy.deepcopy(FACTORIAL_PLOT_DEFAULTS)
    if not isinstance(options, dict) or not set(options).issubset(FACTORIAL_PLOT_DEFAULTS):
        raise ValueError('Unsupported factorial plots options.')
    o = copy.deepcopy(FACTORIAL_PLOT_DEFAULTS)
    o.update(copy.deepcopy(options))
    if o['terms_to_display'] not in ('model', 'all'):
        raise ValueError('Terms to display must be model or all.')
    if type(o['show_main_effects']) is not bool or type(o['show_interaction_plot']) is not bool:
        raise ValueError('Choose valid factorial plots graph checkboxes.')
    if not o['show_main_effects'] and not o['show_interaction_plot']:
        raise ValueError('Select at least one graph (Main effects plot or Interaction plot).')
    if o['matrix_display'] not in ('lower_left', 'full'):
        raise ValueError('Interaction matrix display must be lower_left or full.')
    if o['hold_continuous'] not in HOLD_CONTINUOUS_MODES:
        raise ValueError('Hold continuous variables mode must be mean, min, max or custom.')
    if o['hold_categorical'] not in HOLD_CATEGORICAL_MODES:
        raise ValueError('Hold categorical variables mode must be first, last or custom.')
    o['hold_values'] = _normalize_hold_values(o['hold_values'])
    if not isinstance(o['title'], str) or len(o['title']) > 240:
        raise ValueError('Custom title must be a string up to 240 characters.')
    o['title'] = o['title'].strip()
    return o


def contour_plot_settings(options=None):
    if options is None:
        return copy.deepcopy(CONTOUR_PLOT_DEFAULTS)
    if not isinstance(options, dict) or not set(options).issubset(CONTOUR_PLOT_DEFAULTS):
        raise ValueError('Unsupported model contour plot options.')
    o = copy.deepcopy(CONTOUR_PLOT_DEFAULTS)
    o.update(copy.deepcopy(options))
    if o['pair_mode'] not in ('single', 'all'):
        raise ValueError('Contour plot variable mode must be single or all.')
    if o['level_mode'] not in ('auto', 'number', 'values'):
        raise ValueError('Contour level mode must be auto, number or values.')
    if type(o['level_count']) is not int or not 2 <= o['level_count'] <= 20:
        raise ValueError('Number of contour levels must be an integer from 2 to 20.')
    if not isinstance(o['custom_levels'], list):
        raise ValueError('Custom contour levels must be a list of numbers.')
    vals = []
    for v in o['custom_levels']:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError('Custom contour levels must be finite numbers.')
        vals.append(finite_number(v))
    if o['level_mode'] == 'values':
        if not 2 <= len(vals) <= 20:
            raise ValueError('Enter 2 to 20 custom contour levels.')
        if any(vals[i] >= vals[i + 1] for i in range(len(vals) - 1)):
            raise ValueError('Custom contour levels must be in strictly increasing order.')
    o['custom_levels'] = vals
    for key in ('show_area', 'show_lines', 'show_design_points'):
        if type(o[key]) is not bool:
            raise ValueError('Choose valid contour display checkboxes.')
    if not o['show_area'] and not o['show_lines']:
        raise ValueError('Select Area, Contour lines, or both for contour display.')
    if o['hold_continuous'] not in HOLD_CONTINUOUS_MODES:
        raise ValueError('Hold continuous variables mode must be mean, min, max or custom.')
    if o['hold_categorical'] not in HOLD_CATEGORICAL_MODES:
        raise ValueError('Hold categorical variables mode must be first, last or custom.')
    o['hold_values'] = _normalize_hold_values(o['hold_values'])
    if not isinstance(o['title'], str) or len(o['title']) > 240:
        raise ValueError('Custom title must be a string up to 240 characters.')
    o['title'] = o['title'].strip()
    return o


def surface_plot_settings(options=None):
    if options is None:
        return copy.deepcopy(SURFACE_PLOT_DEFAULTS)
    if not isinstance(options, dict) or not set(options).issubset(SURFACE_PLOT_DEFAULTS):
        raise ValueError('Unsupported model surface plot options.')
    o = copy.deepcopy(SURFACE_PLOT_DEFAULTS)
    o.update(copy.deepcopy(options))
    if o['pair_mode'] not in ('single', 'all'):
        raise ValueError('Surface plot variable mode must be single or all.')
    if o['surface_style'] not in ('shaded', 'wireframe'):
        raise ValueError('Surface style must be shaded or wireframe.')
    if o['hold_continuous'] not in HOLD_CONTINUOUS_MODES:
        raise ValueError('Hold continuous variables mode must be mean, min, max or custom.')
    if o['hold_categorical'] not in HOLD_CATEGORICAL_MODES:
        raise ValueError('Hold categorical variables mode must be first, last or custom.')
    o['hold_values'] = _normalize_hold_values(o['hold_values'])
    if not isinstance(o['title'], str) or len(o['title']) > 240:
        raise ValueError('Custom title must be a string up to 240 characters.')
    o['title'] = o['title'].strip()
    return o


def discover_models(worksheet, history, family=None, require_two_continuous=False):
    """Discover valid fitted models on the active worksheet for Factorial/Contour/Surface plots."""
    family_map = {
        'regression': ('multiple_regression',),
        'glm': ('general_linear_model',),
        'response_surface': ('analyze_response_surface',),
        'logistic': ('fit_binary_logistic',),
        'factorial': ('analyze_factorial', 'analyze_factorial_terms'),
    }
    allowed_actions = family_map.get(family)
    found = []
    seen_recipes = []
    for entry in history:
        if not isinstance(entry, dict) or entry.get('source_unavailable'):
            continue
        from .native_mpx_models import resolve_entry_recipe
        raw_recipe = resolve_entry_recipe(entry, worksheet)
        if not isinstance(raw_recipe, dict):
            continue
        act = raw_recipe.get('action')
        candidates = []
        if act in ('predict_model', 'factorial_plots', 'model_contour_plot', 'model_surface_plot'):
            candidates.append(raw_recipe.get('parameters', {}).get('model_recipe'))
        elif act == 'optimize_responses':
            for r_item in raw_recipe.get('parameters', {}).get('responses', []):
                if isinstance(r_item, dict):
                    candidates.append(r_item.get('model_recipe'))
        else:
            candidates.append(raw_recipe)
        for cand in candidates:
            try:
                recipe = normalize_model_recipe(cand)
                if allowed_actions and recipe['action'] not in allowed_actions:
                    continue
                if recipe in seen_recipes:
                    continue
                bundle = _fit_model_bundle(worksheet, recipe)
            except (ValueError, TypeError, KeyError, IndexError, ArithmeticError):
                continue
            cont_count = sum(1 for p in bundle['predictors'] if p['role'] == 'covariate')
            if require_two_continuous and cont_count < 2:
                continue
            seen_recipes.append(recipe)
            found.append(dict(
                entry=entry,
                recipe=recipe,
                bundle=bundle,
                response_index=bundle['response_index'],
                response_name=bundle['response_name'],
                model_title=bundle['model_title'],
                continuous_count=cont_count,
            ))
    return found


def resolve_hold_settings(worksheet, bundle, hold_continuous='mean', hold_categorical='first', hold_values=None):
    """Compute baseline hold values for every predictor in bundle."""
    preds = bundle['predictors']
    pred_by_idx = {p['index']: p for p in preds}
    custom_map = {}
    for item in _normalize_hold_values(hold_values or []):
        idx = item['index']
        if idx not in pred_by_idx:
            raise ValueError('Hold value references a column that is not a predictor in the selected model.')
        p = pred_by_idx[idx]
        val = item['value']
        if p['role'] == 'factor':
            if val not in p['levels']:
                raise ValueError(f"Hold value for {p['name']} must be an observed factor level.")
            custom_map[idx] = val
        else:
            if isinstance(val, str):
                raise ValueError(f"Hold value for continuous predictor {p['name']} must be numeric.")
            custom_map[idx] = finite_number(val)

    source_rows = bundle['result']['row_indices']
    is_coded_doe = bundle['action'] in ('analyze_response_surface', 'analyze_factorial', 'analyze_factorial_terms')
    hold_row = []
    hold_summary = []
    for p in preds:
        idx = p['index']
        if idx in custom_map:
            val = custom_map[idx]
            rule = 'custom'
        elif p['role'] == 'factor':
            val = p['levels'][0] if hold_categorical != 'last' else p['levels'][-1]
            rule = hold_categorical
        else:
            if hold_continuous == 'min':
                val = float(p['min'])
            elif hold_continuous == 'max':
                val = float(p['max'])
            elif is_coded_doe:
                val = 0.5 * (float(p['min']) + float(p['max']))
            else:
                vals = [float(worksheet.columns[idx].values[r]) for r in source_rows]
                val = math.fsum(vals) / len(vals)
            rule = hold_continuous
        hold_row.append(val)
        hold_summary.append(dict(
            index=idx,
            name=p['name'],
            role=p['role'],
            value=val,
            rule=rule,
        ))
    return hold_row, hold_summary


def _model_term_sets(bundle):
    """Return (active_main_positions, active_pair_positions) in the fitted model."""
    k = len(bundle['predictors'])
    if bundle['action'] == 'multiple_regression':
        return set(range(k)), set()
    raw_terms = bundle['result'].get('terms', [])
    main_pos = set()
    pair_pos = set()
    for term in raw_terms:
        if not isinstance(term, (list, tuple)):
            continue
        distinct = sorted(set(int(i) for i in term if isinstance(i, int) and 0 <= i < k))
        if len(distinct) == 1:
            main_pos.add(distinct[0])
        elif len(distinct) >= 2:
            main_pos.update(distinct)
            for a, b in itertools.combinations(distinct, 2):
                pair_pos.add((a, b))
    if not main_pos:
        main_pos = set(range(k))
    return main_pos, pair_pos


def _has_curvature(bundle, pos):
    """Return True if predictor at position `pos` has a quadratic term or non-identity link."""
    if bundle['action'] == 'fit_binary_logistic':
        return True
    for term in bundle['result'].get('terms', []):
        if isinstance(term, (list, tuple)) and list(term).count(pos) >= 2:
            return True
    return False


def factorial_plots(worksheet, model_recipe, selected_indices=None, options=None):
    """Compute Main Effects and Interaction Plots for a fitted model on the active worksheet."""
    o = factorial_plots_settings(options)
    recipe = normalize_model_recipe(model_recipe)
    bundle = _fit_model_bundle(worksheet, recipe)
    preds = bundle['predictors']
    pred_indices = [p['index'] for p in preds]
    pos_by_idx = {p['index']: j for j, p in enumerate(preds)}

    if selected_indices is None:
        sel = list(pred_indices)
    else:
        if (not isinstance(selected_indices, list) or not 1 <= len(selected_indices) <= len(preds)
                or len(set(selected_indices)) != len(selected_indices)
                or any(type(i) is not int or i not in pos_by_idx for i in selected_indices)):
            raise ValueError('Select 1 to 8 distinct model predictor variables for Factorial Plots.')
        sel = list(selected_indices)

    if o['show_interaction_plot'] and not o['show_main_effects'] and len(sel) < 2:
        raise ValueError('Select at least two model variables to display an interaction plot.')

    hold_row, hold_summary = resolve_hold_settings(
        worksheet, bundle, o['hold_continuous'], o['hold_categorical'], o['hold_values']
    )
    model_mains, model_pairs = _model_term_sets(bundle)
    sel_positions = [pos_by_idx[idx] for idx in sel]

    if o['terms_to_display'] == 'model':
        active_main_pos = [pos for pos in sel_positions if pos in model_mains]
        active_pairs = [
            (a, b) for a, b in itertools.combinations(sel_positions, 2)
            if (min(a, b), max(a, b)) in model_pairs
        ]
    else:
        active_main_pos = list(sel_positions)
        active_pairs = list(itertools.combinations(sel_positions, 2))

    if o['show_main_effects'] and not active_main_pos:
        raise ValueError('None of the selected variables appear in the fitted model terms.')
    if o['show_interaction_plot'] and not o['show_main_effects'] and not active_pairs:
        raise ValueError('The selected model has no two-way interaction terms among the chosen variables; select All terms or include Main effects plot.')

    # 1. Main Effects
    main_effects = []
    if o['show_main_effects']:
        for pos in active_main_pos:
            p = preds[pos]
            if p['role'] == 'factor':
                x_vals = list(p['levels'])
                cand_rows = []
                for lvl in x_vals:
                    row = list(hold_row)
                    row[pos] = lvl
                    cand_rows.append(row)
                fits = [item['fit'] for item in _predict_bundle_rows(bundle, cand_rows, compute_intervals=False)]
                key_points = [dict(label=str(lvl), value=lvl, fit=float(f)) for lvl, f in zip(x_vals, fits)]
                effect = float(max(fits) - min(fits)) if fits else 0.0
            else:
                lo, hi = float(p['min']), float(p['max'])
                mid = 0.5 * (lo + hi)
                n_pts = 25 if _has_curvature(bundle, pos) else 11
                x_vals = [lo + (hi - lo) * i / (n_pts - 1) for i in range(n_pts)]
                cand_rows = []
                for xv in x_vals:
                    row = list(hold_row)
                    row[pos] = xv
                    cand_rows.append(row)
                fits = [item['fit'] for item in _predict_bundle_rows(bundle, cand_rows, compute_intervals=False)]
                anchor_rows = []
                for xv in (lo, mid, hi):
                    row = list(hold_row)
                    row[pos] = xv
                    anchor_rows.append(row)
                anchor_fits = [item['fit'] for item in _predict_bundle_rows(bundle, anchor_rows, compute_intervals=False)]
                key_points = [
                    dict(label='Low', value=lo, fit=float(anchor_fits[0])),
                    dict(label='Center', value=mid, fit=float(anchor_fits[1])),
                    dict(label='High', value=hi, fit=float(anchor_fits[2])),
                ]
                effect = float(anchor_fits[2] - anchor_fits[0])
            mean_fit = math.fsum(fits) / len(fits) if fits else 0.0
            main_effects.append(dict(
                index=p['index'],
                name=p['name'],
                role=p['role'],
                x_values=x_vals,
                fits=[float(f) for f in fits],
                reference_mean=float(mean_fit),
                key_points=key_points,
                effect=float(effect),
            ))

    # 2. Interaction Plots
    interactions = []
    if o['show_interaction_plot'] and len(sel_positions) >= 2:
        pairs_to_eval = []
        if o['matrix_display'] == 'full':
            for a in sel_positions:
                for b in sel_positions:
                    if a == b:
                        continue
                    if o['terms_to_display'] == 'all' or (min(a, b), max(a, b)) in model_pairs:
                        pairs_to_eval.append((a, b))
        else:
            pairs_to_eval = list(active_pairs)

        for pos_x, pos_trace in pairs_to_eval:
            px = preds[pos_x]
            pt = preds[pos_trace]
            if px['role'] == 'factor':
                x_vals = list(px['levels'])
                x_anchors = list(px['levels'])
            else:
                lo_x, hi_x = float(px['min']), float(px['max'])
                n_pts = 21 if _has_curvature(bundle, pos_x) else 9
                x_vals = [lo_x + (hi_x - lo_x) * i / (n_pts - 1) for i in range(n_pts)]
                x_anchors = [lo_x, 0.5 * (lo_x + hi_x), hi_x]

            if pt['role'] == 'factor':
                trace_specs = [(str(lvl), lvl) for lvl in pt['levels']]
            else:
                lo_t, hi_t = float(pt['min']), float(pt['max'])
                if _has_curvature(bundle, pos_trace):
                    trace_specs = [
                        (f"{lo_t:.4g} (Low)", lo_t),
                        (f"{0.5 * (lo_t + hi_t):.4g} (Mid)", 0.5 * (lo_t + hi_t)),
                        (f"{hi_t:.4g} (High)", hi_t),
                    ]
                else:
                    trace_specs = [
                        (f"{lo_t:.4g} (Low)", lo_t),
                        (f"{hi_t:.4g} (High)", hi_t),
                    ]

            series = []
            summary_rows = []
            for t_label, t_val in trace_specs:
                cand_rows = []
                for xv in x_vals:
                    row = list(hold_row)
                    row[pos_x] = xv
                    row[pos_trace] = t_val
                    cand_rows.append(row)
                fits = [float(item['fit']) for item in _predict_bundle_rows(bundle, cand_rows, compute_intervals=False)]
                anchor_rows = []
                for xv in x_anchors:
                    row = list(hold_row)
                    row[pos_x] = xv
                    row[pos_trace] = t_val
                    anchor_rows.append(row)
                anchor_fits = [float(item['fit']) for item in _predict_bundle_rows(bundle, anchor_rows, compute_intervals=False)]
                series.append(dict(
                    label=t_label,
                    level_value=t_val,
                    x_values=list(x_vals),
                    fits=fits,
                    anchor_x=list(x_anchors),
                    anchor_fits=anchor_fits,
                ))
                summary_rows.append(dict(
                    trace_level=t_val,
                    trace_label=t_label,
                    low_fit=anchor_fits[0],
                    mid_fit=anchor_fits[len(anchor_fits) // 2],
                    high_fit=anchor_fits[-1],
                    slope_change=anchor_fits[-1] - anchor_fits[0],
                ))

            interactions.append(dict(
                x_index=px['index'],
                x_name=px['name'],
                x_role=px['role'],
                trace_index=pt['index'],
                trace_name=pt['name'],
                trace_role=pt['role'],
                series=series,
                summary_rows=summary_rows,
            ))

    warnings = list(bundle['warnings'])
    if o['show_interaction_plot'] and not interactions:
        warnings.append('No model interaction terms are present among the selected variables; only Main Effects are shown.')

    title = o['title'] or f"Factorial Plots for {bundle['response_name']}"
    return _finite_result(dict(
        analysis='factorial_plots',
        title=title,
        model_recipe=copy.deepcopy(recipe),
        model_action=bundle['action'],
        model_title=bundle['model_title'],
        response_index=bundle['response_index'],
        response_name=bundle['response_name'],
        is_probability=bundle['is_probability'],
        event=bundle['event'],
        selected_indices=sel,
        selected_names=[preds[pos_by_idx[idx]]['name'] for idx in sel],
        options=o,
        hold_summary=hold_summary,
        main_effects=main_effects,
        interactions=interactions,
        warnings=warnings,
        method='Model-driven fitted marginal curves and two-way interaction profiles',
        method_notes=(
            'Fitted values are evaluated from the current-worksheet model refit while holding non-plotted '
            'predictors at their configured hold settings. Native-product numerical equivalence is unverified.'
        ),
    ))


def _compute_contour_levels(z_min, z_max, level_mode, level_count, custom_levels):
    if level_mode == 'values' and custom_levels:
        return [float(v) for v in custom_levels]
    n_lvls = level_count if level_mode == 'number' else 7
    span = z_max - z_min
    if span <= 1e-12:
        return [round(float(z_min), 6)]
    # Generate `n_lvls` interior/spanning levels across [z_min, z_max]
    step = span / (n_lvls + 1)
    return [float(z_min + step * (i + 1)) for i in range(n_lvls)]


def _resolve_continuous_pairs(bundle, pair_mode, x_index, y_index):
    preds = bundle['predictors']
    cont_preds = [(j, p) for j, p in enumerate(preds) if p['role'] == 'covariate']
    if len(cont_preds) < 2:
        raise ValueError('Contour and Surface plots require a fitted model with at least two continuous predictors.')
    pos_by_idx = {p['index']: j for j, p in enumerate(preds) if p['role'] == 'covariate'}
    if pair_mode == 'single':
        if x_index is None and y_index is None:
            x_index = cont_preds[0][1]['index']
            y_index = cont_preds[1][1]['index']
        if type(x_index) is not int or type(y_index) is not int or x_index == y_index:
            raise ValueError('Select two distinct continuous predictor variables for X Axis and Y Axis.')
        if x_index not in pos_by_idx or y_index not in pos_by_idx:
            raise ValueError('X Axis and Y Axis must be continuous predictors in the selected model.')
        return [(pos_by_idx[x_index], pos_by_idx[y_index])], x_index, y_index, False
    all_pairs = [(a_pos, b_pos) for (a_pos, _), (b_pos, _) in itertools.combinations(cont_preds, 2)]
    truncated = len(all_pairs) > MAX_PAIR_PANELS
    return all_pairs[:MAX_PAIR_PANELS], cont_preds[0][1]['index'], cont_preds[1][1]['index'], truncated


def model_contour_plot(worksheet, model_recipe, x_index=None, y_index=None, options=None):
    """Evaluate 2D fitted response contour grids for one or all pairs of continuous predictors."""
    o = contour_plot_settings(options)
    recipe = normalize_model_recipe(model_recipe)
    bundle = _fit_model_bundle(worksheet, recipe)
    preds = bundle['predictors']
    pairs, norm_x, norm_y, truncated = _resolve_continuous_pairs(bundle, o['pair_mode'], x_index, y_index)
    hold_row, hold_summary = resolve_hold_settings(
        worksheet, bundle, o['hold_continuous'], o['hold_categorical'], o['hold_values']
    )
    source_rows = bundle['result']['row_indices']

    panels = []
    for pos_x, pos_y in pairs:
        px = preds[pos_x]
        py = preds[pos_y]
        x_grid = [float(px['min']) + (float(px['max']) - float(px['min'])) * c / (CONTOUR_GRID_SIZE - 1) for c in range(CONTOUR_GRID_SIZE)]
        y_grid = [float(py['min']) + (float(py['max']) - float(py['min'])) * r / (CONTOUR_GRID_SIZE - 1) for r in range(CONTOUR_GRID_SIZE)]

        eval_rows = []
        for yv in y_grid:
            for xv in x_grid:
                row = list(hold_row)
                row[pos_x] = xv
                row[pos_y] = yv
                eval_rows.append(row)
        fits = [float(item['fit']) for item in _predict_bundle_rows(bundle, eval_rows, compute_intervals=False)]
        z_grid = [fits[r * CONTOUR_GRID_SIZE:(r + 1) * CONTOUR_GRID_SIZE] for r in range(CONTOUR_GRID_SIZE)]

        min_idx = int(np.argmin(fits))
        max_idx = int(np.argmax(fits))
        min_r, min_c = divmod(min_idx, CONTOUR_GRID_SIZE)
        max_r, max_c = divmod(max_idx, CONTOUR_GRID_SIZE)
        z_min = float(fits[min_idx])
        z_max = float(fits[max_idx])
        levels = _compute_contour_levels(z_min, z_max, o['level_mode'], o['level_count'], o['custom_levels'])

        design_points = []
        if o['show_design_points']:
            seen_pts = set()
            for r_idx in source_rows:
                xv = float(worksheet.columns[px['index']].values[r_idx])
                yv = float(worksheet.columns[py['index']].values[r_idx])
                key = (round(xv, 8), round(yv, 8))
                if key not in seen_pts:
                    seen_pts.add(key)
                    design_points.append([xv, yv])

        held_others = [
            dict(index=h['index'], name=h['name'], value=h['value'])
            for j, h in enumerate(hold_summary) if j not in (pos_x, pos_y)
        ]
        panels.append(dict(
            x_index=px['index'],
            x_name=px['name'],
            y_index=py['index'],
            y_name=py['name'],
            x_grid=x_grid,
            y_grid=y_grid,
            z_grid=z_grid,
            z_min=z_min,
            z_max=z_max,
            min_point=dict(x=x_grid[min_c], y=y_grid[min_r], fit=z_min),
            max_point=dict(x=x_grid[max_c], y=y_grid[max_r], fit=z_max),
            levels=levels,
            design_points=design_points,
            held_predictors=held_others,
        ))

    warnings = list(bundle['warnings'])
    if truncated:
        warnings.append(f'Displayed the first {MAX_PAIR_PANELS} continuous variable pairs.')

    first_p = panels[0]
    default_title = (
        f"Contour Plot of {bundle['response_name']} vs {first_p['y_name']}, {first_p['x_name']}"
        if len(panels) == 1
        else f"Contour Plots of {bundle['response_name']}"
    )
    return _finite_result(dict(
        analysis='model_contour_plot',
        title=o['title'] or default_title,
        model_recipe=copy.deepcopy(recipe),
        model_action=bundle['action'],
        model_title=bundle['model_title'],
        response_index=bundle['response_index'],
        response_name=bundle['response_name'],
        is_probability=bundle['is_probability'],
        event=bundle['event'],
        x_index=norm_x,
        y_index=norm_y,
        options=o,
        hold_summary=hold_summary,
        panels=panels,
        warnings=warnings,
        method='Model-driven 2D fitted response contour evaluation over a 41x41 predictor grid',
        method_notes=(
            'Contours are interpolated across a 41x41 grid of fitted model predictions while holding '
            'non-plotted predictors at their configured hold settings. Native-product numerical equivalence is unverified.'
        ),
    ))


def model_surface_plot(worksheet, model_recipe, x_index=None, y_index=None, options=None):
    """Evaluate 3D fitted response surface grids for one or all pairs of continuous predictors."""
    o = surface_plot_settings(options)
    recipe = normalize_model_recipe(model_recipe)
    bundle = _fit_model_bundle(worksheet, recipe)
    preds = bundle['predictors']
    pairs, norm_x, norm_y, truncated = _resolve_continuous_pairs(bundle, o['pair_mode'], x_index, y_index)
    hold_row, hold_summary = resolve_hold_settings(
        worksheet, bundle, o['hold_continuous'], o['hold_categorical'], o['hold_values']
    )

    panels = []
    for pos_x, pos_y in pairs:
        px = preds[pos_x]
        py = preds[pos_y]
        x_grid = [float(px['min']) + (float(px['max']) - float(px['min'])) * c / (SURFACE_GRID_SIZE - 1) for c in range(SURFACE_GRID_SIZE)]
        y_grid = [float(py['min']) + (float(py['max']) - float(py['min'])) * r / (SURFACE_GRID_SIZE - 1) for r in range(SURFACE_GRID_SIZE)]

        eval_rows = []
        for yv in y_grid:
            for xv in x_grid:
                row = list(hold_row)
                row[pos_x] = xv
                row[pos_y] = yv
                eval_rows.append(row)
        fits = [float(item['fit']) for item in _predict_bundle_rows(bundle, eval_rows, compute_intervals=False)]
        z_grid = [fits[r * SURFACE_GRID_SIZE:(r + 1) * SURFACE_GRID_SIZE] for r in range(SURFACE_GRID_SIZE)]

        min_idx = int(np.argmin(fits))
        max_idx = int(np.argmax(fits))
        min_r, min_c = divmod(min_idx, SURFACE_GRID_SIZE)
        max_r, max_c = divmod(max_idx, SURFACE_GRID_SIZE)
        z_min = float(fits[min_idx])
        z_max = float(fits[max_idx])
        center_r = SURFACE_GRID_SIZE // 2
        center_c = SURFACE_GRID_SIZE // 2
        center_fit = float(z_grid[center_r][center_c])

        held_others = [
            dict(index=h['index'], name=h['name'], value=h['value'])
            for j, h in enumerate(hold_summary) if j not in (pos_x, pos_y)
        ]
        panels.append(dict(
            x_index=px['index'],
            x_name=px['name'],
            y_index=py['index'],
            y_name=py['name'],
            x_grid=x_grid,
            y_grid=y_grid,
            z_grid=z_grid,
            z_min=z_min,
            z_max=z_max,
            center_point=dict(x=x_grid[center_c], y=y_grid[center_r], fit=center_fit),
            min_point=dict(x=x_grid[min_c], y=y_grid[min_r], fit=z_min),
            max_point=dict(x=x_grid[max_c], y=y_grid[max_r], fit=z_max),
            held_predictors=held_others,
        ))

    warnings = list(bundle['warnings'])
    if truncated:
        warnings.append(f'Displayed the first {MAX_PAIR_PANELS} continuous variable pairs.')

    first_p = panels[0]
    default_title = (
        f"Surface Plot of {bundle['response_name']} vs {first_p['y_name']}, {first_p['x_name']}"
        if len(panels) == 1
        else f"Surface Plots of {bundle['response_name']}"
    )
    return _finite_result(dict(
        analysis='model_surface_plot',
        title=o['title'] or default_title,
        model_recipe=copy.deepcopy(recipe),
        model_action=bundle['action'],
        model_title=bundle['model_title'],
        response_index=bundle['response_index'],
        response_name=bundle['response_name'],
        is_probability=bundle['is_probability'],
        event=bundle['event'],
        x_index=norm_x,
        y_index=norm_y,
        options=o,
        hold_summary=hold_summary,
        panels=panels,
        warnings=warnings,
        method='Model-driven 3D fitted response surface evaluation over a 25x25 predictor grid',
        method_notes=(
            'The fitted response surface is evaluated on a 25x25 grid while holding non-plotted '
            'predictors at their configured hold settings. Native-product numerical equivalence is unverified.'
        ),
    ))
