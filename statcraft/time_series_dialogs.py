"""Qt Dialogs for Time Series Analysis and Forecasting with native StatCraft PE fidelity.

Covers:
- TrendAnalysisDialog
- DecompositionDialog
- MovingAverageDialog
- SingleExpSmoothingDialog
- DoubleExpSmoothingDialog
- AutocorrelationDialog
- PartialAutocorrelationDialog
- DifferencesDialog
- LagDialog
"""
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


class _TimeSeriesBaseDialog(QDialog):
    """Base dialog providing standard column selector list and variable binding."""

    def __init__(self, worksheet: Worksheet, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle(title)
        self.resize(540, 420)
        self.last_active_edit: Optional[QLineEdit] = None

    def _create_column_picker(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("Columns:")
        layout.addWidget(lbl)

        self.col_list = QListWidget()
        for idx, col in enumerate(self.worksheet.columns):
            name = col.name if col.name else f"C{idx + 1}"
            kind_tag = " (T)" if col.kind == "text" else ""
            item = QListWidgetItem(f"C{idx + 1}  {name}{kind_tag}")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.col_list.addItem(item)
        self.col_list.itemDoubleClicked.connect(self._on_col_double_clicked)
        layout.addWidget(self.col_list)

        btn_select = QPushButton("Select")
        btn_select.clicked.connect(self._on_select_clicked)
        layout.addWidget(btn_select)
        return container

    def _on_col_double_clicked(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.ItemDataRole.UserRole)
        col = self.worksheet.columns[idx]
        name = col.name if col.name else f"C{idx + 1}"
        if self.last_active_edit is not None:
            self.last_active_edit.setText(name)
        elif hasattr(self, "edit_series"):
            self.edit_series.setText(name)

    def _on_select_clicked(self) -> None:
        cur = self.col_list.currentItem()
        if cur is not None:
            self._on_col_double_clicked(cur)


class TrendAnalysisDialog(_TimeSeriesBaseDialog):
    """Trend Analysis Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Trend Analysis", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        # Left picker
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        # Right settings
        right_layout = QVBoxLayout()

        # Variable input
        form_series = QFormLayout()
        self.edit_series = QLineEdit()
        self.last_active_edit = self.edit_series
        form_series.addRow("&Series:", self.edit_series)
        right_layout.addLayout(form_series)

        # Model type group
        grp_model = QGroupBox("Model Type")
        lay_model = QVBoxLayout(grp_model)
        self.rb_linear = QRadioButton("&Linear")
        self.rb_quadratic = QRadioButton("&Quadratic")
        self.rb_exponential = QRadioButton("&Exponential growth")
        self.rb_scurve = QRadioButton("&S-curve (Pearl-Reed logistic)")
        self.rb_linear.setChecked(True)

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.rb_linear, 0)
        self.btn_group.addButton(self.rb_quadratic, 1)
        self.btn_group.addButton(self.rb_exponential, 2)
        self.btn_group.addButton(self.rb_scurve, 3)

        lay_model.addWidget(self.rb_linear)
        lay_model.addWidget(self.rb_quadratic)
        lay_model.addWidget(self.rb_exponential)
        lay_model.addWidget(self.rb_scurve)
        right_layout.addWidget(grp_model)

        # Forecasts group
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

        # Storage group
        grp_store = QGroupBox("Storage in Worksheet")
        lay_store = QVBoxLayout(grp_store)
        self.chk_store_fits = QCheckBox("Fits (fitted values)")
        self.chk_store_residuals = QCheckBox("Residuals")
        self.chk_store_forecasts = QCheckBox("Forecasts")
        lay_store.addWidget(self.chk_store_fits)
        lay_store.addWidget(self.chk_store_residuals)
        lay_store.addWidget(self.chk_store_forecasts)
        right_layout.addWidget(grp_store)

        # Title input
        form_title = QFormLayout()
        self.edit_title = QLineEdit()
        form_title.addRow("&Title:", self.edit_title)
        right_layout.addLayout(form_title)

        # Dialog Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        right_layout.addWidget(button_box)

        main_layout.addLayout(right_layout, stretch=2)

    def _on_accept(self) -> None:
        txt = self.edit_series.text().strip()
        if not txt:
            QMessageBox.warning(self, "Trend Analysis", "Please select a series column.")
            return
        resolved = resolve_variables(txt, self.worksheet, kinds=("number",))
        if not resolved:
            QMessageBox.warning(self, "Trend Analysis", f"Variable '{txt}' not found in worksheet.")
            return

        model_map = {0: "linear", 1: "quadratic", 2: "exponential", 3: "scurve"}
        model_name = model_map.get(self.btn_group.checkedId(), "linear")

        self.settings = {
            "series_index": resolved[0],
            "series_name": txt,
            "model": model_name,
            "forecasts": self.spin_fc.value() if self.chk_fc.isChecked() else 0,
            "title": self.edit_title.text().strip(),
            "store_fits": self.chk_store_fits.isChecked(),
            "store_residuals": self.chk_store_residuals.isChecked(),
            "store_forecasts": self.chk_store_forecasts.isChecked(),
        }
        self.accept()


class DecompositionDialog(_TimeSeriesBaseDialog):
    """Classical Decomposition Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Decomposition", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()

        form = QFormLayout()
        self.edit_series = QLineEdit()
        self.last_active_edit = self.edit_series
        form.addRow("&Series:", self.edit_series)

        self.spin_season = QSpinBox()
        self.spin_season.setRange(2, 365)
        self.spin_season.setValue(4)
        form.addRow("Seasonal &length:", self.spin_season)
        right_layout.addLayout(form)

        # Model type
        grp_type = QGroupBox("Model Type")
        lay_type = QVBoxLayout(grp_type)
        self.rb_multiplicative = QRadioButton("&Multiplicative")
        self.rb_additive = QRadioButton("&Additive")
        self.rb_multiplicative.setChecked(True)
        lay_type.addWidget(self.rb_multiplicative)
        lay_type.addWidget(self.rb_additive)
        right_layout.addWidget(grp_type)

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
        self.chk_store_fits = QCheckBox("Fits")
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
            QMessageBox.warning(self, "Decomposition", "Please select a series column.")
            return
        resolved = resolve_variables(txt, self.worksheet, kinds=("number",))
        if not resolved:
            QMessageBox.warning(self, "Decomposition", f"Variable '{txt}' not found in worksheet.")
            return

        self.settings = {
            "series_index": resolved[0],
            "series_name": txt,
            "season_length": self.spin_season.value(),
            "model": "multiplicative" if self.rb_multiplicative.isChecked() else "additive",
            "forecasts": self.spin_fc.value() if self.chk_fc.isChecked() else 0,
            "store_fits": self.chk_store_fits.isChecked(),
            "store_residuals": self.chk_store_residuals.isChecked(),
            "store_forecasts": self.chk_store_forecasts.isChecked(),
        }
        self.accept()


class MovingAverageDialog(_TimeSeriesBaseDialog):
    """Moving Average Smoothing and Forecast Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Moving Average", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()

        form = QFormLayout()
        self.edit_series = QLineEdit()
        self.last_active_edit = self.edit_series
        form.addRow("&Series:", self.edit_series)

        self.spin_length = QSpinBox()
        self.spin_length.setRange(1, 100)
        self.spin_length.setValue(3)
        form.addRow("MA &length:", self.spin_length)

        self.chk_center = QCheckBox("&Center the moving averages")
        form.addRow("", self.chk_center)
        right_layout.addLayout(form)

        # Forecasts
        grp_fc = QGroupBox("Forecasts")
        lay_fc = QHBoxLayout(grp_fc)
        self.chk_fc = QCheckBox("Generate &forecasts:")
        self.spin_fc = QSpinBox()
        self.spin_fc.setRange(1, 1000)
        self.spin_fc.setValue(3)
        self.spin_fc.setEnabled(False)
        self.chk_fc.toggled.connect(self.spin_fc.setEnabled)
        lay_fc.addWidget(self.chk_fc)
        lay_fc.addWidget(self.spin_fc)
        right_layout.addWidget(grp_fc)

        # Storage
        grp_store = QGroupBox("Storage in Worksheet")
        lay_store = QVBoxLayout(grp_store)
        self.chk_store_fits = QCheckBox("Fits (moving average)")
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
            QMessageBox.warning(self, "Moving Average", "Please select a series column.")
            return
        resolved = resolve_variables(txt, self.worksheet, kinds=("number",))
        if not resolved:
            QMessageBox.warning(self, "Moving Average", f"Variable '{txt}' not found in worksheet.")
            return

        self.settings = {
            "series_index": resolved[0],
            "series_name": txt,
            "ma_length": self.spin_length.value(),
            "center": self.chk_center.isChecked(),
            "forecasts": self.spin_fc.value() if self.chk_fc.isChecked() else 0,
            "store_fits": self.chk_store_fits.isChecked(),
            "store_residuals": self.chk_store_residuals.isChecked(),
            "store_forecasts": self.chk_store_forecasts.isChecked(),
        }
        self.accept()


class SingleExpSmoothingDialog(_TimeSeriesBaseDialog):
    """Single Exponential Smoothing Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Single Exponential Smoothing", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()

        form = QFormLayout()
        self.edit_series = QLineEdit()
        self.last_active_edit = self.edit_series
        form.addRow("&Series:", self.edit_series)
        right_layout.addLayout(form)

        # Weight to use
        grp_wt = QGroupBox("Weight to Use")
        lay_wt = QVBoxLayout(grp_wt)
        self.rb_optimal = QRadioButton("&Optimal ARIMA weight (minimize MSD)")
        self.rb_optimal.setChecked(True)
        self.rb_custom = QRadioButton("Use &weight:")
        self.edit_alpha = QLineEdit("0.2")
        self.edit_alpha.setEnabled(False)
        self.rb_custom.toggled.connect(self.edit_alpha.setEnabled)

        h_custom = QHBoxLayout()
        h_custom.addWidget(self.rb_custom)
        h_custom.addWidget(self.edit_alpha)

        lay_wt.addWidget(self.rb_optimal)
        lay_wt.addLayout(h_custom)
        right_layout.addWidget(grp_wt)

        # Forecasts
        grp_fc = QGroupBox("Forecasts")
        lay_fc = QHBoxLayout(grp_fc)
        self.chk_fc = QCheckBox("Generate &forecasts:")
        self.spin_fc = QSpinBox()
        self.spin_fc.setRange(1, 1000)
        self.spin_fc.setValue(3)
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
            QMessageBox.warning(self, "Single Exp Smoothing", "Please select a series column.")
            return
        resolved = resolve_variables(txt, self.worksheet, kinds=("number",))
        if not resolved:
            QMessageBox.warning(self, "Single Exp Smoothing", f"Variable '{txt}' not found in worksheet.")
            return

        alpha_val: Optional[float] = None
        if self.rb_custom.isChecked():
            try:
                alpha_val = float(self.edit_alpha.text().strip())
                if not (0.0 < alpha_val <= 1.0):
                    raise ValueError()
            except ValueError:
                QMessageBox.warning(self, "Single Exp Smoothing", "Weight alpha must be between 0 and 1.")
                return

        self.settings = {
            "series_index": resolved[0],
            "series_name": txt,
            "alpha": alpha_val,
            "forecasts": self.spin_fc.value() if self.chk_fc.isChecked() else 0,
            "store_fits": self.chk_store_fits.isChecked(),
            "store_residuals": self.chk_store_residuals.isChecked(),
            "store_forecasts": self.chk_store_forecasts.isChecked(),
        }
        self.accept()


class DoubleExpSmoothingDialog(_TimeSeriesBaseDialog):
    """Double Exponential Smoothing Dialog (Holt's Method)."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Double Exponential Smoothing", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()

        form = QFormLayout()
        self.edit_series = QLineEdit()
        self.last_active_edit = self.edit_series
        form.addRow("&Series:", self.edit_series)
        right_layout.addLayout(form)

        # Weights group
        grp_wt = QGroupBox("Weights to Use")
        lay_wt = QVBoxLayout(grp_wt)
        self.rb_optimal = QRadioButton("&Optimal weights (minimize MSD)")
        self.rb_optimal.setChecked(True)
        self.rb_custom = QRadioButton("Use &weights:")

        lay_params = QFormLayout()
        self.edit_alpha = QLineEdit("0.2")
        self.edit_gamma = QLineEdit("0.2")
        self.edit_alpha.setEnabled(False)
        self.edit_gamma.setEnabled(False)
        self.rb_custom.toggled.connect(self.edit_alpha.setEnabled)
        self.rb_custom.toggled.connect(self.edit_gamma.setEnabled)

        lay_params.addRow("Level (alpha):", self.edit_alpha)
        lay_params.addRow("Trend (gamma):", self.edit_gamma)

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
        self.spin_fc.setValue(3)
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
            QMessageBox.warning(self, "Double Exp Smoothing", "Please select a series column.")
            return
        resolved = resolve_variables(txt, self.worksheet, kinds=("number",))
        if not resolved:
            QMessageBox.warning(self, "Double Exp Smoothing", f"Variable '{txt}' not found in worksheet.")
            return

        alpha_val: Optional[float] = None
        gamma_val: Optional[float] = None
        if self.rb_custom.isChecked():
            try:
                alpha_val = float(self.edit_alpha.text().strip())
                gamma_val = float(self.edit_gamma.text().strip())
                if not (0.0 < alpha_val <= 1.0 and 0.0 < gamma_val <= 1.0):
                    raise ValueError()
            except ValueError:
                QMessageBox.warning(self, "Double Exp Smoothing", "Weights alpha and gamma must both be between 0 and 1.")
                return

        self.settings = {
            "series_index": resolved[0],
            "series_name": txt,
            "alpha": alpha_val,
            "gamma": gamma_val,
            "forecasts": self.spin_fc.value() if self.chk_fc.isChecked() else 0,
            "store_fits": self.chk_store_fits.isChecked(),
            "store_residuals": self.chk_store_residuals.isChecked(),
            "store_forecasts": self.chk_store_forecasts.isChecked(),
        }
        self.accept()


class AutocorrelationDialog(_TimeSeriesBaseDialog):
    """Autocorrelation Function (ACF) Dialog."""

    def __init__(self, worksheet: Worksheet, is_partial: bool = False, parent: Optional[QWidget] = None):
        title = "Partial Autocorrelation" if is_partial else "Autocorrelation"
        super().__init__(worksheet, title, parent)
        self.is_partial = is_partial
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()

        form = QFormLayout()
        self.edit_series = QLineEdit()
        self.last_active_edit = self.edit_series
        form.addRow("&Series:", self.edit_series)

        self.chk_custom_lags = QCheckBox("&Number of lags:")
        self.spin_lags = QSpinBox()
        self.spin_lags.setRange(1, 100)
        self.spin_lags.setValue(20)
        self.spin_lags.setEnabled(False)
        self.chk_custom_lags.toggled.connect(self.spin_lags.setEnabled)
        form.addRow(self.chk_custom_lags, self.spin_lags)

        self.edit_title = QLineEdit()
        form.addRow("&Title:", self.edit_title)
        right_layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        right_layout.addWidget(button_box)

        main_layout.addLayout(right_layout, stretch=2)

    def _on_accept(self) -> None:
        txt = self.edit_series.text().strip()
        if not txt:
            QMessageBox.warning(self, self.windowTitle(), "Please select a series column.")
            return
        resolved = resolve_variables(txt, self.worksheet, kinds=("number",))
        if not resolved:
            QMessageBox.warning(self, self.windowTitle(), f"Variable '{txt}' not found in worksheet.")
            return

        self.settings = {
            "series_index": resolved[0],
            "series_name": txt,
            "max_lags": self.spin_lags.value() if self.chk_custom_lags.isChecked() else None,
            "title": self.edit_title.text().strip(),
        }
        self.accept()


class DifferencesDialog(_TimeSeriesBaseDialog):
    """Differences Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Differences", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.edit_series = QLineEdit()
        self.last_active_edit = self.edit_series
        form.addRow("&Series:", self.edit_series)

        self.spin_lag = QSpinBox()
        self.spin_lag.setRange(1, 100)
        self.spin_lag.setValue(1)
        form.addRow("&Lag:", self.spin_lag)

        self.edit_store = QLineEdit()
        form.addRow("Store &differences in:", self.edit_store)
        right_layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        right_layout.addWidget(button_box)

        main_layout.addLayout(right_layout, stretch=2)

    def _on_accept(self) -> None:
        txt = self.edit_series.text().strip()
        if not txt:
            QMessageBox.warning(self, "Differences", "Please select a series column.")
            return
        resolved = resolve_variables(txt, self.worksheet, kinds=("number",))
        if not resolved:
            QMessageBox.warning(self, "Differences", f"Variable '{txt}' not found in worksheet.")
            return

        self.settings = {
            "series_index": resolved[0],
            "series_name": txt,
            "lag": self.spin_lag.value(),
            "store_col": self.edit_store.text().strip() or f"DIFF_{txt}",
        }
        self.accept()


class LagDialog(_TimeSeriesBaseDialog):
    """Lag Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Lag", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.edit_series = QLineEdit()
        self.last_active_edit = self.edit_series
        form.addRow("&Series:", self.edit_series)

        self.spin_lag = QSpinBox()
        self.spin_lag.setRange(1, 100)
        self.spin_lag.setValue(1)
        form.addRow("&Lag:", self.spin_lag)

        self.edit_store = QLineEdit()
        form.addRow("Store &lag in:", self.edit_store)
        right_layout.addLayout(form)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        right_layout.addWidget(button_box)

        main_layout.addLayout(right_layout, stretch=2)

    def _on_accept(self) -> None:
        txt = self.edit_series.text().strip()
        if not txt:
            QMessageBox.warning(self, "Lag", "Please select a series column.")
            return
        resolved = resolve_variables(txt, self.worksheet, kinds=("number",))
        if not resolved:
            QMessageBox.warning(self, "Lag", f"Variable '{txt}' not found in worksheet.")
            return

        self.settings = {
            "series_index": resolved[0],
            "series_name": txt,
            "lag": self.spin_lag.value(),
            "store_col": self.edit_store.text().strip() or f"LAG_{txt}",
        }
        self.accept()
