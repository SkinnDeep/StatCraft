"""Automated 'Plain English' Executive Summary Generator for StatCraft.

Translates complex statistical outputs (ANOVA, Regression, Capability, Hypothesis Tests, SPC)
into deterministic, 2-to-3 sentence executive bullet points suitable for plant managers,
auditors, and non-statistical stakeholders.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .model import Worksheet


def generate_executive_summary(entry: Dict[str, Any], worksheet: Optional[Worksheet] = None) -> List[str]:
    """Generate 2-3 concise, plain-English executive summary bullet points."""
    title = entry.get("title", "Statistical Analysis")
    result = entry.get("result", {})
    recipe = entry.get("recipe", {})
    action = recipe.get("action", "")
    analysis = result.get("analysis", action)
    params = recipe.get("parameters", {})

    bullets: List[str] = []

    # 1. REGRESSION & LINEAR MODELS
    if "regression" in analysis or action in ("multiple_regression", "linear_regression", "orthogonal_regression"):
        r2 = result.get("r_squared") or result.get("r2")
        r2_pred = result.get("predicted_r_squared")
        p_val = result.get("p_value") or result.get("overall_p")
        sig_text = "statistically significant" if (p_val is not None and p_val < 0.05) else "not statistically significant"

        if r2 is not None:
            bullets.append(f"The fitted model is {sig_text} and explains {r2*100:.1f}% of total observed process variation.")
        else:
            bullets.append(f"The fitted regression relationship is {sig_text}.")

        # Significant predictors
        coeffs = result.get("coefficients", [])
        if coeffs:
            sig_preds = [c.get("term") or c.get("name") for c in coeffs if c.get("term") != "Constant" and c.get("p_value", 1.0) < 0.05]
            if sig_preds:
                bullets.append(f"Key driving factor(s) with confirmed impact: {', '.join(sig_preds[:3])}.")
            else:
                bullets.append("None of the individual predictor terms demonstrated an effect distinct from random noise at α = 0.05.")

        # Unusual observations risk check
        unusual = result.get("unusual_observations", [])
        if unusual:
            bullets.append(f"Caution: {len(unusual)} unusual observation(s) exhibit high leverage or large residual error; review for data entry anomalies.")
        elif r2_pred is not None and r2 is not None and (r2 - r2_pred) > 0.20:
            bullets.append(f"Notice: Model exhibits potential over-fitting (Predicted R² = {r2_pred*100:.1f}% vs Fit R² = {r2*100:.1f}%).")

    # 2. PROCESS CAPABILITY (Cp, Cpk)
    elif "capability" in analysis or action in ("capability_analysis", "normal_capability"):
        cp = result.get("cp")
        cpk = result.get("cpk")
        ppm = result.get("ppm_total") or result.get("expected_ppm")
        target_cpk = 1.33

        if cpk is not None:
            if cpk >= target_cpk:
                bullets.append(f"Process is fully capable (Cpk = {cpk:.2f} ≥ {target_cpk}), meeting industrial 4-sigma quality standards.")
            elif cpk >= 1.0:
                bullets.append(f"Process is marginally capable (Cpk = {cpk:.2f} < {target_cpk}); process drift poses risk of out-of-spec parts.")
            else:
                bullets.append(f"Warning: Process is NOT capable (Cpk = {cpk:.2f} < 1.00); immediate centering or variance reduction required.")

        if ppm is not None:
            bullets.append(f"Estimated defect rate is {ppm:,.0f} PPM ({ppm/10000:.3f}% out-of-specification risk).")

        if cp is not None and cpk is not None and (cp - cpk) > 0.25:
            bullets.append(f"Process centering opportunity: Cp ({cp:.2f}) exceeds Cpk ({cpk:.2f}), indicating significant gain from shifting the process mean toward target.")

    # 3. ONE-WAY & TWO-WAY ANOVA
    elif "anova" in analysis or action in ("oneway_anova", "twoway_anova"):
        p_val = result.get("p_value")
        if p_val is not None:
            if p_val < 0.05:
                bullets.append(f"Statistically significant difference detected between factor groups (p = {p_val:.4f} < 0.05).")
                bullets.append("Group means are not uniform; post-hoc comparisons (e.g. Tukey HSD) should be inspected to isolate specific differing levels.")
            else:
                bullets.append(f"No statistically significant difference found between factor groups (p = {p_val:.4f} ≥ 0.05).")
                bullets.append("Observed group variations are consistent with expected random experimental noise.")

    # 4. TWO-SAMPLE T-TEST & HYPOTHESIS TESTS
    elif "two_sample_t" in analysis or action == "two_sample_t":
        p_val = result.get("p_value")
        diff = result.get("difference") or result.get("mean_diff")
        ci = result.get("ci_95") or result.get("confidence_interval")

        if p_val is not None:
            if p_val < 0.05:
                bullets.append(f"Statistically significant difference confirmed between samples (p = {p_val:.4f}).")
                if diff is not None:
                    bullets.append(f"Estimated difference in means is {diff:+.3f} units.")
            else:
                bullets.append(f"No significant difference detected between the two samples (p = {p_val:.4f} ≥ 0.05).")

    # 5. STATISTICAL PROCESS CONTROL (SPC)
    elif "control_chart" in analysis or "spc" in analysis or action in ("imr", "xbar_r", "subgroup_spc"):
        alarms = result.get("rule_violations", []) or result.get("out_of_control_points", [])
        if alarms:
            bullets.append(f"Special cause variation detected: {len(alarms)} out-of-control alarm(s) triggered.")
            bullets.append("Process is not in statistical control; investigate machine, tooling, or operator changes corresponding to flagged runs.")
        else:
            bullets.append("Process demonstrates stable statistical control with zero Nelson rule alarms triggered.")
            bullets.append("All observed variations are attributable to common-cause noise within 3-sigma control limits.")

    # 6. PREDICTIVE ML & DISCOVER BEST MODEL
    elif analysis in ("random_forest", "treenet_gbm", "mars_regression", "discover_best_model"):
        if analysis == "discover_best_model":
            bullets.append(f"AutoML Champion Model: {result.get('champion_model')} ranked #1 across {len(result.get('leaderboard', []))} candidate architectures.")
            top = (result.get("leaderboard") or [{}])[0]
            if result.get("task") == "regression" and "val_r2" in top:
                bullets.append(f"Champion holdout validation performance: R² = {top['val_r2']*100:.1f}%, RMSE = {top['val_rmse']:.4g}.")
            elif "val_accuracy" in top:
                bullets.append(f"Champion holdout validation accuracy: {top['val_accuracy']*100:.1f}%.")
        else:
            top_imp = (result.get("variable_importance") or [{}])[0].get("predictor")
            if analysis == "random_forest":
                om = result.get("oob_metrics", {})
                stat_txt = f"OOB R² = {om['r2']*100:.1f}%" if result.get("task") == "regression" and "r2" in om else f"OOB Accuracy = {om.get('accuracy', 0)*100:.1f}%"
                bullets.append(f"Random Forests ({result.get('n_trees')} trees) achieved {stat_txt}.")
            elif analysis == "treenet_gbm":
                vm = result.get("val_metrics", {})
                stat_txt = f"Validation R² = {vm['r2']*100:.1f}%" if result.get("task") == "regression" and "r2" in vm else f"Validation Accuracy = {vm.get('accuracy', 0)*100:.1f}%"
                bullets.append(f"TreeNet reached {stat_txt} at optimal tree count {result.get('optimal_trees')}.")
            else:
                mm = result.get("metrics", {})
                stat_txt = f"GCV R² = {mm.get('gcv_r2', 0)*100:.1f}%" if result.get("task") == "regression" else f"Accuracy = {mm.get('accuracy', 0)*100:.1f}%"
                bullets.append(f"MARS selected {result.get('n_basis_terms')} spline basis terms with {stat_txt}.")
            if top_imp:
                bullets.append(f"Strongest predictive driver in the model: '{top_imp}' (100% relative importance).")

    # 7. SIX SIGMA, REML, SURVIVAL & MONTE CARLO
    elif analysis == "six_sigma_process_report":
        bullets.append(f"Estimated short-term Sigma Level is {result.get('sigma_level_est', 0):.2f}σ (Z-bench LT = {result.get('z_bench_lt', 0):.2f}, Expected LT DPMO = {result.get('dpmo_expected_lt', 0):,.0f}).")
        cpk = result.get("cpk")
        if cpk is not None:
            bullets.append(f"Process Cpk = {cpk:.2f} ({'meets >= 1.33 benchmark' if cpk >= 1.33 else 'below 1.33 target; centering or variation reduction advised'}).")
    elif analysis == "six_sigma_product_report":
        bullets.append(f"Rolled Throughput Yield (RTY) across {result.get('steps')} steps is {result.get('rty_pct', 0):.2f}% ({result.get('dpmo_total', 0):,.0f} DPMO, {result.get('equivalent_sigma_level', 0):.2f}σ equivalent).")
    elif analysis == "mixed_reml":
        vcs = result.get("variance_components") or []
        top_vc = max(vcs, key=lambda v: v.get("pct_total", 0), default={})
        bullets.append(f"REML Mixed Model fitted ({result.get('n')} observations); dominant variance source is '{top_vc.get('source', 'Error')}' ({top_vc.get('pct_total', 0):.1f}% of total variance).")
    elif analysis == "cox_ph_regression":
        bullets.append(f"Cox PH fitted ({result.get('events')} events / {result.get('n')} subjects) with Harrell's Concordance = {result.get('concordance', 0):.3f} and LR test p = {result.get('lr_p_value', 1):.4f}.")
    elif analysis == "warranty_analysis":
        fc = (result.get("forecasts") or [{}])[-1]
        bullets.append(f"Weibull warranty fit shape β = {result.get('weibull_shape', 0):.2f}; projected total cumulative claims at horizon = {fc.get('expected_total_claims', 0):.1f}.")
    elif analysis == "monte_carlo_simulation":
        cap = result.get("capability", {})
        s = result.get("summary", {})
        bullets.append(f"Monte Carlo ({result.get('n_sims', 0):,} runs) projected Mean = {s.get('mean', 0):.4g}, SD = {s.get('stdev', 0):.4g}, Out-of-Spec = {cap.get('pct_out_of_spec', 0):.2f}% ({cap.get('dpmo', 0):,.0f} DPMO).")
        sens = result.get("sensitivity") or []
        if sens:
            bullets.append(f"Primary variance driver: '{sens[0]['input']}' accounts for {sens[0]['variance_contribution_pct']:.1f}% of simulated output sensitivity.")

    # 8. UNIVERSAL FALLBACK FOR OTHER OUTPUTS
    else:
        bullets.append(f"StatCraft completed evaluation for '{title}'.")
        if "sample_size" in result or "n" in result:
            n = result.get("sample_size") or result.get("n")
            bullets.append(f"Analysis evaluated {n} verified observations from the active worksheet.")
        if "p_value" in result:
            p = result["p_value"]
            bullets.append(f"Hypothesis test result: p-value = {p:.4f} ({'Significant at α = 0.05' if p < 0.05 else 'Not significant'}).")

    return bullets[:3]
