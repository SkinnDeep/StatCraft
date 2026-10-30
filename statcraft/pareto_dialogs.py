"""Qt Dialog for Pareto Chart with native StatCraft PE fidelity.

Form Evidence:
- 0372-AMPARETOCHART.MDF (MenuID 41210)
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Union
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
    QVBoxLayout,
    QWidget,
)

from .model import Worksheet
from .variable_dialogs import format_variable_reference, resolve_variables


class ParetoChartDialog(QDialog):
    """Main dialog for Pareto Chart matching 0372-AMPARETOCHART.MDF."""

    def __init__(
        self,
        worksheet: Worksheet,
        initial_vars: Optional[List[str]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Pareto Chart")
        self.resize(560, 440)
        self.last_active_edit: Optional[QLineEdit] = None
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

        # Right Column: Inputs & Options
        right_layout = QVBoxLayout()

        # Data arrangement dropdown
        lbl_arrange = QLabel("&How are your data arranged in the worksheet?")
        right_layout.addWidget(lbl_arrange)
        self.combo_arrange = QComboBox()
        self.combo_arrange.addItem("Each defect observation is in a separate row", 1)
        self.combo_arrange.addItem("Summarized values in a table", 0)
        self.combo_arrange.currentIndexChanged.connect(self._on_arrange_changed)
        lbl_arrange.setBuddy(self.combo_arrange)
        right_layout.addWidget(self.combo_arrange)

        # Container for Raw Observation Mode
        self.widget_raw = QWidget()
        layout_raw = QFormLayout(self.widget_raw)
        layout_raw.setContentsMargins(0, 5, 0, 5)

        self.edit_defects_raw = QLineEdit(" ".join(initial_vars))
        self.edit_defects_raw.textChanged.connect(lambda: setattr(self, "last_active_edit", self.edit_defects_raw))
        layout_raw.addRow("D&efects data column:", self.edit_defects_raw)

        self.edit_by_raw = QLineEdit()
        self.edit_by_raw.textChanged.connect(lambda: setattr(self, "last_active_edit", self.edit_by_raw))
        layout_raw.addRow("&By / X column (optional):", self.edit_by_raw)
        right_layout.addWidget(self.widget_raw)

        # Container for Summarized Mode
        self.widget_summ = QWidget()
        layout_summ = QFormLayout(self.widget_summ)
        layout_summ.setContentsMargins(0, 5, 0, 5)

        self.edit_labels_summ = QLineEdit(" ".join(initial_vars))
        self.edit_labels_summ.textChanged.connect(lambda: setattr(self, "last_active_edit", self.edit_labels_summ))
        layout_summ.addRow("&Defect names column:", self.edit_labels_summ)

        self.edit_counts_summ = QLineEdit()
        self.edit_counts_summ.textChanged.connect(lambda: setattr(self, "last_active_edit", self.edit_counts_summ))
        layout_summ.addRow("&Frequencies / Counts column:", self.edit_counts_summ)
        right_layout.addWidget(self.widget_summ)
        self.widget_summ.hide()

        # Options Box: Combining
        grp_combine = QGroupBox("Combining Options")
        layout_comb = QVBoxLayout(grp_combine)

        self.btn_group_comb = QButtonGroup(self)
        self.radio_combine_yes = QRadioButton("&Combine defects of this percent or less:")
        self.radio_combine_no = QRadioButton("Do not com&bine")
        self.radio_combine_yes.setChecked(True)
        self.btn_group_comb.addButton(self.radio_combine_yes, 0)
        self.btn_group_comb.addButton(self.radio_combine_no, 1)

        comb_row = QHBoxLayout()
        comb_row.addWidget(self.radio_combine_yes)
        self.edit_combine_pct = QLineEdit("95.0")
        self.edit_combine_pct.setMaximumWidth(70)
        comb_row.addWidget(self.edit_combine_pct)
        comb_row.addWidget(QLabel("%"))
        comb_row.addStretch()

        layout_comb.addLayout(comb_row)
        layout_comb.addWidget(self.radio_combine_no)
        self.radio_combine_yes.toggled.connect(lambda on: self.edit_combine_pct.setEnabled(on))

        right_layout.addWidget(grp_combine)

        # Cumulative Line Checkbox
        self.chk_cumulative = QCheckBox("Show c&umulative line")
        self.chk_cumulative.setChecked(True)
        right_layout.addWidget(self.chk_cumulative)

        right_layout.addStretch()

        # Dialog Buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        right_layout.addWidget(btn_box)

        main_layout.addLayout(right_layout, 2)
        self.last_active_edit = self.edit_defects_raw

    def _on_arrange_changed(self, idx: int) -> None:
        is_raw = (self.combo_arrange.currentData() == 1)
        self.widget_raw.setVisible(is_raw)
        self.widget_summ.setVisible(not is_raw)
        self.last_active_edit = self.edit_defects_raw if is_raw else self.edit_labels_summ

    def _on_select_clicked(self) -> None:
        items = self.col_list.selectedItems()
        if not items:
            return
        selected_names = [it.data(Qt.ItemDataRole.UserRole) for it in items]
        target = self.last_active_edit or self.edit_defects_raw
        curr = target.text().strip()
        new_text = (curr + " " + " ".join(selected_names)).strip()
        target.setText(new_text)

    def _on_accept(self) -> None:
        is_raw = (self.combo_arrange.currentData() == 1)
        if is_raw:
            defect_text = self.edit_defects_raw.text().strip()
            if not defect_text:
                QMessageBox.warning(self, "Missing Defect Column", "Please select a defect data column.")
                return
            try:
                indices = resolve_variables(defect_text, self.worksheet, kinds=('number', 'text'))
            except Exception:
                indices = []
            if not indices:
                QMessageBox.warning(self, "Invalid Selection", f"Defect column '{defect_text}' not found.")
                return
        else:
            names_text = self.edit_labels_summ.text().strip()
            counts_text = self.edit_counts_summ.text().strip()
            if not names_text or not counts_text:
                QMessageBox.warning(self, "Missing Columns", "Please specify both defect names and counts columns.")
                return
            try:
                n_indices = resolve_variables(names_text, self.worksheet, kinds=('number', 'text'))
                c_indices = resolve_variables(counts_text, self.worksheet, kinds=('number',))
            except Exception:
                n_indices, c_indices = [], []
            if not n_indices or not c_indices:
                QMessageBox.warning(self, "Invalid Selection", "Please check defect names and counts columns.")
                return

        # Check combine percent
        if self.radio_combine_yes.isChecked():
            try:
                cp = float(self.edit_combine_pct.text().strip())
                if cp <= 0 or cp > 100:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self, "Invalid Percent", "Combine percent must be between 0 and 100.")
                return

        self.accept()

    def get_configuration(self) -> Dict[str, Any]:
        is_raw = (self.combo_arrange.currentData() == 1)
        combine_pct = float(self.edit_combine_pct.text().strip()) if self.radio_combine_yes.isChecked() else None

        if is_raw:
            defect_text = self.edit_defects_raw.text().strip()
            try:
                indices = resolve_variables(defect_text, self.worksheet, kinds=('number', 'text'))
                defect_col = self.worksheet.columns[indices[0]].name
            except Exception:
                defect_col = defect_text

            by_text = self.edit_by_raw.text().strip()
            by_col = None
            if by_text:
                try:
                    b_indices = resolve_variables(by_text, self.worksheet, kinds=('number', 'text'))
                    by_col = self.worksheet.columns[b_indices[0]].name if b_indices else by_text
                except Exception:
                    by_col = by_text

            return {
                "is_summarized": False,
                "defect_column": defect_col,
                "by_column": by_col,
                "combine_percent": combine_pct,
                "show_cumulative": self.chk_cumulative.isChecked(),
            }
        else:
            names_text = self.edit_labels_summ.text().strip()
            counts_text = self.edit_counts_summ.text().strip()
            try:
                n_indices = resolve_variables(names_text, self.worksheet, kinds=('number', 'text'))
                c_indices = resolve_variables(counts_text, self.worksheet, kinds=('number',))
                names_col = self.worksheet.columns[n_indices[0]].name
                counts_col = self.worksheet.columns[c_indices[0]].name
            except Exception:
                names_col, counts_col = names_text, counts_text

            return {
                "is_summarized": True,
                "defect_column": names_col,
                "count_column": counts_col,
                "combine_percent": combine_pct,
                "show_cumulative": self.chk_cumulative.isChecked(),
            }
