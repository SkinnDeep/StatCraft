"""Session window report generator for Stepwise Regression.

Formats output matching Minitab session window styling:
- Stepwise Selection Method and Alpha thresholds
- Stepwise Details step-by-step table (terms, coefs, t-vals, p-vals, S, R-sq, Cp, AIC, BIC)
- Analysis of Variance for selected model
- Model Summary table (S, R-sq, R-sq(adj), R-sq(pred))
- Final Model Coefficients table (Term, Coef, SE Coef, T-Value, P-Value)
- Regression Equation
"""
from __future__ import annotations

from typing import Any, Dict, List


def generate_stepwise_report(result: Dict[str, Any]) -> str:
    """Format stepwise regression results into a Minitab session text report."""
    lines: List[str] = []
    response_name = result.get("response_name", "Y")
    all_preds = result.get("all_predictor_names", [])
    method = result.get("method", "stepwise")
    method_display = {
        "stepwise": "Stepwise selection",
        "forward": "Forward selection",
        "backward": "Backward elimination",
        "forward_aic": "Forward selection with AIC",
        "forward_bic": "Forward selection with BIC",
        "backward_aic": "Backward elimination with AIC",
        "backward_bic": "Backward elimination with BIC",
    }.get(method, method.capitalize())

    lines.append(f"Stepwise Regression: {response_name} versus {', '.join(all_preds)}")
    lines.append("")
    lines.append(f"Selection Method: {method_display}")
    if method in ("stepwise", "forward"):
        lines.append(f"α to enter = {result.get('alpha_to_enter', 0.15):.2f}")
    if method in ("stepwise", "backward"):
        lines.append(f"α to remove = {result.get('alpha_to_remove', 0.15):.2f}")
    lines.append("")

    # Stepwise Details Table
    steps = result.get("steps", [])
    if steps:
        lines.append("Stepwise Details")
        col_w = 12
        hdr = f"{'':20}" + "".join(f"Step {s['step']}".rjust(col_w) for s in steps)
        lines.append(hdr)
        lines.append("-" * len(hdr))

        # Constant row
        const_row = f"{'Constant':20}"
        for s in steps:
            c_val = s["coefficients"].get("Constant", {}).get("coef")
            const_row += f"{c_val:>{col_w}.4f}" if c_val is not None else "".rjust(col_w)
        lines.append(const_row)
        lines.append("")

        # Each predictor
        for pred in all_preds:
            # Check if this predictor appeared in any step
            appeared = any(pred in s["coefficients"] for s in steps)
            if not appeared:
                continue

            row_coef = f"{pred:20}"
            row_t = f"{'  T-Value':20}"
            row_p = f"{'  P-Value':20}"

            for s in steps:
                info = s["coefficients"].get(pred)
                if info is not None:
                    row_coef += f"{info['coef']:>{col_w}.4f}"
                    row_t += f"{info['t_value']:>{col_w}.2f}"
                    row_p += f"{info['p_value']:>{col_w}.3f}"
                else:
                    row_coef += "".rjust(col_w)
                    row_t += "".rjust(col_w)
                    row_p += "".rjust(col_w)

            lines.append(row_coef)
            lines.append(row_t)
            lines.append(row_p)
            lines.append("")

        lines.append("-" * len(hdr))
        # Summary rows
        s_row = f"{'S':20}" + "".join(f"{s['s']:>{col_w}.4f}" for s in steps)
        rsq_row = f"{'R-sq':20}" + "".join(f"{s['r_sq']:>{col_w-1}.2f}%" for s in steps)
        rsq_adj_row = f"{'R-sq(adj)':20}" + "".join(f"{s['r_sq_adj']:>{col_w-1}.2f}%" for s in steps)
        rsq_pred_row = f"{'R-sq(pred)':20}" + "".join(f"{s['r_sq_pred']:>{col_w-1}.2f}%" for s in steps)
        cp_row = f"{'Mallows\' Cp':20}" + "".join(f"{s['mallows_cp']:>{col_w}.2f}" for s in steps)
        aic_row = f"{'AIC':20}" + "".join(f"{s['aic']:>{col_w}.2f}" for s in steps)
        bic_row = f"{'BIC':20}" + "".join(f"{s['bic']:>{col_w}.2f}" for s in steps)

        lines.append(s_row)
        lines.append(rsq_row)
        lines.append(rsq_adj_row)
        lines.append(rsq_pred_row)
        lines.append(cp_row)
        lines.append(aic_row)
        lines.append(bic_row)
        lines.append("")

    # Final Model Equation
    final_terms = result.get("selected_terms", [])
    final_fit = result.get("final_fit", {})
    coefs = final_fit.get("coef", [])
    if len(coefs) > 0:
        lines.append("Regression Equation")
        eq_parts = [f"{coefs[0]:.4f}"]
        for idx, term in enumerate(final_terms):
            c = coefs[idx + 1]
            sign = "+ " if c >= 0 else "- "
            eq_parts.append(f"{sign}{abs(c):.4f} {term}")
        lines.append(f"{response_name} = {' '.join(eq_parts)}")
        lines.append("")

    # Model Summary
    lines.append("Model Summary")
    lines.append(f"{'S':>10}  {'R-sq':>8}  {'R-sq(adj)':>10}  {'R-sq(pred)':>11}")
    lines.append(
        f"{result.get('s', 0.0):>10.4f}  {result.get('r_sq', 0.0):>7.2f}%  {result.get('r_sq_adj', 0.0):>9.2f}%  {result.get('r_sq_pred', 0.0):>10.2f}%"
    )
    lines.append("")

    # Coefficients Table
    lines.append("Coefficients")
    lines.append(f"{'Term':<16}  {'Coef':>10}  {'SE Coef':>10}  {'T-Value':>8}  {'P-Value':>8}")
    se_coefs = final_fit.get("se_coef", [])
    t_vals = final_fit.get("t_values", [])
    p_vals = final_fit.get("p_values", [])

    if len(coefs) > 0:
        lines.append(f"{'Constant':<16}  {coefs[0]:>10.4f}  {se_coefs[0]:>10.4f}  {t_vals[0]:>8.2f}  {p_vals[0]:>8.3f}")
        for idx, term in enumerate(final_terms):
            pos = idx + 1
            lines.append(
                f"{term:<16}  {coefs[pos]:>10.4f}  {se_coefs[pos]:>10.4f}  {t_vals[pos]:>8.2f}  {p_vals[pos]:>8.3f}"
            )
    lines.append("")

    # Analysis of Variance Table
    lines.append("Analysis of Variance")
    lines.append(f"{'Source':<14}  {'DF':>6}  {'Adj SS':>12}  {'Adj MS':>12}  {'F-Value':>8}  {'P-Value':>8}")
    for row in result.get("anova", []):
        src = row.get("source", "")
        df = row.get("df", 0)
        ss = row.get("ss", 0.0)
        ms = row.get("ms", 0.0)
        f_val = row.get("f")
        p_val = row.get("p")
        f_str = f"{f_val:>8.2f}" if f_val is not None else "".rjust(8)
        p_str = f"{p_val:>8.3f}" if p_val is not None else "".rjust(8)
        lines.append(f"{src:<14}  {df:>6}  {ss:>12.2f}  {ms:>12.2f}  {f_str}  {p_str}")

    return "\n".join(lines)
