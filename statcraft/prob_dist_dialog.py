"""Minitab-Identical Dialog for Probability Distribution Plot.

Allows choosing:
- Mode: View Single vs View Probability
- Distribution: Normal, Student's t, Chi-Square, F, Binomial, Poisson, Exponential, Gamma, Weibull, Uniform, Lognormal, Logistic
- Dynamic parameter fields
- Shaded area specification: By Probability or By X Value (Right Tail, Left Tail, Both Tails, Middle)
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .prob_dist_plot import SUPPORTED_DISTRIBUTIONS


class ProbabilityDistributionPlotDialog(QDialog):
    """Minitab-equivalent Probability Distribution Plot dialog."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Probability Distribution Plot")
        self.resize(520, 560)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # 1. Mode Selection Group
        mode_box = QGroupBox("Plot Mode")
        mode_layout = QHBoxLayout(mode_box)
        self.radio_view_single = QRadioButton("View Single Distribution")
        self.radio_view_prob = QRadioButton("View Probability (Shaded Area)")
        self.radio_view_prob.setChecked(True)
        mode_layout.addWidget(self.radio_view_single)
        mode_layout.addWidget(self.radio_view_prob)
        main_layout.addWidget(mode_box)

        # 2. Distribution Selection & Parameters Group
        dist_box = QGroupBox("Distribution & Parameters")
        dist_layout = QVBoxLayout(dist_box)

        combo_layout = QHBoxLayout()
        combo_layout.addWidget(QLabel("Distribution:"))
        self.cbo_dist = QComboBox()
        for d_name in SUPPORTED_DISTRIBUTIONS.keys():
            self.cbo_dist.addItem(d_name)
        combo_layout.addWidget(self.cbo_dist, 1)
        dist_layout.addLayout(combo_layout)

        # Stacked widget for distribution parameters
        self.param_stack = QStackedWidget()
        self.param_editors: Dict[str, Dict[str, QLineEdit]] = {}

        for d_name, info in SUPPORTED_DISTRIBUTIONS.items():
            page = QWidget()
            f_layout = QFormLayout(page)
            f_layout.setContentsMargins(10, 8, 10, 8)
            f_layout.setSpacing(8)
            self.param_editors[d_name] = {}

            for p_key, p_lbl, p_def in info['params']:
                edit = QLineEdit(str(p_def))
                f_layout.addRow(QLabel(p_lbl + ":"), edit)
                self.param_editors[d_name][p_key] = edit

            self.param_stack.addWidget(page)

        dist_layout.addWidget(self.param_stack)
        main_layout.addWidget(dist_box)

        # 3. Shaded Area Specification Group
        self.shade_box = QGroupBox("Shaded Area")
        shade_layout = QVBoxLayout(self.shade_box)

        # Shade By: Probability vs X Value
        shade_by_layout = QHBoxLayout()
        shade_by_layout.addWidget(QLabel("Define Shaded Area By:"))
        self.radio_by_prob = QRadioButton("Probability")
        self.radio_by_x = QRadioButton("X value")
        self.radio_by_prob.setChecked(True)
        shade_by_layout.addWidget(self.radio_by_prob)
        shade_by_layout.addWidget(self.radio_by_x)
        shade_layout.addLayout(shade_by_layout)

        # Tail Selection
        tail_layout = QHBoxLayout()
        tail_layout.addWidget(QLabel("Region:"))
        self.radio_right = QRadioButton("Right Tail")
        self.radio_left = QRadioButton("Left Tail")
        self.radio_both = QRadioButton("Both Tails")
        self.radio_middle = QRadioButton("Middle")
        self.radio_both.setChecked(True)

        self.tail_group = QButtonGroup(self)
        self.tail_group.addButton(self.radio_right)
        self.tail_group.addButton(self.radio_left)
        self.tail_group.addButton(self.radio_both)
        self.tail_group.addButton(self.radio_middle)

        tail_layout.addWidget(self.radio_right)
        tail_layout.addWidget(self.radio_left)
        tail_layout.addWidget(self.radio_both)
        tail_layout.addWidget(self.radio_middle)
        shade_layout.addLayout(tail_layout)

        # Value inputs
        val_form = QFormLayout()
        val_form.setContentsMargins(10, 6, 10, 6)
        val_form.setSpacing(8)

        self.txt_prob = QLineEdit("0.05")
        val_form.addRow(QLabel("Probability:"), self.txt_prob)

        self.txt_x = QLineEdit("1.96")
        val_form.addRow(QLabel("X value:"), self.txt_x)

        self.txt_x_low = QLineEdit("-1.96")
        val_form.addRow(QLabel("X value 1 (Lower):"), self.txt_x_low)

        self.txt_x_high = QLineEdit("1.96")
        val_form.addRow(QLabel("X value 2 (Upper):"), self.txt_x_high)

        shade_layout.addLayout(val_form)
        main_layout.addWidget(self.shade_box)

        # 4. Standard Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # Connect signals
        self.cbo_dist.currentIndexChanged.connect(self._on_dist_changed)
        self.radio_view_single.toggled.connect(self._sync_ui_state)
        self.radio_view_prob.toggled.connect(self._sync_ui_state)
        self.radio_by_prob.toggled.connect(self._sync_ui_state)
        self.radio_by_x.toggled.connect(self._sync_ui_state)
        self.radio_right.toggled.connect(self._sync_ui_state)
        self.radio_left.toggled.connect(self._sync_ui_state)
        self.radio_both.toggled.connect(self._sync_ui_state)
        self.radio_middle.toggled.connect(self._sync_ui_state)

        self._sync_ui_state()

    def _on_dist_changed(self, index: int):
        self.param_stack.setCurrentIndex(index)

    def _sync_ui_state(self):
        is_prob_mode = self.radio_view_prob.isChecked()
        self.shade_box.setEnabled(is_prob_mode)

        if is_prob_mode:
            by_prob = self.radio_by_prob.isChecked()
            is_single_tail = self.radio_right.isChecked() or self.radio_left.isChecked()

            self.txt_prob.setEnabled(by_prob)
            self.txt_prob.setVisible(by_prob)

            self.txt_x.setEnabled(not by_prob and is_single_tail)
            self.txt_x.setVisible(not by_prob and is_single_tail)

            self.txt_x_low.setEnabled(not by_prob and not is_single_tail)
            self.txt_x_low.setVisible(not by_prob and not is_single_tail)
            self.txt_x_high.setEnabled(not by_prob and not is_single_tail)
            self.txt_x_high.setVisible(not by_prob and not is_single_tail)

    def settings(self) -> Dict[str, Any]:
        """Extract and validate dialog settings."""
        dist_name = self.cbo_dist.currentText()
        editors = self.param_editors.get(dist_name, {})
        params: Dict[str, float] = {}

        for k, edit in editors.items():
            val_text = edit.text().strip()
            try:
                params[k] = float(val_text)
            except ValueError:
                raise ValueError(f"Invalid numeric value for parameter '{k}': {val_text}")

        mode = 'probability' if self.radio_view_prob.isChecked() else 'single'

        if self.radio_right.isChecked():
            tail = 'right'
        elif self.radio_left.isChecked():
            tail = 'left'
        elif self.radio_middle.isChecked():
            tail = 'middle'
        else:
            tail = 'both'

        shade_by = 'probability' if self.radio_by_prob.isChecked() else 'x_value'

        try:
            prob_val = float(self.txt_prob.text().strip())
        except ValueError:
            prob_val = 0.05

        x_val = None
        if self.txt_x.text().strip():
            try:
                x_val = float(self.txt_x.text().strip())
            except ValueError:
                x_val = None

        x_low = None
        if self.txt_x_low.text().strip():
            try:
                x_low = float(self.txt_x_low.text().strip())
            except ValueError:
                x_low = None

        x_high = None
        if self.txt_x_high.text().strip():
            try:
                x_high = float(self.txt_x_high.text().strip())
            except ValueError:
                x_high = None

        return {
            'distribution': dist_name,
            'parameters': params,
            'mode': mode,
            'shade_by': shade_by,
            'tail': tail,
            'prob_value': prob_val,
            'x_value': x_val,
            'x_low': x_low,
            'x_high': x_high,
        }
