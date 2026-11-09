"""Native StatCraft Capability Sixpack (Normal) dialogs.

Corresponds to PE MenuID 40168 and HelpID 95021:
Main dialog: Capability Sixpack (Normal Distribution)
Child dialogs:
- Options: Capability Analysis (0471-CAPABILITY.MDF)
- Estimate: Estimating Standard Deviation (1017-QUALITYESTSIGMA.MDF)
- Tests: Tests for Special Causes (Control charts in Sixpack)
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QListWidget,
    QMessageBox,
    QFrame,
    QGroupBox,
)

from .capability_dialogs import CapabilityOptionsDialog, CapabilityEstimateDialog


class SixpackTestsDialog(QDialog):
    """Tests for Special Causes in Capability Sixpack control charts."""

    def __init__(self, options: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Capability Sixpack: Tests")
        self.setModal(True)
        self.options = dict(options or {})

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        box = QGroupBox("Perform tests for special causes")
        box_layout = QVBoxLayout(box)
        box_layout.setSpacing(8)

        self.chk_test1 = QCheckBox("1 point > 3.00 standard deviations from center line")
        self.chk_test1.setChecked(self.options.get("test1", True))
        box_layout.addWidget(self.chk_test1)

        self.chk_test2 = QCheckBox("9 points in a row on same side of center line")
        self.chk_test2.setChecked(self.options.get("test2", False))
        box_layout.addWidget(self.chk_test2)

        self.chk_test3 = QCheckBox("6 points in a row, all increasing or all decreasing")
        self.chk_test3.setChecked(self.options.get("test3", False))
        box_layout.addWidget(self.chk_test3)

        self.chk_test4 = QCheckBox("14 points in a row, alternating up and down")
        self.chk_test4.setChecked(self.options.get("test4", False))
        box_layout.addWidget(self.chk_test4)

        layout.addWidget(box)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(self._accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _accept(self):
        self.options["test1"] = self.chk_test1.isChecked()
        self.options["test2"] = self.chk_test2.isChecked()
        self.options["test3"] = self.chk_test3.isChecked()
        self.options["test4"] = self.chk_test4.isChecked()
        self.accept()


class CapabilitySixpackDialog(QDialog):
    """Main dialog for Stat > Quality Tools > Capability Sixpack > Normal / Between/Within."""

    def __init__(self, worksheet=None, parent=None, analysis_mode: str = "normal"):
        super().__init__(parent)
        self.analysis_mode = analysis_mode
        title_mode = "Between/Within" if analysis_mode == "between_within" else "Normal Distribution"
        self.setWindowTitle(f"Capability Sixpack ({title_mode})")
        self.resize(580, 430)
        self.worksheet = worksheet
        self.columns: List[str] = []
        if worksheet and hasattr(worksheet, "columns"):
            self.columns = [c.name for c in worksheet.columns]

        self.selected_params: Optional[Dict[str, Any]] = None
        self.options: Dict[str, Any] = {
            "tolerance_k": 6.0,
            "stats_type": "capability",
            "display_unit": "ppm",
            "confidence_level": 95.0,
            "ci_type": "two_sided",
            "include_ci": False,
            "include_ccpk": False,
            "within_subgroup_method": "pooled",
            "unbiased_within": True,
            "unbiased_overall": False,
            "test1": True,
        }

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(12)

        # Left Column List
        left_layout = QVBoxLayout()
        lbl_cols = QLabel("Columns:")
        left_layout.addWidget(lbl_cols)

        self.col_list = QListWidget()
        for c in self.columns:
            self.col_list.addItem(c)
        self.col_list.itemDoubleClicked.connect(self._insert_selected_column)
        left_layout.addWidget(self.col_list)

        btn_select = QPushButton("Select")
        btn_select.clicked.connect(self._insert_selected_column)
        left_layout.addWidget(btn_select)
        main_layout.addLayout(left_layout, 1)

        # Center Controls Layout
        center_layout = QVBoxLayout()
        center_layout.setSpacing(10)

        # 1. Data Arrangement Group
        arr_box = QGroupBox("Data arrangement")
        arr_layout = QVBoxLayout(arr_box)

        # Option A: Single column
        self.rb_single_col = QRadioButton("Data are in &one column:")
        self.rb_across_rows = QRadioButton("Subgroups across &rows of:")
        self.arr_group = QButtonGroup(self)
        self.arr_group.addButton(self.rb_single_col)
        self.arr_group.addButton(self.rb_across_rows)
        self.rb_single_col.setChecked(True)

        sc_grid = QGridLayout()
        self.edit_single_col = QLineEdit()
        self.rb_single_col.toggled.connect(self._update_arrangement_state)
        sc_grid.addWidget(self.rb_single_col, 0, 0)
        sc_grid.addWidget(self.edit_single_col, 0, 1)

        lbl_sub_size = QLabel("&Subgroup size:")
        self.edit_sub_size = QLineEdit("1")
        lbl_sub_size.setBuddy(self.edit_sub_size)
        sc_grid.addWidget(lbl_sub_size, 1, 0, Qt.AlignmentFlag.AlignRight)
        sc_grid.addWidget(self.edit_sub_size, 1, 1)
        arr_layout.addLayout(sc_grid)

        # Option B: Across rows
        ar_grid = QGridLayout()
        self.edit_across_rows = QLineEdit()
        ar_grid.addWidget(self.rb_across_rows, 0, 0)
        ar_grid.addWidget(self.edit_across_rows, 0, 1)
        arr_layout.addLayout(ar_grid)

        center_layout.addWidget(arr_box)

        # 2. Specification Limits Group
        spec_box = QGroupBox("Specification limits (at least 1 required)")
        spec_grid = QGridLayout(spec_box)

        lbl_lsl = QLabel("&Lower spec:")
        self.edit_lsl = QLineEdit()
        lbl_lsl.setBuddy(self.edit_lsl)
        self.chk_lsl_bound = QCheckBox("Bound")
        spec_grid.addWidget(lbl_lsl, 0, 0)
        spec_grid.addWidget(self.edit_lsl, 0, 1)
        spec_grid.addWidget(self.chk_lsl_bound, 0, 2)

        lbl_usl = QLabel("&Upper spec:")
        self.edit_usl = QLineEdit()
        lbl_usl.setBuddy(self.edit_usl)
        self.chk_usl_bound = QCheckBox("Bound")
        spec_grid.addWidget(lbl_usl, 1, 0)
        spec_grid.addWidget(self.edit_usl, 1, 1)
        spec_grid.addWidget(self.chk_usl_bound, 1, 2)

        center_layout.addWidget(spec_box)

        # 3. Historical Parameters Group (Optional)
        hist_box = QGroupBox("Historical parameters (optional)")
        hist_grid = QGridLayout(hist_box)

        lbl_hmean = QLabel("Historical &mean:")
        self.edit_hmean = QLineEdit()
        lbl_hmean.setBuddy(self.edit_hmean)
        hist_grid.addWidget(lbl_hmean, 0, 0)
        hist_grid.addWidget(self.edit_hmean, 0, 1)

        lbl_hsd = QLabel("Historical &standard deviation:")
        self.edit_hsd = QLineEdit()
        lbl_hsd.setBuddy(self.edit_hsd)
        hist_grid.addWidget(lbl_hsd, 1, 0)
        hist_grid.addWidget(self.edit_hsd, 1, 1)

        center_layout.addWidget(hist_box)
        main_layout.addLayout(center_layout, 2)

        # Right Action Buttons
        right_layout = QVBoxLayout()
        right_layout.setSpacing(8)

        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_cancel = QPushButton("Cancel")
        btn_help = QPushButton("Help")

        btn_estimate = QPushButton("&Estimate...")
        btn_options = QPushButton("O&ptions...")
        btn_tests = QPushButton("&Tests...")

        btn_ok.clicked.connect(self._accept)
        btn_cancel.clicked.connect(self.reject)
        btn_estimate.clicked.connect(self._open_estimate)
        btn_options.clicked.connect(self._open_options)
        btn_tests.clicked.connect(self._open_tests)

        right_layout.addWidget(btn_ok)
        right_layout.addWidget(btn_cancel)
        right_layout.addWidget(btn_help)
        right_layout.addSpacing(15)
        right_layout.addWidget(btn_estimate)
        right_layout.addWidget(btn_options)
        right_layout.addWidget(btn_tests)
        right_layout.addStretch()

        main_layout.addLayout(right_layout)

        # Focus tracking
        self._last_focused_edit = self.edit_single_col
        self.edit_single_col.installEventFilter(self)
        self.edit_sub_size.installEventFilter(self)
        self.edit_across_rows.installEventFilter(self)
        self.edit_lsl.installEventFilter(self)
        self.edit_usl.installEventFilter(self)

        self._update_arrangement_state()

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn:
            self._last_focused_edit = obj
        return super().eventFilter(obj, event)

    def _insert_selected_column(self):
        cur_item = self.col_list.currentItem()
        if not cur_item or not self._last_focused_edit:
            return
        col_text = cur_item.text()
        if self._last_focused_edit == self.edit_across_rows:
            current = self.edit_across_rows.text().strip()
            self.edit_across_rows.setText(f"{current} '{col_text}'" if current else f"'{col_text}'")
        else:
            self._last_focused_edit.setText(col_text)

    def _update_arrangement_state(self):
        single = self.rb_single_col.isChecked()
        self.edit_single_col.setEnabled(single)
        self.edit_sub_size.setEnabled(single)
        self.edit_across_rows.setEnabled(not single)
        if single:
            self._last_focused_edit = self.edit_single_col
        else:
            self._last_focused_edit = self.edit_across_rows

    def _open_options(self):
        dlg = CapabilityOptionsDialog(self.options, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.options.update(dlg.options)

    def _open_estimate(self):
        dlg = CapabilityEstimateDialog(self.options, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.options.update(dlg.options)

    def _open_tests(self):
        dlg = SixpackTestsDialog(self.options, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.options.update(dlg.options)

    def _accept(self):
        single = self.rb_single_col.isChecked()
        col_name = self.edit_single_col.text().strip().strip("'\"")
        across_text = self.edit_across_rows.text().strip()
        sub_size_text = self.edit_sub_size.text().strip().strip("'\"")

        if single:
            if not col_name:
                QMessageBox.warning(self, "StatCraft", "Please select or enter a data column.")
                return
            if not sub_size_text:
                QMessageBox.warning(self, "StatCraft", "Please enter a subgroup size or subgroup indicator column.")
                return
        else:
            if not across_text:
                QMessageBox.warning(self, "StatCraft", "Please enter columns across rows.")
                return

        # Spec limits validation
        lsl_text = self.edit_lsl.text().strip()
        usl_text = self.edit_usl.text().strip()
        if not lsl_text and not usl_text:
            QMessageBox.warning(self, "StatCraft", "At least one specification limit (Lower or Upper spec) is required.")
            return

        lsl_val = None
        if lsl_text:
            try:
                lsl_val = float(lsl_text)
            except ValueError:
                QMessageBox.warning(self, "StatCraft", f"Invalid Lower spec limit: '{lsl_text}'")
                return

        usl_val = None
        if usl_text:
            try:
                usl_val = float(usl_text)
            except ValueError:
                QMessageBox.warning(self, "StatCraft", f"Invalid Upper spec limit: '{usl_text}'")
                return

        if lsl_val is not None and usl_val is not None and lsl_val >= usl_val:
            QMessageBox.warning(self, "StatCraft", "Lower specification limit must be strictly less than Upper specification limit.")
            return

        hmean_val = None
        if self.edit_hmean.text().strip():
            try:
                hmean_val = float(self.edit_hmean.text().strip())
            except ValueError:
                QMessageBox.warning(self, "StatCraft", "Invalid Historical mean value.")
                return

        hsd_val = None
        if self.edit_hsd.text().strip():
            try:
                hsd_val = float(self.edit_hsd.text().strip())
                if hsd_val <= 0:
                    raise ValueError()
            except ValueError:
                QMessageBox.warning(self, "StatCraft", "Historical standard deviation must be positive.")
                return

        cols_across_list = []
        if not single:
            import re
            tokens = re.findall(r"'([^']*)'|\"([^\"]*)\"|(\S+)", across_text)
            for t in tokens:
                c = t[0] or t[1] or t[2]
                if c:
                    cols_across_list.append(c)

        self.selected_params = {
            "single_column": single,
            "analysis_mode": self.analysis_mode,
            "column_name": col_name if single else (cols_across_list[0] if cols_across_list else "Data"),
            "subgroup_spec": sub_size_text if single else None,
            "cols_across": cols_across_list if not single else None,
            "lsl": lsl_val,
            "usl": usl_val,
            "lsl_bound": self.chk_lsl_bound.isChecked(),
            "usl_bound": self.chk_usl_bound.isChecked(),
            "historical_mean": hmean_val,
            "historical_stdev": hsd_val,
            "options": dict(self.options),
        }

        self.accept()



class CapabilitySixpackNonnormalDialog(QDialog):
    """Main dialog for Stat > Quality Tools > Capability Sixpack > Nonnormal..."""

    def __init__(self, worksheet=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Capability Sixpack (Nonnormal Distribution)")
        self.resize(560, 400)
        self.worksheet = worksheet
        self.columns: List[str] = []
        if worksheet and hasattr(worksheet, "columns"):
            self.columns = [c.name for c in worksheet.columns]

        self.selected_params: Optional[Dict[str, Any]] = None

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(12)

        # Left Column List
        left_layout = QVBoxLayout()
        lbl_cols = QLabel("Columns:")
        left_layout.addWidget(lbl_cols)

        self.col_list = QListWidget()
        for c in self.columns:
            self.col_list.addItem(c)
        self.col_list.itemDoubleClicked.connect(self._insert_selected_column)
        left_layout.addWidget(self.col_list)

        btn_select = QPushButton("Select")
        btn_select.clicked.connect(self._insert_selected_column)
        left_layout.addWidget(btn_select)
        main_layout.addLayout(left_layout, 1)

        # Center Controls Layout
        center_layout = QVBoxLayout()
        center_layout.setSpacing(10)

        # Single column data
        box_data = QGroupBox("Data arrangement")
        form_data = QGridLayout(box_data)
        lbl_col = QLabel("Single column:")
        self.edit_col = QLineEdit()
        form_data.addWidget(lbl_col, 0, 0)
        form_data.addWidget(self.edit_col, 0, 1)

        lbl_sub = QLabel("Subgroup size:")
        self.edit_sub = QLineEdit("1")
        form_data.addWidget(lbl_sub, 1, 0)
        form_data.addWidget(self.edit_sub, 1, 1)
        center_layout.addWidget(box_data)

        # Distribution selection
        box_dist = QGroupBox("Fit Distribution")
        form_dist = QGridLayout(box_dist)
        lbl_d = QLabel("Distribution:")
        self.cbo_dist = QComboBox()
        self.cbo_dist.addItems(["Weibull", "Lognormal", "Exponential", "Gamma", "Normal"])
        form_dist.addWidget(lbl_d, 0, 0)
        form_dist.addWidget(self.cbo_dist, 0, 1)
        center_layout.addWidget(box_dist)

        # Spec Limits Group
        spec_box = QGroupBox("Specification limits")
        spec_grid = QGridLayout(spec_box)
        lbl_lsl = QLabel("Lower spec (LSL):")
        self.edit_lsl = QLineEdit()
        lbl_usl = QLabel("Upper spec (USL):")
        self.edit_usl = QLineEdit()
        lbl_tgt = QLabel("Target (optional):")
        self.edit_tgt = QLineEdit()

        spec_grid.addWidget(lbl_lsl, 0, 0)
        spec_grid.addWidget(self.edit_lsl, 0, 1)
        spec_grid.addWidget(lbl_usl, 1, 0)
        spec_grid.addWidget(self.edit_usl, 1, 1)
        spec_grid.addWidget(lbl_tgt, 2, 0)
        spec_grid.addWidget(self.edit_tgt, 2, 1)
        center_layout.addWidget(spec_box)

        main_layout.addLayout(center_layout, 2)

        # Action Buttons Layout (Right side)
        right_layout = QVBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        right_layout.addWidget(btn_ok)
        right_layout.addWidget(btn_cancel)
        right_layout.addStretch()
        main_layout.addLayout(right_layout)

    def _insert_selected_column(self):
        item = self.col_list.currentItem()
        if not item:
            return
        col_text = item.text()
        if " " in col_text:
            col_text = f"'{col_text}'"
        self.edit_col.setText(col_text)

    def _accept(self):
        col_name = self.edit_col.text().strip()
        if not col_name:
            QMessageBox.warning(self, "StatCraft", "Please specify a data column.")
            return

        import re
        m = re.match(r"^'([^']*)'$|^\"([^\"]*)\"$", col_name)
        if m:
            col_name = m.group(1) or m.group(2)

        lsl_val = None
        if self.edit_lsl.text().strip():
            try:
                lsl_val = float(self.edit_lsl.text().strip())
            except ValueError:
                QMessageBox.warning(self, "StatCraft", "Invalid Lower Spec Limit.")
                return

        usl_val = None
        if self.edit_usl.text().strip():
            try:
                usl_val = float(self.edit_usl.text().strip())
            except ValueError:
                QMessageBox.warning(self, "StatCraft", "Invalid Upper Spec Limit.")
                return

        tgt_val = None
        if self.edit_tgt.text().strip():
            try:
                tgt_val = float(self.edit_tgt.text().strip())
            except ValueError:
                QMessageBox.warning(self, "StatCraft", "Invalid Target.")
                return

        if lsl_val is None and usl_val is None:
            QMessageBox.warning(self, "StatCraft", "At least one specification limit (LSL or USL) must be provided.")
            return

        sub_spec = self.edit_sub.text().strip() or "1"
        dist = self.cbo_dist.currentText().lower()

        self.selected_params = {
            "single_column": True,
            "column_name": col_name,
            "subgroup_spec": sub_spec,
            "distribution": dist,
            "lsl": lsl_val,
            "usl": usl_val,
            "target": tgt_val,
        }
        self.accept()
