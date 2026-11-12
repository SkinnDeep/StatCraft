"""Compact, capability-driven editor for StatCraft graph object appearance."""
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QLineEdit, QPushButton, QColorDialog, QDoubleSpinBox,
    QCheckBox, QDialogButtonBox, QWidget, QGroupBox)

from .dialog_theme import is_dark_active, dialog_stylesheet, error_label_style
from .graph_styles import validate_styles, style_for, FIELDS, NUMBER_RANGES


_FALLBACKS = dict(color='#4477aa', fill='#80a8d4', edge='#56687c',
    line_width=1.0, line_style='solid', marker='circle', marker_size=5.0,
    opacity=1.0, visible=True, legend_visible=True)
_LABELS = dict(color='Color:', fill='Fill color:', edge='Edge color:',
    line_width='Line width:', line_style='Line style:', marker='Symbol:',
    marker_size='Symbol size:', opacity='Opacity (%):', visible='Show object',
    legend_visible='Show in legend')
_GROUPS = (('Symbols', ('marker', 'marker_size', 'color')),
           ('Lines and fill', ('line_style', 'line_width', 'fill', 'edge')),
           ('Display', ('opacity', 'visible', 'legend_visible')))


class GraphObjectDialog(QDialog):
    def __init__(self, objects, styles, selected=None, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(True)
        self.setWindowTitle('Edit Graph Object')
        self.setMinimumWidth(370)
        dark = is_dark_active(parent or self)
        self.setStyleSheet(dialog_stylesheet(dark))
        self._draft = validate_styles(styles)
        self._objects = []
        seen = set()
        for descriptor in objects:
            target = descriptor['target']
            validate_styles({target: {}})
            if target in seen:
                raise ValueError('Graph object identifiers must be unique.')
            seen.add(target)
            defaults = style_for({}, target, descriptor.get('defaults', {}))
            capabilities = set(descriptor.get('capabilities', ()))
            if capabilities - FIELDS:
                raise ValueError('Unsupported graph object capabilities.')
            self._objects.append(dict(target=target,
                label=str(descriptor.get('label', target)),
                capabilities=capabilities, defaults=defaults))
        self._current = -1
        self._loading = False
        self._dirty = set()
        self.controls = {}
        outer = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel('Graph object:'))
        self.object_combo = QComboBox()
        for item in self._objects:
            self.object_combo.addItem(item['label'], item['target'])
        row.addWidget(self.object_combo, 1)
        outer.addLayout(row)
        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._body)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet(error_label_style(dark))
        self.error.hide()
        outer.addWidget(self.error)
        self.reset_button = QPushButton('Reset Selected')
        self.reset_button.setToolTip('Restore the selected object’s default appearance.')
        bottom = QHBoxLayout()
        bottom.addWidget(self.reset_button)
        bottom.addStretch()
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                        QDialogButtonBox.StandardButton.Cancel)
        bottom.addWidget(self.buttons)
        outer.addLayout(bottom)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.reset_button.clicked.connect(self.reset_selected)
        self.object_combo.currentIndexChanged.connect(self._select)
        initial = next((i for i, item in enumerate(self._objects)
                        if item['target'] == selected), 0)
        if self._objects:
            self.object_combo.blockSignals(True)
            self.object_combo.setCurrentIndex(initial)
            self.object_combo.blockSignals(False)
            self._load(initial)
        else:
            self._body_layout.addWidget(QLabel('No editable graph objects.'))
            self.reset_button.setEnabled(False)
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _read(self, field):
        control = self.controls[field]
        if isinstance(control, QLineEdit):
            return control.text().strip()
        if isinstance(control, QComboBox):
            return control.currentData()
        if isinstance(control, QCheckBox):
            return control.isChecked()
        value = control.value()
        return value / 100 if field == 'opacity' else value

    def _capture(self):
        if self._current < 0:
            return True
        item = self._objects[self._current]
        candidate = dict(self._draft.get(item['target'], {}))
        for field in self._dirty:
            value = self._read(field)
            # Untouched fields stay sparse; returning to the displayed initial
            # value restores the original override (if it existed).
            if value == self._initial_values[field]:
                if field in self._initial_overrides:
                    candidate[field] = self._initial_overrides[field]
                else:
                    candidate.pop(field, None)
            elif value == item['defaults'].get(field, _FALLBACKS[field]):
                candidate.pop(field, None)
            else:
                candidate[field] = value
        try:
            validated = validate_styles({item['target']: candidate})[item['target']]
        except ValueError as exc:
            self.error.setText(str(exc))
            self.error.show()
            return False
        if validated:
            self._draft[item['target']] = validated
        else:
            self._draft.pop(item['target'], None)
        self.error.hide()
        return True

    def _changed(self, field, *args):
        if not self._loading:
            self._dirty.add(field)
            self._capture()

    def _select(self, index):
        if self._loading:
            return
        if not self._capture():
            self.object_combo.blockSignals(True)
            self.object_combo.setCurrentIndex(self._current)
            self.object_combo.blockSignals(False)
            return
        self._load(index)

    def _pick_color(self, field):
        raw = self.controls[field].text().strip()
        initial = (QColor(int(raw[1:3], 16), int(raw[3:5], 16),
                          int(raw[5:7], 16), int(raw[7:9], 16))
                   if len(raw) == 9 and raw.startswith('#')
                   and all(ch in '0123456789abcdefABCDEF' for ch in raw[1:])
                   else QColor(raw))
        if not initial.isValid():
            initial = QColor(_FALLBACKS[field])
        chosen = QColorDialog.getColor(initial, self, 'Choose ' + field + ' color')
        if chosen.isValid():
            self.controls[field].setText(chosen.name())

    def _load(self, index):
        self._loading = True
        self._current = index
        while self._body_layout.count():
            widget = self._body_layout.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.controls = {}
        self._dirty = set()
        item = self._objects[index]
        self._initial_overrides = dict(self._draft.get(item['target'], {}))
        values = dict(_FALLBACKS)
        values.update(item['defaults'])
        values.update(self._initial_overrides)
        self._initial_values = values
        for title, fields in _GROUPS:
            enabled = [field for field in fields if field in item['capabilities']]
            if not enabled:
                continue
            group = QGroupBox(title)
            form = QFormLayout(group)
            for field in enabled:
                value = values[field]
                row_widget = None
                if field in ('color', 'fill', 'edge'):
                    control = QLineEdit(str(value))
                    control.setPlaceholderText('#RRGGBB')
                    row_widget = QWidget()
                    color_row = QHBoxLayout(row_widget)
                    color_row.setContentsMargins(0, 0, 0, 0)
                    color_row.addWidget(control, 1)
                    picker = QPushButton('Choose…')
                    picker.clicked.connect(lambda checked=False, f=field: self._pick_color(f))
                    color_row.addWidget(picker)
                    control.textChanged.connect(lambda text, f=field: self._changed(f))
                elif field in ('line_style', 'marker'):
                    control = QComboBox()
                    choices = ('solid', 'dash', 'dot', 'none') if field == 'line_style' else (
                        'circle', 'square', 'triangle', 'diamond', 'plus', 'cross', 'none')
                    for choice in choices:
                        control.addItem(choice.capitalize(), choice)
                    control.setCurrentIndex(control.findData(value))
                    control.currentIndexChanged.connect(lambda i, f=field: self._changed(f))
                elif field in ('visible', 'legend_visible'):
                    control = QCheckBox(_LABELS[field])
                    control.setChecked(value)
                    control.toggled.connect(lambda checked, f=field: self._changed(f))
                else:
                    control = QDoubleSpinBox()
                    low, high = NUMBER_RANGES[field]
                    multiplier = 100 if field == 'opacity' else 1
                    control.setRange(low * multiplier, high * multiplier)
                    control.setDecimals(1 if field == 'opacity' else 2)
                    control.setSingleStep(5 if field == 'opacity' else .5)
                    control.setValue(value * multiplier)
                    control.valueChanged.connect(lambda number, f=field: self._changed(f))
                self.controls[field] = control
                form.addRow('' if field in ('visible', 'legend_visible') else _LABELS[field],
                            row_widget if row_widget is not None else control)
            self._body_layout.addWidget(group)
        if not self.controls:
            self._body_layout.addWidget(QLabel('This object has no appearance options.'))
        self.error.hide()
        self._loading = False

    def reset_selected(self):
        if self._current < 0:
            return
        self._draft.pop(self._objects[self._current]['target'], None)
        self._load(self._current)

    def styles(self):
        if not self._capture():
            raise ValueError(self.error.text())
        return validate_styles(self._draft)

    def accept(self):
        if self._capture():
            super().accept()
