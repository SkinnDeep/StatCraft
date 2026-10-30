"""Interactive Qt Dialog for Calc > Standardize."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QComboBox, QMessageBox
)


class StandardizeDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Standardize")
        self.setMinimumSize(520, 360)
        self.resize(560, 390)

        main_layout = QVBoxLayout(self)

        content_layout = QHBoxLayout()

        # Available Columns List
        col_group = QGroupBox("Available Columns")
        col_layout = QVBoxLayout(col_group)
        self.col_list = QListWidget()
        for i, col in enumerate(self.worksheet.columns):
            item = QListWidgetItem(f"C{i + 1}  {col.name}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.col_list.addItem(item)
        self.col_list.itemDoubleClicked.connect(self._select_col)
        col_layout.addWidget(self.col_list)

        self.select_btn = QPushButton("Select >>")
        self.select_btn.clicked.connect(self._select_col)
        col_layout.addWidget(self.select_btn)
        content_layout.addWidget(col_group, 4)

        # Inputs
        input_group = QGroupBox("Standardize Specifications")
        input_layout = QVBoxLayout(input_group)

        input_layout.addWidget(QLabel("Columns to standardize:"))
        self.cols_edit = QLineEdit()
        input_layout.addWidget(self.cols_edit)

        input_layout.addWidget(QLabel("Store results in (optional, or leave blank for new columns):"))
        self.dest_edit = QLineEdit()
        input_layout.addWidget(self.dest_edit)

        input_layout.addWidget(QLabel("Standardization Method:"))
        self.method_combo = QComboBox()
        self.method_combo.addItem("Subtract mean and divide by std dev (Z-score)", "zscore")
        self.method_combo.addItem("Subtract mean", "subtract_mean")
        self.method_combo.addItem("Divide by std dev", "divide_stdev")
        self.method_combo.addItem("Subtract min and divide by range (0 to 1)", "range_0_1")
        self.method_combo.addItem("Subtract median", "subtract_median")
        input_layout.addWidget(self.method_combo)

        content_layout.addWidget(input_group, 5)
        main_layout.addLayout(content_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(btn_layout)

    def _select_col(self):
        curr = self.col_list.currentItem()
        if not curr:
            return
        idx = curr.data(Qt.ItemDataRole.UserRole)
        col_ref = f"C{idx + 1}"
        existing = self.cols_edit.text().strip()
        if existing:
            self.cols_edit.setText(f"{existing} {col_ref}")
        else:
            self.cols_edit.setText(col_ref)

    def _resolve_cols(self, text: str) -> list[int]:
        tokens = text.replace(',', ' ').split()
        indices = []
        for t in tokens:
            t = t.strip()
            for i, col in enumerate(self.worksheet.columns):
                if f"C{i+1}" == t or col.name == t or f"'{col.name}'" == t:
                    if i not in indices:
                        indices.append(i)
                    break
        return indices

    def _on_ok(self):
        cols = self._resolve_cols(self.cols_edit.text())
        if not cols:
            QMessageBox.warning(self, "Invalid Selection", "Please select at least one column to standardize.")
            return
        self.accept()

    def get_settings(self) -> dict:
        cols = self._resolve_cols(self.cols_edit.text())
        dest = self._resolve_cols(self.dest_edit.text())
        return {
            'source_indices': cols,
            'target_indices': dest if dest else None,
            'method': self.method_combo.currentData(),
        }
