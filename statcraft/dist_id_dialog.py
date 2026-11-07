"""Individual Distribution Identification Dialog matching Minitab 22 specifications."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .dist_id import DISTRIBUTION_NAMES, DISPLAY_NAMES
from .model import Worksheet


class BoxCoxSubDialog(QDialog):
    """Sub-dialog for Box-Cox power transformation options."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Box-Cox Transformation Options")
        self.setMinimumWidth(320)
        self.user_lambda: Optional[float] = None

        layout = QVBoxLayout(self)
        grp = QGroupBox("Box-Cox Power Transformation (W = Y^λ)")
        g_layout = QVBoxLayout(grp)

        self.btn_grp = QButtonGroup(self)
        self.rb_optimal = QRadioButton("Use optimal &λ")
        self.rb_zero = QRadioButton("λ = &0 (ln)")
        self.rb_half = QRadioButton("λ = 0.&5 (square root)")
        self.rb_custom = QRadioButton("Ot&her:")

        self.rb_optimal.setChecked(True)
        self.btn_grp.addButton(self.rb_optimal)
        self.btn_grp.addButton(self.rb_zero)
        self.btn_grp.addButton(self.rb_half)
        self.btn_grp.addButton(self.rb_custom)

        g_layout.addWidget(self.rb_optimal)
        g_layout.addWidget(self.rb_zero)
        g_layout.addWidget(self.rb_half)

        h_cust = QHBoxLayout()
        h_cust.addWidget(self.rb_custom)
        self.spin_cust = QDoubleSpinBox()
        self.spin_cust.setRange(-5.0, 5.0)
        self.spin_cust.setValue(1.0)
        self.spin_cust.setDecimals(2)
        self.spin_cust.setEnabled(False)
        h_cust.addWidget(self.spin_cust)
        g_layout.addLayout(h_cust)

        self.rb_custom.toggled.connect(self.spin_cust.setEnabled)
        layout.addWidget(grp)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(ok_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def _on_ok(self):
        if self.rb_optimal.isChecked():
            self.user_lambda = None
        elif self.rb_zero.isChecked():
            self.user_lambda = 0.0
        elif self.rb_half.isChecked():
            self.user_lambda = 0.5
        else:
            self.user_lambda = float(self.spin_cust.value())
        self.accept()


class JohnsonSubDialog(QDialog):
    """Sub-dialog for Johnson transformation options."""

    def __init__(self, current_threshold: float = 0.10, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Johnson Transformation Options")
        self.setMinimumWidth(320)
        self.p_threshold = current_threshold

        layout = QVBoxLayout(self)
        grp = QGroupBox("Johnson Transformation")
        g_layout = QFormLayout(grp)

        self.spin_p = QDoubleSpinBox()
        self.spin_p.setRange(0.001, 0.999)
        self.spin_p.setValue(current_threshold)
        self.spin_p.setDecimals(3)
        self.spin_p.setSingleStep(0.01)
        g_layout.addRow("&P-value to select best fit:", self.spin_p)
        layout.addWidget(grp)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(ok_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def _on_ok(self):
        self.p_threshold = float(self.spin_p.value())
        self.accept()


class DistIdOptionsSubDialog(QDialog):
    """Sub-dialog for general options."""

    def __init__(self, current_alpha: float = 0.05, current_show_ci: bool = True, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Individual Distribution Identification: Options")
        self.setMinimumWidth(320)
        self.alpha = current_alpha
        self.show_ci = current_show_ci

        layout = QVBoxLayout(self)
        grp = QGroupBox("Options")
        g_layout = QFormLayout(grp)

        self.spin_ci = QDoubleSpinBox()
        self.spin_ci.setRange(1.0, 99.9)
        self.spin_ci.setValue((1.0 - current_alpha) * 100.0)
        self.spin_ci.setDecimals(1)
        g_layout.addRow("Co&nfidence level (%):", self.spin_ci)

        self.chk_show_ci = QCheckBox("Display &confidence intervals on probability plots")
        self.chk_show_ci.setChecked(current_show_ci)
        g_layout.addRow(self.chk_show_ci)

        layout.addWidget(grp)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(ok_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def _on_ok(self):
        ci_level = float(self.spin_ci.value()) / 100.0
        self.alpha = max(0.001, min(0.999, 1.0 - ci_level))
        self.show_ci = self.chk_show_ci.isChecked()
        self.accept()


class DistIdDialog(QDialog):
    """Minitab 22 Individual Distribution Identification dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.selected_params: Optional[Dict[str, Any]] = None
        self.box_cox_lambda: Optional[float] = None
        self.johnson_p_threshold: float = 0.10
        self.alpha: float = 0.05
        self.show_ci: bool = True

        self.setWindowTitle("Individual Distribution Identification")
        self.setMinimumSize(560, 460)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        content_layout = QHBoxLayout()

        # Left Column: Variables List
        left_box = QVBoxLayout()
        left_box.addWidget(QLabel("Variables:"))
        self.col_list = QListWidget()
        for i, col in enumerate(self.worksheet.columns):
            self.col_list.addItem(f"C{i + 1}  {col.name}")
        self.col_list.itemDoubleClicked.connect(self._on_column_double_clicked)
        left_box.addWidget(self.col_list, 1)

        self.btn_select = QPushButton("Select")
        self.btn_select.clicked.connect(self._on_select_clicked)
        left_box.addWidget(self.btn_select)
        content_layout.addLayout(left_box, 1)

        # Right Column: Main Controls
        right_box = QVBoxLayout()

        f_layout = QFormLayout()
        self.txt_column = QLineEdit()
        self.txt_column.setPlaceholderText("Select numeric data column")
        f_layout.addRow("Single &column:", self.txt_column)

        self.spin_subgroup = QSpinBox()
        self.spin_subgroup.setRange(1, 1000)
        self.spin_subgroup.setValue(1)
        f_layout.addRow("Subgroup si&ze:", self.spin_subgroup)
        right_box.addLayout(f_layout)

        # Distributions selection
        dist_grp = QGroupBox("Distributions")
        d_layout = QVBoxLayout(dist_grp)
        self.rb_all = QRadioButton("Use &all distributions and transformations")
        self.rb_all.setChecked(True)
        self.rb_specify = QRadioButton("&Specify:")
        self.dist_btn_grp = QButtonGroup(self)
        self.dist_btn_grp.addButton(self.rb_all)
        self.dist_btn_grp.addButton(self.rb_specify)

        d_layout.addWidget(self.rb_all)
        d_layout.addWidget(self.rb_specify)

        # 4 combo boxes for specify
        self.combos: List[QComboBox] = []
        c_layout = QFormLayout()
        for i in range(1, 5):
            cb = QComboBox()
            for k in DISTRIBUTION_NAMES:
                cb.addItem(DISPLAY_NAMES[k], k)
            cb.setEnabled(False)
            self.combos.append(cb)
            c_layout.addRow(f"Distribution {i}:", cb)
        d_layout.addLayout(c_layout)

        self.rb_specify.toggled.connect(self._on_specify_toggled)
        right_box.addWidget(dist_grp)

        # Sub-dialog buttons row
        btn_sub_row = QHBoxLayout()
        self.btn_boxcox = QPushButton("Bo&x-Cox...")
        self.btn_boxcox.clicked.connect(self._open_boxcox)
        self.btn_johnson = QPushButton("&Johnson...")
        self.btn_johnson.clicked.connect(self._open_johnson)
        self.btn_options = QPushButton("O&ptions...")
        self.btn_options.clicked.connect(self._open_options)

        btn_sub_row.addWidget(self.btn_boxcox)
        btn_sub_row.addWidget(self.btn_johnson)
        btn_sub_row.addWidget(self.btn_options)
        right_box.addLayout(btn_sub_row)

        content_layout.addLayout(right_box, 2)
        main_layout.addLayout(content_layout, 1)

        # Standard dialog action buttons
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        self.btn_ok = QPushButton("OK")
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_help = QPushButton("Help")
        self.btn_help.clicked.connect(self._on_help)

        bottom_bar.addWidget(self.btn_ok)
        bottom_bar.addWidget(self.btn_cancel)
        bottom_bar.addWidget(self.btn_help)
        main_layout.addLayout(bottom_bar)

    def _on_specify_toggled(self, checked: bool):
        for cb in self.combos:
            cb.setEnabled(checked)

    def _open_boxcox(self):
        dlg = BoxCoxSubDialog(self)
        if dlg.exec():
            self.box_cox_lambda = dlg.user_lambda

    def _open_johnson(self):
        dlg = JohnsonSubDialog(self.johnson_p_threshold, self)
        if dlg.exec():
            self.johnson_p_threshold = dlg.p_threshold

    def _open_options(self):
        dlg = DistIdOptionsSubDialog(self.alpha, self.show_ci, self)
        if dlg.exec():
            self.alpha = dlg.alpha
            self.show_ci = dlg.show_ci

    def _on_help(self):
        QMessageBox.information(
            self,
            "Help - Individual Distribution Identification",
            "Individual Distribution Identification assesses how well your data follow 16 continuous distributions "
            "and transformations (including Box-Cox and Johnson systems) using Anderson-Darling goodness-of-fit statistics, "
            "calibrated p-values, and Likelihood Ratio Tests.",
        )

    def _on_column_double_clicked(self, item):
        self._set_selected_column(item.text())

    def _on_select_clicked(self):
        cur = self.col_list.currentItem()
        if cur:
            self._set_selected_column(cur.text())

    def _set_selected_column(self, text: str):
        col_name = text.split("  ", 1)[-1].strip() if "  " in text else text.strip()
        self.txt_column.setText(col_name)

    def _get_column_index(self, name_or_c: str) -> Optional[int]:
        s = name_or_c.strip()
        if not s:
            return None
        if s.upper().startswith("C") and s[1:].isdigit():
            idx = int(s[1:]) - 1
            if 0 <= idx < len(self.worksheet.columns):
                return idx
        for i, c in enumerate(self.worksheet.columns):
            if c.name == s:
                return i
        return None

    def _on_ok(self):
        col_text = self.txt_column.text().strip()
        if not col_text:
            QMessageBox.warning(self, "Input Error", "Please select a single data column.")
            return

        col_idx = self._get_column_index(col_text)
        if col_idx is None:
            QMessageBox.warning(self, "Input Error", f"Column '{col_text}' not found in active worksheet.")
            return

        col = self.worksheet.columns[col_idx]
        if col.kind != "number":
            QMessageBox.warning(self, "Input Error", f"Column '{col.name}' must be numeric.")
            return

        if self.rb_specify.isChecked():
            # Collect unique specified distributions
            chosen: List[str] = []
            for cb in self.combos:
                k = cb.currentData()
                if k and k not in chosen:
                    chosen.append(k)
            dists = chosen if chosen else None
        else:
            dists = None

        self.selected_params = {
            "column_index": col_idx,
            "distributions": dists,
            "subgroup_size": int(self.spin_subgroup.value()),
            "alpha": self.alpha,
            "box_cox_lambda": self.box_cox_lambda,
            "johnson_p_threshold": self.johnson_p_threshold,
            "show_ci": self.show_ci,
        }
        self.accept()
