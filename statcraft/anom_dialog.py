"""Analysis of Means (ANOM) Dialog matching Minitab 22 specifications."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .model import Worksheet


class ANOMDialog(QDialog):
    """Minitab 22 Analysis of Means dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.selected_params: Optional[Dict[str, Any]] = None
        self.setWindowTitle("Analysis of Means")
        self.setMinimumSize(540, 420)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        content_layout = QHBoxLayout()

        # Left Column: Available Columns List
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

        # Right Column: Controls
        right_box = QVBoxLayout()

        # Response field
        f_layout = QFormLayout()
        self.txt_response = QLineEdit()
        self.txt_response.setPlaceholderText("Select numeric response column")
        f_layout.addRow("&Response:", self.txt_response)

        # Distribution group
        dist_group = QGroupBox("Distribution of Data")
        dist_layout = QVBoxLayout(dist_group)
        self.btn_grp_dist = QButtonGroup(self)
        self.rb_normal = QRadioButton("&Normal")
        self.rb_binomial = QRadioButton("&Binomial")
        self.rb_poisson = QRadioButton("&Poisson")
        self.rb_normal.setChecked(True)
        self.btn_grp_dist.addButton(self.rb_normal)
        self.btn_grp_dist.addButton(self.rb_binomial)
        self.btn_grp_dist.addButton(self.rb_poisson)
        dist_layout.addWidget(self.rb_normal)
        dist_layout.addWidget(self.rb_binomial)
        dist_layout.addWidget(self.rb_poisson)
        self.btn_grp_dist.buttonClicked.connect(self._on_dist_changed)

        # Factor fields
        self.txt_factor1 = QLineEdit()
        self.txt_factor1.setPlaceholderText("Select factor 1 column")
        f_layout.addRow("Factor &1:", self.txt_factor1)

        self.txt_factor2 = QLineEdit()
        self.txt_factor2.setPlaceholderText("(Optional) Select factor 2 column")
        f_layout.addRow("Factor &2 (Optional):", self.txt_factor2)

        self.spin_sample_size = QDoubleSpinBox()
        self.spin_sample_size.setRange(1, 1000000)
        self.spin_sample_size.setValue(100)
        self.spin_sample_size.setDecimals(0)
        self.spin_sample_size.setEnabled(False)
        f_layout.addRow("&Sample size:", self.spin_sample_size)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.001, 0.499)
        self.spin_alpha.setValue(0.05)
        self.spin_alpha.setSingleStep(0.01)
        self.spin_alpha.setDecimals(3)
        f_layout.addRow("&Alpha level:", self.spin_alpha)

        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("Optional custom chart title")
        f_layout.addRow("&Title:", self.txt_title)

        right_box.addLayout(f_layout)
        right_box.addWidget(dist_group)
        right_box.addStretch()
        content_layout.addLayout(right_box, 2)

        main_layout.addLayout(content_layout)

        # Bottom Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_help = QPushButton("Help")
        self.btn_ok = QPushButton("&OK")
        self.btn_ok.setDefault(True)
        self.btn_cancel = QPushButton("Cancel")
        btn_row.addWidget(self.btn_ok)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_help)
        main_layout.addLayout(btn_row)

        self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel.clicked.connect(self.reject)

        self.current_focus_field: QLineEdit = self.txt_response

    def _on_dist_changed(self):
        is_normal = self.rb_normal.isChecked()
        is_binom = self.rb_binomial.isChecked()
        is_poiss = self.rb_poisson.isChecked()

        self.txt_factor2.setEnabled(is_normal)
        self.spin_sample_size.setEnabled(is_binom or is_poiss)
        if is_binom:
            self.spin_sample_size.setValue(100)
            self.spin_sample_size.setDecimals(0)
        elif is_poiss:
            self.spin_sample_size.setValue(1.0)
            self.spin_sample_size.setDecimals(2)

    def _on_select_clicked(self):
        item = self.col_list.currentItem()
        if not item:
            return
        # Extract column name
        text = item.text().split("  ", 1)[-1].strip()
        # Insert into last focused field
        if not self.txt_response.text():
            self.txt_response.setText(text)
        elif not self.txt_factor1.text():
            self.txt_factor1.setText(text)
        elif self.txt_factor2.isEnabled() and not self.txt_factor2.text():
            self.txt_factor2.setText(text)
        else:
            self.txt_response.setText(text)

    def _on_column_double_clicked(self, item):
        self._on_select_clicked()

    def _resolve_col_idx(self, text: str) -> Optional[int]:
        text = text.strip()
        if not text:
            return None
        # Try exact name match
        for i, c in enumerate(self.worksheet.columns):
            if c.name == text:
                return i
        # Try C1, C2 match
        if text.upper().startswith("C") and text[1:].isdigit():
            idx = int(text[1:]) - 1
            if 0 <= idx < len(self.worksheet.columns):
                return idx
        return None

    def _on_ok(self):
        resp_idx = self._resolve_col_idx(self.txt_response.text())
        f1_idx = self._resolve_col_idx(self.txt_factor1.text())
        f2_idx = self._resolve_col_idx(self.txt_factor2.text()) if self.txt_factor2.isEnabled() else None

        if resp_idx is None:
            self.txt_response.setFocus()
            return
        if f1_idx is None:
            self.txt_factor1.setFocus()
            return

        dist = "normal"
        if self.rb_binomial.isChecked():
            dist = "binomial"
        elif self.rb_poisson.isChecked():
            dist = "poisson"

        self.selected_params = {
            "response_index": resp_idx,
            "factor1_index": f1_idx,
            "factor2_index": f2_idx,
            "distribution": dist,
            "sample_size": self.spin_sample_size.value() if dist != "normal" else 100,
            "alpha": self.spin_alpha.value(),
            "title": self.txt_title.text().strip(),
        }
        self.accept()
