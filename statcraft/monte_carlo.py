"""Monte Carlo Process & Tolerance Simulation Engine (Offline NumPy / SciPy).

Evaluates transfer functions Y = f(X1, ..., Xk) across probabilistic input
distributions to quantify:
- Output capability (Simulated Pp, Ppk, DPMO, % Out of Spec)
- Distributional moments & empirical percentiles
- Variance contribution / Sensitivity Tornado rankings (Spearman rho^2 %)
"""
from __future__ import annotations

import ast
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats


_SAFE_FUNCS = {
    "sqrt": np.sqrt,
    "exp": np.exp,
    "log": np.log,
    "ln": np.log,
    "log10": np.log10,
    "abs": np.abs,
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "min": np.minimum,
    "max": np.maximum,
    "minimum": np.minimum,
    "maximum": np.maximum,
    "pow": np.power,
}

_SAFE_CONSTS = {
    "pi": math.pi,
    "e": math.e,
}


def _eval_safe_formula(expr: str, env: Dict[str, np.ndarray]) -> np.ndarray:
    """Safely evaluate vectorized NumPy math AST without arbitrary code execution."""
    text = (expr or "").strip()
    if not text:
        raise ValueError("Enter a transfer equation Y = f(inputs).")
    if "=" in text and not text.startswith("="):
        _, text = text.split("=", 1)
    text = text.lstrip("=").strip()
    tree = ast.parse(text, mode="eval")

    def _visit(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return _visit(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError(f"Unsupported constant: {node.value!r}")
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            if node.id in _SAFE_CONSTS:
                return _SAFE_CONSTS[node.id]
            raise ValueError(f"Unknown variable or symbol '{node.id}' in formula.")
        if isinstance(node, ast.UnaryOp):
            val = _visit(node.operand)
            if isinstance(node.op, ast.UAdd):
                return val
            if isinstance(node.op, ast.USub):
                return -val
            raise ValueError("Unsupported unary operator.")
        if isinstance(node, ast.BinOp):
            left, right = _visit(node.left), _visit(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return np.power(left, right)
            raise ValueError("Unsupported binary operator in transfer formula.")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_FUNCS:
                raise ValueError("Unsupported function call in transfer formula.")
            if node.keywords:
                raise ValueError("Keyword arguments are not supported in formula calls.")
            args = [_visit(a) for a in node.args]
            return _SAFE_FUNCS[node.func.id](*args)
        raise ValueError(f"Disallowed formula construct: {type(node).__name__}")

    out = np.asarray(_visit(tree), dtype=float)
    if out.ndim == 0:
        n_ref = next(iter(env.values())).shape[0]
        out = np.full(n_ref, float(out), dtype=float)
    if not np.all(np.isfinite(out)):
        raise ValueError("Formula evaluation produced non-finite values (e.g., divide by zero or log <= 0).")
    return out


def parse_input_specs(spec_text: str) -> List[Dict[str, Any]]:
    """Parse concise Monte Carlo input strings, e.g. 'X1: Normal(10, 0.5); X2: Uniform(4, 6)'."""
    entries: List[Dict[str, Any]] = []
    chunks = [c.strip() for c in re.split(r"[;\n]+", spec_text or "") if c.strip()]
    pattern = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z]+)\s*\(([^)]+)\)$")
    for chunk in chunks:
        m = pattern.match(chunk)
        if not m:
            raise ValueError(
                f"Invalid input specification '{chunk}'. Expected format e.g. 'X1: Normal(10, 0.5)'."
            )
        name, dist, raw_params = m.group(1), m.group(2).strip(), m.group(3)
        params = [float(x.strip()) for x in raw_params.split(",") if x.strip()]
        entries.append({"name": name, "distribution": dist, "params": params})
    if not entries:
        raise ValueError("Specify at least one probabilistic input variable.")
    return entries


def _sample_distribution(dist: str, params: Sequence[float], n: int, rng: np.random.Generator) -> np.ndarray:
    d = dist.strip().lower()
    if d == "normal":
        if len(params) != 2 or params[1] <= 0:
            raise ValueError("Normal(mean, stdev) requires 2 parameters with stdev > 0.")
        return rng.normal(params[0], params[1], n)
    if d == "uniform":
        if len(params) != 2 or params[0] >= params[1]:
            raise ValueError("Uniform(low, high) requires low < high.")
        return rng.uniform(params[0], params[1], n)
    if d == "triangular":
        if len(params) != 3 or not (params[0] <= params[1] <= params[2]) or params[0] >= params[2]:
            raise ValueError("Triangular(low, mode, high) requires low <= mode <= high and low < high.")
        return rng.triangular(params[0], params[1], params[2], n)
    if d == "lognormal":
        if len(params) != 2 or params[1] <= 0:
            raise ValueError("Lognormal(mu_log, sigma_log) requires sigma_log > 0.")
        return rng.lognormal(params[0], params[1], n)
    if d == "exponential":
        if len(params) != 1 or params[0] <= 0:
            raise ValueError("Exponential(mean) requires mean > 0.")
        return rng.exponential(params[0], n)
    if d == "weibull":
        if len(params) != 2 or params[0] <= 0 or params[1] <= 0:
            raise ValueError("Weibull(shape, scale) requires positive shape and scale.")
        return params[1] * rng.weibull(params[0], n)
    raise ValueError(f"Unsupported distribution '{dist}'. Supported: Normal, Uniform, Triangular, Lognormal, Exponential, Weibull.")


def monte_carlo_simulation(
    inputs: Sequence[Dict[str, Any]],
    formula: str,
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    n_sims: int = 10000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Run Monte Carlo simulation over probabilistic inputs and compute capability & sensitivity."""
    if not inputs:
        raise ValueError("At least one probabilistic input variable is required.")
    if lsl is not None and usl is not None and float(lsl) >= float(usl):
        raise ValueError("LSL must be strictly less than USL.")

    n = max(100, min(100000, int(n_sims)))
    rng = np.random.default_rng(int(seed))

    env: Dict[str, np.ndarray] = {}
    input_summaries: List[Dict[str, Any]] = []
    for item in inputs:
        name = str(item["name"]).strip()
        dist = str(item["distribution"]).strip()
        params = [float(p) for p in item["params"]]
        draws = _sample_distribution(dist, params, n, rng)
        env[name] = draws
        input_summaries.append({
            "name": name,
            "distribution": dist,
            "params": params,
            "sample_mean": float(np.mean(draws)),
            "sample_stdev": float(np.std(draws, ddof=1)),
        })

    y = _eval_safe_formula(formula, env)
    mean_y = float(np.mean(y))
    sd_y = float(np.std(y, ddof=1))
    med_y = float(np.median(y))
    q1_y, q3_y = float(np.percentile(y, 25)), float(np.percentile(y, 75))
    p05_y, p95_y = float(np.percentile(y, 5)), float(np.percentile(y, 95))

    pct_below_lsl = float(np.mean(y < float(lsl)) * 100.0) if lsl is not None else 0.0
    pct_above_usl = float(np.mean(y > float(usl)) * 100.0) if usl is not None else 0.0
    pct_oos = pct_below_lsl + pct_above_usl
    dpmo = pct_oos * 10000.0

    pp = (float(usl) - float(lsl)) / (6.0 * sd_y) if (lsl is not None and usl is not None and sd_y > 1e-12) else None
    ppu = (float(usl) - mean_y) / (3.0 * sd_y) if (usl is not None and sd_y > 1e-12) else None
    ppl = (mean_y - float(lsl)) / (3.0 * sd_y) if (lsl is not None and sd_y > 1e-12) else None
    ppk_candidates = [v for v in (ppl, ppu) if v is not None]
    ppk = min(ppk_candidates) if ppk_candidates else None

    # Tornado variance contribution using Spearman rank correlation squared
    raw_sq = []
    for item in input_summaries:
        rho, _ = stats.spearmanr(env[item["name"]], y)
        r_val = 0.0 if (rho is None or not math.isfinite(float(rho))) else float(rho)
        raw_sq.append((item["name"], r_val, r_val * r_val))
    total_r2 = sum(r2 for _, _, r2 in raw_sq)
    sensitivity = []
    for name, rho, r2 in sorted(raw_sq, key=lambda x: x[2], reverse=True):
        pct_var = (r2 / total_r2 * 100.0) if total_r2 > 1e-15 else 0.0
        sensitivity.append({
            "input": name,
            "spearman_rho": rho,
            "variance_contribution_pct": pct_var,
        })

    # What-If Tolerance-Tightening Sweep on Top Sensitivity Driver
    tolerance_sweep: List[Dict[str, Any]] = []
    if sensitivity:
        top_var = sensitivity[0]["input"]
        base_draws = env[top_var]
        mu_top = float(np.mean(base_draws))
        for cut_pct in (0, 25, 50):
            factor = 1.0 - cut_pct / 100.0
            env_sw = dict(env)
            env_sw[top_var] = mu_top + (base_draws - mu_top) * factor
            y_sw = _eval_safe_formula(formula, env_sw)
            sd_sw = float(np.std(y_sw, ddof=1))
            m_sw = float(np.mean(y_sw))
            oos_sw = (float(np.mean(y_sw < float(lsl)) * 100.0) if lsl is not None else 0.0) + (
                float(np.mean(y_sw > float(usl)) * 100.0) if usl is not None else 0.0
            )
            sw_ppu = (float(usl) - m_sw) / (3.0 * sd_sw) if (usl is not None and sd_sw > 1e-12) else None
            sw_ppl = (m_sw - float(lsl)) / (3.0 * sd_sw) if (lsl is not None and sd_sw > 1e-12) else None
            sw_cands = [v for v in (sw_ppl, sw_ppu) if v is not None]
            tolerance_sweep.append({
                "scenario": "Baseline (0% SD cut)" if cut_pct == 0 else f"Tighten {top_var} SD by -{cut_pct}%",
                "output_stdev": sd_sw,
                "pct_out_of_spec": oos_sw,
                "dpmo": oos_sw * 10000.0,
                "ppk": min(sw_cands) if sw_cands else None,
            })

    h_counts, h_edges = np.histogram(y, bins=24)

    return {
        "analysis": "monte_carlo_simulation",
        "formula": formula,
        "n_sims": n,
        "lsl": float(lsl) if lsl is not None else None,
        "usl": float(usl) if usl is not None else None,
        "inputs": input_summaries,
        "histogram": {"edges": [float(e) for e in h_edges], "counts": [int(c) for c in h_counts]},
        "summary": {
            "mean": mean_y,
            "stdev": sd_y,
            "median": med_y,
            "q1": q1_y,
            "q3": q3_y,
            "p05": p05_y,
            "p95": p95_y,
            "min": float(np.min(y)),
            "max": float(np.max(y)),
        },
        "capability": {
            "pp": pp,
            "ppk": ppk,
            "pct_below_lsl": pct_below_lsl,
            "pct_above_usl": pct_above_usl,
            "pct_out_of_spec": pct_oos,
            "dpmo": dpmo,
        },
        "sensitivity": sensitivity,
        "tolerance_sweep": tolerance_sweep,
        "_draws": [float(v) for v in y],
    }


def format_monte_carlo_report(result: Dict[str, Any]) -> str:
    s = result["summary"]
    cap = result["capability"]
    lines = [
        f"Monte Carlo Process Simulation ({result['n_sims']:,} iterations)",
        "─" * 74,
        f"Transfer Equation : {result['formula']}",
        f"Output Mean / SD  : {s['mean']:.5g}  /  {s['stdev']:.5g}",
        f"Median (Q1 – Q3)  : {s['median']:.5g}  ({s['q1']:.5g} – {s['q3']:.5g})",
        f"Empirical 5%–95%  : [{s['p05']:.5g}, {s['p95']:.5g}]",
    ]
    if result["lsl"] is not None or result["usl"] is not None:
        lines.append("")
        lines.append("Specification Compliance & Simulated Capability:")
        lines.append(
            f"  LSL: {result['lsl'] if result['lsl'] is not None else 'None'}   |   "
            f"USL: {result['usl'] if result['usl'] is not None else 'None'}"
        )
        lines.append(
            f"  Out of Spec       : {cap['pct_out_of_spec']:.3f}%  "
            f"(DPMO = {cap['dpmo']:,.1f}; Below LSL = {cap['pct_below_lsl']:.3f}%, Above USL = {cap['pct_above_usl']:.3f}%)"
        )
        pp_s = f"{cap['pp']:.3f}" if cap["pp"] is not None else "N/A"
        ppk_s = f"{cap['ppk']:.3f}" if cap["ppk"] is not None else "N/A"
        lines.append(f"  Simulated Pp/Ppk  : Pp = {pp_s}  |  Ppk = {ppk_s}")

    lines.append("")
    lines.append("Sensitivity Tornado (Variance Contribution %):")
    lines.append(f"  {'Input Variable':<20} {'Rank Corr':>10} {'Contrib %':>10}  Impact")
    for row in result["sensitivity"]:
        bars = "█" * int(round(row["variance_contribution_pct"] / 5.0))
        lines.append(
            f"  {row['input']:<20} {row['spearman_rho']:>+10.3f} {row['variance_contribution_pct']:>9.1f}%  {bars}"
        )
    if result.get("tolerance_sweep"):
        lines.append("")
        lines.append("Tolerance-Tightening What-If Sweep:")
        lines.append(f"  {'Scenario':<30} {'Out SD':>10} {'OOS %':>9} {'DPMO':>10} {'Ppk':>8}")
        for sw in result["tolerance_sweep"]:
            ppk_txt = f"{sw['ppk']:.3f}" if sw.get("ppk") is not None else "N/A"
            lines.append(f"  {sw['scenario']:<30} {sw['output_stdev']:>10.4g} {sw['pct_out_of_spec']:>8.3f}% {sw['dpmo']:>10,.0f} {ppk_txt:>8}")
    return "\n".join(lines)
