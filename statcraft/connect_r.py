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
    deg = connected.metadata.get("degree", 1) if connected.metadata else 1
    if connected.analysis_type == "fitted_line_plot":
        p0 = format_r_symbol(connected.predictor_names[0]) if connected.predictor_names else "X"
        if deg == 2:
            pred_syms = f"{p0} + I({p0}^2)"
        elif deg == 3:
            pred_syms = f"{p0} + I({p0}^2) + I({p0}^3)"
        else:
            pred_syms = p0
    else:
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

    # 3. Model Summary (Minitab Standard: S, R-sq, R-sq(adj), R-sq(pred), PRESS)
    lines.extend([
        "cat('\\n================================================================\\n')",
        "cat('               Model Summary (Minitab Standard)                 \\n')",
        "cat('================================================================\\n')",
        "s_res <- summary(fit)$sigma",
        "r2 <- summary(fit)$r.squared",
        "r2_adj <- summary(fit)$adj.r.squared",
        "h_diag <- hatvalues(fit)",
        "e_res <- resid(fit)",
        "press_stat <- sum((e_res / (1 - h_diag))^2)",
        f"y_orig <- df[[{json.dumps(connected.response_name)}]]",
        "ss_tot <- sum((y_orig - mean(y_orig, na.rm = TRUE))^2, na.rm = TRUE)",
        "r2_pred <- max(0, 1 - press_stat / ss_tot)",
        "cat(sprintf('S: %.4f   R-sq: %.2f%%   R-sq(adj): %.2f%%   R-sq(pred): %.2f%%\\nPRESS: %.4f\\n\\n', s_res, r2 * 100, r2_adj * 100, r2_pred * 100, press_stat))",
        "",
        "# 4. Fits and Diagnostics for Unusual Observations (Minitab Standard: R and X)",
        "cat('--- Fits and Diagnostics for Unusual Observations ---\\n')",
        "p_terms <- length(coef(fit))",
        "n_obs <- length(e_res)",
        "std_res <- rstandard(fit)",
        "unusual_idx <- which(abs(std_res) > 2.0 | h_diag > (3.0 * p_terms / n_obs))",
        "if (length(unusual_idx) > 0) {",
        "  syms <- ifelse(abs(std_res[unusual_idx]) > 2.0 & h_diag[unusual_idx] > (3.0 * p_terms / n_obs), 'RX',",
        "          ifelse(abs(std_res[unusual_idx]) > 2.0, 'R', 'X'))",
        "  unusual_df <- data.frame(",
        "    Obs = unusual_idx,",
        "    Response = y_orig[unusual_idx],",
        "    Fit = fitted(fit)[unusual_idx],",
        "    Resid = e_res[unusual_idx],",
        "    StdResid = std_res[unusual_idx],",
        "    Leverage = h_diag[unusual_idx],",
        "    Symbol = syms,",
        "    check.names = FALSE",
        "  )",
        "  print(unusual_df)",
        "  cat('\\nR: Large residual (|Std Resid| > 2)\\n')",
        "  cat('X: High leverage (Leverage > 3*p/n)\\n\\n')",
        "} else {",
        "  cat('No unusual observations detected.\\n\\n')",
        "}",
    ])
    if connected.analysis_type == "fitted_line_plot":
        p0 = format_r_symbol(connected.predictor_names[0]) if connected.predictor_names else "X"
        lines.extend([
            "cat('Generating Fitted Line Plot...\\n')",
            f"x_vals <- df[[{json.dumps(connected.predictor_names[0])}]]",
            f"y_vals <- df[[{json.dumps(connected.response_name)}]]",
            "plot(x_vals, y_vals, pch = 19, col = '#2563eb',",
            f"     xlab = {json.dumps(connected.predictor_names[0])}, ylab = {json.dumps(connected.response_name)}, main = 'Fitted Line Plot')",
            "new_x <- seq(min(x_vals, na.rm = TRUE), max(x_vals, na.rm = TRUE), length.out = 120)",
            f"nd <- data.frame({p0} = new_x)",
            f"ci_band <- predict(fit, newdata = nd, interval = 'confidence', level = {connected.confidence})",
            f"pi_band <- predict(fit, newdata = nd, interval = 'prediction', level = {connected.confidence})",
            "lines(new_x, ci_band[, 'fit'], col = '#dc2626', lwd = 2)",
            "lines(new_x, ci_band[, 'lwr'], col = '#0284c7', lty = 2, lwd = 1.5)",
            "lines(new_x, ci_band[, 'upr'], col = '#0284c7', lty = 2, lwd = 1.5)",
            "lines(new_x, pi_band[, 'lwr'], col = '#7c3aed', lty = 2, lwd = 1.5)",
            "lines(new_x, pi_band[, 'upr'], col = '#7c3aed', lty = 2, lwd = 1.5)",
            f"legend('topright', legend = c('Fit', sprintf('%.0f%% CI', {connected.confidence * 100}), sprintf('%.0f%% PI', {connected.confidence * 100})),",
            "       col = c('#dc2626', '#0284c7', '#7c3aed'), lty = c(1, 2, 2), lwd = c(2, 1.5, 1.5), bty = 'n')",
            "",
        ])
    lines.extend([
        "# 5. Minitab-Parity 4-in-1 Residual Diagnostic Plots",
        "cat('Generating 4-in-1 Residual Diagnostic Plots...\\n')",
        "par(mfrow = c(2, 2))",
        "qqnorm(std_res, pch = 19, col = '#0284c7', main = 'Normal Probability Plot')",
        "qqline(std_res, col = '#dc2626', lwd = 2)",
        "plot(fitted(fit), std_res, pch = 19, col = '#0284c7',",
        "     main = 'Versus Fits', xlab = 'Fitted Values', ylab = 'Standardized Residuals')",
        "abline(h = 0, col = '#ef4444', lty = 'dashed', lwd = 1.5)",
        "abline(h = c(-2, 2), col = '#fca5a5', lty = 'dotted')",
        "hist(std_res, breaks = 'FD', col = '#93c5fd', border = '#1d4ed8',",
        "     main = 'Histogram of Residuals', xlab = 'Standardized Residual')",
        "plot(seq_along(std_res), std_res, type = 'o', pch = 19, col = '#0284c7',",
        "     main = 'Versus Order', xlab = 'Observation Order', ylab = 'Standardized Residuals')",
        "abline(h = 0, col = '#ef4444', lty = 'dashed', lwd = 1.5)",
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
        "if (exists('statcraft_export', mode = 'function')) statcraft_export(diagnostics, 'Regression_Diagnostics')",
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
        "if (exists('statcraft_export', mode = 'function')) statcraft_export(diagnostics, 'RSM_Diagnostics')",
        "",
        "# 6. Export Bootstrap Uncertainty Summary back to StatCraft",
        "boot_summary <- data.frame(",
        "  Metric = c('Candidate_Y_Hat', 'Bootstrap_Mean', 'Bootstrap_SE', 'CI_Lower', 'CI_Upper', 'Confidence', 'Replications'),",
        f"  Value = c(as.numeric(y_hat), mean(boot_preds), sd(boot_preds), as.numeric(ci_lower), as.numeric(ci_upper), {conf_val}, as.numeric({replications}))",
        ")",
        "if (exists('statcraft_export', mode = 'function')) statcraft_export(boot_summary, 'Bootstrap_Summary')",
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
        "if (exists('statcraft_export', mode = 'function')) statcraft_export(diagnostics, 'ANOVA_Diagnostics')",
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
        "if (exists('statcraft_export', mode = 'function')) statcraft_export(diagnostics, 'Factorial_Diagnostics')",
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
        "if (exists('statcraft_export', mode = 'function')) statcraft_export(diagnostics, 'GLM_Diagnostics')",
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
    """Generate comprehensive Base R script for descriptive statistics with complete statistical calculations and diagnostics."""
    all_cols = [connected.response_name] + connected.predictor_names if connected.response_name else connected.predictor_names
    col_str_literals = ", ".join(json.dumps(c) for c in all_cols)

    lines = [
        "# ==============================================================================",
        "# StatCraft — Reproducible Base R Translation",
        f"# Procedure: {connected.title}",
        f"# Worksheet: {connected.worksheet_name}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# Target Variables for Descriptive Analysis",
        f"cols <- c({col_str_literals})",
        "sub_df <- df[, cols, drop = FALSE]",
        "",
        "# ------------------------------------------------------------------------------",
        "# 1. Dynamic Statistical Calculations (Minitab-Equivalent Engine)",
        "# ------------------------------------------------------------------------------",
        "calc_descriptives <- function(x, name) {",
        "  x_clean <- as.numeric(x[!is.na(x)])",
        "  n <- length(x_clean)",
        "  n_miss <- sum(is.na(x))",
        "  if (n == 0) return(NULL)",
        "  ",
        "  m <- mean(x_clean)",
        "  s <- sd(x_clean)",
        "  v <- var(x_clean)",
        "  se <- s / sqrt(n)",
        "  cv <- if (abs(m) > 1e-12) (s / m) * 100 else NA",
        "  ",
        "  # Minitab empirical percentile definition (type 6: Weibull standard)",
        "  q1 <- as.numeric(quantile(x_clean, 0.25, type = 6))",
        "  med <- median(x_clean)",
        "  q3 <- as.numeric(quantile(x_clean, 0.75, type = 6))",
        "  iqr_val <- q3 - q1",
        "  min_val <- min(x_clean)",
        "  max_val <- max(x_clean)",
        "  ",
        "  # Sample Skewness & Excess Kurtosis",
        "  m3 <- sum((x_clean - m)^3) / n",
        "  skew <- if (s > 0) m3 / (s^3) else 0",
        "  m4 <- sum((x_clean - m)^4) / n",
        "  kurt <- if (s > 0) (m4 / (s^4)) - 3 else 0",
        "  ",
        "  # Normality Assessment (Shapiro-Wilk)",
        "  norm_test <- if (n >= 3 && n <= 5000) shapiro.test(x_clean) else list(statistic = NA, p.value = NA)",
        "  ",
        "  list(",
        "    Variable = name,",
        "    N = n,",
        "    N_Star = n_miss,",
        "    Mean = m,",
        "    SE_Mean = se,",
        "    StDev = s,",
        "    Variance = v,",
        "    CoeffVar = cv,",
        "    Minimum = min_val,",
        "    Q1 = q1,",
        "    Median = med,",
        "    Q3 = q3,",
        "    Maximum = max_val,",
        "    IQR = iqr_val,",
        "    Skewness = skew,",
        "    Kurtosis = kurt,",
        "    Shapiro_W = unname(norm_test$statistic),",
        "    P_Value = norm_test$p.value",
        "  )",
        "}",
        "",
        "# Execute calculations for all selected columns",
        "results_list <- lapply(cols, function(cn) calc_descriptives(df[[cn]], cn))",
        "results_list <- results_list[!sapply(results_list, is.null)]",
        "",
        "cat('================================================================================\n')",
        "cat('                 StatCraft: Descriptive Statistics Report                       \n')",
        "cat('================================================================================\n\n')",
        "",
        "for (res in results_list) {",
        "  cat(sprintf('Variable: %s\n', res$Variable))",
        "  cat(sprintf('  Total Count (N):    %d\n', res$N))",
        "  cat(sprintf('  Missing Count (N*): %d\n', res$N_Star))",
        "  cat(sprintf('  Mean:               %.4f\n', res$Mean))",
        "  cat(sprintf('  SE Mean:            %.4f\n', res$SE_Mean))",
        "  cat(sprintf('  Standard Deviation: %.4f\n', res$StDev))",
        "  cat(sprintf('  Variance:           %.4f\n', res$Variance))",
        "  cat(sprintf('  Coeff of Variation: %.2f%%\n', res$CoeffVar))",
        "  cat(sprintf('  Minimum:            %.4f\n', res$Minimum))",
        "  cat(sprintf('  First Quartile Q1:  %.4f\n', res$Q1))",
        "  cat(sprintf('  Median:             %.4f\n', res$Median))",
        "  cat(sprintf('  Third Quartile Q3:  %.4f\n', res$Q3))",
        "  cat(sprintf('  Maximum:            %.4f\n', res$Maximum))",
        "  cat(sprintf('  Interquartile Range:%.4f\n', res$IQR))",
        "  cat(sprintf('  Skewness:           %.4f\n', res$Skewness))",
        "  cat(sprintf('  Excess Kurtosis:    %.4f\n', res$Kurtosis))",
        "  if (!is.na(res$P_Value)) {",
        "    cat(sprintf('  Normality Test (p): %.5f %s\n', res$P_Value, if (res$P_Value < 0.05) '(Non-normal at alpha=0.05)' else '(Normal at alpha=0.05)'))",
        "  }",
        "  cat('--------------------------------------------------------------------------------\n')",
        "}",
        "",
        "cat('\n--- Base R Summary ---\n')",
        "print(summary(sub_df))",
        "",
        "# ------------------------------------------------------------------------------",
        "# 2. Graphical Diagnostics & Visualizations",
        "# ------------------------------------------------------------------------------",
        "for (cn in cols) {",
        "  val <- as.numeric(df[[cn]])",
        "  val_clean <- val[!is.na(val)]",
        "  if (length(val_clean) >= 2) {",
        "    old_par <- par(mfrow = c(2, 2), mar = c(4, 4, 3, 2))",
        "    ",
        "    # 1. Histogram with Fitted Normal Distribution Curve",
        "    h <- hist(val_clean, col = '#93c5fd', border = '#1e3a8a',",
        "              main = paste('Histogram of', cn), xlab = cn, prob = TRUE)",
        "    x_seq <- seq(min(val_clean), max(val_clean), length.out = 200)",
        "    lines(x_seq, dnorm(x_seq, mean = mean(val_clean), sd = sd(val_clean)), col = '#dc2626', lwd = 2)",
        "    abline(v = mean(val_clean), col = '#2563eb', lwd = 2, lty = 2)",
        "    abline(v = median(val_clean), col = '#16a34a', lwd = 2, lty = 3)",
        "    legend('topright', legend = c('Normal Fit', 'Mean', 'Median'), col = c('#dc2626', '#2563eb', '#16a34a'), lty = c(1, 2, 3), lwd = 2, bty = 'n', cex = 0.8)",
        "    ",
        "    # 2. Individual Value Plot",
        "    stripchart(val_clean, method = 'jitter', pch = 19, col = '#2563eb',",
        "               main = paste('Individual Values:', cn), xlab = cn)",
        "    abline(v = mean(val_clean), col = '#dc2626', lwd = 2, lty = 2)",
        "    ",
        "    # 3. Boxplot Distribution with Outliers and Mean",
        "    boxplot(val_clean, col = '#bfdbfe', border = '#1e3a8a', horizontal = TRUE,",
        "            main = paste('Boxplot of', cn), xlab = cn)",
        "    points(mean(val_clean), 1, pch = 18, col = '#dc2626', cex = 1.5)",
        "    ",
        "    # 4. Normal Probability Plot (Q-Q Plot)",
        "    qqnorm(val_clean, main = paste('Normal Q-Q Plot of', cn), pch = 19, col = '#2563eb')",
        "    qqline(val_clean, col = '#dc2626', lwd = 2)",
        "    ",
        "    par(old_par)",
        "  }",
        "}",
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


def generate_r_histogram_script(
    column_names: List[str],
    variant: str = "fit",
    bins: Optional[int] = None,
) -> str:
    """Generate Base R script for publication-grade Histogram with Fitted Normal Distribution."""
    cols_quoted = ", ".join(json.dumps(c) for c in column_names)
    breaks_arg = f"breaks = {bins}" if bins else 'breaks = "FD"'
    lines = [
        "# ==============================================================================",
        "# StatCraft : Histogram with Fitted Normal Distribution",
        "# ==============================================================================",
        f"cols <- c({cols_quoted})",
        "",
        "for (cn in cols) {",
        "  x <- df[[cn]]",
        "  x_clean <- x[!is.na(x)]",
        "  n <- length(x_clean)",
        "  m <- mean(x_clean)",
        "  s <- sd(x_clean)",
        "",
        "  # Histogram with fitted normal curve",
        f"  h <- hist(x_clean, {breaks_arg}, col = '#38bdf8', border = 'white', prob = TRUE,",
        "            main = paste('Histogram of', cn, 'with Fitted Normal Distribution'),",
        "            xlab = cn, ylab = 'Density')",
        "",
        "  if (!is.na(s) && s > 0) {",
        "    x_seq <- seq(min(x_clean) - 0.5 * s, max(x_clean) + 0.5 * s, length.out = 200)",
        "    lines(x_seq, dnorm(x_seq, mean = m, sd = s), col = '#dc2626', lwd = 2.5)",
        "    legend('topright',",
        "           legend = c('Normal Fit', sprintf('Mean = %.4f', m), sprintf('StDev = %.4f', s), sprintf('N = %d', n)),",
        "           col = c('#dc2626', NA, NA, NA), lty = c(1, NA, NA, NA), lwd = c(2.5, NA, NA, NA),",
        "           bty = 'n', cex = 0.85, inset = 0.02)",
        "  }",
        "  box()",
        "}",
    ]
    return "\n".join(lines)


def generate_dataframe_definition(worksheet: "Worksheet") -> str:
    """Generate clean, reproducible Base R code reconstructing the active worksheet as 'df'."""
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
        f"# StatCraft — Reproducible Worksheet Data Definition\n"
        f"# Worksheet: {worksheet.name} ({len(worksheet.columns)} columns, {worksheet.row_count} rows)\n"
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "# ==============================================================================\n\n"
        f"df <- data.frame(\n{body},\n  check.names = FALSE,\n  stringsAsFactors = FALSE\n)"
    )


def build_self_contained_r_script(r_script: str, worksheet: "Worksheet", title: str = "") -> str:
    """Ensure any exported or copied R script includes the self-contained data frame definition."""
    if not r_script:
        return generate_dataframe_init_code(worksheet)
    if "df <- data.frame(" in r_script:
        return r_script
    df_def = generate_dataframe_definition(worksheet)
    return f"{df_def}\n\n{r_script}"


def generate_dataframe_init_code(worksheet: "Worksheet") -> str:
    """Generate reproducible Base R script with active worksheet data and smart automated exploratory statistical calculations."""
    df_def = generate_dataframe_definition(worksheet)
    eda_code = (
        '\n\ncat("Active worksheet loaded into R as \'df\':\\n")\n'
        "print(head(df))\n"
        "cat('\\nStructure of df:\\n')\n"
        "str(df)\n\n"
        "# ==============================================================================\n"
        "# Automated Exploratory Statistical Calculations\n"
        "# ==============================================================================\n\n"
        "numeric_cols <- names(df)[sapply(df, is.numeric)]\n"
        "cat_cols <- names(df)[!sapply(df, is.numeric)]\n\n"
        "if (length(numeric_cols) > 0) {\n"
        "  cat('\\n================================================================================\\n')\n"
        "  cat('                 Summary Statistics for Numeric Variables                       \\n')\n"
        "  cat('================================================================================\\n\\n')\n"
        "  for (cn in numeric_cols) {\n"
        "    x <- as.numeric(df[[cn]])\n"
        "    x_clean <- x[!is.na(x)]\n"
        "    if (length(x_clean) > 0) {\n"
        "      n <- length(x_clean)\n"
        "      m <- mean(x_clean)\n"
        "      s <- sd(x_clean)\n"
        "      se <- s / sqrt(n)\n"
        "      med <- median(x_clean)\n"
        "      q1 <- as.numeric(quantile(x_clean, 0.25, type = 6))\n"
        "      q3 <- as.numeric(quantile(x_clean, 0.75, type = 6))\n"
        "      iqr_val <- q3 - q1\n"
        "      m3 <- sum((x_clean - m)^3) / n\n"
        "      skew <- if (s > 0) m3 / (s^3) else 0\n"
        "      cat(sprintf('Variable: %s\\n', cn))\n"
        "      cat(sprintf('  N: %d, N*: %d, Mean: %.4f, SE Mean: %.4f, StDev: %.4f\\n', n, sum(is.na(x)), m, se, s))\n"
        "      cat(sprintf('  Min: %.4f, Q1: %.4f, Median: %.4f, Q3: %.4f, Max: %.4f, IQR: %.4f\\n', min(x_clean), q1, med, q3, max(x_clean), iqr_val))\n"
        "      cat(sprintf('  Skewness: %.4f\\n', skew))\n"
        "      cat('--------------------------------------------------------------------------------\\n')\n"
        "    }\n"
        "  }\n\n"
        "  # Individual Distribution Histograms with Normal Fit for Each Numeric Variable\n"
        "  par(mfrow = c(min(2, ceiling(length(numeric_cols) / 2)), min(2, length(numeric_cols))))\n"
        "  for (cn in numeric_cols) {\n"
        "    x <- df[[cn]]\n"
        "    x_clean <- x[!is.na(x)]\n"
        "    if (length(x_clean) >= 2) {\n"
        "      m <- mean(x_clean)\n"
        "      s <- sd(x_clean)\n"
        "      hist(x_clean, breaks = 'FD', col = '#38bdf8', border = 'white', prob = TRUE,\n"
        "           main = paste('Histogram of', cn, 'with Normal Fit'), xlab = cn, ylab = 'Density')\n"
        "      if (!is.na(s) && s > 0) {\n"
        "        curve(dnorm(x, mean = m, sd = s), col = '#dc2626', lwd = 2, add = TRUE)\n"
        "        legend('topright', legend = c('Normal Fit', sprintf('Mean = %.2f', m), sprintf('StDev = %.2f', s)),\n"
        "               col = c('#dc2626', NA, NA), lty = c(1, NA, NA), lwd = c(2, NA, NA), bty = 'n', cex = 0.8)\n"
        "      }\n"
        "      box()\n"
        "    }\n"
        "  }\n"
        "  par(mfrow = c(1, 1))\n\n"
        "  if (length(numeric_cols) >= 2) {\n"
        "    cat('\\nPairwise Pearson Correlation Matrix:\\n')\n"
        "    print(round(cor(df[numeric_cols], use = 'pairwise.complete.obs'), 4))\n"
        "    # pairs(df[numeric_cols], col = '#2563eb', pch = 19, main = 'Pairwise Scatterplot Matrix')\n"
        "  }\n"
        "}\n\n"
        "if (length(cat_cols) > 0) {\n"
        "  cat('\\nCategorical / Factor Variable Distributions:\\n')\n"
        "  for (cn in cat_cols) {\n"
        "    cat(sprintf('\\nFrequency Table: %s\\n', cn))\n"
        "    print(table(df[[cn]], useNA = 'ifany'))\n"
        "    cat('Relative Percentages:\\n')\n"
        "    print(round(prop.table(table(df[[cn]])) * 100, 2))\n"
        "  }\n"
        "}\n"
    )
    return f"{df_def}{eda_code}"

# ==============================================================================
# Modern Tidyverse, ggplot2, and vroom Ingestion Engine
# ==============================================================================

def generate_vroom_data_import_code(worksheet: "Worksheet") -> str:
    """Generate high-performance data ingestion script using vroom, readr, or readxl."""
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
    clean_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in worksheet.name).strip("_") or "data"

    return (
        "# ==============================================================================\n"
        f"# StatCraft — High-Performance Data Ingestion via vroom / readr / readxl\n"
        f"# Worksheet: {worksheet.name} ({len(worksheet.columns)} columns, {worksheet.row_count} rows)\n"
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "# ==============================================================================\n\n"
        "# 1. Automated Package Verification & Loading\n"
        "io_pkgs <- c('vroom', 'readr', 'readxl', 'tibble')\n"
        "needed <- io_pkgs[!(io_pkgs %in% installed.packages()[, 'Package'])]\n"
        "if (length(needed) > 0) install.packages(needed, repos = 'https://cloud.r-project.org')\n"
        "library(tibble)\n\n"
        "# ------------------------------------------------------------------------------\n"
        "# Ingestion Option A: Blazing Fast CSV/TSV Ingestion with vroom\n"
        "# Multi-threaded, memory-mapped reader (orders of magnitude faster on large files)\n"
        "# ------------------------------------------------------------------------------\n"
        f"# df <- vroom::vroom('{clean_name}.csv', delim = ',', show_col_types = FALSE)\n\n"
        "# ------------------------------------------------------------------------------\n"
        "# Ingestion Option B: Native Excel Ingestion with readxl\n"
        "# Reads binary .xlsx / .xls directly without external Java dependencies\n"
        "# ------------------------------------------------------------------------------\n"
        f"# df <- readxl::read_excel('{clean_name}.xlsx', sheet = '{worksheet.name}')\n\n"
        "# ------------------------------------------------------------------------------\n"
        "# Ingestion Option C: Embedded Self-Contained Reproducible Tibble\n"
        "# ------------------------------------------------------------------------------\n"
        f"df <- tibble::tibble(\n{body}\n)\n\n"
        'cat("Successfully loaded active worksheet data into tibble \'df\':\\n")\n'
        "print(head(df))\n"
    )


def generate_r_tidyverse_script(connected: "ConnectedAnalysis", worksheet: "Worksheet") -> str:
    """Generate modern, publication-grade R script using Tidyverse, dplyr, and ggplot2."""
    vroom_block = generate_vroom_data_import_code(worksheet)
    atype = connected.analysis_type
    meta = connected.metadata or {}
    title = connected.title

    lines = [
        vroom_block,
        "",
        "# ==============================================================================",
        f"# StatCraft — Modern Tidyverse & ggplot2 Analysis Pipeline",
        f"# Procedure: {title}",
        f"# Action: {atype}",
        f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "# ==============================================================================",
        "",
        "# Ensure Tidyverse, ggplot2, and modeling packages are loaded",
        "tidy_pkgs <- c('tidyverse', 'ggplot2', 'dplyr', 'tidyr')",
        "needed <- tidy_pkgs[!(tidy_pkgs %in% installed.packages()[, 'Package'])]",
        "if (length(needed) > 0) install.packages(needed, repos = 'https://cloud.r-project.org')",
        "library(tidyverse)",
        "library(ggplot2)",
        "library(dplyr)",
        "library(tidyr)",
        "",
    ]

    all_cols = [connected.response_name] + connected.predictor_names if connected.response_name else connected.predictor_names
    col_str_literals = ", ".join(json.dumps(c) for c in all_cols)

    if atype in ("histogram", "histogram_graphs"):
        target_cols = connected.metadata.get("column_names") or ([connected.response_name] if connected.response_name else [c.name for c in worksheet.columns if c.kind == "number"][:1])
        target_cols_json = ", ".join(json.dumps(c) for c in target_cols)
        lines.extend([
            "# ------------------------------------------------------------------------------",
            "# Modern ggplot2 Publication-Grade Histogram with Fitted Normal Distribution",
            "# ------------------------------------------------------------------------------",
            f"target_cols <- c({target_cols_json})",
            "",
            "for (cn in target_cols) {",
            "  sub_df <- df %>% filter(!is.na(.data[[cn]]))",
            "  m <- mean(sub_df[[cn]], na.rm = TRUE)",
            "  s <- sd(sub_df[[cn]], na.rm = TRUE)",
            "  n <- nrow(sub_df)",
            "",
            "  p_hist <- ggplot(sub_df, aes(x = .data[[cn]])) +",
            "    geom_histogram(aes(y = after_stat(density)), bins = 20, fill = '#0284c7', color = 'white', alpha = 0.75) +",
            "    geom_density(color = '#10b981', linewidth = 1.2, linetype = 'solid') +",
            "    stat_function(",
            "      fun = dnorm,",
            "      args = list(mean = m, sd = s),",
            "      color = '#dc2626', linewidth = 1.2, linetype = 'dashed'",
            "    ) +",
            "    labs(",
            "      title = paste('Histogram of', cn, 'with Fitted Normal Distribution'),",
            "      subtitle = sprintf('Mean = %.4f | StDev = %.4f | N = %d', m, s, n),",
            "      x = cn,",
            "      y = 'Density'",
            "    ) +",
            "    theme_minimal(base_size = 12) +",
            "    theme(",
            "      plot.title = element_text(face = 'bold', size = 13, color = '#0f172a'),",
            "      plot.subtitle = element_text(color = '#475569', size = 10),",
            "      panel.grid.minor = element_blank()",
            "    )",
            "",
            "  print(p_hist)",
            "}",
        ])
    elif atype in ("descriptive_statistics", "describe_columns", "describe"):
        lines.extend([
            "# ------------------------------------------------------------------------------",
            "# 1. Tidyverse Data Wrangling & Descriptive Summary Pipeline",
            "# ------------------------------------------------------------------------------",
            f"target_cols <- c({col_str_literals})",
            "",
            "descriptive_summary <- df %>%",
            "  select(all_of(target_cols)) %>%",
            "  pivot_longer(cols = everything(), names_to = 'Variable', values_to = 'Value') %>%",
            "  filter(!is.na(Value)) %>%",
            "  group_by(Variable) %>%",
            "  summarise(",
            "    N = n(),",
            "    Mean = mean(Value),",
            "    SE_Mean = sd(Value) / sqrt(n()),",
            "    StDev = sd(Value),",
            "    Variance = var(Value),",
            "    CoeffVar = (StDev / Mean) * 100,",
            "    Min = min(Value),",
            "    Q1 = as.numeric(quantile(Value, 0.25, type = 6)),",
            "    Median = median(Value),",
            "    Q3 = as.numeric(quantile(Value, 0.75, type = 6)),",
            "    Max = max(Value),",
            "    IQR = IQR(Value, type = 6),",
            "    Skewness = (sum((Value - Mean)^3) / n()) / (StDev^3),",
            "    Kurtosis = (sum((Value - Mean)^4) / n()) / (StDev^4) - 3,",
            "    .groups = 'drop'",
            "  )",
            "",
            "cat('================================================================================\n')",
            "cat('            StatCraft: Tidyverse Descriptive Statistics Summary                 \n')",
            "cat('================================================================================\n\n')",
            "print(as.data.frame(descriptive_summary))",
            "",
            "# ------------------------------------------------------------------------------",
            "# 2. Modern ggplot2 Publication-Grade Visualizations",
            "# ------------------------------------------------------------------------------",
            "# Multi-panel Faceted Histogram with Normal Density Fit Curves",
            "p_hist <- df %>%",
            "  select(all_of(target_cols)) %>%",
            "  pivot_longer(cols = everything(), names_to = 'Variable', values_to = 'Value') %>%",
            "  ggplot(aes(x = Value, fill = Variable)) +",
            "  geom_histogram(aes(y = after_stat(density)), bins = 15, color = 'white', alpha = 0.75) +",
            "  geom_density(color = '#dc2626', linewidth = 1) +",
            "  facet_wrap(~ Variable, scales = 'free') +",
            "  theme_minimal(base_size = 12) +",
            "  theme(legend.position = 'none', panel.grid.minor = element_blank()) +",
            "  labs(title = 'Distribution Analysis: Histogram & Density Fit', y = 'Density')",
            "print(p_hist)",
            "",
            "# Modern Boxplot with Observed Jitter & Mean Diamond",
            "p_box <- df %>%",
            "  select(all_of(target_cols)) %>%",
            "  pivot_longer(cols = everything(), names_to = 'Variable', values_to = 'Value') %>%",
            "  ggplot(aes(x = Variable, y = Value, fill = Variable)) +",
            "  geom_boxplot(alpha = 0.6, outlier.colour = '#dc2626', outlier.size = 2, width = 0.5) +",
            "  geom_jitter(width = 0.15, alpha = 0.4, color = '#1e3a8a', size = 1.5) +",
            "  stat_summary(fun = mean, geom = 'point', shape = 18, size = 3.5, color = '#dc2626') +",
            "  theme_minimal(base_size = 12) +",
            "  theme(legend.position = 'none') +",
            "  labs(title = 'Boxplots with Observed Jitter & Mean Diamond (Red)', y = 'Value')",
            "print(p_box)",
        ])
    elif atype in ("multiple_regression", "linear_regression", "regression", "fitted_line_plot"):
        resp = format_r_symbol(connected.response_name)
        preds = " + ".join(format_r_symbol(p) for p in connected.predictor_names)
        first_p = format_r_symbol(connected.predictor_names[0]) if connected.predictor_names else resp
        lines.extend([
            "# ------------------------------------------------------------------------------",
            "# 1. Ordinary Least Squares Linear Model Fit",
            "# ------------------------------------------------------------------------------",
            f"formula_obj <- {resp} ~ {preds}",
            "fit <- lm(formula_obj, data = df)",
            "print(summary(fit))",
            "",
            "cat('\n--- 95% Confidence Intervals for Coefficients ---\n')",
            "print(confint(fit))",
            "",
            "# Augmented Data with Residuals & Fitted Values",
            "model_df <- df %>%",
            "  mutate(",
            "    .fitted = fitted(fit),",
            "    .resid = resid(fit),",
            "    .std_resid = rstandard(fit)",
            "  )",
            "",
            "# ------------------------------------------------------------------------------",
            "# 2. Modern ggplot2 Regression Diagnostics",
            "# ------------------------------------------------------------------------------",
            "# Fitted Line Plot with 95% Confidence Band",
            f"p_fit <- ggplot(df, aes(x = {first_p}, y = {resp})) +",
            "  geom_point(color = '#1e3a8a', alpha = 0.7, size = 2.5) +",
            "  geom_smooth(method = 'lm', formula = y ~ x, color = '#0284c7', fill = '#bae6fd', alpha = 0.4) +",
            "  labs(title = 'Fitted Line Plot with 95% Confidence Band', subtitle = paste('R-squared =', round(summary(fit)$r.squared, 4))) +",
            "  theme_minimal(base_size = 12)",
            "print(p_fit)",
            "",
            "# Residuals vs Fitted Plot",
            "p_resid <- ggplot(model_df, aes(x = .fitted, y = .std_resid)) +",
            "  geom_hline(yintercept = 0, linetype = 'dashed', color = 'gray50') +",
            "  geom_point(color = '#dc2626', alpha = 0.75, size = 2) +",
            "  geom_smooth(method = 'loess', formula = y ~ x, se = FALSE, color = '#2563eb', linewidth = 0.8) +",
            "  labs(title = 'Residuals vs Fitted Values', x = 'Fitted Values', y = 'Standardized Residuals') +",
            "  theme_minimal(base_size = 12)",
            "print(p_resid)",
        ])
    elif atype in ("oneway_anova", "one_way_anova"):
        resp = format_r_symbol(connected.response_name)
        fac = format_r_symbol(connected.predictor_names[0]) if connected.predictor_names else "Group"
        lines.extend([
            "# ------------------------------------------------------------------------------",
            "# 1. One-Way Analysis of Variance",
            "# ------------------------------------------------------------------------------",
            f"formula_obj <- {resp} ~ as.factor({fac})",
            "fit <- aov(formula_obj, data = df)",
            "print(summary(fit))",
            "",
            "cat('\n--- Tukey Honest Significant Differences (Tukey HSD) ---\n')",
            "print(TukeyHSD(fit))",
            "",
            "# ------------------------------------------------------------------------------",
            "# 2. Modern ggplot2 Factor Level Visualizations",
            "# ------------------------------------------------------------------------------",
            f"p_aov <- ggplot(df, aes(x = as.factor({fac}), y = {resp}, fill = as.factor({fac}))) +",
            "  geom_boxplot(alpha = 0.6, width = 0.5, outlier.color = 'red') +",
            "  geom_jitter(width = 0.15, alpha = 0.4, size = 2) +",
            "  stat_summary(fun = mean, geom = 'point', shape = 18, size = 4, color = '#1e3a8a') +",
            f"  labs(title = 'One-Way ANOVA: Factor Levels vs Response', x = {json.dumps(connected.predictor_names[0] if connected.predictor_names else 'Group')}, y = {json.dumps(connected.response_name)}) +",
            "  theme_minimal(base_size = 12) +",
            "  theme(legend.position = 'none')",
            "print(p_aov)",
        ])
    elif atype in ("two_sample_t", "one_sample_t", "paired_t"):
        if atype == "two_sample_t":
            c1, c2 = connected.response_name, connected.predictor_names[0] if connected.predictor_names else "Group"
            lines.extend([
                "# ------------------------------------------------------------------------------",
                "# Two-Sample Hypothesis Testing (t-Test)",
                "# ------------------------------------------------------------------------------",
                f"t_res <- t.test(df[[{json.dumps(c1)}]], df[[{json.dumps(c2)}]], conf.level = {connected.confidence})",
                "print(t_res)",
                "",
                "# ggplot2 Comparison Plot",
                f"p_comp <- df %>%",
                f"  select(all_of(c({json.dumps(c1)}, {json.dumps(c2)}))) %>%",
                "  pivot_longer(cols = everything(), names_to = 'Sample', values_to = 'Measurement') %>%",
                "  ggplot(aes(x = Sample, y = Measurement, fill = Sample)) +",
                "  geom_boxplot(alpha = 0.6, width = 0.4, outlier.shape = NA) +",
                "  geom_jitter(width = 0.15, alpha = 0.5, size = 2) +",
                "  theme_minimal(base_size = 12) +",
                "  theme(legend.position = 'none') +",
                "  labs(title = 'Two-Sample Comparison', subtitle = paste('p-value =', format.pval(t_res$p.value)))",
                "print(p_comp)",
            ])
        else:
            lines.extend([
                f"# Hypothesis Test: {connected.title}",
                f"t_res <- t.test(df[[{json.dumps(connected.response_name)}]], conf.level = {connected.confidence})",
                "print(t_res)",
                f"p_one <- ggplot(df, aes(x = df[[{json.dumps(connected.response_name)}]])) +",
                "  geom_histogram(fill = '#93c5fd', color = '#1e3a8a', bins = 15) +",
                "  theme_minimal(base_size = 12) +",
                f"  labs(title = {json.dumps(connected.title)}, x = {json.dumps(connected.response_name)})",
                "print(p_one)",
            ])
    elif atype in ("imr_chart", "subgroup_spc", "process_control"):
        m_col = connected.response_name or (connected.predictor_names[0] if connected.predictor_names else "Measurement")
        stats = connected.statistics or {}
        ucl = stats.get("ucl", 0)
        cl = stats.get("centerline", stats.get("mean", 0))
        lcl = stats.get("lcl", 0)
        lines.extend([
            "# ------------------------------------------------------------------------------",
            "# Modern ggplot2 Statistical Process Control Chart",
            "# ------------------------------------------------------------------------------",
            "chart_df <- df %>%",
            "  mutate(Observation = row_number())",
            "",
            f"p_spc <- ggplot(chart_df, aes(x = Observation, y = .data[[{json.dumps(m_col)}]])) +",
            "  geom_line(color = '#2563eb', linewidth = 0.7) +",
            "  geom_point(color = '#1e3a8a', size = 2) +",
            f"  geom_hline(yintercept = {ucl}, linetype = 'dashed', color = '#dc2626', linewidth = 0.8) +",
            f"  geom_hline(yintercept = {cl}, color = '#16a34a', linewidth = 0.8) +",
            f"  geom_hline(yintercept = {lcl}, linetype = 'dashed', color = '#dc2626', linewidth = 0.8) +",
            f"  annotate('text', x = nrow(chart_df), y = {ucl}, label = 'UCL', vjust = -0.5, color = '#dc2626', fontface = 'bold') +",
            f"  annotate('text', x = nrow(chart_df), y = {cl}, label = 'Centerline', vjust = -0.5, color = '#16a34a', fontface = 'bold') +",
            f"  annotate('text', x = nrow(chart_df), y = {lcl}, label = 'LCL', vjust = 1.5, color = '#dc2626', fontface = 'bold') +",
            f"  labs(title = 'Statistical Process Control Chart: {m_col}', y = {json.dumps(m_col)}) +",
            "  theme_minimal(base_size = 12)",
            "print(p_spc)",
        ])
    else:
        # Generic automated exploratory tidyverse summary
        lines.extend([
            "# ------------------------------------------------------------------------------",
            "# Automated Exploratory Tidyverse Summary",
            "# ------------------------------------------------------------------------------",
            "eda_summary <- df %>%",
            "  select(where(is.numeric)) %>%",
            "  pivot_longer(cols = everything(), names_to = 'Variable', values_to = 'Value') %>%",
            "  filter(!is.na(Value)) %>%",
            "  group_by(Variable) %>%",
            "  summarise(",
            "    N = n(),",
            "    Mean = mean(Value),",
            "    StDev = sd(Value),",
            "    Median = median(Value),",
            "    IQR = IQR(Value, type = 6),",
            "    Min = min(Value),",
            "    Max = max(Value),",
            "    .groups = 'drop'",
            "  )",
            "print(as.data.frame(eda_summary))",
            "",
            "# Correlation Matrix & Scatterplot Matrix",
            "num_cols <- names(df)[sapply(df, is.numeric)]",
            "if (length(num_cols) >= 2) {",
            "  cat('\nPairwise Pearson Correlation Matrix:\n')",
            "  print(round(cor(df[, num_cols], use = 'pairwise.complete.obs'), 4))",
            "  pairs(df[, num_cols], col = '#2563eb', pch = 19, main = 'Pairwise Scatterplot Matrix')",
            "}",
        ])

    return "\n".join(lines)
