"""Interactive Qt Dialog for Grubbs' Outlier Test."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QComboBox, QMessageBox
)


class OutlierTestDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Outlier Test")
        self.setMinimumSize(480, 320)
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

        input_layout.addWidget(QLabel("Significance level (α):"))
        self.alpha_edit = QLineEdit("0.05")
        input_layout.addWidget(self.alpha_edit)

        input_layout.addWidget(QLabel("Alternative hypothesis:"))
        self.alt_combo = QComboBox()
        self.alt_combo.addItem("Smallest or largest value is an outlier (two-sided)", "two-sided")
        self.alt_combo.addItem("Smallest value is an outlier (low)", "min")
        self.alt_combo.addItem("Largest value is an outlier (high)", "max")
        input_layout.addWidget(self.alt_combo)

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
        self.var_edit.setText(f"C{idx + 1}")

    def _resolve_col(self, text: str) -> int | None:
        raw = text.strip()
        if not raw:
            return None
        for i, col in enumerate(self.worksheet.columns):
            if f"C{i+1}" == raw or col.name == raw or f"'{col.name}'" == raw:
                return i
        return None

    def _on_ok(self):
        col_idx = self._resolve_col(self.var_edit.text())
        if col_idx is None:
            QMessageBox.warning(self, "Invalid Variable", "Please select a valid variable column.")
            return

        try:
            alpha = float(self.alpha_edit.text())
            if not (0.001 <= alpha <= 0.25):
                raise ValueError
        except Exception:
            QMessageBox.warning(self, "Invalid Alpha", "Significance level must be between 0.001 and 0.25.")
            return

        self.accept()

    def get_settings(self) -> dict:
        col_idx = self._resolve_col(self.var_edit.text())
        if col_idx is None:
            col_idx = 0
        return {
            'variable_index': col_idx,
            'alpha': float(self.alpha_edit.text()),
            'alternative': self.alt_combo.currentData(),
        }
