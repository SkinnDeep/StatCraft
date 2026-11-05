"""Interactive dialog for JMP / Minitab Variability and Attribute Gauge Chart platform."""
from __future__ import annotations

from typing import Any, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
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

from .variability_chart import VariabilityPlatformWidget
from .variability_engine import calculate_variability_analysis


class VariabilityChartDialog(QDialog):
    """Dialog to configure and launch Variability / Gauge Chart analysis."""

    def __init__(self, main_window, parent: Optional[QWidget] = None):
        super().__init__(parent or main_window)
        self.main_window = main_window
        self.setWindowTitle("Variability / Attribute Gauge Chart")
        self.resize(520, 520)

        ws = getattr(main_window.presenter, "worksheet", None)
        self.worksheet = ws
        self.columns = list(ws.columns) if ws else []

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header note
        desc = QLabel(
            "Construct a multi-factor hierarchical variability plot and ANOVA Gage R&R analysis.\n"
            "Select a measurement response and one or more grouping factors (e.g. Part, Operator)."
        )
        desc.setStyleSheet("color: #475569; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        form_frame = QFrame()
        form_frame.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px;")
        form = QFormLayout(form_frame)
        form.setSpacing(10)

        # 1. Response Y
        self.combo_y = QComboBox()
        for c in self.columns:
            if c.kind == "number":
                self.combo_y.addItem(c.name, c)
        form.addRow("Response (Y, Measurement):", self.combo_y)

        # 2. X Factors List (Multiple selection / ordered)
        factors_container = QWidget()
        factors_layout = QHBoxLayout(factors_container)
        factors_layout.setContentsMargins(0, 0, 0, 0)
        self.list_available = QListWidget()
        for c in self.columns:
            self.list_available.addItem(c.name)

        btns_vbox = QVBoxLayout()
        self.btn_add_factor = QPushButton("Add X →")
        self.btn_remove_factor = QPushButton("← Remove")
        btns_vbox.addWidget(self.btn_add_factor)
        btns_vbox.addWidget(self.btn_remove_factor)
        btns_vbox.addStretch()

        self.list_selected_x = QListWidget()

        self.btn_add_factor.clicked.connect(self._add_factor)
        self.btn_remove_factor.clicked.connect(self._remove_factor)

        factors_layout.addWidget(self.list_available)
        factors_layout.addLayout(btns_vbox)
        factors_layout.addWidget(self.list_selected_x)

        form.addRow("Grouping Factors (X, Hierarchy):", factors_container)

        # 3. Spec limits (optional)
        limits_widget = QWidget()
        limits_layout = QHBoxLayout(limits_widget)
        limits_layout.setContentsMargins(0, 0, 0, 0)
        self.edit_lsl = QLineEdit()
        self.edit_lsl.setPlaceholderText("LSL (optional)")
        self.edit_usl = QLineEdit()
        self.edit_usl.setPlaceholderText("USL (optional)")
        limits_layout.addWidget(QLabel("LSL:"))
        limits_layout.addWidget(self.edit_lsl)
        limits_layout.addWidget(QLabel("USL:"))
        limits_layout.addWidget(self.edit_usl)
        form.addRow("Specification Limits:", limits_widget)

        layout.addWidget(form_frame)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Run Variability Analysis")
        button_box.accepted.connect(self._run_analysis)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Auto-populate reasonable defaults if columns match common names
        self._auto_select_defaults()

    def _add_factor(self):
        curr = self.list_available.currentItem()
        if curr:
            name = curr.text()
            # Check not already selected
            existing = [self.list_selected_x.item(i).text() for i in range(self.list_selected_x.count())]
            if name not in existing:
                self.list_selected_x.addItem(name)

    def _remove_factor(self):
        curr = self.list_selected_x.currentRow()
        if curr >= 0:
            self.list_selected_x.takeItem(curr)

    def _auto_select_defaults(self):
        col_names = [c.name for c in self.columns]
        for name in col_names:
            n_lower = name.lower()
            if any(k in n_lower for k in ("part", "sample", "item", "batch", "operator", "tech", "user", "machine", "line")):
                self.list_selected_x.addItem(name)

    def _run_analysis(self):
        if self.combo_y.currentIndex() < 0:
            QMessageBox.warning(self, "Input Required", "Please select a response measurement column.")
            return

        y_col_name = self.combo_y.currentText()
        x_names = [self.list_selected_x.item(i).text() for i in range(self.list_selected_x.count())]
        if not x_names:
            QMessageBox.warning(self, "Input Required", "Please specify at least one grouping factor (X).")
            return

        # Fetch columns from worksheet
        name_to_col = {c.name: c for c in self.columns}
        y_col = name_to_col.get(y_col_name)
        if not y_col:
            return

        x_groupings = []
        for xn in x_names:
            col = name_to_col.get(xn)
            if col:
                x_groupings.append((xn, col.values))

        lsl = None
        usl = None
        if self.edit_lsl.text().strip():
            try:
                lsl = float(self.edit_lsl.text().strip())
            except ValueError:
                pass
        if self.edit_usl.text().strip():
            try:
                usl = float(self.edit_usl.text().strip())
            except ValueError:
                pass

        try:
            result = calculate_variability_analysis(
                y_values=y_col.values,
                x_groupings=x_groupings,
                lsl=lsl,
                usl=usl,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Variability Analysis Error", str(exc))
            return

        # Launch platform widget
        title = f"{y_col_name} by {' * '.join(x_names)}"
        widget = VariabilityPlatformWidget(result, title=title, parent=self.main_window)
        widget.show()

        # Log session summary
        if hasattr(self.main_window, "show_session_message"):
            self.main_window.show_session_message(
                f"[Variability / Gauge Analysis: {title} | Observations: {result['n']} | Pooled S: {result['std_repeatability']:.4f}]"
            )

        self.accept()
