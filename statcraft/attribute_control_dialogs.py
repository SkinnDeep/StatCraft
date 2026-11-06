"""Qt Dialogs for Attributes Control Charts (P, NP, C, U Charts) with native StatCraft PE fidelity.

Form Evidence:
- 0922-PCHARTDATASOURCE.MDF (P Chart: MenuID 41047, HelpID 85600)
- 0876-NPCHARTDATASOURCE.MDF (NP Chart: MenuID 41048, HelpID 85700)
- 0472-CCHARTDATASOURCE.MDF (C Chart: MenuID 41049, HelpID 85800)
- 1159-UCHARTDATASOURCE.MDF (U Chart: MenuID 41050, HelpID 85900)
- 1000-QCHARTATTRIBUTEPARAMETERS.MDF (Attribute Chart Options: Parameters, Estimate, Limits, Tests, Storage)
- 1014-QCHARTTESTS4.MDF (Tests 1, 2, 3, 4 for attributes)
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
from .model import Worksheet
from .variable_dialogs import format_variable_reference, resolve_variables


class AttributeOptionsDialog(QDialog):
    """Subdialog for Attribute Chart Options with 5 tabs matching StatCraft."""

    def __init__(self, chart_type: str, options: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        raw_type = chart_type.upper().strip().replace("′", "'")
        if raw_type in ("P'", "P_PRIME", "LANEY_P"):
            self.chart_type = "P'"
            win_title = "Laney P' Chart Options"
        elif raw_type in ("U'", "U_PRIME", "LANEY_U"):
            self.chart_type = "U'"
            win_title = "Laney U' Chart Options"
        else:
            self.chart_type = raw_type
            win_title = f"{self.chart_type} Chart Options"

        self.setWindowTitle(win_title)
        self.setMinimumSize(560, 420)
        self.resize(560, 420)
        self.setSizeGripEnabled(True)
        self.options = copy.deepcopy(options)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        # Tab 1: Parameters (1000-QCHARTATTRIBUTEPARAMETERS)
        tab_param = QWidget()
        layout_param = QVBoxLayout(tab_param)
        form_param = QFormLayout()

        if self.chart_type in ("P", "NP", "P'"):
            desc_param = QLabel(
                "To specify a value for the proportion, enter it here. "
                "StatCraft uses this value instead of estimating it from the data."
            )
            desc_param.setWordWrap(True)
            layout_param.addWidget(desc_param)

            self.prop_edit = QLineEdit()
            if self.options.get("historical_p") is not None:
                self.prop_edit.setText(str(self.options["historical_p"]))
            form_param.addRow("&Proportion:", self.prop_edit)
        else:  # 'C', 'U'
            desc_param = QLabel(
                "To specify a value for the mean, enter it here. "
                "StatCraft uses this value instead of estimating it from the data."
            )
            desc_param.setWordWrap(True)
            layout_param.addWidget(desc_param)

            self.mean_edit = QLineEdit()
            if self.options.get("historical_mean") is not None:
                self.mean_edit.setText(str(self.options["historical_mean"]))
            form_param.addRow("&Mean:", self.mean_edit)

        layout_param.addLayout(form_param)
        layout_param.addStretch()
        self.tabs.addTab(tab_param, "Parameters")

        # Tab 2: Estimate
        tab_est = QWidget()
        layout_est = QVBoxLayout(tab_est)
        desc_est = QLabel("Omit the following subgroups when estimating parameters:")
        desc_est.setWordWrap(True)
        layout_est.addWidget(desc_est)

        form_est = QFormLayout()
        self.omit_edit = QLineEdit()
        if self.options.get("omit_subgroups"):
            omit_val = self.options["omit_subgroups"]
            if isinstance(omit_val, (list, set, tuple)):
                self.omit_edit.setText(" ".join(str(x) for x in sorted(omit_val)))
            else:
                self.omit_edit.setText(str(omit_val))
        form_est.addRow("&Subgroups:", self.omit_edit)
        layout_est.addLayout(form_est)

        note_est = QLabel("(Enter subgroup numbers or a range of numbers, separated by spaces. Example: 3 12:15)")
        note_est.setWordWrap(True)
        note_est.setStyleSheet("color: #5b6b77; font-size: 8.5pt;")
        layout_est.addWidget(note_est)
        layout_est.addStretch()
        self.tabs.addTab(tab_est, "Estimate")

        # Tab 3: Limits
        tab_lim = QWidget()
        layout_lim = QVBoxLayout(tab_lim)
        form_lim = QFormLayout()

        self.k_sigma_edit = QLineEdit()
        self.k_sigma_edit.setText(str(self.options.get("k_sigma", 3.0)))
        form_lim.addRow("&Standard deviations (K):", self.k_sigma_edit)
        layout_lim.addLayout(form_lim)

        box_display = QGroupBox("Display Limits")
        box_disp_layout = QVBoxLayout(box_display)
        self.chk_upper = QCheckBox("Display &upper control limit")
        self.chk_upper.setChecked(self.options.get("display_upper", True))
        self.chk_lower = QCheckBox("Display &lower control limit")
        self.chk_lower.setChecked(self.options.get("display_lower", True))
        box_disp_layout.addWidget(self.chk_upper)
        box_disp_layout.addWidget(self.chk_lower)
        layout_lim.addWidget(box_display)
        layout_lim.addStretch()
        self.tabs.addTab(tab_lim, "Limits")

        # Tab 4: Tests (1014-QCHARTTESTS4)
        tab_tests = QWidget()
        layout_tests = QVBoxLayout(tab_tests)

        self.combo_tests_mode = QComboBox()
        self.combo_tests_mode.addItem("Perform all tests for special causes")
        self.combo_tests_mode.addItem("Perform selected tests for special causes")
        self.combo_tests_mode.addItem("Perform no tests")
        layout_tests.addWidget(self.combo_tests_mode)

        self.box_selected_tests = QGroupBox("Tests")
        layout_sel = QVBoxLayout(self.box_selected_tests)

        t_cfg = self.options.get("tests", {})

        # Test 1
        h1 = QHBoxLayout()
        self.chk_t1 = QCheckBox("1 point > K standard deviations from center line")
        t1_enabled = t_cfg.get("test1", {}).get("enabled", True)
        self.chk_t1.setChecked(t1_enabled)
        self.k_t1 = QLineEdit(str(t_cfg.get("test1", {}).get("k", 3.0)))
        self.k_t1.setFixedWidth(50)
        h1.addWidget(self.chk_t1)
        h1.addStretch()
        h1.addWidget(QLabel("K:"))
        h1.addWidget(self.k_t1)
        layout_sel.addLayout(h1)

        # Test 2
        h2 = QHBoxLayout()
        self.chk_t2 = QCheckBox("K points in a row on same side of center line")
        t2_enabled = t_cfg.get("test2", {}).get("enabled", False)
        self.chk_t2.setChecked(t2_enabled)
        self.k_t2 = QLineEdit(str(t_cfg.get("test2", {}).get("k", 9)))
        self.k_t2.setFixedWidth(50)
        h2.addWidget(self.chk_t2)
        h2.addStretch()
        h2.addWidget(QLabel("K:"))
        h2.addWidget(self.k_t2)
        layout_sel.addLayout(h2)

        # Test 3
        h3 = QHBoxLayout()
        self.chk_t3 = QCheckBox("K points in a row, all increasing or all decreasing")
        t3_enabled = t_cfg.get("test3", {}).get("enabled", False)
        self.chk_t3.setChecked(t3_enabled)
        self.k_t3 = QLineEdit(str(t_cfg.get("test3", {}).get("k", 6)))
        self.k_t3.setFixedWidth(50)
        h3.addWidget(self.chk_t3)
        h3.addStretch()
        h3.addWidget(QLabel("K:"))
        h3.addWidget(self.k_t3)
        layout_sel.addLayout(h3)

        # Test 4
        h4 = QHBoxLayout()
        self.chk_t4 = QCheckBox("K points in a row, alternating up and down")
        t4_enabled = t_cfg.get("test4", {}).get("enabled", False)
        self.chk_t4.setChecked(t4_enabled)
        self.k_t4 = QLineEdit(str(t_cfg.get("test4", {}).get("k", 14)))
        self.k_t4.setFixedWidth(50)
        h4.addWidget(self.chk_t4)
        h4.addStretch()
        h4.addWidget(QLabel("K:"))
        h4.addWidget(self.k_t4)
        layout_sel.addLayout(h4)

        layout_tests.addWidget(self.box_selected_tests)

        # Set combo mode based on existing tests configuration
        all_on = t1_enabled and t2_enabled and t3_enabled and t4_enabled
        all_off = not (t1_enabled or t2_enabled or t3_enabled or t4_enabled)
        if all_on:
            self.combo_tests_mode.setCurrentIndex(0)
        elif all_off:
            self.combo_tests_mode.setCurrentIndex(2)
        else:
            self.combo_tests_mode.setCurrentIndex(1)

        self.combo_tests_mode.currentIndexChanged.connect(self._on_test_mode_changed)
        self._on_test_mode_changed(self.combo_tests_mode.currentIndex())

        layout_tests.addStretch()
        self.tabs.addTab(tab_tests, "Tests")

        # Tab 5: Storage
        tab_storage = QWidget()
        layout_st = QVBoxLayout(tab_storage)
        st_cfg = self.options.get("storage", {})
        stat_name = "Sample proportions" if self.chart_type == "P" else ("Sample counts" if self.chart_type == "NP" else ("Sample rates" if self.chart_type == "U" else "Sample counts"))
        self.chk_st_rates = QCheckBox(f"Store {stat_name}")
        self.chk_st_rates.setChecked(st_cfg.get("rates", False))
        self.chk_st_sizes = QCheckBox("Store Subgroup sizes")
        self.chk_st_sizes.setChecked(st_cfg.get("subgroup_sizes", False))
        self.chk_st_cl = QCheckBox("Store Center lines")
        self.chk_st_cl.setChecked(st_cfg.get("center_lines", False))
        self.chk_st_limits = QCheckBox("Store Control limits")
        self.chk_st_limits.setChecked(st_cfg.get("control_limits", False))
        self.chk_st_tests = QCheckBox("Store Test results")
        self.chk_st_tests.setChecked(st_cfg.get("test_results", False))

        layout_st.addWidget(self.chk_st_rates)
        layout_st.addWidget(self.chk_st_sizes)
        layout_st.addWidget(self.chk_st_cl)
        layout_st.addWidget(self.chk_st_limits)
        layout_st.addWidget(self.chk_st_tests)
        layout_st.addStretch()
        self.tabs.addTab(tab_storage, "Storage")

        # Dialog buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_test_mode_changed(self, idx: int):
        if idx == 0:  # All tests
            self.box_selected_tests.setEnabled(True)
            self.chk_t1.setChecked(True)
            self.chk_t2.setChecked(True)
            self.chk_t3.setChecked(True)
            self.chk_t4.setChecked(True)
        elif idx == 1:  # Selected tests
            self.box_selected_tests.setEnabled(True)
        else:  # No tests
            self.box_selected_tests.setEnabled(False)
            self.chk_t1.setChecked(False)
            self.chk_t2.setChecked(False)
            self.chk_t3.setChecked(False)
            self.chk_t4.setChecked(False)

    def _accept(self):
        # Parameters
        if self.chart_type in ("P", "NP", "P'"):
            txt = self.prop_edit.text().strip()
            if txt:
                try:
                    val = float(txt)
                    if not 0.0 <= val <= 1.0:
                        QMessageBox.warning(self, "Invalid Proportion", "Historical proportion must be between 0.0 and 1.0.")
                        return
                    self.options["historical_p"] = val
                except ValueError:
                    QMessageBox.warning(self, "Invalid Proportion", "Proportion must be a valid number.")
                    return
            else:
                self.options["historical_p"] = None
        else:
            txt = self.mean_edit.text().strip()
            if txt:
                try:
                    val = float(txt)
                    if val < 0.0:
                        QMessageBox.warning(self, "Invalid Mean", "Historical mean defect count cannot be negative.")
                        return
                    self.options["historical_mean"] = val
                except ValueError:
                    QMessageBox.warning(self, "Invalid Mean", "Mean must be a valid number.")
                    return
            else:
                self.options["historical_mean"] = None

        # Estimate
        self.options["omit_subgroups"] = self.omit_edit.text().strip()

        # Limits
        k_txt = self.k_sigma_edit.text().strip()
        try:
            self.options["k_sigma"] = float(k_txt) if k_txt else 3.0
        except ValueError:
            QMessageBox.warning(self, "Invalid K-Sigma", "Standard deviations (K) must be a positive number.")
            return

        self.options["display_upper"] = self.chk_upper.isChecked()
        self.options["display_lower"] = self.chk_lower.isChecked()

        # Tests
        mode = self.combo_tests_mode.currentIndex()
        if mode == 0:
            tests_cfg = {
                "test1": {"enabled": True, "k": float(self.k_t1.text().strip() or 3.0)},
                "test2": {"enabled": True, "k": int(self.k_t2.text().strip() or 9)},
                "test3": {"enabled": True, "k": int(self.k_t3.text().strip() or 6)},
                "test4": {"enabled": True, "k": int(self.k_t4.text().strip() or 14)},
            }
        elif mode == 2:
            tests_cfg = {
                "test1": {"enabled": False, "k": 3.0},
                "test2": {"enabled": False, "k": 9},
                "test3": {"enabled": False, "k": 6},
                "test4": {"enabled": False, "k": 14},
            }
        else:
            tests_cfg = {
                "test1": {"enabled": self.chk_t1.isChecked(), "k": float(self.k_t1.text().strip() or 3.0)},
                "test2": {"enabled": self.chk_t2.isChecked(), "k": int(self.k_t2.text().strip() or 9)},
                "test3": {"enabled": self.chk_t3.isChecked(), "k": int(self.k_t3.text().strip() or 6)},
                "test4": {"enabled": self.chk_t4.isChecked(), "k": int(self.k_t4.text().strip() or 14)},
            }
        self.options["tests"] = tests_cfg

        # Storage
        self.options["storage"] = {
            "rates": self.chk_st_rates.isChecked(),
            "subgroup_sizes": self.chk_st_sizes.isChecked(),
            "center_lines": self.chk_st_cl.isChecked(),
            "control_limits": self.chk_st_limits.isChecked(),
            "test_results": self.chk_st_tests.isChecked(),
        }

        self.accept()


class AttributeChartDialog(QDialog):
    """Main Attribute Chart Dialog matching StatCraft MDF forms:
    - 0922-PCHARTDATASOURCE.MDF (P Chart)
    - 0876-NPCHARTDATASOURCE.MDF (NP Chart)
    - 0472-CCHARTDATASOURCE.MDF (C Chart)
    - 1159-UCHARTDATASOURCE.MDF (U Chart)
    """

    def __init__(self, worksheet: Worksheet, chart_type: str = "P", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        raw_type = chart_type.upper().strip().replace("′", "'")
        if raw_type in ("P'", "P_PRIME", "LANEY_P"):
            self.chart_type = "P'"
            self.setWindowTitle("Laney P' Chart")
            btn_text = "Laney P' Chart O&ptions..."
        elif raw_type in ("U'", "U_PRIME", "LANEY_U"):
            self.chart_type = "U'"
            self.setWindowTitle("Laney U' Chart")
            btn_text = "Laney U' Chart O&ptions..."
        elif raw_type in ("P", "NP", "C", "U"):
            self.chart_type = raw_type
            self.setWindowTitle(f"{self.chart_type} Chart")
            btn_text = f"{self.chart_type} Chart O&ptions..."
        else:
            self.chart_type = "P"
            self.setWindowTitle("P Chart")
            btn_text = "P Chart O&ptions..."

        self.setMinimumSize(560, 420)
        self.resize(560, 420)
        self.setSizeGripEnabled(True)
        self.selected_params: Optional[Dict[str, Any]] = None
        self.options: Dict[str, Any] = {}
        self._active_input: Optional[QLineEdit] = None

        main_layout = QHBoxLayout(self)

        # Left Column: Variables list
        left_layout = QVBoxLayout()
        self.var_list = QListWidget()
        for idx, col in enumerate(worksheet.columns):
            item = QListWidgetItem(format_variable_reference(idx, worksheet))
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.var_list.addItem(item)
        self.var_list.itemDoubleClicked.connect(self._on_list_double_clicked)
        left_layout.addWidget(self.var_list)

        self.btn_select = QPushButton("Select")
        self.btn_select.clicked.connect(self._on_select_clicked)
        left_layout.addWidget(self.btn_select)
        main_layout.addLayout(left_layout, 1)

        # Right Column: Controls
        right_layout = QVBoxLayout()

        # Variables: (MultiEditBoxCSub)
        lbl_vars = QLabel("&Variables:")
        self.edit_vars = QLineEdit()
        self.edit_vars.setFocus()
        self._active_input = self.edit_vars
        lbl_vars.setBuddy(self.edit_vars)
        right_layout.addWidget(lbl_vars)
        right_layout.addWidget(self.edit_vars)

        # Subgroup sizes (for P, NP, U, P', U' charts)
        self.edit_subgroup: Optional[QLineEdit] = None
        if self.chart_type in ("P", "NP", "U", "P'", "U'"):
            lbl_sub = QLabel("S&ubgroup sizes:")
            self.edit_subgroup = QLineEdit()
            lbl_sub.setBuddy(self.edit_subgroup)
            right_layout.addWidget(lbl_sub)
            right_layout.addWidget(self.edit_subgroup)

            note_sub = QLabel("(enter a number or column containing the sizes)")
            note_sub.setStyleSheet("color: #5b6b77; font-size: 8.5pt;")
            right_layout.addWidget(note_sub)

            self.edit_vars.installEventFilter(self)
            self.edit_subgroup.installEventFilter(self)

        right_layout.addSpacing(10)

        # Options buttons
        h_opts = QHBoxLayout()
        self.btn_options = QPushButton(btn_text)
        self.btn_options.clicked.connect(self._open_options)
        h_opts.addWidget(self.btn_options)
        h_opts.addStretch()
        right_layout.addLayout(h_opts)

        right_layout.addStretch()

        # Action buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Help
        )
        btn_box.accepted.connect(self._validate_and_accept)
        btn_box.rejected.connect(self.reject)
        right_layout.addWidget(btn_box)

        main_layout.addLayout(right_layout, 2)

    def eventFilter(self, watched, event):
        if event.type() == event.Type.FocusIn:
            if watched in (self.edit_vars, self.edit_subgroup):
                self._active_input = watched
        return super().eventFilter(watched, event)

    def _on_select_clicked(self):
        items = self.var_list.selectedItems()
        if not items or not self._active_input:
            return
        names = []
        for it in items:
            idx = it.data(Qt.ItemDataRole.UserRole)
            col = self.worksheet.columns[idx]
            names.append(f"'{col.name}'" if " " in col.name else col.name)
        curr = self._active_input.text().strip()
        add_str = " ".join(names)
        self._active_input.setText(f"{curr} {add_str}".strip())

    def _on_list_double_clicked(self, item: QListWidgetItem):
        if not self._active_input:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        col = self.worksheet.columns[idx]
        ref = f"'{col.name}'" if " " in col.name else col.name
        curr = self._active_input.text().strip()
        self._active_input.setText(f"{curr} {ref}".strip())

    def _open_options(self):
        dlg = AttributeOptionsDialog(self.chart_type, self.options, self)
        if dlg.exec():
            self.options = dlg.options

    def _validate_and_accept(self):
        vars_text = self.edit_vars.text().strip()
        if not vars_text:
            QMessageBox.warning(self, "Input Required", "Please specify at least one measurement column in Variables.")
            return

        var_indices = resolve_variables(vars_text, self.worksheet)
        if not var_indices:
            QMessageBox.warning(self, "Invalid Variables", f"Could not find valid columns matching: {vars_text}")
            return

        subgroup_val: Union[float, int, None] = None
        subgroup_col_idx: Optional[int] = None
        is_subgroup_col = False

        if self.chart_type in ("P", "NP", "U", "P'", "U'"):
            sub_text = self.edit_subgroup.text().strip() if self.edit_subgroup else ""
            if not sub_text:
                QMessageBox.warning(self, "Input Required", "Please enter a constant number or column for subgroup sizes.")
                return

            # Check if constant number
            try:
                c_val = float(sub_text)
                if c_val <= 0:
                    QMessageBox.warning(self, "Invalid Size", "Subgroup size must be a positive number.")
                    return
                subgroup_val = c_val
                is_subgroup_col = False
            except ValueError:
                # Resolve as column
                sub_cols = resolve_variables(sub_text, self.worksheet)
                if not sub_cols:
                    QMessageBox.warning(self, "Invalid Subgroup Column", f"Could not find column matching: {sub_text}")
                    return
                subgroup_col_idx = sub_cols[0]
                is_subgroup_col = True

        self.selected_params = {
            "chart_type": self.chart_type,
            "variables": var_indices,
            "subgroup_size": subgroup_val,
            "subgroup_col_idx": subgroup_col_idx,
            "is_subgroup_col": is_subgroup_col,
            "options": self.options,
        }
        self.accept()
