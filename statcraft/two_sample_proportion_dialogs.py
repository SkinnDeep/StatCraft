"""Dialogs for native StatCraft Two-Sample Proportion test."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QCheckBox, QListWidget,
    QStackedWidget, QWidget, QMessageBox
)
from .model import Worksheet
from .two_sample_proportion_engine import two_sample_proportion_settings


class TwoSampleProportionOptionsDialog(QDialog):
    """Options child dialog matching 2SAMPLEPROPORTIONOPTIONS.MDF (HelpID 95315)."""

    def __init__(self, options: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Two-Sample Proportion: Options")
        self.setModal(True)
        self.options = dict(options)
        self.resize(380, 200)

        layout = QVBoxLayout(self)
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

        grid.addWidget(QLabel("Test method:"), 3, 0)
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Estimate the proportions separately",
            "Use the pooled estimate of the proportion",
        ])
        method_val = self.options.get("test_method", "pooled")
        if method_val == "unpooled":
            self.method_combo.setCurrentIndex(0)
        else:
            self.method_combo.setCurrentIndex(1)
        grid.addWidget(self.method_combo, 3, 1)

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

        m_idx = self.method_combo.currentIndex()
        if m_idx == 0:
            self.options["test_method"] = "unpooled"
        else:
            self.options["test_method"] = "pooled"

        self.accept()


class TwoSampleProportionDialog(QDialog):
    """Main Two-Sample Proportion dialog matching 2SAMPLEPROPORTION.MDF (MenuID 41326, HelpID 95314)."""

    def __init__(self, worksheet: Optional[Worksheet] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Two-Sample Proportion")
        self.worksheet = worksheet
        self.active_edit: Optional[QLineEdit] = None
        self.result_payload: Optional[Dict[str, Any]] = None

        self.settings = two_sample_proportion_settings()
        self.resize(540, 320)
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
            "Both samples are in one column",
            "Each sample is in its own column",
            "Summarized data",
        ])
        self.combo_data.setCurrentIndex(1)  # Default: Each sample is in its own column
        self.combo_data.currentIndexChanged.connect(self._on_data_format_changed)
        right_box.addWidget(self.combo_data)

        # Stacked pages for data inputs
        self.stack = QStackedWidget()

        # Page 0: Stacked Mode
        page_stacked = QWidget()
        l_st = QGridLayout(page_stacked)
        l_st.addWidget(QLabel("Samples:"), 0, 0)
        self.samples_edit = QLineEdit()
        self.samples_edit.installEventFilter(self)
        l_st.addWidget(self.samples_edit, 0, 1)
        l_st.addWidget(QLabel("Sample IDs:"), 1, 0)
        self.ids_edit = QLineEdit()
        self.ids_edit.installEventFilter(self)
        l_st.addWidget(self.ids_edit, 1, 1)
        l_st.setRowStretch(2, 1)
        self.stack.addWidget(page_stacked)

        # Page 1: Unstacked Mode (Default)
        page_unstacked = QWidget()
        l_un = QGridLayout(page_unstacked)
        l_un.addWidget(QLabel("Sample 1:"), 0, 0)
        self.sample1_edit = QLineEdit()
        self.sample1_edit.installEventFilter(self)
        l_un.addWidget(self.sample1_edit, 0, 1)
        l_un.addWidget(QLabel("Sample 2:"), 1, 0)
        self.sample2_edit = QLineEdit()
        self.sample2_edit.installEventFilter(self)
        l_un.addWidget(self.sample2_edit, 1, 1)
        l_un.setRowStretch(2, 1)
        self.stack.addWidget(page_unstacked)

        # Page 2: Summarized Data Mode
        page_summ = QWidget()
        l_sum = QGridLayout(page_summ)
        l_sum.addWidget(QLabel("Sample 1"), 0, 1, Qt.AlignmentFlag.AlignCenter)
        l_sum.addWidget(QLabel("Sample 2"), 0, 2, Qt.AlignmentFlag.AlignCenter)

        l_sum.addWidget(QLabel("Number of events:"), 1, 0)
        self.events1_edit = QLineEdit("10")
        self.events2_edit = QLineEdit("10")
        self.events1_edit.installEventFilter(self)
        self.events2_edit.installEventFilter(self)
        l_sum.addWidget(self.events1_edit, 1, 1)
        l_sum.addWidget(self.events2_edit, 1, 2)

        l_sum.addWidget(QLabel("Number of trials:"), 2, 0)
        self.trials1_edit = QLineEdit("20")
        self.trials2_edit = QLineEdit("20")
        self.trials1_edit.installEventFilter(self)
        self.trials2_edit.installEventFilter(self)
        l_sum.addWidget(self.trials1_edit, 2, 1)
        l_sum.addWidget(self.trials2_edit, 2, 2)
        l_sum.setRowStretch(3, 1)
        self.stack.addWidget(page_summ)

        self.stack.setCurrentIndex(1)
        right_box.addWidget(self.stack)

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
        self.active_edit = self.sample1_edit

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn and isinstance(obj, QLineEdit):
            self.active_edit = obj
        return super().eventFilter(obj, event)

    def _on_data_format_changed(self, index: int):
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.active_edit = self.samples_edit
        elif index == 1:
            self.active_edit = self.sample1_edit
        else:
            self.active_edit = self.events1_edit

    def _on_var_double_clicked(self, item):
        self._insert_var_text(item.text().split()[0])

    def _on_select_clicked(self):
        item = self.var_list.currentItem()
        if item:
            self._insert_var_text(item.text().split()[0])

    def _insert_var_text(self, var_id: str):
        if self.active_edit:
            self.active_edit.setText(var_id)

    def _on_options(self):
        dlg = TwoSampleProportionOptionsDialog(self.settings, self)
        if dlg.exec():
            self.settings.update(dlg.options)

    def _parse_col(self, text: str) -> Any:
        tok = text.strip()
        if tok.upper().startswith("C") and tok[1:].isdigit():
            return int(tok[1:]) - 1
        return tok

    def _on_ok(self):
        idx = self.combo_data.currentIndex()
        if idx == 0:  # Stacked
            s_text = self.samples_edit.text().strip()
            id_text = self.ids_edit.text().strip()
            if not s_text or not id_text:
                QMessageBox.critical(self, "Validation Error", "Please specify both the samples column and sample ID column.")
                return
            self.settings["data_format"] = 0
            self.settings["samples_col"] = self._parse_col(s_text)
            self.settings["sample_ids_col"] = self._parse_col(id_text)
        elif idx == 1:  # Unstacked
            s1_text = self.sample1_edit.text().strip()
            s2_text = self.sample2_edit.text().strip()
            if not s1_text or not s2_text:
                QMessageBox.critical(self, "Validation Error", "Please specify both sample columns.")
                return
            self.settings["data_format"] = 1
            self.settings["sample1_col"] = self._parse_col(s1_text)
            self.settings["sample2_col"] = self._parse_col(s2_text)
        else:  # Summarized
            try:
                x1 = int(self.events1_edit.text().strip())
                n1 = int(self.trials1_edit.text().strip())
                x2 = int(self.events2_edit.text().strip())
                n2 = int(self.trials2_edit.text().strip())
                if x1 < 0 or x2 < 0 or n1 < 1 or n2 < 1 or x1 > n1 or x2 > n2:
                    raise ValueError
            except ValueError:
                QMessageBox.critical(
                    self, "Validation Error",
                    "Please enter valid non-negative integer values for events and trials (trials >= 1, events <= trials)."
                )
                return
            self.settings["data_format"] = 2
            self.settings["summarized"] = {
                "events1": x1, "trials1": n1,
                "events2": x2, "trials2": n2,
            }

        self.result_payload = dict(self.settings)
        self.accept()
