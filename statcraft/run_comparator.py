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
        "gcv_r2": "higher",
        "r_sq": "higher",
        "r_sq_adj": "higher",
        "adj_r_squared": "higher",
        "predicted_r_squared": "higher",
        "accuracy": "higher",
        "roc_auc": "higher",
        "canonical_r2": "higher",
        "canonical_rmse": "lower",
        "canonical_mae": "lower",
        "canonical_accuracy": "higher",
        "canonical_roc_auc": "higher",
        "canonical_log_loss": "lower",
        "concordance": "higher",
        "rty_pct": "higher",
        "sigma_level_est": "higher",
        "cp": "higher",
        "cpk": "higher",
        "pp": "higher",
        "ppk": "higher",
        "aic": "lower",
        "bic": "lower",
        "s": "lower",
        "stdev": "lower",
        "rmse": "lower",
        "mse": "lower",
        "mae": "lower",
        "error_rate": "lower",
        "log_loss": "lower",
        "gcv": "lower",
        "neg2_rell": "lower",
        "ppm_total": "lower",
        "expected_ppm": "lower",
        "dpmo": "lower",
        "dpmo_expected_lt": "lower",
        "dpmo_total": "lower",
        "pct_out_of_spec": "lower",
        "pct_below_lsl": "lower",
        "pct_above_usl": "lower",
        "p_value": "lower",
        "p_val": "lower",
        "lr_p_value": "lower",
        "lr_dispersion_p": "lower",
        "press": "lower",
    }

    def _flatten_scalars(d: Dict[str, Any]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for k, v in d.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)):
                out[k] = float(v)
            elif k in ("oob_metrics", "val_metrics", "metrics", "summary", "capability") and isinstance(v, dict):
                for nk, nv in v.items():
                    if isinstance(nv, (int, float)) and not isinstance(nv, bool) and math.isfinite(float(nv)):
                        out[f"{k}.{nk}"] = float(nv)
        return out

    _CANONICAL_SPECS = {
        "canonical_r2": ("val_metrics.r2", "oob_metrics.r2", "metrics.r2", "r_squared", "r_sq", "r2"),
        "canonical_rmse": ("val_metrics.rmse", "oob_metrics.rmse", "metrics.rmse", "rmse", "residual_stdev", "s"),
        "canonical_mae": ("val_metrics.mae", "oob_metrics.mae", "metrics.mae", "mae"),
        "canonical_accuracy": ("val_metrics.accuracy", "oob_metrics.accuracy", "metrics.accuracy", "accuracy"),
        "canonical_roc_auc": ("val_metrics.roc_auc", "oob_metrics.roc_auc", "metrics.roc_auc", "roc_auc", "auc"),
        "canonical_log_loss": ("val_metrics.log_loss", "oob_metrics.log_loss", "metrics.log_loss", "log_loss"),
    }

    flat_a = _flatten_scalars(res_a)
    flat_b = _flatten_scalars(res_b)
    for cname, candidates in _CANONICAL_SPECS.items():
        match_a = next(((k, flat_a[k]) for k in candidates if k in flat_a), None)
        match_b = next(((k, flat_b[k]) for k in candidates if k in flat_b), None)
        if match_a is not None and match_b is not None and match_a[0] != match_b[0]:
            flat_a[cname] = match_a[1]
            flat_b[cname] = match_b[1]
    all_keys = sorted(set(flat_a).union(flat_b))
    deltas: List[MetricDelta] = []

    improvements = 0
    degradations = 0

    for k in all_keys:
        va = flat_a.get(k)
        vb = flat_b.get(k)
        leaf_key = k.split(".")[-1].lower()
        clean_key = k.replace(".", "_")

        if va is not None or vb is not None:
            fa = float(va) if va is not None else None
            fb = float(vb) if vb is not None else None

            d_val = (fb - fa) if (fa is not None and fb is not None) else None
            pct_val = ((fb - fa) / abs(fa) * 100.0) if (fa is not None and fb is not None and abs(fa) > 1e-12) else None

            direction = METRIC_DIRECTIONS.get(leaf_key, METRIC_DIRECTIONS.get(k.lower(), "higher"))
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

            clean_name = clean_key.replace("_", " ").title()
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
