"""Minitab-Identical Dialog for Marginal Plot.

Allows selecting:
- Y variable (Response)
- X variable (Predictor)
- Marginal Plot Type: Histograms, Boxplots, or Dotplots
- Option to include Normal density curve with histograms
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .model import Worksheet


class MarginalPlotDialog(QDialog):
    """Minitab-standard Marginal Plot dialog."""

    def __init__(self, parent: Optional[QWidget], worksheet: Worksheet):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Marginal Plot")
        self.resize(540, 480)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # Content horizontal layout: Columns list on left, Selectors on right
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

        # Right: Variable Selectors & Options
        right_panel = QVBoxLayout()

        # Y variable row
        y_box = QGroupBox("Variables")
        y_layout = QVBoxLayout(y_box)

        y_row = QHBoxLayout()
        y_row.addWidget(QLabel("Y variable:"))
        self.txt_y = QLineEdit()
        self.txt_y.setReadOnly(True)
        btn_sel_y = QPushButton("◀ Select Y")
        btn_sel_y.clicked.connect(self._select_y)
        y_row.addWidget(self.txt_y, 1)
        y_row.addWidget(btn_sel_y)
        y_layout.addLayout(y_row)

        x_row = QHBoxLayout()
        x_row.addWidget(QLabel("X variable:"))
        self.txt_x = QLineEdit()
        self.txt_x.setReadOnly(True)
        btn_sel_x = QPushButton("◀ Select X")
        btn_sel_x.clicked.connect(self._select_x)
        x_row.addWidget(self.txt_x, 1)
        x_row.addWidget(btn_sel_x)
        y_layout.addLayout(x_row)

        right_panel.addWidget(y_box)

        # Marginal Plot Type Group
        type_box = QGroupBox("Marginal Plot Type")
        type_layout = QVBoxLayout(type_box)

        self.radio_hist = QRadioButton("Histograms")
        self.radio_box = QRadioButton("Boxplots")
        self.radio_dot = QRadioButton("Dotplots")
        self.radio_hist.setChecked(True)

        self.type_group = QButtonGroup(self)
        self.type_group.addButton(self.radio_hist)
        self.type_group.addButton(self.radio_box)
        self.type_group.addButton(self.radio_dot)

        type_layout.addWidget(self.radio_hist)
        type_layout.addWidget(self.radio_box)
        type_layout.addWidget(self.radio_dot)

        self.chk_norm = QCheckBox("Include normal density curve with histograms")
        self.chk_norm.setChecked(False)
        type_layout.addWidget(self.chk_norm)

        bins_row = QHBoxLayout()
        bins_row.addWidget(QLabel("Histogram Bins:"))
        self.spin_bins = QSpinBox()
        self.spin_bins.setRange(4, 50)
        self.spin_bins.setValue(12)
        bins_row.addWidget(self.spin_bins)
        bins_row.addStretch()
        type_layout.addLayout(bins_row)

        right_panel.addWidget(type_box)
        content_layout.addLayout(right_panel, 2)
        main_layout.addLayout(content_layout)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.selected_y_idx: Optional[int] = None
        self.selected_x_idx: Optional[int] = None

        self.radio_hist.toggled.connect(self._sync_options)
        self.col_list.doubleClicked.connect(self._on_list_double_click)

        # Pre-select first two numeric columns if available
        if len(self.numeric_indices) >= 2:
            self.selected_y_idx = self.numeric_indices[0]
            self.selected_x_idx = self.numeric_indices[1]
            self.txt_y.setText(f"C{self.selected_y_idx+1} {self.worksheet.columns[self.selected_y_idx].name}")
            self.txt_x.setText(f"C{self.selected_x_idx+1} {self.worksheet.columns[self.selected_x_idx].name}")

        self._sync_options()

    def _sync_options(self):
        is_hist = self.radio_hist.isChecked()
        self.chk_norm.setEnabled(is_hist)
        self.spin_bins.setEnabled(is_hist)

    def _select_y(self):
        row = self.col_list.currentRow()
        if 0 <= row < len(self.numeric_indices):
            self.selected_y_idx = self.numeric_indices[row]
            col = self.worksheet.columns[self.selected_y_idx]
            self.txt_y.setText(f"C{self.selected_y_idx+1} {col.name}")

    def _select_x(self):
        row = self.col_list.currentRow()
        if 0 <= row < len(self.numeric_indices):
            self.selected_x_idx = self.numeric_indices[row]
            col = self.worksheet.columns[self.selected_x_idx]
            self.txt_x.setText(f"C{self.selected_x_idx+1} {col.name}")

    def _on_list_double_click(self):
        if self.selected_y_idx is None:
            self._select_y()
        elif self.selected_x_idx is None:
            self._select_x()

    def _validate_and_accept(self):
        if self.selected_y_idx is None or self.selected_x_idx is None:
            return
        if self.selected_y_idx == self.selected_x_idx:
            return
        self.accept()

    def settings(self) -> Dict[str, Any]:
        """Return validated dialog settings."""
        if self.radio_box.isChecked():
            m_type = 'boxplot'
        elif self.radio_dot.isChecked():
            m_type = 'dotplot'
        else:
            m_type = 'histogram'

        return {
            'y_index': self.selected_y_idx,
            'x_index': self.selected_x_idx,
            'marginal_type': m_type,
            'show_normal_curve': self.chk_norm.isChecked() if m_type == 'histogram' else False,
            'bins': self.spin_bins.value(),
        }
