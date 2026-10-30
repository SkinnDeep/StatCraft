"""Dialog for Nonnormal Capability Analysis matching StatCraft PE forms."""

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
    QComboBox,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QListWidget,
    QMessageBox,
    QFrame,
    QGroupBox,
    QWidget,
)

from .model import Worksheet


class CapabilityNonnormalDialog(QDialog):
    """Native StatCraft dialog for Nonnormal Capability Analysis."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Capability Analysis (Nonnormal Distribution)")
        self.setModal(True)
        self.resize(540, 420)

        self.options: Dict[str, Any] = {
            "dist_or_transform": "weibull",
            "naming_convention": "classical",
            "tolerance_k": 6.0,
            "confidence_level": 0.95,
        }
        self.selected_params: Optional[Dict[str, Any]] = None
        self.entry: Optional[Dict[str, Any]] = None

        layout = QVBoxLayout(self)

        # Main grid: Left column picker, right form fields
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

        # Distribution / Transformation combo
        form_layout.addWidget(QLabel("Fit distribution:"), 1, 0)
        self.combo_dist = QComboBox()
        self.combo_dist.addItem("Weibull", "weibull")
        self.combo_dist.addItem("Lognormal", "lognormal")
        self.combo_dist.addItem("Exponential", "exponential")
        self.combo_dist.addItem("Gamma", "gamma")
        self.combo_dist.addItem("Box-Cox Transformation", "box_cox")
        form_layout.addWidget(self.combo_dist, 1, 1)

        # Specification limits
        form_layout.addWidget(QLabel("Lower spec (LSL):"), 2, 0)
        self.edit_lsl = QLineEdit()
        form_layout.addWidget(self.edit_lsl, 2, 1)

        form_layout.addWidget(QLabel("Upper spec (USL):"), 3, 0)
        self.edit_usl = QLineEdit()
        form_layout.addWidget(self.edit_usl, 3, 1)

        form_layout.addWidget(QLabel("Target:"), 4, 0)
        self.edit_target = QLineEdit()
        form_layout.addWidget(self.edit_target, 4, 1)

        # AIAG/VDA Nomenclature
        self.chk_aiag_vda = QCheckBox("Use Unified AIAG/VDA nomenclature (Cnp, Cnpk)")
        form_layout.addWidget(self.chk_aiag_vda, 5, 0, 1, 2)

        main_grid.addLayout(form_layout, 0, 1, 5, 1)
        layout.addLayout(main_grid)

        # Dialog Buttons
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

        lsl_val = None
        if self.edit_lsl.text().strip():
            try:
                lsl_val = float(self.edit_lsl.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Invalid Limit", "LSL must be a valid number.")
                return

        usl_val = None
        if self.edit_usl.text().strip():
            try:
                usl_val = float(self.edit_usl.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Invalid Limit", "USL must be a valid number.")
                return

        if lsl_val is None and usl_val is None:
            QMessageBox.warning(self, "Missing Specification", "At least one specification limit (LSL or USL) must be entered.")
            return

        if lsl_val is not None and usl_val is not None and lsl_val >= usl_val:
            QMessageBox.warning(self, "Invalid Specifications", "LSL must be strictly less than USL.")
            return

        target_val = None
        if self.edit_target.text().strip():
            try:
                target_val = float(self.edit_target.text().strip())
            except ValueError:
                target_val = None

        dist_val = self.combo_dist.currentData()
        naming = "aiag_vda" if self.chk_aiag_vda.isChecked() else "classical"

        self.selected_params = {
            "variable_index": col_idx,
            "column_index": col_idx,
            "column_name": self.worksheet.columns[col_idx].name,
            "dist_or_transform": dist_val,
            "lsl": lsl_val,
            "usl": usl_val,
            "target": target_val,
            "naming_convention": naming,
            "tolerance_k": 6.0,
        }
        self.accept()
