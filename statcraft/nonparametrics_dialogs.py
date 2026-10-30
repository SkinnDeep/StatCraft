"""Qt Dialogs for Nonparametric Statistical Tests with native StatCraft PE fidelity.

Covers:
- SignTestDialog
- OneSampleWilcoxonDialog
- MannWhitneyDialog
- KruskalWallisDialog
- MoodsMedianDialog
- FriedmanDialog
- RunsTestDialog
- PairedWilcoxonDialog
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
    QDoubleSpinBox,
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


class _NonparametricBaseDialog(QDialog):
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

    def _on_select_clicked(self) -> None:
        cur = self.col_list.currentItem()
        if cur is not None:
            self._on_col_double_clicked(cur)


class SignTestDialog(_NonparametricBaseDialog):
    """1-Sample Sign Test Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "1-Sample Sign Test", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.edit_vars = QLineEdit()
        self.last_active_edit = self.edit_vars
        form.addRow("&Variables:", self.edit_vars)

        self.spin_test_med = QDoubleSpinBox()
        self.spin_test_med.setRange(-1e9, 1e9)
        self.spin_test_med.setDecimals(4)
        self.spin_test_med.setValue(0.0)
        form.addRow("&Test median:", self.spin_test_med)

        self.combo_alt = QComboBox()
        self.combo_alt.addItems(["not equal", "less than", "greater than"])
        form.addRow("&Alternative:", self.combo_alt)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.9)
        self.spin_conf.setValue(95.0)
        form.addRow("&Confidence level:", self.spin_conf)

        right_layout.addLayout(form)
        right_layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        right_layout.addWidget(btns)

        main_layout.addLayout(right_layout, stretch=2)

    def _on_accept(self) -> None:
        txt = self.edit_vars.text().strip()
        if not txt:
            QMessageBox.warning(self, "Invalid Input", "Please select at least one numeric variable.")
            return
        try:
            indices = resolve_variables(txt, self.worksheet, kinds=("number",))
            if not indices:
                raise ValueError("No numeric columns resolved.")
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return
        self.settings = self.get_settings()
        self.accept()

    def get_settings(self) -> Dict[str, Any]:
        indices = resolve_variables(self.edit_vars.text().strip(), self.worksheet, kinds=("number",))
        alt_map = {"not equal": "two_sided", "less than": "less", "greater than": "greater"}
        return {
            "variable_indices": indices,
            "test_median": float(self.spin_test_med.value()),
            "alternative": alt_map[self.combo_alt.currentText()],
            "conf_level": float(self.spin_conf.value()) / 100.0,
        }


class OneSampleWilcoxonDialog(_NonparametricBaseDialog):
    """1-Sample Wilcoxon Signed Rank Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "1-Sample Wilcoxon", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.edit_vars = QLineEdit()
        self.last_active_edit = self.edit_vars
        form.addRow("&Variables:", self.edit_vars)

        self.spin_test_med = QDoubleSpinBox()
        self.spin_test_med.setRange(-1e9, 1e9)
        self.spin_test_med.setDecimals(4)
        self.spin_test_med.setValue(0.0)
        form.addRow("&Test median:", self.spin_test_med)

        self.combo_alt = QComboBox()
        self.combo_alt.addItems(["not equal", "less than", "greater than"])
        form.addRow("&Alternative:", self.combo_alt)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.9)
        self.spin_conf.setValue(95.0)
        form.addRow("&Confidence level:", self.spin_conf)

        right_layout.addLayout(form)
        right_layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        right_layout.addWidget(btns)

        main_layout.addLayout(right_layout, stretch=2)

    def _on_accept(self) -> None:
        txt = self.edit_vars.text().strip()
        if not txt:
            QMessageBox.warning(self, "Invalid Input", "Please select at least one numeric variable.")
            return
        try:
            indices = resolve_variables(txt, self.worksheet, kinds=("number",))
            if not indices:
                raise ValueError("No numeric columns resolved.")
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return
        self.settings = self.get_settings()
        self.accept()

    def get_settings(self) -> Dict[str, Any]:
        indices = resolve_variables(self.edit_vars.text().strip(), self.worksheet, kinds=("number",))
        alt_map = {"not equal": "two_sided", "less than": "less", "greater than": "greater"}
        return {
            "variable_indices": indices,
            "test_median": float(self.spin_test_med.value()),
            "alternative": alt_map[self.combo_alt.currentText()],
            "conf_level": float(self.spin_conf.value()) / 100.0,
        }


class MannWhitneyDialog(_NonparametricBaseDialog):
    """Mann-Whitney Two-Sample Test Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Mann-Whitney", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.edit_sample1 = QLineEdit()
        self.edit_sample1.installEventFilter(self)
        self.last_active_edit = self.edit_sample1
        form.addRow("&First sample:", self.edit_sample1)

        self.edit_sample2 = QLineEdit()
        self.edit_sample2.installEventFilter(self)
        form.addRow("&Second sample:", self.edit_sample2)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.9)
        self.spin_conf.setValue(95.0)
        form.addRow("&Confidence level:", self.spin_conf)

        self.combo_alt = QComboBox()
        self.combo_alt.addItems(["not equal", "less than", "greater than"])
        form.addRow("&Alternative:", self.combo_alt)

        self.spin_test_diff = QDoubleSpinBox()
        self.spin_test_diff.setRange(-1e9, 1e9)
        self.spin_test_diff.setDecimals(4)
        self.spin_test_diff.setValue(0.0)
        form.addRow("&Test difference:", self.spin_test_diff)

        right_layout.addLayout(form)
        right_layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        right_layout.addWidget(btns)

        main_layout.addLayout(right_layout, stretch=2)

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn and isinstance(obj, QLineEdit):
            self.last_active_edit = obj
        return super().eventFilter(obj, event)

    def _on_accept(self) -> None:
        s1 = self.edit_sample1.text().strip()
        s2 = self.edit_sample2.text().strip()
        if not s1 or not s2:
            QMessageBox.warning(self, "Invalid Input", "Please select both first and second sample columns.")
            return
        try:
            idx1 = resolve_variables(s1, self.worksheet, kinds=("number",))
            idx2 = resolve_variables(s2, self.worksheet, kinds=("number",))
            if not idx1 or not idx2:
                raise ValueError("Both samples must be valid numeric columns.")
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return
        self.settings = self.get_settings()
        self.accept()

    def get_settings(self) -> Dict[str, Any]:
        idx1 = resolve_variables(self.edit_sample1.text().strip(), self.worksheet, kinds=("number",))[0]
        idx2 = resolve_variables(self.edit_sample2.text().strip(), self.worksheet, kinds=("number",))[0]
        alt_map = {"not equal": "two_sided", "less than": "less", "greater than": "greater"}
        return {
            "first_index": idx1,
            "second_index": idx2,
            "test_diff": float(self.spin_test_diff.value()),
            "alternative": alt_map[self.combo_alt.currentText()],
            "conf_level": float(self.spin_conf.value()) / 100.0,
        }


class KruskalWallisDialog(_NonparametricBaseDialog):
    """Kruskal-Wallis Multi-Group Test Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Kruskal-Wallis", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.edit_response = QLineEdit()
        self.edit_response.installEventFilter(self)
        self.last_active_edit = self.edit_response
        form.addRow("&Response:", self.edit_response)

        self.edit_factor = QLineEdit()
        self.edit_factor.installEventFilter(self)
        form.addRow("&Factor:", self.edit_factor)

        right_layout.addLayout(form)
        right_layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        right_layout.addWidget(btns)

        main_layout.addLayout(right_layout, stretch=2)

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn and isinstance(obj, QLineEdit):
            self.last_active_edit = obj
        return super().eventFilter(obj, event)

    def _on_accept(self) -> None:
        r_txt = self.edit_response.text().strip()
        f_txt = self.edit_factor.text().strip()
        if not r_txt or not f_txt:
            QMessageBox.warning(self, "Invalid Input", "Please select both Response and Factor columns.")
            return
        try:
            r_idx = resolve_variables(r_txt, self.worksheet, kinds=("number",))
            f_idx = resolve_variables(f_txt, self.worksheet, kinds=("number", "text"))
            if not r_idx or not f_idx:
                raise ValueError("Invalid Response or Factor column.")
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return
        self.settings = self.get_settings()
        self.accept()

    def get_settings(self) -> Dict[str, Any]:
        r_idx = resolve_variables(self.edit_response.text().strip(), self.worksheet, kinds=("number",))[0]
        f_idx = resolve_variables(self.edit_factor.text().strip(), self.worksheet, kinds=("number", "text"))[0]
        return {
            "response_index": r_idx,
            "factor_index": f_idx,
        }


class MoodsMedianDialog(_NonparametricBaseDialog):
    """Mood's Median Test Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Mood's Median Test", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.edit_response = QLineEdit()
        self.edit_response.installEventFilter(self)
        self.last_active_edit = self.edit_response
        form.addRow("&Response:", self.edit_response)

        self.edit_factor = QLineEdit()
        self.edit_factor.installEventFilter(self)
        form.addRow("&Factor:", self.edit_factor)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.9)
        self.spin_conf.setValue(95.0)
        form.addRow("&Confidence level:", self.spin_conf)

        right_layout.addLayout(form)
        right_layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        right_layout.addWidget(btns)

        main_layout.addLayout(right_layout, stretch=2)

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn and isinstance(obj, QLineEdit):
            self.last_active_edit = obj
        return super().eventFilter(obj, event)

    def _on_accept(self) -> None:
        r_txt = self.edit_response.text().strip()
        f_txt = self.edit_factor.text().strip()
        if not r_txt or not f_txt:
            QMessageBox.warning(self, "Invalid Input", "Please select both Response and Factor columns.")
            return
        try:
            r_idx = resolve_variables(r_txt, self.worksheet, kinds=("number",))
            f_idx = resolve_variables(f_txt, self.worksheet, kinds=("number", "text"))
            if not r_idx or not f_idx:
                raise ValueError("Invalid Response or Factor column.")
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return
        self.settings = self.get_settings()
        self.accept()

    def get_settings(self) -> Dict[str, Any]:
        r_idx = resolve_variables(self.edit_response.text().strip(), self.worksheet, kinds=("number",))[0]
        f_idx = resolve_variables(self.edit_factor.text().strip(), self.worksheet, kinds=("number", "text"))[0]
        return {
            "response_index": r_idx,
            "factor_index": f_idx,
            "conf_level": float(self.spin_conf.value()) / 100.0,
        }


class FriedmanDialog(_NonparametricBaseDialog):
    """Friedman Test Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Friedman Test", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.edit_response = QLineEdit()
        self.edit_response.installEventFilter(self)
        self.last_active_edit = self.edit_response
        form.addRow("&Response:", self.edit_response)

        self.edit_treatment = QLineEdit()
        self.edit_treatment.installEventFilter(self)
        form.addRow("&Treatment:", self.edit_treatment)

        self.edit_blocks = QLineEdit()
        self.edit_blocks.installEventFilter(self)
        form.addRow("&Blocks:", self.edit_blocks)

        right_layout.addLayout(form)
        right_layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        right_layout.addWidget(btns)

        main_layout.addLayout(right_layout, stretch=2)

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn and isinstance(obj, QLineEdit):
            self.last_active_edit = obj
        return super().eventFilter(obj, event)

    def _on_accept(self) -> None:
        r_txt = self.edit_response.text().strip()
        t_txt = self.edit_treatment.text().strip()
        b_txt = self.edit_blocks.text().strip()
        if not r_txt or not t_txt or not b_txt:
            QMessageBox.warning(self, "Invalid Input", "Please select Response, Treatment, and Blocks columns.")
            return
        try:
            r_idx = resolve_variables(r_txt, self.worksheet, kinds=("number",))
            t_idx = resolve_variables(t_txt, self.worksheet, kinds=("number", "text"))
            b_idx = resolve_variables(b_txt, self.worksheet, kinds=("number", "text"))
            if not r_idx or not t_idx or not b_idx:
                raise ValueError("Invalid column selection.")
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return
        self.settings = self.get_settings()
        self.accept()

    def get_settings(self) -> Dict[str, Any]:
        r_idx = resolve_variables(self.edit_response.text().strip(), self.worksheet, kinds=("number",))[0]
        t_idx = resolve_variables(self.edit_treatment.text().strip(), self.worksheet, kinds=("number", "text"))[0]
        b_idx = resolve_variables(self.edit_blocks.text().strip(), self.worksheet, kinds=("number", "text"))[0]
        return {
            "response_index": r_idx,
            "treatment_index": t_idx,
            "block_index": b_idx,
        }


class RunsTestDialog(_NonparametricBaseDialog):
    """Runs Test for Randomness Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Runs Test", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.edit_vars = QLineEdit()
        self.last_active_edit = self.edit_vars
        form.addRow("&Variables:", self.edit_vars)

        grp_base = QGroupBox("Baseline (K)")
        lay_base = QVBoxLayout(grp_base)
        self.rb_mean = QRadioButton("&Mean of data")
        self.rb_mean.setChecked(True)
        self.rb_custom = QRadioButton("&Specified value:")
        self.spin_custom = QDoubleSpinBox()
        self.spin_custom.setRange(-1e9, 1e9)
        self.spin_custom.setDecimals(4)
        self.spin_custom.setValue(0.0)
        self.spin_custom.setEnabled(False)
        self.rb_custom.toggled.connect(self.spin_custom.setEnabled)

        lay_base.addWidget(self.rb_mean)
        h_lay = QHBoxLayout()
        h_lay.addWidget(self.rb_custom)
        h_lay.addWidget(self.spin_custom)
        lay_base.addLayout(h_lay)

        right_layout.addLayout(form)
        right_layout.addWidget(grp_base)
        right_layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        right_layout.addWidget(btns)

        main_layout.addLayout(right_layout, stretch=2)

    def _on_accept(self) -> None:
        txt = self.edit_vars.text().strip()
        if not txt:
            QMessageBox.warning(self, "Invalid Input", "Please select at least one numeric variable.")
            return
        try:
            indices = resolve_variables(txt, self.worksheet, kinds=("number",))
            if not indices:
                raise ValueError("No numeric columns resolved.")
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return
        self.settings = self.get_settings()
        self.accept()

    def get_settings(self) -> Dict[str, Any]:
        indices = resolve_variables(self.edit_vars.text().strip(), self.worksheet, kinds=("number",))
        baseline = "mean" if self.rb_mean.isChecked() else "custom"
        custom_val = float(self.spin_custom.value()) if baseline == "custom" else None
        return {
            "variable_indices": indices,
            "baseline": baseline,
            "custom_baseline": custom_val,
        }


class PairedWilcoxonDialog(_NonparametricBaseDialog):
    """Paired Wilcoxon Signed Rank Dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Paired Wilcoxon", parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.addWidget(self._create_column_picker(), stretch=1)

        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.edit_sample1 = QLineEdit()
        self.edit_sample1.installEventFilter(self)
        self.last_active_edit = self.edit_sample1
        form.addRow("&First sample:", self.edit_sample1)

        self.edit_sample2 = QLineEdit()
        self.edit_sample2.installEventFilter(self)
        form.addRow("&Second sample:", self.edit_sample2)

        self.spin_test_diff = QDoubleSpinBox()
        self.spin_test_diff.setRange(-1e9, 1e9)
        self.spin_test_diff.setDecimals(4)
        self.spin_test_diff.setValue(0.0)
        form.addRow("&Test difference:", self.spin_test_diff)

        self.combo_alt = QComboBox()
        self.combo_alt.addItems(["not equal", "less than", "greater than"])
        form.addRow("&Alternative:", self.combo_alt)

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.9)
        self.spin_conf.setValue(95.0)
        form.addRow("&Confidence level:", self.spin_conf)

        right_layout.addLayout(form)
        right_layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        right_layout.addWidget(btns)

        main_layout.addLayout(right_layout, stretch=2)

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn and isinstance(obj, QLineEdit):
            self.last_active_edit = obj
        return super().eventFilter(obj, event)

    def _on_accept(self) -> None:
        s1 = self.edit_sample1.text().strip()
        s2 = self.edit_sample2.text().strip()
        if not s1 or not s2:
            QMessageBox.warning(self, "Invalid Input", "Please select both first and second sample columns.")
            return
        try:
            idx1 = resolve_variables(s1, self.worksheet, kinds=("number",))
            idx2 = resolve_variables(s2, self.worksheet, kinds=("number",))
            if not idx1 or not idx2:
                raise ValueError("Both samples must be valid numeric columns.")
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return
        self.settings = self.get_settings()
        self.accept()

    def get_settings(self) -> Dict[str, Any]:
        idx1 = resolve_variables(self.edit_sample1.text().strip(), self.worksheet, kinds=("number",))[0]
        idx2 = resolve_variables(self.edit_sample2.text().strip(), self.worksheet, kinds=("number",))[0]
        alt_map = {"not equal": "two_sided", "less than": "less", "greater than": "greater"}
        return {
            "first_index": idx1,
            "second_index": idx2,
            "test_diff": float(self.spin_test_diff.value()),
            "alternative": alt_map[self.combo_alt.currentText()],
            "conf_level": float(self.spin_conf.value()) / 100.0,
        }
