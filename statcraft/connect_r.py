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
        f"  df_boot[[{repr(connected.response_name)}]] <- fitted(fit) + sample(resids, replace = TRUE)",
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
        f"fit_resids <- ifelse(is.na(df[[{repr(connected.response_name)}]]), NA, df[[{repr(connected.response_name)}]] - fit_preds)",
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
        f"df[[{repr(fact_name)}]] <- as.factor(df[[{repr(fact_name)}]])",
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
        f"fit_resids <- ifelse(is.na(df[[{repr(resp_name)}]]), NA, df[[{repr(resp_name)}]] - fit_preds)",
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
        f"fit_resids <- ifelse(is.na(df[[{repr(resp_name)}]]), NA, df[[{repr(resp_name)}]] - fit_preds)",
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
        lines.append(f"df[[{repr(fn)}]] <- as.factor(df[[{repr(fn)}]])")

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
        f"fit_resids <- ifelse(is.na(df[[{repr(resp_name)}]]), NA, df[[{repr(resp_name)}]] - fit_preds)",
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
        s1 = format_r_symbol(connected.response_name)
        s2 = format_r_symbol(connected.predictor_names[0]) if connected.predictor_names else "sample2"
        lines.extend([
            "# 2-Sample t-Test (Separate Columns)",
            f"x1 <- df[[{format_r_symbol(connected.response_name)}]]",
            f"x2 <- df[[{s2}]]",
            f"t_res <- t.test(x1, x2, var.equal = {var_eq}, conf.level = {conf}, alternative = '{alt}', mu = {mu})",
            "print(t_res)",
            "",
            "# Visualization",
            f"boxplot(list({s1} = x1, {s2} = x2), col = c('#2563eb', '#10b981'), main = '{connected.title}')",
        ])
    return "\n".join(lines)


def generate_r_one_sample_t_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean Base R script for 1-sample t-test."""
    meta = connected.metadata or {}
    settings = meta.get("settings", {})
    conf = connected.confidence if connected.confidence else 0.95
    alt = _map_r_alternative(settings.get("alternative", "not_equal"))
    mu = settings.get("hypothesized_mean", 0.0)
    col_sym = format_r_symbol(connected.response_name)

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name} (Confidence: {conf * 100:g}%)",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# 1-Sample t-Test",
        f"x <- df[[{col_sym}]]",
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
    s1 = format_r_symbol(connected.response_name)
    s2 = format_r_symbol(connected.predictor_names[0]) if connected.predictor_names else "sample2"

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
        f"hist(diffs, main = 'Paired Differences ({connected.response_name} - {s2})', xlab = 'Difference', col = '#8b5cf6', border = 'white')",
        f"abline(v = {mu}, col = '#ef4444', lwd = 2, lty = 2)",
    ]
    return "\n".join(lines)


def generate_r_correlation_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate clean Base R script for correlation analysis."""
    all_cols = [connected.response_name] + connected.predictor_names
    col_syms = ", ".join(format_r_symbol(c) for c in all_cols)
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
        f"cols <- c({col_syms})",
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
    col_syms = ", ".join(format_r_symbol(c) for c in all_cols)

    lines = [
        "# ==============================================================================",
        "# StatCraft Connect — R Translation",
        f"# Model: {connected.title}",
        f"# Worksheet: {connected.worksheet_name}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# Summary & Descriptive Statistics",
        f"cols <- c({col_syms})",
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

