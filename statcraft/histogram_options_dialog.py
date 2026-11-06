"""Original Scales/Fits dialog; native labels are resource-guided only."""
from copy import deepcopy

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QGroupBox, QLabel, QSpinBox, QVBoxLayout)

from .histogram_options import build_histogram_panel, validate_histogram_settings


class HistogramOptionsDialog(QDialog):
    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(True)
        self.setWindowTitle('Histogram Options')
        self.setMinimumWidth(440)
        self.entry = entry if isinstance(entry, dict) else {}
        result = self.entry.get('result', self.entry)
        self.source = deepcopy(result.get('histogram_source')) if isinstance(result, dict) else None
        initial_error = ''
        try:
            defaults={'bins':max(2,min(1000,self.entry.get('recipe',{}).get('parameters',{}).get('bins',10)))}
            initial = validate_histogram_settings(self.entry.get('histogram_settings', defaults))
        except ValueError as exc:
            initial = validate_histogram_settings({})
            initial_error = str(exc)
        self._settings = None
        layout = QVBoxLayout(self)
        scales = QGroupBox('Scales')
        form = QFormLayout(scales)
        self.bins = QSpinBox()
        self.bins.setRange(2, 1000)
        self.bins.setValue(initial['bins'])
        form.addRow('Number of intervals:', self.bins)
        self.scale = QComboBox()
        self.scale.addItems(['Frequency', 'Percent', 'Density'])
        self.scale.setCurrentText(initial['scale'])
        form.addRow('Y scale:', self.scale)
        self.cumulative = QCheckBox('Cumulative')
        self.cumulative.setChecked(initial['cumulative'])
        self.scale.currentTextChanged.connect(self._scale_changed)
        self._scale_changed(self.scale.currentText())
        form.addRow(self.cumulative)
        layout.addWidget(scales)
        fits = QGroupBox('Fits')
        fit_form = QFormLayout(fits)
        self.fit = QComboBox()
        self.fit.addItems(['None', 'Normal'])
        self.fit.setCurrentText(initial['fit'] or 'None')
        fit_form.addRow('Distribution:', self.fit)
        layout.addWidget(fits)
        note = QLabel('Equal-width intervals; Normal fit uses the sample mean and '
                      'sample standard deviation. Native numerical equivalence is unverified.')
        note.setWordWrap(True)
        note.setObjectName('secondary')
        layout.addWidget(note)
        self.error = QLabel(initial_error)
        self.error.setWordWrap(True)
        self.error.setObjectName('error')
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                       QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        if not isinstance(self.source, (list, tuple)) or not self.source:
            self.error.setText('Original observations are unavailable. Rerun this histogram to enable interval and fit editing.')
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            scales.setEnabled(False)
            fits.setEnabled(False)

    def _scale_changed(self,scale):
        self.cumulative.setEnabled(scale!='Density')
        if scale=='Density':self.cumulative.setChecked(False)

    def validate(self):
        try:
            settings = validate_histogram_settings(dict(
                bins=self.bins.value(), scale=self.scale.currentText(),
                cumulative=self.cumulative.isChecked(),
                fit=None if self.fit.currentText() == 'None' else self.fit.currentText()))
            build_histogram_panel(self.source, settings)
        except ValueError as exc:
            self.error.setText(str(exc))
            return False
        self._settings = settings
        self.error.clear()
        self.accept()
        return True

    def settings(self):
        """Return a detached accepted configuration, or None before acceptance."""
        return deepcopy(self._settings)
