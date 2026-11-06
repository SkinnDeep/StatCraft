"""Interactive Qt Dialog for Graphical Summary of Descriptive Statistics."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QMessageBox
)


class GraphicalSummaryDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Graphical Summary")
        self.setMinimumSize(480, 340)
        self.setMinimumSize(560, 420)
        self.resize(560, 420)
        self.setSizeGripEnabled(True)

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

        input_layout.addWidget(QLabel("Variables:"))
        self.var_edit = QLineEdit()
        input_layout.addWidget(self.var_edit)

        input_layout.addWidget(QLabel("Confidence level (%):"))
        self.conf_edit = QLineEdit("95.0")
        input_layout.addWidget(self.conf_edit)

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
            curr = self.var_edit.text().strip()
            self.var_edit.setText(f"{curr} '{name}'" if curr else f"'{name}'")

    def _on_ok(self):
        text = self.var_edit.text().strip()
        if not text:
            QMessageBox.warning(self, "Invalid Selection", "Please specify at least one variable.")
            return

        try:
            conf = float(self.conf_edit.text())
            if not (1.0 <= conf <= 99.9):
                raise ValueError
        except Exception:
            QMessageBox.warning(self, "Invalid Confidence Level", "Confidence level must be between 1.0 and 99.9.")
            return

        self.accept()

    def get_settings(self) -> dict:
        # Parse column indices
        raw = self.var_edit.text().strip()
        # Find matching columns in worksheet
        indices = []
        for i, col in enumerate(self.worksheet.columns):
            if f"'{col.name}'" in raw or col.name in raw or f"C{i+1}" in raw:
                indices.append(i)
        if not indices and self.col_list.count() > 0:
            indices = [0]

        conf = float(self.conf_edit.text()) / 100.0
        return {
            'variables': indices,
            'confidence': conf,
        }
