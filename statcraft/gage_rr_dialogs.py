"""Named worksheet roles and supported ANOVA options for crossed Gage R&R."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel,
    QLineEdit, QCheckBox, QPushButton, QDialogButtonBox)
from .variable_dialogs import ProcedureDialog, format_variable_reference
from .gage_rr import settings


class GageRROptionsDialog(QDialog):
    def __init__(self, parent, options):
        super().__init__(parent)
        self.setWindowTitle('Gage R&R Study (Crossed): ANOVA Options')
        self.setMinimumWidth(470)
        self.initial = settings(options)
        self.options = None
        self.controls = {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        for key, label in (
            ('study_multiplier', 'Study variation (number of standard deviations):'),
            ('tolerance', 'Process tolerance (Upper spec − Lower spec):'),
            ('process_stdev', 'Reference process SD (%Process only):'),
            ('interaction_alpha', 'Alpha to remove interaction term:')):
            value = self.initial[key]
            control = QLineEdit('' if value is None else str(value))
            if key in ('tolerance', 'process_stdev'):
                control.setPlaceholderText('Optional')
            self.controls[key] = control
            form.addRow(label, control)
        remove = QCheckBox('Remove nonsignificant Part × Operator interaction')
        remove.setChecked(self.initial['remove_interaction'])
        self.controls['remove_interaction'] = remove
        form.addRow(remove)
        layout.addLayout(form)
        note = QLabel('Tolerance is the positive difference between the upper and lower specifications. '
                      'Reference process SD adds %Process; variance components remain estimated from the study. '
                      'The six study graphs are displayed together.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.error = QLabel()
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def validate(self):
        try:
            values = dict(self.initial)
            for key in ('study_multiplier', 'tolerance', 'process_stdev', 'interaction_alpha'):
                raw = self.controls[key].text().strip()
                values[key] = None if not raw and key in ('tolerance', 'process_stdev') else float(raw)
            values['remove_interaction'] = self.controls['remove_interaction'].isChecked()
            self.options = settings(values)
        except (ValueError, TypeError, OverflowError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()


class GageRRDialog(ProcedureDialog):
    def __init__(self, window):
        selectors = [
            dict(key='part_index', label='Part numbers:', kinds=('number', 'text')),
            dict(key='operator_index', label='Operators:', kinds=('number', 'text')),
            dict(key='measurement_index', label='Measurement data:', kinds=('number',))]
        super().__init__(window, 'Gage R&R Study (Crossed)', window.presenter.worksheet,
                         selectors, (), 'Each operator must measure every part with the same number of repeated measurements. '
                         'This study supports the balanced crossed ANOVA method.')
        self.window = window
        self.options = settings()
        self.entry = None
        method = QLabel('Method of Analysis:  ANOVA')
        self.layout().insertWidget(self.layout().count() - 2, method)
        self.options_button = QPushButton('Options…')
        self.options_button.setAutoDefault(False)
        self.options_button.clicked.connect(self.configure_options)
        self.layout().insertWidget(self.layout().count() - 2, self.options_button)
        self.restore_previous()

    def restore_previous(self):
        presenter = self.window.presenter
        for entry in reversed(presenter.history):
            if entry.get('source_unavailable') or entry.get('recipe', {}).get('action') != 'gage_rr':
                continue
            try:
                if presenter.result_worksheet(entry) is not self.worksheet:
                    continue
                values = entry['recipe']['parameters']
                options = settings(values['options'])
                references = {key: format_variable_reference(values[key], self.worksheet)
                              for key in ('part_index', 'operator_index', 'measurement_index')}
                for key, reference in references.items():
                    self.controls[key].setText(reference)
                self.options = options
            except (IndexError, ValueError, KeyError, TypeError):
                continue
            break

    def roles(self):
        values = self.values()
        if len(set(values.values())) != 3:
            raise ValueError('Choose separate columns for part numbers, operators and measurements.')
        return values

    def configure_options(self):
        dialog = GageRROptionsDialog(self, self.options)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.options = dialog.options

    def validate(self):
        try:
            values = self.roles()
            self.entry = self.window.presenter.gage_rr(**values, options=self.options)
            self.window.refresh()
            self.window.show_result(self.entry)
        except (ValueError, TypeError, IndexError, ArithmeticError) as exc:
            self.error.setText(str(exc))
            return
        self.accept()
