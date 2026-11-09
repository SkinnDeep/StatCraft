"""Qt Dialog for Nonlinear Regression with authentic Minitab layout and behavior."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from .variable_dialogs import ProcedureDialog


class NonlinearRegressionDialog(ProcedureDialog):
    """Minitab-standard Nonlinear Regression dialog."""

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
            "Nonlinear Regression",
            ws,
            specs,
            (),
            "Fits a nonlinear regression model using the Gauss-Newton / Levenberg-Marquardt algorithm.",
        )
        self.window = window

        grp_opt = QGroupBox("Nonlinear Model Function")
        form_opt = QFormLayout(grp_opt)

        self.combo_model = QComboBox()
        self.combo_model.addItem("Asymptotic Regression (th1 + th2 * exp(-th3 * X))", "asymptotic")
        self.combo_model.addItem("Michaelis-Menten ((th1 * X) / (th2 + X))", "michaelis_menten")
        self.combo_model.addItem("Logistic Growth (th1 / (1 + exp(th2 - th3 * X)))", "logistic")
        self.combo_model.addItem("Gompertz Growth (th1 * exp(-exp(th2 - th3 * X)))", "gompertz")
        self.combo_model.addItem("Power Function (th1 * X^th2)", "power")
        self.combo_model.addItem("Custom Formula…", "custom")
        self.combo_model.currentIndexChanged.connect(self._on_model_changed)
        form_opt.addRow("Model function:", self.combo_model)

        self.edit_formula = QLineEdit()
        self.edit_formula.setPlaceholderText("e.g. th1 * exp(-th2 * X1) + th3")
        self.edit_formula.setEnabled(False)
        form_opt.addRow("Custom formula:", self.edit_formula)

        self.edit_params = QLineEdit()
        self.edit_params.setPlaceholderText("e.g. th1, th2, th3 (for custom formula)")
        self.edit_params.setEnabled(False)
        form_opt.addRow("Parameter names:", self.edit_params)

        self.edit_init = QLineEdit()
        self.edit_init.setPlaceholderText("Optional (e.g. 1.0, 0.5, 0.1)")
        form_opt.addRow("Initial values:", self.edit_init)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.99)
        self.spin_conf.setValue(95.0)
        self.spin_conf.setSuffix(" %")
        form_opt.addRow("Confidence level:", self.spin_conf)

        self.layout().insertWidget(self.layout().count() - 2, grp_opt)

    def _on_model_changed(self, idx: int) -> None:
        is_custom = self.combo_model.currentData() == "custom"
        self.edit_formula.setEnabled(is_custom)
        self.edit_params.setEnabled(is_custom)

    def validate(self) -> None:
        p = self.parameters
        resp_idx = p.get("response_index")
        pred_idxs = p.get("predictor_indices", []) or []

        if resp_idx is None:
            QMessageBox.warning(self, "Nonlinear Regression", "Please select a response variable.")
            return

        if not pred_idxs:
            QMessageBox.warning(self, "Nonlinear Regression", "Please select at least one predictor.")
            return

        if resp_idx in pred_idxs:
            QMessageBox.warning(
                self,
                "Nonlinear Regression",
                "Response variable cannot also be included as a predictor.",
            )
            return

        model = self.combo_model.currentData()
        formula = None
        param_names = None
        if model == "custom":
            formula = self.edit_formula.text().strip()
            if not formula:
                QMessageBox.warning(self, "Nonlinear Regression", "Please enter a custom formula expression.")
                return
            p_text = self.edit_params.text().strip()
            if not p_text:
                QMessageBox.warning(self, "Nonlinear Regression", "Please enter parameter names for the custom formula.")
                return
            param_names = [x.strip() for x in p_text.split(",") if x.strip()]

        init_vals = None
        init_text = self.edit_init.text().strip()
        if init_text:
            try:
                init_vals = [float(x.strip()) for x in init_text.split(",") if x.strip()]
            except ValueError:
                QMessageBox.warning(self, "Nonlinear Regression", "Enter valid comma-separated numeric initial values.")
                return

        settings = {
            "response_index": resp_idx,
            "predictor_indices": pred_idxs,
            "model": model,
            "custom_formula": formula,
            "parameter_names": param_names,
            "initial_values": init_vals,
            "confidence": self.spin_conf.value() / 100.0,
        }

        self.result_params = {
            "action": "nonlinear_regression",
            "settings": settings,
        }
        self.accept()
