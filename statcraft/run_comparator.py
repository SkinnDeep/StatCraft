"""Side-by-Side Statistical Model and Run Comparator for StatCraft.

Compares any two historical runs (e.g. Before vs After Kaizen, Stepwise vs Full Model)
with metric deltas (ΔR², ΔCpk, ΔPPM, ΔAIC) and automated statistical superiority verdict.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class MetricDelta:
    name: str
    run_a_value: Optional[float]
    run_b_value: Optional[float]
    delta: Optional[float]
    percent_change: Optional[float]
    better_direction: str  # "higher", "lower", "target"
    is_improved: Optional[bool]


def compare_runs(entry_a: Dict[str, Any], entry_b: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two analysis runs and return structured metrics diff with verdict."""
    title_a = entry_a.get("title", "Run 1")
    title_b = entry_b.get("title", "Run 2")
    res_a = entry_a.get("result", {})
    res_b = entry_b.get("result", {})

    # Key metrics catalog with optimization direction
    METRIC_DIRECTIONS = {
        "r_squared": "higher",
        "r2": "higher",
        "adj_r_squared": "higher",
        "predicted_r_squared": "higher",
        "cp": "higher",
        "cpk": "higher",
        "pp": "higher",
        "ppk": "higher",
        "aic": "lower",
        "bic": "lower",
        "s": "lower",
        "stdev": "lower",
        "ppm_total": "lower",
        "expected_ppm": "lower",
        "p_value": "lower",
        "press": "lower"
    }

    all_keys = sorted(list(set(res_a.keys()).union(set(res_b.keys()))))
    deltas: List[MetricDelta] = []

    improvements = 0
    degradations = 0

    for k in all_keys:
        va = res_a.get(k)
        vb = res_b.get(k)

        # Only evaluate numeric scalars
        if (isinstance(va, (int, float)) and not isinstance(va, bool)) or (isinstance(vb, (int, float)) and not isinstance(vb, bool)):
            fa = float(va) if va is not None and math.isfinite(va) else None
            fb = float(vb) if vb is not None and math.isfinite(vb) else None

            d_val = (fb - fa) if (fa is not None and fb is not None) else None
            pct_val = ((fb - fa) / abs(fa) * 100.0) if (fa is not None and fb is not None and abs(fa) > 1e-12) else None

            direction = METRIC_DIRECTIONS.get(k.lower(), "higher")
            is_imp: Optional[bool] = None

            if d_val is not None and abs(d_val) > 1e-9:
                if direction == "higher":
                    is_imp = d_val > 0
                elif direction == "lower":
                    is_imp = d_val < 0
                if is_imp is True:
                    improvements += 1
                elif is_imp is False:
                    degradations += 1

            clean_name = k.replace("_", " ").title()
            deltas.append(MetricDelta(
                name=clean_name,
                run_a_value=fa,
                run_b_value=fb,
                delta=d_val,
                percent_change=pct_val,
                better_direction=direction,
                is_improved=is_imp
            ))

    if improvements > degradations:
        verdict = f"'{title_b}' shows net statistical improvement over '{title_a}' ({improvements} metric(s) improved vs {degradations} degraded)."
    elif degradations > improvements:
        verdict = f"'{title_a}' remains superior or more conservative than '{title_b}' ({degradations} metric(s) degraded in Run 2)."
    else:
        verdict = f"Both runs demonstrate equivalent statistical performance across evaluated metrics."

    return {
        "title_a": title_a,
        "title_b": title_b,
        "deltas": deltas,
        "improvements": improvements,
        "degradations": degradations,
        "verdict": verdict
    }
