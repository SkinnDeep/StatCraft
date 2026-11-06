"""Store Descriptive Statistics module for StatCraft.

Allows computing descriptive statistics across continuous variables (optionally grouped
by a factor variable) and storing them directly into new columns in the worksheet.
"""
from __future__ import annotations

import math
from typing import Any, List, Optional, Sequence
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QListWidget, QAbstractItemView, QGroupBox, QCheckBox,
    QGridLayout, QMessageBox
)

from statcraft.model import Column, Worksheet


STAT_NAMES = [
    ("mean", "Mean"),
    ("se_mean", "SE of Mean"),
    ("stdev", "Standard Deviation"),
    ("variance", "Variance"),
    ("coeff_var", "Coefficient of Variation"),
    ("sum", "Sum"),
    ("minimum", "Minimum"),
    ("q1", "First Quartile (Q1)"),
    ("median", "Median"),
    ("q3", "Third Quartile (Q3)"),
    ("maximum", "Maximum"),
    ("iqr", "Interquartile Range (IQR)"),
    ("n", "N Nonmissing"),
    ("n_missing", "N Missing"),
    ("skewness", "Skewness"),
    ("kurtosis", "Kurtosis")
]


def _calc_stats_for_values(values: Sequence[float]) -> dict[str, Optional[float]]:
    """Compute individual statistics for a list of clean numeric floats."""
    n = len(values)
    if n == 0:
        return {key: None for key, _ in STAT_NAMES}

    sorted_vals = sorted(values)
    sum_val = sum(values)
    mean_val = sum_val / n

    if n > 1:
        variance = sum((x - mean_val) ** 2 for x in values) / (n - 1)
        stdev = math.sqrt(variance)
        se_mean = stdev / math.sqrt(n)
        coeff_var = (stdev / mean_val * 100.0) if mean_val != 0 else None
    else:
        variance = 0.0
        stdev = 0.0
        se_mean = 0.0
        coeff_var = 0.0

    min_val = sorted_vals[0]
    max_val = sorted_vals[-1]

    def _percentile(p: float) -> float:
        pos = p * (n - 1)
        idx = int(pos)
        frac = pos - idx
        if idx + 1 < n:
            return sorted_vals[idx] + frac * (sorted_vals[idx + 1] - sorted_vals[idx])
        return sorted_vals[idx]

    q1_val = _percentile(0.25)
    median_val = _percentile(0.50)
    q3_val = _percentile(0.75)
    iqr_val = q3_val - q1_val

    if n > 2 and stdev > 0:
        m3 = sum((x - mean_val) ** 3 for x in values) / n
        skew = (math.sqrt(n * (n - 1)) / (n - 2)) * (m3 / (stdev ** 3))
    else:
        skew = None

    if n > 3 and stdev > 0:
        m4 = sum((x - mean_val) ** 4 for x in values) / n
        kurt = ((n - 1) / ((n - 2) * (n - 3))) * ((n + 1) * (m4 / (stdev ** 4)) - 3 * (n - 1))
    else:
        kurt = None

    return {
        "mean": mean_val,
        "se_mean": se_mean,
        "stdev": stdev,
        "variance": variance,
        "coeff_var": coeff_var,
        "sum": sum_val,
        "minimum": min_val,
        "q1": q1_val,
        "median": median_val,
        "q3": q3_val,
        "maximum": max_val,
        "iqr": iqr_val,
        "skewness": skew,
        "kurtosis": kurt
    }


def compute_store_descriptive_columns(
    worksheet: Worksheet,
    var_indices: Sequence[int],
    by_index: Optional[int] = None,
    selected_stats: Optional[Sequence[str]] = None
) -> list[Column]:
    """Compute requested descriptive statistics and return new columns ready to add to worksheet."""
    if not selected_stats:
        selected_stats = ["mean", "stdev", "minimum", "median", "maximum", "n"]

    columns_to_add: list[Column] = []

    if by_index is not None and 0 <= by_index < len(worksheet.columns):
        by_col = worksheet.columns[by_index]
        by_raw = list(by_col.values)

        # Natural sort of unique by levels
        def _sort_key(v):
            if v is None:
                return (2, "")
            try:
                return (0, float(v))
            except (ValueError, TypeError):
                return (1, str(v))

        unique_by = sorted(list({v for v in by_raw if v is not None and str(v).strip() != ""}), key=_sort_key)
        
        # Add By-level column
        columns_to_add.append(Column(f"By_{by_col.name}", by_col.kind, unique_by))

        for v_idx in var_indices:
            var_col = worksheet.columns[v_idx]
            v_raw = list(var_col.values)

            # Group values by By-level
            grouped_clean: dict[Any, list[float]] = {lvl: [] for lvl in unique_by}
            grouped_missing: dict[Any, int] = {lvl: 0 for lvl in unique_by}

            n_rows = max(len(v_raw), len(by_raw))
            for i in range(n_rows):
                b_val = by_raw[i] if i < len(by_raw) else None
                if b_val not in grouped_clean:
                    continue
                val = v_raw[i] if i < len(v_raw) else None
                if val is None:
                    grouped_missing[b_val] += 1
                    continue
                try:
                    f_val = float(val)
                    if math.isnan(f_val) or math.isinf(f_val):
                        grouped_missing[b_val] += 1
                    else:
                        grouped_clean[b_val].append(f_val)
                except (ValueError, TypeError):
                    grouped_missing[b_val] += 1

            # Compute stats per group
            stats_by_lvl: list[dict[str, Any]] = []
            for lvl in unique_by:
                st = _calc_stats_for_values(grouped_clean[lvl])
                st["n"] = len(grouped_clean[lvl])
                st["n_missing"] = grouped_missing[lvl]
                stats_by_lvl.append(st)

            for stat_key in selected_stats:
                col_name = f"{stat_key.capitalize()}_{var_col.name}"
                stat_vals = [s.get(stat_key) for s in stats_by_lvl]
                columns_to_add.append(Column(col_name, "number", stat_vals))

    else:
        # Ungrouped overall statistics
        for v_idx in var_indices:
            var_col = worksheet.columns[v_idx]
            v_raw = list(var_col.values)
            clean_vals: list[float] = []
            n_missing = 0

            for val in v_raw:
                if val is None:
                    n_missing += 1
                    continue
                try:
                    f_val = float(val)
                    if math.isnan(f_val) or math.isinf(f_val):
                        n_missing += 1
                    else:
                        clean_vals.append(f_val)
                except (ValueError, TypeError):
                    n_missing += 1

            st = _calc_stats_for_values(clean_vals)
            st["n"] = len(clean_vals)
            st["n_missing"] = n_missing

            for stat_key in selected_stats:
                col_name = f"{stat_key.capitalize()}_{var_col.name}"
                columns_to_add.append(Column(col_name, "number", [st.get(stat_key)]))

    return columns_to_add


class StoreDescriptiveDialog(QDialog):
    """Dialog for Stat > Basic Statistics > Store Descriptive Statistics..."""

    def __init__(self, worksheet: Worksheet, parent=None):
        self.setSizeGripEnabled(True)
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Store Descriptive Statistics")
        self.setMinimumSize(520, 520)
        self.resize(540, 560)

        main_layout = QVBoxLayout(self)

        # Variables Box
        var_group = QGroupBox("Variables")
        var_layout = QVBoxLayout(var_group)

        var_layout.addWidget(QLabel("Variables (Continuous Numeric):"))
        self.list_vars = QListWidget()
        self.list_vars.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        for i, col in enumerate(self.worksheet.columns):
            if col.kind == 'number':
                item = self.list_vars.addItem(f"C{i + 1}  {col.name}")
        if self.list_vars.count() > 0:
            self.list_vars.item(0).setSelected(True)
        var_layout.addWidget(self.list_vars)

        # By Variable Box
        by_layout = QHBoxLayout()
        by_layout.addWidget(QLabel("By Variable (Optional Grouping):"))
        self.combo_by = QComboBox()
        self.combo_by.addItem("(None - Overall Statistics)", None)
        for i, col in enumerate(self.worksheet.columns):
            self.combo_by.addItem(f"C{i + 1}  {col.name}", i)
        by_layout.addWidget(self.combo_by)
        var_layout.addLayout(by_layout)

        main_layout.addWidget(var_group)

        # Statistics Checkboxes
        stat_group = QGroupBox("Statistics to Store")
        stat_grid = QGridLayout(stat_group)

        self.stat_checks: dict[str, QCheckBox] = {}
        defaults = {"mean", "stdev", "minimum", "median", "maximum", "n"}

        for idx, (key, label) in enumerate(STAT_NAMES):
            chk = QCheckBox(label)
            chk.setChecked(key in defaults)
            self.stat_checks[key] = chk
            row = idx // 2
            col = idx % 2
            stat_grid.addWidget(chk, row, col)

        main_layout.addWidget(stat_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_ok = QPushButton("OK")
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.btn_ok)

        main_layout.addLayout(btn_layout)

    def _on_ok(self):
        selected_indexes = [item.row() for item in self.list_vars.selectedIndexes()]
        if not selected_indexes:
            QMessageBox.warning(self, "Validation Error", "Please select at least one numeric variable.")
            return

        selected_keys = [k for k, chk in self.stat_checks.items() if chk.isChecked()]
        if not selected_keys:
            QMessageBox.warning(self, "Validation Error", "Please select at least one statistic to store.")
            return

        self.accept()

    def get_parameters(self) -> dict:
        num_cols = [i for i, c in enumerate(self.worksheet.columns) if c.kind == 'number']
        selected_rows = [item.row() for item in self.list_vars.selectedIndexes()]
        var_indices = [num_cols[r] for r in selected_rows if r < len(num_cols)]
        by_idx = self.combo_by.currentData()
        selected_stats = [k for k, chk in self.stat_checks.items() if chk.isChecked()]

        return {
            "var_indices": var_indices,
            "by_index": by_idx,
            "selected_stats": selected_stats
        }
