"""Text session report formatter for Time Series Analysis and Forecasting.

Produces authentic StatCraft session window outputs for:
- Trend Analysis
- Decomposition
- Moving Average
- Single Exponential Smoothing
- Double Exponential Smoothing
- Autocorrelation (ACF)
- Partial Autocorrelation (PACF)
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


def _format_accuracy_table(accuracy: Dict[str, Any]) -> List[str]:
    lines = [
        "Accuracy Measures",
        f"  {'MAPE':<10} {_fmt(accuracy.get('mape'), 4)}",
        f"  {'MAD':<10} {_fmt(accuracy.get('mad'), 4)}",
        f"  {'MSD':<10} {_fmt(accuracy.get('msd'), 4)}",
        "",
    ]
    return lines


def _format_forecasts_table(forecasts: List[Dict[str, Any]], conf_level: float = 95.0) -> List[str]:
    if not forecasts:
        return []
    lines = [
        f"Forecasts ({conf_level:g}% Confidence Level)",
        f"  {'Period':<8} {'Forecast':>12} {'Lower':>12} {'Upper':>12}",
        "  " + "-" * 48,
    ]
    for fc in forecasts:
        p = fc.get("period", 0)
        f_val = fc.get("forecast")
        low = fc.get("lower")
        upp = fc.get("upper")
        lines.append(f"  {p:<8} {_fmt(f_val, 4):>12} {_fmt(low, 4):>12} {_fmt(upp, 4):>12}")
    lines.append("")
    return lines


def generate_trend_analysis_report(result: Dict[str, Any]) -> str:
    """Format Trend Analysis results into Standard statistical session report."""
    lines: List[str] = []
    title = result.get("title") or f"Trend Analysis Plot for {result.get('variable_name', 'Series')}"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")
    lines.append(f"Data: {result.get('variable_name', 'Series')}")
    lines.append(f"Length: {result.get('n', 0)}")
    lines.append("")

    model_names = {
        "linear": "Linear Trend Model",
        "quadratic": "Quadratic Trend Model",
        "exponential": "Exponential Growth Trend Model",
        "scurve": "S-Curve (Pearl-Reed Logistic) Trend Model",
    }
    model_name = model_names.get(result.get("model", "linear"), "Trend Model")
    lines.append(model_name)
    lines.append(f"  Fitted Equation: {result.get('equation', '')}")
    lines.append("")

    # Accuracy measures
    lines.extend(_format_accuracy_table(result.get("accuracy", {})))

    # Forecasts table
    lines.extend(_format_forecasts_table(result.get("forecasts", []), result.get("conf_level", 95.0)))

    return "\n" + "\n".join(lines)


def generate_decomposition_report(result: Dict[str, Any]) -> str:
    """Format Decomposition results into Standard statistical session report."""
    lines: List[str] = []
    title = result.get("title") or f"Decomposition for {result.get('variable_name', 'Series')}"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")
    lines.append(f"Data: {result.get('variable_name', 'Series')}")
    lines.append(f"Length: {result.get('n', 0)}")
    lines.append(f"Seasonal Length: {result.get('season_length', 0)}")
    lines.append(f"Model Type: {result.get('model', 'multiplicative').capitalize()}")
    lines.append("")

    # Fitted Trend Equation
    lines.append("Trend Line Equation")
    lines.append(f"  {result.get('trend_equation', '')}")
    lines.append("")

    # Seasonal Indices Table
    indices = result.get("seasonal_indices", [])
    if indices:
        lines.append("Seasonal Indices")
        lines.append(f"  {'Period':<8} {'Index':>12}")
        lines.append("  " + "-" * 22)
        for idx, val in enumerate(indices, 1):
            lines.append(f"  {idx:<8} {_fmt(val, 4):>12}")
        lines.append("")

    # Accuracy measures
    lines.extend(_format_accuracy_table(result.get("accuracy", {})))

    # Forecasts
    lines.extend(_format_forecasts_table(result.get("forecasts", []), result.get("conf_level", 95.0)))

    return "\n" + "\n".join(lines)


def generate_moving_average_report(result: Dict[str, Any]) -> str:
    """Format Moving Average results into Standard statistical session report."""
    lines: List[str] = []
    title = result.get("title") or f"Moving Average for {result.get('variable_name', 'Series')}"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")
    lines.append(f"Data: {result.get('variable_name', 'Series')}")
    lines.append(f"Length: {result.get('n', 0)}")
    lines.append(f"MA Length: {result.get('ma_length', 3)}")
    lines.append(f"Centered: {'Yes' if result.get('center') else 'No'}")
    lines.append("")

    # Accuracy measures
    lines.extend(_format_accuracy_table(result.get("accuracy", {})))

    # Forecasts
    lines.extend(_format_forecasts_table(result.get("forecasts", []), result.get("conf_level", 95.0)))

    return "\n" + "\n".join(lines)


def generate_single_exp_smoothing_report(result: Dict[str, Any]) -> str:
    """Format Single Exponential Smoothing report."""
    lines: List[str] = []
    title = result.get("title") or f"Single Exponential Smoothing for {result.get('variable_name', 'Series')}"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")
    lines.append(f"Data: {result.get('variable_name', 'Series')}")
    lines.append(f"Length: {result.get('n', 0)}")
    opt_str = " (optimal/min MSD)" if result.get("is_optimal") else ""
    lines.append(f"Smoothing constant alpha: {_fmt(result.get('alpha'), 4)}{opt_str}")
    lines.append("")

    # Accuracy measures
    lines.extend(_format_accuracy_table(result.get("accuracy", {})))

    # Forecasts
    lines.extend(_format_forecasts_table(result.get("forecasts", []), result.get("conf_level", 95.0)))

    return "\n" + "\n".join(lines)


def generate_double_exp_smoothing_report(result: Dict[str, Any]) -> str:
    """Format Double Exponential Smoothing report."""
    lines: List[str] = []
    title = result.get("title") or f"Double Exponential Smoothing for {result.get('variable_name', 'Series')}"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")
    lines.append(f"Data: {result.get('variable_name', 'Series')}")
    lines.append(f"Length: {result.get('n', 0)}")
    opt_str = " (optimal/min MSD)" if result.get("is_optimal") else ""
    lines.append(f"Smoothing constant alpha (level): {_fmt(result.get('alpha'), 4)}{opt_str}")
    lines.append(f"Smoothing constant gamma (trend): {_fmt(result.get('gamma'), 4)}{opt_str}")
    lines.append("")

    # Accuracy measures
    lines.extend(_format_accuracy_table(result.get("accuracy", {})))

    # Forecasts
    lines.extend(_format_forecasts_table(result.get("forecasts", []), result.get("conf_level", 95.0)))

    return "\n" + "\n".join(lines)


def generate_autocorrelation_report(result: Dict[str, Any]) -> str:
    """Format Autocorrelation report with Box-Pierce / Ljung-Box Q statistics."""
    lines: List[str] = []
    title = result.get("title") or f"Autocorrelation Function: {result.get('variable_name', 'Series')}"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")
    lines.append(f"Data: {result.get('variable_name', 'Series')}")
    lines.append(f"Length: {result.get('n', 0)}")
    lines.append("")

    lines.append("Autocorrelation Function for Series")
    lines.append(f"  {'Lag':<6} {'Correlation':>12} {'T':>10} {'LBQ':>12} {'P-Value':>10}")
    lines.append("  " + "-" * 54)
    for row in result.get("lags", []):
        lag = row.get("lag", 0)
        corr = row.get("correlation")
        t = row.get("t")
        lbq = row.get("lbq")
        p = row.get("p_value")
        lines.append(f"  {lag:<6} {_fmt(corr, 4):>12} {_fmt(t, 2):>10} {_fmt(lbq, 2):>12} {_fmt(p, 3):>10}")
    lines.append("")
    return "\n" + "\n".join(lines)


def generate_partial_autocorrelation_report(result: Dict[str, Any]) -> str:
    """Format Partial Autocorrelation report."""
    lines: List[str] = []
    title = result.get("title") or f"Partial Autocorrelation Function: {result.get('variable_name', 'Series')}"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")
    lines.append(f"Data: {result.get('variable_name', 'Series')}")
    lines.append(f"Length: {result.get('n', 0)}")
    lines.append("")

    lines.append("Partial Autocorrelation Function for Series")
    lines.append(f"  {'Lag':<6} {'PACF':>12} {'T':>10}")
    lines.append("  " + "-" * 32)
    for row in result.get("lags", []):
        lag = row.get("lag", 0)
        pacf = row.get("pacf")
        t = row.get("t")
        lines.append(f"  {lag:<6} {_fmt(pacf, 4):>12} {_fmt(t, 2):>10}")
    lines.append("")
    return "\n" + "\n".join(lines)


from .winters_method_report import generate_winters_method_report
