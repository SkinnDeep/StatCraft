"""Dialogs for native StatCraft One-Sample Poisson Rate test."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QCheckBox, QListWidget,
    QStackedWidget, QWidget, QMessageBox, QGroupBox
)
from .model import Worksheet


class OneSamplePoissonOptionsDialog(QDialog):
    """Options child dialog matching 1SAMPLEPOISSONOPTIONS.MDF (HelpID 95011)."""

    def __init__(self, options: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("One-Sample Poisson Rate: Options")
        self.setModal(True)
        self.options = dict(options)
        self.resize(380, 200)

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        grid.addWidget(QLabel("Confidence level:"), 0, 0)
        self.conf_edit = QLineEdit(str(self.options.get("confidence_level", 95.0)))
        self.conf_edit.setMaximumWidth(90)
        grid.addWidget(self.conf_edit, 0, 1)

        grid.addWidget(QLabel("Alternative hypothesis:"), 1, 0)
        self.alt_combo = QComboBox()
        self.alt_combo.addItems([
            "Rate ≠ hypothesized rate",
            "Rate < hypothesized rate",
            "Rate > hypothesized rate",
        ])
        alt_val = self.options.get("alternative", "not_equal")
        if alt_val == "less":
            self.alt_combo.setCurrentIndex(1)
        elif alt_val == "greater":
            self.alt_combo.setCurrentIndex(2)
        else:
            self.alt_combo.setCurrentIndex(0)
        grid.addWidget(self.alt_combo, 1, 1)

        grid.addWidget(QLabel("Method:"), 2, 0)
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Exact",
            "Normal approximation",
        ])
        method_val = self.options.get("method", "exact")
        if method_val == "normal_approx":
            self.method_combo.setCurrentIndex(1)
        else:
            self.method_combo.setCurrentIndex(0)
        grid.addWidget(self.method_combo, 2, 1)

        grid.addWidget(QLabel("Length of observation:"), 3, 0)
        len_box = QHBoxLayout()
        self.len_edit = QLineEdit(str(self.options.get("length_of_observation", 1.0)))
        self.len_edit.setMaximumWidth(90)
        len_box.addWidget(self.len_edit)
        len_box.addWidget(QLabel("(time, items, area, etc.)"))
        len_box.addStretch()
        grid.addLayout(len_box, 3, 1)

        layout.addLayout(grid)
        layout.addStretch()

        btn_box = QHBoxLayout()
        self.help_btn = QPushButton("Help")
        btn_box.addWidget(self.help_btn)
        btn_box.addStretch()
        self.ok_btn = QPushButton("&OK")
        self.ok_btn.clicked.connect(self._accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.ok_btn)
        btn_box.addWidget(self.cancel_btn)
        layout.addLayout(btn_box)

    def _accept(self):
        try:
            c = float(self.conf_edit.text().strip())
            if not (0.0 < c < 100.0):
                raise ValueError
            self.options["confidence_level"] = c
        except ValueError:
            QMessageBox.warning(self, "Invalid Value", "Confidence level must be between 0 and 100.")
            return

        idx = self.alt_combo.currentIndex()
        if idx == 1:
            self.options["alternative"] = "less"
        elif idx == 2:
            self.options["alternative"] = "greater"
        else:
            self.options["alternative"] = "not_equal"

        m_idx = self.method_combo.currentIndex()
        self.options["method"] = "normal_approx" if m_idx == 1 else "exact"

        try:
            length = float(self.len_edit.text().strip())
            if length <= 0:
                raise ValueError
            self.options["length_of_observation"] = length
        except ValueError:
            QMessageBox.warning(self, "Invalid Value", "Length of observation must be a positive number.")
            return

        self.accept()


class OneSamplePoissonDialog(QDialog):
    """Main dialog matching 1SAMPLEPOISSONRATE.MDF (MenuID 41128, HelpID 95010)."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("One-Sample Poisson Rate")
        self.setModal(True)
        self.resize(560, 360)

        self.options: Dict[str, Any] = {
            "confidence_level": 95.0,
            "alternative": "not_equal",
            "method": "exact",
            "length_of_observation": 1.0,
        }
        self.settings: Optional[Dict[str, Any]] = None
        self.result_payload: Optional[Dict[str, Any]] = None

        main_layout = QHBoxLayout(self)

        # Left: Available Columns
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Columns:"))
        self.col_list = QListWidget()
        self._populate_columns()
        left_layout.addWidget(self.col_list)

        self.select_btn = QPushButton("Select")
        self.select_btn.clicked.connect(self._on_select_clicked)
        left_layout.addWidget(self.select_btn)
        main_layout.addLayout(left_layout, stretch=1)

        # Right: Dialog controls
        right_layout = QVBoxLayout()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "One or more samples, each in a column",
            "Summarized data",
        ])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        right_layout.addWidget(self.mode_combo)

        # Stacked pages
        self.stack = QStackedWidget()

        # Page 0: Columns
        page_cols = QWidget()
        cols_grid = QGridLayout(page_cols)
        cols_grid.addWidget(QLabel("Sample columns:"), 0, 0)
        self.sample_cols_edit = QLineEdit()
        self.sample_cols_edit.setFocus()
        cols_grid.addWidget(self.sample_cols_edit, 0, 1)

        cols_grid.addWidget(QLabel("Frequency columns (optional):"), 1, 0)
        self.freq_cols_edit = QLineEdit()
        cols_grid.addWidget(self.freq_cols_edit, 1, 1)
        self.stack.addWidget(page_cols)

        # Page 1: Summarized
        page_summ = QWidget()
        summ_grid = QGridLayout(page_summ)
        summ_grid.addWidget(QLabel("Sample size:"), 0, 0)
        self.sample_size_edit = QLineEdit()
        self.sample_size_edit.setMaximumWidth(120)
        summ_grid.addWidget(self.sample_size_edit, 0, 1)

        summ_grid.addWidget(QLabel("Total occurrences:"), 1, 0)
        self.total_occurrences_edit = QLineEdit()
        self.total_occurrences_edit.setMaximumWidth(120)
        summ_grid.addWidget(self.total_occurrences_edit, 1, 1)
        self.stack.addWidget(page_summ)

        right_layout.addWidget(self.stack)

        # Hypothesis test box
        test_group = QGroupBox()
        test_layout = QVBoxLayout(test_group)
        self.test_check = QCheckBox("&Perform hypothesis test")
        self.test_check.setChecked(True)
        self.test_check.toggled.connect(self._on_test_toggled)
        test_layout.addWidget(self.test_check)

        rate_row = QHBoxLayout()
        rate_row.addWidget(QLabel("Hypothesized rate:"))
        self.test_rate_edit = QLineEdit()
        self.test_rate_edit.setMaximumWidth(100)
        rate_row.addWidget(self.test_rate_edit)
        rate_row.addStretch()
        test_layout.addLayout(rate_row)
        right_layout.addWidget(test_group)

        # Options button
        opt_layout = QHBoxLayout()
        opt_layout.addStretch()
        self.options_btn = QPushButton("Optio&ns…")
        self.options_btn.clicked.connect(self._open_options)
        opt_layout.addWidget(self.options_btn)
        right_layout.addLayout(opt_layout)

        right_layout.addStretch()

        # Action buttons
        btn_box = QHBoxLayout()
        self.help_btn = QPushButton("Help")
        btn_box.addWidget(self.help_btn)
        btn_box.addStretch()
        self.ok_btn = QPushButton("&OK")
        self.ok_btn.clicked.connect(self._accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.ok_btn)
        btn_box.addWidget(self.cancel_btn)
        right_layout.addLayout(btn_box)

        main_layout.addLayout(right_layout, stretch=2)

        # Wire column double clicks
        self.col_list.itemDoubleClicked.connect(self._on_select_clicked)

    def _populate_columns(self):
        self.col_list.clear()
        if not self.worksheet:
            return
        for idx, col in enumerate(self.worksheet.columns):
            name = col.name or f"C{idx + 1}"
            self.col_list.addItem(f"C{idx + 1}  {name}")

    def _active_edit(self) -> Optional[QLineEdit]:
        if self.mode_combo.currentIndex() == 0:
            if self.freq_cols_edit.hasFocus():
                return self.freq_cols_edit
            return self.sample_cols_edit
        return None

    def _on_select_clicked(self):
        item = self.col_list.currentItem()
        if not item:
            return
        token = item.text().split()[0]
        edit = self._active_edit()
        if edit:
            cur = edit.text().strip()
            if cur:
                edit.setText(f"{cur} {token}")
            else:
                edit.setText(token)

    def _on_mode_changed(self, idx: int):
        self.stack.setCurrentIndex(idx)

    def _on_test_toggled(self, checked: bool):
        self.test_rate_edit.setEnabled(checked)

    def _open_options(self):
        dlg = OneSamplePoissonOptionsDialog(self.options, self)
        if dlg.exec():
            self.options = dlg.options

    def _accept(self):
        mode = self.mode_combo.currentIndex()

        hypo_rate = None
        if self.test_check.isChecked():
            txt = self.test_rate_edit.text().strip()
            if not txt:
                QMessageBox.warning(self, "Invalid Value", "Please enter a hypothesized rate.")
                return
            try:
                hypo_rate = float(txt)
                if hypo_rate <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(self, "Invalid Value", "Hypothesized rate must be a positive number.")
                return

        if mode == 0:
            # Columns mode
            samples_str = self.sample_cols_edit.text().strip()
            if not samples_str:
                QMessageBox.warning(self, "Missing Column", "Please specify at least one sample column.")
                return
            freqs_str = self.freq_cols_edit.text().strip()

            def resolve_col_token(tok: str) -> Any:
                if tok.upper().startswith("C") and tok[1:].isdigit():
                    return int(tok[1:]) - 1
                if hasattr(self.worksheet, "columns"):
                    for c_idx, c in enumerate(self.worksheet.columns):
                        if c.name and c.name.strip().upper() == tok.strip().upper():
                            return c_idx
                return tok

            sample_cols = [resolve_col_token(tok) for tok in samples_str.split()]
            freq_cols = [resolve_col_token(tok) for tok in freqs_str.split()] if freqs_str else []

            if freq_cols and len(freq_cols) != len(sample_cols):
                QMessageBox.warning(self, "Mismatch", "If frequency columns are provided, their count must match the sample columns.")
                return

            self.settings = {
                "mode": "columns",
                "data_format": 0,
                "sample_cols": sample_cols,
                "sample_columns": sample_cols,
                "freq_cols": freq_cols,
                "freq_columns": freq_cols,
                "hypothesized_rate": hypo_rate,
                "confidence_level": self.options["confidence_level"],
                "alternative": self.options["alternative"],
                "method": self.options["method"],
                "length_of_observation": self.options["length_of_observation"],
            }
        else:
            # Summarized mode
            n_txt = self.sample_size_edit.text().strip()
            occur_txt = self.total_occurrences_edit.text().strip()
            if not n_txt or not occur_txt:
                QMessageBox.warning(self, "Missing Data", "Please specify sample size and total occurrences.")
                return
            try:
                n = int(n_txt)
                total_occur = int(occur_txt)
                if n <= 0:
                    raise ValueError("Sample size must be at least 1.")
                if total_occur < 0:
                    raise ValueError("Total occurrences cannot be negative.")
            except ValueError as e:
                QMessageBox.warning(self, "Invalid Data", str(e))
                return

            self.settings = {
                "mode": "summarized",
                "sample_name": "Sample",
                "n": n,
                "total_occurrences": total_occur,
                "hypothesized_rate": hypo_rate,
                "confidence_level": self.options["confidence_level"],
                "alternative": self.options["alternative"],
                "method": self.options["method"],
                "length_of_observation": self.options["length_of_observation"],
            }

        self.result_payload = dict(self.settings) if self.settings else None
        self.accept()
