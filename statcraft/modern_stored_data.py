"""Staged editors for worksheet constants and column-major numeric matrices."""
import copy
import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from .model import Column, Matrix, display_date


MAX_DIMENSION = 1000
MAX_CELLS = 10000
_MISSING_SENTINEL = 1.23456e30


def _number(text):
    text = text.strip()
    if text in ('', '*'):
        return None
    try:
        value = float(text)
    except (ValueError, OverflowError) as exc:
        raise ValueError('Enter a finite number, or leave the cell blank for missing data.') from exc
    if not math.isfinite(value):
        raise ValueError('Enter a finite number, or leave the cell blank for missing data.')
    if value == _MISSING_SENTINEL:
        raise ValueError('1.23456e30 is a reserved native missing-value sentinel. Use a blank or * instead.')
    return value


def _display(value, kind='number'):
    if value is None:
        return '*'
    if kind == 'date':
        return display_date(value)
    if kind == 'number':
        return format(value, '.17g')
    return str(value)


def _item(text, editable=True):
    item = QTableWidgetItem(text)
    if not editable:
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _names(names):
    cleaned = [name.strip() for name in names]
    if any(not name for name in cleaned):
        raise ValueError('Each item must have a name.')
    if len(set(cleaned)) != len(cleaned):
        raise ValueError('Names must be unique within this collection.')
    return cleaned


class ConstantsDialog(QDialog):
    def __init__(self, parent, worksheet, read_only=False):
        super().__init__(parent)
        self.setWindowTitle('Stored Constants')
        self.resize(560, 390)
        self.read_only = read_only
        self.constants = copy.deepcopy(worksheet.constants)
        self._originals = copy.deepcopy(worksheet.constants)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Worksheet: ' + worksheet.name))
        layout.addWidget(QLabel('View stored constants.' if read_only else
                                'Enter numeric constants. Use a blank or * for missing data.'))
        self.table = QTableWidget(0, 4 if read_only else 3)
        self.table.setHorizontalHeaderLabels(['Constant', 'Name', 'Value', 'Type'] if read_only
                                             else ['Constant', 'Name', 'Value'])
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 75)
        self.table.setColumnWidth(1, 180)
        if read_only:
            self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.add_button = QPushButton('Add Constant')
        self.add_button.setEnabled(not read_only)
        self.add_button.clicked.connect(self.add_constant)
        layout.addWidget(self.add_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet('color: #a32020;')
        layout.addWidget(self.error_label)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close if read_only else
                                        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        for c in self._originals:
            self._append_row(c.name, _display(c.values[0], c.kind), c.kind)
        self.setTabOrder(self.table, self.add_button)

    def _append_row(self, name, value, kind='number'):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, _item('K' + str(row + 1), False))
        self.table.setItem(row, 1, _item(name, not self.read_only))
        self.table.setItem(row, 2, _item(value, not self.read_only))
        if self.read_only:
            self.table.setItem(row, 3, _item(kind, False))

    def add_constant(self):
        if self.read_only:
            return
        names = {self.table.item(r, 1).text().strip() for r in range(self.table.rowCount())}
        n = self.table.rowCount() + 1
        while 'K' + str(n) in names:
            n += 1
        self._append_row('K' + str(n), '*')
        self.table.setCurrentCell(self.table.rowCount() - 1, 1)
        self.table.editItem(self.table.currentItem())

    def validate(self):
        if self.read_only:
            self.accept()
            return True
        try:
            names = _names([self.table.item(r, 1).text() for r in range(self.table.rowCount())])
            staged = []
            for r, name in enumerate(names):
                value = _number(self.table.item(r, 2).text())
                metadata = copy.deepcopy(self._originals[r].metadata) if r < len(self._originals) else {}
                staged.append(Column(name, 'number', [value], metadata))
        except ValueError as exc:
            self.error_label.setText(str(exc))
            return False
        self.constants = staged
        self.error_label.clear()
        self.accept()
        return True


class MatricesDialog(QDialog):
    def __init__(self, parent, worksheet, read_only=False):
        super().__init__(parent)
        self.setWindowTitle('Stored Matrices')
        self.resize(780, 540)
        self.read_only = read_only
        self.matrices = copy.deepcopy(worksheet.matrices)
        self._staged = copy.deepcopy(worksheet.matrices)
        self._current = -1
        self._loading = False
        self._preview_truncated = False
        outer = QVBoxLayout(self)
        outer.addWidget(QLabel('Worksheet: ' + worksheet.name))
        outer.addWidget(QLabel('View numeric matrices.' if read_only else
            'Numeric matrices; blank or * means missing. Editor limit: 1,000 per dimension and 10,000 cells.'))
        body = QHBoxLayout()
        left = QVBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(160)
        self.list_widget.setMaximumWidth(230)
        left.addWidget(self.list_widget)
        self.add_button = QPushButton('Add Matrix')
        self.add_button.setEnabled(not read_only)
        self.add_button.clicked.connect(self.add_matrix)
        left.addWidget(self.add_button)
        body.addLayout(left)
        right = QVBoxLayout()
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setReadOnly(read_only)
        form.addRow('Name:', self.name_edit)
        dims = QHBoxLayout()
        self.rows_spin = QSpinBox()
        self.columns_spin = QSpinBox()
        for spin in (self.rows_spin, self.columns_spin):
            spin.setRange(1, MAX_DIMENSION)
            spin.setEnabled(not read_only)
        dims.addWidget(QLabel('Rows:'))
        dims.addWidget(self.rows_spin)
        dims.addWidget(QLabel('Columns:'))
        dims.addWidget(self.columns_spin)
        self.resize_button = QPushButton('Resize')
        self.resize_button.setEnabled(not read_only)
        self.resize_button.clicked.connect(self.resize_matrix)
        dims.addWidget(self.resize_button)
        form.addRow('Dimensions:', dims)
        right.addLayout(form)
        self.preview_notice = QLabel()
        self.preview_notice.setWordWrap(True)
        right.addWidget(self.preview_notice)
        self.table = QTableWidget()
        if read_only:
            self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        right.addWidget(self.table)
        self.paste_button = QPushButton('Paste Cells')
        self.paste_button.setEnabled(not read_only)
        self.paste_button.clicked.connect(lambda: self.paste_tsv())
        right.addWidget(self.paste_button, alignment=Qt.AlignmentFlag.AlignLeft)
        body.addLayout(right, 1)
        outer.addLayout(body, 1)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet('color: #a32020;')
        outer.addWidget(self.error_label)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close if read_only else
                                        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)
        self.list_widget.currentRowChanged.connect(self._select)
        self.name_edit.editingFinished.connect(self._update_label)
        self.paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self.table)
        self.paste_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.paste_shortcut.activated.connect(lambda: self.paste_tsv())
        self.paste_shortcut.setEnabled(not read_only)
        for i, m in enumerate(self._staged):
            self.list_widget.addItem(self._label(i, m.name))
        if self._staged:
            self.list_widget.setCurrentRow(0)
        else:
            self._set_editor_enabled(False)
        self.setTabOrder(self.list_widget, self.add_button)
        self.setTabOrder(self.add_button, self.name_edit)
        self.setTabOrder(self.name_edit, self.rows_spin)
        self.setTabOrder(self.rows_spin, self.columns_spin)
        self.setTabOrder(self.columns_spin, self.resize_button)
        self.setTabOrder(self.resize_button, self.table)
        self.setTabOrder(self.table, self.paste_button)

    @staticmethod
    def _label(index, name):
        return 'M' + str(index + 1) + '  ' + name

    def _set_editor_enabled(self, enabled):
        self.name_edit.setEnabled(enabled)
        self.table.setEnabled(enabled)
        for widget in (self.rows_spin, self.columns_spin, self.resize_button, self.paste_button):
            widget.setEnabled(enabled and not self.read_only)

    def _flush(self):
        if self.read_only or self._current < 0:
            return True
        try:
            if self._preview_truncated:
                raise ValueError('This matrix exceeds the editor limit. Its preview cannot be saved as an edit; all original cells are preserved.')
            name = self.name_edit.text().strip()
            names = [m.name for m in self._staged]
            names[self._current] = name
            _names(names)
            rows, cols = self.table.rowCount(), self.table.columnCount()
            if rows < 1 or cols < 1 or rows > MAX_DIMENSION or cols > MAX_DIMENSION or rows * cols > MAX_CELLS:
                raise ValueError('Use positive dimensions up to 1,000 and at most 10,000 cells.')
            values = [_number(self.table.item(r, c).text() if self.table.item(r, c) else '')
                      for c in range(cols) for r in range(rows)]
            old = self._staged[self._current]
            self._staged[self._current] = Matrix(name, rows, cols, values, copy.deepcopy(old.metadata))
            self.list_widget.item(self._current).setText(self._label(self._current, name))
        except ValueError as exc:
            self.error_label.setText(str(exc))
            return False
        self.error_label.clear()
        return True

    def _update_label(self):
        if self._current >= 0 and not self.read_only:
            self.list_widget.item(self._current).setText(self._label(self._current, self.name_edit.text()))

    def _select(self, index):
        if self._loading or index == self._current:
            return
        if not self._flush():
            self._loading = True
            self.list_widget.setCurrentRow(self._current)
            self._loading = False
            return
        self._current = index
        if index < 0:
            self._set_editor_enabled(False)
            return
        self._set_editor_enabled(True)
        matrix = self._staged[index]
        self.name_edit.setText(matrix.name)
        for spin, value in ((self.rows_spin, matrix.rows), (self.columns_spin, matrix.columns)):
            spin.setRange(0 if self.read_only else 1, max(MAX_DIMENSION, value))
            spin.setValue(value)
        self._render(matrix)

    def _render(self, matrix):
        self._preview_truncated = (matrix.rows > MAX_DIMENSION or matrix.columns > MAX_DIMENSION
                                   or matrix.rows * matrix.columns > MAX_CELLS)
        cols = min(matrix.columns, 100) if self._preview_truncated else matrix.columns
        rows = min(matrix.rows, MAX_CELLS // max(1, cols)) if self._preview_truncated else matrix.rows
        self.preview_notice.setText(
            f'Preview: first {rows} rows and {cols} columns of {matrix.rows} × {matrix.columns}. '
            'This matrix exceeds the editor limit; its full data is preserved and is view only.'
            if self._preview_truncated else '')
        editable = not self.read_only and not self._preview_truncated
        self.name_edit.setReadOnly(not editable)
        for control in (self.rows_spin, self.columns_spin, self.resize_button, self.paste_button):
            control.setEnabled(editable)
        self.paste_shortcut.setEnabled(editable)
        self.table.clear()
        self.table.setRowCount(rows)
        self.table.setColumnCount(cols)
        self.table.setHorizontalHeaderLabels([str(c + 1) for c in range(cols)])
        self.table.setVerticalHeaderLabels([str(r + 1) for r in range(rows)])
        for c in range(cols):
            for r in range(rows):
                self.table.setItem(r, c, _item(_display(matrix.cell(r, c)), editable))
        if rows:
            self.table.setCurrentCell(0, 0)

    def add_matrix(self):
        if self.read_only or not self._flush():
            return False
        n = len(self._staged) + 1
        names = {m.name for m in self._staged}
        while 'M' + str(n) in names:
            n += 1
        matrix = Matrix('M' + str(n), 2, 2, [None] * 4)
        self._staged.append(matrix)
        self.list_widget.addItem(self._label(len(self._staged) - 1, matrix.name))
        self.list_widget.setCurrentRow(len(self._staged) - 1)
        return True

    def resize_matrix(self):
        if self.read_only or self._current < 0 or self._preview_truncated:
            return False
        rows, cols = self.rows_spin.value(), self.columns_spin.value()
        if rows < 1 or cols < 1 or rows > MAX_DIMENSION or cols > MAX_DIMENSION or rows * cols > MAX_CELLS:
            self.error_label.setText('Use positive dimensions up to 1,000 and at most 10,000 cells.')
            return False
        if not self._flush():
            return False
        old = self._staged[self._current]
        values = [old.cell(r, c) if r < old.rows and c < old.columns else None
                  for c in range(cols) for r in range(rows)]
        matrix = Matrix(old.name, rows, cols, values, copy.deepcopy(old.metadata))
        self._staged[self._current] = matrix
        self._render(matrix)
        return True

    def paste_tsv(self, text=None):
        if self.read_only or self._current < 0 or self._preview_truncated:
            return False
        if text is None:
            text = QApplication.clipboard().text()
        try:
            if not isinstance(text, str) or text == '':
                raise ValueError('The clipboard does not contain cells.')
            lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
            if lines[-1] == '':
                lines.pop()
            cells = [line.split('\t') for line in lines]
            if not cells or any(len(row) != len(cells[0]) for row in cells):
                raise ValueError('Paste a rectangular tab-separated range.')
            row, col = max(0, self.table.currentRow()), max(0, self.table.currentColumn())
            if row + len(cells) > self.table.rowCount() or col + len(cells[0]) > self.table.columnCount():
                raise ValueError('The pasted range exceeds the matrix dimensions. Resize the matrix first.')
            parsed = [[_number(value) for value in line] for line in cells]
        except ValueError as exc:
            self.error_label.setText(str(exc))
            return False
        for r, line in enumerate(parsed):
            for c, value in enumerate(line):
                self.table.setItem(row + r, col + c, _item(_display(value)))
        self.error_label.clear()
        return True

    def validate(self):
        if self.read_only:
            self.accept()
            return True
        if not self._flush():
            return False
        try:
            _names([m.name for m in self._staged])
        except ValueError as exc:
            self.error_label.setText(str(exc))
            return False
        self.matrices = copy.deepcopy(self._staged)
        self.error_label.clear()
        self.accept()
        return True
