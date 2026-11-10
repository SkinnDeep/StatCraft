"""Minitab-Identical Dialog for Empirical Cumulative Distribution Function (ECDF).

Allows selecting:
- Variable (Response)
- Optional Grouping variable
- Distribution Fit: None, Normal, Lognormal, Weibull, Exponential
- Confidence level for simultaneous DKW band
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .model import Worksheet


class EmpiricalCDFDialog(QDialog):
    """Minitab-standard Empirical CDF dialog."""

    def __init__(self, parent: Optional[QWidget], worksheet: Worksheet):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Empirical CDF")
        self.resize(520, 440)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        content_layout = QHBoxLayout()

        # Left: Column List
        col_group = QGroupBox("Available Columns")
        col_layout = QVBoxLayout(col_group)
        self.col_list = QListWidget()
        self.numeric_indices: List[int] = []

        for idx, col in enumerate(self.worksheet.columns):
            if col.kind == 'number':
                self.col_list.addItem(f"C{idx+1}  {col.name}")
                self.numeric_indices.append(idx)

        col_layout.addWidget(self.col_list)
        content_layout.addWidget(col_group, 1)

        # Right: Selectors & Options
        right_panel = QVBoxLayout()

        var_box = QGroupBox("Variables")
        var_layout = QVBoxLayout(var_box)

        v_row = QHBoxLayout()
        v_row.addWidget(QLabel("Variable:"))
        self.txt_var = QLineEdit()
        self.txt_var.setReadOnly(True)
        btn_sel_var = QPushButton("◀ Select")
        btn_sel_var.clicked.connect(self._select_var)
        v_row.addWidget(self.txt_var, 1)
        v_row.addWidget(btn_sel_var)
        var_layout.addLayout(v_row)

        g_row = QHBoxLayout()
        g_row.addWidget(QLabel("By variable (optional):"))
        self.txt_grp = QLineEdit()
        self.txt_grp.setReadOnly(True)
        btn_sel_grp = QPushButton("◀ Select")
        btn_sel_grp.clicked.connect(self._select_grp)
        btn_clr_grp = QPushButton("✕")
        btn_clr_grp.clicked.connect(self._clear_grp)
        g_row.addWidget(self.txt_grp, 1)
        g_row.addWidget(btn_sel_grp)
        g_row.addWidget(btn_clr_grp)
        var_layout.addLayout(g_row)

        right_panel.addWidget(var_box)

        # Fit & Confidence Options
        opt_box = QGroupBox("Distribution Fit & Confidence Bands")
        opt_layout = QVBoxLayout(opt_box)

        fit_row = QHBoxLayout()
        fit_row.addWidget(QLabel("Distribution Fit:"))
        self.cbo_dist = QComboBox()
        self.cbo_dist.addItems(["None", "Normal", "Lognormal", "Weibull", "Exponential"])
        fit_row.addWidget(self.cbo_dist, 1)
        opt_layout.addLayout(fit_row)

        conf_row = QHBoxLayout()
        conf_row.addWidget(QLabel("Confidence Level:"))
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.50, 0.999)
        self.spin_conf.setSingleStep(0.01)
        self.spin_conf.setValue(0.95)
        conf_row.addWidget(self.spin_conf)
        conf_row.addStretch()
        opt_layout.addLayout(conf_row)

        right_panel.addWidget(opt_box)
        content_layout.addLayout(right_panel, 2)
        main_layout.addLayout(content_layout)

        # Standard Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.selected_var_idx: Optional[int] = None
        self.selected_grp_idx: Optional[int] = None

        self.col_list.doubleClicked.connect(self._on_list_double_click)

        if self.numeric_indices:
            self.selected_var_idx = self.numeric_indices[0]
            col = self.worksheet.columns[self.selected_var_idx]
            self.txt_var.setText(f"C{self.selected_var_idx+1} {col.name}")

    def _select_var(self):
        row = self.col_list.currentRow()
        if 0 <= row < len(self.numeric_indices):
            self.selected_var_idx = self.numeric_indices[row]
            col = self.worksheet.columns[self.selected_var_idx]
            self.txt_var.setText(f"C{self.selected_var_idx+1} {col.name}")

    def _select_grp(self):
        row = self.col_list.currentRow()
        if 0 <= row < len(self.numeric_indices):
            self.selected_grp_idx = self.numeric_indices[row]
            col = self.worksheet.columns[self.selected_grp_idx]
            self.txt_grp.setText(f"C{self.selected_grp_idx+1} {col.name}")

    def _clear_grp(self):
        self.selected_grp_idx = None
        self.txt_grp.clear()

    def _on_list_double_click(self):
        if self.selected_var_idx is None:
            self._select_var()
        elif self.selected_grp_idx is None:
            self._select_grp()

    def _validate_and_accept(self):
        if self.selected_var_idx is None:
            return
        self.accept()

    def settings(self) -> Dict[str, Any]:
        """Return validated dialog settings."""
        return {
            'variable_index': self.selected_var_idx,
            'group_index': self.selected_grp_idx,
            'distribution': self.cbo_dist.currentText(),
            'confidence': self.spin_conf.value(),
        }
