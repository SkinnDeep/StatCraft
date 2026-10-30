"""Dialogs for native StatCraft Two-Sample t test."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QCheckBox, QListWidget,
    QStackedWidget, QWidget, QMessageBox, QGroupBox
)
from .model import Worksheet
from .two_sample_t_engine import two_sample_t_settings


class TwoSampleTOptionsDialog(QDialog):
    """Options child dialog matching 2SAMPLETOPTIONS.MDF."""

    def __init__(self, options: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Two-Sample t: Options")
        self.setModal(True)
        self.options = dict(options)
        self.resize(360, 200)

        layout = QVBoxLayout(self)

        diff_label = QLabel("Difference = (sample 1 mean) - (sample 2 mean)")
        diff_label.setStyleSheet("color: #444; font-weight: bold;")
        layout.addWidget(diff_label)

        grid = QGridLayout()

        grid.addWidget(QLabel("Confidence level:"), 0, 0)
        self.conf_edit = QLineEdit(str(self.options.get("confidence_level", 95.0)))
        self.conf_edit.setMaximumWidth(90)
        grid.addWidget(self.conf_edit, 0, 1)

        grid.addWidget(QLabel("Hypothesized difference:"), 1, 0)
        self.hyp_edit = QLineEdit(str(self.options.get("hypothesized_difference", 0.0)))
        self.hyp_edit.setMaximumWidth(90)
        grid.addWidget(self.hyp_edit, 1, 1)

        grid.addWidget(QLabel("Alternative hypothesis:"), 2, 0)
        self.alt_combo = QComboBox()
        self.alt_combo.addItems([
            "Difference < hypothesized difference",
            "Difference ≠ hypothesized difference",
            "Difference > hypothesized difference",
        ])
        alt_val = self.options.get("alternative", "not_equal")
        if alt_val == "less_than":
            self.alt_combo.setCurrentIndex(0)
        elif alt_val == "greater_than":
            self.alt_combo.setCurrentIndex(2)
        else:
            self.alt_combo.setCurrentIndex(1)
        grid.addWidget(self.alt_combo, 2, 1)

        layout.addLayout(grid)

        self.pooled_cb = QCheckBox("Assume &equal variances")
        self.pooled_cb.setChecked(bool(self.options.get("assume_equal_variances", False)))
        layout.addWidget(self.pooled_cb)

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

        try:
            h = float(self.hyp_edit.text().strip())
            self.options["hypothesized_difference"] = h
        except ValueError:
            QMessageBox.critical(self, "Validation Error", "Hypothesized difference must be a valid number.")
            return

        idx = self.alt_combo.currentIndex()
        if idx == 0:
            self.options["alternative"] = "less_than"
        elif idx == 2:
            self.options["alternative"] = "greater_than"
        else:
            self.options["alternative"] = "not_equal"

        self.options["assume_equal_variances"] = self.pooled_cb.isChecked()
        self.accept()


class TwoSampleTGraphsDialog(QDialog):
    """Graphs child dialog matching 2SAMPLETGRAPHS.MDF."""

    def __init__(self, graphs: Dict[str, bool], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Two-Sample t: Graphs")
        self.setModal(True)
        self.graphs = dict(graphs)
        self.resize(300, 140)

        layout = QVBoxLayout(self)

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
        self.graphs["individual_value_plot"] = self.ivp_cb.isChecked()
        self.graphs["boxplot"] = self.box_cb.isChecked()
        self.accept()


class TwoSampleTDialog(QDialog):
    """Main Two-Sample t dialog matching 2SAMPLET.MDF (MenuID 41321)."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Two-Sample t for the Mean")
        self.setModal(True)
        self.resize(520, 320)

        self.settings = two_sample_t_settings()
        self.result_payload: Optional[Dict[str, Any]] = None

        main_layout = QHBoxLayout(self)

        # Left Column: Column List Box
        left_box = QVBoxLayout()
        left_label = QLabel("Columns:")
        left_box.addWidget(left_label)
        self.var_list = QListWidget()
        for i, col in enumerate(worksheet.columns):
            self.var_list.addItem(f"C{i + 1} {col.name}")
        self.var_list.itemDoubleClicked.connect(self._on_select_clicked)
        left_box.addWidget(self.var_list)

        self.select_btn = QPushButton("&Select")
        self.select_btn.clicked.connect(self._on_select_clicked)
        left_box.addWidget(self.select_btn)
        main_layout.addLayout(left_box, 1)

        # Right Column
        right_box = QVBoxLayout()

        # ComboBox for data arrangement
        self.combo_data = QComboBox()
        self.combo_data.addItem("Both samples are in one column", 0)
        self.combo_data.addItem("Each sample is in its own column", 1)
        self.combo_data.addItem("Summarized data", 2)
        self.combo_data.currentIndexChanged.connect(self._on_data_format_changed)
        right_box.addWidget(self.combo_data)

        # Stacked widgets for the 3 modes
        self.stack = QStackedWidget()

        # Page 0: Stacked Mode
        page_stacked = QWidget()
        l_st = QGridLayout(page_stacked)
        l_st.addWidget(QLabel("Samples:"), 0, 0)
        self.samples_edit = QLineEdit()
        l_st.addWidget(self.samples_edit, 0, 1)
        l_st.addWidget(QLabel("Sample IDs:"), 1, 0)
        self.ids_edit = QLineEdit()
        l_st.addWidget(self.ids_edit, 1, 1)
        l_st.setRowStretch(2, 1)
        self.stack.addWidget(page_stacked)

        # Page 1: Unstacked Mode (Default)
        page_unstacked = QWidget()
        l_un = QGridLayout(page_unstacked)
        l_un.addWidget(QLabel("Sample 1:"), 0, 0)
        self.sample1_edit = QLineEdit()
        l_un.addWidget(self.sample1_edit, 0, 1)
        l_un.addWidget(QLabel("Sample 2:"), 1, 0)
        self.sample2_edit = QLineEdit()
        l_un.addWidget(self.sample2_edit, 1, 1)
        l_un.setRowStretch(2, 1)
        self.stack.addWidget(page_unstacked)

        # Page 2: Summarized Data Mode
        page_summ = QWidget()
        l_sum = QGridLayout(page_summ)
        l_sum.addWidget(QLabel("Sample 1"), 0, 1, Qt.AlignmentFlag.AlignCenter)
        l_sum.addWidget(QLabel("Sample 2"), 0, 2, Qt.AlignmentFlag.AlignCenter)

        l_sum.addWidget(QLabel("Sample size:"), 1, 0)
        self.size1_edit = QLineEdit("10")
        self.size2_edit = QLineEdit("10")
        l_sum.addWidget(self.size1_edit, 1, 1)
        l_sum.addWidget(self.size2_edit, 1, 2)

        l_sum.addWidget(QLabel("Sample mean:"), 2, 0)
        self.mean1_edit = QLineEdit("0.0")
        self.mean2_edit = QLineEdit("0.0")
        l_sum.addWidget(self.mean1_edit, 2, 1)
        l_sum.addWidget(self.mean2_edit, 2, 2)

        l_sum.addWidget(QLabel("Standard deviation:"), 3, 0)
        self.sd1_edit = QLineEdit("1.0")
        self.sd2_edit = QLineEdit("1.0")
        l_sum.addWidget(self.sd1_edit, 3, 1)
        l_sum.addWidget(self.sd2_edit, 3, 2)
        l_sum.setRowStretch(4, 1)
        self.stack.addWidget(page_summ)

        right_box.addWidget(self.stack)

        # Focus tracking for Select button
        self._last_active_edit: Optional[QLineEdit] = self.sample1_edit
        self.samples_edit.installEventFilter(self)
        self.ids_edit.installEventFilter(self)
        self.sample1_edit.installEventFilter(self)
        self.sample2_edit.installEventFilter(self)

        # Buttons (Options, Graphs, OK, Cancel)
        sub_btn_box = QHBoxLayout()
        sub_btn_box.addStretch()
        self.options_btn = QPushButton("Optio&ns...")
        self.options_btn.clicked.connect(self._open_options)
        self.graphs_btn = QPushButton("&Graphs...")
        self.graphs_btn.clicked.connect(self._open_graphs)
        sub_btn_box.addWidget(self.options_btn)
        sub_btn_box.addWidget(self.graphs_btn)
        right_box.addLayout(sub_btn_box)

        action_box = QHBoxLayout()
        action_box.addStretch()
        self.ok_btn = QPushButton("&OK")
        self.ok_btn.clicked.connect(self._on_ok)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        action_box.addWidget(self.ok_btn)
        action_box.addWidget(self.cancel_btn)
        right_box.addLayout(action_box)

        main_layout.addLayout(right_box, 2)

        # Default to unstacked (Index 1)
        self.combo_data.setCurrentIndex(1)
        self.stack.setCurrentIndex(1)

    def eventFilter(self, watched, event):
        if event.type() == event.Type.FocusIn:
            if isinstance(watched, QLineEdit):
                self._last_active_edit = watched
        return super().eventFilter(watched, event)

    def _on_data_format_changed(self, idx: int):
        self.stack.setCurrentIndex(idx)
        # In summarized mode (2), Graphs button and column list are disabled
        is_summ = (idx == 2)
        self.graphs_btn.setEnabled(not is_summ)
        self.var_list.setEnabled(not is_summ)
        self.select_btn.setEnabled(not is_summ)

        if idx == 0:
            self._last_active_edit = self.samples_edit
        elif idx == 1:
            self._last_active_edit = self.sample1_edit
        else:
            self._last_active_edit = self.size1_edit

    def _on_select_clicked(self):
        item = self.var_list.currentItem()
        if not item or not self._last_active_edit:
            return
        col_ref = item.text().split()[0]  # e.g., 'C1'
        self._last_active_edit.setText(col_ref)

    def _resolve_col(self, text: str) -> Optional[int]:
        s = text.strip()
        if not s:
            return None
        if s.upper().startswith("C"):
            try:
                num = int(s[1:]) - 1
                if 0 <= num < len(self.worksheet.columns):
                    return num
            except ValueError:
                pass
        for i, c in enumerate(self.worksheet.columns):
            if c.name.lower() == s.lower():
                return i
        return None

    def _open_options(self):
        dlg = TwoSampleTOptionsDialog(self.settings, self)
        if dlg.exec():
            self.settings["confidence_level"] = dlg.options["confidence_level"]
            self.settings["hypothesized_difference"] = dlg.options["hypothesized_difference"]
            self.settings["alternative"] = dlg.options["alternative"]
            self.settings["assume_equal_variances"] = dlg.options["assume_equal_variances"]

    def _open_graphs(self):
        dlg = TwoSampleTGraphsDialog(self.settings["graphs"], self)
        if dlg.exec():
            self.settings["graphs"] = dlg.graphs

    def _on_ok(self):
        fmt = self.combo_data.currentIndex()
        self.settings["data_format"] = fmt

        if fmt == 0:  # Stacked
            samp = self._resolve_col(self.samples_edit.text())
            ids = self._resolve_col(self.ids_edit.text())
            if samp is None or ids is None:
                QMessageBox.critical(self, "Invalid Selection", "Please specify valid columns for Samples and Sample IDs.")
                return
            if samp == ids:
                QMessageBox.critical(self, "Invalid Selection", "Samples and Sample IDs must be distinct columns.")
                return
            self.settings["samples_col"] = samp
            self.settings["sample_ids_col"] = ids
        elif fmt == 1:  # Unstacked
            s1 = self._resolve_col(self.sample1_edit.text())
            s2 = self._resolve_col(self.sample2_edit.text())
            if s1 is None or s2 is None:
                QMessageBox.critical(self, "Invalid Selection", "Please specify valid columns for Sample 1 and Sample 2.")
                return
            if s1 == s2:
                QMessageBox.critical(self, "Invalid Selection", "Sample 1 and Sample 2 must be distinct columns.")
                return
            self.settings["sample1_col"] = s1
            self.settings["sample2_col"] = s2
        else:  # Summarized
            try:
                n1 = int(self.size1_edit.text().strip())
                m1 = float(self.mean1_edit.text().strip())
                sd1 = float(self.sd1_edit.text().strip())
                n2 = int(self.size2_edit.text().strip())
                m2 = float(self.mean2_edit.text().strip())
                sd2 = float(self.sd2_edit.text().strip())
                if n1 < 2 or n2 < 2:
                    raise ValueError("Sample sizes must be at least 2.")
                if sd1 < 0 or sd2 < 0:
                    raise ValueError("Standard deviations cannot be negative.")
                self.settings["summarized"] = {
                    "n1": n1, "mean1": m1, "sd1": sd1,
                    "n2": n2, "mean2": m2, "sd2": sd2,
                }
            except ValueError as e:
                QMessageBox.critical(self, "Validation Error", str(e) or "Please enter valid numbers for summarized data.")
                return

        self.result_payload = dict(self.settings)
        self.accept()
