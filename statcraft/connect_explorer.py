"""StatCraft Connect — Interactive Explorer Adapter.

Connects fitted regression, ANOVA, and response surface models directly to JMP-style
interactive visual platforms (Bivariate / Fit Y by X and Prediction Profiler)
without refitting or losing variable roles.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .modern_app import ModernWindow
    from .connect import ConnectedAnalysis


def open_interactive_explorer(window: "ModernWindow", entry: Dict[str, Any]) -> bool:
    """Open the fitted analysis in the appropriate interactive visual explorer."""
    connected_raw = entry.get("connected_analysis")
    result = entry.get("result", {})
    recipe = entry.get("recipe", {})

    if not connected_raw and not recipe:
        window.statusBar().showMessage("Select a statistical result card before opening Interactive Explorer.", 6000)
        return False

    ws = window.presenter.worksheet

    from .connect import create_connected_analysis_from_entry, ConnectedAnalysis
    connected = create_connected_analysis_from_entry(entry, ws)

    action = recipe.get("action") or (connected.analysis_type if connected else "")
    p_params = recipe.get("parameters", {})

    # Route 1: One-Way ANOVA -> JMP Oneway Platform (Fit Y by X)
    if action in ("oneway_anova", "one_way_anova"):
        y_idx = p_params.get("response_index")
        x_idx = p_params.get("factor_index")
        if y_idx is None and connected:
            for idx, col in enumerate(ws.columns):
                if col.name == connected.response_name:
                    y_idx = idx
                elif col.name in connected.predictor_names:
                    x_idx = idx
        if y_idx is not None and x_idx is not None and 0 <= y_idx < len(ws.columns) and 0 <= x_idx < len(ws.columns):
            window.set_ui_mode("jmp")
            fit_entry = window._call(
                lambda: window.presenter.fit_y_by_x(y_index=y_idx, x_index=x_idx),
                result=True
            )
            if fit_entry:
                window.show_result(fit_entry)
                window.statusBar().showMessage(
                    f"StatCraft Connect: Opened JMP Oneway Platform for {ws.columns[y_idx].name} by {ws.columns[x_idx].name}",
                    6000
                )
                return True

    # Route 2: Existing Fit Y by X -> Switch to JMP and display
    if action == "fit_y_by_x":
        window.set_ui_mode("jmp")
        window.show_result(entry)
        window.statusBar().showMessage("StatCraft Connect: Active JMP Fit Y by X Platform", 5000)
        return True

    # Resolve Response and Predictor names safely
    resp_name = connected.response_name if connected else result.get("response_name")
    pred_names = connected.predictor_names if connected else (
        result.get("factor_information") or result.get("variables", [])
    )
    if isinstance(pred_names, list) and pred_names and isinstance(pred_names[0], dict):
        pred_names = [f.get("name") for f in pred_names if isinstance(f, dict)]

    # Fallback to parameters if names are not resolved
    if not resp_name and "response_index" in p_params and 0 <= p_params["response_index"] < len(ws.columns):
        resp_name = ws.columns[p_params["response_index"]].name
    if not pred_names:
        idx_list = p_params.get("predictor_indices") or p_params.get("factor_indices") or []
        pred_names = [ws.columns[i].name for i in idx_list if 0 <= i < len(ws.columns)]

    # Find current column indices for response and predictors
    resp_idx = None
    pred_indices = []

    for i, col in enumerate(ws.columns):
        if col.name == resp_name:
            resp_idx = i
        if col.name in pred_names:
            pred_indices.append(i)

    if resp_idx is None or not pred_indices:
        window.statusBar().showMessage("Cannot open explorer: one or more model columns not found in active worksheet.", 8000)
        return False

    # Route 3: Single continuous predictor for regression -> Open JMP Fit Y by X Bivariate Platform
    if action == "multiple_regression" and len(pred_indices) == 1:
        x_idx = pred_indices[0]
        conf = connected.confidence if connected else p_params.get("confidence", 0.95)
        fit_entry = window._call(
            lambda: window.presenter.fit_y_by_x(y_index=resp_idx, x_index=x_idx, confidence=conf),
            result=True
        )
        if fit_entry:
            window.set_ui_mode("jmp")
            window.show_result(fit_entry)
            window.statusBar().showMessage(f"StatCraft Connect: Opened Bivariate Fit for {resp_name} vs {pred_names[0]}", 6000)
            return True

    # Route 4: Multiple predictors, Factorial, GLM, or Response Surface -> Open JMP Interactive Prediction Profiler
    model_recipe = copy.deepcopy(recipe)
    if not model_recipe and connected:
        if connected.analysis_type in ("analyze_response_surface", "response_surface"):
            model_recipe = {
                "action": "analyze_response_surface",
                "parameters": {
                    "response_index": resp_idx,
                    "factor_indices": pred_indices,
                    "coding": connected.metadata.get("coding"),
                    "terms": connected.metadata.get("terms"),
                    "options": connected.metadata.get("options", {"confidence": connected.confidence})
                }
            }
        elif connected.analysis_type in ("analyze_factorial", "analyze_factorial_terms", "factorial_regression"):
            model_recipe = {
                "action": "analyze_factorial",
                "parameters": {
                    "response_index": resp_idx,
                    "factor_indices": pred_indices,
                    "confidence": connected.confidence,
                    "selected_terms": connected.metadata.get("selected_terms"),
                    "max_order": connected.metadata.get("max_order", 2),
                }
            }
        elif connected.analysis_type in ("general_linear_model", "glm"):
            model_recipe = {
                "action": "general_linear_model",
                "parameters": {
                    "response_index": resp_idx,
                    "factor_indices": pred_indices,
                    "covariate_indices": [],
                    "terms": connected.metadata.get("terms"),
                    "options": connected.metadata.get("options", {"confidence": connected.confidence})
                }
            }
        else:
            model_recipe = {
                "action": "multiple_regression",
                "parameters": {
                    "response_index": resp_idx,
                    "predictor_indices": pred_indices,
                    "confidence": connected.confidence
                }
            }

    window.set_ui_mode("jmp")
    from .prediction_profiler_dialog import PredictionProfilerDialog
    dialog = PredictionProfilerDialog(window, ws, [model_recipe])
    dialog.setSizeGripEnabled(True)
    window._active_profiler_dialog = dialog
    dialog.exec()
    return True
