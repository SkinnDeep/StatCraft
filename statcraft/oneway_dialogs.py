"""Native-informed Qt dialogs for One-Way ANOVA and its child dialogs.

Form evidence:
- ONEWAYANOVA.MDF
- ONEWAYCOMPARISONS.MDF
- ONEWAYGRAPHS.MDF
- ONEWAYOPTIONS.MDF
- ONEWAYRESULTS.MDF
- ONEWAYSTORAGE.MDF
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
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from .oneway import oneway_settings
from .variable_dialogs import format_variable_reference, resolve_variables


def _footer(dialog: QDialog, layout: QVBoxLayout, callback) -> QDialogButtonBox:
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(callback)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    return buttons


class OneWayComparisonsDialog(QDialog):
    """Subdialog for One-Way ANOVA Comparisons (Tukey, Fisher, Dunnett, Hsu MCB, Games-Howell)."""

    def __init__(self, parent: QDialog, options: dict[str, Any], factor_levels: list[str]):
        super().__init__(parent)
        self.setWindowTitle('One-Way Analysis of Variance: Comparisons')
        self.resize(380, 440)
        self.options = copy.deepcopy(options)
        comp = self.options.get('comparisons', {})
        self.factor_levels = list(factor_levels or [])

        layout = QVBoxLayout(self)

        rate_layout = QHBoxLayout()
        rate_layout.addWidget(QLabel('Error rate for comparisons:'))
        self.rate_edit = QLineEdit(str(comp.get('error_rate', 0.05) * 100.0 if comp.get('error_rate', 0.05) <= 1.0 else comp.get('error_rate', 5.0)))
        rate_layout.addWidget(self.rate_edit)
        rate_layout.addWidget(QLabel('%'))
        layout.addLayout(rate_layout)

        # Equal variances group
        eq_group = QGroupBox('Comparison procedures assuming equal variances')
        eq_layout = QVBoxLayout(eq_group)
        self.chk_tukey = QCheckBox('Tukey')
        self.chk_tukey.setChecked(comp.get('tukey', False))
        eq_layout.addWidget(self.chk_tukey)

        self.chk_fisher = QCheckBox('Fisher')
        self.chk_fisher.setChecked(comp.get('fisher', False))
        eq_layout.addWidget(self.chk_fisher)

        dunnett_h = QHBoxLayout()
        self.chk_dunnett = QCheckBox('Dunnett')
        self.chk_dunnett.setChecked(comp.get('dunnett', False))
        dunnett_h.addWidget(self.chk_dunnett)
        dunnett_h.addWidget(QLabel('Control:'))
        self.cbo_control = QComboBox()
        for lv in self.factor_levels:
            self.cbo_control.addItem(str(lv), lv)
        if comp.get('control_group') in self.factor_levels:
            self.cbo_control.setCurrentText(str(comp['control_group']))
        dunnett_h.addWidget(self.cbo_control)
        eq_layout.addLayout(dunnett_h)

        hsu_h = QHBoxLayout()
        self.chk_hsu = QCheckBox('Hsu MCB')
        self.chk_hsu.setChecked(comp.get('hsu_mcb', False))
        hsu_h.addWidget(self.chk_hsu)
        hsu_h.addWidget(QLabel('Best:'))
        self.cbo_best = QComboBox()
        self.cbo_best.addItem('Largest is best', 'largest')
        self.cbo_best.addItem('Smallest is best', 'smallest')
        if comp.get('hsu_best') == 'smallest':
            self.cbo_best.setCurrentIndex(1)
        hsu_h.addWidget(self.cbo_best)
        eq_layout.addLayout(hsu_h)
        layout.addWidget(eq_group)

        # Unequal variances group
        uneq_group = QGroupBox('Comparison procedure not assuming equal variances')
        uneq_layout = QVBoxLayout(uneq_group)
        self.chk_games_howell = QCheckBox('Games-Howell')
        self.chk_games_howell.setChecked(comp.get('games_howell', False))
        uneq_layout.addWidget(self.chk_games_howell)
        layout.addWidget(uneq_group)

        # Results group
        res_group = QGroupBox('Results')
        res_layout = QVBoxLayout(res_group)
        self.chk_diff_plot = QCheckBox('Interval plot for differences of means')
        self.chk_diff_plot.setChecked(comp.get('interval_plot', True))
        res_layout.addWidget(self.chk_diff_plot)

        self.chk_grouping = QCheckBox('Grouping information')
        self.chk_grouping.setChecked(comp.get('grouping_info', True))
        res_layout.addWidget(self.chk_grouping)

        self.chk_tests = QCheckBox('Tests')
        self.chk_tests.setChecked(comp.get('tests', False))
        res_layout.addWidget(self.chk_tests)
        layout.addWidget(res_group)

        self.error = QLabel()
        self.error.setObjectName('error')
        layout.addWidget(self.error)

        _footer(self, layout, self.validate)

    def validate(self) -> None:
        try:
            val = float(self.rate_edit.text().strip())
            rate = val / 100.0 if val > 1.0 else val
            if not (0.001 <= rate <= 0.5):
                raise ValueError('Error rate must lie between 0.1% and 50%.')
        except ValueError as exc:
            self.error.setText(str(exc))
            return

        self.options['comparisons']['error_rate'] = rate
        self.options['comparisons']['tukey'] = self.chk_tukey.isChecked()
        self.options['comparisons']['fisher'] = self.chk_fisher.isChecked()
        self.options['comparisons']['dunnett'] = self.chk_dunnett.isChecked()
        self.options['comparisons']['control_group'] = self.cbo_control.currentData()
        self.options['comparisons']['hsu_mcb'] = self.chk_hsu.isChecked()
        self.options['comparisons']['hsu_best'] = self.cbo_best.currentData()
        self.options['comparisons']['games_howell'] = self.chk_games_howell.isChecked()
        self.options['comparisons']['interval_plot'] = self.chk_diff_plot.isChecked()
        self.options['comparisons']['grouping_info'] = self.chk_grouping.isChecked()
        self.options['comparisons']['tests'] = self.chk_tests.isChecked()
        self.accept()


class OneWayGraphsDialog(QDialog):
    """Subdialog for One-Way ANOVA Graphs (Data plots, Residual plots)."""

    def __init__(self, parent: QDialog, options: dict[str, Any]):
        super().__init__(parent)
        self.setWindowTitle('One-Way Analysis of Variance: Graphs')
        self.resize(360, 410)
        self.options = copy.deepcopy(options)
        gr = self.options.get('graphs', {})

        layout = QVBoxLayout(self)

        # Data plots
        dp_group = QGroupBox('Data plots')
        dp_layout = QVBoxLayout(dp_group)
        self.chk_interval = QCheckBox('Interval plot')
        self.chk_interval.setChecked(gr.get('interval_plot', True))
        dp_layout.addWidget(self.chk_interval)

        self.chk_indiv = QCheckBox('Individual value plot')
        self.chk_indiv.setChecked(gr.get('individual_value_plot', False))
        dp_layout.addWidget(self.chk_indiv)

        self.chk_boxplot = QCheckBox('Boxplot of data')
        self.chk_boxplot.setChecked(gr.get('boxplot', False))
        dp_layout.addWidget(self.chk_boxplot)
        layout.addWidget(dp_group)

        # Residual plots
        rp_group = QGroupBox('Residual plots')
        rp_layout = QVBoxLayout(rp_group)

        self.rad_none = QRadioButton('None')
        self.rad_four = QRadioButton('Four in one')
        self.rad_indiv = QRadioButton('Individual plots')

        mode = gr.get('residual_mode', 'none')
        if mode == 'four_in_one':
            self.rad_four.setChecked(True)
        elif mode == 'individual':
            self.rad_indiv.setChecked(True)
        else:
            self.rad_none.setChecked(True)

        rp_layout.addWidget(self.rad_none)
        rp_layout.addWidget(self.rad_four)
        rp_layout.addWidget(self.rad_indiv)

        self.chk_hist = QCheckBox('Histogram of residuals')
        self.chk_hist.setChecked(gr.get('res_histogram', False))
        rp_layout.addWidget(self.chk_hist)

        self.chk_norm = QCheckBox('Normal probability plot of residuals')
        self.chk_norm.setChecked(gr.get('res_normal', False))
        rp_layout.addWidget(self.chk_norm)

        self.chk_fits = QCheckBox('Residuals versus fits')
        self.chk_fits.setChecked(gr.get('res_fits', False))
        rp_layout.addWidget(self.chk_fits)

        self.chk_order = QCheckBox('Residuals versus order')
        self.chk_order.setChecked(gr.get('res_order', False))
        rp_layout.addWidget(self.chk_order)

        layout.addWidget(rp_group)

        self.rad_none.toggled.connect(self._sync_mode)
        self.rad_four.toggled.connect(self._sync_mode)
        self.rad_indiv.toggled.connect(self._sync_mode)
        self._sync_mode()

        _footer(self, layout, self.validate)

    def _sync_mode(self) -> None:
        indiv = self.rad_indiv.isChecked()
        self.chk_hist.setEnabled(indiv)
        self.chk_norm.setEnabled(indiv)
        self.chk_fits.setEnabled(indiv)
        self.chk_order.setEnabled(indiv)

    def validate(self) -> None:
        gr = self.options['graphs']
        gr['interval_plot'] = self.chk_interval.isChecked()
        gr['individual_value_plot'] = self.chk_indiv.isChecked()
        gr['boxplot'] = self.chk_boxplot.isChecked()

        if self.rad_four.isChecked():
            gr['residual_mode'] = 'four_in_one'
        elif self.rad_indiv.isChecked():
            gr['residual_mode'] = 'individual'
        else:
            gr['residual_mode'] = 'none'

        gr['res_histogram'] = self.chk_hist.isChecked()
        gr['res_normal'] = self.chk_norm.isChecked()
        gr['res_fits'] = self.chk_fits.isChecked()
        gr['res_order'] = self.chk_order.isChecked()
        self.accept()


class OneWayOptionsDialog(QDialog):
    """Subdialog for One-Way ANOVA Options (Confidence level, Interval type, Equal variances)."""

    def __init__(self, parent: QDialog, options: dict[str, Any]):
        super().__init__(parent)
        self.setWindowTitle('One-Way Analysis of Variance: Options')
        self.resize(360, 200)
        self.options = copy.deepcopy(options)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.conf_edit = QLineEdit(str(self.options.get('confidence', 0.95) * 100.0))
        form.addRow('Confidence level:', self.conf_edit)

        self.cbo_type = QComboBox()
        self.cbo_type.addItem('Two-sided', 'two_sided')
        self.cbo_type.addItem('Lower bound', 'lower')
        self.cbo_type.addItem('Upper bound', 'upper')
        itype = self.options.get('interval_type', 'two_sided')
        idx = self.cbo_type.findData(itype)
        if idx >= 0:
            self.cbo_type.setCurrentIndex(idx)
        form.addRow('Type of confidence interval:', self.cbo_type)
        layout.addLayout(form)

        self.chk_equal_var = QCheckBox('Assume equal variances')
        self.chk_equal_var.setChecked(self.options.get('assume_equal_variances', True))
        layout.addWidget(self.chk_equal_var)

        self.error = QLabel()
        self.error.setObjectName('error')
        layout.addWidget(self.error)

        _footer(self, layout, self.validate)

    def validate(self) -> None:
        try:
            val = float(self.conf_edit.text().strip())
            conf = val / 100.0 if val > 1.0 else val
            if not (0.01 <= conf <= 0.999):
                raise ValueError('Confidence level must lie between 1% and 99.9%.')
        except ValueError as exc:
            self.error.setText(str(exc))
            return

        self.options['confidence'] = conf
        self.options['interval_type'] = self.cbo_type.currentData()
        self.options['assume_equal_variances'] = self.chk_equal_var.isChecked()
        self.accept()


class OneWayResultsDialog(QDialog):
    """Subdialog for One-Way ANOVA Results display selections."""

    def __init__(self, parent: QDialog, options: dict[str, Any]):
        super().__init__(parent)
        self.setWindowTitle('One-Way Analysis of Variance: Results')
        self.resize(300, 260)
        self.options = copy.deepcopy(options)
        res = self.options.get('results', {})

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.cbo_display = QComboBox()
        self.cbo_display.addItem('Simple tables', 'simple')
        self.cbo_display.addItem('Expanded tables', 'expanded')
        if res.get('display') == 'expanded':
            self.cbo_display.setCurrentIndex(1)
        form.addRow('Display of results:', self.cbo_display)
        layout.addLayout(form)

        self.chk_method = QCheckBox('Method')
        self.chk_method.setChecked(res.get('method', True))
        layout.addWidget(self.chk_method)

        self.chk_factor = QCheckBox('Factor information')
        self.chk_factor.setChecked(res.get('factor_info', True))
        layout.addWidget(self.chk_factor)

        self.chk_anova = QCheckBox('Analysis of variance')
        self.chk_anova.setChecked(res.get('anova', True))
        layout.addWidget(self.chk_anova)

        self.chk_summary = QCheckBox('Model summary')
        self.chk_summary.setChecked(res.get('model_summary', True))
        layout.addWidget(self.chk_summary)

        self.chk_means = QCheckBox('Means')
        self.chk_means.setChecked(res.get('means', True))
        layout.addWidget(self.chk_means)

        _footer(self, layout, self.validate)

    def validate(self) -> None:
        r = self.options['results']
        r['display'] = self.cbo_display.currentData()
        r['method'] = self.chk_method.isChecked()
        r['factor_info'] = self.chk_factor.isChecked()
        r['anova'] = self.chk_anova.isChecked()
        r['model_summary'] = self.chk_summary.isChecked()
        r['means'] = self.chk_means.isChecked()
        self.accept()


class OneWayStorageDialog(QDialog):
    """Subdialog for One-Way ANOVA Fits and Residuals column storage."""

    def __init__(self, parent: QDialog, options: dict[str, Any]):
        super().__init__(parent)
        self.setWindowTitle('One-Way Analysis of Variance: Storage')
        self.resize(260, 160)
        self.options = copy.deepcopy(options)
        st = self.options.get('storage', {})

        layout = QVBoxLayout(self)
        self.chk_fits = QCheckBox('Fits')
        self.chk_fits.setChecked(st.get('fits', False))
        layout.addWidget(self.chk_fits)

        self.chk_res = QCheckBox('Residuals')
        self.chk_res.setChecked(st.get('residuals', False))
        layout.addWidget(self.chk_res)

        _footer(self, layout, self.validate)

    def validate(self) -> None:
        self.options['storage']['fits'] = self.chk_fits.isChecked()
        self.options['storage']['residuals'] = self.chk_res.isChecked()
        self.accept()


class OneWayAnovaDialog(QDialog):
    """Main dialog for One-Way Analysis of Variance (ONEWAYANOVA.MDF)."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.worksheet = window.presenter.worksheet
        self.entry = None
        self.options = oneway_settings()
        self.active_edit: QLineEdit | None = None

        self.setWindowTitle('One-Way Analysis of Variance')
        self.resize(540, 360)

        main_layout = QHBoxLayout(self)

        # Left: Available variables list
        left_box = QVBoxLayout()
        left_box.addWidget(QLabel('Available:'))
        self.available_list = QListWidget()
        for idx, col in enumerate(self.worksheet.columns):
            label = format_variable_reference(idx, self.worksheet)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.available_list.addItem(item)
        self.available_list.itemDoubleClicked.connect(self._insert_selected)
        left_box.addWidget(self.available_list)

        self.select_button = QPushButton('Select')
        self.select_button.clicked.connect(self._insert_selected)
        left_box.addWidget(self.select_button)
        main_layout.addLayout(left_box, 1)

        # Right: Dialog controls
        right_box = QVBoxLayout()

        self.mode_combo = QComboBox()
        self.mode_combo.addItem('Response data are in one column for all factor levels', 'stacked')
        self.mode_combo.addItem('Response data are in a separate column for each factor level', 'unstacked')
        self.mode_combo.currentIndexChanged.connect(self._toggle_mode)
        right_box.addWidget(self.mode_combo)

        # Stacked fields
        self.stacked_widget = QDialog()
        stacked_layout = QFormLayout(self.stacked_widget)
        stacked_layout.setContentsMargins(0, 4, 0, 4)
        self.response_edit = QLineEdit()
        self.response_edit.setPlaceholderText('e.g. C1')
        self.response_edit.installEventFilter(self)
        stacked_layout.addRow('Response:', self.response_edit)

        self.factor_edit = QLineEdit()
        self.factor_edit.setPlaceholderText('e.g. C2')
        self.factor_edit.installEventFilter(self)
        stacked_layout.addRow('Factor:', self.factor_edit)
        right_box.addWidget(self.stacked_widget)

        # Unstacked fields
        self.unstacked_widget = QDialog()
        unstacked_layout = QFormLayout(self.unstacked_widget)
        unstacked_layout.setContentsMargins(0, 4, 0, 4)
        self.responses_edit = QLineEdit()
        self.responses_edit.setPlaceholderText('e.g. C1 C2 C3')
        self.responses_edit.installEventFilter(self)
        unstacked_layout.addRow('Responses:', self.responses_edit)
        right_box.addWidget(self.unstacked_widget)

        # Child dialog buttons
        buttons_row = QHBoxLayout()
        self.options_button = QPushButton('Options…')
        self.options_button.clicked.connect(self.configure_options)
        buttons_row.addWidget(self.options_button)

        self.comparisons_button = QPushButton('Comparisons…')
        self.comparisons_button.clicked.connect(self.configure_comparisons)
        buttons_row.addWidget(self.comparisons_button)

        self.graphs_button = QPushButton('Graphs…')
        self.graphs_button.clicked.connect(self.configure_graphs)
        buttons_row.addWidget(self.graphs_button)

        self.results_button = QPushButton('Results…')
        self.results_button.clicked.connect(self.configure_results)
        buttons_row.addWidget(self.results_button)

        self.storage_button = QPushButton('Storage…')
        self.storage_button.clicked.connect(self.configure_storage)
        buttons_row.addWidget(self.storage_button)
        right_box.addLayout(buttons_row)

        right_box.addStretch(1)

        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        right_box.addWidget(self.error)

        _footer(self, right_box, self.validate)
        main_layout.addLayout(right_box, 2)

        self.active_edit = self.response_edit
        self._toggle_mode()
        self.restore_previous()

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn and isinstance(obj, QLineEdit):
            self.active_edit = obj
        return super().eventFilter(obj, event)

    def _toggle_mode(self) -> None:
        stacked = self.mode_combo.currentData() == 'stacked'
        self.stacked_widget.setVisible(stacked)
        self.unstacked_widget.setVisible(not stacked)
        self.active_edit = self.response_edit if stacked else self.responses_edit

    def _insert_selected(self) -> None:
        item = self.available_list.currentItem()
        if not item or not self.active_edit:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        ref = f'C{idx + 1}'
        cur = self.active_edit.text().strip()
        if self.active_edit is self.responses_edit:
            self.active_edit.setText(f'{cur} {ref}'.strip())
        else:
            self.active_edit.setText(ref)

    def _get_factor_levels(self) -> list[str]:
        if self.mode_combo.currentData() == 'stacked':
            try:
                tokens = resolve_variables(self.factor_edit.text(), self.worksheet, kinds=('number', 'text', 'date'))
            except Exception:
                tokens = []
            if tokens:
                col = self.worksheet.columns[tokens[0]]
                levels = []
                for v in col.values:
                    if v is not None and str(v).strip() != '':
                        s = str(v).strip()
                        if s not in levels:
                            levels.append(s)
                return levels
            return []
        else:
            try:
                tokens = resolve_variables(self.responses_edit.text(), self.worksheet, kinds=('number',))
            except Exception:
                tokens = []
            return [self.worksheet.columns[i].name or f'C{i + 1}' for i in tokens]

    def configure_comparisons(self) -> None:
        levels = self._get_factor_levels()
        dlg = OneWayComparisonsDialog(self, self.options, levels)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.options = dlg.options

    def configure_graphs(self) -> None:
        dlg = OneWayGraphsDialog(self, self.options)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.options = dlg.options

    def configure_options(self) -> None:
        dlg = OneWayOptionsDialog(self, self.options)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.options = dlg.options

    def configure_results(self) -> None:
        dlg = OneWayResultsDialog(self, self.options)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.options = dlg.options

    def configure_storage(self) -> None:
        dlg = OneWayStorageDialog(self, self.options)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.options = dlg.options

    def restore_previous(self) -> None:
        for entry in reversed(self.window.presenter.history):
            if entry.get('recipe', {}).get('action') == 'oneway_anova':
                p = entry['recipe']['parameters']
                self.options = oneway_settings(p.get('options'))
                stacked = p.get('stacked', True)
                self.mode_combo.setCurrentIndex(0 if stacked else 1)
                if stacked:
                    r_idx = p.get('response_index')
                    f_idx = p.get('factor_index')
                    if r_idx is not None and r_idx < len(self.worksheet.columns):
                        self.response_edit.setText(f'C{r_idx + 1}')
                    if f_idx is not None and f_idx < len(self.worksheet.columns):
                        self.factor_edit.setText(f'C{f_idx + 1}')
                else:
                    r_idxs = p.get('response_indices', [])
                    self.responses_edit.setText(' '.join(f'C{i + 1}' for i in r_idxs if i < len(self.worksheet.columns)))
                break

    def validate(self) -> None:
        stacked = self.mode_combo.currentData() == 'stacked'
        try:
            if stacked:
                r_tokens = resolve_variables(self.response_edit.text(), self.worksheet, kinds=('number',))
                if not r_tokens:
                    raise ValueError('Specify a response column.')
                f_tokens = resolve_variables(self.factor_edit.text(), self.worksheet, kinds=('number', 'text', 'date'))
                if not f_tokens:
                    raise ValueError('Specify a factor column.')
                r_idx, f_idx = r_tokens[0], f_tokens[0]
                if r_idx == f_idx:
                    raise ValueError('Response and factor cannot be the same column.')
                self.entry = self.window.presenter.oneway_anova(
                    response_index=r_idx,
                    factor_index=f_idx,
                    options=self.options,
                )
            else:
                r_tokens = resolve_variables(self.responses_edit.text(), self.worksheet, kinds=('number',))
                if len(r_tokens) < 2:
                    raise ValueError('Specify at least two response columns for unstacked ANOVA.')
                self.entry = self.window.presenter.oneway_anova_unstacked(
                    response_indices=r_tokens,
                    options=self.options,
                )
        except Exception as exc:
            self.error.setText(str(exc))
            return

        self.accept()
        self.window.show_result(self.entry)
