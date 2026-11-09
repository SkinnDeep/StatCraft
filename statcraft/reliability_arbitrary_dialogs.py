"""Qt Dialog for Distribution Analysis (Arbitrary Censoring) with authentic Minitab layout and behavior."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
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


class ArbitraryCensoringDialog(ProcedureDialog):
    """Minitab-standard Parametric Distribution Analysis (Arbitrary Censoring) dialog."""

    def __init__(self, window: Any):
        ws = window.presenter.worksheet if hasattr(window, "presenter") else (getattr(window, "worksheet", window))
        q_parent = window if isinstance(window, QWidget) else None

        specs = [
            dict(key="start_index", label="Start variables:", kinds=("number",)),
            dict(key="end_index", label="End variables:", kinds=("number",)),
            dict(key="frequency_index", label="Frequency columns (optional):", required=False, kinds=("number",)),
        ]

        super().__init__(
            q_parent,
            "Parametric Distribution Analysis (Arbitrary Censoring)",
            ws,
            specs,
            (),
            "Fits a parametric lifetime distribution to arbitrarily censored (interval, left, right) survival data.",
        )
        self.window = window

        grp_opt = QGroupBox("Model Options")
        form_opt = QFormLayout(grp_opt)

        self.combo_dist = QComboBox()
        self.combo_dist.addItem("Weibull", "weibull")
        self.combo_dist.addItem("Lognormal", "lognormal")
        self.combo_dist.addItem("Exponential", "exponential")
        self.combo_dist.addItem("Normal", "normal")
        self.combo_dist.addItem("Loglogistic", "loglogistic")
        form_opt.addRow("Assumed distribution:", self.combo_dist)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.99)
        self.spin_conf.setValue(95.0)
        self.spin_conf.setSuffix(" %")
        form_opt.addRow("Confidence level:", self.spin_conf)

        self.layout().insertWidget(self.layout().count() - 2, grp_opt)

    def validate(self) -> None:
        p = self.parameters
        s_idx = p.get("start_index")
        e_idx = p.get("end_index")
        f_idx = p.get("frequency_index")

        if s_idx is None and e_idx is None:
            QMessageBox.warning(self, "Distribution Analysis", "Please select Start and/or End time variables.")
            return

        dist = self.combo_dist.currentData()
        conf = self.spin_conf.value() / 100.0

        settings = {
            "start_index": s_idx,
            "end_index": e_idx,
            "frequency_index": f_idx,
            "distribution": dist,
            "confidence": conf,
        }

        self.result_params = {
            "action": "reliability_arbitrary",
            "settings": settings,
        }
        self.accept()
