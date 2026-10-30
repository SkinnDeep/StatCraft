"""Native StatCraft Two-Sample Variances engine (0254-2VARIANCES.MDF + child forms)."""
import math
from scipy import stats
from .engine import normalize_numeric
from .value_order import ordered_values


def compute_two_variances(
    sample1_name="Sample 1",
    sample2_name="Sample 2",
    sample1_values=None,
    sample2_values=None,
    sample1_size=None,
    sample1_stdev=None,
    sample1_variance=None,
    sample2_size=None,
    sample2_stdev=None,
    sample2_variance=None,
    hypothesized_ratio=1.0,
    is_variance_ratio=False,
    confidence_level=95.0,
    alternative="not_equal",  # 'not_equal', 'less', 'greater'
    use_normal_distribution=True,
    graphs=None,
    results_options=None,
):
    """Compute Two-Sample Variances test, confidence intervals, and ratios."""
    conf = float(confidence_level)
    if not math.isfinite(conf) or conf <= 0.0 or conf >= 100.0:
        raise ValueError("Confidence level must be strictly between 0 and 100.")
    alpha = 1.0 - (conf / 100.0)

    ratio_val = float(hypothesized_ratio)
    if not math.isfinite(ratio_val) or ratio_val <= 0.0:
        raise ValueError("Hypothesized ratio must be positive and finite.")

    if is_variance_ratio:
        null_ratio_var = ratio_val
        null_ratio_sd = math.sqrt(ratio_val)
    else:
        null_ratio_sd = ratio_val
        null_ratio_var = ratio_val ** 2

    clean1 = None
    clean2 = None

    # Sample 1 stats
    if sample1_values is not None:
        raw1 = list(sample1_values)
        clean1 = [normalize_numeric(v) for v in raw1]
        clean1 = [v for v in clean1 if v is not None]
        n1 = len(clean1)
        if n1 < 2:
            raise ValueError(f"{sample1_name} requires at least 2 nonmissing observations.")
        mean1 = math.fsum(clean1) / n1
        var1 = math.fsum((x - mean1) ** 2 for x in clean1) / (n1 - 1)
        if var1 <= 0:
            raise ValueError(f"{sample1_name} requires nonconstant data.")
        sd1 = math.sqrt(var1)
    else:
        if sample1_size is None or int(sample1_size) < 2:
            raise ValueError("Sample 1 size must be an integer >= 2.")
        n1 = int(sample1_size)
        if sample1_variance is not None:
            var1 = float(sample1_variance)
            if not math.isfinite(var1) or var1 <= 0:
                raise ValueError("Sample 1 variance must be positive.")
            sd1 = math.sqrt(var1)
        elif sample1_stdev is not None:
            sd1 = float(sample1_stdev)
            if not math.isfinite(sd1) or sd1 <= 0:
                raise ValueError("Sample 1 standard deviation must be positive.")
            var1 = sd1 ** 2
        else:
            raise ValueError("Must provide either standard deviation or variance for Sample 1.")

    # Sample 2 stats
    if sample2_values is not None:
        raw2 = list(sample2_values)
        clean2 = [normalize_numeric(v) for v in raw2]
        clean2 = [v for v in clean2 if v is not None]
        n2 = len(clean2)
        if n2 < 2:
            raise ValueError(f"{sample2_name} requires at least 2 nonmissing observations.")
        mean2 = math.fsum(clean2) / n2
        var2 = math.fsum((x - mean2) ** 2 for x in clean2) / (n2 - 1)
        if var2 <= 0:
            raise ValueError(f"{sample2_name} requires nonconstant data.")
        sd2 = math.sqrt(var2)
    else:
        if sample2_size is None or int(sample2_size) < 2:
            raise ValueError("Sample 2 size must be an integer >= 2.")
        n2 = int(sample2_size)
        if sample2_variance is not None:
            var2 = float(sample2_variance)
            if not math.isfinite(var2) or var2 <= 0:
                raise ValueError("Sample 2 variance must be positive.")
            sd2 = math.sqrt(var2)
        elif sample2_stdev is not None:
            sd2 = float(sample2_stdev)
            if not math.isfinite(sd2) or sd2 <= 0:
                raise ValueError("Sample 2 standard deviation must be positive.")
            var2 = sd2 ** 2
        else:
            raise ValueError("Must provide either standard deviation or variance for Sample 2.")

    df1 = n1 - 1
    df2 = n2 - 1

    ratio_sd = sd1 / sd2
    ratio_var = var1 / var2

    # Individual Chi-square CIs for each sample standard deviation
    tail = alpha / 2.0
    q1_low = float(stats.chi2.ppf(tail, df1))
    q1_high = float(stats.chi2.ppf(1.0 - tail, df1))
    ci1_sd = (
        sd1 * math.sqrt(df1 / q1_high) if q1_high > 0 else 0.0,
        sd1 * math.sqrt(df1 / q1_low) if q1_low > 0 else math.inf,
    )

    q2_low = float(stats.chi2.ppf(tail, df2))
    q2_high = float(stats.chi2.ppf(1.0 - tail, df2))
    ci2_sd = (
        sd2 * math.sqrt(df2 / q2_high) if q2_high > 0 else 0.0,
        sd2 * math.sqrt(df2 / q2_low) if q2_low > 0 else math.inf,
    )

    # F-Test for ratio of variances / standard deviations
    # Under H0, F = (s1^2 / s2^2) / null_ratio_var ~ F(df1, df2)
    f_stat = ratio_var / null_ratio_var

    if alternative == "less":
        p_val_f = float(stats.f.cdf(f_stat, df1, df2))
        f_low = float(stats.f.ppf(alpha, df1, df2))
        ci_var_f = (0.0, ratio_var / f_low if f_low > 0 else math.inf)
        ci_sd_f = (0.0, math.sqrt(ci_var_f[1]) if math.isfinite(ci_var_f[1]) else math.inf)
    elif alternative == "greater":
        p_val_f = float(stats.f.sf(f_stat, df1, df2))
        f_high = float(stats.f.ppf(1.0 - alpha, df1, df2))
        ci_var_f = (ratio_var / f_high if f_high > 0 else 0.0, math.inf)
        ci_sd_f = (math.sqrt(ci_var_f[0]), math.inf)
    else:  # not_equal
        cdf_f = float(stats.f.cdf(f_stat, df1, df2))
        sf_f = float(stats.f.sf(f_stat, df1, df2))
        p_val_f = float(min(1.0, 2.0 * min(cdf_f, sf_f)))

        f_lower_crit = float(stats.f.ppf(1.0 - tail, df1, df2))
        f_upper_crit = float(stats.f.ppf(tail, df1, df2))
        ci_var_f = (
            ratio_var / f_lower_crit if f_lower_crit > 0 else 0.0,
            ratio_var / f_upper_crit if f_upper_crit > 0 else math.inf,
        )
        ci_sd_f = (
            math.sqrt(ci_var_f[0]) if ci_var_f[0] > 0 else 0.0,
            math.sqrt(ci_var_f[1]) if math.isfinite(ci_var_f[1]) else math.inf,
        )

    # Non-normal tests (Bonett and Levene) if raw data is provided
    bonett_res = None
    levene_res = None
    if clean1 is not None and clean2 is not None:
        # Levene test
        med1 = float(stats.scoreatpercentile(clean1, 50))
        med2 = float(stats.scoreatpercentile(clean2, 50))
        z1 = [abs(x - med1) for x in clean1]
        z2 = [abs(x - med2) for x in clean2]
        all_z = z1 + z2
        n_tot = n1 + n2
        grand_z = math.fsum(all_z) / n_tot
        m_z1 = math.fsum(z1) / n1
        m_z2 = math.fsum(z2) / n2
        ss_between = n1 * ((m_z1 - grand_z) ** 2) + n2 * ((m_z2 - grand_z) ** 2)
        ss_within = math.fsum((v - m_z1) ** 2 for v in z1) + math.fsum((v - m_z2) ** 2 for v in z2)
        if ss_within > 0:
            f_levene = (ss_between / 1.0) / (ss_within / (n_tot - 2.0))
            p_levene = float(stats.f.sf(f_levene, 1, n_tot - 2))
        else:
            f_levene = 0.0
            p_levene = 1.0
        levene_res = {
            "statistic": f_levene,
            "df1": 1,
            "df2": n_tot - 2,
            "p_value": p_levene,
        }

        # Bonett test for ratio of standard deviations
        m1_4 = math.fsum((x - math.fsum(clean1)/n1)**4 for x in clean1) / n1
        m1_2 = math.fsum((x - math.fsum(clean1)/n1)**2 for x in clean1) / n1
        gamma1 = m1_4 / (m1_2 ** 2) if m1_2 > 0 else 3.0

        m2_4 = math.fsum((x - math.fsum(clean2)/n2)**4 for x in clean2) / n2
        m2_2 = math.fsum((x - math.fsum(clean2)/n2)**2 for x in clean2) / n2
        gamma2 = m2_4 / (m2_2 ** 2) if m2_2 > 0 else 3.0

        var_ln1 = max(0.0, (gamma1 - ((n1 - 3.0) / n1)) / (4.0 * (n1 - 1.0)))
        var_ln2 = max(0.0, (gamma2 - ((n2 - 3.0) / n2)) / (4.0 * (n2 - 1.0)))
        se_ln_diff = math.sqrt(var_ln1 + var_ln2)
        se_ln_diff = max(se_ln_diff, 1e-12)

        z_bonett = (math.log(ratio_sd) - math.log(null_ratio_sd)) / se_ln_diff
        if alternative == "less":
            p_bonett = float(stats.norm.cdf(z_bonett))
            z_crit = float(stats.norm.ppf(1.0 - alpha))
            b_high = ratio_sd * math.exp(z_crit * se_ln_diff)
            ci_sd_bonett = (0.0, b_high)
            ci_var_bonett = (0.0, b_high ** 2)
        elif alternative == "greater":
            p_bonett = float(stats.norm.sf(z_bonett))
            z_crit = float(stats.norm.ppf(1.0 - alpha))
            b_low = ratio_sd * math.exp(-z_crit * se_ln_diff)
            ci_sd_bonett = (b_low, math.inf)
            ci_var_bonett = (b_low ** 2, math.inf)
        else:
            p_bonett = float(min(1.0, 2.0 * stats.norm.sf(abs(z_bonett))))
            z_crit = float(stats.norm.ppf(1.0 - alpha / 2.0))
            b_low = ratio_sd * math.exp(-z_crit * se_ln_diff)
            b_high = ratio_sd * math.exp(z_crit * se_ln_diff)
            ci_sd_bonett = (b_low, b_high)
            ci_var_bonett = (b_low ** 2, b_high ** 2)

        bonett_res = {
            "statistic": z_bonett,
            "df": 1,
            "p_value": p_bonett,
            "ci_sd": ci_sd_bonett,
            "ci_var": ci_var_bonett,
        }

    return {
        "sample1": {
            "name": sample1_name,
            "n": n1,
            "stdev": sd1,
            "variance": var1,
            "ci_stdev": ci1_sd,
            "raw_data": clean1,
        },
        "sample2": {
            "name": sample2_name,
            "n": n2,
            "stdev": sd2,
            "variance": var2,
            "ci_stdev": ci2_sd,
            "raw_data": clean2,
        },
        "ratio_sd": ratio_sd,
        "ratio_variance": ratio_var,
        "null_ratio_sd": null_ratio_sd,
        "null_ratio_variance": null_ratio_var,
        "is_variance_ratio": is_variance_ratio,
        "confidence_level": conf,
        "alternative": alternative,
        "use_normal_distribution": use_normal_distribution,
        "has_raw_data": clean1 is not None and clean2 is not None,
        "f_test": {
            "statistic": f_stat,
            "df1": df1,
            "df2": df2,
            "p_value": p_val_f,
            "ci_sd": ci_sd_f,
            "ci_variance": ci_var_f,
        },
        "bonett": bonett_res,
        "levene": levene_res,
        "graphs": dict(graphs or {}),
        "results_options": dict(results_options or {}),
    }
