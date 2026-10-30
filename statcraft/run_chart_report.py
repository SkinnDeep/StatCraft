"""Standard statistical session report for Quality Run Chart."""
from __future__ import annotations


def _fmt(val, dec=4):
    if val is None:
        return "*"
    return f"{val:.{dec}f}" if isinstance(val, (int, float)) else str(val)


def generate_run_chart_report(var_name: str, result: dict) -> str:
    n = result.get('n', 0)
    sub_size = result.get('subgroup_size', 1)
    med_val = result.get('median', 0.0)

    rbm = result.get('runs_about_median', {})
    rud = result.get('runs_up_or_down', {})

    lines = [
        f"Run Chart of {var_name}",
        "=" * 45,
        f"Subgroup size: {sub_size}    Number of subgroups: {n}",
        f"Center line (Median): {_fmt(med_val, 4)}",
        "",
        "Runs About Median",
        f"  Number of runs about median:     {rbm.get('number_of_runs', 0)}",
        f"  Expected number of runs:         {_fmt(rbm.get('expected_runs', 0.0), 1)}",
        f"  Longest run about median:        {rbm.get('longest_run', 0)}",
        f"  Approx P-Value for Clustering:   {_fmt(rbm.get('p_cluster', 0.0), 3)}",
        f"  Approx P-Value for Mixtures:     {_fmt(rbm.get('p_mixture', 0.0), 3)}",
        "",
        "Runs Up or Down",
        f"  Number of runs up or down:       {rud.get('number_of_runs', 0)}",
        f"  Expected number of runs:         {_fmt(rud.get('expected_runs', 0.0), 1)}",
        f"  Longest run up or down:          {rud.get('longest_run', 0)}",
        f"  Approx P-Value for Trends:       {_fmt(rud.get('p_trend', 0.0), 3)}",
        f"  Approx P-Value for Oscillation:  {_fmt(rud.get('p_oscillation', 0.0), 3)}",
    ]
    return "\n".join(lines)


def format_run_chart_report(result: dict) -> str:
    return generate_run_chart_report(result.get('variable_name', 'Variable'), result)

