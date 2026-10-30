"""Multi-Vari Chart computation engine.

Computes hierarchical factor level means, overall mean, and grouping tree for Multi-Vari analysis.
Supports up to 4 factors (Factor 1: within piece, Factor 2: piece-to-piece, Factor 3: time/operator, Factor 4).
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from .engine import normalize_numeric


def compute_multivari(worksheet, response_index: int, factor_indices: list[int]) -> dict:
    if response_index < 0 or response_index >= len(worksheet.columns):
        raise ValueError("Invalid response column index.")
    if not factor_indices or len(factor_indices) > 4:
        raise ValueError("Multi-Vari chart requires between 1 and 4 factor columns.")

    resp_col = worksheet.columns[response_index]
    factor_cols = [worksheet.columns[i] for i in factor_indices]

    resp_vals = resp_col.numeric_values(True)
    n_rows = len(resp_vals)

    # Extract valid complete cases
    points = []
    for r in range(n_rows):
        y = resp_vals[r]
        if y is None:
            continue
        row_factors = []
        skip = False
        for fc in factor_cols:
            if r >= len(fc.values) or fc.values[r] is None:
                skip = True
                break
            row_factors.append(str(fc.values[r]))
        if not skip:
            points.append({
                'row': r + 1,
                'y': float(y),
                'factors': row_factors,
            })

    if len(points) < 2:
        raise ValueError("Multi-Vari chart requires at least two complete rows with response and factor values.")

    all_y = [p['y'] for p in points]
    grand_mean = statistics.fmean(all_y)

    # Group by factors
    # Hierarchical factor levels
    factor_names = [fc.name for fc in factor_cols]
    num_factors = len(factor_indices)

    # Aggregate means by deepest factor combination
    # key: tuple of factor level strings
    combos = defaultdict(list)
    for p in points:
        key = tuple(p['factors'])
        combos[key].append(p['y'])

    # Structure cells and means
    cells = []
    for key, vals in sorted(combos.items()):
        cells.append({
            'factors': list(key),
            'n': len(vals),
            'mean': statistics.fmean(vals),
            'min': min(vals),
            'max': max(vals),
            'values': vals,
        })

    # Factor level means for each individual factor
    factor_level_means = {}
    for fi, fn in enumerate(factor_names):
        lvl_map = defaultdict(list)
        for p in points:
            lvl_map[p['factors'][fi]].append(p['y'])
        factor_level_means[fn] = {
            lvl: {
                'n': len(v_list),
                'mean': statistics.fmean(v_list),
            }
            for lvl, v_list in sorted(lvl_map.items())
        }

    return {
        'analysis': 'multivari',
        'response_name': resp_col.name,
        'factor_names': factor_names,
        'grand_mean': grand_mean,
        'n_total': len(points),
        'cells': cells,
        'factor_level_means': factor_level_means,
        'points': points,
    }
