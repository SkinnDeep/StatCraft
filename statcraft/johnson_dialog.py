"""Johnson Transformation Dialog matching Minitab 22 specifications."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
    QVBoxLayout,
    QWidget,
)

from .dist_id_dialog import JohnsonSubDialog
from .model import Worksheet


class JohnsonDialog(QDialog):
    """Minitab 22 Johnson Transformation dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.selected_params: Optional[Dict[str, Any]] = None
        self.p_threshold: float = 0.10

        self.setWindowTitle("Johnson Transformation")
        self.setMinimumSize(540, 380)
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

        # Right Column: Data Arrangement & Storage
        right_box = QVBoxLayout()

        data_grp = QGroupBox("Data Arrangement")
        f_layout = QFormLayout(data_grp)
        self.txt_column = QLineEdit()
        self.txt_column.setPlaceholderText("Select numeric data column")
        f_layout.addRow("Single &column:", self.txt_column)
        right_box.addWidget(data_grp)

        store_grp = QGroupBox("Store Transformed Data In")
        s_layout = QFormLayout(store_grp)
        self.txt_store = QLineEdit()
        self.txt_store.setPlaceholderText("Enter target column name or index")
        s_layout.addRow("&Single column:", self.txt_store)
        right_box.addWidget(store_grp)

        # Options Button
        btn_opt_row = QHBoxLayout()
        self.btn_options = QPushButton("O&ptions...")
        self.btn_options.clicked.connect(self._open_options)
        btn_opt_row.addWidget(self.btn_options)
        btn_opt_row.addStretch()
        right_box.addLayout(btn_opt_row)
        right_box.addStretch()

        content_layout.addLayout(right_box, 2)
        main_layout.addLayout(content_layout, 1)

        # Action Buttons
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

    def _open_options(self):
        dlg = JohnsonSubDialog(self.p_threshold, self)
        if dlg.exec():
            self.p_threshold = dlg.p_threshold

    def _on_help(self):
        QMessageBox.information(
            self,
            "Help - Johnson Transformation",
            "Johnson Transformation selects the optimal transformation from the Johnson family "
            "(SB, SL, or SU) so your data follow a normal distribution. "
            "You can store the transformed values in a new or existing worksheet column for capability analysis or SPC.",
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
        if not self.txt_store.text().strip():
            self.txt_store.setText(f"Johnson_{col_name}")

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

        store_name = self.txt_store.text().strip() or f"Johnson_{col.name}"

        self.selected_params = {
            "column_index": col_idx,
            "store_column_name": store_name,
            "p_threshold": self.p_threshold,
        }
        self.accept()
