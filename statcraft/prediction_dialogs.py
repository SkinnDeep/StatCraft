"""Native-informed Predict dialogs for independently fitted current-data models.

Form evidence: PREDICTMAIN, PREDICTMAINGLM, PREDICTMAINRESPSURF,
PREDICTOPTIONS and PREDICTRESULTS resources; unsupported buttons are omitted.
"""
import copy
import math
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton, QDialogButtonBox,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem, QStackedWidget,
    QHeaderView, QTextEdit)
from .prediction import settings, model_spec, normalize_recipe
from .variable_dialogs import format_variable_reference, resolve_variables


def footer(dialog, layout, callback):
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(callback)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    return buttons


class PredictOptionsDialog(QDialog):
    def __init__(self, parent, options):
        self.setSizeGripEnabled(True)
        super().__init__(parent)
        self.setWindowTitle('Predict: Options')
        self.options = None
        self.initial = settings(options)
        layout = QVBoxLayout(self); form = QFormLayout()
        self.confidence = QLineEdit(format(100*self.initial['confidence'], '.12g'))
        form.addRow('Confidence level:', self.confidence)
        self.side = QComboBox()
        for label, value in [('Two-sided', 'two_sided'), ('Lower bound', 'lower'), ('Upper bound', 'upper')]:
            self.side.addItem(label, value)
        self.side.setCurrentIndex(self.side.findData(self.initial.get('side', 'two_sided')))
        form.addRow('Type of interval:', self.side)
        self.intervals = QComboBox()
        for label, value in [('Confidence and prediction', 'both'), ('Confidence', 'confidence'),
                             ('Prediction', 'prediction'), ('None', 'none')]:
            self.intervals.addItem(label, value)
        self.intervals.setCurrentIndex(self.intervals.findData(self.initial['intervals']))
        form.addRow('Intervals to display:', self.intervals)
        layout.addLayout(form)
        self.error = QLabel(); self.error.setObjectName('error'); self.error.setWordWrap(True)
        layout.addWidget(self.error); self.buttons = footer(self, layout, self.validate)

    def validate(self):
        try:
            options = dict(self.initial, confidence=float(self.confidence.text())/100,
                           side=self.side.currentData(), intervals=self.intervals.currentData())
            self.options = settings(options)
        except (ValueError, TypeError, OverflowError) as exc:
            self.error.setText(str(exc)); return
        self.accept()


class PredictResultsDialog(QDialog):
    def __init__(self, parent, options):
        self.setSizeGripEnabled(True)
        super().__init__(parent)
        self.setWindowTitle('Predict: Results')
        self.initial = settings(options); self.options = None
        layout = QVBoxLayout(self)
        self.equation = QCheckBox('Regression equation')
        self.table = QCheckBox('Prediction table')
        self.equation.setChecked(self.initial['show_equation'])
        self.table.setChecked(self.initial['show_table'])
        layout.addWidget(self.equation); layout.addWidget(self.table)
        self.buttons = footer(self, layout, self.validate)

    def validate(self):
        self.options = settings(dict(self.initial, show_equation=self.equation.isChecked(),
                                     show_table=self.table.isChecked()))
        self.accept()


class PredictDialog(QDialog):
    MAX_MANUAL_ROWS = 500
    FAMILIES = {'regression': ('multiple_regression',), 'glm': ('general_linear_model',),
                'response_surface': ('analyze_response_surface',), 'logistic': ('fit_binary_logistic',),
                'factorial': ('analyze_factorial', 'analyze_factorial_terms')}

    def __init__(self, window, family=None):
        self.setSizeGripEnabled(True)
        super().__init__(window)
        self.window = window; self.worksheet = window.presenter.worksheet
        self.family = family; self.entry = None; self.model_recipe = None; self.spec = None
        self.options = settings(); self.models = []; self.active_column = 0; self._building = False
        self.setWindowTitle('Predict'); self.resize(790, 480)
        layout = QVBoxLayout(self); body = QHBoxLayout(); left = QVBoxLayout()
        left.addWidget(QLabel('Available variables'))
        self.available = QListWidget(); self.available.setMinimumWidth(210)
        left.addWidget(self.available)
        self.select_button = QPushButton('Select'); self.select_button.setAutoDefault(False)
        self.select_button.clicked.connect(self.transfer)
        self.available.itemDoubleClicked.connect(lambda item: self.transfer())
        left.addWidget(self.select_button); body.addLayout(left, 1)
        right = QVBoxLayout(); form = QFormLayout()
        self.model_selector = QComboBox(); self.response = self.model_selector
        form.addRow('Response:', self.model_selector)
        self.input_mode = QComboBox()
        self.input_mode.addItem('Enter individual values', 'values')
        self.input_mode.addItem('Enter columns of values', 'columns')
        form.addRow('', self.input_mode); right.addLayout(form)
        self.values_grid = QTableWidget(8, 0)
        self.columns_grid = QTableWidget(1, 0)
        self.values_grid.itemChanged.connect(lambda item: self.ensure_blank_row())
        for grid in (self.values_grid, self.columns_grid):
            grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            grid.setMinimumHeight(180)
            grid.currentCellChanged.connect(lambda row, col, oldrow, oldcol: self.activate_column(col))
        self.stack = QStackedWidget(); self.stack.addWidget(self.values_grid); self.stack.addWidget(self.columns_grid)
        right.addWidget(self.stack)
        self.clear_button = QPushButton('Clear Row'); self.clear_button.setAutoDefault(False)
        self.clear_button.clicked.connect(self.clear_row)
        right.addWidget(self.clear_button)
        tools = QHBoxLayout()
        for attr, label, callback in [('options_button', 'Options…', self.configure_options),
                                      ('results_button', 'Results…', self.configure_results),
                                      ('model_button', 'View Model…', self.view_model)]:
            button = QPushButton(label); button.setAutoDefault(False); button.clicked.connect(callback)
            setattr(self, attr, button); tools.addWidget(button)
        right.addLayout(tools); body.addLayout(right, 2); layout.addLayout(body)
        note = QLabel('Uses current worksheet data and the selected model setup. '
                      'Enter up to 500 rows manually. For larger input sets, select worksheet columns.')
        note.setObjectName('secondary'); note.setWordWrap(True); layout.addWidget(note)
        self.error = QLabel(); self.error.setObjectName('error'); self.error.setWordWrap(True)
        layout.addWidget(self.error); self.buttons = footer(self, layout, self.validate)
        self.load_models()
        self.model_selector.currentIndexChanged.connect(self.change_model)
        self.input_mode.currentIndexChanged.connect(self.change_mode)
        self.change_model(); self.restore_previous()

    def load_models(self):
        actions = self.FAMILIES.get(self.family)
        if isinstance(actions, str):
            actions = (actions,)
        for entry in self.window.presenter.history:
            if entry.get('source_unavailable'):
                continue
            try:
                from .native_mpx_models import resolve_entry_recipe
                source_recipe = resolve_entry_recipe(entry, self.worksheet)
                if not source_recipe:
                    continue
                if source_recipe.get('action') == 'predict_model':
                    source_recipe = source_recipe['parameters']['model_recipe']
                recipe = normalize_recipe(source_recipe)
                if actions and recipe['action'] not in actions:
                    continue
                if self.window.presenter.result_worksheet(entry) is not self.worksheet:
                    continue
                response = recipe['parameters']['response_index']
                if type(response) is not int or not 0 <= response < len(self.worksheet.columns):
                    continue
                name = self.worksheet.columns[response].name
                title = {'multiple_regression': 'Multiple Regression',
                         'general_linear_model': 'General Linear Model',
                         'analyze_response_surface': 'Response Surface Regression',
                         'fit_binary_logistic': 'Binary Logistic Regression',
                         'analyze_factorial': 'Factorial Regression',
                         'analyze_factorial_terms': 'Factorial Regression'}[recipe['action']]
                if any(model[1] == recipe for model in self.models):
                    continue
            except (ValueError, TypeError, KeyError, IndexError, ArithmeticError):
                continue
            index = len(self.models)
            self.models.append((entry, copy.deepcopy(recipe), None))
            self.model_selector.addItem(f'{name} — {title} ({index+1})', index)
        if self.models:
            self.model_selector.setCurrentIndex(len(self.models)-1)

    def change_model(self):
        index = self.model_selector.currentData()
        self.error.clear()
        if index is None:
            self.model_recipe = None; self.spec = None
            self.error.setText('Fit a supported model in this worksheet before predicting.')
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            self.available.clear(); return
        entry, self.model_recipe, self.spec = self.models[index]
        if self.model_recipe['action']=='fit_binary_logistic' and self.options['intervals'] not in ('confidence','none'):self.options['intervals']='confidence'
        if self.spec is None:
            try:
                self.spec = model_spec(self.worksheet, self.model_recipe)
                self.models[index] = (entry, self.model_recipe, self.spec)
            except (ValueError, TypeError, KeyError, IndexError, ArithmeticError) as exc:
                self.spec = None
                self.error.setText(str(exc))
                self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
                self.available.clear(); self.change_mode(); return
        self._building = True
        labels = [format_variable_reference(p['index'], self.worksheet) for p in self.spec['predictors']]
        for grid in (self.values_grid, self.columns_grid):
            for row in range(grid.rowCount()):
                for col in range(grid.columnCount()):
                    if grid.cellWidget(row, col) is not None:
                        grid.removeCellWidget(row, col)
            grid.clear(); grid.setColumnCount(len(labels)); grid.setHorizontalHeaderLabels(labels)
            grid.setRowCount(8 if grid is self.values_grid else 1)
            for col, label in enumerate(labels):
                grid.horizontalHeaderItem(col).setToolTip(label)
                grid.setColumnWidth(col, max(150, min(260, len(label)*8)))
            grid.setCurrentCell(0, 0)
        for row in range(self.values_grid.rowCount()):
            self.prepare_row(row)
        self._building = False
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        self.activate_column(0); self.change_mode()

    def prepare_row(self, row):
        for col, predictor in enumerate(self.spec['predictors']):
            if predictor['role'] == 'factor' and predictor['levels']:
                combo = QComboBox(); combo.addItem('', None)
                for level in predictor['levels']:
                    combo.addItem(str(level), level)
                self.values_grid.setCellWidget(row, col, combo)
                combo.currentIndexChanged.connect(lambda index: self.ensure_blank_row())

    def ensure_blank_row(self):
        if self._building or not self.spec or not self.values_grid.columnCount():
            return
        row = self.values_grid.rowCount()-1
        occupied = any((self.values_grid.cellWidget(row, col).currentData() is not None
                        if self.values_grid.cellWidget(row, col)
                        else bool(self.values_grid.item(row, col) and self.values_grid.item(row, col).text().strip()))
                       for col in range(self.values_grid.columnCount()))
        if occupied and self.values_grid.rowCount() < self.MAX_MANUAL_ROWS:
            self.values_grid.insertRow(row+1); self.prepare_row(row+1)

    def activate_column(self, col):
        if not self.spec or col < 0:
            return
        self.active_column = col; self.available.clear()
        kind = self.spec['predictors'][col]['kind']
        for i, column in enumerate(self.worksheet.columns):
            if column.kind == kind:
                item = QListWidgetItem(format_variable_reference(i, self.worksheet))
                item.setData(Qt.ItemDataRole.UserRole, i); self.available.addItem(item)

    def change_mode(self):
        columns = self.input_mode.currentData() == 'columns'
        self.stack.setCurrentIndex(int(columns)); self.select_button.setEnabled(columns and self.spec is not None)
        self.available.setEnabled(columns); self.clear_button.setEnabled(self.spec is not None)

    def transfer(self):
        if self.input_mode.currentData() != 'columns' or not self.spec:
            return
        item = self.available.currentItem()
        if item is None:
            return
        self.columns_grid.setItem(0, self.active_column, QTableWidgetItem(item.text()))
        self.columns_grid.setCurrentCell(0, self.active_column)

    def clear_row(self):
        grid = self.stack.currentWidget(); row = max(0, grid.currentRow())
        for col in range(grid.columnCount()):
            widget = grid.cellWidget(row, col)
            if widget:
                widget.setCurrentIndex(0)
            else:
                grid.setItem(row, col, QTableWidgetItem(''))

    def configure_options(self):
        dialog = PredictOptionsDialog(self, self.options)
        if self.model_recipe and self.model_recipe['action']=='fit_binary_logistic':
            for index in range(dialog.intervals.count()-1,-1,-1):
                if dialog.intervals.itemData(index) not in ('confidence','none'):dialog.intervals.removeItem(index)
            dialog.intervals.setCurrentIndex(dialog.intervals.findData(self.options['intervals']))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.options = dialog.options

    def configure_results(self):
        dialog = PredictResultsDialog(self, self.options)
        if self.model_recipe and self.model_recipe['action']=='fit_binary_logistic':dialog.equation.setText('Binary logistic regression equation')
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.options = dialog.options

    def model_description(self):
        if not self.spec:
            return 'No supported fitted model is available.'
        lines = [self.spec['model_title'], 'Response: '+self.spec['response_name'], '', 'Predictors:']
        for predictor in self.spec['predictors']:
            line = format_variable_reference(predictor['index'], self.worksheet)+' — '+predictor['role']
            if predictor['levels']:
                line += '; levels: '+', '.join(map(str, predictor['levels']))
            lines.append(line)
        terms = self.model_recipe['parameters'].get('terms')
        names = self.spec['predictor_names']
        lines.extend(['', 'Terms:'])
        if terms:
            lines.extend(' × '.join(names[i] for i in term) for term in terms)
        else:
            lines.extend(names)
        lines.extend(['', 'Refitted using the current worksheet data.'])
        return '\n'.join(lines)

    def view_model(self):
        dialog = QDialog(self); dialog.setWindowTitle('Predict: View Model'); dialog.resize(540, 370)
        layout = QVBoxLayout(dialog); text = QTextEdit(); text.setReadOnly(True)
        text.setPlainText(self.model_description()); layout.addWidget(text)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); close.rejected.connect(dialog.reject)
        layout.addWidget(close); dialog.exec()

    def read_inputs(self):
        if not self.spec:
            raise ValueError('Fit a supported model in this worksheet before predicting.')
        if self.input_mode.currentData() == 'columns':
            indices = []
            for col, predictor in enumerate(self.spec['predictors']):
                item = self.columns_grid.item(0, col)
                found = resolve_variables(item.text() if item else '', self.worksheet, (predictor['kind'],))
                if len(found) != 1:
                    raise ValueError('Choose one input column for '+predictor['name']+'.')
                indices.append(found[0])
            return None, indices
        rows = []
        if self.values_grid.rowCount() > self.MAX_MANUAL_ROWS:
            raise ValueError('Manual entry supports up to 500 rows. For larger input sets, select worksheet columns.')
        for row in range(self.values_grid.rowCount()):
            values = []
            for col, predictor in enumerate(self.spec['predictors']):
                widget = self.values_grid.cellWidget(row, col); item = self.values_grid.item(row, col)
                value = widget.currentData() if widget else (item.text().strip() if item else '')
                values.append(value)
            for col, predictor in enumerate(self.spec['predictors']):
                if values[col] is None or values[col] == '':
                    values[col] = None
                elif predictor['kind'] == 'number':
                    values[col] = float(values[col])
                    if not math.isfinite(values[col]):
                        raise ValueError('Prediction inputs must be finite numbers.')
            rows.append(values)
        while rows and all(value is None for value in rows[-1]):
            rows.pop()
        if not rows:
            raise ValueError('Enter at least one complete prediction row.')
        return rows, None

    def restore_previous(self):
        for entry in reversed(self.window.presenter.history):
            if entry.get('source_unavailable') or entry.get('recipe', {}).get('action') != 'predict_model':
                continue
            try:
                if self.window.presenter.result_worksheet(entry) is not self.worksheet:
                    continue
                p = entry['recipe']['parameters']; canonical = normalize_recipe(p['model_recipe'])
                index = next(i for i, model in enumerate(self.models) if model[1] == canonical)
                options = settings(p['options'])
                if p['input_mode'] not in ('values', 'columns'):
                    continue
                # Refit only the selected setup, never every history entry.
                self.model_selector.setCurrentIndex(index)
                if not self.spec:
                    continue
                predictors = self.spec['predictors']
                if p['input_mode'] == 'columns':
                    if len(p['new_indices']) != len(predictors):
                        continue
                    for col, i in enumerate(p['new_indices']):
                        if type(i) is not int or not 0 <= i < len(self.worksheet.columns) or self.worksheet.columns[i].kind != predictors[col]['kind']:
                            raise ValueError('Saved prediction input column is unavailable.')
                elif not isinstance(p['values'], list) or not 1 <= len(p['values']) <= 20000 or any(not isinstance(row, list) or len(row) != len(predictors) for row in p['values']):
                    continue
                elif len(p['values']) > self.MAX_MANUAL_ROWS:
                    self.change_model()
                    self.error.setText('This saved prediction has more than 500 manual rows. '
                                       'Its input rows have not been loaded. For larger input sets, select worksheet columns.')
                    return
                self.options = options
                self.input_mode.setCurrentIndex(self.input_mode.findData(p['input_mode']))
                if p['input_mode'] == 'columns':
                    if len(p['new_indices']) != len(self.spec['predictors']):
                        continue
                    for col, i in enumerate(p['new_indices']):
                        self.columns_grid.setItem(0, col, QTableWidgetItem(format_variable_reference(i, self.worksheet)))
                else:
                    self.values_grid.setRowCount(min(self.MAX_MANUAL_ROWS, max(8, len(p['values'])+1)))
                    for row in range(self.values_grid.rowCount()):
                        self.prepare_row(row)
                    for row, values in enumerate(p['values']):
                        for col, value in enumerate(values):
                            widget = self.values_grid.cellWidget(row, col)
                            if widget:
                                widget.setCurrentIndex(widget.findData(value))
                            else:
                                self.values_grid.setItem(row, col, QTableWidgetItem('' if value is None else str(value)))
                break
            except (ValueError, TypeError, KeyError, IndexError, StopIteration):
                continue

    def validate(self):
        try:
            values, indices = self.read_inputs()
            entry = self.window.presenter.predict_model(copy.deepcopy(self.model_recipe),
                input_mode=self.input_mode.currentData(), values=values, new_indices=indices, options=self.options)
            self.entry = entry; self.window.refresh(); self.window.show_result(entry)
        except (ValueError, TypeError, KeyError, IndexError, ArithmeticError) as exc:
            self.error.setText(str(exc)); return
        self.accept()


PredictionDialog = PredictDialog
