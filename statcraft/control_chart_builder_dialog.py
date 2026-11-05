"""Interactive Qt Dialog for Control Chart Builder."""
from __future__ import annotations

from typing import Any, Dict, Optional
from PySide6.QtWidgets import QWidget
from .variable_dialogs import ProcedureDialog


class ControlChartBuilderDialog(ProcedureDialog):
    """Procedure dialog for JMP Control Chart Builder platform."""

    def __init__(self, worksheet, parent: Optional[QWidget] = None):
        super().__init__(
            parent,
            "Control Chart Builder (JMP Platform)",
            worksheet,
            selectors=(
                {"key": "y_indices", "label": "Y, Process Variables:", "multi": True, "min_count": 1, "max_count": 20},
                {"key": "subgroup_index", "label": "Subgroup Variable (optional):", "multi": False, "optional": True},
                {"key": "phase_index", "label": "Phase Variable (optional):", "multi": False, "optional": True},
            ),
            fields=(
                {"key": "subgroup_size", "label": "Subgroup Size (if no subgroup col):", "numeric": True, "default": 1},
                {"key": "chart_type", "label": "Chart Type (auto/imr/xbar_r/xbar_s):", "default": "auto"},
                {"key": "k_sigma", "label": "K-Sigma Limits (default 3.0):", "numeric": True, "default": 3.0},
            ),
            note=(
                "Flagship JMP interactive Control Chart Builder. "
                "Supports Shewhart Individual & Moving Range (I-MR), Xbar-R, and Xbar-S charts. "
                "Specify a Phase column to dynamically calculate separate control limits per phase "
                "with vertical phase dividers and Nelson out-of-control alarm rules."
            ),
        )

    def values(self) -> Dict[str, Any]:
        vals = super().values()
        y_cols = vals.get("y_indices", [])
        if not y_cols:
            raise ValueError("Please select at least one Process Variable (Y).")

        sz = int(vals.get("subgroup_size", 1))
        if sz < 1 or sz > 1000:
            raise ValueError("Subgroup size must be between 1 and 1000.")
        vals["subgroup_size"] = sz

        k_sig = float(vals.get("k_sigma", 3.0))
        if k_sig <= 0 or k_sig > 10.0:
            raise ValueError("K-Sigma must be between 0.1 and 10.0.")
        vals["k_sigma"] = k_sig

        ctype = str(vals.get("chart_type", "auto")).strip().lower()
        if ctype not in ("auto", "imr", "xbar_r", "xbar_s"):
            ctype = "auto"
        vals["chart_type"] = ctype

        return vals
