"""Stem-and-Leaf Dialog for StatCraft."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QMessageBox
)


class StemLeafDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Stem-and-Leaf")
        self.setMinimumSize(380, 200)
        self.resize(400, 220)

        main_layout = QVBoxLayout(self)

        group = QGroupBox("Variable")
        group_layout = QVBoxLayout(group)
        group_layout.addWidget(QLabel("Select numeric variable for Stem-and-Leaf display:"))

        self.col_combo = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            if col.kind == 'number':
                self.col_combo.addItem(f"C{i + 1}  {col.name}", i)

        group_layout.addWidget(self.col_combo)
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
        if self.col_combo.currentIndex() < 0:
            QMessageBox.warning(self, "Invalid Selection", "Please select a numeric variable.")
            return
        self.accept()

    def get_settings(self) -> dict:
        return {
            'index': self.col_combo.currentData(),
        }
