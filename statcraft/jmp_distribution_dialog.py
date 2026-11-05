"""Interactive Qt Dialog for JMP Distribution platform."""
from __future__ import annotations

from typing import Any, Dict, Optional
from PySide6.QtWidgets import QWidget
from .variable_dialogs import ProcedureDialog


class JMPDistributionDialog(ProcedureDialog):
    """Procedure dialog for JMP Distribution platform."""

    def __init__(self, worksheet, parent: Optional[QWidget] = None):
        super().__init__(
            parent,
            "Distribution (JMP Analysis Platform)",
            worksheet,
            selectors=(
                {"key": "column_indices", "label": "Y, Columns:", "multi": True, "min_count": 1, "max_count": 50},
            ),
            fields=(
                {"key": "confidence", "label": "Confidence Level (0.50 – 0.999):", "numeric": True, "default": 0.95},
            ),
            note=(
                "Flagship JMP exploratory platform for univariate data. "
                "Generates Outlier Box Plots, Histograms with Normal Curve fit, "
                "Quantiles (100% Max to 0% Min), Summary Statistics (Mean, Std Dev, CI, Skewness, Kurtosis), "
                "and Categorical Frequencies."
            ),
        )

    def values(self) -> Dict[str, Any]:
        vals = super().values()
        cols = vals.get("column_indices", [])
        if not cols:
            raise ValueError("Please select at least one column to analyze.")

        conf = float(vals.get("confidence", 0.95))
        if not (0.50 < conf < 1.0):
            raise ValueError("Confidence level must be between 0.50 and 0.999.")
        vals["confidence"] = conf
        return vals
