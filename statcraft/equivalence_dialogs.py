"""Qt Dialogs for Equivalence Tests with native StatCraft fidelity.

Covers:
- OneSampleEquivalenceDialog
- TwoSampleEquivalenceDialog
- PairedEquivalenceDialog
- CrossoverEquivalenceDialog
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .model import Worksheet


class _EquivalenceBaseDialog(QDialog):
    """Base dialog providing column selector and variable binding."""

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

        self.col_list.itemDoubleClicked.connect(self._on_column_double_clicked)
        layout.addWidget(self.col_list)

        btn_select = QPushButton("Select >>")
        btn_select.clicked.connect(self._on_select_clicked)
        layout.addWidget(btn_select)
        return container

    def _on_column_double_clicked(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.ItemDataRole.UserRole)
        col = self.worksheet.columns[idx]
        name = col.name if col.name else f"C{idx + 1}"
        if self.last_active_edit:
            self.last_active_edit.setText(f"'{name}'")

    def _on_select_clicked(self) -> None:
        item = self.col_list.currentItem()
        if item:
            self._on_column_double_clicked(item)

    def _register_edit(self, edit: QLineEdit) -> None:
        edit.installEventFilter(self)
        if self.last_active_edit is None:
            self.last_active_edit = edit

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn and isinstance(obj, QLineEdit):
            self.last_active_edit = obj
        return super().eventFilter(obj, event)

    def _parse_single_column_index(self, text: str) -> Optional[int]:
        cleaned = text.strip().strip("'\"")
        if not cleaned:
            return None
        for idx, col in enumerate(self.worksheet.columns):
            name = col.name if col.name else f"C{idx + 1}"
            if name.lower() == cleaned.lower() or f"c{idx + 1}" == cleaned.lower():
                return idx
        if cleaned.upper().startswith("C") and cleaned[1:].isdigit():
            idx = int(cleaned[1:]) - 1
            if 0 <= idx < len(self.worksheet.columns):
                return idx
        return None


# ==============================================================================
# 1. 1-SAMPLE EQUIVALENCE DIALOG
# ==============================================================================

class OneSampleEquivalenceDialog(_EquivalenceBaseDialog):
    """Dialog for 1-Sample Equivalence Test."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "1-Sample Equivalence Test", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        form = QFormLayout()
        self.edit_sample = QLineEdit()
        self._register_edit(self.edit_sample)
        form.addRow("Sample:", self.edit_sample)

        self.spin_target = QDoubleSpinBox()
        self.spin_target.setRange(-1e6, 1e6)
        self.spin_target.setDecimals(4)
        self.spin_target.setValue(0.0)
        form.addRow("Target:", self.spin_target)

        self.spin_lower = QDoubleSpinBox()
        self.spin_lower.setRange(-1e6, 1e6)
        self.spin_lower.setDecimals(4)
        self.spin_lower.setValue(-1.0)
        form.addRow("Lower Equivalence Limit:", self.spin_lower)

        self.spin_upper = QDoubleSpinBox()
        self.spin_upper.setRange(-1e6, 1e6)
        self.spin_upper.setDecimals(4)
        self.spin_upper.setValue(1.0)
        form.addRow("Upper Equivalence Limit:", self.spin_upper)

        self.combo_type = QComboBox()
        self.combo_type.addItems(["Difference", "Ratio"])
        form.addRow("Hypothesis Type:", self.combo_type)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.001, 0.499)
        self.spin_alpha.setDecimals(3)
        self.spin_alpha.setValue(0.05)
        form.addRow("Significance Level (Alpha):", self.spin_alpha)

        right_layout.addLayout(form)
        right_layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)

        main_layout.addWidget(right_container)

    def _validate_and_accept(self) -> None:
        idx = self._parse_single_column_index(self.edit_sample.text())
        if idx is None:
            QMessageBox.warning(self, "Invalid Input", "Please select a valid sample column.")
            return

        lo = self.spin_lower.value()
        up = self.spin_upper.value()
        if lo >= up:
            QMessageBox.warning(self, "Invalid Input", "Lower limit must be less than Upper limit.")
            return

        self.settings = {
            "sample_index": idx,
            "target": self.spin_target.value(),
            "lower_margin": lo,
            "upper_margin": up,
            "hypothesis_type": self.combo_type.currentText().lower(),
            "alpha": self.spin_alpha.value(),
        }
        self.accept()


# ==============================================================================
# 2. 2-SAMPLE EQUIVALENCE DIALOG
# ==============================================================================

class TwoSampleEquivalenceDialog(_EquivalenceBaseDialog):
    """Dialog for 2-Sample Equivalence Test."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "2-Sample Equivalence Test", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        form = QFormLayout()
        self.edit_test = QLineEdit()
        self._register_edit(self.edit_test)
        form.addRow("Sample 1 (Test):", self.edit_test)

        self.edit_ref = QLineEdit()
        self._register_edit(self.edit_ref)
        form.addRow("Sample 2 (Reference):", self.edit_ref)

        self.spin_lower = QDoubleSpinBox()
        self.spin_lower.setRange(-1e6, 1e6)
        self.spin_lower.setDecimals(4)
        self.spin_lower.setValue(-1.0)
        form.addRow("Lower Equivalence Limit:", self.spin_lower)

        self.spin_upper = QDoubleSpinBox()
        self.spin_upper.setRange(-1e6, 1e6)
        self.spin_upper.setDecimals(4)
        self.spin_upper.setValue(1.0)
        form.addRow("Upper Equivalence Limit:", self.spin_upper)

        self.combo_type = QComboBox()
        self.combo_type.addItems(["Difference", "Ratio"])
        form.addRow("Hypothesis Type:", self.combo_type)

        self.chk_equal_var = QCheckBox("Assume equal variances")
        form.addRow("", self.chk_equal_var)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.001, 0.499)
        self.spin_alpha.setDecimals(3)
        self.spin_alpha.setValue(0.05)
        form.addRow("Significance Level (Alpha):", self.spin_alpha)

        right_layout.addLayout(form)
        right_layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)

        main_layout.addWidget(right_container)

    def _validate_and_accept(self) -> None:
        idx1 = self._parse_single_column_index(self.edit_test.text())
        idx2 = self._parse_single_column_index(self.edit_ref.text())
        if idx1 is None or idx2 is None:
            QMessageBox.warning(self, "Invalid Input", "Please select valid columns for both samples.")
            return
        if idx1 == idx2:
            QMessageBox.warning(self, "Invalid Input", "Sample 1 and Sample 2 must be different columns.")
            return

        lo = self.spin_lower.value()
        up = self.spin_upper.value()
        if lo >= up:
            QMessageBox.warning(self, "Invalid Input", "Lower limit must be less than Upper limit.")
            return

        self.settings = {
            "first_index": idx1,
            "second_index": idx2,
            "lower_margin": lo,
            "upper_margin": up,
            "equal_variances": self.chk_equal_var.isChecked(),
            "hypothesis_type": self.combo_type.currentText().lower(),
            "alpha": self.spin_alpha.value(),
        }
        self.accept()


# ==============================================================================
# 3. PAIRED EQUIVALENCE DIALOG
# ==============================================================================

class PairedEquivalenceDialog(_EquivalenceBaseDialog):
    """Dialog for Paired Equivalence Test."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Paired Equivalence Test", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        form = QFormLayout()
        self.edit_sample1 = QLineEdit()
        self._register_edit(self.edit_sample1)
        form.addRow("Sample 1:", self.edit_sample1)

        self.edit_sample2 = QLineEdit()
        self._register_edit(self.edit_sample2)
        form.addRow("Sample 2:", self.edit_sample2)

        self.spin_lower = QDoubleSpinBox()
        self.spin_lower.setRange(-1e6, 1e6)
        self.spin_lower.setDecimals(4)
        self.spin_lower.setValue(-1.0)
        form.addRow("Lower Equivalence Limit:", self.spin_lower)

        self.spin_upper = QDoubleSpinBox()
        self.spin_upper.setRange(-1e6, 1e6)
        self.spin_upper.setDecimals(4)
        self.spin_upper.setValue(1.0)
        form.addRow("Upper Equivalence Limit:", self.spin_upper)

        self.combo_type = QComboBox()
        self.combo_type.addItems(["Difference", "Ratio"])
        form.addRow("Hypothesis Type:", self.combo_type)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.001, 0.499)
        self.spin_alpha.setDecimals(3)
        self.spin_alpha.setValue(0.05)
        form.addRow("Significance Level (Alpha):", self.spin_alpha)

        right_layout.addLayout(form)
        right_layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)

        main_layout.addWidget(right_container)

    def _validate_and_accept(self) -> None:
        idx1 = self._parse_single_column_index(self.edit_sample1.text())
        idx2 = self._parse_single_column_index(self.edit_sample2.text())
        if idx1 is None or idx2 is None:
            QMessageBox.warning(self, "Invalid Input", "Please select valid columns for both samples.")
            return

        lo = self.spin_lower.value()
        up = self.spin_upper.value()
        if lo >= up:
            QMessageBox.warning(self, "Invalid Input", "Lower limit must be less than Upper limit.")
            return

        self.settings = {
            "first_index": idx1,
            "second_index": idx2,
            "lower_margin": lo,
            "upper_margin": up,
            "hypothesis_type": self.combo_type.currentText().lower(),
            "alpha": self.spin_alpha.value(),
        }
        self.accept()


# ==============================================================================
# 4. 2x2 CROSSOVER EQUIVALENCE DIALOG
# ==============================================================================

class CrossoverEquivalenceDialog(_EquivalenceBaseDialog):
    """Dialog for 2x2 Crossover Design Equivalence Test."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "2x2 Crossover Equivalence Test", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        form = QFormLayout()
        self.edit_resp = QLineEdit()
        self._register_edit(self.edit_resp)
        form.addRow("Response:", self.edit_resp)

        self.edit_seq = QLineEdit()
        self._register_edit(self.edit_seq)
        form.addRow("Sequence:", self.edit_seq)

        self.edit_per = QLineEdit()
        self._register_edit(self.edit_per)
        form.addRow("Period:", self.edit_per)

        self.edit_sub = QLineEdit()
        self._register_edit(self.edit_sub)
        form.addRow("Subject:", self.edit_sub)

        self.edit_trt = QLineEdit()
        self._register_edit(self.edit_trt)
        form.addRow("Treatment:", self.edit_trt)

        self.spin_lower = QDoubleSpinBox()
        self.spin_lower.setRange(-1e6, 1e6)
        self.spin_lower.setDecimals(4)
        self.spin_lower.setValue(-1.0)
        form.addRow("Lower Equivalence Limit:", self.spin_lower)

        self.spin_upper = QDoubleSpinBox()
        self.spin_upper.setRange(-1e6, 1e6)
        self.spin_upper.setDecimals(4)
        self.spin_upper.setValue(1.0)
        form.addRow("Upper Equivalence Limit:", self.spin_upper)

        self.combo_type = QComboBox()
        self.combo_type.addItems(["Difference", "Ratio"])
        form.addRow("Hypothesis Type:", self.combo_type)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.001, 0.499)
        self.spin_alpha.setDecimals(3)
        self.spin_alpha.setValue(0.05)
        form.addRow("Significance Level (Alpha):", self.spin_alpha)

        right_layout.addLayout(form)
        right_layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)

        main_layout.addWidget(right_container)

    def _validate_and_accept(self) -> None:
        ri = self._parse_single_column_index(self.edit_resp.text())
        si = self._parse_single_column_index(self.edit_seq.text())
        pi = self._parse_single_column_index(self.edit_per.text())
        sub_i = self._parse_single_column_index(self.edit_sub.text())
        ti = self._parse_single_column_index(self.edit_trt.text())

        if any(idx is None for idx in (ri, si, pi, sub_i, ti)):
            QMessageBox.warning(self, "Invalid Input", "Please select valid columns for all crossover variables.")
            return

        lo = self.spin_lower.value()
        up = self.spin_upper.value()
        if lo >= up:
            QMessageBox.warning(self, "Invalid Input", "Lower limit must be less than Upper limit.")
            return

        self.settings = {
            "response_index": ri,
            "sequence_index": si,
            "period_index": pi,
            "subject_index": sub_i,
            "treatment_index": ti,
            "lower_margin": lo,
            "upper_margin": up,
            "hypothesis_type": self.combo_type.currentText().lower(),
            "alpha": self.spin_alpha.value(),
        }
        self.accept()
