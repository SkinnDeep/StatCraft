"""Qt Dialogs for Tables and Chi-Square analysis with native StatCraft fidelity.

Covers:
- CrossTabulationDialog
- ChiSquareGoodnessOfFitDialog
- ChiSquareAssociationDialog
- TallyDialog
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from .model import Worksheet


class _TablesBaseDialog(QDialog):
    """Base dialog providing standard column selector list and variable binding."""

    def __init__(self, worksheet: Worksheet, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle(title)
        self.resize(560, 440)
        self.last_active_edit: Optional[QLineEdit] = None

    def _create_column_picker(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("Columns:")
        layout.addWidget(lbl)

        self.col_list = QListWidget()
        for idx, col in enumerate(self.worksheet.columns):
            name = col.name if col.name else f"C{idx + 1}"
            kind_tag = " (T)" if col.kind == "text" else ""
            item = QListWidgetItem(f"C{idx + 1}  {name}{kind_tag}")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.col_list.addItem(item)

        self.col_list.itemDoubleClicked.connect(self._on_column_double_clicked)
        layout.addWidget(self.col_list)

        btn_select = QPushButton("Select >>")
        btn_select.clicked.connect(self._on_select_clicked)
        layout.addWidget(btn_select)
        return container

    def _on_column_double_clicked(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.ItemDataRole.UserRole)
        col = self.worksheet.columns[idx]
        name = col.name if col.name else f"C{idx + 1}"
        if self.last_active_edit:
            curr = self.last_active_edit.text().strip()
            if curr:
                self.last_active_edit.setText(f"{curr} '{name}'")
            else:
                self.last_active_edit.setText(f"'{name}'")

    def _on_select_clicked(self) -> None:
        item = self.col_list.currentItem()
        if item:
            self._on_column_double_clicked(item)

    def _register_edit(self, edit: QLineEdit) -> None:
        edit.installEventFilter(self)
        if self.last_active_edit is None:
            self.last_active_edit = edit

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn and isinstance(obj, QLineEdit):
            self.last_active_edit = obj
        return super().eventFilter(obj, event)

    def _parse_column_indices(self, text: str) -> List[int]:
        tokens = []
        in_quotes = False
        curr = ""
        for ch in text:
            if ch in ("'", '"'):
                in_quotes = not in_quotes
            elif ch in (",", " ") and not in_quotes:
                if curr.strip():
                    tokens.append(curr.strip())
                curr = ""
            else:
                curr += ch
        if curr.strip():
            tokens.append(curr.strip())

        indices = []
        for tok in tokens:
            cleaned = tok.strip("'\"")
            found = False
            for idx, col in enumerate(self.worksheet.columns):
                name = col.name if col.name else f"C{idx + 1}"
                if name.lower() == cleaned.lower() or f"c{idx + 1}" == cleaned.lower():
                    indices.append(idx)
                    found = True
                    break
            if not found:
                if cleaned.upper().startswith("C") and cleaned[1:].isdigit():
                    idx = int(cleaned[1:]) - 1
                    if 0 <= idx < len(self.worksheet.columns):
                        indices.append(idx)
        return indices


# ==============================================================================
# 1. CROSS TABULATION AND CHI-SQUARE DIALOG
# ==============================================================================

class CrossTabulationDialog(_TablesBaseDialog):
    """Dialog for Cross Tabulation and Chi-Square matching StatCraft."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Cross Tabulation and Chi-Square", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        # Left picker
        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        # Right pane
        right_pane = QVBoxLayout()

        form = QFormLayout()

        self.edit_rows = QLineEdit()
        self._register_edit(self.edit_rows)
        form.addRow("For rows:", self.edit_rows)

        self.edit_cols = QLineEdit()
        self._register_edit(self.edit_cols)
        form.addRow("For columns:", self.edit_cols)

        self.edit_freq = QLineEdit()
        self._register_edit(self.edit_freq)
        form.addRow("Frequencies (optional):", self.edit_freq)

        right_pane.addLayout(form)

        # Display Options
        grp_display = QGroupBox("Display")
        grp_lay = QVBoxLayout(grp_display)

        self.chk_counts = QCheckBox("Counts")
        self.chk_counts.setChecked(True)
        self.chk_counts.setEnabled(False)  # Always included
        grp_lay.addWidget(self.chk_counts)

        self.chk_expected = QCheckBox("Expected cell counts")
        self.chk_expected.setChecked(self.settings.get("include_expected", True))
        grp_lay.addWidget(self.chk_expected)

        self.chk_row_pct = QCheckBox("Row percents")
        self.chk_row_pct.setChecked(self.settings.get("include_row_percents", True))
        grp_lay.addWidget(self.chk_row_pct)

        self.chk_col_pct = QCheckBox("Column percents")
        self.chk_col_pct.setChecked(self.settings.get("include_col_percents", True))
        grp_lay.addWidget(self.chk_col_pct)

        self.chk_tot_pct = QCheckBox("Total percents")
        self.chk_tot_pct.setChecked(self.settings.get("include_total_percents", False))
        grp_lay.addWidget(self.chk_tot_pct)

        self.chk_chi = QCheckBox("Chi-Square test")
        self.chk_chi.setChecked(self.settings.get("include_chi_square", True))
        grp_lay.addWidget(self.chk_chi)

        right_pane.addWidget(grp_display)

        # Populate initial values
        if "row_column" in self.settings:
            idx = self.settings["row_column"]
            if 0 <= idx < len(self.worksheet.columns):
                self.edit_rows.setText(f"'{self.worksheet.columns[idx].name}'")
        if "col_column" in self.settings:
            idx = self.settings["col_column"]
            if 0 <= idx < len(self.worksheet.columns):
                self.edit_cols.setText(f"'{self.worksheet.columns[idx].name}'")
        if "freq_column" in self.settings and self.settings["freq_column"] is not None:
            idx = self.settings["freq_column"]
            if 0 <= idx < len(self.worksheet.columns):
                self.edit_freq.setText(f"'{self.worksheet.columns[idx].name}'")

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        right_pane.addWidget(buttons)

        main_layout.addLayout(right_pane)

    def _on_accept(self) -> None:
        r_indices = self._parse_column_indices(self.edit_rows.text())
        if not r_indices:
            QMessageBox.warning(self, "Invalid Row Variable", "Please select a row variable.")
            return

        c_indices = self._parse_column_indices(self.edit_cols.text())
        if not c_indices:
            QMessageBox.warning(self, "Invalid Column Variable", "Please select a column variable.")
            return

        freq_idx = None
        if self.edit_freq.text().strip():
            f_indices = self._parse_column_indices(self.edit_freq.text())
            if not f_indices:
                QMessageBox.warning(self, "Invalid Frequency Variable", "Frequency variable was not found.")
                return
            freq_idx = f_indices[0]

        self.settings["row_column"] = r_indices[0]
        self.settings["col_column"] = c_indices[0]
        self.settings["freq_column"] = freq_idx
        self.settings["include_expected"] = self.chk_expected.isChecked()
        self.settings["include_row_percents"] = self.chk_row_pct.isChecked()
        self.settings["include_col_percents"] = self.chk_col_pct.isChecked()
        self.settings["include_total_percents"] = self.chk_tot_pct.isChecked()
        self.settings["include_chi_square"] = self.chk_chi.isChecked()
        self.accept()


# ==============================================================================
# 2. CHI-SQUARE GOODNESS-OF-FIT DIALOG
# ==============================================================================

class ChiSquareGoodnessOfFitDialog(_TablesBaseDialog):
    """Dialog for Chi-Square Goodness-of-Fit Test (One Variable) matching StatCraft."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Chi-Square Goodness-of-Fit Test", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        right_pane = QVBoxLayout()

        form = QFormLayout()

        self.edit_obs = QLineEdit()
        self._register_edit(self.edit_obs)
        form.addRow("Categorical variable:", self.edit_obs)

        self.edit_freq = QLineEdit()
        self._register_edit(self.edit_freq)
        form.addRow("Observed counts in (optional):", self.edit_freq)

        right_pane.addLayout(form)

        # Test Proportions Box
        grp_prop = QGroupBox("Test Proportions")
        prop_lay = QVBoxLayout(grp_prop)

        self.rb_equal = QRadioButton("Equal proportions")
        self.rb_equal.setChecked(True)
        prop_lay.addWidget(self.rb_equal)

        self.rb_specified = QRadioButton("Specific proportions:")
        prop_lay.addWidget(self.rb_specified)

        self.edit_props = QLineEdit()
        self.edit_props.setPlaceholderText("e.g. 0.25 0.25 0.50 (or category:prop pairs)")
        self.edit_props.setEnabled(False)
        self.rb_specified.toggled.connect(self.edit_props.setEnabled)
        prop_lay.addWidget(self.edit_props)

        right_pane.addWidget(grp_prop)

        if "observed_column" in self.settings:
            idx = self.settings["observed_column"]
            if 0 <= idx < len(self.worksheet.columns):
                self.edit_obs.setText(f"'{self.worksheet.columns[idx].name}'")
        if "freq_column" in self.settings and self.settings["freq_column"] is not None:
            idx = self.settings["freq_column"]
            if 0 <= idx < len(self.worksheet.columns):
                self.edit_freq.setText(f"'{self.worksheet.columns[idx].name}'")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        right_pane.addWidget(buttons)

        main_layout.addLayout(right_pane)

    def _on_accept(self) -> None:
        obs_indices = self._parse_column_indices(self.edit_obs.text())
        if not obs_indices:
            QMessageBox.warning(self, "Invalid Input", "Please select a categorical variable.")
            return

        freq_idx = None
        if self.edit_freq.text().strip():
            f_indices = self._parse_column_indices(self.edit_freq.text())
            if not f_indices:
                QMessageBox.warning(self, "Invalid Frequency Variable", "Observed counts column not found.")
                return
            freq_idx = f_indices[0]

        test_props = None
        if self.rb_specified.isChecked():
            txt = self.edit_props.text().strip()
            if not txt:
                QMessageBox.warning(self, "Missing Proportions", "Please specify test proportions.")
                return
            # Parse proportions
            parts = txt.replace(",", " ").split()
            props = {}
            for p in parts:
                if ":" in p:
                    k, v = p.split(":", 1)
                    try:
                        props[k.strip()] = float(v.strip())
                    except ValueError:
                        pass
                else:
                    try:
                        idx_k = len(props)
                        props[str(idx_k)] = float(p.strip())
                    except ValueError:
                        pass
            if not props:
                QMessageBox.warning(self, "Invalid Proportions", "Could not parse any numeric proportions.")
                return
            test_props = props

        self.settings["observed_column"] = obs_indices[0]
        self.settings["freq_column"] = freq_idx
        self.settings["test_proportions"] = test_props
        self.accept()


# ==============================================================================
# 3. CHI-SQUARE ASSOCIATION DIALOG (TABLE IN WORKSHEET)
# ==============================================================================

class ChiSquareAssociationDialog(_TablesBaseDialog):
    """Dialog for Chi-Square Test for Association (Two-Way Table in Worksheet)."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Chi-Square Test for Association", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        right_pane = QVBoxLayout()

        form = QFormLayout()

        self.edit_cols = QLineEdit()
        self._register_edit(self.edit_cols)
        form.addRow("Columns containing the table:", self.edit_cols)

        self.edit_labels = QLineEdit()
        self._register_edit(self.edit_labels)
        form.addRow("Labels for the rows (optional):", self.edit_labels)

        right_pane.addLayout(form)

        lbl_info = QLabel("Select 2 or more numeric columns that contain contingency table counts.")
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #555555; font-size: 11px;")
        right_pane.addWidget(lbl_info)

        if "table_columns" in self.settings:
            cols = self.settings["table_columns"]
            names = [f"'{self.worksheet.columns[i].name}'" for i in cols if 0 <= i < len(self.worksheet.columns)]
            self.edit_cols.setText(" ".join(names))

        if "row_labels_column" in self.settings and self.settings["row_labels_column"] is not None:
            idx = self.settings["row_labels_column"]
            if 0 <= idx < len(self.worksheet.columns):
                self.edit_labels.setText(f"'{self.worksheet.columns[idx].name}'")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        right_pane.addWidget(buttons)

        main_layout.addLayout(right_pane)

    def _on_accept(self) -> None:
        table_cols = self._parse_column_indices(self.edit_cols.text())
        if len(table_cols) < 2:
            QMessageBox.warning(self, "Invalid Selection", "Please select at least 2 table columns.")
            return

        for idx in table_cols:
            if self.worksheet.columns[idx].kind != "number":
                QMessageBox.warning(self, "Invalid Column Type", f"Table column C{idx+1} must be numeric.")
                return

        row_label_idx = None
        if self.edit_labels.text().strip():
            lbl_indices = self._parse_column_indices(self.edit_labels.text())
            if lbl_indices:
                row_label_idx = lbl_indices[0]

        self.settings["table_columns"] = table_cols
        self.settings["row_labels_column"] = row_label_idx
        self.accept()


# ==============================================================================
# 4. TALLY INDIVIDUAL VARIABLES DIALOG
# ==============================================================================

class TallyDialog(_TablesBaseDialog):
    """Dialog for Tally Individual Variables matching StatCraft."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Tally Individual Variables", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        right_pane = QVBoxLayout()

        form = QFormLayout()

        self.edit_vars = QLineEdit()
        self._register_edit(self.edit_vars)
        form.addRow("Variables:", self.edit_vars)

        right_pane.addLayout(form)

        # Display Options
        grp_display = QGroupBox("Display")
        grp_lay = QVBoxLayout(grp_display)

        self.chk_counts = QCheckBox("Counts")
        self.chk_counts.setChecked(self.settings.get("include_counts", True))
        grp_lay.addWidget(self.chk_counts)

        self.chk_percents = QCheckBox("Percents")
        self.chk_percents.setChecked(self.settings.get("include_percents", True))
        grp_lay.addWidget(self.chk_percents)

        self.chk_cum_counts = QCheckBox("Cumulative counts")
        self.chk_cum_counts.setChecked(self.settings.get("include_cumulative_counts", True))
        grp_lay.addWidget(self.chk_cum_counts)

        self.chk_cum_percents = QCheckBox("Cumulative percents")
        self.chk_cum_percents.setChecked(self.settings.get("include_cumulative_percents", True))
        grp_lay.addWidget(self.chk_cum_percents)

        right_pane.addWidget(grp_display)

        if "columns" in self.settings:
            cols = self.settings["columns"]
            names = [f"'{self.worksheet.columns[i].name}'" for i in cols if 0 <= i < len(self.worksheet.columns)]
            self.edit_vars.setText(" ".join(names))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        right_pane.addWidget(buttons)

        main_layout.addLayout(right_pane)

    def _on_accept(self) -> None:
        cols = self._parse_column_indices(self.edit_vars.text())
        if not cols:
            QMessageBox.warning(self, "Invalid Selection", "Please select at least one variable to tally.")
            return

        if not (self.chk_counts.isChecked() or self.chk_percents.isChecked() or self.chk_cum_counts.isChecked() or self.chk_cum_percents.isChecked()):
            QMessageBox.warning(self, "Display Option", "Please select at least one display option.")
            return

        self.settings["columns"] = cols
        self.settings["include_counts"] = self.chk_counts.isChecked()
        self.settings["include_percents"] = self.chk_percents.isChecked()
        self.settings["include_cumulative_counts"] = self.chk_cum_counts.isChecked()
        self.settings["include_cumulative_percents"] = self.chk_cum_percents.isChecked()
        self.accept()
