"""Interactive Qt Dialog for Process Screening."""
from __future__ import annotations

from typing import Any, Dict, Optional
from PySide6.QtWidgets import QWidget
from .variable_dialogs import ProcedureDialog


class ProcessScreeningDialog(ProcedureDialog):
    """Procedure dialog for JMP Process Screening platform."""

    def __init__(self, worksheet, parent: Optional[QWidget] = None):
        super().__init__(
            parent,
            "Process Screening (JMP Quality Platform)",
            worksheet,
            selectors=(
                {"key": "variable_indices", "label": "Process Variables (Y):", "multi": True, "min_count": 1, "max_count": 100},
            ),
            fields=(
                {"key": "subgroup_size", "label": "Subgroup Size (1 for I-MR, >1 for Xbar):", "numeric": True, "default": 1},
                {"key": "k_sigma", "label": "Control Limits Sigma (default 3.0):", "numeric": True, "default": 3.0},
            ),
            note=(
                "Flagship JMP Process Screening platform for Six Sigma and quality engineering. "
                "Simultaneously assesses hundreds of process variables across stability and capability: "
                "computes Stability Index (s_overall / s_within), flags out-of-control drift & Nelson alarms, "
                "evaluates Cp/Cpk/Pp/Ppk, and provides 1-click drilldown into Control Chart Builder."
            ),
        )

    def values(self) -> Dict[str, Any]:
        vals = super().values()
        vars_selected = vals.get("variable_indices", [])
        if not vars_selected:
            raise ValueError("Please select at least one process variable to screen.")

        sz = int(vals.get("subgroup_size", 1))
        if sz < 1 or sz > 500:
            raise ValueError("Subgroup size must be between 1 and 500.")
        vals["subgroup_size"] = sz

        ks = float(vals.get("k_sigma", 3.0))
        if ks <= 0 or ks > 10.0:
            raise ValueError("K-Sigma must be between 0.1 and 10.0.")
        vals["k_sigma"] = ks

        return vals
