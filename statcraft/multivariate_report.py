"""StatCraft session window report formatting for Multivariate Analysis."""

from typing import Any, Dict, List


def format_pca_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft PCA session report."""
    vars_str = ", ".join(result["variable_names"])
    lines = [
        f"Principal Component Analysis: {vars_str}",
        "",
        f"Eigenanalysis of the {result['matrix_title']}",
        "",
    ]

    k_comp = len(result["eigenvalues"])
    headers = [f"PC{i+1}" for i in range(k_comp)]

    # Format eigenvalues, proportion, cumulative
    col_w = 9
    h_line = f"{'':15}" + "".join(f"{h:>{col_w}}" for h in headers)
    lines.append(h_line)

    ev_line = f"{'Eigenvalue':15}" + "".join(f"{val:>{col_w}.4f}" for val in result["eigenvalues"])
    lines.append(ev_line)

    pr_line = f"{'Proportion':15}" + "".join(f"{val:>{col_w}.3f}" for val in result["proportions"])
    lines.append(pr_line)

    cu_line = f"{'Cumulative':15}" + "".join(f"{val:>{col_w}.3f}" for val in result["cumulative"])
    lines.append(cu_line)
    lines.append("")

    # Eigenvectors (loadings)
    lines.append("Eigenvectors")
    load_headers = [f"PC{i+1}" for i in range(result["k_components"])]
    h_load = f"{'Variable':15}" + "".join(f"{h:>{col_w}}" for h in load_headers)
    lines.append(h_load)

    for row in result["loadings_table"]:
        v_name = row["variable"]
        v_line = f"{v_name:15}" + "".join(f"{row[f'PC{k+1}']:>{col_w}.3f}" for k in range(result["k_components"]))
        lines.append(v_line)

    lines.append("")
    return "\n".join(lines)


def format_item_analysis_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft Item Analysis report."""
    items_str = ", ".join(result["item_names"])
    lines = [
        f"Item Analysis of {items_str}",
        "",
        f"Cronbach's alpha = {result['cronbach_alpha']:.4f}",
        f"Standardized alpha = {result['standardized_alpha']:.4f}",
        "",
        "Item-Total Statistics",
        "",
        f"{'Item':15}{'Item Mean':>11}{'Item SD':>11}{'Adj Tot Mean':>14}{'Adj Tot SD':>13}{'Item-Tot Corr':>15}{'Sq Mult Corr':>14}{'Alpha if Del':>14}",
        "-" * 97,
    ]

    for st in result["item_stats"]:
        item = st["item"]
        imean = f"{st['item_mean']:.3f}"
        isd = f"{st['item_sd']:.3f}"
        atmean = f"{st['adj_total_mean']:.3f}"
        atsd = f"{st['adj_total_sd']:.3f}"
        corr = f"{st['item_adj_total_corr']:.4f}"
        smc = f"{st['squared_multiple_corr']:.4f}"
        alpha_del = f"{st['alpha_deleted']:.4f}"
        lines.append(f"{item:15}{imean:>11}{isd:>11}{atmean:>14}{atsd:>13}{corr:>15}{smc:>14}{alpha_del:>14}")

    lines.append("")
    lines.append(f"Total Mean = {result['total_mean']:.3f},  Total Standard Deviation = {result['total_sd']:.3f}")
    lines.append("")
    return "\n".join(lines)


def format_cluster_observations_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft Cluster Analysis of Observations report."""
    lines = [
        "Cluster Analysis of Observations",
        "",
        f"Linkage Method:   {result['linkage_method'].capitalize()}",
        f"Distance Measure: {result['distance_measure'].replace('_', ' ').capitalize()}",
        f"Standardization:  {result['standardize'].capitalize()}",
        "",
        "Amalgamation Steps",
        "",
        f"{'Step':>6}{'Number of':>12}{'Similarity':>13}{'Distance':>11}{'Clusters':>12}{'New':>8}{'Number of':>12}",
        f"{'':>6}{'Clusters':>12}{'Level':>13}{'Level':>11}{'Joined':>12}{'Cluster':>8}{'Obs in Clus':>12}",
        "-" * 74,
    ]

    for step in result["amalgamation"]:
        s_num = step["step"]
        rem_c = step["clusters"]
        sim = f"{step['similarity']:.2f}"
        dist = f"{step['distance']:.4f}"
        joined = f"{step['cluster1']} {step['cluster2']}"
        new_c = step["new_cluster"]
        n_obs = step["n_obs"]
        lines.append(f"{s_num:>6}{rem_c:>12}{sim:>13}{dist:>11}{joined:>12}{new_c:>8}{n_obs:>12}")

    lines.append("")
    lines.append(f"Final Partition (Number of clusters: {result['k_clusters']})")
    lines.append("")
    lines.append(f"{'Cluster':>10}{'Number of Obs':>16}{'Within Cluster SS':>20}{'Average Distance':>18}{'Maximum Distance':>18}")
    lines.append("-" * 82)

    for c in result["cluster_summary"]:
        lines.append(f"{c['cluster']:>10}{c['count']:>16}{c['within_ss']:>20.4f}{c['avg_dist']:>18.4f}{c['max_dist']:>18.4f}")

    lines.append("")
    lines.append(f"Total within cluster sum of squares = {result['total_within_ss']:.4f}")
    lines.append("")

    # Centroids
    lines.append("Cluster Centroids")
    headers = [f"Cluster {i+1}" for i in range(result["k_clusters"])]
    h_cent = f"{'Variable':15}" + "".join(f"{h:>14}" for h in headers)
    lines.append(h_cent)
    lines.append("-" * (15 + 14 * result["k_clusters"]))

    for j, name in enumerate(result["variable_names"]):
        vals = [result["centroids"][k][j] for k in range(result["k_clusters"])]
        row_str = f"{name:15}" + "".join(f"{v:>14.4f}" for v in vals)
        lines.append(row_str)

    lines.append("")
    return "\n".join(lines)


def format_cluster_kmeans_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft K-Means Cluster Analysis report."""
    vars_str = ", ".join(result["variable_names"])
    lines = [
        f"K-Means Cluster Analysis: {vars_str}",
        "",
        f"Number of clusters: {result['k_clusters']}",
        f"Number of iterations: {result['iterations']}",
        "",
        "Final Partition",
        "",
        f"{'Cluster':>10}{'Number of Obs':>16}{'Within Cluster SS':>20}{'Average Distance':>18}{'Maximum Distance':>18}",
        "-" * 82,
    ]

    for c in result["summary"]:
        lines.append(f"{c['cluster']:>10}{c['count']:>16}{c['within_ss']:>20.4f}{c['avg_dist']:>18.4f}{c['max_dist']:>18.4f}")

    lines.append("")
    lines.append(f"Total within cluster sum of squares = {result['within_ss']:.4f}")
    lines.append(f"Between cluster sum of squares = {result['between_ss']:.4f}")
    lines.append(f"Total sum of squares = {result['total_ss']:.4f}")
    lines.append("")

    # Centroids
    lines.append("Cluster Centroids")
    headers = [f"Cluster {i+1}" for i in range(result["k_clusters"])]
    h_cent = f"{'Variable':15}" + "".join(f"{h:>14}" for h in headers)
    lines.append(h_cent)
    lines.append("-" * (15 + 14 * result["k_clusters"]))

    for j, name in enumerate(result["variable_names"]):
        vals = [result["centroids"][k][j] for k in range(result["k_clusters"])]
        row_str = f"{name:15}" + "".join(f"{v:>14.4f}" for v in vals)
        lines.append(row_str)

    lines.append("")
    lines.append("Distances Between Cluster Centroids")
    lines.append(f"{'':15}" + "".join(f"{f'Cluster {k+1}':>14}" for k in range(result["k_clusters"])))
    for i in range(result["k_clusters"]):
        row_vals = result["centroid_distances"][i]
        lines.append(f"{f'Cluster {i+1}':15}" + "".join(f"{row_vals[j]:>14.4f}" for j in range(result["k_clusters"])))

    lines.append("")
    return "\n".join(lines)


def format_cluster_variables_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft Cluster Analysis of Variables report."""
    vars_str = ", ".join(result["variable_names"])
    lines = [
        f"Cluster Analysis of Variables: {vars_str}",
        "",
        f"Linkage Method: {result['linkage_method'].capitalize()}",
        "",
        "Amalgamation Steps",
        "",
        f"{'Step':>6}{'Number of':>12}{'Similarity':>13}{'Distance':>11}{'Clusters':>12}{'New':>8}{'Number of':>12}",
        f"{'':>6}{'Clusters':>12}{'Level':>13}{'Level':>11}{'Joined':>12}{'Cluster':>8}{'Variables':>12}",
        "-" * 74,
    ]

    for step in result["amalgamation"]:
        s_num = step["step"]
        rem_c = step["clusters"]
        sim = f"{step['similarity']:.2f}"
        dist = f"{step['distance']:.4f}"
        joined = f"{step['cluster1']} {step['cluster2']}"
        new_c = step["new_cluster"]
        n_vars = step["n_vars"]
        lines.append(f"{s_num:>6}{rem_c:>12}{sim:>13}{dist:>11}{joined:>12}{new_c:>8}{n_vars:>12}")

    lines.append("")
    return "\n".join(lines)


def format_discriminant_analysis_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft Discriminant Analysis report."""
    preds_str = ", ".join(result["predictor_names"])
    lines = [
        f"Discriminant Analysis: {result['group_name']} versus {preds_str}",
        "",
        f"Linear Discriminant Function for {result['group_name']}",
        "",
    ]

    headers = result["unique_groups"]
    col_w = 14
    lines.append(f"{'':15}" + "".join(f"{h:>{col_w}}" for h in headers))
    lines.append("-" * (15 + col_w * len(headers)))

    # Constant row
    c_vals = [f"{entry['constant']:.4f}" for entry in result["linear_coefficients"]]
    lines.append(f"{'Constant':15}" + "".join(f"{v:>{col_w}}" for v in c_vals))

    for p_name in result["predictor_names"]:
        p_vals = [f"{entry[p_name]:.4f}" for entry in result["linear_coefficients"]]
        lines.append(f"{p_name:15}" + "".join(f"{v:>{col_w}}" for v in p_vals))

    lines.append("")
    lines.append("Summary of Classification")
    lines.append("")
    h_class = f"{'True Group':15}{'N':>8}{'Correct':>10}{'%Correct':>11}" + "".join(f"{f'Pred {g}':>{col_w}}" for g in headers)
    lines.append(h_class)
    lines.append("-" * len(h_class))

    for row in result["summary_classification"]:
        g = row["group"]
        rn = row["n"]
        rc = row["correct"]
        rp = f"{row['pct_correct']:.1f}"
        preds = "".join(f"{row[f'pred_{pred_g}']:>{col_w}}" for pred_g in headers)
        lines.append(f"{g:15}{rn:>8}{rc:>10}{rp:>11}{preds}")

    lines.append("-" * len(h_class))
    tot_correct = sum(row["correct"] for row in result["summary_classification"])
    tot_n = sum(row["n"] for row in result["summary_classification"])
    tot_preds = "".join(f"{sum(row[f'pred_{pred_g}'] for row in result['summary_classification']):>{col_w}}" for pred_g in headers)
    lines.append(f"{'Total':15}{tot_n:>8}{tot_correct:>10}{result['total_pct_correct']:>10.1f}%{tot_preds}")

    lines.append("")
    lines.append("Summary of Cross-Validation (Jackknife)")
    lines.append("")
    lines.append(h_class)
    lines.append("-" * len(h_class))

    for row in result["cross_validation_summary"]:
        g = row["group"]
        rn = row["n"]
        rc = row["correct"]
        rp = f"{row['pct_correct']:.1f}"
        preds = "".join(f"{row[f'pred_{pred_g}']:>{col_w}}" for pred_g in headers)
        lines.append(f"{g:15}{rn:>8}{rc:>10}{rp:>11}{preds}")

    lines.append("-" * len(h_class))
    cv_tot_correct = sum(row["correct"] for row in result["cross_validation_summary"])
    cv_tot_n = sum(row["n"] for row in result["cross_validation_summary"])
    cv_tot_preds = "".join(f"{sum(row[f'pred_{pred_g}'] for row in result['cross_validation_summary']):>{col_w}}" for pred_g in headers)
    lines.append(f"{'Total':15}{cv_tot_n:>8}{cv_tot_correct:>10}{result['cv_total_pct_correct']:>10.1f}%{cv_tot_preds}")

    lines.append("")
    return "\n".join(lines)


def format_simple_correspondence_report(result: Dict[str, Any]) -> str:
    """Format authentic StatCraft Simple Correspondence Analysis report."""
    lines = [
        "Simple Correspondence Analysis",
        "",
        f"Total count = {result['total_count']:.0f}",
        f"Total inertia = {result['total_inertia']:.4f}",
        f"Chi-square = {result['total_chi_square']:.2f}",
        "",
        "Inertia Decomposition",
        "",
        f"{'Dimension':>11}{'Singular Value':>16}{'Inertia':>12}{'Chi-Square':>13}{'Proportion':>13}{'Cumulative':>13}",
        "-" * 78,
    ]

    for row in result["decomposition_table"]:
        dim = row["dimension"]
        sv = f"{row['singular_value']:.4f}"
        iner = f"{row['inertia']:.4f}"
        chi = f"{row['chi_square']:.2f}"
        prop = f"{row['proportion']:.3f}"
        cum = f"{row['cumulative']:.3f}"
        lines.append(f"{dim:>11}{sv:>16}{iner:>12}{chi:>13}{prop:>13}{cum:>13}")

    lines.append("")
    return "\n".join(lines)
