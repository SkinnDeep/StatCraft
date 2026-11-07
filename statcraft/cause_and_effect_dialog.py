"""Cause-and-Effect Diagram Dialog matching Minitab 22 specifications (%Fishbone)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .cause_and_effect import DEFAULT_BRANCH_LABELS
from .model import Worksheet


class CauseAndEffectDialog(QDialog):
    """Minitab 22 Cause-and-Effect Diagram dialog."""

    def __init__(self, worksheet: Worksheet, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.selected_params: Optional[Dict[str, Any]] = None
        self.setWindowTitle("Cause-and-Effect Diagram")
        self.setMinimumSize(620, 480)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        content_layout = QHBoxLayout()

        # Left Column: Available Worksheet Columns List
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

        # Right Column: Branch Table & Parameters
        right_box = QVBoxLayout()

        # Table of 6 Branches: Branch | Causes (Column) | Label
        right_box.addWidget(QLabel("Branches and Causes:"))
        self.branch_table = QTableWidget(6, 3)
        self.branch_table.setHorizontalHeaderLabels(["Branch", "Causes (Column)", "Label"])
        self.branch_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.branch_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.branch_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.branch_table.verticalHeader().setVisible(False)

        for i in range(6):
            # Branch number item (read-only)
            b_item = QTableWidgetItem(f"Branch {i + 1}")
            b_item.setFlags(b_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            b_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.branch_table.setItem(i, 0, b_item)

            # Causes column name item
            c_item = QTableWidgetItem("")
            self.branch_table.setItem(i, 1, c_item)

            # Default Label item
            lbl_item = QTableWidgetItem(DEFAULT_BRANCH_LABELS[i] if i < len(DEFAULT_BRANCH_LABELS) else f"Branch {i + 1}")
            self.branch_table.setItem(i, 2, lbl_item)

        right_box.addWidget(self.branch_table, 1)

        # Effect and Title Form
        f_layout = QFormLayout()
        self.txt_effect = QLineEdit()
        self.txt_effect.setPlaceholderText("e.g. Surface Flaws, Delayed Departure")
        f_layout.addRow("&Effect:", self.txt_effect)

        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("Optional diagram title")
        f_layout.addRow("&Title:", self.txt_title)
        right_box.addLayout(f_layout)

        # Checkboxes
        self.chk_no_empty = QCheckBox("&Do not display empty branches")
        self.chk_no_labels = QCheckBox("Do &not label the branches")
        right_box.addWidget(self.chk_no_empty)
        right_box.addWidget(self.chk_no_labels)

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

    def _on_select_clicked(self):
        item = self.col_list.currentItem()
        if not item:
            return
        col_name = item.text().split("  ", 1)[-1].strip()

        # Check if table has a selected row in the Causes column
        row = self.branch_table.currentRow()
        if row == -1:
            # Find first empty causes row
            for r in range(6):
                it = self.branch_table.item(r, 1)
                if not it or not it.text().strip():
                    row = r
                    break
            if row == -1:
                row = 0

        self.branch_table.item(row, 1).setText(col_name)
        # Advance selection
        next_row = min(5, row + 1)
        self.branch_table.setCurrentCell(next_row, 1)

    def _on_column_double_clicked(self, item):
        self._on_select_clicked()

    def _resolve_col_idx(self, text: str) -> Optional[int]:
        text = text.strip()
        if not text:
            return None
        for i, c in enumerate(self.worksheet.columns):
            if c.name == text:
                return i
        if text.upper().startswith("C") and text[1:].isdigit():
            idx = int(text[1:]) - 1
            if 0 <= idx < len(self.worksheet.columns):
                return idx
        return None

    def _on_ok(self):
        effect_str = self.txt_effect.text().strip() or "Effect"
        title_str = self.txt_title.text().strip()

        branches_spec: List[Dict[str, Any]] = []
        for r in range(6):
            c_text = self.branch_table.item(r, 1).text().strip() if self.branch_table.item(r, 1) else ""
            lbl_text = self.branch_table.item(r, 2).text().strip() if self.branch_table.item(r, 2) else ""
            col_idx = self._resolve_col_idx(c_text)

            causes_vals: List[str] = []
            if col_idx is not None and 0 <= col_idx < len(self.worksheet.columns):
                col = self.worksheet.columns[col_idx]
                for v in col.values:
                    if v is not None:
                        s = str(v).strip()
                        if s and s.lower() != "nan" and s.lower() != "none":
                            causes_vals.append(s)

            branches_spec.append({
                "column_index": col_idx,
                "label": lbl_text or DEFAULT_BRANCH_LABELS[r],
                "causes": causes_vals,
            })

        self.selected_params = {
            "branches": branches_spec,
            "effect": effect_str,
            "title": title_str,
            "no_empty": self.chk_no_empty.isChecked(),
            "no_labels": self.chk_no_labels.isChecked(),
        }
        self.accept()
