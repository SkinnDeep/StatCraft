"""Qt Dialogs for Multivariate Control Charts (T-Squared, Generalized Variance, MEWMA).

Form Evidence:
- 1154-TSQUAREDDATASOURCE.MDF (T-Squared Chart: MenuID 41043, HelpID 86300)
- 0753-GENVARDATASOURCE.MDF (Generalized Variance Chart: MenuID 41044, HelpID 86400)
- 0856-MEWMADATASOURCE.MDF (Multivariate EWMA Chart: MenuID 41045, HelpID 86500)
- 1007-QCHARTMULTIPARAMETERS.MDF (Multivariate Options: Covariance, Means, Limits)
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Union
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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


class MultivariateOptionsDialog(QDialog):
    """Subdialog for Multivariate Control Chart Options (Parameters, Estimate / Omit Subgroups)."""

    def __init__(self, chart_type: str, options: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.chart_type = chart_type.upper()
        self.setWindowTitle(f"{self.chart_type} Options")
        self.resize(460, 320)
        self.options = copy.deepcopy(options)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        # Tab 1: Parameters / Limits
        tab_param = QWidget()
        form_param = QFormLayout(tab_param)

        if self.chart_type == "TSQUARED":
            self.edit_alpha = QLineEdit(str(self.options.get("alpha", 0.0027)))
            form_param.addRow("Alpha (&Significance level):", self.edit_alpha)
        elif self.chart_type == "GENVAR":
            self.edit_k_sigma = QLineEdit(str(self.options.get("k_sigma", 3.0)))
            form_param.addRow("Number of standard deviations (&k):", self.edit_k_sigma)
        elif self.chart_type == "MEWMA":
            self.edit_arl = QLineEdit(str(self.options.get("arl", 200.0)))
            form_param.addRow("Target &ARL (Average Run Length):", self.edit_arl)
            self.edit_weight = QLineEdit(str(self.options.get("weight", 0.1)))
            form_param.addRow("&Weight (r):", self.edit_weight)

        self.tabs.addTab(tab_param, "Parameters")

        # Tab 2: Estimate / Omit
        tab_est = QWidget()
        form_est = QFormLayout(tab_est)
        lbl_omit = QLabel("Omit the following subgroups when estimating parameters:")
        lbl_omit.setWordWrap(True)
        form_est.addRow(lbl_omit)
        self.edit_omit = QLineEdit(str(self.options.get("omit_subgroups", "")))
        self.edit_omit.setPlaceholderText("e.g. 2, 4 6-8")
        form_est.addRow("Omit &subgroups:", self.edit_omit)

        self.tabs.addTab(tab_est, "Estimate")

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._save_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _save_and_accept(self) -> None:
        if self.chart_type == "TSQUARED":
            try:
                a_val = float(self.edit_alpha.text().strip())
                if a_val <= 0 or a_val >= 1:
                    raise ValueError
                self.options["alpha"] = a_val
            except ValueError:
                QMessageBox.warning(self, "Invalid Alpha", "Alpha must be between 0 and 1.")
                return
        elif self.chart_type == "GENVAR":
            try:
                k_val = float(self.edit_k_sigma.text().strip())
                if k_val <= 0:
                    raise ValueError
                self.options["k_sigma"] = k_val
            except ValueError:
                QMessageBox.warning(self, "Invalid k", "Sigma multiplier k must be a positive number.")
                return
        elif self.chart_type == "MEWMA":
            try:
                arl_val = float(self.edit_arl.text().strip())
                if arl_val <= 0:
                    raise ValueError
                self.options["arl"] = arl_val
            except ValueError:
                QMessageBox.warning(self, "Invalid ARL", "Target ARL must be positive.")
                return

            try:
                w_val = float(self.edit_weight.text().strip())
                if w_val <= 0 or w_val > 1:
                    raise ValueError
                self.options["weight"] = w_val
            except ValueError:
                QMessageBox.warning(self, "Invalid Weight", "Weight must be between 0 and 1.")
                return

        self.options["omit_subgroups"] = self.edit_omit.text().strip()
        self.accept()

    def get_options(self) -> Dict[str, Any]:
        return self.options


class MultivariateChartDialog(QDialog):
    """Main dialog for Multivariate Control Charts (T-Squared, GenVar, MEWMA)."""

    def __init__(
        self,
        worksheet: Worksheet,
        chart_type: str = "TSQUARED",
        initial_vars: Optional[List[str]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.worksheet = worksheet
        self.chart_type = chart_type.upper()
        self.options: Dict[str, Any] = {}

        if self.chart_type == "TSQUARED":
            self.setWindowTitle("T² Chart")
            self.help_id = 86300
        elif self.chart_type == "GENVAR":
            self.setWindowTitle("Generalized Variance Chart")
            self.help_id = 86400
        elif self.chart_type == "MEWMA":
            self.setWindowTitle("Multivariate EWMA Chart")
            self.help_id = 86500
        else:
            self.setWindowTitle("Multivariate Control Chart")
            self.help_id = 86300

        self.resize(560, 420)
        self._setup_ui(initial_vars or [])

    def _setup_ui(self, initial_vars: List[str]) -> None:
        main_layout = QHBoxLayout(self)

        # Left Column: Column Picker List
        left_layout = QVBoxLayout()
        lbl_cols = QLabel("Columns:")
        left_layout.addWidget(lbl_cols)

        self.col_list = QListWidget()
        for idx, col in enumerate(self.worksheet.columns):
            name = col.name if col.name else f"C{idx+1}"
            item = QListWidgetItem(f"C{idx+1}   {name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.col_list.addItem(item)
        left_layout.addWidget(self.col_list)

        self.btn_select = QPushButton("Select")
        self.btn_select.clicked.connect(self._on_select_clicked)
        left_layout.addWidget(self.btn_select)
        main_layout.addLayout(left_layout, 1)

        # Right Column: Inputs & Controls
        right_layout = QVBoxLayout()

        # Variables Edit
        lbl_vars = QLabel("&Variables:")
        right_layout.addWidget(lbl_vars)
        self.edit_vars = QLineEdit(" ".join(initial_vars))
        lbl_vars.setBuddy(self.edit_vars)
        right_layout.addWidget(self.edit_vars)

        # Subgroup Size Input
        lbl_sg = QLabel("S&ubgroup sizes:")
        right_layout.addWidget(lbl_sg)
        sg_layout = QHBoxLayout()
        self.edit_subgroup = QLineEdit("1" if self.chart_type != "GENVAR" else "5")
        lbl_sg.setBuddy(self.edit_subgroup)
        sg_layout.addWidget(self.edit_subgroup)
        lbl_hint = QLabel("(enter a number or ID column)")
        lbl_hint.setStyleSheet("color: #666;")
        sg_layout.addWidget(lbl_hint)
        right_layout.addLayout(sg_layout)

        # MEWMA specific controls (ARL, Weight)
        if self.chart_type == "MEWMA":
            mewma_layout = QHBoxLayout()
            lbl_arl = QLabel("A&RL:")
            self.edit_arl = QLineEdit("200.0")
            lbl_arl.setBuddy(self.edit_arl)
            mewma_layout.addWidget(lbl_arl)
            mewma_layout.addWidget(self.edit_arl)

            lbl_wt = QLabel("&Weight:")
            self.edit_weight = QLineEdit("0.1")
            lbl_wt.setBuddy(self.edit_weight)
            mewma_layout.addWidget(lbl_wt)
            mewma_layout.addWidget(self.edit_weight)
            right_layout.addLayout(mewma_layout)

        # T-Squared specific decomposition checkbox
        if self.chart_type == "TSQUARED":
            self.chk_decomp = QCheckBox("Display decomposition of &signaled points")
            self.chk_decomp.setChecked(True)
            right_layout.addWidget(self.chk_decomp)

        right_layout.addStretch()

        # Options Button
        btn_options_title = f"{self.chart_type.capitalize()} Options..."
        if self.chart_type == "TSQUARED":
            btn_options_title = "T² Options..."
        elif self.chart_type == "GENVAR":
            btn_options_title = "GenVar Options..."
        elif self.chart_type == "MEWMA":
            btn_options_title = "MEWMA Options..."

        self.btn_options = QPushButton(btn_options_title)
        self.btn_options.clicked.connect(self._on_options_clicked)
        right_layout.addWidget(self.btn_options)

        # Standard Dialog Buttons (OK, Cancel)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        right_layout.addWidget(btn_box)

        main_layout.addLayout(right_layout, 2)

    def _on_select_clicked(self) -> None:
        items = self.col_list.selectedItems()
        if not items:
            return
        selected_names = [it.data(Qt.ItemDataRole.UserRole) for it in items]
        curr = self.edit_vars.text().strip()
        new_text = (curr + " " + " ".join(selected_names)).strip()
        self.edit_vars.setText(new_text)

    def _on_options_clicked(self) -> None:
        dlg = MultivariateOptionsDialog(self.chart_type, self.options, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.options = dlg.get_options()

    def _on_accept(self) -> None:
        vars_text = self.edit_vars.text().strip()
        if not vars_text:
            QMessageBox.warning(self, "Missing Variables", "Please enter at least two variable columns.")
            return

        try:
            resolved_indices = resolve_variables(vars_text, self.worksheet)
        except Exception:
            resolved_indices = []

        if len(resolved_indices) < 2:
            QMessageBox.warning(
                self,
                "Insufficient Variables",
                "Multivariate control charts require at least two variables.",
            )
            return

        sg_text = self.edit_subgroup.text().strip()
        if not sg_text:
            QMessageBox.warning(self, "Missing Subgroup Size", "Please specify a subgroup size or column.")
            return

        if self.chart_type == "GENVAR":
            try:
                val = int(sg_text)
                if val < 2:
                    QMessageBox.warning(
                        self,
                        "Invalid Subgroup Size",
                        "Generalized Variance chart requires subgroup sizes of at least 2.",
                    )
                    return
            except ValueError:
                # Column reference, will be validated during extraction
                pass

        if self.chart_type == "MEWMA":
            try:
                arl = float(self.edit_arl.text().strip())
                if arl <= 0:
                    raise ValueError
                self.options["arl"] = arl
            except ValueError:
                QMessageBox.warning(self, "Invalid ARL", "ARL must be a positive number.")
                return

            try:
                w = float(self.edit_weight.text().strip())
                if w <= 0 or w > 1:
                    raise ValueError
                self.options["weight"] = w
            except ValueError:
                QMessageBox.warning(self, "Invalid Weight", "Weight must be between 0 and 1.")
                return

        self.accept()

    def get_configuration(self) -> Dict[str, Any]:
        vars_text = self.edit_vars.text().strip()
        try:
            resolved_indices = resolve_variables(vars_text, self.worksheet)
            resolved_vars = [self.worksheet.columns[i].name for i in resolved_indices]
        except Exception:
            resolved_vars = vars_text.split()

        sg_text = self.edit_subgroup.text().strip()
        try:
            sg_val: Union[int, str] = int(sg_text)
        except ValueError:
            sg_val = sg_text

        config = {
            "chart_type": self.chart_type,
            "variable_names": resolved_vars,
            "columns": resolved_vars,
            "variables": resolved_vars,
            "subgroup_size": sg_val,
            "options": copy.deepcopy(self.options),
        }
        if self.chart_type == "TSQUARED":
            config["decomp"] = getattr(self, "chk_decomp", None) and self.chk_decomp.isChecked()

        return config
