"""Qt Dialog for Factor Analysis with authentic Minitab layout."""
from __future__ import annotations

from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QMessageBox,
    QSpinBox,
    QWidget,
)

from .variable_dialogs import ProcedureDialog


class FactorAnalysisDialog(ProcedureDialog):
    """Minitab-standard Factor Analysis dialog."""

    def __init__(self, window: Any):
        ws = window.presenter.worksheet if hasattr(window, "presenter") else (getattr(window, "worksheet", window))
        q_parent = window if isinstance(window, QWidget) else None

        specs = [
            dict(
                key="variable_indices",
                label="Variables:",
                multiple=True,
                kinds=("number",),
            ),
        ]

        super().__init__(
            q_parent,
            "Factor Analysis",
            ws,
            specs,
            (),
            "Extracts latent factors from correlated variables using Principal Components and orthogonal rotations.",
        )
        self.window = window
        self.result_params: Optional[Dict[str, Any]] = None

        grp_opt = QGroupBox("Model Options")
        form_opt = QFormLayout(grp_opt)

        self.spin_factors = QSpinBox()
        self.spin_factors.setRange(0, 50)
        self.spin_factors.setValue(0)
        self.spin_factors.setSpecialValueText("Auto (Eigenvalue > 1)")
        form_opt.addRow("Number of factors:", self.spin_factors)

        self.cbo_rotation = QComboBox()
        self.cbo_rotation.addItems(["Varimax", "Quartimax", "Equamax", "None"])
        form_opt.addRow("Rotation method:", self.cbo_rotation)

        self.layout().addWidget(grp_opt)

    def accept(self) -> None:
        raw = self.values()
        v_idxs = raw.get("variable_indices")

        if not v_idxs or len(v_idxs) < 2:
            QMessageBox.warning(self, "Factor Analysis", "Please select at least two numeric variables.")
            return

        n_fac = self.spin_factors.value() if self.spin_factors.value() > 0 else None
        rot = self.cbo_rotation.currentText().lower()

        self.result_params = {
            "variable_columns": list(v_idxs),
            "n_factors": n_fac,
            "rotation": rot,
        }
        super().accept()
