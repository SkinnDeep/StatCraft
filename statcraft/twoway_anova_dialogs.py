"""Two-Way ANOVA Dialog for StatCraft."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QGroupBox, QMessageBox, QDoubleSpinBox
)


class TwoWayAnovaDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        self.setSizeGripEnabled(True)
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Two-Way Analysis of Variance")
        self.setMinimumSize(440, 360)
        self.resize(460, 380)

        main_layout = QVBoxLayout(self)

        group = QGroupBox("Variables")
        form_layout = QVBoxLayout(group)

        # 1. Response Column
        form_layout.addWidget(QLabel("Response (Continuous Numeric):"))
        self.combo_resp = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            if col.kind == 'number':
                self.combo_resp.addItem(f"C{i + 1}  {col.name}", i)
        form_layout.addWidget(self.combo_resp)

        form_layout.addSpacing(6)

        # 2. Row Factor
        form_layout.addWidget(QLabel("Row Factor:"))
        self.combo_factor_a = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            self.combo_factor_a.addItem(f"C{i + 1}  {col.name}", i)
        form_layout.addWidget(self.combo_factor_a)

        form_layout.addSpacing(6)

        # 3. Column Factor
        form_layout.addWidget(QLabel("Column Factor:"))
        self.combo_factor_b = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            self.combo_factor_b.addItem(f"C{i + 1}  {col.name}", i)
        form_layout.addWidget(self.combo_factor_b)

        # Set distinct defaults if available
        if self.combo_factor_b.count() > 1:
            self.combo_factor_b.setCurrentIndex(1)
        if self.combo_factor_b.count() > 2:
            self.combo_factor_b.setCurrentIndex(2)

        main_layout.addWidget(group)

        # Options Group
        opt_group = QGroupBox("Model & Display Options")
        opt_layout = QVBoxLayout(opt_group)

        self.chk_interaction = QCheckBox("Fit interaction (Factor A * Factor B)")
        self.chk_interaction.setChecked(True)
        opt_layout.addWidget(self.chk_interaction)

        self.chk_means = QCheckBox("Display means tables")
        self.chk_means.setChecked(True)
        opt_layout.addWidget(self.chk_means)

        ci_layout = QHBoxLayout()
        ci_layout.addWidget(QLabel("Confidence level (%):"))
        self.spin_ci = QDoubleSpinBox()
        self.spin_ci.setRange(50.0, 99.9)
        self.spin_ci.setValue(95.0)
        self.spin_ci.setDecimals(1)
        ci_layout.addWidget(self.spin_ci)
        ci_layout.addStretch()
        opt_layout.addLayout(ci_layout)

        main_layout.addWidget(opt_group)

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
        self.settings = None

    def _on_ok(self):
        resp_idx = self.combo_resp.currentData()
        fa_idx = self.combo_factor_a.currentData()
        fb_idx = self.combo_factor_b.currentData()

        if resp_idx is None or fa_idx is None or fb_idx is None:
            QMessageBox.warning(self, "Invalid Selection", "Please select valid columns for Response and both Factors.")
            return

        if len({resp_idx, fa_idx, fb_idx}) < 3:
            QMessageBox.warning(self, "Invalid Selection", "Response, Row Factor, and Column Factor must all be distinct columns.")
            return

        self.settings = {
            "response_index": resp_idx,
            "factor_a_index": fa_idx,
            "factor_b_index": fb_idx,
            "fit_interaction": self.chk_interaction.isChecked(),
            "display_means": self.chk_means.isChecked(),
            "confidence": self.spin_ci.value() / 100.0
        }
        self.accept()
