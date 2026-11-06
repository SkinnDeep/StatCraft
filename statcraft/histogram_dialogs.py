"""Resource-guided histogram gallery and variable-entry dialogs.

Thumbnails and widget construction are original. The bounded implementation
supports one categorical grouping variable and at most 16 response/group series.
"""
from copy import deepcopy
import math

from PySide6.QtCore import Qt, QSize, QPointF
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox,
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSpinBox,
    QToolButton, QVBoxLayout)

from .histogram_options import validate_histogram_settings
from .variable_dialogs import VariableEntry, format_variable_reference, resolve_variables

MODES = {'simple': 'Simple', 'fit': 'With Fit', 'groups': 'With Groups',
         'fit_groups': 'With Fit and Groups'}


def histogram_icon(mode):
    """Draw an original gallery preview without vendor image assets."""
    pixmap = QPixmap(240, 160)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(QColor('white'))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor('#64717c'), 1))
    painter.drawLine(12, 69, 112, 69)
    painter.drawLine(12, 69, 12, 8)
    for group in range(2 if mode in ('groups', 'fit_groups') else 1):
        color = QColor('#ad6b36' if group else '#548bb4')
        color.setAlpha(150 if group else 190)
        painter.setBrush(color)
        painter.setPen(QPen(QColor('#855633' if group else '#486b86'), .6))
        for i, height in enumerate((5, 14, 32, 48, 35, 19, 7)):
            painter.drawRect(20 + i * 11 + group * 4, 69 - height + group * 7,
                             11, max(2, height - group * 7))
        if mode in ('fit', 'fit_groups'):
            painter.setPen(QPen(QColor('#975226' if group else '#a22d36'), 1.5))
            points = [QPointF(15 + i, 69 - 50 * math.exp(-((i - 45 - group * 6) / 21) ** 2))
                      for i in range(96)]
            painter.drawPolyline(QPolygonF(points))
    painter.end()
    return QIcon(pixmap)


class HistogramTypeDialog(QDialog):
    def __init__(self, parent=None):
        self.setSizeGripEnabled(True)
        super().__init__(parent)
        self.setWindowTitle('Histograms')
        self.mode = 'simple'
        outer = QVBoxLayout(self)
        grid = QGridLayout()
        self.buttons = QButtonGroup(self)
        self.mode_buttons = {}
        for index, (mode, title) in enumerate(MODES.items()):
            button = QToolButton()
            button.setText(title)
            button.setIcon(histogram_icon(mode))
            button.setIconSize(QSize(120, 80))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setMinimumSize(168, 132)
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.setStyleSheet('QToolButton {border:1px solid #bfc5cb; padding:8px; background:white;} '
                'QToolButton:checked {border:2px solid #205b92; background:#eaf1f8;}')
            button.clicked.connect(lambda checked=False, key=mode: setattr(self, 'mode', key))
            self.buttons.addButton(button)
            self.mode_buttons[mode] = button
            grid.addWidget(button, index // 2, index % 2)
        outer.addLayout(grid)
        self.actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                        QDialogButtonBox.StandardButton.Cancel)
        self.actions.accepted.connect(self.accept)
        self.actions.rejected.connect(self.reject)
        outer.addWidget(self.actions)


class HistogramScaleDialog(QDialog):
    """Functional subset of histogram scales, with shared existing validation."""
    def __init__(self, settings, parent=None):
        self.setSizeGripEnabled(True)
        super().__init__(parent)
        self.setWindowTitle('Histogram: Scale')
        self.initial = validate_histogram_settings(settings)
        outer = QVBoxLayout(self)
        form = QFormLayout()
        self.bins = QSpinBox()
        self.bins.setRange(2, 1000)
        self.bins.setValue(self.initial['bins'])
        form.addRow('Number of intervals:', self.bins)
        self.scale = QComboBox()
        self.scale.addItems(['Frequency', 'Percent', 'Density'])
        self.scale.setCurrentText(self.initial['scale'])
        form.addRow('Y scale type:', self.scale)
        self.cumulative = QCheckBox('Cumulative')
        self.cumulative.setChecked(self.initial['cumulative'])
        form.addRow(self.cumulative)
        self.scale.currentTextChanged.connect(self.scale_changed)
        self.scale_changed(self.scale.currentText())
        outer.addLayout(form)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                        QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)

    def scale_changed(self, scale):
        self.cumulative.setEnabled(scale != 'Density')
        if scale == 'Density':
            self.cumulative.setChecked(False)

    def settings(self):
        return validate_histogram_settings(dict(bins=self.bins.value(),
            scale=self.scale.currentText(), cumulative=self.cumulative.isChecked(),
            fit=self.initial['fit']))


class HistogramDialog(QDialog):
    def __init__(self, parent, worksheet, mode='simple', initial_columns=None,
                 parameters=None, lock_variables=False):
        self.setSizeGripEnabled(True)
        parameters = deepcopy(parameters) if isinstance(parameters, dict) else {}
        mode = parameters.get('variant', mode)
        if mode not in MODES:
            raise ValueError('Unsupported histogram type.')
        super().__init__(parent)
        self.setWindowTitle('Histogram: ' + MODES[mode])
        self.resize(740, 420)
        self.worksheet, self.mode = worksheet, mode
        self.active = None
        self._settings = None
        self.histogram_settings = validate_histogram_settings(
            parameters.get('settings', {'fit': 'Normal' if mode in ('fit', 'fit_groups') else None}))
        self.labels = {'title': '', 'x_label': '', 'y_label': ''}
        outer = QVBoxLayout(self)
        body = QHBoxLayout()
        left = QVBoxLayout()
        self.available = QListWidget()
        self.available.setMinimumWidth(230)
        self.available.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        left.addWidget(self.available)
        self.select_button = QPushButton('Select')
        self.select_button.setAutoDefault(False)
        self.select_button.clicked.connect(self.transfer)
        self.available.itemDoubleClicked.connect(lambda item: self.transfer())
        self.available.itemSelectionChanged.connect(lambda: self.select_button.setEnabled(
            bool(self.available.selectedItems())))
        left.addWidget(self.select_button)
        body.addLayout(left, 1)
        right = QVBoxLayout()
        form = QFormLayout()
        self.variables = VariableEntry(lambda: self.activate('responses'))
        self.variables.setPlaceholderText('C1 C2 or quoted column names')
        form.addRow('Graph variables:', self.variables)
        self.group = VariableEntry(lambda: self.activate('group'))
        self.grouped = mode in ('groups', 'fit_groups')
        if self.grouped:
            self.group.setPlaceholderText('One numeric or text column')
            form.addRow('Categorical variable for grouping:', self.group)
        else:
            self.group.hide()
        self.arrangement = QComboBox()
        self.arrangement.addItem('Overlaid on the same graph', 'overlay')
        self.arrangement.addItem('In separate panels of the same graph', 'panels')
        if self.grouped:
            form.addRow('Groups:', self.arrangement)
        else:
            self.arrangement.hide()
        right.addLayout(form)
        if mode in ('fit', 'fit_groups'):
            right.addWidget(QLabel('Distribution fit: Normal'))
        right.addStretch()
        options = QHBoxLayout()
        self.scale_button = QPushButton('Scale…')
        self.labels_button = QPushButton('Labels…')
        for button, callback in ((self.scale_button, self.edit_scale),
                                 (self.labels_button, self.edit_labels)):
            button.setAutoDefault(False)
            button.clicked.connect(callback)
            options.addWidget(button)
        right.addLayout(options)
        note = QLabel('Select up to 16 response/group combinations. Missing response or group values are omitted.')
        note.setWordWrap(True)
        note.setObjectName('secondary')
        right.addWidget(note)
        body.addLayout(right, 2)
        outer.addLayout(body)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setObjectName('error')
        outer.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                        QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)
        initial_columns = parameters.get('response_indices', initial_columns)
        if initial_columns:
            self.variables.setText(' '.join(format_variable_reference(i, worksheet)
                for i in initial_columns if worksheet.columns[i].kind == 'number'))
        group_index = parameters.get('group_index')
        if group_index is not None:
            self.group.setText(format_variable_reference(group_index, worksheet))
        position = self.arrangement.findData(parameters.get('layout', 'overlay'))
        self.arrangement.setCurrentIndex(max(0, position))
        self.activate('responses')
        if lock_variables:
            for widget in (self.available, self.select_button, self.variables, self.group):
                widget.setEnabled(False)
        self.variables.setFocus()

    def activate(self, role):
        if self.active == role:
            return
        self.active = role
        self.available.clear()
        for index, column in enumerate(self.worksheet.columns):
            if column.kind == 'number' or role == 'group' and column.kind == 'text':
                text = format_variable_reference(index, self.worksheet)
                item = QListWidgetItem(text)
                item.setToolTip(text)
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.available.addItem(item)
        self.select_button.setEnabled(False)

    def transfer(self):
        selected = self.available.selectedItems()
        if not selected:
            return
        target = self.group if self.active == 'group' else self.variables
        refs = [format_variable_reference(item.data(Qt.ItemDataRole.UserRole), self.worksheet)
                for item in selected]
        if self.active == 'group':
            target.setText(refs[0])
        else:
            prefix = target.text().strip()
            target.setText((prefix + ' ' if prefix else '') + ' '.join(refs))
        target.setFocus()

    def edit_scale(self):
        dialog = HistogramScaleDialog(self.histogram_settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.histogram_settings = dialog.settings()

    def edit_labels(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.windowTitle().split(':',1)[0]+': Labels')
        outer = QVBoxLayout(dialog)
        form = QFormLayout()
        edits = {}
        for key, title in (('title', 'Title:'), ('x_label', 'X-axis label:'),
                           ('y_label', 'Y-axis label:')):
            edit = QLineEdit(self.labels[key])
            edit.setMaxLength(145)
            edit.setPlaceholderText('Use default')
            edits[key] = edit
            form.addRow(title, edit)
        outer.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        outer.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.labels = {key: edit.text() for key, edit in edits.items()}

    def values(self):
        from .histogram_graphs import validate_parameters
        responses = resolve_variables(self.variables.text(), self.worksheet)
        groups = resolve_variables(self.group.text(), self.worksheet, ('number', 'text')) if self.grouped else []
        if self.grouped and len(groups) != 1:
            raise ValueError('Choose one categorical variable for grouping.')
        return validate_parameters(self.worksheet, responses, variant=self.mode,
            group_index=groups[0] if groups else None,
            layout=self.arrangement.currentData(), settings=self.histogram_settings)

    def validate(self):
        try:
            from .histogram_graphs import build_histograms
            parameters = self.values()
            build_histograms(self.worksheet, **parameters)
        except (ValueError, TypeError, ArithmeticError) as exc:
            self.error.setText(str(exc))
            return False
        self._settings = parameters
        self.error.clear()
        self.accept()
        return True

    def settings(self):
        return deepcopy(self._settings)

    def presentation(self):
        """Sparse labels preserve automatic titles when a field was left blank."""
        return {key: value for key, value in self.labels.items() if value}

    def presentation_settings(self):
        return self.presentation()
