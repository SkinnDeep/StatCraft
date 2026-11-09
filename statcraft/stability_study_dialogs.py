"""Qt Dialog for Stability Study (Shelf Life Estimation) with authentic Minitab layout."""
from __future__ import annotations

from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from .variable_dialogs import ProcedureDialog


class StabilityStudyDialog(ProcedureDialog):
    """Minitab-standard Stability Study dialog."""

    def __init__(self, window: Any):
        ws = window.presenter.worksheet if hasattr(window, "presenter") else (getattr(window, "worksheet", window))
        q_parent = window if isinstance(window, QWidget) else None

        specs = [
            dict(key="response_index", label="Response (e.g. Potency):", kinds=("number",)),
            dict(key="time_index", label="Time variable (e.g. Month):", kinds=("number",)),
            dict(key="batch_index", label="Batch variable:", kinds=("number", "text")),
        ]

        super().__init__(
            q_parent,
            "Stability Study",
            ws,
            specs,
            (),
            "Estimates product shelf life / expiration period across batches per ICH Q1E guidelines.",
        )
        self.window = window
        self.result_params: Optional[Dict[str, Any]] = None

        # Specification limits group
        spec_box = QGroupBox("Specification Limits")
        spec_layout = QGridLayout(spec_box)

        lbl_lsl = QLabel("Lower specification limit (LSL):")
        self.edit_lsl = QLineEdit()
        spec_layout.addWidget(lbl_lsl, 0, 0)
        spec_layout.addWidget(self.edit_lsl, 0, 1)

        lbl_usl = QLabel("Upper specification limit (USL):")
        self.edit_usl = QLineEdit()
        spec_layout.addWidget(lbl_usl, 1, 0)
        spec_layout.addWidget(self.edit_usl, 1, 1)
        self.layout().addWidget(spec_box)

        # Options group
        opt_box = QGroupBox("Model Options")
        form_opt = QFormLayout(opt_box)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.01, 0.50)
        self.spin_alpha.setDecimals(2)
        self.spin_alpha.setSingleStep(0.05)
        self.spin_alpha.setValue(0.25)
        form_opt.addRow("Significance level for pooling batches:", self.spin_alpha)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.99)
        self.spin_conf.setDecimals(1)
        self.spin_conf.setValue(95.0)
        form_opt.addRow("Confidence level for shelf life (%):", self.spin_conf)
        self.layout().addWidget(opt_box)

    def accept(self) -> None:
        raw = self.values()
        r_idx = raw.get("response_index")
        t_idx = raw.get("time_index")
        b_idx = raw.get("batch_index")

        if r_idx is None:
            QMessageBox.warning(self, "Stability Study", "Please select a response variable.")
            return
        if t_idx is None:
            QMessageBox.warning(self, "Stability Study", "Please select a time variable.")
            return
        if b_idx is None:
            QMessageBox.warning(self, "Stability Study", "Please select a batch variable.")
            return

        lsl_val = None
        if self.edit_lsl.text().strip():
            try:
                lsl_val = float(self.edit_lsl.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Stability Study", "Invalid Lower Specification Limit.")
                return

        usl_val = None
        if self.edit_usl.text().strip():
            try:
                usl_val = float(self.edit_usl.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Stability Study", "Invalid Upper Specification Limit.")
                return

        if lsl_val is None and usl_val is None:
            QMessageBox.warning(self, "Stability Study", "Please specify at least one specification limit (LSL or USL).")
            return

        alpha_pool = self.spin_alpha.value()
        conf = self.spin_conf.value() / 100.0

        self.result_params = {
            "response_column": r_idx,
            "time_column": t_idx,
            "batch_column": b_idx,
            "lsl": lsl_val,
            "usl": usl_val,
            "alpha_pool": alpha_pool,
            "confidence": conf,
        }
        super().accept()
