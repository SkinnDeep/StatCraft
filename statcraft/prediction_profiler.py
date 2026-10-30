"""Prediction Profiler computational engine for StatCraft.

Provides interactive prediction profiling, confidence intervals, Derringer-Suich
desirability analysis, and optimal setting discovery across multiple fitted models.
Matches JMP Prediction Profiler capabilities.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from scipy import optimize

from .model import Worksheet, finite_number
from .prediction import predict, model_spec, normalize_recipe


@dataclass
class ProfilerFactor:
    """Factor / Predictor specification for the profiler."""
    name: str
    column_index: int
    kind: str  # 'number' | 'text'
    role: str  # 'covariate' | 'factor'
    min_val: float
    max_val: float
    current_val: float | str
    levels: list[str] = field(default_factory=list)


@dataclass
class ProfilerResponse:
    """Response variable specification for desirability calculation."""
    name: str
    column_index: int
    goal: str = "none"  # 'none' | 'maximize' | 'minimize' | 'target'
    lower: Optional[float] = None
    target: Optional[float] = None
    upper: Optional[float] = None
    weight: float = 1.0
    importance: float = 1.0


def extract_profiler_specs(
    worksheet: Worksheet,
    model_recipes: list[dict[str, Any]]
) -> tuple[list[ProfilerFactor], list[ProfilerResponse]]:
    """Extract unified factor and response specifications from fitted model recipes."""
    if not model_recipes:
        raise ValueError("At least one fitted model recipe is required.")

    # Collect predictors from all models
    factor_map: dict[str, ProfilerFactor] = {}
    response_map: dict[str, ProfilerResponse] = {}

    for recipe in model_recipes:
        norm_recipe = normalize_recipe(recipe)
        spec = model_spec(worksheet, norm_recipe)
        resp_idx = norm_recipe['parameters']['response_index']
        resp_col = worksheet.columns[resp_idx]

        if resp_col.name not in response_map:
            # Check for spec limits in column metadata
            meta_specs = resp_col.metadata.get("spec_limits", {})
            lsl = meta_specs.get("lsl")
            usl = meta_specs.get("usl")
            tgt = meta_specs.get("target")

            goal = "none"
            if lsl is not None and usl is not None:
                goal = "target"
            elif lsl is not None:
                goal = "maximize"
            elif usl is not None:
                goal = "minimize"

            response_map[resp_col.name] = ProfilerResponse(
                name=resp_col.name,
                column_index=resp_idx,
                goal=goal,
                lower=lsl,
                target=tgt,
                upper=usl,
            )

        for p_info in spec['predictors']:
            p_name = p_info['name']
            p_idx = p_info['index']
            c = worksheet.columns[p_idx]

            if p_name not in factor_map:
                if c.kind == 'number':
                    finite_vals = [v for v in c.values if v is not None and isinstance(v, (int, float)) and math.isfinite(v)]
                    if not finite_vals:
                        min_v, max_v = 0.0, 1.0
                    else:
                        min_v = float(min(finite_vals))
                        max_v = float(max(finite_vals))
                        if min_v == max_v:
                            max_v = min_v + 1.0
                    current_v = (min_v + max_v) / 2.0
                    factor_map[p_name] = ProfilerFactor(
                        name=p_name,
                        column_index=p_idx,
                        kind='number',
                        role=p_info['role'],
                        min_val=min_v,
                        max_val=max_v,
                        current_val=current_v,
                    )
                else:
                    levels = p_info.get('levels', [])
                    if not levels:
                        levels = sorted(list(set(str(v) for v in c.values if v is not None)))
                    current_v = levels[0] if levels else ""
                    factor_map[p_name] = ProfilerFactor(
                        name=p_name,
                        column_index=p_idx,
                        kind='text',
                        role=p_info['role'],
                        min_val=0.0,
                        max_val=float(max(1, len(levels) - 1)),
                        current_val=current_v,
                        levels=levels,
                    )

    return list(factor_map.values()), list(response_map.values())


def compute_prediction_profiles(
    worksheet: Worksheet,
    model_recipes: list[dict[str, Any]],
    factor_specs: list[ProfilerFactor],
    current_settings: dict[str, float | str],
    n_points: int = 51,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Compute prediction traces, CI bands, and current fits for all models across each factor."""
    n_pts = max(11, n_points)
    options = dict(confidence=confidence, intervals='both', side='two_sided', show_equation=False, show_table=False)

    results_by_response: dict[str, Any] = {}

    for recipe in model_recipes:
        norm_recipe = normalize_recipe(recipe)
        spec = model_spec(worksheet, norm_recipe)
        resp_name = spec['response_name']
        preds = spec['predictors']

        # Determine current base point aligned with this model's predictors
        current_row = [current_settings.get(p['name'], factor.current_val)
                       for p in preds
                       for factor in factor_specs if factor.name == p['name']]

        # 1. Compute current point prediction
        curr_pred = predict(worksheet, norm_recipe, input_mode='values', values=[current_row], options=options)
        curr_row_res = curr_pred['rows'][0]

        factor_traces: dict[str, Any] = {}

        # 2. Compute 1D trace for each factor holding others fixed
        for f_idx, factor in enumerate(factor_specs):
            # Check if factor is in this model
            if factor.name not in [p['name'] for p in preds]:
                continue

            model_p_idx = [i for i, p in enumerate(preds) if p['name'] == factor.name][0]

            if factor.kind == 'number':
                xs = np.linspace(factor.min_val, factor.max_val, n_pts).tolist()
            else:
                xs = list(factor.levels)

            # Build prediction batch for this factor
            batch = []
            for x_val in xs:
                row = list(current_row)
                row[model_p_idx] = x_val
                batch.append(row)

            pred_res = predict(worksheet, norm_recipe, input_mode='values', values=batch, options=options)

            fits = [r['fit'] for r in pred_res['rows']]
            ci_lows = [r['ci_low'] for r in pred_res['rows']]
            ci_highs = [r['ci_high'] for r in pred_res['rows']]

            factor_traces[factor.name] = {
                'xs': xs,
                'fits': fits,
                'ci_low': ci_lows,
                'ci_high': ci_highs,
                'current_x': current_settings.get(factor.name, factor.current_val),
            }

        results_by_response[resp_name] = {
            'response_name': resp_name,
            'current_fit': curr_row_res['fit'],
            'current_se': curr_row_res['se_fit'],
            'current_ci_low': curr_row_res['ci_low'],
            'current_ci_high': curr_row_res['ci_high'],
            'factor_traces': factor_traces,
        }

    return results_by_response


def compute_desirability(
    y: Optional[float],
    goal: str,
    lower: Optional[float] = None,
    target: Optional[float] = None,
    upper: Optional[float] = None,
    weight: float = 1.0,
) -> float:
    """Compute Derringer-Suich individual desirability d(y) in [0, 1]."""
    if y is None or not math.isfinite(y):
        return 0.0

    g = (goal or "none").lower()
    if g == "none":
        return 1.0

    s = max(0.01, min(100.0, weight))

    if g == "maximize":
        l = lower if lower is not None else (target - 1.0 if target is not None else y - 1.0)
        t = target if target is not None else (upper if upper is not None else l + 1.0)
        if t <= l:
            t = l + 1e-6
        if y < l:
            return 0.0
        elif y > t:
            return 1.0
        else:
            return float(((y - l) / (t - l)) ** s)

    elif g == "minimize":
        t = target if target is not None else (lower if lower is not None else y - 1.0)
        u = upper if upper is not None else (t + 1.0)
        if u <= t:
            u = t + 1e-6
        if y < t:
            return 1.0
        elif y > u:
            return 0.0
        else:
            return float(((u - y) / (u - t)) ** s)

    elif g == "target":
        l = lower if lower is not None else (target - 1.0 if target is not None else 0.0)
        t = target if target is not None else (lower + upper) / 2.0 if (lower is not None and upper is not None) else y
        u = upper if upper is not None else (target + 1.0 if target is not None else 1.0)

        if l >= t or t >= u:
            return 1.0 if abs(y - t) < 1e-6 else 0.0

        if y < l or y > u:
            return 0.0
        elif y <= t:
            return float(((y - l) / (t - l)) ** s)
        else:
            return float(((u - y) / (u - t)) ** s)

    return 1.0


def compute_composite_desirability(
    response_values: dict[str, Optional[float]],
    response_specs: list[ProfilerResponse]
) -> tuple[float, dict[str, float]]:
    """Compute overall geometric mean composite desirability D and individual d_i values."""
    individual_d: dict[str, float] = {}
    d_list: list[float] = []
    weight_list: list[float] = []

    for spec in response_specs:
        y = response_values.get(spec.name)
        d = compute_desirability(y, spec.goal, spec.lower, spec.target, spec.upper, spec.weight)
        individual_d[spec.name] = d
        if spec.goal != "none":
            d_list.append(d)
            weight_list.append(spec.importance)

    if not d_list:
        return 1.0, individual_d

    # Any 0 individual desirability results in 0 composite desirability
    if any(d <= 0.0 for d in d_list):
        return 0.0, individual_d

    total_weight = sum(weight_list)
    if total_weight <= 0:
        total_weight = float(len(d_list))
        weight_list = [1.0] * len(d_list)

    log_d = sum(w * math.log(max(1e-12, d)) for w, d in zip(weight_list, d_list)) / total_weight
    composite_d = float(math.exp(log_d))
    return max(0.0, min(1.0, composite_d)), individual_d


def optimize_profiler_settings(
    worksheet: Worksheet,
    model_recipes: list[dict[str, Any]],
    factor_specs: list[ProfilerFactor],
    response_specs: list[ProfilerResponse],
) -> dict[str, float | str]:
    """Find factor settings that maximize composite desirability D."""
    # Filter continuous factors for optimization
    cont_factors = [f for f in factor_specs if f.kind == 'number']
    if not cont_factors:
        return {f.name: f.current_val for f in factor_specs}

    bounds = [(f.min_val, f.max_val) for f in cont_factors]
    x0 = [(f.min_val + f.max_val) / 2.0 for f in cont_factors]

    cat_settings = {f.name: f.current_val for f in factor_specs if f.kind != 'number'}

    def objective(x_vec: np.ndarray) -> float:
        # Build settings dict
        settings: dict[str, float | str] = dict(cat_settings)
        for f, val in zip(cont_factors, x_vec):
            settings[f.name] = float(val)

        # Predict responses
        resp_vals: dict[str, Optional[float]] = {}
        for recipe in model_recipes:
            norm_recipe = normalize_recipe(recipe)
            spec = model_spec(worksheet, norm_recipe)
            preds = spec['predictors']
            row = [settings.get(p['name']) for p in preds]
            try:
                res = predict(worksheet, norm_recipe, input_mode='values', values=[row],
                              options=dict(confidence=0.95, intervals='none', side='two_sided', show_equation=False, show_table=False))
                resp_vals[spec['response_name']] = res['rows'][0]['fit']
            except Exception:
                resp_vals[spec['response_name']] = None

        comp_d, _ = compute_composite_desirability(resp_vals, response_specs)
        # Minimize negative desirability
        return -comp_d

    res = optimize.minimize(
        objective,
        x0=x0,
        bounds=bounds,
        method='L-BFGS-B',
        options=dict(maxiter=100, ftol=1e-5)
    )

    optimal_settings = dict(cat_settings)
    for f, opt_x in zip(cont_factors, res.x):
        # Clamp to factor bounds
        clamped = max(f.min_val, min(f.max_val, float(opt_x)))
        optimal_settings[f.name] = clamped

    return optimal_settings
