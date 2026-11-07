"""Report generator for Individual Distribution Identification (Stat > Quality Tools > Individual Distribution Identification).

Generates Minitab 22-standard plain text reports including:
- Goodness of Fit Test table (AD, P-value, LRT P-value)
- ML Estimates of Distribution Parameters table (Location, Shape, Scale, Threshold)
- Transformation specifications for Box-Cox and Johnson systems
- Best distribution selection summary
"""

from __future__ import annotations

from typing import Any, Dict, List


def generate_dist_id_report(result: Dict[str, Any]) -> str:
    """Format Minitab 22-standard text session report for Individual Distribution Identification."""
    var_name = result.get("variable_name", "Variable")
    n = result.get("n_samples", 0)
    alpha = result.get("alpha", 0.05)
    best_fit = result.get("best_fit", "None")

    lines: List[str] = []
    lines.append(f"Individual Distribution Identification for {var_name}")
    lines.append(f"Sample Size (N) = {n}")
    lines.append("")
    lines.append("Goodness of Fit Test")
    lines.append("")
    lines.append(f"{'Distribution':<28} {'AD':>8} {'P':>10} {'LRT P':>10}")
    lines.append("-" * 60)

    for row in result.get("gof_table", []):
        dist_title = row.get("distribution", "")
        ad_val = row.get("ad")
        ad_str = f"{ad_val:.3f}" if ad_val is not None else "*"
        p_val = row.get("p_value")
        if p_val is None:
            p_str = "*"
        elif p_val < 0.001:
            p_str = "<0.001"
        elif p_val > 0.999:
            p_str = ">0.999"
        else:
            p_str = f"{p_val:.3f}"

        lrt_val = row.get("lrt_p")
        if lrt_val is None:
            lrt_str = "-"
        elif lrt_val < 0.001:
            lrt_str = "<0.001"
        else:
            lrt_str = f"{lrt_val:.3f}"

        lines.append(f"{dist_title:<28} {ad_str:>8} {p_str:>10} {lrt_str:>10}")

    lines.append("")
    lines.append("ML Estimates of Distribution Parameters")
    lines.append("")
    lines.append(f"{'Distribution':<28} {'Location':>10} {'Shape':>10} {'Scale':>10} {'Threshold':>10}")
    lines.append("-" * 72)

    for row in result.get("param_table", []):
        dist_title = row.get("distribution", "")
        if dist_title in ("Normal", "Box-Cox Transformation"):
            dist_title_marked = f"{dist_title}*"
        else:
            dist_title_marked = dist_title

        loc = f"{row['location']:.3f}" if row.get("location") is not None else "-"
        shp = f"{row['shape']:.3f}" if row.get("shape") is not None else "-"
        scl = f"{row['scale']:.3f}" if row.get("scale") is not None else "-"
        thr = f"{row['threshold']:.3f}" if row.get("threshold") is not None else "-"

        lines.append(f"{dist_title_marked:<28} {loc:>10} {shp:>10} {scl:>10} {thr:>10}")

    lines.append("")
    lines.append("* For Normal and Box-Cox Transformation, Location is Mean and Scale is StDev.")
    lines.append("")

    # Transformations detail
    fits = result.get("fits", {})
    if "box_cox" in fits:
        bc = fits["box_cox"]
        lam = bc.get("lambda", 0.0)
        rlam = bc.get("rounded_lambda", 0.0)
        shift = bc.get("shift", 0.0)
        lines.append(f"Box-Cox Transformation: Rounded Lambda = {rlam:.1f} (Optimal Lambda = {lam:.4f}, Shift = {shift:.3f})")

    if "johnson" in fits:
        j = fits["johnson"]
        fn = j.get("function", "")
        family = j.get("family", "")
        p_val = j.get("p_value", 0.0)
        p_crit = j.get("p_threshold", 0.10)
        status = "Accepted" if j.get("passed") else "Rejected"
        lines.append(f"Johnson Transformation ({family}): {fn}")
        lines.append(f"  P-value: {p_val:.3f} (P-value to select best fit: {p_crit:.2f} -> {status})")

    lines.append("")
    lines.append(f"Selected Best-Fitting Distribution (AD lowest, P >= {alpha:.2f}): {best_fit}")
    return "\n".join(lines)
