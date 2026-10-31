"""Interactive Qt dialog for Accelerated Life Testing (Stat > Reliability/Survival > Accelerated Life Testing...)."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import QWidget

from .variable_dialogs import ProcedureDialog


class AcceleratedLifeTestingDialog(ProcedureDialog):
    """Procedure dialog for Accelerated Life Testing (ALT)."""

    def __init__(self, worksheet, parent: Optional[QWidget] = None):
        super().__init__(
            parent,
            "Accelerated Life Testing",
            worksheet,
            selectors=(
                {"key": "time_index", "label": "Time variable:"},
                {"key": "stress_index", "label": "Accelerating stress variable:"},
                {"key": "censor_index", "label": "Censor variable (optional):", "optional": True},
            ),
            fields=(
                {
                    "key": "model",
                    "label": "Acceleration relationship:",
                    "choices": ["Arrhenius (Temperature)", "Inverse Power (Voltage/Stress)", "Log-linear", "Linear"],
                    "default": "Arrhenius (Temperature)",
                },
                {
                    "key": "distribution",
                    "label": "Assumed distribution:",
                    "choices": ["Weibull", "Lognormal", "Exponential", "Normal"],
                    "default": "Weibull",
                },
                {"key": "use_stress", "label": "Normal use stress condition:", "numeric": True, "default": 25.0},
                {"key": "confidence", "label": "Confidence level (%):", "numeric": True, "default": 95.0},
            ),
            note=(
                "Models the relationship between stress and lifetime with Maximum Likelihood Estimation (MLE). "
                "Extrapolates failure times and B-life percentiles down to normal operating conditions."
            ),
        )

    def values(self) -> Dict[str, Any]:
        vals = super().values()
        if vals["time_index"] == vals["stress_index"]:
            raise ValueError("Time variable and Stress variable must be different columns.")
        if vals.get("censor_index") is not None:
            if vals["censor_index"] in (vals["time_index"], vals["stress_index"]):
                raise ValueError("Censor column cannot be the same as Time or Stress column.")

        model_map = {
            "Arrhenius (Temperature)": "arrhenius",
            "Inverse Power (Voltage/Stress)": "inverse_power",
            "Log-linear": "log_linear",
            "Linear": "linear",
        }
        vals["model"] = model_map.get(vals.get("model"), "arrhenius")
        vals["distribution"] = str(vals.get("distribution", "weibull")).lower()
        return vals
