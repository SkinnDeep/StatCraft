"""Scrollable worksheet tabs with external controls independent of data paging.

Native arrow handlers remain unrecovered. This is an original tab-scroll design.
"""
from PySide6.QtCore import Qt,Signal,QTimer
from PySide6.QtWidgets import QScrollArea,QTabBar,QFrame,QSizePolicy


class WorksheetTabStrip(QScrollArea):
    scrollStateChanged=Signal()

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidgetResizable(False)
        self.setMinimumWidth(70)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred)
        self.tabs=QTabBar();self.tabs.setObjectName('worksheetTabs')
        self.tabs.setExpanding(False);self.tabs.setUsesScrollButtons(False)
        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)
        self.setWidget(self.tabs)
        self.horizontalScrollBar().valueChanged.connect(self.scrollStateChanged)
        self.horizontalScrollBar().rangeChanged.connect(lambda *_:self.scrollStateChanged.emit())
        self.tabs.currentChanged.connect(lambda _:QTimer.singleShot(0,self.reveal_current))

    def sync(self):
        self.tabs.resize(max(self.viewport().width(),self.tabs.sizeHint().width()),self.viewport().height())
        self.scrollStateChanged.emit()

    def resizeEvent(self,event):
        super().resizeEvent(event);self.sync()

    def showEvent(self,event):
        super().showEvent(event);self.sync()

    def reveal_current(self):
        index=self.tabs.currentIndex()
        if index<0:return
        self.sync();rect=self.tabs.tabRect(index);scroll=self.horizontalScrollBar()
        if rect.left()<scroll.value():scroll.setValue(rect.left())
        elif rect.right()>=scroll.value()+self.viewport().width():
            scroll.setValue(rect.right()-self.viewport().width()+1)

    def scroll_tabs(self,direction,edge=False):
        self.sync();scroll=self.horizontalScrollBar();position=scroll.value()
        if edge:destination=scroll.minimum() if direction<0 else scroll.maximum()
        else:
            boundaries=[self.tabs.tabRect(i).left() for i in range(self.tabs.count())]
            candidates=[v for v in boundaries if v<position] if direction<0 else [v for v in boundaries if v>position]
            destination=(max(candidates) if candidates else 0) if direction<0 else (min(candidates) if candidates else scroll.maximum())
        scroll.setValue(destination)
