"""Dialogs for native StatCraft One-Sample Proportion test."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QCheckBox, QListWidget,
    QStackedWidget, QWidget, QMessageBox, QGroupBox
)
from .model import Worksheet
from .one_sample_proportion_engine import one_sample_proportion_settings


class OneSampleProportionOptionsDialog(QDialog):
    """Options child dialog matching 1SAMPLEPROPORTIONOPTIONS.MDF (HelpID 95313)."""

    def __init__(self, options: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("One-Sample Proportion: Options")
        self.setModal(True)
        self.options = dict(options)
        self.resize(340, 180)

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        grid.addWidget(QLabel("Confidence level:"), 0, 0)
        self.conf_edit = QLineEdit(str(self.options.get("confidence_level", 95.0)))
        self.conf_edit.setMaximumWidth(90)
        grid.addWidget(self.conf_edit, 0, 1)

        grid.addWidget(QLabel("Alternative hypothesis:"), 1, 0)
        self.alt_combo = QComboBox()
        self.alt_combo.addItems([
            "Proportion < hypothesized proportion",
            "Proportion ≠ hypothesized proportion",
            "Proportion > hypothesized proportion",
        ])
        alt_val = self.options.get("alternative", "not_equal")
        if alt_val == "less_than":
            self.alt_combo.setCurrentIndex(0)
        elif alt_val == "greater_than":
            self.alt_combo.setCurrentIndex(2)
        else:
            self.alt_combo.setCurrentIndex(1)
        grid.addWidget(self.alt_combo, 1, 1)

        grid.addWidget(QLabel("Method:"), 2, 0)
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Exact",
            "Normal approximation",
        ])
        method_val = self.options.get("method", "exact")
        if method_val == "normal":
            self.method_combo.setCurrentIndex(1)
        else:
            self.method_combo.setCurrentIndex(0)
        grid.addWidget(self.method_combo, 2, 1)

        layout.addLayout(grid)
        layout.addStretch()

        btn_box = QHBoxLayout()
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
            QMessageBox.critical(self, "Validation Error", "Confidence level must be a number between 0 and 100.")
            return

        idx = self.alt_combo.currentIndex()
        if idx == 0:
            self.options["alternative"] = "less_than"
        elif idx == 2:
            self.options["alternative"] = "greater_than"
        else:
            self.options["alternative"] = "not_equal"

        m_idx = self.method_combo.currentIndex()
        if m_idx == 1:
            self.options["method"] = "normal"
        else:
            self.options["method"] = "exact"

        self.accept()


class OneSampleProportionDialog(QDialog):
    """Main One-Sample Proportion dialog matching 1SAMPLEPROPORTION.MDF (MenuID 41325, HelpID 95312)."""

    def __init__(self, worksheet: Optional[Worksheet] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("One-Sample Proportion")
        self.worksheet = worksheet
        self.active_edit: Optional[QLineEdit] = None
        self.result_payload: Optional[Dict[str, Any]] = None

        self.settings = one_sample_proportion_settings()
        self.resize(520, 320)
        self._build_ui()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)

        # Left: Variable List & Select
        left_box = QVBoxLayout()
        self.var_list = QListWidget()
        if self.worksheet:
            for idx, col in enumerate(self.worksheet.columns):
                self.var_list.addItem(f"C{idx+1}   {col.name}")
        self.var_list.itemDoubleClicked.connect(self._on_var_double_clicked)
        left_box.addWidget(self.var_list)

        self.select_btn = QPushButton("&Select")
        self.select_btn.clicked.connect(self._on_select_clicked)
        left_box.addWidget(self.select_btn)
        main_layout.addLayout(left_box, 1)

        # Right: Data Layout, Fields, Subdialog Buttons, Actions
        right_box = QVBoxLayout()

        self.combo_data = QComboBox()
        self.combo_data.addItems([
            "One or more samples, each in a column",
            "Summarized data",
        ])
        self.combo_data.currentIndexChanged.connect(self._on_data_format_changed)
        right_box.addWidget(self.combo_data)

        # Stacked pages for data inputs
        self.stack = QStackedWidget()

        # Page 0: Raw Column(s)
        page_raw = QWidget()
        raw_layout = QVBoxLayout(page_raw)
        raw_layout.addWidget(QLabel("Sample columns:"))
        self.sample_cols_edit = QLineEdit()
        self.sample_cols_edit.installEventFilter(self)
        raw_layout.addWidget(self.sample_cols_edit)
        raw_layout.addStretch()
        self.stack.addWidget(page_raw)

        # Page 1: Summarized Data
        page_sum = QWidget()
        sum_layout = QGridLayout(page_sum)

        sum_layout.addWidget(QLabel("Number of events:"), 0, 0)
        self.events_edit = QLineEdit("10")
        self.events_edit.installEventFilter(self)
        sum_layout.addWidget(self.events_edit, 0, 1)

        sum_layout.addWidget(QLabel("Number of trials:"), 1, 0)
        self.trials_edit = QLineEdit("20")
        self.trials_edit.installEventFilter(self)
        sum_layout.addWidget(self.trials_edit, 1, 1)

        self.stack.addWidget(page_sum)
        right_box.addWidget(self.stack)

        # Hypothesis test group
        test_group = QGroupBox()
        test_layout = QVBoxLayout(test_group)
        self.test_cb = QCheckBox("&Perform hypothesis test")
        self.test_cb.setChecked(True)
        self.test_cb.toggled.connect(self._on_test_toggled)
        test_layout.addWidget(self.test_cb)

        hyp_h = QHBoxLayout()
        self.hyp_lbl = QLabel("Hypothesized proportion:")
        hyp_h.addWidget(self.hyp_lbl)
        self.hyp_edit = QLineEdit("0.5")
        self.hyp_edit.installEventFilter(self)
        self.hyp_edit.setMaximumWidth(100)
        hyp_h.addWidget(self.hyp_edit)
        hyp_h.addStretch()
        test_layout.addLayout(hyp_h)

        right_box.addWidget(test_group)
        right_box.addStretch()

        # Subdialog Buttons (Options)
        sub_btns = QHBoxLayout()
        self.opts_btn = QPushButton("Optio&ns...")
        self.opts_btn.clicked.connect(self._on_options)
        sub_btns.addWidget(self.opts_btn)
        sub_btns.addStretch()
        right_box.addLayout(sub_btns)

        # Action Buttons (OK, Cancel, Help)
        action_btns = QHBoxLayout()
        action_btns.addStretch()
        self.ok_btn = QPushButton("&OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.help_btn = QPushButton("Help")
        action_btns.addWidget(self.ok_btn)
        action_btns.addWidget(self.cancel_btn)
        action_btns.addWidget(self.help_btn)
        right_box.addLayout(action_btns)

        main_layout.addLayout(right_box, 2)

        # Set default active edit
        self.active_edit = self.sample_cols_edit

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn and isinstance(obj, QLineEdit):
            self.active_edit = obj
        return super().eventFilter(obj, event)

    def _on_data_format_changed(self, index: int):
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.active_edit = self.sample_cols_edit
        else:
            self.active_edit = self.events_edit

    def _on_test_toggled(self, checked: bool):
        self.hyp_lbl.setEnabled(checked)
        self.hyp_edit.setEnabled(checked)

    def _on_var_double_clicked(self, item):
        self._insert_var_text(item.text().split()[0])

    def _on_select_clicked(self):
        item = self.var_list.currentItem()
        if item:
            self._insert_var_text(item.text().split()[0])

    def _insert_var_text(self, var_id: str):
        if self.active_edit:
            cur = self.active_edit.text().strip()
            if self.active_edit == self.sample_cols_edit:
                # Can append multiple columns
                if cur:
                    self.active_edit.setText(f"{cur} {var_id}")
                else:
                    self.active_edit.setText(var_id)
            else:
                self.active_edit.setText(var_id)

    def _on_options(self):
        dlg = OneSampleProportionOptionsDialog(self.settings, self)
        if dlg.exec():
            self.settings.update(dlg.options)

    def _on_ok(self):
        idx = self.combo_data.currentIndex()
        perform_test = self.test_cb.isChecked()
        hyp_p = 0.5
        if perform_test:
            try:
                hyp_p = float(self.hyp_edit.text().strip())
                if not (0.0 < hyp_p < 1.0):
                    raise ValueError
            except ValueError:
                QMessageBox.critical(self, "Validation Error", "Hypothesized proportion must be a number between 0 and 1.")
                return

        if idx == 0:  # Raw Columns
            cols_text = self.sample_cols_edit.text().strip()
            if not cols_text:
                QMessageBox.critical(self, "Validation Error", "Please specify at least one sample column.")
                return
            col_tokens = cols_text.split()
            cols: List[Any] = []
            for tok in col_tokens:
                if tok.upper().startswith("C") and tok[1:].isdigit():
                    cols.append(int(tok[1:]) - 1)
                else:
                    cols.append(tok)

            self.settings["data_format"] = 0
            self.settings["sample_cols"] = cols
            self.settings["perform_test"] = perform_test
            self.settings["hypothesized_proportion"] = hyp_p
        else:  # Summarized
            try:
                events = int(self.events_edit.text().strip())
                trials = int(self.trials_edit.text().strip())
                if events < 0:
                    raise ValueError
                if trials < 1:
                    raise ValueError
                if events > trials:
                    QMessageBox.critical(self, "Validation Error", "Number of events cannot exceed number of trials.")
                    return
            except ValueError:
                QMessageBox.critical(
                    self, "Validation Error",
                    "Please enter valid non-negative integer values for events and trials (trials >= 1)."
                )
                return

            self.settings["data_format"] = 2
            self.settings["summarized"] = {"events": events, "trials": trials}
            self.settings["perform_test"] = perform_test
            self.settings["hypothesized_proportion"] = hyp_p

        self.result_payload = dict(self.settings)
        self.accept()
