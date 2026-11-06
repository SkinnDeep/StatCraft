"""Qt Dialogs for Time-Weighted Control Charts (EWMA, Moving Average, CUSUM) with native StatCraft PE fidelity.

Form Evidence:
- 0716-EWMADATASOURCE.MDF (EWMA Chart: MenuID 41039, HelpID 86100)
- 0836-MACHARTDATASOURCE.MDF (Moving Average Chart: MenuID 41040, HelpID 86000)
- 1026-RCUSUMDATASOURCE.MDF (CUSUM Chart: MenuID 41041, HelpID 86200)
- 1027-RCUSUMPLANANDTYPE.MDF (Options: Plan & Type for CUSUM)
- 1008-QCHARTPARAMETERS.MDF (Options: Parameters, Estimate, Limits)
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Union
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .attribute_control_engine import parse_subgroup_omission
from .model import Worksheet
from .variable_dialogs import format_variable_reference, resolve_variables


class TimeWeightedOptionsDialog(QDialog):
    """Options dialog for EWMA, Moving Average, and CUSUM charts."""

    def __init__(self, chart_type: str, options: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.chart_type = chart_type.upper()
        if self.chart_type == "EWMA":
            self.setWindowTitle("EWMA Chart Options")
        elif self.chart_type in ("MA", "MOVING_AVERAGE"):
            self.setWindowTitle("Moving Average Chart Options")
        elif self.chart_type == "CUSUM":
            self.setWindowTitle("CUSUM Chart Options")
        else:
            self.setWindowTitle(f"{self.chart_type} Chart Options")

        self.setMinimumSize(560, 420)
        self.resize(560, 420)
        self.setSizeGripEnabled(True)
        self.options = copy.deepcopy(options)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        if self.chart_type == "CUSUM":
            self._setup_cusum_tabs()
        else:
            self._setup_ewma_ma_tabs()

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._save_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _setup_ewma_ma_tabs(self) -> None:
        # Tab 1: Parameters (1008-QCHARTPARAMETERS)
        tab_param = QWidget()
        layout_param = QVBoxLayout(tab_param)
        form_param = QFormLayout()

        desc_param = QLabel("Historical parameters (optional):")
        desc_param.setStyleSheet("font-weight: bold; margin-bottom: 6px;")
        layout_param.addWidget(desc_param)

        self.edit_mean = QLineEdit()
        if self.options.get("historical_mean") is not None:
            self.edit_mean.setText(str(self.options["historical_mean"]))
        form_param.addRow("Mean:", self.edit_mean)

        self.edit_sigma = QLineEdit()
        if self.options.get("historical_sigma") is not None:
            self.edit_sigma.setText(str(self.options["historical_sigma"]))
        form_param.addRow("Standard deviation:", self.edit_sigma)

        layout_param.addLayout(form_param)
        layout_param.addStretch()
        self.tabs.addTab(tab_param, "Parameters")

        # Tab 2: Estimate
        tab_est = QWidget()
        layout_est = QVBoxLayout(tab_est)
        form_est = QFormLayout()

        self.combo_method = QComboBox()
        self.combo_method.addItem("Pooled standard deviation", "pooled_stdev")
        self.combo_method.addItem("Rbar", "rbar")
        self.combo_method.addItem("Sbar", "sbar")
        cur_m = str(self.options.get("estimation_method", "pooled_stdev")).lower()
        idx_m = self.combo_method.findData(cur_m)
        if idx_m >= 0:
            self.combo_method.setCurrentIndex(idx_m)
        form_est.addRow("Method for estimating standard deviation:", self.combo_method)

        self.edit_omit = QLineEdit()
        omits = self.options.get("omit_subgroups", [])
        if omits:
            self.edit_omit.setText(" ".join(str(x) for x in omits))
        form_est.addRow("Omit following subgroups from calculations:", self.edit_omit)

        layout_est.addLayout(form_est)
        lbl_hint = QLabel("(Example: 3 12:15 to omit subgroups 3, 12, 13, 14, 15)")
        lbl_hint.setStyleSheet("color: #666; font-size: 8pt;")
        layout_est.addWidget(lbl_hint)
        layout_est.addStretch()
        self.tabs.addTab(tab_est, "Estimate")

        # Tab 3: Limits
        tab_lim = QWidget()
        layout_lim = QVBoxLayout(tab_lim)
        form_lim = QFormLayout()

        self.edit_k = QLineEdit()
        self.edit_k.setText(str(self.options.get("k_sigma", 3.0)))
        form_lim.addRow("Display control limits at (K sigma):", self.edit_k)

        layout_lim.addLayout(form_lim)
        layout_lim.addStretch()
        self.tabs.addTab(tab_lim, "Limits")

    def _setup_cusum_tabs(self) -> None:
        # Tab 1: Plan & Type (1027-RCUSUMPLANANDTYPE)
        tab_plan = QWidget()
        layout_plan = QVBoxLayout(tab_plan)

        grp_type = QGroupBox("Type of CUSUM")
        lay_type = QVBoxLayout(grp_type)
        self.rad_tabular = QRadioButton("&Tabular")
        self.rad_tabular.setChecked(True)
        self.rad_vmask = QRadioButton("&V-mask")
        lay_type.addWidget(self.rad_tabular)
        lay_type.addWidget(self.rad_vmask)
        layout_plan.addWidget(grp_type)

        grp_plan = QGroupBox("CUSUM Plan")
        form_plan = QFormLayout(grp_plan)
        self.edit_h = QLineEdit(str(self.options.get("h", 4.0)))
        form_plan.addRow("Decision interval (h):", self.edit_h)
        self.edit_k_param = QLineEdit(str(self.options.get("k", 0.5)))
        form_plan.addRow("Slack parameter (k):", self.edit_k_param)

        self.chk_fir = QCheckBox("Use Fast Initial Response (&FIR)")
        self.chk_fir.setChecked(bool(self.options.get("use_fir", False)))
        self.edit_fir = QLineEdit(str(self.options.get("fir", 2.0)))
        self.edit_fir.setEnabled(self.chk_fir.isChecked())
        self.chk_fir.toggled.connect(self.edit_fir.setEnabled)

        form_plan.addRow(self.chk_fir)
        form_plan.addRow("  Initial response value:", self.edit_fir)

        self.chk_reset = QCheckBox("&Reset after out of control")
        self.chk_reset.setChecked(bool(self.options.get("reset", False)))
        form_plan.addRow(self.chk_reset)

        layout_plan.addWidget(grp_plan)
        layout_plan.addStretch()
        self.tabs.addTab(tab_plan, "Plan & Type")

        # Tab 2: Estimate
        tab_est = QWidget()
        layout_est = QVBoxLayout(tab_est)
        form_est = QFormLayout()

        self.combo_method = QComboBox()
        self.combo_method.addItem("Pooled standard deviation", "pooled_stdev")
        self.combo_method.addItem("Rbar", "rbar")
        self.combo_method.addItem("Sbar", "sbar")
        cur_m = str(self.options.get("estimation_method", "pooled_stdev")).lower()
        idx_m = self.combo_method.findData(cur_m)
        if idx_m >= 0:
            self.combo_method.setCurrentIndex(idx_m)
        form_est.addRow("Method for estimating standard deviation:", self.combo_method)

        self.edit_sigma = QLineEdit()
        if self.options.get("historical_sigma") is not None:
            self.edit_sigma.setText(str(self.options["historical_sigma"]))
        form_est.addRow("Historical standard deviation:", self.edit_sigma)

        self.edit_omit = QLineEdit()
        omits = self.options.get("omit_subgroups", [])
        if omits:
            self.edit_omit.setText(" ".join(str(x) for x in omits))
        form_est.addRow("Omit following subgroups:", self.edit_omit)

        layout_est.addLayout(form_est)
        layout_est.addStretch()
        self.tabs.addTab(tab_est, "Estimate")

    def _save_and_accept(self) -> None:
        if self.chart_type == "CUSUM":
            self.options["cusum_type"] = "tabular" if self.rad_tabular.isChecked() else "vmask"
            try:
                self.options["h"] = float(self.edit_h.text().strip())
            except ValueError:
                self.options["h"] = 4.0
            try:
                self.options["k"] = float(self.edit_k_param.text().strip())
            except ValueError:
                self.options["k"] = 0.5
            self.options["use_fir"] = self.chk_fir.isChecked()
            try:
                self.options["fir"] = float(self.edit_fir.text().strip())
            except ValueError:
                self.options["fir"] = self.options["h"] / 2.0
            self.options["reset"] = self.chk_reset.isChecked()

            txt_sig = self.edit_sigma.text().strip()
            self.options["historical_sigma"] = float(txt_sig) if txt_sig else None
            self.options["estimation_method"] = self.combo_method.currentData()
            self.options["omit_subgroups"] = sorted(parse_subgroup_omission(self.edit_omit.text()))
        else:
            txt_m = self.edit_mean.text().strip()
            self.options["historical_mean"] = float(txt_m) if txt_m else None
            txt_s = self.edit_sigma.text().strip()
            self.options["historical_sigma"] = float(txt_s) if txt_s else None
            self.options["estimation_method"] = self.combo_method.currentData()
            self.options["omit_subgroups"] = sorted(parse_subgroup_omission(self.edit_omit.text()))
            try:
                self.options["k_sigma"] = float(self.edit_k.text().strip())
            except ValueError:
                self.options["k_sigma"] = 3.0

        self.accept()


class TimeWeightedChartDialog(QDialog):
    """Main parameter dialog for Time-Weighted Control Charts."""

    def __init__(self, worksheet: Worksheet, chart_type: str = "EWMA", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.chart_type = chart_type.upper()
        if self.chart_type == "EWMA":
            self.setWindowTitle("EWMA Chart")
        elif self.chart_type in ("MA", "MOVING_AVERAGE"):
            self.setWindowTitle("Moving Average Chart")
        elif self.chart_type == "CUSUM":
            self.setWindowTitle("CUSUM Chart")
        else:
            self.setWindowTitle(f"{self.chart_type} Chart")

        self.setMinimumSize(560, 420)
        self.resize(560, 420)
        self.setSizeGripEnabled(True)
        self.options: Dict[str, Any] = {}

        self._setup_ui()
        self._populate_variables()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        # Left panel: Variable listbox
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Variables:"))
        self.var_list = QListWidget(self)
        self.var_list.itemDoubleClicked.connect(self._select_variable)
        left_layout.addWidget(self.var_list)

        self.btn_select = QPushButton("Select")
        self.btn_select.clicked.connect(self._select_variable)
        left_layout.addWidget(self.btn_select)
        main_layout.addLayout(left_layout, 1)

        # Right panel: Form inputs matching MDF
        right_layout = QVBoxLayout()

        self.combo_arranged = QComboBox(self)
        self.combo_arranged.addItem("All observations for a chart are in one column:", 0)
        self.combo_arranged.addItem("Observations for a subgroup are in one row of columns:", 1)
        self.combo_arranged.currentIndexChanged.connect(self._on_arrangement_changed)
        right_layout.addWidget(self.combo_arranged)

        # Variable / Column input
        self.lbl_var = QLabel("Variable / Columns:")
        right_layout.addWidget(self.lbl_var)
        self.edit_var = QLineEdit(self)
        right_layout.addWidget(self.edit_var)

        # Subgroup size input
        self.lbl_subgroups = QLabel("Subgroup sizes (enter a number or ID column):")
        right_layout.addWidget(self.lbl_subgroups)
        self.edit_subgroup = QLineEdit(self)
        self.edit_subgroup.setText("1")
        right_layout.addWidget(self.edit_subgroup)

        # Chart-specific parameter input
        form_param = QFormLayout()
        if self.chart_type == "EWMA":
            self.edit_param = QLineEdit(self)
            self.edit_param.setText("0.2")
            form_param.addRow("Weight of EWMA:", self.edit_param)
        elif self.chart_type in ("MA", "MOVING_AVERAGE"):
            self.edit_param = QLineEdit(self)
            self.edit_param.setText("3")
            form_param.addRow("Length of MA (Span):", self.edit_param)
        elif self.chart_type == "CUSUM":
            self.edit_param = QLineEdit(self)
            self.edit_param.setText("0.0")
            form_param.addRow("Target:", self.edit_param)
        else:
            self.edit_param = QLineEdit(self)
            form_param.addRow("Parameter:", self.edit_param)

        right_layout.addLayout(form_param)

        # Options button
        btn_options_text = (
            "EWMA Options..." if self.chart_type == "EWMA"
            else "MA Options..." if self.chart_type in ("MA", "MOVING_AVERAGE")
            else "CUSUM Options..."
        )
        self.btn_options = QPushButton(btn_options_text)
        self.btn_options.clicked.connect(self._open_options)
        right_layout.addWidget(self.btn_options)

        right_layout.addStretch()

        # OK / Cancel buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._on_ok)
        btn_box.rejected.connect(self.reject)
        right_layout.addWidget(btn_box)

        main_layout.addLayout(right_layout, 2)

    def _populate_variables(self) -> None:
        self.var_list.clear()
        for col in self.worksheet.columns:
            name = getattr(col, 'name', str(col))
            item = QListWidgetItem(name)
            self.var_list.addItem(item)

    def _select_variable(self) -> None:
        idx = self.var_list.currentRow()
        if idx < 0 or idx >= len(self.worksheet.columns):
            return
        name = format_variable_reference(idx, self.worksheet)
        cur = self.edit_var.text().strip()
        if cur:
            self.edit_var.setText(f"{cur} {name}")
        else:
            self.edit_var.setText(name)

    def _on_arrangement_changed(self, idx: int) -> None:
        if idx == 1:
            # Row of columns
            self.lbl_var.setText("Subgroup columns:")
            self.lbl_subgroups.setVisible(False)
            self.edit_subgroup.setVisible(False)
        else:
            self.lbl_var.setText("Variable:")
            self.lbl_subgroups.setVisible(True)
            self.edit_subgroup.setVisible(True)

    def _open_options(self) -> None:
        dlg = TimeWeightedOptionsDialog(self.chart_type, self.options, self)
        if dlg.exec():
            self.options = dlg.options

    def _on_ok(self) -> None:
        var_text = self.edit_var.text().strip()
        if not var_text:
            QMessageBox.warning(self, "Input Error", "Please specify a variable or column.")
            return

        arranged_mode = self.combo_arranged.currentIndex()
        if arranged_mode == 1:
            cols = resolve_variables(var_text, self.worksheet)
            if not cols:
                QMessageBox.warning(self, "Input Error", "Please specify valid columns for subgroup rows.")
                return
        else:
            cols = resolve_variables(var_text, self.worksheet)
            if not cols:
                QMessageBox.warning(self, "Input Error", f"Variable '{var_text}' not found in worksheet.")
                return

        self.accept()

    def get_configuration(self) -> Dict[str, Any]:
        """Return the collected dialog configuration."""
        arranged_mode = self.combo_arranged.currentIndex()
        var_text = self.edit_var.text().strip()
        cols = resolve_variables(var_text, self.worksheet)
        col_names = [self.worksheet.columns[i].name for i in cols]

        subgroup_text = self.edit_subgroup.text().strip()
        subgroup_spec: Any = 1
        ws_col_map = {c.name: c for c in self.worksheet.columns}
        if arranged_mode == 0:
            if subgroup_text in ws_col_map:
                subgroup_spec = list(ws_col_map[subgroup_text].values)
            else:
                try:
                    subgroup_spec = max(1, int(float(subgroup_text)))
                except ValueError:
                    subgroup_spec = 1

        param_text = self.edit_param.text().strip()

        config: Dict[str, Any] = {
            "chart_type": self.chart_type,
            "arranged_mode": arranged_mode,
            "columns": col_names,
            "variable_indices": cols,
            "subgroup_spec": subgroup_spec,
            "subgroup_text": subgroup_text if arranged_mode == 0 else None,
            "options": copy.deepcopy(self.options),
        }

        if self.chart_type == "EWMA":
            try:
                config["weight"] = float(param_text)
            except ValueError:
                config["weight"] = 0.2
        elif self.chart_type in ("MA", "MOVING_AVERAGE"):
            try:
                config["span"] = int(float(param_text))
            except ValueError:
                config["span"] = 3
        elif self.chart_type == "CUSUM":
            try:
                config["target"] = float(param_text)
            except ValueError:
                config["target"] = 0.0

        return config
