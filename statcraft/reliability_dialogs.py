"""Native StatCraft Dialog for Reliability Distribution Analysis (Right Censoring)."""

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
    QWidget,
)

from .model import Worksheet


class ReliabilityDistributionDialog(QDialog):
    """Native dialog for Distribution Analysis (Right Censoring) matching StatCraft."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Distribution Analysis (Right Censoring)")
        self.setModal(True)
        self.resize(540, 400)

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
        form_layout.addWidget(QLabel("Variables / Life data:"), 0, 0)
        self.edit_var = QLineEdit()
        form_layout.addWidget(self.edit_var, 0, 1)

        form_layout.addWidget(QLabel("Assumed distribution:"), 1, 0)
        self.combo_dist = QComboBox()
        self.combo_dist.addItem("Weibull", "weibull")
        self.combo_dist.addItem("Lognormal", "lognormal")
        self.combo_dist.addItem("Exponential", "exponential")
        self.combo_dist.addItem("Normal", "normal")
        form_layout.addWidget(self.combo_dist, 1, 1)

        form_layout.addWidget(QLabel("Censor column (optional):"), 2, 0)
        self.edit_censor_col = QLineEdit()
        form_layout.addWidget(self.edit_censor_col, 2, 1)

        form_layout.addWidget(QLabel("Censoring value:"), 3, 0)
        self.edit_censor_val = QLineEdit("0")
        form_layout.addWidget(self.edit_censor_val, 3, 1)

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
        if not self.edit_var.text().strip():
            self.edit_var.setText(item.text())
        else:
            self.edit_censor_col.setText(item.text())

    def _on_select_clicked(self):
        item = self.col_list.currentItem()
        if item:
            if not self.edit_var.text().strip():
                self.edit_var.setText(item.text())
            else:
                self.edit_censor_col.setText(item.text())

    def _on_ok(self):
        var_name = self.edit_var.text().strip().strip("'\"")
        if not var_name:
            QMessageBox.warning(self, "Invalid Selection", "Please specify a numeric life data column.")
            return

        var_idx = None
        for i, c in enumerate(self.worksheet.columns):
            if c.name == var_name or f"C{i+1}" == var_name:
                var_idx = i
                break

        if var_idx is None:
            QMessageBox.warning(self, "Invalid Selection", f"Column '{var_name}' not found.")
            return

        censor_idx = None
        censor_name = self.edit_censor_col.text().strip().strip("'\"")
        if censor_name:
            for i, c in enumerate(self.worksheet.columns):
                if c.name == censor_name or f"C{i+1}" == censor_name:
                    censor_idx = i
                    break

        censor_val = None
        if self.edit_censor_val.text().strip():
            try:
                censor_val = float(self.edit_censor_val.text().strip())
            except ValueError:
                censor_val = 0.0

        dist_name = self.combo_dist.currentData()

        self.selected_params = {
            "variable_index": var_idx,
            "column_index": var_idx,
            "column_name": self.worksheet.columns[var_idx].name,
            "censor_index": censor_idx,
            "censor_value": censor_val,
            "dist_name": dist_name,
            "confidence_level": 0.95,
        }
        self.accept()
