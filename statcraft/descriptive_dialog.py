"""Display Descriptive Statistics dialog with Variables, By variables, Statistics..., and Graphs... subdialogs."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from .variable_dialogs import (
    ProcedureDialog,
    load_dialog_state,
    resolve_variables,
    save_dialog_state,
)


STATISTICS_CHOICES = [
    ("mean", "Mean", True),
    ("standard_error", "SE of mean", True),
    ("sample_stdev", "Standard deviation", True),
    ("sample_variance", "Variance", False),
    ("coef_var", "Coefficient of variation", False),
    ("trimmed_mean", "Trimmed mean (5%)", False),
    ("sum", "Sum", False),
    ("minimum", "Minimum", True),
    ("q1", "First quartile (Q1)", True),
    ("median", "Median", True),
    ("q3", "Third quartile (Q3)", True),
    ("maximum", "Maximum", True),
    ("range", "Range", False),
    ("iqr", "Interquartile range (IQR)", False),
    ("mode", "Mode", False),
    ("skewness", "Skewness", False),
    ("kurtosis", "Kurtosis", False),
    ("count", "N nonmissing", True),
    ("missing", "N missing", True),
    ("n_total", "N total", False),
]

DEFAULT_STATISTICS = [key for key, _, checked in STATISTICS_CHOICES if checked]

GRAPH_CHOICES = [
    ("histogram", "Histogram of data"),
    ("histogram_normal", "Histogram of data, with normal curve"),
    ("individual_value", "Individual value plot"),
    ("boxplot", "Boxplot of data"),
]


class _DescriptiveStatisticsSubDialog(QDialog):
    def __init__(self, parent, selected_keys: list[str]):
        super().__init__(parent)
        self.setWindowTitle("Display Descriptive Statistics: Statistics")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        box = QGroupBox("Statistics")
        grid = QGridLayout(box)
        self.checks = {}
        active = set(selected_keys)
        for idx, (key, label, _) in enumerate(STATISTICS_CHOICES):
            chk = QCheckBox(label)
            chk.setChecked(key in active)
            self.checks[key] = chk
            grid.addWidget(chk, idx % 10, idx // 10)
        layout.addWidget(box)

        preset_row = QHBoxLayout()
        btn_default = QPushButton("Default")
        btn_all = QPushButton("Select All")
        btn_none = QPushButton("Clear All")
        btn_default.clicked.connect(lambda: self._apply(DEFAULT_STATISTICS))
        btn_all.clicked.connect(lambda: self._apply([k for k, _, _ in STATISTICS_CHOICES]))
        btn_none.clicked.connect(lambda: self._apply([]))
        preset_row.addWidget(btn_default)
        preset_row.addWidget(btn_all)
        preset_row.addWidget(btn_none)
        preset_row.addStretch(1)
        layout.addLayout(preset_row)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _apply(self, keys):
        keyset = set(keys)
        for k, chk in self.checks.items():
            chk.setChecked(k in keyset)

    def selected_statistics(self) -> list[str]:
        return [k for k, _, _ in STATISTICS_CHOICES if self.checks[k].isChecked()]


class _DescriptiveGraphsSubDialog(QDialog):
    def __init__(self, parent, graph_opts: dict[str, bool]):
        super().__init__(parent)
        self.setWindowTitle("Display Descriptive Statistics: Graphs")
        self.setMinimumWidth(340)
        layout = QVBoxLayout(self)
        box = QGroupBox("Graphs")
        vbox = QVBoxLayout(box)
        self.checks = {}
        for key, label in GRAPH_CHOICES:
            chk = QCheckBox(label)
            chk.setChecked(bool(graph_opts.get(key, False)))
            self.checks[key] = chk
            vbox.addWidget(chk)
        layout.addWidget(box)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def graph_options(self) -> dict[str, bool]:
        return {k: chk.isChecked() for k, chk in self.checks.items()}


class DisplayDescriptiveDialog(ProcedureDialog):
    """Minitab-style Stat > Basic Statistics > Display Descriptive Statistics dialog."""

    _STATE_KEY = "DisplayDescriptiveDialog"

    def __init__(self, worksheet, parent=None):
        self._selected_stats = list(DEFAULT_STATISTICS)
        self._graph_opts = {k: False for k, _ in GRAPH_CHOICES}
        super().__init__(
            parent,
            "Display Descriptive Statistics",
            worksheet,
            [
                {
                    "key": "indices",
                    "label": "Variables",
                    "multiple": True,
                    "minimum": 1,
                    "kinds": ("number",),
                },
                {
                    "key": "by_indices",
                    "label": "By variables (optional)",
                    "multiple": True,
                    "optional": True,
                    "kinds": ("number", "text", "date"),
                },
            ],
            [],
            "Select numeric variables, optional grouping columns, and customize Statistics… or Graphs….",
        )
        saved = load_dialog_state(worksheet, self._STATE_KEY)
        if isinstance(saved, dict):
            if isinstance(saved.get("statistics"), list) and saved["statistics"]:
                self._selected_stats = list(saved["statistics"])
            if isinstance(saved.get("graphs"), dict):
                self._graph_opts.update(saved["graphs"])
            for key in ("indices", "by_indices"):
                if isinstance(saved.get(key), str) and key in self.controls:
                    self.controls[key].setText(saved[key])

        sub_row = QHBoxLayout()
        self.stats_btn = QPushButton("Statistics…")
        self.graphs_btn = QPushButton("Graphs…")
        self.stats_btn.clicked.connect(self._open_statistics)
        self.graphs_btn.clicked.connect(self._open_graphs)
        sub_row.addWidget(self.stats_btn)
        sub_row.addWidget(self.graphs_btn)
        sub_row.addStretch(1)
        # Insert subdialog button row right above the main OK/Cancel button box.
        main_layout = self.layout()
        if main_layout is not None:
            main_layout.insertLayout(max(0, main_layout.count() - 1), sub_row)

    def _open_statistics(self):
        dlg = _DescriptiveStatisticsSubDialog(self, self._selected_stats)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            chosen = dlg.selected_statistics()
            self._selected_stats = chosen if chosen else list(DEFAULT_STATISTICS)

    def _open_graphs(self):
        dlg = _DescriptiveGraphsSubDialog(self, self._graph_opts)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._graph_opts = dlg.graph_options()

    def get_parameters(self) -> dict:
        indices = resolve_variables(
            self.controls["indices"].text(), self.worksheet, ("number",)
        )
        raw_by = self.controls["by_indices"].text().strip()
        by_indices = (
            resolve_variables(raw_by, self.worksheet, ("number", "text", "date"))
            if raw_by
            else []
        )
        save_dialog_state(
            self.worksheet,
            self._STATE_KEY,
            {
                "indices": self.controls["indices"].text(),
                "by_indices": self.controls["by_indices"].text(),
                "statistics": list(self._selected_stats),
                "graphs": dict(self._graph_opts),
            },
        )
        return {
            "indices": indices,
            "by_indices": by_indices or None,
            "statistics": list(self._selected_stats),
            "graphs": dict(self._graph_opts),
        }
