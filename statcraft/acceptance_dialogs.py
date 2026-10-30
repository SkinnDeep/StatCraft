"""Dialogs for Acceptance Control Charts (ISO 7870-3 / AIAG / VDA SPC)."""

import shlex
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)


class AcceptanceOptionsDialog(QDialog):
    """Options subdialog for Acceptance Control Chart."""

    def __init__(self, current_options: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Acceptance Control Chart: Options")
        self.setModal(True)
        self.options = dict(current_options)

        main_layout = QVBoxLayout(self)

        # Target & Title
        form_grid = QGridLayout()
        lbl_target = QLabel("Target (optional):")
        self.edit_target = QLineEdit()
        if self.options.get("target") is not None:
            self.edit_target.setText(str(self.options["target"]))
        form_grid.addWidget(lbl_target, 0, 0)
        form_grid.addWidget(self.edit_target, 0, 1)

        lbl_title = QLabel("Chart Title:")
        self.edit_title = QLineEdit(self.options.get("title", ""))
        form_grid.addWidget(lbl_title, 1, 0)
        form_grid.addWidget(self.edit_title, 1, 1)
        main_layout.addLayout(form_grid)

        # Sigma estimation method
        method_box = QGroupBox("Standard deviation estimation method")
        m_layout = QVBoxLayout(method_box)
        self.rb_pooled = QRadioButton("Pooled standard deviation")
        self.rb_rbar = QRadioButton("Rbar (Average range)")
        self.rb_sbar = QRadioButton("Sbar (Average standard deviation)")
        self.m_group = QButtonGroup(self)
        self.m_group.addButton(self.rb_pooled)
        self.m_group.addButton(self.rb_rbar)
        self.m_group.addButton(self.rb_sbar)

        cur_m = self.options.get("estimate_method", "pooled")
        if cur_m == "rbar":
            self.rb_rbar.setChecked(True)
        elif cur_m == "sbar":
            self.rb_sbar.setChecked(True)
        else:
            self.rb_pooled.setChecked(True)

        self.chk_unbiased = QCheckBox("Unbias standard deviation estimate")
        self.chk_unbiased.setChecked(self.options.get("unbiased", True))

        m_layout.addWidget(self.rb_pooled)
        m_layout.addWidget(self.rb_rbar)
        m_layout.addWidget(self.rb_sbar)
        m_layout.addWidget(self.chk_unbiased)
        main_layout.addWidget(method_box)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(self._accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        main_layout.addLayout(btn_layout)

    def _accept(self):
        t_text = self.edit_target.text().strip()
        t_val = None
        if t_text:
            try:
                t_val = float(t_text)
            except ValueError:
                QMessageBox.critical(self, "StatCraft", "Target value must be numeric.")
                return

        m_chosen = "pooled"
        if self.rb_rbar.isChecked():
            m_chosen = "rbar"
        elif self.rb_sbar.isChecked():
            m_chosen = "sbar"

        self.options.update({
            "target": t_val,
            "title": self.edit_title.text().strip(),
            "estimate_method": m_chosen,
            "unbiased": self.chk_unbiased.isChecked(),
        })
        self.accept()


class AcceptanceControlChartDialog(QDialog):
    """Main StatCraft Acceptance Control Chart Dialog."""

    def __init__(self, worksheet_or_cols: Any, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Acceptance Control Chart")
        self.setModal(True)
        if hasattr(worksheet_or_cols, "columns"):
            self.columns = [c.name for c in worksheet_or_cols.columns]
        else:
            self.columns = list(worksheet_or_cols)
        self.selected_params: Optional[Dict[str, Any]] = None

        self.options: Dict[str, Any] = {
            "target": None,
            "title": "",
            "estimate_method": "pooled",
            "unbiased": True,
        }

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(12)

        # Left: Columns list
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

        # 1. Data Arrangement
        arr_box = QGroupBox("Data arrangement")
        arr_layout = QVBoxLayout(arr_box)

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

        lbl_sub_size = QLabel("&Subgroup size or column:")
        self.edit_sub_size = QLineEdit("5")
        lbl_sub_size.setBuddy(self.edit_sub_size)
        sc_grid.addWidget(lbl_sub_size, 1, 0, Qt.AlignmentFlag.AlignRight)
        sc_grid.addWidget(self.edit_sub_size, 1, 1)
        arr_layout.addLayout(sc_grid)

        ar_grid = QGridLayout()
        self.edit_across_rows = QLineEdit()
        ar_grid.addWidget(self.rb_across_rows, 0, 0)
        ar_grid.addWidget(self.edit_across_rows, 0, 1)
        arr_layout.addLayout(ar_grid)
        center_layout.addWidget(arr_box)

        # 2. Specification Limits Group
        spec_box = QGroupBox("Specification limits (at least 1 required)")
        spec_grid = QGridLayout(spec_box)

        lbl_lsl = QLabel("&Lower spec limit (LSL):")
        self.edit_lsl = QLineEdit()
        lbl_lsl.setBuddy(self.edit_lsl)
        spec_grid.addWidget(lbl_lsl, 0, 0)
        spec_grid.addWidget(self.edit_lsl, 0, 1)

        lbl_usl = QLabel("&Upper spec limit (USL):")
        self.edit_usl = QLineEdit()
        lbl_usl.setBuddy(self.edit_usl)
        spec_grid.addWidget(lbl_usl, 1, 0)
        spec_grid.addWidget(self.edit_usl, 1, 1)
        center_layout.addWidget(spec_box)

        # 3. Parameters Group
        param_box = QGroupBox("Acceptance parameters")
        param_grid = QGridLayout(param_box)

        lbl_delta = QLabel("Acceptable &fraction nonconforming (δ):")
        self.edit_delta = QLineEdit("0.001")
        lbl_delta.setBuddy(self.edit_delta)
        param_grid.addWidget(lbl_delta, 0, 0)
        param_grid.addWidget(self.edit_delta, 0, 1)

        lbl_alpha = QLabel("&Producer's risk (α):")
        self.edit_alpha = QLineEdit("0.05")
        lbl_alpha.setBuddy(self.edit_alpha)
        param_grid.addWidget(lbl_alpha, 1, 0)
        param_grid.addWidget(self.edit_alpha, 1, 1)

        lbl_hsd = QLabel("Historical standard &deviation (optional):")
        self.edit_hsd = QLineEdit()
        lbl_hsd.setBuddy(self.edit_hsd)
        param_grid.addWidget(lbl_hsd, 2, 0)
        param_grid.addWidget(self.edit_hsd, 2, 1)
        center_layout.addWidget(param_box)

        main_layout.addLayout(center_layout, 2)

        # Right Actions
        right_layout = QVBoxLayout()
        right_layout.setSpacing(8)

        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_cancel = QPushButton("Cancel")
        btn_help = QPushButton("Help")
        btn_options = QPushButton("O&ptions...")

        btn_ok.clicked.connect(self._accept)
        btn_cancel.clicked.connect(self.reject)
        btn_options.clicked.connect(self._open_options)

        right_layout.addWidget(btn_ok)
        right_layout.addWidget(btn_cancel)
        right_layout.addWidget(btn_help)
        right_layout.addSpacing(15)
        right_layout.addWidget(btn_options)
        right_layout.addStretch()
        main_layout.addLayout(right_layout)

        self._last_focused_edit = self.edit_single_col
        self.edit_single_col.installEventFilter(self)
        self.edit_sub_size.installEventFilter(self)
        self.edit_across_rows.installEventFilter(self)
        self.edit_lsl.installEventFilter(self)
        self.edit_usl.installEventFilter(self)
        self.edit_delta.installEventFilter(self)
        self.edit_alpha.installEventFilter(self)
        self.edit_hsd.installEventFilter(self)

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
        dlg = AcceptanceOptionsDialog(self.options, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.options.update(dlg.options)

    def _accept(self):
        single = self.rb_single_col.isChecked()
        col_name = ""
        subgroup_spec: Any = 1
        cols_across: List[str] = []

        if single:
            col_name = self.edit_single_col.text().strip().strip("'\"")
            if not col_name:
                QMessageBox.critical(self, "StatCraft", "Please select or enter a data column.")
                return
            sub_text = self.edit_sub_size.text().strip().strip("'\"")
            if not sub_text:
                subgroup_spec = 5
            elif sub_text.isdigit():
                subgroup_spec = int(sub_text)
                if subgroup_spec <= 1:
                    QMessageBox.critical(self, "StatCraft", "Subgroup size must be an integer greater than 1, or specify a subgroup column.")
                    return
            else:
                subgroup_spec = sub_text
        else:
            raw_across = self.edit_across_rows.text().strip()
            if not raw_across:
                QMessageBox.critical(self, "StatCraft", "Please enter columns for subgroups across rows.")
                return
            try:
                cols_across = [c.strip("'\"") for c in shlex.split(raw_across)]
            except ValueError:
                cols_across = [c.strip("'\"") for c in raw_across.split()]
            if len(cols_across) < 2:
                QMessageBox.critical(self, "StatCraft", "Subgroups across rows requires at least two columns.")
                return

        # Specs
        lsl_text = self.edit_lsl.text().strip()
        usl_text = self.edit_usl.text().strip()
        if not lsl_text and not usl_text:
            QMessageBox.critical(self, "StatCraft", "Enter at least one specification limit (Lower spec or Upper spec).")
            return

        lsl_val = None
        if lsl_text:
            try:
                lsl_val = float(lsl_text)
            except ValueError:
                QMessageBox.critical(self, "StatCraft", "Lower spec must be numeric.")
                return

        usl_val = None
        if usl_text:
            try:
                usl_val = float(usl_text)
            except ValueError:
                QMessageBox.critical(self, "StatCraft", "Upper spec must be numeric.")
                return

        if lsl_val is not None and usl_val is not None and lsl_val >= usl_val:
            QMessageBox.critical(self, "StatCraft", "Lower specification must be strictly less than upper specification.")
            return

        # Parameters
        try:
            delta_val = float(self.edit_delta.text().strip())
            if delta_val <= 0 or delta_val >= 0.5:
                raise ValueError
        except ValueError:
            QMessageBox.critical(self, "StatCraft", "Acceptable fraction nonconforming (delta) must be between 0 and 0.5.")
            return

        try:
            alpha_val = float(self.edit_alpha.text().strip())
            if alpha_val <= 0 or alpha_val >= 0.5:
                raise ValueError
        except ValueError:
            QMessageBox.critical(self, "StatCraft", "Producer's risk (alpha) must be between 0 and 0.5.")
            return

        hsd_val = None
        if self.edit_hsd.text().strip():
            try:
                hsd_val = float(self.edit_hsd.text().strip())
                if hsd_val <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.critical(self, "StatCraft", "Historical standard deviation must be a positive number.")
                return

        self.selected_params = {
            "single_column": single,
            "column_name": col_name,
            "subgroup_spec": subgroup_spec,
            "cols_across": cols_across,
            "lsl": lsl_val,
            "usl": usl_val,
            "delta": delta_val,
            "alpha": alpha_val,
            "historical_stdev": hsd_val,
            "options": dict(self.options),
        }
        self.accept()
