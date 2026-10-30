"""Dialogs for Make Patterned Data and Random Data Generation."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QGroupBox, QMessageBox
)


class PatternedNumbersDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Make Patterned Data - Simple Set of Numbers")
        self.setMinimumSize(420, 290)
        self.resize(440, 310)

        main_layout = QVBoxLayout(self)

        grid_group = QGroupBox("Pattern Specifications")
        grid_layout = QVBoxLayout(grid_group)

        grid_layout.addWidget(QLabel("Store patterned data in column:"))
        self.col_combo = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            self.col_combo.addItem(f"C{i + 1}  {col.name}", i)
        self.col_combo.addItem(f"C{len(self.worksheet.columns) + 1}  (New Column)", -1)
        grid_layout.addWidget(self.col_combo)

        grid_layout.addWidget(QLabel("From first value:"))
        self.from_edit = QLineEdit("1.0")
        grid_layout.addWidget(self.from_edit)

        grid_layout.addWidget(QLabel("To last value:"))
        self.to_edit = QLineEdit("10.0")
        grid_layout.addWidget(self.to_edit)

        grid_layout.addWidget(QLabel("In steps of:"))
        self.step_edit = QLineEdit("1.0")
        grid_layout.addWidget(self.step_edit)

        row_rep = QHBoxLayout()
        row_rep.addWidget(QLabel("Repeat each value:"))
        self.rep_each_edit = QLineEdit("1")
        row_rep.addWidget(self.rep_each_edit)

        row_rep.addWidget(QLabel("Repeat sequence:"))
        self.rep_seq_edit = QLineEdit("1")
        row_rep.addWidget(self.rep_seq_edit)
        grid_layout.addLayout(row_rep)

        main_layout.addWidget(grid_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(btn_layout)

    def _on_ok(self):
        try:
            from_v = float(self.from_edit.text())
            to_v = float(self.to_edit.text())
            step_v = float(self.step_edit.text())
            if step_v == 0:
                raise ValueError("Step cannot be zero.")
            rep_e = int(self.rep_each_edit.text())
            rep_s = int(self.rep_seq_edit.text())
            if rep_e < 1 or rep_s < 1:
                raise ValueError("Repeat counts must be positive.")
        except Exception as e:
            QMessageBox.warning(self, "Invalid Parameters", f"Please check your input values:\n{e}")
            return

        self.accept()

    def get_settings(self) -> dict:
        return {
            'target_col': self.col_combo.currentData(),
            'from_val': float(self.from_edit.text()),
            'to_val': float(self.to_edit.text()),
            'step': float(self.step_edit.text()),
            'repeat_each': int(self.rep_each_edit.text()),
            'repeat_sequence': int(self.rep_seq_edit.text()),
        }


class RandomNormalDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Random Data - Normal")
        self.setMinimumSize(400, 240)
        self.resize(420, 260)

        main_layout = QVBoxLayout(self)

        group = QGroupBox("Generate Normal Random Numbers")
        layout = QVBoxLayout(group)

        layout.addWidget(QLabel("Number of rows of data to generate:"))
        self.num_edit = QLineEdit("50")
        layout.addWidget(self.num_edit)

        layout.addWidget(QLabel("Store in column:"))
        self.col_combo = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            self.col_combo.addItem(f"C{i + 1}  {col.name}", i)
        self.col_combo.addItem(f"C{len(self.worksheet.columns) + 1}  (New Column)", -1)
        layout.addWidget(self.col_combo)

        row_params = QHBoxLayout()
        row_params.addWidget(QLabel("Mean:"))
        self.mean_edit = QLineEdit("0.0")
        row_params.addWidget(self.mean_edit)

        row_params.addWidget(QLabel("Standard deviation:"))
        self.sd_edit = QLineEdit("1.0")
        row_params.addWidget(self.sd_edit)
        layout.addLayout(row_params)

        main_layout.addWidget(group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

    def _on_ok(self):
        try:
            n = int(self.num_edit.text())
            if n < 1: raise ValueError
            sd = float(self.sd_edit.text())
            if sd <= 0: raise ValueError
            float(self.mean_edit.text())
        except Exception:
            QMessageBox.warning(self, "Invalid Parameters", "Please enter positive number of rows and positive standard deviation.")
            return
        self.accept()

    def get_settings(self) -> dict:
        return {
            'n': int(self.num_edit.text()),
            'target_col': self.col_combo.currentData(),
            'mean': float(self.mean_edit.text()),
            'stdev': float(self.sd_edit.text()),
        }


class RandomUniformDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Random Data - Uniform")
        self.setMinimumSize(400, 240)
        self.resize(420, 260)

        main_layout = QVBoxLayout(self)

        group = QGroupBox("Generate Uniform Random Numbers")
        layout = QVBoxLayout(group)

        layout.addWidget(QLabel("Number of rows of data to generate:"))
        self.num_edit = QLineEdit("50")
        layout.addWidget(self.num_edit)

        layout.addWidget(QLabel("Store in column:"))
        self.col_combo = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            self.col_combo.addItem(f"C{i + 1}  {col.name}", i)
        self.col_combo.addItem(f"C{len(self.worksheet.columns) + 1}  (New Column)", -1)
        layout.addWidget(self.col_combo)

        row_params = QHBoxLayout()
        row_params.addWidget(QLabel("Lower endpoint:"))
        self.low_edit = QLineEdit("0.0")
        row_params.addWidget(self.low_edit)

        row_params.addWidget(QLabel("Upper endpoint:"))
        self.high_edit = QLineEdit("1.0")
        row_params.addWidget(self.high_edit)
        layout.addLayout(row_params)

        main_layout.addWidget(group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

    def _on_ok(self):
        try:
            n = int(self.num_edit.text())
            if n < 1: raise ValueError
            low = float(self.low_edit.text())
            high = float(self.high_edit.text())
            if high <= low: raise ValueError
        except Exception:
            QMessageBox.warning(self, "Invalid Parameters", "Please enter positive number of rows and Upper > Lower endpoint.")
            return
        self.accept()

    def get_settings(self) -> dict:
        return {
            'n': int(self.num_edit.text()),
            'target_col': self.col_combo.currentData(),
            'low': float(self.low_edit.text()),
            'high': float(self.high_edit.text()),
        }


class RandomExponentialDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Random Data - Exponential")
        self.setMinimumSize(400, 240)
        self.resize(420, 260)

        main_layout = QVBoxLayout(self)

        group = QGroupBox("Generate Exponential Random Numbers")
        layout = QVBoxLayout(group)

        layout.addWidget(QLabel("Number of rows of data to generate:"))
        self.num_edit = QLineEdit("50")
        layout.addWidget(self.num_edit)

        layout.addWidget(QLabel("Store in column:"))
        self.col_combo = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            self.col_combo.addItem(f"C{i + 1}  {col.name}", i)
        self.col_combo.addItem(f"C{len(self.worksheet.columns) + 1}  (New Column)", -1)
        layout.addWidget(self.col_combo)

        row_params = QHBoxLayout()
        row_params.addWidget(QLabel("Scale (mean):"))
        self.scale_edit = QLineEdit("1.0")
        row_params.addWidget(self.scale_edit)
        layout.addLayout(row_params)

        main_layout.addWidget(group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

    def _on_ok(self):
        try:
            n = int(self.num_edit.text())
            if n < 1: raise ValueError
            scale = float(self.scale_edit.text())
            if scale <= 0: raise ValueError
        except Exception:
            QMessageBox.warning(self, "Invalid Parameters", "Please enter positive number of rows and positive scale.")
            return
        self.accept()

    def get_settings(self) -> dict:
        return {
            'n': int(self.num_edit.text()),
            'target_col': self.col_combo.currentData(),
            'scale': float(self.scale_edit.text()),
        }


class RandomPoissonDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Random Data - Poisson")
        self.setMinimumSize(400, 240)
        self.resize(420, 260)

        main_layout = QVBoxLayout(self)

        group = QGroupBox("Generate Poisson Random Numbers")
        layout = QVBoxLayout(group)

        layout.addWidget(QLabel("Number of rows of data to generate:"))
        self.num_edit = QLineEdit("50")
        layout.addWidget(self.num_edit)

        layout.addWidget(QLabel("Store in column:"))
        self.col_combo = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            self.col_combo.addItem(f"C{i + 1}  {col.name}", i)
        self.col_combo.addItem(f"C{len(self.worksheet.columns) + 1}  (New Column)", -1)
        layout.addWidget(self.col_combo)

        row_params = QHBoxLayout()
        row_params.addWidget(QLabel("Mean:"))
        self.mean_edit = QLineEdit("1.0")
        row_params.addWidget(self.mean_edit)
        layout.addLayout(row_params)

        main_layout.addWidget(group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

    def _on_ok(self):
        try:
            n = int(self.num_edit.text())
            if n < 1: raise ValueError
            m = float(self.mean_edit.text())
            if m <= 0: raise ValueError
        except Exception:
            QMessageBox.warning(self, "Invalid Parameters", "Please enter positive number of rows and positive mean.")
            return
        self.accept()

    def get_settings(self) -> dict:
        return {
            'n': int(self.num_edit.text()),
            'target_col': self.col_combo.currentData(),
            'mean': float(self.mean_edit.text()),
        }


class RandomBinomialDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Random Data - Binomial")
        self.setMinimumSize(400, 240)
        self.resize(420, 260)

        main_layout = QVBoxLayout(self)

        group = QGroupBox("Generate Binomial Random Numbers")
        layout = QVBoxLayout(group)

        layout.addWidget(QLabel("Number of rows of data to generate:"))
        self.num_edit = QLineEdit("50")
        layout.addWidget(self.num_edit)

        layout.addWidget(QLabel("Store in column:"))
        self.col_combo = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            self.col_combo.addItem(f"C{i + 1}  {col.name}", i)
        self.col_combo.addItem(f"C{len(self.worksheet.columns) + 1}  (New Column)", -1)
        layout.addWidget(self.col_combo)

        row_params = QHBoxLayout()
        row_params.addWidget(QLabel("Number of trials:"))
        self.trials_edit = QLineEdit("10")
        row_params.addWidget(self.trials_edit)

        row_params.addWidget(QLabel("Event probability:"))
        self.prob_edit = QLineEdit("0.5")
        row_params.addWidget(self.prob_edit)
        layout.addLayout(row_params)

        main_layout.addWidget(group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

    def _on_ok(self):
        try:
            n = int(self.num_edit.text())
            if n < 1: raise ValueError
            trials = int(self.trials_edit.text())
            if trials < 1: raise ValueError
            prob = float(self.prob_edit.text())
            if not (0.0 <= prob <= 1.0): raise ValueError
        except Exception:
            QMessageBox.warning(self, "Invalid Parameters", "Please enter positive rows, trials >= 1, and probability between 0 and 1.")
            return
        self.accept()

    def get_settings(self) -> dict:
        return {
            'n': int(self.num_edit.text()),
            'target_col': self.col_combo.currentData(),
            'trials': int(self.trials_edit.text()),
            'prob': float(self.prob_edit.text()),
        }


class PatternedArbitraryDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Make Patterned Data - Arbitrary Set of Numbers")
        self.setMinimumSize(420, 270)
        self.resize(440, 290)

        main_layout = QVBoxLayout(self)
        grid_group = QGroupBox("Pattern Specifications")
        grid_layout = QVBoxLayout(grid_group)

        grid_layout.addWidget(QLabel("Store patterned data in column:"))
        self.col_combo = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            self.col_combo.addItem(f"C{i + 1}  {col.name}", i)
        self.col_combo.addItem(f"C{len(self.worksheet.columns) + 1}  (New Column)", -1)
        grid_layout.addWidget(self.col_combo)

        grid_layout.addWidget(QLabel("Arbitrary set of numbers (space or comma separated):"))
        self.values_edit = QLineEdit("10 20 30 40 50")
        grid_layout.addWidget(self.values_edit)

        row_rep = QHBoxLayout()
        row_rep.addWidget(QLabel("Repeat each value:"))
        self.rep_each_edit = QLineEdit("1")
        row_rep.addWidget(self.rep_each_edit)

        row_rep.addWidget(QLabel("Repeat sequence:"))
        self.rep_seq_edit = QLineEdit("1")
        row_rep.addWidget(self.rep_seq_edit)
        grid_layout.addLayout(row_rep)

        main_layout.addWidget(grid_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

    def _on_ok(self):
        try:
            raw = self.values_edit.text().replace(',', ' ').split()
            nums = [float(x) for x in raw]
            if not nums: raise ValueError
            rep_each = int(self.rep_each_edit.text())
            rep_seq = int(self.rep_seq_edit.text())
            if rep_each < 1 or rep_seq < 1: raise ValueError
        except Exception:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numbers and positive integers for repetitions.")
            return
        self.accept()

    def get_settings(self) -> dict:
        raw = self.values_edit.text().replace(',', ' ').split()
        nums = [float(x) for x in raw]
        return {
            'target_col': self.col_combo.currentData(),
            'numbers': nums,
            'repeat_each': int(self.rep_each_edit.text()),
            'repeat_sequence': int(self.rep_seq_edit.text()),
        }


class PatternedTextDialog(QDialog):
    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Make Patterned Data - Text Values")
        self.setMinimumSize(420, 270)
        self.resize(440, 290)

        main_layout = QVBoxLayout(self)
        grid_group = QGroupBox("Pattern Specifications")
        grid_layout = QVBoxLayout(grid_group)

        grid_layout.addWidget(QLabel("Store patterned data in column:"))
        self.col_combo = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            self.col_combo.addItem(f"C{i + 1}  {col.name}", i)
        self.col_combo.addItem(f"C{len(self.worksheet.columns) + 1}  (New Column)", -1)
        grid_layout.addWidget(self.col_combo)

        grid_layout.addWidget(QLabel("Text values (space or comma separated):"))
        self.values_edit = QLineEdit("Low Medium High")
        grid_layout.addWidget(self.values_edit)

        row_rep = QHBoxLayout()
        row_rep.addWidget(QLabel("Repeat each value:"))
        self.rep_each_edit = QLineEdit("1")
        row_rep.addWidget(self.rep_each_edit)

        row_rep.addWidget(QLabel("Repeat sequence:"))
        self.rep_seq_edit = QLineEdit("1")
        row_rep.addWidget(self.rep_seq_edit)
        grid_layout.addLayout(row_rep)

        main_layout.addWidget(grid_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

    def _on_ok(self):
        try:
            raw = self.values_edit.text().replace(',', ' ').split()
            if not raw: raise ValueError
            rep_each = int(self.rep_each_edit.text())
            rep_seq = int(self.rep_seq_edit.text())
            if rep_each < 1 or rep_seq < 1: raise ValueError
        except Exception:
            QMessageBox.warning(self, "Invalid Input", "Please enter at least one text item and positive repetitions.")
            return
        self.accept()

    def get_settings(self) -> dict:
        raw = self.values_edit.text().replace(',', ' ').split()
        return {
            'target_col': self.col_combo.currentData(),
            'items': raw,
            'repeat_each': int(self.rep_each_edit.text()),
            'repeat_sequence': int(self.rep_seq_edit.text()),
        }


class PatternedDateTimeDialog(QDialog):
    """Dialog for Calc > Make Patterned Data > Date/Time Values..."""

    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Make Patterned Data - Date/Time Values")
        self.setMinimumSize(440, 360)
        self.resize(460, 380)

        main_layout = QVBoxLayout(self)
        grid_group = QGroupBox("Date/Time Specifications")
        grid_layout = QVBoxLayout(grid_group)

        grid_layout.addWidget(QLabel("Store patterned data in column:"))
        self.col_combo = QComboBox()
        for i, col in enumerate(self.worksheet.columns):
            self.col_combo.addItem(f"C{i + 1}  {col.name}", i)
        self.col_combo.addItem(f"C{len(self.worksheet.columns) + 1}  (New Column)", -1)
        grid_layout.addWidget(self.col_combo)

        grid_layout.addWidget(QLabel("From first date/time:"))
        self.start_edit = QLineEdit("2026-01-01")
        grid_layout.addWidget(self.start_edit)

        grid_layout.addWidget(QLabel("To last date/time (or leave blank to use count):"))
        self.end_edit = QLineEdit("2026-01-10")
        grid_layout.addWidget(self.end_edit)

        step_row = QHBoxLayout()
        step_row.addWidget(QLabel("Step size:"))
        self.step_edit = QLineEdit("1")
        step_row.addWidget(self.step_edit)

        step_row.addWidget(QLabel("Unit:"))
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["Days", "Weeks", "Months", "Years", "Hours", "Minutes"])
        step_row.addWidget(self.unit_combo)
        grid_layout.addLayout(step_row)

        row_rep = QHBoxLayout()
        row_rep.addWidget(QLabel("Repeat each:"))
        self.rep_each_edit = QLineEdit("1")
        row_rep.addWidget(self.rep_each_edit)

        row_rep.addWidget(QLabel("Repeat sequence:"))
        self.rep_seq_edit = QLineEdit("1")
        row_rep.addWidget(self.rep_seq_edit)
        grid_layout.addLayout(row_rep)

        main_layout.addWidget(grid_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

    def _on_ok(self):
        try:
            start_s = self.start_edit.text().strip()
            if not start_s:
                raise ValueError("Start date is required.")
            step_v = int(self.step_edit.text())
            if step_v == 0:
                raise ValueError("Step cannot be zero.")
            rep_each = int(self.rep_each_edit.text())
            rep_seq = int(self.rep_seq_edit.text())
            if rep_each < 1 or rep_seq < 1:
                raise ValueError("Repeat counts must be positive.")
        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", f"Please check date/time parameters:\n{e}")
            return
        self.accept()

    def get_settings(self) -> dict:
        unit_map = {
            "Days": "days", "Weeks": "weeks", "Months": "months",
            "Years": "years", "Hours": "hours", "Minutes": "minutes"
        }
        end_s = self.end_edit.text().strip() or None
        unit_s = unit_map.get(self.unit_combo.currentText(), "days")
        fmt = "%Y-%m-%d %H:%M:%S" if unit_s in ("hours", "minutes") else "%Y-%m-%d"

        return {
            'target_col': self.col_combo.currentData(),
            'start_dt': self.start_edit.text().strip(),
            'end_dt': end_s,
            'step': int(self.step_edit.text()),
            'unit': unit_s,
            'repeat_each': int(self.rep_each_edit.text()),
            'repeat_sequence': int(self.rep_seq_edit.text()),
            'dt_format': fmt
        }

