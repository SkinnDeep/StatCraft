"""Original Qt factorial term selector, guided by resource dialog 3622.

The editable factor context is a StatCraft addition. Terms contain zero-based
positions within factor_indices, rather than worksheet column numbers.
"""
from itertools import combinations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout)

from .variable_dialogs import resolve_variables


class FactorialTermsDialog(QDialog):
    def __init__(self, parent, worksheet, factor_indices, max_order=2,
                 selected_terms=None, include_blocks=None):
        super().__init__(parent)
        self.setWindowTitle('Analyze Factorial Design: Terms')
        self.setMinimumSize(680, 460)
        self.worksheet = worksheet
        self.factor_indices = []
        self.max_order = max(1, min(3, int(max_order)))
        self.selected_terms = []
        self._chosen = set()
        layout = QVBoxLayout(self)

        factors_row = QHBoxLayout()
        factors_row.addWidget(QLabel('Factor columns:'))
        self.factor_entry = QLineEdit()
        self.factor_entry.setPlaceholderText('C5 C6 C7')
        self.factor_entry.setText(' '.join('C' + str(i + 1) for i in factor_indices))
        factors_row.addWidget(self.factor_entry, 1)
        self.apply_button = QPushButton('Apply')
        self.apply_button.setAutoDefault(False)
        self.apply_button.clicked.connect(lambda: self.apply_factors())
        factors_row.addWidget(self.apply_button)
        layout.addLayout(factors_row)
        note = QLabel('Applying different factor columns resets terms to defaults. '
                      'Use 2 to 8 numeric columns.')
        note.setObjectName('secondary')
        note.setWordWrap(True)
        layout.addWidget(note)

        order_row = QHBoxLayout()
        order_row.addWidget(QLabel('Include terms in the model up through order:'))
        self.order_combo = QComboBox()
        self.order_combo.addItems(['1', '2', '3'])
        self.order_combo.setCurrentText(str(self.max_order))
        self.order = self.order_combo
        order_row.addWidget(self.order_combo)
        order_row.addStretch()
        layout.addLayout(order_row)

        lists = QHBoxLayout()
        available_column = QVBoxLayout()
        available_column.addWidget(QLabel('Available Terms'))
        self.available = QListWidget()
        self.available.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        available_column.addWidget(self.available)
        lists.addLayout(available_column, 1)
        transfers = QVBoxLayout()
        transfers.addSpacing(26)
        for label, callback, tooltip in (
                ('>', lambda: self.add_terms(), 'Add selected terms and their lower-order terms'),
                ('>>', lambda: self.add_terms(True), 'Add all available terms'),
                ('<', lambda: self.remove_terms(), 'Remove selected terms and interactions containing them'),
                ('<<', lambda: self.remove_terms(True), 'Remove all terms')):
            button = QPushButton(label)
            button.setAutoDefault(False)
            button.setToolTip(tooltip)
            button.clicked.connect(callback)
            transfers.addWidget(button)
        cross = QPushButton('Cross')
        cross.setEnabled(False)
        cross.setToolTip('Cross-term generation is not implemented. Select an interaction from Available Terms.')
        transfers.addWidget(cross)
        default_button = QPushButton('Default')
        default_button.setAutoDefault(False)
        default_button.setToolTip('Select every term through the chosen order')
        default_button.clicked.connect(lambda: self.defaults())
        transfers.addWidget(default_button)
        transfers.addStretch()
        lists.addLayout(transfers)
        selected_column = QVBoxLayout()
        selected_column.addWidget(QLabel('Selected Terms'))
        self.selected = QListWidget()
        self.selected.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        selected_column.addWidget(self.selected)
        lists.addLayout(selected_column, 1)
        layout.addLayout(lists, 1)
        self.available.itemDoubleClicked.connect(lambda item: self.add_terms())
        self.selected.itemDoubleClicked.connect(lambda item: self.remove_terms())

        b_col = next((c for c in worksheet.columns if c.name.casefold() == 'blocks'), None)
        has_blocks = False
        if b_col is not None:
            levels = set(v for v in b_col.values if v is not None)
            has_blocks = len(levels) > 1
        self.include_blocks = QCheckBox('Include blocks in the model')
        self.include_blocks.setEnabled(has_blocks)
        initial_block_check = (include_blocks if include_blocks is not None else has_blocks) and has_blocks
        self.include_blocks.setChecked(initial_block_check)
        if not has_blocks:
            self.include_blocks.setToolTip('Worksheet has only one block.')
        else:
            self.include_blocks.setToolTip('Include block terms in the factorial model.')
        layout.addWidget(self.include_blocks)

        self.include_center_points = QCheckBox('Include center points in the model')
        self.include_center_points.setEnabled(False)
        self.include_center_points.setToolTip('This model term is not implemented in the current factorial analysis.')
        layout.addWidget(self.include_center_points)
        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                 QDialogButtonBox.StandardButton.Cancel)
        footer.accepted.connect(self.validate)
        footer.rejected.connect(self.reject)
        layout.addWidget(footer)
        self.order_combo.currentIndexChanged.connect(self._order_changed)

        if self.apply_factors():
            if selected_terms is not None:
                try:
                    terms = self._checked_terms(selected_terms)
                    if terms:
                        self.order_combo.setCurrentText(str(max(self.max_order, max(map(len, terms)))))
                    self._chosen = self._hierarchy(terms)
                    self._render()
                except ValueError as exc:
                    self._chosen = set()
                    self._render()
                    self.error.setText(str(exc))

    def _checked_terms(self, terms):
        checked = set()
        for term in terms:
            if (not isinstance(term, (list, tuple)) or not 1 <= len(term) <= 3
                    or any(type(i) is not int or not 0 <= i < len(self.factor_indices) for i in term)
                    or len(set(term)) != len(term)):
                raise ValueError('Each term must contain 1 to 3 distinct factor positions.')
            canonical = tuple(sorted(term))
            if canonical in checked:
                raise ValueError('A model term is selected more than once.')
            checked.add(canonical)
        return checked

    @staticmethod
    def _hierarchy(terms):
        return {subset for term in terms for order in range(1, len(term) + 1)
                for subset in combinations(term, order)}

    def _universe(self):
        return {term for order in range(1, min(self.max_order, len(self.factor_indices)) + 1)
                for term in combinations(range(len(self.factor_indices)), order)}

    def _render(self):
        self.available.clear()
        self.selected.clear()
        for target, terms in ((self.available, self._universe() - self._chosen),
                              (self.selected, self._chosen)):
            for term in sorted(terms, key=lambda value: (len(value), value)):
                names = [self.worksheet.columns[self.factor_indices[i]].name
                         or 'C' + str(self.factor_indices[i] + 1) for i in term]
                item = QListWidgetItem('*'.join(names))
                item.setData(Qt.ItemDataRole.UserRole, list(term))
                item.setToolTip(' * '.join('C' + str(self.factor_indices[i] + 1) for i in term))
                target.addItem(item)
        self.selected_terms = [list(term) for term in sorted(self._chosen, key=lambda value: (len(value), value))]

    def apply_factors(self):
        """Apply numeric column context; a changed context resets the model."""
        try:
            indices = resolve_variables(self.factor_entry.text(), self.worksheet)
            if not 2 <= len(indices) <= 8:
                raise ValueError('Choose 2 to 8 distinct numeric factor columns.')
        except ValueError as exc:
            self.error.setText(str(exc))
            return False
        changed = indices != self.factor_indices
        self.factor_indices = list(indices)
        self.factor_entry.setText(' '.join('C' + str(i + 1) for i in indices))
        self.error.clear()
        if changed:
            self.defaults()
        return True

    def _order_changed(self, index):
        self.max_order = int(self.order_combo.currentText())
        self._chosen = {term for term in self._chosen if len(term) <= self.max_order}
        self.error.clear()
        self._render()

    def add_terms(self, all_terms=False):
        """Add selected available terms, including every hierarchical subset."""
        terms = (self._universe() - self._chosen if all_terms else
                 {tuple(item.data(Qt.ItemDataRole.UserRole)) for item in self.available.selectedItems()})
        self._chosen.update(self._hierarchy(terms))
        self.error.clear()
        self._render()

    def remove_terms(self, all_terms=False):
        """Remove selected model terms and every interaction containing them."""
        terms = (set(self._chosen) if all_terms else
                 {tuple(item.data(Qt.ItemDataRole.UserRole)) for item in self.selected.selectedItems()})
        self._chosen = {chosen for chosen in self._chosen
                        if not any(set(term).issubset(chosen) for term in terms)}
        self.error.clear()
        self._render()

    def defaults(self):
        self._chosen = self._universe()
        self.error.clear()
        self._render()

    def validate(self):
        """Validate without modal errors, accept on success, and return bool."""
        try:
            indices = resolve_variables(self.factor_entry.text(), self.worksheet)
            if indices != self.factor_indices:
                raise ValueError('Click Apply to update the factor columns before accepting the model.')
            if not 2 <= len(indices) <= 8:
                raise ValueError('Choose 2 to 8 distinct numeric factor columns.')
            if not self._chosen:
                raise ValueError('Select at least one model term.')
            self._checked_terms(self.selected_terms)
            if self._hierarchy(self._chosen) != self._chosen:
                raise ValueError('Include all lower-order terms for every interaction.')
        except ValueError as exc:
            self.error.setText(str(exc))
            return False
        self.error.clear()
        self.accept()
        return True
