"""Dialogs for native StatCraft One-Sample Z test."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QCheckBox, QListWidget,
    QStackedWidget, QWidget, QMessageBox, QGroupBox
)
from .model import Worksheet
from .one_sample_z_engine import one_sample_z_settings


class OneSampleZOptionsDialog(QDialog):
    """Options child dialog matching 1SAMPLEZOPTIONS.MDF (HelpID 95301)."""

    def __init__(self, options: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("One-Sample Z: Options")
        self.setModal(True)
        self.options = dict(options)
        self.resize(340, 160)

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        grid.addWidget(QLabel("Confidence level:"), 0, 0)
        self.conf_edit = QLineEdit(str(self.options.get("confidence_level", 95.0)))
        self.conf_edit.setMaximumWidth(90)
        grid.addWidget(self.conf_edit, 0, 1)

        grid.addWidget(QLabel("Alternative hypothesis:"), 1, 0)
        self.alt_combo = QComboBox()
        self.alt_combo.addItems([
            "Mean < hypothesized mean",
            "Mean ≠ hypothesized mean",
            "Mean > hypothesized mean",
        ])
        alt_val = self.options.get("alternative", "not_equal")
        if alt_val == "less_than":
            self.alt_combo.setCurrentIndex(0)
        elif alt_val == "greater_than":
            self.alt_combo.setCurrentIndex(2)
        else:
            self.alt_combo.setCurrentIndex(1)
        grid.addWidget(self.alt_combo, 1, 1)

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

        self.accept()


class OneSampleZGraphsDialog(QDialog):
    """Graphs child dialog matching 1SAMPLEZGRAPHS.MDF (HelpID 95302)."""

    def __init__(self, graphs: Dict[str, bool], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("One-Sample Z: Graphs")
        self.setModal(True)
        self.graphs = dict(graphs)
        self.resize(280, 160)

        layout = QVBoxLayout(self)

        self.hist_cb = QCheckBox("&Histogram")
        self.hist_cb.setChecked(bool(self.graphs.get("histogram", True)))
        layout.addWidget(self.hist_cb)

        self.ivp_cb = QCheckBox("&Individual value plot")
        self.ivp_cb.setChecked(bool(self.graphs.get("individual_value_plot", True)))
        layout.addWidget(self.ivp_cb)

        self.box_cb = QCheckBox("&Boxplot")
        self.box_cb.setChecked(bool(self.graphs.get("boxplot", True)))
        layout.addWidget(self.box_cb)

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
        self.graphs["histogram"] = self.hist_cb.isChecked()
        self.graphs["individual_value_plot"] = self.ivp_cb.isChecked()
        self.graphs["boxplot"] = self.box_cb.isChecked()
        self.accept()


class OneSampleZDialog(QDialog):
    """Main One-Sample Z dialog matching 1SAMPLEZ.MDF (MenuID 41323, HelpID 95300)."""

    def __init__(self, worksheet: Optional[Worksheet] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("One-Sample Z for the Mean")
        self.worksheet = worksheet
        self.active_edit: Optional[QLineEdit] = None
        self.result_payload: Optional[Dict[str, Any]] = None

        self.settings = one_sample_z_settings()
        self.resize(520, 360)
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

        sum_layout.addWidget(QLabel("Sample size:"), 0, 0)
        self.size_edit = QLineEdit("10")
        self.size_edit.installEventFilter(self)
        sum_layout.addWidget(self.size_edit, 0, 1)

        sum_layout.addWidget(QLabel("Sample mean:"), 1, 0)
        self.mean_edit = QLineEdit("0.0")
        self.mean_edit.installEventFilter(self)
        sum_layout.addWidget(self.mean_edit, 1, 1)

        self.stack.addWidget(page_sum)
        right_box.addWidget(self.stack)

        # Known Standard Deviation (mandatory in 1SAMPLEZ.MDF)
        sd_box = QHBoxLayout()
        self.sd_lbl = QLabel("Known standard deviation:")
        sd_box.addWidget(self.sd_lbl)
        self.sigma_edit = QLineEdit("1.0")
        self.sigma_edit.installEventFilter(self)
        self.sigma_edit.setMaximumWidth(100)
        sd_box.addWidget(self.sigma_edit)
        sd_box.addStretch()
        right_box.addLayout(sd_box)

        # Hypothesis test group
        test_group = QGroupBox()
        test_layout = QVBoxLayout(test_group)
        self.test_cb = QCheckBox("&Perform hypothesis test")
        self.test_cb.setChecked(True)
        self.test_cb.toggled.connect(self._on_test_toggled)
        test_layout.addWidget(self.test_cb)

        hyp_h = QHBoxLayout()
        self.hyp_lbl = QLabel("Hypothesized mean:")
        hyp_h.addWidget(self.hyp_lbl)
        self.hyp_edit = QLineEdit("0.0")
        self.hyp_edit.installEventFilter(self)
        self.hyp_edit.setMaximumWidth(100)
        hyp_h.addWidget(self.hyp_edit)
        hyp_h.addStretch()
        test_layout.addLayout(hyp_h)

        right_box.addWidget(test_group)
        right_box.addStretch()

        # Subdialog Buttons (Options, Graphs)
        sub_btns = QHBoxLayout()
        self.opts_btn = QPushButton("Optio&ns...")
        self.opts_btn.clicked.connect(self._on_options)
        self.graphs_btn = QPushButton("&Graphs...")
        self.graphs_btn.clicked.connect(self._on_graphs)
        sub_btns.addWidget(self.opts_btn)
        sub_btns.addWidget(self.graphs_btn)
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
        # In StatCraft, Graphs button is disabled when summarized data is selected (ButtonGraphs.Enable = This.Value <> 2)
        self.graphs_btn.setEnabled(index != 1)
        if index == 0:
            self.active_edit = self.sample_cols_edit
        else:
            self.active_edit = self.size_edit

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
        dlg = OneSampleZOptionsDialog(self.settings, self)
        if dlg.exec():
            self.settings.update(dlg.options)

    def _on_graphs(self):
        dlg = OneSampleZGraphsDialog(self.settings["graphs"], self)
        if dlg.exec():
            self.settings["graphs"] = dlg.graphs

    def _on_ok(self):
        # Validate known standard deviation (sigma > 0)
        try:
            sigma = float(self.sigma_edit.text().strip())
            if sigma <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.critical(self, "Validation Error", "Known standard deviation must be a positive number (> 0).")
            return

        idx = self.combo_data.currentIndex()
        perform_test = self.test_cb.isChecked()
        hyp_mean = 0.0
        if perform_test:
            try:
                hyp_mean = float(self.hyp_edit.text().strip())
            except ValueError:
                QMessageBox.critical(self, "Validation Error", "Hypothesized mean must be a valid number.")
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
            self.settings["sigma"] = sigma
            self.settings["perform_test"] = perform_test
            self.settings["hypothesized_mean"] = hyp_mean
        else:  # Summarized
            try:
                n = int(self.size_edit.text().strip())
                if n < 1:
                    raise ValueError
                m = float(self.mean_edit.text().strip())
            except ValueError:
                QMessageBox.critical(
                    self, "Validation Error",
                    "Please enter valid summarized values (Sample size >= 1)."
                )
                return

            self.settings["data_format"] = 2
            self.settings["summarized"] = {"n": n, "mean": m}
            self.settings["sigma"] = sigma
            self.settings["perform_test"] = perform_test
            self.settings["hypothesized_mean"] = hyp_mean
            self.settings["graphs"] = {"histogram": False, "individual_value_plot": False, "boxplot": False}

        self.result_payload = dict(self.settings)
        self.accept()
