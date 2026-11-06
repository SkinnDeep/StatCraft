"""Interactive Qt Dialog for Multi-Vari Chart."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QMessageBox
)


class MultiVariDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(True)
        self.worksheet = worksheet
        self.setWindowTitle("Multi-Vari Chart")
        self.setMinimumSize(540, 380)
        self.resize(580, 420)

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

        input_layout.addWidget(QLabel("Response:"))
        self.resp_edit = QLineEdit()
        input_layout.addWidget(self.resp_edit)

        input_layout.addWidget(QLabel("Factor 1:"))
        self.f1_edit = QLineEdit()
        input_layout.addWidget(self.f1_edit)

        input_layout.addWidget(QLabel("Factor 2 (optional):"))
        self.f2_edit = QLineEdit()
        input_layout.addWidget(self.f2_edit)

        input_layout.addWidget(QLabel("Factor 3 (optional):"))
        self.f3_edit = QLineEdit()
        input_layout.addWidget(self.f3_edit)

        input_layout.addWidget(QLabel("Factor 4 (optional):"))
        self.f4_edit = QLineEdit()
        input_layout.addWidget(self.f4_edit)

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
        col_name = f"C{idx + 1}"

        for ed in (self.resp_edit, self.f1_edit, self.f2_edit, self.f3_edit, self.f4_edit):
            if not ed.text().strip():
                ed.setText(col_name)
                return

    def _resolve_col(self, text: str) -> int | None:
        raw = text.strip()
        if not raw:
            return None
        for i, col in enumerate(self.worksheet.columns):
            if f"C{i+1}" == raw or col.name == raw or f"'{col.name}'" == raw:
                return i
        return None

    def _on_ok(self):
        resp_idx = self._resolve_col(self.resp_edit.text())
        if resp_idx is None:
            QMessageBox.warning(self, "Invalid Response", "Please specify a valid response variable.")
            return

        f1 = self._resolve_col(self.f1_edit.text())
        if f1 is None:
            QMessageBox.warning(self, "Invalid Factor", "Please specify at least Factor 1.")
            return

        self.accept()

    def get_settings(self) -> dict:
        resp_idx = self._resolve_col(self.resp_edit.text())
        if resp_idx is None:
            resp_idx = 0

        factors = []
        for ed in (self.f1_edit, self.f2_edit, self.f3_edit, self.f4_edit):
            idx = self._resolve_col(ed.text())
            if idx is not None and idx not in factors:
                factors.append(idx)

        if not factors and len(self.worksheet.columns) > 1:
            factors = [1]

        return {
            'response_index': resp_idx,
            'factor_indices': factors,
        }
