"""Qt Dialog for Best Subsets Regression with authentic Minitab layout and behavior."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .variable_dialogs import ProcedureDialog


class BestSubsetsDialog(ProcedureDialog):
    """Minitab-standard Best Subsets Regression dialog."""

    def __init__(self, window: Any):
        specs = [
            dict(key="response_index", label="Response:", kinds=("number",)),
            dict(
                key="free_indices",
                label="Free predictors:",
                multiple=True,
                minimum=1,
                kinds=("number",),
            ),
            dict(
                key="forced_indices",
                label="Predictors in all models:",
                multiple=True,
                required=False,
                kinds=("number",),
            ),
        ]
        super().__init__(
            window,
            "Best Subsets Regression",
            window.presenter.worksheet if hasattr(window, "presenter") else window,
            specs,
            (),
            "Evaluates candidate predictor subsets calculating R-Sq, R-Sq(adj), Mallows' C-p, and s.",
        )
        self.window = window

        # Subset control options group
        grp = QGroupBox("Model Selection Options")
        form = QFormLayout(grp)

        self.spin_models_per_subset = QSpinBox()
        self.spin_models_per_subset.setRange(1, 10)
        self.spin_models_per_subset.setValue(2)
        form.addRow("Models of each size to print:", self.spin_models_per_subset)

        self.spin_min_free = QSpinBox()
        self.spin_min_free.setRange(0, 100)
        self.spin_min_free.setValue(1)
        form.addRow("Minimum free predictors in subset:", self.spin_min_free)

        self.spin_max_free = QSpinBox()
        self.spin_max_free.setRange(0, 100)
        self.spin_max_free.setValue(0)
        self.spin_max_free.setSpecialValueText("All")
        form.addRow("Maximum free predictors in subset:", self.spin_max_free)

        self.layout().insertWidget(self.layout().count() - 2, grp)

    def validate(self) -> None:
        p = self.parameters
        resp_idx = p.get("response_index")
        free_idxs = p.get("free_indices", [])
        forced_idxs = p.get("forced_indices", []) or []

        if resp_idx is None:
            QMessageBox.warning(self, "Best Subsets", "Please select a response variable.")
            return

        if not free_idxs:
            QMessageBox.warning(self, "Best Subsets", "Please select at least one free predictor.")
            return

        if resp_idx in free_idxs or resp_idx in forced_idxs:
            QMessageBox.warning(
                self,
                "Best Subsets",
                "Response variable cannot also be used as a predictor.",
            )
            return

        # Check overlap between free and forced predictors
        overlap = set(free_idxs).intersection(set(forced_idxs))
        if overlap:
            QMessageBox.warning(
                self,
                "Best Subsets",
                "A variable cannot be both a free predictor and a predictor in all models.",
            )
            return

        min_f = self.spin_min_free.value()
        max_f_val = self.spin_max_free.value()
        max_f = len(free_idxs) if max_f_val == 0 else min(len(free_idxs), max_f_val)
        if min_f > max_f:
            QMessageBox.warning(
                self,
                "Best Subsets",
                "Minimum free predictors cannot exceed maximum free predictors.",
            )
            return

        self.best_subsets_settings = {
            "response_index": resp_idx,
            "free_indices": free_idxs,
            "forced_indices": forced_idxs,
            "models_per_subset": self.spin_models_per_subset.value(),
            "min_free": min_f,
            "max_free": max_f,
        }
        self.accept()
