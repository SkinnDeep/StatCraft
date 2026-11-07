"""Minitab 22-parity Fitted Line Plot Dialog (Stat > Regression > Fitted Line Plot).

Supports Response (Y), Predictor (X), Model Type (Linear, Quadratic, Cubic),
Graphs (4-in-1, individual), Options (Confidence/Prediction intervals, Title), and Storage.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QRadioButton, QPushButton, QVBoxLayout
)
from .variable_dialogs import ProcedureDialog, format_variable_reference


def default_fitted_line_plot_options() -> Dict[str, Any]:
    return {
        "model_type": "linear",  # 'linear', 'quadratic', 'cubic'
        "confidence": 0.95,
        "ci": True,
        "pi": True,
        "title": "",
        "residuals_type": "regular",  # 'regular', 'standardized', 'deleted'
        "graphs": "four",  # 'four', 'fits', 'order', 'normal', 'histogram', 'none'
        "storage": {
            "fits": False,
            "residuals": False,
            "standardized_residuals": False,
            "deleted_residuals": False,
            "coefficients": False,
        },
    }


class FittedLinePlotOptionsDialog(QDialog):
    """Subdialog for Fitted Line Plot Options (CI/PI intervals and Title)."""

    def __init__(self, parent: QDialog, options: Dict[str, Any]):
        super().__init__(parent)
        self.setWindowTitle("Fitted Line Plot: Options")
        self.setMinimumSize(380, 240)
        self.setSizeGripEnabled(True)
        self.options = copy.deepcopy(options)

        layout = QVBoxLayout(self)

        grp_display = QGroupBox("Display Options")
        l_disp = QVBoxLayout(grp_display)

        self.chk_ci = QCheckBox("Display confidence interval")
        self.chk_ci.setChecked(self.options.get("ci", True))
        l_disp.addWidget(self.chk_ci)

        self.chk_pi = QCheckBox("Display prediction interval")
        self.chk_pi.setChecked(self.options.get("pi", True))
        l_disp.addWidget(self.chk_pi)

        h_conf = QHBoxLayout()
        h_conf.addWidget(QLabel("Confidence level:"))
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(50.0, 99.99)
        self.spin_conf.setDecimals(2)
        self.spin_conf.setSuffix(" %")
        self.spin_conf.setValue(self.options.get("confidence", 0.95) * 100.0)
        h_conf.addWidget(self.spin_conf)
        h_conf.addStretch()
        l_disp.addLayout(h_conf)

        layout.addWidget(grp_display)

        # Title
        h_title = QHBoxLayout()
        h_title.addWidget(QLabel("Title:"))
        self.txt_title = QLineEdit(self.options.get("title", ""))
        self.txt_title.setPlaceholderText("Default: Fitted Line Plot of Y versus X")
        h_title.addWidget(self.txt_title)
        layout.addLayout(h_title)

        layout.addStretch()
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        footer.accepted.connect(self.validate)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)

    def validate(self):
        self.options["ci"] = self.chk_ci.isChecked()
        self.options["pi"] = self.chk_pi.isChecked()
        self.options["confidence"] = self.spin_conf.value() / 100.0
        self.options["title"] = self.txt_title.text().strip()
        self.accept()


class FittedLinePlotGraphsDialog(QDialog):
    """Subdialog for Fitted Line Plot Graphs (4-in-1 vs Individual residual plots)."""

    def __init__(self, parent: QDialog, options: Dict[str, Any]):
        super().__init__(parent)
        self.setWindowTitle("Fitted Line Plot: Graphs")
        self.setMinimumSize(400, 310)
        self.setSizeGripEnabled(True)
        self.options = copy.deepcopy(options)

        layout = QVBoxLayout(self)

        # Residuals type
        grp_type = QGroupBox("Residuals for Plots")
        l_type = QHBoxLayout(grp_type)
        self.btn_grp_type = QButtonGroup(self)
        self.rdo_reg = QRadioButton("Regular")
        self.rdo_std = QRadioButton("Standardized")
        self.rdo_del = QRadioButton("Deleted")
        self.btn_grp_type.addButton(self.rdo_reg, 0)
        self.btn_grp_type.addButton(self.rdo_std, 1)
        self.btn_grp_type.addButton(self.rdo_del, 2)

        cur_rtype = self.options.get("residuals_type", "regular")
        if cur_rtype == "standardized":
            self.rdo_std.setChecked(True)
        elif cur_rtype == "deleted":
            self.rdo_del.setChecked(True)
        else:
            self.rdo_reg.setChecked(True)

        l_type.addWidget(self.rdo_reg)
        l_type.addWidget(self.rdo_std)
        l_type.addWidget(self.rdo_del)
        layout.addWidget(grp_type)

        # Residual Plots
        grp_plots = QGroupBox("Residual Plots")
        l_plots = QVBoxLayout(grp_plots)
        self.btn_grp_plots = QButtonGroup(self)
        self.rdo_four = QRadioButton("Four in one (4-in-1)")
        self.rdo_indiv = QRadioButton("Individual plots")
        self.rdo_none = QRadioButton("None")
        self.btn_grp_plots.addButton(self.rdo_four, 0)
        self.btn_grp_plots.addButton(self.rdo_indiv, 1)
        self.btn_grp_plots.addButton(self.rdo_none, 2)

        cur_g = self.options.get("graphs", "four")
        if cur_g == "four":
            self.rdo_four.setChecked(True)
        elif cur_g in ("normal", "fits", "histogram", "order"):
            self.rdo_indiv.setChecked(True)
        else:
            self.rdo_none.setChecked(True)

        l_plots.addWidget(self.rdo_four)
        l_plots.addWidget(self.rdo_indiv)

        # Individual checkboxes
        indiv_layout = QGridLayout()
        indiv_layout.setContentsMargins(20, 0, 0, 0)
        self.chk_hist = QCheckBox("Histogram of residuals")
        self.chk_norm = QCheckBox("Normal plot of residuals")
        self.chk_fits = QCheckBox("Residuals versus fits")
        self.chk_order = QCheckBox("Residuals versus order")

        self.chk_hist.setChecked(cur_g == "histogram")
        self.chk_norm.setChecked(cur_g == "normal")
        self.chk_fits.setChecked(cur_g == "fits")
        self.chk_order.setChecked(cur_g == "order")

        indiv_layout.addWidget(self.chk_hist, 0, 0)
        indiv_layout.addWidget(self.chk_norm, 0, 1)
        indiv_layout.addWidget(self.chk_fits, 1, 0)
        indiv_layout.addWidget(self.chk_order, 1, 1)
        l_plots.addLayout(indiv_layout)
        l_plots.addWidget(self.rdo_none)

        layout.addWidget(grp_plots)

        # Sync enable
        def sync_enabled():
            indiv = self.rdo_indiv.isChecked()
            for chk in (self.chk_hist, self.chk_norm, self.chk_fits, self.chk_order):
                chk.setEnabled(indiv)

        self.rdo_four.toggled.connect(sync_enabled)
        self.rdo_indiv.toggled.connect(sync_enabled)
        self.rdo_none.toggled.connect(sync_enabled)
        sync_enabled()

        layout.addStretch()
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        footer.accepted.connect(self.validate)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)

    def validate(self):
        # Residual type
        if self.rdo_std.isChecked():
            self.options["residuals_type"] = "standardized"
        elif self.rdo_del.isChecked():
            self.options["residuals_type"] = "deleted"
        else:
            self.options["residuals_type"] = "regular"

        # Graph selection
        if self.rdo_four.isChecked():
            self.options["graphs"] = "four"
        elif self.rdo_none.isChecked():
            self.options["graphs"] = "none"
        else:
            if self.chk_hist.isChecked():
                self.options["graphs"] = "histogram"
            elif self.chk_norm.isChecked():
                self.options["graphs"] = "normal"
            elif self.chk_fits.isChecked():
                self.options["graphs"] = "fits"
            elif self.chk_order.isChecked():
                self.options["graphs"] = "order"
            else:
                self.options["graphs"] = "four"

        self.accept()


class FittedLinePlotStorageDialog(QDialog):
    """Subdialog for storing Fitted Line Plot results in worksheet columns."""

    def __init__(self, parent: QDialog, options: Dict[str, Any]):
        super().__init__(parent)
        self.setWindowTitle("Fitted Line Plot: Storage")
        self.setMinimumSize(360, 240)
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

        self.chk_del_resids = QCheckBox("Deleted Residuals")
        self.chk_del_resids.setChecked(st.get("deleted_residuals", False))
        layout.addWidget(self.chk_del_resids)

        self.chk_coefs = QCheckBox("Coefficients")
        self.chk_coefs.setChecked(st.get("coefficients", False))
        layout.addWidget(self.chk_coefs)

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
            "deleted_residuals": self.chk_del_resids.isChecked(),
            "coefficients": self.chk_coefs.isChecked(),
        }
        self.accept()


class FittedLinePlotDialog(ProcedureDialog):
    """Minitab 22-parity Fitted Line Plot procedure dialog."""

    def __init__(self, window):
        specs = [
            dict(key="response_index", label="Response (Y):", kinds=("number",)),
            dict(key="predictor_index", label="Predictor (X):", kinds=("number",)),
        ]
        super().__init__(
            window,
            "Fitted Line Plot",
            window.presenter.worksheet,
            specs,
            (),
            "Fit Linear, Quadratic, or Cubic polynomial regression with confidence and prediction bands."
        )
        self.window = window
        self.options = default_fitted_line_plot_options()
        self.entry = None

        # Add Type of Regression Model Group
        grp_model = QGroupBox("Type of Regression Model")
        l_model = QHBoxLayout(grp_model)
        self.btn_grp_model = QButtonGroup(self)
        self.rdo_lin = QRadioButton("Linear")
        self.rdo_quad = QRadioButton("Quadratic")
        self.rdo_cub = QRadioButton("Cubic")
        self.btn_grp_model.addButton(self.rdo_lin, 0)
        self.btn_grp_model.addButton(self.rdo_quad, 1)
        self.btn_grp_model.addButton(self.rdo_cub, 2)
        self.rdo_lin.setChecked(True)

        l_model.addWidget(self.rdo_lin)
        l_model.addWidget(self.rdo_quad)
        l_model.addWidget(self.rdo_cub)

        # Subdialog Buttons
        grid = QGridLayout()
        self.btn_options = QPushButton("Options…")
        self.btn_options.clicked.connect(self.open_options)
        grid.addWidget(self.btn_options, 0, 0)

        self.btn_graphs = QPushButton("Graphs…")
        self.btn_graphs.clicked.connect(self.open_graphs)
        grid.addWidget(self.btn_graphs, 0, 1)

        self.btn_storage = QPushButton("Storage…")
        self.btn_storage.clicked.connect(self.open_storage)
        grid.addWidget(self.btn_storage, 0, 2)

        # Insert above footer
        layout = self.layout()
        idx_footer = layout.count() - 2
        layout.insertWidget(idx_footer, grp_model)
        layout.insertLayout(idx_footer + 1, grid)

        self.restore_previous()

    def restore_previous(self):
        p = self.window.presenter
        worksheet_id = p.native_project.worksheet_ids[p.native_project.active_index] if getattr(p, 'native_project', None) else None
        for entry in reversed(getattr(p, 'history', [])):
            if entry.get("source_unavailable") or entry.get("recipe", {}).get("action") != "fitted_line_plot":
                continue
            if entry.get("worksheet_id") != worksheet_id or entry.get("worksheet_name") != p.worksheet.name:
                continue
            params = entry.get("recipe", {}).get("parameters", {})
            resp_idx = params.get("response_index")
            pred_idx = params.get("predictor_index")
            if resp_idx is not None and resp_idx < len(self.worksheet.columns):
                self.fields["response_index"].set_reference(format_variable_reference(self.worksheet.columns[resp_idx]))
            if pred_idx is not None and pred_idx < len(self.worksheet.columns):
                self.fields["predictor_index"].set_reference(format_variable_reference(self.worksheet.columns[pred_idx]))

            m_type = params.get("model_type", "linear").lower()
            if m_type == "quadratic":
                self.rdo_quad.setChecked(True)
            elif m_type == "cubic":
                self.rdo_cub.setChecked(True)
            else:
                self.rdo_lin.setChecked(True)

            opts = params.get("options", {})
            if opts:
                self.options.update(opts)
            break

    def open_options(self):
        d = FittedLinePlotOptionsDialog(self, self.options)
        try:
            if d.exec() == QDialog.DialogCode.Accepted:
                self.options = d.options
        finally:
            d.setParent(None)
            d.close()
            d.deleteLater()

    def open_graphs(self):
        d = FittedLinePlotGraphsDialog(self, self.options)
        try:
            if d.exec() == QDialog.DialogCode.Accepted:
                self.options = d.options
        finally:
            d.setParent(None)
            d.close()
            d.deleteLater()

    def open_storage(self):
        d = FittedLinePlotStorageDialog(self, self.options)
        try:
            if d.exec() == QDialog.DialogCode.Accepted:
                self.options = d.options
        finally:
            d.setParent(None)
            d.close()
            d.deleteLater()

    def accept(self):
        values = self.values()
        resp_idx = values.get("response_index")
        pred_idx = values.get("predictor_index")

        if resp_idx is None or pred_idx is None:
            self.set_error("Select both a Response (Y) and a Predictor (X).")
            return
        if resp_idx == pred_idx:
            self.set_error("Response (Y) and Predictor (X) must be different columns.")
            return

        m_type = "quadratic" if self.rdo_quad.isChecked() else "cubic" if self.rdo_cub.isChecked() else "linear"
        self.options["model_type"] = m_type

        try:
            self.entry = self.window.presenter.fitted_line_plot(
                response_index=resp_idx,
                predictor_index=pred_idx,
                model_type=m_type,
                confidence=self.options.get("confidence", 0.95),
                options=self.options,
            )
            # Execute storage options if requested
            self._apply_storage(self.entry)
            super().accept()
        except Exception as exc:
            self.set_error(str(exc))

    def _apply_storage(self, entry: Dict[str, Any]):
        if not entry:
            return
        st = self.options.get("storage", {})
        res = entry.get("result", {})
        ws = self.window.presenter.worksheet

        storage_specs = [
            ("fits", "FITS", res.get("fits")),
            ("residuals", "RESI", res.get("residuals")),
            ("standardized_residuals", "SRES", res.get("std_residuals")),
            ("deleted_residuals", "TRES", res.get("del_residuals")),
        ]

        from .model import Column
        for key, prefix, data in storage_specs:
            if st.get(key) and data:
                # Find non-conflicting column name
                base_name = f"{prefix}1"
                counter = 1
                while any(c.name == base_name for c in ws.columns):
                    counter += 1
                    base_name = f"{prefix}{counter}"

                # Align with full worksheet length
                aligned_vals = [None] * ws.row_count
                row_indices = res.get("points", {}).get("row_indices", list(range(len(data))))
                for r_idx, val in zip(row_indices, data):
                    if r_idx < len(aligned_vals):
                        aligned_vals[r_idx] = float(val)

                ws.columns.append(Column(base_name, "number", aligned_vals))
                ws.row_count = max(ws.row_count, len(aligned_vals))

        if any(st.values()):
            self.window.refresh()
