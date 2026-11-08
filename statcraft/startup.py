"""Instant startup and optional splash with project path support."""
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QElapsedTimer
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPen
from PySide6.QtWidgets import QSplashScreen


def splash_pixmap():
    pixmap = QPixmap(560, 280)
    pixmap.fill(QColor('#f4f4f4'))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.fillRect(0, 0, 8, 280, QColor('#00569a'))
    painter.setPen(QPen(QColor('#00569a'), 3))
    from PySide6.QtCore import QPointF
    import math
    points = [QPointF(40 + i, 166 - 58 * math.exp(-((i - 35) / 15) ** 2)) for i in range(71)]
    for a, b in zip(points, points[1:]):
        painter.drawLine(a, b)
    painter.setPen(QColor('#202020'))
    font = QFont('Segoe UI', 32)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(138, 146, 'StatCraft')
    painter.setFont(QFont('Segoe UI', 11))
    painter.setPen(QColor('#555555'))
    painter.drawText(140, 175, 'Statistics and data analysis')
    painter.setFont(QFont('Segoe UI', 9))
    painter.drawText(28, 250, 'Starting workspace…')
    painter.end()
    return pixmap


def start_window(app, window_factory, arguments=(), minimum_ms=0):
    """Return a controller kept alive by app; instant window creation with zero splash delay when minimum_ms=0."""
    if minimum_ms <= 0:
        state = {'splash': None, 'window': None, 'ready': False, 'error': None}
        try:
            window = window_factory()
            state['window'] = window
            paths = [value for value in arguments if not str(value).startswith('-')]
            if paths:
                window.load_path(Path(paths[0]))
            state['ready'] = True
            window.showMaximized()
        except Exception as exc:
            state['error'] = str(exc)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, 'StatCraft startup', str(exc))
            app.exit(1)
        app._statcraft_startup = state
        return state

    splash = QSplashScreen(splash_pixmap(), Qt.WindowType.WindowStaysOnTopHint)
    splash.show()
    timer = QElapsedTimer()
    timer.start()
    state = {'splash': splash, 'window': None, 'ready': False, 'error': None}

    def construct():
        try:
            window = window_factory()
            state['window'] = window
            paths = [value for value in arguments if not str(value).startswith('-')]
            if paths:
                window.load_path(Path(paths[0]))
            state['ready'] = True

            def reveal():
                window.showMaximized()
                splash.finish(window)

            QTimer.singleShot(max(0, minimum_ms - timer.elapsed()), reveal)
        except Exception as exc:
            state['error'] = str(exc)
            splash.close()
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, 'StatCraft startup', str(exc))
            app.exit(1)

    QTimer.singleShot(0, construct)
    app._statcraft_startup = state
    return state


def dispose_startup(app):
    from PySide6.QtCore import QCoreApplication, QEvent
    from shiboken6 import isValid
    state = getattr(app, '_statcraft_startup', {})
    for key in ('window', 'splash'):
        widget = state.get(key)
        if widget is not None and isValid(widget):
            widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    state.clear()
