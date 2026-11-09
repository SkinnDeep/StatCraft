"""Qt Dialog for Winters' Method Exponential Smoothing with native StatCraft/Minitab PE fidelity."""
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
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .model import Worksheet
from .variable_dialogs import resolve_variables
from .time_series_dialogs import _TimeSeriesBaseDialog


class WintersMethodDialog(_TimeSeriesBaseDialog):
    """Winters' Method Exponential Smoothing Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Winters' Method", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()

        # Variable & Seasonal length
        form = QFormLayout()
        self.edit_series = QLineEdit()
        self.last_active_edit = self.edit_series
        form.addRow("&Series:", self.edit_series)

        self.spin_season = QSpinBox()
        self.spin_season.setRange(2, 1000)
        self.spin_season.setValue(4)
        form.addRow("Seasonal &length:", self.spin_season)
        right_layout.addLayout(form)

        # Method / Model type
        grp_model = QGroupBox("Method")
        lay_model = QHBoxLayout(grp_model)
        self.rb_multiplicative = QRadioButton("&Multiplicative")
        self.rb_multiplicative.setChecked(True)
        self.rb_additive = QRadioButton("&Additive")
        lay_model.addWidget(self.rb_multiplicative)
        lay_model.addWidget(self.rb_additive)
        right_layout.addWidget(grp_model)

        # Weights group
        grp_wt = QGroupBox("Weights to Use")
        lay_wt = QVBoxLayout(grp_wt)
        self.rb_optimal = QRadioButton("&Optimal weights (minimize MSD)")
        self.rb_optimal.setChecked(True)
        self.rb_custom = QRadioButton("Use &weights:")

        lay_params = QFormLayout()
        self.edit_alpha = QLineEdit("0.2")
        self.edit_gamma = QLineEdit("0.2")
        self.edit_delta = QLineEdit("0.2")
        self.edit_alpha.setEnabled(False)
        self.edit_gamma.setEnabled(False)
        self.edit_delta.setEnabled(False)

        self.rb_custom.toggled.connect(self.edit_alpha.setEnabled)
        self.rb_custom.toggled.connect(self.edit_gamma.setEnabled)
        self.rb_custom.toggled.connect(self.edit_delta.setEnabled)

        lay_params.addRow("Level (alpha):", self.edit_alpha)
        lay_params.addRow("Trend (gamma):", self.edit_gamma)
        lay_params.addRow("Seasonal (delta):", self.edit_delta)

        lay_wt.addWidget(self.rb_optimal)
        lay_wt.addWidget(self.rb_custom)
        lay_wt.addLayout(lay_params)
        right_layout.addWidget(grp_wt)

        # Forecasts
        grp_fc = QGroupBox("Forecasts")
        lay_fc = QHBoxLayout(grp_fc)
        self.chk_fc = QCheckBox("Generate &forecasts:")
        self.spin_fc = QSpinBox()
        self.spin_fc.setRange(1, 1000)
        self.spin_fc.setValue(4)
        self.spin_fc.setEnabled(False)
        self.chk_fc.toggled.connect(self.spin_fc.setEnabled)
        lay_fc.addWidget(self.chk_fc)
        lay_fc.addWidget(self.spin_fc)
        right_layout.addWidget(grp_fc)

        # Storage
        grp_store = QGroupBox("Storage in Worksheet")
        lay_store = QVBoxLayout(grp_store)
        self.chk_store_fits = QCheckBox("Smoothed values (fits)")
        self.chk_store_residuals = QCheckBox("Residuals")
        self.chk_store_forecasts = QCheckBox("Forecasts")
        lay_store.addWidget(self.chk_store_fits)
        lay_store.addWidget(self.chk_store_residuals)
        lay_store.addWidget(self.chk_store_forecasts)
        right_layout.addWidget(grp_store)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        right_layout.addWidget(button_box)

        main_layout.addLayout(right_layout, stretch=2)

    def _on_accept(self) -> None:
        txt = self.edit_series.text().strip()
        if not txt:
            QMessageBox.warning(self, "Winters' Method", "Please select a series column.")
            return
        resolved = resolve_variables(txt, self.worksheet, kinds=("number",))
        if not resolved:
            QMessageBox.warning(self, "Winters' Method", f"Variable '{txt}' not found in worksheet.")
            return

        alpha_val: Optional[float] = None
        gamma_val: Optional[float] = None
        delta_val: Optional[float] = None
        if self.rb_custom.isChecked():
            try:
                alpha_val = float(self.edit_alpha.text().strip())
                gamma_val = float(self.edit_gamma.text().strip())
                delta_val = float(self.edit_delta.text().strip())
                if not (
                    0.0 < alpha_val <= 1.0 and 0.0 < gamma_val <= 1.0 and 0.0 < delta_val <= 1.0
                ):
                    raise ValueError()
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Winters' Method",
                    "Weights alpha, gamma, and delta must all be between 0 and 1.",
                )
                return

        model_type = "multiplicative" if self.rb_multiplicative.isChecked() else "additive"

        self.settings = {
            "series_index": resolved[0],
            "series_name": txt,
            "season_length": self.spin_season.value(),
            "model": model_type,
            "alpha": alpha_val,
            "gamma": gamma_val,
            "delta": delta_val,
            "forecasts": self.spin_fc.value() if self.chk_fc.isChecked() else 0,
            "store_fits": self.chk_store_fits.isChecked(),
            "store_residuals": self.chk_store_residuals.isChecked(),
            "store_forecasts": self.chk_store_forecasts.isChecked(),
            "title": f"Winters' Method Plot for {txt}",
        }
        self.accept()
