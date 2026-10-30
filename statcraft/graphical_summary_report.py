"""Standard statistical session report for Graphical Summary of Descriptive Statistics."""
from __future__ import annotations


def _fmt(val, dec=4):
    if val is None:
        return "*"
    return f"{val:.{dec}f}" if isinstance(val, (int, float)) else str(val)


def generate_graphical_summary_report(var_name: str, result: dict) -> str:
    n = result.get('n', 0)
    mean_val = result.get('mean', 0.0)
    stdev_val = result.get('stdev', 0.0)
    var_val = result.get('variance', 0.0)
    skew_val = result.get('skewness', 0.0)
    kurt_val = result.get('kurtosis', 0.0)

    min_val = result.get('min', 0.0)
    q1_val = result.get('q1', 0.0)
    med_val = result.get('median', 0.0)
    q3_val = result.get('q3', 0.0)
    max_val = result.get('max', 0.0)

    ad_stat = result.get('ad_stat')
    ad_p = result.get('ad_p')

    ci_mean = result.get('ci_mean', (0.0, 0.0))
    ci_med = result.get('ci_median', (0.0, 0.0))
    ci_sd = result.get('ci_stdev', (0.0, 0.0))
    conf_pct = int(round(result.get('confidence', 0.95) * 100))

    lines = [
        f"Summary Report for {var_name}",
        "=" * 45,
        "",
        "Anderson-Darling Normality Test",
        f"  A-Squared:           {_fmt(ad_stat, 2)}",
        f"  P-Value:             {_fmt(ad_p, 3) if ad_p is not None else '< 0.005'}",
        "",
        "Descriptive Statistics",
        f"  Mean:                {_fmt(mean_val, 4)}",
        f"  StDev:               {_fmt(stdev_val, 4)}",
        f"  Variance:            {_fmt(var_val, 4)}",
        f"  Skewness:            {_fmt(skew_val, 4)}",
        f"  Kurtosis:            {_fmt(kurt_val, 4)}",
        f"  N:                   {n}",
        "",
        "Five-Number Summary",
        f"  Minimum:             {_fmt(min_val, 4)}",
        f"  1st Quartile:        {_fmt(q1_val, 4)}",
        f"  Median:              {_fmt(med_val, 4)}",
        f"  3rd Quartile:        {_fmt(q3_val, 4)}",
        f"  Maximum:             {_fmt(max_val, 4)}",
        "",
        f"{conf_pct}% Confidence Intervals",
        f"  Mean:                ({_fmt(ci_mean[0], 4)}, {_fmt(ci_mean[1], 4)})",
        f"  Median:              ({_fmt(ci_med[0], 4)}, {_fmt(ci_med[1], 4)})",
        f"  StDev:               ({_fmt(ci_sd[0], 4)}, {_fmt(ci_sd[1], 4)})",
    ]
    return "\n".join(lines)


def format_graphical_summary_report(result: dict) -> str:
    return generate_graphical_summary_report(result.get('variable_name', 'Variable'), result)

