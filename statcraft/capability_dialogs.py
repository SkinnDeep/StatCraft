"""Native StatCraft Capability Analysis (Normal) dialogs.

Corresponds to PE MenuID 40167 and definitions:
- 0471-CAPABILITY.MDF.xml (Options: Capability Analysis)
- 1017-QUALITYESTSIGMA.MDF.xml (Options: Estimating Standard Deviation)
"""

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


class CapabilityOptionsDialog(QDialog):
    """0471-CAPABILITY.MDF: Options: Capability Analysis."""

    def __init__(self, options: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Options: Capability Analysis")
        self.setModal(True)
        self.options = dict(options or {})

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Tolerance K
        tol_layout = QHBoxLayout()
        lbl_k = QLabel("Use toleran&ce of K × σ for capability statistics    K =")
        self.edit_k = QLineEdit(str(self.options.get("tolerance_k", 6.0)))
        lbl_k.setBuddy(self.edit_k)
        tol_layout.addWidget(lbl_k)
        tol_layout.addWidget(self.edit_k)
        layout.addLayout(tol_layout)

        # Target value
        target_layout = QHBoxLayout()
        lbl_target = QLabel("&Target (adds Cpm to table):")
        target_val = self.options.get("target")
        self.edit_target = QLineEdit(str(target_val) if target_val is not None else "")
        lbl_target.setBuddy(self.edit_target)
        target_layout.addWidget(lbl_target)
        target_layout.addWidget(self.edit_target)
        layout.addLayout(target_layout)

        # Display Frame
        disp_box = QGroupBox("Display")
        disp_grid = QGridLayout(disp_box)

        self.rb_cap_stats = QRadioButton("C&apability stats (Cp, Pp)")
        self.rb_z_bench = QRadioButton("&Benchmark Z’s (σ level)")
        self.stat_group = QButtonGroup(self)
        self.stat_group.addButton(self.rb_cap_stats)
        self.stat_group.addButton(self.rb_z_bench)
        if self.options.get("stats_type", "capability") == "zbench":
            self.rb_z_bench.setChecked(True)
        else:
            self.rb_cap_stats.setChecked(True)

        disp_grid.addWidget(self.rb_cap_stats, 0, 0)
        disp_grid.addWidget(self.rb_z_bench, 1, 0)

        self.rb_ppm = QRadioButton("Pa&rts per million")
        self.rb_pct = QRadioButton("Perc&ents")
        self.unit_group = QButtonGroup(self)
        self.unit_group.addButton(self.rb_ppm)
        self.unit_group.addButton(self.rb_pct)
        if self.options.get("display_unit", "ppm") == "percent":
            self.rb_pct.setChecked(True)
        else:
            self.rb_ppm.setChecked(True)

        disp_grid.addWidget(self.rb_ppm, 0, 1)
        disp_grid.addWidget(self.rb_pct, 1, 1)

        self.chk_ccpk = QCheckBox("CC&pk")
        self.chk_ccpk.setChecked(self.options.get("show_ccpk", False))
        disp_grid.addWidget(self.chk_ccpk, 2, 0)

        layout.addWidget(disp_box)

        # Confidence Intervals Frame
        ci_box = QGroupBox("Confidence Intervals")
        ci_layout = QVBoxLayout(ci_box)

        self.chk_include_ci = QCheckBox("I&nclude confidence intervals")
        self.chk_include_ci.setChecked(self.options.get("include_ci", False))
        ci_layout.addWidget(self.chk_include_ci)

        ci_form = QGridLayout()
        lbl_clevel = QLabel("Confidence le&vel:")
        self.edit_clevel = QLineEdit(str(self.options.get("confidence_level", 95.0)))
        lbl_clevel.setBuddy(self.edit_clevel)
        ci_form.addWidget(lbl_clevel, 0, 0)
        ci_form.addWidget(self.edit_clevel, 0, 1)

        lbl_ctype = QLabel("Confi&dence intervals:")
        self.combo_ctype = QComboBox()
        self.combo_ctype.addItem("Two-sided", "two_sided")
        self.combo_ctype.addItem("Lower bound", "lower")
        self.combo_ctype.addItem("Upper bound", "upper")
        curr_type = self.options.get("ci_type", "two_sided")
        for i in range(self.combo_ctype.count()):
            if self.combo_ctype.itemData(i) == curr_type:
                self.combo_ctype.setCurrentIndex(i)
                break
        lbl_ctype.setBuddy(self.combo_ctype)
        ci_form.addWidget(lbl_ctype, 1, 0)
        ci_form.addWidget(self.combo_ctype, 1, 1)

        ci_layout.addLayout(ci_form)
        layout.addWidget(ci_box)

        # Toggle CI inputs enabled state
        self.chk_include_ci.toggled.connect(self._toggle_ci)
        self._toggle_ci(self.chk_include_ci.isChecked())

        # Capability Nomenclature Frame (AIAG / VDA Standard)
        nomen_box = QGroupBox("Capability Nomenclature")
        nomen_layout = QVBoxLayout(nomen_box)
        self.rb_classical = QRadioButton("Classical &AIAG (Cp, Cpk, Pp, Ppk)")
        self.rb_aiag_vda = QRadioButton("Unified AIAG/&VDA (Cbw, Cbwk, Cm, Cmk, Pp, Ppk)")
        self.nomen_group = QButtonGroup(self)
        self.nomen_group.addButton(self.rb_classical)
        self.nomen_group.addButton(self.rb_aiag_vda)
        if self.options.get("naming_convention", "classical") == "aiag_vda":
            self.rb_aiag_vda.setChecked(True)
        else:
            self.rb_classical.setChecked(True)
        nomen_layout.addWidget(self.rb_classical)
        nomen_layout.addWidget(self.rb_aiag_vda)
        layout.addWidget(nomen_box)

        # Title
        title_layout = QHBoxLayout()
        lbl_title = QLabel("Titl&e:")
        self.edit_title = QLineEdit(self.options.get("title", ""))
        lbl_title.setBuddy(self.edit_title)
        title_layout.addWidget(lbl_title)
        title_layout.addWidget(self.edit_title)
        layout.addLayout(title_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_help = QPushButton("Help")
        btn_ok.clicked.connect(self._accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_help)
        layout.addLayout(btn_layout)

    def _toggle_ci(self, enabled: bool):
        self.edit_clevel.setEnabled(enabled)
        self.combo_ctype.setEnabled(enabled)

    def _accept(self):
        try:
            k = float(self.edit_k.text().strip())
            if k <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.critical(self, "StatCraft", "Tolerance K must be a positive number.")
            return

        target_text = self.edit_target.text().strip()
        target_val = None
        if target_text:
            try:
                target_val = float(target_text)
            except ValueError:
                QMessageBox.critical(self, "StatCraft", "Target value must be numeric.")
                return

        conf_val = 95.0
        if self.chk_include_ci.isChecked():
            try:
                conf_val = float(self.edit_clevel.text().strip())
                if not (0.0 < conf_val < 100.0):
                    raise ValueError
            except ValueError:
                QMessageBox.critical(self, "StatCraft", "Confidence level must be between 0 and 100.")
                return

        self.options["tolerance_k"] = k
        self.options["target"] = target_val
        self.options["stats_type"] = "zbench" if self.rb_z_bench.isChecked() else "capability"
        self.options["display_unit"] = "percent" if self.rb_pct.isChecked() else "ppm"
        self.options["show_ccpk"] = self.chk_ccpk.isChecked()
        self.options["include_ci"] = self.chk_include_ci.isChecked()
        self.options["confidence_level"] = conf_val
        self.options["ci_type"] = self.combo_ctype.currentData()
        self.options["naming_convention"] = "aiag_vda" if self.rb_aiag_vda.isChecked() else "classical"
        self.options["title"] = self.edit_title.text().strip()
        self.accept()


class CapabilityEstimateDialog(QDialog):
    """1017-QUALITYESTSIGMA.MDF: Options: Estimating Standard Deviation."""

    def __init__(self, options: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Options: Estimating Standard Deviation")
        self.setModal(True)
        self.options = dict(options or {})

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Method for Subgroup Size > 1
        gt1_box = QGroupBox("Method for Subgroup Size > 1")
        gt1_layout = QVBoxLayout(gt1_box)
        self.rb_rbar = QRadioButton("&Rbar")
        self.rb_sbar = QRadioButton("&Sbar")
        self.rb_pooled = QRadioButton("&Pooled standard deviation")
        self.gt1_group = QButtonGroup(self)
        self.gt1_group.addButton(self.rb_rbar)
        self.gt1_group.addButton(self.rb_sbar)
        self.gt1_group.addButton(self.rb_pooled)

        m_gt1 = self.options.get("estimate_method_gt1", "pooled").lower()
        if m_gt1 == "rbar":
            self.rb_rbar.setChecked(True)
        elif m_gt1 == "sbar":
            self.rb_sbar.setChecked(True)
        else:
            self.rb_pooled.setChecked(True)

        gt1_layout.addWidget(self.rb_rbar)
        gt1_layout.addWidget(self.rb_sbar)
        gt1_layout.addWidget(self.rb_pooled)
        layout.addWidget(gt1_box)

        # Method for Subgroup Size = 1
        eq1_box = QGroupBox("Method for Subgroup Size = 1")
        eq1_layout = QVBoxLayout(eq1_box)
        self.rb_amr = QRadioButton("Average &moving range")
        self.rb_mmr = QRadioButton("Me&dian moving range")
        self.rb_srmssd = QRadioButton("Square roo&t of MSSD")
        self.eq1_group = QButtonGroup(self)
        self.eq1_group.addButton(self.rb_amr)
        self.eq1_group.addButton(self.rb_mmr)
        self.eq1_group.addButton(self.rb_srmssd)

        m_eq1 = self.options.get("estimate_method_eq1", "amr").lower()
        if m_eq1 == "mmr":
            self.rb_mmr.setChecked(True)
        elif m_eq1 == "srmssd":
            self.rb_srmssd.setChecked(True)
        else:
            self.rb_amr.setChecked(True)

        eq1_layout.addWidget(self.rb_amr)
        eq1_layout.addWidget(self.rb_mmr)
        eq1_layout.addWidget(self.rb_srmssd)
        layout.addWidget(eq1_box)

        # Unbiasing constants and moving range length
        all_box = QGroupBox("All Cases")
        all_layout = QVBoxLayout(all_box)
        all_layout.addWidget(QLabel("Use unbiasing constants to calculate standard deviations:"))

        self.chk_unbias_within = QCheckBox("&Within subgroup")
        self.chk_unbias_within.setChecked(self.options.get("unbiased_within", True))
        all_layout.addWidget(self.chk_unbias_within)

        self.chk_unbias_overall = QCheckBox("Overall (&capability analysis only)")
        self.chk_unbias_overall.setChecked(self.options.get("unbiased_overall", False))
        all_layout.addWidget(self.chk_unbias_overall)

        mr_layout = QHBoxLayout()
        lbl_mr = QLabel("&Length of moving range:")
        self.edit_mr_len = QLineEdit(str(self.options.get("moving_range_len", 2)))
        lbl_mr.setBuddy(self.edit_mr_len)
        mr_layout.addWidget(lbl_mr)
        mr_layout.addWidget(self.edit_mr_len)
        all_layout.addLayout(mr_layout)

        layout.addWidget(all_box)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_help = QPushButton("Help")
        btn_ok.clicked.connect(self._accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_help)
        layout.addLayout(btn_layout)

    def _accept(self):
        try:
            mr_len = int(self.edit_mr_len.text().strip())
            if not (2 <= mr_len <= 100):
                raise ValueError
        except ValueError:
            QMessageBox.critical(self, "StatCraft", "Length of moving range must be an integer between 2 and 100.")
            return

        if self.rb_rbar.isChecked():
            m_gt1 = "rbar"
        elif self.rb_sbar.isChecked():
            m_gt1 = "sbar"
        else:
            m_gt1 = "pooled"

        if self.rb_mmr.isChecked():
            m_eq1 = "mmr"
        elif self.rb_srmssd.isChecked():
            m_eq1 = "srmssd"
        else:
            m_eq1 = "amr"

        self.options["estimate_method_gt1"] = m_gt1
        self.options["estimate_method_eq1"] = m_eq1
        self.options["moving_range_len"] = mr_len
        self.options["unbiased_within"] = self.chk_unbias_within.isChecked()
        self.options["unbiased_overall"] = self.chk_unbias_overall.isChecked()
        self.accept()


class CapabilityDialog(QDialog):
    """Main StatCraft Process Capability (Normal Distribution) Dialog."""

    def __init__(
        self,
        worksheet_or_cols: Any,
        parent=None,
        analysis_mode: str = "normal",
        study_type: str = "process",
        naming_convention: str = "classical"
    ):
        super().__init__(parent)
        self.analysis_mode = analysis_mode
        self.study_type = study_type
        self.naming_convention = naming_convention
        if study_type == "machine":
            self.setWindowTitle("Machine Capability Analysis (Normal Distribution)")
        elif analysis_mode == "between_within":
            self.setWindowTitle("Between/Within Capability Analysis")
        else:
            self.setWindowTitle("Capability Analysis (Normal Distribution)")
        self.setModal(True)
        if hasattr(worksheet_or_cols, "columns"):
            self.columns = [c.name for c in worksheet_or_cols.columns]
        else:
            self.columns = list(worksheet_or_cols)
        self.selected_params: Optional[Dict[str, Any]] = None

        # Options state
        self.options: Dict[str, Any] = {
            "tolerance_k": 6.0,
            "target": None,
            "stats_type": "capability",
            "display_unit": "ppm",
            "show_ccpk": False,
            "include_ci": False,
            "confidence_level": 95.0,
            "ci_type": "two_sided",
            "title": "",
            "estimate_method_gt1": "pooled",
            "estimate_method_eq1": "amr",
            "moving_range_len": 2,
            "unbiased_within": True,
            "unbiased_overall": False,
            "naming_convention": naming_convention,
            "study_type": study_type,
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

        btn_ok.clicked.connect(self._accept)
        btn_cancel.clicked.connect(self.reject)
        btn_estimate.clicked.connect(self._open_estimate)
        btn_options.clicked.connect(self._open_options)

        right_layout.addWidget(btn_ok)
        right_layout.addWidget(btn_cancel)
        right_layout.addWidget(btn_help)
        right_layout.addSpacing(15)
        right_layout.addWidget(btn_estimate)
        right_layout.addWidget(btn_options)
        right_layout.addStretch()

        main_layout.addLayout(right_layout)

        # Focus track
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

    def _accept(self):
        # Validation
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
                subgroup_spec = 1
            elif sub_text.isdigit():
                subgroup_spec = int(sub_text)
            else:
                # Column name as subgroup indicator
                subgroup_spec = sub_text
        else:
            raw_across = self.edit_across_rows.text().strip()
            if not raw_across:
                QMessageBox.critical(self, "StatCraft", "Please enter columns for subgroups across rows.")
                return
            # Parse multiple columns
            import shlex
            try:
                cols_across = [c.strip("'\"") for c in shlex.split(raw_across)]
            except ValueError:
                cols_across = [c.strip("'\"") for c in raw_across.split()]
            if not cols_across:
                QMessageBox.critical(self, "StatCraft", "Please enter valid columns for subgroups across rows.")
                return

        if self.analysis_mode == "between_within":
            if single:
                if isinstance(subgroup_spec, int) and subgroup_spec <= 1:
                    QMessageBox.critical(self, "StatCraft", "Subgroup size must be an integer greater than 1, or specify a subgroup column.")
                    return
            else:
                if len(cols_across) < 2:
                    QMessageBox.critical(self, "StatCraft", "Between/Within capability analysis across rows requires at least two columns.")
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

        # Historical
        hmean_val = None
        if self.edit_hmean.text().strip():
            try:
                hmean_val = float(self.edit_hmean.text().strip())
            except ValueError:
                QMessageBox.critical(self, "StatCraft", "Historical mean must be numeric.")
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
            "analysis_mode": self.analysis_mode,
            "study_type": self.study_type,
            "naming_convention": self.options.get("naming_convention", self.naming_convention),
            "single_column": single,
            "column_name": col_name,
            "subgroup_spec": subgroup_spec,
            "cols_across": cols_across,
            "lsl": lsl_val,
            "usl": usl_val,
            "lsl_bound": self.chk_lsl_bound.isChecked(),
            "usl_bound": self.chk_usl_bound.isChecked(),
            "historical_mean": hmean_val,
            "historical_stdev": hsd_val,
            "options": dict(self.options),
        }
        self.accept()
