"""Native StatCraft Test for Equal Variances engine (VARTEST.MDF + child forms)."""
import math
from scipy import stats
from .engine import normalize_numeric
from .variance_tests import equal_variances, _median
from .value_order import ordered_values


def equal_variances_settings(options=None):
    """Validate and normalize options for Test for Equal Variances."""
    raw = dict(options or {})
    conf = raw.get("confidence_level", 95.0)
    try:
        conf = float(conf)
    except (TypeError, ValueError) as exc:
        raise ValueError("Confidence level must be a number between 0 and 100.") from exc
    if not math.isfinite(conf) or conf <= 0.0 or conf >= 100.0:
        raise ValueError("Confidence level must be strictly between 0 and 100.")

    use_normal = bool(raw.get("use_normal_distribution", False))

    raw_graphs = dict(raw.get("graphs") or {})
    graphs = {
        "summary_plot": bool(raw_graphs.get("summary_plot", True)),
        "individual_value_plot": bool(raw_graphs.get("individual_value_plot", False)),
        "boxplot": bool(raw_graphs.get("boxplot", False)),
    }

    raw_results = dict(raw.get("results") or {})
    results = {
        "method": bool(raw_results.get("method", True)),
        "confidence_intervals": bool(raw_results.get("confidence_intervals", True)),
        "tests": bool(raw_results.get("tests", True)),
    }

    raw_storage = dict(raw.get("storage") or {})
    storage = {
        "stdevs": bool(raw_storage.get("stdevs", False)),
        "variances": bool(raw_storage.get("variances", False)),
        "bonferroni_ci": bool(raw_storage.get("bonferroni_ci", False)),
        "mci": False if use_normal else bool(raw_storage.get("mci", False)),
    }

    return {
        "confidence_level": conf,
        "use_normal_distribution": use_normal,
        "graphs": graphs,
        "results": results,
        "storage": storage,
    }


def _factor_token(col, row):
    val = col.values[row] if row < len(col.values) else None
    if val is None:
        return None
    if col.kind == "number":
        num = normalize_numeric(val)
        if num is None:
            return None
        return str(int(num)) if float(num).is_integer() else f"{num:g}"
    text = str(val).strip()
    return text if text else None


def _compute_bonferroni_ci(stdev, n, alpha, k):
    """Exact normal-theory Bonferroni CI for standard deviation."""
    df = n - 1
    if df < 1 or stdev <= 0:
        return (0.0, 0.0)
    alpha_tail = alpha / (2.0 * k)
    chi2_upper = float(stats.chi2.ppf(1.0 - alpha_tail, df))
    chi2_lower = float(stats.chi2.ppf(alpha_tail, df))
    low = stdev * math.sqrt(df / chi2_upper) if chi2_upper > 0 else 0.0
    high = stdev * math.sqrt(df / chi2_lower) if chi2_lower > 0 else stdev
    return (low, high)


def _compute_multiple_comparisons(clean_groups, summaries, alpha):
    """Compute Multiple Comparison Intervals (MCI) and overall Multiple Comparisons test."""
    k = len(clean_groups)
    # Critical value from studentized range distribution (or normal Bonferroni fallback)
    try:
        q_crit = float(stats.studentized_range.ppf(1.0 - alpha, k, math.inf))
        if not math.isfinite(q_crit) or q_crit <= 0:
            raise ValueError("Invalid studentized range quantile.")
        crit = q_crit / math.sqrt(2.0)
    except Exception:
        num_pairs = max(1, k * (k - 1) // 2)
        crit = float(stats.norm.ppf(1.0 - alpha / (2.0 * num_pairs)))

    log_sds = []
    se_logs = []
    mci_list = []

    for g, s in zip(clean_groups, summaries):
        n = s["count"]
        sd = s["sample_stdev"]
        med = s["median"]
        mean = s["mean"]
        if sd <= 0 or n < 2:
            log_sds.append(0.0)
            se_logs.append(0.0)
            mci_list.append((0.0, 0.0))
            continue
        # Fourth central moment / kurtosis estimator (Bonett 2006 / Layard)
        m2 = math.fsum((x - mean) ** 2 for x in g) / n
        m4 = math.fsum((x - med) ** 4 for x in g) / n
        gamma4 = (m4 / (m2 ** 2)) if m2 > 0 else 3.0
        # Bound kurtosis away from degeneracy so SE is well-behaved for small samples
        gamma_adj = max(1.2, min(50.0, gamma4))
        var_log_s = max(1e-6, (gamma_adj - (n - 3.0) / n) / (4.0 * (n - 1.0)))
        se_log = math.sqrt(var_log_s)
        # Half-width for non-overlapping visual comparison intervals
        half_w = (crit / math.sqrt(2.0)) * se_log
        low = sd * math.exp(-half_w)
        high = sd * math.exp(half_w)
        log_sds.append(math.log(sd))
        se_logs.append(se_log)
        mci_list.append((low, high))

    # Overall Multiple Comparisons test statistic (chi-square / maximum studentized spread)
    if all(se > 0 for se in se_logs):
        weights = [1.0 / (se ** 2) for se in se_sds] if False else [1.0 / (se ** 2) for se in se_logs]
        w_sum = math.fsum(weights)
        weighted_mean = math.fsum(w * l for w, l in zip(weights, log_sds)) / w_sum
        mc_stat = math.fsum(w * ((l - weighted_mean) ** 2) for w, l in zip(weights, log_sds))
        mc_p = float(stats.chi2.sf(mc_stat, k - 1))
    else:
        mc_stat = 0.0
        mc_p = 1.0

    return mci_list, mc_stat, mc_p


def run_test_equal_variances(
    worksheet,
    stacked=True,
    response_index=None,
    factor_indices=None,
    response_indices=None,
    options=None,
):
    """Run native StatCraft Test for Equal Variances on stacked or unstacked data."""
    cfg = equal_variances_settings(options)
    conf = cfg["confidence_level"]
    alpha = 1.0 - conf / 100.0
    use_normal = cfg["use_normal_distribution"]

    group_names = []
    raw_groups = []
    missing_rows = []
    factor_names = []
    response_name = ""

    if stacked:
        if response_index is None or not (0 <= response_index < len(worksheet.columns)):
            raise ValueError("Select a valid numeric response column.")
        resp_col = worksheet.columns[response_index]
        if resp_col.kind != "number":
            raise ValueError("Response column must be numeric.")
        response_name = resp_col.name

        if not factor_indices or not (1 <= len(factor_indices) <= 9):
            raise ValueError("Select between 1 and 9 factor columns.")
        seen_f = set()
        f_cols = []
        for idx in factor_indices:
            if not (0 <= idx < len(worksheet.columns)):
                raise ValueError("Invalid factor column selection.")
            if idx == response_index:
                raise ValueError("Response column cannot also be selected as a factor.")
            if idx in seen_f:
                raise ValueError("Factor columns must be distinct.")
            seen_f.add(idx)
            f_cols.append(worksheet.columns[idx])
        factor_names = [c.name for c in f_cols]

        row_count = max([len(resp_col.values)] + [len(c.values) for c in f_cols])
        buckets = {}
        first_seen_order = []

        for r in range(row_count):
            y_raw = resp_col.values[r] if r < len(resp_col.values) else None
            y_val = normalize_numeric(y_raw)
            tokens = [_factor_token(c, r) for c in f_cols]
            if y_val is None or any(t is None for t in tokens):
                if y_raw is not None or any((r < len(c.values) and c.values[r] is not None) for c in f_cols):
                    missing_rows.append(r + 1)
                continue
            key = " * ".join(tokens) if len(tokens) > 1 else tokens[0]
            if key not in buckets:
                buckets[key] = []
                first_seen_order.append(key)
            buckets[key].append(y_val)

        if len(buckets) < 2:
            raise ValueError("Factor column(s) must define at least two nonmissing groups.")

        if len(f_cols) == 1 and f_cols[0].kind == "text":
            ordered_keys = ordered_values(f_cols[0], list(buckets.keys()))
        elif len(f_cols) == 1 and f_cols[0].kind == "number":
            ordered_keys = sorted(buckets.keys(), key=lambda x: float(x))
        else:
            ordered_keys = sorted(buckets.keys())

        for key in ordered_keys:
            group_names.append(key)
            raw_groups.append(buckets[key])
    else:
        if not response_indices or len(response_indices) < 2:
            raise ValueError("Select at least two numeric response columns.")
        seen_r = set()
        for idx in response_indices:
            if not (0 <= idx < len(worksheet.columns)):
                raise ValueError("Invalid response column selection.")
            if idx in seen_r:
                raise ValueError("Response columns must be distinct.")
            seen_r.add(idx)
            col = worksheet.columns[idx]
            if col.kind != "number":
                raise ValueError(f"Column {col.name} must be numeric.")
            group_names.append(col.name)
            raw_groups.append(list(col.values))
        response_name = ", ".join(group_names)
        factor_names = []

    # Run core Levene test (always computed)
    levene_res = equal_variances(raw_groups, "Levene")

    # Run Bartlett test if requested or if all groups have positive variance
    bartlett_res = None
    if use_normal:
        bartlett_res = equal_variances(raw_groups, "Bartlett")
    else:
        try:
            bartlett_res = equal_variances(raw_groups, "Bartlett")
        except ValueError:
            bartlett_res = None

    clean_groups = []
    for g in raw_groups:
        clean = [normalize_numeric(v) for v in g]
        clean_groups.append([v for v in clean if v is not None])

    k = len(clean_groups)
    ind_conf = 100.0 * (1.0 - alpha / k)
    mci_bounds, mc_stat, mc_p = _compute_multiple_comparisons(clean_groups, levene_res["group_statistics"], alpha)

    groups_table = []
    for idx, (gname, stats_row, mci_pair) in enumerate(zip(group_names, levene_res["group_statistics"], mci_bounds)):
        n = stats_row["count"]
        sd = stats_row["sample_stdev"]
        var = sd ** 2
        bonf_low, bonf_high = _compute_bonferroni_ci(sd, n, alpha, k)
        groups_table.append({
            "index": idx + 1,
            "level": gname,
            "count": n,
            "mean": stats_row["mean"],
            "median": stats_row["median"],
            "stdev": sd,
            "variance": var,
            "bonf_lower": bonf_low,
            "bonf_upper": bonf_high,
            "mci_lower": mci_pair[0],
            "mci_upper": mci_pair[1],
            "values": clean_groups[idx],
        })

    tests_table = []
    if use_normal and bartlett_res is not None:
        tests_table.append({
            "method": "Bartlett",
            "test_statistic": bartlett_res["test_statistic"],
            "df1": bartlett_res["df_numerator"],
            "df2": None,
            "p_value": bartlett_res["p_value"],
        })
    else:
        tests_table.append({
            "method": "Multiple comparisons",
            "test_statistic": mc_stat,
            "df1": k - 1,
            "df2": None,
            "p_value": mc_p,
        })
    tests_table.append({
        "method": "Levene",
        "test_statistic": levene_res["test_statistic"],
        "df1": levene_res["df_numerator"],
        "df2": levene_res["df_denominator"],
        "p_value": levene_res["p_value"],
    })

    primary = bartlett_res if (use_normal and bartlett_res is not None) else levene_res

    return {
        "stacked": bool(stacked),
        "response_name": response_name,
        "factor_names": factor_names,
        "variables": group_names,
        "confidence_level": conf,
        "individual_confidence_level": ind_conf,
        "use_normal_distribution": use_normal,
        "method": primary["method"],
        "test_statistic": primary["test_statistic"],
        "p_value": primary["p_value"],
        "df": primary["df"],
        "df_numerator": primary["df_numerator"],
        "df_denominator": primary["df_denominator"],
        "levene": {
            "test_statistic": levene_res["test_statistic"],
            "df1": levene_res["df_numerator"],
            "df2": levene_res["df_denominator"],
            "p_value": levene_res["p_value"],
        },
        "bartlett": ({
            "test_statistic": bartlett_res["test_statistic"],
            "df1": bartlett_res["df_numerator"],
            "p_value": bartlett_res["p_value"],
        } if bartlett_res is not None else None),
        "multiple_comparisons": {
            "test_statistic": mc_stat,
            "df1": k - 1,
            "p_value": mc_p,
        },
        "groups": groups_table,
        "group_statistics": levene_res["group_statistics"],
        "tests": tests_table,
        "count": levene_res["count"],
        "missing": len(missing_rows) if stacked else levene_res["missing"],
        "missing_rows": missing_rows,
        "options": cfg,
        "assumptions": primary["assumptions"],
        "warnings": list(primary.get("warnings", [])),
    }


def _next_column_name(worksheet, base):
    existing = {c.name.upper() for c in worksheet.columns if c.name}
    if base.upper() not in existing:
        return base
    idx = 1
    while f"{base}{idx}".upper() in existing:
        idx += 1
    return f"{base}{idx}"


def store_equal_variances_columns(worksheet, result, options=None):
    """Store requested standard deviations, variances, Bonferroni CIs, and MCIs to worksheet."""
    from .model import Column
    cfg = equal_variances_settings(options or result.get("options"))
    storage = cfg["storage"]
    groups = result.get("groups", [])
    stored = []

    if storage.get("stdevs"):
        cname = _next_column_name(worksheet, "STDEV")
        worksheet.columns.append(Column(cname, "number", [g["stdev"] for g in groups]))
        stored.append(cname)

    if storage.get("variances"):
        cname = _next_column_name(worksheet, "VARIANCES")
        worksheet.columns.append(Column(cname, "number", [g["variance"] for g in groups]))
        stored.append(cname)

    if storage.get("bonferroni_ci"):
        c_low = _next_column_name(worksheet, "BONF1")
        worksheet.columns.append(Column(c_low, "number", [g["bonf_lower"] for g in groups]))
        c_high = _next_column_name(worksheet, "BONF2")
        worksheet.columns.append(Column(c_high, "number", [g["bonf_upper"] for g in groups]))
        stored.extend([c_low, c_high])

    if storage.get("mci") and not cfg.get("use_normal_distribution"):
        c_low = _next_column_name(worksheet, "MCI1")
        worksheet.columns.append(Column(c_low, "number", [g["mci_lower"] for g in groups]))
        c_high = _next_column_name(worksheet, "MCI2")
        worksheet.columns.append(Column(c_high, "number", [g["mci_upper"] for g in groups]))
        stored.extend([c_low, c_high])

    result["stored_columns"] = stored
    return stored
