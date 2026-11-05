"""Computational Engine for JMP Process Screening Platform.

Screen dozens to hundreds of manufacturing / lab process parameters simultaneously:
- Calculates Stability Index (s_overall / s_within)
- Identifies out-of-control special-cause drift and Nelson alarms
- Evaluates capability indices (Cp, Cpk, Pp, Ppk) and defect PPM
- Categorizes process health status (Stable & Capable, Unstable, Incapable)
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
import numpy as np

from .subgroup_control import d2


def _normal_cdf(z: float) -> float:
    """Standard normal cumulative distribution function using math.erf."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def calculate_process_screening(
    columns_data: List[Dict[str, Any]],
    subgroup_size: int = 1,
    subgroup_values: Optional[List[Any]] = None,
    specs_dict: Optional[Dict[str, Dict[str, Optional[float]]]] = None,
    k_sigma: float = 3.0,
) -> Dict[str, Any]:
    """Perform multi-process capability and stability screening.
    
    columns_data: list of dicts with keys: 'name', 'index', 'values'
    specs_dict: optional mapping of column name -> {'lsl': float, 'target': float, 'usl': float}
    """
    if not columns_data:
        raise ValueError("At least one process variable must be provided for screening.")

    results: List[Dict[str, Any]] = []

    for col in columns_data:
        col_name = col["name"]
        col_idx = col["index"]
        raw_vals = col["values"]

        # Clean numeric observations
        clean_vals: List[float] = []
        for v in raw_vals:
            if v is None or v == "":
                continue
            try:
                fv = float(v)
                if math.isfinite(fv):
                    clean_vals.append(fv)
            except (ValueError, TypeError):
                continue

        n_obs = len(clean_vals)
        if n_obs < 3:
            # Skip series with insufficient data
            continue

        arr = np.array(clean_vals, dtype=float)
        mean_val = float(np.mean(arr))
        s_overall = float(np.std(arr, ddof=1)) if n_obs > 1 else 0.0

        # Calculate within-subgroup variation
        if subgroup_size <= 1 and (subgroup_values is None or len(subgroup_values) != len(raw_vals)):
            # Moving Range method
            mr_list = [abs(arr[i] - arr[i - 1]) for i in range(1, n_obs)]
            mr_bar = float(np.mean(mr_list)) if mr_list else 0.0
            s_within = mr_bar / d2(2) if mr_bar > 0 else s_overall
        else:
            # Fixed subgroup chunks of subgroup_size
            sz = max(2, subgroup_size)
            ranges: List[float] = []
            for j in range(0, n_obs - sz + 1, sz):
                chunk = arr[j:j + sz]
                ranges.append(float(np.ptp(chunk)))
            r_bar = float(np.mean(ranges)) if ranges else 0.0
            d2_val = d2(sz)
            s_within = r_bar / d2_val if (d2_val > 0 and r_bar > 0) else s_overall

        # Stability Index = s_overall / s_within
        if s_within > 1e-12:
            stability_index = s_overall / s_within
        else:
            stability_index = 1.0

        if stability_index < 1.25:
            stability_status = "Stable"
            stability_color = "#16a34a"  # Green
        elif stability_index < 1.50:
            stability_status = "Alert"
            stability_color = "#ca8a04"  # Amber
        else:
            stability_status = "Unstable"
            stability_color = "#dc2626"  # Red

        # Out-of-control checks (3-sigma limits and 9 in a row)
        ucl = mean_val + k_sigma * s_within
        lcl = mean_val - k_sigma * s_within
        alarm_indices: List[int] = []

        for idx, y in enumerate(arr):
            if y > ucl or y < lcl:
                alarm_indices.append(idx)
            elif idx >= 8:
                run = arr[idx - 8:idx + 1]
                if all(val > mean_val for val in run) or all(val < mean_val for val in run):
                    alarm_indices.append(idx)

        unique_alarms = sorted(set(alarm_indices))
        alarm_count = len(unique_alarms)
        alarm_rate = (alarm_count / n_obs * 100.0) if n_obs > 0 else 0.0

        # Specifications and Capability
        col_specs = (specs_dict or {}).get(col_name, {})
        lsl = col_specs.get("lsl")
        usl = col_specs.get("usl")
        target = col_specs.get("target")

        has_specs = (lsl is not None) or (usl is not None)

        if not has_specs:
            # Auto-derived 3-sigma specifications for baseline reference
            lsl = mean_val - 3.0 * s_overall
            usl = mean_val + 3.0 * s_overall
            has_specs = False  # Mark as estimated

        # Compute Pp and Ppk (overall)
        pp = None
        ppk = None
        cp = None
        cpk = None
        ppm_defect = 0.0

        if lsl is not None and usl is not None and usl > lsl:
            if s_overall > 1e-12:
                pp = (usl - lsl) / (6.0 * s_overall)
                cpu_p = (usl - mean_val) / (3.0 * s_overall)
                cpl_p = (mean_val - lsl) / (3.0 * s_overall)
                ppk = min(cpu_p, cpl_p)
            if s_within > 1e-12:
                cp = (usl - lsl) / (6.0 * s_within)
                cpu_c = (usl - mean_val) / (3.0 * s_within)
                cpl_c = (mean_val - lsl) / (3.0 * s_within)
                cpk = min(cpu_c, cpl_c)

            # Defect PPM calculation
            if s_overall > 1e-12:
                p_below = _normal_cdf((lsl - mean_val) / s_overall)
                p_above = 1.0 - _normal_cdf((usl - mean_val) / s_overall)
                ppm_defect = (p_below + p_above) * 1e6
        elif usl is not None:
            if s_overall > 1e-12:
                ppk = (usl - mean_val) / (3.0 * s_overall)
                p_above = 1.0 - _normal_cdf((usl - mean_val) / s_overall)
                ppm_defect = p_above * 1e6
            if s_within > 1e-12:
                cpk = (usl - mean_val) / (3.0 * s_within)
        elif lsl is not None:
            if s_overall > 1e-12:
                ppk = (mean_val - lsl) / (3.0 * s_overall)
                p_below = _normal_cdf((lsl - mean_val) / s_overall)
                ppm_defect = p_below * 1e6
            if s_within > 1e-12:
                cpk = (mean_val - lsl) / (3.0 * s_within)

        # Health Classification
        is_stable = stability_index < 1.25
        is_capable = (ppk is not None) and (ppk >= 1.33)

        if is_stable and is_capable:
            status_label = "Capable & Stable"
            status_color = "#16a34a"  # Green
            health_code = 1
        elif is_capable and not is_stable:
            status_label = "Capable, Needs Monitoring"
            status_color = "#ca8a04"  # Amber
            health_code = 2
        elif is_stable and not is_capable:
            status_label = "Stable, Low Capability"
            status_color = "#ea580c"  # Orange
            health_code = 3
        else:
            status_label = "Unstable & Incapable"
            status_color = "#dc2626"  # Red
            health_code = 4

        results.append({
            "process": col_name,
            "col_index": col_idx,
            "n": n_obs,
            "mean": mean_val,
            "stdev_overall": s_overall,
            "stdev_within": s_within,
            "stability_index": round(stability_index, 3),
            "stability_status": stability_status,
            "stability_color": stability_color,
            "alarms_count": alarm_count,
            "alarm_rate": round(alarm_rate, 2),
            "lsl": lsl,
            "usl": usl,
            "target": target,
            "has_specs": has_specs,
            "cp": round(cp, 3) if cp is not None else None,
            "cpk": round(cpk, 3) if cpk is not None else None,
            "pp": round(pp, 3) if pp is not None else None,
            "ppk": round(ppk, 3) if ppk is not None else None,
            "ppm_defect": round(ppm_defect, 1),
            "status_label": status_label,
            "status_color": status_color,
            "health_code": health_code,
        })

    if not results:
        raise ValueError("None of the selected variables contained sufficient numeric observations (>=3).")

    # Overall Summary Scorecard
    total_screened = len(results)
    stable_count = sum(1 for r in results if r["stability_index"] < 1.25)
    capable_count = sum(1 for r in results if r["ppk"] is not None and r["ppk"] >= 1.33)
    alarms_processes_count = sum(1 for r in results if r["alarms_count"] > 0)

    worst_stability = max(results, key=lambda r: r["stability_index"])
    lowest_ppk = min([r for r in results if r["ppk"] is not None] or results, key=lambda r: r["ppk"] if r["ppk"] is not None else 999.0)

    return {
        "analysis": "process_screening",
        "title": f"Process Screening ({total_screened} Variables)",
        "subgroup_size": subgroup_size,
        "k_sigma": k_sigma,
        "total_screened": total_screened,
        "stable_count": stable_count,
        "stable_percent": round(stable_count / total_screened * 100.0, 1),
        "capable_count": capable_count,
        "capable_percent": round(capable_count / total_screened * 100.0, 1),
        "alarms_processes_count": alarms_processes_count,
        "worst_stability_process": worst_stability["process"],
        "worst_stability_index": worst_stability["stability_index"],
        "lowest_ppk_process": lowest_ppk["process"],
        "lowest_ppk": lowest_ppk["ppk"],
        "processes": results,
    }
