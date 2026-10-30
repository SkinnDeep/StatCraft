"""Native StatCraft Dialogs for Nonparametric and Automated Capability Analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QListWidget,
    QMessageBox,
    QWidget,
)

from .model import Worksheet


class CapabilityNonparametricDialog(QDialog):
    """Dialog for Nonparametric Capability Analysis matching StatCraft."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Capability Analysis (Nonparametric / Distribution-Free)")
        self.setModal(True)
        self.resize(520, 380)

        self.selected_params: Optional[Dict[str, Any]] = None

        layout = QVBoxLayout(self)
        main_grid = QGridLayout()

        # Variable list
        v_box = QVBoxLayout()
        v_box.addWidget(QLabel("Columns:"))
        self.col_list = QListWidget()
        for col in self.worksheet.columns:
            if col.kind == "number":
                self.col_list.addItem(col.name)
        self.col_list.itemDoubleClicked.connect(self._on_col_double_clicked)
        v_box.addWidget(self.col_list)

        btn_select = QPushButton("Select")
        btn_select.clicked.connect(self._on_select_clicked)
        v_box.addWidget(btn_select)
        main_grid.addLayout(v_box, 0, 0, 5, 1)

        # Fields
        form_layout = QGridLayout()
        form_layout.addWidget(QLabel("Single column:"), 0, 0)
        self.edit_single_col = QLineEdit()
        form_layout.addWidget(self.edit_single_col, 0, 1)

        form_layout.addWidget(QLabel("Lower spec (LSL):"), 1, 0)
        self.edit_lsl = QLineEdit()
        form_layout.addWidget(self.edit_lsl, 1, 1)

        form_layout.addWidget(QLabel("Upper spec (USL):"), 2, 0)
        self.edit_usl = QLineEdit()
        form_layout.addWidget(self.edit_usl, 2, 1)

        form_layout.addWidget(QLabel("Target:"), 3, 0)
        self.edit_target = QLineEdit()
        form_layout.addWidget(self.edit_target, 3, 1)

        self.chk_aiag_vda = QCheckBox("Use Unified AIAG/VDA nomenclature (Cnp, Cnpk)")
        form_layout.addWidget(self.chk_aiag_vda, 4, 0, 1, 2)

        main_grid.addLayout(form_layout, 0, 1, 5, 1)
        layout.addLayout(main_grid)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self._on_ok)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _on_col_double_clicked(self, item):
        self.edit_single_col.setText(item.text())

    def _on_select_clicked(self):
        item = self.col_list.currentItem()
        if item:
            self.edit_single_col.setText(item.text())

    def _on_ok(self):
        col_name = self.edit_single_col.text().strip().strip("'\"")
        if not col_name:
            QMessageBox.warning(self, "Invalid Selection", "Please specify a numeric measurement column.")
            return

        col_idx = None
        for i, c in enumerate(self.worksheet.columns):
            if c.name == col_name or f"C{i+1}" == col_name:
                col_idx = i
                break

        if col_idx is None:
            QMessageBox.warning(self, "Invalid Selection", f"Column '{col_name}' not found.")
            return

        lsl_val = float(self.edit_lsl.text().strip()) if self.edit_lsl.text().strip() else None
        usl_val = float(self.edit_usl.text().strip()) if self.edit_usl.text().strip() else None
        if lsl_val is None and usl_val is None:
            QMessageBox.warning(self, "Missing Specification", "At least one specification limit (LSL or USL) must be entered.")
            return

        naming = "aiag_vda" if self.chk_aiag_vda.isChecked() else "classical"
        self.selected_params = {
            "variable_index": col_idx,
            "column_index": col_idx,
            "column_name": self.worksheet.columns[col_idx].name,
            "lsl": lsl_val,
            "usl": usl_val,
            "target": float(self.edit_target.text().strip()) if self.edit_target.text().strip() else None,
            "naming_convention": naming,
            "tolerance_k": 6.0,
        }
        self.accept()


class CapabilityAutomatedDialog(CapabilityNonparametricDialog):
    """Dialog for Automated Capability Analysis (Distribution Tournament)."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(worksheet, parent)
        self.setWindowTitle("Automated Capability Analysis")
