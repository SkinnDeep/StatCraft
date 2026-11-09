"""Qt Dialog for Stepwise Regression with authentic Minitab layout and behavior."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QMessageBox,
)

from .variable_dialogs import ProcedureDialog


class StepwiseRegressionDialog(ProcedureDialog):
    """Minitab-standard Stepwise Regression dialog."""

    def __init__(self, window: Any):
        from PySide6.QtWidgets import QWidget
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
            "Stepwise Regression",
            ws,
            specs,
            (),
            "Performs Stepwise, Forward, or Backward regression selection to identify significant predictors.",
        )
        self.window = window

        grp = QGroupBox("Stepwise Options")
        form = QFormLayout(grp)

        self.combo_method = QComboBox()
        self.combo_method.addItem("Stepwise", "stepwise")
        self.combo_method.addItem("Forward selection", "forward")
        self.combo_method.addItem("Backward elimination", "backward")
        self.combo_method.addItem("Forward selection with AIC", "forward_aic")
        self.combo_method.addItem("Forward selection with BIC", "forward_bic")
        self.combo_method.addItem("Backward elimination with AIC", "backward_aic")
        self.combo_method.addItem("Backward elimination with BIC", "backward_bic")
        self.combo_method.currentIndexChanged.connect(self._on_method_changed)
        form.addRow("Method:", self.combo_method)

        self.spin_alpha_enter = QDoubleSpinBox()
        self.spin_alpha_enter.setRange(0.001, 0.999)
        self.spin_alpha_enter.setSingleStep(0.01)
        self.spin_alpha_enter.setDecimals(3)
        self.spin_alpha_enter.setValue(0.15)
        form.addRow("Alpha to enter:", self.spin_alpha_enter)

        self.spin_alpha_remove = QDoubleSpinBox()
        self.spin_alpha_remove.setRange(0.001, 0.999)
        self.spin_alpha_remove.setSingleStep(0.01)
        self.spin_alpha_remove.setDecimals(3)
        self.spin_alpha_remove.setValue(0.15)
        form.addRow("Alpha to remove:", self.spin_alpha_remove)

        self.layout().insertWidget(self.layout().count() - 2, grp)
        self._on_method_changed(0)

    def _on_method_changed(self, idx: int) -> None:
        method = self.combo_method.currentData()
        if method == "stepwise":
            self.spin_alpha_enter.setEnabled(True)
            self.spin_alpha_remove.setEnabled(True)
        elif method == "forward":
            self.spin_alpha_enter.setEnabled(True)
            self.spin_alpha_remove.setEnabled(False)
        elif method == "backward":
            self.spin_alpha_enter.setEnabled(False)
            self.spin_alpha_remove.setEnabled(True)
        else:
            # Information criteria methods (AIC/BIC) don't use alpha
            self.spin_alpha_enter.setEnabled(False)
            self.spin_alpha_remove.setEnabled(False)

    def validate(self) -> None:
        p = self.parameters
        resp_idx = p.get("response_index")
        pred_idxs = p.get("predictor_indices", [])

        if resp_idx is None:
            QMessageBox.warning(self, "Stepwise Regression", "Please select a response variable.")
            return

        if not pred_idxs:
            QMessageBox.warning(self, "Stepwise Regression", "Please select at least one predictor.")
            return

        if resp_idx in pred_idxs:
            QMessageBox.warning(
                self,
                "Stepwise Regression",
                "Response variable cannot also be included as a predictor.",
            )
            return

        method = self.combo_method.currentData()
        a_enter = self.spin_alpha_enter.value()
        a_remove = self.spin_alpha_remove.value()

        if method == "stepwise" and a_enter > a_remove:
            QMessageBox.warning(
                self,
                "Stepwise Regression",
                "Alpha to enter must be less than or equal to Alpha to remove.",
            )
            return

        settings = {
            "response_index": resp_idx,
            "predictor_indices": pred_idxs,
            "method": method,
            "alpha_to_enter": a_enter,
            "alpha_to_remove": a_remove,
        }

        self.result_params = {
            "action": "stepwise_regression",
            "settings": settings,
        }
        self.accept()
