"""Type 1 Gage Study computational engine.

Follows StatCraft statistical formulas (AIAG MSA 4th Edition standard):
- Evaluates gage repeatability and bias on a single reference standard.
- Cg: Gage capability index for repeatability.
- Cgk: Gage capability index for repeatability and bias combined.
- Bias test: One-sample t-test testing H0: Bias = 0 vs H1: Bias != 0.
"""
import math
import numpy as np
from scipy import stats


DEFAULT_SETTINGS = {
    'cg_percent': 20.0,         # Percent of tolerance for calculating Cg (default 20.0%)
    'study_var': 6.0,           # Study variation multiplier (default 6.0 standard deviations)
    'resolution': None,         # Optional gage resolution
    'perform_bias_test': True,  # Perform one-sample t-test for bias
    'title': '',                # Custom chart title
    'tolerance_type': 'tolerance', # 'tolerance', 'lower', or 'upper'
    'tolerance_val': None,      # Tolerance value (USL - LSL)
    'lsl': None,                # Lower specification limit
    'usl': None,                # Upper specification limit
    'gage_info': {
        'gage_name': '',
        'date_of_study': '',
        'reported_by': '',
        'misc': ''
    }
}


def compute_type1_gage(values, reference, settings=None):
    """Compute Type 1 Gage Study statistics.

    Parameters
    ----------
    values : sequence of numeric
        Raw repeated measurement values.
    reference : float
        Known reference standard value.
    settings : dict, optional
        Analysis options and tolerance specifications.

    Returns
    -------
    dict
        Complete results dictionary including descriptive statistics,
        bias test, capability indices, and run chart series.
    """
    opts = dict(DEFAULT_SETTINGS)
    if settings:
        opts.update(settings)

    clean_values = [float(v) for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    n = len(clean_values)
    if n < 2:
        raise ValueError('Type 1 Gage Study requires at least 2 valid measurements.')

    ref = float(reference)
    if not math.isfinite(ref):
        raise ValueError('Reference value must be a finite number.')

    # Determine effective tolerance
    tol_type = opts.get('tolerance_type', 'tolerance')
    if tol_type == 'tolerance':
        tol = opts.get('tolerance_val')
        if tol is None or float(tol) <= 0:
            raise ValueError('Tolerance (USL - LSL) must be a positive number.')
        tol = float(tol)
    elif tol_type == 'lower':
        lsl = opts.get('lsl')
        if lsl is None:
            raise ValueError('Lower specification limit (LSL) must be specified.')
        lsl = float(lsl)
        if ref <= lsl:
            raise ValueError('Reference value must be strictly greater than LSL.')
        tol = 2.0 * (ref - lsl)
    elif tol_type == 'upper':
        usl = opts.get('usl')
        if usl is None:
            raise ValueError('Upper specification limit (USL) must be specified.')
        usl = float(usl)
        if ref >= usl:
            raise ValueError('Reference value must be strictly less than USL.')
        tol = 2.0 * (usl - ref)
    else:
        raise ValueError(f"Unknown tolerance specification type: '{tol_type}'.")

    # Sample statistics
    arr = np.array(clean_values, dtype=np.float64)
    mean = float(np.mean(arr))
    s = float(np.std(arr, ddof=1))
    if not math.isfinite(s) or s == 0.0 or np.all(arr == arr[0]):
        raise ValueError('Type 1 Gage Study requires nonzero, finite measurement variation. Check the measurements and instrument resolution.')

    cg_pct = float(opts.get('cg_percent', 20.0))
    if cg_pct <= 0 or cg_pct > 100:
        raise ValueError('Percent of tolerance for Cg must be between 0 and 100.')
    k_factor = cg_pct / 100.0

    study_var = float(opts.get('study_var', 6.0))
    if study_var <= 0:
        raise ValueError('Study variation must be a positive number.')

    study_variation = study_var * s
    bias = mean - ref

    # Nonzero finite variation is validated above; zero dispersion cannot
    # establish perfect capability, especially for a biased instrument.
    cg = (k_factor * tol) / (study_var * s)
    cgk_num = (0.5 * k_factor * tol) - abs(bias)
    cgk_den = 0.5 * study_var * s
    cgk = cgk_num / cgk_den
    pct_var_rep = (study_var * s) / tol * 100.0
    pct_var_rep_bias = (study_var * s + 2.0 * abs(bias)) / tol * 100.0

    # One-sample t-test for bias
    se_mean = s / math.sqrt(n) if n > 0 else 0.0
    perform_bias_test = opts.get('perform_bias_test', True)
    if perform_bias_test and s > 1e-15:
        t_stat = bias / se_mean
        df = n - 1
        p_val = 2.0 * (1.0 - stats.t.cdf(abs(t_stat), df))
    else:
        t_stat = 0.0 if s <= 1e-15 else None
        df = n - 1
        p_val = 1.0 if s <= 1e-15 and abs(bias) < 1e-15 else 0.0

    # Resolution check
    res_val = opts.get('resolution')
    pct_res = None
    if res_val is not None:
        try:
            res_val = float(res_val)
            if res_val > 0:
                pct_res = (res_val / tol) * 100.0
        except (ValueError, TypeError):
            res_val = None

    # Chart reference limits (Tolerance boundary lines)
    # Default is Reference +/- 0.5 * k_factor * tol = Reference +/- 0.10 * tol
    upper_tol_limit = ref + 0.5 * k_factor * tol
    lower_tol_limit = ref - 0.5 * k_factor * tol

    return {
        'n': n,
        'reference': ref,
        'tolerance': tol,
        'tolerance_type': tol_type,
        'lsl': opts.get('lsl'),
        'usl': opts.get('usl'),
        'mean': mean,
        'std': s,
        'study_multiplier': study_var,
        'study_variation': study_variation,
        'bias': bias,
        'se_mean': se_mean,
        't_stat': t_stat,
        'df': df,
        'p_value': p_val,
        'perform_bias_test': perform_bias_test,
        'cg_percent': cg_pct,
        'k_factor': k_factor,
        'cg': cg,
        'cgk': cgk,
        'pct_var_repeatability': pct_var_rep,
        'pct_var_rep_and_bias': pct_var_rep_bias,
        'resolution': res_val,
        'pct_resolution': pct_res,
        'upper_tol_limit': upper_tol_limit,
        'lower_tol_limit': lower_tol_limit,
        'observations': clean_values,
        'gage_info': opts.get('gage_info', {}),
        'title': opts.get('title', '')
    }
