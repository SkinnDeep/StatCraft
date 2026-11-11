"""Native Qt Report Table Sections Builder for Phases 3-7 Analyses.

Provides `sections(result) -> List[Tuple[str, List[str], List[List[Any]]]]`
matching the exact contract consumed by `ModernWindow.show_result`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

Section = Tuple[str, List[str], List[List[Any]]]

PHASE6_REPORT_ANALYSES = {
    "random_forest",
    "treenet_gbm",
    "mars_regression",
    "discover_best_model",
    "monte_carlo_simulation",
    "balanced_anova",
    "fully_nested_anova",
    "oneway_manova",
    "mixed_reml",
    "cox_ph_regression",
    "warranty_analysis",
    "poisson_gof",
    "negative_binomial_regression",
    "six_sigma_process_report",
    "six_sigma_product_report",
    "bootstrap_1sample",
    "bootstrap_2sample",
    "randomization_1sample",
    "randomization_2sample",
    "one_variance_power",
    "two_variances_power",
    "one_poisson_rate_power",
    "two_poisson_rates_power",
    "equivalence_tost_power",
    "sample_size_estimation",
    "sample_size_tolerance_interval",
}


def _fmt_num(val: Any, fmt: str = ".4g") -> Any:
    if isinstance(val, float):
        return f"{val:{fmt}}"
    return "" if val is None else val


def _dict_table_rows(d: Dict[str, Any]) -> List[List[Any]]:
    return [[k.replace("_", " ").title(), _fmt_num(v, ".5g")] for k, v in d.items() if not isinstance(v, (dict, list))]


def sections(result: Dict[str, Any]) -> List[Section]:
    """Convert structured Phase 3-7 analysis dictionaries into Qt report tables."""
    kind = result.get("analysis", "")
    out: List[Section] = []

    if kind == "random_forest":
        out.append(("Model Configuration", ["Setting", "Value"], [
            ["Response", result.get("response")],
            ["Task", str(result.get("task", "")).title()],
            ["N Observations", result.get("n")],
            ["Number of Trees", result.get("n_trees")],
            ["Features per Split (mtry)", result.get("mtry")],
            ["Max Tree Depth", result.get("max_depth")],
            ["OOB Samples Covered", result.get("oob_covered")],
        ]))
        if result.get("oob_metrics"):
            out.append(("Out-of-Bag (OOB) Performance", ["Metric", "Value"], _dict_table_rows(result["oob_metrics"])))
        if result.get("train_metrics"):
            out.append(("Training Set Performance", ["Metric", "Value"], _dict_table_rows(result["train_metrics"])))
        if result.get("variable_importance"):
            out.append(("Relative Variable Importance", ["Predictor", "Relative Importance (%)", "Raw Score"], [
                [r["predictor"], f"{r['relative_importance']:.2f}%", _fmt_num(r["raw_importance"])]
                for r in result["variable_importance"]
            ]))

    elif kind == "treenet_gbm":
        out.append(("TreeNet® Configuration", ["Setting", "Value"], [
            ["Response", result.get("response")],
            ["Task", str(result.get("task", "")).title()],
            ["Loss Function", result.get("loss")],
            ["Requested Trees", result.get("n_trees_requested")],
            ["Optimal Trees", result.get("optimal_trees")],
            ["Learning Rate", result.get("learning_rate")],
            ["Subsample Fraction", result.get("subsample")],
            ["Train / Val Split", f"{result.get('n_train')} / {result.get('n_val')}"],
        ]))
        if result.get("val_metrics"):
            out.append(("Validation Set Performance", ["Metric", "Value"], _dict_table_rows(result["val_metrics"])))
        if result.get("variable_importance"):
            out.append(("Relative Variable Importance", ["Predictor", "Relative Importance (%)", "Raw Score"], [
                [r["predictor"], f"{r['relative_importance']:.2f}%", _fmt_num(r["raw_importance"])]
                for r in result["variable_importance"]
            ]))

    elif kind == "mars_regression":
        summary = [
            ["Response", result.get("response")],
            ["Task", str(result.get("task", "")).title()],
            ["Observations (N)", result.get("n")],
            ["Selected Basis Terms", result.get("n_basis_terms")],
            ["GCV", _fmt_num(result.get("gcv"), ".6g")],
        ]
        if result.get("equation"):
            summary.append(["Equation", f"{result.get('response')} = {result['equation']}"])
        out.append(("MARS® Model Summary", ["Measure", "Value"], summary))
        if result.get("metrics"):
            out.append(("Fit & Cross-Validation Metrics", ["Metric", "Value"], _dict_table_rows(result["metrics"])))
        if result.get("basis_functions"):
            out.append(("Selected Basis Functions", ["Term", "Coefficient"], [
                [row["basis"], _fmt_num(row["coef"], ".6g")] for row in result["basis_functions"]
            ]))
        if result.get("variable_importance"):
            out.append(("GCV Predictor Importance", ["Predictor", "Relative Importance (%)"], [
                [r["predictor"], f"{r['relative_importance']:.2f}%"] for r in result["variable_importance"]
            ]))

    elif kind == "discover_best_model":
        out.append(("AutoML Benchmark Setup", ["Setting", "Value"], [
            ["Response", result.get("response")],
            ["Task", str(result.get("task", "")).title()],
            ["Train / Validation Rows", f"{result.get('n_train')} / {result.get('n_val')}"],
            ["Champion Model", result.get("champion_model")],
        ]))
        lb = result.get("leaderboard") or []
        if lb:
            if result.get("task") == "regression":
                out.append(("Model Leaderboard (Validation Holdout)", ["Rank", "Model", "Val R² (%)", "Val RMSE", "Val MAE", "Notes"], [
                    [r["rank"], r["model"], f"{r['val_r2'] * 100:.2f}%", _fmt_num(r["val_rmse"], ".4f"), _fmt_num(r["val_mae"], ".4f"), r["notes"]]
                    for r in lb
                ]))
            else:
                out.append(("Model Leaderboard (Validation Holdout)", ["Rank", "Model", "Val Accuracy (%)", "Log-Loss", "ROC AUC", "Notes"], [
                    [r["rank"], r["model"], f"{r['val_accuracy'] * 100:.2f}%", _fmt_num(r["val_log_loss"], ".4f"), _fmt_num(r.get("val_roc_auc"), ".4f"), r["notes"]]
                    for r in lb
                ]))

    elif kind == "monte_carlo_simulation":
        s = result.get("summary", {})
        cap = result.get("capability", {})
        out.append(("Simulation Output Summary", ["Metric", "Value"], [
            ["Transfer Equation", result.get("formula")],
            ["Iterations", result.get("n_sims")],
            ["Mean", _fmt_num(s.get("mean"), ".5g")],
            ["StDev", _fmt_num(s.get("stdev"), ".5g")],
            ["Median (Q1 – Q3)", f"{_fmt_num(s.get('median'), '.5g')} ({_fmt_num(s.get('q1'), '.5g')} – {_fmt_num(s.get('q3'), '.5g')})"],
            ["5th – 95th Percentile", f"[{_fmt_num(s.get('p05'), '.5g')}, {_fmt_num(s.get('p95'), '.5g')}]"],
            ["LSL / USL", f"{result.get('lsl')} / {result.get('usl')}"],
            ["% Out of Spec (DPMO)", f"{cap.get('pct_out_of_spec', 0):.3f}% ({cap.get('dpmo', 0):,.1f})"],
            ["Simulated Pp / Ppk", f"{_fmt_num(cap.get('pp'), '.3f')} / {_fmt_num(cap.get('ppk'), '.3f')}"],
        ]))
        if result.get("sensitivity"):
            out.append(("Sensitivity Tornado (Variance Contribution)", ["Input Variable", "Spearman ρ", "Variance Contrib (%)"], [
                [r["input"], f"{r['spearman_rho']:+.4f}", f"{r['variance_contribution_pct']:.2f}%"]
                for r in result["sensitivity"]
            ]))
        if result.get("tolerance_sweep"):
            out.append(("Tolerance-Tightening What-If Sweep", ["Scenario", "Output StDev", "Out of Spec (%)", "DPMO", "Ppk"], [
                [sw["scenario"], _fmt_num(sw["output_stdev"], ".4g"), f"{sw['pct_out_of_spec']:.3f}%", f"{sw['dpmo']:,.0f}", _fmt_num(sw.get("ppk"), ".3f")]
                for sw in result["tolerance_sweep"]
            ]))

    elif kind in ("balanced_anova", "fully_nested_anova"):
        headers = ["Source", "DF", "SS", "MS", "F-Value", "P-Value"]
        if kind == "fully_nested_anova":
            headers.extend(["Var Comp", "% Total"])
        rows_data: List[List[Any]] = []
        for r in result.get("rows", []):
            row = [r.get("source"), r.get("df"), _fmt_num(r.get("ss")), _fmt_num(r.get("ms")), _fmt_num(r.get("f_value")), _fmt_num(r.get("p_value"))]
            if kind == "fully_nested_anova":
                row.extend([_fmt_num(r.get("var_comp")), f"{r.get('pct_total', 0):.2f}%"])
            rows_data.append(row)
        err = result.get("error")
        if err:
            er = ["Error", err.get("df"), _fmt_num(err.get("ss")), _fmt_num(err.get("ms")), "", ""]
            if kind == "fully_nested_anova":
                er.extend([_fmt_num(err.get("var_comp")), f"{err.get('pct_total', 0):.2f}%"])
            rows_data.append(er)
        out.append(("Analysis of Variance", headers, rows_data))

    elif kind == "oneway_manova":
        out.append(("MANOVA Multivariate Test Criteria", ["Criterion", "Statistic", "F-Value", "Num DF", "Den DF", "P-Value"], [
            [c["criterion"], _fmt_num(c["stat"]), _fmt_num(c["f"]), c["num_df"], _fmt_num(c["den_df"]), _fmt_num(c["p_value"])]
            for c in result.get("criteria", [])
        ]))

    elif kind == "mixed_reml":
        if result.get("variance_components"):
            out.append(("REML Variance Components", ["Source", "Variance", "% of Total", "StDev"], [
                [v["source"], _fmt_num(v["var_comp"], ".5g"), f"{v['pct_total']:.2f}%", _fmt_num(v["stdev"], ".5g")]
                for v in result["variance_components"]
            ]))
        if result.get("fixed_effects"):
            out.append(("Fixed Effects Coefficients", ["Term", "Coef", "SE Coef", "T-Value", "P-Value"], [
                [f["term"], _fmt_num(f["coef"], ".5g"), _fmt_num(f["se_coef"], ".5g"), _fmt_num(f["t_value"], ".3f"), _fmt_num(f["p_value"], ".4f")]
                for f in result["fixed_effects"]
            ]))
        out.append(("Model Fit Statistics", ["Criterion", "Value"], [
            ["-2 Log Likelihood (REML)", _fmt_num(result.get("neg2_rell"), ".4f")],
            ["AIC", _fmt_num(result.get("aic"), ".4f")],
            ["BIC", _fmt_num(result.get("bic"), ".4f")],
        ]))

    elif kind == "cox_ph_regression":
        out.append(("Cox Proportional Hazards Summary", ["Measure", "Value"], [
            ["Time Variable", result.get("time_variable")],
            ["Event Variable", result.get("event_variable")],
            ["N / Events / Censored", f"{result.get('n')} / {result.get('events')} / {result.get('censored')}"],
            ["Harrell's Concordance", _fmt_num(result.get("concordance"), ".4f")],
            ["LR Chi-Square (DF)", f"{_fmt_num(result.get('lr_chi_sq'), '.4f')} (df={result.get('lr_df')})"],
            ["LR P-Value", _fmt_num(result.get("lr_p_value"), ".4f")],
        ]))
        if result.get("coefficients"):
            out.append(("Hazard Ratios & Coefficients", ["Covariate", "Coef", "SE Coef", "Hazard Ratio", "95% CI Low", "95% CI High", "Z-Value", "P-Value"], [
                [c["covariate"], _fmt_num(c["coef"]), _fmt_num(c["se_coef"]), _fmt_num(c["hazard_ratio"]), _fmt_num(c["hr_95_low"]), _fmt_num(c["hr_95_high"]), _fmt_num(c["z_value"]), _fmt_num(c["p_value"])]
                for c in result["coefficients"]
            ]))

    elif kind == "warranty_analysis":
        out.append(("Weibull Warranty Parameters", ["Measure", "Value"], [
            ["Units at Risk", result.get("units_at_risk")],
            ["Observed Claims", result.get("observed_claims")],
            ["Observed Claim Rate (%)", f"{result.get('observed_claim_rate_pct', 0):.3f}%"],
            ["Weibull Shape (β)", _fmt_num(result.get("weibull_shape"), ".4f")],
            ["Weibull Scale (η)", _fmt_num(result.get("weibull_scale"), ".4f")],
        ]))
        if result.get("forecasts"):
            out.append(("Cumulative Warranty Claims Forecast", ["Age Horizon", "Cum Failure (%)", "Expected Total Claims", "Additional Future Claims"], [
                [f["age"], f"{f['cum_failure_pct']:.3f}%", _fmt_num(f["expected_total_claims"], ".2f"), _fmt_num(f["additional_future_claims"], ".2f")]
                for f in result["forecasts"]
            ]))

    elif kind == "negative_binomial_regression":
        out.append(("Negative Binomial Regression (NB2) Fit", ["Measure", "Value"], [
            ["Response", result.get("response")],
            ["N", result.get("n")],
            ["Dispersion α", _fmt_num(result.get("alpha"), ".5g")],
            ["Log-Likelihood (NB2 / Poisson)", f"{_fmt_num(result.get('log_likelihood'), '.3f')} / {_fmt_num(result.get('poisson_log_likelihood'), '.3f')}"],
            ["LR Dispersion P-Value", _fmt_num(result.get("lr_dispersion_p"), ".4f")],
            ["AIC / BIC", f"{_fmt_num(result.get('aic'), '.3f')} / {_fmt_num(result.get('bic'), '.3f')}"],
        ]))
        if result.get("coefficients"):
            out.append(("Model Coefficients", ["Term", "Coef", "SE Coef", "Z-Value", "P-Value", "IRR"], [
                [c.get("term"), _fmt_num(c.get("coef")), _fmt_num(c.get("se_coef")), _fmt_num(c.get("z_value")), _fmt_num(c.get("p_value")), _fmt_num(c.get("irr"))]
                for c in result["coefficients"]
            ]))

    elif kind == "poisson_gof":
        out.append(("Goodness-of-Fit Test for Poisson", ["Measure", "Value"], _dict_table_rows(result)))
        if result.get("bins"):
            out.append(("Observed vs Expected Count Bins", ["Count Bin", "Observed", "Expected Poisson", "Contribution to Chi-Sq"], [
                [b.get("bin"), b.get("observed"), _fmt_num(b.get("expected")), _fmt_num(b.get("chi_sq_contrib"))]
                for b in result["bins"]
            ]))

    elif kind in ("six_sigma_process_report", "six_sigma_product_report"):
        out.append(("Six Sigma Quality Metrics", ["Measure", "Value"], _dict_table_rows(result)))
        if result.get("step_yields_pct"):
            out.append(("Process Step Yields", ["Step", "Yield (%)"], [
                [f"Step {i + 1}", f"{y:.3f}%"] for i, y in enumerate(result["step_yields_pct"])
            ]))

    else:
        out.append((kind.replace("_", " ").title() or "Analysis Summary", ["Measure", "Value"], _dict_table_rows(result)))

    return out
