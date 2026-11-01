"""Interactive Qt dialogs for D-Optimal Custom Designs and Design Diagnostics.

Matches JMP Pro "DOE > Custom Design" and "DOE > Design Diagnostics > Evaluate Design".
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .optimal_design import FactorSpec
from .variable_dialogs import ProcedureDialog


class CreateDOptimalDesignDialog(QDialog):
    """Dialog to create a D-Optimal Custom Design with arbitrary factors and model terms."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Create D-Optimal Custom Design")
        self.resize(740, 560)

        self.factors: List[Dict[str, Any]] = [
            {"name": f"X{i+1}", "type": "continuous", "low": -1.0, "high": 1.0}
            for i in range(4)
        ]
        self.parameters: Optional[Dict[str, Any]] = None

        layout = QVBoxLayout(self)

        top_group = QGroupBox("Design Specifications")
        form = QFormLayout(top_group)

        self.factor_count = QSpinBox()
        self.factor_count.setRange(2, 12)
        self.factor_count.setValue(4)
        self.factor_count.valueChanged.connect(self._on_factor_count_changed)
        form.addRow("Number of factors (2 to 12):", self.factor_count)

        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "Main Effects + 2-Factor Interactions",
            "Main Effects Only (Linear)",
            "Full Response Surface (Quadratic)",
        ])
        self.model_combo.currentIndexChanged.connect(self._update_run_summary)
        form.addRow("Assumed model terms:", self.model_combo)

        self.run_count = QSpinBox()
        self.run_count.setRange(4, 200)
        self.run_count.setValue(16)
        form.addRow("Number of runs:", self.run_count)

        self.randomize = QCheckBox("Randomize run order")
        self.randomize.setChecked(True)
        form.addRow("", self.randomize)

        self.seed = QSpinBox()
        self.seed.setRange(1, 2147483647)
        self.seed.setValue(42)
        form.addRow("Random seed:", self.seed)

        self.ws_name = QLineEdit("Custom D-Optimal Design")
        form.addRow("Worksheet name:", self.ws_name)

        layout.addWidget(top_group)

        # Factors table
        factor_group = QGroupBox("Factors and Settings")
        factor_layout = QVBoxLayout(factor_group)

        self.factor_table = QTableWidget(4, 4)
        self.factor_table.setHorizontalHeaderLabels(["Factor Name", "Type", "Low / Level 1", "High / Level 2"])
        self.factor_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        factor_layout.addWidget(self.factor_table)
        layout.addWidget(factor_group)

        # Summary Label
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
            self.factors.append({"name": f"X{idx+1}", "type": "continuous", "low": -1.0, "high": 1.0})
        while len(self.factors) > count:
            self.factors.pop()
        self._populate_factor_table()
        self._update_run_summary()

    def _populate_factor_table(self):
        self.factor_table.setRowCount(len(self.factors))
        for r, f in enumerate(self.factors):
            # Name
            item_name = QTableWidgetItem(f["name"])
            self.factor_table.setItem(r, 0, item_name)

            # Type combo
            combo = QComboBox()
            combo.addItems(["Continuous", "2-Level Categorical"])
            combo.setCurrentIndex(0 if f["type"] == "continuous" else 1)
            combo.currentIndexChanged.connect(lambda idx, row=r: self._on_type_changed(row, idx))
            self.factor_table.setCellWidget(r, 1, combo)

            # Low & High
            item_low = QTableWidgetItem(str(f["low"]))
            item_high = QTableWidgetItem(str(f["high"]))
            self.factor_table.setItem(r, 2, item_low)
            self.factor_table.setItem(r, 3, item_high)

    def _on_type_changed(self, row: int, type_idx: int):
        if type_idx == 0:
            self.factors[row]["type"] = "continuous"
            self.factor_table.item(row, 2).setText("-1.0")
            self.factor_table.item(row, 3).setText("1.0")
        else:
            self.factors[row]["type"] = "categorical"
            self.factor_table.item(row, 2).setText("A")
            self.factor_table.item(row, 3).setText("B")

    def _update_run_summary(self):
        k = len(self.factors)
        m_idx = self.model_combo.currentIndex()
        if m_idx == 1:
            # Linear: 1 + k
            min_terms = 1 + k
        elif m_idx == 0:
            # Interactions: 1 + k + k*(k-1)//2
            min_terms = 1 + k + (k * (k - 1)) // 2
        else:
            # Full quadratic: 1 + 2k + k*(k-1)//2
            min_terms = 1 + (2 * k) + (k * (k - 1)) // 2

        rec_runs = min_terms + 4
        if self.run_count.value() < min_terms:
            self.run_count.setValue(rec_runs)

        self.summary_label.setText(
            f"Model requires at least {min_terms} runs to estimate all terms. "
            f"Recommended runs: {rec_runs} (includes 4 degrees of freedom for pure error)."
        )

    def _validate_and_accept(self):
        k = len(self.factors)
        factor_specs = []

        seen_names = set()
        for r in range(k):
            name_item = self.factor_table.item(r, 0)
            name = name_item.text().strip() if name_item else f"X{r+1}"
            if not name or name in seen_names:
                QMessageBox.warning(self, "Invalid Factor", f"Factor in row {r+1} has an empty or duplicate name.")
                return
            seen_names.add(name)

            f_type = self.factors[r]["type"]
            low_text = self.factor_table.item(r, 2).text().strip()
            high_text = self.factor_table.item(r, 3).text().strip()

            if f_type == "continuous":
                try:
                    low_val = float(low_text)
                    high_val = float(high_text)
                except ValueError:
                    QMessageBox.warning(self, "Invalid Settings", f"Factor '{name}' low/high settings must be numbers.")
                    return
                if low_val >= high_val:
                    QMessageBox.warning(self, "Invalid Settings", f"Factor '{name}' low must be strictly less than high.")
                    return
                factor_specs.append(FactorSpec(name=name, kind="continuous", low=low_val, high=high_val))
            else:
                if not low_text or not high_text or low_text == high_text:
                    QMessageBox.warning(self, "Invalid Settings", f"Factor '{name}' categorical levels must be distinct.")
                    return
                factor_specs.append(FactorSpec(name=name, kind="categorical", levels=[low_text, high_text]))

        m_idx = self.model_combo.currentIndex()
        order_map = {0: "interactions", 1: "linear", 2: "quadratic"}
        model_order = order_map.get(m_idx, "interactions")

        self.parameters = {
            "factors": factor_specs,
            "n_runs": self.run_count.value(),
            "model_order": model_order,
            "randomize": self.randomize.isChecked(),
            "seed": self.seed.value(),
            "name": self.ws_name.text().strip() or "Custom D-Optimal Design",
        }
        self.accept()


class EvaluateDesignDialog(ProcedureDialog):
    """Dialog to evaluate an existing experimental design from active worksheet columns."""

    def __init__(self, worksheet, parent: Optional[QWidget] = None):
        super().__init__(
            parent,
            "Evaluate Design (Color Map on Correlations)",
            worksheet,
            selectors=(
                {"key": "factor_indices", "label": "Factors to evaluate:", "multiple": True, "minimum": 2},
            ),
            fields=(
                {
                    "key": "model_order",
                    "label": "Assumed model structure:",
                    "choices": [
                        "Main Effects + 2-Factor Interactions",
                        "Main Effects Only (Linear)",
                        "Full Response Surface (Quadratic)",
                    ],
                    "default": "Main Effects + 2-Factor Interactions",
                },
            ),
            note=(
                "Evaluates design efficiency (D-efficiency, A-efficiency, G-efficiency) and generates "
                "the signature JMP Color Map on Correlations to inspect confounding, term aliasing, and orthogonality."
            ),
        )

    def values(self) -> Dict[str, Any]:
        vals = super().values()
        order_map = {
            "Main Effects + 2-Factor Interactions": "interactions",
            "Main Effects Only (Linear)": "linear",
            "Full Response Surface (Quadratic)": "quadratic",
        }
        vals["model_order"] = order_map.get(vals.get("model_order"), "interactions")
        return vals
