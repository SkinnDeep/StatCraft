"""Qt Dialog for Probit Analysis with authentic Minitab layout."""
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


class ProbitAnalysisDialog(ProcedureDialog):
    """Minitab-standard Probit Analysis dialog."""

    def __init__(self, window: Any):
        ws = window.presenter.worksheet if hasattr(window, "presenter") else (getattr(window, "worksheet", window))
        q_parent = window if isinstance(window, QWidget) else None

        specs = [
            dict(key="response_index", label="Response (Events):", kinds=("number",)),
            dict(key="trials_index", label="Number of trials (optional):", required=False, kinds=("number",)),
            dict(key="dose_index", label="Stress / Stimulus (Dose):", kinds=("number",)),
        ]

        super().__init__(
            q_parent,
            "Probit Analysis",
            ws,
            specs,
            (),
            "Evaluates the relationship between stimulus levels and proportion responding (LD50 / ED50 analysis).",
        )
        self.window = window
        self.result_params: Optional[Dict[str, Any]] = None

        grp_opt = QGroupBox("Model Options")
        form_opt = QFormLayout(grp_opt)

        self.cbo_dist = QComboBox()
        self.cbo_dist.addItems(["Probit", "Logit", "Weibull", "Gompertz"])
        form_opt.addRow("Assumed distribution:", self.cbo_dist)

        self.cbo_trans = QComboBox()
        self.cbo_trans.addItem("None", "none")
        self.cbo_trans.addItem("Natural Log (ln)", "ln")
        self.cbo_trans.addItem("Log base 10", "log10")
        form_opt.addRow("Transform dose:", self.cbo_trans)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.99)
        self.spin_conf.setDecimals(1)
        self.spin_conf.setValue(95.0)
        form_opt.addRow("Confidence level (%):", self.spin_conf)

        self.layout().addWidget(grp_opt)

    def accept(self) -> None:
        raw = self.values()
        resp_idx = raw.get("response_index")
        trials_idx = raw.get("trials_index")
        dose_idx = raw.get("dose_index")

        if resp_idx is None:
            QMessageBox.warning(self, "Probit Analysis", "Please select a response (events) variable.")
            return
        if dose_idx is None:
            QMessageBox.warning(self, "Probit Analysis", "Please select a stress / stimulus (dose) variable.")
            return

        dist = self.cbo_dist.currentText().lower()
        trans = self.cbo_trans.currentData()
        conf = self.spin_conf.value() / 100.0

        self.result_params = {
            "response_column": resp_idx,
            "trials_column": trials_idx,
            "dose_column": dose_idx,
            "distribution": dist,
            "dose_transform": trans,
            "confidence": conf,
        }
        super().accept()
