"""Six Sigma Quality Tools: Process Capability Sigma Report & Rolled Throughput Yield."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence
import numpy as np
from scipy import stats


def _clean_vals(values: Sequence[Any]) -> np.ndarray:
    nums = []
    for v in values:
        if v is None or isinstance(v, bool):
            continue
        try:
            f = float(v)
            if math.isfinite(f):
                nums.append(f)
        except (ValueError, TypeError):
            continue
    if len(nums) < 3:
        raise ValueError("Six Sigma Process Report requires at least 3 numeric measurements.")
    return np.asarray(nums, dtype=float)


def six_sigma_process_report(
    values: Sequence[Any],
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    subgroup_size: int = 1,
    sigma_shift: float = 1.5,
    variable_name: str = "Process",
) -> Dict[str, Any]:
    """Compute Six Sigma Process Report (Z-Bench, Z.st, Z.lt, Yield%, DPMO, Cpk, Ppk)."""
    if lsl is None and usl is None:
        raise ValueError("Specify at least one specification limit (LSL or USL).")
    if lsl is not None and usl is not None and lsl >= usl:
        raise ValueError("LSL must be strictly less than USL.")

    arr = _clean_vals(values)
    n = len(arr)
    mean = float(np.mean(arr))
    stdev_overall = float(np.std(arr, ddof=1))
    if stdev_overall <= 0:
        raise ValueError("Process observations have zero variance.")

    # Within-subgroup stdev (MR-bar / d2 for subgroup_size == 1, or R-bar / d2)
    sg = max(1, int(subgroup_size))
    if sg == 1:
        mr = np.abs(np.diff(arr))
        stdev_within = float(np.mean(mr) / 1.128) if len(mr) > 0 else stdev_overall
    else:
        n_groups = n // sg
        if n_groups < 1:
            stdev_within = stdev_overall
        else:
            d2_map = {2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970, 10: 3.078}
            d2 = d2_map.get(min(sg, 10), 3.078)
            ranges = [float(np.ptp(arr[i * sg:(i + 1) * sg])) for i in range(n_groups)]
            stdev_within = float(np.mean(ranges) / d2)
    stdev_within = max(stdev_within, 1e-12)

    # Defect probability Overall (Long-Term) & Within (Short-Term)
    p_lt = 0.0
    p_st = 0.0
    if lsl is not None:
        p_lt += float(stats.norm.cdf((lsl - mean) / stdev_overall))
        p_st += float(stats.norm.cdf((lsl - mean) / stdev_within))
    if usl is not None:
        p_lt += float(1.0 - stats.norm.cdf((usl - mean) / stdev_overall))
        p_st += float(1.0 - stats.norm.cdf((usl - mean) / stdev_within))

    p_lt = float(np.clip(p_lt, 1e-15, 1.0 - 1e-15))
    p_st = float(np.clip(p_st, 1e-15, 1.0 - 1e-15))
    z_lt = float(stats.norm.ppf(1.0 - p_lt))
    z_st = float(stats.norm.ppf(1.0 - p_st))
    # Observed empirical out-of-spec
    oos_count = int(sum(1 for v in arr if (lsl is not None and v < lsl) or (usl is not None and v > usl)))
    dpmo_observed = 1_000_000.0 * oos_count / n
    dpmo_expected_lt = 1_000_000.0 * p_lt
    dpmo_expected_st = 1_000_000.0 * p_st

    cp = (usl - lsl) / (6.0 * stdev_within) if (lsl is not None and usl is not None) else None
    pp = (usl - lsl) / (6.0 * stdev_overall) if (lsl is not None and usl is not None) else None
    cpu = (usl - mean) / (3.0 * stdev_within) if usl is not None else None
    cpl = (mean - lsl) / (3.0 * stdev_within) if lsl is not None else None
    cpk = min(x for x in (cpl, cpu) if x is not None)

    ppu = (usl - mean) / (3.0 * stdev_overall) if usl is not None else None
    ppl = (mean - lsl) / (3.0 * stdev_overall) if lsl is not None else None
    ppk = min(x for x in (ppl, ppu) if x is not None)

    return {
        "analysis": "six_sigma_process_report",
        "variable": variable_name,
        "n": n,
        "lsl": lsl,
        "usl": usl,
        "mean": mean,
        "stdev_within": stdev_within,
        "stdev_overall": stdev_overall,
        "z_bench_lt": z_lt,
        "z_bench_st": z_st,
        "sigma_level_est": z_lt + float(sigma_shift),
        "yield_pct_lt": (1.0 - p_lt) * 100.0,
        "dpmo_expected_lt": dpmo_expected_lt,
        "dpmo_expected_st": dpmo_expected_st,
        "dpmo_observed": dpmo_observed,
        "cp": cp,
        "cpk": cpk,
        "pp": pp,
        "ppk": ppk,
    }


def rolled_throughput_yield(
    step_yields_pct: Sequence[float],
    process_name: str = "Product Process",
) -> Dict[str, Any]:
    """Compute Six Sigma Product Report / Rolled Throughput Yield (RTY) across process steps."""
    if not step_yields_pct:
        raise ValueError("Enter at least one step yield percentage.")
    yields = []
    for y in step_yields_pct:
        yf = float(y)
        if not 0.0 < yf <= 100.0:
            raise ValueError("Step yield percentages must lie in (0, 100].")
        yields.append(yf / 100.0)

    rty = float(np.prod(yields))
    rty_clipped = float(np.clip(rty, 1e-12, 1.0 - 1e-12))
    z_equiv = float(stats.norm.ppf(rty_clipped)) + 1.5
    dpmo_total = (1.0 - rty) * 1_000_000.0
    dpu_total = -math.log(max(rty, 1e-12))

    return {
        "analysis": "six_sigma_product_report",
        "process": process_name,
        "steps": len(yields),
        "step_yields_pct": [y * 100.0 for y in yields],
        "rty_pct": rty * 100.0,
        "dpu_total": dpu_total,
        "dpmo_total": dpmo_total,
        "equivalent_sigma_level": z_equiv,
    }


def format_six_sigma_report(result: Dict[str, Any]) -> str:
    kind = result.get("analysis", "")
    lines = []
    if kind == "six_sigma_process_report":
        lines.extend([
            f"Six Sigma Process Report: {result['variable']}",
            f"  N = {result['n']}   |   Mean = {result['mean']:.5g}   |   StDev(Within) = {result['stdev_within']:.5g}   |   StDev(Overall) = {result['stdev_overall']:.5g}",
            f"  LSL = {result['lsl']}   |   USL = {result['usl']}",
            "",
            "  Six Sigma Benchmark Metrics:",
            f"    Z.Bench (Long-Term)  : {result['z_bench_lt']:.4f}",
            f"    Z.Bench (Short-Term) : {result['z_bench_st']:.4f}",
            f"    Sigma Level (+1.5s)  : {result['sigma_level_est']:.4f} sigma",
            f"    Expected Yield (LT)  : {result['yield_pct_lt']:.4f}%",
            f"    Expected DPMO (LT)   : {result['dpmo_expected_lt']:.1f}   |   Observed DPMO: {result['dpmo_observed']:.1f}",
            f"    Capability Ratios    : Cp = {result['cp'] or 'N/A'}   Cpk = {result['cpk']:.4f}   Pp = {result['pp'] or 'N/A'}   Ppk = {result['ppk']:.4f}",
        ])
    elif kind == "six_sigma_product_report":
        lines.extend([
            f"Six Sigma Product Report (Rolled Throughput Yield): {result['process']}",
            f"  Stages = {result['steps']}   |   Step Yields (%) = {', '.join(f'{y:.2f}%' for y in result['step_yields_pct'])}",
            f"  Rolled Throughput Yield (RTY): {result['rty_pct']:.4f}%",
            f"  Defects Per Unit (DPU)       : {result['dpu_total']:.5f}",
            f"  Total DPMO                   : {result['dpmo_total']:.1f}",
            f"  Process Sigma Level (+1.5s)  : {result['equivalent_sigma_level']:.4f} sigma",
        ])
    return "\n".join(lines)
