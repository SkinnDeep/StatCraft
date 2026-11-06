"""Dialogs for native StatCraft Two-Sample Poisson Rate test."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QCheckBox, QListWidget,
    QStackedWidget, QWidget, QMessageBox, QGroupBox
)
from .model import Worksheet


class TwoSamplePoissonOptionsDialog(QDialog):
    """Options child dialog matching 2SAMPLEPOISSONOPTIONS.MDF (HelpID 95009)."""

    def __init__(self, options: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Two-Sample Poisson Rate: Options")
        self.setModal(True)
        self.options = dict(options)
        self.setMinimumSize(400, 260)
        self.resize(400, 260)
        self.setSizeGripEnabled(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Difference = (sample 1 rate) - (sample 2 rate)"))
        layout.addSpacing(6)

        grid = QGridLayout()

        grid.addWidget(QLabel("Confidence level:"), 0, 0)
        self.conf_edit = QLineEdit(str(self.options.get("confidence_level", 95.0)))
        self.conf_edit.setMaximumWidth(90)
        grid.addWidget(self.conf_edit, 0, 1)

        grid.addWidget(QLabel("Hypothesized difference:"), 1, 0)
        self.diff_edit = QLineEdit(str(self.options.get("hypothesized_difference", 0.0)))
        self.diff_edit.setMaximumWidth(90)
        grid.addWidget(self.diff_edit, 1, 1)

        grid.addWidget(QLabel("Alternative hypothesis:"), 2, 0)
        self.alt_combo = QComboBox()
        self.alt_combo.addItems([
            "Difference ≠ hypothesized difference",
            "Difference < hypothesized difference",
            "Difference > hypothesized difference",
        ])
        alt_val = self.options.get("alternative", "not_equal")
        if alt_val == "less":
            self.alt_combo.setCurrentIndex(1)
        elif alt_val == "greater":
            self.alt_combo.setCurrentIndex(2)
        else:
            self.alt_combo.setCurrentIndex(0)
        grid.addWidget(self.alt_combo, 2, 1)

        grid.addWidget(QLabel("Test method:"), 3, 0)
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Estimate the rates separately",
            "Use the pooled estimate of the rate",
        ])
        method_val = self.options.get("test_method", "separate")
        if method_val == "pooled":
            self.method_combo.setCurrentIndex(1)
        else:
            self.method_combo.setCurrentIndex(0)
        grid.addWidget(self.method_combo, 3, 1)

        grid.addWidget(QLabel("Lengths of observation:"), 4, 0)
        len_box = QHBoxLayout()
        self.len_edit = QLineEdit(str(self.options.get("length_of_observation", 1.0)))
        self.len_edit.setMaximumWidth(90)
        len_box.addWidget(self.len_edit)
        len_box.addWidget(QLabel("(time, items, area, etc.)"))
        len_box.addStretch()
        grid.addLayout(len_box, 4, 1)

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

        try:
            d = float(self.diff_edit.text().strip())
            self.options["hypothesized_difference"] = d
        except ValueError:
            QMessageBox.warning(self, "Invalid Value", "Hypothesized difference must be a valid number.")
            return

        idx = self.alt_combo.currentIndex()
        if idx == 1:
            self.options["alternative"] = "less"
        elif idx == 2:
            self.options["alternative"] = "greater"
        else:
            self.options["alternative"] = "not_equal"

        m_idx = self.method_combo.currentIndex()
        self.options["test_method"] = "pooled" if m_idx == 1 else "separate"

        try:
            length = float(self.len_edit.text().strip())
            if length <= 0:
                raise ValueError
            self.options["length_of_observation"] = length
        except ValueError:
            QMessageBox.warning(self, "Invalid Value", "Length of observation must be a positive number.")
            return

        self.accept()


class TwoSamplePoissonDialog(QDialog):
    """Main dialog matching 2SAMPLEPOISSON.MDF (MenuID 41129, HelpID 95008)."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Two-Sample Poisson Rate")
        self.setModal(True)
        self.setMinimumSize(580, 420)
        self.resize(580, 420)
        self.setSizeGripEnabled(True)

        self.options: Dict[str, Any] = {
            "confidence_level": 95.0,
            "hypothesized_difference": 0.0,
            "alternative": "not_equal",
            "test_method": "separate",
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
            "Both samples are in one column",
            "Each sample is in its own column",
            "Summarized data",
        ])
        self.mode_combo.setCurrentIndex(1)  # Default: Each sample in its own column
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        right_layout.addWidget(self.mode_combo)

        # Stacked pages
        self.stack = QStackedWidget()

        # Page 0: Stacked
        page_stacked = QWidget()
        stacked_grid = QGridLayout(page_stacked)
        stacked_grid.addWidget(QLabel("Samples:"), 0, 0)
        self.samples_edit = QLineEdit()
        stacked_grid.addWidget(self.samples_edit, 0, 1)

        stacked_grid.addWidget(QLabel("Sample IDs:"), 1, 0)
        self.sample_ids_edit = QLineEdit()
        stacked_grid.addWidget(self.sample_ids_edit, 1, 1)

        stacked_grid.addWidget(QLabel("Frequency column:"), 2, 0)
        self.freq1_edit = QLineEdit()
        stacked_grid.addWidget(self.freq1_edit, 2, 1)
        self.stack.addWidget(page_stacked)

        # Page 1: Unstacked
        page_unstacked = QWidget()
        unstacked_grid = QGridLayout(page_unstacked)
        unstacked_grid.addWidget(QLabel("Sample 1:"), 0, 0)
        self.sample1_edit = QLineEdit()
        unstacked_grid.addWidget(self.sample1_edit, 0, 1)

        unstacked_grid.addWidget(QLabel("Sample 2:"), 1, 0)
        self.sample2_edit = QLineEdit()
        unstacked_grid.addWidget(self.sample2_edit, 1, 1)

        unstacked_grid.addWidget(QLabel("Frequency columns (optional):"), 2, 0)
        self.freq2_edit = QLineEdit()
        unstacked_grid.addWidget(self.freq2_edit, 2, 1)
        self.stack.addWidget(page_unstacked)

        # Page 2: Summarized
        page_summ = QWidget()
        summ_grid = QGridLayout(page_summ)
        summ_grid.addWidget(QLabel("Sample 1"), 0, 1)
        summ_grid.addWidget(QLabel("Sample 2"), 0, 2)

        summ_grid.addWidget(QLabel("Sample size:"), 1, 0)
        self.sz1_edit = QLineEdit()
        self.sz1_edit.setMaximumWidth(90)
        summ_grid.addWidget(self.sz1_edit, 1, 1)
        self.sz2_edit = QLineEdit()
        self.sz2_edit.setMaximumWidth(90)
        summ_grid.addWidget(self.sz2_edit, 1, 2)

        summ_grid.addWidget(QLabel("Total occurrences:"), 2, 0)
        self.tot1_edit = QLineEdit()
        self.tot1_edit.setMaximumWidth(90)
        summ_grid.addWidget(self.tot1_edit, 2, 1)
        self.tot2_edit = QLineEdit()
        self.tot2_edit.setMaximumWidth(90)
        summ_grid.addWidget(self.tot2_edit, 2, 2)
        self.stack.addWidget(page_summ)

        self.s1_edit = self.sample1_edit
        self.s2_edit = self.sample2_edit
        self.sum_s1_size = self.sz1_edit
        self.sum_s1_events = self.tot1_edit
        self.sum_s2_size = self.sz2_edit
        self.sum_s2_events = self.tot2_edit

        self.stack.setCurrentIndex(1)  # Match default
        right_layout.addWidget(self.stack)

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

        self.col_list.itemDoubleClicked.connect(self._on_select_clicked)

    def _populate_columns(self):
        self.col_list.clear()
        if not self.worksheet:
            return
        for idx, col in enumerate(self.worksheet.columns):
            name = col.name or f"C{idx + 1}"
            self.col_list.addItem(f"C{idx + 1}  {name}")

    def _active_edit(self) -> Optional[QLineEdit]:
        mode = self.mode_combo.currentIndex()
        if mode == 0:
            if self.sample_ids_edit.hasFocus():
                return self.sample_ids_edit
            if self.freq1_edit.hasFocus():
                return self.freq1_edit
            return self.samples_edit
        elif mode == 1:
            if self.sample2_edit.hasFocus():
                return self.sample2_edit
            if self.freq2_edit.hasFocus():
                return self.freq2_edit
            return self.sample1_edit
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

    def _open_options(self):
        dlg = TwoSamplePoissonOptionsDialog(self.options, self)
        if dlg.exec():
            self.options = dlg.options

    def _accept(self):
        mode = self.mode_combo.currentIndex()

        def resolve_col_token(tok: str) -> Any:
            if tok.upper().startswith("C") and tok[1:].isdigit():
                return int(tok[1:]) - 1
            if hasattr(self.worksheet, "columns"):
                for c_idx, c in enumerate(self.worksheet.columns):
                    if c.name and c.name.strip().upper() == tok.strip().upper():
                        return c_idx
            return tok

        if mode == 0:  # Stacked
            s_txt = self.samples_edit.text().strip()
            id_txt = self.sample_ids_edit.text().strip()
            if not s_txt or not id_txt:
                QMessageBox.warning(self, "Missing Column", "Please specify both Samples and Sample IDs columns.")
                return
            f_txt = self.freq1_edit.text().strip()

            self.settings = {
                "mode": "stacked",
                "data_format": 0,
                "samples_col": resolve_col_token(s_txt.split()[0]),
                "sample_ids_col": resolve_col_token(id_txt.split()[0]),
                "freq_col": resolve_col_token(f_txt.split()[0]) if f_txt else None,
                "confidence_level": self.options["confidence_level"],
                "hypothesized_difference": self.options["hypothesized_difference"],
                "alternative": self.options["alternative"],
                "test_method": self.options["test_method"],
                "length_of_observation": self.options["length_of_observation"],
            }
        elif mode == 1:  # Unstacked
            s1_txt = self.sample1_edit.text().strip()
            s2_txt = self.sample2_edit.text().strip()
            if not s1_txt or not s2_txt:
                QMessageBox.warning(self, "Missing Column", "Please specify both Sample 1 and Sample 2 columns.")
                return
            f_txt = self.freq2_edit.text().strip()
            f_cols = [resolve_col_token(t) for t in f_txt.split()] if f_txt else []

            self.settings = {
                "mode": "unstacked",
                "data_format": 1,
                "sample1_col": resolve_col_token(s1_txt.split()[0]),
                "sample2_col": resolve_col_token(s2_txt.split()[0]),
                "freq_cols": f_cols,
                "confidence_level": self.options["confidence_level"],
                "hypothesized_difference": self.options["hypothesized_difference"],
                "alternative": self.options["alternative"],
                "test_method": self.options["test_method"],
                "length_of_observation": self.options["length_of_observation"],
            }
        else:  # Summarized
            sz1_txt = self.sz1_edit.text().strip()
            tot1_txt = self.tot1_edit.text().strip()
            sz2_txt = self.sz2_edit.text().strip()
            tot2_txt = self.tot2_edit.text().strip()
            if not sz1_txt or not tot1_txt or not sz2_txt or not tot2_txt:
                QMessageBox.warning(self, "Missing Data", "Please specify sample size and occurrences for both samples.")
                return
            try:
                n1 = int(sz1_txt)
                x1 = int(tot1_txt)
                n2 = int(sz2_txt)
                x2 = int(tot2_txt)
                if n1 <= 0 or n2 <= 0:
                    raise ValueError("Sample sizes must be at least 1.")
                if x1 < 0 or x2 < 0:
                    raise ValueError("Total occurrences cannot be negative.")
            except ValueError as e:
                QMessageBox.warning(self, "Invalid Data", str(e))
                return

            self.settings = {
                "mode": "summarized",
                "data_format": 2,
                "summarized": {
                    "n1": n1,
                    "total_occurrences1": x1,
                    "n2": n2,
                    "total_occurrences2": x2,
                },
                "confidence_level": self.options["confidence_level"],
                "hypothesized_difference": self.options["hypothesized_difference"],
                "alternative": self.options["alternative"],
                "test_method": self.options["test_method"],
                "length_of_observation": self.options["length_of_observation"],
            }

        self.result_payload = dict(self.settings) if self.settings else None
        self.accept()
