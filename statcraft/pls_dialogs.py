"""Qt Dialog for Partial Least Squares Regression with authentic Minitab layout and behavior."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QMessageBox,
    QRadioButton,
    QSpinBox,
    QWidget,
)

from .variable_dialogs import ProcedureDialog


class PLSDialog(ProcedureDialog):
    """Minitab-standard Partial Least Squares Regression dialog."""

    def __init__(self, window: Any):
        ws = window.presenter.worksheet if hasattr(window, "presenter") else (getattr(window, "worksheet", window))
        q_parent = window if isinstance(window, QWidget) else None

        specs = [
            dict(key="response_index", label="Response:", kinds=("number",)),
            dict(
                key="predictor_indices",
                label="Predictors:",
                multiple=True,
                minimum=1,
                kinds=("number",),
            ),
        ]

        super().__init__(
            q_parent,
            "Partial Least Squares",
            ws,
            specs,
            (),
            "Fits a Partial Least Squares regression model using NIPALS/SIMPLS and Cross-Validation.",
        )
        self.window = window

        grp_opt = QGroupBox("Component Selection")
        form_opt = QFormLayout(grp_opt)

        self.rb_auto = QRadioButton("Cross-validation (Automatic selection)")
        self.rb_auto.setChecked(True)
        form_opt.addRow(self.rb_auto)

        self.spin_max_comp = QSpinBox()
        self.spin_max_comp.setRange(1, 50)
        self.spin_max_comp.setValue(10)
        form_opt.addRow("Maximum components to evaluate:", self.spin_max_comp)

        self.rb_custom = QRadioButton("Specify number of components:")
        form_opt.addRow(self.rb_custom)

        self.spin_custom_comp = QSpinBox()
        self.spin_custom_comp.setRange(1, 50)
        self.spin_custom_comp.setValue(2)
        self.spin_custom_comp.setEnabled(False)
        form_opt.addRow("Number of components:", self.spin_custom_comp)

        self.rb_auto.toggled.connect(self._on_comp_mode_changed)

        self.layout().insertWidget(self.layout().count() - 2, grp_opt)

    def _on_comp_mode_changed(self, auto_checked: bool) -> None:
        self.spin_max_comp.setEnabled(auto_checked)
        self.spin_custom_comp.setEnabled(not auto_checked)

    def validate(self) -> None:
        p = self.parameters
        resp_idx = p.get("response_index")
        pred_idxs = p.get("predictor_indices", []) or []

        if resp_idx is None:
            QMessageBox.warning(self, "Partial Least Squares", "Please select a response variable.")
            return

        if not pred_idxs:
            QMessageBox.warning(self, "Partial Least Squares", "Please select at least one predictor.")
            return

        if resp_idx in pred_idxs:
            QMessageBox.warning(
                self,
                "Partial Least Squares",
                "Response variable cannot also be included as a predictor.",
            )
            return

        n_comp = None
        if self.rb_custom.isChecked():
            n_comp = self.spin_custom_comp.value()

        settings = {
            "response_index": resp_idx,
            "predictor_indices": pred_idxs,
            "n_components": n_comp,
            "max_components": self.spin_max_comp.value(),
        }

        self.result_params = {
            "action": "pls_regression",
            "settings": settings,
        }
        self.accept()
