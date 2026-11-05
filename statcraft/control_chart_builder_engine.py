"""Computational Engine for JMP Control Chart Builder Platform.

Supports:
- Shewhart Individual & Moving Range (I-MR)
- Xbar-R and Xbar-S charts with dynamic subgrouping
- Multi-phase partitioning (distinct phase boundaries, separate limits/center lines)
- Nelson / Western Electric alarm detection
- Phase limit summaries and within-subgroup variation estimation
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from .subgroup_control import d2, d3, c4, c5


def _clean_float(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def calculate_control_chart_builder(
    y_values: List[Any],
    subgroup_values: Optional[List[Any]] = None,
    subgroup_size: int = 1,
    phase_values: Optional[List[Any]] = None,
    y_name: str = "Y",
    subgroup_name: Optional[str] = None,
    phase_name: Optional[str] = None,
    chart_type: str = "auto",  # 'auto', 'imr', 'xbar_r', 'xbar_s'
    k_sigma: float = 3.0,
) -> Dict[str, Any]:
    """Perform Control Chart Builder analysis across phases."""
    n_total = len(y_values)
    if n_total < 2:
        raise ValueError("At least 2 observations are required to build a control chart.")

    # 1. Clean and organize observation records
    records: List[Dict[str, Any]] = []
    for i in range(n_total):
        y_val = _clean_float(y_values[i])
        if y_val is None:
            continue
        sub_val = subgroup_values[i] if subgroup_values is not None and i < len(subgroup_values) else None
        ph_val = str(phase_values[i]).strip() if phase_values is not None and i < len(phase_values) and phase_values[i] is not None and str(phase_values[i]).strip() != "" else "Phase 1"
        records.append({
            "orig_index": i + 1,
            "y": y_val,
            "subgroup_id": sub_val,
            "phase": ph_val,
        })

    if len(records) < 2:
        raise ValueError("At least 2 valid numeric observations are required.")

    # 2. Determine Subgroups and Phases
    # Distinct phases in order of first appearance
    phase_order: List[str] = []
    for rec in records:
        if rec["phase"] not in phase_order:
            phase_order.append(rec["phase"])

    # Determine whether we do I-MR or Subgrouped (Xbar)
    has_subgroup_col = subgroup_values is not None and any(r["subgroup_id"] is not None for r in records)
    use_fixed_subgroups = (not has_subgroup_col) and (subgroup_size > 1)

    effective_subgrouped = has_subgroup_col or use_fixed_subgroups
    if chart_type == "auto":
        resolved_type = "xbar_r" if effective_subgrouped else "imr"
    else:
        resolved_type = chart_type.lower()
        if resolved_type not in ("imr", "xbar_r", "xbar_s"):
            resolved_type = "imr" if not effective_subgrouped else "xbar_r"

    # 3. Process Each Phase
    phase_results: List[Dict[str, Any]] = []
    all_points: List[Dict[str, Any]] = []
    all_disp_points: List[Dict[str, Any]] = []

    global_subgroup_counter = 0

    for p_name in phase_order:
        phase_recs = [r for r in records if r["phase"] == p_name]
        if not phase_recs:
            continue

        if resolved_type == "imr":
            # Individual observations
            p_subgroups = [[r] for r in phase_recs]
        elif has_subgroup_col:
            # Group by subgroup_id within phase preserving order
            sg_dict: Dict[Any, List[Dict[str, Any]]] = {}
            for r in phase_recs:
                sg_key = r["subgroup_id"]
                if sg_key not in sg_dict:
                    sg_dict[sg_key] = []
                sg_dict[sg_key].append(r)
            p_subgroups = list(sg_dict.values())
        else:
            # Chunk into fixed subgroup_size
            sz = max(1, subgroup_size)
            p_subgroups = [phase_recs[j:j + sz] for j in range(0, len(phase_recs), sz)]

        # Calculate subgroup stats
        p_means: List[float] = []
        p_ranges: List[float] = []
        p_stdevs: List[float] = []
        p_sizes: List[int] = []
        p_subgroup_labels: List[str] = []

        for sg in p_subgroups:
            global_subgroup_counter += 1
            vals = [item["y"] for item in sg]
            n_sg = len(vals)
            p_sizes.append(n_sg)
            m = float(np.mean(vals))
            p_means.append(m)
            if n_sg >= 2:
                p_ranges.append(float(np.ptp(vals)))
                p_stdevs.append(float(np.std(vals, ddof=1)))
            else:
                p_ranges.append(0.0)
                p_stdevs.append(0.0)

            first_rec = sg[0]
            if resolved_type == "imr":
                lbl = str(first_rec["orig_index"])
            elif has_subgroup_col:
                lbl = str(first_rec["subgroup_id"])
            else:
                lbl = str(global_subgroup_counter)
            p_subgroup_labels.append(lbl)

        k_p = len(p_subgroups)
        tot_n = sum(p_sizes)

        # Center line and sigma estimation for phase
        if resolved_type == "imr":
            # I-MR formulas
            x_bar = float(np.mean(p_means))
            mr_vals: List[float] = []
            for j in range(1, k_p):
                mr_vals.append(abs(p_means[j] - p_means[j - 1]))
            mr_bar = float(np.mean(mr_vals)) if mr_vals else 0.0
            sigma_within = mr_bar / d2(2) if mr_bar > 0 else 0.0

            ucl_x = x_bar + k_sigma * sigma_within
            lcl_x = x_bar - k_sigma * sigma_within
            cl_x = x_bar

            cl_disp = mr_bar
            ucl_disp = 3.267 * mr_bar  # D4 for n=2 is 3.267
            lcl_disp = 0.0  # D3 for n=2 is 0.0

            disp_vals = [None] + mr_vals  # First point has no MR
        elif resolved_type == "xbar_s":
            # Xbar-S formulas
            x_bar = float(sum(p_sizes[j] * p_means[j] for j in range(k_p)) / tot_n) if tot_n > 0 else 0.0
            valid_s = [p_stdevs[j] for j in range(k_p) if p_sizes[j] >= 2]
            s_bar = float(np.mean(valid_s)) if valid_s else 0.0
            avg_n = int(round(np.mean(p_sizes))) if p_sizes else 2
            c4_val = c4(avg_n)
            sigma_within = s_bar / c4_val if c4_val > 0 else s_bar

            cl_x = x_bar
            ucl_x = x_bar + k_sigma * (sigma_within / math.sqrt(max(1, avg_n)))
            lcl_x = x_bar - k_sigma * (sigma_within / math.sqrt(max(1, avg_n)))

            cl_disp = s_bar
            c5_val = c5(avg_n)
            ucl_disp = s_bar + k_sigma * (c5_val / c4_val) * s_bar if c4_val > 0 else s_bar * 2.0
            lcl_disp = max(0.0, s_bar - k_sigma * (c5_val / c4_val) * s_bar) if c4_val > 0 else 0.0
            disp_vals = p_stdevs
        else:
            # Xbar-R formulas (default)
            x_bar = float(sum(p_sizes[j] * p_means[j] for j in range(k_p)) / tot_n) if tot_n > 0 else 0.0
            valid_r = [p_ranges[j] for j in range(k_p) if p_sizes[j] >= 2]
            r_bar = float(np.mean(valid_r)) if valid_r else 0.0
            avg_n = int(round(np.mean(p_sizes))) if p_sizes else 2
            d2_val = d2(avg_n)
            d3_val = d3(avg_n)
            sigma_within = r_bar / d2_val if d2_val > 0 else 0.0

            cl_x = x_bar
            ucl_x = x_bar + k_sigma * (sigma_within / math.sqrt(max(1, avg_n)))
            lcl_x = x_bar - k_sigma * (sigma_within / math.sqrt(max(1, avg_n)))

            cl_disp = r_bar
            ucl_disp = r_bar + k_sigma * (d3_val / d2_val) * r_bar if d2_val > 0 else r_bar * 2.0
            lcl_disp = max(0.0, r_bar - k_sigma * (d3_val / d2_val) * r_bar) if d2_val > 0 else 0.0
            disp_vals = p_ranges

        # 4. Check Nelson / Western Electric Rules on Means/Individuals
        alarms_phase = 0
        point_records: List[Dict[str, Any]] = []
        for j in range(k_p):
            val = p_means[j]
            violations: List[int] = []

            # Test 1: 1 point > 3 sigma beyond center line
            if val > ucl_x or val < lcl_x:
                violations.append(1)

            # Test 2: 9 points in a row on same side of center line
            if j >= 8:
                run = p_means[j - 8:j + 1]
                if all(v > cl_x for v in run) or all(v < cl_x for v in run):
                    violations.append(2)

            # Test 3: 6 points in a row steadily increasing or decreasing
            if j >= 5:
                run = p_means[j - 5:j + 1]
                if all(run[k] < run[k + 1] for k in range(5)) or all(run[k] > run[k + 1] for k in range(5)):
                    violations.append(3)

            # Test 4: 14 points alternating up and down
            if j >= 13:
                run = p_means[j - 13:j + 1]
                diffs = [run[k + 1] - run[k] for k in range(13)]
                if all(diffs[k] * diffs[k + 1] < 0 for k in range(12)):
                    violations.append(4)

            is_alarm = len(violations) > 0
            if is_alarm:
                alarms_phase += 1

            pt_entry = {
                "subgroup_index": len(all_points) + 1,
                "label": p_subgroup_labels[j],
                "phase": p_name,
                "value": val,
                "ucl": ucl_x,
                "cl": cl_x,
                "lcl": lcl_x,
                "size": p_sizes[j],
                "alarm": is_alarm,
                "violations": violations,
            }
            point_records.append(pt_entry)
            all_points.append(pt_entry)

            # Dispersion point entry
            disp_val = disp_vals[j]
            disp_alarm = False
            if disp_val is not None:
                if disp_val > ucl_disp or disp_val < lcl_disp:
                    disp_alarm = True

            all_disp_points.append({
                "subgroup_index": len(all_disp_points) + 1,
                "label": p_subgroup_labels[j],
                "phase": p_name,
                "value": disp_val,
                "ucl": ucl_disp,
                "cl": cl_disp,
                "lcl": lcl_disp,
                "alarm": disp_alarm,
            })

        phase_summary = {
            "phase": p_name,
            "k_subgroups": k_p,
            "n_observations": tot_n,
            "mean": x_bar,
            "ucl_x": ucl_x,
            "cl_x": cl_x,
            "lcl_x": lcl_x,
            "disp_name": "Moving Range" if resolved_type == "imr" else ("Range" if resolved_type == "xbar_r" else "StDev"),
            "disp_symbol": "MR" if resolved_type == "imr" else ("R" if resolved_type == "xbar_r" else "S"),
            "ucl_disp": ucl_disp,
            "cl_disp": cl_disp,
            "lcl_disp": lcl_disp,
            "sigma_within": sigma_within,
            "alarms_count": alarms_phase,
            "alarm_rate": (alarms_phase / k_p * 100.0) if k_p > 0 else 0.0,
        }
        phase_results.append(phase_summary)

    total_alarms = sum(p["alarms_count"] for p in phase_results)
    total_subgroups = len(all_points)

    result: Dict[str, Any] = {
        "analysis": "control_chart_builder",
        "title": f"Control Chart Builder - {y_name}",
        "y_name": y_name,
        "subgroup_name": subgroup_name,
        "phase_name": phase_name,
        "chart_type": resolved_type,
        "primary_label": "Individual Value" if resolved_type == "imr" else "Sample Mean",
        "disp_label": "Moving Range" if resolved_type == "imr" else ("Sample Range" if resolved_type == "xbar_r" else "Sample StDev"),
        "k_sigma": k_sigma,
        "phases": phase_results,
        "points": all_points,
        "disp_points": all_disp_points,
        "total_subgroups": total_subgroups,
        "total_alarms": total_alarms,
        "is_stable": total_alarms == 0,
    }
    return result
