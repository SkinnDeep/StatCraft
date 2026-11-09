"""Qt Dialogs for Repairable Systems Analysis with authentic Minitab layout."""
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


class NonparametricGrowthCurveDialog(ProcedureDialog):
    """Minitab-standard Nonparametric Growth Curve (Mean Cumulative Function - MCF) dialog."""

    def __init__(self, window: Any):
        ws = window.presenter.worksheet if hasattr(window, "presenter") else (getattr(window, "worksheet", window))
        q_parent = window if isinstance(window, QWidget) else None

        specs = [
            dict(key="time_index", label="Event / Operating time:", kinds=("number",)),
            dict(key="system_index", label="System ID:", kinds=("number", "text")),
            dict(key="event_index", label="Event count / indicator (optional):", required=False, kinds=("number",)),
            dict(key="cost_index", label="Cost (optional):", required=False, kinds=("number",)),
        ]

        super().__init__(
            q_parent,
            "Nonparametric Growth Curve (MCF)",
            ws,
            specs,
            (),
            "Estimates the Mean Cumulative Function (MCF) of repairs or recurrent event costs over operating time.",
        )
        self.window = window
        self.result_params: Optional[Dict[str, Any]] = None

        grp_opt = QGroupBox("Options")
        form_opt = QFormLayout(grp_opt)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.99)
        self.spin_conf.setDecimals(1)
        self.spin_conf.setValue(95.0)
        form_opt.addRow("Confidence level (%):", self.spin_conf)

        self.layout().addWidget(grp_opt)

    def accept(self) -> None:
        raw = self.values()
        t_idx = raw.get("time_index")
        s_idx = raw.get("system_index")
        ev_idx = raw.get("event_index")
        c_idx = raw.get("cost_index")

        if t_idx is None:
            QMessageBox.warning(self, "Growth Curve", "Please select an event / operating time variable.")
            return
        if s_idx is None:
            QMessageBox.warning(self, "Growth Curve", "Please select a system ID variable.")
            return

        conf = self.spin_conf.value() / 100.0

        self.result_params = {
            "time_column": t_idx,
            "system_column": s_idx,
            "event_column": ev_idx,
            "cost_column": c_idx,
            "confidence": conf,
        }
        super().accept()


class ParametricGrowthCurveDialog(ProcedureDialog):
    """Minitab-standard Parametric Growth Curve (Crow-AMSAA / Power Law Process) dialog."""

    def __init__(self, window: Any):
        ws = window.presenter.worksheet if hasattr(window, "presenter") else (getattr(window, "worksheet", window))
        q_parent = window if isinstance(window, QWidget) else None

        specs = [
            dict(key="time_index", label="Event / Operating time:", kinds=("number",)),
            dict(key="system_index", label="System ID:", kinds=("number", "text")),
            dict(key="event_index", label="Event indicator (optional):", required=False, kinds=("number",)),
        ]

        super().__init__(
            q_parent,
            "Parametric Growth Curve (Power Law)",
            ws,
            specs,
            (),
            "Models repair rate trends, evaluates reliability growth, and estimates MTBF using Crow-AMSAA NHPP.",
        )
        self.window = window
        self.result_params: Optional[Dict[str, Any]] = None

        grp_opt = QGroupBox("Options")
        form_opt = QFormLayout(grp_opt)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.99)
        self.spin_conf.setDecimals(1)
        self.spin_conf.setValue(95.0)
        form_opt.addRow("Confidence level (%):", self.spin_conf)

        self.layout().addWidget(grp_opt)

    def accept(self) -> None:
        raw = self.values()
        t_idx = raw.get("time_index")
        s_idx = raw.get("system_index")
        ev_idx = raw.get("event_index")

        if t_idx is None:
            QMessageBox.warning(self, "Growth Curve", "Please select an event / operating time variable.")
            return
        if s_idx is None:
            QMessageBox.warning(self, "Growth Curve", "Please select a system ID variable.")
            return

        conf = self.spin_conf.value() / 100.0

        self.result_params = {
            "time_column": t_idx,
            "system_column": s_idx,
            "event_column": ev_idx,
            "confidence": conf,
        }
        super().accept()
