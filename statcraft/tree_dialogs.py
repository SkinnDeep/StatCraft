"""Interactive Qt dialog for CART® / Partition Decision Trees."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtWidgets import QWidget

from .variable_dialogs import ProcedureDialog


class DecisionTreeDialog(ProcedureDialog):
    """Procedure dialog for CART® Classification and Regression Trees."""

    def __init__(self, worksheet, parent: Optional[QWidget] = None):
        super().__init__(
            parent,
            "CART® / Partition Decision Tree",
            worksheet,
            selectors=(
                {"key": "response_index", "label": "Response variable (Y):"},
                {"key": "predictor_indices", "label": "Predictor variables (X):", "multiple": True, "minimum": 1},
            ),
            fields=(
                {
                    "key": "tree_type",
                    "label": "Tree type:",
                    "choices": ["Auto-detect", "Regression (Continuous Y)", "Classification (Categorical Y)"],
                    "default": "Auto-detect",
                },
                {"key": "max_depth", "label": "Maximum tree depth:", "numeric": True, "default": 5},
                {"key": "min_split_size", "label": "Minimum node split size:", "numeric": True, "default": 10},
                {"key": "min_leaf_size", "label": "Minimum leaf size:", "numeric": True, "default": 5},
            ),
            note=(
                "Builds a non-parametric recursive partitioning decision tree (CART®) for continuous or categorical "
                "responses. Automatically discovers non-linear interactions, ranks predictor importance, and "
                "visualizes the hierarchical decision splits."
            ),
        )

    def values(self) -> Dict[str, Any]:
        vals = super().values()
        r_idx = vals["response_index"]
        p_indices = vals.get("predictor_indices", [])

        if not p_indices:
            raise ValueError("Select at least one predictor variable.")

        if r_idx in p_indices:
            raise ValueError("Response variable cannot also be in the predictor variables list.")

        type_map = {
            "Auto-detect": "auto",
            "Regression (Continuous Y)": "regression",
            "Classification (Categorical Y)": "classification",
        }
        vals["tree_type"] = type_map.get(vals.get("tree_type"), "auto")
        vals["max_depth"] = int(vals.get("max_depth", 5))
        vals["min_split_size"] = int(vals.get("min_split_size", 10))
        vals["min_leaf_size"] = int(vals.get("min_leaf_size", 5))
        return vals
