"""Interactive Qt Dialog for Quality Run Chart."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QMessageBox
)


class RunChartDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Run Chart")
        self.setMinimumSize(480, 320)
        self.resize(500, 340)

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
        input_group = QGroupBox("Variables")
        input_layout = QVBoxLayout(input_group)

        input_layout.addWidget(QLabel("Single column:"))
        self.var_edit = QLineEdit()
        input_layout.addWidget(self.var_edit)

        input_layout.addWidget(QLabel("Subgroup size:"))
        self.subgroup_edit = QLineEdit("1")
        input_layout.addWidget(self.subgroup_edit)

        input_layout.addStretch()
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
        item = self.col_list.currentItem()
        if item:
            name = item.text().split("  ", 1)[-1]
            self.var_edit.setText(f"'{name}'")

    def _on_ok(self):
        text = self.var_edit.text().strip()
        if not text:
            QMessageBox.warning(self, "Invalid Selection", "Please specify a column.")
            return

        try:
            sz = int(self.subgroup_edit.text())
            if sz < 1:
                raise ValueError
        except Exception:
            QMessageBox.warning(self, "Invalid Subgroup Size", "Subgroup size must be a positive integer.")
            return

        self.accept()

    def get_settings(self) -> dict:
        raw = self.var_edit.text().strip()
        col_idx = 0
        for i, col in enumerate(self.worksheet.columns):
            if f"'{col.name}'" in raw or col.name in raw or f"C{i+1}" in raw:
                col_idx = i
                break

        sz = int(self.subgroup_edit.text().strip() or "1")
        return {
            'variable': col_idx,
            'subgroup_size': sz,
        }
