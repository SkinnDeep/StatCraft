"""Qt Dialog for Acceptance Sampling by Variables with native Minitab fidelity."""
from __future__ import annotations

from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class AcceptanceSamplingVariablesDialog(QDialog):
    """Minitab Acceptance Sampling by Variables Dialog."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Acceptance Sampling by Variables")
        self.resize(540, 480)
        self.settings: Optional[Dict[str, Any]] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Specifications group
        grp_specs = QGroupBox("Specification Limits")
        form_specs = QFormLayout(grp_specs)

        self.combo_spec_type = QComboBox()
        self.combo_spec_type.addItems(["Lower specification limit only", "Upper specification limit only", "Both specification limits"])
        form_specs.addRow("Specification type:", self.combo_spec_type)

        self.edit_lsl = QLineEdit("10.0")
        self.edit_usl = QLineEdit("20.0")
        self.edit_usl.setEnabled(False)
        self.combo_spec_type.currentIndexChanged.connect(self._on_spec_type_changed)

        form_specs.addRow("Lower specification limit (LSL):", self.edit_lsl)
        form_specs.addRow("Upper specification limit (USL):", self.edit_usl)
        layout.addWidget(grp_specs)

        # Standard deviation group
        grp_sd = QGroupBox("Standard Deviation")
        lay_sd = QVBoxLayout(grp_sd)
        self.rb_sd_unknown = QRadioButton("Unknown (estimate using sample standard deviation s)")
        self.rb_sd_unknown.setChecked(True)
        self.rb_sd_known = QRadioButton("Historical / Known standard deviation:")

        h_known = QHBoxLayout()
        self.edit_sigma = QLineEdit("1.0")
        self.edit_sigma.setEnabled(False)
        self.rb_sd_known.toggled.connect(self.edit_sigma.setEnabled)
        h_known.addWidget(self.rb_sd_known)
        h_known.addWidget(self.edit_sigma)

        lay_sd.addWidget(self.rb_sd_unknown)
        lay_sd.addLayout(h_known)
        layout.addWidget(grp_sd)

        # Quality levels & risks
        grp_quality = QGroupBox("Quality Levels and Risks (Percent Defective)")
        form_qual = QFormLayout(grp_quality)

        self.spin_aql = QDoubleSpinBox()
        self.spin_aql.setRange(0.001, 50.0)
        self.spin_aql.setValue(1.5)
        self.spin_aql.setSuffix(" %")
        form_qual.addRow("Acceptable Quality Level (AQL):", self.spin_aql)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.001, 0.499)
        self.spin_alpha.setValue(0.05)
        self.spin_alpha.setSingleStep(0.01)
        form_qual.addRow("Producer's Risk (Alpha):", self.spin_alpha)

        self.spin_rql = QDoubleSpinBox()
        self.spin_rql.setRange(0.001, 50.0)
        self.spin_rql.setValue(5.0)
        self.spin_rql.setSuffix(" %")
        form_qual.addRow("Rejectable Quality Level (RQL / LTPD):", self.spin_rql)

        self.spin_beta = QDoubleSpinBox()
        self.spin_beta.setRange(0.001, 0.499)
        self.spin_beta.setValue(0.10)
        self.spin_beta.setSingleStep(0.01)
        form_qual.addRow("Consumer's Risk (Beta):", self.spin_beta)

        self.edit_lot_size = QLineEdit("1000")
        form_qual.addRow("Lot size (optional):", self.edit_lot_size)

        layout.addWidget(grp_quality)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_spec_type_changed(self, idx: int):
        # 0: Lower only, 1: Upper only, 2: Both
        self.edit_lsl.setEnabled(idx in (0, 2))
        self.edit_usl.setEnabled(idx in (1, 2))

    def _on_accept(self):
        idx = self.combo_spec_type.currentIndex()
        lsl_val = None
        usl_val = None
        try:
            if idx in (0, 2):
                lsl_val = float(self.edit_lsl.text().strip())
            if idx in (1, 2):
                usl_val = float(self.edit_usl.text().strip())
            if idx == 2 and lsl_val >= usl_val:
                QMessageBox.warning(self, "Acceptance Sampling", "LSL must be strictly less than USL.")
                return
        except ValueError:
            QMessageBox.warning(self, "Acceptance Sampling", "Enter valid numeric specification limits.")
            return

        sigma_val = None
        if self.rb_sd_known.isChecked():
            try:
                sigma_val = float(self.edit_sigma.text().strip())
                if sigma_val <= 0:
                    raise ValueError()
            except ValueError:
                QMessageBox.warning(self, "Acceptance Sampling", "Historical standard deviation must be positive.")
                return

        aql_pct = self.spin_aql.value()
        rql_pct = self.spin_rql.value()
        if aql_pct >= rql_pct:
            QMessageBox.warning(self, "Acceptance Sampling", "AQL must be strictly less than RQL.")
            return

        lot_size = None
        lot_txt = self.edit_lot_size.text().strip()
        if lot_txt:
            try:
                lot_size = int(lot_txt)
                if lot_size < 1:
                    raise ValueError()
            except ValueError:
                QMessageBox.warning(self, "Acceptance Sampling", "Lot size must be a positive integer.")
                return

        self.settings = {
            "lsl": lsl_val,
            "usl": usl_val,
            "sigma": sigma_val,
            "aql": aql_pct / 100.0,
            "rql": rql_pct / 100.0,
            "alpha": self.spin_alpha.value(),
            "beta": self.spin_beta.value(),
            "lot_size": lot_size,
        }
        self.accept()
