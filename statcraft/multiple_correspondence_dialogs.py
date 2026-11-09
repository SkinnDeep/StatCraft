"""Qt Dialog for Multiple Correspondence Analysis with authentic Minitab layout."""
from __future__ import annotations

from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QMessageBox,
    QSpinBox,
    QWidget,
)

from .variable_dialogs import ProcedureDialog


class MultipleCorrespondenceDialog(ProcedureDialog):
    """Minitab-standard Multiple Correspondence Analysis dialog."""

    def __init__(self, window: Any):
        ws = window.presenter.worksheet if hasattr(window, "presenter") else (getattr(window, "worksheet", window))
        q_parent = window if isinstance(window, QWidget) else None

        specs = [
            dict(
                key="variable_indices",
                label="Categorical variables:",
                multiple=True,
                kinds=("text", "number"),
            ),
        ]

        super().__init__(
            q_parent,
            "Multiple Correspondence Analysis",
            ws,
            specs,
            (),
            "Analyzes associations among multiple categorical variables using an indicator matrix.",
        )
        self.window = window
        self.result_params: Optional[Dict[str, Any]] = None

        grp_opt = QGroupBox("Model Options")
        form_opt = QFormLayout(grp_opt)

        self.spin_comp = QSpinBox()
        self.spin_comp.setRange(1, 10)
        self.spin_comp.setValue(2)
        form_opt.addRow("Number of components:", self.spin_comp)

        self.layout().addWidget(grp_opt)

    def accept(self) -> None:
        raw = self.values()
        v_idxs = raw.get("variable_indices")

        if not v_idxs or len(v_idxs) < 2:
            QMessageBox.warning(self, "Multiple Correspondence", "Please select at least two categorical variables.")
            return

        n_comp = self.spin_comp.value()

        self.result_params = {
            "variable_columns": list(v_idxs),
            "n_components": n_comp,
        }
        super().accept()
