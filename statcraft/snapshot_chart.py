"""Shared output-window contract for the newer standalone QPainter plots.

These renderers support output annotations and capture. They do not advertise
series/axis style editing until their individual painters implement it.
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from .graph_interaction import GraphInteractionMixin


class SnapshotChartWidget(GraphInteractionMixin, QWidget):
    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.entry = entry if 'result' in entry else {'result': entry}
        self.panels = [{'kind': 'snapshot'}]
        self._init_graph_interaction()
        self.setMouseTracking(True)

    def editable_objects(self):
        return []
