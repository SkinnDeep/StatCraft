"""Multiple-variable capability reports composed from the actual child painters.

This is one scrollable graph composition, with an internal column-count option.
It does not claim separate native graph windows or individual child-axis editing.
"""
import copy
import math
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QGridLayout
from .snapshot_chart import SnapshotChartWidget
from .capability_chart import CapabilityPlotWidget
from .capability_nonnormal_chart import NonnormalCapabilityPlotWidget


class MultipleCapabilityChartWidget(SnapshotChartWidget):
    """Live child widgets ensure screen capture and Office export include every plot."""
    PANEL_WIDTH = 780
    PANEL_HEIGHT = 520
    SPACING = 18
    MARGIN = 4

    def __init__(self, entry, parent=None):
        super().__init__(entry, parent)
        self.error = None
        self.child_charts = []
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        self.grid.setSpacing(self.SPACING)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor('white'))
        self.setPalette(palette)
        self.refresh_composition()

    def refresh_composition(self):
        result = self.entry.get('result', {})
        series = result.get('series')
        if result.get('analysis') != 'multiple_capability' or not isinstance(series, list) or not series:
            raise ValueError('A multiple-capability graph requires at least one analyzed series.')
        method = result.get('method')
        if method not in ('normal', 'nonnormal'):
            raise ValueError('Unsupported multiple-capability graph method.')
        options = result.get('options', {})
        columns = options.get('columns', 2)
        if type(columns) is not int or not 1 <= columns <= 4:
            raise ValueError('Graph layout columns must be an integer from 1 to 4.')
        self.layout_columns = min(columns, len(series))
        self.layout_rows = math.ceil(len(series) / self.layout_columns)
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.child_charts = []
        for index, series_item in enumerate(series):
            if not isinstance(series_item, dict) or not isinstance(series_item.get('result'), dict):
                raise ValueError('Each capability series must contain its analyzed child result.')
            child_result = copy.deepcopy(series_item['result'])
            variable = str(series_item.get('variable_name', child_result.get('variable_name', 'Measurement')))
            label = str(series_item.get('label', variable))
            child_result['variable_name'] = label
            if label != variable:
                child_result['title'] = 'Process Capability Report for ' + label
            child_entry = {'title': 'Process Capability Report for ' + label,
                           'variable_name': label, 'result': child_result}
            child_type = CapabilityPlotWidget if method == 'normal' else NonnormalCapabilityPlotWidget
            child = child_type(child_entry, self)
            child.setMinimumSize(self.PANEL_WIDTH, self.PANEL_HEIGHT)
            child.setObjectName('multipleCapabilityPanel' + str(index + 1))
            child.objectSelected.connect(self.objectSelected)
            child.objectActivated.connect(self.objectActivated)
            self.grid.addWidget(child, index // self.layout_columns, index % self.layout_columns)
            self.child_charts.append(child)
        self.panels = [{'kind': 'snapshot'} for _ in series]
        self.setMinimumSize(self.layout_columns * self.PANEL_WIDTH + (self.layout_columns - 1) * self.SPACING + 2 * self.MARGIN,
                            self.layout_rows * self.PANEL_HEIGHT + (self.layout_rows - 1) * self.SPACING + 2 * self.MARGIN)
        self.grid.activate()
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        return QSize(self.minimumWidth(), self.minimumHeight())


# Descriptive alias retained for callers that use the child report naming pattern.
MultipleCapabilityPlotWidget = MultipleCapabilityChartWidget
