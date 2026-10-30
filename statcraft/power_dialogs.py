"""Qt Dialogs for Power and Sample Size with authentic StatCraft parity."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def _parse_float_list(text: str) -> List[float]:
    parts = text.replace(",", " ").split()
    res = []
    for p in parts:
        try:
            f = float(p)
            res.append(f)
        except (ValueError, TypeError):
            continue
    return res


def _parse_int_list(text: str) -> List[int]:
    parts = text.replace(",", " ").split()
    res = []
    for p in parts:
        try:
            i = int(round(float(p)))
            if i > 0:
                res.append(i)
        except (ValueError, TypeError):
            continue
    return res


# ==============================================================================
# 1. 1-SAMPLE Z POWER DIALOG
# ==============================================================================

class OneSampleZPowerDialog(QDialog):
    """Dialog for 1-Sample Z Power and Sample Size."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Power and Sample Size for 1-Sample Z")
        self.resize(460, 360)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Calculation mode
        self.radio_calc_ss = QRadioButton("Calculate sample sizes")
        self.radio_calc_ss.setChecked(True)
        self.radio_calc_pow = QRadioButton("Calculate power")
        btn_grp = QButtonGroup(self)
        btn_grp.addButton(self.radio_calc_ss)
        btn_grp.addButton(self.radio_calc_pow)

        mode_box = QHBoxLayout()
        mode_box.addWidget(self.radio_calc_ss)
        mode_box.addWidget(self.radio_calc_pow)
        form.addRow("Compute:", mode_box)

        self.edit_diffs = QLineEdit("1.0")
        form.addRow("Differences:", self.edit_diffs)

        self.edit_sample_sizes = QLineEdit("")
        form.addRow("Sample sizes:", self.edit_sample_sizes)

        self.edit_target_powers = QLineEdit("0.8 0.9")
        form.addRow("Target power values:", self.edit_target_powers)

        self.spin_sigma = QDoubleSpinBox()
        self.spin_sigma.setRange(0.0001, 1e6)
        self.spin_sigma.setValue(1.0)
        form.addRow("Standard deviation:", self.spin_sigma)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.001, 0.499)
        self.spin_alpha.setDecimals(3)
        self.spin_alpha.setValue(0.05)
        form.addRow("Significance level (alpha):", self.spin_alpha)

        self.combo_alt = QComboBox()
        self.combo_alt.addItems(["Two-sided", "Greater than", "Less than"])
        form.addRow("Alternative hypothesis:", self.combo_alt)

        layout.addLayout(form)
        layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.radio_calc_ss.toggled.connect(self._on_mode_changed)
        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        calc_ss = self.radio_calc_ss.isChecked()
        self.edit_sample_sizes.setEnabled(not calc_ss)
        self.edit_target_powers.setEnabled(calc_ss)

    def _validate_and_accept(self) -> None:
        diffs = _parse_float_list(self.edit_diffs.text())
        if not diffs:
            QMessageBox.warning(self, "Invalid Input", "Please enter at least one difference value.")
            return

        calc_ss = self.radio_calc_ss.isChecked()
        if calc_ss:
            tps = _parse_float_list(self.edit_target_powers.text())
            if not tps:
                QMessageBox.warning(self, "Invalid Input", "Please enter at least one target power (0 to 1).")
                return
            ss = None
        else:
            ss = _parse_int_list(self.edit_sample_sizes.text())
            if not ss:
                QMessageBox.warning(self, "Invalid Input", "Please enter at least one sample size.")
                return
            tps = None

        self.settings = {
            "differences": diffs,
            "sample_sizes": ss,
            "target_powers": tps,
            "sigma": self.spin_sigma.value(),
            "alpha": self.spin_alpha.value(),
            "alternative": self.combo_alt.currentText().lower().replace(" ", "_"),
        }
        self.accept()


# ==============================================================================
# 2. 1-SAMPLE T POWER DIALOG
# ==============================================================================

class OneSampleTPowerDialog(OneSampleZPowerDialog):
    """Dialog for 1-Sample t Power and Sample Size."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(settings, parent)
        self.setWindowTitle("Power and Sample Size for 1-Sample t")


# ==============================================================================
# 3. 2-SAMPLE T POWER DIALOG
# ==============================================================================

class TwoSampleTPowerDialog(OneSampleZPowerDialog):
    """Dialog for 2-Sample t Power and Sample Size."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(settings, parent)
        self.setWindowTitle("Power and Sample Size for 2-Sample t")


# ==============================================================================
# 4. PAIRED T POWER DIALOG
# ==============================================================================

class PairedTPowerDialog(OneSampleZPowerDialog):
    """Dialog for Paired t Power and Sample Size."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(settings, parent)
        self.setWindowTitle("Power and Sample Size for Paired t")


# ==============================================================================
# 5. 1 PROPORTION POWER DIALOG
# ==============================================================================

class OneProportionPowerDialog(QDialog):
    """Dialog for 1 Proportion Power and Sample Size."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Power and Sample Size for 1 Proportion")
        self.resize(460, 360)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.radio_calc_ss = QRadioButton("Calculate sample sizes")
        self.radio_calc_ss.setChecked(True)
        self.radio_calc_pow = QRadioButton("Calculate power")
        btn_grp = QButtonGroup(self)
        btn_grp.addButton(self.radio_calc_ss)
        btn_grp.addButton(self.radio_calc_pow)

        mode_box = QHBoxLayout()
        mode_box.addWidget(self.radio_calc_ss)
        mode_box.addWidget(self.radio_calc_pow)
        form.addRow("Compute:", mode_box)

        self.edit_props = QLineEdit("0.6 0.7")
        form.addRow("Comparison proportions:", self.edit_props)

        self.edit_sample_sizes = QLineEdit("")
        form.addRow("Sample sizes:", self.edit_sample_sizes)

        self.edit_target_powers = QLineEdit("0.8 0.9")
        form.addRow("Target power values:", self.edit_target_powers)

        self.spin_p0 = QDoubleSpinBox()
        self.spin_p0.setRange(0.001, 0.999)
        self.spin_p0.setValue(0.5)
        form.addRow("Baseline proportion (p0):", self.spin_p0)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.001, 0.499)
        self.spin_alpha.setDecimals(3)
        self.spin_alpha.setValue(0.05)
        form.addRow("Significance level (alpha):", self.spin_alpha)

        self.combo_alt = QComboBox()
        self.combo_alt.addItems(["Two-sided", "Greater than", "Less than"])
        form.addRow("Alternative hypothesis:", self.combo_alt)

        layout.addLayout(form)
        layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.radio_calc_ss.toggled.connect(self._on_mode_changed)
        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        calc_ss = self.radio_calc_ss.isChecked()
        self.edit_sample_sizes.setEnabled(not calc_ss)
        self.edit_target_powers.setEnabled(calc_ss)

    def _validate_and_accept(self) -> None:
        props = _parse_float_list(self.edit_props.text())
        if not props or any(not (0.0 < p < 1.0) for p in props):
            QMessageBox.warning(self, "Invalid Input", "Please enter valid comparison proportions between 0 and 1.")
            return

        calc_ss = self.radio_calc_ss.isChecked()
        if calc_ss:
            tps = _parse_float_list(self.edit_target_powers.text())
            if not tps:
                QMessageBox.warning(self, "Invalid Input", "Please enter at least one target power (0 to 1).")
                return
            ss = None
        else:
            ss = _parse_int_list(self.edit_sample_sizes.text())
            if not ss:
                QMessageBox.warning(self, "Invalid Input", "Please enter at least one sample size.")
                return
            tps = None

        self.settings = {
            "comparison_proportions": props,
            "baseline_p0": self.spin_p0.value(),
            "sample_sizes": ss,
            "target_powers": tps,
            "alpha": self.spin_alpha.value(),
            "alternative": self.combo_alt.currentText().lower().replace(" ", "_"),
        }
        self.accept()


# ==============================================================================
# 6. 2 PROPORTIONS POWER DIALOG
# ==============================================================================

class TwoProportionsPowerDialog(QDialog):
    """Dialog for 2 Proportions Power and Sample Size."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Power and Sample Size for 2 Proportions")
        self.resize(460, 360)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.radio_calc_ss = QRadioButton("Calculate sample sizes")
        self.radio_calc_ss.setChecked(True)
        self.radio_calc_pow = QRadioButton("Calculate power")
        btn_grp = QButtonGroup(self)
        btn_grp.addButton(self.radio_calc_ss)
        btn_grp.addButton(self.radio_calc_pow)

        mode_box = QHBoxLayout()
        mode_box.addWidget(self.radio_calc_ss)
        mode_box.addWidget(self.radio_calc_pow)
        form.addRow("Compute:", mode_box)

        self.edit_p1 = QLineEdit("0.6 0.7")
        form.addRow("Proportion 1 values:", self.edit_p1)

        self.spin_p2 = QDoubleSpinBox()
        self.spin_p2.setRange(0.001, 0.999)
        self.spin_p2.setValue(0.5)
        form.addRow("Comparison proportion 2:", self.spin_p2)

        self.edit_sample_sizes = QLineEdit("")
        form.addRow("Sample sizes (per group):", self.edit_sample_sizes)

        self.edit_target_powers = QLineEdit("0.8 0.9")
        form.addRow("Target power values:", self.edit_target_powers)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.001, 0.499)
        self.spin_alpha.setDecimals(3)
        self.spin_alpha.setValue(0.05)
        form.addRow("Significance level (alpha):", self.spin_alpha)

        self.combo_alt = QComboBox()
        self.combo_alt.addItems(["Two-sided", "Greater than", "Less than"])
        form.addRow("Alternative hypothesis:", self.combo_alt)

        layout.addLayout(form)
        layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.radio_calc_ss.toggled.connect(self._on_mode_changed)
        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        calc_ss = self.radio_calc_ss.isChecked()
        self.edit_sample_sizes.setEnabled(not calc_ss)
        self.edit_target_powers.setEnabled(calc_ss)

    def _validate_and_accept(self) -> None:
        props1 = _parse_float_list(self.edit_p1.text())
        if not props1 or any(not (0.0 < p < 1.0) for p in props1):
            QMessageBox.warning(self, "Invalid Input", "Please enter valid Proportion 1 values between 0 and 1.")
            return

        calc_ss = self.radio_calc_ss.isChecked()
        if calc_ss:
            tps = _parse_float_list(self.edit_target_powers.text())
            if not tps:
                QMessageBox.warning(self, "Invalid Input", "Please enter at least one target power (0 to 1).")
                return
            ss = None
        else:
            ss = _parse_int_list(self.edit_sample_sizes.text())
            if not ss:
                QMessageBox.warning(self, "Invalid Input", "Please enter at least one sample size.")
                return
            tps = None

        self.settings = {
            "p1_values": props1,
            "p2": self.spin_p2.value(),
            "sample_sizes": ss,
            "target_powers": tps,
            "alpha": self.spin_alpha.value(),
            "alternative": self.combo_alt.currentText().lower().replace(" ", "_"),
        }
        self.accept()


# ==============================================================================
# 7. ONE-WAY ANOVA POWER DIALOG
# ==============================================================================

class OneWayAnovaPowerDialog(QDialog):
    """Dialog for One-Way ANOVA Power and Sample Size."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Power and Sample Size for One-Way ANOVA")
        self.resize(460, 360)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.radio_calc_ss = QRadioButton("Calculate sample sizes")
        self.radio_calc_ss.setChecked(True)
        self.radio_calc_pow = QRadioButton("Calculate power")
        btn_grp = QButtonGroup(self)
        btn_grp.addButton(self.radio_calc_ss)
        btn_grp.addButton(self.radio_calc_pow)

        mode_box = QHBoxLayout()
        mode_box.addWidget(self.radio_calc_ss)
        mode_box.addWidget(self.radio_calc_pow)
        form.addRow("Compute:", mode_box)

        self.spin_levels = QSpinBox()
        self.spin_levels.setRange(2, 50)
        self.spin_levels.setValue(3)
        form.addRow("Number of levels:", self.spin_levels)

        self.edit_max_diffs = QLineEdit("1.0 1.5")
        form.addRow("Maximum differences:", self.edit_max_diffs)

        self.edit_sample_sizes = QLineEdit("")
        form.addRow("Sample sizes (per level):", self.edit_sample_sizes)

        self.edit_target_powers = QLineEdit("0.8 0.9")
        form.addRow("Target power values:", self.edit_target_powers)

        self.spin_sigma = QDoubleSpinBox()
        self.spin_sigma.setRange(0.0001, 1e6)
        self.spin_sigma.setValue(1.0)
        form.addRow("Standard deviation:", self.spin_sigma)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.001, 0.499)
        self.spin_alpha.setDecimals(3)
        self.spin_alpha.setValue(0.05)
        form.addRow("Significance level (alpha):", self.spin_alpha)

        layout.addLayout(form)
        layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.radio_calc_ss.toggled.connect(self._on_mode_changed)
        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        calc_ss = self.radio_calc_ss.isChecked()
        self.edit_sample_sizes.setEnabled(not calc_ss)
        self.edit_target_powers.setEnabled(calc_ss)

    def _validate_and_accept(self) -> None:
        diffs = _parse_float_list(self.edit_max_diffs.text())
        if not diffs:
            QMessageBox.warning(self, "Invalid Input", "Please enter at least one maximum difference value.")
            return

        calc_ss = self.radio_calc_ss.isChecked()
        if calc_ss:
            tps = _parse_float_list(self.edit_target_powers.text())
            if not tps:
                QMessageBox.warning(self, "Invalid Input", "Please enter at least one target power (0 to 1).")
                return
            ss = None
        else:
            ss = _parse_int_list(self.edit_sample_sizes.text())
            if not ss:
                QMessageBox.warning(self, "Invalid Input", "Please enter at least one sample size.")
                return
            tps = None

        self.settings = {
            "levels": self.spin_levels.value(),
            "max_differences": diffs,
            "sample_sizes": ss,
            "target_powers": tps,
            "sigma": self.spin_sigma.value(),
            "alpha": self.spin_alpha.value(),
        }
        self.accept()


# ==============================================================================
# 8. 2-LEVEL FACTORIAL POWER DIALOG
# ==============================================================================

class FactorialPowerDialog(QDialog):
    """Dialog for 2-Level Factorial Power and Sample Size."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Power and Sample Size for 2-Level Factorial Design")
        self.resize(460, 360)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.radio_calc_ss = QRadioButton("Calculate replicates")
        self.radio_calc_ss.setChecked(True)
        self.radio_calc_pow = QRadioButton("Calculate power")
        btn_grp = QButtonGroup(self)
        btn_grp.addButton(self.radio_calc_ss)
        btn_grp.addButton(self.radio_calc_pow)

        mode_box = QHBoxLayout()
        mode_box.addWidget(self.radio_calc_ss)
        mode_box.addWidget(self.radio_calc_pow)
        form.addRow("Compute:", mode_box)

        self.spin_factors = QSpinBox()
        self.spin_factors.setRange(2, 15)
        self.spin_factors.setValue(3)
        form.addRow("Number of factors:", self.spin_factors)

        self.spin_corners = QSpinBox()
        self.spin_corners.setRange(4, 128)
        self.spin_corners.setValue(8)
        form.addRow("Corner points:", self.spin_corners)

        self.edit_effects = QLineEdit("1.0 2.0")
        form.addRow("Effects to detect:", self.edit_effects)

        self.edit_replicates = QLineEdit("")
        form.addRow("Number of replicates:", self.edit_replicates)

        self.edit_target_powers = QLineEdit("0.8 0.9")
        form.addRow("Target power values:", self.edit_target_powers)

        self.spin_centers = QSpinBox()
        self.spin_centers.setRange(0, 50)
        self.spin_centers.setValue(0)
        form.addRow("Center points:", self.spin_centers)

        self.spin_sigma = QDoubleSpinBox()
        self.spin_sigma.setRange(0.0001, 1e6)
        self.spin_sigma.setValue(1.0)
        form.addRow("Standard deviation:", self.spin_sigma)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.001, 0.499)
        self.spin_alpha.setDecimals(3)
        self.spin_alpha.setValue(0.05)
        form.addRow("Significance level (alpha):", self.spin_alpha)

        layout.addLayout(form)
        layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.radio_calc_ss.toggled.connect(self._on_mode_changed)
        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        calc_ss = self.radio_calc_ss.isChecked()
        self.edit_replicates.setEnabled(not calc_ss)
        self.edit_target_powers.setEnabled(calc_ss)

    def _validate_and_accept(self) -> None:
        effects = _parse_float_list(self.edit_effects.text())
        if not effects:
            QMessageBox.warning(self, "Invalid Input", "Please enter at least one effect value.")
            return

        calc_ss = self.radio_calc_ss.isChecked()
        if calc_ss:
            tps = _parse_float_list(self.edit_target_powers.text())
            if not tps:
                QMessageBox.warning(self, "Invalid Input", "Please enter at least one target power (0 to 1).")
                return
            reps = None
        else:
            reps = _parse_int_list(self.edit_replicates.text())
            if not reps:
                QMessageBox.warning(self, "Invalid Input", "Please enter at least one number of replicates.")
                return
            tps = None

        self.settings = {
            "factors": self.spin_factors.value(),
            "corner_points": self.spin_corners.value(),
            "effects": effects,
            "replicates": reps,
            "target_powers": tps,
            "center_points": self.spin_centers.value(),
            "sigma": self.spin_sigma.value(),
            "alpha": self.spin_alpha.value(),
        }
        self.accept()
