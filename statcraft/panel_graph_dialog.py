"""Compact BY-variable selection for independently recalculated graph panels."""
import copy

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel,
    QComboBox, QCheckBox, QDialogButtonBox)

from .panel_graphs import build_panels, validate_parameters
from .variable_dialogs import format_variable_reference


class PanelGraphDialog(QDialog):
    def __init__(self, worksheet, source_entry, parent=None):
        self.setSizeGripEnabled(True)
        super().__init__(parent)
        self.setWindowTitle('Panel Graph — By Variables')
        self.setMinimumWidth(430)
        self.worksheet = worksheet
        self.source_recipe = copy.deepcopy(source_entry.get('recipe'))
        self.controls = {}
        outer = QVBoxLayout(self)
        note = QLabel('Create a separate panel for each observed BY-variable combination (up to 16 panels).')
        note.setWordWrap(True)
        outer.addWidget(note)
        form = QFormLayout()
        eligible = [(i, format_variable_reference(i, worksheet)) for i, column
                    in enumerate(worksheet.columns) if column.kind in ('number', 'text')]
        for key, label, optional in (('by_index', 'By variable:', False),
                                     ('second_by_index', 'Second by variable:', True)):
            control = QComboBox()
            control.addItem('(None)' if optional else '(Select a variable)', None)
            for index, text in eligible:
                control.addItem(text, index)
            self.controls[key] = control
            form.addRow(label, control)
        for key, label in (('shared_x', 'Use the same X scale in each panel'),
                           ('shared_y', 'Use the same Y scale in each panel')):
            control = QCheckBox(label)
            control.setChecked(True)
            self.controls[key] = control
            form.addRow('', control)
        outer.addLayout(form)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #a00000;')
        self.error.hide()
        outer.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                        QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        outer.addWidget(self.buttons)

    def settings(self):
        first = self.controls['by_index'].currentData()
        second = self.controls['second_by_index'].currentData()
        indices = [first] if second is None else [first, second]
        return validate_parameters(self.source_recipe, indices,
            self.controls['shared_x'].isChecked(), self.controls['shared_y'].isChecked())

    def accept(self):
        try:
            parameters = self.settings()
            # Validate every subset before closing; a singleton fit or missing
            # response is reported with its BY label rather than losing the dialog.
            build_panels(self.worksheet, **parameters)
        except (ValueError, ArithmeticError) as exc:
            self.error.setText(str(exc))
            self.error.show()
            return
        self.error.hide()
        super().accept()
