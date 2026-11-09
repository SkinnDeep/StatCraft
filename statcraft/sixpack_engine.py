"""Process Capability Sixpack (Normal Distribution) Engine for StatCraft.

Computes the 6 diagnostic components of the StatCraft Capability Sixpack:
1. Xbar Chart (or I Chart for n=1): Subgroup means with control limits and special cause tests
2. R Chart (or S Chart for n>8, MR Chart for n=1): Dispersion with control limits and special cause tests
3. Last 25 Subgroups Plot (Run Chart): Individual observation points and subgroup means across the last <=25 subgroups
4. Capability Histogram: Data distribution with fitted Within and Overall normal curves, LSL, Target, and USL
5. Normal Probability Plot: Empirical percentiles vs theoretical normal quantiles with Anderson-Darling test
6. Capability Plot / Summary Box: Within vs Overall capability indices (Cp, Cpk, Pp, Ppk) and defect rates (PPM)
"""

from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy import stats

from .capability_engine import (
    run_normal_capability,
    c4,
    d2,
)
from .normality import normality


# Control chart factor constants
D3_TABLE = {
    2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.076, 8: 0.136, 9: 0.184, 10: 0.223,
    11: 0.256, 12: 0.283, 13: 0.307, 14: 0.328, 15: 0.347, 16: 0.363, 17: 0.378,
    18: 0.391, 19: 0.403, 20: 0.415, 21: 0.425, 22: 0.434, 23: 0.443, 24: 0.451, 25: 0.459
}
D4_TABLE = {
    2: 3.267, 3: 2.574, 4: 2.282, 5: 2.114, 6: 2.004, 7: 1.924, 8: 1.864, 9: 1.816, 10: 1.777,
    11: 1.744, 12: 1.717, 13: 1.693, 14: 1.672, 15: 1.653, 16: 1.637, 17: 1.622,
    18: 1.608, 19: 1.597, 20: 1.585, 21: 1.575, 22: 1.566, 23: 1.557, 24: 1.548, 25: 1.541
}
B3_TABLE = {
    2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.029, 7: 0.118, 8: 0.185, 9: 0.239, 10: 0.284,
    11: 0.321, 12: 0.354, 13: 0.382, 14: 0.406, 15: 0.428, 16: 0.448, 17: 0.466,
    18: 0.482, 19: 0.497, 20: 0.510, 21: 0.523, 22: 0.534, 23: 0.545, 24: 0.555, 25: 0.565
}
B4_TABLE = {
    2: 3.267, 3: 2.568, 4: 2.266, 5: 2.089, 6: 1.970, 7: 1.882, 8: 1.815, 9: 1.761, 10: 1.716,
    11: 1.679, 12: 1.646, 13: 1.618, 14: 1.594, 15: 1.572, 16: 1.552, 17: 1.534,
    18: 1.518, 19: 1.503, 20: 1.490, 21: 1.477, 22: 1.466, 23: 1.455, 24: 1.445, 25: 1.435
}


class SubgroupInfo:
    def __init__(self, values: List[float]):
        self.values = values
        self.n = len(values)
        self.mean = float(np.mean(values)) if values else 0.0
        self.stdev = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        self.range = (max(values) - min(values)) if values else 0.0


def extract_subgroups_from_settings(settings: Dict[str, Any]) -> Tuple[List[SubgroupInfo], List[float]]:
    """Helper to partition inputs into subgroups matching StatCraft rules."""
    data_mode = settings.get("data_mode", "single_column")
    subgroups: List[SubgroupInfo] = []
    flat_clean: List[float] = []

    if data_mode == "subgroups_across":
        cols_across_data = settings.get("cols_across_data", [])
        if not cols_across_data:
            return subgroups, flat_clean
        num_rows = max(len(c) for c in cols_across_data)
        for r in range(num_rows):
            row_clean = []
            for col in cols_across_data:
                if r < len(col):
                    v = col[r]
                    if v is not None and not (isinstance(v, float) and math.isnan(v)):
                        try:
                            fv = float(v)
                            if math.isfinite(fv):
                                row_clean.append(fv)
                                flat_clean.append(fv)
                        except (ValueError, TypeError):
                            pass
            if row_clean:
                subgroups.append(SubgroupInfo(row_clean))
    else:
        raw_vals = settings.get("column_data", [])
        sub_type = settings.get("subgroup_type", "size")
        if sub_type == "column" and settings.get("subgroup_data") is not None:
            sub_col = settings.get("subgroup_data", [])
            current_group: List[float] = []
            current_id = None
            for v, g in zip(raw_vals, sub_col):
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    continue
                try:
                    fv = float(v)
                    if not math.isfinite(fv):
                        continue
                except (ValueError, TypeError):
                    continue
                flat_clean.append(fv)
                if current_id is None or g != current_id:
                    if current_group:
                        subgroups.append(SubgroupInfo(current_group))
                    current_group = [fv]
                    current_id = g
                else:
                    current_group.append(fv)
            if current_group:
                subgroups.append(SubgroupInfo(current_group))
        else:
            sub_size = int(settings.get("subgroup_size", 1))
            if sub_size < 1:
                sub_size = 1
            for v in raw_vals:
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    continue
                try:
                    fv = float(v)
                    if math.isfinite(fv):
                        flat_clean.append(fv)
                except (ValueError, TypeError):
                    continue

            if sub_size == 1:
                subgroups = [SubgroupInfo([x]) for x in flat_clean]
            else:
                for i in range(0, len(flat_clean), sub_size):
                    chunk = flat_clean[i:i + sub_size]
                    if chunk:
                        subgroups.append(SubgroupInfo(chunk))

    return subgroups, flat_clean


def run_normal_sixpack(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Compute complete Process Capability Sixpack analysis for Normal distribution."""
    # Extract subgroups and individual observations
    subgroups, all_values = extract_subgroups_from_settings(settings)
    k = len(subgroups)
    if k == 0 or len(all_values) == 0:
        raise ValueError("Capability Sixpack requires valid numeric observations.")

    # Convert to arguments for run_normal_capability
    data_mode = settings.get("data_mode", "single_column")
    opts = settings.get("options", {})
    lsl_val = settings.get("lsl")
    usl_val = settings.get("usl")
    target_val = opts.get("target") or settings.get("target")

    if data_mode == "subgroups_across":
        cols_across_data = settings.get("cols_across_data", [])
        num_rows = max(len(c) for c in cols_across_data) if cols_across_data else 0
        rows_data = []
        for r in range(num_rows):
            row = [cols_across_data[ci][r] if r < len(cols_across_data[ci]) else None for ci in range(len(cols_across_data))]
            rows_data.append(row)
        capa_data = rows_data
        sub_arg = 1
        var_name = settings.get("column_name", "Data")
    else:
        capa_data = settings.get("column_data", [])
        sub_type = settings.get("subgroup_type", "size")
        if sub_type == "column":
            sub_arg = settings.get("subgroup_data")
        else:
            sub_arg = settings.get("subgroup_size", 1)
        var_name = settings.get("column_name", "Data")

    mode = settings.get("analysis_mode", opts.get("analysis_mode", "normal"))
    is_bw = (mode == "between_within")
    capa_res = run_normal_capability(
        data=capa_data,
        subgroup_spec=sub_arg,
        lsl=lsl_val,
        usl=usl_val,
        target=target_val,
        historical_mean=settings.get("historical_mean"),
        historical_stdev=settings.get("historical_stdev"),
        analysis_mode=mode,
        estimate_method_gt1=opts.get("estimate_method_gt1", opts.get("within_subgroup_method", "pooled")),
        estimate_method_eq1=opts.get("estimate_method_eq1", "amr"),
        moving_range_len=opts.get("moving_range_len", 2),
        unbiased_within=opts.get("unbiased_within", True),
        unbiased_overall=opts.get("unbiased_overall", False),
        tolerance_k=opts.get("tolerance_k", 6.0),
        display_unit=opts.get("display_unit", "ppm"),
        stats_type=opts.get("stats_type", "capability"),
        include_ci=opts.get("include_ci", False),
        confidence_level=opts.get("confidence_level", 95.0),
        ci_type=opts.get("ci_type", "two_sided"),
        variable_name=var_name,
        title=f"Process Capability Sixpack of {var_name}",
    )

    avg_n = float(np.mean([sg.n for sg in subgroups]))
    is_individual = (avg_n == 1.0)
    use_s_chart = (avg_n > 8.0)

    overall_mean = capa_res["mean"]
    sigma_within = capa_res["stdev_within"]
    sigma_overall = capa_res["stdev_overall"]

    # ----------------------------------------------------
    # Panel 1: Xbar Chart (or I Chart if n=1)
    # ----------------------------------------------------
    subgroup_indices = list(range(1, k + 1))
    means = [sg.mean for sg in subgroups]

    xbar_center = overall_mean
    xbar_ucl = []
    xbar_lcl = []
    xbar_test1_failures = []

    for i, sg in enumerate(subgroups):
        se = sigma_within / math.sqrt(sg.n) if sg.n > 0 else 0.0
        ucl = xbar_center + 3.0 * se
        lcl = xbar_center - 3.0 * se
        xbar_ucl.append(ucl)
        xbar_lcl.append(lcl)
        if sg.mean > ucl or sg.mean < lcl:
            xbar_test1_failures.append(i + 1)

    chart_x_name = "I Chart" if is_individual else "Xbar Chart"
    panel_xbar = {
        "title": chart_x_name,
        "x": subgroup_indices,
        "y": means,
        "center": xbar_center,
        "ucl": xbar_ucl,
        "lcl": xbar_lcl,
        "is_constant_limits": (len(set([sg.n for sg in subgroups])) == 1),
        "ucl_val": xbar_ucl[0] if xbar_ucl else None,
        "lcl_val": xbar_lcl[0] if xbar_lcl else None,
        "test1_failures": xbar_test1_failures,
        "ylabel": "Individual Value" if is_individual else "Sample Mean",
    }

    # ----------------------------------------------------
    # Panel 2: R Chart (or S Chart for n>8, MR Chart for n=1)
    # ----------------------------------------------------
    disp_values = []
    disp_ucl = []
    disp_lcl = []
    disp_center = 0.0
    disp_test1_failures = []

    if is_individual:
        chart_disp_name = "Moving Range Chart"
        mrs = []
        for i in range(1, len(all_values)):
            mrs.append(abs(all_values[i] - all_values[i - 1]))
        disp_values = [None] + mrs
        valid_mrs = [mr for mr in mrs if mr is not None]
        disp_center = float(np.mean(valid_mrs)) if valid_mrs else 0.0
        mr_ucl_val = 3.267 * disp_center
        mr_lcl_val = 0.0
        disp_ucl = [mr_ucl_val] * len(all_values)
        disp_lcl = [mr_lcl_val] * len(all_values)
        for i in range(1, len(all_values)):
            mr = mrs[i - 1]
            if mr > mr_ucl_val:
                disp_test1_failures.append(i + 1)
        panel_disp = {
            "title": chart_disp_name,
            "x": subgroup_indices,
            "y": disp_values,
            "center": disp_center,
            "ucl": disp_ucl,
            "lcl": disp_lcl,
            "is_constant_limits": True,
            "ucl_val": mr_ucl_val,
            "lcl_val": mr_lcl_val,
            "test1_failures": disp_test1_failures,
            "ylabel": "Moving Range",
        }
    elif use_s_chart:
        chart_disp_name = "S Chart"
        stdevs = [sg.stdev for sg in subgroups]
        disp_values = stdevs
        n_round = int(round(avg_n))
        c4_val = c4(n_round)
        disp_center = c4_val * sigma_within
        b3_val = B3_TABLE.get(n_round, max(0.0, 1.0 - 3.0 / (c4_val * math.sqrt(2.0 * (n_round - 1)))))
        b4_val = B4_TABLE.get(n_round, 1.0 + 3.0 / (c4_val * math.sqrt(2.0 * (n_round - 1))))
        for i, sg in enumerate(subgroups):
            ucl_i = b4_val * disp_center
            lcl_i = b3_val * disp_center
            disp_ucl.append(ucl_i)
            disp_lcl.append(lcl_i)
            if sg.stdev > ucl_i or sg.stdev < lcl_i:
                disp_test1_failures.append(i + 1)
        panel_disp = {
            "title": chart_disp_name,
            "x": subgroup_indices,
            "y": disp_values,
            "center": disp_center,
            "ucl": disp_ucl,
            "lcl": disp_lcl,
            "is_constant_limits": (len(set([sg.n for sg in subgroups])) == 1),
            "ucl_val": disp_ucl[0] if disp_ucl else None,
            "lcl_val": disp_lcl[0] if disp_lcl else None,
            "test1_failures": disp_test1_failures,
            "ylabel": "Sample StDev",
        }
    else:
        chart_disp_name = "R Chart"
        ranges = [sg.range for sg in subgroups]
        disp_values = ranges
        n_round = int(round(avg_n))
        d2_val = d2(n_round)
        disp_center = d2_val * sigma_within
        d3_val = D3_TABLE.get(n_round, 0.0)
        d4_val = D4_TABLE.get(n_round, 2.114)
        for i, sg in enumerate(subgroups):
            ucl_i = d4_val * disp_center
            lcl_i = d3_val * disp_center
            disp_ucl.append(ucl_i)
            disp_lcl.append(lcl_i)
            if sg.range > ucl_i or sg.range < lcl_i:
                disp_test1_failures.append(i + 1)
        panel_disp = {
            "title": chart_disp_name,
            "x": subgroup_indices,
            "y": disp_values,
            "center": disp_center,
            "ucl": disp_ucl,
            "lcl": disp_lcl,
            "is_constant_limits": (len(set([sg.n for sg in subgroups])) == 1),
            "ucl_val": disp_ucl[0] if disp_ucl else None,
            "lcl_val": disp_lcl[0] if disp_lcl else None,
            "test1_failures": disp_test1_failures,
            "ylabel": "Sample Range",
        }

    # ----------------------------------------------------
    # Panel 3: Last 25 Subgroups (Run Chart)
    # ----------------------------------------------------
    num_last = min(25, k)
    last_subgroups = subgroups[-num_last:]
    last_indices = list(range(k - num_last + 1, k + 1))

    subgroup_points = []
    last_means = []
    for idx, sg in zip(last_indices, last_subgroups):
        last_means.append((idx, sg.mean))
        for v in sg.values:
            subgroup_points.append((idx, v))

    panel_last25 = {
        "title": f"Last {num_last} Subgroups",
        "subgroup_indices": last_indices,
        "points": subgroup_points,
        "means": last_means,
        "process_mean": overall_mean,
        "ylabel": "Values",
    }

    # ----------------------------------------------------
    # Panel 4: Capability Histogram
    # ----------------------------------------------------
    panel_hist = {
        "title": "Capability Histogram",
        "observations": all_values,
        "mean": overall_mean,
        "stdev_within": sigma_within,
        "stdev_overall": sigma_overall,
        "lsl": capa_res["lsl"],
        "usl": capa_res["usl"],
        "target": capa_res["target"],
    }

    # ----------------------------------------------------
    # Panel 5: Normal Probability Plot
    # ----------------------------------------------------
    norm_res = normality(all_values)
    clean_sorted = sorted(all_values)
    n_pts = len(clean_sorted)
    blom_pcts = [100.0 * (i - 0.375) / (n_pts + 0.25) for i in range(1, n_pts + 1)]
    normal_scores = [float(stats.norm.ppf((i - 0.375) / (n_pts + 0.25))) for i in range(1, n_pts + 1)]

    panel_norm = {
        "title": "Normal Probability Plot",
        "observed": clean_sorted,
        "percentiles": blom_pcts,
        "normal_scores": normal_scores,
        "mean": overall_mean,
        "stdev": sigma_overall,
        "ad_stat": norm_res.get("anderson_darling"),
        "p_value": norm_res.get("p_value"),
    }

    # ----------------------------------------------------
    # Panel 6: Capability Plot / Capability Summary
    # ----------------------------------------------------
    obs_perf = capa_res.get("observed_perf", {})
    w_perf = capa_res.get("within_perf", {})
    o_perf = capa_res.get("overall_perf", {})

    panel_summary = {
        "title": "Capability Plot",
        "stdev_within": sigma_within,
        "stdev_overall": sigma_overall,
        "cp": capa_res.get("cp"),
        "cpl": capa_res.get("cpl"),
        "cpu": capa_res.get("cpu"),
        "cpk": capa_res.get("cpk"),
        "cpm": capa_res.get("cpm"),
        "ccpk": capa_res.get("ccpk"),
        "pp": capa_res.get("pp"),
        "ppl": capa_res.get("ppl"),
        "ppu": capa_res.get("ppu"),
        "ppk": capa_res.get("ppk"),
        "ci_cp": capa_res.get("ci_cp"),
        "ci_cpk": capa_res.get("ci_cpk"),
        "ci_pp": capa_res.get("ci_pp"),
        "ci_ppk": capa_res.get("ci_ppk"),
        "ppm_observed": obs_perf.get("total", 0.0),
        "ppm_exp_within": w_perf.get("expected_total", 0.0),
        "ppm_exp_overall": o_perf.get("expected_total", 0.0),
        "lsl": capa_res["lsl"],
        "usl": capa_res["usl"],
        "target": capa_res["target"],
    }

    stdev_bw = capa_res.get("stdev_between_within")
    if is_bw and stdev_bw:
        panel_summary["stdev_between_within"] = stdev_bw
        panel_summary["cp_bw"] = capa_res.get("cp")
        panel_summary["cpk_bw"] = capa_res.get("cpk")

    # Bundle complete sixpack payload
    sixpack_result = {
        "analysis": "capability_sixpack_between_within" if is_bw else "capability_sixpack_normal",
        "analysis_mode": mode,
        "stdev_between_within": stdev_bw,
        "column_name": var_name,
        "sample_n": capa_res["sample_n"],
        "subgroup_count": k,
        "subgroup_avg_size": avg_n,
        "mean": overall_mean,
        "sigma_within": sigma_within,
        "sigma_overall": sigma_overall,
        "within_method": capa_res.get("within_method"),
        "lsl": capa_res["lsl"],
        "usl": capa_res["usl"],
        "target": capa_res["target"],
        "capa_res": capa_res,
        "panel_xbar": panel_xbar,
        "panel_disp": panel_disp,
        "panel_last25": panel_last25,
        "panel_hist": panel_hist,
        "panel_norm": panel_norm,
        "panel_summary": panel_summary,
    }

    return sixpack_result



def run_nonnormal_sixpack(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Compute complete Process Capability Sixpack analysis for Nonnormal distributions."""
    subgroups, all_values = extract_subgroups_from_settings(settings)
    k = len(subgroups)
    if k == 0 or len(all_values) == 0:
        raise ValueError("Nonnormal Capability Sixpack requires valid numeric observations.")

    from .capability_nonnormal_engine import run_nonnormal_capability

    lsl_val = settings.get("lsl")
    usl_val = settings.get("usl")
    target_val = settings.get("target") or settings.get("options", {}).get("target")
    var_name = settings.get("column_name", "Data")
    dist_name = settings.get("distribution", "weibull").lower()

    capa_res = run_nonnormal_capability(
        values=all_values,
        dist_or_transform=dist_name,
        lsl=lsl_val,
        usl=usl_val,
        target=target_val,
    )

    avg_n = float(np.mean([sg.n for sg in subgroups]))
    is_individual = (avg_n == 1.0)

    overall_mean = float(np.mean(all_values))
    sigma_overall = float(np.std(all_values, ddof=1)) if len(all_values) > 1 else 0.0

    # Panel 1: Xbar Chart (or I Chart)
    subgroup_indices = list(range(1, k + 1))
    means = [sg.mean for sg in subgroups]
    mrs = [abs(all_values[i] - all_values[i - 1]) for i in range(1, len(all_values))]
    mean_mr = float(np.mean(mrs)) if mrs else 0.0
    sigma_mr = mean_mr / 1.128 if mean_mr > 0 else (sigma_overall or 1.0)

    xbar_center = overall_mean
    xbar_ucl = [xbar_center + 3.0 * (sigma_mr / math.sqrt(sg.n)) for sg in subgroups]
    xbar_lcl = [xbar_center - 3.0 * (sigma_mr / math.sqrt(sg.n)) for sg in subgroups]
    xbar_test1 = [i + 1 for i, m in enumerate(means) if m > xbar_ucl[i] or m < xbar_lcl[i]]

    panel_xbar = {
        "title": "I Chart" if is_individual else "Xbar Chart",
        "x": subgroup_indices,
        "y": means,
        "center": xbar_center,
        "ucl": xbar_ucl,
        "lcl": xbar_lcl,
        "ucl_val": xbar_ucl[0] if xbar_ucl else None,
        "lcl_val": xbar_lcl[0] if xbar_lcl else None,
        "test1_failures": xbar_test1,
        "ylabel": "Individual Value" if is_individual else "Sample Mean",
    }

    # Panel 2: MR Chart (or R Chart)
    if is_individual:
        disp_title = "Moving Range Chart"
        disp_values = [None] + mrs
        mr_ucl = 3.267 * mean_mr
        disp_ucl = [mr_ucl] * len(all_values)
        disp_lcl = [0.0] * len(all_values)
        disp_test1 = [i + 1 for i, mr in enumerate(mrs) if mr > mr_ucl]
        disp_center = mean_mr
    else:
        disp_title = "R Chart"
        disp_values = [sg.range for sg in subgroups]
        disp_center = float(np.mean(disp_values)) if disp_values else 0.0
        disp_ucl = [2.114 * disp_center] * k
        disp_lcl = [0.0] * k
        disp_test1 = [i + 1 for i, r in enumerate(disp_values) if r > disp_ucl[i]]

    panel_disp = {
        "title": disp_title,
        "x": list(range(1, len(disp_values) + 1)),
        "y": disp_values,
        "center": disp_center,
        "ucl": disp_ucl,
        "lcl": disp_lcl,
        "ucl_val": disp_ucl[0] if disp_ucl else None,
        "lcl_val": 0.0,
        "test1_failures": disp_test1,
        "ylabel": "Moving Range" if is_individual else "Sample Range",
    }

    # Panel 3: Last 25 subgroups
    recent_sgs = subgroups[-25:] if len(subgroups) > 25 else subgroups
    panel_last25 = {
        "title": "Last 25 Subgroups",
        "subgroups": [list(sg.values) for sg in recent_sgs],
        "means": [sg.mean for sg in recent_sgs],
        "overall_mean": overall_mean,
        "start_idx": max(1, k - len(recent_sgs) + 1),
    }

    # Panel 4: Capability Histogram
    counts, bin_edges = np.histogram(all_values, bins="auto")
    panel_hist = {
        "title": "Capability Histogram",
        "counts": counts.tolist(),
        "bin_edges": bin_edges.tolist(),
        "lsl": lsl_val,
        "usl": usl_val,
        "target": target_val,
        "distribution": dist_name,
        "fit_info": capa_res.get("fit_info", {}),
    }

    # Panel 5: Nonnormal Probability Plot
    sorted_vals = np.sort(all_values)
    n_sorted = len(sorted_vals)
    blom_pcts = [((i + 1 - 0.375) / (n_sorted + 0.25)) * 100.0 for i in range(n_sorted)]
    ad_stat = capa_res.get("fit_info", {}).get("anderson_darling", 0.0)
    p_val = capa_res.get("fit_info", {}).get("p_value")

    panel_norm = {
        "title": f"Probability Plot ({dist_name.capitalize()})",
        "observed": sorted_vals.tolist(),
        "percentiles": blom_pcts,
        "distribution": dist_name,
        "ad_stat": ad_stat,
        "p_value": p_val,
    }

    # Panel 6: Capability Summary
    indices = capa_res.get("indices", {})
    panel_summary = {
        "title": "Capability Plot",
        "distribution": dist_name,
        "pp": indices.get("pp"),
        "ppl": indices.get("ppl"),
        "ppu": indices.get("ppu"),
        "ppk": indices.get("ppk"),
        "z_bench": capa_res.get("benchmark_z", {}).get("z_bench"),
        "ppm_observed": capa_res.get("observed_ppm", {}).get("total", 0.0),
        "ppm_expected": capa_res.get("expected_ppm", {}).get("total", 0.0),
        "lsl": lsl_val,
        "usl": usl_val,
        "target": target_val,
    }

    return {
        "analysis": "capability_sixpack_nonnormal",
        "distribution": dist_name,
        "column_name": var_name,
        "sample_n": len(all_values),
        "subgroup_count": k,
        "subgroup_avg_size": avg_n,
        "mean": overall_mean,
        "sigma_overall": sigma_overall,
        "lsl": lsl_val,
        "usl": usl_val,
        "target": target_val,
        "capa_res": capa_res,
        "panel_xbar": panel_xbar,
        "panel_disp": panel_disp,
        "panel_last25": panel_last25,
        "panel_hist": panel_hist,
        "panel_norm": panel_norm,
        "panel_summary": panel_summary,
    }
