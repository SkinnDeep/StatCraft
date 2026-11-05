"""Variability / Gauge Chart analytical engine (JMP & Six Sigma standard).

Computes:
- Multi-factor hierarchical / crossed cell means, min, max, count, and standard deviations.
- Subgroup dispersion (within-cell standard deviation S) across nested groups.
- Variance component analysis (Repeatability, Reproducibility, Part-to-Part, Total Variation).
- Gauge R&R metrics: % Contribution (Variance), % Study Variation (StdDev),
  Tolerance ratio (%Tolerance / P/T ratio), and Number of Distinct Categories (ndc).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple


def calculate_variability_analysis(
    y_values: Sequence[Optional[float]],
    x_groupings: Sequence[Tuple[str, Sequence[Any]]],
    part_factor_name: Optional[str] = None,
    operator_factor_name: Optional[str] = None,
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    sigma_multiplier: float = 6.0,
) -> Dict[str, Any]:
    """Calculate multi-level variability and Gage R&R variance components.

    Parameters
    ----------
    y_values : Sequence[Optional[float]]
        Continuous response measurement values.
    x_groupings : Sequence[Tuple[str, Sequence[Any]]]
        Ordered list of (factor_name, factor_values) establishing hierarchical/crossed grouping.
    part_factor_name : Optional[str]
        Factor designated as 'Part' for Gauge R&R decomposition.
    operator_factor_name : Optional[str]
        Factor designated as 'Operator' for Gauge R&R decomposition.
    lsl : Optional[float]
        Lower specification limit for %Tolerance calculation.
    usl : Optional[float]
        Upper specification limit for %Tolerance calculation.
    sigma_multiplier : float
        Sigma multiplier for study variation (standard is 6.0 for 99.73% spread).
    """
    n = len(y_values)
    if n == 0 or not x_groupings:
        raise ValueError("Variability analysis requires measurement data and at least one grouping factor.")

    # Validate lengths
    for fname, fvals in x_groupings:
        if len(fvals) != n:
            raise ValueError(f"Grouping factor '{fname}' length ({len(fvals)}) does not match measurement count ({n}).")

    # Filter complete cases
    complete_indices: List[int] = []
    for i in range(n):
        y = y_values[i]
        if y is not None and not math.isnan(y):
            # Check all factors are non-empty
            all_valid = True
            for _, fvals in x_groupings:
                val = fvals[i]
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    all_valid = False
                    break
            if all_valid:
                complete_indices.append(i)

    if len(complete_indices) < 2:
        raise ValueError("Variability analysis requires at least two valid complete observations.")

    clean_y = [float(y_values[i]) for i in complete_indices]
    clean_factors = {
        fname: [str(fvals[i]) for i in complete_indices]
        for fname, fvals in x_groupings
    }
    factor_names = [fname for fname, _ in x_groupings]

    # Overall summary
    total_n = len(clean_y)
    grand_mean = sum(clean_y) / total_n
    ss_total = sum((y - grand_mean) ** 2 for y in clean_y)
    overall_var = ss_total / (total_n - 1) if total_n > 1 else 0.0
    overall_std = math.sqrt(overall_var) if overall_var > 0 else 0.0

    # Build unique compound cells preserving order of appearance
    # Each cell is a tuple of factor values (f1, f2, ...)
    cells_order: List[Tuple[str, ...]] = []
    cells_data: Dict[Tuple[str, ...], List[float]] = {}
    for i in range(total_n):
        key = tuple(clean_factors[fn][i] for fn in factor_names)
        if key not in cells_data:
            cells_data[key] = []
            cells_order.append(key)
        cells_data[key].append(clean_y[i])

    # Compute cell-level statistics
    cell_summaries: List[Dict[str, Any]] = []
    pooled_ss_within = 0.0
    pooled_df_within = 0

    for key in cells_order:
        vals = cells_data[key]
        c_count = len(vals)
        c_mean = sum(vals) / c_count
        c_min = min(vals)
        c_max = max(vals)
        c_range = c_max - c_min
        if c_count > 1:
            c_var = sum((v - c_mean) ** 2 for v in vals) / (c_count - 1)
            c_std = math.sqrt(c_var)
            pooled_ss_within += sum((v - c_mean) ** 2 for v in vals)
            pooled_df_within += (c_count - 1)
        else:
            c_var = 0.0
            c_std = 0.0

        cell_summaries.append({
            "key": key,
            "labels": {fn: key[idx] for idx, fn in enumerate(factor_names)},
            "values": vals,
            "count": c_count,
            "mean": c_mean,
            "std": c_std,
            "min": c_min,
            "max": c_max,
            "range": c_range,
        })

    # Within-cell pooled standard deviation (Repeatability / Pure Error estimate)
    if pooled_df_within > 0:
        var_repeatability = pooled_ss_within / pooled_df_within
        std_repeatability = math.sqrt(var_repeatability)
    else:
        var_repeatability = 0.0
        std_repeatability = 0.0

    # Auto-detect Part and Operator if not explicitly provided
    detected_part = part_factor_name
    detected_operator = operator_factor_name

    if not detected_part:
        for fn in factor_names:
            fn_lower = fn.lower()
            if any(term in fn_lower for term in ("part", "sample", "item", "piece", "unit")):
                detected_part = fn
                break
        if not detected_part and len(factor_names) > 0:
            detected_part = factor_names[0]

    if not detected_operator:
        for fn in factor_names:
            if fn == detected_part:
                continue
            fn_lower = fn.lower()
            if any(term in fn_lower for term in ("oper", "tech", "user", "appraiser", "run", "batch")):
                detected_operator = fn
                break
        if not detected_operator and len(factor_names) > 1:
            detected_operator = [fn for fn in factor_names if fn != detected_part][0]

    # Two-way crossed / nested Gage R&R variance components (ANOVA method)
    grr_results: Optional[Dict[str, Any]] = None
    if detected_part and detected_operator and detected_part in clean_factors and detected_operator in clean_factors:
        parts = clean_factors[detected_part]
        operators = clean_factors[detected_operator]
        unique_parts = sorted(list(set(parts)))
        unique_ops = sorted(list(set(operators)))
        p = len(unique_parts)
        o = len(unique_ops)

        if p > 1 and o > 1:
            # Check balanced replications
            part_totals = {prt: 0.0 for prt in unique_parts}
            part_counts = {prt: 0 for prt in unique_parts}
            op_totals = {op: 0.0 for op in unique_ops}
            op_counts = {op: 0 for op in unique_ops}
            cell_totals: Dict[Tuple[str, str], float] = {}
            cell_counts: Dict[Tuple[str, str], int] = {}

            for i in range(total_n):
                prt = parts[i]
                op = operators[i]
                y = clean_y[i]
                part_totals[prt] += y
                part_counts[prt] += 1
                op_totals[op] += y
                op_counts[op] += 1
                ck = (prt, op)
                cell_totals[ck] = cell_totals.get(ck, 0.0) + y
                cell_counts[ck] = cell_counts.get(ck, 0) + 1

            # Approximate harmonic replication count
            r_nominal = total_n / (p * o)

            ss_part = sum((part_totals[prt] ** 2) / part_counts[prt] for prt in unique_parts) - (sum(clean_y) ** 2 / total_n)
            ss_op = sum((op_totals[op] ** 2) / op_counts[op] for op in unique_ops) - (sum(clean_y) ** 2 / total_n)
            ss_subtotal = sum((cell_totals[ck] ** 2) / cell_counts[ck] for ck in cell_totals) - (sum(clean_y) ** 2 / total_n)
            ss_part_op = max(0.0, ss_subtotal - ss_part - ss_op)
            ss_pure_error = max(0.0, ss_total - ss_subtotal)

            df_part = p - 1
            df_op = o - 1
            df_part_op = (p - 1) * (o - 1)
            df_error = max(1, total_n - (p * o))

            ms_part = ss_part / df_part if df_part > 0 else 0.0
            ms_op = ss_op / df_op if df_op > 0 else 0.0
            ms_part_op = ss_part_op / df_part_op if df_part_op > 0 else 0.0
            ms_error = ss_pure_error / df_error if df_error > 0 else 0.0

            # Variance components
            # Repeatability
            var_repeat = ms_error
            # Part*Op Interaction
            var_part_op = max(0.0, (ms_part_op - ms_error) / r_nominal) if r_nominal > 0 else 0.0
            # Operator Reproducibility
            var_repro = max(0.0, (ms_op - ms_part_op) / (p * r_nominal)) if (p * r_nominal) > 0 else 0.0
            total_repro = var_repro + var_part_op
            # Part-to-Part
            var_part = max(0.0, (ms_part - ms_part_op) / (o * r_nominal)) if (o * r_nominal) > 0 else 0.0
            # Total Gage R&R
            var_grr = var_repeat + total_repro
            # Total Variation
            var_total = var_grr + var_part

            std_repeat = math.sqrt(var_repeat)
            std_repro = math.sqrt(total_repro)
            std_grr = math.sqrt(var_grr)
            std_part = math.sqrt(var_part)
            std_tot = math.sqrt(var_total) if var_total > 0 else 1e-12

            # Percent Contributions (% of Total Variance)
            pct_contrib_grr = (var_grr / var_total) * 100.0 if var_total > 0 else 0.0
            pct_contrib_repeat = (var_repeat / var_total) * 100.0 if var_total > 0 else 0.0
            pct_contrib_repro = (total_repro / var_total) * 100.0 if var_total > 0 else 0.0
            pct_contrib_part = (var_part / var_total) * 100.0 if var_total > 0 else 0.0

            # Percent Study Variation (% of Total StdDev)
            pct_study_grr = (std_grr / std_tot) * 100.0
            pct_study_repeat = (std_repeat / std_tot) * 100.0
            pct_study_repro = (std_repro / std_tot) * 100.0
            pct_study_part = (std_part / std_tot) * 100.0

            # Study Variations (6 * sigma)
            study_var_grr = sigma_multiplier * std_grr
            study_var_repeat = sigma_multiplier * std_repeat
            study_var_repro = sigma_multiplier * std_repro
            study_var_part = sigma_multiplier * std_part
            study_var_total = sigma_multiplier * std_tot

            # Tolerance Metrics
            tolerance = None
            pct_tol_grr = None
            pct_tol_repeat = None
            pct_tol_repro = None
            pct_tol_part = None
            if usl is not None and lsl is not None and usl > lsl:
                tolerance = usl - lsl
                pct_tol_grr = (study_var_grr / tolerance) * 100.0
                pct_tol_repeat = (study_var_repeat / tolerance) * 100.0
                pct_tol_repro = (study_var_repro / tolerance) * 100.0
                pct_tol_part = (study_var_part / tolerance) * 100.0

            # Number of Distinct Categories (ndc)
            # ndc = 1.41 * (PV / GRR) = sqrt(2) * (std_part / std_grr)
            ndc = int(math.floor(1.4142 * (std_part / std_grr))) if std_grr > 0 else 0

            # AIAG evaluation status
            if pct_study_grr < 10.0:
                aiag_status = "Acceptable (< 10%)"
                aiag_badge = "Excellent"
            elif pct_study_grr <= 30.0:
                aiag_status = "May be acceptable based on application (10% - 30%)"
                aiag_badge = "Marginal"
            else:
                aiag_status = "Unacceptable (> 30%) - system requires improvement"
                aiag_badge = "Unacceptable"

            grr_results = {
                "part_factor": detected_part,
                "operator_factor": detected_operator,
                "num_parts": p,
                "num_operators": o,
                "replications_nominal": r_nominal,
                "tolerance": tolerance,
                "sigma_multiplier": sigma_multiplier,
                "ndc": ndc,
                "aiag_status": aiag_status,
                "aiag_badge": aiag_badge,
                "var_repeatability": var_repeat,
                "var_reproducibility": total_repro,
                "var_part_operator": var_part_op,
                "var_grr": var_grr,
                "var_part_to_part": var_part,
                "var_total": var_total,
                "std_repeatability": std_repeat,
                "std_reproducibility": std_repro,
                "std_grr": std_grr,
                "std_part_to_part": std_part,
                "std_total": std_tot,
                "pct_contrib_grr": pct_contrib_grr,
                "pct_contrib_repeat": pct_contrib_repeat,
                "pct_contrib_repro": pct_contrib_repro,
                "pct_contrib_part": pct_contrib_part,
                "pct_study_grr": pct_study_grr,
                "pct_study_repeat": pct_study_repeat,
                "pct_study_repro": pct_study_repro,
                "pct_study_part": pct_study_part,
                "study_var_grr": study_var_grr,
                "study_var_repeat": study_var_repeat,
                "study_var_repro": study_var_repro,
                "study_var_part": study_var_part,
                "study_var_total": study_var_total,
                "pct_tol_grr": pct_tol_grr,
                "pct_tol_repeat": pct_tol_repeat,
                "pct_tol_repro": pct_tol_repro,
                "pct_tol_part": pct_tol_part,
            }

    return {
        "n": total_n,
        "grand_mean": grand_mean,
        "overall_var": overall_var,
        "overall_std": overall_std,
        "factor_names": factor_names,
        "cell_summaries": cell_summaries,
        "var_repeatability": var_repeatability,
        "std_repeatability": std_repeatability,
        "gauge_rr": grr_results,
        "specs": {"lsl": lsl, "usl": usl},
    }
