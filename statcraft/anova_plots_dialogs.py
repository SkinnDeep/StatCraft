"""Dialogs for standalone ANOVA plots: Main Effects Plot and Interactions Plot."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QListWidget, QAbstractItemView, QGroupBox, QMessageBox
)


class MainEffectsPlotDialog(QDialog):
    """Dialog for Stat > ANOVA > Main Effects Plot..."""

    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(True)
        self.worksheet = worksheet
        self.setWindowTitle("Main Effects Plot")
        self.setMinimumSize(460, 420)
        self.resize(480, 450)

        main_layout = QVBoxLayout(self)

        group = QGroupBox("Variables")
        form_layout = QVBoxLayout(group)

        # Response
        form_layout.addWidget(QLabel("Responses (Continuous Numeric):"))
        self.combo_resp = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            if col.kind == 'number':
                self.combo_resp.addItem(f"C{i + 1}  {col.name}", i)
        form_layout.addWidget(self.combo_resp)

        form_layout.addSpacing(8)

        # Factors (Multiple selection list)
        form_layout.addWidget(QLabel("Factors (Select 1 to 9):"))
        self.list_factors = QListWidget()
        self.list_factors.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        for i, col in enumerate(self.worksheet.columns):
            self.list_factors.addItem(f"C{i + 1}  {col.name}")
        form_layout.addWidget(self.list_factors)

        # Select first 2 non-response factors if available
        if self.list_factors.count() > 1:
            self.list_factors.item(1).setSelected(True)
        if self.list_factors.count() > 2:
            self.list_factors.item(2).setSelected(True)

        main_layout.addWidget(group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_ok = QPushButton("OK")
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.btn_ok)

        main_layout.addLayout(btn_layout)

    def _on_ok(self):
        if self.combo_resp.currentIndex() < 0:
            QMessageBox.warning(self, "Validation Error", "Please select a numeric response variable.")
            return

        selected_factor_rows = [item.row() for item in self.list_factors.selectedIndexes()]
        resp_idx = self.combo_resp.currentData()

        # Remove response index if accidentally selected as a factor
        factor_indices = [r for r in selected_factor_rows if r != resp_idx]
        if not factor_indices:
            QMessageBox.warning(self, "Validation Error", "Please select at least one factor separate from the response.")
            return

        if len(factor_indices) > 9:
            QMessageBox.warning(self, "Validation Error", "Main Effects Plot supports a maximum of 9 factors.")
            return

        self.accept()

    def get_parameters(self) -> dict:
        resp_idx = self.combo_resp.currentData()
        selected_factor_rows = [item.row() for item in self.list_factors.selectedIndexes()]
        factor_indices = [r for r in selected_factor_rows if r != resp_idx]
        return {
            "response_index": resp_idx,
            "factor_indices": factor_indices
        }


class InteractionsPlotDialog(QDialog):
    """Dialog for Stat > ANOVA > Interactions Plot..."""

    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(True)
        self.worksheet = worksheet
        self.setWindowTitle("Interaction Plot")
        self.setMinimumSize(440, 360)
        self.resize(460, 380)

        main_layout = QVBoxLayout(self)

        group = QGroupBox("Variables")
        form_layout = QVBoxLayout(group)

        # 1. Response
        form_layout.addWidget(QLabel("Responses (Continuous Numeric):"))
        self.combo_resp = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            if col.kind == 'number':
                self.combo_resp.addItem(f"C{i + 1}  {col.name}", i)
        form_layout.addWidget(self.combo_resp)

        form_layout.addSpacing(6)

        # 2. Factor A (Horizontal Axis)
        form_layout.addWidget(QLabel("Factor A (Horizontal Axis):"))
        self.combo_factor_a = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            self.combo_factor_a.addItem(f"C{i + 1}  {col.name}", i)
        form_layout.addWidget(self.combo_factor_a)

        form_layout.addSpacing(6)

        # 3. Factor B (Curves / Lines)
        form_layout.addWidget(QLabel("Factor B (Separate Lines):"))
        self.combo_factor_b = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            self.combo_factor_b.addItem(f"C{i + 1}  {col.name}", i)
        form_layout.addWidget(self.combo_factor_b)

        if self.combo_factor_a.count() > 1:
            self.combo_factor_a.setCurrentIndex(1)
        if self.combo_factor_b.count() > 2:
            self.combo_factor_b.setCurrentIndex(2)

        main_layout.addWidget(group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_ok = QPushButton("OK")
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.btn_ok)

        main_layout.addLayout(btn_layout)

    def _on_ok(self):
        if self.combo_resp.currentIndex() < 0:
            QMessageBox.warning(self, "Validation Error", "Please select a numeric response variable.")
            return

        resp_idx = self.combo_resp.currentData()
        fa_idx = self.combo_factor_a.currentData()
        fb_idx = self.combo_factor_b.currentData()

        if fa_idx == fb_idx:
            QMessageBox.warning(self, "Validation Error", "Factor A and Factor B must be different columns.")
            return

        if resp_idx in (fa_idx, fb_idx):
            QMessageBox.warning(self, "Validation Error", "Response variable cannot be used as a factor.")
            return

        self.accept()

    def get_parameters(self) -> dict:
        return {
            "response_index": self.combo_resp.currentData(),
            "factor_a_index": self.combo_factor_a.currentData(),
            "factor_b_index": self.combo_factor_b.currentData()
        }
