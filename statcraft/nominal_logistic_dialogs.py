"""Qt Dialog for Nominal Logistic Regression with authentic Minitab layout and behavior."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from .variable_dialogs import ProcedureDialog


class NominalLogisticDialog(ProcedureDialog):
    """Minitab-standard Nominal Logistic Regression dialog."""

    def __init__(self, window: Any):
        ws = window.presenter.worksheet if hasattr(window, "presenter") else (getattr(window, "worksheet", window))
        q_parent = window if isinstance(window, QWidget) else None

        specs = [
            dict(key="response_index", label="Response:", kinds=("number", "text")),
            dict(
                key="continuous_indices",
                label="Continuous predictors:",
                multiple=True,
                required=False,
                kinds=("number",),
            ),
            dict(
                key="categorical_indices",
                label="Categorical predictors:",
                multiple=True,
                required=False,
                kinds=("number", "text"),
            ),
        ]

        super().__init__(
            q_parent,
            "Nominal Logistic Regression",
            ws,
            specs,
            (),
            "Fits a generalized logit / multinomial model to analyze unordered categorical responses.",
        )
        self.window = window

        grp_opt = QGroupBox("Options")
        form_opt = QFormLayout(grp_opt)

        self.edit_ref = QLineEdit()
        self.edit_ref.setPlaceholderText("Optional (defaults to first level)")
        form_opt.addRow("Reference event:", self.edit_ref)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.99)
        self.spin_conf.setDecimals(2)
        self.spin_conf.setValue(95.0)
        self.spin_conf.setSuffix(" %")
        form_opt.addRow("Confidence level:", self.spin_conf)

        self.layout().insertWidget(self.layout().count() - 2, grp_opt)

    def validate(self) -> None:
        p = self.parameters
        resp_idx = p.get("response_index")
        cont_idxs = p.get("continuous_indices", []) or []
        cat_idxs = p.get("categorical_indices", []) or []

        if resp_idx is None:
            QMessageBox.warning(self, "Nominal Logistic Regression", "Please select a response variable.")
            return

        if not cont_idxs and not cat_idxs:
            QMessageBox.warning(
                self,
                "Nominal Logistic Regression",
                "Please select at least one continuous or categorical predictor.",
            )
            return

        all_preds = set(cont_idxs).union(set(cat_idxs))
        if resp_idx in all_preds:
            QMessageBox.warning(
                self,
                "Nominal Logistic Regression",
                "Response variable cannot also be included as a predictor.",
            )
            return

        overlap = set(cont_idxs).intersection(set(cat_idxs))
        if overlap:
            QMessageBox.warning(
                self,
                "Nominal Logistic Regression",
                "A variable cannot be both continuous and categorical.",
            )
            return

        ref_val = self.edit_ref.text().strip() or None

        settings = {
            "response_index": resp_idx,
            "continuous_indices": cont_idxs,
            "categorical_indices": cat_idxs,
            "reference_level": ref_val,
            "confidence": self.spin_conf.value() / 100.0,
        }

        self.result_params = {
            "action": "nominal_logistic_regression",
            "settings": settings,
        }
        self.accept()
