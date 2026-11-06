"""Original ordered graph-selection workflow for a layout grid."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QSpinBox, QVBoxLayout)

from .graph_layouts import _identity, build_layout, layout_eligible


class GraphLayoutDialog(QDialog):
    def __init__(self, entries, parent=None, layout=None):
        self.setSizeGripEnabled(True)
        super().__init__(parent)
        self.setWindowTitle('Graph Layout')
        self.setMinimumSize(720, 460)
        seen = set()
        self.entries = []
        for entry in entries:
            if layout_eligible(entry) and _identity(entry) not in seen:
                self.entries.append(entry)
                seen.add(_identity(entry))
        self._selected_indices = []
        self._accepted_settings = None
        initial = layout.get('result', layout) if isinstance(layout, dict) else {}
        for entry in initial.get('graphs', []):
            if not layout_eligible(entry):
                continue
            identity = _identity(entry)
            index = next((i for i, existing in enumerate(self.entries) if _identity(existing) == identity), None)
            if index is None:
                index = len(self.entries)
                self.entries.append(entry)
            if index not in self._selected_indices:
                self._selected_indices.append(index)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title = QLineEdit(str(initial.get('title', 'Graph Layout')))
        self.title.setMaxLength(145)
        form.addRow('Title:', self.title)
        dimensions = QHBoxLayout()
        self.rows = QSpinBox(); self.rows.setRange(1, 9); self.rows.setValue(initial.get('rows', 2))
        self.columns = QSpinBox(); self.columns.setRange(1, 9); self.columns.setValue(initial.get('columns', 2))
        dimensions.addWidget(QLabel('Rows:')); dimensions.addWidget(self.rows)
        dimensions.addWidget(QLabel('Columns:')); dimensions.addWidget(self.columns)
        dimensions.addStretch()
        form.addRow(dimensions)
        layout.addLayout(form)
        body = QHBoxLayout()
        left = QVBoxLayout(); left.addWidget(QLabel('Available graphs'))
        self.available = QListWidget()
        self.available.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        left.addWidget(self.available); body.addLayout(left, 1)
        transfers = QVBoxLayout(); transfers.addSpacing(26)
        self.add_button = QPushButton('Add >')
        self.remove_button = QPushButton('< Remove')
        self.up_button = QPushButton('Move Up')
        self.down_button = QPushButton('Move Down')
        for button, callback in ((self.add_button, self.add_entries),
                                 (self.remove_button, self.remove_entries),
                                 (self.up_button, lambda: self.move_selected(-1)),
                                 (self.down_button, lambda: self.move_selected(1))):
            button.setAutoDefault(False); button.clicked.connect(callback); transfers.addWidget(button)
        transfers.addStretch(); body.addLayout(transfers)
        right = QVBoxLayout(); right.addWidget(QLabel('Graphs in layout (row order)'))
        self.selected = QListWidget()
        self.selected.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        right.addWidget(self.selected); body.addLayout(right, 1)
        layout.addLayout(body, 1)
        self.capacity = QLabel(); layout.addWidget(self.capacity)
        self.error = QLabel(); self.error.setObjectName('error'); self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Finish')
        self.buttons.accepted.connect(self.validate); self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.controls = dict(rows=self.rows, columns=self.columns, title=self.title)
        self.available.itemDoubleClicked.connect(lambda item: self.add_entries())
        self.selected.itemDoubleClicked.connect(lambda item: self.remove_entries())
        self.rows.valueChanged.connect(self._capacity_changed)
        self.columns.valueChanged.connect(self._capacity_changed)
        self._render()

    def _label(self, index):
        entry = self.entries[index]
        title = str(entry.get('title') or entry.get('result', {}).get('title') or 'Graph')
        worksheet = entry.get('worksheet_name')
        return title + ('  [' + str(worksheet) + ']' if worksheet else '')

    def _render(self, highlight=()):
        self.available.clear(); self.selected.clear()
        for index in range(len(self.entries)):
            if index not in self._selected_indices:
                item = QListWidgetItem(self._label(index)); item.setData(Qt.ItemDataRole.UserRole, index)
                self.available.addItem(item)
        for index in self._selected_indices:
            item = QListWidgetItem(self._label(index)); item.setData(Qt.ItemDataRole.UserRole, index)
            self.selected.addItem(item); item.setSelected(index in highlight)
        self._capacity_changed()

    def _capacity_changed(self, *args):
        capacity = self.rows.value() * self.columns.value()
        count = len(self._selected_indices)
        self.capacity.setText(str(count) + ' selected · ' + str(capacity) + ' cells · up to 16 graphs · row order')
        self.error.setText('A layout supports at most 16 selected graphs.' if count > 16 else
                           'Selected graphs exceed layout capacity. Increase rows/columns or remove graphs.'
                           if count > capacity else '')

    def add_entries(self):
        added = [item.data(Qt.ItemDataRole.UserRole) for item in self.available.selectedItems()]
        self._selected_indices.extend(i for i in added if i not in self._selected_indices)
        self._render(added)

    def remove_entries(self):
        removed = {item.data(Qt.ItemDataRole.UserRole) for item in self.selected.selectedItems()}
        self._selected_indices = [i for i in self._selected_indices if i not in removed]
        self._render()

    def move_selected(self, direction):
        chosen = {item.data(Qt.ItemDataRole.UserRole) for item in self.selected.selectedItems()}
        positions = range(len(self._selected_indices)) if direction < 0 else range(len(self._selected_indices) - 1, -1, -1)
        for position in positions:
            destination = position + (-1 if direction < 0 else 1)
            if (0 <= destination < len(self._selected_indices)
                    and self._selected_indices[position] in chosen
                    and self._selected_indices[destination] not in chosen):
                self._selected_indices[position], self._selected_indices[destination] = self._selected_indices[destination], self._selected_indices[position]
        self._render(chosen)

    def selected_entries(self):
        """Return ordered original references; build_layout creates snapshots."""
        return [self.entries[index] for index in self._selected_indices]

    def settings(self):
        return dict(rows=self.rows.value(), columns=self.columns.value(), title=self.title.text())

    def validate(self):
        try:
            build_layout(self.selected_entries(), **self.settings())
        except ValueError as exc:
            self.error.setText(str(exc)); return False
        self._accepted_settings = self.settings()
        self.error.clear(); self.accept(); return True
