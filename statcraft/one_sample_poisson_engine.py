"""Engine for StatCraft One-Sample Poisson Rate (OneRate)."""
from __future__ import annotations
import math
from typing import Dict, Any, List, Optional, Tuple, Sequence, Union
from scipy import stats


def one_sample_poisson_settings(
    data_format: int = 0,  # 0: Columns, 1: Summarized
    sample_cols: Optional[List[Union[int, str]]] = None,
    freq_cols: Optional[List[Union[int, str]]] = None,
    summarized: Optional[Dict[str, int]] = None,
    perform_test: bool = True,
    hypothesized_rate: Optional[float] = 1.0,
    confidence_level: float = 95.0,
    alternative: str = "not_equal",  # "not_equal", "less", "greater"
    method: str = "exact",  # "exact", "normal_approx"
    length_of_observation: float = 1.0,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Validate and return normalized settings for One-Sample Poisson Rate."""
    if "mode" in kwargs:
        data_format = 1 if kwargs["mode"] == "summarized" else 0
    if "sample_columns" in kwargs and not sample_cols:
        sample_cols = kwargs["sample_columns"]
    if "freq_columns" in kwargs and not freq_cols:
        freq_cols = kwargs["freq_columns"]
    if data_format == 1 and summarized is None:
        summarized = {
            "n": int(kwargs.get("n", 10)),
            "total_occurrences": int(kwargs.get("total_occurrences", 20)),
        }

    return {
        "data_format": int(data_format),
        "sample_cols": list(sample_cols or []),
        "freq_cols": list(freq_cols or []),
        "summarized": summarized or {"n": 10, "total_occurrences": 20},
        "perform_test": bool(perform_test and hypothesized_rate is not None),
        "hypothesized_rate": float(hypothesized_rate) if (perform_test and hypothesized_rate is not None) else None,
        "confidence_level": float(confidence_level),
        "alternative": alternative,
        "method": method,
        "length_of_observation": float(length_of_observation),
    }


def calculate_one_sample_poisson(
    sample_name: str,
    n: int,
    total_occurrences: int,
    length_of_observation: float = 1.0,
    confidence_level: float = 95.0,
    alternative: str = "not_equal",  # "not_equal", "less", "greater"
    method: str = "exact",  # "exact", "normal_approx"
    hypothesized_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """Calculate descriptive statistics, confidence interval, and test for One-Sample Poisson Rate."""
    if n <= 0:
        raise ValueError("Sample size must be at least 1.")
    if total_occurrences < 0:
        raise ValueError("Total occurrences cannot be negative.")
    if length_of_observation <= 0:
        raise ValueError("Length of observation must be positive.")
    if not (0.0 < confidence_level < 100.0):
        raise ValueError("Confidence level must be between 0 and 100.")
    if hypothesized_rate is not None and hypothesized_rate <= 0:
        raise ValueError("Hypothesized rate must be strictly positive.")

    total_exposure = n * length_of_observation
    sample_rate = total_occurrences / total_exposure
    mean_per_unit = total_occurrences / n

    alpha = 1.0 - (confidence_level / 100.0)

    # Confidence Interval
    if method == "exact":
        if alternative == "not_equal":
            if total_occurrences == 0:
                ci_lower = 0.0
            else:
                ci_lower = float(stats.chi2.ppf(alpha / 2.0, 2 * total_occurrences) / (2.0 * total_exposure))
            ci_upper = float(stats.chi2.ppf(1.0 - alpha / 2.0, 2 * (total_occurrences + 1)) / (2.0 * total_exposure))
        elif alternative == "less":
            ci_lower = None
            ci_upper = float(stats.chi2.ppf(1.0 - alpha, 2 * (total_occurrences + 1)) / (2.0 * total_exposure))
        elif alternative == "greater":
            if total_occurrences == 0:
                ci_lower = 0.0
            else:
                ci_lower = float(stats.chi2.ppf(alpha, 2 * total_occurrences) / (2.0 * total_exposure))
            ci_upper = None
        else:
            raise ValueError(f"Unknown alternative: {alternative}")
    else:  # normal_approx
        se = math.sqrt(sample_rate / total_exposure) if sample_rate > 0 else 0.0
        if alternative == "not_equal":
            z_crit = float(stats.norm.ppf(1.0 - alpha / 2.0))
            ci_lower = max(0.0, sample_rate - z_crit * se)
            ci_upper = sample_rate + z_crit * se
        elif alternative == "less":
            z_crit = float(stats.norm.ppf(1.0 - alpha))
            ci_lower = None
            ci_upper = sample_rate + z_crit * se
        elif alternative == "greater":
            z_crit = float(stats.norm.ppf(1.0 - alpha))
            ci_lower = max(0.0, sample_rate - z_crit * se)
            ci_upper = None
        else:
            raise ValueError(f"Unknown alternative: {alternative}")

    # Hypothesis Testing
    z_value = None
    p_value = None
    if hypothesized_rate is not None:
        mu0 = total_exposure * hypothesized_rate
        if method == "exact":
            if alternative == "less":
                p_value = float(stats.poisson.cdf(total_occurrences, mu0))
            elif alternative == "greater":
                p_value = float(1.0 - stats.poisson.cdf(total_occurrences - 1, mu0)) if total_occurrences > 0 else 1.0
            else:  # not_equal
                cdf_val = float(stats.poisson.cdf(total_occurrences, mu0))
                sf_val = float(1.0 - stats.poisson.cdf(total_occurrences - 1, mu0)) if total_occurrences > 0 else 1.0
                p_value = float(min(1.0, 2.0 * min(cdf_val, sf_val)))
        else:  # normal_approx
            se0 = math.sqrt(hypothesized_rate / total_exposure)
            z_value = (sample_rate - hypothesized_rate) / se0
            if alternative == "less":
                p_value = float(stats.norm.cdf(z_value))
            elif alternative == "greater":
                p_value = float(1.0 - stats.norm.cdf(z_value))
            else:  # not_equal
                p_value = float(2.0 * (1.0 - stats.norm.cdf(abs(z_value))))

    return {
        "sample_name": sample_name,
        "n": n,
        "total_occurrences": total_occurrences,
        "length_of_observation": length_of_observation,
        "total_exposure": total_exposure,
        "sample_rate": sample_rate,
        "mean_per_unit": mean_per_unit,
        "confidence_level": confidence_level,
        "alternative": alternative,
        "method": method,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "hypothesized_rate": hypothesized_rate,
        "z_value": z_value,
        "p_value": p_value,
    }


def run_one_sample_poisson(worksheet_or_samples: Any, settings: Dict[str, Any]) -> Dict[str, Any]:
    """Execute One-Sample Poisson Rate test on worksheet columns or summarized data."""
    st = one_sample_poisson_settings(**settings)
    data_format = st["data_format"]
    conf_level = st["confidence_level"]
    length = st["length_of_observation"]
    alt = st["alternative"]
    method = st["method"]
    hypo_rate = st["hypothesized_rate"]

    samples_results: List[Dict[str, Any]] = []

    if data_format == 1:  # Summarized data
        summ = st["summarized"]
        n = int(summ.get("n", summ.get("sample_size", 10)))
        total_occur = int(summ.get("total_occurrences", 20))
        res = calculate_one_sample_poisson(
            sample_name="Sample",
            n=n,
            total_occurrences=total_occur,
            length_of_observation=length,
            confidence_level=conf_level,
            alternative=alt,
            method=method,
            hypothesized_rate=hypo_rate,
        )
        samples_results.append(res)
    else:  # Columns mode
        sample_cols = st["sample_cols"]
        freq_cols = st["freq_cols"]
        if not sample_cols:
            raise ValueError("Please specify at least one sample column.")

        ws = worksheet_or_samples

        def get_col_data(col_spec: Union[int, str]) -> Tuple[str, List[Any]]:
            name = str(col_spec)
            vals: List[Any] = []
            if hasattr(ws, "columns"):
                if isinstance(col_spec, int):
                    if 0 <= col_spec < len(ws.columns):
                        c = ws.columns[col_spec]
                        return c.name or f"C{col_spec+1}", list(c.values)
                spec_str = str(col_spec).strip().upper()
                for idx, c in enumerate(ws.columns):
                    if (c.name and c.name.strip().upper() == spec_str) or f"C{idx+1}".upper() == spec_str:
                        return c.name or f"C{idx+1}", list(c.values)
            elif isinstance(ws, dict):
                if col_spec in ws:
                    return str(col_spec), list(ws[col_spec])
            return name, vals

        for i, s_col in enumerate(sample_cols):
            s_name, s_vals = get_col_data(s_col)
            f_vals = None
            if freq_cols and i < len(freq_cols):
                _, f_vals = get_col_data(freq_cols[i])

            # Aggregate occurrences and n
            total_n = 0
            total_occur = 0
            if f_vals is not None:
                for sv, fv in zip(s_vals, f_vals):
                    if sv is None or fv is None:
                        continue
                    try:
                        s_num = float(str(sv).strip())
                        f_num = float(str(fv).strip())
                        if s_num < 0 or f_num <= 0:
                            continue
                        if not s_num.is_integer() or not f_num.is_integer():
                            raise ValueError("Occurrences and frequencies must be integers.")
                        total_n += int(f_num)
                        total_occur += int(s_num) * int(f_num)
                    except ValueError as e:
                        if "integers" in str(e):
                            raise
                        continue
            else:
                for sv in s_vals:
                    if sv is None:
                        continue
                    try:
                        s_str = str(sv).strip()
                        if not s_str or s_str == "*":
                            continue
                        s_num = float(s_str)
                        if s_num < 0:
                            raise ValueError("Occurrences cannot be negative.")
                        if not s_num.is_integer():
                            raise ValueError("Occurrences must be non-negative integers.")
                        total_n += 1
                        total_occur += int(s_num)
                    except ValueError as e:
                        if "Occurrences" in str(e):
                            raise
                        continue

            if total_n == 0:
                raise ValueError(f"No valid observations found in column '{s_name}'.")

            res = calculate_one_sample_poisson(
                sample_name=s_name,
                n=total_n,
                total_occurrences=total_occur,
                length_of_observation=length,
                confidence_level=conf_level,
                alternative=alt,
                method=method,
                hypothesized_rate=hypo_rate,
            )
            samples_results.append(res)

    return {
        "one_sample_poisson": True,
        "settings": st,
        "confidence_level": conf_level,
        "length_of_observation": length,
        "alternative": alt,
        "method": method,
        "hypothesized_rate": hypo_rate,
        "samples": samples_results,
        "native_parity": True,
    }
