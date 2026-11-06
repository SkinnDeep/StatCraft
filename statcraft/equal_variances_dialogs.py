"""Native StatCraft Dialogs for Test for Equal Variances (VARTEST.MDF + child forms)."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QGroupBox,
    QDialogButtonBox,
    QStackedWidget,
    QWidget,
)
from .variable_dialogs import format_variable_reference, resolve_variables
from .equal_variances_engine import equal_variances_settings


class TestEqualVariancesOptionsDialog(QDialog):
    """Subdialog matching VARTESTOPTIONS.MDF."""

    def __init__(self, current_options, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(True)
        self.setWindowTitle("Test for Equal Variances: Options")
        self.setMinimumWidth(380)
        self.options = dict(current_options)

        layout = QVBoxLayout(self)

        form = QGridLayout()
        form.addWidget(QLabel("Confidence level:"), 0, 0)
        self.conf_edit = QLineEdit(str(self.options.get("confidence_level", 95.0)))
        form.addWidget(self.conf_edit, 0, 1)
        layout.addLayout(form)

        self.normal_cb = QCheckBox("Use test based on normal distribution")
        self.normal_cb.setChecked(bool(self.options.get("use_normal_distribution", False)))
        layout.addWidget(self.normal_cb)

        layout.addSpacing(15)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        try:
            val = float(self.conf_edit.text().strip())
            if not (0 < val < 100):
                raise ValueError
        except Exception:
            return
        self.options["confidence_level"] = val
        self.options["use_normal_distribution"] = self.normal_cb.isChecked()
        self.accept()


class TestEqualVariancesGraphsDialog(QDialog):
    """Subdialog matching VARTESTGRAPHS.MDF."""

    def __init__(self, current_graphs, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(True)
        self.setWindowTitle("Test for Equal Variances: Graphs")
        self.setMinimumWidth(340)
        self.graphs = dict(current_graphs)

        layout = QVBoxLayout(self)

        self.summary_cb = QCheckBox("Summary plot")
        self.summary_cb.setChecked(bool(self.graphs.get("summary_plot", True)))
        layout.addWidget(self.summary_cb)

        self.ivp_cb = QCheckBox("Individual value plot")
        self.ivp_cb.setChecked(bool(self.graphs.get("individual_value_plot", False)))
        layout.addWidget(self.ivp_cb)

        self.boxplot_cb = QCheckBox("Boxplot")
        self.boxplot_cb.setChecked(bool(self.graphs.get("boxplot", False)))
        layout.addWidget(self.boxplot_cb)

        layout.addSpacing(15)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        self.graphs["summary_plot"] = self.summary_cb.isChecked()
        self.graphs["individual_value_plot"] = self.ivp_cb.isChecked()
        self.graphs["boxplot"] = self.boxplot_cb.isChecked()
        self.accept()


class TestEqualVariancesResultsDialog(QDialog):
    """Subdialog matching VARTESTRESULTS.MDF."""

    def __init__(self, current_results, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(True)
        self.setWindowTitle("Test for Equal Variances: Results")
        self.setMinimumWidth(340)
        self.results = dict(current_results)

        layout = QVBoxLayout(self)

        self.method_cb = QCheckBox("Method")
        self.method_cb.setChecked(bool(self.results.get("method", True)))
        layout.addWidget(self.method_cb)

        self.ci_cb = QCheckBox("Confidence intervals")
        self.ci_cb.setChecked(bool(self.results.get("confidence_intervals", True)))
        layout.addWidget(self.ci_cb)

        self.tests_cb = QCheckBox("Tests")
        self.tests_cb.setChecked(bool(self.results.get("tests", True)))
        layout.addWidget(self.tests_cb)

        layout.addSpacing(15)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        self.results["method"] = self.method_cb.isChecked()
        self.results["confidence_intervals"] = self.ci_cb.isChecked()
        self.results["tests"] = self.tests_cb.isChecked()
        self.accept()


class TestEqualVariancesStorageDialog(QDialog):
    """Subdialog matching VARTESTSTORAGE.MDF."""

    def __init__(self, current_storage, use_normal=False, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(True)
        self.setWindowTitle("Test for Equal Variances: Storage")
        self.setMinimumWidth(380)
        self.storage = dict(current_storage)
        self.use_normal = use_normal

        layout = QVBoxLayout(self)

        self.stdev_cb = QCheckBox("Standard deviations")
        self.stdev_cb.setChecked(bool(self.storage.get("stdevs", False)))
        layout.addWidget(self.stdev_cb)

        self.var_cb = QCheckBox("Variances")
        self.var_cb.setChecked(bool(self.storage.get("variances", False)))
        layout.addWidget(self.var_cb)

        self.bonf_cb = QCheckBox("Bonferroni confidence intervals for standard deviations")
        self.bonf_cb.setChecked(bool(self.storage.get("bonferroni_ci", False)))
        layout.addWidget(self.bonf_cb)

        self.mci_cb = QCheckBox("Multiple comparison intervals")
        self.mci_cb.setChecked(bool(self.storage.get("mci", False)))
        if self.use_normal:
            self.mci_cb.setEnabled(False)
            self.mci_cb.setChecked(False)
        layout.addWidget(self.mci_cb)

        layout.addSpacing(15)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        self.storage["stdevs"] = self.stdev_cb.isChecked()
        self.storage["variances"] = self.var_cb.isChecked()
        self.storage["bonferroni_ci"] = self.bonf_cb.isChecked()
        self.storage["mci"] = False if self.use_normal else self.mci_cb.isChecked()
        self.accept()


class TestEqualVariancesDialog(QDialog):
    """Main dialog matching VARTEST.MDF."""

    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(True)
        self.worksheet = worksheet
        self.setWindowTitle("Test for Equal Variances")
        self.setMinimumSize(560, 360)

        self.options = equal_variances_settings()
        self.result_payload = None

        layout = QHBoxLayout(self)

        # Left Column: Variables List
        left_box = QVBoxLayout()
        left_box.addWidget(QLabel("Variables:"))
        self.var_list = QListWidget()
        for idx, col in enumerate(worksheet.columns):
            item = QListWidgetItem(format_variable_reference(idx, worksheet))
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.var_list.addItem(item)
        left_box.addWidget(self.var_list)

        self.select_btn = QPushButton("Select")
        self.select_btn.clicked.connect(self._on_select)
        left_box.addWidget(self.select_btn)
        layout.addLayout(left_box, 1)

        # Middle Column: Controls & Data arrangement
        mid_box = QVBoxLayout()

        self.combo_data = QComboBox()
        self.combo_data.addItem("Response data are in one column for all factor levels", 0)
        self.combo_data.addItem("Response data are in a separate column for each factor level", 1)
        self.combo_data.currentIndexChanged.connect(self._on_data_arrangement_changed)
        mid_box.addWidget(self.combo_data)

        self.stack = QStackedWidget()

        # Page 0: Stacked
        p0 = QWidget()
        p0_layout = QVBoxLayout(p0)
        p0_layout.addWidget(QLabel("Response:"))
        self.resp_edit = QLineEdit()
        self.resp_edit.setPlaceholderText("e.g. C1")
        p0_layout.addWidget(self.resp_edit)

        p0_layout.addWidget(QLabel("Factors (1 to 9):"))
        self.factors_edit = QLineEdit()
        self.factors_edit.setPlaceholderText("e.g. C2 or C2 C3")
        p0_layout.addWidget(self.factors_edit)
        p0_layout.addStretch()
        self.stack.addWidget(p0)

        # Page 1: Unstacked
        p1 = QWidget()
        p1_layout = QVBoxLayout(p1)
        p1_layout.addWidget(QLabel("Responses (2 or more columns):"))
        self.unstacked_edit = QLineEdit()
        self.unstacked_edit.setPlaceholderText("e.g. C1 C2 C3")
        p1_layout.addWidget(self.unstacked_edit)
        p1_layout.addStretch()
        self.stack.addWidget(p1)

        mid_box.addWidget(self.stack)

        self.err_label = QLabel("")
        self.err_label.setStyleSheet("color: red;")
        mid_box.addWidget(self.err_label)

        # Bottom buttons
        btn_box = QHBoxLayout()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._on_ok)
        btn_box.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.cancel_btn)

        self.help_btn = QPushButton("Help")
        btn_box.addWidget(self.help_btn)

        mid_box.addLayout(btn_box)
        layout.addLayout(mid_box, 2)

        # Right Column: Subdialog Buttons
        right_box = QVBoxLayout()
        self.opt_btn = QPushButton("Options...")
        self.opt_btn.clicked.connect(self._open_options)
        right_box.addWidget(self.opt_btn)

        self.graph_btn = QPushButton("Graphs...")
        self.graph_btn.clicked.connect(self._open_graphs)
        right_box.addWidget(self.graph_btn)

        self.results_btn = QPushButton("Results...")
        self.results_btn.clicked.connect(self._open_results)
        right_box.addWidget(self.results_btn)

        self.storage_btn = QPushButton("Storage...")
        self.storage_btn.clicked.connect(self._open_storage)
        right_box.addWidget(self.storage_btn)

        right_box.addStretch()
        layout.addLayout(right_box, 1)

        self.var_list.itemDoubleClicked.connect(self._on_select)
        self._active_edit = self.resp_edit
        self.resp_edit.installEventFilter(self)
        self.factors_edit.installEventFilter(self)
        self.unstacked_edit.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn:
            self._active_edit = obj
        return super().eventFilter(obj, event)

    def _on_data_arrangement_changed(self, idx):
        self.stack.setCurrentIndex(idx)
        self._active_edit = self.unstacked_edit if idx == 1 else self.resp_edit

    def _on_select(self):
        item = self.var_list.currentItem()
        if not item or not hasattr(self, "_active_edit"):
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        cname = f"C{idx+1}"
        cur = self._active_edit.text().strip()
        if self._active_edit is self.resp_edit:
            self._active_edit.setText(cname)
        else:
            self._active_edit.setText(f"{cur} {cname}".strip())

    def _open_options(self):
        dlg = TestEqualVariancesOptionsDialog(self.options, self)
        if dlg.exec():
            self.options = dlg.options

    def _open_graphs(self):
        dlg = TestEqualVariancesGraphsDialog(self.options["graphs"], self)
        if dlg.exec():
            self.options["graphs"] = dlg.graphs

    def _open_results(self):
        dlg = TestEqualVariancesResultsDialog(self.options["results"], self)
        if dlg.exec():
            self.options["results"] = dlg.results

    def _open_storage(self):
        dlg = TestEqualVariancesStorageDialog(self.options["storage"], self.options.get("use_normal_distribution", False), self)
        if dlg.exec():
            self.options["storage"] = dlg.storage

    def _on_ok(self):
        self.err_label.setText("")
        is_stacked = (self.combo_data.currentIndex() == 0)
        try:
            if is_stacked:
                resp_text = self.resp_edit.text().strip()
                if not resp_text:
                    raise ValueError("Choose a numeric response column.")
                resp_indices = resolve_variables(resp_text, self.worksheet, ("number",))
                if len(resp_indices) != 1:
                    raise ValueError("Select exactly one numeric response column.")
                resp_idx = resp_indices[0]

                factors_text = self.factors_edit.text().strip()
                if not factors_text:
                    raise ValueError("Select 1 to 9 factor columns.")
                factor_indices = resolve_variables(factors_text, self.worksheet, ("number", "text", "date"))
                if not (1 <= len(factor_indices) <= 9):
                    raise ValueError("Select between 1 and 9 factor columns.")
                if resp_idx in factor_indices:
                    raise ValueError("Response column cannot also be a factor column.")

                self.result_payload = {
                    "stacked": True,
                    "response_index": resp_idx,
                    "factor_indices": factor_indices,
                    "options": self.options,
                }
            else:
                resp_text = self.unstacked_edit.text().strip()
                if not resp_text:
                    raise ValueError("Select at least two numeric response columns.")
                resp_indices = resolve_variables(resp_text, self.worksheet, ("number",))
                if len(resp_indices) < 2:
                    raise ValueError("Select at least two numeric response columns.")
                self.result_payload = {
                    "stacked": False,
                    "response_indices": resp_indices,
                    "options": self.options,
                }
            self.accept()
        except ValueError as exc:
            self.err_label.setText(str(exc))
