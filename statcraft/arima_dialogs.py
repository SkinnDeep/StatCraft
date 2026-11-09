"""Qt Dialog for Box-Jenkins ARIMA Modeling with authentic Minitab fidelity."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .model import Worksheet
from .variable_dialogs import resolve_variables
from .time_series_dialogs import _TimeSeriesBaseDialog


class ARIMADialog(_TimeSeriesBaseDialog):
    """Minitab ARIMA Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "ARIMA", parent)
        self.resize(620, 520)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()

        # Series picker
        form_series = QFormLayout()
        self.edit_series = QLineEdit()
        self.last_active_edit = self.edit_series
        form_series.addRow("&Series:", self.edit_series)
        right_layout.addLayout(form_series)

        # Nonseasonal Box
        grp_nonseasonal = QGroupBox("Nonseasonal Model Orders")
        form_ns = QFormLayout(grp_nonseasonal)

        self.spin_p = QSpinBox()
        self.spin_p.setRange(0, 10)
        self.spin_p.setValue(1)
        form_ns.addRow("Autoregressive (p):", self.spin_p)

        self.spin_d = QSpinBox()
        self.spin_d.setRange(0, 5)
        self.spin_d.setValue(0)
        form_ns.addRow("Difference (d):", self.spin_d)

        self.spin_q = QSpinBox()
        self.spin_q.setRange(0, 10)
        self.spin_q.setValue(0)
        form_ns.addRow("Moving average (q):", self.spin_q)

        right_layout.addWidget(grp_nonseasonal)

        # Seasonal Box
        grp_seasonal = QGroupBox("Seasonal Model Orders")
        lay_s = QVBoxLayout(grp_seasonal)

        self.chk_seasonal = QCheckBox("Fit &seasonal model")
        lay_s.addWidget(self.chk_seasonal)

        form_s = QFormLayout()
        self.spin_P = QSpinBox()
        self.spin_P.setRange(0, 5)
        self.spin_P.setValue(0)
        self.spin_P.setEnabled(False)
        form_s.addRow("Seasonal AR (P):", self.spin_P)

        self.spin_D = QSpinBox()
        self.spin_D.setRange(0, 3)
        self.spin_D.setValue(0)
        self.spin_D.setEnabled(False)
        form_s.addRow("Seasonal Difference (D):", self.spin_D)

        self.spin_Q = QSpinBox()
        self.spin_Q.setRange(0, 5)
        self.spin_Q.setValue(0)
        self.spin_Q.setEnabled(False)
        form_s.addRow("Seasonal MA (Q):", self.spin_Q)

        self.spin_S = QSpinBox()
        self.spin_S.setRange(2, 365)
        self.spin_S.setValue(12)
        self.spin_S.setEnabled(False)
        form_s.addRow("Period (S):", self.spin_S)

        self.chk_seasonal.toggled.connect(self.spin_P.setEnabled)
        self.chk_seasonal.toggled.connect(self.spin_D.setEnabled)
        self.chk_seasonal.toggled.connect(self.spin_Q.setEnabled)
        self.chk_seasonal.toggled.connect(self.spin_S.setEnabled)

        lay_s.addLayout(form_s)
        right_layout.addWidget(grp_seasonal)

        # Constant term
        self.chk_constant = QCheckBox("Include &constant term in model")
        self.chk_constant.setChecked(True)
        right_layout.addWidget(self.chk_constant)

        # Forecasts
        grp_fc = QGroupBox("Forecasts")
        lay_fc = QHBoxLayout(grp_fc)
        self.chk_fc = QCheckBox("Generate &forecasts:")
        self.spin_fc = QSpinBox()
        self.spin_fc.setRange(1, 1000)
        self.spin_fc.setValue(6)
        self.spin_fc.setEnabled(False)
        self.chk_fc.toggled.connect(self.spin_fc.setEnabled)
        lay_fc.addWidget(self.chk_fc)
        lay_fc.addWidget(self.spin_fc)
        right_layout.addWidget(grp_fc)

        # Storage
        grp_store = QGroupBox("Storage in Worksheet")
        lay_store = QVBoxLayout(grp_store)
        self.chk_store_fits = QCheckBox("Fitted values (fits)")
        self.chk_store_residuals = QCheckBox("Residuals")
        self.chk_store_forecasts = QCheckBox("Forecasts")
        lay_store.addWidget(self.chk_store_fits)
        lay_store.addWidget(self.chk_store_residuals)
        lay_store.addWidget(self.chk_store_forecasts)
        right_layout.addWidget(grp_store)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)

        main_layout.addLayout(right_layout, stretch=2)

    def _on_accept(self) -> None:
        txt = self.edit_series.text().strip()
        if not txt:
            QMessageBox.warning(self, "ARIMA", "Please select a series column.")
            return

        resolved = resolve_variables(txt, self.worksheet, kinds=("number",))
        if not resolved:
            QMessageBox.warning(self, "ARIMA", f"Column '{txt}' not found in worksheet.")
            return

        p = self.spin_p.value()
        d = self.spin_d.value()
        q = self.spin_q.value()
        is_s = self.chk_seasonal.isChecked()
        P = self.spin_P.value() if is_s else 0
        D = self.spin_D.value() if is_s else 0
        Q = self.spin_Q.value() if is_s else 0
        S = self.spin_S.value() if is_s else 1

        if p == 0 and q == 0 and P == 0 and Q == 0 and not self.chk_constant.isChecked():
            QMessageBox.warning(self, "ARIMA", "Model must contain at least one AR, MA, or constant parameter.")
            return

        self.settings = {
            "series_index": resolved[0],
            "series_name": txt,
            "p": p,
            "d": d,
            "q": q,
            "P": P,
            "D": D,
            "Q": Q,
            "S": S,
            "include_constant": self.chk_constant.isChecked(),
            "forecasts": self.spin_fc.value() if self.chk_fc.isChecked() else 0,
            "store_fits": self.chk_store_fits.isChecked(),
            "store_residuals": self.chk_store_residuals.isChecked(),
            "store_forecasts": self.chk_store_forecasts.isChecked(),
        }
        self.accept()
