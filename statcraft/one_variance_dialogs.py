"""Native StatCraft One-Sample Variance dialogs (0245-1VARIANCE.MDF + 0246-1VARIANCEOPTIONS.MDF)."""
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


class OneVarianceOptionsDialog(QDialog):
    """0246-1VARIANCEOPTIONS.MDF: One-Sample Variance: Options."""

    def __init__(self, options=None, is_variance=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("One-Sample Variance: Options")
        self.setModal(True)
        self.is_variance = is_variance
        self.options = dict(options or {})

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setSpacing(8)

        # Confidence level
        lbl_conf = QLabel("&Confidence level:")
        self.conf_edit = QLineEdit(str(self.options.get("confidence_level", 95.0)))
        lbl_conf.setBuddy(self.conf_edit)
        grid.addWidget(lbl_conf, 0, 0)
        grid.addWidget(self.conf_edit, 0, 1)

        # Alternative hypothesis
        lbl_alt = QLabel("&Alternative hypothesis:")
        self.alt_combo = QComboBox()
        target = "variance" if self.is_variance else "standard deviation"
        self.alt_combo.addItem(f"{target.capitalize()} ≠ hypothesized {target}", "not_equal")
        self.alt_combo.addItem(f"{target.capitalize()} < hypothesized {target}", "less")
        self.alt_combo.addItem(f"{target.capitalize()} > hypothesized {target}", "greater")

        curr_alt = self.options.get("alternative", "not_equal")
        idx = {"not_equal": 0, "less": 1, "greater": 2}.get(curr_alt, 0)
        self.alt_combo.setCurrentIndex(idx)
        lbl_alt.setBuddy(self.alt_combo)
        grid.addWidget(lbl_alt, 1, 0)
        grid.addWidget(self.alt_combo, 1, 1)

        layout.addLayout(grid)

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
            val = float(self.conf_edit.text().strip())
            if val <= 0.0 or val >= 100.0:
                raise ValueError
        except ValueError:
            QMessageBox.critical(self, "Validation Error", "Confidence level must be a number between 0 and 100.")
            return

        self.options["confidence_level"] = val
        self.options["alternative"] = self.alt_combo.currentData()
        self.accept()


class OneVarianceDialog(QDialog):
    """0245-1VARIANCE.MDF: One-Sample Variance dialog."""

    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.setWindowTitle("One-Sample Variance")
        self.setModal(True)
        self.worksheet = worksheet
        self.result_payload = None

        self.options = {
            "confidence_level": 95.0,
            "alternative": "not_equal",
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
        self.mode_combo.addItem("One or more samples, each in a column", 0)
        self.mode_combo.addItem("Sample standard deviation", 1)
        self.mode_combo.addItem("Sample variance", 2)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        right_box.addWidget(self.mode_combo)

        # Mode 0 container (Raw columns)
        self.mode0_frame = QFrame()
        m0_layout = QVBoxLayout(self.mode0_frame)
        m0_layout.setContentsMargins(0, 0, 0, 0)
        self.sample_cols_edit = QLineEdit()
        self.sample_cols_edit.setPlaceholderText("e.g. C1 C2")
        m0_layout.addWidget(QLabel("Sample &columns:"))
        m0_layout.addWidget(self.sample_cols_edit)
        right_box.addWidget(self.mode0_frame)

        # Mode 1 container (Sample SD summarized)
        self.mode1_frame = QFrame()
        m1_layout = QGridLayout(self.mode1_frame)
        m1_layout.setContentsMargins(0, 0, 0, 0)
        self.sd_size_edit = QLineEdit()
        self.sd_val_edit = QLineEdit()
        m1_layout.addWidget(QLabel("S&ample size:"), 0, 0)
        m1_layout.addWidget(self.sd_size_edit, 0, 1)
        m1_layout.addWidget(QLabel("&Sample standard deviation:"), 1, 0)
        m1_layout.addWidget(self.sd_val_edit, 1, 1)
        right_box.addWidget(self.mode1_frame)

        # Mode 2 container (Sample Variance summarized)
        self.mode2_frame = QFrame()
        m2_layout = QGridLayout(self.mode2_frame)
        m2_layout.setContentsMargins(0, 0, 0, 0)
        self.var_size_edit = QLineEdit()
        self.var_val_edit = QLineEdit()
        m2_layout.addWidget(QLabel("S&ample size:"), 0, 0)
        m2_layout.addWidget(self.var_size_edit, 0, 1)
        m2_layout.addWidget(QLabel("&Sample variance:"), 1, 0)
        m2_layout.addWidget(self.var_val_edit, 1, 1)
        right_box.addWidget(self.mode2_frame)

        # Hypothesis Test section
        test_frame = QFrame()
        test_layout = QVBoxLayout(test_frame)
        test_layout.setContentsMargins(0, 4, 0, 4)

        self.test_check = QCheckBox("&Perform hypothesis test")
        self.test_check.setChecked(True)
        self.test_check.toggled.connect(self._on_test_toggled)
        test_layout.addWidget(self.test_check)

        hyp_grid = QGridLayout()
        self.hyp_type_combo = QComboBox()
        self.hyp_type_combo.addItem("Hypothesized standard deviation", 0)
        self.hyp_type_combo.addItem("Hypothesized variance", 1)
        self.hyp_type_combo.currentIndexChanged.connect(self._on_hyp_type_changed)

        self.hyp_val_edit = QLineEdit("1.0")
        hyp_grid.addWidget(self.hyp_type_combo, 0, 0)
        hyp_grid.addWidget(QLabel("&Value:"), 0, 1)
        hyp_grid.addWidget(self.hyp_val_edit, 0, 2)
        test_layout.addLayout(hyp_grid)
        right_box.addWidget(test_frame)

        # Options button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.options_btn = QPushButton("Optio&ns...")
        self.options_btn.clicked.connect(self._open_options)
        btn_row.addWidget(self.options_btn)
        right_box.addLayout(btn_row)

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

        self._on_mode_changed(0)
        self._on_test_toggled(True)

    def _on_mode_changed(self, idx):
        self.mode0_frame.setVisible(idx == 0)
        self.mode1_frame.setVisible(idx == 1)
        self.mode2_frame.setVisible(idx == 2)

    def _on_test_toggled(self, checked):
        self.hyp_type_combo.setEnabled(checked)
        self.hyp_val_edit.setEnabled(checked)

    def _on_hyp_type_changed(self, idx):
        pass

    def _on_select(self):
        row = self.var_list.currentRow()
        if row >= 0:
            token = f"C{row+1}"
            cur = self.sample_cols_edit.text().strip()
            self.sample_cols_edit.setText(f"{cur} {token}".strip() if cur else token)

    def _open_options(self):
        is_var = (self.hyp_type_combo.currentIndex() == 1)
        dlg = OneVarianceOptionsDialog(self.options, is_variance=is_var, parent=self)
        if dlg.exec():
            self.options.update(dlg.options)

    def _accept(self):
        mode = self.mode_combo.currentIndex()
        perform_test = self.test_check.isChecked()
        is_variance = (self.hyp_type_combo.currentIndex() == 1)
        try:
            hyp_val = float(self.hyp_val_edit.text().strip()) if perform_test else 1.0
            if hyp_val <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.critical(self, "Validation Error", "Hypothesized value must be a positive number.")
            return

        payload = {
            "mode": mode,
            "perform_test": perform_test,
            "is_variance_test": is_variance,
            "hypothesized_value": hyp_val,
            "confidence_level": self.options.get("confidence_level", 95.0),
            "alternative": self.options.get("alternative", "not_equal"),
        }

        if mode == 0:
            text = self.sample_cols_edit.text().strip()
            if not text:
                QMessageBox.critical(self, "Validation Error", "Please select at least one sample column.")
                return
            tokens = text.split()
            cols = []
            for t in tokens:
                t = t.upper()
                if t.startswith("C") and t[1:].isdigit():
                    idx = int(t[1:]) - 1
                    if self.worksheet and 0 <= idx < len(self.worksheet.columns):
                        cols.append(idx)
                    else:
                        QMessageBox.critical(self, "Validation Error", f"Column {t} not found.")
                        return
                elif self.worksheet:
                    found = False
                    for i, c in enumerate(self.worksheet.columns):
                        if c.name.lower() == t.lower():
                            cols.append(i)
                            found = True
                            break
                    if not found:
                        QMessageBox.critical(self, "Validation Error", f"Column {t} not found.")
                        return
            if not cols:
                QMessageBox.critical(self, "Validation Error", "No valid sample columns specified.")
                return
            payload["columns"] = cols
        elif mode == 1:
            try:
                sz = int(self.sd_size_edit.text().strip())
                sd = float(self.sd_val_edit.text().strip())
                if sz < 2 or sd <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.critical(self, "Validation Error", "Sample size must be >= 2 and standard deviation > 0.")
                return
            payload["sample_size"] = sz
            payload["sample_stdev"] = sd
        elif mode == 2:
            try:
                sz = int(self.var_size_edit.text().strip())
                var = float(self.var_val_edit.text().strip())
                if sz < 2 or var <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.critical(self, "Validation Error", "Sample size must be >= 2 and variance > 0.")
                return
            payload["sample_size"] = sz
            payload["sample_variance"] = var

        self.result_payload = payload
        self.accept()
