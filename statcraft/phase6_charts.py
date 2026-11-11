"""Native Qt QPainter Visual Charts for Phases 3-6 Analyses.

Renders crisp multi-panel vector plots with interactive hover tooltips inside ChartWidget for:
- Monte Carlo Process Simulation (Output Histogram + LSL/USL + Sensitivity Tornado)
- Random Forests & TreeNet GBM (Variable Importance + OOB/Validation Curve + Partial Dependence + ROC)
- MARS Splines & Discover Best Model (Importance + Binary ROC / AutoML Leaderboard Bars)
- Resampling (Bootstrap / Randomization Null Distribution Histogram + CI / Observed)
- Warranty Analysis, REML/Nested Variance Components, Six Sigma RTY & Cox PH Hazard Ratios
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen


PHASE6_CHART_ANALYSES = {
    "monte_carlo_simulation",
    "random_forest",
    "treenet_gbm",
    "mars_regression",
    "discover_best_model",
    "bootstrap_1sample",
    "bootstrap_2sample",
    "randomization_1sample",
    "randomization_2sample",
    "warranty_analysis",
    "mixed_reml",
    "fully_nested_anova",
    "six_sigma_product_report",
    "cox_ph_regression",
}


def supported(result: Any) -> bool:
    return isinstance(result, dict) and result.get("analysis") in PHASE6_CHART_ANALYSES


def _maybe_roc_panel(r: Dict[str, Any], auc_val: Any = None) -> List[Dict[str, Any]]:
    roc = r.get("roc_curve") or []
    if not roc:
        return []
    auc_txt = f" (AUC = {auc_val:.3f})" if isinstance(auc_val, (int, float)) else ""
    return [{
        "kind": "phase6_chart",
        "mode": "line",
        "title": f"ROC Curve{auc_txt}",
        "series": [
            {"label": "Model ROC", "x": [pt["fpr"] for pt in roc], "y": [pt["tpr"] for pt in roc], "color": "#2563eb", "dash": False},
            {"label": "Random (0.5)", "x": [0.0, 1.0], "y": [0.0, 1.0], "color": "#94a3b8", "dash": True},
        ],
        "xlabel": "False Positive Rate (1 - Specificity)",
        "ylabel": "True Positive Rate (Sensitivity)",
    }]


def prepare(chart: Any, r: Dict[str, Any]) -> None:
    kind = r.get("analysis", "")
    panels: List[Dict[str, Any]] = []

    if kind == "monte_carlo_simulation":
        hist = r.get("histogram") or {}
        if hist.get("edges") and hist.get("counts"):
            vlines = [{"x": r["summary"]["mean"], "label": f"Mean={r['summary']['mean']:.3g}", "color": "#16a34a", "dash": False}]
            if r.get("lsl") is not None:
                vlines.append({"x": float(r["lsl"]), "label": f"LSL={r['lsl']:.3g}", "color": "#dc2626", "dash": True})
            if r.get("usl") is not None:
                vlines.append({"x": float(r["usl"]), "label": f"USL={r['usl']:.3g}", "color": "#dc2626", "dash": True})
            panels.append({
                "kind": "phase6_chart",
                "mode": "hist",
                "title": f"Simulated Distribution (OOS = {r['capability']['pct_out_of_spec']:.2f}%)",
                "edges": hist["edges"],
                "counts": hist["counts"],
                "vlines": vlines,
                "xlabel": r.get("formula", "Y"),
                "ylabel": "Frequency",
                "fill": "#3b82f6",
            })
        sens = r.get("sensitivity") or []
        if sens:
            panels.append({
                "kind": "phase6_chart",
                "mode": "barh",
                "title": "Sensitivity Tornado (% Variance Contribution)",
                "labels": [s["input"] for s in sens[:8]],
                "values": [s["variance_contribution_pct"] for s in sens[:8]],
                "xlabel": "Contribution (%)",
                "unit": "%",
                "fill": "#0ea5e9",
            })

    elif kind in ("random_forest", "treenet_gbm", "mars_regression"):
        imp = r.get("variable_importance") or []
        if imp:
            panels.append({
                "kind": "phase6_chart",
                "mode": "barh",
                "title": "Relative Variable Importance (0–100%)",
                "labels": [x["predictor"] for x in imp[:10]],
                "values": [x["relative_importance"] for x in imp[:10]],
                "xlabel": "Relative Importance (%)",
                "unit": "%",
                "fill": "#2563eb",
            })
        if kind == "random_forest":
            if r.get("oob_curve"):
                curve = r["oob_curve"]
                panels.append({
                    "kind": "phase6_chart",
                    "mode": "line",
                    "title": "OOB Error / RMSE Convergence vs. Trees",
                    "series": [{"label": "OOB Metric", "x": [c["trees"] for c in curve], "y": [c["metric"] for c in curve], "color": "#dc2626", "dash": False}],
                    "xlabel": "Number of Trees",
                    "ylabel": "OOB RMSE" if r.get("task") == "regression" else "OOB Error",
                })
            panels.extend(_maybe_roc_panel(r, (r.get("oob_metrics") or {}).get("roc_auc")))
        elif kind == "treenet_gbm":
            if r.get("history"):
                hist = r["history"]
                panels.append({
                    "kind": "phase6_chart",
                    "mode": "line",
                    "title": f"Training vs. Validation Loss (Opt Trees = {r.get('optimal_trees')})",
                    "series": [
                        {"label": "Train", "x": [h["trees"] for h in hist], "y": [h["train_loss"] for h in hist], "color": "#2563eb", "dash": False},
                        {"label": "Validation", "x": [h["trees"] for h in hist], "y": [h["val_loss"] for h in hist], "color": "#dc2626", "dash": True},
                    ],
                    "xlabel": "Boosting Iterations",
                    "ylabel": "Loss",
                })
            pdp = r.get("top_pdp") or []
            if pdp and imp:
                y_key = "y_hat" if "y_hat" in pdp[0] else "prob_class1"
                panels.append({
                    "kind": "phase6_chart",
                    "mode": "line",
                    "title": f"Partial Dependence: {imp[0]['predictor']}",
                    "series": [{"label": "Fitted Response", "x": [pt["x"] for pt in pdp], "y": [pt[y_key] for pt in pdp], "color": "#059669", "dash": False}],
                    "xlabel": imp[0]["predictor"],
                    "ylabel": "Predicted Mean" if y_key == "y_hat" else "P(Class 1)",
                })
            panels.extend(_maybe_roc_panel(r, (r.get("val_metrics") or {}).get("roc_auc")))
        elif kind == "mars_regression":
            panels.extend(_maybe_roc_panel(r, (r.get("metrics") or {}).get("roc_auc")))

    elif kind == "discover_best_model":
        lb = r.get("leaderboard") or []
        is_reg = r.get("task") == "regression"
        panels.append({
            "kind": "phase6_chart",
            "mode": "barh",
            "title": f"AutoML Model Leaderboard (Champion: {r.get('champion_model')})",
            "labels": [row["model"] for row in lb],
            "values": [max(0.0, (row["val_r2"] if is_reg else row["val_accuracy"]) * 100.0) for row in lb],
            "xlabel": "Validation R² (%)" if is_reg else "Validation Accuracy (%)",
            "unit": "%",
            "fill": "#16a34a",
        })

    elif kind in ("bootstrap_1sample", "bootstrap_2sample"):
        hist = r.get("histogram") or {}
        if hist.get("edges"):
            panels.append({
                "kind": "phase6_chart",
                "mode": "hist",
                "title": f"Bootstrap Sampling Distribution ({r.get('resamples')} resamples)",
                "edges": hist["edges"],
                "counts": hist["counts"],
                "vlines": [
                    {"x": r["observed"], "label": f"Obs={r['observed']:.3g}", "color": "#16a34a", "dash": False},
                    {"x": r["ci_low"], "label": f"LCL={r['ci_low']:.3g}", "color": "#dc2626", "dash": True},
                    {"x": r["ci_high"], "label": f"UCL={r['ci_high']:.3g}", "color": "#dc2626", "dash": True},
                ],
                "xlabel": r.get("statistic", "Statistic"),
                "ylabel": "Frequency",
                "fill": "#3b82f6",
            })

    elif kind in ("randomization_1sample", "randomization_2sample"):
        hist = r.get("histogram") or {}
        if hist.get("edges"):
            panels.append({
                "kind": "phase6_chart",
                "mode": "hist",
                "title": f"Permutation Null Distribution (p = {r['p_value']:.4f})",
                "edges": hist["edges"],
                "counts": hist["counts"],
                "vlines": [
                    {"x": r["observed_diff"], "label": f"Obs={r['observed_diff']:.3g}", "color": "#dc2626", "dash": False},
                ],
                "xlabel": "Permuted Difference",
                "ylabel": "Frequency",
                "fill": "#6366f1",
            })

    elif kind == "warranty_analysis" and r.get("forecasts"):
        fc = r["forecasts"]
        panels.append({
            "kind": "phase6_chart",
            "mode": "line",
            "title": f"Warranty Claims Forecast (Weibull β = {r['weibull_shape']:.2f})",
            "series": [{
                "label": "Expected Cumulative Claims",
                "x": [f["age"] for f in fc],
                "y": [f["expected_total_claims"] for f in fc],
                "color": "#ea580c",
                "dash": False,
            }],
            "xlabel": "Product Age / Time Horizon",
            "ylabel": "Cumulative Claims",
        })

    elif kind == "mixed_reml" and r.get("variance_components"):
        vcs = r["variance_components"]
        panels.append({
            "kind": "phase6_chart",
            "mode": "barh",
            "title": "REML Variance Components (% of Total Variance)",
            "labels": [v["source"] for v in vcs],
            "values": [v["pct_total"] for v in vcs],
            "xlabel": "Percent of Total Variance (%)",
            "unit": "%",
            "fill": "#0284c7",
        })

    elif kind == "fully_nested_anova" and r.get("rows"):
        items = list(r["rows"]) + [dict(r["error"], source="Error")]
        panels.append({
            "kind": "phase6_chart",
            "mode": "barh",
            "title": "Nested ANOVA Variance Contribution (%)",
            "labels": [it["source"] for it in items],
            "values": [it.get("pct_total", 0.0) for it in items],
            "xlabel": "Percent of Total Variance (%)",
            "unit": "%",
            "fill": "#0284c7",
        })

    elif kind == "six_sigma_product_report" and r.get("step_yields_pct"):
        ys = r["step_yields_pct"]
        panels.append({
            "kind": "phase6_chart",
            "mode": "barh",
            "title": f"Process Step Yields (%) — Overall RTY = {r['rty_pct']:.2f}%",
            "labels": [f"Step {i + 1}" for i in range(len(ys))],
            "values": list(ys),
            "xlabel": "Yield (%)",
            "unit": "%",
            "fill": "#10b981",
        })

    elif kind == "cox_ph_regression" and r.get("coefficients"):
        cs = r["coefficients"]
        panels.append({
            "kind": "phase6_chart",
            "mode": "barh",
            "title": f"Cox PH Hazard Ratios (Concordance = {r['concordance']:.3f})",
            "labels": [c["covariate"] for c in cs],
            "values": [min(50.0, c["hazard_ratio"]) for c in cs],
            "xlabel": "Hazard Ratio exp(β)",
            "unit": "x",
            "fill": "#e11d48",
        })

    chart.panels = panels
    chart.panel_columns = 2 if len(panels) > 1 else 1
    chart.note = f"StatCraft Vector Plot — {r.get('analysis', '')}"
    rows_n = (len(panels) + 1) // 2 if len(panels) > 1 else 1
    chart.setMinimumSize(760 if len(panels) > 1 else 560, max(400, 360 * rows_n))


def draw_panel(chart: Any, p: QPainter, area: QRectF, d: Dict[str, Any]) -> None:
    mode = d.get("mode", "barh")
    if mode == "hist":
        _draw_hist(chart, p, area, d)
    elif mode == "line":
        _draw_line(chart, p, area, d)
    else:
        _draw_barh(chart, p, area, d)


def _draw_barh(chart: Any, p: QPainter, area: QRectF, d: Dict[str, Any]) -> None:
    labels: Sequence[str] = d.get("labels", [])
    values: Sequence[float] = [float(v) for v in d.get("values", [])]
    if not labels or not values:
        return
    left_pad = 135.0
    plot = QRectF(area.left() + left_pad, area.top() + 34, max(80.0, area.width() - left_pad - 28), max(80.0, area.height() - 74))
    vmax = max(max(values), 1e-6)
    unit = d.get("unit", "")
    if unit == "%" and vmax <= 100.0:
        vmax = 100.0

    p.setPen(QPen(QColor("#e2e8f0"), 1))
    for g in range(5):
        gx = plot.left() + plot.width() * (g / 4.0)
        p.drawLine(QPointF(gx, plot.top()), QPointF(gx, plot.bottom()))
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor("#475569"))
        p.drawText(QRectF(gx - 28, plot.bottom() + 4, 56, 16), Qt.AlignmentFlag.AlignCenter, f"{vmax * g / 4.0:.3g}")
        p.setPen(QPen(QColor("#e2e8f0"), 1))

    p.setPen(QPen(QColor("#334155"), 1.2))
    p.drawLine(plot.bottomLeft(), plot.bottomRight())
    p.drawLine(plot.topLeft(), plot.bottomLeft())

    row_h = plot.height() / len(labels)
    bar_h = min(26.0, row_h * 0.65)
    fill_col = QColor(d.get("fill", "#2563eb"))

    for i, (lbl, val) in enumerate(zip(labels, values)):
        cy = plot.top() + row_h * (i + 0.5)
        bw = max(2.0, (val / vmax) * plot.width())
        rect = QRectF(plot.left(), cy - bar_h / 2.0, bw, bar_h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(fill_col))
        p.drawRoundedRect(rect, 3, 3)

        if hasattr(chart, "remember_hover"):
            chart.remember_hover(rect, {"text": f"{lbl}: {val:.4g}{unit}"}, clip=plot)

        p.setFont(QFont("Segoe UI", 8.5))
        p.setPen(QColor("#0f172a"))
        elided = p.fontMetrics().elidedText(str(lbl), Qt.TextElideMode.ElideRight, int(left_pad - 14))
        p.drawText(QRectF(area.left() + 6, cy - 10, left_pad - 14, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, elided)
        p.drawText(QRectF(rect.right() + 6, cy - 10, 64, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{val:.3g}{unit}")

    p.setFont(QFont("Segoe UI", 9))
    p.setPen(QColor("#334155"))
    p.drawText(QRectF(plot.left(), plot.bottom() + 20, plot.width(), 18), Qt.AlignmentFlag.AlignCenter, d.get("xlabel", ""))


def _draw_hist(chart: Any, p: QPainter, area: QRectF, d: Dict[str, Any]) -> None:
    edges: Sequence[float] = [float(e) for e in d.get("edges", [])]
    counts: Sequence[int] = [int(c) for c in d.get("counts", [])]
    if len(edges) < 2 or not counts:
        return
    plot = QRectF(area.left() + 64, area.top() + 34, max(80.0, area.width() - 92), max(80.0, area.height() - 78))

    vlines = d.get("vlines") or []
    x_min = min([edges[0]] + [float(v["x"]) for v in vlines])
    x_max = max([edges[-1]] + [float(v["x"]) for v in vlines])
    if x_max <= x_min:
        x_max = x_min + 1.0
    ymax = max(max(counts), 1) * 1.15

    def sx(val: float) -> float:
        return plot.left() + ((val - x_min) / (x_max - x_min)) * plot.width()

    def sy(val: float) -> float:
        return plot.bottom() - (val / ymax) * plot.height()

    p.setPen(QPen(QColor("#e2e8f0"), 1))
    for g in range(5):
        gy = plot.bottom() - plot.height() * (g / 4.0)
        p.drawLine(QPointF(plot.left(), gy), QPointF(plot.right(), gy))

    p.setBrush(QBrush(QColor(d.get("fill", "#3b82f6"))))
    p.setPen(QPen(QColor("#ffffff"), 0.8))
    for i, c in enumerate(counts):
        x0, x1 = sx(edges[i]), sx(edges[i + 1])
        y0 = sy(c)
        bar_rect = QRectF(x0, y0, max(1.0, x1 - x0), plot.bottom() - y0)
        p.drawRect(bar_rect)
        if hasattr(chart, "remember_hover") and c > 0:
            chart.remember_hover(bar_rect, {"text": f"Bin [{edges[i]:.4g}, {edges[i+1]:.4g}]\nCount: {c}"}, clip=plot)

    for vl in vlines:
        vx = sx(float(vl["x"]))
        pen = QPen(QColor(vl.get("color", "#dc2626")), 1.8)
        if vl.get("dash"):
            pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawLine(QPointF(vx, plot.top()), QPointF(vx, plot.bottom()))
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        p.drawText(QRectF(vx - 40, plot.top() - 16, 80, 15), Qt.AlignmentFlag.AlignCenter, vl.get("label", ""))

    p.setPen(QPen(QColor("#334155"), 1.2))
    p.drawLine(plot.bottomLeft(), plot.bottomRight())
    p.drawLine(plot.topLeft(), plot.bottomLeft())

    p.setFont(QFont("Segoe UI", 8))
    for g in range(5):
        xv = x_min + (x_max - x_min) * (g / 4.0)
        gx = sx(xv)
        p.drawText(QRectF(gx - 30, plot.bottom() + 4, 60, 16), Qt.AlignmentFlag.AlignCenter, f"{xv:.4g}")
    p.setFont(QFont("Segoe UI", 9))
    p.drawText(QRectF(plot.left(), plot.bottom() + 20, plot.width(), 18), Qt.AlignmentFlag.AlignCenter, d.get("xlabel", ""))


def _draw_line(chart: Any, p: QPainter, area: QRectF, d: Dict[str, Any]) -> None:
    series = d.get("series") or []
    all_x = [float(v) for s in series for v in s.get("x", [])]
    all_y = [float(v) for s in series for v in s.get("y", [])]
    if not all_x or not all_y:
        return
    plot = QRectF(area.left() + 68, area.top() + 34, max(80.0, area.width() - 96), max(80.0, area.height() - 78))
    xmin, xmax = min(all_x), max(all_x)
    ymin, ymax = min(all_y), max(all_y)
    if xmax <= xmin:
        xmax = xmin + 1.0
    if ymax <= ymin:
        ymax = ymin + 1.0

    def sx(v: float) -> float:
        return plot.left() + ((v - xmin) / (xmax - xmin)) * plot.width()

    def sy(v: float) -> float:
        return plot.bottom() - ((v - ymin) / (ymax - ymin)) * plot.height()

    p.setPen(QPen(QColor("#e2e8f0"), 1))
    for g in range(5):
        gy = plot.bottom() - plot.height() * (g / 4.0)
        p.drawLine(QPointF(plot.left(), gy), QPointF(plot.right(), gy))
        yv = ymin + (ymax - ymin) * (g / 4.0)
        p.setPen(QColor("#475569"))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(area.left() + 4, gy - 8, 60, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{yv:.3g}")
        p.setPen(QPen(QColor("#e2e8f0"), 1))

    for s in series:
        xs, ys = s.get("x", []), s.get("y", [])
        if not xs:
            continue
        col = QColor(s.get("color", "#2563eb"))
        pen = QPen(col, 2.0)
        if s.get("dash"):
            pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        pts = [QPointF(sx(xs[i]), sy(ys[i])) for i in range(len(xs))]
        path.moveTo(pts[0])
        for pt in pts[1:]:
            path.lineTo(pt)
        p.drawPath(path)

        if not s.get("dash") and len(pts) <= 30:
            p.setBrush(QBrush(col))
            for i, pt in enumerate(pts):
                p.drawEllipse(pt, 3.0, 3.0)
                if hasattr(chart, "remember_point_hover"):
                    chart.remember_point_hover(pt, {"text": f"{s.get('label', 'Series')}\nX = {xs[i]:.4g}, Y = {ys[i]:.4g}"}, size=10, clip=plot)

    p.setPen(QPen(QColor("#334155"), 1.2))
    p.drawLine(plot.bottomLeft(), plot.bottomRight())
    p.drawLine(plot.topLeft(), plot.bottomLeft())

    p.setFont(QFont("Segoe UI", 8))
    for g in range(5):
        xv = xmin + (xmax - xmin) * (g / 4.0)
        p.drawText(QRectF(sx(xv) - 28, plot.bottom() + 4, 56, 16), Qt.AlignmentFlag.AlignCenter, f"{xv:.3g}")
    p.setFont(QFont("Segoe UI", 9))
    p.drawText(QRectF(plot.left(), plot.bottom() + 20, plot.width(), 18), Qt.AlignmentFlag.AlignCenter, d.get("xlabel", ""))

    # Multi-series legend in top-right corner
    if len(series) > 1:
        p.setFont(QFont("Segoe UI", 8))
        leg_w = 132.0
        leg_h = 12.0 + 16.0 * len(series)
        leg_rect = QRectF(plot.right() - leg_w - 8, plot.top() + 8, leg_w, leg_h)
        p.setBrush(QBrush(QColor(255, 255, 255, 225)))
        p.setPen(QPen(QColor("#cbd5e1"), 1))
        p.drawRoundedRect(leg_rect, 4, 4)
        for li, s in enumerate(series):
            ly = leg_rect.top() + 14.0 + li * 16.0
            lpen = QPen(QColor(s.get("color", "#2563eb")), 2.0)
            if s.get("dash"):
                lpen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(lpen)
            p.drawLine(QPointF(leg_rect.left() + 8, ly), QPointF(leg_rect.left() + 26, ly))
            p.setPen(QColor("#0f172a"))
            lbl_s = p.fontMetrics().elidedText(str(s.get("label", f"Series {li+1}")), Qt.TextElideMode.ElideRight, int(leg_w - 36))
            p.drawText(QRectF(leg_rect.left() + 30, ly - 8, leg_w - 36, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lbl_s)
