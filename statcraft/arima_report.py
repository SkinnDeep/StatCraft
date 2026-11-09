"""Session report formatter for ARIMA analysis.

Matches Minitab standard layout:
- Model specification: ARIMA(p,d,q) x (P,D,Q)_s
- Final Estimates of Parameters: Type, Coef, SE Coef, T, P
- Number of observations, Residuals SS, MS, DF
- Forecasts table with confidence limits
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def _fmt(val: Optional[float], dec: int = 4) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "*"
    return f"{val:.{dec}f}"


def generate_arima_report(result: Dict[str, Any]) -> str:
    """Format ARIMA results into Minitab session window report."""
    lines: List[str] = []
    var_name = result.get("variable_name", "Series")
    p = result.get("p", 1)
    d = result.get("d", 0)
    q = result.get("q", 0)
    P = result.get("P", 0)
    D = result.get("D", 0)
    Q = result.get("Q", 0)
    S = result.get("S", 1)

    if P > 0 or D > 0 or Q > 0:
        spec_str = f"ARIMA({p},{d},{q})x({P},{D},{Q})_{S}: {var_name}"
    else:
        spec_str = f"ARIMA({p},{d},{q}): {var_name}"

    lines.append(spec_str)
    lines.append("=" * len(spec_str))
    lines.append("")

    estimates = result.get("estimates", [])
    if estimates:
        lines.append("Final Estimates of Parameters")
        lines.append(f"  {'Type':<12} {'Coef':>10} {'SE Coef':>10} {'T':>8} {'P':>8}")
        lines.append("  " + "-" * 50)
        for est in estimates:
            t_type = est.get("type", "")
            coef = _fmt(est.get("coef"), 4)
            se = _fmt(est.get("se"), 4)
            t_stat = _fmt(est.get("t"), 2)
            p_val = _fmt(est.get("p"), 4)
            lines.append(f"  {t_type:<12} {coef:>10} {se:>10} {t_stat:>8} {p_val:>8}")
        lines.append("")

    n = result.get("n_orig", 0)
    ss = result.get("ss", 0.0)
    ms = result.get("ms", 0.0)
    df = result.get("df", 1)

    lines.append(f"Number of observations: {n}")
    lines.append(f"Residuals:  SS = {_fmt(ss, 3)} (backforecasts excluded)")
    lines.append(f"            MS = {_fmt(ms, 4)}   DF = {df}")
    lines.append("")

    forecasts = result.get("forecasts", [])
    if forecasts:
        conf = result.get("conf_level", 95.0)
        lines.append(f"Forecasts ({conf:g}% Confidence Level)")
        lines.append(f"  {'Period':<8} {'Forecast':>12} {'Lower':>12} {'Upper':>12}")
        lines.append("  " + "-" * 48)
        for fc in forecasts:
            per = fc.get("period", 0)
            f_val = fc.get("forecast")
            low = fc.get("lower")
            upp = fc.get("upper")
            lines.append(f"  {per:<8} {_fmt(f_val, 4):>12} {_fmt(low, 4):>12} {_fmt(upp, 4):>12}")
        lines.append("")

    return "\n" + "\n".join(lines)
