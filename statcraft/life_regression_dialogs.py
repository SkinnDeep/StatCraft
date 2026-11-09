"""Qt Dialog for Regression with Life Data (Parametric Survival Regression)."""
from __future__ import annotations

from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QMessageBox,
    QWidget,
)

from .variable_dialogs import ProcedureDialog


class LifeRegressionDialog(ProcedureDialog):
    """Minitab-standard Regression with Life Data dialog."""

    def __init__(self, window: Any):
        ws = window.presenter.worksheet if hasattr(window, "presenter") else (getattr(window, "worksheet", window))
        q_parent = window if isinstance(window, QWidget) else None

        specs = [
            dict(key="response_index", label="Response (Life / Failure Time):", kinds=("number",)),
            dict(
                key="predictor_indices",
                label="Predictors:",
                multiple=True,
                kinds=("number",),
            ),
            dict(key="censor_index", label="Censor column (1=Fail, 0=Censor):", required=False, kinds=("number",)),
        ]

        super().__init__(
            q_parent,
            "Regression with Life Data",
            ws,
            specs,
            (),
            "Fits an Accelerated Failure Time (AFT) parametric survival regression model to censored lifetime data.",
        )
        self.window = window
        self.result_params: Optional[Dict[str, Any]] = None

        grp_opt = QGroupBox("Model Options")
        form_opt = QFormLayout(grp_opt)

        self.cbo_dist = QComboBox()
        self.cbo_dist.addItems(["Weibull", "Lognormal", "Exponential", "Loglogistic"])
        form_opt.addRow("Assumed distribution:", self.cbo_dist)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.99)
        self.spin_conf.setDecimals(1)
        self.spin_conf.setValue(95.0)
        form_opt.addRow("Confidence level (%):", self.spin_conf)

        self.layout().addWidget(grp_opt)

    def accept(self) -> None:
        raw = self.values()
        r_idx = raw.get("response_index")
        p_idxs = raw.get("predictor_indices")
        c_idx = raw.get("censor_index")

        if r_idx is None:
            QMessageBox.warning(self, "Life Regression", "Please select a response lifetime variable.")
            return
        if not p_idxs:
            QMessageBox.warning(self, "Life Regression", "Please select at least one predictor variable.")
            return

        dist = self.cbo_dist.currentText().lower()
        conf = self.spin_conf.value() / 100.0

        self.result_params = {
            "response_column": r_idx,
            "predictor_columns": list(p_idxs),
            "censor_column": c_idx,
            "distribution": dist,
            "confidence": conf,
        }
        super().accept()
