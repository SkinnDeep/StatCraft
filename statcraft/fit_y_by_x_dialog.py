"""Interactive Qt Dialog for JMP Fit Y by X platform."""
from __future__ import annotations

from typing import Any, Dict, Optional
from PySide6.QtWidgets import QWidget, QLabel, QComboBox, QHBoxLayout
from PySide6.QtCore import Qt

from .variable_dialogs import ProcedureDialog, resolve_variables
from .fit_y_by_x_engine import detect_platform


class FitYByXDialog(ProcedureDialog):
    """Procedure dialog for JMP Fit Y by X platform."""

    def __init__(self, worksheet, parent: Optional[QWidget] = None):
        super().__init__(
            parent,
            "Fit Y by X (JMP Analysis Platform)",
            worksheet,
            selectors=(
                {"key": "y_index", "label": "Y, Response:", "kinds": ("number", "text")},
                {"key": "x_index", "label": "X, Factor:", "kinds": ("number", "text")},
            ),
            fields=(
                {"key": "confidence", "label": "Confidence Level (0.50 – 0.999):", "numeric": True, "default": 0.95},
            ),
            note=(
                "Unified exploratory platform matching JMP's flagship 'Fit Y by X'. "
                "Automatically chooses Bivariate (Fit Line & Density Ellipses), "
                "Oneway ANOVA (with signature Means Diamonds & Tukey HSD), or "
                "Contingency (Mosaic Plot & Chi-Square tests)."
            ),
        )

        self.platform_label = QLabel("")
        self.platform_label.setWordWrap(True)
        if self.layout() is not None:
            self.layout().insertWidget(max(0, self.layout().count() - 2), self.platform_label)

        # Connect selector QLineEdits to update the detected platform badge dynamically
        for key in ("y_index", "x_index"):
            ctrl = self.controls.get(key)
            if ctrl is not None and hasattr(ctrl, "textChanged"):
                ctrl.textChanged.connect(self._update_detected_platform)

    def _update_detected_platform(self):
        try:
            y_idx = resolve_variables(self.controls["y_index"].text(), self.worksheet, ("number", "text"))
            x_idx = resolve_variables(self.controls["x_index"].text(), self.worksheet, ("number", "text"))
            if len(y_idx) == 1 and len(x_idx) == 1 and y_idx[0] != x_idx[0]:
                plat = detect_platform(self.worksheet, y_idx[0], x_idx[0])
                plat_names = {
                    "bivariate": "Bivariate (Fit Line & Density Ellipses)",
                    "oneway": "Oneway ANOVA (Means Diamonds & Tukey HSD)",
                    "contingency": "Contingency (Mosaic Plot & Chi-Square)",
                    "logistic": "Logistic Fit (Categorical Y by Continuous X)",
                }
                desc = plat_names.get(plat, plat.capitalize())
                self.platform_label.setText(f"<b>Detected Platform:</b> <span style='color: #0284c7; font-weight: bold;'>{desc}</span>")
        except Exception:
            self.platform_label.setText("")

    def values(self) -> Dict[str, Any]:
        vals = super().values()
        y_idx = vals["y_index"]
        x_idx = vals["x_index"]

        if y_idx == x_idx:
            raise ValueError("Y (Response) and X (Factor) must be different columns.")

        conf = float(vals.get("confidence", 0.95))
        if not (0.50 < conf < 1.0):
            raise ValueError("Confidence must be between 0.50 and 0.999.")
        vals["confidence"] = conf
        return vals
