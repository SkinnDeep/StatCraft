"""Qt Dialogs for Type 1 Gage Study with native StatCraft PE fidelity.

Form Evidence:
- 1158-TYPE1GAGESTUDY.MDF (MenuID 41127, HelpID 88670)
- 1157-TYPE1GAGEOPTIONS.MDF (HelpID 88669)
- 1156-TYPE1GAGEINFO.MDF (HelpID 88668)
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
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
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from .model import Worksheet
from .variable_dialogs import resolve_variables


class Type1GageInfoDialog(QDialog):
    """Sub-dialog for entering metadata about the gage under test (1156-TYPE1GAGEINFO.MDF)."""

    def __init__(self, current_info: Optional[Dict[str, str]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Type 1 Gage Study: Gage Info")
        self.resize(400, 200)

        info = current_info or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.edit_name = QLineEdit(info.get("gage_name", ""))
        form.addRow("&Gage Name:", self.edit_name)

        self.edit_date = QLineEdit(info.get("date_of_study", ""))
        form.addRow("&Date of study:", self.edit_date)

        self.edit_reported = QLineEdit(info.get("reported_by", ""))
        form.addRow("&Reported by:", self.edit_reported)

        self.edit_misc = QLineEdit(info.get("misc", ""))
        form.addRow("&Miscellaneous:", self.edit_misc)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_info(self) -> Dict[str, str]:
        return {
            "gage_name": self.edit_name.text().strip(),
            "date_of_study": self.edit_date.text().strip(),
            "reported_by": self.edit_reported.text().strip(),
            "misc": self.edit_misc.text().strip(),
        }


class Type1GageOptionsDialog(QDialog):
    """Sub-dialog for statistical options (1157-TYPE1GAGEOPTIONS.MDF)."""

    def __init__(self, current_opts: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Type 1 Gage Study: Options")
        self.resize(440, 240)

        opts = current_opts or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.edit_pct = QLineEdit(str(opts.get("cg_percent", 20.0)))
        form.addRow("&Percent of the tolerance for calculating Cg:", self.edit_pct)

        h_stdy = QHBoxLayout()
        self.edit_stdy = QLineEdit(str(opts.get("study_var", 6.0)))
        self.edit_stdy.setFixedWidth(60)
        h_stdy.addWidget(self.edit_stdy)
        h_stdy.addWidget(QLabel("(number of standard deviations)"))
        h_stdy.addStretch()
        form.addRow("&Study variation:", h_stdy)

        self.edit_reso = QLineEdit(str(opts.get("resolution", "") or ""))
        self.edit_reso.setPlaceholderText("Optional")
        form.addRow("R&esolution:", self.edit_reso)

        self.chk_no_bias = QCheckBox("&No bias test")
        self.chk_no_bias.setChecked(not opts.get("perform_bias_test", True))
        form.addRow("", self.chk_no_bias)

        self.edit_title = QLineEdit(opts.get("title", ""))
        self.edit_title.setPlaceholderText("Optional custom graph title")
        form.addRow("&Title:", self.edit_title)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate_and_accept(self) -> None:
        try:
            pct = float(self.edit_pct.text().strip())
            if pct <= 0 or pct > 100:
                raise ValueError("Percent of tolerance must be between 0 and 100.")
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Option", str(exc))
            return

        try:
            stdy = float(self.edit_stdy.text().strip())
            if stdy <= 0:
                raise ValueError("Study variation must be a positive number.")
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Option", str(exc))
            return

        reso_text = self.edit_reso.text().strip()
        if reso_text:
            try:
                reso = float(reso_text)
                if reso <= 0:
                    raise ValueError("Resolution must be a positive number.")
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid Option", str(exc))
                return

        self.accept()

    def get_options(self) -> Dict[str, Any]:
        reso_text = self.edit_reso.text().strip()
        reso = float(reso_text) if reso_text else None
        return {
            "cg_percent": float(self.edit_pct.text().strip()),
            "study_var": float(self.edit_stdy.text().strip()),
            "resolution": reso,
            "perform_bias_test": not self.chk_no_bias.isChecked(),
            "title": self.edit_title.text().strip(),
        }


class Type1GageDialog(QDialog):
    """Main dialog for Type 1 Gage Study matching 1158-TYPE1GAGESTUDY.MDF."""

    def __init__(
        self,
        worksheet: Worksheet,
        initial_vars: Optional[List[str]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Type 1 Gage Study")
        self.resize(520, 360)
        self.last_active_edit: Optional[QLineEdit] = None

        self.gage_info: Dict[str, str] = {
            "gage_name": "",
            "date_of_study": "",
            "reported_by": "",
            "misc": ""
        }
        self.options: Dict[str, Any] = {
            "cg_percent": 20.0,
            "study_var": 6.0,
            "resolution": None,
            "perform_bias_test": True,
            "title": ""
        }
        self.result_params: Optional[Dict[str, Any]] = None

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

        # Right Column: Inputs & Specifications
        right_layout = QVBoxLayout()

        form = QFormLayout()
        init_meas = initial_vars[0] if initial_vars else ""
        self.edit_measurement = QLineEdit(init_meas)
        self.edit_measurement.textChanged.connect(lambda: setattr(self, "last_active_edit", self.edit_measurement))
        form.addRow("&Measurement data:", self.edit_measurement)

        self.edit_reference = QLineEdit()
        self.edit_reference.textChanged.connect(lambda: setattr(self, "last_active_edit", self.edit_reference))
        form.addRow("&Reference:", self.edit_reference)
        right_layout.addLayout(form)

        # Tolerance specifications group box
        group_tol = QGroupBox("Tolerance")
        group_layout = QVBoxLayout(group_tol)

        self.radio_tol = QRadioButton("&Upper spec - lower spec:")
        self.radio_lsl = QRadioButton("&Lower spec only:")
        self.radio_usl = QRadioButton("Upp&er spec only:")
        self.radio_tol.setChecked(True)

        self.btn_group_tol = QButtonGroup(self)
        self.btn_group_tol.addButton(self.radio_tol, 0)
        self.btn_group_tol.addButton(self.radio_lsl, 1)
        self.btn_group_tol.addButton(self.radio_usl, 2)
        self.btn_group_tol.buttonClicked.connect(self._on_tol_type_changed)

        # Tolerance edit box
        h_tol = QHBoxLayout()
        h_tol.addWidget(self.radio_tol)
        self.edit_tol = QLineEdit()
        self.edit_tol.textChanged.connect(lambda: setattr(self, "last_active_edit", self.edit_tol))
        h_tol.addWidget(self.edit_tol)
        group_layout.addLayout(h_tol)

        # LSL edit box
        h_lsl = QHBoxLayout()
        h_lsl.addWidget(self.radio_lsl)
        self.edit_lsl = QLineEdit()
        self.edit_lsl.setEnabled(False)
        self.edit_lsl.textChanged.connect(lambda: setattr(self, "last_active_edit", self.edit_lsl))
        h_lsl.addWidget(self.edit_lsl)
        group_layout.addLayout(h_lsl)

        # USL edit box
        h_usl = QHBoxLayout()
        h_usl.addWidget(self.radio_usl)
        self.edit_usl = QLineEdit()
        self.edit_usl.setEnabled(False)
        self.edit_usl.textChanged.connect(lambda: setattr(self, "last_active_edit", self.edit_usl))
        h_usl.addWidget(self.edit_usl)
        group_layout.addLayout(h_usl)

        right_layout.addWidget(group_tol)

        # Sub-dialog buttons row
        btn_layout = QHBoxLayout()
        self.btn_gage_info = QPushButton("&Gage Info...")
        self.btn_gage_info.clicked.connect(self._on_gage_info_clicked)
        btn_layout.addWidget(self.btn_gage_info)

        self.btn_options = QPushButton("O&ptions...")
        self.btn_options.clicked.connect(self._on_options_clicked)
        btn_layout.addWidget(self.btn_options)
        btn_layout.addStretch()
        right_layout.addLayout(btn_layout)

        right_layout.addStretch()

        # Standard dialog buttons
        dialog_btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Help
        )
        dialog_btns.accepted.connect(self._validate_and_accept)
        dialog_btns.rejected.connect(self.reject)
        dialog_btns.helpRequested.connect(self._on_help)
        right_layout.addWidget(dialog_btns)

        main_layout.addLayout(right_layout, 2)
        self.last_active_edit = self.edit_measurement

    def _on_tol_type_changed(self) -> None:
        if self.radio_tol.isChecked():
            self.edit_tol.setEnabled(True)
            self.edit_lsl.setEnabled(False)
            self.edit_usl.setEnabled(False)
        elif self.radio_lsl.isChecked():
            self.edit_tol.setEnabled(False)
            self.edit_lsl.setEnabled(True)
            self.edit_usl.setEnabled(False)
        else:
            self.edit_tol.setEnabled(False)
            self.edit_lsl.setEnabled(False)
            self.edit_usl.setEnabled(True)

    def _on_select_clicked(self) -> None:
        current_item = self.col_list.currentItem()
        if not current_item or not self.last_active_edit:
            return
        col_name = current_item.data(Qt.ItemDataRole.UserRole)
        self.last_active_edit.setText(f"'{col_name}'" if " " in col_name else col_name)

    def _on_gage_info_clicked(self) -> None:
        dlg = Type1GageInfoDialog(self.gage_info, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.gage_info = dlg.get_info()

    def _on_options_clicked(self) -> None:
        dlg = Type1GageOptionsDialog(self.options, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.options = dlg.get_options()

    def _on_help(self) -> None:
        QMessageBox.information(
            self,
            "Type 1 Gage Study Help",
            "A Type 1 Gage Study evaluates the repeatability and bias of a measurement system using repeated measurements of a single standard part.\n\n"
            "AIAG standard acceptance threshold: Cg >= 1.33 and Cgk >= 1.33.",
        )

    def _validate_and_accept(self) -> None:
        meas_text = self.edit_measurement.text().strip()
        if not meas_text:
            QMessageBox.warning(self, "Missing Measurement Data", "Please select a column containing measurement data.")
            self.edit_measurement.setFocus()
            return

        try:
            col_indices = resolve_variables(meas_text, self.worksheet, kinds=("number",))
            if not col_indices:
                raise ValueError("No valid numeric measurement column selected.")
            meas_idx = col_indices[0]
        except Exception as exc:
            QMessageBox.warning(self, "Invalid Measurement Column", str(exc))
            self.edit_measurement.setFocus()
            return

        ref_text = self.edit_reference.text().strip()
        if not ref_text:
            QMessageBox.warning(self, "Missing Reference", "Please enter a known reference standard value.")
            self.edit_reference.setFocus()
            return

        try:
            ref_val = float(ref_text)
        except ValueError:
            QMessageBox.warning(self, "Invalid Reference", "Reference value must be a valid number.")
            self.edit_reference.setFocus()
            return

        tol_val = None
        lsl_val = None
        usl_val = None

        if self.radio_tol.isChecked():
            tol_text = self.edit_tol.text().strip()
            if not tol_text:
                QMessageBox.warning(self, "Missing Tolerance", "Please enter the tolerance value (USL - LSL).")
                self.edit_tol.setFocus()
                return
            try:
                tol_val = float(tol_text)
                if tol_val <= 0:
                    raise ValueError("Tolerance must be a positive number.")
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid Tolerance", str(exc))
                self.edit_tol.setFocus()
                return
            tol_type = "tolerance"
        elif self.radio_lsl.isChecked():
            lsl_text = self.edit_lsl.text().strip()
            if not lsl_text:
                QMessageBox.warning(self, "Missing LSL", "Please enter the Lower Specification Limit (LSL).")
                self.edit_lsl.setFocus()
                return
            try:
                lsl_val = float(lsl_text)
                if ref_val <= lsl_val:
                    raise ValueError("Reference value must be strictly greater than LSL.")
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid LSL", str(exc))
                self.edit_lsl.setFocus()
                return
            tol_type = "lower"
        else:
            usl_text = self.edit_usl.text().strip()
            if not usl_text:
                QMessageBox.warning(self, "Missing USL", "Please enter the Upper Specification Limit (USL).")
                self.edit_usl.setFocus()
                return
            try:
                usl_val = float(usl_text)
                if ref_val >= usl_val:
                    raise ValueError("Reference value must be strictly less than USL.")
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid USL", str(exc))
                self.edit_usl.setFocus()
                return
            tol_type = "upper"

        # Bundle settings
        full_settings = copy.deepcopy(self.options)
        full_settings["tolerance_type"] = tol_type
        full_settings["tolerance_val"] = tol_val
        full_settings["lsl"] = lsl_val
        full_settings["usl"] = usl_val
        full_settings["gage_info"] = copy.deepcopy(self.gage_info)

        col_name = self.worksheet.columns[meas_idx].name or f"C{meas_idx+1}"

        self.result_params = {
            "measurement_index": meas_idx,
            "measurement_name": col_name,
            "reference": ref_val,
            "settings": full_settings,
        }
        self.accept()
