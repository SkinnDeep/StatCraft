"""Qt Dialog for Orthogonal Regression (Deming Regression) with authentic Minitab layout."""
from __future__ import annotations

from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QMessageBox,
    QWidget,
)

from .variable_dialogs import ProcedureDialog


class OrthogonalRegressionDialog(ProcedureDialog):
    """Minitab-standard Orthogonal Regression dialog."""

    def __init__(self, window: Any):
        ws = window.presenter.worksheet if hasattr(window, "presenter") else (getattr(window, "worksheet", window))
        q_parent = window if isinstance(window, QWidget) else None

        specs = [
            dict(key="response_index", label="Response (Y):", kinds=("number",)),
            dict(key="predictor_index", label="Predictor (X):", kinds=("number",)),
        ]

        super().__init__(
            q_parent,
            "Orthogonal Regression",
            ws,
            specs,
            (),
            "Fits an orthogonal (Deming) regression line when both response and predictor contain measurement error.",
        )
        self.window = window
        self.result_params: Optional[Dict[str, Any]] = None

        grp_opt = QGroupBox("Model Options")
        form_opt = QFormLayout(grp_opt)

        self.spin_ratio = QDoubleSpinBox()
        self.spin_ratio.setRange(0.0001, 100000.0)
        self.spin_ratio.setDecimals(4)
        self.spin_ratio.setValue(1.0)
        form_opt.addRow("Error variance ratio (Y / X):", self.spin_ratio)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.99)
        self.spin_conf.setDecimals(1)
        self.spin_conf.setValue(95.0)
        form_opt.addRow("Confidence level (%):", self.spin_conf)

        self.layout().addWidget(grp_opt)

    def accept(self) -> None:
        raw = self.values()
        resp_idx = raw.get("response_index")
        pred_idx = raw.get("predictor_index")

        if resp_idx is None:
            QMessageBox.warning(self, "Orthogonal Regression", "Please select a response variable (Y).")
            return
        if pred_idx is None:
            QMessageBox.warning(self, "Orthogonal Regression", "Please select a predictor variable (X).")
            return
        if resp_idx == pred_idx:
            QMessageBox.warning(self, "Orthogonal Regression", "Response and predictor must be different columns.")
            return

        delta = self.spin_ratio.value()
        conf = self.spin_conf.value() / 100.0

        self.result_params = {
            "response_column": resp_idx,
            "predictor_column": pred_idx,
            "error_variance_ratio": delta,
            "confidence": conf,
        }
        super().accept()
