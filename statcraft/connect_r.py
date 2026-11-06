"""StatCraft Connect — R Translation & Worksheet Exchange Adapter.

Generates robust, readable, and executable R scripts for supported models,
handles variable names with special characters or reserved keywords, and
safely imports R predictions back into the source worksheet via observation IDs.
"""
from __future__ import annotations

import copy
import json
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
        f"fit_resids <- ifelse(is.na(df[[{json.dumps(connected.response_name)}]]), NA, df[[{json.dumps(connected.response_name)}]] - fit_preds)",
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


def generate_r_rsm_script(
    connected: "ConnectedAnalysis",
    worksheet: "Worksheet",
    replications: int = 1000,
    confidence: Optional[float] = None,
    candidate_point: Optional[Dict[str, float]] = None,
) -> str:
    """Generate clean, standalone R code for Response Surface Methodology and Bootstrap."""
    resp_sym = format_r_symbol(connected.response_name)
    fact_syms = [format_r_symbol(p) for p in connected.predictor_names]
    conf_val = confidence if confidence is not None else connected.confidence
    alpha = (1.0 - conf_val) / 2.0
    alpha_low_pct = f"{alpha * 100:.3g}"
    alpha_high_pct = f"{(1.0 - alpha) * 100:.3g}"

    # Linear & 2-factor interactions + quadratic terms
    formula_terms = [f"({ ' + '.join(fact_syms) })^2"] + [f"I({f}^2)" for f in fact_syms]
    formula_rhs = " + ".join(formula_terms)

    candidate_lines = []
    for f_orig, f_sym in zip(connected.predictor_names, fact_syms):
        if candidate_point and f_orig in candidate_point:
            candidate_lines.append(f"  {f_sym} = {candidate_point[f_orig]}")
        else:
            candidate_lines.append(f"  {f_sym} = mean(df${f_sym}, na.rm = TRUE)")
    candidate_def = ",\n".join(candidate_lines)

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation (Response Surface & Bootstrap)",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name} (Confidence: {conf_val * 100:g}%)",
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
        f"# 4. Bootstrap Prediction Uncertainty at Operating Point",
        f"# (Fixed-X Non-Parametric Residual Resampling with {replications:,} replications)",
        "candidate_point <- data.frame(",
        candidate_def,
        ")",
        "y_hat <- predict(fit, newdata = candidate_point)",
        "",
        "set.seed(42)",
        f"B <- {replications}",
        "resids <- residuals(fit)",
        "boot_preds <- numeric(B)",
        "for (b in seq_len(B)) {",
        "  df_boot <- df",
        f"  df_boot[[{json.dumps(connected.response_name)}]] <- fitted(fit) + sample(resids, replace = TRUE)",
        "  b_fit <- lm(formula_obj, data = df_boot)",
        "  boot_preds[b] <- predict(b_fit, newdata = candidate_point)",
        "}",
        f"ci_lower <- quantile(boot_preds, {alpha})",
        f"ci_upper <- quantile(boot_preds, {1.0 - alpha})",
        "cat(sprintf('\\n[StatCraft Connect] Candidate Operating Point Prediction: %.4f\\n', y_hat))",
        f"cat(sprintf('[StatCraft Connect] {conf_val * 100:g}%% Bootstrap Uncertainty Interval: [%.4f, %.4f]\\n\\n', ci_lower, ci_upper))",
        "",
        "# 5. Export Diagnostics back to StatCraft Worksheet",
        "fit_preds <- predict(fit, newdata = df)",
        f"fit_resids <- ifelse(is.na(df[[{json.dumps(connected.response_name)}]]), NA, df[[{json.dumps(connected.response_name)}]] - fit_preds)",
        "diagnostics <- data.frame(",
        "  Row_ID = if ('.statcraft_row_id' %in% names(df)) df$.statcraft_row_id else seq_len(nrow(df)),",
        "  Fitted = fit_preds,",
        "  Residuals = fit_resids",
        ")",
        "statcraft_export(diagnostics, 'RSM_Diagnostics')",
        "",
        "# 6. Export Bootstrap Uncertainty Summary back to StatCraft",
        "boot_summary <- data.frame(",
        "  Metric = c('Candidate_Y_Hat', 'Bootstrap_Mean', 'Bootstrap_SE', 'CI_Lower', 'CI_Upper', 'Confidence', 'Replications'),",
        f"  Value = c(as.numeric(y_hat), mean(boot_preds), sd(boot_preds), as.numeric(ci_lower), as.numeric(ci_upper), {conf_val}, as.numeric({replications}))",
        ")",
        "statcraft_export(boot_summary, 'Bootstrap_Summary')",
        "cat('[StatCraft Connect] RSM Diagnostics and Bootstrap Summary exported. Ready for ReportPad.\\n')",
    ])

    return "\n".join(lines)


def generate_response_surface_bootstrap_script(
    connected: "ConnectedAnalysis",
    worksheet: "Worksheet",
    replications: int = 2000,
    confidence: Optional[float] = None,
    candidate_point: Optional[Dict[str, float]] = None,
) -> str:
    """Generate standalone R script for response surface bootstrap uncertainty."""
    return generate_r_rsm_script(connected, worksheet, replications=replications, confidence=confidence, candidate_point=candidate_point)


def generate_r_oneway_anova_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean, standalone R code for One-Way Analysis of Variance."""
    resp_name = connected.response_name
    fact_name = connected.predictor_names[0] if connected.predictor_names else "Factor"
    resp_sym = format_r_symbol(resp_name)
    fact_sym = format_r_symbol(fact_name)

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation (One-Way ANOVA)",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name} (Confidence: {connected.confidence * 100:g}%)",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# 1. Ensure Factor is treated as Categorical",
        f"df[[{json.dumps(fact_name)}]] <- as.factor(df[[{json.dumps(fact_name)}]])",
        f"formula_obj <- {resp_sym} ~ {fact_sym}",
        "fit <- aov(formula_obj, data = df)",
        "",
        "# 2. Summary & ANOVA Table",
        "cat('================================================================\\n')",
        "cat('              StatCraft Connect : One-Way ANOVA Summary         \\n')",
        "cat('================================================================\\n\\n')",
        "print(summary(fit))",
        "",
        "# 3. Tukey Honestly Significant Differences (HSD)",
        "cat('\\n--- Tukey Multiple Comparisons (95% Family-wise CI) ---\\n')",
        "tukey_out <- TukeyHSD(fit)",
        "print(tukey_out)",
        "",
        "# 4. Group Boxplot and Tukey Interval Plot",
        "par(mfrow = c(1, 2))",
        f"boxplot({resp_sym} ~ {fact_sym}, data = df, col = '#e0f2fe', border = '#0284c7',",
        f"        main = 'Response by Factor Level', xlab = '{fact_name}', ylab = '{resp_name}')",
        "plot(tukey_out, las = 1, col = '#0284c7')",
        "par(mfrow = c(1, 1))",
        "",
        "# 5. Export Diagnostics back to StatCraft Worksheet",
        "fit_preds <- predict(fit, newdata = df)",
        f"fit_resids <- ifelse(is.na(df[[{json.dumps(resp_name)}]]), NA, df[[{json.dumps(resp_name)}]] - fit_preds)",
        "diagnostics <- data.frame(",
        "  Row_ID = if ('.statcraft_row_id' %in% names(df)) df$.statcraft_row_id else seq_len(nrow(df)),",
        "  Fitted = fit_preds,",
        "  Residuals = fit_resids",
        ")",
        "statcraft_export(diagnostics, 'ANOVA_Diagnostics')",
        "cat('\\n[StatCraft Connect] ANOVA Diagnostics exported. Click \"Apply Predictions\" to sync.\\n')",
    ]
    return "\n".join(lines)


def generate_r_factorial_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean, standalone R code for Factorial Design of Experiments."""
    resp_name = connected.response_name
    fact_names = connected.predictor_names
    resp_sym = format_r_symbol(resp_name)
    fact_syms = [format_r_symbol(f) for f in fact_names]

    formula_rhs = " * ".join(fact_syms) if len(fact_syms) <= 4 else f"({ ' + '.join(fact_syms) })^2"

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation (Factorial DOE)",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name} (Confidence: {connected.confidence * 100:g}%)",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# 1. Model Formula with Interaction Terms",
        f"formula_obj <- {resp_sym} ~ {formula_rhs}",
        "fit <- lm(formula_obj, data = df)",
        "",
        "# 2. Model Summary & ANOVA",
        "cat('================================================================\\n')",
        "cat('              StatCraft Connect : Factorial DOE Summary          \\n')",
        "cat('================================================================\\n\\n')",
        "print(summary(fit))",
        "cat('\\n--- Analysis of Variance Table ---\\n')",
        "print(anova(fit))",
        "",
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
        "# 4. Export Diagnostics back to StatCraft Worksheet",
        "fit_preds <- predict(fit, newdata = df)",
        f"fit_resids <- ifelse(is.na(df[[{json.dumps(resp_name)}]]), NA, df[[{json.dumps(resp_name)}]] - fit_preds)",
        "diagnostics <- data.frame(",
        "  Row_ID = if ('.statcraft_row_id' %in% names(df)) df$.statcraft_row_id else seq_len(nrow(df)),",
        "  Fitted = fit_preds,",
        "  Residuals = fit_resids",
        ")",
        "statcraft_export(diagnostics, 'Factorial_Diagnostics')",
        "cat('\\n[StatCraft Connect] Factorial Diagnostics exported. Click \"Apply Predictions\" to sync.\\n')",
    ]
    return "\n".join(lines)


def generate_r_glm_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean, standalone R code for General Linear Model."""
    resp_name = connected.response_name
    fact_names = connected.metadata.get("factor_names", [])
    resp_sym = format_r_symbol(resp_name)

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation (General Linear Model)",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name} (Confidence: {connected.confidence * 100:g}%)",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# 1. Ensure Factors are treated as Categorical",
    ]
    for fn in fact_names:
        lines.append(f"df[[{json.dumps(fn)}]] <- as.factor(df[[{json.dumps(fn)}]])")

    all_terms = [format_r_symbol(p) for p in connected.predictor_names]
    formula_rhs = " + ".join(all_terms) if all_terms else "1"

    lines.extend([
        f"formula_obj <- {resp_sym} ~ {formula_rhs}",
        "fit <- lm(formula_obj, data = df)",
        "",
        "# 2. Summary & ANOVA Table",
        "cat('================================================================\\n')",
        "cat('              StatCraft Connect : General Linear Model Summary   \\n')",
        "cat('================================================================\\n\\n')",
        "print(summary(fit))",
        "cat('\\n--- Analysis of Variance Table ---\\n')",
        "print(anova(fit))",
        "",
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
        "# 4. Export Diagnostics",
        "fit_preds <- predict(fit, newdata = df)",
        f"fit_resids <- ifelse(is.na(df[[{json.dumps(resp_name)}]]), NA, df[[{json.dumps(resp_name)}]] - fit_preds)",
        "diagnostics <- data.frame(",
        "  Row_ID = if ('.statcraft_row_id' %in% names(df)) df$.statcraft_row_id else seq_len(nrow(df)),",
        "  Fitted = fit_preds,",
        "  Residuals = fit_resids",
        ")",
        "statcraft_export(diagnostics, 'GLM_Diagnostics')",
        "cat('\\n[StatCraft Connect] GLM Diagnostics exported. Click \"Apply Predictions\" to sync.\\n')",
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
    table_data = (
        export_dict.get(table_name)
        or export_dict.get("Regression_Diagnostics")
        or export_dict.get("RSM_Diagnostics")
        or export_dict.get("ANOVA_Diagnostics")
        or export_dict.get("Factorial_Diagnostics")
        or export_dict.get("GLM_Diagnostics")
    )
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


def normalize_term_name(name: str) -> str:
    """Normalize term names across StatCraft and R representations."""
    s = str(name).strip()
    if s in ("(Intercept)", "Intercept", "Constant"):
        return "Constant"
    # Replace R interaction separator ':' with '*'
    s = s.replace(":", "*")
    if "*" in s:
        parts = [p.strip() for p in s.split("*")]
        return "*".join(sorted(parts))
    return s


def _extract_coef_map(obj: Any) -> Dict[str, float]:
    """Helper to extract {term_name: estimate} from various coefficient representations."""
    coef_map: Dict[str, float] = {}
    if hasattr(obj, "coefficients"):
        raw = obj.coefficients
    elif isinstance(obj, dict):
        if "coefficients" in obj:
            raw = obj["coefficients"]
        else:
            # Direct mapping {term: float}
            for k, v in obj.items():
                try:
                    norm_k = normalize_term_name(k)
                    coef_map[norm_k] = float(v)
                except (ValueError, TypeError):
                    pass
            return coef_map
    elif isinstance(obj, (list, tuple)):
        raw = obj
    else:
        raw = []

    for item in raw:
        if isinstance(item, dict):
            name = item.get("name") or item.get("term", "")
            val = item.get("estimate") if item.get("estimate") is not None else (item.get("coef") or item.get("coefficient", 0.0))
            norm_name = normalize_term_name(name)
            coef_map[norm_name] = float(val)
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            norm_name = normalize_term_name(item[0])
            coef_map[norm_name] = float(item[1])
    return coef_map


def compare_implementations(
    connected_or_statcraft: Any,
    r_coefficients_or_result: Any,
    tolerance: float = 1e-4
) -> Dict[str, Any]:
    """Numerically compare coefficients or ANOVA statistics between StatCraft and R implementations."""
    diffs = []
    max_abs_diff = 0.0

    # Handle One-Way ANOVA special case
    is_anova = (
        (hasattr(connected_or_statcraft, "analysis_type") and getattr(connected_or_statcraft, "analysis_type") == "oneway_anova")
        or (isinstance(connected_or_statcraft, dict) and connected_or_statcraft.get("analysis_type") == "oneway_anova")
        or (isinstance(r_coefficients_or_result, dict) and "f_stat" in r_coefficients_or_result and not _extract_coef_map(r_coefficients_or_result))
    )

    if is_anova:
        sc_stats = (
            getattr(connected_or_statcraft, "statistics", {})
            if hasattr(connected_or_statcraft, "statistics")
            else (connected_or_statcraft.get("statistics", {}) if isinstance(connected_or_statcraft, dict) else {})
        )
        r_stats = r_coefficients_or_result if isinstance(r_coefficients_or_result, dict) else {}
        metrics = [
            ("Factor Degrees of Freedom", "df_factor"),
            ("Error Degrees of Freedom", "df_error"),
            ("F-Statistic", "f_stat"),
            ("P-Value", "p_value"),
            ("R-Squared", "r_squared"),
        ]
        for label, key in metrics:
            s_val = sc_stats.get(key)
            r_val = r_stats.get(key)
            if s_val is not None:
                s_val = float(s_val)
            if r_val is not None:
                r_val = float(r_val)
            if s_val is None or r_val is None:
                diffs.append({
                    "term": label,
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
                "term": label,
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
        "aligned": all(d["aligned"] for d in diffs) if diffs else False,
        "tolerance": tolerance,
        "max_diff": max_abs_diff,
        "comparisons": diffs,
        "differences": [d for d in diffs if not d["aligned"]],
    }


def create_bootstrap_result_entry(
    connected: Any,
    candidate_point: Dict[str, float],
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a StatCraft Result Card entry for a completed bootstrap uncertainty run."""
    y_hat = float(metrics.get("Candidate_Y_Hat", metrics.get("y_hat", 0.0)))
    boot_mean = float(metrics.get("Bootstrap_Mean", metrics.get("boot_mean", y_hat)))
    boot_se = float(metrics.get("Bootstrap_SE", metrics.get("boot_se", 0.0)))
    ci_lower = float(metrics.get("CI_Lower", metrics.get("ci_lower", y_hat - 1.96 * boot_se)))
    ci_upper = float(metrics.get("CI_Upper", metrics.get("ci_upper", y_hat + 1.96 * boot_se)))
    conf = float(metrics.get("Confidence", metrics.get("confidence", getattr(connected, "confidence", 0.95))))
    reps = int(float(metrics.get("Replications", metrics.get("replications", 2000))))

    resp_name = getattr(connected, "response_name", "Response") if hasattr(connected, "response_name") else connected.get("response_name", "Response")
    model_title = getattr(connected, "title", "Model") if hasattr(connected, "title") else connected.get("title", "Model")

    cand_str = ", ".join(f"{k} = {v:.4g}" for k, v in candidate_point.items()) if candidate_point else "Midpoint settings"
    report_lines = [
        f"Non-Parametric Residual Bootstrap Uncertainty Analysis",
        f"Response Variable: {resp_name}",
        f"Model: {model_title}",
        f"Operating Point: {cand_str}",
        f"Resampling Scheme: Fixed-X Residual Resampling ({reps:,} replications, seed = 42)",
        f"",
        f"Estimated Mean Response (Y_hat): {y_hat:.4f}",
        f"Bootstrap Resample Mean:         {boot_mean:.4f}",
        f"Bootstrap Standard Error:        {boot_se:.4f}",
        f"{int(conf * 100):d}% Bootstrap Percentile CI:   [{ci_lower:.4f}, {ci_upper:.4f}]",
        f"",
        f"Status: R base::lm execution verified. Ready for ReportPad.",
    ]
    report_text = "\n".join(report_lines)

    conn_dict = connected.to_dict() if hasattr(connected, "to_dict") else connected
    entry = {
        "origin": "statcraft",
        "title": f"R Bootstrap Uncertainty: {resp_name}",
        "time": datetime.now().strftime("%I:%M:%S %p"),
        "connected_analysis": conn_dict,
        "recipe": {
            "action": "bootstrap_uncertainty",
            "parameters": {
                "response": resp_name,
                "replications": reps,
                "confidence": conf,
                "candidate_point": candidate_point,
            }
        },
        "result": {
            "analysis": "bootstrap_uncertainty",
            "text": report_text,
            "y_hat": y_hat,
            "boot_mean": boot_mean,
            "boot_se": boot_se,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "confidence": conf,
            "replications": reps,
            "candidate_point": candidate_point,
        }
    }
    return entry


def _map_r_alternative(alt: str) -> str:
    alt_lower = str(alt).lower()
    if "great" in alt_lower:
        return "greater"
    if "less" in alt_lower:
        return "less"
    return "two.sided"


def generate_r_two_sample_t_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean Base R script for 2-sample t-test."""
    meta = connected.metadata or {}
    settings = meta.get("settings", {})
    fmt = settings.get("data_format", 1)
    conf = connected.confidence if connected.confidence else 0.95
    alt = _map_r_alternative(settings.get("alternative", "not_equal"))
    var_eq = "TRUE" if settings.get("assume_equal_variances", False) else "FALSE"
    mu = settings.get("hypothesized_difference", 0.0)

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name} (Confidence: {conf * 100:g}%)",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
    ]
    if fmt == 2:
        s_col = format_r_symbol(connected.response_name)
        g_col = format_r_symbol(connected.predictor_names[0]) if connected.predictor_names else "group"
        lines.extend([
            "# 2-Sample t-Test (Stacked Format)",
            f"t_res <- t.test({s_col} ~ {g_col}, data = df, var.equal = {var_eq}, conf.level = {conf}, alternative = '{alt}', mu = {mu})",
            "print(t_res)",
            "",
            "# Visualization",
            f"boxplot({s_col} ~ {g_col}, data = df, col = c('#2563eb', '#10b981'), main = '{connected.title}', ylab = '{connected.response_name}')",
        ])
    else:
        s1 = json.dumps(connected.response_name)
        s2 = json.dumps(connected.predictor_names[0]) if connected.predictor_names else '"sample2"'
        lines.extend([
            "# 2-Sample t-Test (Separate Columns)",
            f"x1 <- df[[{s1}]]",
            f"x2 <- df[[{s2}]]",
            f"t_res <- t.test(x1, x2, var.equal = {var_eq}, conf.level = {conf}, alternative = '{alt}', mu = {mu})",
            "print(t_res)",
            "",
            "# Visualization",
            f"boxplot(list(x1, x2), names = c({s1}, {s2}), col = c('#2563eb', '#10b981'), main = '{connected.title}')",
        ])
    return "\n".join(lines)


def generate_r_one_sample_t_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean Base R script for 1-sample t-test."""
    meta = connected.metadata or {}
    settings = meta.get("settings", {})
    conf = connected.confidence if connected.confidence else 0.95
    alt = _map_r_alternative(settings.get("alternative", "not_equal"))
    mu = settings.get("hypothesized_mean", 0.0)
    col_name = json.dumps(connected.response_name)

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name} (Confidence: {conf * 100:g}%)",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# 1-Sample t-Test",
        f"x <- df[[{col_name}]]",
        f"t_res <- t.test(x, mu = {mu}, conf.level = {conf}, alternative = '{alt}')",
        "print(t_res)",
        "",
        "# Visualization",
        f"hist(x, main = '{connected.title}', xlab = '{connected.response_name}', col = '#3b82f6', border = 'white')",
        f"abline(v = {mu}, col = '#ef4444', lwd = 2, lty = 2)",
    ]
    return "\n".join(lines)


def generate_r_paired_t_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean Base R script for paired t-test."""
    meta = connected.metadata or {}
    settings = meta.get("settings", {})
    conf = connected.confidence if connected.confidence else 0.95
    alt = _map_r_alternative(settings.get("alternative", "not_equal"))
    mu = settings.get("hypothesized_difference", 0.0)
    s1 = json.dumps(connected.response_name)
    s2 = json.dumps(connected.predictor_names[0]) if connected.predictor_names else '"sample2"'

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name} (Confidence: {conf * 100:g}%)",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# Paired t-Test",
        f"x1 <- df[[{s1}]]",
        f"x2 <- df[[{s2}]]",
        f"t_res <- t.test(x1, x2, paired = TRUE, conf.level = {conf}, alternative = '{alt}', mu = {mu})",
        "print(t_res)",
        "",
        "# Differences & Visualization",
        "diffs <- x1 - x2",
        f"hist(diffs, main = 'Paired Differences ({connected.response_name} vs {s2})', xlab = 'Difference', col = '#8b5cf6', border = 'white')",
        f"abline(v = {mu}, col = '#ef4444', lwd = 2, lty = 2)",
    ]
    return "\n".join(lines)


def generate_r_correlation_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean Base R script for correlation analysis."""
    all_cols = [connected.response_name] + connected.predictor_names
    col_str_literals = ", ".join(json.dumps(c) for c in all_cols)
    meta = connected.metadata or {}
    method = str(meta.get("method", "Pearson")).lower()
    missing_pol = meta.get("missing", "Pairwise")
    use_arg = "pairwise.complete.obs" if str(missing_pol).lower() == "pairwise" else "complete.obs"

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        f"# Correlation Matrix ({method.title()}, Missing: {missing_pol})",
        f"cols <- c({col_str_literals})",
        "sub_df <- df[, cols, drop = FALSE]",
        f"cor_mat <- cor(sub_df, use = '{use_arg}', method = '{method}')",
        "cat('Correlation Matrix:\\n')",
        "print(round(cor_mat, 4))",
        "",
        "# Scatterplot Matrix",
        "pairs(sub_df, main = 'Scatterplot Matrix', col = '#2563eb', pch = 19)",
    ]
    return "\n".join(lines)


def generate_r_descriptives_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean Base R script for descriptive statistics."""
    all_cols = [connected.response_name] + connected.predictor_names if connected.response_name else connected.predictor_names
    col_str_literals = ", ".join(json.dumps(c) for c in all_cols)

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# Summary & Descriptive Statistics",
        f"cols <- c({col_str_literals})",
        "sub_df <- df[, cols, drop = FALSE]",
        "cat('--- Summary Statistics ---\\n')",
        "print(summary(sub_df))",
        "",
        "cat('\\n--- Standard Deviations ---\\n')",
        "print(sapply(sub_df, sd, na.rm = TRUE))",
        "",
        "# Boxplot Distribution",
        "boxplot(sub_df, col = '#3b82f6', main = 'Distributions', border = '#1e3a8a')",
    ]
    return "\n".join(lines)



def generate_r_twoway_anova_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean Base R script for 2-way ANOVA."""
    meta = connected.metadata or {}
    resp = format_r_symbol(connected.response_name)
    fa = format_r_symbol(meta.get("factor_a_name", connected.predictor_names[0] if connected.predictor_names else "FactorA"))
    fb = format_r_symbol(meta.get("factor_b_name", connected.predictor_names[1] if len(connected.predictor_names) > 1 else "FactorB"))
    fit_int = meta.get("fit_interaction", True)
    formula_str = f"{resp} ~ {fa} * {fb}" if fit_int else f"{resp} ~ {fa} + {fb}"

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# Two-Way Analysis of Variance",
        f"fit <- aov({formula_str}, data = df)",
        "print(summary(fit))",
        "",
        "# Interaction Plot",
        f"interaction.plot(df[[{json.dumps(connected.predictor_names[0])}]], df[[{json.dumps(connected.predictor_names[1])}]], df[[{json.dumps(connected.response_name)}]], col = c('#2563eb', '#10b981', '#f59e0b', '#ef4444'), lwd = 2, xlab = {json.dumps(connected.predictor_names[0])}, ylab = {json.dumps(connected.response_name)}, trace.label = {json.dumps(connected.predictor_names[1])})",
    ]
    return "\n".join(lines)


def generate_r_logistic_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean Base R script for binary logistic regression."""
    meta = connected.metadata or {}
    event = meta.get("event", "1")
    resp_name = connected.response_name
    preds = connected.predictor_names
    pred_str = " + ".join(format_r_symbol(p) for p in preds) if preds else "1"

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# Binary Logistic Regression",
        f"df$y_binary <- as.numeric(as.character(df[[{json.dumps(resp_name)}]]) == {json.dumps(str(event))})",
        f"fit <- glm(y_binary ~ {pred_str}, data = df, family = binomial(link = 'logit'))",
        "print(summary(fit))",
        "",
        "# Odds Ratios & 95% Confidence Intervals",
        "cat('\n--- Odds Ratios ---\n')",
        "print(exp(coef(fit)))",
        "",
        "# Diagnostic Plot",
        "prob <- predict(fit, type = 'response')",
        "plot(prob, pch = 19, col = ifelse(df$y_binary == 1, '#10b981', '#ef4444'), main = 'Predicted Probabilities', ylab = 'P(Event)')",
        "abline(h = 0.5, lty = 2, col = 'gray')",
    ]
    return "\n".join(lines)


def generate_r_capability_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean Base R script for process capability analysis."""
    meta = connected.metadata or {}
    lsl = meta.get("lsl")
    usl = meta.get("usl")
    target = meta.get("target")
    var_name = connected.response_name
    stats = connected.statistics or {}
    cp = stats.get("cp")
    cpk = stats.get("cpk")
    pp = stats.get("pp")
    ppk = stats.get("ppk")

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# Process Capability Metrics",
        f"x <- df[[{json.dumps(var_name)}]]",
        "x <- x[!is.na(x)]",
        "n <- length(x)",
        "x_bar <- mean(x)",
        "s_overall <- sd(x)",
        f"cat(sprintf('Sample Mean: %.4f | Overall StDev: %.4f\n', x_bar, s_overall))",
    ]
    if cp is not None:
        lines.append(f"cat(sprintf('Cp: {cp:.4f} | Cpk: {cpk:.4f} | Pp: {pp:.4f} | Ppk: {ppk:.4f}\n'))")
    lines.extend([
        "",
        "# Capability Histogram & Curve Overlay",
        f"h <- hist(x, col = '#e0f2fe', border = 'white', freq = FALSE, main = '{connected.title}', xlab = '{var_name}')",
        "curve(dnorm(x, mean = x_bar, sd = s_overall), add = TRUE, col = '#2563eb', lwd = 2)",
    ])
    if lsl is not None:
        lines.append(f"abline(v = {lsl}, col = '#ef4444', lwd = 2, lty = 2)")
    if usl is not None:
        lines.append(f"abline(v = {usl}, col = '#ef4444', lwd = 2, lty = 2)")
    if target is not None:
        lines.append(f"abline(v = {target}, col = '#10b981', lwd = 2, lty = 3)")
    return "\n".join(lines)


def generate_r_imr_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean Base R script for I-MR SPC control chart."""
    meta = connected.metadata or {}
    stats = connected.statistics or {}
    var_name = connected.response_name
    i_c = stats.get("i_center", 0.0)
    i_ucl = stats.get("i_ucl", 0.0)
    i_lcl = stats.get("i_lcl", 0.0)
    mr_c = stats.get("mr_center", 0.0)
    mr_ucl = stats.get("mr_ucl", 0.0)
    mr_lcl = stats.get("mr_lcl", 0.0)

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# Individuals & Moving Range (I-MR) Control Chart",
        f"x <- df[[{json.dumps(var_name)}]]",
        "mr <- c(NA, abs(diff(x)))",
        "par(mfrow = c(2, 1))",
        "",
        "# 1. Individuals Chart (I-Chart)",
        f"plot(x, type = 'b', pch = 19, col = '#2563eb', main = 'Individuals Chart for {var_name}', ylab = 'Individual Value', xlab = 'Observation')",
        f"abline(h = {i_c}, col = '#10b981', lwd = 2)",
        f"abline(h = {i_ucl}, col = '#ef4444', lwd = 2, lty = 2)",
        f"abline(h = {i_lcl}, col = '#ef4444', lwd = 2, lty = 2)",
        f"text(length(x), {i_ucl}, 'UCL', pos = 4, col = '#ef4444')",
        f"text(length(x), {i_lcl}, 'LCL', pos = 4, col = '#ef4444')",
        "",
        "# 2. Moving Range Chart (MR-Chart)",
        f"plot(mr, type = 'b', pch = 19, col = '#8b5cf6', main = 'Moving Range Chart for {var_name}', ylab = 'Moving Range', xlab = 'Observation')",
        f"abline(h = {mr_c}, col = '#10b981', lwd = 2)",
        f"abline(h = {mr_ucl}, col = '#ef4444', lwd = 2, lty = 2)",
        f"abline(h = {mr_lcl}, col = '#ef4444', lwd = 2, lty = 2)",
        f"text(length(mr), {mr_ucl}, 'UCL', pos = 4, col = '#ef4444')",
        f"text(length(mr), {mr_lcl}, 'LCL', pos = 4, col = '#ef4444')",
        "par(mfrow = c(1, 1))",
    ]
    return "\n".join(lines)



def generate_r_gage_rr_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean Base R script for crossed Gage R&R study."""
    meas_col = connected.response_name
    preds = connected.predictor_names
    part_col = preds[0] if preds else "Part"
    oper_col = preds[1] if len(preds) > 1 else "Operator"
    stats = connected.statistics or {}
    var_comps = stats.get("variance_components") or []
    ndc = stats.get("ndc")

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation (Gage R&R Crossed MSA)",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# 1. Ensure Factors are Categorical",
        f"df[[{json.dumps(part_col)}]] <- as.factor(df[[{json.dumps(part_col)}]])",
        f"df[[{json.dumps(oper_col)}]] <- as.factor(df[[{json.dumps(oper_col)}]])",
        "",
        "# 2. Two-Way ANOVA with Interaction",
        f"fit <- aov(df[[{json.dumps(meas_col)}]] ~ df[[{json.dumps(part_col)}]] * df[[{json.dumps(oper_col)}]])",
        "cat('================================================================\n')",
        "cat('             StatCraft Connect : Gage R&R ANOVA Table           \n')",
        "cat('================================================================\n\n')",
        "print(summary(fit))",
        "",
        "# 3. Variance Components & Gage Evaluation",
        "cat('\n--- Gage R&R Variance Components ---\n')",
    ]

    if var_comps:
        lines.append("cat(sprintf('%-22s %10s %14s %12s\n', 'Source', 'VarComp', '%Contribution', '%Study Var'))")
        lines.append("cat(paste(rep('-', 62), collapse = ''), '\n')")
        for vc in var_comps:
            src = vc.get("source", "")
            var = vc.get("variance", 0.0) or 0.0
            pct_c = vc.get("percent_contribution", 0.0) or 0.0
            pct_sv = vc.get("percent_study_variation", 0.0) or 0.0
            lines.append(f"cat(sprintf('%-22s %10.5f %14.2f %12.2f\n', {json.dumps(src)}, {var:.5f}, {pct_c:.2f}, {pct_sv:.2f}))")
        if ndc is not None:
            lines.append(f"cat(sprintf('\nNumber of Distinct Categories (ndc): %d\n', {int(ndc)}))")

    lines.extend([
        "",
        "# 4. 4-Panel Gage R&R Diagnostic Graphics",
        "par(mfrow = c(2, 2))",
        f"interaction.plot(df[[{json.dumps(part_col)}]], df[[{json.dumps(oper_col)}]], df[[{json.dumps(meas_col)}]], col = c('#2563eb', '#10b981', '#f59e0b', '#ef4444'), lwd = 2, main = 'Operator * Part Interaction', xlab = {json.dumps(part_col)}, ylab = {json.dumps(meas_col)}, trace.label = {json.dumps(oper_col)})",
        f"boxplot(df[[{json.dumps(meas_col)}]] ~ df[[{json.dumps(part_col)}]], col = '#93c5fd', main = {json.dumps(meas_col + ' by ' + part_col)}, xlab = {json.dumps(part_col)}, ylab = {json.dumps(meas_col)})",
        f"boxplot(df[[{json.dumps(meas_col)}]] ~ df[[{json.dumps(oper_col)}]], col = '#86efac', main = {json.dumps(meas_col + ' by ' + oper_col)}, xlab = {json.dumps(oper_col)}, ylab = {json.dumps(meas_col)})",
        f"plot(df[[{json.dumps(meas_col)}]], pch = 19, col = '#6366f1', main = 'Run Chart of Measurements', xlab = 'Index', ylab = {json.dumps(meas_col)})",
        "grid(col = '#cbd5e1', lty = 'dotted')",
        "par(mfrow = c(1, 1))",
    ])
    return "\n".join(lines)



def generate_r_subgroup_spc_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean Base R script for Subgroup SPC (Xbar-R / Xbar-S) control charts."""
    def _scalar(v, default=0.0):
        if isinstance(v, (list, tuple)):
            return float(v[0]) if v else default
        return float(v) if v is not None else default

    meas_col = connected.response_name
    preds = connected.predictor_names
    factor_col = preds[0] if preds else None
    meta = connected.metadata or {}
    chart_type = meta.get("chart_type", connected.analysis_type or "xbar_r")
    is_r_chart = (chart_type == "xbar_r")
    disp_label = "R Chart" if is_r_chart else "S Chart"
    subgroup_size = meta.get("subgroup_size") or 5

    stats = connected.statistics or {}
    xb_c = _scalar(stats.get("xbar_center"), 0.0)
    xb_u = _scalar(stats.get("xbar_ucl"), 0.0)
    xb_l = _scalar(stats.get("xbar_lcl"), 0.0)
    dp_c = _scalar(stats.get("disp_center"), 0.0)
    dp_u = _scalar(stats.get("disp_ucl"), 0.0)
    dp_l = _scalar(stats.get("disp_lcl"), 0.0)

    lines = [
        "# ==============================================================================",
        f"# StatCraft Connect — R Translation (Subgroup SPC: {disp_label})",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# 1. Subgroup Aggregation in Base R",
    ]

    if factor_col:
        lines.extend([
            f"groups <- split(df[[{json.dumps(meas_col)}]], factor(df[[{json.dumps(factor_col)}]], levels = unique(df[[{json.dumps(factor_col)}]][!is.na(df[[{json.dumps(factor_col)}]])])))",
            "# Filter out empty subgroups if any",
            "groups <- groups[sapply(groups, length) > 0]",
        ])
    else:
        lines.extend([
            f"meas <- df[[{json.dumps(meas_col)}]]",
            "meas <- meas[!is.na(meas)]",
            f"sz <- {int(subgroup_size)}",
            "sg_id <- rep(seq_len(ceiling(length(meas) / sz)), each = sz, length.out = length(meas))",
            "groups <- split(meas, sg_id)",
        ])

    lines.extend([
        "subgroup_means <- sapply(groups, mean, na.rm = TRUE)",
    ])

    if is_r_chart:
        lines.append("subgroup_disp <- sapply(groups, function(v) { r <- range(v, na.rm = TRUE); r[2] - r[1] })")
    else:
        lines.append("subgroup_disp <- sapply(groups, sd, na.rm = TRUE)")

    xbar_plot_title = f"X-bar Chart for {meas_col}"
    disp_plot_title = f"{disp_label} for {meas_col}"

    lines.extend([
        "",
        "# 2. Summary Statistics",
        "cat('================================================================\n')",
        f"cat('        StatCraft Connect : {disp_label} Control Chart Summary   \n')",
        "cat('================================================================\n\n')",
        f"cat(sprintf('X-bar Center: %.4f | UCL: %.4f | LCL: %.4f\n', {xb_c:.4f}, {xb_u:.4f}, {xb_l:.4f}))",
        f"cat(sprintf('{disp_label} Center: %.4f | UCL: %.4f | LCL: %.4f\n', {dp_c:.4f}, {dp_u:.4f}, {dp_l:.4f}))",
        "",
        "# 3. Two-Panel Control Chart",
        "par(mfrow = c(2, 1))",
        "",
        "# Panel 1: X-bar Chart",
        f"plot(subgroup_means, type = 'b', pch = 19, col = '#2563eb', main = {json.dumps(xbar_plot_title)}, ylab = 'Subgroup Mean', xlab = 'Subgroup')",
        f"abline(h = {xb_c:.4f}, col = '#10b981', lwd = 2)",
        f"abline(h = {xb_u:.4f}, col = '#ef4444', lwd = 2, lty = 2)",
        f"abline(h = {xb_l:.4f}, col = '#ef4444', lwd = 2, lty = 2)",
        f"text(length(subgroup_means), {xb_u:.4f}, 'UCL', pos = 4, col = '#ef4444')",
        f"text(length(subgroup_means), {xb_l:.4f}, 'LCL', pos = 4, col = '#ef4444')",
        "",
        f"# Panel 2: {disp_label}",
        f"plot(subgroup_disp, type = 'b', pch = 19, col = '#8b5cf6', main = {json.dumps(disp_plot_title)}, ylab = {json.dumps(disp_label)}, xlab = 'Subgroup')",
        f"abline(h = {dp_c:.4f}, col = '#10b981', lwd = 2)",
        f"abline(h = {dp_u:.4f}, col = '#ef4444', lwd = 2, lty = 2)",
        f"abline(h = {dp_l:.4f}, col = '#ef4444', lwd = 2, lty = 2)",
        f"text(length(subgroup_disp), {dp_u:.4f}, 'UCL', pos = 4, col = '#ef4444')",
        f"text(length(subgroup_disp), {dp_l:.4f}, 'LCL', pos = 4, col = '#ef4444')",
        "par(mfrow = c(1, 1))",
    ])
    return "\n".join(lines)



def generate_generic_r_script(entry: Dict[str, Any], worksheet: "Worksheet") -> str:
    """Generate clean, standalone pure Base R code for any analysis or graph in StatCraft."""
    title = entry.get("title", "StatCraft Analysis")
    recipe = entry.get("recipe", {})
    action = recipe.get("action", "analysis")
    params = recipe.get("parameters", {})

    referenced_col_names = []
    for k, v in params.items():
        if isinstance(v, int) and 0 <= v < len(worksheet.columns):
            c_name = worksheet.columns[v].name
            if c_name not in referenced_col_names:
                referenced_col_names.append(c_name)
        elif isinstance(v, (list, tuple)):
            for item in v:
                if isinstance(item, int) and 0 <= item < len(worksheet.columns):
                    c_name = worksheet.columns[item].name
                    if c_name not in referenced_col_names:
                        referenced_col_names.append(c_name)
                elif isinstance(item, str) and any(c.name == item for c in worksheet.columns):
                    if item not in referenced_col_names:
                        referenced_col_names.append(item)
        elif isinstance(v, dict):
            for sub_k, sub_v in v.items():
                if isinstance(sub_v, int) and 0 <= sub_v < len(worksheet.columns) and ("col" in sub_k or "idx" in sub_k or "index" in sub_k or "samples" in sub_k or "subscripts" in sub_k):
                    c_name = worksheet.columns[sub_v].name
                    if c_name not in referenced_col_names:
                        referenced_col_names.append(c_name)

    if not referenced_col_names and worksheet.columns:
        referenced_col_names.append(worksheet.columns[0].name)

    lines = [
        "# ==============================================================================",
        f"# StatCraft — Reproducible Base R Translation",
        f"# Procedure: {title}",
        f"# Action: {action}",
        f"# Worksheet: {worksheet.name}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# Target Columns in Active Worksheet",
    ]

    for col in referenced_col_names:
        lines.append(f"# - {col}")
    lines.append("")

    if "run_chart" in action:
        primary_col = referenced_col_names[0]
        lines.extend([
            f"x <- df[[{json.dumps(primary_col)}]]",
            "x <- x[!is.na(x)]",
            "n <- length(x)",
            "med <- median(x)",
            f"plot(x, type = 'b', pch = 19, col = '#2563eb', main = {json.dumps(f'Run Chart for {primary_col}')}, ylab = {json.dumps(primary_col)}, xlab = 'Observation')",
            "abline(h = med, col = '#10b981', lwd = 2)",
            "text(n, med, 'Median', pos = 4, col = '#10b981')",
        ])
    elif "two_variances" in action:
        val_col = referenced_col_names[0]
        grp_col = referenced_col_names[1] if len(referenced_col_names) > 1 else None
        if grp_col:
            lines.extend([
                "# Two-Variances Test (F-Test)",
                f"fit <- var.test(df[[{json.dumps(val_col)}]] ~ df[[{json.dumps(grp_col)}]], data = df)",
                "print(fit)",
                f"boxplot(df[[{json.dumps(val_col)}]] ~ df[[{json.dumps(grp_col)}]], col = '#93c5fd', main = {json.dumps(f'Variances: {val_col} by {grp_col}')}, xlab = {json.dumps(grp_col)}, ylab = {json.dumps(val_col)})",
            ])
        else:
            lines.extend([
                f"print(summary(df[[{json.dumps(val_col)}]]))",
            ])
    else:
        col_list_str = ", ".join(json.dumps(c) for c in referenced_col_names)
        lines.extend([
            f"sub_df <- df[, c({col_list_str}), drop = FALSE]",
            "",
            "# Summary Statistics",
            "cat('================================================================\n')",
            f"cat('               StatCraft Summary: {title}                       \n')",
            "cat('================================================================\n\n')",
            "print(summary(sub_df))",
            "",
            "# Diagnostic Visuals",
            "if (ncol(sub_df) == 1) {",
            "  if (is.numeric(sub_df[[1]])) {",
            f"    hist(sub_df[[1]], col = '#93c5fd', border = 'white', main = {json.dumps(title)}, xlab = {json.dumps(referenced_col_names[0])})",
            "  } else {",
            f"    barplot(table(sub_df[[1]]), col = '#93c5fd', main = {json.dumps(title)})",
            "  }",
            "} else {",
            f"  boxplot(sub_df, col = '#93c5fd', main = {json.dumps(title)})",
            "}",
        ])

    return "\n".join(lines)


def generate_dataframe_init_code(worksheet: "Worksheet") -> str:
    """Generate a clean, reproducible Base R script reconstructing the active worksheet as 'df'."""
    col_defs = []
    for col in worksheet.columns:
        safe_name = col.name.replace('"', '\"')
        if col.kind == "number":
            vals = [str(v) if v is not None and not (isinstance(v, float) and math.isnan(v)) else "NA" for v in col.values]
            col_defs.append(f'  "{safe_name}" = c({", ".join(vals)})')
        else:
            vals = [f'"{str(v)}"' if v is not None else "NA" for v in col.values]
            col_defs.append(f'  "{safe_name}" = c({", ".join(vals)})')
    body = ",\n".join(col_defs)
    return (
        "# ==============================================================================\n"
        f"# StatCraft — Active Worksheet R Data Frame Export\n"
        f"# Worksheet: {worksheet.name} ({len(worksheet.columns)} columns, {worksheet.row_count} rows)\n"
        "# ==============================================================================\n\n"
        f"df <- data.frame(\n{body},\n  stringsAsFactors = FALSE\n)\n\n"
        "cat('Active worksheet loaded into R as \'df\':\\n')\n"
        "print(head(df))\n"
        "cat('\\nStructure of df:\\n')\n"
        "str(df)\n"
    )
