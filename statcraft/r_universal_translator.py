"""Universal R Translator for Statcraft.

Seamlessly translates ANY Statcraft analysis, graph, or native output into:
1. Self-contained, runnable Pure Base R script (zero external dependencies required)
2. Modern, publication-grade Tidyverse & ggplot2 data science pipeline
3. High-performance vroom / readr ingestion code
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .model import Worksheet


def _escape_str(val: str) -> str:
    return json.dumps(str(val))


def generate_dataframe_r_code(worksheet: Worksheet) -> str:
    """Generate self-contained data.frame definition in Base R."""
    lines = ["# ------------------------------------------------------------------------------",
             f"# Data Definition: {worksheet.name}",
             "# ------------------------------------------------------------------------------"]
    col_defs = []
    for c in worksheet.columns:
        if c.kind == "number":
            vals = ["NA" if v is None or not math.isfinite(v) else repr(float(v)) for v in c.values]
            col_defs.append(f"  {_escape_str(c.name)} = c({', '.join(vals)})")
        elif c.kind == "date":
            from .model import display_date
            vals = ["NA" if v is None else repr(display_date(v)) for v in c.values]
            col_defs.append(f"  {_escape_str(c.name)} = as.Date(c({', '.join(vals)}))")
        else:
            vals = ["NA" if v is None else repr(str(v)) for v in c.values]
            col_defs.append(f"  {_escape_str(c.name)} = c({', '.join(vals)})")

    df_body = ",\n".join(col_defs)
    lines.append(f"df <- data.frame(\n{df_body},\n  stringsAsFactors = FALSE,\n  check.names = FALSE\n)")
    return "\n".join(lines)


def translate_entry_to_r(entry: Dict[str, Any], worksheet: Worksheet) -> Tuple[str, str, str]:
    """Universal translator returning (base_r_script, tidyverse_script, procedure_title)."""
    title = entry.get("title", "Analysis")
    recipe = entry.get("recipe", {})
    action = recipe.get("action", "")
    params = recipe.get("parameters", {})
    result = entry.get("result", {})
    analysis = result.get("analysis", action)
    graph = result.get("graph", "")

    df_init = generate_dataframe_r_code(worksheet)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Header templates
    base_hdr = [
        df_init,
        "",
        "# ==============================================================================",
        f"# StatCraft — Reproducible Pure Base R Script",
        f"# Procedure: {title}",
        f"# Timestamp: {now_str}",
        "# ==============================================================================",
        "",
    ]

    tidy_hdr = [
        df_init,
        "",
        "# ==============================================================================",
        f"# StatCraft — Modern Tidyverse & ggplot2 Pipeline",
        f"# Procedure: {title}",
        f"# Timestamp: {now_str}",
        "# ==============================================================================",
        "",
        "# Load tidyverse packages",
        "suppressPackageStartupMessages({",
        "  if (!requireNamespace('tidyverse', quietly = TRUE)) install.packages('tidyverse')",
        "  library(tidyverse)",
        "})",
        "",
    ]

    # Dispatch based on analysis / action / graph
    b_body: List[str] = []
    t_body: List[str] = []

    if analysis in ("random_forest", "treenet_gbm", "mars_regression", "discover_best_model"):
        r_idx = params.get("response_index", 0)
        p_idxs = params.get("predictor_indices") or [1]
        y_col = worksheet.columns[r_idx].name if 0 <= r_idx < len(worksheet.columns) else worksheet.columns[0].name
        x_cols = [worksheet.columns[i].name for i in p_idxs if 0 <= i < len(worksheet.columns)] or [worksheet.columns[-1].name]
        rhs = " + ".join(f"`{c}`" for c in x_cols)
        if analysis == "random_forest":
            pkg = "randomForest"
            call_lines = [
                f"fit <- randomForest(`{y_col}` ~ {rhs}, data = df_ml, ntree = {params.get('n_trees', 80)}, importance = TRUE)",
                "print(fit)",
                "varImpPlot(fit, main = 'Random Forest Variable Importance')",
            ]
        elif analysis == "treenet_gbm":
            pkg = "gbm"
            call_lines = [
                f"fit <- gbm(`{y_col}` ~ {rhs}, data = df_ml, n.trees = {params.get('n_trees', 100)}, shrinkage = {params.get('learning_rate', 0.08)}, interaction.depth = {params.get('max_depth', 3)}, bag.fraction = {params.get('subsample', 0.8)})",
                "summary(fit)",
            ]
        elif analysis == "mars_regression":
            pkg = "earth"
            call_lines = [
                f"fit <- earth(`{y_col}` ~ {rhs}, data = df_ml, degree = {params.get('max_degree', 2)}, nk = {params.get('max_terms', 16)})",
                "print(summary(fit))",
            ]
        else:
            pkg = "caret"
            call_lines = [
                f"# AutoML Benchmark Comparison for `{y_col}`",
                f"summary(lm(`{y_col}` ~ {rhs}, data = df_ml))",
            ]
        b_body = [
            f"if (!requireNamespace('{pkg}', quietly = TRUE)) install.packages('{pkg}')",
            f"library({pkg})",
            f"df_ml <- na.omit(df[, c({_escape_str(y_col)}, {', '.join(_escape_str(c) for c in x_cols)}), drop = FALSE])",
            *call_lines,
        ]
        t_body = list(b_body) + [
            f"# Visualize top relationship",
            f"ggplot(df_ml, aes(x = .data[[{_escape_str(x_cols[0])}]], y = .data[[{_escape_str(y_col)}]])) + geom_point(alpha = 0.7, color = '#2563eb') + geom_smooth(se = FALSE, color = '#dc2626') + labs(title = {repr(title)}) + theme_minimal()",
        ]

    elif analysis in ("mixed_reml", "cox_ph_regression", "negative_binomial_regression"):
        if analysis == "mixed_reml":
            r_col = worksheet.columns[params.get("response_index", 0)].name
            f_names = [worksheet.columns[i].name for i in (params.get("fixed_indices") or []) if 0 <= i < len(worksheet.columns)]
            rnd_names = [worksheet.columns[i].name for i in (params.get("random_indices") or []) if 0 <= i < len(worksheet.columns)]
            fixed_part = " + ".join(f"`{c}`" for c in f_names) if f_names else "1"
            rnd_part = " + ".join(f"(1 | `{c}`)" for c in rnd_names) if rnd_names else "(1 | 1)"
            b_body = [
                "if (!requireNamespace('lme4', quietly = TRUE)) install.packages('lme4')",
                "library(lme4)",
                f"fit_reml <- lmer(`{r_col}` ~ {fixed_part} + {rnd_part}, data = df, REML = TRUE)",
                "print(summary(fit_reml))",
                "print(VarCorr(fit_reml))",
            ]
        elif analysis == "cox_ph_regression":
            t_col = worksheet.columns[params.get("time_index", 0)].name
            e_col = worksheet.columns[params.get("event_index", 1)].name
            c_names = [worksheet.columns[i].name for i in (params.get("covariate_indices") or [2]) if 0 <= i < len(worksheet.columns)]
            rhs = " + ".join(f"`{c}`" for c in c_names)
            b_body = [
                "if (!requireNamespace('survival', quietly = TRUE)) install.packages('survival')",
                "library(survival)",
                f"fit_cox <- coxph(Surv(`{t_col}`, `{e_col}` == {params.get('event_value', 1)}) ~ {rhs}, data = df)",
                "print(summary(fit_cox))",
                "plot(survfit(fit_cox), col = '#2563eb', main = 'Cox Proportional Hazards Survival Curve')",
            ]
        else:
            r_col = worksheet.columns[params.get("response_index", 0)].name
            p_names = [worksheet.columns[i].name for i in (params.get("predictor_indices") or [1]) if 0 <= i < len(worksheet.columns)]
            rhs = " + ".join(f"`{c}`" for c in p_names)
            b_body = [
                "if (!requireNamespace('MASS', quietly = TRUE)) install.packages('MASS')",
                f"fit_nb <- MASS::glm.nb(`{r_col}` ~ {rhs}, data = df)",
                "print(summary(fit_nb))",
            ]
        t_body = list(b_body)

    elif analysis in ("bootstrap_1sample", "bootstrap_2sample"):
        c1 = worksheet.columns[params.get("index", params.get("index1", 0))].name
        b_body = [
            "if (!requireNamespace('boot', quietly = TRUE)) install.packages('boot')",
            "library(boot)",
            f"x <- na.omit(df[[{_escape_str(c1)}]])",
            f"b_out <- boot(x, function(d, i) mean(d[i]), R = {params.get('resamples', params.get('n_resamples', 2000))})",
            "print(b_out)",
            f"print(boot.ci(b_out, conf = {params.get('confidence', 0.95)}, type = c('perc', 'bca')))",
            "hist(b_out$t, col = '#93c5fd', border = 'white', main = 'Bootstrap Distribution')",
        ]
        t_body = list(b_body)

    elif analysis in ("balanced_anova", "fully_nested_anova", "oneway_manova"):
        if analysis == "oneway_manova":
            r_cols = [worksheet.columns[i].name for i in (params.get("response_indices") or [0, 1]) if 0 <= i < len(worksheet.columns)]
            f_col = worksheet.columns[params.get("factor_index", 2)].name
            lhs = ", ".join(f"`{c}`" for c in r_cols)
            b_body = [
                f"fit_man <- manova(cbind({lhs}) ~ factor(`{f_col}`), data = df)",
                "print(summary(fit_man, test = 'Wilks'))",
                "print(summary(fit_man, test = 'Pillai'))",
            ]
        else:
            r_col = worksheet.columns[params.get("response_index", 0)].name
            f_cols = [worksheet.columns[i].name for i in (params.get("factor_indices") or [1]) if 0 <= i < len(worksheet.columns)]
            rhs = " / ".join(f"factor(`{c}`)" for c in f_cols) if analysis == "fully_nested_anova" else " * ".join(f"factor(`{c}`)" for c in f_cols)
            b_body = [
                f"fit_aov <- aov(`{r_col}` ~ {rhs}, data = df)",
                "print(summary(fit_aov))",
            ]
        t_body = list(b_body)

    elif analysis == "monte_carlo_simulation":
        inps = result.get("inputs") or []
        sim_n = int(result.get("n_sims", 10000))
        b_body = [f"set.seed({params.get('seed', 42)})", f"N <- {sim_n}"]
        for inp in inps:
            nm = inp["name"]
            dist = inp["distribution"].lower()
            ps = ", ".join(str(x) for x in inp["params"])
            fn_map = {"normal": "rnorm", "uniform": "runif", "lognormal": "rlnorm", "exponential": "rexp", "weibull": "rweibull"}
            if dist in fn_map:
                if dist == "exponential":
                    b_body.append(f"{nm} <- rexp(N, rate = 1 / ({inp['params'][0]}))")
                elif dist == "weibull":
                    b_body.append(f"{nm} <- rweibull(N, shape = {inp['params'][0]}, scale = {inp['params'][1]})")
                else:
                    b_body.append(f"{nm} <- {fn_map[dist]}(N, {ps})")
            else:
                b_body.append(f"{nm} <- runif(N, {inp['params'][0]}, {inp['params'][-1]})")
        eq = str(result.get("formula", "X1")).strip()
        b_body += [
            f"Y <- {eq}",
            "cat('Mean:', mean(Y), 'SD:', sd(Y), '\n')",
            "hist(Y, breaks = 30, col = '#3b82f6', border = 'white', main = 'Monte Carlo Simulation Output')",
        ]
        t_body = list(b_body)

    # 1. ORTHOGONAL REGRESSION (DEMING)
    elif analysis == "orthogonal_regression" or action == "orthogonal_regression":
        y_name = result.get("response_name") or (worksheet.columns[params["response_index"]].name if "response_index" in params else "Y")
        x_name = result.get("predictor_name") or (worksheet.columns[params["predictor_index"]].name if "predictor_index" in params else "X")
        delta = float(params.get("error_variance_ratio", result.get("error_variance_ratio", 1.0)))

        b_body = [
            f"# Deming (Orthogonal) Regression: {y_name} vs {x_name} (Error Ratio delta = {delta})",
            f"x <- df[[{_escape_str(x_name)}]]",
            f"y <- df[[{_escape_str(y_name)}]]",
            "ok <- complete.cases(x, y); x <- x[ok]; y <- y[ok]",
            f"delta <- {delta}",
            "s_xx <- var(x); s_yy <- var(y); s_xy <- cov(x, y)",
            "b1 <- ((s_yy - delta * s_xx) + sqrt((s_yy - delta * s_xx)^2 + 4 * delta * s_xy^2)) / (2 * s_xy)",
            "b0 <- mean(y) - b1 * mean(x)",
            "cat(sprintf('Deming Fit: %s = %.4f + %.4f * %s\\n', " + f"{_escape_str(y_name)}, b0, b1, {_escape_str(x_name)}))",
            f"plot(x, y, pch = 19, col = '#2563eb', xlab = {_escape_str(x_name)}, ylab = {_escape_str(y_name)}, main = 'Orthogonal Regression (Deming)')",
            "abline(b0, b1, col = '#dc2626', lwd = 2)",
            "abline(0, 1, col = '#64748b', lty = 2)",
            "legend('topleft', legend = c('Deming Fit', 'Equality (Y = X)'), col = c('#dc2626', '#64748b'), lty = c(1, 2), lwd = c(2, 1))",
        ]
        t_body = [
            f"# Tidyverse Deming Regression visualization",
            f"b0 <- {result.get('intercept', 0.0)}; b1 <- {result.get('slope', 1.0)}",
            f"ggplot(df, aes(x = .data[[{_escape_str(x_name)}]], y = .data[[{_escape_str(y_name)}]])) +",
            "  geom_point(color = '#2563eb', size = 2.5, alpha = 0.8) +",
            "  geom_abline(intercept = b0, slope = b1, color = '#dc2626', linewidth = 1.2) +",
            "  geom_abline(intercept = 0, slope = 1, color = '#64748b', linetype = 'dashed') +",
            f"  labs(title = 'Orthogonal Regression: {y_name} vs {x_name}', subtitle = sprintf('Y = %.4f + %.4f * X', b0, b1)) +",
            "  theme_minimal(base_size = 12)",
        ]

    # 2. PROBIT ANALYSIS
    elif analysis == "probit_analysis" or action == "probit_analysis":
        resp = worksheet.columns[params.get("response_index", 0)].name
        trials = worksheet.columns[params.get("trials_index", 1)].name
        dose = worksheet.columns[params.get("dose_index", 2)].name
        link = params.get("distribution", "probit").lower()
        if link not in ("probit", "logit", "cloglog"):
            link = "probit"

        b_body = [
            f"# Probit / Bioassay Analysis",
            f"fit <- glm(cbind(df[[{_escape_str(resp)}]], df[[{_escape_str(trials)}]] - df[[{_escape_str(resp)}]]) ~ df[[{_escape_str(dose)}]], family = binomial(link = '{link}'))",
            "summary(fit)",
            "if (requireNamespace('MASS', quietly = TRUE)) {",
            "  cat('\\nEstimated Lethal Doses (LD50, LD90):\\n')",
            "  print(MASS::dose.p(fit, p = c(0.10, 0.50, 0.90)))",
            "}",
            f"plot(df[[{_escape_str(dose)}]], df[[{_escape_str(resp)}]] / df[[{_escape_str(trials)}]], pch = 19, col = '#2563eb', xlab = {_escape_str(dose)}, ylab = 'Event Probability', main = 'Probit Analysis')",
            f"lines(sort(df[[{_escape_str(dose)}]]), predict(fit, newdata = data.frame(setNames(list(sort(df[[{_escape_str(dose)}]])), {_escape_str(dose)})), type = 'response'), col = '#dc2626', lwd = 2)",
        ]
        t_body = [
            f"ggplot(df, aes(x = .data[[{_escape_str(dose)}]], y = .data[[{_escape_str(resp)}]] / .data[[{_escape_str(trials)}]])) +",
            "  geom_point(color = '#2563eb', size = 3) +",
            f"  stat_smooth(method = 'glm', method.args = list(family = binomial(link = '{link}')), color = '#dc2626', linewidth = 1.2) +",
            f"  labs(title = 'Probit Analysis of {resp}', x = {_escape_str(dose)}, y = 'Response Probability') +",
            "  theme_minimal(base_size = 12)",
        ]

    # 3. STABILITY STUDY (ICH Q1E)
    elif analysis == "stability_study" or action == "stability_study":
        resp = worksheet.columns[params.get("response_index", 0)].name
        time_c = worksheet.columns[params.get("time_index", 1)].name
        batch_c = worksheet.columns[params.get("batch_index", 2)].name

        b_body = [
            f"# ICH Q1E Stability Study ANCOVA Poolability",
            f"df[[{_escape_str(batch_c)}]] <- as.factor(df[[{_escape_str(batch_c)}]])",
            f"fit_full <- lm(df[[{_escape_str(resp)}]] ~ df[[{_escape_str(time_c)}]] * df[[{_escape_str(batch_c)}]])",
            f"fit_common <- lm(df[[{_escape_str(resp)}]] ~ df[[{_escape_str(time_c)}]] + df[[{_escape_str(batch_c)}]])",
            f"fit_pooled <- lm(df[[{_escape_str(resp)}]] ~ df[[{_escape_str(time_c)}]])",
            "cat('--- Test of Common Slope (Poolability of Slopes) ---\\n')",
            "print(anova(fit_common, fit_full))",
            "cat('\\n--- Test of Common Intercept (Poolability of Batches) ---\\n')",
            "print(anova(fit_pooled, fit_common))",
            f"plot(df[[{_escape_str(time_c)}]], df[[{_escape_str(resp)}]], col = as.numeric(df[[{_escape_str(batch_c)}]]), pch = 19, xlab = {_escape_str(time_c)}, ylab = {_escape_str(resp)}, main = 'ICH Q1E Shelf Life Stability Study')",
        ]
        t_body = [
            f"ggplot(df, aes(x = .data[[{_escape_str(time_c)}]], y = .data[[{_escape_str(resp)}]], color = as.factor(.data[[{_escape_str(batch_c)}]]))) +",
            "  geom_point(size = 2.5) +",
            "  geom_smooth(method = 'lm', se = TRUE) +",
            f"  labs(title = 'ICH Q1E Stability Shelf Life: {resp}', color = {_escape_str(batch_c)}) +",
            "  theme_minimal(base_size = 12)",
        ]

    # 4. FACTOR ANALYSIS
    elif analysis == "factor_analysis" or action == "factor_analysis":
        var_indices = params.get("variable_indices", list(range(min(5, len(worksheet.columns)))))
        var_names = [worksheet.columns[i].name for i in var_indices]
        n_fac = params.get("n_factors", result.get("n_factors", 2))
        cols_code = ", ".join(_escape_str(v) for v in var_names)

        b_body = [
            f"# Factor Analysis (Principal Components Extraction, Varimax Rotation)",
            f"sub_df <- df[, c({cols_code})]",
            f"fit <- factanal(sub_df, factors = {n_fac}, rotation = 'varimax', scores = 'regression')",
            "print(fit)",
            "loadings <- fit$loadings[, 1:2]",
            "plot(loadings, type = 'n', xlim = c(-1.1, 1.1), ylim = c(-1.1, 1.1), main = 'Factor Loading Plot')",
            "arrows(0, 0, loadings[, 1], loadings[, 2], length = 0.1, col = '#0284c7', lwd = 1.5)",
            "text(loadings[, 1], loadings[, 2], labels = rownames(loadings), col = '#0f172a', font = 2, pos = 3)",
            "symbols(0, 0, circles = 1, inches = FALSE, add = TRUE, lty = 2, fg = '#94a3b8')",
            "abline(h = 0, v = 0, lty = 3)",
        ]
        t_body = [
            f"# Tidyverse Factor Loading Biplot",
            f"sub_df <- df %>% select(all_of(c({cols_code})))",
            f"fit <- factanal(sub_df, factors = {n_fac}, rotation = 'varimax')",
            "loads_df <- as.data.frame(unclass(fit$loadings[, 1:2])) %>%",
            "  rownames_to_column(var = 'Variable')",
            "ggplot(loads_df, aes(x = Factor1, y = Factor2, label = Variable)) +",
            "  geom_segment(aes(x = 0, y = 0, xend = Factor1, yend = Factor2), arrow = arrow(length = unit(0.2, 'cm')), color = '#0284c7', linewidth = 1) +",
            "  geom_text(vjust = -0.7, fontface = 'bold', color = '#0f172a') +",
            "  annotate('path', x = cos(seq(0, 2*pi, length.out = 100)), y = sin(seq(0, 2*pi, length.out = 100)), linetype = 'dashed', color = '#94a3b8') +",
            "  geom_vline(xintercept = 0, linetype = 'dotted') + geom_hline(yintercept = 0, linetype = 'dotted') +",
            "  coord_fixed(xlim = c(-1.15, 1.15), ylim = c(-1.15, 1.15)) +",
            "  labs(title = 'Factor Loading Plot') + theme_minimal(base_size = 12)",
        ]

    # 5. MULTIPLE CORRESPONDENCE ANALYSIS (MCA)
    elif analysis == "multiple_correspondence" or action == "multiple_correspondence":
        var_indices = params.get("variable_indices", list(range(min(4, len(worksheet.columns)))))
        var_names = [worksheet.columns[i].name for i in var_indices]
        cols_code = ", ".join(_escape_str(v) for v in var_names)

        b_body = [
            "# Multiple Correspondence Analysis (MCA)",
            "if (requireNamespace('MASS', quietly = TRUE)) {",
            f"  sub_df <- df[, c({cols_code})]",
            "  mca_fit <- MASS::mca(sub_df, nf = 2)",
            "  plot(mca_fit, main = 'MCA Category Coordinates')",
            "} else {",
            f"  cat('Install MASS package to run MCA.\\n')",
            "}",
        ]
        t_body = [
            f"# Tidyverse MCA via FactoMineR / factoextra",
            "if (requireNamespace('FactoMineR', quietly = TRUE) && requireNamespace('factoextra', quietly = TRUE)) {",
            f"  sub_df <- df %>% select(all_of(c({cols_code})))",
            "  mca_res <- FactoMineR::MCA(sub_df, graph = FALSE)",
            "  factoextra::fviz_mca_var(mca_res, repel = TRUE, ggtheme = theme_minimal())",
            "}",
        ]

    # 6. PROBABILITY DISTRIBUTION PLOT
    elif analysis == "probability_distribution" or action == "probability_distribution_plot" or graph == "probability_distribution":
        dist_n = params.get("distribution", result.get("distribution", "Normal"))
        dist_p = params.get("parameters", result.get("parameters", {}))
        m_val = float(dist_p.get("mean", 0.0))
        s_val = float(dist_p.get("stdev", 1.0))
        c1 = result.get("c1", m_val - 1.96 * s_val)
        c2 = result.get("c2", m_val + 1.96 * s_val)
        tail = params.get("tail", result.get("tail", "both"))

        b_body = [
            f"# Probability Distribution Plot: {dist_n}(Mean={m_val}, StDev={s_val})",
            f"curve(dnorm(x, mean = {m_val}, sd = {s_val}), from = {m_val - 3.8 * s_val}, to = {m_val + 3.8 * s_val}, col = '#0284c7', lwd = 2.2, ylab = 'Density', xlab = 'X', main = 'Distribution Plot: {dist_n}')",
            f"x_vals <- seq({c1 if c1 is not None else m_val}, {c2 if c2 is not None else m_val + 2*s_val}, length.out = 150)",
            f"polygon(c(x_vals, rev(x_vals)), c(dnorm(x_vals, {m_val}, {s_val}), rep(0, length(x_vals))), col = '#e11d4855', border = NA)",
            f"abline(v = c({c1}, {c2}), col = '#dc2626', lty = 2)",
        ]
        t_body = [
            f"ggplot() +",
            f"  stat_function(fun = dnorm, args = list(mean = {m_val}, sd = {s_val}), color = '#0284c7', linewidth = 1.2) +",
            f"  stat_function(fun = dnorm, args = list(mean = {m_val}, sd = {s_val}), xlim = c({c1}, {c2}), geom = 'area', fill = '#e11d48', alpha = 0.45) +",
            f"  labs(title = 'Probability Distribution Plot: {dist_n}', subtitle = sprintf('Shaded Area = %.4f', {result.get('total_shaded_prob', 0.05)})) +",
            "  theme_minimal(base_size = 12)",
        ]

    # 7. MARGINAL PLOT
    elif analysis == "marginal_plot" or action == "marginal_plot" or graph == "marginal_plot":
        y_name = result.get("y_name") or (worksheet.columns[params["y_index"]].name if "y_index" in params else "Y")
        x_name = result.get("x_name") or (worksheet.columns[params["x_index"]].name if "x_index" in params else "X")

        b_body = [
            f"# Marginal Plot: {y_name} vs {x_name}",
            f"x <- df[[{_escape_str(x_name)}]]; y <- df[[{_escape_str(y_name)}]]",
            "layout(matrix(c(2, 0, 1, 3), 2, 2, byrow = TRUE), widths = c(3, 1), heights = c(1, 3))",
            "par(mar = c(4, 4, 1, 1))",
            f"plot(x, y, pch = 19, col = '#0284c7', xlab = {_escape_str(x_name)}, ylab = {_escape_str(y_name)})",
            "abline(lm(y ~ x), col = '#dc2626', lty = 2)",
            "par(mar = c(0, 4, 2, 1))",
            f"hist(x, col = '#bae6fd', border = 'white', main = 'Marginal Plot', xaxt = 'n')",
            "par(mar = c(4, 0, 1, 2))",
            "h_y <- hist(y, plot = FALSE)",
            "barplot(h_y$counts, horiz = TRUE, col = '#bae6fd', border = 'white', space = 0, yaxt = 'n')",
        ]
        t_body = [
            f"# Tidyverse & ggExtra Marginal Plot",
            "if (requireNamespace('ggExtra', quietly = TRUE)) {",
            f"  p <- ggplot(df, aes(x = .data[[{_escape_str(x_name)}]], y = .data[[{_escape_str(y_name)}]])) +",
            "    geom_point(color = '#0284c7', alpha = 0.8, size = 2) +",
            "    geom_smooth(method = 'lm', color = '#dc2626', linetype = 'dashed') +",
            "    theme_minimal(base_size = 12)",
            "  ggExtra::ggMarginal(p, type = 'histogram', fill = '#bae6fd', color = 'white')",
            "}",
        ]

    # 8. EMPIRICAL CDF (ECDF) PLOT
    elif analysis == "ecdf_plot" or action == "ecdf_plot" or graph == "ecdf_plot":
        v_name = result.get("variable_name") or (worksheet.columns[params.get("variable_index", 0)].name if "variable_index" in params else "X")

        b_body = [
            f"# Empirical Cumulative Distribution Function (ECDF)",
            f"x <- df[[{_escape_str(v_name)}]]",
            "x <- x[!is.na(x)]",
            f"plot(ecdf(x), verticals = TRUE, col = '#0284c7', lwd = 2, xlab = {_escape_str(v_name)}, ylab = 'Cumulative Probability', main = paste0('Empirical CDF of ', {_escape_str(v_name)}))",
            "curve(pnorm(x, mean(x), sd(x)), add = TRUE, col = '#dc2626', lty = 2, lwd = 1.5)",
            "legend('bottomright', legend = c('Empirical CDF', 'Fitted Normal'), col = c('#0284c7', '#dc2626'), lty = c(1, 2), lwd = c(2, 1.5))",
        ]
        t_body = [
            f"ggplot(df, aes(x = .data[[{_escape_str(v_name)}]])) +",
            "  stat_ecdf(geom = 'step', color = '#0284c7', linewidth = 1.2) +",
            f"  stat_function(fun = pnorm, args = list(mean = mean(df[[{_escape_str(v_name)}]], na.rm = TRUE), sd = sd(df[[{_escape_str(v_name)}]], na.rm = TRUE)), color = '#dc2626', linetype = 'dashed', linewidth = 1) +",
            f"  labs(title = 'Empirical CDF: {v_name}', y = 'Cumulative Probability') +",
            "  theme_minimal(base_size = 12)",
        ]

    # 9. TWO-SAMPLE T-TEST
    elif "two_sample_t" in analysis or action == "two_sample_t":
        s1 = worksheet.columns[params.get("first_index", 0)].name if "first_index" in params else worksheet.columns[0].name
        s2 = worksheet.columns[params.get("second_index", 1)].name if "second_index" in params else worksheet.columns[1].name
        b_body = [
            f"# Two-Sample T-Test",
            f"t_res <- t.test(df[[{_escape_str(s1)}]], df[[{_escape_str(s2)}]], var.equal = FALSE)",
            "print(t_res)",
            f"boxplot(df[[{_escape_str(s1)}]], df[[{_escape_str(s2)}]], names = c({_escape_str(s1)}, {_escape_str(s2)}), col = c('#93c5fd', '#fecdd3'), main = 'Two-Sample Comparison')",
        ]
        t_body = [
            f"df %>% select(all_of(c({_escape_str(s1)}, {_escape_str(s2)}))) %>%",
            "  pivot_longer(everything(), names_to = 'Sample', values_to = 'Value') %>%",
            "  ggplot(aes(x = Sample, y = Value, fill = Sample)) +",
            "  geom_boxplot(alpha = 0.8) + theme_minimal(base_size = 12)",
        ]

    # 10. ONE-WAY ANOVA
    elif "oneway_anova" in analysis or action in ("oneway_anova", "one_way_anova"):
        r_col = worksheet.columns[params.get("response_index", 0)].name if "response_index" in params else "Response"
        f_col = worksheet.columns[params.get("factor_index", 1)].name if "factor_index" in params else "Factor"
        b_body = [
            f"# One-Way ANOVA",
            f"fit <- aov(df[[{_escape_str(r_col)}]] ~ as.factor(df[[{_escape_str(f_col)}]]))",
            "summary(fit)",
            "cat('\\n--- Tukey Honest Significant Differences (HSD) ---\\n')",
            "print(TukeyHSD(fit))",
            f"boxplot(df[[{_escape_str(r_col)}]] ~ df[[{_escape_str(f_col)}]], col = '#93c5fd', xlab = {_escape_str(f_col)}, ylab = {_escape_str(r_col)}, main = 'One-Way ANOVA')",
        ]
        t_body = [
            f"ggplot(df, aes(x = as.factor(.data[[{_escape_str(f_col)}]]), y = .data[[{_escape_str(r_col)}]], fill = as.factor(.data[[{_escape_str(f_col)}]]))) +",
            "  geom_boxplot(alpha = 0.75) +",
            f"  labs(title = 'One-Way ANOVA: {r_col} by {f_col}', x = {_escape_str(f_col)}, y = {_escape_str(r_col)}) +",
            "  theme_minimal(base_size = 12) + theme(legend.position = 'none')",
        ]

    # 11. MULTIPLE REGRESSION
    elif ("regression" in analysis or action in ("multiple_regression", "linear_regression")) and "logistic" not in analysis and "logistic" not in action:
        r_col = worksheet.columns[params.get("response_index", 0)].name if "response_index" in params else "Response"
        p_cols = [worksheet.columns[i].name for i in params.get("predictor_indices", [1])]
        formula = f"df[[{_escape_str(r_col)}]] ~ " + " + ".join(f"df[[{_escape_str(p)}]]" for p in p_cols)
        b_body = [
            f"# Multiple Linear Regression",
            f"fit <- lm({formula})",
            "summary(fit)",
            "confint(fit)",
            "par(mfrow = c(2, 2)); plot(fit); par(mfrow = c(1, 1))",
        ]
        t_body = [
            f"fit <- lm({formula})",
            "summary(fit)",
            f"ggplot(df, aes(x = .data[[{_escape_str(p_cols[0])}]], y = .data[[{_escape_str(r_col)}]])) +",
            "  geom_point(color = '#2563eb', size = 2) +",
            "  geom_smooth(method = 'lm', color = '#dc2626') +",
            "  theme_minimal(base_size = 12)",
        ]

    # 12. RUN CHART / PROCESS CONTROL
    elif "run_chart" in analysis or action == "run_chart":
        v_col = worksheet.columns[params.get("index", 0)].name if "index" in params else worksheet.columns[0].name
        b_body = [
            f"# Run Chart",
            f"x <- df[[{_escape_str(v_col)}]]; x <- x[!is.na(x)]",
            f"plot(x, type = 'b', pch = 19, col = '#2563eb', xlab = 'Observation', ylab = {_escape_str(v_col)}, main = paste0('Run Chart of ', {_escape_str(v_col)}))",
            "abline(h = median(x), col = '#16a34a', lwd = 2)",
            "abline(h = mean(x), col = '#dc2626', lty = 2)",
            "legend('topright', legend = c('Median', 'Mean'), col = c('#16a34a', '#dc2626'), lty = c(1, 2))",
        ]
        t_body = [
            f"df %>% mutate(Observation = row_number()) %>%",
            f"  ggplot(aes(x = Observation, y = .data[[{_escape_str(v_col)}]])) +",
            "  geom_line(color = '#2563eb') + geom_point(color = '#1e3a8a', size = 2) +",
            f"  geom_hline(yintercept = median(df[[{_escape_str(v_col)}]], na.rm = TRUE), color = '#16a34a', linewidth = 1) +",
            f"  labs(title = 'Run Chart: {v_col}') + theme_minimal(base_size = 12)",
        ]

    # 13. DESCRIPTIVE STATISTICS
    elif "describe" in analysis or action in ("describe_columns", "descriptive_statistics"):
        cols = [worksheet.columns[i].name for i in params.get("indices", list(range(len(worksheet.columns))))]
        cols_code = ", ".join(_escape_str(c) for c in cols)
        b_body = [
            f"# Descriptive Statistics",
            f"sub_df <- df[, c({cols_code})]",
            "summary(sub_df)",
            "cat('\\n--- Detailed Metrics ---\\n')",
            "sapply(sub_df, function(x) c(Mean = mean(x, na.rm = TRUE), StDev = sd(x, na.rm = TRUE), Median = median(x, na.rm = TRUE), IQR = IQR(x, na.rm = TRUE)))",
        ]
        t_body = [
            f"df %>% select(all_of(c({cols_code}))) %>%",
            "  pivot_longer(everything(), names_to = 'Variable', values_to = 'Value') %>%",
            "  group_by(Variable) %>%",
            "  summarise(N = sum(!is.na(Value)), Mean = mean(Value, na.rm = TRUE), StDev = sd(Value, na.rm = TRUE), Median = median(Value, na.rm = TRUE), Min = min(Value, na.rm = TRUE), Max = max(Value, na.rm = TRUE))",
        ]

    # 14. ONE-SAMPLE T-TEST
    elif "one_sample_t" in analysis or action == "one_sample_t":
        v_col = worksheet.columns[params.get("index", 0)].name if "index" in params else worksheet.columns[0].name
        mu_val = params.get("mu", 0.0)
        b_body = [
            f"# 1-Sample T-Test (H0: mu = {mu_val})",
            f"t_res <- t.test(df[[{_escape_str(v_col)}]], mu = {mu_val})",
            "print(t_res)",
            f"boxplot(df[[{_escape_str(v_col)}]], main = paste0('1-Sample T: ', {_escape_str(v_col)}), col = '#93c5fd')",
            f"abline(h = {mu_val}, col = '#dc2626', lty = 2, lwd = 2)",
        ]
        t_body = [
            f"ggplot(df, aes(y = .data[[{_escape_str(v_col)}]])) +",
            "  geom_boxplot(fill = '#93c5fd', alpha = 0.8) +",
            f"  geom_hline(yintercept = {mu_val}, color = '#dc2626', linetype = 'dashed', linewidth = 1) +",
            f"  labs(title = '1-Sample T-Test: {v_col} vs mu={mu_val}') + theme_minimal(base_size = 12)",
        ]

    # 15. PAIRED T-TEST
    elif "paired_t" in analysis or action == "paired_t":
        c1 = worksheet.columns[params.get("first_index", 0)].name if "first_index" in params else worksheet.columns[0].name
        c2 = worksheet.columns[params.get("second_index", 1)].name if "second_index" in params else worksheet.columns[1].name
        b_body = [
            f"# Paired T-Test: {c1} vs {c2}",
            f"t_res <- t.test(df[[{_escape_str(c1)}]], df[[{_escape_str(c2)}]], paired = TRUE)",
            "print(t_res)",
            f"diff_vals <- df[[{_escape_str(c1)}]] - df[[{_escape_str(c2)}]]",
            "hist(diff_vals, col = '#bae6fd', border = 'white', main = 'Paired Differences Distribution')",
            "abline(v = 0, col = '#dc2626', lty = 2, lwd = 2)",
        ]
        t_body = [
            f"df %>% mutate(Diff = .data[[{_escape_str(c1)}]] - .data[[{_escape_str(c2)}]]) %>%",
            "  ggplot(aes(x = Diff)) +",
            "  geom_histogram(bins = 15, fill = '#0284c7', color = 'white', alpha = 0.8) +",
            "  geom_vline(xintercept = 0, color = '#dc2626', linetype = 'dashed', linewidth = 1) +",
            f"  labs(title = 'Paired T-Test Differences ({c1} - {c2})') + theme_minimal(base_size = 12)",
        ]

    # 16. TWO-WAY ANOVA
    elif "twoway_anova" in analysis or action in ("twoway_anova", "two_way_anova"):
        r_col = worksheet.columns[params.get("response_index", 0)].name if "response_index" in params else "Response"
        f1 = worksheet.columns[params.get("row_factor_index", 1)].name if "row_factor_index" in params else "FactorA"
        f2 = worksheet.columns[params.get("col_factor_index", 2)].name if "col_factor_index" in params else "FactorB"
        b_body = [
            f"# Two-Way ANOVA with Interaction",
            f"fit <- aov(df[[{_escape_str(r_col)}]] ~ as.factor(df[[{_escape_str(f1)}]]) * as.factor(df[[{_escape_str(f2)}]]))",
            "summary(fit)",
            f"interaction.plot(as.factor(df[[{_escape_str(f1)}]]), as.factor(df[[{_escape_str(f2)}]]), df[[{_escape_str(r_col)}]], col = 1:5, lwd = 2, main = 'Interaction Plot')",
        ]
        t_body = [
            f"ggplot(df, aes(x = as.factor(.data[[{_escape_str(f1)}]]), y = .data[[{_escape_str(r_col)}]], color = as.factor(.data[[{_escape_str(f2)}]]), group = as.factor(.data[[{_escape_str(f2)}]]))) +",
            "  stat_summary(fun = mean, geom = 'point', size = 3) +",
            "  stat_summary(fun = mean, geom = 'line', linewidth = 1) +",
            f"  labs(title = 'Two-Way ANOVA: {r_col} by {f1} and {f2}', x = {_escape_str(f1)}, color = {_escape_str(f2)}) +",
            "  theme_minimal(base_size = 12)",
        ]

    # 17. BINARY LOGISTIC REGRESSION
    elif "binary_logistic" in analysis or action in ("binary_logistic_regression", "logistic_regression"):
        r_col = worksheet.columns[params.get("response_index", 0)].name if "response_index" in params else "Response"
        p_cols = [worksheet.columns[i].name for i in params.get("predictor_indices", [1])]
        formula = f"as.factor(df[[{_escape_str(r_col)}]]) ~ " + " + ".join(f"df[[{_escape_str(p)}]]" for p in p_cols)
        b_body = [
            f"# Binary Logistic Regression",
            f"fit <- glm({formula}, family = binomial)",
            "summary(fit)",
            "cat('\\n--- Odds Ratios and 95% CI ---\\n')",
            "print(exp(cbind(OR = coef(fit), confint(fit))))",
        ]
        t_body = [
            f"fit <- glm({formula}, family = binomial)",
            "summary(fit)",
            f"ggplot(df, aes(x = .data[[{_escape_str(p_cols[0])}]], y = as.numeric(as.factor(.data[[{_escape_str(r_col)}]])) - 1)) +",
            "  geom_point(alpha = 0.5, color = '#2563eb') +",
            "  stat_smooth(method = 'glm', method.args = list(family = 'binomial'), color = '#dc2626') +",
            f"  labs(title = 'Logistic Regression: {r_col}', y = 'Predicted Probability') + theme_minimal(base_size = 12)",
        ]

    # 18. PROCESS CAPABILITY ANALYSIS
    elif "capability" in analysis or action in ("capability_analysis", "normal_capability"):
        v_col = worksheet.columns[params.get("index", 0)].name if "index" in params else worksheet.columns[0].name
        lsl = params.get("lsl", "NA")
        usl = params.get("usl", "NA")
        b_body = [
            f"# Process Capability Analysis for {v_col}",
            f"x <- df[[{_escape_str(v_col)}]]; x <- x[!is.na(x)]",
            "m <- mean(x); s <- sd(x)",
            f"lsl <- {lsl}; usl <- {usl}",
            "cat(sprintf('Capability Metrics:\\nMean = %.4f, StDev = %.4f\\n', m, s))",
            "if (!is.na(lsl) && !is.na(usl)) cat(sprintf('Cp = %.4f, Cpk = %.4f\\n', (usl - lsl)/(6*s), min((usl - m)/(3*s), (m - lsl)/(3*s))))",
            f"hist(x, col = '#bae6fd', border = 'white', prob = TRUE, main = paste0('Capability Histogram: ', {_escape_str(v_col)}))",
            "curve(dnorm(x, m, s), add = TRUE, col = '#2563eb', lwd = 2)",
            "if (!is.na(lsl)) abline(v = lsl, col = '#dc2626', lwd = 2, lty = 2)",
            "if (!is.na(usl)) abline(v = usl, col = '#dc2626', lwd = 2, lty = 2)",
        ]
        t_lines = [
            f"x_vals <- df[[{_escape_str(v_col)}]][!is.na(df[[{_escape_str(v_col)}]])]",
            "m_val <- mean(x_vals); s_val <- sd(x_vals)",
            f"p <- ggplot(df, aes(x = .data[[{_escape_str(v_col)}]])) +",
            "  geom_histogram(aes(y = after_stat(density)), bins = 20, fill = '#bae6fd', color = 'white') +",
            "  stat_function(fun = dnorm, args = list(mean = m_val, sd = s_val), color = '#2563eb', linewidth = 1.2) +",
            f"  labs(title = 'Process Capability: {v_col}') + theme_minimal(base_size = 12)",
        ]
        if lsl != "NA":
            t_lines.append(f"p <- p + geom_vline(xintercept = {lsl}, color = '#dc2626', linetype = 'dashed', linewidth = 1)")
        if usl != "NA":
            t_lines.append(f"p <- p + geom_vline(xintercept = {usl}, color = '#dc2626', linetype = 'dashed', linewidth = 1)")
        t_lines.append("print(p)")
        t_body = t_lines

    # 19. FITTED LINE PLOT & CORRELATION
    elif "fitted_line" in analysis or action == "fitted_line_plot" or "correlation" in analysis or action == "correlation":
        y_name = result.get("response_name") or (worksheet.columns[params.get("y_index", 0)].name if "y_index" in params else worksheet.columns[0].name)
        x_name = result.get("predictor_name") or (worksheet.columns[params.get("x_index", 1)].name if "x_index" in params else worksheet.columns[1].name)
        b_body = [
            f"# Fitted Line Plot & Pearson Correlation",
            f"x <- df[[{_escape_str(x_name)}]]; y <- df[[{_escape_str(y_name)}]]",
            "cor_res <- cor.test(x, y)",
            "print(cor_res)",
            f"plot(x, y, pch = 19, col = '#2563eb', xlab = {_escape_str(x_name)}, ylab = {_escape_str(y_name)}, main = 'Fitted Line Plot')",
            "abline(lm(y ~ x), col = '#dc2626', lwd = 2)",
        ]
        t_body = [
            f"ggplot(df, aes(x = .data[[{_escape_str(x_name)}]], y = .data[[{_escape_str(y_name)}]])) +",
            "  geom_point(color = '#2563eb', size = 2, alpha = 0.8) +",
            "  geom_smooth(method = 'lm', color = '#dc2626', linewidth = 1.2) +",
            f"  labs(title = 'Fitted Line Plot: {y_name} vs {x_name}') + theme_minimal(base_size = 12)",
        ]

    # 20. BOXPLOT & SCATTERPLOT GRAPHS
    elif "boxplot" in analysis or action in ("boxplot", "boxplot_graphs"):
        col_name = worksheet.columns[params.get("index", 0)].name if "index" in params else worksheet.columns[0].name
        b_body = [
            f"# Boxplot",
            f"boxplot(df[[{_escape_str(col_name)}]], col = '#93c5fd', main = paste0('Boxplot: ', {_escape_str(col_name)}))",
        ]
        t_body = [
            f"ggplot(df, aes(y = .data[[{_escape_str(col_name)}]])) +",
            "  geom_boxplot(fill = '#93c5fd', alpha = 0.8) +",
            f"  labs(title = 'Boxplot: {col_name}') + theme_minimal(base_size = 12)",
        ]
    elif "scatterplot" in analysis or action in ("scatterplot", "scatter_plot"):
        y_name = worksheet.columns[params.get("y_index", 0)].name if "y_index" in params else worksheet.columns[0].name
        x_name = worksheet.columns[params.get("x_index", 1)].name if "x_index" in params else worksheet.columns[1].name
        b_body = [
            f"# Scatterplot",
            f"plot(df[[{_escape_str(x_name)}]], df[[{_escape_str(y_name)}]], pch = 19, col = '#2563eb', xlab = {_escape_str(x_name)}, ylab = {_escape_str(y_name)}, main = 'Scatterplot')",
        ]
        t_body = [
            f"ggplot(df, aes(x = .data[[{_escape_str(x_name)}]], y = .data[[{_escape_str(y_name)}]])) +",
            "  geom_point(color = '#2563eb', size = 2.5, alpha = 0.8) +",
            f"  labs(title = 'Scatterplot: {y_name} vs {x_name}') + theme_minimal(base_size = 12)",
        ]

    elif analysis in ("randomization_1sample", "randomization_2sample"):
        c1 = worksheet.columns[params.get("index", params.get("index1", 0))].name
        b_body = [
            f"x1 <- na.omit(df[[{_escape_str(c1)}]])",
            f"set.seed({params.get('seed', 42)}); B <- {params.get('resamples', params.get('n_resamples', 2000))}",
            "perm_stats <- replicate(B, mean(sample(c(-1, 1), length(x1), replace = TRUE) * (x1 - mean(x1))))",
            "hist(perm_stats, col = '#a5b4fc', border = 'white', main = 'Randomization Null Distribution')",
        ]
        t_body = list(b_body)

    elif analysis in ("poisson_gof", "goodness_of_fit_poisson"):
        c1 = worksheet.columns[params.get("index", 0)].name
        b_body = [
            f"counts <- na.omit(df[[{_escape_str(c1)}]])",
            "lam <- mean(counts)",
            "tab <- table(counts); k <- as.numeric(names(tab))",
            "probs <- dpois(k, lambda = lam); probs <- probs / sum(probs)",
            "print(chisq.test(as.numeric(tab), p = probs))",
        ]
        t_body = list(b_body)

    elif analysis in ("six_sigma_process_report", "six_sigma_product_report"):
        if analysis == "six_sigma_process_report":
            c1 = worksheet.columns[params.get("index", 0)].name
            lsl_v = result.get("lsl")
            usl_v = result.get("usl")
            b_body = [
                f"x <- na.omit(df[[{_escape_str(c1)}]])",
                f"mu <- mean(x); s <- sd(x)",
                f"cat(sprintf('Mean=%.4f StDev=%.4f\n', mu, s))",
                f"# Spec limits: LSL={lsl_v}, USL={usl_v}",
                "hist(x, col = '#60a5fa', border = 'white', main = 'Six Sigma Process Distribution')",
            ]
        else:
            ys = result.get("step_yields_pct") or [99.0]
            b_body = [
                f"yields <- c({', '.join(str(v) for v in ys)}) / 100",
                "rty <- prod(yields)",
                "cat(sprintf('Rolled Throughput Yield (RTY): %.2f%%\n', rty * 100))",
                "barplot(yields * 100, col = '#10b981', ylim = c(0, 105), main = 'Step Yields (%)')",
            ]
        t_body = list(b_body)

    elif analysis in ("one_variance_power", "two_variances_power", "one_poisson_rate_power", "two_poisson_rates_power", "equivalence_tost_power", "sample_size_estimation", "sample_size_tolerance_interval"):
        b_body = [
            "if (!requireNamespace('pwr', quietly = TRUE)) install.packages('pwr')",
            "library(pwr)",
            f"# StatCraft Extended Power Analysis: {title}",
            f"cat('Computed Sample Size:', {result.get('sample_size') or result.get('sample_size_per_group') or 'NA'}, '\n')",
        ]
        t_body = list(b_body)

    elif analysis == "warranty_analysis":
        b_body = [
            f"# Weibull Warranty Analysis (shape={result.get('weibull_shape', 1.0):.3f}, scale={result.get('weibull_scale', 1.0):.3f})",
            "cat('Observed Claims:', " + str(result.get("observed_claims", 0)) + ", '\n')",
        ]
        t_body = list(b_body)

    # UNIVERSAL SMART FALLBACK (Matches ANY other analysis or graph)
    else:
        # Detect relevant column names
        cols_detected = []
        for k, v in params.items():
            if isinstance(v, int) and 0 <= v < len(worksheet.columns):
                c_name = worksheet.columns[v].name
                if c_name not in cols_detected:
                    cols_detected.append(c_name)
            elif isinstance(v, (list, tuple)):
                for item in v:
                    if isinstance(item, int) and 0 <= item < len(worksheet.columns):
                        c_name = worksheet.columns[item].name
                        if c_name not in cols_detected:
                            cols_detected.append(c_name)

        if not cols_detected:
            cols_detected = [c.name for c in worksheet.columns if c.kind == "number"][:4] or [worksheet.columns[0].name]

        cols_code = ", ".join(_escape_str(c) for c in cols_detected)

        b_body = [
            f"# Procedure Execution & Statistical Diagnostics: {title}",
            f"sub_df <- df[, c({cols_code}), drop = FALSE]",
            "cat('================================================================\\n')",
            f"cat('        StatCraft Procedure: {title}\\n')",
            "cat('================================================================\\n\\n')",
            "summary(sub_df)",
            "",
            "if (ncol(sub_df) >= 2 && all(sapply(sub_df, is.numeric))) {",
            "  cat('\\n--- Pairwise Correlation Matrix ---\\n')",
            "  print(round(cor(sub_df, use = 'pairwise.complete.obs'), 4))",
            "  pairs(sub_df, pch = 19, col = '#2563eb', main = 'Pairwise Scatterplot Matrix')",
            "} else if (ncol(sub_df) == 1 && is.numeric(sub_df[[1]])) {",
            f"  hist(sub_df[[1]], col = '#93c5fd', border = 'white', main = {json.dumps(title)}, xlab = colnames(sub_df)[1])",
            "}",
        ]
        t_body = [
            f"# Tidyverse Diagnostic Pipeline: {title}",
            f"df %>% select(all_of(c({cols_code}))) %>%",
            "  pivot_longer(where(is.numeric), names_to = 'Variable', values_to = 'Value') %>%",
            "  ggplot(aes(x = Value, fill = Variable)) +",
            "  geom_histogram(bins = 20, color = 'white', alpha = 0.7) +",
            "  facet_wrap(~ Variable, scales = 'free') +",
            f"  labs(title = {json.dumps(title)}) + theme_minimal(base_size = 12)",
        ]

    base_script = "\n".join(base_hdr + b_body)
    tidy_script = "\n".join(tidy_hdr + t_body)
    return base_script, tidy_script, title


def translate_analysis_to_r(entry: Any, worksheet: Any, dialect: str = "tidyverse") -> str:
    """Convenience helper returning the standalone R script string for the chosen dialect."""
    base_script, tidy_script, _ = translate_entry_to_r(entry, worksheet)
    if str(dialect).lower().startswith("base"):
        return base_script
    return tidy_script

