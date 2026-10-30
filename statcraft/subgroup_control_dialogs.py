"""Qt Dialogs for Subgroup Control Charts (Xbar-R and Xbar-S) with native StatCraft PE fidelity.

Form Evidence:
- XRCHARTDATASOURCE.MDF (Xbar-R Chart main dialog)
- XSCHARTDATASOURCE.MDF (Xbar-S Chart main dialog)
- QCHARTPARAMETERS.MDF (Options: Parameters tab)
- QCHARTESTIMATE.MDF (Options: Estimate tab)
- QCHARTSLIMITS.MDF (Options: Limits tab)
- QCHARTTESTS.MDF (Options: Tests tab - All 8 Nelson tests)
- QCHARTSTORAGE.MDF (Options: Storage tab)
"""
from __future__ import annotations

import copy
from typing import Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
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
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .subgroup_control import control_chart_settings, fit_from_worksheet
from .variable_dialogs import format_variable_reference, resolve_variables


def _footer(dialog: QDialog, layout: QVBoxLayout, callback) -> QDialogButtonBox:
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(callback)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    return buttons


class ControlChartOptionsDialog(QDialog):
    """Subdialog for Control Chart Options (Parameters, Estimate, Limits, Tests, Storage)."""

    def __init__(self, parent: QDialog, options: dict[str, Any], chart_type: str = 'xbar_r'):
        super().__init__(parent)
        title_prefix = "Xbar-R" if chart_type == 'xbar_r' else "Xbar-S"
        self.setWindowTitle(f"{title_prefix} Options")
        self.resize(480, 420)
        self.options = copy.deepcopy(options)
        self.chart_type = chart_type

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        # Tab 1: Parameters
        tab_param = QWidget()
        layout_param = QVBoxLayout(tab_param)
        desc_param = QLabel("To specify the values for one or both parameters, enter them here. "
                            "StatCraft uses these values instead of estimating them from the data.")
        desc_param.setWordWrap(True)
        layout_param.addWidget(desc_param)
        form_param = QFormLayout()
        self.mean_edit = QLineEdit()
        if self.options.get('historical_mean') is not None:
            self.mean_edit.setText(str(self.options['historical_mean']))
        form_param.addRow("Mean:", self.mean_edit)

        self.sigma_edit = QLineEdit()
        if self.options.get('historical_sigma') is not None:
            self.sigma_edit.setText(str(self.options['historical_sigma']))
        form_param.addRow("Standard deviation:", self.sigma_edit)
        layout_param.addLayout(form_param)
        layout_param.addStretch()
        self.tabs.addTab(tab_param, "Parameters")

        # Tab 2: Estimate
        tab_est = QWidget()
        layout_est = QVBoxLayout(tab_est)
        group_meth = QGroupBox("Method for estimating standard deviation")
        v_meth = QVBoxLayout(group_meth)
        self.rad_default = QRadioButton("Average range (Rbar)" if chart_type == 'xbar_r' else "Average standard deviation (Sbar)")
        self.rad_pooled = QRadioButton("Pooled standard deviation")
        self.method_group = QButtonGroup(self)
        self.method_group.addButton(self.rad_default, 0)
        self.method_group.addButton(self.rad_pooled, 1)

        curr_meth = self.options.get('estimation_method', 'rbar' if chart_type == 'xbar_r' else 'sbar')
        if curr_meth == 'pooled_stdev':
            self.rad_pooled.setChecked(True)
        else:
            self.rad_default.setChecked(True)
        v_meth.addWidget(self.rad_default)
        v_meth.addWidget(self.rad_pooled)
        layout_est.addWidget(group_meth)

        self.chk_unbiasing = QCheckBox("Use unbiasing constants (c4, d2)")
        self.chk_unbiasing.setChecked(self.options.get('unbiasing', True))
        layout_est.addWidget(self.chk_unbiasing)

        group_omit = QGroupBox("Omit subgroups")
        v_omit = QVBoxLayout(group_omit)
        v_omit.addWidget(QLabel("Omit the following subgroups when estimating parameters:"))
        self.omit_edit = QLineEdit()
        omit_list = self.options.get('omit_subgroups', [])
        if omit_list:
            self.omit_edit.setText(" ".join(str(x) for x in omit_list))
        v_omit.addWidget(self.omit_edit)
        layout_est.addWidget(group_omit)
        layout_est.addStretch()
        self.tabs.addTab(tab_est, "Estimate")

        # Tab 3: Limits
        tab_lim = QWidget()
        layout_lim = QVBoxLayout(tab_lim)
        form_lim = QFormLayout()
        k_val = self.options.get('k_sigma', 3.0)
        if isinstance(k_val, list):
            k_val_str = " ".join(str(x) for x in k_val)
        else:
            k_val_str = str(k_val)
        self.ksigma_edit = QLineEdit(k_val_str)
        form_lim.addRow("Number of standard deviations:", self.ksigma_edit)
        layout_lim.addLayout(form_lim)

        group_disp = QGroupBox("Display control limits")
        v_disp = QVBoxLayout(group_disp)
        self.chk_ucl = QCheckBox("Upper control limit (UCL)")
        self.chk_ucl.setChecked(self.options.get('display_upper', True))
        self.chk_lcl = QCheckBox("Lower control limit (LCL)")
        self.chk_lcl.setChecked(self.options.get('display_lower', True))
        v_disp.addWidget(self.chk_ucl)
        v_disp.addWidget(self.chk_lcl)

        # StatCraft.6: Extended limits & warning limits
        h_warn = QHBoxLayout()
        self.chk_warning = QCheckBox("Display warning limits at K standard deviations:")
        self.chk_warning.setChecked(self.options.get('warning_limits', False))
        h_warn.addWidget(self.chk_warning)
        self.edit_warn_k = QLineEdit(str(self.options.get('warning_k', 2.0)))
        self.edit_warn_k.setFixedWidth(50)
        h_warn.addWidget(self.edit_warn_k)
        h_warn.addStretch()
        v_disp.addLayout(h_warn)

        self.chk_zones = QCheckBox("Display zone boundary lines (A, B, C bands at 1, 2, 3 sigma)")
        self.chk_zones.setChecked(self.options.get('display_zones', False))
        v_disp.addWidget(self.chk_zones)

        layout_lim.addWidget(group_disp)
        layout_lim.addStretch()
        self.tabs.addTab(tab_lim, "Limits")

        # Tab 4: Tests
        tab_tests = QWidget()
        layout_tests = QVBoxLayout(tab_tests)
        self.chk_perform_all = QCheckBox("Perform all 8 Nelson / Western Electric tests")
        layout_tests.addWidget(self.chk_perform_all)

        t_cfg = self.options.get('tests', {})
        self.test_widgets: list[tuple[QCheckBox, QLineEdit | None, str]] = []

        tests_info = [
            ("test1", "1 point > K standard deviations from center line", True, 3.0),
            ("test2", "K points in a row on same side of center line", False, 9),
            ("test3", "K points in a row, all increasing or all decreasing", False, 6),
            ("test4", "K points in a row, alternating up and down", False, 14),
            ("test5", "K out of K+1 points > 2 standard deviations from center line (same side)", False, 2),
            ("test6", "K out of K+1 points > 1 standard deviations from center line (same side)", False, 4),
            ("test7", "K points in a row within 1 standard deviation of center line (either side)", False, 15),
            ("test8", "K points in a row > 1 standard deviation from center line (either side)", False, 8),
        ]

        for key, desc, def_chk, def_k in tests_info:
            sub_h = QHBoxLayout()
            chk = QCheckBox(desc.split("K")[0] + ("K " if "K" in desc else ""))
            cur_test = t_cfg.get(key, {})
            chk.setChecked(cur_test.get('enabled', def_chk))

            ledit = QLineEdit(str(cur_test.get('k', def_k)))
            ledit.setMaximumWidth(50)

            rest_lbl = QLabel(desc.split("K", 1)[1] if "K" in desc else "")
            sub_h.addWidget(chk)
            sub_h.addWidget(ledit)
            sub_h.addWidget(rest_lbl)
            sub_h.addStretch()
            layout_tests.addLayout(sub_h)
            self.test_widgets.append((chk, ledit, key))

        self.chk_perform_all.toggled.connect(self._toggle_all_tests)
        layout_tests.addStretch()
        self.tabs.addTab(tab_tests, "Tests")

        # Tab 5: Storage
        tab_store = QWidget()
        layout_store = QVBoxLayout(tab_store)
        layout_store.addWidget(QLabel("Store the following columns on the active worksheet:"))
        st_cfg = self.options.get('storage', {})
        self.chk_s_points = QCheckBox("Plotted points (Means and Ranges/StDevs)")
        self.chk_s_points.setChecked(st_cfg.get('points', False))
        self.chk_s_center = QCheckBox("Center line values")
        self.chk_s_center.setChecked(st_cfg.get('center_line', False))
        self.chk_s_limits = QCheckBox("Control limits (LCL and UCL)")
        self.chk_s_limits.setChecked(st_cfg.get('control_limits', False))
        self.chk_s_sizes = QCheckBox("Subgroup sizes")
        self.chk_s_sizes.setChecked(st_cfg.get('subgroup_sizes', False))
        self.chk_s_tests = QCheckBox("Test results")
        self.chk_s_tests.setChecked(st_cfg.get('test_results', False))

        layout_store.addWidget(self.chk_s_points)
        layout_store.addWidget(self.chk_s_center)
        layout_store.addWidget(self.chk_s_limits)
        layout_store.addWidget(self.chk_s_sizes)
        layout_store.addWidget(self.chk_s_tests)
        layout_store.addStretch()
        self.tabs.addTab(tab_store, "Storage")

        _footer(self, layout, self.validate)

    def _toggle_all_tests(self, checked: bool):
        for chk, _, _ in self.test_widgets:
            chk.setChecked(checked)

    def validate(self):
        m_txt = self.mean_edit.text().strip()
        hist_m = float(m_txt) if m_txt else None

        s_txt = self.sigma_edit.text().strip()
        hist_s = None
        if s_txt:
            try:
                hist_s = float(s_txt)
                if hist_s <= 0:
                    QMessageBox.warning(self, "Invalid Input", "Historical standard deviation must be positive.")
                    return
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "Historical standard deviation must be a number.")
                return

        meth = 'pooled_stdev' if self.rad_pooled.isChecked() else ('rbar' if self.chart_type == 'xbar_r' else 'sbar')
        unbias = self.chk_unbiasing.isChecked()
        omit_str = self.omit_edit.text().strip()

        k_txt = self.ksigma_edit.text().strip()
        try:
            parts = [float(x) for x in k_txt.replace(',', ' ').split()] if k_txt else [3.0]
            k_sig = parts[-1] if parts else 3.0
            if not (0.1 <= k_sig <= 10.0):
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Number of standard deviations must lie between 0.1 and 10.0.")
            return

        warn_k = 2.0
        try:
            warn_k = float(self.edit_warn_k.text().strip() or "2.0")
        except ValueError:
            warn_k = 2.0

        disp_u = self.chk_ucl.isChecked()
        disp_l = self.chk_lcl.isChecked()

        tests_dict = {}
        for chk, ledit, key in self.test_widgets:
            en = chk.isChecked()
            k_val = float(ledit.text().strip() or "3") if ledit else 3.0
            if key in ('test2', 'test3', 'test4', 'test5', 'test6', 'test7', 'test8'):
                k_val = int(round(k_val))
            tests_dict[key] = {'enabled': en, 'k': k_val}

        store_dict = {
            'points': self.chk_s_points.isChecked(),
            'center_line': self.chk_s_center.isChecked(),
            'control_limits': self.chk_s_limits.isChecked(),
            'subgroup_sizes': self.chk_s_sizes.isChecked(),
            'test_results': self.chk_s_tests.isChecked(),
        }

        self.options['historical_mean'] = hist_m
        self.options['historical_sigma'] = hist_s
        self.options['estimation_method'] = meth
        self.options['unbiasing'] = unbias
        self.options['omit_subgroups'] = omit_str
        self.options['k_sigma'] = k_txt if len(parts) > 1 else k_sig
        self.options['warning_limits'] = self.chk_warning.isChecked() or len(parts) > 1
        self.options['warning_k'] = warn_k
        self.options['display_zones'] = self.chk_zones.isChecked() or len(parts) >= 3
        self.options['display_upper'] = disp_u
        self.options['display_lower'] = disp_l
        self.options['tests'] = tests_dict
        self.options['storage'] = store_dict

        self.accept()


class BaseSubgroupChartDialog(QDialog):
    """Base dialog for Xbar-R and Xbar-S charts matching StatCraft PE forms."""

    def __init__(self, parent: QWidget, chart_type: str = 'xbar_r'):
        super().__init__(parent)
        self.main_window = parent
        self.chart_type = chart_type
        title = "Xbar-R Chart" if chart_type == 'xbar_r' else "Xbar-S Chart"
        self.setWindowTitle(title)
        self.resize(560, 380)

        self.options = control_chart_settings({'chart_type': chart_type})
        self.entry = None

        # Main layout: Left column list, Right controls
        root_layout = QVBoxLayout(self)
        body_layout = QHBoxLayout()
        root_layout.addLayout(body_layout)

        # Left Column List
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Columns:"))
        self.col_list = QListWidget()
        left_layout.addWidget(self.col_list)
        self.btn_select = QPushButton("Select")
        self.btn_select.clicked.connect(self._on_select)
        left_layout.addWidget(self.btn_select)
        body_layout.addLayout(left_layout, stretch=1)

        # Right Controls
        right_layout = QVBoxLayout()
        body_layout.addLayout(right_layout, stretch=2)

        # Data arrangement dropdown
        self.combo_arrangement = QComboBox()
        self.combo_arrangement.addItem("All observations for a chart are in one column:")
        self.combo_arrangement.addItem("Observations for a subgroup are in one row of columns:")
        self.combo_arrangement.currentIndexChanged.connect(self._on_arrangement_changed)
        right_layout.addWidget(self.combo_arrangement)

        # Stacked widgets (Layer 1)
        self.stacked_widget = QWidget()
        stacked_form = QFormLayout(self.stacked_widget)
        self.resp_edit = QLineEdit()
        stacked_form.addRow("Measurements:", self.resp_edit)

        sub_size_layout = QHBoxLayout()
        self.sub_size_edit = QLineEdit("5")
        sub_size_layout.addWidget(self.sub_size_edit)
        sub_size_layout.addWidget(QLabel("(enter a number or ID column)"))
        stacked_form.addRow("Subgroup sizes:", sub_size_layout)
        right_layout.addWidget(self.stacked_widget)

        # Unstacked widgets (Layer 2)
        self.unstacked_widget = QWidget()
        unstacked_form = QFormLayout(self.unstacked_widget)
        self.rows_edit = QLineEdit()
        unstacked_form.addRow("Subgroup columns:", self.rows_edit)
        self.unstacked_widget.setVisible(False)
        right_layout.addWidget(self.unstacked_widget)

        # Child Options Button
        btn_opts_title = f"{'Xbar-R' if chart_type == 'xbar_r' else 'Xbar-S'} Options…"
        self.btn_options = QPushButton(btn_opts_title)
        self.btn_options.clicked.connect(self._open_options)
        right_layout.addWidget(self.btn_options)
        right_layout.addStretch()

        # Footer OK / Cancel
        _footer(self, root_layout, self.run_analysis)

        self._populate_columns()
        self.col_list.itemDoubleClicked.connect(self._on_select)

    def _populate_columns(self):
        ws = getattr(self.main_window.presenter, 'worksheet', None)
        if not ws:
            return
        for i, col in enumerate(ws.columns):
            item = QListWidgetItem(format_variable_reference(i, ws))
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.col_list.addItem(item)

    def _on_arrangement_changed(self, index: int):
        if index == 0:
            self.stacked_widget.setVisible(True)
            self.unstacked_widget.setVisible(False)
        else:
            self.stacked_widget.setVisible(False)
            self.unstacked_widget.setVisible(True)

    def _on_select(self):
        items = self.col_list.selectedItems()
        if not items:
            return
        names = [item.text().split()[0] for item in items]
        text_to_add = " ".join(names)

        if self.combo_arrangement.currentIndex() == 0:
            if self.sub_size_edit.hasFocus():
                self.sub_size_edit.setText(text_to_add)
            else:
                self.resp_edit.setText(text_to_add)
        else:
            cur = self.rows_edit.text().strip()
            self.rows_edit.setText(f"{cur} {text_to_add}".strip())

    def _open_options(self):
        dlg = ControlChartOptionsDialog(self, self.options, chart_type=self.chart_type)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.options = dlg.options

    def run_analysis(self):
        ws = getattr(self.main_window.presenter, 'worksheet', None)
        if not ws:
            QMessageBox.warning(self, "No Worksheet", "No active worksheet available.")
            return

        is_stacked = (self.combo_arrangement.currentIndex() == 0)
        try:
            if is_stacked:
                resp_tokens = resolve_variables(self.resp_edit.text(), ws, kinds=('number',))
                if not resp_tokens:
                    QMessageBox.warning(self, "Invalid Selection", "Select a numeric measurement column.")
                    return
                resp_idx = resp_tokens[0]

                sz_text = self.sub_size_edit.text().strip()
                factor_idx = None
                sub_size = None
                try:
                    sub_size = int(sz_text)
                    if sub_size < 2:
                        QMessageBox.warning(self, "Invalid Subgroup Size", "Subgroup size must be at least 2.")
                        return
                except ValueError:
                    fac_tokens = resolve_variables(sz_text, ws, kinds=('number', 'text'))
                    if not fac_tokens:
                        QMessageBox.warning(self, "Invalid Subgroup Size", "Enter a subgroup size >= 2 or an ID column.")
                        return
                    factor_idx = fac_tokens[0]

                res = self.main_window.presenter.subgroup_control_chart(
                    chart_type=self.chart_type,
                    stacked=True,
                    response_index=resp_idx,
                    factor_index=factor_idx,
                    subgroup_size=sub_size,
                    options=self.options
                )
            else:
                row_tokens = resolve_variables(self.rows_edit.text(), ws, kinds=('number',))
                if not row_tokens or len(row_tokens) < 2:
                    QMessageBox.warning(self, "Invalid Selection", "Select at least 2 measurement columns.")
                    return

                res = self.main_window.presenter.subgroup_control_chart(
                    chart_type=self.chart_type,
                    stacked=False,
                    indices=row_tokens,
                    options=self.options
                )

            self.entry = res
            self.accept()
            if hasattr(self.main_window, 'show_result'):
                self.main_window.show_result(res)
        except Exception as exc:
            QMessageBox.critical(self, "Calculation Error", str(exc))


class XbarRChartDialog(BaseSubgroupChartDialog):
    """Native Xbar-R Chart dialog matching XRCHARTDATASOURCE.MDF."""

    def __init__(self, parent: QWidget):
        super().__init__(parent, chart_type='xbar_r')


class XbarSChartDialog(BaseSubgroupChartDialog):
    """Native Xbar-S Chart dialog matching XSCHARTDATASOURCE.MDF."""

    def __init__(self, parent: QWidget):
        super().__init__(parent, chart_type='xbar_s')
