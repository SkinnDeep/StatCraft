"""Session window report formatter for Winters' Method Exponential Smoothing.

Matches Minitab standard text output structure:
- Title banner and data description (Variable, Length, Model, Seasonal length)
- Smoothing Constants (alpha, gamma, delta, indicator if optimal)
- Accuracy Measures (MAPE, MAD, MSD)
- Forecasts table with confidence limits
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def _fmt(val: Optional[float], dec: int = 4) -> str:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "*"
    if val == float("inf"):
        return "Inf"
    if val == float("-inf"):
        return "-Inf"
    return f"{val:.{dec}f}"


def generate_winters_method_report(result: Dict[str, Any]) -> str:
    """Format Winters' Method Exponential Smoothing output into standard session report."""
    lines: List[str] = []
    title = result.get("title") or f"Winters' Method for {result.get('variable_name', 'Series')}"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")
    lines.append(f"Data: {result.get('variable_name', 'Series')}")
    lines.append(f"Length: {result.get('n', 0)}")
    lines.append(f"Model: {result.get('model', 'multiplicative').capitalize()}")
    lines.append(f"Seasonal Length: {result.get('season_length', 4)}")
    opt_str = " (optimal/min MSD)" if result.get("is_optimal") else ""
    lines.append(f"Smoothing constant alpha (level):    {_fmt(result.get('alpha'), 4)}{opt_str}")
    lines.append(f"Smoothing constant gamma (trend):    {_fmt(result.get('gamma'), 4)}{opt_str}")
    lines.append(f"Smoothing constant delta (seasonal): {_fmt(result.get('delta'), 4)}{opt_str}")
    lines.append("")

    # Accuracy measures
    acc = result.get("accuracy", {})
    lines.extend([
        "Accuracy Measures",
        f"  {'MAPE':<10} {_fmt(acc.get('mape'), 4)}",
        f"  {'MAD':<10} {_fmt(acc.get('mad'), 4)}",
        f"  {'MSD':<10} {_fmt(acc.get('msd'), 4)}",
        "",
    ])

    # Forecasts
    forecasts = result.get("forecasts", [])
    if forecasts:
        conf = result.get("conf_level", 95.0)
        lines.extend([
            f"Forecasts ({conf:g}% Confidence Level)",
            f"  {'Period':<8} {'Forecast':>12} {'Lower':>12} {'Upper':>12}",
            "  " + "-" * 48,
        ])
        for fc in forecasts:
            p = fc.get("period", 0)
            f_val = fc.get("forecast")
            low = fc.get("lower")
            upp = fc.get("upper")
            lines.append(f"  {p:<8} {_fmt(f_val, 4):>12} {_fmt(low, 4):>12} {_fmt(upp, 4):>12}")
        lines.append("")

    return "\n" + "\n".join(lines)
