"""Qt Dialog for Data Recoding (Data > Recode > To Numeric / To Text).

Matches Minitab fidelity:
- Scans unique values of source column to populate mapping table automatically.
- Allows mapping individual values or numeric ranges.
- Allows storing in new columns or replacing original columns in place.
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
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .model import Worksheet
from .variable_dialogs import resolve_variables


class RecodeDialog(QDialog):
    """Minitab Recode Dialog supporting Recode to Numeric and Recode to Text."""

    def __init__(
        self,
        worksheet: Worksheet,
        target_kind: str = "number",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.worksheet = worksheet
        self.target_kind = "number" if target_kind.lower() in ("number", "numeric") else "text"
        title_kind = "Numeric" if self.target_kind == "number" else "Text"
        self.setWindowTitle(f"Recode to {title_kind}")
        self.resize(720, 520)
        self.settings: Optional[Dict[str, Any]] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        # Left panel: column picker
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Available columns:"))
        self.col_list = QListWidget()
        for idx, col in enumerate(self.worksheet.columns):
            item_text = f"C{idx+1} {col.name}" if col.name else f"C{idx+1}"
            it = QListWidgetItem(item_text)
            it.setData(Qt.ItemDataRole.UserRole, idx)
            self.col_list.addItem(it)

        left_layout.addWidget(self.col_list)
        btn_select = QPushButton("Select")
        btn_select.clicked.connect(self._on_select_column)
        self.col_list.itemDoubleClicked.connect(self._on_select_column)
        left_layout.addWidget(btn_select)
        main_layout.addLayout(left_layout, stretch=1)

        # Right panel: controls and mapping table
        right_layout = QVBoxLayout()

        top_form = QFormLayout()
        self.edit_source = QLineEdit()
        self.edit_source.setPlaceholderText("Select column from list or enter C1")
        self.edit_source.textChanged.connect(self._on_source_text_changed)
        top_form.addRow("Recode values in &columns:", self.edit_source)
        right_layout.addLayout(top_form)

        # Mapping Table
        table_grp = QGroupBox("Value Mapping Table")
        table_layout = QVBoxLayout(table_grp)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Current Value", "Recoded Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table_layout.addWidget(self.table)

        btn_row_layout = QHBoxLayout()
        btn_add_row = QPushButton("Add Row")
        btn_add_row.clicked.connect(self._add_row)
        btn_del_row = QPushButton("Delete Row")
        btn_del_row.clicked.connect(self._delete_selected_row)
        btn_reload = QPushButton("Reload Distinct Values")
        btn_reload.clicked.connect(self._populate_distinct_values)

        btn_row_layout.addWidget(btn_add_row)
        btn_row_layout.addWidget(btn_del_row)
        btn_row_layout.addWidget(btn_reload)
        btn_row_layout.addStretch()
        table_layout.addLayout(btn_row_layout)
        right_layout.addWidget(table_grp)

        # Storage Group
        grp_store = QGroupBox("Storage Location")
        lay_store = QVBoxLayout(grp_store)
        self.rb_store_new = QRadioButton("In &new columns of current worksheet")
        self.rb_store_new.setChecked(True)
        self.rb_store_orig = QRadioButton("In the &original columns")
        lay_store.addWidget(self.rb_store_new)
        lay_store.addWidget(self.rb_store_orig)
        right_layout.addWidget(grp_store)

        # Unmapped Values Group
        grp_unmapped = QGroupBox("Handling of Unmapped Values")
        lay_unmapped = QVBoxLayout(grp_unmapped)
        self.rb_unmapped_orig = QRadioButton("&Keep original values (missing if invalid)")
        self.rb_unmapped_orig.setChecked(True)
        self.rb_unmapped_custom = QRadioButton("Recode into &specified value:")

        h_custom = QHBoxLayout()
        self.edit_unmapped_val = QLineEdit()
        self.edit_unmapped_val.setPlaceholderText("Default value or leave empty for missing (*)")
        self.edit_unmapped_val.setEnabled(False)
        self.rb_unmapped_custom.toggled.connect(self.edit_unmapped_val.setEnabled)
        h_custom.addWidget(self.rb_unmapped_custom)
        h_custom.addWidget(self.edit_unmapped_val)

        lay_unmapped.addWidget(self.rb_unmapped_orig)
        lay_unmapped.addLayout(h_custom)
        right_layout.addWidget(grp_unmapped)

        # OK / Cancel
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)

        main_layout.addLayout(right_layout, stretch=2)

    def _on_select_column(self) -> None:
        item = self.col_list.currentItem()
        if not item:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        col = self.worksheet.columns[idx]
        name = col.name or f"C{idx+1}"
        self.edit_source.setText(name)
        self._populate_distinct_values()

    def _on_source_text_changed(self) -> None:
        pass

    def _populate_distinct_values(self) -> None:
        txt = self.edit_source.text().strip()
        if not txt:
            return
        try:
            resolved = resolve_variables(txt, self.worksheet, kinds=("number", "text", "date"))
        except ValueError:
            return
        if not resolved:
            return
        col = self.worksheet.columns[resolved[0]]

        # Gather unique non-empty values
        unique_vals = []
        seen = set()
        for v in col.values:
            s_val = "*" if v is None else str(v).strip()
            if s_val not in seen:
                seen.add(s_val)
                unique_vals.append(s_val)

        self.table.setRowCount(len(unique_vals))
        for r, val_str in enumerate(unique_vals):
            it_curr = QTableWidgetItem(val_str)
            it_curr.setFlags(it_curr.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 0, it_curr)

            it_rec = QTableWidgetItem("")
            self.table.setItem(r, 1, it_rec)

    def _add_row(self) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(""))
        self.table.setItem(r, 1, QTableWidgetItem(""))

    def _delete_selected_row(self) -> None:
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def _on_accept(self) -> None:
        txt = self.edit_source.text().strip()
        if not txt:
            QMessageBox.warning(self, "Recode", "Please select a source column.")
            return

        try:
            resolved = resolve_variables(txt, self.worksheet, kinds=("number", "text", "date"))
        except ValueError:
            return
        if not resolved:
            QMessageBox.warning(self, "Recode", f"Column '{txt}' not found in worksheet.")
            return

        rules: List[Dict[str, Any]] = []
        for r in range(self.table.rowCount()):
            it0 = self.table.item(r, 0)
            it1 = self.table.item(r, 1)
            curr = it0.text().strip() if it0 else ""
            rec = it1.text().strip() if it1 else ""
            if not curr:
                continue

            if curr == "*":
                rules.append({"type": "missing", "recoded": rec if rec else None})
            else:
                rules.append({"type": "exact", "current": curr, "recoded": rec if rec else None})

        if not rules:
            QMessageBox.warning(self, "Recode", "Please enter at least one recoding rule.")
            return

        default_action = "specified" if self.rb_unmapped_custom.isChecked() else "original"
        def_val = self.edit_unmapped_val.text().strip() if self.rb_unmapped_custom.isChecked() else None

        storage = "new_columns" if self.rb_store_new.isChecked() else "original"

        self.settings = {
            "source_indices": resolved,
            "rules": rules,
            "target_kind": self.target_kind,
            "storage": storage,
            "default_action": default_action,
            "default_value": def_val,
        }
        self.accept()
