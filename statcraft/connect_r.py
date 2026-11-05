"""StatCraft Connect — R Translation & Worksheet Exchange Adapter.

Generates robust, readable, and executable R scripts for supported models,
handles variable names with special characters or reserved keywords, and
safely imports R predictions back into the source worksheet via observation IDs.
"""
from __future__ import annotations

import copy
import math
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .connect import ConnectedAnalysis
    from .model import Column, Worksheet


R_RESERVED = {
    "if", "else", "repeat", "while", "function", "for", "in", "next", "break",
    "TRUE", "FALSE", "NULL", "Inf", "NaN", "NA", "NA_integer_", "NA_real_",
    "NA_complex_", "NA_character_", "c", "q", "t", "D", "I"
}


def format_r_symbol(name: str) -> str:
    """Safely format a variable name as a valid R symbol, wrapping with backticks if needed."""
    if not re.match(r"^[a-zA-Z.][a-zA-Z0-9._]*$", name) or name in R_RESERVED or name.startswith(".."):
        escaped = name.replace("\\", "\\\\").replace("`", "\\`")
        return f"`{escaped}`"
    return name


def generate_r_regression_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean, standalone R code reproducing the fitted OLS regression."""
    resp_sym = format_r_symbol(connected.response_name)
    pred_syms = " + ".join(format_r_symbol(p) for p in connected.predictor_names)

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name} (Confidence: {connected.confidence * 100:g}%)",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# 1. Model Formula & Ordinary Least Squares Fit",
        f"formula_obj <- {resp_sym} ~ {pred_syms}",
        "fit <- lm(formula_obj, data = df)",
        "",
        "# 2. Summary & Analysis of Variance",
        "cat('================================================================\\n')",
        "cat('              StatCraft Connect : Fitted Model Summary           \\n')",
        "cat('================================================================\\n\\n')",
        "print(summary(fit))",
        "cat('\\n--- Analysis of Variance (ANOVA) ---\\n')",
        "print(anova(fit))",
        "",
    ]

    # Add diagnostic plot if 1 predictor, or residual diagnostics for multiple
    if len(connected.predictor_names) == 1:
        p_name = connected.predictor_names[0]
        p_sym = format_r_symbol(p_name)
        lines.extend([
            "# 3. Fitted Line & Diagnostic Plot",
            f"plot(df${p_sym}, df${resp_sym}, pch = 19, col = '#0284c7', cex = 1.1,",
            f"     main = 'Fitted Line Plot: {connected.response_name} vs {p_name}',",
            f"     xlab = '{p_name}', ylab = '{connected.response_name}')",
            "abline(fit, col = '#ef4444', lwd = 2)",
            "grid(col = '#cbd5e1', lty = 'dotted')",
            "",
        ])
    else:
        lines.extend([
            "# 3. Diagnostic Plots",
            "par(mfrow = c(1, 2))",
            "plot(fitted(fit), residuals(fit), pch = 19, col = '#0284c7',",
            "     main = 'Residuals vs Fitted', xlab = 'Fitted Values', ylab = 'Residuals')",
            "abline(h = 0, col = '#ef4444', lty = 'dashed', lwd = 2)",
            "grid(col = '#cbd5e1', lty = 'dotted')",
            "qqnorm(residuals(fit), pch = 19, col = '#059669', main = 'Normal Q-Q Plot')",
            "qqline(residuals(fit), col = '#ef4444', lwd = 2)",
            "par(mfrow = c(1, 1))",
            "",
        ])

    lines.extend([
        "# 4. Align Predictions with Source Observations via .statcraft_row_id",
        "fit_preds <- predict(fit, newdata = df)",
        f"fit_resids <- ifelse(is.na(df[[{repr(connected.response_name)}]]), NA, df[[{repr(connected.response_name)}]] - fit_preds)",
        "",
        "diagnostics <- data.frame(",
        "  Row_ID = if ('.statcraft_row_id' %in% names(df)) df$.statcraft_row_id else seq_len(nrow(df)),",
        "  Fitted = fit_preds,",
        "  Residuals = fit_resids",
        ")",
        "",
        "# 5. Export back to StatCraft Worksheet",
        "statcraft_export(diagnostics, 'Regression_Diagnostics')",
        "cat('\\n[StatCraft Connect] Diagnostics exported. Click \"Apply Predictions\" to sync.\\n')",
    ])

    return "\n".join(lines)


def generate_r_rsm_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean, standalone R code for Response Surface Methodology and Bootstrap."""
    resp_sym = format_r_symbol(connected.response_name)
    fact_syms = [format_r_symbol(p) for p in connected.predictor_names]

    # Linear & 2-factor interactions + quadratic terms
    formula_terms = [f"({ ' + '.join(fact_syms) })^2"] + [f"I({f}^2)" for f in fact_syms]
    formula_rhs = " + ".join(formula_terms)

    candidate_lines = []
    for f_orig, f_sym in zip(connected.predictor_names, fact_syms):
        candidate_lines.append(f"  {f_sym} = mean(df${f_sym}, na.rm = TRUE)")
    candidate_def = ",\n".join(candidate_lines)

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation (Response Surface & Bootstrap)",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name} (Confidence: {connected.confidence * 100:g}%)",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# 1. Model Formula & Quadratic Response Surface Fit",
        f"formula_obj <- {resp_sym} ~ {formula_rhs}",
        "fit <- lm(formula_obj, data = df)",
        "",
        "# 2. Summary & Analysis of Variance",
        "cat('================================================================\\n')",
        "cat('         Response Surface Regression Summary (OLS Fit)          \\n')",
        "cat('================================================================\\n\\n')",
        "print(summary(fit))",
        "cat('\\n--- Analysis of Variance (ANOVA) ---\\n')",
        "print(anova(fit))",
        "",
    ]

    if len(fact_syms) >= 2:
        f1, f2 = fact_syms[0], fact_syms[1]
        lines.extend([
            "# 3. Contour & Perspective Surface Plots",
            "par(mfrow = c(1, 2))",
            f"grid_x <- seq(min(df${f1}, na.rm = TRUE), max(df${f1}, na.rm = TRUE), length.out = 30)",
            f"grid_y <- seq(min(df${f2}, na.rm = TRUE), max(df${f2}, na.rm = TRUE), length.out = 30)",
            f"grid_df <- expand.grid({f1} = grid_x, {f2} = grid_y)",
        ])
        for extra in fact_syms[2:]:
            lines.append(f"grid_df${extra} <- mean(df${extra}, na.rm = TRUE)")
        lines.extend([
            "grid_z <- matrix(predict(fit, newdata = grid_df), nrow = 30, ncol = 30)",
            f"contour(grid_x, grid_y, grid_z, main = 'RSM Contour Plot', xlab = '{connected.predictor_names[0]}', ylab = '{connected.predictor_names[1]}', col = '#0284c7', lwd = 1.5)",
            f"persp(grid_x, grid_y, grid_z, main = '3D Response Surface', xlab = '{connected.predictor_names[0]}', ylab = '{connected.predictor_names[1]}', zlab = '{connected.response_name}', col = '#38bdf8', shade = 0.4, theta = 35, phi = 25)",
            "par(mfrow = c(1, 1))",
            "",
        ])

    lines.extend([
        "# 4. Bootstrap Prediction Uncertainty at Operating Point",
        "# (Fixed-X Non-Parametric Residual Resampling with 1,000 replications)",
        "candidate_point <- data.frame(",
        candidate_def,
        ")",
        "y_hat <- predict(fit, newdata = candidate_point)",
        "",
        "set.seed(42)",
        "B <- 1000",
        "resids <- residuals(fit)",
        "boot_preds <- numeric(B)",
        "for (b in seq_len(B)) {",
        "  df_boot <- df",
        f"  df_boot[[{repr(connected.response_name)}]] <- fitted(fit) + sample(resids, replace = TRUE)",
        "  b_fit <- lm(formula_obj, data = df_boot)",
        "  boot_preds[b] <- predict(b_fit, newdata = candidate_point)",
        "}",
        "ci_lower <- quantile(boot_preds, 0.025)",
        "ci_upper <- quantile(boot_preds, 0.975)",
        "cat(sprintf('\\n[StatCraft Connect] Candidate Operating Point Prediction: %.4f\\n', y_hat))",
        "cat(sprintf('[StatCraft Connect] 95%% Bootstrap Uncertainty Interval: [%.4f, %.4f]\\n\\n', ci_lower, ci_upper))",
        "",
        "# 5. Export Diagnostics back to StatCraft Worksheet",
        "fit_preds <- predict(fit, newdata = df)",
        f"fit_resids <- ifelse(is.na(df[[{repr(connected.response_name)}]]), NA, df[[{repr(connected.response_name)}]] - fit_preds)",
        "diagnostics <- data.frame(",
        "  Row_ID = if ('.statcraft_row_id' %in% names(df)) df$.statcraft_row_id else seq_len(nrow(df)),",
        "  Fitted = fit_preds,",
        "  Residuals = fit_resids",
        ")",
        "statcraft_export(diagnostics, 'RSM_Diagnostics')",
        "cat('[StatCraft Connect] RSM Diagnostics exported. Click \"Apply Predictions\" to sync.\\n')",
    ])

    return "\n".join(lines)


def import_r_predictions_to_worksheet(
    worksheet: "Worksheet",
    export_dict: Dict[str, Any],
    connected: "ConnectedAnalysis",
    table_name: str = "Regression_Diagnostics"
) -> Dict[str, Any]:
    """Safely apply exported R predictions back to the worksheet using durable row IDs.
    
    Returns:
        dict summary: {'success': bool, 'fitted_col': str, 'residuals_col': str, 'rows_updated': int, 'warning': str}
    """
    from .model import Column

    # 1. Locate exported table
    table_data = export_dict.get(table_name) or export_dict.get("RSM_Diagnostics") or export_dict.get("Regression_Diagnostics")
    if not table_data and len(export_dict) == 1:
        # Fall back to single exported table if name differs
        table_data = next(iter(export_dict.values()))

    if not table_data:
        raise ValueError(f"No exported table found in R output matching '{table_name}'.")

    # Table columns dict: col_name -> list of values
    col_map = {col.name: col.values for col in table_data}

    # Locate Fitted, Residuals, and Row_ID
    fitted_vals = None
    residuals_vals = None
    row_ids = None

    for k, vals in col_map.items():
        k_clean = k.strip().lower()
        if k_clean in ("fitted", "fitted_values", "predictions", "fit"):
            fitted_vals = vals
        elif k_clean in ("residuals", "resid", "residual"):
            residuals_vals = vals
        elif k_clean in ("row_id", ".statcraft_row_id", "row.id", "id"):
            row_ids = vals

    if fitted_vals is None and residuals_vals is None:
        raise ValueError("Exported R table does not contain 'Fitted' or 'Residuals' columns.")

    from .connect import ensure_worksheet_identities
    ensure_worksheet_identities(worksheet)
    ws_row_ids = list(worksheet.metadata.get("row_ids", []))
    n_ws = len(ws_row_ids)

    # Prepare aligned values
    aligned_fitted = [None] * n_ws
    aligned_residuals = [None] * n_ws

    rows_updated = 0
    if row_ids and len(row_ids) == len(fitted_vals or residuals_vals):
        # Match by explicit Row ID
        id_to_idx = {rid: i for i, rid in enumerate(ws_row_ids)}
        for pos, rid in enumerate(row_ids):
            target_idx = id_to_idx.get(str(rid))
            if target_idx is not None and 0 <= target_idx < n_ws:
                if fitted_vals is not None and pos < len(fitted_vals):
                    v = fitted_vals[pos]
                    aligned_fitted[target_idx] = float(v) if v is not None and not (isinstance(v, float) and math.isnan(v)) else None
                if residuals_vals is not None and pos < len(residuals_vals):
                    r = residuals_vals[pos]
                    aligned_residuals[target_idx] = float(r) if r is not None and not (isinstance(r, float) and math.isnan(r)) else None
                rows_updated += 1
    else:
        # Fall back to direct positional index alignment
        limit = min(n_ws, len(fitted_vals or residuals_vals))
        for pos in range(limit):
            if fitted_vals is not None and pos < len(fitted_vals):
                v = fitted_vals[pos]
                aligned_fitted[pos] = float(v) if v is not None and not (isinstance(v, float) and math.isnan(v)) else None
            if residuals_vals is not None and pos < len(residuals_vals):
                r = residuals_vals[pos]
                aligned_residuals[pos] = float(r) if r is not None and not (isinstance(r, float) and math.isnan(r)) else None
            rows_updated += 1

    # 3. Add or update columns in worksheet
    resp_name = connected.response_name
    fit_col_name = f"FITS_{resp_name}"
    res_col_name = f"RESI_{resp_name}"

    def update_or_add_column(name: str, values: list, kind: str = "number", col_type: str = "fitted"):
        meta = {
            "connect_provenance": {
                "analysis_id": connected.analysis_id,
                "engine": "r",
                "type": col_type,
                "source_response": resp_name,
                "imported_at": datetime.now().isoformat(timespec="seconds"),
            }
        }
        for col in worksheet.columns:
            if col.name == name:
                col.values = values
                col.kind = kind
                col.metadata.update(meta)
                return col
        # If not present, create new
        new_col = Column(name=name, kind=kind, values=values, metadata=meta)
        worksheet.columns.append(new_col)
        return new_col

    if fitted_vals is not None:
        update_or_add_column(fit_col_name, aligned_fitted, "number", "fitted_values")
    if residuals_vals is not None:
        update_or_add_column(res_col_name, aligned_residuals, "number", "residuals")

    return {
        "success": True,
        "fitted_col": fit_col_name if fitted_vals is not None else None,
        "residuals_col": res_col_name if residuals_vals is not None else None,
        "rows_updated": rows_updated,
        "rows_omitted": n_ws - rows_updated,
        "total_rows": n_ws,
    }


def _extract_coef_map(obj: Any) -> Dict[str, float]:
    """Helper to extract {term_name: estimate} from various coefficient representations."""
    raw = []
    if hasattr(obj, "coefficients"):
        raw = obj.coefficients
    elif isinstance(obj, dict):
        raw = obj.get("coefficients", [])
    elif isinstance(obj, (list, tuple)):
        raw = obj

    coef_map: Dict[str, float] = {}
    for item in raw:
        if isinstance(item, dict):
            name = item.get("name") or item.get("term", "")
            val = item.get("estimate") if item.get("estimate") is not None else (item.get("coef") or item.get("coefficient", 0.0))
            coef_map[str(name)] = float(val)
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            coef_map[str(item[0])] = float(item[1])
    return coef_map


def compare_implementations(
    connected_or_statcraft: Any,
    r_coefficients_or_result: Any,
    tolerance: float = 1e-4
) -> Dict[str, Any]:
    """Numerically compare coefficients between StatCraft and R implementations."""
    diffs = []
    max_abs_diff = 0.0

    stat_map = _extract_coef_map(connected_or_statcraft)
    r_map = _extract_coef_map(r_coefficients_or_result)

    all_keys = set(stat_map.keys()) | set(r_map.keys())
    for k in sorted(all_keys):
        s_val = stat_map.get(k)
        r_val = r_map.get(k)
        if s_val is None or r_val is None:
            diffs.append({
                "term": k,
                "statcraft": s_val,
                "r": r_val,
                "diff": None,
                "aligned": False,
                "status": "Missing in one implementation",
            })
            continue

        abs_diff = abs(s_val - r_val)
        max_abs_diff = max(max_abs_diff, abs_diff)
        aligned = abs_diff <= tolerance
        diffs.append({
            "term": k,
            "statcraft": s_val,
            "r": r_val,
            "diff": abs_diff,
            "aligned": aligned,
            "status": "Agreement" if aligned else "Discrepancy exceeds tolerance",
        })

    return {
        "aligned": all(d["aligned"] for d in diffs),
        "tolerance": tolerance,
        "max_diff": max_abs_diff,
        "comparisons": diffs,
        "differences": [d for d in diffs if not d["aligned"]],
    }
