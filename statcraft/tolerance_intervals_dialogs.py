"""Qt Dialogs for Tolerance Intervals (Normal Distribution) with native StatCraft PE fidelity.

Form Evidence:
- 1140-TOLERANCEINTERVALS.MDF (MenuID 41198, HelpID 88690)
- 1144-TOLERINTERVALOPTIONS.MDF (HelpID 88692)
- 1142-TOLERINTERVALGRAPHS.MDF (HelpID 88691)
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
    QVBoxLayout,
    QWidget,
)

from .model import Worksheet
from .variable_dialogs import resolve_variables


class ToleranceIntervalsOptionsDialog(QDialog):
    """Sub-dialog for confidence level and interval type (1144-TOLERINTERVALOPTIONS.MDF)."""

    def __init__(self, current_opts: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Tolerance Intervals: Options")
        self.setMinimumSize(380, 260)
        self.resize(380, 260)
        self.setSizeGripEnabled(True)

        opts = current_opts or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.edit_conf = QLineEdit(str(opts.get("conf_level", 95.0)))
        form.addRow("&Confidence level:", self.edit_conf)

        self.combo_type = QComboBox()
        self.combo_type.addItem("Two-sided", "two_sided")
        self.combo_type.addItem("Lower bound", "lower")
        self.combo_type.addItem("Upper bound", "upper")

        current_type = opts.get("interval_type", "two_sided")
        idx = {"two_sided": 0, "lower": 1, "upper": 2}.get(current_type, 0)
        self.combo_type.setCurrentIndex(idx)
        form.addRow("&Tolerance interval:", self.combo_type)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._validate_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _validate_and_accept(self) -> None:
        try:
            conf = float(self.edit_conf.text().strip())
            if not (0.0 < conf < 100.0):
                raise ValueError("Confidence level must be strictly between 0 and 100.")
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Confidence Level", str(exc))
            return
        self.accept()

    def get_options(self) -> Dict[str, Any]:
        return {
            "conf_level": float(self.edit_conf.text().strip()),
            "interval_type": self.combo_type.currentData(),
        }


class ToleranceIntervalsGraphsDialog(QDialog):
    """Sub-dialog for graphic display options (1142-TOLERINTERVALGRAPHS.MDF)."""

    def __init__(self, current_graphs: bool = True, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Tolerance Intervals: Graphs")
        self.setMinimumSize(380, 260)
        self.resize(380, 260)
        self.setSizeGripEnabled(True)

        layout = QVBoxLayout(self)
        self.chk_plot = QCheckBox("&Tolerance interval plots")
        self.chk_plot.setChecked(current_graphs)
        layout.addWidget(self.chk_plot)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_show_graphs(self) -> bool:
        return self.chk_plot.isChecked()


class ToleranceIntervalsDialog(QDialog):
    """Main dialog for Tolerance Intervals (Normal Distribution) matching 1140-TOLERANCEINTERVALS.MDF."""

    def __init__(
        self,
        worksheet: Worksheet,
        initial_vars: Optional[List[str]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Tolerance Intervals (Normal Distribution)")
        self.setMinimumSize(560, 420)
        self.resize(560, 420)
        self.setSizeGripEnabled(True)
        self.last_active_edit: Optional[QLineEdit] = None

        self.options: Dict[str, Any] = {
            "conf_level": 95.0,
            "interval_type": "two_sided",
        }
        self.show_graphs: bool = True
        self.result_params: Optional[Dict[str, Any]] = None

        self._setup_ui(initial_vars or [])

    def _setup_ui(self, initial_vars: List[str]) -> None:
        main_layout = QHBoxLayout(self)

        # Left Column: Column Picker List
        left_layout = QVBoxLayout()
        lbl_cols = QLabel("Columns:")
        left_layout.addWidget(lbl_cols)

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

        # Right Column: Data Arrangement & Inputs
        right_layout = QVBoxLayout()

        lbl_arrange = QLabel("&Data arrangement:")
        right_layout.addWidget(lbl_arrange)
        self.combo_arrange = QComboBox()
        self.combo_arrange.addItem("One or more samples, each in a column", 0)
        self.combo_arrange.addItem("Summarized data", 1)
        self.combo_arrange.currentIndexChanged.connect(self._on_arrange_changed)
        lbl_arrange.setBuddy(self.combo_arrange)
        right_layout.addWidget(self.combo_arrange)

        # Container for Column Samples Mode
        self.widget_cols = QWidget()
        layout_cols = QFormLayout(self.widget_cols)
        layout_cols.setContentsMargins(0, 5, 0, 5)

        self.edit_vars = QLineEdit(" ".join(initial_vars))
        self.edit_vars.textChanged.connect(lambda: setattr(self, "last_active_edit", self.edit_vars))
        layout_cols.addRow("&Variables:", self.edit_vars)
        right_layout.addWidget(self.widget_cols)

        # Container for Summarized Data Mode
        self.widget_summ = QWidget()
        layout_summ = QFormLayout(self.widget_summ)
        layout_summ.setContentsMargins(0, 5, 0, 5)

        self.edit_n = QLineEdit()
        self.edit_n.textChanged.connect(lambda: setattr(self, "last_active_edit", self.edit_n))
        layout_summ.addRow("S&ample size:", self.edit_n)

        self.edit_mean = QLineEdit()
        self.edit_mean.textChanged.connect(lambda: setattr(self, "last_active_edit", self.edit_mean))
        layout_summ.addRow("Sample &mean:", self.edit_mean)

        self.edit_std = QLineEdit()
        self.edit_std.textChanged.connect(lambda: setattr(self, "last_active_edit", self.edit_std))
        layout_summ.addRow("&Standard deviation:", self.edit_std)

        self.widget_summ.setVisible(False)
        right_layout.addWidget(self.widget_summ)

        # Minimum percentage input
        form_pct = QFormLayout()
        self.edit_min_pct = QLineEdit("95.0")
        self.edit_min_pct.textChanged.connect(lambda: setattr(self, "last_active_edit", self.edit_min_pct))
        form_pct.addRow("Mi&nimum percentage of population in interval:", self.edit_min_pct)
        right_layout.addLayout(form_pct)

        # Sub-dialog buttons row
        btn_layout = QHBoxLayout()
        self.btn_options = QPushButton("O&ptions...")
        self.btn_options.clicked.connect(self._on_options_clicked)
        btn_layout.addWidget(self.btn_options)

        self.btn_graphs = QPushButton("&Graphs...")
        self.btn_graphs.clicked.connect(self._on_graphs_clicked)
        btn_layout.addWidget(self.btn_graphs)
        btn_layout.addStretch()
        right_layout.addLayout(btn_layout)

        right_layout.addStretch()

        # Dialog Buttons
        dialog_btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Help
        )
        dialog_btns.accepted.connect(self._validate_and_accept)
        dialog_btns.rejected.connect(self.reject)
        dialog_btns.helpRequested.connect(self._on_help)
        right_layout.addWidget(dialog_btns)

        main_layout.addLayout(right_layout, 2)
        self.last_active_edit = self.edit_vars

    def _on_arrange_changed(self, idx: int) -> None:
        is_cols = (idx == 0)
        self.widget_cols.setVisible(is_cols)
        self.widget_summ.setVisible(not is_cols)
        self.btn_graphs.setEnabled(is_cols)  # Graphs enabled when raw sample data provided
        self.last_active_edit = self.edit_vars if is_cols else self.edit_n

    def _on_select_clicked(self) -> None:
        current_item = self.col_list.currentItem()
        if not current_item or not self.last_active_edit:
            return
        col_name = current_item.data(Qt.ItemDataRole.UserRole)
        formatted = f"'{col_name}'" if " " in col_name else col_name
        current_text = self.last_active_edit.text().strip()
        if current_text:
            self.last_active_edit.setText(f"{current_text} {formatted}")
        else:
            self.last_active_edit.setText(formatted)

    def _on_options_clicked(self) -> None:
        dlg = ToleranceIntervalsOptionsDialog(self.options, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.options = dlg.get_options()

    def _on_graphs_clicked(self) -> None:
        dlg = ToleranceIntervalsGraphsDialog(self.show_graphs, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.show_graphs = dlg.get_show_graphs()

    def _on_help(self) -> None:
        QMessageBox.information(
            self,
            "Tolerance Intervals Help",
            "A tolerance interval covers at least a specified percentage of a population with a given confidence level.\n\n"
            "Calculates both parametric Normal intervals and distribution-free Nonparametric intervals.",
        )

    def _validate_and_accept(self) -> None:
        is_cols = (self.combo_arrange.currentIndex() == 0)

        try:
            min_pct = float(self.edit_min_pct.text().strip())
            if not (0.0 < min_pct < 100.0):
                raise ValueError("Minimum percentage must be between 0 and 100.")
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Minimum Percentage", str(exc))
            self.edit_min_pct.setFocus()
            return

        settings = copy.deepcopy(self.options)
        settings["min_percent"] = min_pct
        settings["show_graphs"] = self.show_graphs and is_cols

        if is_cols:
            vars_text = self.edit_vars.text().strip()
            if not vars_text:
                QMessageBox.warning(self, "Missing Variables", "Please select at least one numeric sample column.")
                self.edit_vars.setFocus()
                return

            try:
                col_indices = resolve_variables(vars_text, self.worksheet, kinds=("number",))
                if not col_indices:
                    raise ValueError("No valid numeric columns found.")
            except Exception as exc:
                QMessageBox.warning(self, "Invalid Variables", str(exc))
                self.edit_vars.setFocus()
                return

            self.result_params = {
                "is_summarized": False,
                "variable_indices": col_indices,
                "settings": settings,
            }
        else:
            try:
                n_val = int(self.edit_n.text().strip())
                if n_val < 2:
                    raise ValueError("Sample size must be an integer >= 2.")
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid Sample Size", str(exc))
                self.edit_n.setFocus()
                return

            try:
                mean_val = float(self.edit_mean.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Invalid Sample Mean", "Sample mean must be a valid number.")
                self.edit_mean.setFocus()
                return

            try:
                std_val = float(self.edit_std.text().strip())
                if std_val <= 0.0:
                    raise ValueError("Standard deviation must be positive.")
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid Standard Deviation", str(exc))
                self.edit_std.setFocus()
                return

            self.result_params = {
                "is_summarized": True,
                "n": n_val,
                "mean": mean_val,
                "std": std_val,
                "settings": settings,
            }

        self.accept()
