"""Statistical engine for Acceptance Control Charts (ISO 7870-3 / AIAG / VDA SPC)."""

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy.stats import norm

from .capability_engine import c4, d2


def run_acceptance_control_chart(
    data: Union[List[float], List[List[float]], np.ndarray],
    subgroup_spec: Union[int, List[Any], np.ndarray] = 1,
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    target: Optional[float] = None,
    delta: float = 0.001,               # Acceptable fraction nonconforming (default 0.1%)
    alpha: float = 0.05,                # Producer's risk (default 5%)
    historical_stdev: Optional[float] = None,
    estimate_method: str = "pooled",    # 'pooled', 'rbar', 'sbar'
    unbiased: bool = True,
    variable_name: str = "Data",
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute Acceptance Control Chart computation."""
    if lsl is None and usl is None:
        raise ValueError("Acceptance Control Chart requires at least one specification limit (LSL or USL).")

    if lsl is not None and usl is not None and lsl >= usl:
        raise ValueError("Lower specification limit must be strictly less than upper specification limit.")

    if delta <= 0.0 or delta >= 0.5:
        raise ValueError("Acceptable fraction nonconforming (delta) must be between 0 and 0.5.")

    if alpha <= 0.0 or alpha >= 0.5:
        raise ValueError("Producer's risk (alpha) must be between 0 and 0.5.")

    # 1. Parse Subgroups
    subgroups_data: List[List[float]] = []
    all_obs: List[float] = []

    if isinstance(data, (list, np.ndarray)) and len(data) > 0 and isinstance(data[0], (list, tuple, np.ndarray)):
        # Data arranged across rows
        for row in data:
            row_clean = [float(v) for v in row if v is not None and not (isinstance(v, float) and math.isnan(v))]
            if row_clean:
                subgroups_data.append(row_clean)
                all_obs.extend(row_clean)
    elif isinstance(subgroup_spec, (list, tuple, np.ndarray)):
        # Subgroup indicator column
        from collections import OrderedDict
        grouped: OrderedDict = OrderedDict()
        for v, g in zip(data, subgroup_spec):
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                fv = float(v)
                all_obs.append(fv)
                if g not in grouped:
                    grouped[g] = []
                grouped[g].append(fv)
        subgroups_data = list(grouped.values())
    elif isinstance(subgroup_spec, int):
        sz = max(1, subgroup_spec)
        clean_obs = [float(v) for v in data if v is not None and not (isinstance(v, float) and math.isnan(v))]
        all_obs = clean_obs
        if sz <= 1:
            raise ValueError("Acceptance Control Chart requires subgroups of size greater than 1.")
        for i in range(0, len(clean_obs), sz):
            chunk = clean_obs[i : i + sz]
            if chunk:
                subgroups_data.append(chunk)
    else:
        raise ValueError("Invalid subgroup specification.")

    if len(subgroups_data) < 2:
        raise ValueError("Acceptance Control Chart requires at least two subgroups.")

    subgroup_sizes = [len(sg) for sg in subgroups_data]
    subgroup_means = [float(np.mean(sg)) for sg in subgroups_data]
    subgroup_ranges = [float(np.ptp(sg)) if len(sg) > 1 else 0.0 for sg in subgroups_data]
    subgroup_sds = [float(np.std(sg, ddof=1)) if len(sg) > 1 else 0.0 for sg in subgroups_data]
    total_n = sum(subgroup_sizes)
    k_subgroups = len(subgroups_data)
    avg_subgroup_size = float(np.mean(subgroup_sizes))
    n_effective = avg_subgroup_size

    grand_mean = float(np.mean(all_obs))

    # 2. Standard deviation estimation
    if historical_stdev is not None and historical_stdev > 0:
        sigma = float(historical_stdev)
        sigma_source = "Historical"
    else:
        sigma_source = f"Estimated ({estimate_method})"
        if estimate_method == "rbar":
            mean_r = float(np.mean(subgroup_ranges))
            d2_val = d2(int(round(avg_subgroup_size)))
            sigma = mean_r / d2_val if d2_val > 0 else float(np.std(all_obs, ddof=1))
        elif estimate_method == "sbar":
            mean_s = float(np.mean(subgroup_sds))
            c4_val = c4(int(round(avg_subgroup_size))) if unbiased else 1.0
            sigma = mean_s / c4_val if c4_val > 0 else float(np.std(all_obs, ddof=1))
        else:  # 'pooled'
            sum_sq = sum((n - 1) * (s ** 2) for n, s in zip(subgroup_sizes, subgroup_sds) if n > 1)
            df = sum(n - 1 for n in subgroup_sizes if n > 1)
            if df > 0:
                s_pool = math.sqrt(sum_sq / df)
                c4_val = c4(df + 1) if unbiased else 1.0
                sigma = s_pool / c4_val if c4_val > 0 else s_pool
            else:
                sigma = float(np.std(all_obs, ddof=1))

    if sigma <= 0:
        sigma = 1e-9

    # 3. Z values
    z_delta = float(norm.ppf(1.0 - delta))
    z_alpha = float(norm.ppf(1.0 - alpha))
    sigma_mean = sigma / math.sqrt(n_effective)

    # 4. Acceptance Limits Computation
    # Band offset from specification limit: (z_delta * sigma + z_alpha * sigma / sqrt(n))
    band_offset = (z_delta + (z_alpha / math.sqrt(n_effective))) * sigma

    apl_upper: Optional[float] = None
    uacl: Optional[float] = None
    if usl is not None:
        apl_upper = usl - z_delta * sigma
        uacl = usl - band_offset

    apl_lower: Optional[float] = None
    lacl: Optional[float] = None
    if lsl is not None:
        apl_lower = lsl + z_delta * sigma
        lacl = lsl + band_offset

    # Capability Check when two-sided specs exist
    min_spec_spread: Optional[float] = None
    if lsl is not None and usl is not None:
        min_spec_spread = 2.0 * band_offset
        if (usl - lsl) < min_spec_spread:
            min_cp_req = (z_delta + z_alpha / math.sqrt(n_effective)) / 3.0
            raise ValueError(
                f"Specification spread (USL - LSL = {usl - lsl:g}) is too narrow for an Acceptance Control Chart "
                f"(requires at least {min_spec_spread:g}). Process capability ratio Cp must exceed {min_cp_req:.2f}."
            )

    # Center Line
    if target is not None:
        center_line = float(target)
    elif lsl is not None and usl is not None:
        center_line = (lsl + usl) / 2.0
    else:
        center_line = grand_mean

    # 5. Test 1 Signals: Points beyond acceptance control limits
    test1_signals: List[int] = []
    for idx, m in enumerate(subgroup_means, start=1):
        if uacl is not None and m > uacl:
            test1_signals.append(idx)
        elif lacl is not None and m < lacl:
            test1_signals.append(idx)

    # 6. Overall Process Capability Context
    stdev_overall = float(np.std(all_obs, ddof=1))
    cp_val = ((usl - lsl) / (6.0 * sigma)) if (lsl is not None and usl is not None) else None
    cpk_val: Optional[float] = None
    if cp_val is not None:
        cpu = (usl - grand_mean) / (3.0 * sigma) if usl is not None else None
        cpl = (grand_mean - lsl) / (3.0 * sigma) if lsl is not None else None
        if cpu is not None and cpl is not None:
            cpk_val = min(cpu, cpl)
        elif cpu is not None:
            cpk_val = cpu
        elif cpl is not None:
            cpk_val = cpl

    return {
        "analysis": "acceptance_control",
        "graph": "acceptance_control",
        "variable_name": variable_name,
        "title": title or f"Acceptance Control Chart of {variable_name}",
        "sample_n": total_n,
        "subgroup_count": k_subgroups,
        "avg_subgroup_size": avg_subgroup_size,
        "grand_mean": grand_mean,
        "stdev": sigma,
        "stdev_overall": stdev_overall,
        "sigma_source": sigma_source,
        "lsl": lsl,
        "usl": usl,
        "target": target,
        "delta": delta,
        "alpha": alpha,
        "z_delta": z_delta,
        "z_alpha": z_alpha,
        "apl_upper": apl_upper,
        "apl_lower": apl_lower,
        "uacl": uacl,
        "lacl": lacl,
        "center_line": center_line,
        "cp": cp_val,
        "cpk": cpk_val,
        "subgroup_means": subgroup_means,
        "subgroup_sizes": subgroup_sizes,
        "test1_signals": test1_signals,
    }
