"""Qt Dialogs for Attribute Gage Study (Analytic Method) matching Minitab standard."""
from __future__ import annotations

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


class AttributeGageInfoDialog(QDialog):
    """Sub-dialog for entering metadata about the gage under test."""

    def __init__(self, current_info: Optional[Dict[str, str]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Attribute Gage Study: Gage Info")
        self.setMinimumSize(380, 240)
        self.resize(380, 240)
        self.setSizeGripEnabled(True)

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
        layout.addStretch()

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


class AttributeGageOptionsDialog(QDialog):
    """Sub-dialog for Attribute Gage Study calculation and plot options."""

    def __init__(self, current_options: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Attribute Gage Study: Options")
        self.setMinimumSize(420, 280)
        self.resize(420, 280)
        self.setSizeGripEnabled(True)

        opts = current_options or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.edit_multiplier = QLineEdit(str(opts.get("study_multiplier", 5.15)))
        form.addRow("&Study variation multiplier (5.15 or 6.0):", self.edit_multiplier)

        self.edit_alpha = QLineEdit(str(opts.get("alpha", 0.05)))
        form.addRow("&Alpha level for bias test (e.g. 0.05):", self.edit_alpha)

        self.edit_target = QLineEdit(str(opts.get("target")) if opts.get("target") is not None else "")
        form.addRow("&Target reference value (optional):", self.edit_target)

        self.edit_tolerance = QLineEdit(str(opts.get("tolerance")) if opts.get("tolerance") is not None else "")
        form.addRow("T&olerance (USL - LSL, optional):", self.edit_tolerance)

        self.edit_title = QLineEdit(opts.get("title", ""))
        form.addRow("&Title:", self.edit_title)

        layout.addLayout(form)
        layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate_and_accept(self):
        try:
            m = float(self.edit_multiplier.text().strip())
            if m <= 0:
                raise ValueError("Study variation multiplier must be positive.")
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Option", str(exc))
            return

        try:
            a = float(self.edit_alpha.text().strip())
            if a <= 0 or a >= 1:
                raise ValueError("Alpha level must be between 0 and 1.")
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Option", str(exc))
            return

        tgt_txt = self.edit_target.text().strip()
        if tgt_txt:
            try:
                float(tgt_txt)
            except ValueError:
                QMessageBox.warning(self, "Invalid Option", "Target must be a valid numeric value.")
                return

        tol_txt = self.edit_tolerance.text().strip()
        if tol_txt:
            try:
                tol_val = float(tol_txt)
                if tol_val <= 0:
                    raise ValueError("Tolerance must be a positive number.")
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid Option", str(exc))
                return

        self.accept()

    def get_options(self) -> Dict[str, Any]:
        tgt_txt = self.edit_target.text().strip()
        tol_txt = self.edit_tolerance.text().strip()
        return {
            "study_multiplier": float(self.edit_multiplier.text().strip()),
            "alpha": float(self.edit_alpha.text().strip()),
            "target": float(tgt_txt) if tgt_txt else None,
            "tolerance": float(tol_txt) if tol_txt else None,
            "title": self.edit_title.text().strip(),
        }


class AttributeGageDialog(QDialog):
    """Main Attribute Gage Study (Analytic Method) dialog matching Minitab standard."""

    def __init__(
        self,
        worksheet: Worksheet,
        initial_vars: Optional[List[str]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Attribute Gage Study (Analytic Method)")
        self.setMinimumSize(580, 420)
        self.resize(580, 420)
        self.setSizeGripEnabled(True)
        self.last_active_edit: Optional[QLineEdit] = None

        self.gage_info: Dict[str, str] = {
            "gage_name": "",
            "date_of_study": "",
            "reported_by": "",
            "misc": ""
        }
        self.options: Dict[str, Any] = {
            "study_multiplier": 5.15,
            "alpha": 0.05,
            "target": None,
            "tolerance": None,
            "title": ""
        }
        self.result_params: Optional[Dict[str, Any]] = None

        self._setup_ui(initial_vars or [])

    def _setup_ui(self, initial_vars: List[str]):
        main_layout = QHBoxLayout(self)

        # Left Column: Column Picker List
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Columns:"))

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

        # Right Column: Inputs
        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.edit_part = QLineEdit()
        self.edit_part.setPlaceholderText("Optional (e.g. C1 or Part)")
        self.edit_part.installEventFilter(self)
        form.addRow("&Part numbers (optional):", self.edit_part)

        self.edit_ref = QLineEdit()
        self.edit_ref.setPlaceholderText("Column containing standard reference values")
        self.edit_ref.installEventFilter(self)
        form.addRow("&Reference values:", self.edit_ref)

        self.edit_trials = QLineEdit("20")
        self.edit_trials.setPlaceholderText("Number of trials (e.g. 20) or Column")
        self.edit_trials.installEventFilter(self)
        form.addRow("Number of &trials:", self.edit_trials)

        self.edit_acc = QLineEdit()
        self.edit_acc.setPlaceholderText("Column containing count of acceptances")
        self.edit_acc.installEventFilter(self)
        form.addRow("Number of &acceptances:", self.edit_acc)

        self.edit_target = QLineEdit()
        self.edit_target.setPlaceholderText("Reference standard / lower or upper limit")
        self.edit_target.installEventFilter(self)
        form.addRow("Target / &Limit value:", self.edit_target)

        self.edit_tolerance = QLineEdit()
        self.edit_tolerance.setPlaceholderText("Optional USL - LSL for %Repeatability")
        self.edit_tolerance.installEventFilter(self)
        form.addRow("T&olerance (optional):", self.edit_tolerance)

        right_layout.addLayout(form)
        right_layout.addStretch()

        # Sub-dialog buttons
        sub_btn_layout = QHBoxLayout()
        btn_info = QPushButton("Gage &Info...")
        btn_info.clicked.connect(self._on_gage_info)
        sub_btn_layout.addWidget(btn_info)

        btn_opts = QPushButton("&Options...")
        btn_opts.clicked.connect(self._on_options)
        sub_btn_layout.addWidget(btn_opts)
        right_layout.addLayout(sub_btn_layout)

        # Standard Dialog Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        right_layout.addWidget(btns)

        main_layout.addLayout(right_layout, 2)

        # Pre-populate initial vars if provided
        if initial_vars:
            if len(initial_vars) >= 1:
                self.edit_ref.setText(initial_vars[0])
            if len(initial_vars) >= 2:
                self.edit_acc.setText(initial_vars[1])

        self.last_active_edit = self.edit_ref

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn and isinstance(obj, QLineEdit):
            self.last_active_edit = obj
        return super().eventFilter(obj, event)

    def _on_select_clicked(self):
        item = self.col_list.currentItem()
        if not item or not self.last_active_edit:
            return
        col_name = item.data(Qt.ItemDataRole.UserRole)
        self.last_active_edit.setText(col_name)

    def _on_gage_info(self):
        dlg = AttributeGageInfoDialog(self.gage_info, self)
        if dlg.exec():
            self.gage_info = dlg.get_info()

    def _on_options(self):
        curr = dict(self.options)
        if self.edit_target.text().strip():
            try:
                curr["target"] = float(self.edit_target.text().strip())
            except ValueError:
                pass
        if self.edit_tolerance.text().strip():
            try:
                curr["tolerance"] = float(self.edit_tolerance.text().strip())
            except ValueError:
                pass
        dlg = AttributeGageOptionsDialog(curr, self)
        if dlg.exec():
            self.options = dlg.get_options()
            if self.options.get("target") is not None:
                self.edit_target.setText(str(self.options["target"]))
            if self.options.get("tolerance") is not None:
                self.edit_tolerance.setText(str(self.options["tolerance"]))

    def _on_ok(self):
        ref_text = self.edit_ref.text().strip()
        acc_text = self.edit_acc.text().strip()
        trials_text = self.edit_trials.text().strip()
        part_text = self.edit_part.text().strip()

        if not ref_text:
            QMessageBox.warning(self, "Missing Variable", "Please specify a column for Reference values.")
            return
        if not acc_text:
            QMessageBox.warning(self, "Missing Variable", "Please specify a column for Number of acceptances.")
            return
        if not trials_text:
            QMessageBox.warning(self, "Missing Variable", "Please specify the Number of trials (a number or column).")
            return

        ref_cols = resolve_variables(ref_text, self.worksheet)
        if not ref_cols:
            QMessageBox.warning(self, "Invalid Variable", f"Could not find Reference values column: '{ref_text}'.")
            return

        acc_cols = resolve_variables(acc_text, self.worksheet)
        if not acc_cols:
            QMessageBox.warning(self, "Invalid Variable", f"Could not find Acceptances column: '{acc_text}'.")
            return

        # Determine if trials is a column or a constant integer
        trials_val: Any = None
        try:
            trials_val = int(trials_text)
            if trials_val <= 0:
                raise ValueError("Trials must be positive.")
        except ValueError:
            t_cols = resolve_variables(trials_text, self.worksheet)
            if not t_cols:
                QMessageBox.warning(self, "Invalid Variable", f"Could not resolve trials column or number: '{trials_text}'.")
                return
            trials_val = t_cols[0]

        part_col = None
        if part_text:
            p_cols = resolve_variables(part_text, self.worksheet, kinds=('number', 'text', 'date'))
            if p_cols:
                part_col = p_cols[0]

        target_val = None
        if self.edit_target.text().strip():
            try:
                target_val = float(self.edit_target.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Invalid Target", "Target reference value must be a valid number.")
                return

        tol_val = None
        if self.edit_tolerance.text().strip():
            try:
                tol_val = float(self.edit_tolerance.text().strip())
                if tol_val <= 0:
                    raise ValueError("Tolerance must be positive.")
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid Tolerance", str(exc))
                return

        opts = dict(self.options)
        opts["gage_info"] = self.gage_info
        if target_val is not None:
            opts["target"] = target_val
        if tol_val is not None:
            opts["tolerance"] = tol_val

        self.result_params = {
            "ref_column": ref_cols[0],
            "acc_column": acc_cols[0],
            "trials": trials_val,
            "part_column": part_col,
            "settings": opts,
        }
        self.accept()
