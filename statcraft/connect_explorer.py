"""StatCraft Connect — Interactive Explorer Adapter.

Connects fitted regression and response surface models directly to JMP-style
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
    connected: Optional["ConnectedAnalysis"] = entry.get("connected_analysis")
    result = entry.get("result", {})
    recipe = entry.get("recipe", {})

    if not connected and not recipe:
        return False

    resp_name = connected.response_name if connected else result.get("response_name")
    pred_names = connected.predictor_names if connected else (
        result.get("factor_information") or result.get("variables", [])
    )
    if isinstance(pred_names, list) and pred_names and isinstance(pred_names[0], dict):
        pred_names = [f.get("name") for f in pred_names]

    ws = window.presenter.worksheet

    # Find current column indices for response and predictors
    resp_idx = None
    pred_indices = []

    for i, col in enumerate(ws.columns):
        if col.name == resp_name:
            resp_idx = i
        if col.name in pred_names:
            pred_indices.append(i)

    if resp_idx is None or not pred_indices:
        window.statusBar().showMessage("Cannot open explorer: one or more model columns not found.", 8000)
        return False

    action = recipe.get("action") or (connected.analysis_type if connected else "")

    # Single continuous predictor for simple regression -> Open JMP Fit Y by X Bivariate Platform
    if action == "multiple_regression" and len(pred_indices) == 1:
        x_idx = pred_indices[0]
        conf = connected.confidence if connected else recipe.get("parameters", {}).get("confidence", 0.95)
        fit_entry = window._call(
            lambda: window.presenter.fit_y_by_x(y_index=resp_idx, x_index=x_idx, confidence=conf),
            result=True
        )
        if fit_entry:
            window.set_ui_mode("jmp")
            window.show_result(fit_entry)
            window.statusBar().showMessage(f"StatCraft Connect: Opened Bivariate Fit for {resp_name} vs {pred_names[0]}", 6000)
            return True

    # Multiple predictors or Response Surface -> Open JMP-style Interactive Prediction Profiler
    model_recipe = copy.deepcopy(recipe)
    if not model_recipe and connected:
        if connected.analysis_type == "analyze_response_surface":
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
        else:
            model_recipe = {
                "action": "multiple_regression",
                "parameters": {
                    "response_index": resp_idx,
                    "predictor_indices": pred_indices,
                    "confidence": connected.confidence
                }
            }

    from .prediction_profiler_dialog import PredictionProfilerDialog
    dialog = PredictionProfilerDialog(window, ws, [model_recipe])
    dialog.exec()
    return True
