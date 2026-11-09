"""Qt Dialogs for Acceptance Sampling by Attributes matching Minitab standard."""
from __future__ import annotations

from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class AcceptanceSamplingDialog(QDialog):
    """Main Acceptance Sampling by Attributes dialog matching Minitab standard."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Acceptance Sampling by Attributes")
        self.setMinimumSize(480, 440)
        self.resize(480, 440)
        self.setSizeGripEnabled(True)

        self.result_params: Optional[Dict[str, Any]] = None
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Plan mode: Create vs Compare
        mode_box = QGroupBox("Sampling Plan Mode")
        mode_lay = QVBoxLayout(mode_box)
        self.rb_create = QRadioButton("Create a sampling plan")
        self.rb_create.setChecked(True)
        self.rb_create.toggled.connect(self._on_mode_toggled)
        self.rb_compare = QRadioButton("Compare user-specified sampling plan")
        mode_lay.addWidget(self.rb_create)
        mode_lay.addWidget(self.rb_compare)
        main_layout.addWidget(mode_box)

        # Measurement type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Measurement type:"))
        self.combo_type = QComboBox()
        self.combo_type.addItem("Go / no go (defective parts)", "defective")
        self.combo_type.addItem("Number of defects", "defect")
        type_layout.addWidget(self.combo_type)
        type_layout.addStretch()
        main_layout.addLayout(type_layout)

        # Quality Levels Form
        self.qual_box = QGroupBox("Quality Levels and Risks (Percent Defective)")
        form = QFormLayout(self.qual_box)

        self.edit_aql = QLineEdit("1.0")
        form.addRow("Acceptable Quality Level (&AQL, %):", self.edit_aql)

        self.edit_alpha = QLineEdit("0.05")
        form.addRow("Producer's risk (&Alpha):", self.edit_alpha)

        self.edit_rql = QLineEdit("5.0")
        form.addRow("Rejectable Quality Level (&RQL / LTPD, %):", self.edit_rql)

        self.edit_beta = QLineEdit("0.10")
        form.addRow("Consumer's risk (&Beta):", self.edit_beta)

        self.edit_lot = QLineEdit("")
        self.edit_lot.setPlaceholderText("Optional (e.g. 5000; blank = infinite)")
        form.addRow("&Lot size (optional):", self.edit_lot)

        main_layout.addWidget(self.qual_box)

        # User-specified Plan Form (enabled only in compare mode)
        self.user_box = QGroupBox("User Sampling Plan Parameters")
        u_form = QFormLayout(self.user_box)
        self.edit_user_n = QLineEdit("50")
        u_form.addRow("Sample si&ze (n):", self.edit_user_n)
        self.edit_user_c = QLineEdit("1")
        u_form.addRow("Acceptance &number (c):", self.edit_user_c)
        self.user_box.setEnabled(False)
        main_layout.addWidget(self.user_box)

        main_layout.addStretch()

        # Dialog Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        main_layout.addWidget(btns)

    def _on_mode_toggled(self, checked: bool):
        self.qual_box.setEnabled(checked)
        self.user_box.setEnabled(not checked)

    def _on_ok(self):
        try:
            aql_pct = float(self.edit_aql.text().strip())
            rql_pct = float(self.edit_rql.text().strip())
            alpha = float(self.edit_alpha.text().strip())
            beta = float(self.edit_beta.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numeric quality levels and risks.")
            return

        if aql_pct <= 0 or aql_pct >= 100:
            QMessageBox.warning(self, "Invalid AQL", "AQL percent must be between 0 and 100%.")
            return
        if rql_pct <= aql_pct or rql_pct >= 100:
            QMessageBox.warning(self, "Invalid RQL", "RQL percent must be greater than AQL and less than 100%.")
            return
        if alpha <= 0 or alpha >= 1:
            QMessageBox.warning(self, "Invalid Alpha", "Alpha (Producer's risk) must be between 0 and 1.")
            return
        if beta <= 0 or beta >= 1:
            QMessageBox.warning(self, "Invalid Beta", "Beta (Consumer's risk) must be between 0 and 1.")
            return

        lot_size = None
        lot_txt = self.edit_lot.text().strip()
        if lot_txt:
            try:
                lot_size = int(lot_txt)
                if lot_size <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self, "Invalid Lot Size", "Lot size must be a positive integer.")
                return

        user_n = None
        user_c = None
        if self.rb_compare.isChecked():
            try:
                user_n = int(self.edit_user_n.text().strip())
                user_c = int(self.edit_user_c.text().strip())
                if user_n <= 0 or user_c < 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self, "Invalid User Plan", "Sample size n must be positive and acceptance number c non-negative.")
                return

        settings = {
            "aql": aql_pct / 100.0,
            "rql": rql_pct / 100.0,
            "alpha": alpha,
            "beta": beta,
            "lot_size": lot_size,
            "measurement_type": self.combo_type.currentData(),
            "user_n": user_n,
            "user_c": user_c,
        }

        self.result_params = {"settings": settings}
        self.accept()
