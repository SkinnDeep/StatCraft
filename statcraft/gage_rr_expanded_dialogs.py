"""Qt Dialog for Gage R&R Study (Expanded) with authentic Minitab layout and behavior."""
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


class GageRRExpandedDialog(ProcedureDialog):
    """Minitab-standard Gage R&R Study (Expanded) dialog."""

    def __init__(self, window: Any):
        ws = window.presenter.worksheet if hasattr(window, "presenter") else (getattr(window, "worksheet", window))
        q_parent = window if isinstance(window, QWidget) else None

        specs = [
            dict(key="measurement_index", label="Measurement:", kinds=("number",)),
            dict(key="part_index", label="Part:", kinds=("number", "text")),
            dict(key="operator_index", label="Operator:", kinds=("number", "text")),
            dict(
                key="additional_factor_indices",
                label="Additional factors:",
                multiple=True,
                required=False,
                kinds=("number", "text"),
            ),
        ]

        super().__init__(
            q_parent,
            "Gage R&R Study (Expanded)",
            ws,
            specs,
            (),
            "Performs Gage R&R evaluation with multiple factors (Part, Operator, Gage, Machine, etc.) using multi-factor ANOVA.",
        )
        self.window = window

        grp_opt = QGroupBox("Study Options")
        form_opt = QFormLayout(grp_opt)

        self.spin_mult = QDoubleSpinBox()
        self.spin_mult.setRange(1.0, 10.0)
        self.spin_mult.setValue(6.0)
        self.spin_mult.setSingleStep(0.1)
        form_opt.addRow("Study variation (SD multiplier):", self.spin_mult)

        self.edit_tolerance = QLineEdit()
        self.edit_tolerance.setPlaceholderText("e.g. 10.0 (USL - LSL)")
        form_opt.addRow("Process tolerance (optional):", self.edit_tolerance)

        self.edit_proc_sd = QLineEdit()
        self.edit_proc_sd.setPlaceholderText("e.g. 1.5")
        form_opt.addRow("Historical standard deviation (optional):", self.edit_proc_sd)

        self.layout().insertWidget(self.layout().count() - 2, grp_opt)

    def validate(self) -> None:
        p = self.parameters
        meas_idx = p.get("measurement_index")
        part_idx = p.get("part_index")
        op_idx = p.get("operator_index")
        add_idxs = p.get("additional_factor_indices", []) or []

        if meas_idx is None:
            QMessageBox.warning(self, "Expanded Gage R&R", "Please select a measurement column.")
            return

        if part_idx is None:
            QMessageBox.warning(self, "Expanded Gage R&R", "Please select a part column.")
            return

        if op_idx is None:
            QMessageBox.warning(self, "Expanded Gage R&R", "Please select an operator column.")
            return

        all_selected = [meas_idx, part_idx, op_idx] + add_idxs
        if len(set(all_selected)) != len(all_selected):
            QMessageBox.warning(self, "Expanded Gage R&R", "All selected columns must be distinct.")
            return

        tol = None
        tol_text = self.edit_tolerance.text().strip()
        if tol_text:
            try:
                tol = float(tol_text)
                if tol <= 0:
                    raise ValueError()
            except ValueError:
                QMessageBox.warning(self, "Expanded Gage R&R", "Process tolerance must be a positive number.")
                return

        proc_sd = None
        proc_text = self.edit_proc_sd.text().strip()
        if proc_text:
            try:
                proc_sd = float(proc_text)
                if proc_sd <= 0:
                    raise ValueError()
            except ValueError:
                QMessageBox.warning(self, "Expanded Gage R&R", "Historical standard deviation must be a positive number.")
                return

        settings = {
            "measurement_index": meas_idx,
            "part_index": part_idx,
            "operator_index": op_idx,
            "additional_factor_indices": add_idxs,
            "study_multiplier": self.spin_mult.value(),
            "tolerance": tol,
            "process_stdev": proc_sd,
        }

        self.result_params = {
            "action": "gage_rr_expanded",
            "settings": settings,
        }
        self.accept()
