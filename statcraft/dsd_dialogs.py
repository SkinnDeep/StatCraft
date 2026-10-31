"""Interactive Qt dialogs for Definitive Screening Designs (DSD).

Provides:
- CreateDefinitiveScreeningDesignDialog (Stat > DOE > Screening > Create Definitive Screening Design...)
- AnalyzeDefinitiveScreeningDesignDialog (Stat > DOE > Screening > Analyze Definitive Screening Design...)
"""
from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .dsd import _CONFERENCE_CATALOG
from .variable_dialogs import ProcedureDialog, format_variable_list


class CreateDefinitiveScreeningDesignDialog(QDialog):
    """Dialog to create a Definitive Screening Design (Jones & Nachtsheim 2011/2013)."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Create Definitive Screening Design")
        self.resize(720, 520)

        self.factors: List[Dict[str, Any]] = [
            {"name": f"Factor {chr(65 + i)}", "type": "continuous", "low": -1.0, "high": 1.0, "mid": 0.0}
            for i in range(6)
        ]
        self.parameters: Optional[Dict[str, Any]] = None

        layout = QVBoxLayout(self)

        top_group = QGroupBox("Design Setup")
        form = QFormLayout(top_group)

        self.factor_count = QSpinBox()
        self.factor_count.setRange(3, 24)
        self.factor_count.setValue(6)
        self.factor_count.valueChanged.connect(self._on_factor_count_changed)
        form.addRow("Number of factors (3 to 24):", self.factor_count)

        self.extra_centers = QSpinBox()
        self.extra_centers.setRange(0, 10)
        self.extra_centers.setValue(0)
        self.extra_centers.valueChanged.connect(self._update_run_summary)
        form.addRow("Extra center points:", self.extra_centers)

        self.replicates = QSpinBox()
        self.replicates.setRange(1, 5)
        self.replicates.setValue(1)
        self.replicates.valueChanged.connect(self._update_run_summary)
        form.addRow("Number of replicates:", self.replicates)

        self.randomize = QCheckBox("Randomize run order")
        self.randomize.setChecked(True)
        form.addRow("", self.randomize)

        self.seed = QSpinBox()
        self.seed.setRange(1, 2147483647)
        self.seed.setValue(1)
        form.addRow("Random seed:", self.seed)

        self.ws_name = QLineEdit("Definitive Screening Design")
        form.addRow("Worksheet name:", self.ws_name)

        layout.addWidget(top_group)

        # Factor table
        factor_group = QGroupBox("Factors Settings")
        factor_layout = QVBoxLayout(factor_group)

        self.factor_table = QTableWidget(6, 4)
        self.factor_table.setHorizontalHeaderLabels(["Name", "Type", "Low", "High"])
        self.factor_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        factor_layout.addWidget(self.factor_table)
        layout.addWidget(factor_group)

        # Run Summary Box
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("color: #0061a8; font-weight: bold; padding: 4px;")
        layout.addWidget(self.summary_label)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._populate_factor_table()
        self._update_run_summary()

    def _on_factor_count_changed(self, count: int):
        while len(self.factors) < count:
            idx = len(self.factors)
            name = f"Factor {chr(65 + (idx % 26))}" + (f"_{idx // 26}" if idx >= 26 else "")
            self.factors.append({"name": name, "type": "continuous", "low": -1.0, "high": 1.0, "mid": 0.0})
        while len(self.factors) > count:
            self.factors.pop()

        self._populate_factor_table()
        self._update_run_summary()

    def _populate_factor_table(self):
        self.factor_table.setRowCount(len(self.factors))
        for row, f in enumerate(self.factors):
            # Name
            self.factor_table.setItem(row, 0, QTableWidgetItem(f["name"]))

            # Type combo
            combo = QComboBox()
            combo.addItems(["Continuous", "2-Level Categorical"])
            combo.setCurrentIndex(0 if f["type"] == "continuous" else 1)
            combo.currentIndexChanged.connect(lambda idx, r=row: self._on_type_changed(r, idx))
            self.factor_table.setCellWidget(row, 1, combo)

            # Low / High
            self.factor_table.setItem(row, 2, QTableWidgetItem(str(f["low"])))
            self.factor_table.setItem(row, 3, QTableWidgetItem(str(f["high"])))

    def _on_type_changed(self, row: int, combo_idx: int):
        is_cat = (combo_idx == 1)
        self.factors[row]["type"] = "categorical" if is_cat else "continuous"
        if is_cat:
            self.factor_table.setItem(row, 2, QTableWidgetItem("-1"))
            self.factor_table.setItem(row, 3, QTableWidgetItem("1"))

    def _update_run_summary(self):
        k = self.factor_count.value()
        avail = sorted([m for m in _CONFERENCE_CATALOG if m >= k])
        m = avail[0] if avail else k
        extra_c = self.extra_centers.value()
        reps = self.replicates.value()
        runs_per_rep = 2 * m + 1 + extra_c
        total_runs = runs_per_rep * reps
        self.summary_label.setText(
            f"Summary: {k} factors, {runs_per_rep} runs per replicate ({1 + extra_c} center points), "
            f"{total_runs} total runs across {reps} replicate(s)."
        )

    def _validate_and_accept(self):
        updated_factors = []
        for row in range(self.factor_table.rowCount()):
            name_item = self.factor_table.item(row, 0)
            fname = name_item.text().strip() if name_item else f"X{row + 1}"

            combo = self.factor_table.cellWidget(row, 1)
            ftype = "categorical" if combo and combo.currentIndex() == 1 else "continuous"

            low_item = self.factor_table.item(row, 2)
            high_item = self.factor_table.item(row, 3)

            low_str = low_item.text().strip() if low_item else "-1"
            high_str = high_item.text().strip() if high_item else "1"

            if ftype == "continuous":
                try:
                    low_val = float(low_str)
                    high_val = float(high_str)
                except ValueError:
                    QMessageBox.warning(self, "Invalid Setting", f"Factor '{fname}' low and high settings must be numeric.")
                    return
                if low_val >= high_val:
                    QMessageBox.warning(self, "Invalid Setting", f"Factor '{fname}' low setting must be less than high setting.")
                    return
                mid_val = (low_val + high_val) / 2.0
            else:
                try:
                    low_val = float(low_str)
                    high_val = float(high_str)
                except ValueError:
                    low_val = low_str
                    high_val = high_str
                mid_val = None

            updated_factors.append({
                "name": fname,
                "type": ftype,
                "low": low_val,
                "high": high_val,
                "mid": mid_val,
            })

        self.parameters = {
            "factors": updated_factors,
            "replicates": self.replicates.value(),
            "extra_centers": self.extra_centers.value(),
            "randomize": self.randomize.isChecked(),
            "seed": self.seed.value(),
            "name": self.ws_name.text().strip() or "Definitive Screening Design",
        }
        self.accept()


class AnalyzeDefinitiveScreeningDesignDialog(ProcedureDialog):
    """Procedure dialog to fit and analyze a Definitive Screening Design."""

    def __init__(self, worksheet, parent: Optional[QWidget] = None):
        super().__init__(
            parent,
            "Analyze Definitive Screening Design",
            worksheet,
            selectors=(
                {"key": "response_index", "label": "Response:"},
                {"key": "factor_indices", "label": "Factors:", "multiple": True, "minimum": 2, "optional": True},
            ),
            fields=(
                {
                    "key": "selection",
                    "label": "Model selection:",
                    "choices": ["Stepwise (Heredity)", "Main effects only", "Full model"],
                    "default": "Stepwise (Heredity)",
                },
                {"key": "alpha_enter", "label": "Alpha-to-enter (α):", "numeric": True, "default": 0.10},
                {"key": "alpha_leave", "label": "Alpha-to-leave (α):", "numeric": True, "default": 0.10},
                {"key": "confidence", "label": "Confidence level (%):", "numeric": True, "default": 95.0},
                {"key": "show_pareto", "label": "", "boolean": True, "text": "Pareto chart of standardized effects", "default": True},
            ),
            note=(
                "Fits a screening regression model with orthogonal main effects. "
                "Stepwise selection evaluates 2-factor interactions and quadratic curvature terms "
                "using hereditary principles (Jones & Nachtsheim, 2011)."
            ),
        )

        # Auto-populate factors if this worksheet is a DSD
        metadata = worksheet.metadata.get("doe", {})
        if metadata.get("design") == "definitive_screening" and "factors" in metadata:
            f_indices = [
                f["column_index"]
                for f in metadata["factors"]
                if 0 <= f.get("column_index", -1) < len(worksheet.columns)
            ]
            if f_indices:
                self.controls["factor_indices"].setText(format_variable_list(f_indices, worksheet))

    def values(self) -> Dict[str, Any]:
        vals = super().values()
        sel_map = {
            "Stepwise (Heredity)": "stepwise",
            "Main effects only": "main_effects",
            "Full model": "full",
        }
        vals["selection"] = sel_map.get(vals.get("selection"), "stepwise")
        if vals.get("factor_indices") and vals["response_index"] in vals["factor_indices"]:
            raise ValueError("Response column cannot also be a factor.")
        return vals
