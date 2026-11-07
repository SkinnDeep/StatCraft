"""Original continuous-predictor OLS with an intercept; vendor parity unverified.

Numerical solve/covariance use centered, scaled NumPy SVD, not native binaries.
Official API references: numpy.org/doc/stable/reference/generated/numpy.linalg.svd.html
and docs.scipy.org/doc/scipy/reference/generated/scipy.stats.{t,f}.html.
"""
import math
import numpy as np
from scipy import stats
from .engine import normalize_numeric
from .inference import _confidence, _interval


def multiple_regression(predictors, response, confidence=.95, predictor_names=None, response_name=None):
    """Fit y=b0+sum(bj*xj); predictors are columns, not rows.

    Missing values delete the whole aligned row. At least p+2 complete rows,
    varying response/predictors and numerically full column rank are required.
    Exact fits at floating-point resolution retain estimates but omit inference.
    Only unweighted continuous predictors are supported; names are display text.
    """
    confidence = _confidence(confidence)
    columns, response = [list(c) for c in predictors], list(response)
    p = len(columns)
    if p == 0:
        raise ValueError("At least one predictor is required.")
    if any(len(c) != len(response) for c in columns):
        raise ValueError("Every predictor must have the same row count as the response.")
    names = list(predictor_names) if predictor_names is not None else [f"X{i+1}" for i in range(p)]
    if len(names) != p or any(not isinstance(v, str) or not v.strip() for v in names):
        raise ValueError("Provide one nonempty display name per predictor.")
    rows, outcomes, indices = [], [], []
    for i, y in enumerate(response):
        values = [normalize_numeric(c[i]) for c in columns]
        y = normalize_numeric(y)
        if y is not None and all(v is not None for v in values):
            rows.append(values); outcomes.append(y); indices.append(i)
    n = len(rows)
    if n < p + 2:
        raise ValueError("At least predictor count + 2 complete rows are required for residual degrees of freedom.")
    x, y = np.asarray(rows, dtype=float), np.asarray(outcomes, dtype=float)
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            means = np.asarray([math.fsum(x[:, j] / n) for j in range(p)])
            mean_y = math.fsum(y / n)
            centered, dy = x - means, y - mean_y
            scales = np.max(np.abs(centered), axis=0)
            scale_y = float(np.max(np.abs(dy)))
            if np.any(scales == 0):
                raise ValueError("Constant predictors are rank deficient with the intercept.")
            if scale_y == 0:
                raise ValueError("Regression inference and R-squared require a varying response.")
            z, target = centered / scales, dy / scale_y
            u, singular, vh = np.linalg.svd(z, full_matrices=False)
            tolerance = np.finfo(float).eps * max(n, p) * singular[0]
            if singular[-1] <= tolerance:
                raise ValueError("Predictors are linearly dependent or numerically rank deficient.")
            gamma = vh.T @ ((u.T @ target) / singular)
            fitted_unit = z @ gamma
            residual_unit = target - fitted_unit
            # Limit applies only to residuals at numerical solve resolution.
            resolution = np.finfo(float).eps * max(n, p) * np.linalg.norm(target)
            exact = bool(np.linalg.norm(residual_unit) <= resolution)
            if exact:
                residual_unit = np.zeros(n)
            slopes = (gamma * scale_y) / scales
            intercept = math.fsum([mean_y] + [-float(b)*float(m) for b,m in zip(slopes, means)])
            fitted = mean_y + scale_y * fitted_unit
            residuals = scale_y * residual_unit
            error_unit = float(residual_unit @ residual_unit)
            total_unit = float(target @ target)
            ss_error = scale_y * (scale_y * error_unit)
            ss_total = scale_y * (scale_y * total_unit)
            ss_regression = max(0., ss_total - ss_error)
            df_error = n - p - 1
            ms_error, ms_regression = ss_error / df_error, ss_regression / p
            if not exact and ms_error <= 0:
                raise ValueError("Residual variation is below the supported numeric range.")
            s = math.sqrt(ms_error)
            r2 = min(1., max(0., 1. - error_unit / total_unit))
            adjusted = 1. - (1. - r2) * (n - 1) / df_error
            inverse = (vh.T / singular**2) @ vh
            slope_se = (s * np.sqrt(np.diag(inverse))) / scales
            mean_scaled = means / scales
            intercept_se = s * math.sqrt(max(0., 1/n + float(mean_scaled @ inverse @ mean_scaled)))
            vif = np.maximum(1., np.sum(z*z, axis=0) * np.diag(inverse))
            estimates = [intercept] + slopes.tolist()
            errors = [intercept_se] + slope_se.tolist()
            f = None if exact else ms_regression / ms_error

            # Leverages from centered SVD: h_i = 1/n + sum_j(u_ij^2)
            leverages = 1.0 / n + np.sum(u**2, axis=1)
            one_minus_h = np.maximum(1e-14, 1.0 - leverages)

            if exact:
                press = 0.0
                pred_r2 = 1.0
                std_resids = np.zeros(n)
                cooks_d = np.zeros(n)
                unusual_observations = []
            else:
                std_resids = residuals / (s * np.sqrt(one_minus_h))
                del_resids = residuals / one_minus_h
                cooks_d = (std_resids**2 / (p + 1)) * (leverages / one_minus_h)
                press = float(np.sum(del_resids**2))
                pred_r2 = max(0.0, min(1.0, 1.0 - press / ss_total)) if ss_total > 0 else 0.0

                # Identify unusual observations (Minitab standard criteria)
                # Cutoff for unusual X (high leverage): min(0.75, 3 * (p + 1) / n) for small n, else 3 * (p + 1) / n
                # Cutoff for large standardized residual: |std_resid| > 2.0
                leverage_cutoff = min(0.75, 3.0 * (p + 1) / n) if n < 20 else 3.0 * (p + 1) / n
                unusual_observations = []
                for idx, (orig_row, y_val, fit_val, res_val, r_val, h_val) in enumerate(
                    zip(indices, y, fitted, residuals, std_resids, leverages)
                ):
                    flags = ""
                    if abs(r_val) > 2.0:
                        flags += "R"
                    if h_val > leverage_cutoff:
                        flags += "X"
                    if flags:
                        unusual_observations.append({
                            "obs": orig_row + 1,
                            "response": float(y_val),
                            "fit": float(fit_val),
                            "resid": float(res_val),
                            "std_resid": float(r_val),
                            "leverage": float(h_val),
                            "symbol": flags,
                        })

            scalars = estimates + errors + [ss_error, ss_total, ss_regression, ms_error, ms_regression, s, r2, adjusted] + vif.tolist()
            if f is not None:
                scalars.append(f)
            if not all(math.isfinite(v) for v in scalars) or not np.all(np.isfinite(fitted)) or not np.all(np.isfinite(residuals)):
                raise ValueError("Regression arithmetic exceeds the supported numeric range.")
    except (FloatingPointError, OverflowError, np.linalg.LinAlgError) as exc:
        raise ValueError("Regression arithmetic exceeds the supported numeric range or the numerical solve failed.") from exc
    coefficients = []
    for i, (name, estimate, se) in enumerate(zip(["Constant"] + names, estimates, errors)):
        row = dict(name=name, estimate=estimate, standard_error=se,
                   vif=None if i == 0 else float(vif[i-1]))
        if exact:
            row.update(t=None, p_value=None, ci_low=None, ci_high=None)
        else:
            if se <= 0:
                raise ValueError("Coefficient uncertainty is below the supported numeric range.")
            t = estimate / se
            if not math.isfinite(t):
                raise ValueError("Coefficient statistic exceeds the supported numeric range.")
            lo, hi = _interval(estimate, se, df_error, confidence)
            row.update(t=t, p_value=float(2*stats.t.sf(abs(t), df_error)), ci_low=lo, ci_high=hi)
        coefficients.append(row)
    warnings = []
    if exact:
        warnings.append("Exact fit at floating-point resolution: residual variation is zero; coefficient tests, intervals and model F test are not reported.")
    if singular[0] / singular[-1] > 1e8:
        warnings.append("Predictors are poorly conditioned; coefficient estimates may be sensitive to rounding.")

    resp_title = response_name if (response_name and isinstance(response_name, str)) else "Y"
    eq_parts = [f"{intercept:.4g}"]
    for b, name in zip(slopes, names):
        sign = "+ " if b >= 0 else "- "
        eq_parts.append(f"{sign}{abs(b):.4g} {name}")
    regression_equation = f"{resp_title} = " + " ".join(eq_parts)

    return dict(method="Multiple linear regression (OLS, intercept included)",
                count=n, missing=len(response)-n, row_indices=indices, predictor_names=names,
                response_name=resp_title,
                regression_equation=regression_equation,
                coefficients=coefficients, r_squared=r2, adjusted_r_squared=adjusted,
                predicted_r_squared=pred_r2, press=press,
                residual_stdev=s, df_regression=p, df_error=df_error, df_total=n-1,
                ss_regression=ss_regression, ss_error=ss_error, ss_total=ss_total,
                ms_regression=ms_regression, ms_error=ms_error, f=f,
                p_value=None if exact else float(stats.f.sf(f, p, df_error)),
                fitted=fitted.tolist(), residuals=residuals.tolist(),
                standardized_residuals=std_resids.tolist() if not exact else [0.0]*n,
                leverages=leverages.tolist(),
                cooks_distance=cooks_d.tolist() if not exact else [0.0]*n,
                unusual_observations=unusual_observations,
                confidence=confidence,
                status="exact_fit" if exact else "estimated", warnings=warnings,
                assumptions="Continuous predictors and a linear mean relationship; independent, normally distributed errors of constant variance for coefficient and model inference. Rows missing any selected value are omitted together.")
