"""Native StatCraft Two-Sample Variances dialogs (0254-2VARIANCES.MDF + child forms)."""
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
    QListWidget,
    QMessageBox,
    QFrame,
)


class TwoVariancesOptionsDialog(QDialog):
    """0256-2VARIANCESOPTIONS.MDF: Two-Sample Variance: Options."""

    def __init__(self, options=None, is_summarized=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Two-Sample Variance: Options")
        self.setModal(True)
        self.options = dict(options or {})
        self.is_summarized = is_summarized

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setSpacing(8)

        # Ratio type combo
        lbl_ratio = QLabel("&Ratio:")
        self.ratio_combo = QComboBox()
        self.ratio_combo.addItem("(sample 1 standard deviation) / (sample 2 standard deviation)", 0)
        self.ratio_combo.addItem("(sample 1 variance) / (sample 2 variance)", 1)
        self.ratio_combo.setCurrentIndex(1 if self.options.get("is_variance_ratio", False) else 0)
        lbl_ratio.setBuddy(self.ratio_combo)
        grid.addWidget(lbl_ratio, 0, 0)
        grid.addWidget(self.ratio_combo, 0, 1)

        # Confidence level
        lbl_conf = QLabel("&Confidence level:")
        self.conf_edit = QLineEdit(str(self.options.get("confidence_level", 95.0)))
        lbl_conf.setBuddy(self.conf_edit)
        grid.addWidget(lbl_conf, 1, 0)
        grid.addWidget(self.conf_edit, 1, 1)

        # Hypothesized ratio
        lbl_hyp = QLabel("&Hypothesized ratio:")
        self.hyp_edit = QLineEdit(str(self.options.get("hypothesized_ratio", 1.0)))
        lbl_hyp.setBuddy(self.hyp_edit)
        grid.addWidget(lbl_hyp, 2, 0)
        grid.addWidget(self.hyp_edit, 2, 1)

        # Alternative hypothesis
        lbl_alt = QLabel("&Alternative hypothesis:")
        self.alt_combo = QComboBox()
        self.alt_combo.addItem("Ratio ≠ hypothesized ratio", "not_equal")
        self.alt_combo.addItem("Ratio < hypothesized ratio", "less")
        self.alt_combo.addItem("Ratio > hypothesized ratio", "greater")
        curr_alt = self.options.get("alternative", "not_equal")
        idx = {"not_equal": 0, "less": 1, "greater": 2}.get(curr_alt, 0)
        self.alt_combo.setCurrentIndex(idx)
        lbl_alt.setBuddy(self.alt_combo)
        grid.addWidget(lbl_alt, 3, 0)
        grid.addWidget(self.alt_combo, 3, 1)

        layout.addLayout(grid)

        # Normal distribution checkbox
        self.norm_check = QCheckBox("&Use test and confidence intervals based on normal distribution")
        self.norm_check.setChecked(bool(self.options.get("use_normal_distribution", True)))
        if self.is_summarized:
            self.norm_check.setChecked(True)
            self.norm_check.setEnabled(False)
        layout.addWidget(self.norm_check)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("&OK")
        self.ok_btn.setDefault(True)
        self.cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.ok_btn.clicked.connect(self._accept)
        self.cancel_btn.clicked.connect(self.reject)

    def _accept(self):
        try:
            conf = float(self.conf_edit.text().strip())
            if conf <= 0.0 or conf >= 100.0:
                raise ValueError
        except ValueError:
            QMessageBox.critical(self, "Validation Error", "Confidence level must be a number between 0 and 100.")
            return

        try:
            hyp = float(self.hyp_edit.text().strip())
            if hyp <= 0.0:
                raise ValueError
        except ValueError:
            QMessageBox.critical(self, "Validation Error", "Hypothesized ratio must be positive.")
            return

        self.options["is_variance_ratio"] = (self.ratio_combo.currentIndex() == 1)
        self.options["confidence_level"] = conf
        self.options["hypothesized_ratio"] = hyp
        self.options["alternative"] = self.alt_combo.currentData()
        self.options["use_normal_distribution"] = self.norm_check.isChecked()
        self.accept()


class TwoVariancesGraphsDialog(QDialog):
    """0255-2VARIANCESGRAPHS.MDF: Two-Sample Variance: Graphs."""

    def __init__(self, graphs=None, is_summarized=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Two-Sample Variance: Graphs")
        self.setModal(True)
        self.graphs = dict(graphs or {})

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.summary_check = QCheckBox("&Summary plot")
        self.summary_check.setChecked(self.graphs.get("summary_plot", True))
        layout.addWidget(self.summary_check)

        self.hist_check = QCheckBox("&Histogram")
        self.hist_check.setChecked(self.graphs.get("histogram", False))
        layout.addWidget(self.hist_check)

        self.ind_check = QCheckBox("&Individual value plot")
        self.ind_check.setChecked(self.graphs.get("individual_plot", False))
        layout.addWidget(self.ind_check)

        if is_summarized:
            self.hist_check.setEnabled(False)
            self.ind_check.setEnabled(False)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("&OK")
        self.ok_btn.setDefault(True)
        self.cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.ok_btn.clicked.connect(self._accept)
        self.cancel_btn.clicked.connect(self.reject)

    def _accept(self):
        self.graphs["summary_plot"] = self.summary_check.isChecked()
        self.graphs["histogram"] = self.hist_check.isChecked()
        self.graphs["individual_plot"] = self.ind_check.isChecked()
        self.accept()


class TwoVariancesResultsDialog(QDialog):
    """0257-2VARIANCESRESULTS.MDF: Two-Sample Variance: Results."""

    def __init__(self, results=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Two-Sample Variance: Results")
        self.setModal(True)
        self.results = dict(results or {})

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.method_check = QCheckBox("&Method")
        self.method_check.setChecked(self.results.get("method", True))
        layout.addWidget(self.method_check)

        self.stats_check = QCheckBox("&Statistics")
        self.stats_check.setChecked(self.results.get("statistics", True))
        layout.addWidget(self.stats_check)

        self.ci_check = QCheckBox("&Confidence intervals")
        self.ci_check.setChecked(self.results.get("confidence_intervals", True))
        layout.addWidget(self.ci_check)

        self.test_check = QCheckBox("&Test")
        self.test_check.setChecked(self.results.get("test", True))
        layout.addWidget(self.test_check)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("&OK")
        self.ok_btn.setDefault(True)
        self.cancel_btn = QPushButton("Cancel")
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.ok_btn.clicked.connect(self._accept)
        self.cancel_btn.clicked.connect(self.reject)

    def _accept(self):
        self.results["method"] = self.method_check.isChecked()
        self.results["statistics"] = self.stats_check.isChecked()
        self.results["confidence_intervals"] = self.ci_check.isChecked()
        self.results["test"] = self.test_check.isChecked()
        self.accept()


class TwoVariancesDialog(QDialog):
    """0254-2VARIANCES.MDF: Two-Sample Variance dialog."""

    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Two-Sample Variance")
        self.setModal(True)
        self.worksheet = worksheet
        self.result_payload = None

        self.options = {
            "is_variance_ratio": False,
            "confidence_level": 95.0,
            "hypothesized_ratio": 1.0,
            "alternative": "not_equal",
            "use_normal_distribution": True,
        }
        self.graphs = {
            "summary_plot": True,
            "histogram": False,
            "individual_plot": False,
        }
        self.results_options = {
            "method": True,
            "statistics": True,
            "confidence_intervals": True,
            "test": True,
        }

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(12)

        # Left Column: Variable Picker
        left_box = QVBoxLayout()
        self.var_list = QListWidget()
        for i, col in enumerate(self.worksheet.columns if self.worksheet else []):
            self.var_list.addItem(f"C{i+1}   {col.name}")
        left_box.addWidget(self.var_list)

        self.select_btn = QPushButton("&Select")
        self.select_btn.clicked.connect(self._on_select)
        left_box.addWidget(self.select_btn)
        main_layout.addLayout(left_box, 1)

        # Right Column: Controls
        right_box = QVBoxLayout()
        right_box.setSpacing(10)

        # Data mode combo
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Both samples are in one column", 0)
        self.mode_combo.addItem("Each sample is in its own column", 1)
        self.mode_combo.addItem("Sample standard deviations", 2)
        self.mode_combo.addItem("Sample variances", 3)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        right_box.addWidget(self.mode_combo)

        # Mode 0 container (Stacked)
        self.mode0_frame = QFrame()
        m0_layout = QGridLayout(self.mode0_frame)
        m0_layout.setContentsMargins(0, 0, 0, 0)
        self.stacked_samples_edit = QLineEdit()
        self.stacked_ids_edit = QLineEdit()
        m0_layout.addWidget(QLabel("&Samples:"), 0, 0)
        m0_layout.addWidget(self.stacked_samples_edit, 0, 1)
        m0_layout.addWidget(QLabel("S&ample IDs:"), 1, 0)
        m0_layout.addWidget(self.stacked_ids_edit, 1, 1)
        right_box.addWidget(self.mode0_frame)

        # Mode 1 container (Unstacked)
        self.mode1_frame = QFrame()
        m1_layout = QGridLayout(self.mode1_frame)
        m1_layout.setContentsMargins(0, 0, 0, 0)
        self.s1_edit = QLineEdit()
        self.s2_edit = QLineEdit()
        m1_layout.addWidget(QLabel("&Sample 1:"), 0, 0)
        m1_layout.addWidget(self.s1_edit, 0, 1)
        m1_layout.addWidget(QLabel("S&ample 2:"), 1, 0)
        m1_layout.addWidget(self.s2_edit, 1, 1)
        right_box.addWidget(self.mode1_frame)

        # Mode 2 & 3 container (Summarized)
        self.mode_sum_frame = QFrame()
        ms_layout = QGridLayout(self.mode_sum_frame)
        ms_layout.setContentsMargins(0, 0, 0, 0)
        self.sum_lbl_val1 = QLabel("St&andard deviation:")
        self.sum_lbl_val2 = QLabel("Standard deviation:")
        self.sum_s1_size = QLineEdit()
        self.sum_s1_val = QLineEdit()
        self.sum_s2_size = QLineEdit()
        self.sum_s2_val = QLineEdit()

        ms_layout.addWidget(QLabel("Sample 1"), 0, 1, Qt.AlignmentFlag.AlignCenter)
        ms_layout.addWidget(QLabel("Sample 2"), 0, 2, Qt.AlignmentFlag.AlignCenter)
        ms_layout.addWidget(QLabel("&Sample size:"), 1, 0)
        ms_layout.addWidget(self.sum_s1_size, 1, 1)
        ms_layout.addWidget(self.sum_s2_size, 1, 2)
        ms_layout.addWidget(self.sum_lbl_val1, 2, 0)
        ms_layout.addWidget(self.sum_s1_val, 2, 1)
        ms_layout.addWidget(self.sum_s2_val, 2, 2)
        right_box.addWidget(self.mode_sum_frame)

        # Child Buttons
        child_btn_row = QHBoxLayout()
        child_btn_row.addStretch()
        self.options_btn = QPushButton("Optio&ns...")
        self.options_btn.clicked.connect(self._open_options)
        self.graphs_btn = QPushButton("&Graphs...")
        self.graphs_btn.clicked.connect(self._open_graphs)
        self.results_btn = QPushButton("&Results...")
        self.results_btn.clicked.connect(self._open_results)
        child_btn_row.addWidget(self.options_btn)
        child_btn_row.addWidget(self.graphs_btn)
        child_btn_row.addWidget(self.results_btn)
        right_box.addLayout(child_btn_row)

        right_box.addStretch()

        # Bottom OK / Cancel / Help
        action_row = QHBoxLayout()
        self.help_btn = QPushButton("Help")
        action_row.addWidget(self.help_btn)
        action_row.addStretch()
        self.ok_btn = QPushButton("&OK")
        self.ok_btn.setDefault(True)
        self.cancel_btn = QPushButton("Cancel")
        action_row.addWidget(self.ok_btn)
        action_row.addWidget(self.cancel_btn)
        right_box.addLayout(action_row)

        main_layout.addLayout(right_box, 2)

        self.ok_btn.clicked.connect(self._accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.var_list.doubleClicked.connect(self._on_select)

        # Set default to Unstacked mode (mode 1) matching user standard workflow
        self.mode_combo.setCurrentIndex(1)
        self._on_mode_changed(1)

    def _on_mode_changed(self, idx):
        self.mode0_frame.setVisible(idx == 0)
        self.mode1_frame.setVisible(idx == 1)
        self.mode_sum_frame.setVisible(idx in (2, 3))
        if idx == 2:
            self.sum_lbl_val1.setText("St&andard deviation:")
        elif idx == 3:
            self.sum_lbl_val1.setText("V&ariance:")

    def _resolve_col(self, token):
        t = token.strip().upper()
        if t.startswith("C") and t[1:].isdigit():
            idx = int(t[1:]) - 1
            if self.worksheet and 0 <= idx < len(self.worksheet.columns):
                return idx
        elif self.worksheet:
            for i, c in enumerate(self.worksheet.columns):
                if c.name.lower() == token.strip().lower():
                    return i
        return None

    def _on_select(self):
        row = self.var_list.currentRow()
        if row < 0:
            return
        token = f"C{row+1}"
        fw = self.focusWidget()
        if isinstance(fw, QLineEdit) and fw.isEnabled():
            fw.setText(token)
        else:
            if self.mode_combo.currentIndex() == 0:
                if not self.stacked_samples_edit.text():
                    self.stacked_samples_edit.setText(token)
                else:
                    self.stacked_ids_edit.setText(token)
            elif self.mode_combo.currentIndex() == 1:
                if not self.s1_edit.text():
                    self.s1_edit.setText(token)
                else:
                    self.s2_edit.setText(token)

    def _open_options(self):
        is_sum = (self.mode_combo.currentIndex() in (2, 3))
        dlg = TwoVariancesOptionsDialog(self.options, is_summarized=is_sum, parent=self)
        if dlg.exec():
            self.options.update(dlg.options)

    def _open_graphs(self):
        is_sum = (self.mode_combo.currentIndex() in (2, 3))
        dlg = TwoVariancesGraphsDialog(self.graphs, is_summarized=is_sum, parent=self)
        if dlg.exec():
            self.graphs.update(dlg.graphs)

    def _open_results(self):
        dlg = TwoVariancesResultsDialog(self.results_options, parent=self)
        if dlg.exec():
            self.results_options.update(dlg.results)

    def _accept(self):
        mode = self.mode_combo.currentIndex()
        payload = {
            "mode": mode,
            "is_variance_ratio": self.options.get("is_variance_ratio", False),
            "confidence_level": self.options.get("confidence_level", 95.0),
            "hypothesized_ratio": self.options.get("hypothesized_ratio", 1.0),
            "alternative": self.options.get("alternative", "not_equal"),
            "use_normal_distribution": self.options.get("use_normal_distribution", True),
            "graphs": dict(self.graphs),
            "results_options": dict(self.results_options),
        }

        if mode == 0:
            t_s = self.stacked_samples_edit.text().strip()
            t_id = self.stacked_ids_edit.text().strip()
            idx_s = self._resolve_col(t_s)
            idx_id = self._resolve_col(t_id)
            if idx_s is None:
                QMessageBox.critical(self, "Validation Error", f"Samples column '{t_s}' not found.")
                return
            if idx_id is None:
                QMessageBox.critical(self, "Validation Error", f"Sample IDs column '{t_id}' not found.")
                return
            payload["samples_col"] = idx_s
            payload["subscripts_col"] = idx_id
        elif mode == 1:
            t1 = self.s1_edit.text().strip()
            t2 = self.s2_edit.text().strip()
            idx1 = self._resolve_col(t1)
            idx2 = self._resolve_col(t2)
            if idx1 is None:
                QMessageBox.critical(self, "Validation Error", f"Sample 1 column '{t1}' not found.")
                return
            if idx2 is None:
                QMessageBox.critical(self, "Validation Error", f"Sample 2 column '{t2}' not found.")
                return
            payload["s1_col"] = idx1
            payload["s2_col"] = idx2
        elif mode in (2, 3):
            try:
                n1 = int(self.sum_s1_size.text().strip())
                v1 = float(self.sum_s1_val.text().strip())
                n2 = int(self.sum_s2_size.text().strip())
                v2 = float(self.sum_s2_val.text().strip())
                if n1 < 2 or n2 < 2 or v1 <= 0 or v2 <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.critical(self, "Validation Error", "Sample sizes must be >= 2 and values > 0.")
                return
            payload["sample1_size"] = n1
            payload["sample2_size"] = n2
            if mode == 2:
                payload["sample1_stdev"] = v1
                payload["sample2_stdev"] = v2
            else:
                payload["sample1_variance"] = v1
                payload["sample2_variance"] = v2

        self.result_payload = payload
        self.accept()
