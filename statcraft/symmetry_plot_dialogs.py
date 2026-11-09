"""Qt Dialogs for Symmetry Plot matching Minitab standard."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .model import Worksheet
from .variable_dialogs import resolve_variables


class SymmetryPlotOptionsDialog(QDialog):
    """Sub-dialog for Symmetry Plot display options."""

    def __init__(self, current_options: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Symmetry Plot: Options")
        self.setMinimumSize(380, 220)
        self.resize(380, 220)
        self.setSizeGripEnabled(True)

        opts = current_options or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.chk_line = QCheckBox("Draw 45° reference line (Y = X)")
        self.chk_line.setChecked(opts.get("show_line", True))
        form.addRow(self.chk_line)

        self.edit_title = QLineEdit(opts.get("title", ""))
        form.addRow("&Title:", self.edit_title)

        self.edit_sub = QLineEdit(opts.get("subtitle", ""))
        form.addRow("&Subtitle:", self.edit_sub)

        self.edit_foot = QLineEdit(opts.get("footnote", ""))
        form.addRow("&Footnote:", self.edit_foot)

        layout.addLayout(form)
        layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_options(self) -> Dict[str, Any]:
        return {
            "show_line": self.chk_line.isChecked(),
            "title": self.edit_title.text().strip(),
            "subtitle": self.edit_sub.text().strip(),
            "footnote": self.edit_foot.text().strip(),
        }


class SymmetryPlotDialog(QDialog):
    """Main Symmetry Plot dialog matching Minitab standard."""

    def __init__(
        self,
        worksheet: Worksheet,
        initial_vars: Optional[List[str]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Symmetry Plot")
        self.setMinimumSize(540, 380)
        self.resize(540, 380)
        self.setSizeGripEnabled(True)

        self.options: Dict[str, Any] = {
            "show_line": True,
            "title": "",
            "subtitle": "",
            "footnote": "",
        }
        self.result_params: Optional[Dict[str, Any]] = None

        self._setup_ui(initial_vars or [])

    def _setup_ui(self, initial_vars: List[str]):
        main_layout = QHBoxLayout(self)

        # Left Column: Column Picker List
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Columns:"))

        self.col_list = QListWidget()
        for idx, col in enumerate(self.worksheet.columns):
            name = col.name if col.name else f"C{idx+1}"
            item = QListWidgetItem(f"C{idx+1}   {name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.col_list.addItem(item)
        left_layout.addWidget(self.col_list)

        self.btn_select = QPushButton("Select")
        self.btn_select.clicked.connect(self._on_select_clicked)
        left_layout.addWidget(self.btn_select)
        main_layout.addLayout(left_layout, 1)

        # Right Column: Variables & Options
        right_layout = QVBoxLayout()
        form = QFormLayout()

        self.edit_vars = QLineEdit()
        self.edit_vars.setPlaceholderText("One or more numeric columns (e.g. C1 C2)")
        form.addRow("&Variables:", self.edit_vars)

        right_layout.addLayout(form)
        right_layout.addStretch()

        # Options Button
        btn_opts = QPushButton("&Options…")
        btn_opts.clicked.connect(self._on_options)
        right_layout.addWidget(btn_opts, 0, Qt.AlignmentFlag.AlignLeft)

        # Standard Dialog Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        right_layout.addWidget(btns)

        main_layout.addLayout(right_layout, 2)

        # Populate initial vars
        if initial_vars:
            self.edit_vars.setText(" ".join(initial_vars))

    def _on_select_clicked(self):
        item = self.col_list.currentItem()
        if not item:
            return
        col_name = item.data(Qt.ItemDataRole.UserRole)
        current = self.edit_vars.text().strip()
        new_text = f"{current} {col_name}".strip() if current else col_name
        self.edit_vars.setText(new_text)

    def _on_options(self):
        dlg = SymmetryPlotOptionsDialog(self.options, self)
        if dlg.exec():
            self.options.update(dlg.get_options())

    def _on_ok(self):
        text = self.edit_vars.text().strip()
        if not text:
            QMessageBox.warning(self, "Missing Variable", "Please enter one or more numeric variables for the Symmetry Plot.")
            return

        cols = resolve_variables(text, self.worksheet, kinds=('number',))
        if not cols:
            QMessageBox.warning(self, "Invalid Variables", f"Could not find valid numeric columns matching: '{text}'.")
            return

        self.result_params = {
            "columns": cols,
            "settings": dict(self.options),
        }
        self.accept()
