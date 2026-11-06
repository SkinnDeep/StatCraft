"""Covariance Dialog for StatCraft.

Provides column selection and Missing observation policy (Pairwise vs Listwise).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QAbstractItemView, QComboBox, QGroupBox, QMessageBox
)


class CovarianceDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Covariance")
        self.setMinimumSize(420, 320)
        self.setMinimumSize(560, 420)
        self.resize(560, 420)
        self.setSizeGripEnabled(True)

        main_layout = QVBoxLayout(self)

        group = QGroupBox("Variables")
        group_layout = QVBoxLayout(group)
        group_layout.addWidget(QLabel("Select 2 or more numeric columns (Ctrl+Click to multiselect):"))

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        for i, col in enumerate(self.worksheet.columns):
            if col.kind == 'number':
                item_text = f"C{i + 1}  {col.name}"
                self.list_widget.addItem(item_text)
                # Store original column index in item data
                item = self.list_widget.item(self.list_widget.count() - 1)
                item.setData(Qt.ItemDataRole.UserRole, i)

        group_layout.addWidget(self.list_widget)

        opt_layout = QHBoxLayout()
        opt_layout.addWidget(QLabel("Missing observations:"))
        self.missing_combo = QComboBox()
        self.missing_combo.addItems(["Pairwise", "Listwise"])
        opt_layout.addWidget(self.missing_combo)
        group_layout.addLayout(opt_layout)

        main_layout.addWidget(group)

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

    def _on_ok(self):
        selected_items = self.list_widget.selectedItems()
        if len(selected_items) < 2:
            QMessageBox.warning(self, "Invalid Selection", "Please select at least 2 numeric variables.")
            return
        self.accept()

    def get_settings(self) -> dict:
        selected_indices = [item.data(Qt.ItemDataRole.UserRole) for item in self.list_widget.selectedItems()]
        return {
            'indices': selected_indices,
            'missing': self.missing_combo.currentText(),
        }
