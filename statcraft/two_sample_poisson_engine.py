"""Engine for StatCraft Two-Sample Poisson Rate (TwoRates)."""
from __future__ import annotations
import math
from typing import Dict, Any, List, Optional, Tuple, Sequence, Union
from scipy import stats


def two_sample_poisson_settings(
    settings: Optional[Union[Dict[str, Any], int, str]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Validate and normalize settings for Two-Sample Poisson Rate."""
    if isinstance(settings, dict):
        merged = dict(settings)
        merged.update(kwargs)
    else:
        merged = dict(kwargs)
        if settings is not None:
            merged["data_format"] = settings

    df_raw = merged.get("data_format", 1)
    if isinstance(df_raw, str):
        s = df_raw.casefold()
        if "stack" in s and "un" not in s: df_val = 0
        elif "sum" in s: df_val = 2
        else: df_val = 1
    else:
        df_val = int(df_raw)

    s1_col = merged.get("sample1_col", merged.get("sample1"))
    s2_col = merged.get("sample2_col", merged.get("sample2"))
    sample_col = merged.get("sample_col", merged.get("samples_col", merged.get("samples")))
    group_col = merged.get("group_col", merged.get("sample_ids_col", merged.get("sample_ids")))
    l1_col = merged.get("length1_col")
    l2_col = merged.get("length2_col")
    l_col = merged.get("length_col")

    sum_dict = dict(merged.get("summarized") or {})
    if "n1" in merged: sum_dict["n1"] = int(merged["n1"])
    if "x1" in merged: sum_dict["total_occurrences1"] = int(merged["x1"])
    if "total_occurrences1" in merged: sum_dict["total_occurrences1"] = int(merged["total_occurrences1"])
    if "n2" in merged: sum_dict["n2"] = int(merged["n2"])
    if "x2" in merged: sum_dict["total_occurrences2"] = int(merged["x2"])
    if "total_occurrences2" in merged: sum_dict["total_occurrences2"] = int(merged["total_occurrences2"])
    if not sum_dict and df_val == 2:
        sum_dict = {
            "n1": 50,
            "total_occurrences1": 80,
            "n2": 50,
            "total_occurrences2": 50,
        }

    return {
        "data_format": df_val,
        "sample1_col": s1_col,
        "sample2_col": s2_col,
        "samples_col": sample_col,
        "sample_ids_col": group_col,
        "length1_col": l1_col,
        "length2_col": l2_col,
        "length_col": l_col,
        "freq_col": merged.get("freq_col"),
        "freq_cols": list(merged.get("freq_cols") or []),
        "summarized": sum_dict,
        "confidence_level": float(merged.get("confidence_level", 95.0)),
        "hypothesized_difference": float(merged.get("hypothesized_difference", 0.0)),
        "alternative": str(merged.get("alternative", "not_equal")),
        "test_method": str(merged.get("test_method", "separate")),
        "length_of_observation": float(merged.get("length_of_observation", 1.0)),
    }


def calculate_two_sample_poisson(
    n1: Optional[int] = None,
    total_occurrences1: Optional[int] = None,
    n2: Optional[int] = None,
    total_occurrences2: Optional[int] = None,
    sample1_name: str = "Sample 1",
    sample2_name: str = "Sample 2",
    length_of_observation: float = 1.0,
    confidence_level: float = 95.0,
    hypothesized_difference: float = 0.0,
    alternative: str = "not_equal",
    test_method: str = "separate",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Calculate descriptive statistics, difference CI, and test for Two-Sample Poisson Rate."""
    x1 = kwargs.get("x1", total_occurrences1 if total_occurrences1 is not None else 0)
    x2 = kwargs.get("x2", total_occurrences2 if total_occurrences2 is not None else 0)
    t1_in = kwargs.get("t1")
    t2_in = kwargs.get("t2")
    n1_val = n1 if n1 is not None else (int(t1_in) if t1_in is not None else 1)
    n2_val = n2 if n2 is not None else (int(t2_in) if t2_in is not None else 1)
    total_occurrences1 = x1
    total_occurrences2 = x2
    if n1_val <= 0 or n2_val <= 0:
        raise ValueError("Sample sizes must be at least 1.")
    if total_occurrences1 < 0 or total_occurrences2 < 0:
        raise ValueError("Total occurrences cannot be negative.")
    if length_of_observation <= 0:
        raise ValueError("Length of observation must be positive.")
    if not (0.0 < confidence_level < 100.0):
        raise ValueError("Confidence level must be between 0 and 100.")

    t1 = float(t1_in) if t1_in is not None else (n1_val * length_of_observation)
    t2 = float(t2_in) if t2_in is not None else (n2_val * length_of_observation)
    rate1 = total_occurrences1 / t1
    rate2 = total_occurrences2 / t2
    diff = rate1 - rate2

    # Standard error for difference (unpooled)
    se_diff = math.sqrt((rate1 / t1) + (rate2 / t2)) if (rate1 > 0 or rate2 > 0) else 0.0

    alpha = 1.0 - (confidence_level / 100.0)

    # Confidence Interval (unpooled Wald)
    if alternative == "not_equal":
        z_crit = float(stats.norm.ppf(1.0 - alpha / 2.0))
        ci_lower = diff - z_crit * se_diff
        ci_upper = diff + z_crit * se_diff
    elif alternative == "less":
        z_crit = float(stats.norm.ppf(1.0 - alpha))
        ci_lower = None
        ci_upper = diff + z_crit * se_diff
    elif alternative == "greater":
        z_crit = float(stats.norm.ppf(1.0 - alpha))
        ci_lower = diff - z_crit * se_diff
        ci_upper = None
    else:
        raise ValueError(f"Unknown alternative: {alternative}")

    # Hypothesis Testing
    delta0 = hypothesized_difference
    z_value = None
    p_value = None
    p_value_exact = None

    if test_method == "pooled" and delta0 == 0.0:
        tot_x = total_occurrences1 + total_occurrences2
        tot_t = t1 + t2
        rate_pool = tot_x / tot_t
        se_pool = math.sqrt(rate_pool * ((1.0 / t1) + (1.0 / t2))) if rate_pool > 0 else 0.0
        z_value = (diff - delta0) / se_pool if se_pool > 0 else 0.0

        # Exact test via conditional binomial distribution
        if tot_x > 0:
            pi0 = t1 / (t1 + t2)
            alt_binom = "two-sided" if alternative == "not_equal" else alternative
            p_value_exact = float(stats.binomtest(total_occurrences1, tot_x, p=pi0, alternative=alt_binom).pvalue)
    else:
        z_value = (diff - delta0) / se_diff if se_diff > 0 else 0.0

    if z_value is not None:
        if alternative == "less":
            p_value = float(stats.norm.cdf(z_value))
        elif alternative == "greater":
            p_value = float(1.0 - stats.norm.cdf(z_value))
        else:
            p_value = float(2.0 * (1.0 - stats.norm.cdf(abs(z_value))))

    return {
        "sample1_name": sample1_name,
        "sample2_name": sample2_name,
        "n1": n1_val,
        "n2": n2_val,
        "x1": total_occurrences1,
        "x2": total_occurrences2,
        "t1": t1,
        "t2": t2,
        "rate1": rate1,
        "rate2": rate2,
        "diff": diff,
        "sample1": {
            "name": sample1_name,
            "n": n1_val,
            "total_occurrences": total_occurrences1,
            "total_exposure": t1,
            "sample_rate": rate1,
            "mean_per_unit": total_occurrences1 / n1_val,
        },
        "sample2": {
            "name": sample2_name,
            "n": n2_val,
            "total_occurrences": total_occurrences2,
            "total_exposure": t2,
            "sample_rate": rate2,
            "mean_per_unit": total_occurrences2 / n2_val,
        },
        "difference": diff,
        "length_of_observation": length_of_observation,
        "confidence_level": confidence_level,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "hypothesized_difference": hypothesized_difference,
        "alternative": alternative,
        "test_method": test_method,
        "z_value": z_value,
        "p_value": p_value,
        "p_value_exact": p_value_exact,
        "exact_p_value": p_value_exact,
    }


def run_two_sample_poisson(worksheet_or_samples: Any, settings: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Two-Sample Poisson Rate test on worksheet columns or summarized data."""
    st = two_sample_poisson_settings(**settings)
    fmt = st["data_format"]
    conf = st["confidence_level"]
    length = st["length_of_observation"]
    hypo_diff = st["hypothesized_difference"]
    alt = st["alternative"]
    test_method = st["test_method"]

    if fmt == 2:  # Summarized
        s = st["summarized"]
        res = calculate_two_sample_poisson(
            n1=int(s["n1"]),
            total_occurrences1=int(s["total_occurrences1"]),
            n2=int(s["n2"]),
            total_occurrences2=int(s["total_occurrences2"]),
            sample1_name="Sample 1",
            sample2_name="Sample 2",
            length_of_observation=length,
            confidence_level=conf,
            hypothesized_difference=hypo_diff,
            alternative=alt,
            test_method=test_method,
        )
    else:
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

        if fmt == 0:  # Stacked
            s_name, s_vals = get_col_data(st["samples_col"])
            id_name, id_vals = get_col_data(st["sample_ids_col"])
            f_vals = None
            if st.get("freq_col") is not None:
                _, f_vals = get_col_data(st["freq_col"])
            l_vals = None
            if st.get("length_col") is not None:
                _, l_vals = get_col_data(st["length_col"])

            groups: Dict[Any, List[Tuple[float, float, float]]] = {}
            for row_idx in range(min(len(s_vals), len(id_vals))):
                sv = s_vals[row_idx]
                iv = id_vals[row_idx]
                fv = f_vals[row_idx] if f_vals is not None and row_idx < len(f_vals) else 1.0
                lv = l_vals[row_idx] if l_vals is not None and row_idx < len(l_vals) else length
                if sv is None or iv is None or str(sv).strip() == "*" or str(iv).strip() == "*":
                    continue
                try:
                    s_num = float(str(sv).strip())
                    f_num = float(str(fv).strip()) if fv is not None else 1.0
                    l_num = float(str(lv).strip()) if lv is not None else length
                    if s_num < 0 or f_num <= 0 or l_num <= 0:
                        continue
                    if not s_num.is_integer() or not f_num.is_integer():
                        raise ValueError("Occurrences and frequencies must be integers.")
                    grp_key = str(iv).strip()
                    if grp_key not in groups:
                        groups[grp_key] = []
                    groups[grp_key].append((int(s_num), int(f_num), float(l_num)))
                except ValueError as e:
                    if "integers" in str(e):
                        raise
                    continue

            if len(groups) != 2:
                raise ValueError(f"Sample IDs column must contain exactly 2 distinct groups. Found: {len(groups)}")

            keys = list(groups.keys())
            g1_name, g2_name = keys[0], keys[1]
            n1 = sum(f for _, f, _ in groups[g1_name])
            tot1 = sum(s * f for s, f, _ in groups[g1_name])
            t1 = sum(l * f for _, f, l in groups[g1_name])
            n2 = sum(f for _, f, _ in groups[g2_name])
            tot2 = sum(s * f for s, f, _ in groups[g2_name])
            t2 = sum(l * f for _, f, l in groups[g2_name])

            res = calculate_two_sample_poisson(
                n1=n1,
                total_occurrences1=tot1,
                n2=n2,
                total_occurrences2=tot2,
                sample1_name=g1_name,
                sample2_name=g2_name,
                length_of_observation=length,
                t1=t1,
                t2=t2,
                confidence_level=conf,
                hypothesized_difference=hypo_diff,
                alternative=alt,
                test_method=test_method,
            )
        else:  # Unstacked (Each sample in its own column)
            s1_name, s1_vals = get_col_data(st["sample1_col"])
            s2_name, s2_vals = get_col_data(st["sample2_col"])
            f_cols = st.get("freq_cols") or []
            f1_vals = None
            f2_vals = None
            if len(f_cols) > 0:
                _, f1_vals = get_col_data(f_cols[0])
            if len(f_cols) > 1:
                _, f2_vals = get_col_data(f_cols[1])
            l1_vals = None
            l2_vals = None
            if st.get("length1_col") is not None:
                _, l1_vals = get_col_data(st["length1_col"])
            if st.get("length2_col") is not None:
                _, l2_vals = get_col_data(st["length2_col"])

            def extract_col_sum(vals: List[Any], freqs: Optional[List[Any]], lengths: Optional[List[Any]]) -> Tuple[int, int, float]:
                tot_n = 0
                tot_occur = 0
                tot_t = 0.0
                for row_idx, sv in enumerate(vals):
                    if sv is None or str(sv).strip() == "*":
                        continue
                    fv = freqs[row_idx] if freqs is not None and row_idx < len(freqs) else 1.0
                    lv = lengths[row_idx] if lengths is not None and row_idx < len(lengths) else length
                    if fv is None or str(fv).strip() == "*":
                        continue
                    try:
                        s_num = float(str(sv).strip())
                        f_num = float(str(fv).strip())
                        l_num = float(str(lv).strip()) if lv is not None else length
                        if s_num < 0 or f_num <= 0 or l_num <= 0:
                            continue
                        if not s_num.is_integer() or not f_num.is_integer():
                            raise ValueError("Occurrences and frequencies must be integers.")
                        tot_n += int(f_num)
                        tot_occur += int(s_num) * int(f_num)
                        tot_t += float(l_num) * int(f_num)
                    except ValueError as e:
                        if "integers" in str(e):
                            raise
                        continue
                return tot_n, tot_occur, tot_t

            n1, tot1, t1 = extract_col_sum(s1_vals, f1_vals, l1_vals)
            n2, tot2, t2 = extract_col_sum(s2_vals, f2_vals, l2_vals)

            if n1 == 0:
                raise ValueError(f"No valid observations in column '{s1_name}'.")
            if n2 == 0:
                raise ValueError(f"No valid observations in column '{s2_name}'.")

            res = calculate_two_sample_poisson(
                n1=n1,
                total_occurrences1=tot1,
                n2=n2,
                total_occurrences2=tot2,
                sample1_name=s1_name,
                sample2_name=s2_name,
                length_of_observation=length,
                t1=t1,
                t2=t2,
                confidence_level=conf,
                hypothesized_difference=hypo_diff,
                alternative=alt,
                test_method=test_method,
            )

    return {
        "two_sample_poisson": True,
        "settings": st,
        "result": res,
        "confidence_level": conf,
        "length_of_observation": length,
        "hypothesized_difference": hypo_diff,
        "alternative": alt,
        "test_method": test_method,
        "difference": res["difference"],
        "diff": res["difference"],
        "ci_lower": res["ci_lower"],
        "ci_upper": res["ci_upper"],
        "z_value": res["z_value"],
        "p_value": res["p_value"],
        "p_value_exact": res["p_value_exact"],
        "exact_p_value": res["p_value_exact"],
        "sample1": res["sample1"],
        "sample2": res["sample2"],
        "x1": res["sample1"]["total_occurrences"],
        "x2": res["sample2"]["total_occurrences"],
        "n1": res["sample1"]["n"],
        "n2": res["sample2"]["n"],
        "t1": res["sample1"]["total_exposure"],
        "t2": res["sample2"]["total_exposure"],
        "rate1": res["sample1"]["sample_rate"],
        "rate2": res["sample2"]["sample_rate"],
        "native_parity": False,
    }
