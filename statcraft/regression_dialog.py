"""Minitab 22-parity Fit Regression Model Dialog.

Supports Response, Continuous Predictors, Options, Graphs (4-in-1), Results, and Storage.
"""
import copy
from typing import Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QDialogButtonBox, QComboBox, QCheckBox, QDoubleSpinBox
)
from .variable_dialogs import ProcedureDialog, format_variable_reference, format_variable_list


def default_regression_options() -> dict[str, Any]:
    return {
        "confidence": 0.95,
        "graphs": "four",  # 'four', 'fits', 'order', 'normal', 'histogram', 'none'
        "results": {
            "equation": True,
            "summary": True,
            "anova": True,
            "unusual": True,
        },
        "storage": {
            "fits": False,
            "residuals": False,
            "standardized_residuals": False,
            "leverages": False,
        }
    }


class RegressionOptionsDialog(QDialog):
    """Subdialog for Regression Options (Confidence level)."""

    def __init__(self, parent: QDialog, options: dict[str, Any]):
        super().__init__(parent)
        self.setWindowTitle("Regression: Options")
        self.setMinimumSize(360, 180)
        self.setSizeGripEnabled(True)
        self.options = copy.deepcopy(options)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Confidence level for all intervals:"))

        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.99)
        self.spin_conf.setDecimals(2)
        self.spin_conf.setSuffix(" %")
        self.spin_conf.setValue(self.options.get("confidence", 0.95) * 100.0)
        layout.addWidget(self.spin_conf)

        layout.addStretch()
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        footer.accepted.connect(self.validate)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)

    def validate(self):
        self.options["confidence"] = self.spin_conf.value() / 100.0
        self.accept()


class RegressionGraphsDialog(QDialog):
    """Subdialog for Regression Residual Plots (4-in-1, individual)."""

    def __init__(self, parent: QDialog, options: dict[str, Any]):
        super().__init__(parent)
        self.setWindowTitle("Regression: Graphs")
        self.setMinimumSize(400, 220)
        self.setSizeGripEnabled(True)
        self.options = copy.deepcopy(options)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Residual plots for model diagnostics:"))

        self.combo_graphs = QComboBox()
        self.graph_choices = [
            ("Four in one (Normal, Fits, Histogram, Order)", "four"),
            ("Residuals versus fits", "fits"),
            ("Residuals versus order", "order"),
            ("Normal probability plot of residuals", "normal"),
            ("Histogram of residuals", "histogram"),
            ("None", "none"),
        ]
        for label, val in self.graph_choices:
            self.combo_graphs.addItem(label, val)

        current = self.options.get("graphs", "four")
        idx = next((i for i, (_, val) in enumerate(self.graph_choices) if val == current), 0)
        self.combo_graphs.setCurrentIndex(idx)
        layout.addWidget(self.combo_graphs)

        note = QLabel("The 'Four in one' plot combines all four diagnostic graphs into a single view under the Graph tab.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #64748b; font-size: 8.5pt;")
        layout.addWidget(note)

        layout.addStretch()
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        footer.accepted.connect(self.validate)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)

    def validate(self):
        self.options["graphs"] = self.combo_graphs.currentData()
        self.accept()


class RegressionResultsDialog(QDialog):
    """Subdialog for Regression Results Display."""

    def __init__(self, parent: QDialog, options: dict[str, Any]):
        super().__init__(parent)
        self.setWindowTitle("Regression: Results")
        self.setMinimumSize(380, 240)
        self.setSizeGripEnabled(True)
        self.options = copy.deepcopy(options)
        res = self.options.get("results", {})

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Display of Results in Report:"))

        self.chk_eq = QCheckBox("Regression equation")
        self.chk_eq.setChecked(res.get("equation", True))
        layout.addWidget(self.chk_eq)

        self.chk_sum = QCheckBox("Model summary (S, R-sq, R-sq(adj), R-sq(pred), PRESS)")
        self.chk_sum.setChecked(res.get("summary", True))
        layout.addWidget(self.chk_sum)

        self.chk_anova = QCheckBox("Analysis of variance (ANOVA)")
        self.chk_anova.setChecked(res.get("anova", True))
        layout.addWidget(self.chk_anova)

        self.chk_unusual = QCheckBox("Fits and diagnostics for unusual observations (R and X)")
        self.chk_unusual.setChecked(res.get("unusual", True))
        layout.addWidget(self.chk_unusual)

        layout.addStretch()
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        footer.accepted.connect(self.validate)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)

    def validate(self):
        self.options["results"] = {
            "equation": self.chk_eq.isChecked(),
            "summary": self.chk_sum.isChecked(),
            "anova": self.chk_anova.isChecked(),
            "unusual": self.chk_unusual.isChecked(),
        }
        self.accept()


class RegressionStorageDialog(QDialog):
    """Subdialog for storing regression fitted values, residuals, and leverages in the worksheet."""

    def __init__(self, parent: QDialog, options: dict[str, Any]):
        super().__init__(parent)
        self.setWindowTitle("Regression: Storage")
        self.setMinimumSize(360, 230)
        self.setSizeGripEnabled(True)
        self.options = copy.deepcopy(options)
        st = self.options.get("storage", {})

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Store in worksheet columns:"))

        self.chk_fits = QCheckBox("Fits (Fitted Values)")
        self.chk_fits.setChecked(st.get("fits", False))
        layout.addWidget(self.chk_fits)

        self.chk_residuals = QCheckBox("Residuals")
        self.chk_residuals.setChecked(st.get("residuals", False))
        layout.addWidget(self.chk_residuals)

        self.chk_std_resids = QCheckBox("Standardized Residuals")
        self.chk_std_resids.setChecked(st.get("standardized_residuals", False))
        layout.addWidget(self.chk_std_resids)

        self.chk_leverages = QCheckBox("Leverages (Hi)")
        self.chk_leverages.setChecked(st.get("leverages", False))
        layout.addWidget(self.chk_leverages)

        layout.addStretch()
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        footer.accepted.connect(self.validate)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)

    def validate(self):
        self.options["storage"] = {
            "fits": self.chk_fits.isChecked(),
            "residuals": self.chk_residuals.isChecked(),
            "standardized_residuals": self.chk_std_resids.isChecked(),
            "leverages": self.chk_leverages.isChecked(),
        }
        self.accept()


class RegressionModelTermsDialog(QDialog):
    """Subdialog for Regression Model Terms (main effects, 2-way interactions, quadratic X*X)."""

    def __init__(self, parent: QDialog, cont_names: list[str], cat_names: list[str], selected_higher: set[tuple[int, int]]):
        super().__init__(parent)
        self.setWindowTitle("Regression: Model")
        self.setMinimumSize(420, 320)
        self.setSizeGripEnabled(True)
        self.cont_count = len(cont_names)
        self.all_names = list(cont_names) + list(cat_names)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Main effects for all selected predictors are included automatically."))
        layout.addWidget(QLabel("Optional higher-order terms (interactions & continuous quadratics):"))

        from PySide6.QtWidgets import QScrollArea, QWidget
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        vbox = QVBoxLayout(inner)
        self.term_checks: dict[tuple[int, int], QCheckBox] = {}
        n_total = len(self.all_names)
        for i in range(n_total):
            # Continuous quadratic i*i
            if i < self.cont_count:
                pair = (i, i)
                chk = QCheckBox(f"{self.all_names[i]}*{self.all_names[i]}  (quadratic)")
                chk.setChecked(pair in selected_higher)
                self.term_checks[pair] = chk
                vbox.addWidget(chk)
            for j in range(i + 1, n_total):
                pair = (i, j)
                chk = QCheckBox(f"{self.all_names[i]}*{self.all_names[j]}  (interaction)")
                chk.setChecked(pair in selected_higher)
                self.term_checks[pair] = chk
                vbox.addWidget(chk)
        if not self.term_checks:
            vbox.addWidget(QLabel("Add at least 1 continuous predictor (for X*X) or 2 predictors (for A*B)."))
        vbox.addStretch(1)
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        preset_row = QHBoxLayout()
        btn_linear = QPushButton("Linear Only")
        btn_inter = QPushButton("2-Way Interactions")
        btn_full = QPushButton("Full 2nd Order")
        btn_linear.clicked.connect(lambda: self._apply_preset("linear"))
        btn_inter.clicked.connect(lambda: self._apply_preset("interactions"))
        btn_full.clicked.connect(lambda: self._apply_preset("full"))
        preset_row.addWidget(btn_linear)
        preset_row.addWidget(btn_inter)
        preset_row.addWidget(btn_full)
        preset_row.addStretch(1)
        layout.addLayout(preset_row)

        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        footer.accepted.connect(self.accept)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)

    def _apply_preset(self, preset: str):
        for pair, chk in self.term_checks.items():
            is_quad = pair[0] == pair[1]
            if preset == "linear":
                chk.setChecked(False)
            elif preset == "interactions":
                chk.setChecked(not is_quad)
            elif preset == "full":
                chk.setChecked(True)

    def selected_pairs(self) -> list[tuple[int, int]]:
        return sorted(pair for pair, chk in self.term_checks.items() if chk.isChecked())


class FitRegressionModelDialog(ProcedureDialog):
    """Minitab-standard Fit Regression Model procedure dialog."""

    def __init__(self, window):
        specs = [
            dict(key="response_index", label="Response:", kinds=("number",)),
            dict(key="predictor_indices", label="Continuous predictors:", multiple=True, optional=True, minimum=0, kinds=("number",)),
            dict(key="categorical_indices", label="Categorical predictors:", multiple=True, optional=True, minimum=0, kinds=("number", "text")),
        ]
        super().__init__(
            window,
            "Fit Regression Model",
            window.presenter.worksheet,
            specs,
            (),
            "Fit OLS regression with continuous or categorical predictors, interactions, and quadratic terms."
        )
        self.window = window
        self.options = default_regression_options()
        self.higher_terms: list[tuple[int, int]] = []
        self.entry = None

        # Add subdialog buttons grid
        grid = QGridLayout()
        self.btn_model = QPushButton("Model…")
        self.btn_model.clicked.connect(self.open_model)
        grid.addWidget(self.btn_model, 0, 0)

        self.btn_options = QPushButton("Options…")
        self.btn_options.clicked.connect(self.open_options)
        grid.addWidget(self.btn_options, 0, 1)

        self.btn_graphs = QPushButton("Graphs…")
        self.btn_graphs.clicked.connect(self.open_graphs)
        grid.addWidget(self.btn_graphs, 0, 2)

        self.btn_results = QPushButton("Results…")
        self.btn_results.clicked.connect(self.open_results)
        grid.addWidget(self.btn_results, 0, 3)

        self.btn_storage = QPushButton("Storage…")
        self.btn_storage.clicked.connect(self.open_storage)
        grid.addWidget(self.btn_storage, 0, 4)

        self.layout().insertLayout(self.layout().count() - 2, grid)
        self.restore_previous()

    def _save_dialog_state(self):
        super()._save_dialog_state()
        from .variable_dialogs import save_dialog_state
        save_dialog_state(self.worksheet, "FitRegressionModelDialog_extras", {
            "options": self.options,
            "higher_terms": [list(t) for t in self.higher_terms],
        })

    def restore_previous(self):
        from .variable_dialogs import load_dialog_state
        saved = load_dialog_state(self.worksheet, "FitRegressionModelDialog_extras")
        if saved and isinstance(saved.get("options"), dict):
            merged = copy.deepcopy(default_regression_options())
            merged.update(saved["options"])
            self.options = merged
        if saved and isinstance(saved.get("higher_terms"), list):
            self.higher_terms = [tuple(t) for t in saved["higher_terms"] if isinstance(t, (list, tuple)) and len(t) == 2]
        p = self.window.presenter
        worksheet_id = p.native_project.worksheet_ids[p.native_project.active_index] if getattr(p, 'native_project', None) else None
        for entry in reversed(getattr(p, 'history', [])):
            if entry.get("source_unavailable") or entry.get("recipe", {}).get("action") != "multiple_regression":
                continue
            if entry.get("worksheet_id") != worksheet_id or entry.get("worksheet_name") != p.worksheet.name:
                continue
            v = entry["recipe"]["parameters"]
            try:
                self.controls["response_index"].setText(format_variable_reference(v["response_index"], self.worksheet))
                self.controls["predictor_indices"].setText(format_variable_list(v.get("predictor_indices") or (), self.worksheet))
                if v.get("categorical_indices"):
                    self.controls["categorical_indices"].setText(format_variable_list(v["categorical_indices"], self.worksheet))
                if "confidence" in v:
                    self.options["confidence"] = float(v["confidence"])
            except Exception:
                continue
            break

    def _current_predictor_lists(self):
        from .variable_dialogs import resolve_variables
        raw_cont = self.controls["predictor_indices"].text().strip()
        raw_cat = self.controls["categorical_indices"].text().strip()
        cont = resolve_variables(raw_cont, self.worksheet, ("number",)) if raw_cont else []
        cat = resolve_variables(raw_cat, self.worksheet, ("number", "text")) if raw_cat else []
        return cont, cat

    def open_model(self):
        try:
            cont, cat = self._current_predictor_lists()
        except ValueError as exc:
            self.error.setText(str(exc))
            self.error.setVisible(True)
            return
        if not cont and not cat:
            self.error.setText("Select at least one continuous or categorical predictor first.")
            self.error.setVisible(True)
            return
        self.error.setVisible(False)
        cont_names = [self.worksheet.columns[i].name for i in cont]
        cat_names = [self.worksheet.columns[i].name for i in cat]
        dlg = RegressionModelTermsDialog(self, cont_names, cat_names, set(self.higher_terms))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.higher_terms = dlg.selected_pairs()
        dlg.deleteLater()

    def open_options(self):
        dlg = RegressionOptionsDialog(self, self.options)
        if dlg.exec():
            self.options = dlg.options
        dlg.deleteLater()

    def open_graphs(self):
        dlg = RegressionGraphsDialog(self, self.options)
        if dlg.exec():
            self.options = dlg.options
        dlg.deleteLater()

    def open_results(self):
        dlg = RegressionResultsDialog(self, self.options)
        if dlg.exec():
            self.options = dlg.options
        dlg.deleteLater()

    def open_storage(self):
        dlg = RegressionStorageDialog(self, self.options)
        if dlg.exec():
            self.options = dlg.options
        dlg.deleteLater()

    def validate(self):
        try:
            v = self.values()
            resp_idx = v["response_index"]
            pred_indices = list(v.get("predictor_indices") or ())
            cat_indices = list(v.get("categorical_indices") or ())
            all_pred = pred_indices + cat_indices
            if resp_idx in all_pred:
                raise ValueError("Response variable cannot also be a predictor.")
            if len(set(all_pred)) != len(all_pred):
                raise ValueError("Choose distinct columns for continuous and categorical predictors.")
            if not all_pred:
                raise ValueError("Choose at least one continuous or categorical predictor.")

            n_total = len(all_pred)
            n_cont = len(pred_indices)
            valid_higher = [
                list(pair)
                for pair in self.higher_terms
                if 0 <= pair[0] < n_total
                and 0 <= pair[1] < n_total
                and (pair[0] != pair[1] or pair[0] < n_cont)
            ]
            model_terms = [[i] for i in range(n_total)] + valid_higher if valid_higher else None

            conf = self.options.get("confidence", 0.95)
            self.entry = self.window.presenter.multiple_regression(
                resp_idx,
                pred_indices,
                confidence=conf,
                categorical_indices=cat_indices or None,
                model_terms=model_terms,
            )

            # Apply graphs & results options
            graphs_mode = self.options.get("graphs", "four")
            res_opts = copy.deepcopy(self.options.get("results", {"equation": True, "summary": True, "anova": True, "unusual": True}))
            if "result" in self.entry and isinstance(self.entry["result"], dict):
                self.entry["result"]["options"] = {"graphs": graphs_mode, "results": res_opts}
                self.entry["result"]["graphs"] = graphs_mode
            self.entry["graphs"] = graphs_mode

            # Handle storage
            st = self.options.get("storage", {})
            if any(st.values()):
                self._store_columns(self.entry.get("result", {}), st)

            self.window.refresh()
            self.window.show_result(self.entry)
            self.error.setVisible(False)
            self.parameters = v
            if hasattr(self, "_save_dialog_state"):
                self._save_dialog_state()
        except Exception as exc:
            self.error.setText(str(exc))
            self.error.setVisible(True)
            return

        self.accept()

    def _store_columns(self, result: dict[str, Any], storage: dict[str, bool]):
        from .app import Column
        ws = self.window.presenter.worksheet
        indices = result.get("row_indices", list(range(result.get("count", 0))))
        total_rows = len(ws.columns[0].values) if ws.columns else result.get("count", 0)

        def make_full_col(values_subset):
            full = [None] * total_rows
            for orig_idx, val in zip(indices, values_subset):
                if orig_idx < total_rows:
                    full[orig_idx] = float(val) if val is not None else None
            return full

        def unique_col_name(base):
            existing = {c.name.upper() for c in ws.columns}
            idx = 1
            while f"{base}{idx}".upper() in existing:
                idx += 1
            return f"{base}{idx}"

        if storage.get("fits") and "fitted" in result:
            ws.columns.append(Column(name=unique_col_name("FITS"), kind="number", values=make_full_col(result["fitted"])))
        if storage.get("residuals") and "residuals" in result:
            ws.columns.append(Column(name=unique_col_name("RESI"), kind="number", values=make_full_col(result["residuals"])))
        if storage.get("standardized_residuals") and "standardized_residuals" in result:
            ws.columns.append(Column(name=unique_col_name("SRES"), kind="number", values=make_full_col(result["standardized_residuals"])))
        if storage.get("leverages") and "leverages" in result:
            ws.columns.append(Column(name=unique_col_name("HI"), kind="number", values=make_full_col(result["leverages"])))
