"""Qt Dialogs for Rare Event Control Charts (G Chart & T Chart) with native StatCraft PE fidelity.

Form Evidence:
- 0750-GCHARTDATASOURCE.MDF (G Chart: MenuID 41256, HelpID 88700)
- 0751-GCHARTPARAMETERS.MDF (G Chart Parameters: Proportion p)
- 0752-GCHARTTESTS.MDF (G Chart Tests: Test 1, Benneyan test)
- 1136-TCHARTDATASOURCE.MDF (T Chart: MenuID 41257, HelpID 88701)
- 1137-TCHARTPARAMETERS.MDF (T Chart Parameters: Weibull/Exponential shape and scale)
- 1138-TCHARTTESTS.MDF (T Chart Tests: Test 1, Benneyan test)
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .attribute_control_engine import parse_subgroup_omission
from .dialog_theme import is_dark_active, subtle_label_style
from .model import Worksheet
from .variable_dialogs import format_variable_reference, resolve_variables


class RareEventOptionsDialog(QDialog):
    """Subdialog for Rare Event Chart Options (Parameters, Tests, Estimate)."""

    def __init__(self, chart_type: str, options: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.chart_type = chart_type.upper()
        self.setWindowTitle(f"{self.chart_type} Chart Options")
        self.resize(480, 380)
        self.options = copy.deepcopy(options)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        if self.chart_type == "G":
            self._setup_g_tabs()
        else:
            self._setup_t_tabs()

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._save_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _setup_g_tabs(self) -> None:
        # Tab 1: Parameters (0751-GCHARTPARAMETERS)
        tab_param = QWidget()
        layout_param = QVBoxLayout(tab_param)
        form_param = QFormLayout()

        lbl_desc = QLabel("To specify a value for the proportion, enter it here. StatCraft uses this value instead of estimating it from the data.")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(subtle_label_style(is_dark_active(self.parent() or self), font_size="9pt", extra="margin-bottom: 8px;"))
        layout_param.addWidget(lbl_desc)

        self.edit_p = QLineEdit()
        if self.options.get("p") is not None:
            self.edit_p.setText(str(self.options["p"]))
        form_param.addRow("&Proportion:", self.edit_p)

        layout_param.addLayout(form_param)
        layout_param.addStretch()
        self.tabs.addTab(tab_param, "Parameters")

        # Tab 2: Tests (0752-GCHARTTESTS)
        tab_tests = QWidget()
        layout_tests = QVBoxLayout(tab_tests)
        self.chk_test1 = QCheckBox("1 point > 3 standard deviations from center line (Test 1)")
        self.chk_test1.setChecked(bool(self.options.get("test1", True)))
        self.chk_benneyan = QCheckBox("Benneyan test: Consecutive observations of zeros/minimum count")
        self.chk_benneyan.setChecked(bool(self.options.get("test_benneyan", True)))

        layout_tests.addWidget(self.chk_test1)
        layout_tests.addWidget(self.chk_benneyan)

        form_b = QFormLayout()
        self.edit_b_thresh = QLineEdit(str(self.options.get("benneyan_threshold", 3)))
        form_b.addRow("  Benneyan run length threshold:", self.edit_b_thresh)
        layout_tests.addLayout(form_b)

        layout_tests.addStretch()
        self.tabs.addTab(tab_tests, "Tests")

        # Tab 3: Estimate
        tab_est = QWidget()
        layout_est = QVBoxLayout(tab_est)
        form_est = QFormLayout()
        self.edit_omit = QLineEdit()
        omits = self.options.get("omit_subgroups", [])
        if omits:
            self.edit_omit.setText(" ".join(str(x) for x in omits))
        form_est.addRow("Omit following observations:", self.edit_omit)
        layout_est.addLayout(form_est)
        layout_est.addStretch()
        self.tabs.addTab(tab_est, "Estimate")

    def _setup_t_tabs(self) -> None:
        # Tab 1: Parameters (1137-TCHARTPARAMETERS)
        tab_param = QWidget()
        layout_param = QVBoxLayout(tab_param)
        form_param = QFormLayout()

        self.combo_dist = QComboBox()
        self.combo_dist.addItem("Weibull", "Weibull")
        self.combo_dist.addItem("Exponential", "Exponential")
        cur_d = str(self.options.get("distribution", "Weibull"))
        idx_d = self.combo_dist.findData(cur_d)
        if idx_d >= 0:
            self.combo_dist.setCurrentIndex(idx_d)
        self.combo_dist.currentIndexChanged.connect(self._on_dist_changed)
        form_param.addRow("Distribution:", self.combo_dist)

        self.edit_shape = QLineEdit()
        if self.options.get("shape") is not None:
            self.edit_shape.setText(str(self.options["shape"]))
        form_param.addRow("Shape (&Beta):", self.edit_shape)

        self.edit_scale = QLineEdit()
        if self.options.get("scale") is not None:
            self.edit_scale.setText(str(self.options["scale"]))
        form_param.addRow("Scale (&Eta):", self.edit_scale)

        layout_param.addLayout(form_param)
        layout_param.addStretch()
        self.tabs.addTab(tab_param, "Parameters")

        # Tab 2: Tests (1138-TCHARTTESTS)
        tab_tests = QWidget()
        layout_tests = QVBoxLayout(tab_tests)
        self.chk_test1 = QCheckBox("1 point > 3 standard deviations from center line (Test 1)")
        self.chk_test1.setChecked(bool(self.options.get("test1", True)))
        self.chk_benneyan = QCheckBox("Benneyan test: Consecutive observations of short intervals")
        self.chk_benneyan.setChecked(bool(self.options.get("test_benneyan", True)))

        layout_tests.addWidget(self.chk_test1)
        layout_tests.addWidget(self.chk_benneyan)

        form_b = QFormLayout()
        self.edit_b_thresh = QLineEdit(str(self.options.get("benneyan_threshold", 3)))
        form_b.addRow("  Benneyan run length threshold:", self.edit_b_thresh)
        layout_tests.addLayout(form_b)

        layout_tests.addStretch()
        self.tabs.addTab(tab_tests, "Tests")

        # Tab 3: Estimate
        tab_est = QWidget()
        layout_est = QVBoxLayout(tab_est)
        form_est = QFormLayout()
        self.edit_omit = QLineEdit()
        omits = self.options.get("omit_subgroups", [])
        if omits:
            self.edit_omit.setText(" ".join(str(x) for x in omits))
        form_est.addRow("Omit following observations:", self.edit_omit)
        layout_est.addLayout(form_est)
        layout_est.addStretch()
        self.tabs.addTab(tab_est, "Estimate")

    def _on_dist_changed(self, idx: int) -> None:
        is_expo = self.combo_dist.currentData() == "Exponential"
        self.edit_shape.setEnabled(not is_expo)
        if is_expo:
            self.edit_shape.setText("1.0")

    def _save_and_accept(self) -> None:
        if self.chart_type == "G":
            txt_p = self.edit_p.text().strip()
            self.options["p"] = float(txt_p) if txt_p else None
        else:
            self.options["distribution"] = self.combo_dist.currentData()
            txt_sh = self.edit_shape.text().strip()
            self.options["shape"] = float(txt_sh) if txt_sh else None
            txt_sc = self.edit_scale.text().strip()
            self.options["scale"] = float(txt_sc) if txt_sc else None

        self.options["test1"] = self.chk_test1.isChecked()
        self.options["test_benneyan"] = self.chk_benneyan.isChecked()
        try:
            self.options["benneyan_threshold"] = int(self.edit_b_thresh.text().strip())
        except ValueError:
            self.options["benneyan_threshold"] = 3

        self.options["omit_subgroups"] = sorted(parse_subgroup_omission(self.edit_omit.text()))
        self.accept()


class RareEventChartDialog(QDialog):
    """Main parameter dialog for G Chart and T Chart matching StatCraft."""

    def __init__(self, worksheet: Worksheet, chart_type: str = "G", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.chart_type = chart_type.upper()
        self.setWindowTitle(f"{self.chart_type} Chart")
        self.resize(540, 380)
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

        # Right panel: Controls matching MDF
        right_layout = QVBoxLayout()

        # Form of data
        right_layout.addWidget(QLabel("&Form of data:"))
        self.combo_form = QComboBox(self)
        if self.chart_type == "G":
            self.combo_form.addItem("Dates of events", 0)
            self.combo_form.addItem("Number of opportunities", 1)
            self.combo_form.setCurrentIndex(1)  # Default: opportunities
        else:
            self.combo_form.addItem("Dates/Times of events or Time between events", 0)
            self.combo_form.addItem("Number of intervals between events", 1)
            self.combo_form.setCurrentIndex(1)  # Default: numeric intervals

        self.combo_form.currentIndexChanged.connect(self._on_form_changed)
        right_layout.addWidget(self.combo_form)

        # Second combo: Method of counting / Units
        if self.chart_type == "G":
            self.lbl_method = QLabel("Method of &counting opportunities:")
            self.combo_method = QComboBox(self)
            self.combo_method.addItem("Opportunities between events (0, 1, 2, ...)", 0)
            self.combo_method.addItem("Opportunities until an event (1, 2, 3, ...)", 1)
        else:
            self.lbl_method = QLabel("&Units for intervals:")
            self.combo_method = QComboBox(self)
            self.combo_method.addItem("Days", "Days")
            self.combo_method.addItem("Hours", "Hours")

        right_layout.addWidget(self.lbl_method)
        right_layout.addWidget(self.combo_method)

        # Variables edit box
        right_layout.addWidget(QLabel("&Variables:"))
        self.edit_var = QLineEdit(self)
        right_layout.addWidget(self.edit_var)

        # Options button
        self.btn_options = QPushButton(f"{self.chart_type} Chart O&ptions...")
        self.btn_options.clicked.connect(self._open_options)
        right_layout.addWidget(self.btn_options)

        right_layout.addStretch()

        # OK / Cancel
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

    def _on_form_changed(self, idx: int) -> None:
        # Toggle method / units availability depending on form of data
        if self.chart_type == "G":
            is_opp = idx == 1
            self.lbl_method.setVisible(is_opp)
            self.combo_method.setVisible(is_opp)
        else:
            is_int = idx == 1
            self.lbl_method.setVisible(is_int)
            self.combo_method.setVisible(is_int)

    def _open_options(self) -> None:
        dlg = RareEventOptionsDialog(self.chart_type, self.options, self)
        if dlg.exec():
            self.options = dlg.options

    def _on_ok(self) -> None:
        var_text = self.edit_var.text().strip()
        if not var_text:
            QMessageBox.warning(self, "Input Error", "Please specify a variable or column.")
            return

        cols = resolve_variables(var_text, self.worksheet)
        if not cols:
            QMessageBox.warning(self, "Input Error", f"Variable '{var_text}' not found in worksheet.")
            return

        self.accept()

    def get_configuration(self) -> Dict[str, Any]:
        """Return the collected dialog configuration."""
        var_text = self.edit_var.text().strip()
        cols = resolve_variables(var_text, self.worksheet)
        col_names = [self.worksheet.columns[i].name for i in cols]
        form_val = self.combo_form.currentData()
        method_val = self.combo_method.currentData()

        return {
            "chart_type": self.chart_type,
            "columns": col_names,
            "variable_indices": cols,
            "form_of_data": form_val,
            "method_of_count": method_val if self.chart_type == "G" else None,
            "units": method_val if self.chart_type == "T" else None,
            "options": copy.deepcopy(self.options),
        }
