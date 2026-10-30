"""Qt Dialogs for Individuals-Moving Range (I-MR) Chart with native StatCraft PE fidelity.

Form Evidence:
- 0811-IMRCHARTDATASOURCE.MDF (Main I-MR Dialog: MenuID 41031, HelpID 87100)
- 0812-INDIVIDUALCHARTESTIMATE.MDF (Estimate Tab: AMR, MMR, SRMSSD, span, Nelson estimate, omission)
- 0813-INDIVIDUALCHARTPARAMETERS.MDF (Parameters Tab: historical mean, historical sigma)
- QCHARTSLIMITS.MDF (Limits Tab: K sigma, upper/lower limit display toggles)
- QCHARTTESTS.MDF (Tests Tab: Nelson tests 1, 2, 3, 4 on Individual chart)
- QCHARTSTORAGE.MDF (Storage Tab)
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .imr_engine import parse_subgroup_omission, run_imr_chart
from .model import Worksheet
from .variable_dialogs import format_variable_reference, resolve_variables


class IMROptionsDialog(QDialog):
    """Subdialog for I-MR Chart Options with 5 tabs matching StatCraft."""

    def __init__(self, parent: QDialog, options: Dict[str, Any]):
        super().__init__(parent)
        self.setWindowTitle("I-MR Options")
        self.resize(480, 420)
        self.options = copy.deepcopy(options)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        # Tab 1: Parameters (0813-INDIVIDUALCHARTPARAMETERS)
        tab_param = QWidget()
        layout_param = QVBoxLayout(tab_param)
        desc_param = QLabel(
            "To specify the values for one or both parameters, enter them here. "
            "StatCraft uses these values instead of estimating them from the data."
        )
        desc_param.setWordWrap(True)
        layout_param.addWidget(desc_param)
        form_param = QFormLayout()

        self.mean_edit = QLineEdit()
        if self.options.get("historical_mean") is not None:
            self.mean_edit.setText(str(self.options["historical_mean"]))
        form_param.addRow("&Mean:", self.mean_edit)

        self.sigma_edit = QLineEdit()
        if self.options.get("historical_sigma") is not None:
            self.sigma_edit.setText(str(self.options["historical_sigma"]))
        form_param.addRow("&Standard deviation:", self.sigma_edit)

        layout_param.addLayout(form_param)
        layout_param.addStretch()
        self.tabs.addTab(tab_param, "Parameters")

        # Tab 2: Estimate (0812-INDIVIDUALCHARTESTIMATE)
        tab_est = QWidget()
        layout_est = QVBoxLayout(tab_est)

        grp_omit = QGroupBox("Subgroup Omission")
        layout_omit = QVBoxLayout(grp_omit)
        self.omit_combo = QComboBox()
        self.omit_combo.addItems([
            "Omit the following subgroups when estimating parameters (eg, 3 12:15)",
            "Use the following subgroups when estimating parameters (eg, 3 12:15)",
        ])
        layout_omit.addWidget(self.omit_combo)
        self.omit_edit = QLineEdit()
        if self.options.get("omit_subgroups"):
            omit_s = " ".join(str(x) for x in self.options["omit_subgroups"])
            self.omit_edit.setText(omit_s)
        layout_omit.addWidget(self.omit_edit)
        layout_est.addWidget(grp_omit)

        grp_method = QGroupBox("Method for estimating standard deviation")
        layout_method = QVBoxLayout(grp_method)
        self.bg_method = QButtonGroup(self)
        self.rb_amr = QRadioButton("&Average moving range")
        self.rb_mmr = QRadioButton("Me&dian moving range")
        self.rb_srmssd = QRadioButton("S&quare root of MSSD")
        self.bg_method.addButton(self.rb_amr, 0)
        self.bg_method.addButton(self.rb_mmr, 1)
        self.bg_method.addButton(self.rb_srmssd, 2)
        layout_method.addWidget(self.rb_amr)
        layout_method.addWidget(self.rb_mmr)
        layout_method.addWidget(self.rb_srmssd)

        cur_meth = self.options.get("estimation_method", "amr")
        if cur_meth == "mmr":
            self.rb_mmr.setChecked(True)
        elif cur_meth == "srmssd":
            self.rb_srmssd.setChecked(True)
        else:
            self.rb_amr.setChecked(True)

        layout_est.addWidget(grp_method)

        form_span = QFormLayout()
        self.span_edit = QLineEdit(str(self.options.get("span", 2)))
        form_span.addRow("&Length of moving range:", self.span_edit)
        layout_est.addLayout(form_span)

        self.chk_nelson = QCheckBox("Use Nelson &estimate")
        self.chk_nelson.setChecked(bool(self.options.get("use_nelson", True)))
        layout_est.addWidget(self.chk_nelson)

        layout_est.addStretch()
        self.tabs.addTab(tab_est, "Estimate")

        # Tab 3: Limits (QCHARTSLIMITS)
        tab_lim = QWidget()
        layout_lim = QVBoxLayout(tab_lim)
        form_lim = QFormLayout()
        k_val = self.options.get("k_sigma", 3.0)
        if isinstance(k_val, list):
            k_val_str = " ".join(str(x) for x in k_val)
        else:
            k_val_str = str(k_val)
        self.k_sigma_edit = QLineEdit(k_val_str)
        form_lim.addRow("&Number of standard deviations:", self.k_sigma_edit)
        layout_lim.addLayout(form_lim)

        self.chk_upper = QCheckBox("Display &upper control limit")
        self.chk_upper.setChecked(bool(self.options.get("display_upper", True)))
        layout_lim.addWidget(self.chk_upper)

        self.chk_lower = QCheckBox("Display &lower control limit")
        self.chk_lower.setChecked(bool(self.options.get("display_lower", True)))
        layout_lim.addWidget(self.chk_lower)

        # StatCraft.6: Extended limits & warning limits
        h_warn = QHBoxLayout()
        self.chk_warning = QCheckBox("Display &warning limits at K standard deviations:")
        self.chk_warning.setChecked(bool(self.options.get("warning_limits", False)))
        h_warn.addWidget(self.chk_warning)
        self.edit_warn_k = QLineEdit(str(self.options.get("warning_k", 2.0)))
        self.edit_warn_k.setFixedWidth(50)
        h_warn.addWidget(self.edit_warn_k)
        h_warn.addStretch()
        layout_lim.addLayout(h_warn)

        self.chk_zones = QCheckBox("Display zone boundary lines (A, B, C bands at 1, 2, 3 sigma)")
        self.chk_zones.setChecked(bool(self.options.get("display_zones", False)))
        layout_lim.addWidget(self.chk_zones)

        layout_lim.addStretch()
        self.tabs.addTab(tab_lim, "Limits")

        # Tab 4: Tests (QCHARTTESTS - Tests 1-4 for individuals)
        tab_tests = QWidget()
        layout_tests = QVBoxLayout(tab_tests)
        lbl_tests = QLabel("Perform tests for special causes on Individual Chart:")
        lbl_tests.setFont(tab_tests.font())
        layout_tests.addWidget(lbl_tests)

        tests_cfg = self.options.get("tests", {})

        # Test 1
        t1_cfg = tests_cfg.get("test1", {})
        h_t1 = QHBoxLayout()
        self.chk_t1 = QCheckBox("1 point >")
        self.chk_t1.setChecked(bool(t1_cfg.get("enabled", True)))
        self.edit_t1 = QLineEdit(str(t1_cfg.get("k", 3.0)))
        self.edit_t1.setFixedWidth(50)
        lbl_t1 = QLabel("standard deviations from center line [Test 1]")
        h_t1.addWidget(self.chk_t1)
        h_t1.addWidget(self.edit_t1)
        h_t1.addWidget(lbl_t1)
        h_t1.addStretch()
        layout_tests.addLayout(h_t1)

        # Test 2
        t2_cfg = tests_cfg.get("test2", {})
        h_t2 = QHBoxLayout()
        self.chk_t2 = QCheckBox("")
        self.chk_t2.setChecked(bool(t2_cfg.get("enabled", False)))
        self.edit_t2 = QLineEdit(str(t2_cfg.get("k", 9)))
        self.edit_t2.setFixedWidth(50)
        lbl_t2 = QLabel("points in a row on same side of center line [Test 2]")
        h_t2.addWidget(self.chk_t2)
        h_t2.addWidget(self.edit_t2)
        h_t2.addWidget(lbl_t2)
        h_t2.addStretch()
        layout_tests.addLayout(h_t2)

        # Test 3
        t3_cfg = tests_cfg.get("test3", {})
        h_t3 = QHBoxLayout()
        self.chk_t3 = QCheckBox("")
        self.chk_t3.setChecked(bool(t3_cfg.get("enabled", False)))
        self.edit_t3 = QLineEdit(str(t3_cfg.get("k", 6)))
        self.edit_t3.setFixedWidth(50)
        lbl_t3 = QLabel("points in a row, all increasing or all decreasing [Test 3]")
        h_t3.addWidget(self.chk_t3)
        h_t3.addWidget(self.edit_t3)
        h_t3.addWidget(lbl_t3)
        h_t3.addStretch()
        layout_tests.addLayout(h_t3)

        # Test 4
        t4_cfg = tests_cfg.get("test4", {})
        h_t4 = QHBoxLayout()
        self.chk_t4 = QCheckBox("")
        self.chk_t4.setChecked(bool(t4_cfg.get("enabled", False)))
        self.edit_t4 = QLineEdit(str(t4_cfg.get("k", 14)))
        self.edit_t4.setFixedWidth(50)
        lbl_t4 = QLabel("points in a row, alternating up and down [Test 4]")
        h_t4.addWidget(self.chk_t4)
        h_t4.addWidget(self.edit_t4)
        h_t4.addWidget(lbl_t4)
        h_t4.addStretch()
        layout_tests.addLayout(h_t4)

        # Buttons to toggle all tests
        h_btn_tests = QHBoxLayout()
        btn_all = QPushButton("Perform &All Tests")
        btn_all.clicked.connect(self._select_all_tests)
        btn_none = QPushButton("Perform &No Tests")
        btn_none.clicked.connect(self._deselect_all_tests)
        h_btn_tests.addWidget(btn_all)
        h_btn_tests.addWidget(btn_none)
        h_btn_tests.addStretch()
        layout_tests.addLayout(h_btn_tests)

        layout_tests.addStretch()
        self.tabs.addTab(tab_tests, "Tests")

        # Tab 5: Storage (QCHARTSTORAGE)
        tab_store = QWidget()
        layout_store = QVBoxLayout(tab_store)
        store_cfg = self.options.get("storage", {})
        self.chk_store_pts = QCheckBox("Individual values and moving ranges")
        self.chk_store_pts.setChecked(bool(store_cfg.get("points", False)))
        self.chk_store_cl = QCheckBox("Center lines")
        self.chk_store_cl.setChecked(bool(store_cfg.get("center_line", False)))
        self.chk_store_lim = QCheckBox("Control limits")
        self.chk_store_lim.setChecked(bool(store_cfg.get("control_limits", False)))
        self.chk_store_res = QCheckBox("Test results")
        self.chk_store_res.setChecked(bool(store_cfg.get("test_results", False)))

        layout_store.addWidget(self.chk_store_pts)
        layout_store.addWidget(self.chk_store_cl)
        layout_store.addWidget(self.chk_store_lim)
        layout_store.addWidget(self.chk_store_res)
        layout_store.addStretch()
        self.tabs.addTab(tab_store, "Storage")

        # Dialog Buttons
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bbox.accepted.connect(self._save_and_accept)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    def _select_all_tests(self) -> None:
        self.chk_t1.setChecked(True)
        self.chk_t2.setChecked(True)
        self.chk_t3.setChecked(True)
        self.chk_t4.setChecked(True)

    def _deselect_all_tests(self) -> None:
        self.chk_t1.setChecked(False)
        self.chk_t2.setChecked(False)
        self.chk_t3.setChecked(False)
        self.chk_t4.setChecked(False)

    def _save_and_accept(self) -> None:
        # Validate Parameters
        mean_val = None
        if self.mean_edit.text().strip():
            try:
                mean_val = float(self.mean_edit.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Invalid Entry", "Historical Mean must be a valid number.")
                return

        sigma_val = None
        if self.sigma_edit.text().strip():
            try:
                sigma_val = float(self.sigma_edit.text().strip())
                if sigma_val <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self, "Invalid Entry", "Historical Standard Deviation must be a positive number.")
                return

        # Validate Span
        try:
            span_val = int(self.span_edit.text().strip())
            if not (2 <= span_val <= 100):
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Invalid Entry", "Length of moving range must be an integer between 2 and 100.")
            return

        # Validate K Sigma
        k_txt = self.k_sigma_edit.text().strip()
        try:
            parts = [float(x) for x in k_txt.replace(',', ' ').split()] if k_txt else [3.0]
            k_sigma_val = parts[-1] if parts else 3.0
            if not (0.1 <= k_sigma_val <= 10.0):
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Invalid Entry", "Number of standard deviations must be between 0.1 and 10.0.")
            return

        warn_k = 2.0
        try:
            warn_k = float(self.edit_warn_k.text().strip() or "2.0")
        except ValueError:
            warn_k = 2.0

        # Estimation method
        mid = self.bg_method.checkedId()
        meth = "amr" if mid == 0 else ("mmr" if mid == 1 else "srmssd")

        # Omission
        omit_set = parse_subgroup_omission(self.omit_edit.text().strip())

        # Tests
        t1_k = float(self.edit_t1.text().strip() or 3.0)
        t2_k = int(self.edit_t2.text().strip() or 9)
        t3_k = int(self.edit_t3.text().strip() or 6)
        t4_k = int(self.edit_t4.text().strip() or 14)

        tests_dict = {
            "test1": {"enabled": self.chk_t1.isChecked(), "k": t1_k},
            "test2": {"enabled": self.chk_t2.isChecked(), "k": t2_k},
            "test3": {"enabled": self.chk_t3.isChecked(), "k": t3_k},
            "test4": {"enabled": self.chk_t4.isChecked(), "k": t4_k},
        }

        self.options = {
            "historical_mean": mean_val,
            "historical_sigma": sigma_val,
            "estimation_method": meth,
            "span": span_val,
            "use_nelson": self.chk_nelson.isChecked(),
            "unbiasing": True,
            "omit_subgroups": sorted(omit_set),
            "k_sigma": k_txt if len(parts) > 1 else k_sigma_val,
            "warning_limits": self.chk_warning.isChecked() or len(parts) > 1,
            "warning_k": warn_k,
            "display_zones": self.chk_zones.isChecked() or len(parts) >= 3,
            "display_upper": self.chk_upper.isChecked(),
            "display_lower": self.chk_lower.isChecked(),
            "tests": tests_dict,
            "storage": {
                "points": self.chk_store_pts.isChecked(),
                "center_line": self.chk_store_cl.isChecked(),
                "control_limits": self.chk_store_lim.isChecked(),
                "test_results": self.chk_store_res.isChecked(),
            },
        }
        self.accept()


class IMRChartDialog(QDialog):
    """Main dialog for Individuals-Moving Range Chart matching 0811-IMRCHARTDATASOURCE.MDF."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Individuals - Moving Range Chart")
        self.resize(520, 320)

        self.options: Dict[str, Any] = {
            "span": 2,
            "estimation_method": "amr",
            "use_nelson": True,
            "unbiasing": True,
            "k_sigma": 3.0,
            "display_upper": True,
            "display_lower": True,
            "tests": {
                "test1": {"enabled": True, "k": 3.0},
                "test2": {"enabled": False, "k": 9},
                "test3": {"enabled": False, "k": 6},
                "test4": {"enabled": False, "k": 14},
            },
        }
        self.selected_params: Optional[Dict[str, Any]] = None

        main_layout = QHBoxLayout(self)

        # Left Column: Variables ListBox + Select Button
        left_layout = QVBoxLayout()
        self.var_list = QListWidget()
        for idx, col in enumerate(worksheet.columns):
            if col.kind == "number":
                item = QListWidgetItem(f"C{idx + 1}  {col.name}")
                item.setData(Qt.ItemDataRole.UserRole, idx)
                self.var_list.addItem(item)

        left_layout.addWidget(self.var_list)
        self.btn_select = QPushButton("&Select")
        self.btn_select.setEnabled(False)
        self.btn_select.clicked.connect(self._select_variable)
        self.var_list.itemSelectionChanged.connect(self._list_selection_changed)
        self.var_list.itemDoubleClicked.connect(self._select_variable)
        left_layout.addWidget(self.btn_select)
        main_layout.addLayout(left_layout, 1)

        # Right Column: Controls & Subdialog Launchers
        right_layout = QVBoxLayout()
        lbl_vars = QLabel("&Variables:")
        right_layout.addWidget(lbl_vars)

        self.edit_vars = QLineEdit()
        lbl_vars.setBuddy(self.edit_vars)
        right_layout.addWidget(self.edit_vars)

        right_layout.addSpacing(16)

        # Child Dialog Launchers
        grid_buttons = QHBoxLayout()
        self.btn_scale = QPushButton("&Scale...")
        self.btn_labels = QPushButton("&Labels...")
        self.btn_options = QPushButton("I-MR O&ptions...")
        self.btn_options.clicked.connect(self._open_options)

        grid_buttons.addWidget(self.btn_scale)
        grid_buttons.addWidget(self.btn_labels)
        grid_buttons.addWidget(self.btn_options)
        right_layout.addLayout(grid_buttons)

        right_layout.addStretch()

        # Dialog Footer Buttons: OK, Cancel, Help
        footer_layout = QHBoxLayout()
        self.btn_help = QPushButton("Help")
        footer_layout.addWidget(self.btn_help)
        footer_layout.addStretch()

        self.btn_ok = QPushButton("&OK")
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)

        footer_layout.addWidget(self.btn_ok)
        footer_layout.addWidget(self.btn_cancel)
        right_layout.addLayout(footer_layout)

        main_layout.addLayout(right_layout, 2)

    def _list_selection_changed(self) -> None:
        self.btn_select.setEnabled(bool(self.var_list.selectedItems()))

    def _select_variable(self) -> None:
        items = self.var_list.selectedItems()
        if not items:
            return
        selected_refs: List[str] = []
        for it in items:
            idx = it.data(Qt.ItemDataRole.UserRole)
            col = self.worksheet.columns[idx]
            selected_refs.append(format_variable_reference(col, idx))

        cur_text = self.edit_vars.text().strip()
        add_text = " ".join(selected_refs)
        if cur_text:
            self.edit_vars.setText(f"{cur_text} {add_text}")
        else:
            self.edit_vars.setText(add_text)
        self.edit_vars.setFocus()

    def _open_options(self) -> None:
        dlg = IMROptionsDialog(self, self.options)
        if dlg.exec():
            self.options = dlg.options

    def _on_ok(self) -> None:
        raw_text = self.edit_vars.text().strip()
        if not raw_text:
            QMessageBox.warning(self, "Invalid Entry", "Select or enter at least one numeric variable.")
            return

        try:
            col_indices = resolve_variables(raw_text, self.worksheet)
        except ValueError as ex:
            QMessageBox.warning(self, "Invalid Entry", str(ex))
            return

        if not col_indices:
            QMessageBox.warning(self, "Invalid Entry", "No matching columns found in worksheet.")
            return

        # Check all are numeric
        for idx in col_indices:
            if self.worksheet.columns[idx].kind != "number":
                col_name = self.worksheet.columns[idx].name
                QMessageBox.warning(self, "Invalid Entry", f"Column '{col_name}' must be numeric.")
                return

        self.selected_params = {
            "variables": col_indices,
            "options": copy.deepcopy(self.options),
        }
        self.accept()
