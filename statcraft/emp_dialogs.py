"""Interactive Qt dialog for Evaluating the Measurement Process (Stat > Quality Tools > Gage Study > EMP...)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtWidgets import QWidget

from .variable_dialogs import ProcedureDialog


class EvaluatingMeasurementProcessDialog(ProcedureDialog):
    """Procedure dialog for Wheeler's Evaluating the Measurement Process (EMP)."""

    def __init__(self, worksheet, parent: Optional[QWidget] = None):
        super().__init__(
            parent,
            "Evaluating the Measurement Process (EMP — Wheeler)",
            worksheet,
            selectors=(
                {"key": "measurement_index", "label": "Measurement data (response):"},
                {"key": "part_index", "label": "Part / sample variable:"},
                {"key": "operator_index", "label": "Operator / appraiser variable:"},
            ),
            fields=(
                {"key": "alpha_interaction", "label": "Interaction alpha (pool threshold):", "numeric": True, "default": 0.05},
            ),
            note=(
                "Evaluates measurement system capability using Dr. Donald J. Wheeler's EMP methodology. "
                "Calculates Intraclass Correlation (ICC), signal attenuation, monitor classification "
                "(First, Second, Third, Fourth Class), Probable Error (PE), and data chunkiness."
            ),
        )

    def values(self) -> Dict[str, Any]:
        vals = super().values()
        m_idx = vals["measurement_index"]
        p_idx = vals["part_index"]
        o_idx = vals["operator_index"]

        if len({m_idx, p_idx, o_idx}) < 3:
            raise ValueError("Measurement, Part, and Operator must all be different columns.")

        vals["alpha_interaction"] = float(vals.get("alpha_interaction", 0.05))
        return vals
