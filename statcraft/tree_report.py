"""Report formatting and structured table extraction for CART® Decision Trees."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _fmt(val: Any, dec: int = 4) -> str:
    if val is None:
        return "*"
    try:
        return f"{float(val):.{dec}f}"
    except (ValueError, TypeError):
        return str(val)


def format_tree_report(entry: Dict[str, Any]) -> str:
    """Format full session text report for CART® Decision Trees matching Minitab 22 and JMP."""
    res = entry.get("result", entry)
    resp_name = str(res.get("response_name", "Response"))
    tree_type = str(res.get("tree_type", "regression")).capitalize()
    metrics = res.get("metrics", {})

    lines = [
        f"CART® {tree_type} Tree: {resp_name}",
        "",
        "Model Description",
        f"  Response:            {resp_name}",
        f"  Predictors:          {', '.join(res.get('feature_names', []))}",
        f"  Tree Type:           {tree_type}",
        f"  Number of rows:      {metrics.get('n_samples', 0)}",
        f"  Terminal nodes:      {metrics.get('n_terminal_nodes', 0)}",
        f"  Max depth reached:   {metrics.get('max_depth_reached', 0)}",
        "",
        "Model Performance Summary",
    ]

    if tree_type.lower() == "regression":
        r2 = metrics.get("r2", 0.0)
        rmse = metrics.get("rmse", 0.0)
        mae = metrics.get("mae", 0.0)
        lines.extend([
            f"  R-squared (R²):      {r2*100:.2f}%",
            f"  RMSE:                {rmse:.4f}",
            f"  Mean Absolute Error: {mae:.4f}",
        ])
    else:
        acc = metrics.get("accuracy", 0.0)
        mis = metrics.get("misclassification_rate", 0.0)
        lines.extend([
            f"  Accuracy:            {acc*100:.2f}%",
            f"  Misclassification:   {mis*100:.2f}%",
        ])

    lines.extend([
        "",
        "Variable Importance",
        f"  {'Predictor':24s} {'Importance':>12s} {'Relative':>12s}",
        "  " + "-" * 50,
    ])

    importances = res.get("importances", [])
    max_imp = importances[0]["importance"] if importances and importances[0]["importance"] > 0 else 1.0
    for imp_row in importances:
        feat = imp_row.get("feature", "")
        imp = imp_row.get("importance", 0.0)
        rel = (imp / max_imp * 100.0) if max_imp > 0 else 0.0
        lines.append(f"  {feat:24s} {imp:>11.1f}% {rel:>11.1f}%")

    lines.extend([
        "",
        "Terminal Leaves Summary",
        f"  {'Node ID':>8s} {'Depth':>7s} {'Count':>9s} {'% Total':>10s} {'Predicted Value':>18s} {'SD / Purity':>14s}",
        "  " + "-" * 72,
    ])

    for node in res.get("terminal_nodes", []):
        n_id = str(node.get("node_id", ""))
        depth = str(node.get("depth", ""))
        cnt = str(node.get("n_samples", ""))
        pct = f"{node.get('pct_samples', 0.0):.1f}%"
        if tree_type.lower() == "regression":
            val_s = _fmt(node.get("mean"), 4)
            sd_s = _fmt(node.get("sd"), 4)
        else:
            val_s = str(node.get("predicted_class", ""))
            sd_s = f"{node.get('purity', 0.0):.1f}%"
        lines.append(f"  {n_id:>8s} {depth:>7s} {cnt:>9s} {pct:>10s} {val_s:>18s} {sd_s:>14s}")

    return "\n".join(lines)


def get_tree_structured_tables(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return structured card tables for rich Report tab rendering."""
    tables = []
    tree_type = str(res.get("tree_type", "regression")).capitalize()
    metrics = res.get("metrics", {})

    # 1. Model Summary Table
    if tree_type.lower() == "regression":
        summary_rows = [
            ["Response Variable", str(res.get("response_name", ""))],
            ["Tree Type", tree_type],
            ["Number of Observations", str(metrics.get("n_samples", 0))],
            ["Terminal Leaves", str(metrics.get("n_terminal_nodes", 0))],
            ["Maximum Depth", str(metrics.get("max_depth_reached", 0))],
            ["R-squared (R²)", f"{metrics.get('r2', 0.0)*100:.2f}%"],
            ["Root Mean Squared Error (RMSE)", f"{metrics.get('rmse', 0.0):.4f}"],
            ["Mean Absolute Error (MAE)", f"{metrics.get('mae', 0.0):.4f}"],
        ]
    else:
        summary_rows = [
            ["Response Variable", str(res.get("response_name", ""))],
            ["Tree Type", tree_type],
            ["Number of Observations", str(metrics.get("n_samples", 0))],
            ["Terminal Leaves", str(metrics.get("n_terminal_nodes", 0))],
            ["Maximum Depth", str(metrics.get("max_depth_reached", 0))],
            ["Overall Accuracy", f"{metrics.get('accuracy', 0.0)*100:.2f}%"],
            ["Misclassification Rate", f"{metrics.get('misclassification_rate', 0.0)*100:.2f}%"],
        ]

    tables.append({
        "title": f"CART® {tree_type} Tree Summary",
        "headers": ["Metric", "Value"],
        "rows": summary_rows,
    })

    # 2. Variable Importance Table
    importances = res.get("importances", [])
    max_imp = importances[0]["importance"] if importances and importances[0]["importance"] > 0 else 1.0
    imp_rows = []
    for rank, imp_row in enumerate(importances, start=1):
        imp = imp_row.get("importance", 0.0)
        rel = (imp / max_imp * 100.0) if max_imp > 0 else 0.0
        imp_rows.append([
            str(rank),
            str(imp_row.get("feature", "")),
            f"{imp:.1f}%",
            f"{rel:.1f}%",
        ])

    tables.append({
        "title": "Predictor Importance Ranking",
        "headers": ["Rank", "Predictor", "Importance", "Relative to Top"],
        "rows": imp_rows,
    })

    # 3. Terminal Nodes Table
    node_rows = []
    for node in res.get("terminal_nodes", []):
        n_id = str(node.get("node_id", ""))
        depth = str(node.get("depth", ""))
        cnt = str(node.get("n_samples", ""))
        pct = f"{node.get('pct_samples', 0.0):.1f}%"
        if tree_type.lower() == "regression":
            val_s = _fmt(node.get("mean"), 4)
            var_s = _fmt(node.get("sd"), 4)
            h_var = "Std Dev"
        else:
            val_s = str(node.get("predicted_class", ""))
            var_s = f"{node.get('purity', 0.0):.1f}%"
            h_var = "Purity"

        node_rows.append([n_id, depth, cnt, pct, val_s, var_s])

    tables.append({
        "title": "Terminal Leaves Details",
        "headers": ["Node ID", "Depth", "Count", "% Total", "Predicted Value", "SD / Purity"],
        "rows": node_rows,
    })

    # 4. Confusion matrix for classification
    if tree_type.lower() == "classification" and "confusion_matrix" in metrics:
        cm = metrics["confusion_matrix"]
        labels = res.get("classes", [])
        headers = ["Actual \\ Predicted"] + labels
        cm_rows = []
        for true_lbl in labels:
            row = [true_lbl]
            for pred_lbl in labels:
                row.append(str(cm.get(true_lbl, {}).get(pred_lbl, 0)))
            cm_rows.append(row)

        tables.append({
            "title": "Confusion Matrix (Classification)",
            "headers": headers,
            "rows": cm_rows,
        })

    return tables
