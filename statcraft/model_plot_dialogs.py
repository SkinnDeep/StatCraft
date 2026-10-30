"""Native-informed dialogs for Factorial Plots, Model Contour Plot, and Model Surface Plot.

Form evidence:
- Factorial Plots: FACTORIALPLOT, REGRESSIONFACPLOT, GLMFACPLOT, FACPLOTFACTORIAL,
  FACPLOTRESPONSESURFACE, BINARYLOGISTICFACPLOT, REGRFACPLOTGRAPHS,
  REGRFACPLOTOPTIONS, FACTORIALPLOTSETTINGS
- Contour Plot: REGRESSIONCONTOURPLOT, GLMCONTOURPLOT, CONTOURPLOTFACTORIAL,
  CONTOURPLOTRESPSURF, BINARYLOGISTICCONTOURPLOT, REGRCONTOURPLOTCONTOURS,
  REGRSURFACEPLOTSETTINGS
- Surface Plot: REGRESSIONSURFACEPLOT, GLMSURFACEPLOT, SURFACEPLOTFACTORIAL,
  SURFACEPLOTRESPSURF, BINARYLOGISTICSURFACEPLOT, REGRSURFACEPLOTOPTIONS,
  REGRSURFACEPLOTSETTINGS
"""
import copy
import math
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)
from .model_plots import (
    contour_plot_settings,
    discover_models,
    factorial_plots_settings,
    surface_plot_settings,
)
from .optimizer import normalize_model_recipe
from .variable_dialogs import format_variable_reference


def _footer(dialog, layout, callback):
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(callback)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    return buttons


def _model_description(worksheet, model_recipe, bundle):
    if not bundle:
        return 'No supported fitted model is available.'
    lines = [
        bundle['model_title'],
        'Response: ' + bundle['response_name'],
        '',
        'Predictors:',
    ]
    for pred in bundle['predictors']:
        role_label = 'factor' if pred['role'] == 'factor' else 'continuous'
        line = f"{format_variable_reference(pred['index'], worksheet)} — {role_label}"
        if pred.get('levels'):
            line += '; levels: ' + ', '.join(map(str, pred['levels']))
        lines.append(line)
    terms = model_recipe['parameters'].get('terms')
    names = [p['name'] for p in bundle['predictors']]
    lines.extend(['', 'Terms:'])
    if terms:
        lines.extend(' × '.join(names[i] for i in term) for term in terms)
    else:
        lines.extend(names)
    lines.extend(['', 'Refitted using the current worksheet data.'])
    return '\n'.join(lines)


def _show_view_model_dialog(parent, title, worksheet, model_recipe, bundle):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(520, 360)
    layout = QVBoxLayout(dialog)
    text = QTextEdit()
    text.setReadOnly(True)
    text.setPlainText(_model_description(worksheet, model_recipe, bundle))
    layout.addWidget(text)
    close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close.rejected.connect(dialog.reject)
    layout.addWidget(close)
    dialog.exec()


def _hold_map(hold_values):
    if isinstance(hold_values, list):
        return {item['index']: item['value'] for item in hold_values if isinstance(item, dict) and 'index' in item}
    if isinstance(hold_values, dict):
        return {int(k): v for k, v in hold_values.items()}
    return {}


class HoldSettingsDialog(QDialog):
    """Shared Hold Values / Settings subdialog for Factorial, Contour, and Surface plots."""

    def __init__(self, parent, title, worksheet, bundle, options, settings_fn):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(500, 360)
        self.worksheet = worksheet
        self.bundle = bundle
        self.initial = settings_fn(options)
        self.settings_fn = settings_fn
        self.options = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.hold_cont = QComboBox()
        for label, value in [('Mean', 'mean'), ('Minimum', 'min'), ('Maximum', 'max')]:
            self.hold_cont.addItem(label, value)
        self.hold_cont.setCurrentIndex(
            max(0, self.hold_cont.findData(self.initial['hold_continuous']))
        )
        form.addRow('Hold continuous variables at:', self.hold_cont)

        self.hold_cat = QComboBox()
        for label, value in [('Lowest level', 'first'), ('Highest level', 'last')]:
            self.hold_cat.addItem(label, value)
        self.hold_cat.setCurrentIndex(
            max(0, self.hold_cat.findData(self.initial['hold_categorical']))
        )
        form.addRow('Hold categorical variables at:', self.hold_cat)
        layout.addLayout(form)

        layout.addWidget(QLabel('Optional per-variable hold overrides (leave blank for default):'))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Variable', 'Type', 'Hold Setting'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        predictors = self.bundle['predictors'] if self.bundle else []
        self.table.setRowCount(len(predictors))
        saved_holds = _hold_map(self.initial.get('hold_values', []))
        for row, pred in enumerate(predictors):
            ref = format_variable_reference(pred['index'], self.worksheet)
            name_item = QTableWidgetItem(ref)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            role_item = QTableWidgetItem('Categorical' if pred['role'] == 'factor' else 'Continuous')
            role_item.setFlags(role_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, role_item)
            saved_val = saved_holds.get(pred['index'])
            if pred['role'] == 'factor' and pred.get('levels'):
                combo = QComboBox()
                combo.addItem('(Default)', None)
                for lvl in pred['levels']:
                    combo.addItem(str(lvl), lvl)
                if saved_val is not None:
                    idx = combo.findData(saved_val)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                self.table.setCellWidget(row, 2, combo)
            else:
                txt = '' if saved_val is None else format(float(saved_val), '.6g')
                self.table.setItem(row, 2, QTableWidgetItem(txt))

        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = _footer(self, layout, self.validate)

    def validate(self):
        try:
            hold_values = []
            predictors = self.bundle['predictors'] if self.bundle else []
            for row, pred in enumerate(predictors):
                widget = self.table.cellWidget(row, 2)
                if widget is not None:
                    val = widget.currentData()
                    if val is not None:
                        hold_values.append(dict(index=pred['index'], value=val))
                else:
                    item = self.table.item(row, 2)
                    txt = item.text().strip() if item else ''
                    if txt:
                        num = float(txt)
                        if not math.isfinite(num):
                            raise ValueError(f"Hold value for {pred['name']} must be finite.")
                        hold_values.append(dict(index=pred['index'], value=num))
            updated = dict(
                self.initial,
                hold_continuous=self.hold_cont.currentData(),
                hold_categorical=self.hold_cat.currentData(),
                hold_values=hold_values,
            )
            self.options = self.settings_fn(updated)
        except (ValueError, TypeError, OverflowError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()


class FactorialPlotsGraphsDialog(QDialog):
    """Subdialog matching REGRFACPLOTGRAPHS / FACTORIALPLOT graphs selection."""

    def __init__(self, parent, options):
        super().__init__(parent)
        self.setWindowTitle('Factorial Plots: Graphs')
        self.initial = factorial_plots_settings(options)
        self.options = None

        layout = QVBoxLayout(self)
        self.main_effects = QCheckBox('Main effects plot')
        self.main_effects.setChecked(self.initial['show_main_effects'])
        self.interaction_plot = QCheckBox('Interaction plot')
        self.interaction_plot.setChecked(self.initial['show_interaction_plot'])
        layout.addWidget(self.main_effects)
        layout.addWidget(self.interaction_plot)

        form = QFormLayout()
        self.matrix_mode = QComboBox()
        self.matrix_mode.addItem('Show only lower-left matrix', 'lower_left')
        self.matrix_mode.addItem('Show full interaction plot matrix', 'full')
        self.matrix_mode.setCurrentIndex(
            max(0, self.matrix_mode.findData(self.initial['matrix_display']))
        )
        form.addRow('Interaction matrix:', self.matrix_mode)

        self.terms_mode = QComboBox()
        self.terms_mode.addItem('Only model terms', 'model')
        self.terms_mode.addItem('All terms', 'all')
        self.terms_mode.setCurrentIndex(
            max(0, self.terms_mode.findData(self.initial['terms_to_display']))
        )
        form.addRow('Terms to display:', self.terms_mode)
        layout.addLayout(form)

        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = _footer(self, layout, self.validate)

    def validate(self):
        try:
            updated = dict(
                self.initial,
                show_main_effects=self.main_effects.isChecked(),
                show_interaction_plot=self.interaction_plot.isChecked(),
                matrix_display=self.matrix_mode.currentData(),
                terms_to_display=self.terms_mode.currentData(),
            )
            self.options = factorial_plots_settings(updated)
        except (ValueError, TypeError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()


class FactorialPlotsOptionsDialog(QDialog):
    """Subdialog matching REGRFACPLOTOPTIONS + FACTORIALPLOTSETTINGS."""

    def __init__(self, parent, worksheet, bundle, options):
        super().__init__(parent)
        self.setWindowTitle('Factorial Plots: Options')
        self.resize(500, 390)
        self.worksheet = worksheet
        self.bundle = bundle
        self.initial = factorial_plots_settings(options)
        self.options = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit(self.initial.get('title', ''))
        form.addRow('Title:', self.title_edit)

        self.hold_cont = QComboBox()
        for label, value in [('Mean', 'mean'), ('Minimum', 'min'), ('Maximum', 'max')]:
            self.hold_cont.addItem(label, value)
        self.hold_cont.setCurrentIndex(
            max(0, self.hold_cont.findData(self.initial['hold_continuous']))
        )
        form.addRow('Hold continuous variables at:', self.hold_cont)

        self.hold_cat = QComboBox()
        for label, value in [('Lowest level', 'first'), ('Highest level', 'last')]:
            self.hold_cat.addItem(label, value)
        self.hold_cat.setCurrentIndex(
            max(0, self.hold_cat.findData(self.initial['hold_categorical']))
        )
        form.addRow('Hold categorical variables at:', self.hold_cat)
        layout.addLayout(form)

        layout.addWidget(QLabel('Optional per-variable hold overrides (for unplotted variables):'))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Variable', 'Type', 'Hold Setting'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        predictors = self.bundle['predictors'] if self.bundle else []
        self.table.setRowCount(len(predictors))
        saved_holds = _hold_map(self.initial.get('hold_values', []))
        for row, pred in enumerate(predictors):
            ref = format_variable_reference(pred['index'], self.worksheet)
            name_item = QTableWidgetItem(ref)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            role_item = QTableWidgetItem('Categorical' if pred['role'] == 'factor' else 'Continuous')
            role_item.setFlags(role_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, role_item)
            saved_val = saved_holds.get(pred['index'])
            if pred['role'] == 'factor' and pred.get('levels'):
                combo = QComboBox()
                combo.addItem('(Default)', None)
                for lvl in pred['levels']:
                    combo.addItem(str(lvl), lvl)
                if saved_val is not None:
                    idx = combo.findData(saved_val)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                self.table.setCellWidget(row, 2, combo)
            else:
                txt = '' if saved_val is None else format(float(saved_val), '.6g')
                self.table.setItem(row, 2, QTableWidgetItem(txt))

        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = _footer(self, layout, self.validate)

    def validate(self):
        try:
            hold_values = []
            predictors = self.bundle['predictors'] if self.bundle else []
            for row, pred in enumerate(predictors):
                widget = self.table.cellWidget(row, 2)
                if widget is not None:
                    val = widget.currentData()
                    if val is not None:
                        hold_values.append(dict(index=pred['index'], value=val))
                else:
                    item = self.table.item(row, 2)
                    txt = item.text().strip() if item else ''
                    if txt:
                        num = float(txt)
                        if not math.isfinite(num):
                            raise ValueError(f"Hold value for {pred['name']} must be finite.")
                        hold_values.append(dict(index=pred['index'], value=num))
            updated = dict(
                self.initial,
                title=self.title_edit.text().strip(),
                hold_continuous=self.hold_cont.currentData(),
                hold_categorical=self.hold_cat.currentData(),
                hold_values=hold_values,
            )
            self.options = factorial_plots_settings(updated)
        except (ValueError, TypeError, OverflowError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()


class FactorialPlotsDialog(QDialog):
    """Main dialog for Factorial Plots across all 5 fitted model families."""

    def __init__(self, window, family=None):
        super().__init__(window)
        self.window = window
        self.worksheet = window.presenter.worksheet
        self.family = family
        self.entry = None
        self.model_recipe = None
        self.bundle = None
        self.models = []
        self.options = factorial_plots_settings()

        self.setWindowTitle('Factorial Plots')
        self.resize(720, 440)

        layout = QVBoxLayout(self)
        top_form = QFormLayout()
        self.model_selector = QComboBox()
        self.response = self.model_selector
        top_form.addRow('Response:', self.model_selector)
        layout.addLayout(top_form)

        lists_row = QHBoxLayout()
        avail_col = QVBoxLayout()
        avail_col.addWidget(QLabel('Available:'))
        self.available = QListWidget()
        avail_col.addWidget(self.available)
        lists_row.addLayout(avail_col, 1)

        mid_col = QVBoxLayout()
        mid_col.addStretch(1)
        self.add_one_button = QPushButton('>')
        self.add_all_button = QPushButton('>>')
        self.remove_one_button = QPushButton('<')
        self.remove_all_button = QPushButton('<<')
        for btn, fn in [
            (self.add_one_button, self.add_selected),
            (self.add_all_button, self.add_all),
            (self.remove_one_button, self.remove_selected),
            (self.remove_all_button, self.remove_all),
        ]:
            btn.setAutoDefault(False)
            btn.setFixedWidth(44)
            btn.clicked.connect(fn)
            mid_col.addWidget(btn)
        mid_col.addStretch(1)
        lists_row.addLayout(mid_col)

        sel_col = QVBoxLayout()
        sel_col.addWidget(QLabel('Selected:'))
        self.selected = QListWidget()
        sel_col.addWidget(self.selected)
        lists_row.addLayout(sel_col, 1)

        self.available.itemDoubleClicked.connect(lambda _: self.add_selected())
        self.selected.itemDoubleClicked.connect(lambda _: self.remove_selected())
        layout.addLayout(lists_row)

        tools = QHBoxLayout()
        for attr, label, cb in [
            ('graphs_button', 'Graphs…', self.configure_graphs),
            ('options_button', 'Options…', self.configure_options),
            ('model_button', 'View Model…', self.view_model),
        ]:
            btn = QPushButton(label)
            btn.setAutoDefault(False)
            btn.clicked.connect(cb)
            setattr(self, attr, btn)
            tools.addWidget(btn)
        tools.addStretch(1)
        layout.addLayout(tools)

        note = QLabel(
            'Displays Main Effects and Interaction plots of fitted response means '
            '(or probabilities) across selected model variables.'
        )
        note.setObjectName('secondary')
        note.setWordWrap(True)
        layout.addWidget(note)

        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = _footer(self, layout, self.validate)

        self.load_models()
        self.model_selector.currentIndexChanged.connect(self.change_model)
        self.change_model()
        self.restore_previous()

    def load_models(self):
        worksheet_history = [
            e for e in self.window.presenter.history
            if not e.get('source_unavailable') and self._is_active_sheet(e)
        ]
        self.models = discover_models(
            self.worksheet,
            worksheet_history,
            family=self.family,
            require_two_continuous=False,
        )
        for idx, item in enumerate(self.models):
            lbl = f"{item['response_name']} — {item['model_title']} ({idx + 1})"
            self.model_selector.addItem(lbl, idx)
        if self.models:
            self.model_selector.setCurrentIndex(len(self.models) - 1)

    def _is_active_sheet(self, entry):
        try:
            return self.window.presenter.result_worksheet(entry) is self.worksheet
        except ValueError:
            return False

    def change_model(self):
        idx = self.model_selector.currentData()
        self.error.clear()
        self.available.clear()
        self.selected.clear()
        if idx is None or not (0 <= idx < len(self.models)):
            self.model_recipe = None
            self.bundle = None
            self.error.setText('Fit a supported model in this worksheet before creating Factorial Plots.')
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return
        item = self.models[idx]
        self.model_recipe = copy.deepcopy(item['recipe'])
        self.bundle = item['bundle']
        for pred in self.bundle['predictors']:
            lw_item = QListWidgetItem(format_variable_reference(pred['index'], self.worksheet))
            lw_item.setData(Qt.ItemDataRole.UserRole, pred['index'])
            self.selected.addItem(lw_item)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _move_item(self, source, dest, row):
        if not (0 <= row < source.count()):
            return
        item = source.takeItem(row)
        dest.addItem(item)

    def add_selected(self):
        row = self.available.currentRow()
        if row < 0 and self.available.count():
            row = 0
        self._move_item(self.available, self.selected, row)

    def add_all(self):
        while self.available.count():
            self._move_item(self.available, self.selected, 0)

    def remove_selected(self):
        row = self.selected.currentRow()
        if row < 0 and self.selected.count():
            row = 0
        self._move_item(self.selected, self.available, row)

    def remove_all(self):
        while self.selected.count():
            self._move_item(self.selected, self.available, 0)

    def selected_indices(self):
        return [
            self.selected.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.selected.count())
        ]

    def set_selected_indices(self, indices):
        if not self.bundle:
            return
        wanted = list(indices or [])
        self.available.clear()
        self.selected.clear()
        pred_map = {p['index']: p for p in self.bundle['predictors']}
        for col_idx in wanted:
            if col_idx in pred_map:
                lw_item = QListWidgetItem(format_variable_reference(col_idx, self.worksheet))
                lw_item.setData(Qt.ItemDataRole.UserRole, col_idx)
                self.selected.addItem(lw_item)
        for pred in self.bundle['predictors']:
            if pred['index'] not in wanted:
                lw_item = QListWidgetItem(format_variable_reference(pred['index'], self.worksheet))
                lw_item.setData(Qt.ItemDataRole.UserRole, pred['index'])
                self.available.addItem(lw_item)

    def configure_graphs(self):
        dialog = FactorialPlotsGraphsDialog(self, self.options)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.options = dialog.options

    def configure_options(self):
        dialog = FactorialPlotsOptionsDialog(self, self.worksheet, self.bundle, self.options)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.options = dialog.options

    def model_description(self):
        return _model_description(self.worksheet, self.model_recipe, self.bundle)

    def view_model(self):
        _show_view_model_dialog(
            self, 'Factorial Plots: View Model', self.worksheet, self.model_recipe, self.bundle
        )

    def restore_previous(self):
        for entry in reversed(self.window.presenter.history):
            if entry.get('source_unavailable') or entry.get('recipe', {}).get('action') != 'factorial_plots':
                continue
            try:
                if not self._is_active_sheet(entry):
                    continue
                p = entry['recipe']['parameters']
                canonical = normalize_model_recipe(p['model_recipe'])
                idx = next(i for i, m in enumerate(self.models) if m['recipe'] == canonical)
                opts = factorial_plots_settings(p.get('options'))
                self.model_selector.setCurrentIndex(idx)
                self.options = opts
                if p.get('selected_indices'):
                    self.set_selected_indices(p['selected_indices'])
                break
            except (ValueError, TypeError, KeyError, IndexError, StopIteration):
                continue

    def validate(self):
        try:
            if not self.bundle or not self.model_recipe:
                raise ValueError('Fit a supported model in this worksheet before creating Factorial Plots.')
            sel = self.selected_indices()
            if not sel:
                raise ValueError('Select at least one model variable for Factorial Plots.')
            entry = self.window.presenter.factorial_plots(
                copy.deepcopy(self.model_recipe),
                selected_indices=sel,
                options=self.options,
            )
            self.entry = entry
            self.window.refresh()
            self.window.show_result(entry)
        except (ValueError, TypeError, KeyError, IndexError, ArithmeticError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()


class ContourLevelsDialog(QDialog):
    """Subdialog matching REGRCONTOURPLOTCONTOURS."""

    def __init__(self, parent, options):
        super().__init__(parent)
        self.setWindowTitle('Contour Plot: Contours')
        self.initial = contour_plot_settings(options)
        self.options = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.display_mode = QComboBox()
        self.display_mode.addItem('Area and contour lines', ('area_lines', True, True))
        self.display_mode.addItem('Area only', ('area', True, False))
        self.display_mode.addItem('Contour lines only', ('lines', False, True))
        if self.initial['show_area'] and self.initial['show_lines']:
            self.display_mode.setCurrentIndex(0)
        elif self.initial['show_area']:
            self.display_mode.setCurrentIndex(1)
        else:
            self.display_mode.setCurrentIndex(2)
        form.addRow('Display:', self.display_mode)

        self.design_points = QCheckBox('Show design points on plot')
        self.design_points.setChecked(self.initial.get('show_design_points', False))
        form.addRow('', self.design_points)

        self.level_mode = QComboBox()
        self.level_mode.addItem('Automatic', 'auto')
        self.level_mode.addItem('Number of levels', 'number')
        self.level_mode.addItem('Custom values', 'values')
        self.level_mode.setCurrentIndex(
            max(0, self.level_mode.findData(self.initial['level_mode']))
        )
        form.addRow('Contour levels:', self.level_mode)

        self.level_count = QLineEdit(str(self.initial['level_count']))
        form.addRow('Number (2–20):', self.level_count)

        vals_str = ' '.join(format(float(v), '.6g') for v in self.initial.get('custom_levels', []))
        self.level_values = QLineEdit(vals_str)
        self.level_values.setPlaceholderText('e.g. 50 60 70 80 90')
        form.addRow('Values:', self.level_values)
        layout.addLayout(form)

        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = _footer(self, layout, self.validate)

    def validate(self):
        try:
            _, show_area, show_lines = self.display_mode.currentData()
            mode = self.level_mode.currentData()
            count = int(self.level_count.text().strip() or '7')
            raw_vals = self.level_values.text().replace(',', ' ').split()
            vals = [float(tok) for tok in raw_vals] if mode == 'values' else self.initial.get('custom_levels', [])
            updated = dict(
                self.initial,
                show_area=show_area,
                show_lines=show_lines,
                show_design_points=self.design_points.isChecked(),
                level_mode=mode,
                level_count=count,
                custom_levels=vals,
            )
            self.options = contour_plot_settings(updated)
        except (ValueError, TypeError, OverflowError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()


class ContourOptionsDialog(QDialog):
    """Subdialog for Contour Plot title."""

    def __init__(self, parent, options):
        super().__init__(parent)
        self.setWindowTitle('Contour Plot: Options')
        self.initial = contour_plot_settings(options)
        self.options = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title_edit = QLineEdit(self.initial.get('title', ''))
        form.addRow('Title:', self.title_edit)
        layout.addLayout(form)

        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = _footer(self, layout, self.validate)

    def validate(self):
        try:
            updated = dict(
                self.initial,
                title=self.title_edit.text().strip(),
            )
            self.options = contour_plot_settings(updated)
        except (ValueError, TypeError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()


class ModelContourPlotDialog(QDialog):
    """Main dialog for Model-Driven Contour Plot across all 5 fitted model families."""

    def __init__(self, window, family=None):
        super().__init__(window)
        self.window = window
        self.worksheet = window.presenter.worksheet
        self.family = family
        self.entry = None
        self.model_recipe = None
        self.bundle = None
        self.models = []
        self.options = contour_plot_settings()

        self.setWindowTitle('Contour Plot')
        self.resize(620, 390)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.model_selector = QComboBox()
        self.response = self.model_selector
        form.addRow('Response:', self.model_selector)

        self.pair_mode = QComboBox()
        self.pair_mode.addItem('Generate plots for a single pair', 'single')
        self.pair_mode.addItem('Generate plots for all pairs of continuous variables', 'all')
        form.addRow('Variables:', self.pair_mode)

        self.x_combo = QComboBox()
        form.addRow('X Axis:', self.x_combo)
        self.y_combo = QComboBox()
        form.addRow('Y Axis:', self.y_combo)
        layout.addLayout(form)

        tools = QHBoxLayout()
        for attr, label, cb in [
            ('contours_button', 'Contours…', self.configure_contours),
            ('settings_button', 'Settings…', self.configure_settings),
            ('options_button', 'Options…', self.configure_options),
            ('model_button', 'View Model…', self.view_model),
        ]:
            btn = QPushButton(label)
            btn.setAutoDefault(False)
            btn.clicked.connect(cb)
            setattr(self, attr, btn)
            tools.addWidget(btn)
        tools.addStretch(1)
        layout.addLayout(tools)

        note = QLabel(
            'Evaluates fitted response contours across two continuous model predictors '
            'while holding any remaining predictors at fixed settings.'
        )
        note.setObjectName('secondary')
        note.setWordWrap(True)
        layout.addWidget(note)

        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = _footer(self, layout, self.validate)

        self.load_models()
        self.model_selector.currentIndexChanged.connect(self.change_model)
        self.pair_mode.currentIndexChanged.connect(self.change_pair_mode)
        self.change_model()
        self.restore_previous()

    def _is_active_sheet(self, entry):
        try:
            return self.window.presenter.result_worksheet(entry) is self.worksheet
        except ValueError:
            return False

    def load_models(self):
        worksheet_history = [
            e for e in self.window.presenter.history
            if not e.get('source_unavailable') and self._is_active_sheet(e)
        ]
        self.models = discover_models(
            self.worksheet,
            worksheet_history,
            family=self.family,
            require_two_continuous=True,
        )
        for idx, item in enumerate(self.models):
            lbl = f"{item['response_name']} — {item['model_title']} ({idx + 1})"
            self.model_selector.addItem(lbl, idx)
        if self.models:
            self.model_selector.setCurrentIndex(len(self.models) - 1)

    def change_model(self):
        idx = self.model_selector.currentData()
        self.error.clear()
        self.x_combo.clear()
        self.y_combo.clear()
        if idx is None or not (0 <= idx < len(self.models)):
            self.model_recipe = None
            self.bundle = None
            self.error.setText(
                'Fit a supported model with at least two continuous predictors before creating a Contour Plot.'
            )
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return
        item = self.models[idx]
        self.model_recipe = copy.deepcopy(item['recipe'])
        self.bundle = item['bundle']
        cont_preds = [p for p in self.bundle['predictors'] if p['role'] == 'covariate']
        for pred in cont_preds:
            ref = format_variable_reference(pred['index'], self.worksheet)
            self.x_combo.addItem(ref, pred['index'])
            self.y_combo.addItem(ref, pred['index'])
        if len(cont_preds) >= 2:
            self.x_combo.setCurrentIndex(0)
            self.y_combo.setCurrentIndex(1)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        self.change_pair_mode()

    def change_pair_mode(self):
        single = self.pair_mode.currentData() == 'single'
        self.x_combo.setEnabled(single and self.bundle is not None)
        self.y_combo.setEnabled(single and self.bundle is not None)
        self.options['pair_mode'] = self.pair_mode.currentData()

    def configure_contours(self):
        dialog = ContourLevelsDialog(self, self.options)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.options = dialog.options

    def configure_settings(self):
        dialog = HoldSettingsDialog(
            self,
            'Contour Plot: Settings',
            self.worksheet,
            self.bundle,
            self.options,
            contour_plot_settings,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.options = dialog.options

    def configure_options(self):
        dialog = ContourOptionsDialog(self, self.options)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.options = dialog.options

    def model_description(self):
        return _model_description(self.worksheet, self.model_recipe, self.bundle)

    def view_model(self):
        _show_view_model_dialog(
            self, 'Contour Plot: View Model', self.worksheet, self.model_recipe, self.bundle
        )

    def restore_previous(self):
        for entry in reversed(self.window.presenter.history):
            if entry.get('source_unavailable') or entry.get('recipe', {}).get('action') != 'model_contour_plot':
                continue
            try:
                if not self._is_active_sheet(entry):
                    continue
                p = entry['recipe']['parameters']
                canonical = normalize_model_recipe(p['model_recipe'])
                idx = next(i for i, m in enumerate(self.models) if m['recipe'] == canonical)
                opts = contour_plot_settings(p.get('options'))
                self.model_selector.setCurrentIndex(idx)
                self.options = opts
                self.pair_mode.setCurrentIndex(
                    max(0, self.pair_mode.findData(opts.get('pair_mode', 'single')))
                )
                if p.get('x_index') is not None:
                    xi = self.x_combo.findData(p['x_index'])
                    if xi >= 0:
                        self.x_combo.setCurrentIndex(xi)
                if p.get('y_index') is not None:
                    yi = self.y_combo.findData(p['y_index'])
                    if yi >= 0:
                        self.y_combo.setCurrentIndex(yi)
                break
            except (ValueError, TypeError, KeyError, IndexError, StopIteration):
                continue

    def validate(self):
        try:
            if not self.bundle or not self.model_recipe:
                raise ValueError(
                    'Fit a supported model with at least two continuous predictors before creating a Contour Plot.'
                )
            self.options['pair_mode'] = self.pair_mode.currentData()
            x_idx = self.x_combo.currentData() if self.options['pair_mode'] == 'single' else None
            y_idx = self.y_combo.currentData() if self.options['pair_mode'] == 'single' else None
            entry = self.window.presenter.model_contour_plot(
                copy.deepcopy(self.model_recipe),
                x_index=x_idx,
                y_index=y_idx,
                options=self.options,
            )
            self.entry = entry
            self.window.refresh()
            self.window.show_result(entry)
        except (ValueError, TypeError, KeyError, IndexError, ArithmeticError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()


class SurfaceOptionsDialog(QDialog):
    """Subdialog matching REGRSURFACEPLOTOPTIONS."""

    def __init__(self, parent, options):
        super().__init__(parent)
        self.setWindowTitle('Surface Plot: Options')
        self.initial = surface_plot_settings(options)
        self.options = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.style_combo = QComboBox()
        self.style_combo.addItem('Shaded surface', 'shaded')
        self.style_combo.addItem('Wireframe', 'wireframe')
        self.style_combo.setCurrentIndex(
            max(0, self.style_combo.findData(self.initial.get('surface_style', 'shaded')))
        )
        form.addRow('Surface style:', self.style_combo)

        self.title_edit = QLineEdit(self.initial.get('title', ''))
        form.addRow('Title:', self.title_edit)
        layout.addLayout(form)

        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = _footer(self, layout, self.validate)

    def validate(self):
        try:
            updated = dict(
                self.initial,
                surface_style=self.style_combo.currentData(),
                title=self.title_edit.text().strip(),
            )
            self.options = surface_plot_settings(updated)
        except (ValueError, TypeError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()


class ModelSurfacePlotDialog(QDialog):
    """Main dialog for Model-Driven 3D Surface Plot across all 5 fitted model families."""

    def __init__(self, window, family=None):
        super().__init__(window)
        self.window = window
        self.worksheet = window.presenter.worksheet
        self.family = family
        self.entry = None
        self.model_recipe = None
        self.bundle = None
        self.models = []
        self.options = surface_plot_settings()

        self.setWindowTitle('Surface Plot')
        self.resize(620, 400)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.model_selector = QComboBox()
        self.response = self.model_selector
        form.addRow('Response:', self.model_selector)

        self.pair_mode = QComboBox()
        self.pair_mode.addItem('Generate plots for a single pair', 'single')
        self.pair_mode.addItem('Generate plots for all pairs of continuous variables', 'all')
        form.addRow('Variables:', self.pair_mode)

        self.x_combo = QComboBox()
        form.addRow('X Axis:', self.x_combo)
        self.y_combo = QComboBox()
        form.addRow('Y Axis:', self.y_combo)

        self.style_combo = QComboBox()
        self.style_combo.addItem('Shaded surface', 'shaded')
        self.style_combo.addItem('Wireframe', 'wireframe')
        form.addRow('Surface style:', self.style_combo)
        layout.addLayout(form)

        tools = QHBoxLayout()
        for attr, label, cb in [
            ('settings_button', 'Settings…', self.configure_settings),
            ('options_button', 'Options…', self.configure_options),
            ('model_button', 'View Model…', self.view_model),
        ]:
            btn = QPushButton(label)
            btn.setAutoDefault(False)
            btn.clicked.connect(cb)
            setattr(self, attr, btn)
            tools.addWidget(btn)
        tools.addStretch(1)
        layout.addLayout(tools)

        note = QLabel(
            'Evaluates 3D fitted response surfaces across two continuous model predictors '
            'while holding any remaining predictors at fixed settings.'
        )
        note.setObjectName('secondary')
        note.setWordWrap(True)
        layout.addWidget(note)

        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = _footer(self, layout, self.validate)

        self.load_models()
        self.model_selector.currentIndexChanged.connect(self.change_model)
        self.pair_mode.currentIndexChanged.connect(self.change_pair_mode)
        self.style_combo.currentIndexChanged.connect(self.change_style)
        self.change_model()
        self.restore_previous()

    def _is_active_sheet(self, entry):
        try:
            return self.window.presenter.result_worksheet(entry) is self.worksheet
        except ValueError:
            return False

    def load_models(self):
        worksheet_history = [
            e for e in self.window.presenter.history
            if not e.get('source_unavailable') and self._is_active_sheet(e)
        ]
        self.models = discover_models(
            self.worksheet,
            worksheet_history,
            family=self.family,
            require_two_continuous=True,
        )
        for idx, item in enumerate(self.models):
            lbl = f"{item['response_name']} — {item['model_title']} ({idx + 1})"
            self.model_selector.addItem(lbl, idx)
        if self.models:
            self.model_selector.setCurrentIndex(len(self.models) - 1)

    def change_model(self):
        idx = self.model_selector.currentData()
        self.error.clear()
        self.x_combo.clear()
        self.y_combo.clear()
        if idx is None or not (0 <= idx < len(self.models)):
            self.model_recipe = None
            self.bundle = None
            self.error.setText(
                'Fit a supported model with at least two continuous predictors before creating a Surface Plot.'
            )
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return
        item = self.models[idx]
        self.model_recipe = copy.deepcopy(item['recipe'])
        self.bundle = item['bundle']
        cont_preds = [p for p in self.bundle['predictors'] if p['role'] == 'covariate']
        for pred in cont_preds:
            ref = format_variable_reference(pred['index'], self.worksheet)
            self.x_combo.addItem(ref, pred['index'])
            self.y_combo.addItem(ref, pred['index'])
        if len(cont_preds) >= 2:
            self.x_combo.setCurrentIndex(0)
            self.y_combo.setCurrentIndex(1)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        self.change_pair_mode()

    def change_pair_mode(self):
        single = self.pair_mode.currentData() == 'single'
        self.x_combo.setEnabled(single and self.bundle is not None)
        self.y_combo.setEnabled(single and self.bundle is not None)
        self.options['pair_mode'] = self.pair_mode.currentData()

    def change_style(self):
        self.options['surface_style'] = self.style_combo.currentData()

    def configure_settings(self):
        dialog = HoldSettingsDialog(
            self,
            'Surface Plot: Settings',
            self.worksheet,
            self.bundle,
            self.options,
            surface_plot_settings,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.options = dialog.options

    def configure_options(self):
        dialog = SurfaceOptionsDialog(self, self.options)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.options = dialog.options
            idx = self.style_combo.findData(self.options.get('surface_style', 'shaded'))
            if idx >= 0:
                self.style_combo.setCurrentIndex(idx)

    def model_description(self):
        return _model_description(self.worksheet, self.model_recipe, self.bundle)

    def view_model(self):
        _show_view_model_dialog(
            self, 'Surface Plot: View Model', self.worksheet, self.model_recipe, self.bundle
        )

    def restore_previous(self):
        for entry in reversed(self.window.presenter.history):
            if entry.get('source_unavailable') or entry.get('recipe', {}).get('action') != 'model_surface_plot':
                continue
            try:
                if not self._is_active_sheet(entry):
                    continue
                p = entry['recipe']['parameters']
                canonical = normalize_model_recipe(p['model_recipe'])
                idx = next(i for i, m in enumerate(self.models) if m['recipe'] == canonical)
                opts = surface_plot_settings(p.get('options'))
                self.model_selector.setCurrentIndex(idx)
                self.options = opts
                self.pair_mode.setCurrentIndex(
                    max(0, self.pair_mode.findData(opts.get('pair_mode', 'single')))
                )
                self.style_combo.setCurrentIndex(
                    max(0, self.style_combo.findData(opts.get('surface_style', 'shaded')))
                )
                if p.get('x_index') is not None:
                    xi = self.x_combo.findData(p['x_index'])
                    if xi >= 0:
                        self.x_combo.setCurrentIndex(xi)
                if p.get('y_index') is not None:
                    yi = self.y_combo.findData(p['y_index'])
                    if yi >= 0:
                        self.y_combo.setCurrentIndex(yi)
                break
            except (ValueError, TypeError, KeyError, IndexError, StopIteration):
                continue

    def validate(self):
        try:
            if not self.bundle or not self.model_recipe:
                raise ValueError(
                    'Fit a supported model with at least two continuous predictors before creating a Surface Plot.'
                )
            self.options['pair_mode'] = self.pair_mode.currentData()
            self.options['surface_style'] = self.style_combo.currentData()
            x_idx = self.x_combo.currentData() if self.options['pair_mode'] == 'single' else None
            y_idx = self.y_combo.currentData() if self.options['pair_mode'] == 'single' else None
            entry = self.window.presenter.model_surface_plot(
                copy.deepcopy(self.model_recipe),
                x_index=x_idx,
                y_index=y_idx,
                options=self.options,
            )
            self.entry = entry
            self.window.refresh()
            self.window.show_result(entry)
        except (ValueError, TypeError, KeyError, IndexError, ArithmeticError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()
