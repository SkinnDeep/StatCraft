"""Native-informed Response Optimizer dialogs for current-worksheet fitted models.

Form evidence: REGRESSIONOPTIMIZER, GLMOPTIMIZER, OPTIMIZERRESPSURF,
OPTIMIZERFACTORIAL, BINARYLOGISTICOPTIMIZER, REGROPTIMIZERSETUP,
BLOGOPTIMIZERSETUP, REGROPTIMIZEROPTIONS, FACTORIALOPTIMIZEROPTIONS,
GLMOPTIMIZEROPTIONS, REGROPTIMIZERGRAPHS and REGROPTIMIZEROUTPUT resources.
Unsupported storage controls are omitted.
"""
import copy
import math
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QCheckBox, QPushButton, QDialogButtonBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QTextEdit, QSpinBox, QWidget,
)
from .optimizer import (
    settings, discover_models, default_desirability, normalize_response_spec,
    individual_desirability, _merge_predictors,
)
from .variable_dialogs import format_variable_reference


def _footer(dialog, layout, callback):
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(callback)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    return buttons


def _fmt_num(val):
    if val is None:
        return ''
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return format(float(val), '.8g')
    return str(val)


class DesirabilityPreviewWidget(QWidget):
    """Mini Derringer-Suich desirability curve preview for the selected response row."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 120)
        self.spec = None

    def set_spec(self, spec):
        self.spec = spec
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        p.fillRect(rect, QColor('#ffffff'))
        p.setPen(QPen(QColor('#c6cfd6'), 1.0))
        p.drawRect(rect)
        if not self.spec:
            p.end()
            return
        goal = self.spec.get('goal')
        lo = self.spec.get('lower')
        t = self.spec.get('target')
        hi = self.spec.get('upper')
        w = self.spec.get('weight', 1.0)
        try:
            if goal == 'minimize':
                x0, x1 = float(t), float(hi)
            elif goal == 'maximize':
                x0, x1 = float(lo), float(t)
            else:
                x0, x1 = float(lo), float(hi)
            if x1 <= x0:
                p.end()
                return
            span = x1 - x0
            xa, xb = x0 - 0.15 * span, x1 + 0.15 * span
            plot = rect.adjusted(32, 18, -16, -24)
            xs = [xa + (xb - xa) * i / 80.0 for i in range(81)]
            ys = [individual_desirability(x, goal, lo, t, hi, w) for x in xs]
            x_px = lambda xv: plot.left() + (xv - xa) / (xb - xa) * plot.width()
            y_px = lambda yv: plot.bottom() - yv * plot.height()
            p.setPen(QPen(QColor('#dde3e8'), 1.0))
            p.drawLine(plot.bottomLeft(), plot.bottomRight())
            p.drawLine(plot.topLeft(), plot.bottomLeft())
            path = QPainterPath(QPointF(x_px(xs[0]), y_px(ys[0])))
            for xv, yv in zip(xs[1:], ys[1:]):
                path.lineTo(QPointF(x_px(xv), y_px(yv)))
            p.setPen(QPen(QColor('#056eb2'), 2.0))
            p.drawPath(path)
            p.setFont(QFont('Segoe UI', 8))
            p.setPen(QColor('#263440'))
            p.drawText(QRectF(plot.left(), rect.top() + 2, plot.width(), 14),
                       Qt.AlignmentFlag.AlignCenter,
                       f"{self.spec.get('response_name', 'Response')} ({goal.title()}, w={w:g})")
        except (ValueError, TypeError, ArithmeticError):
            pass
        p.end()


class OptimizerDesirabilityDialog(QDialog):
    """Response Optimizer: Desirability (`REGROPTIMIZERSETUP.MDF` / `BLOGOPTIMIZERSETUP.MDF`)."""
    def __init__(self, parent, worksheet, active_rows):
        super().__init__(parent)
        self.setWindowTitle('Response Optimizer: Desirability')
        self.resize(740, 380)
        self.worksheet = worksheet
        self.rows_data = copy.deepcopy(active_rows)
        self.result_rows = None
        self._building = True

        layout = QVBoxLayout(self)
        headers = ['Response', 'Goal', 'Lower', 'Target', 'Upper', 'Weight', 'Importance']
        self.table = QTableWidget(len(self.rows_data), len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r_i, item in enumerate(self.rows_data):
            goal = item['goal']
            goal_label = {'minimize': 'Minimize', 'target': 'Target', 'maximize': 'Maximize'}[goal]
            for c_i, text in enumerate([item['response_name'], goal_label]):
                cell = QTableWidgetItem(text)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r_i, c_i, cell)

            # Lower (col 2), Target (col 3), Upper (col 4), Weight (col 5), Importance (col 6)
            for c_i, key, enabled in [
                (2, 'lower', goal in ('target', 'maximize')),
                (3, 'target', True),
                (4, 'upper', goal in ('minimize', 'target')),
                (5, 'weight', True),
                (6, 'importance', True),
            ]:
                val = item.get(key)
                cell = QTableWidgetItem(_fmt_num(val) if enabled else '*')
                if not enabled:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    cell.setForeground(QColor('#888888'))
                self.table.setItem(r_i, c_i, cell)

        layout.addWidget(self.table, 1)
        self.preview = DesirabilityPreviewWidget(self)
        layout.addWidget(self.preview)
        note = QLabel('Weight (0.1 to 10) shapes each individual desirability curve; Importance (0.1 to 10) weights the composite desirability.')
        note.setObjectName('secondary')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = _footer(self, layout, self.validate)
        self._building = False
        self.table.currentCellChanged.connect(lambda r, c, pr, pc: self._update_preview(r))
        self.table.itemChanged.connect(lambda item: self._update_preview(item.row()))
        if self.rows_data:
            self.table.setCurrentCell(0, 3)
            self._update_preview(0)

    def _read_row(self, r_i):
        base = dict(self.rows_data[r_i])
        goal = base['goal']
        def num_cell(col, label_name):
            it = self.table.item(r_i, col)
            txt = it.text().strip() if it else ''
            if not txt or txt == '*':
                raise ValueError(f"{base['response_name']}: Enter a numeric value for {label_name}.")
            val = float(txt)
            if not math.isfinite(val):
                raise ValueError(f"{base['response_name']}: {label_name} must be a finite number.")
            return val
        base['lower'] = num_cell(2, 'Lower') if goal in ('target', 'maximize') else None
        base['target'] = num_cell(3, 'Target')
        base['upper'] = num_cell(4, 'Upper') if goal in ('minimize', 'target') else None
        base['weight'] = num_cell(5, 'Weight')
        base['importance'] = num_cell(6, 'Importance')
        spec, _ = normalize_response_spec(self.worksheet, {
            k: base[k] for k in ('model_recipe', 'goal', 'lower', 'target', 'upper', 'weight', 'importance')
        })
        base.update(spec)
        return base

    def _update_preview(self, r_i):
        if self._building or r_i < 0 or r_i >= len(self.rows_data):
            return
        try:
            row = self._read_row(r_i)
            self.preview.set_spec(row)
        except (ValueError, TypeError, ArithmeticError):
            self.preview.set_spec(self.rows_data[r_i])

    def validate(self):
        try:
            updated = [self._read_row(r_i) for r_i in range(len(self.rows_data))]
        except (ValueError, TypeError, ArithmeticError) as exc:
            self.error.setText(str(exc))
            return
        self.result_rows = updated
        self.accept()


class OptimizerOptionsDialog(QDialog):
    """Response Optimizer: Options (`REGROPTIMIZEROPTIONS.MDF` / `FACTORIALOPTIMIZEROPTIONS.MDF` / `GLMOPTIMIZEROPTIONS.MDF`)."""
    def __init__(self, parent, worksheet, bundles, current_options):
        super().__init__(parent)
        self.setWindowTitle('Response Optimizer: Options')
        self.resize(720, 460)
        self.worksheet = worksheet
        self.bundles = bundles
        self.initial = settings(current_options)
        self.options = None
        self._building = True

        # Discover union of predictors with default bounds
        base_opts = settings(dict(self.initial, constraints=[], starting_values=[]))
        self.predictors = _merge_predictors(bundles, base_opts)
        c_map = {c['index']: c for c in self.initial['constraints']}
        s_map = {s['index']: s['value'] for s in self.initial['starting_values']}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Constraints on Variables'))
        c_headers = ['Variable', 'Constraint', 'Hold Value', 'Lower', 'Upper']
        self.constraints_table = QTableWidget(len(self.predictors), len(c_headers))
        self.constraints_table.setHorizontalHeaderLabels(c_headers)
        self.constraints_table.verticalHeader().setVisible(False)
        self.constraints_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for r_i, pred in enumerate(self.predictors):
            idx = pred['index']
            saved_c = c_map.get(idx, dict(index=idx, mode='none', value=None, lower=None, upper=None))
            var_item = QTableWidgetItem(format_variable_reference(idx, worksheet))
            var_item.setFlags(var_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.constraints_table.setItem(r_i, 0, var_item)

            mode_combo = QComboBox()
            mode_combo.addItem('No constraints', 'none')
            mode_combo.addItem('Hold at value', 'hold')
            if pred['role'] == 'covariate':
                mode_combo.addItem('Constrain to region', 'region')
            mode_combo.setCurrentIndex(max(0, mode_combo.findData(saved_c['mode'])))
            mode_combo.currentIndexChanged.connect(lambda _=0, row=r_i: self._sync_constraint_row(row))
            self.constraints_table.setCellWidget(r_i, 1, mode_combo)

            if pred['role'] == 'factor':
                hold_combo = QComboBox()
                for lvl in pred['levels']:
                    hold_combo.addItem(str(lvl), lvl)
                if saved_c['mode'] == 'hold' and saved_c['value'] in pred['levels']:
                    hold_combo.setCurrentIndex(hold_combo.findData(saved_c['value']))
                self.constraints_table.setCellWidget(r_i, 2, hold_combo)
                for col in (3, 4):
                    dash = QTableWidgetItem('*')
                    dash.setFlags(dash.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.constraints_table.setItem(r_i, col, dash)
            else:
                hold_val = saved_c['value'] if saved_c['mode'] == 'hold' else 0.5 * (pred['observed_min'] + pred['observed_max'])
                lo_val = saved_c['lower'] if saved_c['mode'] == 'region' else pred['observed_min']
                hi_val = saved_c['upper'] if saved_c['mode'] == 'region' else pred['observed_max']
                self.constraints_table.setItem(r_i, 2, QTableWidgetItem(_fmt_num(hold_val)))
                self.constraints_table.setItem(r_i, 3, QTableWidgetItem(_fmt_num(lo_val)))
                self.constraints_table.setItem(r_i, 4, QTableWidgetItem(_fmt_num(hi_val)))
            self._sync_constraint_row(r_i)

        layout.addWidget(self.constraints_table, 1)

        layout.addWidget(QLabel('Starting Values for Variables'))
        s_headers = ['Variable', 'Starting Value']
        self.starting_table = QTableWidget(len(self.predictors), len(s_headers))
        self.starting_table.setHorizontalHeaderLabels(s_headers)
        self.starting_table.verticalHeader().setVisible(False)
        self.starting_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for r_i, pred in enumerate(self.predictors):
            idx = pred['index']
            var_item = QTableWidgetItem(format_variable_reference(idx, worksheet))
            var_item.setFlags(var_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.starting_table.setItem(r_i, 0, var_item)
            sv = s_map.get(idx, pred['starting_value'])
            if pred['role'] == 'factor':
                s_combo = QComboBox()
                for lvl in pred['levels']:
                    s_combo.addItem(str(lvl), lvl)
                if sv in pred['levels']:
                    s_combo.setCurrentIndex(s_combo.findData(sv))
                self.starting_table.setCellWidget(r_i, 1, s_combo)
            else:
                self.starting_table.setItem(r_i, 1, QTableWidgetItem(_fmt_num(sv)))

        layout.addWidget(self.starting_table, 1)

        form = QFormLayout()
        self.confidence = QLineEdit(_fmt_num(100.0 * self.initial['confidence']))
        form.addRow('Confidence level for all intervals:', self.confidence)
        self.side = QComboBox()
        for label_txt, val in [('Two-sided', 'two_sided'), ('Lower bound', 'lower'), ('Upper bound', 'upper')]:
            self.side.addItem(label_txt, val)
        self.side.setCurrentIndex(max(0, self.side.findData(self.initial['side'])))
        form.addRow('Type of confidence interval:', self.side)
        layout.addLayout(form)

        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = _footer(self, layout, self.validate)
        self._building = False

    def _sync_constraint_row(self, r_i):
        pred = self.predictors[r_i]
        mode = self.constraints_table.cellWidget(r_i, 1).currentData()
        if pred['role'] == 'factor':
            w = self.constraints_table.cellWidget(r_i, 2)
            if w is not None:
                w.setEnabled(mode == 'hold')
            return
        for col, active in [(2, mode == 'hold'), (3, mode == 'region'), (4, mode == 'region')]:
            item = self.constraints_table.item(r_i, col)
            if item is not None:
                flags = item.flags()
                if active:
                    item.setFlags(flags | Qt.ItemFlag.ItemIsEditable)
                    item.setForeground(QColor('#222222'))
                else:
                    item.setFlags(flags & ~Qt.ItemFlag.ItemIsEditable)
                    item.setForeground(QColor('#888888'))

    def validate(self):
        try:
            conf = float(self.confidence.text()) / 100.0
            constraints = []
            starting_values = []
            for r_i, pred in enumerate(self.predictors):
                idx = pred['index']
                mode = self.constraints_table.cellWidget(r_i, 1).currentData()
                if pred['role'] == 'factor':
                    if mode == 'hold':
                        val = self.constraints_table.cellWidget(r_i, 2).currentData()
                        constraints.append(dict(index=idx, mode='hold', value=val, lower=None, upper=None))
                        sv = val
                    else:
                        sv = self.starting_table.cellWidget(r_i, 1).currentData()
                    starting_values.append(dict(index=idx, value=sv))
                else:
                    if mode == 'hold':
                        txt = self.constraints_table.item(r_i, 2).text().strip()
                        hold_v = float(txt)
                        constraints.append(dict(index=idx, mode='hold', value=hold_v, lower=None, upper=None))
                        sv = hold_v
                    elif mode == 'region':
                        lo_v = float(self.constraints_table.item(r_i, 3).text().strip())
                        hi_v = float(self.constraints_table.item(r_i, 4).text().strip())
                        constraints.append(dict(index=idx, mode='region', value=None, lower=lo_v, upper=hi_v))
                        sv_txt = self.starting_table.item(r_i, 1).text().strip()
                        sv = float(sv_txt) if sv_txt else 0.5 * (lo_v + hi_v)
                        if not lo_v <= sv <= hi_v:
                            sv = 0.5 * (lo_v + hi_v)
                    else:
                        sv_txt = self.starting_table.item(r_i, 1).text().strip()
                        sv = float(sv_txt) if sv_txt else pred['starting_value']
                    starting_values.append(dict(index=idx, value=sv))
            cand_opts = settings(dict(
                self.initial,
                confidence=conf,
                side=self.side.currentData(),
                constraints=constraints,
                starting_values=starting_values,
            ))
            _merge_predictors(self.bundles, cand_opts)
            self.options = cand_opts
        except (ValueError, TypeError, OverflowError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()


class OptimizerGraphsDialog(QDialog):
    """Response Optimizer: Graphs (`REGROPTIMIZERGRAPHS.MDF`)."""
    def __init__(self, parent, current_options):
        super().__init__(parent)
        self.setWindowTitle('Response Optimizer: Graphs')
        self.initial = settings(current_options)
        self.options = None
        layout = QVBoxLayout(self)
        self.optimization_plot = QCheckBox('Optimization plot')
        self.optimization_plot.setChecked(self.initial['optimization_plot'])
        layout.addWidget(self.optimization_plot)
        note = QLabel('Displays predictor profile curves, optimal variable settings [Cur], individual desirabilities d, and composite desirability D.')
        note.setObjectName('secondary')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.buttons = _footer(self, layout, self.validate)

    def validate(self):
        self.options = settings(dict(self.initial, optimization_plot=self.optimization_plot.isChecked()))
        self.accept()


class OptimizerResultsDialog(QDialog):
    """Response Optimizer: Results (`REGROPTIMIZEROUTPUT.MDF`)."""
    def __init__(self, parent, current_options):
        super().__init__(parent)
        self.setWindowTitle('Response Optimizer: Results')
        self.initial = settings(current_options)
        self.options = None
        layout = QVBoxLayout(self)
        self.show_parameters = QCheckBox('Parameters')
        self.show_parameters.setChecked(self.initial['show_parameters'])
        self.show_variable_ranges = QCheckBox('Variable ranges')
        self.show_variable_ranges.setChecked(self.initial['show_variable_ranges'])
        self.show_starting_point = QCheckBox('Starting point')
        self.show_starting_point.setChecked(self.initial['show_starting_point'])
        self.show_solutions = QCheckBox('Solutions')
        self.show_solutions.setChecked(self.initial['show_solutions'])
        self.max_solutions = QSpinBox()
        self.max_solutions.setRange(1, 10)
        self.max_solutions.setValue(self.initial['max_solutions'])
        self.max_solutions.setEnabled(self.initial['show_solutions'])
        self.show_solutions.toggled.connect(self.max_solutions.setEnabled)
        self.show_prediction = QCheckBox('Multiple response prediction')
        self.show_prediction.setChecked(self.initial['show_prediction'])

        for chk in (self.show_parameters, self.show_variable_ranges, self.show_starting_point, self.show_solutions):
            layout.addWidget(chk)
        sol_row = QHBoxLayout()
        sol_row.setContentsMargins(22, 0, 0, 0)
        sol_row.addWidget(QLabel('Number of solutions to display:'))
        sol_row.addWidget(self.max_solutions)
        sol_row.addStretch(1)
        layout.addLayout(sol_row)
        layout.addWidget(self.show_prediction)
        self.buttons = _footer(self, layout, self.validate)

    def validate(self):
        self.options = settings(dict(
            self.initial,
            show_parameters=self.show_parameters.isChecked(),
            show_variable_ranges=self.show_variable_ranges.isChecked(),
            show_starting_point=self.show_starting_point.isChecked(),
            show_solutions=self.show_solutions.isChecked(),
            max_solutions=int(self.max_solutions.value()),
            show_prediction=self.show_prediction.isChecked(),
        ))
        self.accept()


class ResponseOptimizerDialog(QDialog):
    """Main Response Optimizer dialog (`REGRESSIONOPTIMIZER.MDF`, `GLMOPTIMIZER.MDF`, etc.)."""
    def __init__(self, window, family=None):
        super().__init__(window)
        self.window = window
        self.worksheet = window.presenter.worksheet
        self.family = family
        self.entry = None
        self.options = settings()
        self.models = []
        self.row_specs = []
        self._building = False

        self.setWindowTitle('Response Optimizer')
        self.resize(740, 420)
        layout = QVBoxLayout(self)

        headers = ['Response', 'Goal', 'Target']
        self.responses_table = QTableWidget(0, len(headers))
        self.responses_table.setHorizontalHeaderLabels(headers)
        self.responses_table.verticalHeader().setVisible(False)
        self.responses_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.responses_table.itemChanged.connect(self._on_target_edited)
        layout.addWidget(self.responses_table, 1)

        tools = QHBoxLayout()
        for attr, label_txt, callback in [
            ('setup_button', 'Desirability…', self.configure_desirability),
            ('options_button', 'Options…', self.configure_options),
            ('graphs_button', 'Graphs…', self.configure_graphs),
            ('results_button', 'Results…', self.configure_results),
            ('model_button', 'View Model…', self.view_model),
        ]:
            btn = QPushButton(label_txt)
            btn.setAutoDefault(False)
            btn.clicked.connect(callback)
            setattr(self, attr, btn)
            tools.addWidget(btn)
        layout.addLayout(tools)

        note = QLabel('Select Minimize, Target, or Maximize for one or more fitted responses on the active worksheet. '
                      'Source models are refitted using current worksheet data.')
        note.setObjectName('secondary')
        note.setWordWrap(True)
        layout.addWidget(note)

        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = _footer(self, layout, self.validate)

        self._load_models()
        self.restore_previous()
        self._update_button_states()

    def _load_models(self):
        # Discover all supported fitted models on this worksheet
        self.models = discover_models(self.worksheet, self.window.presenter.history, family=None)
        self.row_specs = []
        self._building = True
        self.responses_table.setRowCount(len(self.models))
        for r_i, m in enumerate(self.models):
            defs = default_desirability(self.worksheet, m['recipe'], goal='none')
            self.row_specs.append(dict(
                response_index=m['response_index'],
                response_name=m['response_name'],
                model_title=m['model_title'],
                model_recipe=copy.deepcopy(m['recipe']),
                bundle=m['bundle'],
                goal='none',
                lower=defs['lower'],
                target=defs['target'],
                upper=defs['upper'],
                weight=1.0,
                importance=1.0,
            ))
            resp_label = f"{format_variable_reference(m['response_index'], self.worksheet)} ({m['model_title']})"
            resp_item = QTableWidgetItem(resp_label)
            resp_item.setFlags(resp_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.responses_table.setItem(r_i, 0, resp_item)

            goal_combo = QComboBox()
            for text, val in [
                ('Do not optimize', 'none'),
                ('Minimize', 'minimize'),
                ('Target', 'target'),
                ('Maximize', 'maximize'),
            ]:
                goal_combo.addItem(text, val)
            goal_combo.currentIndexChanged.connect(lambda _=0, row=r_i: self._on_goal_changed(row))
            self.responses_table.setCellWidget(r_i, 1, goal_combo)

            target_item = QTableWidgetItem('')
            target_item.setFlags(target_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.responses_table.setItem(r_i, 2, target_item)
        self._building = False
        if not self.models:
            self.error.setText('Fit a supported regression, GLM, factorial, response surface or binary logistic model on this worksheet first.')

    def set_response_goal(self, row, goal, target=None):
        """Programmatically set a response row's goal and optional target."""
        if not 0 <= row < len(self.row_specs):
            raise IndexError('Response row index out of range.')
        combo = self.responses_table.cellWidget(row, 1)
        idx = combo.findData(goal)
        if idx < 0:
            raise ValueError('Unsupported optimization goal.')
        combo.setCurrentIndex(idx)
        if target is not None:
            self._building = True
            self.responses_table.item(row, 2).setText(_fmt_num(target))
            self._building = False
            self._on_target_edited(self.responses_table.item(row, 2))

    def _on_goal_changed(self, row):
        if self._building or not 0 <= row < len(self.row_specs):
            return
        spec = self.row_specs[row]
        goal = self.responses_table.cellWidget(row, 1).currentData()
        spec['goal'] = goal
        self._building = True
        target_item = self.responses_table.item(row, 2)
        if goal == 'none':
            spec['lower'] = spec['target'] = spec['upper'] = None
            target_item.setText('')
            target_item.setFlags(target_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        else:
            defs = default_desirability(self.worksheet, spec['model_recipe'], goal=goal)
            spec['lower'] = defs['lower']
            spec['target'] = defs['target']
            spec['upper'] = defs['upper']
            if goal == 'target':
                target_item.setText(_fmt_num(spec['target']))
                target_item.setFlags(target_item.flags() | Qt.ItemFlag.ItemIsEditable)
            else:
                target_item.setText('')
                target_item.setFlags(target_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._building = False
        self.error.clear()
        self._update_button_states()

    def _on_target_edited(self, item):
        if self._building or item is None or item.column() != 2:
            return
        row = item.row()
        if not 0 <= row < len(self.row_specs):
            return
        spec = self.row_specs[row]
        if spec['goal'] != 'target':
            return
        txt = item.text().strip()
        if not txt:
            return
        try:
            t_val = float(txt)
            defs = default_desirability(self.worksheet, spec['model_recipe'], goal='target', target=t_val)
            spec['target'] = defs['target']
            if spec['lower'] is None or spec['lower'] >= spec['target']:
                spec['lower'] = defs['lower']
            if spec['upper'] is None or spec['upper'] <= spec['target']:
                spec['upper'] = defs['upper']
            self.error.clear()
        except (ValueError, TypeError) as exc:
            self.error.setText(str(exc))

    def _active_specs(self):
        active = []
        for r_i, spec in enumerate(self.row_specs):
            if spec['goal'] == 'none':
                continue
            if spec['goal'] == 'target':
                txt = self.responses_table.item(r_i, 2).text().strip()
                if not txt:
                    raise ValueError(f"{spec['response_name']}: Enter a target value.")
                t_val = float(txt)
                if spec['target'] != t_val:
                    defs = default_desirability(self.worksheet, spec['model_recipe'], goal='target', target=t_val)
                    spec['target'] = defs['target']
                    if spec['lower'] is None or spec['lower'] >= t_val:
                        spec['lower'] = defs['lower']
                    if spec['upper'] is None or spec['upper'] <= t_val:
                        spec['upper'] = defs['upper']
            active.append(spec)
        return active

    def _update_button_states(self):
        has_active = any(s['goal'] != 'none' for s in self.row_specs)
        self.setup_button.setEnabled(has_active)
        self.options_button.setEnabled(has_active)
        self.model_button.setEnabled(bool(self.models))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(has_active)

    def configure_desirability(self):
        try:
            active = self._active_specs()
            if not active:
                return
            dlg = OptimizerDesirabilityDialog(self, self.worksheet, active)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_rows:
                by_resp = {r['response_index']: r for r in dlg.result_rows}
                self._building = True
                for r_i, spec in enumerate(self.row_specs):
                    if spec['response_index'] in by_resp:
                        updated = by_resp[spec['response_index']]
                        spec.update(updated)
                        if spec['goal'] == 'target':
                            self.responses_table.item(r_i, 2).setText(_fmt_num(spec['target']))
                self._building = False
                self.error.clear()
        except (ValueError, TypeError, ArithmeticError) as exc:
            self.error.setText(str(exc))

    def configure_options(self):
        try:
            active = self._active_specs()
            if not active:
                return
            bundles = [s['bundle'] for s in active]
            # Filter out any stale constraints/starting_values from predictors no longer in active models
            active_pred_indices = {p['index'] for b in bundles for p in b['predictors']}
            filtered_opts = dict(
                self.options,
                constraints=[c for c in self.options['constraints'] if c['index'] in active_pred_indices],
                starting_values=[s for s in self.options['starting_values'] if s['index'] in active_pred_indices],
            )
            dlg = OptimizerOptionsDialog(self, self.worksheet, bundles, filtered_opts)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.options:
                self.options = dlg.options
                self.error.clear()
        except (ValueError, TypeError, ArithmeticError) as exc:
            self.error.setText(str(exc))

    def configure_graphs(self):
        dlg = OptimizerGraphsDialog(self, self.options)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.options:
            self.options = dlg.options

    def configure_results(self):
        dlg = OptimizerResultsDialog(self, self.options)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.options:
            self.options = dlg.options

    def model_description(self):
        if not self.models:
            return 'No supported fitted models are available on this worksheet.'
        lines = []
        for m in self.models:
            b = m['bundle']
            lines.append(f"{b['response_name']} — {b['model_title']}")
            for p in b['predictors']:
                ref = format_variable_reference(p['index'], self.worksheet)
                if p['role'] == 'factor':
                    lines.append(f"  Predictor: {ref} (factor; levels: {', '.join(map(str, p['levels']))})")
                else:
                    lines.append(f"  Predictor: {ref} (continuous; range: {_fmt_num(p['min'])} to {_fmt_num(p['max'])})")
            lines.append('')
        lines.append('Models are refitted using the current worksheet data.')
        return '\n'.join(lines)

    def view_model(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('Response Optimizer: View Model')
        dlg.resize(560, 380)
        layout = QVBoxLayout(dlg)
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(self.model_description())
        layout.addWidget(txt)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(dlg.reject)
        layout.addWidget(close)
        dlg.exec()

    def restore_previous(self):
        for entry in reversed(self.window.presenter.history):
            if entry.get('source_unavailable') or entry.get('recipe', {}).get('action') != 'optimize_responses':
                continue
            try:
                if self.window.presenter.result_worksheet(entry) is not self.worksheet:
                    continue
                p = entry['recipe']['parameters']
                opts = settings(p['options'])
                saved_resps = p.get('responses', [])
                if not isinstance(saved_resps, list) or not saved_resps:
                    continue
                by_resp = {}
                for item in saved_resps:
                    norm_spec, bundle = normalize_response_spec(self.worksheet, item)
                    by_resp[bundle['response_index']] = (norm_spec, bundle)
                if not any(spec['response_index'] in by_resp for spec in self.row_specs):
                    continue
                self._building = True
                for r_i, spec in enumerate(self.row_specs):
                    r_idx = spec['response_index']
                    combo = self.responses_table.cellWidget(r_i, 1)
                    target_item = self.responses_table.item(r_i, 2)
                    if r_idx in by_resp:
                        norm_spec, bundle = by_resp[r_idx]
                        spec.update(norm_spec)
                        spec['bundle'] = bundle
                        combo.setCurrentIndex(max(0, combo.findData(norm_spec['goal'])))
                        if norm_spec['goal'] == 'target':
                            target_item.setText(_fmt_num(norm_spec['target']))
                            target_item.setFlags(target_item.flags() | Qt.ItemFlag.ItemIsEditable)
                        else:
                            target_item.setText('')
                            target_item.setFlags(target_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    else:
                        spec['goal'] = 'none'
                        combo.setCurrentIndex(0)
                        target_item.setText('')
                        target_item.setFlags(target_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._building = False
                self.options = opts
                self._update_button_states()
                break
            except (ValueError, TypeError, KeyError, IndexError, ArithmeticError):
                self._building = False
                continue

    def validate(self):
        try:
            active = self._active_specs()
            if not active:
                raise ValueError('Choose Minimize, Target, or Maximize for at least one response.')
            bundles = [s['bundle'] for s in active]
            active_pred_indices = {p['index'] for b in bundles for p in b['predictors']}
            clean_opts = settings(dict(
                self.options,
                constraints=[c for c in self.options['constraints'] if c['index'] in active_pred_indices],
                starting_values=[s for s in self.options['starting_values'] if s['index'] in active_pred_indices],
            ))
            payload = [
                {k: s[k] for k in ('model_recipe', 'goal', 'lower', 'target', 'upper', 'weight', 'importance')}
                for s in active
            ]
            entry = self.window.presenter.optimize_responses(payload, options=clean_opts)
            self.entry = entry
            self.window.refresh()
            self.window.show_result(entry)
        except (ValueError, TypeError, KeyError, IndexError, ArithmeticError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()
