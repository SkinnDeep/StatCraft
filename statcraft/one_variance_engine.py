"""Native StatCraft One-Sample Variance engine (0245-1VARIANCE.MDF + 0246-1VARIANCEOPTIONS.MDF)."""
import math
from scipy import stats
from .engine import normalize_numeric


def _bonett_kurtosis(clean):
    n = len(clean)
    mean = math.fsum(clean) / n
    m2 = math.fsum((x - mean) ** 2 for x in clean) / n
    m4 = math.fsum((x - mean) ** 4 for x in clean) / n
    if m2 <= 0:
        return 3.0
    return m4 / (m2 ** 2)


def compute_one_variance_sample(
    sample_name="Sample",
    values=None,
    sample_size=None,
    sample_stdev=None,
    sample_variance=None,
    hypothesized_value=1.0,
    is_variance_test=False,
    perform_test=True,
    confidence_level=95.0,
    alternative="not_equal",  # 'not_equal', 'less', 'greater'
):
    """Compute 1-Sample Variance test and confidence intervals.

    Supports both raw observations and summarized inputs (size + stdev/variance).
    """
    conf = float(confidence_level)
    if not math.isfinite(conf) or conf <= 0.0 or conf >= 100.0:
        raise ValueError("Confidence level must be strictly between 0 and 100.")
    alpha = 1.0 - (conf / 100.0)

    hyp_val = float(hypothesized_value)
    if not math.isfinite(hyp_val) or hyp_val <= 0.0:
        raise ValueError("Hypothesized value must be positive and finite.")

    if is_variance_test:
        null_var = hyp_val
        null_sd = math.sqrt(hyp_val)
    else:
        null_sd = hyp_val
        null_var = hyp_val ** 2

    # Extract sample statistics
    clean = None
    if values is not None:
        raw = list(values)
        clean = [normalize_numeric(v) for v in raw]
        clean = [v for v in clean if v is not None]
        n = len(clean)
        missing = len(raw) - n
        if n < 2:
            raise ValueError(f"{sample_name} requires at least 2 finite nonmissing observations.")
        mean = math.fsum(clean) / n
        var = math.fsum((x - mean) ** 2 for x in clean) / (n - 1)
        if var <= 0:
            raise ValueError(f"{sample_name} requires nonconstant data with positive variance.")
        sd = math.sqrt(var)
    else:
        if sample_size is None or int(sample_size) < 2:
            raise ValueError("Sample size must be an integer >= 2.")
        n = int(sample_size)
        missing = 0
        mean = None
        if sample_variance is not None:
            var = float(sample_variance)
            if not math.isfinite(var) or var <= 0:
                raise ValueError("Sample variance must be positive.")
            sd = math.sqrt(var)
        elif sample_stdev is not None:
            sd = float(sample_stdev)
            if not math.isfinite(sd) or sd <= 0:
                raise ValueError("Sample standard deviation must be positive.")
            var = sd ** 2
        else:
            raise ValueError("Must provide either sample standard deviation or sample variance.")

    df = n - 1

    # Chi-Square Method (Normal theory)
    chi2_stat = df * var / null_var

    # P-value for Chi-square test
    if perform_test:
        if alternative == "less":
            p_val_chi2 = float(stats.chi2.cdf(chi2_stat, df))
        elif alternative == "greater":
            p_val_chi2 = float(stats.chi2.sf(chi2_stat, df))
        else:  # not_equal
            cdf_val = float(stats.chi2.cdf(chi2_stat, df))
            sf_val = float(stats.chi2.sf(chi2_stat, df))
            p_val_chi2 = float(min(1.0, 2.0 * min(cdf_val, sf_val)))
    else:
        p_val_chi2 = None

    # Confidence intervals for Chi-square
    if alternative == "less":
        # Upper bound
        q_low = float(stats.chi2.ppf(alpha, df))
        ci_sd_chi2 = (0.0, sd * math.sqrt(df / q_low) if q_low > 0 else math.inf)
        ci_var_chi2 = (0.0, df * var / q_low if q_low > 0 else math.inf)
    elif alternative == "greater":
        # Lower bound
        q_high = float(stats.chi2.ppf(1.0 - alpha, df))
        ci_sd_chi2 = (sd * math.sqrt(df / q_high) if q_high > 0 else 0.0, math.inf)
        ci_var_chi2 = (df * var / q_high if q_high > 0 else 0.0, math.inf)
    else:
        # Two-sided
        tail = alpha / 2.0
        q_low = float(stats.chi2.ppf(tail, df))
        q_high = float(stats.chi2.ppf(1.0 - tail, df))
        ci_sd_chi2 = (
            sd * math.sqrt(df / q_high) if q_high > 0 else 0.0,
            sd * math.sqrt(df / q_low) if q_low > 0 else math.inf,
        )
        ci_var_chi2 = (
            df * var / q_high if q_high > 0 else 0.0,
            df * var / q_low if q_low > 0 else math.inf,
        )

    # Bonett Method (when raw data is available)
    bonett_res = None
    if clean is not None:
        gamma = _bonett_kurtosis(clean)
        var_ln_s = max(0.0, (gamma - ((n - 3.0) / n)) / (4.0 * (n - 1.0)))
        se_ln_s = math.sqrt(var_ln_s)
        se_ln_s = max(se_ln_s, 1e-12)

        # Bonett Z statistic for ln(s) vs ln(null_sd)
        z_stat = (math.log(sd) - math.log(null_sd)) / se_ln_s
        if perform_test:
            if alternative == "less":
                p_bonett = float(stats.norm.cdf(z_stat))
            elif alternative == "greater":
                p_bonett = float(stats.norm.sf(z_stat))
            else:
                p_bonett = float(min(1.0, 2.0 * stats.norm.sf(abs(z_stat))))
        else:
            p_bonett = None

        if alternative == "less":
            z_crit = float(stats.norm.ppf(1.0 - alpha))
            b_high = sd * math.exp(z_crit * se_ln_s)
            ci_sd_bonett = (0.0, b_high)
            ci_var_bonett = (0.0, b_high ** 2)
        elif alternative == "greater":
            z_crit = float(stats.norm.ppf(1.0 - alpha))
            b_low = sd * math.exp(-z_crit * se_ln_s)
            ci_sd_bonett = (b_low, math.inf)
            ci_var_bonett = (b_low ** 2, math.inf)
        else:
            z_crit = float(stats.norm.ppf(1.0 - alpha / 2.0))
            b_low = sd * math.exp(-z_crit * se_ln_s)
            b_high = sd * math.exp(z_crit * se_ln_s)
            ci_sd_bonett = (b_low, b_high)
            ci_var_bonett = (b_low ** 2, b_high ** 2)

        bonett_res = {
            "statistic": z_stat,
            "df": 1,
            "p_value": p_bonett,
            "ci_stdev": ci_sd_bonett,
            "ci_variance": ci_var_bonett,
        }

    return {
        "name": sample_name,
        "n": n,
        "missing": missing,
        "stdev": sd,
        "variance": var,
        "null_stdev": null_sd,
        "null_variance": null_var,
        "is_variance_test": is_variance_test,
        "perform_test": perform_test,
        "confidence_level": conf,
        "alternative": alternative,
        "has_raw_data": clean is not None,
        "chi2": {
            "statistic": chi2_stat,
            "df": df,
            "p_value": p_val_chi2,
            "ci_stdev": ci_sd_chi2,
            "ci_variance": ci_var_chi2,
        },
        "bonett": bonett_res,
    }
