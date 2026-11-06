"""Original Qt desktop workflow. Backend contracts remain in Presenter.

Qt Widgets and Qt Print Support provide the desktop interface. Native package content remains inert;
unsupported native features are not exposed as working procedures.
"""
import math
import copy
from pathlib import Path
import sys
from PySide6.QtCore import Qt, QSize, QSignalBlocker, QRectF, QPointF, QTimer, QSettings
from PySide6.QtGui import (
    QAction, QKeySequence, QIcon, QFont, QPalette, QColor, QPixmap,
    QPainter, QPen, QPolygonF, QActionGroup,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QLabel, QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox, QToolBar, QStyle,
    QTabWidget, QScrollArea, QPlainTextEdit, QDialog, QDialogButtonBox,
    QFormLayout, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QMessageBox, QFileDialog, QInputDialog, QCheckBox, QTabBar, QMenu,
    QToolButton, QSlider, QRadioButton, QGroupBox, QGridLayout, QFrame,QTableWidgetSelectionRange,
    QStackedWidget, QSizePolicy,
)
from .app import Presenter, format_entry, _display, _number_list
from .model import Column, finite_number, display_date
from .modern_worksheet import WorksheetTable, WorksheetHeaderView, WorksheetDelegate
from .modern_icons import tool_icon
from .io import MAX_CELLS
from .variable_dialogs import (
    ProcedureDialog, ScatterDialog, ScatterTypeDialog,
    format_variable_reference, resolve_variables,
)


def label(text, role=None):
    widget = QLabel(str(text))
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if role: widget.setObjectName(role)
    widget.setWordWrap(True)
    return widget


def display(value):
    if isinstance(value, (list, tuple)):
        return ", ".join(_display(v) for v in value)
    return _display(value)


def numeric(key, title, default="", optional=False, integer=False):
    return {"key": key, "label": title, "default": default, "numeric": True, "optional": optional, "integer": integer}


def selector(key, title, multiple=False, minimum=1, maximum=None, kinds=("number",)):
    return {"key": key, "label": title, "multiple": multiple, "minimum": minimum, "maximum": maximum, "kinds": kinds}


class WelcomeWatermarkWidget(QWidget):
    """Statistical `#e6e6e6` output-pane watermark with centered title, mark, and shortcut table."""
    def __init__(self, on_open, on_new_project, on_new_worksheet, on_try_connect=None, on_overview=None, parent=None):
        super().__init__(parent)
        self.setObjectName("welcomeStage")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.addStretch(2)

        center = QWidget()
        center.setObjectName("welcomeCard")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(8)

        logo = WelcomeLogoBanner()
        center_layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)

        tagline = QLabel("Modern Statistical Analysis & Quality Engineering Software")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet("color: #64748b; font-size: 9pt; font-style: italic; padding-bottom: 4px;")
        center_layout.addWidget(tagline)

        shortcuts = QWidget()
        grid = QGridLayout(shortcuts)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(22)
        grid.setVerticalSpacing(6)
        rows = [
            ("Open Project", "Ctrl+O", on_open),
            ("New Project", "Ctrl+Shift+N", on_new_project),
            ("New Worksheet", "Ctrl+N", on_new_worksheet),
            ("Sample Data (Chemical Process)", "Dataset", on_try_connect),
        ]
        for row_idx, (action_label, accel, callback) in enumerate(rows):
            btn = QPushButton(action_label)
            btn.setObjectName("watermarkLink")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFlat(True)
            btn.clicked.connect(callback)
            key_lbl = QLabel(accel)
            key_lbl.setObjectName("watermarkKey")
            grid.addWidget(btn, row_idx, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(key_lbl, row_idx, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        center_layout.addWidget(shortcuts, 0, Qt.AlignmentFlag.AlignHCenter)

        outer.addWidget(center, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(3)


class WelcomeLogoBanner(QWidget):
    """Paints the original StatCraft watermark wordmark and Gaussian-curve + diamond emblem."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(304, 58)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor("#bcbcbc"))
        font = QFont("Segoe UI", 28, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QRectF(0, 2, 215, 50), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "StatCraft")
        # Original StatCraft emblem: rounded badge with Gaussian distribution curve + peak diamond
        p.setPen(QPen(QColor("#b8b8b8"), 2.0))
        p.setBrush(QColor("#dcdcdc"))
        p.drawRoundedRect(QRectF(226, 8, 44, 42), 9, 9)
        pts = []
        for i in range(25):
            x = 231.0 + i * (34.0 / 24.0)
            z = (i - 12) / 5.2
            y = 43.0 - 22.0 * math.exp(-0.5 * z * z)
            pts.append(QPointF(x, y))
        poly_fill = [QPointF(231.0, 43.0)] + pts + [QPointF(265.0, 43.0)]
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#c8c8c8"))
        p.drawPolygon(QPolygonF(poly_fill))
        p.setPen(QPen(QColor("#9e9e9e"), 2.3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolyline(QPolygonF(pts))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#a6a6a6"))
        cx, cy, r = 248.0, 19.0, 4.2
        p.drawPolygon(QPolygonF([QPointF(cx, cy - r), QPointF(cx + r, cy), QPointF(cx, cy + r), QPointF(cx - r, cy)]))
        p.end()



def apply_theme_palette(app, is_dark: bool) -> None:
    if not app:
        return
    app.styleHints().setColorScheme(Qt.ColorScheme.Dark if is_dark else Qt.ColorScheme.Light)
    palette = QPalette()
    if is_dark:
        for grp in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            palette.setColor(grp, QPalette.ColorRole.Window, QColor('#18181b'))
            palette.setColor(grp, QPalette.ColorRole.WindowText, QColor('#f4f4f5'))
            palette.setColor(grp, QPalette.ColorRole.Base, QColor('#1f1f23'))
            palette.setColor(grp, QPalette.ColorRole.AlternateBase, QColor('#27272a'))
            palette.setColor(grp, QPalette.ColorRole.ToolTipBase, QColor('#09090b'))
            palette.setColor(grp, QPalette.ColorRole.ToolTipText, QColor('#f4f4f5'))
            palette.setColor(grp, QPalette.ColorRole.Text, QColor('#f4f4f5'))
            palette.setColor(grp, QPalette.ColorRole.Button, QColor('#27272a'))
            palette.setColor(grp, QPalette.ColorRole.ButtonText, QColor('#f4f4f5'))
            palette.setColor(grp, QPalette.ColorRole.BrightText, QColor('#ffffff'))
            palette.setColor(grp, QPalette.ColorRole.Light, QColor('#3f3f46'))
            palette.setColor(grp, QPalette.ColorRole.Midlight, QColor('#27272a'))
            palette.setColor(grp, QPalette.ColorRole.Dark, QColor('#09090b'))
            palette.setColor(grp, QPalette.ColorRole.Mid, QColor('#18181b'))
            palette.setColor(grp, QPalette.ColorRole.Shadow, QColor('#000000'))
            palette.setColor(grp, QPalette.ColorRole.Highlight, QColor('#0284c7'))
            palette.setColor(grp, QPalette.ColorRole.HighlightedText, QColor('#ffffff'))
            palette.setColor(grp, QPalette.ColorRole.PlaceholderText, QColor('#71717a'))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Window, QColor('#18181b'))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor('#71717a'))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor('#71717a'))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor('#71717a'))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor('#18181b'))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor('#18181b'))
    else:
        for grp in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            palette.setColor(grp, QPalette.ColorRole.Window, QColor('#f8fafc'))
            palette.setColor(grp, QPalette.ColorRole.WindowText, QColor('#1e293b'))
            palette.setColor(grp, QPalette.ColorRole.Base, QColor('#ffffff'))
            palette.setColor(grp, QPalette.ColorRole.AlternateBase, QColor('#f1f5f9'))
            palette.setColor(grp, QPalette.ColorRole.ToolTipBase, QColor('#0f172a'))
            palette.setColor(grp, QPalette.ColorRole.ToolTipText, QColor('#ffffff'))
            palette.setColor(grp, QPalette.ColorRole.Text, QColor('#1e293b'))
            palette.setColor(grp, QPalette.ColorRole.Button, QColor('#f8fafc'))
            palette.setColor(grp, QPalette.ColorRole.ButtonText, QColor('#1e293b'))
            palette.setColor(grp, QPalette.ColorRole.BrightText, QColor('#ffffff'))
            palette.setColor(grp, QPalette.ColorRole.Light, QColor('#ffffff'))
            palette.setColor(grp, QPalette.ColorRole.Midlight, QColor('#e2e8f0'))
            palette.setColor(grp, QPalette.ColorRole.Dark, QColor('#94a3b8'))
            palette.setColor(grp, QPalette.ColorRole.Mid, QColor('#cbd5e1'))
            palette.setColor(grp, QPalette.ColorRole.Shadow, QColor('#64748b'))
            palette.setColor(grp, QPalette.ColorRole.Highlight, QColor('#e0f2fe'))
            palette.setColor(grp, QPalette.ColorRole.HighlightedText, QColor('#0369a1'))
            palette.setColor(grp, QPalette.ColorRole.PlaceholderText, QColor('#94a3b8'))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Window, QColor('#f8fafc'))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor('#94a3b8'))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor('#94a3b8'))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor('#94a3b8'))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, QColor('#f1f5f9'))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, QColor('#f1f5f9'))
    app.setPalette(palette)


def get_theme_stylesheet(is_dark: bool) -> str:
    if is_dark:
        return """
            QMainWindow, QDialog { background-color: #18181b; color: #f4f4f5; }
            QWidget { font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Roboto', 'Helvetica Neue', sans-serif; font-size: 9pt; color: #f4f4f5; }
            QMenuBar { background-color: #18181b; border-bottom: 1px solid #27272a; padding: 2px 4px; }
            QMenuBar::item { padding: 4px 10px; background: transparent; border-radius: 4px; color: #e4e4e7; }
            QMenuBar::item:selected { background-color: #27272a; color: #38bdf8; }
            QMenu { background-color: #1f1f23; border: 1px solid #3f3f46; border-radius: 6px; padding: 4px; color: #f4f4f5; }
            QMenu::item { padding: 6px 28px 6px 24px; border-radius: 4px; color: #e4e4e7; }
            QMenu::item:selected { background-color: #0284c7; color: #ffffff; }
            QMenu::separator { height: 1px; background-color: #3f3f46; margin: 4px 6px; }
            QToolBar { background-color: #18181b; border-top: none; border-bottom: 1px solid #27272a; padding: 2px 6px; spacing: 3px; }
            QToolBar::separator { width: 1px; background-color: #3f3f46; margin: 4px 5px; }
            QToolButton { padding: 4px; border: 1px solid transparent; border-radius: 4px; background: transparent; color: #e4e4e7; }
            QToolButton:hover { background-color: #27272a; border: 1px solid #3f3f46; color: #38bdf8; }
            QToolButton:pressed, QToolButton:checked { background-color: #27272a; border: 1px solid #0284c7; color: #38bdf8; }
            QSplitter::handle { background-color: #27272a; }
            QSplitter::handle:horizontal { width: 2px; }
            QSplitter::handle:vertical { height: 2px; }
            QSplitter::handle:hover { background-color: #0284c7; }
            QWidget#navigatorPane { background-color: #18181b; border-right: 1px solid #27272a; }
            QWidget#navigatorHeader { background-color: #1f1f23; border-bottom: 1px solid #27272a; }
            QLabel#navigatorTitle { font-size: 9.5pt; font-weight: 600; color: #f4f4f5; padding-left: 6px; }
            QTreeWidget { background-color: #18181b; border: none; padding: 4px 0px; font-size: 9pt; color: #e4e4e7; outline: 0; }
            QTreeWidget::item { padding: 5px 8px; border-left: 3px solid transparent; border-radius: 3px; color: #d4d4d8; margin: 1px 4px; }
            QTreeWidget::item:hover { background-color: #27272a; color: #ffffff; }
            QTreeWidget::item:selected { background-color: #094771; color: #ffffff; font-weight: 600; border-left: 3px solid #38bdf8; }
            QWidget#outputPane, QWidget#welcomeStage, QWidget#welcomeCard { background-color: #09090b; }
            QWidget#outputHeaderBar { background-color: #18181b; border-bottom: 1px solid #27272a; }
            QToolButton#outputDropdownBtn {
                background-color: #27272a; border: 1px solid #3f3f46; border-radius: 4px;
                padding: 3px 8px; font-size: 9pt; font-weight: 600; color: #e4e4e7;
            }
            QToolButton#outputDropdownBtn:hover { background-color: #3f3f46; border-color: #0284c7; color: #38bdf8; }
            QPushButton#watermarkLink {
                background: transparent; border: none; color: #a1a1aa;
                font-size: 9.5pt; font-weight: 600; text-align: left; padding: 1px 2px;
            }
            QPushButton#watermarkLink:hover { color: #38bdf8; text-decoration: underline; }
            QLabel#watermarkKey { background: transparent; color: #a1a1aa; font-size: 9.5pt; font-weight: 600; }
            QTableWidget {
                background-color: #18181b; color: #f4f4f5; gridline-color: #27272a; border: none;
                selection-background-color: #094771; selection-color: #ffffff;
                font-size: 9pt;
            }
            QTableWidget#columnNamesTable {
                background-color: #1f1f23; color: #f4f4f5; gridline-color: #27272a;
                border-top: 1px solid #3f3f46; border-bottom: 1px solid #3f3f46;
            }
            QHeaderView::section {
                background-color: #27272a; color: #d4d4d8; border: none;
                border-right: 1px solid #3f3f46; border-bottom: 1px solid #3f3f46;
                padding: 2px 6px; font-weight: 500; font-size: 8.5pt;
            }
            QHeaderView::section:hover { background-color: #3f3f46; color: #ffffff; }
            QWidget#sheetChromeBar { background-color: #18181b; border-top: 1px solid #27272a; }
            QPushButton#chromeNavButton {
                background-color: #18181b; border: none; border-right: 1px solid #27272a;
                padding: 3px 6px; min-height: 20px; color: #a1a1aa; font-size: 8.5pt;
            }
            QPushButton#chromeNavButton:hover { background-color: #27272a; color: #38bdf8; }
            QTabWidget::pane { background-color: #18181b; border: none; }
            QTabBar::tab {
                background-color: #27272a; color: #a1a1aa; padding: 6px 16px;
                border: 1px solid #3f3f46; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px;
                margin-right: 2px; font-size: 9pt;
            }
            QTabBar::tab:hover { background-color: #3f3f46; color: #ffffff; }
            QTabBar::tab:selected {
                background-color: #18181b; color: #ffffff; border-color: #3f3f46;
                border-top: 3px solid #0284c7; font-weight: 600;
            }
            QTabBar#worksheetTabs { background-color: #18181b; }
            QTabBar#worksheetTabs::tab {
                background-color: #27272a; color: #a1a1aa; padding: 4px 16px;
                border: none; border-right: 1px solid #3f3f46; font-size: 8.5pt;
            }
            QTabBar#worksheetTabs::tab:hover { background-color: #3f3f46; color: #ffffff; }
            QTabBar#worksheetTabs::tab:selected {
                background-color: #18181b; color: #38bdf8;
                border-bottom: 3px solid #38bdf8; font-weight: 600;
            }
            QWidget#resultCard { background-color: #1f1f23; border: 1px solid #27272a; border-radius: 4px; }
            QLabel#worksheetBadge {
                background-color: #27272a; color: #e4e4e7; border-bottom: 1px solid #3f3f46;
                padding: 6px 12px; font-size: 8.5pt; font-weight: 700;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #27272a; color: #f4f4f5; border: 1px solid #3f3f46; border-radius: 4px;
                padding: 4px 8px; min-height: 20px; selection-background-color: #094771; selection-color: #ffffff;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #0284c7; background-color: #27272a;
            }
            QLineEdit:disabled, QComboBox:disabled {
                background-color: #18181b; color: #71717a; border-color: #27272a;
            }
            QComboBox::drop-down { border: none; width: 20px; background: transparent; }
            QComboBox::down-arrow {
                width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent;
                border-top: 5px solid #a1a1aa; margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #1f1f23; color: #f4f4f5; border: 1px solid #3f3f46; border-radius: 4px;
                selection-background-color: #094771; selection-color: #ffffff; padding: 2px;
            }
            QListWidget { background-color: #1f1f23; color: #f4f4f5; border: 1px solid #3f3f46; border-radius: 4px; }
            QListWidget::item { padding: 4px 6px; border-radius: 2px; }
            QListWidget::item:hover { background-color: #27272a; color: #ffffff; }
            QListWidget::item:selected { background-color: #094771; color: #ffffff; }
            QGroupBox {
                background-color: #1f1f23; color: #f4f4f5; border: 1px solid #27272a;
                border-radius: 6px; margin-top: 14px; padding: 12px 10px 10px 10px; font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin; subcontrol-position: top left; left: 10px;
                padding: 0 4px; background-color: #1f1f23; color: #38bdf8;
            }
            QRadioButton, QCheckBox { color: #f4f4f5; spacing: 6px; background: transparent; }
            QRadioButton:disabled, QCheckBox:disabled { color: #71717a; }
            QRadioButton::indicator {
                width: 14px; height: 14px; border-radius: 7px;
                border: 1px solid #71717a; background-color: #27272a;
            }
            QRadioButton::indicator:hover { border-color: #0284c7; }
            QRadioButton::indicator:checked {
                border: 1px solid #0284c7;
                background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #0284c7, stop:0.55 #0284c7, stop:0.65 #27272a, stop:1 #27272a);
            }
            QCheckBox::indicator {
                width: 14px; height: 14px; border-radius: 3px;
                border: 1px solid #71717a; background-color: #27272a;
            }
            QCheckBox::indicator:hover { border-color: #0284c7; }
            QCheckBox::indicator:checked {
                border-color: #0284c7; background-color: #0284c7;
            }
            QPushButton {
                background-color: #27272a; color: #f4f4f5; border: 1px solid #3f3f46; border-radius: 4px;
                padding: 4px 14px; min-height: 22px; font-weight: 500;
            }
            QPushButton:hover { background-color: #3f3f46; border-color: #52525b; color: #ffffff; }
            QPushButton:pressed { background-color: #18181b; border-color: #0284c7; }
            QPushButton:default { background-color: #0284c7; color: #ffffff; border: 1px solid #0369a1; font-weight: 600; }
            QPushButton:default:hover { background-color: #0369a1; }
            QPushButton:disabled { background-color: #18181b; color: #71717a; border-color: #27272a; }
            QLabel#pageHeading { font-size: 11.5pt; font-weight: 700; color: #f4f4f5; }
            QLabel#sectionHeading, QLabel#dialogHeading { font-size: 10pt; font-weight: 700; color: #38bdf8; }
            QLabel#secondary { color: #a1a1aa; font-size: 8.5pt; }
            QLabel#error { color: #f87171; }
            QWidget#commandLinePane { background-color: #18181b; border-left: 1px solid #27272a; }
            QStatusBar {
                background: #18181b; color: #f4f4f5; border-top: 1px solid #27272a; min-height: 24px;
            }
            QStatusBar::item { border: none; }
            QStatusBar QLabel { color: #f4f4f5; background: transparent; font-size: 8.5pt; padding: 0 6px; }
            QStatusBar QToolButton {
                color: #f4f4f5; background: transparent; border: 1px solid transparent;
                padding: 2px 6px; border-radius: 3px; font-size: 8.5pt;
            }
            QStatusBar QToolButton:hover { background: rgba(255, 255, 255, 0.18); border-color: rgba(255, 255, 255, 0.35); }
            QStatusBar QToolButton:checked { background: rgba(0, 0, 0, 0.4); border-color: #0284c7; }
            QSlider#zoomSlider::groove:horizontal { height: 3px; background: rgba(255, 255, 255, 0.25); border-radius: 1px; }
            QSlider#zoomSlider::handle:horizontal { width: 8px; height: 12px; margin: -5px 0; background: #38bdf8; border-radius: 2px; }
            QToolTip {
                background-color: #09090b; color: #ffffff; border: 1px solid #3f3f46;
                border-radius: 4px; padding: 4px 8px; font-size: 8.5pt;
            }
            QScrollBar:vertical {
                background: #18181b; width: 10px; margin: 0px; border: none;
            }
            QScrollBar::handle:vertical {
                background: #3f3f46; min-height: 24px; border-radius: 5px; margin: 2px;
            }
            QScrollBar::handle:vertical:hover { background: #52525b; }
            QScrollBar::handle:vertical:pressed { background: #71717a; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: none; border: none; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
            QScrollBar::horizontal {
                background: #18181b; height: 10px; margin: 0px; border: none;
            }
            QScrollBar::handle:horizontal {
                background: #3f3f46; min-width: 24px; border-radius: 5px; margin: 2px;
            }
            QScrollBar::handle:horizontal:hover { background: #52525b; }
            QScrollBar::handle:horizontal:pressed { background: #71717a; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; background: none; border: none; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
        """
    else:
        return """
            QMainWindow, QDialog { background-color: #f8fafc; color: #1e293b; }
            QWidget { font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Roboto', 'Helvetica Neue', sans-serif; font-size: 9pt; color: #1e293b; }
            QMenuBar { background-color: #f8fafc; border-bottom: 1px solid #e2e8f0; padding: 2px 4px; }
            QMenuBar::item { padding: 4px 10px; background: transparent; border-radius: 4px; color: #1e293b; }
            QMenuBar::item:selected { background-color: #e0f2fe; color: #005a9e; }
            QMenu { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 6px 28px 6px 24px; border-radius: 4px; color: #1e293b; }
            QMenu::item:selected { background-color: #e0f2fe; color: #005a9e; }
            QMenu::separator { height: 1px; background-color: #e2e8f0; margin: 4px 6px; }
            QToolBar { background-color: #f8fafc; border-top: none; border-bottom: 1px solid #e2e8f0; padding: 2px 6px; spacing: 3px; }
            QToolBar::separator { width: 1px; background-color: #cbd5e1; margin: 4px 5px; }
            QToolButton { padding: 4px; border: 1px solid transparent; border-radius: 4px; background: transparent; color: #1e293b; }
            QToolButton:hover { background-color: #e0f2fe; border: 1px solid #bae6fd; color: #005a9e; }
            QToolButton:pressed, QToolButton:checked { background-color: #bae6fd; border: 1px solid #7dd3fc; color: #0369a1; }
            QSplitter::handle { background-color: #cbd5e1; }
            QSplitter::handle:horizontal { width: 2px; }
            QSplitter::handle:vertical { height: 2px; }
            QSplitter::handle:hover { background-color: #005a9e; }
            QWidget#navigatorPane { background-color: #f8fafc; border-right: 1px solid #e2e8f0; }
            QWidget#navigatorHeader { background-color: #ffffff; border-bottom: 1px solid #e2e8f0; }
            QLabel#navigatorTitle { font-size: 9.5pt; font-weight: 600; color: #0f172a; padding-left: 6px; }
            QTreeWidget { background-color: #f8fafc; border: none; padding: 4px 0px; font-size: 9pt; color: #1e293b; outline: 0; }
            QTreeWidget::item { padding: 5px 8px; border-left: 3px solid transparent; border-radius: 3px; color: #334155; margin: 1px 4px; }
            QTreeWidget::item:hover { background-color: #f1f5f9; color: #0f172a; }
            QTreeWidget::item:selected { background-color: #e0f2fe; color: #005a9e; font-weight: 600; border-left: 3px solid #005a9e; }
            QWidget#outputPane, QWidget#welcomeStage, QWidget#welcomeCard { background-color: #f1f5f9; }
            QWidget#outputHeaderBar { background-color: #ffffff; border-bottom: 1px solid #e2e8f0; }
            QToolButton#outputDropdownBtn {
                background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 3px 8px; font-size: 9pt; font-weight: 600; color: #334155;
            }
            QToolButton#outputDropdownBtn:hover { background-color: #e0f2fe; border-color: #005a9e; color: #005a9e; }
            QPushButton#watermarkLink {
                background: transparent; border: none; color: #64748b;
                font-size: 9.5pt; font-weight: 600; text-align: left; padding: 1px 2px;
            }
            QPushButton#watermarkLink:hover { color: #005a9e; text-decoration: underline; }
            QLabel#watermarkKey { background: transparent; color: #64748b; font-size: 9.5pt; font-weight: 600; }
            QTableWidget {
                background-color: #ffffff; color: #0f172a; gridline-color: #e2e8f0; border: none;
                selection-background-color: #e0f2fe; selection-color: #0369a1;
                font-size: 9pt;
            }
            QTableWidget#columnNamesTable {
                background-color: #f8fafc; color: #0f172a; gridline-color: #e2e8f0;
                border-top: 1px solid #cbd5e1; border-bottom: 1px solid #cbd5e1;
            }
            QHeaderView::section {
                background-color: #f1f5f9; color: #475569; border: none;
                border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0;
                padding: 2px 6px; font-weight: 500; font-size: 8.5pt;
            }
            QHeaderView::section:hover { background-color: #e2e8f0; color: #0f172a; }
            QWidget#sheetChromeBar { background-color: #f8fafc; border-top: 1px solid #e2e8f0; }
            QPushButton#chromeNavButton {
                background-color: #f8fafc; border: none; border-right: 1px solid #e2e8f0;
                padding: 3px 6px; min-height: 20px; color: #475569; font-size: 8.5pt;
            }
            QPushButton#chromeNavButton:hover { background-color: #e0f2fe; color: #005a9e; }
            QTabWidget::pane { background-color: #f1f5f9; border: none; }
            QTabBar::tab {
                background-color: #e2e8f0; color: #475569; padding: 6px 16px;
                border: 1px solid #cbd5e1; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px;
                margin-right: 2px; font-size: 9pt;
            }
            QTabBar::tab:hover { background-color: #f1f5f9; color: #0f172a; }
            QTabBar::tab:selected {
                background-color: #ffffff; color: #0f172a; border-color: #cbd5e1;
                border-top: 3px solid #005a9e; font-weight: 600;
            }
            QTabBar#worksheetTabs { background-color: #f8fafc; }
            QTabBar#worksheetTabs::tab {
                background-color: #f1f5f9; color: #475569; padding: 4px 16px;
                border: none; border-right: 1px solid #e2e8f0; font-size: 8.5pt;
            }
            QTabBar#worksheetTabs::tab:hover { background-color: #e2e8f0; color: #0f172a; }
            QTabBar#worksheetTabs::tab:selected {
                background-color: #ffffff; color: #005a9e;
                border-bottom: 3px solid #005a9e; font-weight: 600;
            }
            QWidget#resultCard { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 4px; }
            QLabel#worksheetBadge {
                background-color: #f8fafc; color: #334155; border-bottom: 1px solid #e2e8f0;
                padding: 6px 12px; font-size: 8.5pt; font-weight: 700;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 4px 8px; min-height: 20px; selection-background-color: #e0f2fe; selection-color: #0369a1;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #0078d7; background-color: #ffffff;
            }
            QLineEdit:disabled, QComboBox:disabled {
                background-color: #f1f5f9; color: #94a3b8; border-color: #e2e8f0;
            }
            QComboBox::drop-down { border: none; width: 20px; background: transparent; }
            QComboBox::down-arrow {
                width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent;
                border-top: 5px solid #475569; margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px;
                selection-background-color: #e0f2fe; selection-color: #0369a1; padding: 2px;
            }
            QListWidget { background-color: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; }
            QListWidget::item { padding: 4px 6px; border-radius: 2px; }
            QListWidget::item:hover { background-color: #f1f5f9; color: #0f172a; }
            QListWidget::item:selected { background-color: #e0f2fe; color: #005a9e; }
            QGroupBox {
                background-color: #ffffff; color: #0f172a; border: 1px solid #e2e8f0;
                border-radius: 6px; margin-top: 14px; padding: 12px 10px 10px 10px; font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin; subcontrol-position: top left; left: 10px;
                padding: 0 4px; background-color: #ffffff; color: #005a9e;
            }
            QRadioButton, QCheckBox { color: #1e293b; spacing: 6px; background: transparent; }
            QRadioButton:disabled, QCheckBox:disabled { color: #94a3b8; }
            QRadioButton::indicator {
                width: 14px; height: 14px; border-radius: 7px;
                border: 1px solid #94a3b8; background-color: #ffffff;
            }
            QRadioButton::indicator:hover { border-color: #0078d7; }
            QRadioButton::indicator:checked {
                border: 1px solid #0078d7;
                background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #0078d7, stop:0.55 #0078d7, stop:0.65 #ffffff, stop:1 #ffffff);
            }
            QCheckBox::indicator {
                width: 14px; height: 14px; border-radius: 3px;
                border: 1px solid #94a3b8; background-color: #ffffff;
            }
            QCheckBox::indicator:hover { border-color: #0078d7; }
            QCheckBox::indicator:checked {
                border-color: #0078d7; background-color: #0078d7;
            }
            QPushButton {
                background-color: #ffffff; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 4px 14px; min-height: 22px; font-weight: 500;
            }
            QPushButton:hover { background-color: #f1f5f9; border-color: #94a3b8; color: #0f172a; }
            QPushButton:pressed { background-color: #e2e8f0; border-color: #64748b; }
            QPushButton:default { background-color: #005a9e; color: #ffffff; border: 1px solid #004578; font-weight: 600; }
            QPushButton:default:hover { background-color: #0078d7; border-color: #005a9e; }
            QPushButton:disabled { background-color: #f8fafc; color: #94a3b8; border-color: #e2e8f0; }
            QLabel#pageHeading { font-size: 11.5pt; font-weight: 700; color: #0f172a; }
            QLabel#sectionHeading, QLabel#dialogHeading { font-size: 10pt; font-weight: 700; color: #005a9e; }
            QLabel#secondary { color: #64748b; font-size: 8.5pt; }
            QLabel#error { color: #dc2626; }
            QWidget#commandLinePane { background-color: #f8fafc; border-left: 1px solid #e2e8f0; }
            QStatusBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #005a9e, stop:1 #004578);
                color: #ffffff; border-top: 1px solid #003b66; min-height: 24px;
            }
            QStatusBar::item { border: none; }
            QStatusBar QLabel { color: #ffffff; background: transparent; font-size: 8.5pt; padding: 0 6px; }
            QStatusBar QToolButton {
                color: #ffffff; background: transparent; border: 1px solid transparent;
                padding: 2px 6px; border-radius: 3px; font-size: 8.5pt;
            }
            QStatusBar QToolButton:hover { background: rgba(255, 255, 255, 0.18); border-color: rgba(255, 255, 255, 0.35); }
            QStatusBar QToolButton:checked { background: rgba(0, 0, 0, 0.28); border-color: rgba(255, 255, 255, 0.5); }
            QSlider#zoomSlider::groove:horizontal { height: 3px; background: rgba(255, 255, 255, 0.4); border-radius: 1px; }
            QSlider#zoomSlider::handle:horizontal { width: 8px; height: 12px; margin: -5px 0; background: #ffffff; border-radius: 2px; }
            QToolTip {
                background-color: #0f172a; color: #ffffff; border: 1px solid #334155;
                border-radius: 4px; padding: 4px 8px; font-size: 8.5pt;
            }
            QScrollBar:vertical {
                background: #f1f5f9; width: 10px; margin: 0px; border: none;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1; min-height: 24px; border-radius: 5px; margin: 2px;
            }
            QScrollBar::handle:vertical:hover { background: #94a3b8; }
            QScrollBar::handle:vertical:pressed { background: #64748b; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: none; border: none; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
            QScrollBar::horizontal {
                background: #f1f5f9; height: 10px; margin: 0px; border: none;
            }
            QScrollBar::handle:horizontal {
                background: #cbd5e1; min-width: 24px; border-radius: 5px; margin: 2px;
            }
            QScrollBar::handle:horizontal:hover { background: #94a3b8; }
            QScrollBar::handle:horizontal:pressed { background: #64748b; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; background: none; border: none; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
        """

class ModernWindow(QMainWindow):
    PAGE_SIZE = 300

    def __init__(self, presenter=None, sandbox_mode: bool = False):
        super().__init__()
        self.sandbox_mode = sandbox_mode
        if self.sandbox_mode:
            self.sandbox_workspace = Path(__file__).resolve().parents[1] / ".sandbox_workspace"
            self.sandbox_workspace.mkdir(parents=True, exist_ok=True)
        app = QApplication.instance()
        self._dark_mode = QSettings("StatCraft", "StatCraft").value("dark_mode", False, type=bool)
        apply_theme_palette(app, self._dark_mode)
        self.presenter = presenter or Presenter()
        self.page = 0
        self.selected_entry = None
        self._refreshing = False
        self._last_dialog_action = None
        self._find_state = {"query": "", "match_case": False, "whole_word": False, "direction": "down"}
        self._navigator_group_by_sheet = True
        self._navigator_sort_mode = "oldest"  # 'newest', 'oldest', 'name'
        self._zoom_percent = 100
        self._worksheet_zoom = 100
        self._output_zoom_levels = {}
        self._view_mode = "both"  # 'both', 'data', 'output'
        self._selected_columns = set()
        self._selected_rows = set()
        self._hidden_columns = set()
        self._use_hidden_in_dialogs = False
        self._report_pad_entries = []
        self._prepare_blank()
        self._ui_mode = "minitab"
        self.setWindowTitle("StatCraft - Untitled")
        self.resize(1280, 760); self.setMinimumSize(920, 520)
        self.setFont(QFont("Segoe UI", 9))
        icon = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "StatCraft.ico"
        if icon.is_file(): self.setWindowIcon(QIcon(str(icon)))
        self.setStyleSheet(get_theme_stylesheet(self._dark_mode))
        self._create_layout()
        from .graph_options_pane import GraphOptionsPane
        self.graph_options_pane=GraphOptionsPane(self,apply_callback=self._apply_graph_settings)
        self.graph_options_pane.objectEditRequested.connect(lambda:self.edit_graph_object())
        self.graph_options_pane.histogramEditRequested.connect(lambda:self.histogram_options_dialog())
        self.graph_options_pane.setMinimumWidth(280);self.graph_options_pane.setMaximumWidth(440)
        self.graph_options_pane.closeRequested.connect(self.close_graph_options)
        self.splitter.addWidget(self.graph_options_pane);self.graph_options_pane.hide()
        self._create_actions(); self._create_status_bar(); self.refresh()
        self._show_welcome()
        self.set_ui_mode(self._ui_mode)
        QTimer.singleShot(2500, self._check_startup_updates)

    def _prepare_blank(self):
        sheet = self.presenter.worksheet
        if sheet.row_count == 0 and len(sheet.columns) == 1 and sheet.columns[0].name == "C1" and self.presenter.native_project is None:
            if sheet.name == 'Untitled': sheet.name = 'Worksheet 1'
            sheet.columns[0].metadata["auto_type"] = True
            sheet.columns.extend(Column("C" + str(i), metadata={"auto_type": True}) for i in range(2, 17))

    def setWindowTitle(self, title: str):
        if getattr(self, "sandbox_mode", False) and not title.startswith("[🧪 LIVE SANDBOX"):
            title = f"[🧪 LIVE SANDBOX · v111.0.0-dev] {title}"
        super().setWindowTitle(title)

    def _create_sandbox_banner(self, layout):
        self.sandbox_banner = QFrame()
        self.sandbox_banner.setObjectName("sandboxBanner")
        b_lay = QHBoxLayout(self.sandbox_banner)
        b_lay.setContentsMargins(10, 4, 10, 4)
        b_lay.setSpacing(10)

        self.sandbox_badge = QLabel("<b>🧪 LIVE SANDBOX · v111.0.0-dev</b>")
        b_lay.addWidget(self.sandbox_badge)

        self.sandbox_msg = QLabel("Running directly from local repository source. Code edits apply immediately upon restart.")
        b_lay.addWidget(self.sandbox_msg, 1)

        btn_diag = QPushButton("📋 Copy Diagnostics")
        btn_diag.setStyleSheet("font-size: 8pt; padding: 2px 8px;")
        btn_diag.clicked.connect(self._copy_sandbox_diagnostics)
        b_lay.addWidget(btn_diag)

        self._style_sandbox_banner(self._dark_mode)
        layout.addWidget(self.sandbox_banner)

    def _style_sandbox_banner(self, is_dark: bool):
        if not hasattr(self, "sandbox_banner") or not self.sandbox_banner:
            return
        self.sandbox_banner.setStyleSheet(
            "QFrame#sandboxBanner { background-color: #78350f; border-bottom: 2px solid #f59e0b; padding: 4px 10px; }"
            if is_dark else
            "QFrame#sandboxBanner { background-color: #fef3c7; border-bottom: 2px solid #d97706; padding: 4px 10px; }"
        )
        if hasattr(self, "sandbox_badge") and self.sandbox_badge:
            self.sandbox_badge.setStyleSheet("color: #fbbf24; font-size: 9pt;" if is_dark else "color: #b45309; font-size: 9pt;")
        if hasattr(self, "sandbox_msg") and self.sandbox_msg:
            self.sandbox_msg.setStyleSheet("color: #fef3c7; font-size: 8.5pt;" if is_dark else "color: #92400e; font-size: 8.5pt;")

    def _copy_sandbox_diagnostics(self):
        import platform
        text = f"StatCraft Live Sandbox v111.0.0-dev\nPlatform: {platform.platform()}\nPython: {sys.executable}\nSource: {Path(__file__).resolve().parent}"
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(text)
        if self.statusBar():
            self.statusBar().showMessage("✓ Copied sandbox diagnostics to clipboard", 4000)

    def _create_layout(self):
        central = QWidget(); outer = QVBoxLayout(central); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        if getattr(self, "sandbox_mode", False):
            self._create_sandbox_banner(outer)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left pane: Navigator container with compact white header bar and dropdown menu button (`RT_MENU 10186`)
        self.navigator_container = QWidget(); self.navigator_container.setObjectName("navigatorPane")
        self.navigator_container.setMinimumWidth(175); self.navigator_container.setMaximumWidth(360)
        nav_layout = QVBoxLayout(self.navigator_container); nav_layout.setContentsMargins(0, 0, 0, 0); nav_layout.setSpacing(0)
        nav_header = QWidget(); nav_header.setObjectName("navigatorHeader"); nav_header.setFixedHeight(32)
        nav_header_row = QHBoxLayout(nav_header); nav_header_row.setContentsMargins(8, 2, 6, 2); nav_header_row.setSpacing(4)
        nav_title = QLabel("Navigator"); nav_title.setObjectName("navigatorTitle"); nav_header_row.addWidget(nav_title)
        nav_header_row.addStretch()
        self.navigator_menu_button = QToolButton(); self.navigator_menu_button.setText("▾")
        self.navigator_menu_button.setToolTip("Navigator options")
        self.navigator_menu_button.clicked.connect(self._show_navigator_menu)
        nav_header_row.addWidget(self.navigator_menu_button)
        nav_layout.addWidget(nav_header)

        self.navigator = QTreeWidget(); self.navigator.setHeaderHidden(True)
        self.navigator.setIndentation(12)
        self.navigator.itemClicked.connect(self._navigate)
        self.navigator.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.navigator.customContextMenuRequested.connect(self._show_navigator_item_menu)
        nav_layout.addWidget(self.navigator, 1)

        from .jmp_panel import JMPTablePanel
        self.jmp_panel = JMPTablePanel(self)

        self.sidebar_stack = QStackedWidget()
        self.sidebar_stack.setObjectName("sidebarStack")
        self.sidebar_stack.setMinimumWidth(175); self.sidebar_stack.setMaximumWidth(380)
        self.sidebar_stack.addWidget(self.navigator_container)
        self.sidebar_stack.addWidget(self.jmp_panel)
        from .r_file_explorer import RExplorerPanel
        self.r_explorer_panel = RExplorerPanel(
            main_window=self,
            presenter=self.presenter,
            workbench=getattr(self, "r_workbench", None),
        )
        self.sidebar_stack.addWidget(self.r_explorer_panel)
        self.splitter.addWidget(self.sidebar_stack)

        # Center/Right vertical splitter: Output pane on top, Worksheet grid on bottom
        self.work_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top right: Output pane + optional Command Line / History side pane
        self.output_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.output_pane = QWidget(); self.output_pane.setObjectName("outputPane")
        output_layout = QVBoxLayout(self.output_pane); output_layout.setContentsMargins(0, 0, 0, 0); output_layout.setSpacing(0)

        self.output_header_bar = QWidget(); self.output_header_bar.setObjectName("outputHeaderBar")
        title_row = QHBoxLayout(self.output_header_bar); title_row.setContentsMargins(10, 4, 10, 4); title_row.setSpacing(8)
        self.result_title = label("Session output", "sectionHeading"); title_row.addWidget(self.result_title)
        self.result_state = label("", "secondary"); title_row.addWidget(self.result_state, 1)
        self.rerun_button = QPushButton("Rerun with current data"); self.rerun_button.clicked.connect(self.rerun_selected)
        self.rerun_button.setEnabled(False); title_row.addWidget(self.rerun_button)
        self.output_menu_button = QToolButton(); self.output_menu_button.setObjectName("outputDropdownBtn")
        self.output_menu_button.setText("▾")
        self.output_menu_button.setToolTip("Output / Graph Options")
        self.output_menu_button.clicked.connect(lambda: self._show_output_context_menu(self.output_menu_button.mapToGlobal(self.output_menu_button.rect().bottomLeft())))
        title_row.addWidget(self.output_menu_button)
        output_layout.addWidget(self.output_header_bar)
        self.output_header_bar.hide()

        self.result_tabs = QTabWidget()
        self.result_tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.result_tabs.customContextMenuRequested.connect(lambda pos: self._show_output_context_menu(self.result_tabs.mapToGlobal(pos)))
        self.tab_corner_widget = QWidget()
        corner_row = QHBoxLayout(self.tab_corner_widget); corner_row.setContentsMargins(0, 0, 6, 0); corner_row.setSpacing(2)
        self.tab_copy_r_btn = QToolButton()
        self.tab_copy_r_btn.setText("📋 Copy R")
        self.tab_copy_r_btn.setToolTip("Copy reproducible Base R script for current output (Ctrl+Alt+R)")
        self.tab_copy_r_btn.setStyleSheet(
            "QToolButton { font-size: 8pt; font-weight: 600; padding: 2px 7px; border: 1px solid #0284c7; border-radius: 3px; background: #0284c7; color: white; }"
            "QToolButton:hover { background: #0369a1; }"
        )
        self.tab_copy_r_btn.clicked.connect(self.copy_active_r_script)
        corner_row.addWidget(self.tab_copy_r_btn)

        self.tab_dropdown_btn = QToolButton(); self.tab_dropdown_btn.setObjectName("outputDropdownBtn")
        self.tab_dropdown_btn.setText("▾"); self.tab_dropdown_btn.setToolTip("Output Menu")
        self.tab_dropdown_btn.clicked.connect(lambda: self._show_output_context_menu(self.tab_dropdown_btn.mapToGlobal(self.tab_dropdown_btn.rect().bottomLeft())))
        self.tab_close_btn = QToolButton(); self.tab_close_btn.setText("×"); self.tab_close_btn.setToolTip("Close Output Tab")
        self.tab_close_btn.clicked.connect(lambda:self._workspace.close_current())
        corner_row.addWidget(self.tab_dropdown_btn); corner_row.addWidget(self.tab_close_btn)
        self.result_tabs.setCornerWidget(self.tab_corner_widget, Qt.Corner.TopRightCorner)
        output_layout.addWidget(self.result_tabs, 1)
        from .output_workspace import OutputWorkspace
        self._workspace=OutputWorkspace(self,output_layout)
        self.output_splitter.addWidget(self.output_pane)

        # Dockable Command Line / History pane (`MTB >`) toggled from View or Status Bar
        self.command_line_pane = QWidget(); self.command_line_pane.setObjectName("commandLinePane")
        self.command_line_pane.setMinimumWidth(250); self.command_line_pane.hide()
        cmd_layout = QVBoxLayout(self.command_line_pane); cmd_layout.setContentsMargins(8, 6, 8, 6); cmd_layout.setSpacing(4)
        cmd_header = QHBoxLayout()
        cmd_header.addWidget(label("Command Line", "sectionHeading"))
        cmd_header.addStretch()
        run_cmd_btn = QPushButton("Run"); run_cmd_btn.clicked.connect(self.run_command_line)
        cmd_header.addWidget(run_cmd_btn)
        cmd_layout.addLayout(cmd_header)
        self.command_editor = QPlainTextEdit()
        self.command_editor.setPlaceholderText("DESCRIBE C1\nLET C2 = C1 * 2\nREGRESS C2 C1")
        self.command_editor.setMaximumHeight(95)
        self.command_editor.setFont(QFont("Consolas", 9))
        cmd_layout.addWidget(self.command_editor)
        cmd_layout.addWidget(label("History", "sectionHeading"))
        self.command_history_view = QPlainTextEdit(); self.command_history_view.setReadOnly(True)
        self.command_history_view.setFont(QFont("Consolas", 8.5))
        def _on_hist_change():
            c = self.command_history_view.textCursor()
            line = c.block().text().strip()
            if line.startswith("MTB > "): line = line[6:].strip()
            elif line.startswith("SUBC > "): line = line[7:].strip()
            if line: self.command_editor.setPlainText(line)
        self.command_history_view.cursorPositionChanged.connect(_on_hist_change)
        cmd_layout.addWidget(self.command_history_view, 1)
        self.output_splitter.addWidget(self.command_line_pane)
        self.output_splitter.setStretchFactor(0, 3); self.output_splitter.setStretchFactor(1, 1)
        self.work_splitter.addWidget(self.output_splitter)

        # Bottom right: Edge-to-edge Worksheet pane
        self.worksheet_pane = QWidget(); sheet_layout = QVBoxLayout(self.worksheet_pane)
        sheet_layout.setContentsMargins(0, 0, 0, 0); sheet_layout.setSpacing(0)
        self.worksheet_selector = QComboBox(self.worksheet_pane); self.worksheet_selector.hide()
        self.worksheet_selector.currentIndexChanged.connect(self._select_sheet)

        self.column_names = QTableWidget(1, 0)
        self.column_names.setObjectName("columnNamesTable")
        self.column_names.selected_columns = set()
        self.column_names.selected_rows = set()
        self.column_names.setItemDelegate(WorksheetDelegate(self.column_names, None, is_column_names=True))
        self.col_header_view = WorksheetHeaderView(Qt.Orientation.Horizontal, self.column_names)
        self.column_names.setHorizontalHeader(self.col_header_view)
        self.col_header_view.sectionClicked.connect(self._on_column_header_clicked)
        self.col_header_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.col_header_view.customContextMenuRequested.connect(self._on_column_header_context_menu)
        self.column_names.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.column_names.customContextMenuRequested.connect(lambda pos: self._show_worksheet_context_menu(self.column_names.viewport().mapToGlobal(pos)))
        self.column_names.setToolTip("Column names — click a column header (C1, C2…) to select column, or click a name cell to edit")
        self.column_names.setVerticalHeaderLabels([""])
        self.column_names.verticalHeader().setFixedWidth(44)
        self.column_names.verticalHeader().setToolTip("Data entry direction — click to toggle Down (↓) or Right (→)")
        self.column_names.verticalHeader().sectionClicked.connect(lambda _: self.toggle_entry_direction())
        self.column_names.horizontalHeader().setDefaultSectionSize(54)
        self.column_names.horizontalHeader().setMinimumSectionSize(38)
        self.column_names.verticalHeader().setDefaultSectionSize(20)
        self.column_names.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.column_names.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.column_names.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
        self.column_names.setFixedHeight(42)
        self.column_names.itemChanged.connect(self._column_name_changed)
        self.column_names.currentCellChanged.connect(self._column_name_current_changed)
        self.column_names.cellClicked.connect(self._column_name_current_changed)
        self.entry_dir_label = QLabel("↓", self.column_names)
        self.entry_dir_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.entry_dir_label.setGeometry(0, 20, 44, 21)
        self.entry_dir_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.entry_dir_label.setStyleSheet("background: transparent; color: #555555; font-size: 9pt; font-weight: 600;")
        sheet_layout.addWidget(self.column_names)

        self.table = WorksheetTable(self._navigate_cell)
        self.table.page_rows=self._scroll_row_page
        self.row_header_view = WorksheetHeaderView(Qt.Orientation.Vertical, self.table)
        self.table.setVerticalHeader(self.row_header_view)
        self.row_header_view.sectionClicked.connect(self._on_row_header_clicked)
        self.row_header_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.row_header_view.customContextMenuRequested.connect(self._on_row_header_context_menu)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.table.horizontalHeader().setDefaultSectionSize(54)
        self.table.horizontalHeader().setMinimumSectionSize(38)
        self.table.horizontalHeader().hide()
        self.table.verticalHeader().setFixedWidth(44)
        self.table.verticalHeader().setDefaultSectionSize(19)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.horizontalScrollBar().valueChanged.connect(self.column_names.horizontalScrollBar().setValue)
        self.column_names.horizontalHeader().sectionResized.connect(lambda index, old, size: self.table.setColumnWidth(index, size))
        self.table.itemChanged.connect(self._cell_changed)
        self.table.itemSelectionChanged.connect(self._sync_selection_highlights)
        self.table.currentCellChanged.connect(lambda r, c, pr, pc: (self._update_corner_arrow(), self._sync_selection_highlights()))
        sheet_layout.addWidget(self.table, 1)

        # Bottom worksheet chrome bar (`⊞`, `|<`, `<`, `>`, `>|`, `+`, `#worksheetTabs`, page/row counts)
        chrome_bar = QWidget(); chrome_bar.setObjectName("sheetChromeBar"); chrome_bar.setFixedHeight(25)
        tab_row = QHBoxLayout(chrome_bar); tab_row.setContentsMargins(2, 0, 8, 0); tab_row.setSpacing(0)

        self.sheet_menu_button = QPushButton(); self.sheet_menu_button.setObjectName("chromeNavButton")
        self.sheet_menu_button.setIcon(tool_icon("sheet_menu")); self.sheet_menu_button.setFixedWidth(26)
        self.sheet_menu_button.setToolTip("All Worksheets Menu")
        self.sheet_menu_button.clicked.connect(self._show_all_worksheets_menu)
        tab_row.addWidget(self.sheet_menu_button)

        first_btn = QPushButton("|<"); first_btn.setToolTip("Scroll to first worksheet tab")
        first_btn.clicked.connect(lambda: self.worksheet_tab_strip.scroll_tabs(-1,True))
        prev_btn = QPushButton("<"); prev_btn.setToolTip("Scroll worksheet tabs left")
        prev_btn.clicked.connect(lambda: self.worksheet_tab_strip.scroll_tabs(-1))
        next_btn = QPushButton(">"); next_btn.setToolTip("Scroll worksheet tabs right")
        next_btn.clicked.connect(lambda: self.worksheet_tab_strip.scroll_tabs(1))
        last_btn = QPushButton(">|"); last_btn.setToolTip("Scroll to last worksheet tab")
        last_btn.clicked.connect(lambda: self.worksheet_tab_strip.scroll_tabs(1,True))
        self.worksheet_tab_nav=(first_btn,prev_btn,next_btn,last_btn)
        for nav_b in (first_btn, prev_btn, next_btn, last_btn):
            nav_b.setObjectName("chromeNavButton"); nav_b.setFixedWidth(22)
            tab_row.addWidget(nav_b)

        self.add_sheet_button = QPushButton("+"); self.add_sheet_button.setObjectName("chromeNavButton")
        self.add_sheet_button.setFixedWidth(24); self.add_sheet_button.setToolTip("Create New Worksheet")
        self.add_sheet_button.clicked.connect(self.new_worksheet)
        tab_row.addWidget(self.add_sheet_button)

        from .worksheet_tab_strip import WorksheetTabStrip
        self.worksheet_tab_strip=WorksheetTabStrip()
        self.worksheet_tabs=self.worksheet_tab_strip.tabs
        self.worksheet_tab_strip.scrollStateChanged.connect(self._update_tab_navigation)
        self.worksheet_tabs.currentChanged.connect(self._select_sheet)
        self.worksheet_tabs.tabBarDoubleClicked.connect(self._rename_tab)
        self.worksheet_tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.worksheet_tabs.customContextMenuRequested.connect(self._worksheet_menu)
        tab_row.addWidget(self.worksheet_tab_strip, 1)

        from PySide6.QtWidgets import QScrollBar
        self.chrome_hscroll = QScrollBar(Qt.Orientation.Horizontal)
        self.chrome_hscroll.setFixedWidth(180); self.chrome_hscroll.setFixedHeight(15)
        self.table.horizontalScrollBar().rangeChanged.connect(self.chrome_hscroll.setRange)
        self.table.horizontalScrollBar().valueChanged.connect(self.chrome_hscroll.setValue)
        self.chrome_hscroll.valueChanged.connect(self.table.horizontalScrollBar().setValue)
        tab_row.addWidget(self.chrome_hscroll)
        tab_row.addSpacing(8)

        self.page_label = label("", "secondary"); self.page_label.setWordWrap(False)
        tab_row.addWidget(self.page_label)
        sep_lbl = label("  ·  ", "secondary"); sep_lbl.setWordWrap(False); tab_row.addWidget(sep_lbl)
        self.sheet_counts = label("", "secondary"); self.sheet_counts.setWordWrap(False)
        tab_row.addWidget(self.sheet_counts)
        sheet_layout.addWidget(chrome_bar)

        self.work_splitter.addWidget(self.worksheet_pane)
        self.work_splitter.setSizes([310, 360])

        self.work_stack = QStackedWidget()
        self.work_stack.addWidget(self.work_splitter)

        from .r_workbench_widget import RWorkbenchWidget
        self.r_workbench = RWorkbenchWidget(self)
        if hasattr(self, "r_explorer_panel"):
            self.r_explorer_panel.workbench = self.r_workbench
        self.work_stack.addWidget(self.r_workbench)

        self.splitter.addWidget(self.work_stack)
        self.splitter.setSizes([182, 1098])
        self.splitter.setStretchFactor(0, 0); self.splitter.setStretchFactor(1, 1)
        outer.addWidget(self.splitter); self.setCentralWidget(central)

    def _create_status_bar(self):
        sb = self.statusBar()
        sb.setSizeGripEnabled(True)

        self.status_nav_button = QToolButton()
        self.status_nav_button.setIcon(tool_icon("status_navigator"))
        self.status_nav_button.setIconSize(QSize(15, 15))
        self.status_nav_button.setCheckable(True); self.status_nav_button.setChecked(True)
        self.status_nav_button.setToolTip("Show or Hide Navigator")
        self.status_nav_button.clicked.connect(self.toggle_navigator)
        sb.addWidget(self.status_nav_button)

        self.status_sheet_label = QLabel("Worksheet 1")
        sb.addWidget(self.status_sheet_label)

        # Right-side permanent StatCraft controls: pane layout buttons, zoom controls, Command Line toggle
        self.view_mode_buttons = {}
        for mode, icon_key, tip in (
            ("both", "status_split", "Data and Output (Split View)"),
            ("data", "status_data_only", "Data Only"),
            ("output", "status_output_only", "Output Only"),
        ):
            btn = QToolButton()
            btn.setIcon(tool_icon(icon_key)); btn.setIconSize(QSize(15, 15))
            btn.setCheckable(True); btn.setChecked(mode == "both")
            btn.setToolTip(tip)
            btn.clicked.connect(lambda checked=False, m=mode: self.set_view_mode(m))
            self.view_mode_buttons[mode] = btn
            sb.addPermanentWidget(btn)

        zoom_out_btn = QToolButton(); zoom_out_btn.setText("−"); zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.clicked.connect(lambda: self.set_zoom(self._zoom_percent - 10))
        sb.addPermanentWidget(zoom_out_btn)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setObjectName("zoomSlider")
        self.zoom_slider.setRange(10, 500); self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(84); self.zoom_slider.setToolTip("Zoom current output or worksheet")
        self.zoom_slider.valueChanged.connect(self.set_zoom)
        sb.addPermanentWidget(self.zoom_slider)

        zoom_in_btn = QToolButton(); zoom_in_btn.setText("+"); zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.clicked.connect(lambda: self.set_zoom(self._zoom_percent + 10))
        sb.addPermanentWidget(zoom_in_btn)

        self.zoom_label_button = QToolButton(); self.zoom_label_button.setText("100%")
        self.zoom_label_button.setToolTip("Reset Zoom to 100%")
        self.zoom_label_button.clicked.connect(lambda: self.set_zoom(100))
        sb.addPermanentWidget(self.zoom_label_button)
        self.result_tabs.currentChanged.connect(self._sync_output_zoom)

        self.status_cmd_button = QToolButton()
        self.status_cmd_button.setIcon(tool_icon("status_command_line"))
        self.status_cmd_button.setIconSize(QSize(15, 15))
        self.status_cmd_button.setCheckable(True); self.status_cmd_button.setChecked(False)
        self.status_cmd_button.setToolTip("Command Line / History")
        self.status_cmd_button.clicked.connect(self.toggle_command_line)
        sb.addPermanentWidget(self.status_cmd_button)

    def _action(self, menu, text, callback, shortcut=None, icon_kind=None, record_last=False):
        action = QAction(text, self)
        if shortcut: action.setShortcut(shortcut)
        if icon_kind is not None: action.setIcon(tool_icon(icon_kind))
        def invoke():
            if record_last:
                self._last_dialog_action = callback
            callback()
        action.triggered.connect(lambda checked=False: invoke())
        menu.addAction(action); return action

    def _populate_minitab_menubar(self, bar):
        # 1. File menu
        file = bar.addMenu("&File")
        new_menu = file.addMenu("New")
        self.new_sheet_action = self._action(new_menu, "Worksheet", self.new_worksheet, QKeySequence("Ctrl+N"), "new_sheet")
        new_proj = self._action(new_menu, "Project", self.new_document, QKeySequence("Ctrl+Shift+N"), "new_project")
        self.open_action = self._action(file, "Open…", self.open_document, QKeySequence.StandardKey.Open, "open")
        self._action(file, "Import delimited text with column types…", lambda: self.open_document(True))
        file.addSeparator()
        self.save_action = self._action(file, "Save Project", self.save_document, QKeySequence.StandardKey.Save, "save")
        self._action(file, "Save Project As…", lambda: self.save_document(True), QKeySequence.StandardKey.SaveAs, "save_copy")
        self._action(file, "Save Current Worksheet As…", self.export_data, None, "export")
        self._action(file, "Export Output to Base &R Script (.R)…", self.export_active_r_file, None, "save")
        self._action(file, "Export Worksheet to &R Data Frame (.R)…", self.export_worksheet_r_dataframe, None, "save")
        file.addSeparator()
        excel=file.addMenu('Export to Excel')
        self._action(excel,'All Project Worksheets…',lambda:self.export_excel(True),None,'export')
        self._action(excel,'Current Worksheet…',lambda:self.export_excel(False))
        self._action(file,'Convert MPX File to Excel…',self.convert_mpx_excel)
        self._action(file, "Export Current Report…", self.export_report)
        self._action(file, "Export to Word…", self.send_output_to_word)
        self._action(file, "Export to PowerPoint…", self.send_output_to_powerpoint)
        file.addSeparator()
        self._action(file, "Page Setup…", lambda: self._printing().page_setup())
        self._action(file, "Print Preview…", lambda: self._printing().run("preview"))
        self._action(file, "Export PDF…", lambda: self._printing().run("pdf"))
        self.print_action = self._action(file, "Print…", self.print_current, QKeySequence.StandardKey.Print, "print")
        file.addSeparator()
        self._action(file, "Exit", self.close, QKeySequence.StandardKey.Quit)

        # 2. Edit menu
        edit = bar.addMenu("&Edit")
        self.undo_action = self._action(edit, "Undo", self.undo, QKeySequence.StandardKey.Undo, "undo")
        self.redo_action = self._action(edit, "Redo", self.redo, QKeySequence.StandardKey.Redo, "redo")
        edit.addSeparator()
        self.clear_action = self._action(edit, "Clear Cells", self.clear_cells, QKeySequence("Delete"), "erase")
        self.delete_action = self._action(edit, "Delete Cells", self.delete_selected_rows, None, "delete")
        self.cut_action = self._action(edit, "Cut Cells", self.cut_cells, QKeySequence.StandardKey.Cut, "cut")
        self.copy_action = self._action(edit, "Copy Cells", self.copy_cells, QKeySequence.StandardKey.Copy, "copy")
        self._action(edit, "Copy &R Script for Active Output\tCtrl+Alt+R", self.copy_active_r_script, "Ctrl+Alt+R", "copy")
        self.paste_action = self._action(edit, "Paste Cells", self.paste_cells, QKeySequence.StandardKey.Paste, "paste")
        edit.addSeparator()
        self._action(edit, "Select All Cells in Worksheet", self.table.selectAll, QKeySequence.StandardKey.SelectAll)
        self.last_dialog_action = self._action(edit, "Edit Last Dialog", self.edit_last_dialog, QKeySequence("Ctrl+E"), "last_dialog")
        edit.addSeparator()
        self.find_action = self._action(edit, "Find…", self.find_dialog, QKeySequence.StandardKey.Find, "find", True)
        self.find_next_action = self._action(edit, "Find Next", self.find_next, QKeySequence("F3"), "find_next")
        self._action(edit, "Go To…", self.goto_dialog, QKeySequence("Ctrl+G"), "goto", True)
        edit.addSeparator()
        self._action(edit, "Worksheet Description…", self.worksheet_description_dialog, None, "worksheet", True)

        # 3. Data menu
        data = bar.addMenu("D&ata")
        self.insert_cells_action = self._action(data, "Insert Cells…", self.insert_cells_action_handler, None, "insert_cells")
        self.insert_rows_action = self._action(data, "Insert Rows…", self.insert_rows_action_handler, None, "insert_rows")
        self.insert_columns_action = self._action(data, "Insert Columns…", self.insert_columns_action_handler, None, "insert_columns")
        self._action(data, "Add Columns…", self.add_column, None, "insert_columns", True)
        self._action(data, "Add Rows…", self.add_rows, None, "insert_rows", True)
        self.move_columns_action = self._action(data, "Move Columns…", self.move_columns_dialog, None, "move_columns", True)
        data.addSeparator()
        self._action(data, "Sort…", self.sort_dialog, None, None, True)
        self._action(data, "Rank…", self.rank_dialog, None, None, True)
        self._action(data, "Delete Rows…", self.delete_rows_dialog, None, "delete", True)
        self._action(data, "Erase Variables…", self.erase_variables_dialog, None, "erase", True)
        data.addSeparator()
        self._action(data, "Rename Column…", self.rename_column, None, None, True)
        self._action(data, "Change Data Type…", self.change_type, None, None, True)
        col_prop_menu = data.addMenu("Column Properties")
        self._action(col_prop_menu, "Value Order…", self.column_value_order_dialog, None, None, True)
        self._action(col_prop_menu, "Description…", self.column_description_dialog, None, None, True)
        self._action(col_prop_menu, "Assign Formula…", self.assign_formula_dialog, None, "assign_formula", True)
        self._action(col_prop_menu, "Conditional Formatting…", self.conditional_formatting_dialog, None, None, True)
        self._action(data, "Worksheet Information", self.show_worksheet_information, None, "worksheet")
        self._action(data, "Stored Constants…", self.stored_constants, None, "constants", True)
        data.addSeparator()
        self._action(data, "Recall Named Selection…", self.recall_named_selection_dialog, None, "select_all", True)
        self._action(data, "Subset Worksheet from Selection…", self.subset_worksheet_from_selection, None, "subset", True)
        self._action(data, "Replay Saved Workflow…", self.replay_saved_workflow_dialog, None, "workflow", True)
        worksheets_menu = data.addMenu("Worksheets")
        self.rename_sheet_action = self._action(worksheets_menu, "Rename Worksheet…", self.rename_worksheet, None, "rename_sheet")
        self.duplicate_sheet_action = self._action(worksheets_menu, "Duplicate Worksheet…", self.duplicate_worksheet, None, "duplicate_sheet")
        self.delete_sheet_action = self._action(worksheets_menu, "Delete Worksheet…", self.delete_worksheet, None, "delete_sheet")

        from .data_prep_dialogs import open_dialog as prepare_dialog
        data.addSeparator()
        stack_menu=data.addMenu("Stack")
        self._action(stack_menu,"Columns…",lambda:prepare_dialog(self,'stack'),None,None,True)
        self._action(stack_menu,"Stack Worksheets…",lambda:prepare_dialog(self,'stack_worksheets'),None,None,True)
        self._action(data,"Unstack Columns…",lambda:prepare_dialog(self,'unstack'),None,None,True)
        self._action(data,"Transpose Columns…",lambda:prepare_dialog(self,'transpose'),None,None,True)
        self._action(data,"Merge Worksheets…",lambda:prepare_dialog(self,'merge'),None,None,True)

        # 4. Calc menu
        calc = bar.addMenu("&Calc")
        self._action(calc, "Calculator…", self.calculator, None, "calculator", True)
        self.assign_formula_action = self._action(calc, "Assign Formula to Column…", self.assign_formula_dialog, None, "assign_formula", True)
        self.standardize_action = self._action(calc, "Standardize…", self.standardize_dialog, None, "standardize", True)
        patterned_menu = calc.addMenu("Make Patterned Data")
        self._action(patterned_menu, "Simple Set of Numbers…", self.patterned_numbers_dialog, None, None, True)
        self._action(patterned_menu, "Arbitrary Set of Numbers…", self.patterned_arbitrary_dialog, None, None, True)
        self._action(patterned_menu, "Text Values…", self.patterned_text_dialog, None, None, True)
        self._action(patterned_menu, "Date/Time Values…", self.patterned_datetime_dialog, None, None, True)
        random_menu = calc.addMenu("Random Data")
        self._action(random_menu, "Normal…", self.random_normal_dialog, None, None, True)
        self._action(random_menu, "Uniform…", self.random_uniform_dialog, None, None, True)
        self._action(random_menu, "Exponential…", self.random_exponential_dialog, None, None, True)
        self._action(random_menu, "Poisson…", self.random_poisson_dialog, None, None, True)
        self._action(random_menu, "Binomial…", self.random_binomial_dialog, None, None, True)
        matrix_menu = calc.addMenu("Matrices")
        self._action(matrix_menu, "Input Data…", self.stored_matrices, None, "matrices", True)
        self._action(matrix_menu, "Packed Triangular Solve…", self.triangular, None, "matrices", True)
        self._action(calc, "Probability Distributions…", self.probability, None, "probability", True)

        # 5. Stat menu
        stat = bar.addMenu("&Stat")
        self._action(stat, "Fit &Y by X (JMP Platform)…", self.fit_y_by_x_dialog, None, "scatter", True)
        self._action(stat, "Distribution (JMP Platform)…", self.jmp_distribution_dialog, None, "graphical_summary", True)
        basic = stat.addMenu("Basic Statistics")
        summary = self._action(basic, "Display Descriptive Statistics…", self.describe, None, "summary", True)
        self.store_descriptive_action = self._action(basic, "Store Descriptive Statistics…", self.store_descriptive_dialog, None, "summary", True)
        self.graphical_summary_action = self._action(basic, "Graphical Summary…", self.graphical_summary_dialog, None, "graphical_summary", True)
        self.outlier_test_action = self._action(basic, "Outlier Test…", self.outlier_test_dialog, None, "outlier_test", True)
        self._action(basic, "Correlation…", self.correlation, None, "correlation", True)
        self.covariance_action = self._action(basic, "Covariance…", self.covariance_dialog, None, "covariance", True)
        self._action(basic, "Normality Test…", self.normality, None, "normality", True)
        self.one_variance_action = self._action(basic, "1 Varianc&e…", self.one_sample_variance_dialog, None, None, True)
        self.two_variances_action = self._action(basic, "2 V&ariances…", self.two_sample_variances_dialog, None, None, True)
        self.one_proportion_action = self._action(basic, "1 Proportion…", self.one_sample_proportion_dialog, None, None, True)
        self.two_proportions_action = self._action(basic, "2 Proportions…", self.two_sample_proportion_dialog, None, None, True)
        self.one_sample_poisson_action = self._action(basic, "1-Sample Poisson Rate…", self.one_sample_poisson_dialog, None, None, True)
        self.two_sample_poisson_action = self._action(basic, "2-Sample Poisson Rate…", self.two_sample_poisson_dialog, None, None, True)
        self.one_sample_z_action = self._action(basic, "1-Sample Z…", self.one_sample_z_dialog, None, None, True)
        self.one_sample_t_action = self._action(basic, "1-Sample t…", self.one_sample_t_dialog, None, None, True)
        self.two_sample_t_action = self._action(basic, "2-Sample t…", self.two_sample_t_dialog, None, None, True)
        self.paired_t_action = self._action(basic, "Paired t…", self.paired_t_dialog, None, None, True)
        anova = stat.addMenu("ANOVA")
        self.oneway_anova_action = self._action(anova, "One-Way...", self.oneway_anova_dialog, None, None, True)
        self.twoway_anova_action = self._action(anova, "Two-Way…", self.twoway_anova_dialog, None, None, True)
        self.main_effects_plot_action = self._action(anova, "Main Effects Plot…", self.main_effects_plot_dialog, None, None, True)
        self.interactions_plot_action = self._action(anova, "Interactions Plot…", self.interactions_plot_dialog, None, None, True)
        self.test_equal_variances_action = self._action(anova, "Test for Equal Variances…", self.test_equal_variances_dialog, None, None, True)
        glm_menu=anova.addMenu("General Linear Model")
        self.glm_fit_action=self._action(glm_menu,"Fit General Linear Model…",self.general_linear_model,None,"regression",True)
        self.predict_actions={}; self.optimizer_actions={}; self.factorial_plot_actions={}; self.contour_plot_actions={}; self.surface_plot_actions={}; self.profiler_actions={}
        self.predict_actions['general_linear_model']=self._action(glm_menu,'Predict…',lambda:self.predict_model('glm'),None,None,True)
        self.profiler_actions['general_linear_model']=self._action(glm_menu,'Prediction Profiler…',lambda:self.prediction_profiler('glm'),None,None,True)
        self.factorial_plot_actions['general_linear_model']=self._action(glm_menu,'Factorial Plots…',lambda:self.factorial_plots('glm'),None,None,True)
        self.contour_plot_actions['general_linear_model']=self._action(glm_menu,'Contour Plot…',lambda:self.model_contour_plot('glm'),None,None,True)
        self.surface_plot_actions['general_linear_model']=self._action(glm_menu,'Surface Plot…',lambda:self.model_surface_plot('glm'),None,None,True)
        self.optimizer_actions['general_linear_model']=self._action(glm_menu,'Response Optimizer…',lambda:self.optimize_responses('glm'),None,None,True)
        regression_root = stat.addMenu("Regression")
        self._action(regression_root, "Simple regression…", lambda: self.inference_dialog("linear_regression"), None, "regression", True)
        regression=regression_root.addMenu('Regression')
        self._action(regression, "Fit regression model…", self.multiple_regression, None, "regression", True)
        self.predict_actions['multiple_regression']=self._action(regression,'Predict…',lambda:self.predict_model('regression'),None,None,True)
        self.profiler_actions['multiple_regression']=self._action(regression,'Prediction Profiler…',lambda:self.prediction_profiler('regression'),None,None,True)
        self.factorial_plot_actions['multiple_regression']=self._action(regression,'Factorial Plots…',lambda:self.factorial_plots('regression'),None,None,True)
        self.contour_plot_actions['multiple_regression']=self._action(regression,'Contour Plot…',lambda:self.model_contour_plot('regression'),None,None,True)
        self.surface_plot_actions['multiple_regression']=self._action(regression,'Surface Plot…',lambda:self.model_surface_plot('regression'),None,None,True)
        self.optimizer_actions['multiple_regression']=self._action(regression,'Response Optimizer…',lambda:self.optimize_responses('regression'),None,None,True)
        binary=regression_root.addMenu('Binary Logistic Regression')
        self._action(binary,'Fit Binary Logistic Model…',self.fit_binary_logistic,None,'regression',True)
        self.predict_actions['fit_binary_logistic']=self._action(binary,'Predict…',lambda:self.predict_model('logistic'),None,None,True)
        self.profiler_actions['fit_binary_logistic']=self._action(binary,'Prediction Profiler…',lambda:self.prediction_profiler('logistic'),None,None,True)
        self.factorial_plot_actions['fit_binary_logistic']=self._action(binary,'Factorial Plots…',lambda:self.factorial_plots('logistic'),None,None,True)
        self.contour_plot_actions['fit_binary_logistic']=self._action(binary,'Contour Plot…',lambda:self.model_contour_plot('logistic'),None,None,True)
        self.surface_plot_actions['fit_binary_logistic']=self._action(binary,'Surface Plot…',lambda:self.model_surface_plot('logistic'),None,None,True)
        self.optimizer_actions['fit_binary_logistic']=self._action(binary,'Response Optimizer…',lambda:self.optimize_responses('logistic'),None,None,True)
        doe = stat.addMenu("DOE")
        self._action(doe,'DOE Planner…',self.doe_planner,None,'doe',True)
        doe.addSeparator(); factorial = doe.addMenu("Factorial")
        self._action(factorial, "Create Factorial Design…", self.create_factorial, None, "doe", True)
        self._action(factorial, "Analyze Factorial Design…", self.analyze_factorial, None, "doe", True)
        self.predict_actions['analyze_factorial']=self._action(factorial,'Predict…',lambda:self.predict_model('factorial'),None,None,True)
        self.profiler_actions['analyze_factorial']=self._action(factorial,'Prediction Profiler…',lambda:self.prediction_profiler('factorial'),None,None,True)
        self.factorial_plot_actions['analyze_factorial']=self._action(factorial,'Factorial Plots…',lambda:self.factorial_plots('factorial'),None,None,True)
        self.contour_plot_actions['analyze_factorial']=self._action(factorial,'Contour Plot…',lambda:self.model_contour_plot('factorial'),None,None,True)
        self.surface_plot_actions['analyze_factorial']=self._action(factorial,'Surface Plot…',lambda:self.model_surface_plot('factorial'),None,None,True)
        self.optimizer_actions['analyze_factorial']=self._action(factorial,'Response Optimizer…',lambda:self.optimize_responses('factorial'),None,None,True)
        self._action(factorial,'Create General Factorial Design…',lambda:self.doe_planner('general_factorial'),None,'doe',True)
        self._action(factorial,'Create Plackett–Burman Design…',lambda:self.doe_planner('plackett_burman'),None,'doe',True)
        screening = doe.addMenu("Screening")
        self._action(screening, "Create Definitive Screening Design…", self.create_dsd_dialog, None, "doe", True)
        self._action(screening, "Analyze Definitive Screening Design…", self.analyze_dsd_dialog, None, "doe", True)
        self.profiler_actions['definitive_screening_analysis'] = self._action(screening, 'Prediction Profiler…', lambda: self.prediction_profiler('definitive_screening'), None, None, True)
        self._action(screening, "Create D-&Optimal Custom Design…", self.create_d_optimal_dialog, None, "doe", True)
        diagnostics = doe.addMenu("Design Diagnostics")
        self._action(diagnostics, "Evaluate &Design (Color Map on Correlations)…", self.evaluate_design_dialog, None, "doe", True)
        mixtures=doe.addMenu('Mixture')
        self._action(mixtures,'Create Mixture Design…',lambda:self.doe_planner('simplex_centroid'),None,'doe',True)
        self._action(mixtures,'Analyze Mixture Design…',self.analyze_mixture,None,'regression',True)
        self._action(mixtures,'Analyze Mixture with Process Variables…',self.analyze_mixture_process,None,'regression',True)
        self._action(mixtures,'Predict with Process Variables…',self.predict_mixture_process,None,None,True)
        self._action(mixtures,'Contour with Process Variables…',self.mixture_process_contour,None,None,True)
        self._action(mixtures,'Optimize with Process Variables…',self.optimize_mixture_process,None,'regression',True)
        self._action(mixtures,'Joint Mixture and Process Optimizer…',self.optimize_mixture_joint,None,'regression',True)
        self._action(mixtures,'Predict…',self.predict_mixture,None,None,True)
        self._action(mixtures,'Contour Plot…',self.mixture_contour,None,None,True)
        self._action(mixtures,'Response Optimizer…',self.optimize_mixture,None,'regression',True)
        self._action(mixtures,'Multiple Response Optimizer…',self.optimize_mixture_multi,None,'regression',True)
        taguchi=doe.addMenu('Taguchi')
        self._action(taguchi,'Create Taguchi Design…',lambda:self.doe_planner('taguchi'),None,'doe',True)
        self._action(taguchi,'Analyze Taguchi Design…',self.analyze_taguchi,None,'regression',True)
        self._action(taguchi,'Analyze Dynamic Taguchi Design…',self.analyze_dynamic_taguchi,None,'regression',True)
        self._action(doe,'Create Custom Optimal Design…',lambda:self.doe_planner('custom_optimal'),None,'doe',True)
        response_surface_menu=doe.addMenu("Response Surface")
        self._action(response_surface_menu,"Create Response Surface Design…",self.create_response_surface,None,"doe",True)
        self._action(response_surface_menu,"Analyze Response Surface Design…",self.analyze_response_surface,None,"regression",True)
        self.predict_actions['analyze_response_surface']=self._action(response_surface_menu,'Predict…',lambda:self.predict_model('response_surface'),None,None,True)
        self.profiler_actions['analyze_response_surface']=self._action(response_surface_menu,'Prediction Profiler…',lambda:self.prediction_profiler('response_surface'),None,None,True)
        self.factorial_plot_actions['analyze_response_surface']=self._action(response_surface_menu,'Factorial Plots…',lambda:self.factorial_plots('response_surface'),None,None,True)
        self.contour_plot_actions['analyze_response_surface']=self._action(response_surface_menu,'Contour Plot…',lambda:self.model_contour_plot('response_surface'),None,None,True)
        self.surface_plot_actions['analyze_response_surface']=self._action(response_surface_menu,'Surface Plot…',lambda:self.model_surface_plot('response_surface'),None,None,True)
        self.optimizer_actions['analyze_response_surface']=self._action(response_surface_menu,'Response Optimizer…',lambda:self.optimize_responses('response_surface'),None,None,True)
        control = stat.addMenu("Control Charts")
        self._action(control, "Control Chart &Builder (Interactive)…", self.control_chart_builder_dialog, None, "chart", True)
        control.addSeparator()
        subgroups_menu = control.addMenu("Variables Charts for Subgroups")
        self.xbar_r_action = self._action(subgroups_menu, "Xbar-R…", self.xbar_r_dialog, None, None, True)
        self.xbar_s_action = self._action(subgroups_menu, "Xbar-S…", self.xbar_s_dialog, None, None, True)
        self._action(subgroups_menu, "Xbar…", self.xbar_r_dialog, None, None, False)
        self._action(subgroups_menu, "R…", self.xbar_r_dialog, None, None, False)
        self._action(subgroups_menu, "S…", self.xbar_s_dialog, None, None, False)
        self._action(subgroups_menu, "&Acceptance Control Chart\u2026", self.acceptance_control_chart_dialog, None, None, True)

        individuals_menu = control.addMenu("Variables Charts for Individuals")
        self._action(individuals_menu, "&I-MR…", self.imr_dialog, None, None, True)

        attributes_menu = control.addMenu("Attributes Charts")
        self._action(attributes_menu, "&P…", lambda: self.attribute_control_dialog("P"), None, None, True)
        self._action(attributes_menu, "&NP…", lambda: self.attribute_control_dialog("NP"), None, None, True)
        self._action(attributes_menu, "&C…", lambda: self.attribute_control_dialog("C"), None, None, True)
        self._action(attributes_menu, "&U…", lambda: self.attribute_control_dialog("U"), None, None, True)
        self._action(attributes_menu, "Laney &P'…", lambda: self.attribute_control_dialog("P'"), None, None, True)
        self._action(attributes_menu, "Laney &U'…", lambda: self.attribute_control_dialog("U'"), None, None, True)

        time_weighted_menu = control.addMenu("&Time-Weighted Charts")
        self._action(time_weighted_menu, "&Moving Average…", self.moving_average_dialog, None, None, True)
        self._action(time_weighted_menu, "&EWMA…", self.ewma_dialog, None, None, True)
        self._action(time_weighted_menu, "&CUSUM…", self.cusum_dialog, None, None, True)

        multivariate_menu = control.addMenu("&Multivariate Charts")
        self._action(multivariate_menu, "&T²…", self.tsquared_chart_dialog, None, None, True)
        self._action(multivariate_menu, "&Generalized Variance…", self.genvar_chart_dialog, None, None, True)
        self._action(multivariate_menu, "&Multivariate EWMA…", self.mewma_chart_dialog, None, None, True)

        rare_event_menu = control.addMenu("&Rare Event Charts")
        self._action(rare_event_menu, "&G…", self.g_chart_dialog, None, None, True)
        self._action(rare_event_menu, "&T…", self.t_chart_dialog, None, None, True)
        quality = stat.addMenu("Quality Tools")
        self._action(quality, "Process &Screening…", self.process_screening_dialog, None, "table", True)
        self._action(quality, "&Variability / Gauge Chart…", self.variability_chart_dialog, None, "chart", True)
        self.run_chart_action = self._action(quality, "&Run Chart…", self.run_chart_dialog, None, "run_chart", True)
        self.multivari_action = self._action(quality, "&Multi-Vari Chart…", self.multivari_dialog, None, "multivari", True)
        self._action(quality, "&Pareto Chart…", self.pareto_chart_dialog, None, None, True)
        capa_menu = quality.addMenu("Capability Analysis")
        self._action(capa_menu, "&Normal…", self.capability, None, None, True)
        self._action(capa_menu, "Between/W&ithin…", self.capability_between_within, None, None, True)
        self._action(capa_menu, "&Machine (Normal)…", self.capability_machine, None, None, True)
        self._action(capa_menu, "Nonnorma&l…", self.capability_nonnormal_dialog, None, None, True)
        self._action(capa_menu, "Non&parametric…", self.capability_nonparametric_dialog, None, None, True)
        self._action(capa_menu, "&Automated…", self.capability_automated_dialog, None, None, True)
        self._action(capa_menu, "&Multiple Variables (Normal)…", lambda: self.multiple_capability_dialog('normal'), None, None, True)
        self._action(capa_menu, "Multiple &Variables (Nonnormal)…", lambda: self.multiple_capability_dialog('nonnormal'), None, None, True)
        self._action(capa_menu, "&Binomial…", lambda: self.attribute_capability_dialog('binomial'), None, None, True)
        self._action(capa_menu, "Poiss&on…", lambda: self.attribute_capability_dialog('poisson'), None, None, True)

        sixpack_menu = quality.addMenu("Capability Sixpack")
        self._action(sixpack_menu, "&Normal…", self.capability_sixpack, None, None, True)

        self._action(quality, "&Tolerance Intervals…", self.tolerance_intervals_dialog, None, None, True)

        gage=quality.addMenu('Gage Study')
        self._action(gage,'&Type 1 Gage Study…',self.type1_gage_dialog,None,None,True)
        self._action(gage,'Gage R&R Study (Crossed)…',self.gage_rr,None,None,True)
        self._action(gage,'Gage R&R Study (&Nested)…',self.nested_gage_rr_dialog,None,None,True)
        self._action(gage,'Gage &Linearity and Bias Study…',self.gage_linearity_dialog,None,None,True)
        self._action(gage,'Evaluating the &Measurement Process (EMP)…',self.emp_dialog,None,None,True)
        self._action(quality, '&Attribute Agreement Analysis…', self.attribute_agreement_dialog, None, None, True)

        # 5b. Reliability/Survival menu
        reliability = stat.addMenu("&Reliability/Survival")
        dist_analysis = reliability.addMenu("&Distribution Analysis (Right Censoring)")
        self._action(dist_analysis, "Parametric &Distribution Analysis…", self.reliability_distribution_dialog, None, None, True)
        self._action(reliability, "Accelerated &Life Testing…", self.alt_dialog, None, None, True)

        # 5c. Time Series menu
        time_series = stat.addMenu("&Time Series")
        self._action(time_series, "&Trend Analysis…", self.trend_analysis_dialog, None, None, True)
        self._action(time_series, "&Decomposition…", self.decomposition_dialog, None, None, True)
        self._action(time_series, "&Moving Average…", self.moving_average_dialog, None, None, True)
        self._action(time_series, "&Single Exp Smoothing…", self.single_exp_smoothing_dialog, None, None, True)
        self._action(time_series, "&Double Exp Smoothing…", self.double_exp_smoothing_dialog, None, None, True)
        time_series.addSeparator()
        self._action(time_series, "&Autocorrelation…", self.autocorrelation_dialog, None, None, True)
        self._action(time_series, "&Partial Autocorrelation…", self.partial_autocorrelation_dialog, None, None, True)
        self._action(time_series, "Cross &Correlation…", self.cross_correlation_dialog, None, None, True)
        time_series.addSeparator()
        self._action(time_series, "Di&fferences…", self.differences_dialog, None, None, True)
        self._action(time_series, "&Lag…", self.lag_dialog, None, None, True)

        # 5d. Nonparametrics menu
        nonparam = stat.addMenu("&Nonparametrics")
        self._action(nonparam, "&1-Sample Sign…", self.sign_test_dialog, None, None, True)
        self._action(nonparam, "1-Sample &Wilcoxon…", self.one_sample_wilcoxon_dialog, None, None, True)
        self._action(nonparam, "&Mann-Whitney…", self.mann_whitney_dialog, None, None, True)
        self._action(nonparam, "&Kruskal-Wallis…", self.kruskal_wallis_dialog, None, None, True)
        self._action(nonparam, "M&ood's Median Test…", self.moods_median_dialog, None, None, True)
        self._action(nonparam, "&Friedman…", self.friedman_dialog, None, None, True)
        self._action(nonparam, "&Runs Test…", self.runs_test_dialog, None, None, True)
        self._action(nonparam, "&Paired Wilcoxon…", self.paired_wilcoxon_dialog, None, None, True)

        # 5e. Multivariate menu
        multivar = stat.addMenu("&Multivariate")
        self._action(multivar, "&Principal Components...", self.pca_dialog, None, None, True)
        self._action(multivar, "&Item Analysis...", self.item_analysis_dialog, None, None, True)
        multivar.addSeparator()
        self._action(multivar, "Cluster &Observations...", self.cluster_observations_dialog, None, None, True)
        self._action(multivar, "Cluster &K-Means...", self.cluster_kmeans_dialog, None, None, True)
        self._action(multivar, "Cluster &Variables...", self.cluster_variables_dialog, None, None, True)

        multivar.addSeparator()
        self._action(multivar, "&Discriminant Analysis...", self.discriminant_analysis_dialog, None, None, True)
        self._action(multivar, "&Simple Correspondence Analysis...", self.simple_correspondence_dialog, None, None, True)

        # 5f. Equivalence Tests menu
        equiv = stat.addMenu("&Equivalence Tests")
        self._action(equiv, "&1-Sample...", self.one_sample_equivalence_dialog, None, None, True)
        self._action(equiv, "&2-Sample...", self.two_sample_equivalence_dialog, None, None, True)
        self._action(equiv, "&Paired...", self.paired_equivalence_dialog, None, None, True)
        self._action(equiv, "&2x2 Crossover Design...", self.crossover_equivalence_dialog, None, None, True)

        # 5f2. Predictive Analytics menu
        predictive = stat.addMenu("&Predictive Analytics")
        self._action(predictive, "Fit &Y by X (Bivariate / Oneway / Contingency)…", self.fit_y_by_x_dialog, None, "scatter", True)
        self._action(predictive, "CART® / &Partition Decision Tree…", self.cart_tree_dialog, None, None, True)
        self._action(predictive, "Fit &Regression Model…", self.multiple_regression, None, "regression", True)
        self._action(predictive, "&Correlation Matrix…", self.correlation, None, "correlation", True)

        # 5g. Power and Sample Size menu
        power_menu = stat.addMenu("&Power and Sample Size")
        self._action(power_menu, "&1-Sample Z...", self.one_sample_z_power_dialog, None, None, True)
        self._action(power_menu, "1-Sample &t...", self.one_sample_t_power_dialog, None, None, True)
        self._action(power_menu, "&2-Sample t...", self.two_sample_t_power_dialog, None, None, True)
        self._action(power_menu, "&Paired t...", self.paired_t_power_dialog, None, None, True)
        self._action(power_menu, "1 &Proportion...", self.one_proportion_power_dialog, None, None, True)
        self._action(power_menu, "2 P&roportions...", self.two_proportions_power_dialog, None, None, True)
        self._action(power_menu, "&One-Way ANOVA...", self.oneway_anova_power_dialog, None, None, True)
        self._action(power_menu, "2-Level &Factorial Design...", self.factorial_power_dialog, None, None, True)

        # 5h. Tables menu
        tables_menu = stat.addMenu("&Tables")
        self._action(tables_menu, "&Cross Tabulation and Chi-Square...", self.cross_tabulation_dialog, None, None, True)
        self._action(tables_menu, "Chi-Square &Goodness-of-Fit Test (One Variable)...", self.chi_square_goodness_of_fit_dialog, None, None, True)
        self._action(tables_menu, "Chi-Square Test for &Association...", self.chi_square_association_dialog, None, None, True)
        self._action(tables_menu, "&Tally Individual Variables...", self.tally_dialog, None, None, True)

        # 5i. R Translator menu
        stat.addSeparator()
        r_menu = stat.addMenu("&R Translator")
        self._action(r_menu, "Copy &R Script for Active Output\tCtrl+Alt+R", self.copy_active_r_script, "Ctrl+Alt+R", "copy")
        self._action(r_menu, "View &R Code for Active Output...", self.view_active_r_code, None, "code_view")
        self._action(r_menu, "Export Output as Standalone &R Script (.R)...", self.export_active_r_file, None, "save")
        self._action(r_menu, "Export Worksheet to &R Data Frame (.R)...", self.export_worksheet_r_dataframe, None, "save")
        r_menu.addSeparator()
        self._action(r_menu, "Run &R Script...", self.run_r_script_dialog, None, None, True)

        # 7. Graph menu
        graph = bar.addMenu("&Graph")
        from .graph_catalog import MENU
        self.graph_actions = {}
        for item in MENU:
            if item is None: graph.addSeparator(); continue
            title, method = item
            self.graph_actions[method] = self._action(graph, title + "…", lambda checked=False, m=method: self.graph(m), None, method, True)

        # 8. View menu (`RT_MENU 8445`: Navigator, Command Line/History, Data and Output, Data Only, Output Only, Zoom)
        view = bar.addMenu("&View")
        self.dark_mode_action = QAction("Dark Mode", self, checkable=True, checked=getattr(self, "_dark_mode", False))
        self.dark_mode_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
        self.dark_mode_action.triggered.connect(self.toggle_dark_mode)
        view.addAction(self.dark_mode_action)
        view.addSeparator()
        self.view_nav_action = QAction("Navigator", self, checkable=True, checked=True)
        self.view_nav_action.triggered.connect(self.toggle_navigator)
        view.addAction(self.view_nav_action)
        self.view_cmd_action = QAction("Command Line/History", self, checkable=True, checked=False)
        self.view_cmd_action.setShortcut(QKeySequence("Ctrl+Alt+M"))
        self.view_cmd_action.triggered.connect(self.toggle_command_line)
        view.addAction(self.view_cmd_action)
        view.addSeparator()
        self.view_mode_actions = {}
        mode_group = QActionGroup(self)
        for mode, text, accel in (
            ("both", "Data and Output", "Ctrl+Alt+D"),
            ("data", "Data Only", "Ctrl+Alt+W"),
            ("output", "Output Only", "Ctrl+Alt+O"),
        ):
            act = QAction(text, self, checkable=True, checked=(mode == "both"))
            act.setShortcut(QKeySequence(accel))
            act.triggered.connect(lambda checked=False, m=mode: self.set_view_mode(m))
            mode_group.addAction(act); view.addAction(act)
            self.view_mode_actions[mode] = act
        view.addSeparator()
        zoom_menu = view.addMenu("Zoom")
        self._action(zoom_menu, "Zoom In", lambda: self.set_zoom(self._zoom_percent + 10), QKeySequence.StandardKey.ZoomIn, "zoom_in")
        self._action(zoom_menu, "Zoom Out", lambda: self.set_zoom(self._zoom_percent - 10), QKeySequence.StandardKey.ZoomOut, "zoom_out")
        self._action(zoom_menu, "100%", lambda: self.set_zoom(100), QKeySequence("Ctrl+0"), "zoom")
        self._action(zoom_menu, "Fit Window", self.fit_output_window)
        self._action(zoom_menu, "Specify…", self.specify_zoom)
        for percent in (50,75,150,200):
            self._action(zoom_menu,str(percent)+"%",lambda checked=False,p=percent:self.set_zoom(p))
        view.addSeparator()
        view.addSeparator()
        self._action(view,"Show ReportPad",lambda:self._workspace.show_pad())
        self._action(view,"Reopen Closed Output Tab",lambda:self._workspace.reopen())
        self._action(view,"Close Other Output Tabs",lambda:self._workspace.close_all(self._workspace.state['active']))
        self._action(view,"Close All Output Tabs",lambda:self._workspace.close_all())
        self._action(view, "Toggle Entry Direction (Down / Right)", self.toggle_entry_direction)
        self._action(view, "Refresh Worksheet", self.refresh)

        # 9. Assistant menu (`RT_MENU 8445` guided workflow shortcuts)
        assistant = bar.addMenu("Assista&nt")
        self._action(assistant, "Graphical Analysis (Graph Builder)…", lambda: self.graph("builder"), None, "graph_builder", True)
        self._action(assistant, "Hypothesis Tests (1-Sample / 2-Sample t)…", lambda: self.inference_dialog("two_sample_t"), None, None, True)
        self._action(assistant, "Regression…", self.multiple_regression, None, "regression", True)
        self._action(assistant, "Capability Analysis…", self.capability, None, None, True)
        self._action(assistant, "DOE (Factorial Design)…", self.create_factorial, None, "doe", True)
        self._action(assistant, "Control Charts (I-MR)…", self.imr_dialog, None, None, True)

        # 10. Help menu (Always final menu on desktop menubar)
        help_menu = bar.addMenu("&Help")
        self.help_action = self._action(help_menu, "Help", self.about, QKeySequence.StandardKey.HelpContents, "help")
        help_menu.addSeparator()
        self._action(help_menu, "Check for &Updates…", self.check_for_updates_dialog, None, "update", True)
        self._action(help_menu, "About StatCraft", self.about)

        # Toolbar: Exact 21-button StatCraft layout (`RT_TOOLBAR 8445` + `RT_TOOLBAR 9915`)
    def _create_actions(self):
        bar = self.menuBar()
        self._populate_minitab_menubar(bar)

        self.cancel_action = QAction(tool_icon("cancel"), "Cancel", self)
        self.cancel_action.setToolTip("Cancel active edit / operation")
        self.cancel_action.triggered.connect(self.cancel_operation)

        self.prev_brushed_action = QAction(tool_icon("prev_brushed"), "Go To Previous Brushed Row", self)
        self.prev_brushed_action.setToolTip("Go To Previous Brushed Row")
        self.prev_brushed_action.triggered.connect(lambda: self.go_to_brushed_row(-1))

        self.next_brushed_action = QAction(tool_icon("next_brushed"), "Go To Next Brushed Row", self)
        self.next_brushed_action.setToolTip("Go To Next Brushed Row")
        self.next_brushed_action.triggered.connect(lambda: self.go_to_brushed_row(1))

        toolbar = QToolBar("Standard and Worksheet Toolbar", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.addToolBar(toolbar)
        self.main_toolbar = toolbar



        # Standard Toolbar (8445) — 13 buttons
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.save_action)
        toolbar.addSeparator()
        toolbar.addAction(self.print_action)
        toolbar.addSeparator()
        toolbar.addAction(self.cut_action)
        toolbar.addAction(self.copy_action)
        toolbar.addAction(self.paste_action)
        toolbar.addSeparator()
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addSeparator()
        toolbar.addAction(self.last_dialog_action)
        toolbar.addSeparator()
        toolbar.addAction(self.find_action)
        toolbar.addAction(self.find_next_action)
        toolbar.addSeparator()
        toolbar.addAction(self.cancel_action)
        toolbar.addAction(self.help_action)
        toolbar.addSeparator()
        # Worksheet Toolbar (9915) — 8 buttons
        toolbar.addAction(self.assign_formula_action)
        toolbar.addSeparator()
        toolbar.addAction(self.insert_cells_action)
        toolbar.addAction(self.insert_rows_action)
        toolbar.addAction(self.insert_columns_action)
        toolbar.addAction(self.move_columns_action)
        toolbar.addSeparator()
        toolbar.addAction(self.prev_brushed_action)
        toolbar.addAction(self.next_brushed_action)
        toolbar.addSeparator()
        toolbar.addAction(self.clear_action)

        # Right-aligned R Code Translator Buttons & Dark Mode Toggle
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # Prominent R Code Translator Action Buttons on Main Toolbar
        r_box = QWidget()
        r_box.setObjectName("rTranslatorBox")
        r_layout = QHBoxLayout(r_box)
        r_layout.setContentsMargins(4, 0, 4, 0)
        r_layout.setSpacing(6)

        self.btn_tb_copy_r = QPushButton("📋 Copy R Script")
        self.btn_tb_copy_r.setObjectName("btnCopyR")
        self.btn_tb_copy_r.setToolTip("Copy reproducible Base R script for active analysis to clipboard (Ctrl+Alt+R)")
        self.btn_tb_copy_r.setStyleSheet(
            "QPushButton#btnCopyR { background-color: #0284c7; color: white; font-weight: 700; font-size: 8.5pt; padding: 4px 12px; border-radius: 4px; border: 1px solid #0369a1; }"
            "QPushButton#btnCopyR:hover { background-color: #0369a1; }"
        )
        self.btn_tb_copy_r.clicked.connect(self.copy_active_r_script)
        r_layout.addWidget(self.btn_tb_copy_r)

        self.btn_tb_view_r = QPushButton("👁️ View R Code")
        self.btn_tb_view_r.setObjectName("btnViewR")
        self.btn_tb_view_r.setToolTip("View and export reproducible Base R script for active analysis")
        self.btn_tb_view_r.setStyleSheet(
            "QPushButton#btnViewR { background-color: #ffffff; color: #0f172a; font-weight: 600; font-size: 8.5pt; padding: 4px 10px; border-radius: 4px; border: 1px solid #cbd5e1; }"
            "QPushButton#btnViewR:hover { background-color: #f1f5f9; }"
        )
        self.btn_tb_view_r.clicked.connect(self.view_active_r_code)
        r_layout.addWidget(self.btn_tb_view_r)

        toolbar.addWidget(r_box)

        mode_box = QWidget()
        mode_box.setObjectName("modeToggleBox")
        mode_layout = QHBoxLayout(mode_box)
        mode_layout.setContentsMargins(4, 0, 4, 0)
        
        self.btn_mode_minitab = QToolButton()
        self.btn_mode_minitab.setText("Minitab")
        self.btn_mode_minitab.setToolTip("Minitab Mode: Quality, Engineering & SPC (Ctrl+Alt+J)")
        self.btn_mode_minitab.setCheckable(True)
        self.btn_mode_minitab.clicked.connect(lambda: self.set_ui_mode("minitab"))

        self.btn_mode_jmp = QToolButton()
        self.btn_mode_jmp.setText("JMP")
        self.btn_mode_jmp.setToolTip("JMP Mode: Interactive Visual Platforms (Ctrl+Alt+J)")
        self.btn_mode_jmp.setCheckable(True)
        self.btn_mode_jmp.clicked.connect(lambda: self.set_ui_mode("jmp"))

        self.btn_mode_r = QToolButton()
        self.btn_mode_r.setText("R")
        self.btn_mode_r.setToolTip("R Workbench: Positron-Style Scripting & REPL (Ctrl+Alt+J)")
        self.btn_mode_r.setCheckable(True)
        self.btn_mode_r.clicked.connect(lambda: self.set_ui_mode("r"))

        self.btn_theme_toggle = QToolButton()
        self.btn_theme_toggle.setText("Light" if getattr(self, "_dark_mode", False) else "Dark")
        self.btn_theme_toggle.setToolTip("Toggle Dark / Light Theme (Ctrl+Shift+D)")
        self.btn_theme_toggle.setCheckable(True)
        self.btn_theme_toggle.setChecked(getattr(self, "_dark_mode", False))
        self.btn_theme_toggle.clicked.connect(self.toggle_dark_mode)

        self._update_mode_button_styles()

        self.btn_mode_minitab.setVisible(False)
        self.btn_mode_jmp.setVisible(False)
        self.btn_mode_r.setVisible(False)
        mode_layout.addWidget(self.btn_mode_minitab)
        mode_layout.addWidget(self.btn_mode_jmp)
        mode_layout.addWidget(self.btn_mode_r)
        mode_layout.addWidget(self.btn_theme_toggle)
        toolbar.addWidget(mode_box)



        # Global shortcut Ctrl+Shift+D to toggle theme
        self.toggle_theme_action = QAction(self)
        self.toggle_theme_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
        self.toggle_theme_action.triggered.connect(self.toggle_dark_mode)
        self.addAction(self.toggle_theme_action)

        # Global shortcut Ctrl+Alt+J to toggle modes (Minitab -> JMP -> R -> Minitab)
        self.toggle_mode_action = QAction(self)
        self.toggle_mode_action.setShortcut(QKeySequence("Ctrl+Alt+J"))
        def _cycle_mode():
            curr = getattr(self, "_ui_mode", "minitab")
            nxt = "jmp" if curr == "minitab" else ("r" if curr == "jmp" else "minitab")
            self.set_ui_mode(nxt)
        self.toggle_mode_action.triggered.connect(_cycle_mode)
        self.addAction(self.toggle_mode_action)

    def _update_mode_button_styles(self):
        is_dark = getattr(self, "_dark_mode", False)
        base_style = (
            "QToolButton { border: 1px solid #3f3f46; border-radius: 4px; padding: 2px 10px; font-size: 8.5pt; font-weight: 600; background-color: #27272a; color: #a1a1aa; } "
            "QToolButton:hover { background-color: #3f3f46; color: #f4f4f5; } "
            "QToolButton:checked { background-color: #0284c7; color: #ffffff; border-color: #0284c7; }"
            if is_dark else
            "QToolButton { border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 10px; font-size: 8.5pt; font-weight: 600; background-color: #f8fafc; color: #475569; } "
            "QToolButton:hover { background-color: #e2e8f0; color: #0f172a; } "
            "QToolButton:checked { background-color: #0284c7; color: #ffffff; border-color: #0284c7; }"
        )
        if hasattr(self, "btn_mode_minitab"): self.btn_mode_minitab.setStyleSheet(base_style)
        if hasattr(self, "btn_mode_jmp"): self.btn_mode_jmp.setStyleSheet(base_style)
        if hasattr(self, "btn_mode_r"): self.btn_mode_r.setStyleSheet(base_style)
        if hasattr(self, "btn_theme_toggle"):
            theme_style = (
                "QToolButton { border: 1px solid #3f3f46; border-radius: 4px; padding: 2px 8px; font-size: 8.5pt; font-weight: 600; background-color: #27272a; color: #f4f4f5; } QToolButton:hover { background-color: #3f3f46; }"
                if is_dark else
                "QToolButton { border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 8px; font-size: 8.5pt; font-weight: 600; background-color: #f8fafc; color: #334155; } QToolButton:hover { background-color: #e2e8f0; }"
            )
            self.btn_theme_toggle.setStyleSheet(theme_style)
            self.btn_theme_toggle.setText("Light" if is_dark else "Dark")

    def set_ui_mode(self, mode: str):
        mode = mode.lower() if isinstance(mode, str) else "minitab"
        if mode not in ("minitab", "jmp", "r"):
            mode = "minitab"
        self._ui_mode = mode

        if hasattr(self, "btn_mode_minitab") and hasattr(self, "btn_mode_jmp") and hasattr(self, "btn_mode_r"):
            self.btn_mode_minitab.setChecked(mode == "minitab")
            self.btn_mode_jmp.setChecked(mode == "jmp")
            self.btn_mode_r.setChecked(mode == "r")

        bar = self.menuBar()
        bar.clear()
        if mode == "jmp":
            from .jmp_panel import populate_jmp_menubar
            populate_jmp_menubar(self, bar)
        else:
            self._populate_minitab_menubar(bar)

        is_dark = getattr(self, "_dark_mode", False)
        if hasattr(self, "_update_mode_button_styles"):
            self._update_mode_button_styles()

        if hasattr(self, "sidebar_stack"):
            if mode == "jmp":
                self.sidebar_stack.show()
                self.sidebar_stack.setCurrentIndex(1)
                if hasattr(self, "jmp_panel"):
                    self.jmp_panel.set_dark_mode(is_dark)
                    self.jmp_panel.refresh()
            elif mode == "r":
                self.sidebar_stack.show()
                self.sidebar_stack.setCurrentIndex(2)
                if hasattr(self, "r_explorer_panel") and self.r_explorer_panel:
                    self.r_explorer_panel.set_dark_mode(is_dark)
                    self.r_explorer_panel.refresh_all()
            else:
                self.sidebar_stack.show()
                self.sidebar_stack.setCurrentIndex(0)

        if hasattr(self, "work_stack"):
            self.work_stack.setCurrentIndex(1 if mode == "r" else 0)
            if mode == "r" and hasattr(self, "r_workbench") and self.r_workbench:
                self.r_workbench.set_dark_mode(is_dark)
                self.r_workbench.sync_active_worksheet_to_r()
                target_entry = self.selected_entry or (self.presenter.history[-1] if hasattr(self, "presenter") and getattr(self.presenter, "history", None) else None)
                if target_entry:
                    conn_dict = target_entry.get("connected_analysis")
                    if not conn_dict:
                        from .connect import create_connected_analysis_from_entry
                        try:
                            conn_obj = create_connected_analysis_from_entry(target_entry, self.presenter.worksheet)
                            if conn_obj:
                                conn_dict = conn_obj.to_dict()
                                target_entry["connected_analysis"] = conn_dict
                        except Exception:
                            conn_dict = None
                    if conn_dict and conn_dict.get("r_script"):
                        self.r_workbench.load_connected_analysis(conn_dict)
                        if hasattr(self, "statusBar") and self.statusBar():
                            self.statusBar().showMessage(f"R Translator: Translated '{conn_dict.get('title', 'Analysis')}' to Base R", 5000)
                self.r_workbench.refresh_environment()

        if hasattr(self, "column_names") and not getattr(self, "_refreshing", False):
            self.refresh()

        from PySide6.QtCore import QSettings
        settings = QSettings("StatCraft", "StatCraft")
        settings.setValue("ui_mode", mode)

        if hasattr(self, "status_sheet_label"):
            ws_name = getattr(self.presenter.worksheet, "name", "Worksheet 1")
            self.status_sheet_label.setText(ws_name + ("  (Modified)" if getattr(self.presenter, "dirty", False) else ""))

    def toggle_dark_mode(self):
        self.set_dark_mode(not getattr(self, "_dark_mode", False))

    def set_dark_mode(self, is_dark: bool):
        self._dark_mode = is_dark
        self._style_sandbox_banner(is_dark)
        QSettings("StatCraft", "StatCraft").setValue("dark_mode", is_dark)
        apply_theme_palette(QApplication.instance(), is_dark)
        self.setStyleSheet(get_theme_stylesheet(is_dark))
        if hasattr(self, "btn_theme_toggle"):
            self.btn_theme_toggle.setChecked(is_dark)
            self.btn_theme_toggle.setText("☀️ Light" if is_dark else "🌙 Dark")
            self.btn_theme_toggle.setStyleSheet(
                "QToolButton { border: 1px solid #3f3f46; border-radius: 3px; padding: 2px 8px; font-family: 'Segoe UI'; font-size: 8.5pt; font-weight: 600; background-color: #27272a; color: #f4f4f5; } QToolButton:hover { background-color: #3f3f46; }"
                if is_dark else
                "QToolButton { border: 1px solid #adadad; border-radius: 3px; padding: 2px 8px; font-family: 'Segoe UI'; font-size: 8.5pt; font-weight: 600; background-color: #f7f7f7; color: #222222; } QToolButton:hover { background-color: #e5f1fb; }"
            )
        if hasattr(self, "dark_mode_action"):
            self.dark_mode_action.setChecked(is_dark)
        if hasattr(self, "dark_mode_action_jmp") and self.dark_mode_action_jmp:
            self.dark_mode_action_jmp.setChecked(is_dark)

        if hasattr(self, "jmp_panel") and self.jmp_panel:
            self.jmp_panel.set_dark_mode(is_dark)
        if hasattr(self, "r_workbench") and self.r_workbench:
            self.r_workbench.set_dark_mode(is_dark)
        if hasattr(self, "r_explorer_panel") and self.r_explorer_panel:
            self.r_explorer_panel.set_dark_mode(is_dark)

        if hasattr(self, "entry_dir_label"):
            self.entry_dir_label.setStyleSheet(
                "background: transparent; color: #a1a1aa; font-size: 9pt; font-weight: 600;" if is_dark else
                "background: transparent; color: #555555; font-size: 9pt; font-weight: 600;"
            )
        if hasattr(self, "col_header_view"):
            self.col_header_view.viewport().update()
        if hasattr(self, "row_header_view"):
            self.row_header_view.viewport().update()
        if hasattr(self, "column_names"):
            self.column_names.viewport().update()
        if hasattr(self, "table"):
            self.table.viewport().update()
        self.update()

    def run_r_script_dialog(self):
        """Prompt to choose an R script file, switch to R Mode and execute."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Run R Script",
            "",
            "R Scripts (*.R *.r);;All Files (*.*)",
        )
        if not path:
            return
        content = Path(path).read_text(encoding="utf-8", errors="replace")
        self.set_ui_mode("r")
        if hasattr(self, "jmp_panel") and self.jmp_panel:
            self.jmp_panel.set_dark_mode(is_dark)
        if hasattr(self, "r_workbench") and self.r_workbench:
            self.r_workbench.editor.setPlainText(content)
            self.r_workbench.run_all()
            self.statusBar().showMessage(f"Executed R script: {Path(path).name}", 4000)

    def _module_notice(self, title, message):
        QMessageBox.information(self, title, message)

    def _call(self, callback, result=False):
        try:
            value = callback()
            self.refresh()
            if result and value is not None: self.show_result(value)
            return value
        except (ValueError, TypeError, IndexError, KeyError, ArithmeticError, OSError, ImportError) as exc:
            self.refresh(); self.statusBar().showMessage(str(exc), 12000)
            QMessageBox.warning(self, "StatCraft", str(exc)); return None

    def _commit_editor(self):
        focused = QApplication.focusWidget()
        if isinstance(focused, QLineEdit) and (self.table.isAncestorOf(focused) or self.column_names.isAncestorOf(focused)):
            target = self.table if self.column_names.isAncestorOf(focused) else self.column_names
            target.setFocus(Qt.FocusReason.OtherFocusReason)
            QApplication.processEvents()

    def _update_corner_arrow(self):
        arrow = "→" if getattr(self.table, "enter_direction", "down") == "right" else "↓"
        if hasattr(self, "entry_dir_label"):
            self.entry_dir_label.setText(arrow)
            hdr_h = self.column_names.horizontalHeader().height() or 20
            row_h = self.column_names.rowHeight(0) or 20
            self.entry_dir_label.setGeometry(0, hdr_h, 44, row_h)
        self.column_names.verticalHeader().setToolTip("Data entry direction (" + arrow + ") — click to toggle Down (↓) or Right (→)")

    def toggle_entry_direction(self):
        self.table.enter_direction = "right" if getattr(self.table, "enter_direction", "down") == "down" else "down"
        self._update_corner_arrow()
        mode_text = "Right (→)" if self.table.enter_direction == "right" else "Down (↓)"
        self.statusBar().showMessage("Data entry direction: " + mode_text, 5000)

    def toggle_navigator(self):
        target = getattr(self, "sidebar_stack", self.navigator_container)
        vis = not target.isVisible()
        target.setVisible(vis)
        if hasattr(self, "status_nav_button"): self.status_nav_button.setChecked(vis)
        if hasattr(self, "view_nav_action"): self.view_nav_action.setChecked(vis)

    def toggle_command_line(self):
        vis = not self.command_line_pane.isVisible()
        self.command_line_pane.setVisible(vis)
        if hasattr(self, "status_cmd_button"): self.status_cmd_button.setChecked(vis)
        if hasattr(self, "view_cmd_action"): self.view_cmd_action.setChecked(vis)
        if vis:
            self.output_pane.setVisible(True)
            self.command_editor.setFocus()

    def set_view_mode(self, mode):
        if mode not in ("both", "data", "output"):
            raise ValueError("Choose data, output or both panes.")
        self._view_mode = mode
        self.output_splitter.setVisible(mode in ("both", "output"))
        self.worksheet_pane.setVisible(mode in ("both", "data"))
        if mode == "both":
            self.work_splitter.setSizes([310, 360])
        for m, btn in getattr(self, "view_mode_buttons", {}).items():
            btn.setChecked(m == mode)
        for m, act in getattr(self, "view_mode_actions", {}).items():
            act.setChecked(m == mode)

    def findChildren(self, widget_type, *args, **kwargs):
        # Proxy widgets retain their own QWidget roots. Include those logical
        # descendants for graph helpers and accessibility/acceptance tooling.
        found=list(super().findChildren(widget_type,*args,**kwargs))
        from .output_zoom import OutputZoomView
        for view in super().findChildren(OutputZoomView):
            if isinstance(view.content,widget_type):found.append(view.content)
            found.extend(view.content.findChildren(widget_type,*args,**kwargs))
        unique=[];seen=set()
        for item in found:
            if id(item) not in seen:unique.append(item);seen.add(id(item))
        return unique

    def _zoom_key(self):
        if self.result_tabs.currentWidget() is getattr(self,"_report_pad_editor",None):return ("__report_pad__","ReportPad")
        entry=self.selected_entry or {}
        return (entry.get('entry_id',entry.get('title','')),self.result_tabs.tabText(self.result_tabs.currentIndex()))

    def _sync_output_zoom(self, *args):
        if not hasattr(self,'zoom_slider'):return
        from .output_zoom import OutputZoomView
        page=self.result_tabs.currentWidget()
        if isinstance(page, OutputZoomView):
            from .graph_frame import GraphFrame
            frame = page.findChild(GraphFrame)
            if frame is not None:
                self._active_graph_frame = frame
                self._active_chart_widget = getattr(frame, 'chart', None)
        percent=page.percent if isinstance(page,OutputZoomView) else self._output_zoom_levels.get(self._zoom_key(),100) if self.selected_entry else self._worksheet_zoom
        if page is getattr(self,'_report_pad_editor',None):percent=self._output_zoom_levels.get(('__report_pad__','ReportPad'),100)
        if isinstance(page,QPlainTextEdit) and (self.selected_entry is not None or page is getattr(self,'_report_pad_editor',None)):
            page.setStyleSheet('font-family: Consolas; font-size: '+str(9.5*percent/100)+'pt;')
        self._zoom_percent=percent
        with QSignalBlocker(self.zoom_slider):self.zoom_slider.setValue(percent)
        self.zoom_label_button.setText(str(percent)+'%')

    def set_zoom(self, percent):
        from .output_zoom import OutputZoomView
        page=self.result_tabs.currentWidget()
        percent=max(10,min(500,int(percent)))
        if self.selected_entry is not None and isinstance(page,OutputZoomView):
            page.set_zoom(percent);self._output_zoom_levels[self._zoom_key()]=percent
        elif isinstance(page,QPlainTextEdit) and (self.selected_entry is not None or page is self._report_pad_editor):
            font=QFont('Consolas');font.setPointSizeF(9.5*percent/100);page.setFont(font)
            page.setStyleSheet('font-family: Consolas; font-size: '+str(9.5*percent/100)+'pt;')
            self._output_zoom_levels[self._zoom_key()]=percent
        else:
            percent=max(50,min(200,percent));ratio=percent/self._worksheet_zoom
            self._worksheet_zoom=percent
            font=QFont('Segoe UI');font.setPointSizeF(9*percent/100)
            self.table.setFont(font);self.column_names.setFont(font)
            self.table.verticalHeader().setDefaultSectionSize(max(16,round(19*percent/100)))
            for i in range(self.table.columnCount()):
                width=max(24,round(self.table.columnWidth(i)*ratio))
                self.table.setColumnWidth(i,width);self.column_names.setColumnWidth(i,width)
            self._update_corner_arrow()
        self._zoom_percent=percent
        with QSignalBlocker(self.zoom_slider):self.zoom_slider.setValue(percent)
        self.zoom_label_button.setText(str(percent)+'%')

    def fit_output_window(self):
        from .output_zoom import OutputZoomView
        page=self.result_tabs.currentWidget()
        if isinstance(page,OutputZoomView):
            page.fit_window();self._output_zoom_levels[self._zoom_key()]=page.percent;self._sync_output_zoom()

    def specify_zoom(self):
        value,ok=QInputDialog.getInt(self,'Zoom','Percent:',self._zoom_percent,10,500)
        if ok:self.set_zoom(value)

    def _show_navigator_menu(self):
        menu = QMenu(self)
        grp_act = menu.addAction("Group Commands by Worksheet")
        grp_act.setCheckable(True); grp_act.setChecked(self._navigator_group_by_sheet)
        grp_act.triggered.connect(lambda checked: (setattr(self, "_navigator_group_by_sheet", bool(checked)), self.refresh()))
        menu.addSeparator()
        for mode, text in (
            ("newest", "Sort Newest to Oldest"),
            ("oldest", "Sort Oldest to Newest"),
            ("name", "Sort by Command Name"),
        ):
            act = menu.addAction(text)
            act.setCheckable(True); act.setChecked(self._navigator_sort_mode == mode)
            act.triggered.connect(lambda checked=False, m=mode: (setattr(self, "_navigator_sort_mode", m), self.refresh()))
        menu.exec(self.navigator_menu_button.mapToGlobal(self.navigator_menu_button.rect().bottomLeft()))

    def _show_all_worksheets_menu(self):
        menu = QMenu(self)
        project = self.presenter.native_project
        names = [w.name for w in project.worksheets] if project else [self.presenter.worksheet.name]
        active = project.active_index if project else 0
        for idx, name in enumerate(names):
            act = menu.addAction(name)
            act.setCheckable(True); act.setChecked(idx == active)
            act.triggered.connect(lambda checked=False, i=idx: self._select_sheet(i))
        menu.addSeparator()
        menu.addAction(self.new_sheet_action)
        menu.exec(self.sheet_menu_button.mapToGlobal(self.sheet_menu_button.rect().topLeft()))

    def refresh(self):
        if hasattr(self,"_workspace"):
            self._workspace.sync_document()
            if not self._workspace.busy:self._workspace.rebuild()
        self._refreshing = True
        sheet = self.presenter.worksheet
        current_row, current_col = self.table.currentRow(), self.table.currentColumn()
        table_block = QSignalBlocker(self.table)
        selector_block = QSignalBlocker(self.worksheet_selector)
        tree_block = QSignalBlocker(self.navigator)
        name_block = QSignalBlocker(self.column_names)
        tab_block = QSignalBlocker(self.worksheet_tabs)
        project = self.presenter.native_project
        names = [w.name for w in project.worksheets] if project else [sheet.name]
        self.worksheet_selector.clear(); self.worksheet_selector.addItems(names)
        self.worksheet_selector.setCurrentIndex(project.active_index if project else 0)
        tabs_changed=[self.worksheet_tabs.tabText(i) for i in range(self.worksheet_tabs.count())]!=names
        if tabs_changed:
            while self.worksheet_tabs.count(): self.worksheet_tabs.removeTab(0)
            for name in names: self.worksheet_tabs.addTab(name)
        active=project.active_index if project else 0
        selection_changed=self.worksheet_tabs.currentIndex()!=active
        if selection_changed:self.worksheet_tabs.setCurrentIndex(active)
        self.worksheet_tab_strip.sync()
        if tabs_changed or selection_changed:self.worksheet_tab_strip.reveal_current()
        editable = project is None or getattr(project, 'statcraft_owned', False)
        for action in (self.new_sheet_action, self.rename_sheet_action, self.duplicate_sheet_action):
            action.setEnabled(editable)
        self.delete_sheet_action.setEnabled(editable and project is not None and len(project.worksheets) > 1)
        self.add_sheet_button.setEnabled(editable)
        self.add_sheet_button.setToolTip('New Worksheet' if editable else 'Worksheet creation in imported native projects is not implemented yet.')
        self.table.setColumnCount(len(sheet.columns))
        self.column_names.setColumnCount(len(sheet.columns))
        headers = []
        default_w = max(40, int(round(54 * (self._zoom_percent / 100.0))))
        for i, column in enumerate(sheet.columns):
            if column.kind == 'date' and i not in getattr(self, '_displayed_date_columns', set()):
                self.table.setColumnWidth(i, max(165, self.table.columnWidth(i)))
            elif self.table.columnWidth(i) <= 0:
                self.table.setColumnWidth(i, default_w)
            address = "C" + str(i + 1) + ("-T" if column.kind == "text" else "-D" if column.kind == "date" else "")
            if getattr(self, "_ui_mode", "minitab") == "jmp":
                mt = column.metadata.get("modeling_type") or ("nominal" if column.kind == "text" else "ordinal" if column.kind == "date" else "continuous")
                symbol = "▲ " if mt == "continuous" else "▮ " if mt == "nominal" else "📶 "
                address = symbol + address
            headers.append(address)
            item = QTableWidgetItem(column.name if column.name != "C" + str(i + 1) else "")
            formula_note = ("  [Formula: " + column.metadata["formula"] + "]") if column.metadata.get("formula") else ""
            item.setToolTip("Name for " + address + formula_note + " — edit directly here")
            self.column_names.setItem(0, i, item)
            self.column_names.setColumnWidth(i, self.table.columnWidth(i))
        self.table.setHorizontalHeaderLabels(headers)
        self._displayed_date_columns = {i for i, c in enumerate(sheet.columns) if c.kind == 'date'}
        self.column_names.setHorizontalHeaderLabels(headers)
        formula_cols = {i for i, c in enumerate(sheet.columns) if c.metadata.get('formula')}
        if hasattr(self.table.horizontalHeader(), 'formula_columns'):
            self.table.horizontalHeader().formula_columns = formula_cols
            self.table.horizontalHeader().viewport().update()
        if hasattr(self.col_header_view, 'formula_columns'):
            self.col_header_view.formula_columns = formula_cols
            self.col_header_view.viewport().update()
        self._update_corner_arrow()
        self.column_names.setFixedHeight(self.column_names.horizontalHeader().sizeHint().height() + self.column_names.rowHeight(0) + 3)
        start = self.page * self.PAGE_SIZE
        visible = min(self.PAGE_SIZE, max(25, sheet.row_count + 12 - start))
        requested = getattr(self, '_navigation_row', -1)
        if start <= requested < start + self.PAGE_SIZE: visible = max(visible, requested - start + 1)
        self.table.setRowCount(visible)
        from .conditional_formatting import effective_highlights
        conditional_colors={}
        for index,column in enumerate(sheet.columns):
            if column.metadata.get('conditional_rules'):
                try:conditional_colors[index]=effective_highlights(column,sheet.row_count)
                except ValueError as exc:
                    self.statusBar().showMessage('Conditional formatting in C'+str(index+1)+': '+str(exc),12000)
        self.table.setVerticalHeaderLabels([str(start + i + 1) for i in range(visible)])
        for row in range(visible):
            source_row = start + row
            for col, column in enumerate(sheet.columns):
                value = column.values[source_row] if source_row < len(column.values) else None
                fmt = column.metadata.get("format")
                if source_row >= len(column.values) or (value is None and column.kind == "text"):
                    text = ""
                elif value is None:
                    text = "*"
                elif column.kind == "date":
                    text = display_date(value)
                elif column.kind == "number" and isinstance(fmt, dict) and isinstance(value, (int, float)):
                    decimals = int(fmt.get("decimals", 2))
                    mode = fmt.get("mode", "fixed")
                    if mode == "currency":
                        text = f"${float(value):,.{decimals}f}"
                    elif mode == "percent":
                        text = f"{float(value) * 100.0:.{decimals}f}%"
                    elif mode == "scientific":
                        text = f"{float(value):.{decimals}E}"
                    else:
                        text = f"{float(value):.{decimals}f}"
                else:
                    text = str(value)
                item = QTableWidgetItem(text)
                highlights = column.metadata.get("cell_highlights", {})
                comments = column.metadata.get("cell_comments", {})
                bg_hex = conditional_colors.get(col,{}).get(str(source_row),highlights.get(str(source_row)))
                if bg_hex:
                    item.setData(Qt.ItemDataRole.BackgroundRole, QColor(bg_hex))
                comment_str = comments.get(str(source_row))
                if comment_str:
                    item.setData(Qt.ItemDataRole.UserRole + 2, comment_str)
                    item.setToolTip("Comment: " + comment_str)
                elif column.kind == 'date':
                    item.setToolTip('Enter a date (2026-10-15) or date and time (2026-10-15 14:30:00).')
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter if column.kind != "text" else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, item)
        for col_idx in range(len(sheet.columns)):
            is_hidden = col_idx in self._hidden_columns
            self.table.setColumnHidden(col_idx, is_hidden)
            self.column_names.setColumnHidden(col_idx, is_hidden)
        if visible and sheet.columns:
            self.table.setCurrentCell(max(0, min(current_row, visible - 1)), max(0, min(current_col, len(sheet.columns) - 1)))
        counts = str(sheet.row_count) + " rows × " + str(len(sheet.columns)) + " cols"
        if sheet.constants: counts += ' · ' + str(len(sheet.constants)) + ' constants'
        if sheet.matrices: counts += ' · ' + str(len(sheet.matrices)) + ' matrices'
        self.sheet_counts.setText(counts)
        self.page_label.setText("Rows " + str(start + 1) + "–" + str(start + visible))
        from .prediction import normalize_recipe
        from .optimizer import normalize_model_recipe
        available_models=set(); optimizer_models=set(); two_cont_models=set()
        for entry in self.presenter.history:
            if entry.get('source_unavailable'):continue
            try:
                if self.presenter.result_worksheet(entry) is sheet:
                    from .native_mpx_models import resolve_entry_recipe
                    recipe = resolve_entry_recipe(entry, sheet)
                    if not isinstance(recipe, dict):
                        continue
                    if recipe.get('action') in ('predict_model','factorial_plots','model_contour_plot','model_surface_plot'):
                        recipe=recipe.get('parameters',{}).get('model_recipe')
                    if recipe.get('action')=='optimize_responses':
                        for r_item in recipe.get('parameters',{}).get('responses',[]):
                            norm_r=normalize_model_recipe(r_item.get('model_recipe')); act=norm_r['action']; canon='analyze_factorial' if act=='analyze_factorial_terms' else act
                            optimizer_models.add(canon); available_models.add(canon)
                            rp=norm_r['parameters']; n_c=len(rp['predictor_indices']) if act=='multiple_regression' else len(rp['covariate_indices']) if act=='general_linear_model' else len(rp['factor_indices']) if act=='analyze_response_surface' else len(rp['continuous_indices']) if act=='fit_binary_logistic' else sum(1 for c_i in rp['factor_indices'] if 0<=c_i<len(sheet.columns) and sheet.columns[c_i].kind=='number')
                            if n_c>=2:two_cont_models.add(canon)
                        continue
                    act=normalize_model_recipe(recipe)['action']
                    optimizer_models.add('analyze_factorial' if act=='analyze_factorial_terms' else act)
                    norm_rec=normalize_model_recipe(recipe); act=norm_rec['action']
                    canon='analyze_factorial' if act=='analyze_factorial_terms' else act
                    optimizer_models.add(canon); available_models.add(canon)
                    p=norm_rec['parameters']
                    n_cont=len(p['predictor_indices']) if act=='multiple_regression' else len(p['covariate_indices']) if act=='general_linear_model' else len(p['factor_indices']) if act=='analyze_response_surface' else len(p['continuous_indices']) if act=='fit_binary_logistic' else sum(1 for c_i in p['factor_indices'] if 0<=c_i<len(sheet.columns) and sheet.columns[c_i].kind=='number')
                    if n_cont>=2:two_cont_models.add(canon)
            except (ValueError,TypeError,KeyError,IndexError,OverflowError):pass
        for name,action in self.predict_actions.items():action.setEnabled(name in available_models)
        for name,action in self.profiler_actions.items():action.setEnabled(name in available_models)
        for name,action in self.optimizer_actions.items():action.setEnabled(name in optimizer_models)
        for name,action in self.factorial_plot_actions.items():action.setEnabled(name in optimizer_models)
        for name,action in self.contour_plot_actions.items():action.setEnabled(name in two_cont_models)
        for name,action in self.surface_plot_actions.items():action.setEnabled(name in two_cont_models)
        self.undo_action.setEnabled(self.presenter.can_undo); self.redo_action.setEnabled(self.presenter.can_redo)
        brushed_entry=getattr(self,'_brushed_entry',None)
        brushed_valid=bool(getattr(self,'_brushed_rows',[])) and brushed_entry is not None and any(item is brushed_entry for item in self.presenter.history) and self.presenter.result_stale(brushed_entry) is False
        self.prev_brushed_action.setEnabled(brushed_valid);self.next_brushed_action.setEnabled(brushed_valid)
        doc_title = (project.name if project else "Untitled")
        self.setWindowTitle("StatCraft - " + doc_title + " — " + sheet.name + (" *" if self.presenter.dirty else ""))
        if hasattr(self, "status_sheet_label"):
            self.status_sheet_label.setText(sheet.name + ("  (Modified)" if self.presenter.dirty else ""))

        # Populate Navigator tree matching StatCraft (`WORKSHEET 1` top-level nodes with output items directly beneath; no "Commands" header)
        self.navigator.clear()
        entries = [e for e in self.presenter.history if e.get("origin") == "statcraft" or not str(e.get("title", "")).startswith("Native command ")]
        if self._navigator_sort_mode == "newest":
            entries = list(reversed(entries))
        elif self._navigator_sort_mode == "name":
            entries = sorted(entries, key=lambda e: e.get("title", "").casefold())

        cache = {}
        bold_font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        normal_font = QFont("Segoe UI", 9, QFont.Weight.Normal)
        selected_tree_item = None
        if self._navigator_group_by_sheet:
            sheet_nodes = {}
            for index, name in enumerate(names):
                parent_node = QTreeWidgetItem(self.navigator, [name.upper()])
                parent_node.setFont(0, bold_font)
                parent_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "sheet", "index": index})
                parent_node.setExpanded(True)
                sheet_nodes[name] = parent_node
            for entry in entries:
                sname = entry.get("worksheet_name") or sheet.name
                parent_node = sheet_nodes.get(sname)
                if parent_node is None:
                    parent_node = QTreeWidgetItem(self.navigator, [sname.upper()])
                    parent_node.setFont(0, bold_font)
                    parent_node.setExpanded(True)
                    sheet_nodes[sname] = parent_node
                stale = self.presenter.result_stale(entry, cache)
                title = entry.get("title", "Result") + ("  *" if stale is True else "")
                node = QTreeWidgetItem(parent_node, [title])
                node.setFont(0, normal_font)
                node.setToolTip(0, entry.get("time", "") + "\nRight-click to copy R script")
                node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "result", "entry": entry})
                if entry is self.selected_entry and getattr(self, '_selected_graph_index', None) is None and getattr(self, '_selected_nav_kind', None) is None:
                    selected_tree_item = node
                graphs_raw = entry.get("result", {}).get("graphs", [])
                graphs = [g for g in graphs_raw if isinstance(g, dict)] if isinstance(graphs_raw, (list, tuple)) else []
                tables = entry.get("result", {}).get("tables", [])
                if not isinstance(tables, list):
                    tables = []
                has_subitems = len(graphs) > 1 or len(tables) > 1 or (bool(tables) and bool(graphs))
                if has_subitems:
                    has_text = bool(entry.get("result", {}).get("text", "").strip()) or bool(tables)
                    if has_text:
                        r_node = QTreeWidgetItem(node, ["Report"])
                        r_node.setFont(0, normal_font)
                        r_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "report", "entry": entry})
                        if entry is self.selected_entry and getattr(self, '_selected_nav_kind', None) == "report":
                            selected_tree_item = r_node
                    if len(tables) > 1:
                        for t_idx, tbl in enumerate(tables):
                            t_title = tbl.get("title") or (tbl["headers"][0] if tbl.get("headers") and tbl["headers"][0] else f"Table {t_idx + 1}")
                            t_node = QTreeWidgetItem(node, [t_title])
                            t_node.setFont(0, normal_font)
                            t_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "table", "entry": entry, "table_index": t_idx, "table_title": t_title})
                            if entry is self.selected_entry and getattr(self, '_selected_nav_kind', None) == "table" and (getattr(self, '_selected_table_index', None) == t_idx or getattr(self, '_selected_table_title', None) == t_title):
                                selected_tree_item = t_node
                    for g_idx, g in enumerate(graphs):
                        g_title = g.get("title") or f"Graph {g_idx + 1}"
                        g_node = QTreeWidgetItem(node, [g_title])
                        g_node.setFont(0, normal_font)
                        g_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "graph", "entry": entry, "graph_index": g_idx})
                        if entry is self.selected_entry and getattr(self, '_selected_graph_index', None) == g_idx:
                            selected_tree_item = g_node
                    node.setExpanded(True)
        else:
            for entry in entries:
                stale = self.presenter.result_stale(entry, cache)
                title = entry.get("title", "Result") + ("  *" if stale is True else "")
                node = QTreeWidgetItem(self.navigator, [title])
                node.setFont(0, normal_font)
                node.setToolTip(0, (entry.get("worksheet_name") or sheet.name) + " · " + entry.get("time", "") + "\nRight-click to copy R script")
                node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "result", "entry": entry})
                if entry is self.selected_entry and getattr(self, '_selected_graph_index', None) is None and getattr(self, '_selected_nav_kind', None) is None:
                    selected_tree_item = node
                graphs_raw = entry.get("result", {}).get("graphs", [])
                graphs = [g for g in graphs_raw if isinstance(g, dict)] if isinstance(graphs_raw, (list, tuple)) else []
                tables = entry.get("result", {}).get("tables", [])
                if not isinstance(tables, list):
                    tables = []
                has_subitems = len(graphs) > 1 or len(tables) > 1 or (bool(tables) and bool(graphs))
                if has_subitems:
                    has_text = bool(entry.get("result", {}).get("text", "").strip()) or bool(tables)
                    if has_text:
                        r_node = QTreeWidgetItem(node, ["Report"])
                        r_node.setFont(0, normal_font)
                        r_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "report", "entry": entry})
                        if entry is self.selected_entry and getattr(self, '_selected_nav_kind', None) == "report":
                            selected_tree_item = r_node
                    if len(tables) > 1:
                        for t_idx, tbl in enumerate(tables):
                            t_title = tbl.get("title") or (tbl["headers"][0] if tbl.get("headers") and tbl["headers"][0] else f"Table {t_idx + 1}")
                            t_node = QTreeWidgetItem(node, [t_title])
                            t_node.setFont(0, normal_font)
                            t_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "table", "entry": entry, "table_index": t_idx, "table_title": t_title})
                            if entry is self.selected_entry and getattr(self, '_selected_nav_kind', None) == "table" and (getattr(self, '_selected_table_index', None) == t_idx or getattr(self, '_selected_table_title', None) == t_title):
                                selected_tree_item = t_node
                    for g_idx, g in enumerate(graphs):
                        g_title = g.get("title") or f"Graph {g_idx + 1}"
                        g_node = QTreeWidgetItem(node, [g_title])
                        g_node.setFont(0, normal_font)
                        g_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "graph", "entry": entry, "graph_index": g_idx})
                        if entry is self.selected_entry and getattr(self, '_selected_graph_index', None) == g_idx:
                            selected_tree_item = g_node
                    node.setExpanded(True)
        if selected_tree_item is not None:
            self.navigator.setCurrentItem(selected_tree_item)

        # Update Command History view
        if hasattr(self, "command_history_view"):
            cmd_lines = [e.get("title", "") + "  [" + e.get("worksheet_name", "") + "]" for e in self.presenter.history]
            self.command_history_view.setPlainText("\n".join(cmd_lines))

        del table_block, selector_block, tree_block, name_block, tab_block
        self._refreshing = False
        frame=getattr(self,'_active_graph_frame',None)
        if frame is not None and frame.entry is self.selected_entry:
            frame.apply_appearance()
        self._sync_selection_highlights()
        if self.selected_entry is not None: self._update_result_state()
        if hasattr(self, "jmp_panel"):
            self.jmp_panel.refresh()

    def _column_name_current_changed(self,row,column,*unused):
        if self._refreshing or column<0:return
        # Keep the active worksheet column when a menu/toolbar or another
        # window takes focus away from the separate name-row widget.
        self.table.clearSelection()
        self.table.setCurrentCell(max(0,self.table.currentRow()),column)
        self._sync_selection_highlights()

    def _column_name_changed(self, item):
        if self._refreshing: return
        name = item.text().strip() or "C" + str(item.column() + 1)
        self._call(lambda: self.presenter.rename_column(item.column(), name))

    def _cell_changed(self, item):
        if self._refreshing: return
        row = self.page * self.PAGE_SIZE + item.row(); column = item.column(); raw = item.text()
        self._call(lambda: self.presenter.set_cell(row, column, raw))

    def _navigate_cell(self, direction, editor=None, delegate=None):
        columns = len(self.presenter.worksheet.columns)
        if not columns: return
        local_row = max(0, self.table.currentRow()); column = max(0, self.table.currentColumn())
        row = self.page * self.PAGE_SIZE + local_row
        if editor is not None:
            item = self.table.item(local_row, column)
            try:
                if item is None or item.text() != editor.text(): self.presenter.set_cell(row, column, editor.text())
            except (ValueError, TypeError, ArithmeticError) as exc:
                self.statusBar().showMessage(str(exc), 12000); return
            delegate.closeEditor.emit(editor, delegate.EndEditHint.NoHint)
        if direction == 'down': row += 1
        elif direction == 'up': row = max(0, row - 1)
        elif direction == 'right':
            column += 1
            if column >= columns: column = 0; row += 1
        elif direction == 'left':
            if column: column -= 1
            elif row: column = columns - 1; row -= 1
        row = min(row, max(0, MAX_CELLS // columns - 1))
        self._navigation_row = row; self.page = row // self.PAGE_SIZE; self.refresh()
        self.table.setCurrentCell(row % self.PAGE_SIZE, column)
        self.table.scrollToItem(self.table.currentItem()); self.table.setFocus(Qt.FocusReason.OtherFocusReason)

    def _select_sheet(self, index):
        if self._refreshing or index < 0: return
        self._commit_editor(); self.page = 0
        self._call(lambda: self.presenter.select_worksheet(index))

    def new_worksheet(self):
        self._commit_editor(); self.page = 0
        self._call(lambda: self.presenter.add_worksheet())

    def rename_worksheet(self):
        self._commit_editor()
        name, accepted = QInputDialog.getText(self, 'Rename Worksheet', 'Name:', text=self.presenter.worksheet.name)
        if accepted: self._call(lambda: self.presenter.rename_worksheet(name))

    def duplicate_worksheet(self):
        self._commit_editor()
        name, accepted = QInputDialog.getText(self, 'Duplicate Worksheet', 'Name:', text=self.presenter.worksheet.name + ' Copy')
        if accepted: self._call(lambda: self.presenter.duplicate_worksheet(name))

    def delete_worksheet(self):
        self._commit_editor()
        project = self.presenter.native_project
        if project is None or len(project.worksheets) < 2: return
        name = self.presenter.worksheet.name; identifier = project.worksheet_ids[project.active_index]
        answer = QMessageBox.question(self, 'Delete Worksheet', "Delete '" + name + "' and its StatCraft results? This cannot be undone.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes: return
        clear = self.selected_entry is not None and self.selected_entry.get('worksheet_id') == identifier
        if self._call(self.presenter.delete_worksheet) and clear:
            self._workspace.rebuild();self._show_welcome();self.result_title.setText('Select a result')

    def _rename_tab(self, index):
        if index >= 0 and self.rename_sheet_action.isEnabled():
            self._select_sheet(index); self.rename_worksheet()

    def _worksheet_menu(self, point):
        index = self.worksheet_tabs.tabAt(point)
        if index < 0: return
        self._select_sheet(index)
        menu = QMenu(self)
        menu.addAction(self.new_sheet_action)
        menu.addSeparator()
        menu.addAction(self.delete_sheet_action)
        menu.addAction(self.rename_sheet_action)
        menu.addAction(self.duplicate_sheet_action)
        menu.addSeparator()
        desc_act = menu.addAction("Worksheet Description…")
        desc_act.triggered.connect(self.worksheet_description_dialog)
        info_act = menu.addAction("Worksheet Information")
        info_act.triggered.connect(self.show_worksheet_information)
        menu.exec(self.worksheet_tabs.mapToGlobal(point))

    def _navigate(self, item, column):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict): return
        if data["kind"] == "sheet":
            self._select_sheet(data["index"])
        elif data["kind"] == "table":
            self._selected_table_index = data.get("table_index", 0)
            self._selected_table_title = data.get("table_title", "")
            self._selected_graph_index = None
            self._selected_nav_kind = "table"
            self.show_result(data["entry"], target_tab=data.get("table_title"))
        elif data["kind"] == "graph":
            self._selected_graph_index = data.get("graph_index", 0)
            self._selected_nav_kind = "graph"
            self.show_result(data["entry"], target_graph_index=self._selected_graph_index)
        elif data["kind"] == "report":
            self._selected_graph_index = None
            self._selected_nav_kind = "report"
            self.show_result(data["entry"], target_tab="Report")
        else:
            self._selected_graph_index = None
            self._selected_nav_kind = None
            self.show_result(data["entry"])

    def _page(self, delta):
        self._commit_editor(); self.page = max(0, self.page + delta); self.refresh()

    def _scroll_row_page(self,direction):
        old=self.page
        maximum=max(0,(MAX_CELLS//max(1,len(self.presenter.worksheet.columns))-1)//self.PAGE_SIZE)
        page=max(0,min(maximum,old+direction))
        if old==page:return False
        self._commit_editor();self.page=page;self._navigation_row=page*self.PAGE_SIZE
        self.refresh();column=max(0,self.table.currentColumn())
        row=self.table.rowCount()-1 if direction<0 else 0
        self.table.setCurrentCell(row,column)
        if direction<0:self.table.scrollToBottom()
        else:self.table.scrollToTop()
        return True

    def _update_tab_navigation(self):
        scroll=self.worksheet_tab_strip.horizontalScrollBar()
        for button in self.worksheet_tab_nav[:2]:button.setEnabled(scroll.value()>scroll.minimum())
        for button in self.worksheet_tab_nav[2:]:button.setEnabled(scroll.value()<scroll.maximum())

    def _range(self):
        ranges = self.table.selectedRanges()
        if not ranges:
            r, c = max(0, self.table.currentRow()), max(0, self.table.currentColumn())
            start = self.page * self.PAGE_SIZE
            return start + r, start + r, c, c
        if len(ranges) != 1: raise ValueError("Select one contiguous rectangular cell block.")
        area = ranges[0]; start = self.page * self.PAGE_SIZE
        return start + area.topRow(), start + area.bottomRow(), area.leftColumn(), area.rightColumn()

    def cut_cells(self):
        focused = QApplication.focusWidget()
        if isinstance(focused, (QLineEdit, QPlainTextEdit)) and not self.table.isAncestorOf(focused):
            focused.cut(); return
        self._commit_editor()
        self._call(lambda: QApplication.clipboard().setText(self.presenter.cut_block(*self._range())))

    def copy_cells(self):
        focused = QApplication.focusWidget()
        if isinstance(focused, (QLineEdit, QPlainTextEdit)) and not self.table.isAncestorOf(focused): focused.copy(); return
        if self.column_names.hasFocus():
            selected = self.column_names.selectedRanges()
            if len(selected) == 1:
                area = selected[0]
                QApplication.clipboard().setText("\t".join(self.column_names.item(0, c).text() for c in range(area.leftColumn(), area.rightColumn() + 1)))
            return
        self._commit_editor()
        self._call(lambda: QApplication.clipboard().setText(self.presenter.copy_block(*self._range())))

    def paste_cells(self):
        focused = QApplication.focusWidget()
        if isinstance(focused, (QLineEdit, QPlainTextEdit)) and not self.table.isAncestorOf(focused): focused.paste(); return
        if self.column_names.hasFocus():
            text = QApplication.clipboard().text().rstrip("\r\n")
            if "\n" in text or "\r" in text:
                self.statusBar().showMessage("Paste one row of column names.", 10000); return
            start = max(0, self.column_names.currentColumn())
            self._call(lambda: self.presenter.rename_columns(start, text.split("\t")))
            return
        self._commit_editor(); row, col = self.table.currentRow(), self.table.currentColumn()
        if row < 0 or col < 0: row, col = 0, 0
        self._call(lambda: self.presenter.paste(self.page * self.PAGE_SIZE + row, col, QApplication.clipboard().text()))

    def clear_cells(self):
        focused = QApplication.focusWidget()
        if self.column_names.hasFocus():
            selected = self.column_names.selectedRanges()
            if len(selected) == 1:
                area = selected[0]
                self._call(lambda: self.presenter.rename_columns(area.leftColumn(), [""] * (area.rightColumn() - area.leftColumn() + 1)))
            return
        if focused is not None and not self.table.hasFocus() and not self.table.isAncestorOf(focused):
            # When invoked from toolbar button, table may have lost focus to the toolbar
            pass
        self._commit_editor()
        def clear():
            first, last, left, right = self._range()
            text = "\n".join("\t".join("" for _ in range(left, right + 1)) for _ in range(first, last + 1)) + "\n"
            self.presenter.paste(first, left, text)
        self._call(clear)

    def delete_selected_rows(self):
        self._commit_editor()
        first, last, left, right = self._range()
        if self.presenter.worksheet.row_count == 0 or first >= self.presenter.worksheet.row_count:
            return
        rows = [r for r in range(first, min(last + 1, self.presenter.worksheet.row_count))]
        if rows:
            self._call(lambda: self.presenter.delete_rows(rows, range(left, right + 1)))

    def insert_cells_action_handler(self):
        self._commit_editor()
        first, last, left, right = self._range()
        count = max(1, last - first + 1)
        self._call(lambda: self.presenter.insert_cells(first, left, right, count))

    def insert_rows_action_handler(self):
        self._commit_editor()
        first, last, _, _ = self._range()
        count = max(1, last - first + 1)
        self._call(lambda: self.presenter.insert_rows(first, count))

    def insert_columns_action_handler(self):
        targets=self._column_targets()
        self._commit_editor()
        left=min(targets);count=len(targets)
        if self._call(lambda: self._mutate_columns(lambda:self.presenter.insert_columns(left,count))):
            self.select_worksheet_column(left)
            for index in range(left+1,left+count):self.select_worksheet_column(index,extend=True)
            self.table.scrollToItem(self.table.item(0,left))

    def _column_targets(self):
        """Column operations use header/name selections independently of cell ranges."""
        count=len(self.presenter.worksheet.columns)
        chosen=sorted(index for index in self._selected_columns if 0<=index<count)
        if chosen:return chosen
        focused=QApplication.focusWidget()
        if self.column_names.hasFocus() or (focused is not None and self.column_names.isAncestorOf(focused)):
            chosen=sorted({index for area in self.column_names.selectedRanges() for index in range(area.leftColumn(),area.rightColumn()+1)})
            if chosen:return chosen
            return [max(0,self.column_names.currentColumn())]
        chosen=sorted({index for area in self.table.selectedRanges() for index in range(area.leftColumn(),area.rightColumn()+1)})
        return chosen or [max(0,min(count-1,self.table.currentColumn()))]

    def delete_selected_columns(self):
        targets=self._column_targets();self._commit_editor()
        if self._call(lambda:self._mutate_columns(lambda:self.presenter.delete_columns(targets))):
            self.select_worksheet_column(min(targets[0],len(self.presenter.worksheet.columns)-1))

    def _column_view(self):
        return dict(widths=[self.table.columnWidth(i) for i in range(self.table.columnCount())],hidden=sorted(self._hidden_columns))

    def _restore_column_view(self,state):
        count=len(self.presenter.worksheet.columns)
        table_block=QSignalBlocker(self.table);name_block=QSignalBlocker(self.column_names)
        self.table.setColumnCount(count);self.column_names.setColumnCount(count)
        self._hidden_columns={i for i in state['hidden'] if i<count}
        for i,width in enumerate(state['widths'][:count]):
            self.table.setColumnWidth(i,width);self.column_names.setColumnWidth(i,width)
        del table_block,name_block

    def _mutate_columns(self,callback):
        """Keep view geometry attached to moved columns and structural undo."""
        columns=list(self.presenter.worksheet.columns);before=self._column_view()
        previous=self.presenter._undo_stack[-1] if self.presenter._undo_stack else None
        callback()
        old={id(column):i for i,column in enumerate(columns)}
        widths=[];hidden=[]
        for i,column in enumerate(self.presenter.worksheet.columns):
            original=old.get(id(column));widths.append(before['widths'][original] if original is not None else max(40,round(54*self._zoom_percent/100)))
            if original in before['hidden']:hidden.append(i)
        after=dict(widths=widths,hidden=hidden);self._restore_column_view(after)
        if self.presenter._undo_stack and self.presenter._undo_stack[-1] is not previous:
            self.presenter._undo_stack[-1].update(column_view_before=before,column_view_after=after)
        return True

    def move_columns_dialog(self):
        selected=set(self._column_targets())
        self._commit_editor()
        sheet = self.presenter.worksheet
        dialog = QDialog(self); dialog.setWindowTitle("Move Columns"); dialog.setMinimumWidth(480)
        layout = QVBoxLayout(dialog)
        body = QHBoxLayout()
        avail = QListWidget(); avail.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for i, c in enumerate(sheet.columns):
            item = QListWidgetItem(format_variable_reference(i, sheet))
            item.setData(Qt.ItemDataRole.UserRole, i)
            avail.addItem(item)
            if i in selected:
                item.setSelected(True)
        left_col = QVBoxLayout(); left_col.addWidget(QLabel("Move Selected Columns:")); left_col.addWidget(avail)
        body.addLayout(left_col, 1)

        grp = QGroupBox("Location"); grp_layout = QVBoxLayout(grp)
        rb_before_c1 = QRadioButton("Before column C1")
        rb_after_last = QRadioButton("After last column in use"); rb_after_last.setChecked(True)
        rb_before_col = QRadioButton("Before column:")
        target_combo = QComboBox()
        for i, c in enumerate(sheet.columns):
            target_combo.addItem(format_variable_reference(i, sheet), i)
        grp_layout.addWidget(rb_before_c1)
        grp_layout.addWidget(rb_after_last)
        grp_layout.addWidget(rb_before_col)
        grp_layout.addWidget(target_combo)
        grp_layout.addStretch()
        body.addLayout(QVBoxLayout(), 0)
        body.addWidget(grp, 1)
        layout.addLayout(body)
        err = label("", "error"); layout.addWidget(err)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        def accept_move():
            indices = [item.data(Qt.ItemDataRole.UserRole) for item in avail.selectedItems()]
            moving=[sheet.columns[index] for index in indices]
            dest = "before_c1" if rb_before_c1.isChecked() else "after_last" if rb_after_last.isChecked() else "before_column"
            before_idx = target_combo.currentData()
            try:
                self._mutate_columns(lambda:self.presenter.move_columns(indices,dest,before_idx))
            except ValueError as exc:
                err.setText(str(exc)); return
            dialog.accept(); self.refresh()
            positions=[index for index,column in enumerate(sheet.columns) if any(column is chosen for chosen in moving)]
            if positions:
                self.select_worksheet_column(positions[0])
                for index in positions[1:]:self.select_worksheet_column(index,extend=True)
                self.table.scrollToItem(self.table.item(0,positions[0]))
        buttons.accepted.connect(accept_move); buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def assign_formula_dialog(self):
        self._commit_editor()
        sheet = self.presenter.worksheet
        col_idx = max(0, min(self.table.currentColumn(), len(sheet.columns) - 1))
        col = sheet.columns[col_idx]
        dialog = QDialog(self); dialog.setWindowTitle("Assign Formula to " + "C" + str(col_idx + 1) + (" " + col.name if col.name != "C" + str(col_idx + 1) else ""))
        dialog.setMinimumWidth(520)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        col_combo = QComboBox()
        for i, c in enumerate(sheet.columns):
            col_combo.addItem(format_variable_reference(i, sheet), i)
        col_combo.setCurrentIndex(col_idx)
        expr_edit = QLineEdit(col.metadata.get("formula", ""))
        col_combo.currentIndexChanged.connect(lambda index: expr_edit.setText(sheet.columns[index].metadata.get('formula','')))
        expr_edit.setPlaceholderText("e.g., C1 * 2 + 10, SQRT(C1), LOG(C1)")
        func_combo = QComboBox()
        func_combo.addItems(["ABS", "SQRT", "LOG", "LOG10", "EXP", "SIN", "COS", "ROUND"])
        insert_fn_btn = QPushButton("Insert Function")
        insert_fn_btn.clicked.connect(lambda: expr_edit.insert(func_combo.currentText() + "(C1)"))
        fn_row = QHBoxLayout(); fn_row.addWidget(func_combo, 1); fn_row.addWidget(insert_fn_btn)
        form.addRow("Column:", col_combo)
        form.addRow("Expression:", expr_edit)
        form.addRow("Functions:", fn_row)
        layout.addLayout(form)
        err = label("", "error"); layout.addWidget(err)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        def accept_formula():
            target_idx = col_combo.currentData()
            try:
                entry = self.presenter.assign_formula(target_idx, expr_edit.text())
            except ValueError as exc:
                err.setText(str(exc)); return
            dialog.accept(); self.refresh(); self.show_result(entry)
        buttons.accepted.connect(accept_formula); buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def find_dialog(self):
        self._commit_editor()
        dialog = QDialog(self); dialog.setWindowTitle("Find"); dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        query_edit = QLineEdit(self._find_state["query"])
        form.addRow("Find what:", query_edit)
        layout.addLayout(form)
        match_case = QCheckBox("Match case"); match_case.setChecked(self._find_state["match_case"])
        whole_word = QCheckBox("Match whole word only"); whole_word.setChecked(self._find_state["whole_word"])
        dir_grp = QGroupBox("Direction"); dir_row = QHBoxLayout(dir_grp)
        rb_up = QRadioButton("Up"); rb_down = QRadioButton("Down")
        rb_up.setChecked(self._find_state["direction"] == "up")
        rb_down.setChecked(self._find_state["direction"] != "up")
        dir_row.addWidget(rb_up); dir_row.addWidget(rb_down)
        opts_row = QHBoxLayout()
        left_opts = QVBoxLayout(); left_opts.addWidget(match_case); left_opts.addWidget(whole_word)
        opts_row.addLayout(left_opts); opts_row.addWidget(dir_grp)
        layout.addLayout(opts_row)
        status_lbl = label("", "secondary"); layout.addWidget(status_lbl)
        btn_row = QHBoxLayout(); btn_row.addStretch()
        find_btn = QPushButton("Find Next"); find_btn.setDefault(True)
        close_btn = QPushButton("Cancel")
        btn_row.addWidget(find_btn); btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        def do_find():
            self._find_state = {
                "query": query_edit.text(),
                "match_case": match_case.isChecked(),
                "whole_word": whole_word.isChecked(),
                "direction": "up" if rb_up.isChecked() else "down",
            }
            if not self.find_next(silent=True):
                status_lbl.setText("No matching cell found in active worksheet.")
            else:
                dialog.accept()
        find_btn.clicked.connect(do_find); close_btn.clicked.connect(dialog.reject)
        dialog.exec()

    def find_next(self, silent=False):
        query = self._find_state.get("query", "")
        if not query:
            if not silent: self.find_dialog()
            return False
        start_r = self.page * self.PAGE_SIZE + max(0, self.table.currentRow())
        start_c = max(0, self.table.currentColumn())
        found = self.presenter.find_cell(
            query, start_r, start_c,
            self._find_state.get("match_case", False),
            self._find_state.get("whole_word", False),
            self._find_state.get("direction", "down"),
        )
        if found is None:
            if not silent:
                self.statusBar().showMessage("Cannot find '" + query + "'", 6000)
            return False
        r, c = found
        self._navigation_row = r; self.page = r // self.PAGE_SIZE; self.refresh()
        self.table.setCurrentCell(r % self.PAGE_SIZE, c)
        self.table.scrollToItem(self.table.currentItem())
        return True

    def goto_dialog(self):
        self._commit_editor()
        dialog = QDialog(self); dialog.setWindowTitle("Go To"); dialog.setMinimumWidth(360)
        layout = QVBoxLayout(dialog); form = QFormLayout()
        col_edit = QLineEdit("C" + str(max(1, self.table.currentColumn() + 1)))
        row_edit = QLineEdit(str(self.page * self.PAGE_SIZE + max(0, self.table.currentRow()) + 1))
        form.addRow("Enter column number or name:", col_edit)
        form.addRow("Enter row number:", row_edit)
        layout.addLayout(form)
        err = label("", "error"); layout.addWidget(err)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        def do_goto():
            try:
                indices = resolve_variables(col_edit.text().strip(), self.presenter.worksheet, ("number", "text", "date"))
                if len(indices) != 1: raise ValueError("Enter a single column (e.g., C1).")
                r = int(row_edit.text().strip()) - 1
                if r < 0 or r >= MAX_CELLS // max(1, len(self.presenter.worksheet.columns)):
                    raise ValueError("Enter a valid positive row number.")
            except ValueError as exc:
                err.setText(str(exc)); return
            self._navigation_row = r; self.page = r // self.PAGE_SIZE; self.refresh()
            self.table.setCurrentCell(r % self.PAGE_SIZE, indices[0])
            self.table.scrollToItem(self.table.currentItem())
            dialog.accept()
        buttons.accepted.connect(do_goto); buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def worksheet_description_dialog(self):
        self._commit_editor()
        sheet = self.presenter.worksheet
        desc = sheet.metadata.get("description", {})
        dialog = QDialog(self); dialog.setWindowTitle("Worksheet Description"); dialog.setMinimumWidth(460)
        layout = QVBoxLayout(dialog); form = QFormLayout()
        form.addRow("Worksheet:", QLabel(sheet.name))
        form.addRow("Location:", QLabel(self.presenter.project_path or "In Project"))
        creator_edit = QLineEdit(desc.get("creator", ""))
        date_edit = QLineEdit(desc.get("date", ""))
        comments_edit = QPlainTextEdit(desc.get("comments", "")); comments_edit.setMaximumHeight(110)
        form.addRow("Creator:", creator_edit)
        form.addRow("Date(s):", date_edit)
        form.addRow("Comments:", comments_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        def save_desc():
            self._call(lambda: self.presenter.set_worksheet_description(creator_edit.text(), date_edit.text(), comments_edit.toPlainText()))
            dialog.accept()
        buttons.accepted.connect(save_desc); buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def show_worksheet_information(self):
        self._commit_editor()
        self._call(self.presenter.worksheet_information, result=True)

    def sort_dialog(self):
        self._dialog(
            "Sort",
            [
                selector("target_indices", "Columns to sort", True, 1, None, ("number", "text", "date")),
                selector("by_index", "By column", False, 1, 1, ("number", "text", "date")),
            ],
            [{"key": "descending", "label": "Order", "boolean": True, "text": "Descending"}],
            lambda p: self.presenter.sort_columns(p["target_indices"], p["by_index"], p["descending"]),
            "Sorts selected columns in place by the chosen key column. Missing values are placed at the end.",
        )

    def rank_dialog(self):
        self._dialog(
            "Rank",
            [selector("source_index", "Rank data in", False, 1, 1, ("number",))],
            [{"key": "destination", "label": "Store ranks in", "default": "Ranks"}],
            lambda p: self.presenter.rank_column(p["source_index"], p["destination"]),
            "Computes 1-based average ranks for nonmissing numeric observations.",
        )

    def delete_rows_dialog(self):
        self._commit_editor()
        text, accepted = QInputDialog.getText(self, "Delete Rows", "Rows to delete (e.g., 1 3 5 or 2:4):")
        if not accepted or not text.strip(): return
        def parse_and_delete():
            rows = []
            for part in text.replace(",", " ").split():
                if ":" in part:
                    a, b = part.split(":", 1)
                    rows.extend(range(int(a) - 1, int(b)))
                else:
                    rows.append(int(part) - 1)
            self.presenter.delete_rows(rows)
        self._call(parse_and_delete)

    def erase_variables_dialog(self):
        self._dialog(
            "Erase Variables",
            [selector("indices", "Columns to erase", True, 1, None, ("number", "text", "date"))],
            [
                {"key": "clear_constants", "label": "Constants", "boolean": True, "text": "Erase all stored constants"},
                {"key": "clear_matrices", "label": "Matrices", "boolean": True, "text": "Erase all stored matrices"},
            ],
            lambda p: self.presenter.erase_variables(p["indices"], p["clear_constants"], p["clear_matrices"]),
            "Clears selected columns back to empty C1, C2… placeholders.",
        )

    def edit_last_dialog(self):
        if self._last_dialog_action is not None:
            self._last_dialog_action()
        else:
            self.describe()

    def cancel_operation(self):
        self._commit_editor()
        self.table.clearSelection()
        self.statusBar().showMessage("Canceled active selection", 4000)

    def _printing(self):
        from .printing import PrintController
        if not hasattr(self, "_print_controller"):
            self._print_controller = PrintController(self)
        return self._print_controller

    def print_current(self, entry=None):
        self._printing().run("print", entry if isinstance(entry, dict) else None)

    def run_command_line(self):
        raw = self.command_editor.toPlainText().strip()
        if not raw: return
        for line in raw.splitlines():
            cmd = line.strip()
            if cmd:
                self.command_history_view.appendPlainText(f"MTB > {cmd}")
                self._call(lambda l=cmd: self.presenter.execute_session_command(l), result=True)
        self.command_editor.clear()

    def undo(self):
        self._commit_editor()
        if not self.graph_options_pane.flush():return
        def restore():
            command=self.presenter._undo_stack[-1] if self.presenter._undo_stack else {}
            self.presenter.undo()
            if 'column_view_before' in command:self._restore_column_view(command['column_view_before'])
        self._call(restore)
        if self.graph_options_pane.bound_entry is self.selected_entry:self.graph_options_pane.load_entry(self.selected_entry)

    def redo(self):
        self._commit_editor()
        if not self.graph_options_pane.flush():return
        def restore():
            command=self.presenter._redo_stack[-1] if self.presenter._redo_stack else {}
            self.presenter.redo()
            if 'column_view_after' in command:self._restore_column_view(command['column_view_after'])
        self._call(restore)
        if self.graph_options_pane.bound_entry is self.selected_entry:self.graph_options_pane.load_entry(self.selected_entry)

    def _confirm_leave(self):
        if not self.graph_options_pane.flush():return False
        self._commit_editor()
        if not self.presenter.dirty: return True
        choice = QMessageBox.question(self, "Unsaved changes", "Save the current project before continuing?", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Save)
        if choice == QMessageBox.StandardButton.Cancel: return False
        if choice == QMessageBox.StandardButton.Save: return self.save_document()
        return True

    def closeEvent(self, event):
        if self._confirm_leave():
            if hasattr(self, '_startup_worker') and self._startup_worker and self._startup_worker.isRunning():
                try:
                    self._startup_worker.quit()
                    self._startup_worker.wait(500)
                except Exception:
                    pass
            if hasattr(self, "r_workbench"):
                self.r_workbench.shutdown(wait=True)
            # Tab/header signals can fire while Qt dismantles child widgets.
            self._refreshing = True
            self.worksheet_tabs.blockSignals(True); self.worksheet_selector.blockSignals(True)
            self.table.blockSignals(True); self.column_names.blockSignals(True)
            event.accept()
        else: event.ignore()

    def new_document(self):
        if self._confirm_leave():
            self.presenter.new(); self._prepare_blank(); self.page = 0; self.selected_entry = None
            self.refresh(); self._show_welcome()

    def open_document(self, typed=False):
        if not self._confirm_leave(): return
        path, _ = QFileDialog.getOpenFileName(self, "Open project or worksheet", "", "Projects and worksheets (*.mpx *.statcraft *.csv *.tsv *.tab *.mwx *.jmp *.jsl);;JMP Tables (*.jmp *.jsl);;All files (*)")
        if not path: return
        column_types = None
        if typed and Path(path).suffix.lower() in (".csv", ".tsv", ".tab"):
            text, accepted = QInputDialog.getText(self, "Column types", "Types in column order: number, text or date. Blank uses inference.")
            if not accepted: return
            if text.strip(): column_types = [value.strip().lower() for value in text.split(",")]
        self._call(lambda: self.load_path(path, column_types))

    def load_path(self, path, column_types=None):
        if not self.graph_options_pane.flush():raise ValueError('Correct the Graph Options values before opening another project.')
        notices = self.presenter.load(path, column_types)
        self.graph_options_pane.load_entry(None);self.graph_options_pane.hide()
        self._active_graph_frame=None;self._active_chart_widget=None
        self.page = 0; self.selected_entry = None; self.refresh()
        self.output_header_bar.setVisible(False)
        self.result_tabs.tabBar().setVisible(True)
        self.result_title.setText("Project opened" if self.presenter.native_project else "Worksheet opened")
        self._clear_result_tabs()
        notes = QPlainTextEdit(); notes.setReadOnly(True); notes.setPlainText("\n\n".join(notices) if notices else "Ready for analysis.")
        self.result_tabs.addTab(notes, "Import notes"); self.result_state.setText("Import details and retained-format limitations")
        self.rerun_button.setEnabled(False)
        self._workspace.restore(self.presenter.workspace)
        if self.selected_entry is None and self.presenter.native_project:
            project = self.presenter.native_project
            active_id = project.worksheet_ids[project.active_index]
            outputs = [e for e in self.presenter.history if e.get('result',{}).get('analysis')=='native_saved_output' and e.get('worksheet_id')==active_id]
            if outputs:self.show_result(outputs[-1])
        return notices

    def save_path(self, path):
        if not self.graph_options_pane.flush():raise ValueError('Correct the Graph Options values before saving.')
        self._commit_editor()
        state=self._workspace.snapshot()
        self.presenter.workspace=state if any(state[k] for k in ("open_ids","closed_ids","views","report_pad")) else None
        self.presenter.save(path);self._workspace.history=self.presenter.history
        self.refresh(); self.statusBar().showMessage("Project saved", 8000)
        return True

    def save_document(self, save_as=False):
        self._commit_editor(); native = self.presenter.native_project is not None
        owned = native and getattr(self.presenter.native_project, 'statcraft_owned', False)
        path = None if save_as else self.presenter.project_path
        selected_filter = 'MPX project (*.mpx)'
        if not path:
            filters = 'MPX project (*.mpx)' if native else 'MPX project (*.mpx);;StatCraft worksheet (*.statcraft)'
            path, selected_filter = QFileDialog.getSaveFileName(self, "Save MPX copy" if native and not owned else "Save project", "", filters)
        if not path: return False
        suffix = '.statcraft' if not native and ('statcraft' in selected_filter.lower() or Path(path).suffix.lower() == '.statcraft') else '.mpx'
        if not Path(path).suffix: path += suffix
        if native and not owned and self.presenter.dirty:
            choice = QMessageBox.question(self, "Save native copy", "Original native output is retained without recalculation. StatCraft session results are saved separately from native commands. Save the supported changes to this copy?", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel)
            if choice != QMessageBox.StandardButton.Save: return False
        return bool(self._call(lambda: self.save_path(path)))

    def export_excel(self,all_worksheets=True):
        self._commit_editor()
        path,_=QFileDialog.getSaveFileName(self,'Export Project to Excel' if all_worksheets else 'Export Worksheet to Excel','StatCraft.xlsx','Excel Workbook (*.xlsx)')
        if not path:return
        if not path.lower().endswith('.xlsx'):path+='.xlsx'
        result=self._call(lambda:self.presenter.export_excel(path,all_worksheets))
        if result:self.statusBar().showMessage(f"Exported {result['worksheets']} worksheet(s) to {path}",10000)

    def convert_mpx_excel(self):
        source,_=QFileDialog.getOpenFileName(self,'Convert MPX File to Excel','','MPX Project / Worksheet (*.mpx *.mwx)')
        if not source:return
        path,_=QFileDialog.getSaveFileName(self,'Save Excel Workbook',str(Path(source).with_suffix('.xlsx')),'Excel Workbook (*.xlsx)')
        if not path:return
        if not path.lower().endswith('.xlsx'):path+='.xlsx'
        from .xlsx_export import convert_mpx
        result=self._call(lambda:convert_mpx(source,path))
        if result:self.statusBar().showMessage(f"Converted {result['worksheets']} worksheet(s) to {path}",10000)

    def doe_planner(self,kind=None):
        from .doe_planner_dialog import DOEPlannerDialog
        self._commit_editor();self._last_dialog_action=lambda:self.doe_planner(kind)
        dialog=DOEPlannerDialog(self)
        if kind is not None:dialog.family.setCurrentIndex(dialog.family.findData(kind))
        if dialog.exec()==QDialog.DialogCode.Accepted:
            entry=self._call(lambda:self.presenter.create_doe_plan(**dialog.parameters),result=True)
            if entry:self.refresh();self.show_result(entry)

    def export_data(self):
        self._commit_editor()
        choice = QMessageBox.question(self, "Delimited export", "\n\n".join(self.presenter.export_notices()), QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        if choice != QMessageBox.StandardButton.Ok: return
        path, selected = QFileDialog.getSaveFileName(self, "Export worksheet table", "", "CSV (*.csv);;Tab-separated (*.tsv)")
        if path:
            if not Path(path).suffix: path += ".tsv" if "tsv" in selected else ".csv"
            self._call(lambda: self.presenter.export(path))

    def export_report(self):
        if self.selected_entry is None: QMessageBox.information(self, "Export report", "Select a result first."); return
        path, _ = QFileDialog.getSaveFileName(self, "Export report", "", "Text report (*.txt)")
        if path: self._call(lambda: Path(path).write_text(format_entry(self.selected_entry), encoding="utf-8"))

    def _current_column(self):
        index = self._column_targets()[0]
        if index >= len(self.presenter.worksheet.columns): raise ValueError("Select an existing column.")
        return index

    def add_column(self):
        name, accepted = QInputDialog.getText(self, "Add column", "Name")
        if not accepted: return
        kind, accepted = QInputDialog.getItem(self, "Column type", "Type", ["number", "text", "date"], editable=False)
        if accepted: self._call(lambda: self.presenter.add_column(name, kind))

    def add_rows(self):
        count, accepted = QInputDialog.getInt(self, "Add rows", "Rows to add", 1, 1, 100000)
        if accepted: self._call(lambda: self.presenter.add_rows(count))

    def rename_column(self):
        index = self._current_column(); old = self.presenter.worksheet.columns[index].name
        name, accepted = QInputDialog.getText(self, "Rename column", "Name", text=old)
        if accepted: self._call(lambda: self.presenter.rename_column(index, name))

    def change_type(self):
        index = self._current_column(); types = ["number", "text", "date"]
        kind, accepted = QInputDialog.getItem(self, "Change column type", "All existing values must convert successfully.", types, types.index(self.presenter.worksheet.columns[index].kind), False)
        if accepted: self._call(lambda: self.presenter.set_column_type(index, kind))

    def stored_constants(self):
        from .modern_stored_data import ConstantsDialog
        self._commit_editor()
        read_only = (self.presenter.native_project is not None and not getattr(self.presenter.native_project, 'statcraft_owned', False)) or any(c.kind != 'number' for c in self.presenter.worksheet.constants)
        dialog = ConstantsDialog(self, self.presenter.worksheet, read_only)
        if dialog.exec() == QDialog.DialogCode.Accepted and not read_only:
            self._call(lambda: self.presenter.replace_stored_data(constants=dialog.constants))

    def stored_matrices(self):
        from .modern_stored_data import MatricesDialog
        self._commit_editor()
        read_only = self.presenter.native_project is not None and not getattr(self.presenter.native_project, 'statcraft_owned', False)
        dialog = MatricesDialog(self, self.presenter.worksheet, read_only)
        if dialog.exec() == QDialog.DialogCode.Accepted and not read_only:
            self._call(lambda: self.presenter.replace_stored_data(matrices=dialog.matrices))

    def _dialog(self, title, selectors, fields, callback, note=""):
        self._commit_editor()
        dialog = ProcedureDialog(self, title, self.presenter.worksheet, selectors, fields, note)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._call(lambda: callback(dialog.parameters), result=True)

    def describe(self):
        self._dialog("Display Descriptive Statistics", [selector("indices", "Variables", True)], [], lambda p: self.presenter.describe_columns(p["indices"]), "Select one or more numeric columns. Missing observations are counted separately.")

    def store_descriptive_dialog(self):
        from .store_descriptive import StoreDescriptiveDialog
        self._commit_editor()
        self._last_dialog_action = self.store_descriptive_dialog
        dlg = StoreDescriptiveDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.get_parameters()
            if p:
                entry = self._call(lambda: self.presenter.store_descriptive_stats(**p), result=True)
                self.refresh()

    def inference_dialog(self, method):
        count = 1 if method == "one_sample_t" else 2
        maximum = None if method == "one_way_anova" else count
        fields = []
        if method in ("one_sample_t", "two_sample_t", "paired_t"): fields.append(numeric("mu", "Hypothesized mean / difference", 0))
        if method != "one_way_anova": fields.append(numeric("confidence", "Confidence level (0–1)", .95))
        note = "First selected column is X (predictor); second is Y (response)." if method == "linear_regression" else "For paired data, worksheet rows stay aligned. All tests are two-sided."
        self._dialog(method.replace("_", " ").title(), [selector("indices", "Variables", True, count, maximum)], fields,
            lambda p: self.presenter.inference(method, p["indices"], p.get("mu", 0), p.get("confidence", .95)), note)

    def create_factorial(self):
        from .doe_dialogs import CreateFactorialDialog
        dialog = CreateFactorialDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not self._confirm_leave(): return
        entry = self._call(lambda: self.presenter.create_factorial(**dialog.parameters), result=True)
        self.page = 0; self.refresh()
        if entry is not None and not dialog.summary:
            self.presenter.history = []; self._show_welcome(); self.refresh()

    def analyze_factorial(self):
        self._commit_editor()
        from .doe_dialogs import AnalyzeFactorialDialog
        dialog = AnalyzeFactorialDialog(self, self.presenter.worksheet)
        if dialog.exec() == QDialog.DialogCode.Accepted: self._call(lambda: self.presenter.analyze_factorial(**dialog.parameters), result=True)

    def create_dsd_dialog(self):
        from .dsd_dialogs import CreateDefinitiveScreeningDesignDialog
        dlg = CreateDefinitiveScreeningDesignDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted or not self._confirm_leave():
            return
        entry = self._call(lambda: self.presenter.create_definitive_screening_design(**dlg.parameters), result=True)
        self.page = 0
        self.refresh()
        if entry:
            self.show_result(entry)

    def analyze_dsd_dialog(self):
        self._commit_editor()
        from .dsd_dialogs import AnalyzeDefinitiveScreeningDesignDialog
        dlg = AnalyzeDefinitiveScreeningDesignDialog(self.presenter.worksheet, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.values()
            entry = self._call(lambda: self.presenter.analyze_definitive_screening_design(**vals), result=True)
            if entry:
                self.show_result(entry)

    def create_d_optimal_dialog(self):
        from .optimal_dialogs import CreateDOptimalDesignDialog
        dlg = CreateDOptimalDesignDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted or not self._confirm_leave():
            return
        entry = self._call(lambda: self.presenter.create_optimal_design(**dlg.parameters), result=True)
        self.page = 0
        self.refresh()
        if entry:
            self.show_result(entry)

    def evaluate_design_dialog(self):
        self._commit_editor()
        from .optimal_dialogs import EvaluateDesignDialog
        dlg = EvaluateDesignDialog(self.presenter.worksheet, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.values()
            entry = self._call(lambda: self.presenter.evaluate_design(**vals), result=True)
            if entry:
                self.show_result(entry)

    def alt_dialog(self):
        self._commit_editor()
        from .alt_dialogs import AcceleratedLifeTestingDialog
        dlg = AcceleratedLifeTestingDialog(self.presenter.worksheet, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.values()
            entry = self._call(lambda: self.presenter.accelerated_life_testing(**vals), result=True)
            if entry:
                self.show_result(entry)

    def emp_dialog(self):
        self._commit_editor()
        from .emp_dialogs import EvaluatingMeasurementProcessDialog
        dlg = EvaluatingMeasurementProcessDialog(self.presenter.worksheet, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.values()
            entry = self._call(lambda: self.presenter.evaluating_measurement_process(**vals), result=True)
            if entry:
                self.show_result(entry)

    def fit_y_by_x_dialog(self):
        self._commit_editor()
        from .fit_y_by_x_dialog import FitYByXDialog
        dlg = FitYByXDialog(self.presenter.worksheet, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.values()
            entry = self._call(lambda: self.presenter.fit_y_by_x(**vals), result=True)
            if entry:
                self.show_result(entry)

    def jmp_distribution_dialog(self):
        self._commit_editor()
        from .jmp_distribution_dialog import JMPDistributionDialog
        dlg = JMPDistributionDialog(self.presenter.worksheet, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.values()
            entry = self._call(lambda: self.presenter.jmp_distribution(**vals), result=True)
            if entry:
                self.show_result(entry)

    def control_chart_builder_dialog(self):
        self._commit_editor()
        from .control_chart_builder_dialog import ControlChartBuilderDialog
        dlg = ControlChartBuilderDialog(self.presenter.worksheet, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.values()
            entry = self._call(lambda: self.presenter.control_chart_builder(**vals), result=True)
            if entry:
                self.show_result(entry)

    def process_screening_dialog(self):
        self._commit_editor()
        from .process_screening_dialog import ProcessScreeningDialog
        dlg = ProcessScreeningDialog(self.presenter.worksheet, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.values()
            entry = self._call(lambda: self.presenter.process_screening(**vals), result=True)
            if entry:
                self.show_result(entry)

    def variability_chart_dialog(self):
        self._commit_editor()
        from .variability_dialog import VariabilityChartDialog
        dlg = VariabilityChartDialog(self)
        dlg.exec()

    def cart_tree_dialog(self):
        self._commit_editor()
        from .tree_dialogs import DecisionTreeDialog
        dlg = DecisionTreeDialog(self.presenter.worksheet, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.values()
            entry = self._call(lambda: self.presenter.cart_tree(**vals), result=True)
            if entry:
                self.show_result(entry)

    def one_variance(self):
        self._dialog("1 Variance — Normal Population", [selector("index", "Variable")],
            [numeric("null_stdev", "Hypothesized standard deviation", 1), numeric("confidence", "Confidence level (0–1)", .95)],
            lambda parameters: self.presenter.one_variance(**parameters),
            "Two-sided chi-square test, with standard deviation and variance confidence intervals. Requires independent normal observations; Bonett and robust methods are not implemented.")

    def normality(self):
        self._dialog("Normality Test", [selector("index", "Variable")], [],
            lambda parameters: self.presenter.normality(**parameters),
            "Anderson–Darling test of normality, with an approximate P value and a normal probability plot. Requires at least 8 observations; missing values are omitted.")

    def correlation(self):
        self._dialog("Correlation", [selector("indices", "Variables", True, 2, 50)],
            [{"key": "method", "label": "Method", "choices": ["Pearson", "Spearman"]},
             {"key": "missing", "label": "Missing observations", "choices": ["Pairwise", "Listwise"]},
             numeric("confidence", "Pearson confidence level (0–1)", .95)],
            lambda p: self.presenter.correlation(**p),
            "Two-sided tests of zero correlation. Pearson uses Fisher-z intervals; Spearman uses average ranks and approximate P values. P values are unadjusted.")

    def covariance_dialog(self):
        self._commit_editor()
        from .covariance_dialogs import CovarianceDialog
        from PySide6.QtWidgets import QDialog
        dlg = CovarianceDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        p = dlg.get_settings()
        self._call(lambda: self.presenter.covariance(**p), result=True)

    def one_proportion(self):
        self._dialog("1 Proportion", [selector("index", "Binary sample")],
            [numeric("null_proportion", "Hypothesized proportion", .5), numeric("confidence", "Confidence level (0–1)", .95),
             {"key": "alternative", "label": "Alternative", "choices": ["two-sided", "less", "greater"]}],
            lambda p: self.presenter.one_proportion(**p),
            "Numeric data must contain 0 and 1; 1 is the event. Exact binomial test and Clopper-Pearson confidence bounds. Missing observations are omitted.")

    def two_proportions(self):
        self._dialog("2 Proportions", [selector("first_index", "Sample 1"), selector("second_index", "Sample 2")],
            [numeric("confidence", "Confidence level (0–1)", .95)],
            lambda p: self.presenter.two_proportions(**p),
            "Independent binary samples: 1 is the event. Two-sided pooled Z and Fisher exact tests of equal proportions; Newcombe difference interval. Missing values are omitted separately.")

    def stacked_anova(self):
        self._dialog("One-Way ANOVA", [selector("response_index", "Response"), selector("factor_index", "Factor", kinds=("number", "text"))], [], lambda p: self.presenter.stacked_anova(**p), "Numeric response and a separate numeric or text factor. Incomplete pairs are omitted.")

    def oneway_anova_dialog(self):
        from .oneway_dialogs import OneWayAnovaDialog
        dlg = OneWayAnovaDialog(self)
        if dlg.exec():
            if dlg.entry is not None:
                self.set_entry(dlg.entry)
                self.refresh()

    def stacked_anova(self):
        self.oneway_anova_dialog()

    def twoway_anova_dialog(self):
        from .twoway_anova_dialogs import TwoWayAnovaDialog
        self._commit_editor()
        self._last_dialog_action = self.twoway_anova_dialog
        dlg = TwoWayAnovaDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.settings
            if p:
                entry = self._call(lambda: self.presenter.twoway_anova(**p), result=True)
                if entry:
                    self.show_result(entry)

    def main_effects_plot_dialog(self):
        from .anova_plots_dialogs import MainEffectsPlotDialog
        self._commit_editor()
        self._last_dialog_action = self.main_effects_plot_dialog
        dlg = MainEffectsPlotDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.get_parameters()
            if p:
                entry = self._call(lambda: self.presenter.main_effects_plot(**p), result=True)
                if entry:
                    self.show_result(entry)

    def interactions_plot_dialog(self):
        from .anova_plots_dialogs import InteractionsPlotDialog
        self._commit_editor()
        self._last_dialog_action = self.interactions_plot_dialog
        dlg = InteractionsPlotDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.get_parameters()
            if p:
                entry = self._call(lambda: self.presenter.interactions_plot(**p), result=True)
                if entry:
                    self.show_result(entry)

    def one_sample_proportion_dialog(self):
        from .one_sample_proportion_dialogs import OneSampleProportionDialog
        self._commit_editor()
        self._last_dialog_action = self.one_sample_proportion_dialog
        dlg = OneSampleProportionDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.result_payload
            if p:
                entry = self._call(lambda: self.presenter.one_sample_proportion(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def one_sample_variance_dialog(self):
        from .one_variance_dialogs import OneVarianceDialog
        self._commit_editor()
        self._last_dialog_action = self.one_sample_variance_dialog
        dlg = OneVarianceDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.result_payload
            if p:
                entry = self._call(lambda: self.presenter.one_variance(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def two_sample_variances_dialog(self):
        from .two_variances_dialogs import TwoVariancesDialog
        self._commit_editor()
        self._last_dialog_action = self.two_sample_variances_dialog
        dlg = TwoVariancesDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.result_payload
            if p:
                entry = self._call(lambda: self.presenter.two_variances(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def two_sample_poisson_dialog(self):
        from .two_sample_poisson_dialogs import TwoSamplePoissonDialog
        self._commit_editor()
        self._last_dialog_action = self.two_sample_poisson_dialog
        dlg = TwoSamplePoissonDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.result_payload or dlg.settings
            if p:
                entry = self._call(lambda: self.presenter.two_sample_poisson(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def one_sample_poisson_dialog(self):
        from .one_sample_poisson_dialogs import OneSamplePoissonDialog
        self._commit_editor()
        self._last_dialog_action = self.one_sample_poisson_dialog
        dlg = OneSamplePoissonDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.result_payload or dlg.settings
            if p:
                entry = self._call(lambda: self.presenter.one_sample_poisson(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def two_sample_proportion_dialog(self):
        from .two_sample_proportion_dialogs import TwoSampleProportionDialog
        self._commit_editor()
        self._last_dialog_action = self.two_sample_proportion_dialog
        dlg = TwoSampleProportionDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.result_payload
            if p:
                entry = self._call(lambda: self.presenter.two_sample_proportion(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def one_sample_z_dialog(self):
        from .one_sample_z_dialogs import OneSampleZDialog
        self._commit_editor()
        self._last_dialog_action = self.one_sample_z_dialog
        dlg = OneSampleZDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.result_payload
            if p:
                entry = self._call(lambda: self.presenter.one_sample_z(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def one_sample_t_dialog(self):
        from .one_sample_t_dialogs import OneSampleTDialog
        self._commit_editor()
        self._last_dialog_action = self.one_sample_t_dialog
        dlg = OneSampleTDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.result_payload
            if p:
                entry = self._call(lambda: self.presenter.one_sample_t(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def paired_t_dialog(self):
        from .paired_t_dialogs import PairedTDialog
        self._commit_editor()
        self._last_dialog_action = self.paired_t_dialog
        dlg = PairedTDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.result_payload
            if p:
                entry = self._call(lambda: self.presenter.paired_t(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def two_sample_t_dialog(self):
        from .two_sample_t_dialogs import TwoSampleTDialog
        self._commit_editor()
        self._last_dialog_action = self.two_sample_t_dialog
        dlg = TwoSampleTDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.result_payload
            if p:
                entry = self._call(lambda: self.presenter.two_sample_t(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def test_equal_variances_dialog(self):
        from .equal_variances_dialogs import TestEqualVariancesDialog
        self._commit_editor()
        self._last_dialog_action = self.test_equal_variances_dialog
        dlg = TestEqualVariancesDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.result_payload
            if p:
                entry = self._call(lambda: self.presenter.test_equal_variances(
                    stacked=p.get('stacked', True),
                    response_index=p.get('response_index'),
                    factor_indices=p.get('factor_indices'),
                    response_indices=p.get('response_indices'),
                    options=p.get('options'),
                ), result=True)
                if entry:
                    self.show_result(entry)

    def equal_variances(self, stacked):
        selectors = [selector("response_index", "Response"), selector("factor_index", "Factor", kinds=("number", "text"))] if stacked else [selector("indices", "Group columns", True, 2)]
        fields = [{"key": "method", "label": "Method", "choices": ["Levene", "Bartlett"]}]
        action = self.presenter.equal_variances_stacked if stacked else self.presenter.equal_variances_columns
        self._dialog("Test for Equal Variances", selectors, fields, lambda p: action(**p), "Bartlett assumes normal populations. Levene uses the implemented robust center convention.")

    def create_response_surface(self):
        from .response_surface_dialogs import CreateSurfaceDialog
        self._commit_editor();CreateSurfaceDialog(self).exec()

    def _mixture_process_entries(self):
        entries=[]
        for entry in self.presenter.history:
            if entry.get('recipe',{}).get('action')!='analyze_mixture_process' or entry.get('source_unavailable'):continue
            try:
                if self.presenter.result_worksheet(entry) is self.presenter.worksheet:entries.append(entry)
            except ValueError:continue
        return entries

    def mixture_process_contour(self):
        from .mixture_condition_dialogs import MixtureProcessContourDialog
        self._commit_editor();self._last_dialog_action=self.mixture_process_contour
        dialog=MixtureProcessContourDialog(self.presenter.worksheet,self._mixture_process_entries(),self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self._call(lambda:self.presenter.mixture_process_contour(**dialog.parameters),result=True)

    def optimize_mixture_process(self):
        from .mixture_condition_dialogs import MixtureProcessOptimizerDialog
        self._commit_editor();self._last_dialog_action=self.optimize_mixture_process
        dialog=MixtureProcessOptimizerDialog(self.presenter.worksheet,self._mixture_process_entries(),self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self._call(lambda:self.presenter.optimize_mixture_process(**dialog.parameters),result=True)

    def optimize_mixture_joint(self):
        from .mixture_joint_dialog import MixtureJointOptimizerDialog
        self._commit_editor();self._last_dialog_action=self.optimize_mixture_joint
        dialog=MixtureJointOptimizerDialog(self.presenter.worksheet,self._mixture_process_entries(),self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self._call(lambda:self.presenter.optimize_mixture_joint(**dialog.parameters),result=True)

    def analyze_mixture_process(self):
        from .mixture_process_dialogs import MixtureProcessDialog
        self._commit_editor();self._last_dialog_action=self.analyze_mixture_process
        dialog=MixtureProcessDialog(self.presenter.worksheet,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self._call(lambda:self.presenter.analyze_mixture_process(**dialog.parameters),result=True)

    def predict_mixture_process(self):
        from .mixture_process_dialogs import MixtureProcessPredictionDialog
        self._commit_editor();self._last_dialog_action=self.predict_mixture_process
        entries=[]
        for entry in self.presenter.history:
            if entry.get('recipe',{}).get('action')!='analyze_mixture_process' or entry.get('source_unavailable'):continue
            try:
                if self.presenter.result_worksheet(entry) is self.presenter.worksheet:entries.append(entry)
            except ValueError:continue
        dialog=MixtureProcessPredictionDialog(self.presenter.worksheet,entries,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self._call(lambda:self.presenter.predict_mixture_process(**dialog.parameters),result=True)

    def analyze_mixture(self):
        from .doe_analysis_dialogs import BuildAnalyzeMixtureDialog
        self._commit_editor();self._last_dialog_action=self.analyze_mixture
        dialog=BuildAnalyzeMixtureDialog(self.presenter.worksheet,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self._call(lambda:self.presenter.analyze_mixture(**dialog.parameters),result=True)

    def _mixture_model_entries(self):
        entries=[]
        for entry in self.presenter.history:
            if entry.get('recipe',{}).get('action')!='analyze_mixture' or entry.get('source_unavailable'):continue
            try:
                if self.presenter.result_worksheet(entry) is self.presenter.worksheet:entries.append(entry)
            except ValueError:continue
        return entries

    def mixture_contour(self):
        from .mixture_exploration_dialogs import MixtureContourDialog
        self._commit_editor();self._last_dialog_action=self.mixture_contour
        dialog=MixtureContourDialog(self.presenter.worksheet,self._mixture_model_entries(),self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self._call(lambda:self.presenter.mixture_contour(**dialog.parameters),result=True)

    def optimize_mixture_multi(self):
        from .mixture_multi_optimizer_dialog import MixtureMultiOptimizerDialog
        self._commit_editor();self._last_dialog_action=self.optimize_mixture_multi
        dialog=MixtureMultiOptimizerDialog(self.presenter.worksheet,self._mixture_model_entries(),self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self._call(lambda:self.presenter.optimize_mixture_multi(**dialog.parameters),result=True)

    def _reoptimize_mixture_multi(self,entry):
        def apply():
            self.presenter.select_worksheet(self.presenter.native_project.worksheets.index(self.presenter.result_worksheet(entry)))
            if entry.get('source_unavailable'):raise ValueError(entry['source_unavailable'])
            params=entry['recipe']['parameters'];options=copy.deepcopy(params['options'])
            options['start_values']=list(entry['result']['components'])
            result=self.presenter.optimize_mixture_multi(params['responses'],params['bounds'],options)
            for key in ('graph_presentation','graph_styles'):
                if key in entry:result[key]=copy.deepcopy(entry[key])
            return result
        self._commit_editor();self._call(apply,result=True)

    def _select_mixture_profile(self,entry,components):
        def apply():
            self.presenter.select_worksheet(self.presenter.native_project.worksheets.index(self.presenter.result_worksheet(entry)))
            if entry.get('source_unavailable'):raise ValueError(entry['source_unavailable'])
            params=entry['recipe']['parameters']
            result=self.presenter.evaluate_mixture_multi(params['responses'],components,params['bounds'],params['options'])
            for key in ('graph_presentation','graph_styles'):
                if key in entry:result[key]=copy.deepcopy(entry[key])
            return result
        self._commit_editor();self._call(apply,result=True)

    def optimize_mixture(self):
        from .mixture_exploration_dialogs import MixtureOptimizerDialog
        self._commit_editor();self._last_dialog_action=self.optimize_mixture
        dialog=MixtureOptimizerDialog(self.presenter.worksheet,self._mixture_model_entries(),self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self._call(lambda:self.presenter.optimize_mixture(**dialog.parameters),result=True)

    def predict_mixture(self):
        from .mixture_prediction_dialog import MixturePredictionDialog
        self._commit_editor();self._last_dialog_action=self.predict_mixture
        entries=[]
        for entry in self.presenter.history:
            if entry.get('recipe',{}).get('action')!='analyze_mixture' or entry.get('source_unavailable'):continue
            try:
                if self.presenter.result_worksheet(entry) is self.presenter.worksheet:entries.append(entry)
            except ValueError:continue
        dialog=MixturePredictionDialog(self.presenter.worksheet,entries,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self._call(lambda:self.presenter.predict_mixture(**dialog.parameters),result=True)

    def analyze_dynamic_taguchi(self):
        from .dynamic_taguchi_dialog import BuildAnalyzeDynamicTaguchiDialog
        self._commit_editor();self._last_dialog_action=self.analyze_dynamic_taguchi
        dialog=BuildAnalyzeDynamicTaguchiDialog(self.presenter.worksheet,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self._call(lambda:self.presenter.analyze_dynamic_taguchi(**dialog.parameters),result=True)

    def analyze_taguchi(self):
        from .doe_analysis_dialogs import BuildAnalyzeTaguchiDialog
        self._commit_editor();self._last_dialog_action=self.analyze_taguchi
        dialog=BuildAnalyzeTaguchiDialog(self.presenter.worksheet,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self._call(lambda:self.presenter.analyze_taguchi(**dialog.parameters),result=True)

    def analyze_response_surface(self):
        from .response_surface_dialogs import AnalyzeSurfaceDialog
        self._commit_editor();AnalyzeSurfaceDialog(self).exec()

    def general_linear_model(self):
        from .glm_dialogs import GeneralLinearModelDialog
        self._commit_editor();GeneralLinearModelDialog(self).exec()

    def multiple_regression(self):
        self._dialog("Fit Regression Model", [selector("response_index", "Response"), selector("predictor_indices", "Continuous predictors", True)], [numeric("confidence", "Confidence level", .95)], lambda p: self.presenter.multiple_regression(**p), "Choose a response and distinct numeric predictors. An intercept is included; incomplete rows are omitted together.")

    def imr_dialog(self):
        from .imr_dialogs import IMRChartDialog
        self._commit_editor()
        self._last_dialog_action = self.imr_dialog
        dlg = IMRChartDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.selected_params
            if p:
                entry = self._call(lambda: self.presenter.imr_chart(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def imr(self):
        self._dialog("I-MR Chart", [selector("index", "Variable")], [], lambda p: self.presenter.individuals_moving_range(**p), "Moving range span 2; three-sigma limits. Missing gaps are not bridged.")

    def attribute_control_dialog(self, chart_type="P"):
        from .attribute_control_dialogs import AttributeChartDialog
        self._commit_editor()
        self._last_dialog_action = lambda: self.attribute_control_dialog(chart_type)
        dlg = AttributeChartDialog(self.presenter.worksheet, chart_type=chart_type, parent=self)
        if dlg.exec():
            p = dlg.selected_params
            if p:
                entry = self._call(lambda: self.presenter.attribute_control_chart(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def attribute(self, chart):
        self.attribute_control_dialog(chart)

    def time_weighted_control_dialog(self, chart_type="EWMA"):
        from .time_weighted_control_dialogs import TimeWeightedChartDialog
        self._commit_editor()
        self._last_dialog_action = lambda: self.time_weighted_control_dialog(chart_type)
        dlg = TimeWeightedChartDialog(self.presenter.worksheet, chart_type=chart_type, parent=self)
        if dlg.exec():
            cfg = dlg.get_configuration()
            if cfg:
                entry = self._call(lambda: self.presenter.time_weighted_control_chart(settings=cfg), result=True)
                if entry:
                    self.show_result(entry)

    def moving_average_dialog(self):
        self.time_weighted_control_dialog("MA")

    def ewma_dialog(self):
        self.time_weighted_control_dialog("EWMA")

    def cusum_dialog(self):
        self.time_weighted_control_dialog("CUSUM")

    def rare_event_control_dialog(self, chart_type="G"):
        from .rare_event_control_dialogs import RareEventChartDialog
        self._commit_editor()
        self._last_dialog_action = lambda: self.rare_event_control_dialog(chart_type)
        dlg = RareEventChartDialog(self.presenter.worksheet, chart_type=chart_type, parent=self)
        if dlg.exec():
            cfg = dlg.get_configuration()
            if cfg:
                entry = self._call(lambda: self.presenter.rare_event_control_chart(settings=cfg), result=True)
                if entry:
                    self.show_result(entry)

    def g_chart_dialog(self):
        self.rare_event_control_dialog("G")

    def t_chart_dialog(self):
        self.rare_event_control_dialog("T")

    def multivariate_control_dialog(self, chart_type="TSQUARED"):
        from .multivariate_control_dialogs import MultivariateChartDialog
        self._commit_editor()
        self._last_dialog_action = lambda: self.multivariate_control_dialog(chart_type)
        dlg = MultivariateChartDialog(self.presenter.worksheet, chart_type=chart_type, parent=self)
        if dlg.exec():
            cfg = dlg.get_configuration()
            if cfg:
                entry = self._call(lambda: self.presenter.multivariate_control_chart(settings=cfg), result=True)
                if entry:
                    self.show_result(entry)

    def tsquared_chart_dialog(self):
        self.multivariate_control_dialog("TSQUARED")

    def genvar_chart_dialog(self):
        self.multivariate_control_dialog("GENVAR")

    def mewma_chart_dialog(self):
        self.multivariate_control_dialog("MEWMA")

    def pareto_chart_dialog(self):
        from .pareto_dialogs import ParetoChartDialog
        self._commit_editor()
        self._last_dialog_action = self.pareto_chart_dialog
        dlg = ParetoChartDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            cfg = dlg.get_configuration()
            if cfg:
                entry = self._call(lambda: self.presenter.pareto_chart(settings=cfg), result=True)
                if entry:
                    self.show_result(entry)

    def type1_gage_dialog(self):
        from .type1_gage_dialogs import Type1GageDialog
        self._commit_editor()
        self._last_dialog_action = self.type1_gage_dialog
        dlg = Type1GageDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = dlg.result_params
            if p:
                entry = self._call(
                    lambda: self.presenter.type1_gage(
                        measurement_index=p["measurement_index"],
                        reference=p["reference"],
                        settings=p.get("settings"),
                        measurement_name=p.get("measurement_name"),
                    ),
                    result=True,
                )
                if entry:
                    self.show_result(entry)

    def attribute_capability_dialog(self, method='binomial'):
        from .attribute_capability_dialogs import AttributeCapabilityDialog
        self._last_dialog_action = lambda: self.attribute_capability_dialog(method)
        dialog = AttributeCapabilityDialog(self, self.presenter.worksheet, method)
        if dialog.exec():
            parameters = dialog.get_configuration()
            entry = self._call(lambda: self.presenter.attribute_capability(**parameters), result=True)
            if entry:
                self.show_result(entry)

    def tolerance_intervals_dialog(self):
        from .tolerance_intervals_dialogs import ToleranceIntervalsDialog
        self._commit_editor()
        self._last_dialog_action = self.tolerance_intervals_dialog
        dlg = ToleranceIntervalsDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = dlg.result_params
            if p:
                entry = self._call(
                    lambda: self.presenter.tolerance_intervals(settings=p),
                    result=True,
                )
                if entry:
                    self.show_result(entry)

    def trend_analysis_dialog(self):
        from .time_series_dialogs import TrendAnalysisDialog
        self._commit_editor()
        self._last_dialog_action = self.trend_analysis_dialog
        dlg = TrendAnalysisDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.trend_analysis(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def decomposition_dialog(self):
        from .time_series_dialogs import DecompositionDialog
        self._commit_editor()
        self._last_dialog_action = self.decomposition_dialog
        dlg = DecompositionDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.decomposition(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def moving_average_dialog(self):
        from .time_series_dialogs import MovingAverageDialog
        self._commit_editor()
        self._last_dialog_action = self.moving_average_dialog
        dlg = MovingAverageDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.moving_average(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def single_exp_smoothing_dialog(self):
        from .time_series_dialogs import SingleExpSmoothingDialog
        self._commit_editor()
        self._last_dialog_action = self.single_exp_smoothing_dialog
        dlg = SingleExpSmoothingDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.single_exp_smoothing(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def double_exp_smoothing_dialog(self):
        from .time_series_dialogs import DoubleExpSmoothingDialog
        self._commit_editor()
        self._last_dialog_action = self.double_exp_smoothing_dialog
        dlg = DoubleExpSmoothingDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.double_exp_smoothing(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def autocorrelation_dialog(self):
        from .time_series_dialogs import AutocorrelationDialog
        self._commit_editor()
        self._last_dialog_action = self.autocorrelation_dialog
        dlg = AutocorrelationDialog(self.presenter.worksheet, is_partial=False, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.autocorrelation(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def cross_correlation_dialog(self):
        from .variable_dialogs import ProcedureDialog
        self._commit_editor()
        self._last_dialog_action = self.cross_correlation_dialog
        selectors = [
            dict(key="first_index", label="First series:", kinds=("number",)),
            dict(key="second_index", label="Second series:", kinds=("number",)),
        ]
        fields = [
            dict(key="lags", label="Number of lags:", numeric=True, integer=True,
                 optional=True, placeholder="Default number of lags"),
            dict(key="store_ccf", label="Storage:", boolean=True, text="Store CCF"),
            dict(key="title", label="Title:", optional=True, placeholder="Default chart title"),
        ]
        dialog = ProcedureDialog(self, "Cross Correlation", self.presenter.worksheet, selectors, fields,
                                 "Compare two regularly spaced series. Positive lags pair the first series with later values of the second.")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.parameters
            settings["lags"] = settings["lags"] or 0
            self._call(lambda: self.presenter.cross_correlation(**settings), result=True)

    def partial_autocorrelation_dialog(self):
        from .time_series_dialogs import AutocorrelationDialog
        self._commit_editor()
        self._last_dialog_action = self.partial_autocorrelation_dialog
        dlg = AutocorrelationDialog(self.presenter.worksheet, is_partial=True, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.partial_autocorrelation(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def differences_dialog(self):
        from .time_series_dialogs import DifferencesDialog
        self._commit_editor()
        self._last_dialog_action = self.differences_dialog
        dlg = DifferencesDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.differences(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def lag_dialog(self):
        from .time_series_dialogs import LagDialog
        self._commit_editor()
        self._last_dialog_action = self.lag_dialog
        dlg = LagDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.lag(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def sign_test_dialog(self):
        from .nonparametrics_dialogs import SignTestDialog
        self._commit_editor()
        self._last_dialog_action = self.sign_test_dialog
        dlg = SignTestDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.sign_test(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def one_sample_wilcoxon_dialog(self):
        from .nonparametrics_dialogs import OneSampleWilcoxonDialog
        self._commit_editor()
        self._last_dialog_action = self.one_sample_wilcoxon_dialog
        dlg = OneSampleWilcoxonDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.one_sample_wilcoxon(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def mann_whitney_dialog(self):
        from .nonparametrics_dialogs import MannWhitneyDialog
        self._commit_editor()
        self._last_dialog_action = self.mann_whitney_dialog
        dlg = MannWhitneyDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.mann_whitney(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def kruskal_wallis_dialog(self):
        from .nonparametrics_dialogs import KruskalWallisDialog
        self._commit_editor()
        self._last_dialog_action = self.kruskal_wallis_dialog
        dlg = KruskalWallisDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.kruskal_wallis(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def moods_median_dialog(self):
        from .nonparametrics_dialogs import MoodsMedianDialog
        self._commit_editor()
        self._last_dialog_action = self.moods_median_dialog
        dlg = MoodsMedianDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.moods_median(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def friedman_dialog(self):
        from .nonparametrics_dialogs import FriedmanDialog
        self._commit_editor()
        self._last_dialog_action = self.friedman_dialog
        dlg = FriedmanDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.friedman_test(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def runs_test_dialog(self):
        from .nonparametrics_dialogs import RunsTestDialog
        self._commit_editor()
        self._last_dialog_action = self.runs_test_dialog
        dlg = RunsTestDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.runs_test(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def paired_wilcoxon_dialog(self):
        from .nonparametrics_dialogs import PairedWilcoxonDialog
        self._commit_editor()
        self._last_dialog_action = self.paired_wilcoxon_dialog
        dlg = PairedWilcoxonDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.paired_wilcoxon(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def pca_dialog(self):
        from .multivariate_dialogs import PcaDialog
        self._commit_editor()
        self._last_dialog_action = self.pca_dialog
        dlg = PcaDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.pca(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def item_analysis_dialog(self):
        from .multivariate_dialogs import ItemAnalysisDialog
        self._commit_editor()
        self._last_dialog_action = self.item_analysis_dialog
        dlg = ItemAnalysisDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.item_analysis(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def cluster_observations_dialog(self):
        from .multivariate_dialogs import ClusterObservationsDialog
        self._commit_editor()
        self._last_dialog_action = self.cluster_observations_dialog
        dlg = ClusterObservationsDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.cluster_observations(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def cluster_kmeans_dialog(self):
        from .multivariate_dialogs import ClusterKMeansDialog
        self._commit_editor()
        self._last_dialog_action = self.cluster_kmeans_dialog
        dlg = ClusterKMeansDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.cluster_kmeans(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def cluster_variables_dialog(self):
        from .multivariate_dialogs import ClusterVariablesDialog
        self._commit_editor()
        self._last_dialog_action = self.cluster_variables_dialog
        dlg = ClusterVariablesDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.cluster_variables(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def discriminant_analysis_dialog(self):
        from .multivariate_dialogs import DiscriminantAnalysisDialog
        self._commit_editor()
        self._last_dialog_action = self.discriminant_analysis_dialog
        dlg = DiscriminantAnalysisDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.discriminant_analysis(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def simple_correspondence_dialog(self):
        from .multivariate_dialogs import SimpleCorrespondenceDialog
        self._commit_editor()
        self._last_dialog_action = self.simple_correspondence_dialog
        dlg = SimpleCorrespondenceDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.simple_correspondence(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def one_sample_equivalence_dialog(self):
        from .equivalence_dialogs import OneSampleEquivalenceDialog
        self._commit_editor()
        self._last_dialog_action = self.one_sample_equivalence_dialog
        dlg = OneSampleEquivalenceDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.one_sample_equivalence(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def two_sample_equivalence_dialog(self):
        from .equivalence_dialogs import TwoSampleEquivalenceDialog
        self._commit_editor()
        self._last_dialog_action = self.two_sample_equivalence_dialog
        dlg = TwoSampleEquivalenceDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.two_sample_equivalence(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def paired_equivalence_dialog(self):
        from .equivalence_dialogs import PairedEquivalenceDialog
        self._commit_editor()
        self._last_dialog_action = self.paired_equivalence_dialog
        dlg = PairedEquivalenceDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.paired_equivalence(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def crossover_equivalence_dialog(self):
        from .equivalence_dialogs import CrossoverEquivalenceDialog
        self._commit_editor()
        self._last_dialog_action = self.crossover_equivalence_dialog
        dlg = CrossoverEquivalenceDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.crossover_equivalence(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def one_sample_z_power_dialog(self):
        from .power_dialogs import OneSampleZPowerDialog
        self._commit_editor()
        self._last_dialog_action = self.one_sample_z_power_dialog
        dlg = OneSampleZPowerDialog(parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.one_sample_z_power(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def one_sample_t_power_dialog(self):
        from .power_dialogs import OneSampleTPowerDialog
        self._commit_editor()
        self._last_dialog_action = self.one_sample_t_power_dialog
        dlg = OneSampleTPowerDialog(parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.one_sample_t_power(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def two_sample_t_power_dialog(self):
        from .power_dialogs import TwoSampleTPowerDialog
        self._commit_editor()
        self._last_dialog_action = self.two_sample_t_power_dialog
        dlg = TwoSampleTPowerDialog(parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.two_sample_t_power(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def paired_t_power_dialog(self):
        from .power_dialogs import PairedTPowerDialog
        self._commit_editor()
        self._last_dialog_action = self.paired_t_power_dialog
        dlg = PairedTPowerDialog(parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.paired_t_power(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def one_proportion_power_dialog(self):
        from .power_dialogs import OneProportionPowerDialog
        self._commit_editor()
        self._last_dialog_action = self.one_proportion_power_dialog
        dlg = OneProportionPowerDialog(parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.one_proportion_power(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def two_proportions_power_dialog(self):
        from .power_dialogs import TwoProportionsPowerDialog
        self._commit_editor()
        self._last_dialog_action = self.two_proportions_power_dialog
        dlg = TwoProportionsPowerDialog(parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.two_proportions_power(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def oneway_anova_power_dialog(self):
        from .power_dialogs import OneWayAnovaPowerDialog
        self._commit_editor()
        self._last_dialog_action = self.oneway_anova_power_dialog
        dlg = OneWayAnovaPowerDialog(parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.oneway_anova_power(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def factorial_power_dialog(self):
        from .power_dialogs import FactorialPowerDialog
        self._commit_editor()
        self._last_dialog_action = self.factorial_power_dialog
        dlg = FactorialPowerDialog(parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.factorial_power(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def cross_tabulation_dialog(self):
        from .tables_dialogs import CrossTabulationDialog
        self._commit_editor()
        self._last_dialog_action = self.cross_tabulation_dialog
        dlg = CrossTabulationDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.cross_tabulation(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def chi_square_goodness_of_fit_dialog(self):
        from .tables_dialogs import ChiSquareGoodnessOfFitDialog
        self._commit_editor()
        self._last_dialog_action = self.chi_square_goodness_of_fit_dialog
        dlg = ChiSquareGoodnessOfFitDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.chi_square_goodness_of_fit(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def chi_square_association_dialog(self):
        from .tables_dialogs import ChiSquareAssociationDialog
        self._commit_editor()
        self._last_dialog_action = self.chi_square_association_dialog
        dlg = ChiSquareAssociationDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.chi_square_association_table(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def tally_dialog(self):
        from .tables_dialogs import TallyDialog
        self._commit_editor()
        self._last_dialog_action = self.tally_dialog
        dlg = TallyDialog(self.presenter.worksheet, parent=self)
        if dlg.exec():
            p = getattr(dlg, "settings", None)
            if p:
                entry = self._call(lambda: self.presenter.tally_variables(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def xbar_r_dialog(self):
        from .subgroup_control_dialogs import XbarRChartDialog
        XbarRChartDialog(self).exec()

    def xbar_s_dialog(self):
        from .subgroup_control_dialogs import XbarSChartDialog
        XbarSChartDialog(self).exec()

    def xbar_r(self, stacked):
        selectors = [selector("response_index", "Measurements"), selector("factor_index", "Subgroup IDs", kinds=("number", "text"))] if stacked else [selector("indices", "Measurements within each subgroup", True, 2, 10)]
        action = self.presenter.xbar_r_stacked if stacked else self.presenter.xbar_r_rows
        self._dialog("Xbar-R Chart", selectors, [], lambda p: action(**p), "Subgroup sizes 2–10. Use separate columns for each measurement, or a measurement column with subgroup IDs.")

    def fit_binary_logistic(self):
        from .logistic_dialogs import BinaryLogisticDialog
        BinaryLogisticDialog(self).exec()

    def predict_model(self,family=None):
        from .prediction_dialogs import PredictDialog
        PredictDialog(self,family).exec()

    def optimize_responses(self,family=None):
        from .optimizer_dialogs import ResponseOptimizerDialog
        ResponseOptimizerDialog(self,family).exec()

    def prediction_profiler(self, family=None):
        from .native_mpx_models import resolve_entry_recipe
        from .prediction import normalize_recipe
        from .prediction_profiler_dialog import PredictionProfilerDialog
        recipes = []
        for entry in self.presenter.history:
            if entry.get('source_unavailable'): continue
            try:
                recipe = resolve_entry_recipe(entry, self.presenter.worksheet)
                if not recipe: continue
                if recipe.get('action') == 'predict_model': recipe = recipe['parameters']['model_recipe']
                recipe = normalize_recipe(recipe)
                if self.presenter.result_worksheet(entry) is not self.presenter.worksheet: continue
                if not any(r == recipe for r in recipes):
                    recipes.append(recipe)
            except Exception:
                continue

        if not recipes:
            QMessageBox.information(self, "Prediction Profiler", "Fit a supported regression, factorial, or response surface model before opening the Prediction Profiler.")
            return

        dialog = PredictionProfilerDialog(self, self.presenter.worksheet, recipes)
        dialog.exec()

    def factorial_plots(self,family=None):
        from .model_plot_dialogs import FactorialPlotsDialog
        self._commit_editor();FactorialPlotsDialog(self,family).exec()

    def model_contour_plot(self,family=None):
        from .model_plot_dialogs import ModelContourPlotDialog
        self._commit_editor();ModelContourPlotDialog(self,family).exec()

    def model_surface_plot(self,family=None):
        from .model_plot_dialogs import ModelSurfacePlotDialog
        self._commit_editor();ModelSurfacePlotDialog(self,family).exec()

    def gage_rr(self):
        from .gage_rr_dialogs import GageRRDialog
        GageRRDialog(self).exec()

    def capability(self):
        from .capability_dialogs import CapabilityDialog
        self._commit_editor()
        self._last_dialog_action = self.capability
        dlg = CapabilityDialog(self.presenter.worksheet, self, analysis_mode="normal")
        if dlg.exec():
            p = dlg.selected_params
            if p:
                entry = self._call(lambda: self.presenter.normal_capability(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def capability_between_within(self):
        from .capability_dialogs import CapabilityDialog
        self._commit_editor()
        self._last_dialog_action = self.capability_between_within
        dlg = CapabilityDialog(self.presenter.worksheet, self, analysis_mode="between_within")
        if dlg.exec():
            p = dlg.selected_params
            if p:
                entry = self._call(lambda: self.presenter.normal_capability(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def capability_machine(self):
        from .capability_dialogs import CapabilityDialog
        self._commit_editor()
        self._last_dialog_action = self.capability_machine
        dlg = CapabilityDialog(self.presenter.worksheet, self, analysis_mode="normal", study_type="machine", naming_convention="aiag_vda")
        if dlg.exec():
            p = dlg.selected_params
            if p:
                entry = self._call(lambda: self.presenter.normal_capability(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def capability_nonparametric_dialog(self):
        from .capability_automated_dialogs import CapabilityNonparametricDialog
        self._commit_editor()
        self._last_dialog_action = self.capability_nonparametric_dialog
        dlg = CapabilityNonparametricDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.selected_params
            if p:
                entry = self._call(lambda: self.presenter.capability_nonparametric(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def nested_gage_rr_dialog(self):
        from .msa_dialogs import GageRRNestedDialog
        self._commit_editor()
        self._last_dialog_action = self.nested_gage_rr_dialog
        dlg = GageRRNestedDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.selected_params
            if p:
                entry = self._call(lambda: self.presenter.nested_gage_rr(**p), result=True)
                if entry:
                    self.show_result(entry)

    def gage_linearity_dialog(self):
        from .msa_dialogs import GageLinearityDialog
        self._commit_editor()
        self._last_dialog_action = self.gage_linearity_dialog
        dlg = GageLinearityDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.selected_params
            if p:
                entry = self._call(lambda: self.presenter.gage_linearity(**p), result=True)
                if entry:
                    self.show_result(entry)

    def attribute_agreement_dialog(self):
        from .msa_dialogs import AttributeAgreementDialog
        self._commit_editor()
        self._last_dialog_action = self.attribute_agreement_dialog
        dlg = AttributeAgreementDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.selected_params
            if p:
                entry = self._call(lambda: self.presenter.attribute_agreement(**p), result=True)
                if entry:
                    self.show_result(entry)

    def capability_automated_dialog(self):
        from .capability_automated_dialogs import CapabilityAutomatedDialog
        self._commit_editor()
        self._last_dialog_action = self.capability_automated_dialog
        dlg = CapabilityAutomatedDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.selected_params
            if p:
                entry = self._call(lambda: self.presenter.capability_automated(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def reliability_distribution_dialog(self):
        from .reliability_dialogs import ReliabilityDistributionDialog
        self._commit_editor()
        self._last_dialog_action = self.reliability_distribution_dialog
        dlg = ReliabilityDistributionDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.selected_params
            if p:
                entry = self._call(lambda: self.presenter.reliability_distribution(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def multiple_capability_dialog(self, method='normal'):
        from .multiple_capability_dialogs import MultipleCapabilityDialog
        self._commit_editor()
        self._last_dialog_action = lambda: self.multiple_capability_dialog(method)
        dialog = MultipleCapabilityDialog(self.presenter.worksheet, method, self)
        if dialog.exec():
            entry = self._call(lambda: self.presenter.multiple_capability(**dialog.parameters), result=True)
            if entry:
                self.show_result(entry)

    def capability_nonnormal_dialog(self):
        from .capability_nonnormal_dialogs import CapabilityNonnormalDialog
        self._commit_editor()
        self._last_dialog_action = self.capability_nonnormal_dialog
        dlg = CapabilityNonnormalDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.selected_params
            if p:
                entry = self._call(lambda: self.presenter.capability_nonnormal(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def acceptance_control_chart_dialog(self):
        from .acceptance_dialogs import AcceptanceControlChartDialog
        self._commit_editor()
        self._last_dialog_action = self.acceptance_control_chart_dialog
        dlg = AcceptanceControlChartDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.selected_params
            if p:
                entry = self._call(lambda: self.presenter.acceptance_control_chart(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def capability_sixpack(self):
        from .sixpack_dialogs import CapabilitySixpackDialog
        self._commit_editor()
        self._last_dialog_action = self.capability_sixpack
        dlg = CapabilitySixpackDialog(self.presenter.worksheet, self)
        if dlg.exec():
            p = dlg.selected_params
            if p:
                entry = self._call(lambda: self.presenter.normal_sixpack(settings=p), result=True)
                if entry:
                    self.show_result(entry)

    def multivari_dialog(self):
        self._commit_editor()
        from .multivari_dialogs import MultiVariDialog
        from PySide6.QtWidgets import QDialog
        dlg = MultiVariDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        s = dlg.get_settings()
        self._call(lambda: self.presenter.multivari(s['response_index'], s['factor_indices']), result=True)

    def outlier_test_dialog(self):
        self._commit_editor()
        from .outlier_test_dialogs import OutlierTestDialog
        from PySide6.QtWidgets import QDialog
        dlg = OutlierTestDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        s = dlg.get_settings()
        self._call(lambda: self.presenter.outlier_test(s['variable_index'], s['alpha'], s['alternative']), result=True)

    def standardize_dialog(self):
        self._commit_editor()
        from .standardize_dialogs import StandardizeDialog
        from PySide6.QtWidgets import QDialog
        dlg = StandardizeDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        s = dlg.get_settings()
        self._call(lambda: self.presenter.standardize(s['source_indices'], s['target_indices'], s['method']), result=False)

    def graphical_summary_dialog(self):
        self._commit_editor()
        from .graphical_summary_dialogs import GraphicalSummaryDialog
        from PySide6.QtWidgets import QDialog
        dlg = GraphicalSummaryDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dlg.get_settings()
        for v in settings.get('variables', []):
            self._call(lambda idx=v, conf=settings['confidence']: self.presenter.graphical_summary(idx, conf), result=True)

    def run_chart_dialog(self):
        self._commit_editor()
        from .run_chart_dialogs import RunChartDialog
        from PySide6.QtWidgets import QDialog
        dlg = RunChartDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dlg.get_settings()
        self._call(lambda: self.presenter.run_chart(settings['variable'], settings['subgroup_size']), result=True)

    def patterned_numbers_dialog(self):
        self._commit_editor()
        from .calc_data_dialogs import PatternedNumbersDialog
        from PySide6.QtWidgets import QDialog
        dlg = PatternedNumbersDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        s = dlg.get_settings()
        self._call(lambda: self.presenter.make_patterned_data(s['target_col'], s['from_val'], s['to_val'], s['step'], s['repeat_each'], s['repeat_sequence']), result=False)

    def patterned_arbitrary_dialog(self):
        self._commit_editor()
        from .calc_data_dialogs import PatternedArbitraryDialog
        from PySide6.QtWidgets import QDialog
        dlg = PatternedArbitraryDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        s = dlg.get_settings()
        self._call(lambda: self.presenter.make_patterned_arbitrary(s['target_col'], s['numbers'], s['repeat_each'], s['repeat_sequence']), result=False)

    def patterned_text_dialog(self):
        self._commit_editor()
        from .calc_data_dialogs import PatternedTextDialog
        from PySide6.QtWidgets import QDialog
        dlg = PatternedTextDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        s = dlg.get_settings()
        self._call(lambda: self.presenter.make_patterned_text_data(s['target_col'], s['items'], s['repeat_each'], s['repeat_sequence']), result=False)

    def patterned_datetime_dialog(self):
        self._commit_editor()
        from .calc_data_dialogs import PatternedDateTimeDialog
        from PySide6.QtWidgets import QDialog
        dlg = PatternedDateTimeDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        s = dlg.get_settings()
        self._call(lambda: self.presenter.make_patterned_datetime_data(
            s['target_col'], s['start_dt'], s.get('end_dt'), s.get('count'),
            s.get('step', 1), s.get('unit', 'days'), s.get('repeat_each', 1),
            s.get('repeat_sequence', 1), s.get('dt_format', '%Y-%m-%d')
        ), result=False)

    def random_normal_dialog(self):
        self._commit_editor()
        from .calc_data_dialogs import RandomNormalDialog
        from PySide6.QtWidgets import QDialog
        dlg = RandomNormalDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        s = dlg.get_settings()
        self._call(lambda: self.presenter.generate_random_data(s['target_col'], 'normal', s.get('n', 50), s['mean'], s['stdev']), result=False)

    def random_uniform_dialog(self):
        self._commit_editor()
        from .calc_data_dialogs import RandomUniformDialog
        from PySide6.QtWidgets import QDialog
        dlg = RandomUniformDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        s = dlg.get_settings()
        self._call(lambda: self.presenter.generate_random_data(s['target_col'], 'uniform', s.get('n', 50), s['low'], s['high']), result=False)

    def random_exponential_dialog(self):
        self._commit_editor()
        from .calc_data_dialogs import RandomExponentialDialog
        from PySide6.QtWidgets import QDialog
        dlg = RandomExponentialDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        s = dlg.get_settings()
        self._call(lambda: self.presenter.generate_random_data(s['target_col'], 'exponential', s.get('n', 50), s['scale']), result=False)

    def random_poisson_dialog(self):
        self._commit_editor()
        from .calc_data_dialogs import RandomPoissonDialog
        from PySide6.QtWidgets import QDialog
        dlg = RandomPoissonDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        s = dlg.get_settings()
        self._call(lambda: self.presenter.generate_random_data(s['target_col'], 'poisson', s.get('n', 50), s['mean']), result=False)

    def random_binomial_dialog(self):
        self._commit_editor()
        from .calc_data_dialogs import RandomBinomialDialog
        from PySide6.QtWidgets import QDialog
        dlg = RandomBinomialDialog(self.presenter.worksheet, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        s = dlg.get_settings()
        self._call(lambda: self.presenter.generate_random_data(s['target_col'], 'binomial', s.get('n', 50), s['trials'], s['prob']), result=False)

    def calculator(self):
        self._dialog("Calculator", [], [{"key": "expression", "label": "Expression", "placeholder": "C1 + K1, SQRT(C1), C1 ^ 2"}, {"key": "destination", "label": "Store result", "default": "Calculated"}], lambda p: self.presenter.calculate(**p), "Columns: C1, C2…; stored numeric constants: K1, K2…. Destination: existing numeric column number or a name for a new column. Functions: ABS, SQRT, LOG, LOG10, EXP, SIN, COS, ROUND.")

    def probability(self):
        from . import probability
        dialog = QDialog(self); dialog.setWindowTitle("Probability Distributions"); dialog.setMinimumWidth(540)
        layout = QVBoxLayout(dialog); layout.addWidget(label("Probability Distributions", "dialogHeading"))
        form = QFormLayout(); distribution = QComboBox(); distribution.addItems(list(probability.PARAMETERS))
        operation = QComboBox(); operation.addItems(["CDF", "PDF/PMF", "Inverse CDF"])
        form.addRow("Distribution", distribution); form.addRow("Operation", operation)
        layout.addLayout(form); parameters_widget = QWidget(); parameters_layout = QFormLayout(parameters_widget); layout.addWidget(parameters_widget)
        parameter_edits = []
        def update_parameters():
            while parameters_layout.rowCount(): parameters_layout.removeRow(0)
            parameter_edits.clear()
            for title, default in zip(probability.PARAMETERS[distribution.currentText()], probability.DEFAULTS[distribution.currentText()]):
                edit = QLineEdit(str(default)); parameter_edits.append(edit); parameters_layout.addRow(title, edit)
        distribution.currentTextChanged.connect(lambda text: update_parameters()); update_parameters()
        input_form = QFormLayout(); input_label = label("Input value"); value = QLineEdit("0"); input_form.addRow(input_label, value); layout.addLayout(input_form)
        def update_operation(text): input_label.setText("Cumulative probability" if text == "Inverse CDF" else "Input value"); value.setText("0.5" if text == "Inverse CDF" else "0")
        operation.currentTextChanged.connect(update_operation)
        error = label("", "error"); layout.addWidget(error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel); layout.addWidget(buttons)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Calculate")
        def calculate():
            try:
                result = probability.calculate(distribution.currentText(), operation.currentText(), finite_number(float(value.text())), [finite_number(float(edit.text())) for edit in parameter_edits])
                entry = self.presenter._record(distribution.currentText() + " — " + operation.currentText(), result)
            except (ValueError, TypeError, ArithmeticError) as exc: error.setText(str(exc)); return
            dialog.accept(); self.refresh(); self.show_result(entry)
        buttons.accepted.connect(calculate); buttons.rejected.connect(dialog.reject); dialog.exec()

    def weibull_mean(self):
        self._dialog("Weibull Mean", [], [numeric("shape", "Shape", 2), numeric("scale", "Scale", 1), numeric("location", "Location", 0)], lambda p: self.presenter.weibull("mean", **p))

    def triangular(self):
        self._dialog("Packed Triangular Solve", [], [{"key": "packed", "label": "Packed upper triangle", "default": "2, 1, 3"}, {"key": "rhs", "label": "Right-hand side", "default": "5, 6"}, {"key": "transpose", "label": "Orientation", "boolean": True, "text": "Solve Uᵀ x = b"}], lambda p: self.presenter.solve(_number_list(p["packed"]), _number_list(p["rhs"]), p["transpose"]), "Upper triangle is stored by columns: U00, U01, U11, U02, U12, U22, …")

    def graph(self, method):
        if method in ('individual_value','interval_plot'):
            self._commit_editor()
            from .categorical_points_dialogs import CategoricalTypeDialog,CategoricalPlotDialog
            plot_type='individual' if method=='individual_value' else 'interval';chooser=CategoricalTypeDialog(plot_type,self)
            if chooser.exec()!=QDialog.DialogCode.Accepted:return
            dialog=CategoricalPlotDialog(self,self.presenter.worksheet,plot_type,chooser.mode)
            if dialog.exec()!=QDialog.DialogCode.Accepted:return
            def create():
                entry=self.presenter.categorical_points(**dialog.settings())
                from .graph_presentation import graph_presentation
                presentation=graph_presentation(entry);presentation.update(dialog.presentation_settings());entry['graph_presentation']=presentation
                return entry
            self._call(create,result=True);return
        if method=='dotplot':
            self._commit_editor()
            from .dotplot_dialogs import DotplotTypeDialog,DotplotDialog
            chooser=DotplotTypeDialog(self)
            if chooser.exec()!=QDialog.DialogCode.Accepted:return
            dialog=DotplotDialog(self,self.presenter.worksheet,chooser.mode)
            if dialog.exec()!=QDialog.DialogCode.Accepted:return
            def create():
                entry=self.presenter.dotplot_graphs(**dialog.settings())
                from .graph_presentation import graph_presentation
                presentation=graph_presentation(entry);presentation.update(dialog.presentation_settings());entry['graph_presentation']=presentation
                return entry
            self._call(create,result=True);return
        if method=='boxplot':
            self._commit_editor()
            from .boxplot_dialogs import BoxplotTypeDialog,BoxplotDialog
            chooser=BoxplotTypeDialog(self)
            if chooser.exec()!=QDialog.DialogCode.Accepted:return
            dialog=BoxplotDialog(self,self.presenter.worksheet,chooser.mode)
            if dialog.exec()!=QDialog.DialogCode.Accepted:return
            def create():
                entry=self.presenter.boxplot_graphs(**dialog.settings())
                from .graph_presentation import graph_presentation
                presentation=graph_presentation(entry);presentation.update(dialog.presentation_settings())
                entry['graph_presentation']=presentation;return entry
            self._call(create,result=True);return
        if method=='histogram':
            self._commit_editor()
            from .histogram_dialogs import HistogramTypeDialog,HistogramDialog
            chooser=HistogramTypeDialog(self)
            if chooser.exec()!=QDialog.DialogCode.Accepted:return
            dialog=HistogramDialog(self,self.presenter.worksheet,chooser.mode)
            if dialog.exec()!=QDialog.DialogCode.Accepted:return
            def create():
                entry=self.presenter.histogram_graphs(**dialog.settings())
                settings=dialog.presentation_settings()
                if settings:
                    from .graph_presentation import graph_presentation
                    presentation=graph_presentation(entry);presentation.update(settings)
                    entry['graph_presentation']=presentation
                return entry
            self._call(create,result=True);return
        if method == 'stem_leaf':
            self._commit_editor()
            from .stem_leaf_dialogs import StemLeafDialog
            dialog = StemLeafDialog(self.presenter.worksheet, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            s = dialog.get_settings()
            self._call(lambda: self.presenter.stem_and_leaf(s['index']), result=True)
            return
        if method == 'builder':
            self._commit_editor()
            from .graph_builder_dialog import GraphBuilderDialog
            dialog=GraphBuilderDialog(self,self.presenter.worksheet)
            if dialog.exec()==QDialog.DialogCode.Accepted:self._call(lambda:self.presenter.graph_builder(**dialog.settings()),result=True)
            return
        if method not in ('scatter', 'histogram', 'boxplot'):
            self.expanded_graph_dialog(method); return
        if method == "scatter":
            self._commit_editor()
            chooser = ScatterTypeDialog(self)
            if chooser.exec() != QDialog.DialogCode.Accepted: return
            dialog = ScatterDialog(self, self.presenter.worksheet, chooser.mode)
            if dialog.exec() != QDialog.DialogCode.Accepted: return
            for y, x in dialog.pairs:
                self._call(lambda x=x, y=y: self.presenter.scatter_plot(x, y, **dialog.settings), result=True)
            return
        fields = [numeric("bins", "Equal-width bins", 10, integer=True)] if method == "histogram" else []
        columns = [selector("indices", "X then Y" if method == "scatter" else "Variable", True, 2 if method == "scatter" else 1, 2 if method == "scatter" else 1)]
        def run(parameters):
            from .recipes import run
            return run(self.presenter, {"action": "graph", "parameters": {"method": method, "indices": parameters["indices"], "bins": parameters.get("bins", 1)}})
        self._dialog(method.title(), columns, fields, run, "Missing values are omitted. Scatterplots preserve complete worksheet-row pairs.")

    def expanded_graph_dialog(self, method):
        from .expanded_graphs import METHODS
        spec = METHODS[method]; selectors = []; fields = []; keys = []
        if len(spec['roles']) > 1:
            keys = ['variable' + str(i) for i in range(len(spec['roles']))]
            order = ([2, 1, 0] if len(keys) == 3 and method != 'bubble' else [1, 0, 2] if len(keys) == 3 else [1, 0])
            for i in order: selectors.append(selector(keys[i], spec['roles'][i]))
        elif spec['maximum']:
            title = 'Variables'
            if method in ('line_plot', 'area_graph'): title = 'Y variable, or X then Y'
            if method == 'time_series': title = 'Responses, or date axis then responses'
            selectors.append(selector('indices', title, True, spec['minimum'], spec['maximum'], kinds=tuple(spec['kinds'])))
        if spec['group_allowed']: selectors.append(selector('groups', 'By variable (optional)', True, 0, 1, kinds=('number', 'text')))
        if method in ('binned_scatter', 'marginal', 'matrix_plot'): fields.append(numeric('bins', 'Bins', 10, integer=True))
        if method == 'interval_plot': fields.append(numeric('confidence', 'Confidence level', .95))
        if method == 'distribution_plot':
            fields = [{'key': 'distribution', 'label': 'Distribution', 'choices': ['Normal', 'Uniform', 'Exponential']},
                numeric('mean', 'Mean (Normal)', 0), numeric('stdev', 'Standard deviation (Normal)', 1),
                numeric('lower', 'Lower bound (Uniform)', 0), numeric('upper', 'Upper bound (Uniform)', 1), numeric('rate', 'Rate (Exponential)', 1)]
        note = ''
        if method in ('contour', 'surface3d'): note = 'Select X/Y/Z on a complete rectangular grid, with one observation per coordinate. Interpolation is not implemented.'
        elif method == 'probability_plot': note = 'Normal probability plot with Blom plotting positions; native confidence bands are not implemented.'
        elif method in ('bar_chart', 'pie_chart'): note = 'Counts of nonmissing category values in one numeric or text column.'
        elif method == 'interval_plot': note = 'Separate Student t confidence intervals for group means; no pooled variance or multiplicity adjustment.'
        elif method == 'time_series': note = 'Numeric responses in worksheet order, optionally preceded by a date column. No forecasting or gap filling.'
        def calculate(values):
            indices = [values[key] for key in keys] if keys else values.get('indices', [])
            groups = values.get('groups', [])
            distribution = values.get('distribution', 'Normal'); parameters = {}
            if method == 'distribution_plot':
                names = {'Normal': ['mean', 'stdev'], 'Uniform': ['lower', 'upper'], 'Exponential': ['rate']}[distribution]
                parameters = {name: values[name] for name in names}
            return self.presenter.expanded_graph(method, indices, groups[0] if groups else None,
                bins=values.get('bins', 10), confidence=values.get('confidence', .95), distribution=distribution, parameters=parameters)
        self._dialog(spec['label'], selectors, fields, calculate, note)

    def _clear_result_tabs(self):
        self._active_graph_frame=None;self._active_chart_widget=None
        while self.result_tabs.count():
            page = self.result_tabs.widget(0); self.result_tabs.removeTab(0)
            if page is getattr(self,"_report_pad_editor",None):page.setParent(self);page.hide()
            else:page.deleteLater()

    def _show_welcome(self):
        if hasattr(self,"_workspace"):self._workspace.sync_document()
        self.selected_entry=None
        if hasattr(self,'graph_options_pane'):
            self.graph_options_pane.load_entry(None);self.graph_options_pane.hide()
        self._clear_result_tabs()
        self.output_header_bar.setVisible(False)
        self.result_tabs.tabBar().setVisible(False)
        if hasattr(self, "tab_corner_widget"):
            self.tab_corner_widget.setVisible(False)
        welcome = WelcomeWatermarkWidget(self.open_document, self.new_document, self.new_worksheet, on_try_connect=self.load_connect_sample, on_overview=self.show_connect_overview)
        self.result_tabs.addTab(welcome, "Session")
        if hasattr(self,"_workspace"):self._workspace.rebuild()
        self.result_title.setText("Session output")
        self.result_state.setText("")
        self.rerun_button.setEnabled(False)

    def _update_result_state(self):
        if self.selected_entry is None: return
        stale = self.presenter.result_stale(self.selected_entry)
        state = "Outdated result — worksheet inputs changed. Rerun to update." if stale is True else "Current result — source inputs match." if stale is False else "Retained snapshot — source input tracking is unavailable."
        self.result_state.setText(state + "  ·  " + self.selected_entry.get("worksheet_name", "") + "  ·  " + self.selected_entry.get("time", ""))
        self.rerun_button.setEnabled(self.selected_entry.get("origin") == "statcraft" and "recipe" in self.selected_entry)

    def _result_table(self, headers, rows):
        import io, csv
        table = QTableWidget(len(rows), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        def _table_context_menu(pos):
            menu = QMenu(table)
            act_tsv = menu.addAction("Copy Table as TSV (Excel / JMP / Minitab)")
            act_csv = menu.addAction("Copy Table as CSV")
            menu.addSeparator()
            act_def = menu.addAction("More Output Actions…")
            action = menu.exec(table.viewport().mapToGlobal(pos))
            if action in (act_tsv, act_csv):
                delim = "\t" if action == act_tsv else ","
                buf = io.StringIO()
                writer = csv.writer(buf, delimiter=delim)
                writer.writerow(headers)
                for r in rows:
                    writer.writerow([display(v) for v in r])
                QGuiApplication.clipboard().setText(buf.getvalue())
                self.statusBar().showMessage(f"Table copied to clipboard ({'TSV' if delim == '\t' else 'CSV'})", 3500)
            elif action == act_def:
                self._show_output_context_menu(table.viewport().mapToGlobal(pos))

        table.customContextMenuRequested.connect(_table_context_menu)
        table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                gridline-color: #f1f5f9;
                background: #ffffff;
                alternate-background-color: #f8fafc;
                font-size: 11px;
            }
            QTableWidget::item { padding: 4px 8px; }
            QTableWidget::item:selected { background: #e0f2fe; color: #0f172a; }
            QHeaderView::section {
                background: #f8fafc;
                color: #334155;
                font-weight: 700;
                border: none;
                border-bottom: 1px solid #cbd5e1;
                padding: 5px 8px;
            }
        """)
        for row, values in enumerate(rows):
            for col, value in enumerate(values):
                item = QTableWidgetItem(display(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row, col, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setMinimumSectionSize(75)
        table.setMinimumHeight(min(300, max(78, 30 + len(rows) * 26)))
        table.setMaximumHeight(min(390, max(95, 40 + len(rows) * 26)))
        return table

    def show_result(self, entry, target_graph_index=None, target_tab=None):
        if self.graph_options_pane.bound_entry is not entry and not self.graph_options_pane.flush():return
        if target_graph_index is not None:
            self._selected_graph_index = target_graph_index
            self._selected_nav_kind = "graph"
        elif target_tab == "Report":
            self._selected_graph_index = None
            self._selected_nav_kind = "report"
        elif target_tab is not None:
            self._selected_graph_index = None
            self._selected_nav_kind = "table"
            self._selected_table_title = target_tab
        elif getattr(self, "selected_entry", None) is not entry:
            self._selected_graph_index = None
            self._selected_nav_kind = None
        self._workspace.before_show(entry)
        self.selected_entry = entry
        self.output_header_bar.setVisible(False)
        self.result_tabs.tabBar().setVisible(True)
        if hasattr(self, "tab_corner_widget"):
            self.tab_corner_widget.setVisible(True)
        self.result_title.setText(entry.get("title", "Result")); self._update_result_state(); self._clear_result_tabs()
        result = entry.get("result", {})
        from .output_zoom import OutputZoomView
        stage = QWidget(); stage.setObjectName("outputPane")
        stage.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        stage.customContextMenuRequested.connect(lambda pos: self._show_output_context_menu(stage.mapToGlobal(pos)))
        stage_layout = QVBoxLayout(stage); stage_layout.setContentsMargins(14, 12, 14, 14)
        content = QFrame(); content.setObjectName("resultCard")
        content.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        content.customContextMenuRequested.connect(lambda pos: self._show_output_context_menu(content.mapToGlobal(pos)))
        layout = QVBoxLayout(content); layout.setContentsMargins(18, 14, 18, 18); layout.setSpacing(11)
        badge_row = QHBoxLayout(); badge_row.setContentsMargins(0, 0, 0, 0)
        ws_badge = QLabel("WORKSHEET: " + (entry.get("worksheet_name") or self.presenter.worksheet.name).upper())
        ws_badge.setObjectName("worksheetBadge")
        badge_row.addWidget(ws_badge, 1)
        report_drop_btn = QToolButton(); report_drop_btn.setObjectName("outputDropdownBtn")
        report_drop_btn.setText("▾"); report_drop_btn.setToolTip("Output Options")
        report_drop_btn.clicked.connect(lambda: self._show_output_context_menu(report_drop_btn.mapToGlobal(report_drop_btn.rect().bottomLeft())))
        badge_row.addWidget(report_drop_btn)
        if entry.get('native_model',{}).get('supported'):
            refit=QToolButton();refit.setText('Refit in StatCraft');refit.setObjectName('nativeRefitModel')
            refit.setToolTip('Fit the saved model setup to the current source worksheet using StatCraft.')
            refit.clicked.connect(lambda checked=False,e=entry:self.refit_native_model(e));badge_row.addWidget(refit)
        layout.addLayout(badge_row)
        layout.addWidget(label(entry.get("title", "Result"), "pageHeading"))

        # --- Clean StatCraft Connect Header Action ---
        conn_dict = entry.get("connected_analysis")
        if not conn_dict:
            from .connect import create_connected_analysis_from_entry
            try:
                conn_obj = create_connected_analysis_from_entry(entry, self.presenter.worksheet)
                if conn_obj:
                    conn_dict = conn_obj.to_dict()
                    entry["connected_analysis"] = conn_dict
            except Exception:
                conn_dict = None

        if conn_dict:
            from .connect_hub import ConnectBridgeWidget
            bridge = ConnectBridgeWidget(self, entry, conn_dict)
            layout.addWidget(bridge)
        rendered = set()
        if result.get("analysis") == "cross_correlation":
            layout.addWidget(label("Cross Correlations", "sectionHeading"))
            layout.addWidget(label(f"Correlates {result['first_name']}(t) with {result['second_name']}(t+k).", "secondary"))
            layout.addWidget(self._result_table(["Lag", "CCF", "Pairs"], [
                [row["lag"], row["correlation"], row["pairs"]] for row in result["lags"]
            ]))
            if result.get("stored_column"):
                layout.addWidget(label(f"Stored in {result['stored_column']}.", "secondary"))
            rendered.update(result)
        if result.get('analysis') == 'native_saved_output':
            native_tables = result.get('tables', [])
            self._report_table_widgets = {}
            if native_tables:
                for t_idx, tbl in enumerate(native_tables):
                    t_title = tbl.get('title', '')
                    t_headers = tbl.get('headers', [])
                    t_rows = tbl.get('rows', [])
                    t_notes = tbl.get('footnotes', [])
                    heading_widget = None
                    if t_title:
                        heading_widget = label(t_title, 'sectionHeading')
                        layout.addWidget(heading_widget)
                    has_headers = any(bool(h.strip()) for h in t_headers)
                    anchor = heading_widget
                    if has_headers:
                        t_widget = self._result_table(t_headers, t_rows)
                        t_widget.resizeColumnsToContents()
                        t_widget.setMaximumWidth(min(1800, sum(t_widget.columnWidth(i) for i in range(t_widget.columnCount())) + 28))
                        if len(t_rows) <= 100:
                            t_widget.setFixedHeight(t_widget.horizontalHeader().height() + sum(t_widget.rowHeight(i) for i in range(t_widget.rowCount())) + 4)
                            t_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                        layout.addWidget(t_widget)
                        if anchor is None:
                            anchor = t_widget
                    else:
                        for row in t_rows:
                            eq_line = "  ".join(str(cell) for cell in row if str(cell).strip())
                            if eq_line:
                                eq_lbl = QLabel(eq_line)
                                eq_lbl.setFont(QFont('Segoe UI', 9.5))
                                eq_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                                eq_lbl.setWordWrap(True)
                                eq_lbl.setStyleSheet("padding: 2px 4px; background: #fafafa; border: 1px solid #e0e0e0; border-radius: 3px;")
                                layout.addWidget(eq_lbl)
                                if anchor is None:
                                    anchor = eq_lbl
                    for fn in t_notes:
                        fn_lbl = QLabel(fn)
                        fn_lbl.setFont(QFont('Segoe UI', 8.5))
                        fn_lbl.setStyleSheet("color: #666666; font-style: italic;")
                        fn_lbl.setWordWrap(True)
                        layout.addWidget(fn_lbl)
                    if anchor is not None:
                        if t_title:
                            self._report_table_widgets[t_title] = anchor
                            short_tbl_title = t_title.split(" (")[0] if " (" in t_title else t_title
                            self._report_table_widgets[short_tbl_title] = anchor
                        self._report_table_widgets[t_idx] = anchor
                rendered.update(result)
            else:
                session = QPlainTextEdit(); session.setReadOnly(True); session.setFont(QFont('Consolas', 9.5))
                session.setPlainText(format_entry(entry)); session.setMinimumHeight(420)
                layout.addWidget(session)
                rendered.update(result)
        elif result.get('analysis') in ('optimal_design', 'design_evaluation', 'cart_tree', 'evaluating_measurement_process', 'fit_y_by_x', 'jmp_distribution', 'control_chart_builder', 'process_screening', 'definitive_screening_analysis', 'accelerated_life_testing', 'mixture_process_model','mixture_process_prediction','mixture_multi_optimization','mixture_multi_evaluation','mixture_contour','mixture_optimization','mixture_prediction','mixture_model','taguchi_analysis','dynamic_taguchi_analysis','doe_plan', 'multiple_capability', 'capability_nonnormal', 'capability_nonparametric', 'capability_automated', 'reliability_distribution', 'nested_gage_rr', 'gage_linearity_and_bias', 'attribute_agreement_analysis'):
            session = QPlainTextEdit(); session.setReadOnly(True); session.setFont(QFont('Consolas', 9.5))
            session.setPlainText(result.get('session_text', format_entry(entry))); session.setMinimumHeight(320)
            layout.addWidget(session)
            rendered.update(result)
        if result.get('analysis') == 'definitive_screening_analysis':
            layout.addWidget(label('Regression Equation in Unstandardized Units', 'sectionHeading'))
            eq_box = QPlainTextEdit(); eq_box.setReadOnly(True); eq_box.setFont(QFont('Consolas', 10))
            eq_box.setPlainText(result.get('equation', '')); eq_box.setMaximumHeight(55)
            layout.addWidget(eq_box)

            ms_data = [
                ['S', f"{result.get('s', 0.0):.4f}"],
                ['R-sq', f"{result.get('r2', 0.0)*100:.2f}%"],
                ['R-sq(adj)', f"{result.get('r2_adj', 0.0)*100:.2f}%"],
                ['R-sq(pred)', f"{result.get('r2_pred', 0.0)*100:.2f}%"]
            ]
            layout.addWidget(label('Model Summary', 'sectionHeading'))
            layout.addWidget(self._result_table(['Measure', 'Value'], ms_data))

            coef_headers = ['Term', 'Coef', 'SE Coef', f"{result.get('confidence', 95):g}% CI", 'T-Value', 'P-Value', 'VIF']
            coef_rows = []
            for tr in result.get('terms', []):
                coef_rows.append([
                    tr.get('term', ''),
                    f"{tr.get('coef', 0.0):.4f}",
                    f"{tr.get('se', 0.0):.4f}",
                    f"({tr.get('ci_lower', 0.0):.4f}, {tr.get('ci_upper', 0.0):.4f})",
                    f"{tr.get('t_val', 0.0):.2f}",
                    f"{tr.get('p_val', 0.0):.4f}",
                    f"{tr.get('vif', 1.0):.2f}"
                ])
            layout.addWidget(label('Coded Coefficients', 'sectionHeading'))
            layout.addWidget(self._result_table(coef_headers, coef_rows))

            anova_headers = ['Source', 'DF', 'Adj SS', 'Adj MS', 'F-Value', 'P-Value']
            anova_rows = []
            for ar in result.get('anova', []):
                f_s = f"{ar.get('f_val'):.2f}" if ar.get('f_val') is not None else ""
                p_s = f"{ar.get('p_val'):.4f}" if ar.get('p_val') is not None else ""
                ms_s = f"{ar.get('adj_ms'):.4f}" if ar.get('adj_ms') is not None else ""
                anova_rows.append([
                    ar.get('source', ''),
                    str(ar.get('df', '')),
                    f"{ar.get('adj_ss', 0.0):.4f}",
                    ms_s,
                    f_s,
                    p_s
                ])
            layout.addWidget(label('Analysis of Variance', 'sectionHeading'))
            layout.addWidget(self._result_table(anova_headers, anova_rows))

        if result.get('analysis') in ('optimal_design', 'design_evaluation', 'cart_tree', 'accelerated_life_testing', 'evaluating_measurement_process', 'fit_y_by_x', 'jmp_distribution', 'control_chart_builder', 'process_screening') and result.get('tables'):
            for tbl in result['tables']:
                layout.addWidget(label(tbl['title'], 'sectionHeading'))
                layout.addWidget(self._result_table(tbl['headers'], tbl['rows']))
        if result.get('analysis') == 'attribute_capability':
            binomial = result['method'] == 'binomial'
            data = [['Count variable', result['count_name']], ['Sample size', result['size_name']],
                    ['Samples analyzed', result['n_samples']], ['Rows omitted', len(result['omitted_rows'])],
                    ['Total count', result['total_count']], ['Total sample size', result['total_size']]]
            layout.addWidget(label('Data', 'sectionHeading'))
            layout.addWidget(self._result_table(['Measure', 'Value'], data))
            if binomial:
                values = [['% Defective', result['percent_defective']], ['PPM Defective', result['ppm_defective']],
                          ['Process Z', result['process_z_label']], ['Target % Defective', result['target_percent']]]
                bounds = result['percent_ci']
            else:
                values = [['Mean defects per sample', result['mean_defects']], ['Mean DPU', result['mean_dpu']],
                          ['Minimum DPU', result['min_dpu']], ['Maximum DPU', result['max_dpu']],
                          ['Target DPU', result['target']]]
                bounds = result['rate_ci']
            values.append([f"{result['confidence']:g}% confidence interval", ' to '.join(display(value) for value in bounds)])
            if result['historical_rate'] is not None:
                values.append(['Historical p (proportion)' if binomial else 'Historical mean DPU', result['historical_rate']])
            values.append(['Points beyond 3-sigma limits', len(result['violations'])])
            layout.addWidget(label('Capability Statistics', 'sectionHeading'))
            layout.addWidget(self._result_table(['Measure', 'Value'], values))
            for note in result['notes']:
                text = QLabel(note); text.setWordWrap(True); layout.addWidget(text)
            rendered.update(result)
        if result.get('graph')=='categorical_points':
            rows=[[item['response_name'],item['group_label'] or '(all)',item['n'],item['mean'],item['median'],item['stdev'],item['standard_error'],item['df'],item['lower'],item['upper']] for panel in result['panels'] for item in panel['items']]
            layout.addWidget(label('Group Summaries','sectionHeading'));layout.addWidget(self._result_table(['Variable','Group','N','Mean','Median','StDev','SE Mean','DF','Lower','Upper'],rows))
        if result.get('graph')=='dotplot_graphs':
            rows=[[s['label'],panel['lanes'][s['lane']],len(s['source'])] for panel in result['panels'] for s in panel['series']]
            layout.addWidget(label('Dotplot Groups','sectionHeading'));layout.addWidget(self._result_table(['Series','Category','N'],rows))
        if result.get('graph')=='boxplot_graphs':
            rows=[[item['response_name'],item['group_label'] or '(all)',item['n'],item['box']['q1'],item['box']['median'],item['box']['q3'],item['mean'],len(item['box']['outliers'])] for panel in result['panels'] for item in panel['items']]
            layout.addWidget(label('Boxplot Groups','sectionHeading'));layout.addWidget(self._result_table(['Variable','Group','N','Q1','Median','Q3','Mean','Outliers'],rows))
        if result.get('graph')=='histogram_graphs':
            rows=[]
            for panel in result['panels']:
                for series in panel['series']:
                    fit=series.get('fit_parameters') or {}
                    rows.append([panel['xlabel'],series['label'] if panel['group_name'] else '(all)',series['n'],fit.get('mean'),fit.get('stdev')])
            layout.addWidget(label('Histogram Groups','sectionHeading'))
            layout.addWidget(self._result_table(['Variable','Group','N','Fit Mean','Fit StDev'],rows))
        tables = [
            ("columns", "Statistics"),
            ("coefficients", "Coefficients"),
            ("group_statistics", "Group Summaries"),
            ("correlations", "Pairwise Correlations"),
            ("samples", "Samples"),
            ("fits", "Fitted Lines"),
            ("effects", "Estimated Effects"),
            ("factor_coding", "Factor Coding"),
            ("alias_structure", "Alias Structure"),
            ("variables_table", "Worksheet Columns"),
            ("design_table", "Design Table"),
        ]
        if result.get('analysis') in ('factorial_plots','model_contour_plot','model_surface_plot','response_optimizer','binary_logistic','logistic_prediction','model_prediction','gage_rr','general_linear_model','response_surface','response_surface_design'):
            if result['analysis'] in ('factorial_plots','model_contour_plot','model_surface_plot'):
                from .model_plots_report import sections
            elif result['analysis']=='response_optimizer':
                from .optimizer_report import sections
            elif result['analysis']=='binary_logistic':
                from .logistic_report import sections
            elif result['analysis']=='logistic_prediction':
                from .logistic_report import prediction_sections as sections
            elif result['analysis']=='model_prediction':
                from .prediction_report import sections
            elif result['analysis']=='gage_rr':
                from .gage_rr_report import sections
            elif result['analysis']=='response_surface_design':
                from .response_surface_report import design_sections as sections
            elif result['analysis']=='response_surface':
                from .response_surface_report import sections
            else:
                from .glm_report import sections
            for heading,headers,rows in sections(result):
                layout.addWidget(label(heading,'sectionHeading'))
                table=self._result_table(headers,rows);table.resizeColumnsToContents()
                table.setMaximumWidth(min(1800,sum(table.columnWidth(i) for i in range(table.columnCount()))+28))
                if len(rows)<=100:
                    table.setFixedHeight(table.horizontalHeader().height()+sum(table.rowHeight(i) for i in range(table.rowCount()))+4)
                    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                layout.addWidget(table)
            rendered.update(result);tables=[]
        for key, title in tables:
            if key == 'factor_coding' and result.get('show_factor_coding') is False: continue
            records = result.get(key)
            if isinstance(records, list) and records and isinstance(records[0], dict):
                if key == "columns": keys = [k for k in ("name", "count", "missing", "mean", "standard_error", "sample_stdev", "minimum", "q1", "median", "q3", "maximum") if k in records[0]]
                elif key == "coefficients": keys = [k for k in ("name", "estimate", "standard_error", "t", "p_value", "ci_low", "ci_high", "vif") if k in records[0]]
                elif key == 'factor_coding': keys = [k for k in ('letter', 'name', 'low', 'center', 'high') if k in records[0]]
                else: keys = [k for k in records[0] if k != "warnings"]
                aliases = {"name": "Variable" if key == "columns" else "Term", "count": "N", "missing": "N*", "standard_error": "SE Mean" if key == "columns" else "SE Coef", "sample_stdev": "StDev", "p_value": "P-Value", "estimate": "Coef", "ci_low": "Lower CI", "ci_high": "Upper CI", "vif": "VIF", "q1": "Q1", "q3": "Q3"}
                layout.addWidget(label(title, "sectionHeading")); layout.addWidget(self._result_table([aliases.get(k, k.replace("_", " ").title()) for k in keys], [[row.get(k) for k in keys] for row in records]))
                rendered.add(key)
        excluded = {"observations", "moving_ranges", "subgroup_means", "subgroup_ranges", "counts", "sample_sizes", "exposures", "proportions", "rates", "lcl", "ucl", "graph_data", "fitted", "residuals", "row_indices", "used_rows", "missing_rows", 'coded_factors', 'selected_terms', 'native_parity', 'plot_residuals', 'show_factor_coding'}
        scalars = [(key.replace("_", " ").title(), value) for key, value in result.items() if key not in rendered | excluded | {"assumptions", "warnings", "parameters"} and not isinstance(value, (dict, list))]
        if scalars:
            layout.addWidget(label("Summary", "sectionHeading")); layout.addWidget(self._result_table(["Measure", "Value"], scalars))
        if isinstance(result.get("parameters"), dict):
            layout.addWidget(label("Parameters", "sectionHeading")); layout.addWidget(self._result_table(["Parameter", "Value"], list(result["parameters"].items())))
        for key in ("variables", "predictor_names", "i_signals", "mr_signals", "signals", "xbar_signals", "r_signals", "commands", "command"):
            value = result.get(key)
            if value is not None:
                text = display(value); note = QPlainTextEdit(); note.setReadOnly(True); note.setPlainText(key.replace("_", " ").title() + ": " + text)
                note.setMaximumHeight(130 if key in ("commands", "command") else 70); layout.addWidget(note)
        notes = []
        for key in ("assumptions", "warnings", "convention", "missing_policy"):
            value = result.get(key)
            if isinstance(value, list): notes.extend(str(item) for item in value)
            elif value: notes.append(str(value))
        if notes:
            layout.addWidget(label("Method Notes", "sectionHeading")); note = QPlainTextEdit(); note.setReadOnly(True); note.setPlainText("\n\n".join(notes)); note.setMinimumHeight(90); note.setMaximumHeight(210); layout.addWidget(note)
        layout.addStretch()
        stage_layout.addWidget(content); stage_layout.addStretch()
        scroll=OutputZoomView(stage); self.result_tabs.addTab(scroll, "Report")
        scroll.set_zoom(self._output_zoom_levels.get(self._zoom_key(),100))
        chosen_tab = 0
        native_tables = result.get('tables', []) if result.get('analysis') == 'native_saved_output' else []
        from .modern_charts import ChartWidget, supported
        if supported(entry):
            if result.get('analysis') == 'native_saved_output':
                from .native_output_chart import NativeOutputChart
                from .graph_frame import GraphFrame
                from .output_zoom import OutputZoomView
                native_graphs = result.get('graphs', []) or [{}]
                graph_tab_indices = []
                for g_idx, g in enumerate(native_graphs):
                    chart = NativeOutputChart(entry, graph_index=g_idx)
                    chart.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    chart.customContextMenuRequested.connect(lambda pos, c=chart: self._show_output_context_menu(c.mapToGlobal(pos)) if not (getattr(c, '_has_3d_panel', lambda: False)()) else None)
                    if g_idx == 0:
                        self._active_chart_widget = chart

                    graph_stage = QWidget(); graph_stage.setObjectName("outputPane")
                    graph_stage.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    graph_stage.customContextMenuRequested.connect(lambda pos: self._show_output_context_menu(graph_stage.mapToGlobal(pos)))
                    graph_stage_layout = QVBoxLayout(graph_stage); graph_stage_layout.setContentsMargins(8, 6, 8, 6); graph_stage_layout.setSpacing(6)
                    graph_card = QFrame(); graph_card.setObjectName("resultCard")
                    graph_card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    graph_card.customContextMenuRequested.connect(lambda pos: self._show_output_context_menu(graph_card.mapToGlobal(pos)))
                    graph_card_layout = QVBoxLayout(graph_card); graph_card_layout.setContentsMargins(8, 6, 8, 6); graph_card_layout.setSpacing(6)

                    graph_frame = GraphFrame(chart, entry)
                    graph_frame.export_hidden.extend(getattr(chart, "export_controls", []))
                    if g_idx == 0:
                        self._active_graph_frame = graph_frame

                    chart.graphSelected.connect(lambda index, e=entry, c=chart: self._native_graph_switched(e, c, index))
                    def _safe_update_camera(camera, e=entry, c=chart):
                        try:
                            safe_cam = {
                                'azimuth': max(-180.0, min(180.0, float(camera.get('azimuth', -35.0)))),
                                'elevation': max(-89.0, min(89.0, float(camera.get('elevation', 25.0)))),
                                'zoom': max(0.4, min(2.5, float(camera.get('zoom', 1.0)))),
                            }
                            if 'pan_x' in camera and isinstance(camera['pan_x'], (int, float)):
                                safe_cam['pan_x'] = float(camera['pan_x'])
                            if 'pan_y' in camera and isinstance(camera['pan_y'], (int, float)):
                                safe_cam['pan_y'] = float(camera['pan_y'])
                            self.presenter.update_native_graph_view(e, c.graph_index, {'camera': safe_cam})
                        except Exception:
                            pass
                    chart.cameraChanged.connect(_safe_update_camera)
                    if entry.get('native_model', {}).get('supported'):
                        refit = QToolButton(); refit.setText('Refit in StatCraft'); refit.setObjectName('nativeRefitModel')
                        refit.clicked.connect(lambda checked=False, e=entry: self.refit_native_model(e))
                        graph_frame.header.addWidget(refit); graph_frame.export_hidden.append(refit)
                    chart.objectSelected.connect(lambda target: self._graph_object_selected(target))
                    chart.objectActivated.connect(lambda target, e=entry: self._activate_graph_object(e, target))
                    chart.brushRowsSelected.connect(lambda rows, e=entry: self._receive_brushed_rows(e, rows))
                    graph_frame.annotationActivated.connect(lambda name, e=entry: self.edit_graph_annotation(e, name))
                    self._setup_graph_frame(graph_frame, chart, entry)

                    dropdown_btn = QToolButton(); dropdown_btn.setObjectName("outputDropdownBtn")
                    dropdown_btn.setText("▾")
                    dropdown_btn.setToolTip("Graph / Output Options")
                    dropdown_btn.clicked.connect(lambda b=dropdown_btn: self._show_output_context_menu(b.mapToGlobal(b.rect().bottomLeft())))
                    graph_frame.header.addWidget(dropdown_btn)
                    graph_frame.export_hidden.append(dropdown_btn)

                    graph_card_layout.addWidget(graph_frame, 1)
                    graph_stage_layout.addWidget(graph_card, 1)

                    graph_scroll = OutputZoomView(graph_stage)
                    g_title = g.get('title') or (f"Graph {g_idx + 1}" if len(native_graphs) > 1 else "Graph")
                    short_title = g_title.split(" for ")[0] if " for " in g_title else g_title
                    tab_idx = self.result_tabs.addTab(graph_scroll, short_title)
                    self.result_tabs.setTabToolTip(tab_idx, g_title)
                    graph_scroll.set_zoom(self._output_zoom_levels.get(self._zoom_key(), 100))
                    graph_tab_indices.append(tab_idx)

                has_tables = bool(native_tables)
                has_report_text = bool(result.get('text', '').strip())
                if target_graph_index is not None and 0 <= target_graph_index < len(graph_tab_indices):
                    chosen_tab = graph_tab_indices[target_graph_index]
                elif target_tab is not None and target_tab in getattr(self, '_report_table_widgets', {}):
                    chosen_tab = 0
                    try:
                        scroll.ensureWidgetVisible(self._report_table_widgets[target_tab], 0, 50)
                    except Exception:
                        pass
                elif target_tab == "Report":
                    chosen_tab = 0
                elif has_tables:
                    chosen_tab = 0
                elif graph_tab_indices:
                    chosen_tab = graph_tab_indices[0]
                elif has_report_text:
                    chosen_tab = 0
                else:
                    chosen_tab = 0
                self.result_tabs.setCurrentIndex(chosen_tab)
                self._sync_output_zoom()
            else:
                if result.get('analysis') in ('mixture_multi_optimization','mixture_multi_evaluation'):
                    from .mixture_multi_chart import MixtureMultiChart
                    chart=MixtureMultiChart(entry)
                    chart.settingSelected.connect(lambda values,e=entry:self._select_mixture_profile(e,values))
                elif result.get('analysis') == 'mixture_joint_optimization':
                    from .mixture_joint_chart import MixtureJointChart
                    chart=MixtureJointChart(entry)
                elif result.get('analysis') in ('mixture_contour','mixture_optimization'):
                    from .mixture_exploration_chart import MixtureExplorationChart
                    chart=MixtureExplorationChart(entry)
                elif result.get('analysis') == 'dynamic_taguchi_analysis':
                    from .dynamic_taguchi_chart import DynamicTaguchiWidget
                    chart=DynamicTaguchiWidget(entry)
                elif result.get('analysis') == 'taguchi_analysis':
                    from .doe_analysis_charts import TaguchiEffectsWidget
                    chart=TaguchiEffectsWidget(entry)
                elif result.get('analysis') == 'multiple_capability':
                    from .multiple_capability_chart import MultipleCapabilityChartWidget
                    chart = MultipleCapabilityChartWidget(entry)
                elif result.get('graph') in ('panel_graph','graph_layout'):
                    from .graph_composite import GraphCompositeWidget
                    chart=GraphCompositeWidget(entry)
                elif result.get('graph') == 'expanded':
                    from .modern_expanded_charts import ExpandedChartWidget
                    chart = ExpandedChartWidget(entry)
                elif result.get('graph') == 'capability_sixpack' or result.get('analysis') == 'capability_sixpack_normal':
                    from .sixpack_chart import CapabilitySixpackWidget
                    chart = CapabilitySixpackWidget(entry)
                elif result.get('graph') in ('capability_nonparametric', 'capability_automated') or result.get('analysis') in ('capability_nonparametric', 'capability_automated'):
                    from .capability_automated_chart import NonparametricCapabilityPlotWidget
                    chart = NonparametricCapabilityPlotWidget(entry)
                elif result.get('graph') == 'reliability_distribution' or result.get('analysis') == 'reliability_distribution':
                    from .reliability_chart import ReliabilityPlotWidget
                    chart = ReliabilityPlotWidget(entry)
                elif result.get('graph') == 'capability_nonnormal' or result.get('analysis') == 'capability_nonnormal':
                    from .capability_nonnormal_chart import NonnormalCapabilityPlotWidget
                    chart = NonnormalCapabilityPlotWidget(entry)
                elif result.get('graph') == 'acceptance_control' or result.get('analysis') == 'acceptance_control':
                    from .acceptance_chart import AcceptanceControlChartWidget
                    chart = AcceptanceControlChartWidget(entry)
                elif result.get('graph') == 'capability' or result.get('analysis') == 'capability' or 'observed_perf' in result:
                    from .capability_chart import CapabilityPlotWidget
                    chart = CapabilityPlotWidget(entry)
                elif result.get('graph') == 'imr_chart' or result.get('analysis') == 'imr_control':
                    from .imr_chart import IMRChartWidget
                    chart = IMRChartWidget(entry)
                elif result.get('graph') == 'attribute_control' or result.get('analysis') == 'attribute_control':
                    from .attribute_control_chart import AttributeControlChartWidget
                    chart = AttributeControlChartWidget(entry)
                elif result.get('graph') == 'time_weighted_control' or result.get('analysis') == 'time_weighted_control':
                    from .time_weighted_control_chart import TimeWeightedControlChartWidget
                    chart = TimeWeightedControlChartWidget(entry)
                elif result.get('graph') == 'rare_event_control' or result.get('analysis') == 'rare_event_control':
                    from .rare_event_control_chart import RareEventControlChartWidget
                    chart = RareEventControlChartWidget(entry)
                elif result.get('graph') == 'multivariate_control' or result.get('analysis') == 'multivariate_control':
                    from .multivariate_control_chart import MultivariateControlChartWidget
                    chart = MultivariateControlChartWidget(entry)
                elif result.get('graph') == 'pareto_chart' or result.get('analysis') == 'pareto_chart':
                    from .pareto_chart import ParetoChartWidget
                    chart = ParetoChartWidget(entry)
                elif result.get('analysis') == 'nested_gage_rr':
                    from .msa_charts import NestedGageRRChartWidget
                    chart = NestedGageRRChartWidget(entry)
                elif result.get('analysis') == 'gage_linearity_and_bias':
                    from .msa_charts import GageLinearityChartWidget
                    chart = GageLinearityChartWidget(entry)
                elif result.get('analysis') == 'attribute_agreement_analysis':
                    from .msa_charts import AttributeAgreementChartWidget
                    chart = AttributeAgreementChartWidget(entry)
                elif result.get('graph') == 'type1_gage' or result.get('analysis') == 'type1_gage':
                    from .type1_gage_chart import Type1GageChartWidget
                    chart = Type1GageChartWidget(entry)
                elif result.get('graph') == 'attribute_capability':
                    from .attribute_capability_chart import AttributeCapabilityChartWidget
                    chart = AttributeCapabilityChartWidget(entry)
                elif result.get('analysis') == 'definitive_screening_analysis':
                    from .dsd_chart import DSDParetoEffectsWidget
                    chart = DSDParetoEffectsWidget(entry)
                elif result.get('analysis') == 'accelerated_life_testing':
                    from .alt_chart import ALTLifeVsStressWidget
                    chart = ALTLifeVsStressWidget(entry)
                elif result.get('analysis') == 'evaluating_measurement_process':
                    from .emp_chart import EMPChartWidget
                    chart = EMPChartWidget(entry)
                elif result.get('analysis') == 'cart_tree':
                    from .tree_chart import DecisionTreeWidget
                    chart = DecisionTreeWidget(entry)
                elif result.get('analysis') == 'fit_y_by_x':
                    from .fit_y_by_x_chart import FitYByXChartWidget
                    chart = FitYByXChartWidget(entry)
                elif result.get('analysis') == 'jmp_distribution':
                    from .jmp_distribution_chart import JMPDistributionWidget
                    chart = JMPDistributionWidget(entry)
                elif result.get('analysis') == 'control_chart_builder':
                    from .control_chart_builder_chart import ControlChartBuilderWidget
                    chart = ControlChartBuilderWidget(entry)
                elif result.get('analysis') == 'process_screening':
                    from .process_screening_chart import ProcessScreeningWidget
                    chart = ProcessScreeningWidget(entry)
                elif result.get('analysis') in ('optimal_design', 'design_evaluation'):
                    from .design_eval_chart import DesignEvaluationChartWidget
                    chart = DesignEvaluationChartWidget(entry)
                elif result.get('graph') == 'tolerance_intervals' or result.get('analysis') == 'tolerance_intervals':
                    from .tolerance_intervals_chart import ToleranceIntervalChartWidget
                    chart = ToleranceIntervalChartWidget(entry)
                elif result.get('analysis') in ('trend_analysis', 'decomposition', 'moving_average', 'single_exp_smoothing', 'double_exp_smoothing', 'autocorrelation', 'partial_autocorrelation', 'cross_correlation'):
                    from .time_series_chart import TimeSeriesChartWidget
                    chart = TimeSeriesChartWidget(entry)
                elif result.get('analysis') in ('pca', 'item_analysis', 'cluster_observations', 'cluster_kmeans', 'cluster_variables', 'discriminant_analysis', 'simple_correspondence'):
                    from .multivariate_chart import MultivariateChartWidget
                    chart = MultivariateChartWidget(entry)
                elif result.get('analysis') in ('mann_whitney', 'kruskal_wallis', 'moods_median', 'runs_test'):
                    from .nonparametrics_chart import NonparametricChartWidget
                    chart = NonparametricChartWidget(entry)
                elif result.get('analysis') in ('one_sample_equivalence', 'two_sample_equivalence', 'paired_equivalence', 'crossover_equivalence'):
                    from .equivalence_chart import EquivalenceChartWidget
                    chart = EquivalenceChartWidget(entry)
                elif result.get('analysis') in ('one_sample_z_power', 'one_sample_t_power', 'two_sample_t_power', 'paired_t_power', 'one_proportion_power', 'two_proportions_power', 'oneway_anova_power', 'factorial_power'):
                    from .power_chart import PowerCurveWidget
                    chart = PowerCurveWidget(entry)
                elif result.get('analysis') == 'multivari':
                    from .multivari_chart import MultiVariChartWidget
                    chart = MultiVariChartWidget(entry)
                elif result.get('analysis') == 'outlier_test':
                    from .outlier_test_chart import OutlierTestChartWidget
                    chart = OutlierTestChartWidget(entry)
                elif result.get('analysis') == 'graphical_summary':
                    from .graphical_summary_chart import GraphicalSummaryChartWidget
                    chart = GraphicalSummaryChartWidget(entry)
                elif result.get('analysis') == 'run_chart':
                    from .run_chart_plot import RunChartWidget
                    chart = RunChartWidget(entry)
                elif result.get('analysis') in ('cross_tabulation', 'chi_square_goodness_of_fit', 'chi_square_association_table', 'tally_variables'):
                    from .tables_chart import TablesChartWidget
                    chart = TablesChartWidget(entry)
                else:
                    chart = ChartWidget(entry)
                if result.get('graph')=='categorical_points':chart.setMinimumHeight(len(chart.panels)*350+36)
                elif result.get('graph')=='dotplot_graphs':
                    from .dotplot_chart import panel_height
                    chart.setMinimumHeight(sum(panel_height(panel) for panel in chart.panels)+36)
                elif result.get('graph')=='boxplot_graphs':chart.setMinimumHeight(len(chart.panels)*330+36)
                elif result.get('analysis')=='mixture_joint_optimization':chart.setMinimumHeight(chart.minimumHeight())
                elif result.get('analysis')=='response_optimizer':chart.setMinimumHeight(max(440,130+(1+len(result.get('predictions',[])))*130))
                elif result.get('analysis')=='binary_logistic':chart.setMinimumHeight(720)
                elif result.get('analysis')=='gage_rr':chart.setMinimumHeight(1000)
                elif result.get('analysis')=='attribute_control':chart.setMinimumHeight(480)
                elif result.get('analysis') in ('general_linear_model','response_surface'):chart.setMinimumHeight(680 if result['options']['graphs']=='four' else 350)
                elif result.get('analysis') in ('optimal_design', 'design_evaluation', 'cart_tree', 'evaluating_measurement_process', 'fit_y_by_x', 'jmp_distribution', 'control_chart_builder', 'process_screening', 'definitive_screening_analysis', 'accelerated_life_testing'): chart.setMinimumHeight(440)
                elif result.get('graph') not in ('panel_graph','graph_layout'):
                    chart.setMinimumHeight(max(chart.minimumHeight(), len(chart.panels)*max(260,max(len(panel['series']) for panel in chart.panels)*42+100)+36 if result.get('graph')=='histogram_graphs' and chart.panels else 480 if len(chart.panels)>1 else 180))
                chart.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                chart.customContextMenuRequested.connect(lambda pos, c=chart: self._show_output_context_menu(c.mapToGlobal(pos)) if not (getattr(c, '_has_3d_panel', lambda: False)()) else None)
                self._active_chart_widget = chart

                graph_stage = QWidget(); graph_stage.setObjectName("outputPane")
                graph_stage.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                graph_stage.customContextMenuRequested.connect(lambda pos: self._show_output_context_menu(graph_stage.mapToGlobal(pos)))
                graph_stage_layout = QVBoxLayout(graph_stage); graph_stage_layout.setContentsMargins(8, 6, 8, 6); graph_stage_layout.setSpacing(6)
                graph_card = QFrame(); graph_card.setObjectName("resultCard")
                graph_card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                graph_card.customContextMenuRequested.connect(lambda pos: self._show_output_context_menu(graph_card.mapToGlobal(pos)))
                graph_card_layout = QVBoxLayout(graph_card); graph_card_layout.setContentsMargins(8, 6, 8, 6); graph_card_layout.setSpacing(6)

                from .graph_frame import GraphFrame
                graph_frame=GraphFrame(chart,entry)
                graph_frame.export_hidden.extend(getattr(chart,"export_controls",[]))
                chart.objectSelected.connect(lambda target:self._graph_object_selected(target))
                chart.objectActivated.connect(lambda target,e=entry:self._activate_graph_object(e,target))
                if hasattr(chart, 'brushRowsSelected'):
                    chart.brushRowsSelected.connect(lambda rows,e=entry:self._receive_brushed_rows(e,rows))
                graph_frame.annotationActivated.connect(lambda name,e=entry:self.edit_graph_annotation(e,name))
                self._setup_graph_frame(graph_frame, chart, entry)
                self.graph_dropdown_button = QToolButton(); self.graph_dropdown_button.setObjectName("outputDropdownBtn")
                self.graph_dropdown_button.setText("▾")
                self.graph_dropdown_button.setToolTip("Graph / Output Options")
                self.graph_dropdown_button.clicked.connect(lambda: self._show_output_context_menu(self.graph_dropdown_button.mapToGlobal(self.graph_dropdown_button.rect().bottomLeft())))
                if result.get('analysis') in ('mixture_multi_optimization','mixture_multi_evaluation'):
                    reoptimize=QToolButton();reoptimize.setText('Re-optimize');reoptimize.setObjectName('mixtureReoptimize')
                    reoptimize.setToolTip('Search again using this mixture as a starting point, with the same goals and bounds.')
                    reoptimize.clicked.connect(lambda checked=False,e=entry:self._reoptimize_mixture_multi(e))
                    graph_frame.header.addWidget(reoptimize);graph_frame.export_hidden.append(reoptimize)
                graph_frame.header.addWidget(self.graph_dropdown_button)
                graph_frame.export_hidden.append(self.graph_dropdown_button)
                if conn_dict:
                    from .connect_hub import StatCraftAnalysisBar
                    graph_r_bar = StatCraftAnalysisBar(self, entry, conn_dict)
                    graph_card_layout.addWidget(graph_r_bar)
                graph_card_layout.addWidget(graph_frame, 1)
                self._active_graph_frame=graph_frame
                graph_stage_layout.addWidget(graph_card, 1)

                graph_scroll = OutputZoomView(graph_stage)
                graph_index = self.result_tabs.addTab(graph_scroll, "Graph")
                chosen_tab = 0 if target_tab == "Report" else graph_index
                self.result_tabs.setCurrentIndex(chosen_tab)
                graph_scroll.set_zoom(self._output_zoom_levels.get(self._zoom_key(),100))
                self._sync_output_zoom()
        else:
            self._active_chart_widget = None
            self._active_graph_frame=None
            self.graph_options_pane.load_entry(None);self.graph_options_pane.hide()
            if target_tab is not None and target_tab in getattr(self, '_report_table_widgets', {}):
                chosen_tab = 0
                try:
                    scroll.ensureWidgetVisible(self._report_table_widgets[target_tab], 0, 50)
                except Exception:
                    pass
                self.result_tabs.setCurrentIndex(0)
        text = QPlainTextEdit(); text.setReadOnly(True); text.setFont(QFont("Consolas", 9.5)); text.setPlainText(format_entry(entry))
        text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        text.customContextMenuRequested.connect(lambda pos: self._show_output_context_menu(text.mapToGlobal(pos)))
        self.result_tabs.addTab(text, "Text export")
        if not self.graph_options_pane.isHidden():self.graph_options_pane.load_entry(entry)
        self.refresh()
        explicit_target = (target_graph_index is not None or target_tab is not None)
        self._workspace.after_show(target_index=chosen_tab if explicit_target else None)

    # --- StatCraft Column & Row Selection Highlighting (`RT_MENU 9839` / `RT_MENU 10521`) ---

    def select_worksheet_column(self, col_index, extend=False):
        if col_index < 0 or col_index >= self.table.columnCount():
            return
        from PySide6.QtWidgets import QTableWidgetSelectionRange
        if not extend:
            self._selected_columns = {col_index}
            self._selected_rows = set()
            blocker = QSignalBlocker(self.table)
            self.table.clearSelection()
            self.table.setCurrentCell(0, col_index)
            self.table.setRangeSelected(QTableWidgetSelectionRange(0, col_index, max(0, self.table.rowCount() - 1), col_index), True)
            del blocker
        else:
            self._selected_columns.add(col_index)
            self.table.setRangeSelected(QTableWidgetSelectionRange(0, col_index, max(0, self.table.rowCount() - 1), col_index), True)
        self._apply_selection_state()

    def select_worksheet_row(self, row_index, extend=False):
        if row_index < 0 or row_index >= self.table.rowCount():
            return
        from PySide6.QtWidgets import QTableWidgetSelectionRange
        if not extend:
            self._selected_rows = {row_index}
            self._selected_columns = set()
            blocker = QSignalBlocker(self.table)
            self.table.clearSelection()
            self.table.setCurrentCell(row_index, 0)
            self.table.setRangeSelected(QTableWidgetSelectionRange(row_index, 0, row_index, max(0, self.table.columnCount() - 1)), True)
            del blocker
        else:
            self._selected_rows.add(row_index)
            self.table.setRangeSelected(QTableWidgetSelectionRange(row_index, 0, row_index, max(0, self.table.columnCount() - 1)), True)
        self._apply_selection_state()

    def _on_column_header_clicked(self, logical_index):
        self._select_column_header(logical_index,QApplication.keyboardModifiers())

    def _select_column_header(self,logical_index,mods):
        if mods & Qt.KeyboardModifier.ShiftModifier:
            anchor=getattr(self,'_column_selection_anchor',max(0,self.table.currentColumn()))
            self.select_worksheet_column(min(anchor,logical_index))
            for index in range(min(anchor,logical_index)+1,max(anchor,logical_index)+1):self.select_worksheet_column(index,extend=True)
        elif mods & Qt.KeyboardModifier.ControlModifier:
            if logical_index in self._selected_columns:
                self.table.setRangeSelected(QTableWidgetSelectionRange(0,logical_index,max(0,self.table.rowCount()-1),logical_index),False)
                self._sync_selection_highlights()
            else:self.select_worksheet_column(logical_index,extend=True)
            self._column_selection_anchor=logical_index
        else:
            self.select_worksheet_column(logical_index);self._column_selection_anchor=logical_index

    def _on_row_header_clicked(self, logical_index):
        mods = QApplication.keyboardModifiers()
        extend = bool(mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier))
        self.select_worksheet_row(logical_index, extend=extend)

    def _sync_selection_highlights(self):
        if self._refreshing:
            return
        ranges = self.table.selectedRanges()
        total_rows = max(1, self.table.rowCount())
        total_cols = max(1, self.table.columnCount())
        sel_cols = set()
        sel_rows = set()
        for area in ranges:
            if area.topRow() == 0 and area.bottomRow() >= total_rows - 1:
                for c in range(area.leftColumn(), area.rightColumn() + 1):
                    sel_cols.add(c)
            if area.leftColumn() == 0 and area.rightColumn() >= total_cols - 1:
                for r in range(area.topRow(), area.bottomRow() + 1):
                    sel_rows.add(r)
        self._selected_columns = sel_cols
        self._selected_rows = sel_rows
        self._apply_selection_state()

    def _apply_selection_state(self):
        sheet = self.presenter.worksheet
        start = self.page * self.PAGE_SIZE
        nonempty_rows = max(0, min(self.table.rowCount(), sheet.row_count - start))
        active_rows = set(range(nonempty_rows)) if self._selected_columns else set()
        cur_r = self.table.currentRow()
        cur_c = self.table.currentColumn()
        if cur_r >= 0 and not self._selected_rows and not self._selected_columns:
            active_rows.add(cur_r)
        active_cols = {cur_c} if (cur_c >= 0 and not self._selected_columns and not self._selected_rows) else set()

        self.table.selected_columns = set(self._selected_columns)
        self.table.selected_rows = set(self._selected_rows)
        self.column_names.selected_columns = set(self._selected_columns)
        self.col_header_view.selected_sections = set(self._selected_columns)
        self.col_header_view.active_sections = active_cols
        self.row_header_view.selected_sections = set(self._selected_rows)
        self.row_header_view.active_sections = active_rows
        self.col_header_view.viewport().update()
        self.row_header_view.viewport().update()
        self.column_names.viewport().update()
        self.table.viewport().update()

    # --- Worksheet Right-Click Context Menu (`RT_MENU 9839`) ---

    def _on_column_header_context_menu(self, pos):
        col = self.col_header_view.logicalIndexAt(pos)
        if col >= 0 and col not in self._selected_columns:
            self.select_worksheet_column(col)
        self._show_worksheet_context_menu(self.col_header_view.viewport().mapToGlobal(pos))

    def _on_row_header_context_menu(self, pos):
        row = self.row_header_view.logicalIndexAt(pos)
        if row >= 0 and row not in self._selected_rows:
            self.select_worksheet_row(row)
        self._show_worksheet_context_menu(self.row_header_view.viewport().mapToGlobal(pos))

    def _on_table_context_menu(self, pos):
        idx = self.table.indexAt(pos)
        if idx.isValid():
            r, c = idx.row(), idx.column()
            if c not in self._selected_columns and r not in self._selected_rows and not self.table.item(r, c).isSelected():
                self.table.setCurrentCell(r, c)
        self._show_worksheet_context_menu(self.table.viewport().mapToGlobal(pos))

    def build_worksheet_context_menu(self):
        menu = QMenu(self)
        col_mode = bool(self._selected_columns)
        row_mode = bool(self._selected_rows) and not col_mode
        cur_col = max(0, min(self.table.currentColumn(), len(self.presenter.worksheet.columns) - 1))
        cur_row = self.page * self.PAGE_SIZE + max(0, self.table.currentRow())

        # Group 1: Clear, Delete, Copy, Cut, Paste
        clear_act = menu.addAction(tool_icon("erase"), "Clear Cells")
        clear_act.triggered.connect(self.clear_cells)
        del_act = menu.addAction(tool_icon("delete_red_x"), "Delete Cells")
        if col_mode:
            del_act.triggered.connect(self.delete_selected_columns)
        else:
            del_act.triggered.connect(self.delete_selected_rows)
        copy_act = menu.addAction(tool_icon("copy"), "Copy Cells\tCtrl+C")
        copy_act.triggered.connect(self.copy_cells)
        cut_act = menu.addAction(tool_icon("cut"), "Cut Cells\tCtrl+X")
        cut_act.triggered.connect(self.cut_cells)
        paste_act = menu.addAction(tool_icon("paste"), "Paste Cells\tCtrl+V")
        paste_act.triggered.connect(self.paste_cells)

        menu.addSeparator()

        # Group 2: Find and Replace, Sort Columns
        find_sub = menu.addMenu("Find and Replace")
        find_sub.addAction(tool_icon("find"), "Find...\tCtrl+F", self.find_dialog)
        find_sub.addAction("Replace...\tCtrl+H", self.replace_dialog)
        find_sub.addSeparator()
        find_sub.addAction(tool_icon("goto"), "Go To...\tCtrl+G", self.goto_dialog)
        goto_sub = find_sub.addMenu("Go To")
        goto_sub.addAction("Next Column", lambda: self._navigate_cell("right"))
        goto_sub.addAction("Active Cell", lambda: self.table.scrollToItem(self.table.currentItem()))
        goto_sub.addAction(tool_icon("next_brushed"), "Next Brushed Row", lambda: self.go_to_brushed_row(1))
        goto_sub.addAction(tool_icon("prev_brushed"), "Previous Brushed Row", lambda: self.go_to_brushed_row(-1))

        sort_sub = menu.addMenu("Sort Columns")
        entire_ws_sub = sort_sub.addMenu("Entire Worksheet")
        all_cols = list(range(len(self.presenter.worksheet.columns)))
        entire_ws_sub.addAction("Smallest to Largest", lambda: self._call(lambda: self.presenter.sort_columns(all_cols, cur_col, False), result=True))
        entire_ws_sub.addAction("Largest to Smallest", lambda: self._call(lambda: self.presenter.sort_columns(all_cols, cur_col, True), result=True))
        sort_sub.addAction("Custom Sort...", self.sort_dialog)

        menu.addSeparator()

        # Group 3: Cell Properties
        cell_sub = menu.addMenu("Cell Properties")
        cell_sub.addAction("Comment...", self.cell_comment_dialog)
        cell_sub.addSeparator()
        first_r, last_r, left_c, right_c = self._range()
        sel_r_range = list(range(first_r, last_r + 1))
        sel_c_range = list(range(left_c, right_c + 1))
        cell_sub.addAction("Highlight Red", lambda: self._call(lambda: self.presenter.set_cell_highlight(sel_r_range, sel_c_range, "#f8d7da")))
        cell_sub.addAction("Highlight Green", lambda: self._call(lambda: self.presenter.set_cell_highlight(sel_r_range, sel_c_range, "#d4edda")))
        cell_sub.addAction("Highlight Yellow", lambda: self._call(lambda: self.presenter.set_cell_highlight(sel_r_range, sel_c_range, "#fff3cd")))
        cell_sub.addSeparator()
        cell_sub.addAction("Clear Formats", lambda: self._call(lambda: self.presenter.clear_cell_formats(sel_r_range, sel_c_range)))

        menu.addSeparator()

        # Group 4: Format Column, Column Properties, Conditional Formatting, Formulas
        fmt_col_act = menu.addAction(tool_icon("format_column"), "Format Column...\tCtrl+1")
        fmt_col_act.triggered.connect(self.format_column_dialog)

        col_prop_sub = menu.addMenu("Column Properties")
        col_prop_sub.addAction("Description...", self.column_description_dialog)
        value_order_action=col_prop_sub.addAction("Value Order...", self.column_value_order_dialog)
        value_order_action.setEnabled(self.presenter.worksheet.columns[cur_col].kind=='text')
        col_prop_sub.addSeparator()
        col_prop_sub.addAction("Width...", self.column_width_dialog)
        col_prop_sub.addAction("Standard Width...", self.standard_column_width_dialog)
        col_prop_sub.addSeparator()
        col_prop_sub.addAction("Hide Selected Columns", self.hide_selected_columns)
        col_prop_sub.addAction("Unhide Selected Columns", self.unhide_all_columns)
        use_hidden_act = col_prop_sub.addAction("Use Hidden Columns in Dialog Boxes")
        use_hidden_act.setCheckable(True); use_hidden_act.setChecked(self._use_hidden_in_dialogs)
        use_hidden_act.triggered.connect(lambda checked: setattr(self, "_use_hidden_in_dialogs", bool(checked)))

        cond_sub = menu.addMenu("Conditional Formatting")
        hl_sub = cond_sub.addMenu("Highlight Cell")
        hl_sub.addAction("Missing Observations...", lambda: self._call(lambda: self.presenter.apply_conditional_formatting(cur_col, "missing", color="#fff3cd")))
        hl_sub.addAction("Greater Than...", lambda: self.conditional_formatting_dialog("greater_than", "Greater Than"))
        hl_sub.addAction("Less Than...", lambda: self.conditional_formatting_dialog("less_than", "Less Than"))
        hl_sub.addAction("Between...", lambda: self.conditional_formatting_dialog("between", "Between"))
        hl_sub.addAction("Equal To...", lambda: self.conditional_formatting_dialog("equal_to", "Equal To"))
        hl_sub.addAction("Text that Contains...", lambda: self.conditional_formatting_dialog("contains", "Text that Contains"))
        hi_lo_sub = cond_sub.addMenu("High/Low")
        hi_lo_sub.addAction("Highest Values...", lambda: self.conditional_formatting_dialog("highest", "Highest Values (Count)"))
        hi_lo_sub.addAction("Lowest Values...", lambda: self.conditional_formatting_dialog("lowest", "Lowest Values (Count)"))
        stat_sub = cond_sub.addMenu("Statistical")
        stat_sub.addAction("Outlier...", lambda: self._call(lambda: self.presenter.apply_conditional_formatting(cur_col, "outlier", color="#f8d7da")))
        clear_rules_sub = cond_sub.addMenu("Clear Rules")
        clear_rules_sub.addAction("Clear Rules from Selected Columns", lambda: self._call(lambda: self.presenter.clear_conditional_formatting(sel_c_range)))
        clear_rules_sub.addAction("Clear Rules from Entire Worksheet", lambda: self._call(lambda: self.presenter.clear_conditional_formatting(None)))

        form_sub = menu.addMenu("Formulas")
        form_sub.addAction(tool_icon("assign_formula"), "Assign Formula to Column...", self.assign_formula_dialog)
        form_sub.addAction("Remove Formulas from Selected Columns", lambda: self._call(lambda: self.presenter.remove_formulas(sel_c_range)))
        form_sub.addSeparator()
        form_sub.addAction("Calculate All Formulas Now", lambda: self._call(self.presenter.calculate_all_formulas))
        auto_calc_act = form_sub.addAction("Calculate All Formulas Automatically")
        auto_calc_act.setCheckable(True); auto_calc_act.setChecked(self.presenter.auto_calculate_formulas)
        auto_calc_act.triggered.connect(lambda checked: self._call(lambda: self.presenter.set_automatic_formulas(bool(checked))))

        menu.addSeparator()

        # Group 5: Subset Worksheet, Worksheet Properties
        subset_sub = menu.addMenu("Subset Worksheet")
        subset_sub.addAction("Include Selected Rows", lambda: self._call(lambda: self.presenter.subset_worksheet(mode="include", row_indices=sel_r_range)))
        subset_sub.addAction("Exclude Selected Rows", lambda: self._call(lambda: self.presenter.subset_worksheet(mode="exclude", row_indices=sel_r_range)))
        subset_sub.addAction("Custom Subset...", self.subset_worksheet_dialog)

        ws_prop_sub = menu.addMenu("Worksheet Properties")
        ws_prop_sub.addAction("Description...", self.worksheet_description_dialog)
        ws_prop_sub.addAction("Change Entry Direction", self.toggle_entry_direction)

        menu.addSeparator()

        # Group 6: Insert Cells, Insert Rows, Insert Columns, Move Columns
        menu.addAction(tool_icon("insert_cells"), "Insert Cells", self.insert_cells_action_handler)
        menu.addAction(tool_icon("insert_rows"), "Insert Rows", self.insert_rows_action_handler)
        menu.addAction(tool_icon("insert_columns"), "Insert Columns", self.insert_columns_action_handler)
        menu.addAction(tool_icon("move_columns"), "Move Columns...", self.move_columns_dialog)
        return menu

    def _show_worksheet_context_menu(self, global_pos):
        menu = self.build_worksheet_context_menu()
        menu.exec(global_pos)

    # --- Output / Graph Right-Click & Dropdown Menu (`RT_MENU 19209` / `RT_MENU 23702`, excluding StatCraft apps) ---

    def build_output_context_menu(self, entry=None):
        target_entry = entry or self.selected_entry
        menu = QMenu(self)
        if target_entry is None:
            return menu
        from .modern_charts import supported
        is_graph = supported(target_entry)

        menu.addAction("Send to Microsoft® Word", lambda: self.send_output_to_word(target_entry))
        menu.addAction("Send to Microsoft® PowerPoint", lambda: self.send_output_to_powerpoint(target_entry))
        menu.addAction(tool_icon("send_report"), "Send to Report", lambda: self.send_output_to_report(target_entry))
        if is_graph:
            menu.addAction(tool_icon("copy_graph"), "Copy Graph", lambda: self.copy_output_graph(target_entry))
            from .similar_graph_dialog import supports_similar
            menu.addAction(tool_icon("make_similar_graph"), "Make Similar Graph...", lambda: self.make_similar_graph(target_entry)).setEnabled(supports_similar(target_entry))
            menu.addSeparator()
            native_snapshot = target_entry.get('result',{}).get('analysis')=='native_saved_output'
            can_edit_graph = (target_entry.get('origin') == 'statcraft' and 'recipe' in target_entry and target_entry.get('recipe', {}).get('action') in ('graph', 'scatter_plot', 'expanded_graph')) or native_snapshot
            edit_action = menu.addAction(tool_icon("edit_graph"), "Edit Graph...", lambda: self.edit_graph_dialog(target_entry))
            edit_action.setEnabled(can_edit_graph)
            if native_snapshot:
                appearance=menu.addAction('Graph Appearance…',lambda:self.native_graph_appearance(target_entry))
                appearance.setToolTip('Edit this saved graph’s color palette and 3D view in the StatCraft project copy.')
            result=target_entry.get('result',{})
            composition=result.get('graph') in ('panel_graph','graph_layout')
            object_capable=not composition and (result.get('graph')!='expanded' or any(p.get('kind') in ('xy','bars','binbars','intervals','xyz') for p in result.get('panels',[])))
            object_action=menu.addAction('Edit Selected Object...',lambda:self.edit_graph_object(target_entry))
            active_native=getattr(self,'_active_chart_widget',None) if target_entry is self.selected_entry else None
            object_action.setEnabled(can_edit_graph and object_capable and (not native_snapshot or active_native is not None and bool(active_native.editable_objects())))
            scale_action=menu.addAction('Edit Scales...',lambda:self.edit_graph_scales(target_entry));scale_action.setEnabled(can_edit_graph and not composition and result.get('analysis')!='mixture_joint_optimization')
            if native_snapshot:
                from .native_graph_view import cartesian
                scale_action.setEnabled(cartesian(target_entry))
            if result.get('graph')=='histogram':menu.addAction('Histogram Scales and Fits...',lambda:self.histogram_options_dialog(target_entry))
            panel_action=menu.addAction(tool_icon("panel_graph"), "Panel...", lambda: self.panel_graph_dialog(target_entry))
            panel_action.setEnabled(target_entry.get('recipe',{}).get('action') in ('graph','scatter_plot','expanded_graph'))
            from .brushing import brushable_rows
            brush_action=menu.addAction(tool_icon("brush_points"), "Brush Points...", lambda: self.brush_points_dialog(target_entry))
            brush_action.setEnabled(bool(brushable_rows(target_entry)))
            brush_action.setCheckable(True)
            brush_action.setChecked(target_entry is self.selected_entry and getattr(getattr(self,'_active_chart_widget',None),'is_brushing',False))
            menu.addAction(tool_icon("layout_tool"), "Layout Tool...", lambda: self.layout_tool_dialog(target_entry))
            menu.addAction("Reset to Default Size", self.reset_graph_size)
            menu.addSeparator()
            menu.addAction(tool_icon("save"), "Save Graph As...", lambda: self.save_graph_as(target_entry))
        else:
            menu.addAction(tool_icon("copy"), "Copy\tCtrl+C", lambda: QApplication.clipboard().setText(format_entry(target_entry)))
            menu.addAction(tool_icon("copy_graph"), "Copy as Picture", lambda: self.copy_output_graph(target_entry))
            menu.addSeparator()
            menu.addAction("Rename...", lambda: self.rename_output_dialog(target_entry))
            menu.addSeparator()
        # R Script Export Actions
        menu.addSeparator()
        menu.addAction("📋 Copy R Script\tCtrl+Alt+R", lambda: self.copy_entry_r_script(target_entry))
        menu.addAction("👁️ View R Code...", lambda: self.view_entry_r_code(target_entry))
        menu.addAction("💾 Export to R Script (.R)...", lambda: self.export_entry_r_file(target_entry))
        menu.addAction("📑 Append to ReportPad", lambda: self.append_connected_report_to_report_pad(target_entry))

        if is_graph and getattr(self, "_brushed_rows", None):
            menu.addSeparator()
            menu.addAction("Highlight in Worksheet", lambda: self.highlight_brushed_selection())
            menu.addAction("Save Selection…", lambda: self.save_brushed_selection())
            menu.addAction("Analyze Selection…", lambda: self.analyze_brushed_selection())
            menu.addAction("Open Selection in R Workbench…", lambda: self.open_brushed_selection_in_r())
            menu.addAction("Clear Selection", lambda: self.clear_brushed_selection())

        menu.addAction(tool_icon("save"), "Save Output As...", self.export_report)
        menu.addAction(tool_icon("print"), "Print...\tCtrl+P", lambda checked=False: self.print_current(target_entry))
        menu.addAction("Close Output Tab",lambda:self._workspace.close_index(self._workspace.state["open_ids"].index(self._workspace.key(target_entry))) if self._workspace.key(target_entry) in self._workspace.state["open_ids"] else None)
        menu.addAction(tool_icon("delete_red_x"), "Delete", lambda: self.delete_selected_output(target_entry))
        if target_entry.get('native_model',{}).get('supported'):
            menu.addSeparator();menu.addAction('Refit Model in StatCraft…',lambda:self.refit_native_model(target_entry))
        if target_entry.get('origin')=='statcraft' and 'recipe' in target_entry:
            menu.addSeparator()
            menu.addAction('Rerun with Current Data',lambda:self._call(lambda:self.presenter.rerun_result(target_entry),result=True))
        return menu

    def _populate_connect_menu(self, connect_menu):
        self._action(connect_menu, "What is StatCraft Connect?…", self.show_connect_overview, None, "connect")
        self._action(connect_menu, "StatCraft Connect Tri-Engine Tour (Multi-Sheet) ...", self.load_connect_sample_project, None, "new_project")
        self._action(connect_menu, "Try Connect Sample Project (Chemical Yield)…", self.load_connect_sample, None, "new_project")
        connect_menu.addSeparator()
        self._action(connect_menu, "Open in Statistical Dialog (Minitab Mode)…", lambda: self.connect_open_dialog(self.selected_entry) if self.selected_entry else None, None, None, True)
        self._action(connect_menu, "Open in Interactive Explorer (JMP Mode)…", lambda: self.connect_open_explorer(self.selected_entry) if self.selected_entry else self.prediction_profiler(), None, None, True)
        self._action(connect_menu, "Open in R Workbench (R Mode)…", lambda: self.connect_open_in_r(self.selected_entry) if self.selected_entry else None, None, None, True)
        connect_menu.addSeparator()
        self._action(connect_menu, "Compare StatCraft vs R Execution…", lambda: self.connect_compare_implementations(self.selected_entry) if self.selected_entry else None, None, None, True)
        self._action(connect_menu, "Apply Predictions & Residuals to Worksheet…", lambda: self.connect_apply_predictions(self.selected_entry) if self.selected_entry else None, None, None, True)
        self._action(connect_menu, "Append Connected Report to ReportPad…", lambda: self.append_connected_report_to_report_pad(self.selected_entry) if self.selected_entry else None, None, "report", True)
        connect_menu.addSeparator()
        self._action(connect_menu, "Save as Reusable Workflow Recipe…", lambda: self.save_connected_workflow(self.selected_entry) if self.selected_entry else None, None, "workflow", True)
        self._action(connect_menu, "Replay Saved Workflow on Another Sheet…", self.replay_saved_workflow_dialog, None, "workflow", True)

    def multiple_regression_dialog(self):
        return self.multiple_regression()

    def analyze_surface_dialog(self):
        return self.analyze_response_surface()

    def connect_open_dialog(self, entry):
        if not entry:
            return
        recipe = entry.get("recipe", {})
        action = recipe.get("action")
        self.set_ui_mode("minitab")
        if action == "multiple_regression":
            self.multiple_regression()
        elif action in ("analyze_response_surface", "response_surface"):
            self.analyze_response_surface()
        elif action in ("oneway_anova", "one_way_anova", "stacked_anova"):
            self.oneway_anova_dialog()
        elif action in ("analyze_factorial", "analyze_factorial_terms", "factorial_regression"):
            self.analyze_factorial()
        elif action in ("general_linear_model", "glm"):
            self.general_linear_model()
        elif action in ("two_sample_t", "2_sample_t"):
            self.inference_dialog("two_sample_t")
        elif action in ("one_sample_t", "1_sample_t"):
            self.inference_dialog("one_sample_t")
        elif action in ("paired_t", "paired"):
            self.inference_dialog("paired_t")
        elif action == "correlation":
            self.correlation()
        elif action in ("twoway_anova", "two_way_anova"):
            self.twoway_anova_dialog()
        elif action in ("fit_binary_logistic", "binary_logistic"):
            self.fit_binary_logistic()
        elif action in ("normal_capability", "process_capability", "capability"):
            self.capability()
        elif action in ("individuals_moving_range", "imr_chart", "imr"):
            self.imr_dialog()
        elif action in ("gage_rr", "gage_rr_crossed", "crossed_gage_rr"):
            self.gage_rr()
        elif action in ("subgroup_control_chart", "xbar_r", "xbar_r_dialog", "xbar_r_stacked"):
            self.xbar_r_dialog()
        elif action in ("xbar_s", "xbar_s_dialog", "xbar_s_stacked"):
            self.xbar_s_dialog()
        elif action == "fit_y_by_x":
            self.multiple_regression()
        elif action in ("describe_columns", "descriptive_statistics", "describe_column"):
            self.describe()
        else:
            self.statusBar().showMessage(f"Recalled dialog for procedure '{action}'.", 5000)

    def show_connect_overview(self):
        from .connect_hub import ConnectOverviewDialog
        dlg = ConnectOverviewDialog(self)
        dlg.exec()

    def load_connect_sample_project(self):
        from .model import Worksheet, Column
        from .connect import create_connected_analysis_from_entry
        from .mpx_create import create_project

        self.presenter.new()
        self.page = 0
        self.selected_entry = None

        # Sheet 1: DOE_Battery
        ws1 = Worksheet("DOE_Battery", [
            Column("Temperature", "number", [-15, -15, 20, 20, 50, 50] * 2),
            Column("Material", "text", ["M1"] * 6 + ["M2"] * 6),
            Column("Life", "number", [130, 155, 34, 40, 20, 70, 150, 188, 136, 122, 25, 70]),
        ])

        # Sheet 2: GageRR_Gasket
        ws2 = Worksheet("GageRR_Gasket", [
            Column("Measurement", "number", [10.2, 10.3, 12.1, 12.0, 15.4, 15.6, 10.1, 10.4, 12.3, 12.1, 15.2, 15.5]),
            Column("Part", "text", ["P1", "P1", "P2", "P2", "P3", "P3"] * 2),
            Column("Operator", "text", ["A"] * 6 + ["B"] * 6),
        ])

        # Sheet 3: SPC_PistonRings
        ws3 = Worksheet("SPC_PistonRings", [
            Column("Diameter", "number", [74.010, 74.001, 74.008, 74.003, 74.002, 74.005, 73.998, 74.002, 74.004, 74.000, 74.008, 74.002, 74.005, 74.001, 74.004, 74.002, 74.004, 74.003, 73.999, 74.007]),
            Column("Sample", "text", ["S1"] * 5 + ["S2"] * 5 + ["S3"] * 5 + ["S4"] * 5),
        ])

        project = create_project([ws1, ws2, ws3], active_index=0)
        self.presenter.native_project = project

        self.presenter.select_worksheet(0)
        e1 = self.presenter.twoway_anova(2, 0, 1, fit_interaction=True)
        create_connected_analysis_from_entry(e1, ws1)

        self.presenter.select_worksheet(1)
        e2 = self.presenter.gage_rr(0, 1, 2)
        create_connected_analysis_from_entry(e2, ws2)

        self.presenter.select_worksheet(2)
        e3 = self.presenter.subgroup_control_chart(chart_type="xbar_r", stacked=True, response_index=0, factor_index=1)
        create_connected_analysis_from_entry(e3, ws3)

        self.presenter.select_worksheet(0)
        self._prepare_blank()
        self.refresh()
        self.show_result(e1)
        self.statusBar().showMessage("StatCraft Connect: Tri-Engine Tour Project loaded with 3 benchmark analyses!", 8000)

    def load_connect_sample(self):
        from .connect_hub import create_chemical_process_sample
        ws = create_chemical_process_sample()
        self.presenter.worksheet = ws
        self._prepare_blank()
        self.refresh()
        entry = self._call(lambda: self.presenter.multiple_regression(0, [1, 2]), result=True)
        if entry:
            self.show_result(entry)
            self.statusBar().showMessage("StatCraft Connect: Chemical Process sample loaded. Model bridge is active!", 8000)

    def connect_open_explorer(self, entry):
        from .connect_explorer import open_interactive_explorer
        open_interactive_explorer(self, entry)

    def connect_open_contour(self, entry):
        recipe = entry.get("recipe", {})
        action = recipe.get("action")
        family = "response_surface" if action == "analyze_response_surface" else "regression"
        self.model_contour_plot(family)

    def connect_open_surface(self, entry):
        recipe = entry.get("recipe", {})
        action = recipe.get("action")
        family = "response_surface" if action == "analyze_response_surface" else "regression"
        self.model_surface_plot(family)

    def connect_open_r_bootstrap(self, entry):
        conn_dict = entry.get("connected_analysis")
        if not conn_dict:
            from .connect import create_connected_analysis_from_entry
            try:
                conn_obj = create_connected_analysis_from_entry(entry, self.presenter.worksheet)
                if conn_obj:
                    conn_dict = conn_obj.to_dict()
                    entry["connected_analysis"] = conn_dict
            except Exception:
                conn_dict = None

        if not conn_dict:
            QMessageBox.information(self, "R Bootstrap", "A connected model (Response Surface, Factorial, or Regression) is required.")
            return

        from .connect import ConnectedAnalysis
        from .connect_r import generate_response_surface_bootstrap_script
        conn = ConnectedAnalysis.from_dict(conn_dict)

        cand_pts = self.presenter.worksheet.metadata.get("candidate_points", []) if hasattr(self.presenter.worksheet, "metadata") else []
        cand_point = cand_pts[-1].get("factors", {}) if cand_pts else None

        boot_script = generate_response_surface_bootstrap_script(
            conn,
            self.presenter.worksheet,
            replications=2000,
            confidence=conn.confidence,
            candidate_point=cand_point,
        )

        if self.r_workbench:
            self.set_ui_mode("r")
            self.r_workbench.load_connected_analysis({
                **conn_dict,
                "r_script": boot_script,
                "title": f"RSM Bootstrap Uncertainty ({conn.response_name})",
            })
            self.statusBar().showMessage("StatCraft Connect: Loaded R Bootstrap Uncertainty Script", 6000)

    def connect_open_in_r(self, entry):
        conn_dict = entry.get("connected_analysis")
        if not conn_dict:
            from .connect import create_connected_analysis_from_entry
            try:
                conn_obj = create_connected_analysis_from_entry(entry, self.presenter.worksheet)
                if conn_obj:
                    conn_dict = conn_obj.to_dict()
                    entry["connected_analysis"] = conn_dict
            except Exception:
                conn_dict = None

        if conn_dict and self.r_workbench:
            self.set_ui_mode("r")
            self.r_workbench.load_connected_analysis(conn_dict)
            self.statusBar().showMessage("StatCraft Connect: Model transferred to R Workbench", 5000)
        elif self.r_workbench:
            self.set_ui_mode("r")
            self.r_workbench.sync_active_worksheet_to_r()
            self.statusBar().showMessage("StatCraft Connect: Active worksheet synchronized into R as 'df'", 5000)

    def connect_apply_predictions(self, entry):
        conn_dict = entry.get("connected_analysis")
        recipe = entry.get("recipe", {})
        action = recipe.get("action")
        p = recipe.get("parameters", {})
        if not conn_dict:
            if action == "multiple_regression" and "response_index" in p:
                from .connect import create_connected_regression
                conn_dict = create_connected_regression(
                    self.presenter.worksheet, p["response_index"], p["predictor_indices"],
                    entry.get("result", {}), p.get("confidence", 0.95)
                ).to_dict()
                entry["connected_analysis"] = conn_dict
            elif action == "analyze_response_surface" and "response_index" in p:
                from .connect import create_connected_response_surface
                conf = p.get("options", {}).get("confidence", 0.95) if isinstance(p.get("options"), dict) else 0.95
                conn_dict = create_connected_response_surface(
                    self.presenter.worksheet, p["response_index"], p["factor_indices"],
                    entry.get("result", {}), conf, coding=p.get("coding"), terms=p.get("terms"), options=p.get("options")
                ).to_dict()
                entry["connected_analysis"] = conn_dict

        if not conn_dict:
            return
        from .connect import ConnectedAnalysis
        from .connect_r import import_r_predictions_to_worksheet
        conn = ConnectedAnalysis.from_dict(conn_dict)

        from .model import Column
        diag_cols = [
            Column("Row_ID", "text", list(conn.fitted_row_ids)),
            Column("Fitted", "number", list(conn.fitted_values)),
            Column("Residuals", "number", list(conn.residuals)),
        ]
        res = import_r_predictions_to_worksheet(self.presenter.worksheet, {"Regression_Diagnostics": diag_cols}, conn)
        self.refresh()
        self.statusBar().showMessage(
            f"StatCraft Connect: Created/updated {res.get('fitted_col')} and {res.get('residuals_col')} ({res.get('rows_updated')} rows aligned by observation ID)",
            6000
        )

    def _setup_graph_frame(self, graph_frame, chart, entry):
        self._active_graph_frame = graph_frame
        if hasattr(graph_frame, 'btn_highlight'):
            graph_frame.btn_highlight.clicked.connect(lambda: self.highlight_brushed_selection())
            graph_frame.btn_save.clicked.connect(lambda: self.save_brushed_selection())
            graph_frame.btn_analyze.clicked.connect(lambda: self.analyze_brushed_selection())
            graph_frame.btn_r.clicked.connect(lambda: self.open_brushed_selection_in_r())
            graph_frame.btn_clear.clicked.connect(lambda: self.clear_brushed_selection())

    def connect_compare_implementations(self, entry):
        conn_dict = entry.get("connected_analysis")
        if not conn_dict:
            from .connect import create_connected_analysis_from_entry
            try:
                conn_obj = create_connected_analysis_from_entry(entry, self.presenter.worksheet)
                if conn_obj:
                    conn_dict = conn_obj.to_dict()
                    entry["connected_analysis"] = conn_dict
            except Exception:
                conn_dict = None

        if not conn_dict:
            QMessageBox.information(self, "Compare Implementations", "This result does not have a connected analysis model.")
            return

        from .connect import ConnectedAnalysis
        from .connect_compare_dialog import run_cross_engine_comparison, CompareImplementationsDialog
        from .r_bridge import is_r_available
        if not is_r_available():
            QMessageBox.information(self, "Compare Implementations", "R is not detected on this system. Click 'Install R' in R Workbench to enable cross-engine verification.")
            return

        conn = ConnectedAnalysis.from_dict(conn_dict)
        self.statusBar().showMessage("Running cross-engine execution comparison...", 4000)
        res = run_cross_engine_comparison(conn, self.presenter.worksheet)
        if not res.get("success"):
            QMessageBox.warning(self, "Compare Implementations", f"Execution comparison failed:\n{res.get('error')}")
            return

        dlg = CompareImplementationsDialog(conn, res, self)
        dlg.exec()

    def append_connected_report_to_report_pad(self, entry=None):
        target_entry = entry or self.selected_entry
        if not target_entry:
            QMessageBox.information(self, "Append to ReportPad", "Please select a model result first.")
            return

        conn_dict = target_entry.get("connected_analysis")
        if not conn_dict:
            from .connect import create_connected_analysis_from_entry
            try:
                conn_obj = create_connected_analysis_from_entry(target_entry, self.presenter.worksheet)
                if conn_obj:
                    conn_dict = conn_obj.to_dict()
                    target_entry["connected_analysis"] = conn_dict
            except Exception:
                conn_dict = None

        if not conn_dict:
            QMessageBox.information(self, "Append to ReportPad", "This result does not have a connected analysis model.")
            return

        from .connect import ConnectedAnalysis
        from .connect_report import generate_connected_report
        conn = ConnectedAnalysis.from_dict(conn_dict)
        report_text = generate_connected_report(conn, self.presenter.worksheet)

        self.append_to_report_pad(report_text)
        self.statusBar().showMessage(f"StatCraft Connect: Appended '{conn.title}' report to ReportPad", 6000)

    def append_to_report_pad(self, text_or_entry):
        if hasattr(self, "_workspace") and self._workspace:
            if isinstance(text_or_entry, dict):
                self._workspace.append(text_or_entry)
            else:
                from PySide6.QtGui import QTextCursor
                pad = self._workspace.pad
                old_text = pad.toPlainText()
                cursor = pad.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.beginEditBlock()
                cursor.insertText(('\n\n' + '─'*80 + '\n\n' if old_text else '') + str(text_or_entry))
                cursor.endEditBlock()
                pad.setTextCursor(cursor)
                self._workspace.show_pad()

    def highlight_brushed_selection(self, rows=None):
        target_rows = rows if rows is not None else getattr(self, "_brushed_rows", [])
        if not target_rows:
            self.statusBar().showMessage("No observations currently selected.", 4000)
            return
        self.set_ui_mode("minitab")
        self.center_tabs.setCurrentIndex(0)
        self._show_brushed_rows(target_rows[0])
        self.statusBar().showMessage(f"Highlighted {len(target_rows)} observations in worksheet.", 5000)

    def save_brushed_selection(self, rows=None):
        target_rows = rows if rows is not None else getattr(self, "_brushed_rows", [])
        if not target_rows:
            QMessageBox.information(self, "Save Selection", "Please select or brush observations on a graph first.")
            return
        from .connect import ensure_worksheet_identities
        ensure_worksheet_identities(self.presenter.worksheet)
        row_ids = self.presenter.worksheet.metadata.get("row_ids", [])
        selected_ids = [row_ids[r - 1] for r in target_rows if 0 <= r - 1 < len(row_ids)]

        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Save Selection", "Enter a name for this observation selection:", text="Selection_1")
        if ok and name.strip():
            clean_name = name.strip()
            sel_dict = self.presenter.worksheet.metadata.setdefault("named_selections", {})
            sel_dict[clean_name] = {
                "name": clean_name,
                "row_ids": selected_ids,
                "row_indices": sorted(target_rows),
                "count": len(selected_ids),
                "source_sheet": getattr(self.presenter.worksheet, "name", "Data"),
            }
            self.presenter.dirty = True
            self.statusBar().showMessage(f"Saved selection '{clean_name}' with {len(selected_ids)} observations.", 5000)

    def analyze_brushed_selection(self, rows=None):
        target_rows = rows if rows is not None else getattr(self, "_brushed_rows", [])
        if not target_rows:
            QMessageBox.information(self, "Analyze Selection", "Please select or brush observations on a graph first.")
            return

        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QCursor
        menu = QMenu(self)
        menu.setTitle(f"Analyze Selection ({len(target_rows)} rows)")
        menu.addAction(f"Create Subset Worksheet ({len(target_rows)} rows)…", lambda: self.subset_worksheet_from_selection(target_rows))
        menu.addSeparator()
        menu.addAction("Fit Regression on Selection…", lambda: self._fit_regression_on_selection(target_rows))
        menu.addAction("Descriptive Statistics on Selection…", lambda: self._descriptive_stats_on_selection(target_rows))
        menu.addAction("Open Selection in R Workbench…", lambda: self.open_brushed_selection_in_r(target_rows))
        menu.exec(QCursor.pos())

    def _fit_regression_on_selection(self, rows):
        sheet = self.subset_worksheet_from_selection(rows)
        if sheet:
            self.multiple_regression_dialog()

    def _descriptive_stats_on_selection(self, rows):
        sheet = self.subset_worksheet_from_selection(rows)
        if sheet:
            self.display_descriptive_dialog()

    def subset_worksheet_from_selection(self, rows=None):
        target_rows = rows if rows is not None else getattr(self, "_brushed_rows", [])
        if not target_rows:
            QMessageBox.information(self, "Subset Worksheet", "Please select or brush observations on a graph or table first.")
            return None
        from PySide6.QtWidgets import QInputDialog
        src = self.presenter.worksheet
        row_indices_0 = [r - 1 for r in sorted(target_rows) if 0 <= r - 1 < src.row_count]
        if not row_indices_0:
            return None
        def_name = f"{getattr(src, "name", "Data")} (Subset {len(row_indices_0)})"
        new_title, ok = QInputDialog.getText(self, "Subset Worksheet", "New worksheet name:", text=def_name)
        if not ok or not new_title.strip():
            return None
        new_sheet = self.presenter.subset_worksheet(new_title.strip(), "include", row_indices_0)
        self.refresh()
        self.set_ui_mode("minitab")
        self.center_tabs.setCurrentIndex(0)
        self.statusBar().showMessage(f"Created subset worksheet '{getattr(new_sheet, "name", "Subset")}' with {len(row_indices_0)} observations.", 6000)
        return new_sheet

    def open_brushed_selection_in_r(self, rows=None):
        target_rows = rows if rows is not None else getattr(self, "_brushed_rows", [])
        if not target_rows:
            QMessageBox.information(self, "Open Selection in R", "Please select or brush observations on a graph first.")
            return
        idx_list = ", ".join(str(r) for r in sorted(target_rows))
        code = (
            f"# StatCraft Connect: Selected Observations\n"
            f"selected_rows <- c({idx_list})\n"
            f"df_subset <- df[selected_rows, ]\n"
            f"cat(sprintf('Subsetting %d observations from %s into df_subset.\n', nrow(df_subset), '{getattr(self.presenter.worksheet, "name", "Data")}'))\n"
            f"summary(df_subset)\n"
        )
        self.set_ui_mode("r")
        if self.r_workbench:
            self.r_workbench.editor.setPlainText(code)
            self.r_workbench._execute_r(code)
            self.statusBar().showMessage(f"Loaded selection of {len(target_rows)} observations into R Workbench (df_subset)", 5000)

    def recall_named_selection_dialog(self):
        sel_dict = self.presenter.worksheet.metadata.get("named_selections", {})
        if not sel_dict:
            QMessageBox.information(self, "Recall Selection", "No saved selections found in this worksheet. Select points on a graph and choose 'Save Selection' first.")
            return

        from PySide6.QtWidgets import QInputDialog
        names = list(sel_dict.keys())
        item, ok = QInputDialog.getItem(self, "Recall Selection", "Select a saved observation set:", names, 0, False)
        if ok and item:
            val = sel_dict[item]
            if isinstance(val, dict):
                saved_ids = val.get("row_ids", [])
                saved_indices = val.get("row_indices", [])
            else:
                saved_ids = list(val)
                saved_indices = []

            current_ids = self.presenter.worksheet.metadata.get("row_ids", [])
            if current_ids and saved_ids:
                id_map = {rid: idx + 1 for idx, rid in enumerate(current_ids)}
                matched_rows = [id_map[rid] for rid in saved_ids if rid in id_map]
            else:
                matched_rows = saved_indices

            if not matched_rows:
                QMessageBox.warning(self, "Recall Selection", f"None of the observations in '{item}' could be found in the current worksheet.")
                return

            self._brushed_rows = matched_rows
            chart = getattr(self, "_active_chart_widget", None)
            if chart is not None and hasattr(chart, "brushed_rows"):
                chart.brushed_rows = set(matched_rows)
                chart.update()
            frame = getattr(self, "_active_graph_frame", None)
            if frame and hasattr(frame, "update_selection_strip"):
                frame.update_selection_strip(len(matched_rows))
            self.highlight_brushed_selection(matched_rows)
            self.statusBar().showMessage(f"Recalled selection '{item}' with {len(matched_rows)} observations.", 5000)

    def clear_brushed_selection(self):
        self._brushed_rows = []
        chart = getattr(self, "_active_chart_widget", None)
        if chart is not None and hasattr(chart, "brushed_rows"):
            chart.brushed_rows = set()
            chart.update()
        frame = getattr(self, "_active_graph_frame", None)
        if frame and hasattr(frame, "update_selection_strip"):
            frame.update_selection_strip(0)
        self.table.clearSelection()
        self.statusBar().showMessage("Selection cleared", 3000)

    def save_connected_workflow(self, entry):
        if not entry or not entry.get("recipe"):
            QMessageBox.information(self, "Save Workflow", "Select an analysis result with a valid recipe first.")
            return

        from .connect_workflow import create_workflow_from_entry
        from PySide6.QtWidgets import QInputDialog
        def_title = f"Workflow: {entry.get('title', 'Analysis')}"
        title, ok = QInputDialog.getText(self, "Save Reusable Workflow", "Enter workflow title:", text=def_title)
        if not ok or not title.strip():
            return

        wf = create_workflow_from_entry(entry, self.presenter.worksheet, title=title.strip())
        workflows = self.presenter.worksheet.metadata.setdefault("saved_workflows", {})
        workflows[wf.title] = wf.to_dict()
        self.presenter.dirty = True
        self.statusBar().showMessage(f"Saved reusable workflow '{wf.title}' with {len(wf.steps)} step(s).", 5000)

    def replay_saved_workflow_dialog(self):
        workflows = self.presenter.worksheet.metadata.get("saved_workflows", {})
        if not workflows:
            QMessageBox.information(self, "Replay Workflow", "No saved workflows found in this worksheet. Create a model and choose 'Save as Reusable Workflow Recipe' in StatCraft Connect first.")
            return

        from PySide6.QtWidgets import QInputDialog, QMessageBox
        from .connect_workflow import ConnectedWorkflow, validate_workflow_compatibility, replay_workflow
        wf_names = list(workflows.keys())
        chosen, ok = QInputDialog.getItem(self, "Replay Workflow", "Select workflow recipe to replay:", wf_names, 0, False)
        if not ok or not chosen:
            return

        wf = ConnectedWorkflow.from_dict(workflows[chosen])
        compat, col_map, missing, warnings = validate_workflow_compatibility(wf, self.presenter.worksheet)
        if not compat:
            QMessageBox.warning(self, "Workflow Incompatible", f"Cannot replay '{wf.title}' on '{self.presenter.worksheet.name}'.\n\nMissing columns:\n" + "\n".join(f"• {m}" for m in missing))
            return

        try:
            res = replay_workflow(wf, self.presenter.worksheet, self.presenter)
            self.refresh()
            if res.get("entries"):
                self.show_result(res["entries"][-1])

            shifts = res.get("convergence", {}).get("shifts", [])
            shift_lines = []
            for s in shifts:
                b_val = f"{s.get('baseline', 0):.4f}" if isinstance(s.get('baseline'), (int, float)) else str(s.get('baseline'))
                c_val = f"{s.get('current', 0):.4f}" if isinstance(s.get('current'), (int, float)) else str(s.get('current'))
                shift_lines.append(f"• {s['metric']}: Baseline {b_val} -> Current {c_val} ({s['status']})")
            shift_text = "\n".join(shift_lines) if shift_lines else "Model converged consistently."

            QMessageBox.information(
                self,
                "Workflow Replay Complete",
                f"Successfully replayed '{wf.title}' on '{self.presenter.worksheet.name}'.\n\nConvergence Summary:\n{shift_text}"
            )
            self.statusBar().showMessage(f"Replayed workflow '{wf.title}' successfully.", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "Replay Failed", f"Workflow execution encountered an error:\n{exc}")


    def _show_output_context_menu(self, global_pos, entry=None):
        if (entry or self.selected_entry) is None:
            return
        menu = self.build_output_context_menu(entry)
        menu.exec(global_pos)

    def _show_navigator_item_menu(self, pos):
        item = self.navigator.itemAt(pos)
        if item is None:
            self._show_navigator_menu()
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict):
            return
        if data.get("kind") == "sheet":
            self._select_sheet(data["index"])
            menu = QMenu(self)
            menu.addAction(self.new_sheet_action)
            menu.addSeparator()
            menu.addAction(self.rename_sheet_action)
            menu.addAction(self.duplicate_sheet_action)
            menu.addAction(self.delete_sheet_action)
            menu.exec(self.navigator.viewport().mapToGlobal(pos))
            return
        entry = data.get("entry")
        if entry is not None:
            self.show_result(entry)
            self._show_output_context_menu(self.navigator.viewport().mapToGlobal(pos), entry=entry)

    # --- Dialogs & Handlers for Worksheet and Output Context Menu Actions ---

    def replace_dialog(self):
        self._commit_editor()
        dialog = QDialog(self); dialog.setWindowTitle("Replace"); dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog); form = QFormLayout()
        find_edit = QLineEdit(self._find_state.get("query", ""))
        replace_edit = QLineEdit()
        form.addRow("Find what:", find_edit)
        form.addRow("Replace with:", replace_edit)
        layout.addLayout(form)
        match_case = QCheckBox("Match case"); match_case.setChecked(self._find_state.get("match_case", False))
        whole_word = QCheckBox("Match whole word only"); whole_word.setChecked(self._find_state.get("whole_word", False))
        layout.addWidget(match_case); layout.addWidget(whole_word)
        status_lbl = label("", "secondary"); layout.addWidget(status_lbl)
        btn_row = QHBoxLayout(); btn_row.addStretch()
        replace_one_btn = QPushButton("Replace")
        replace_all_btn = QPushButton("Replace All"); replace_all_btn.setDefault(True)
        close_btn = QPushButton("Close")
        btn_row.addWidget(replace_one_btn); btn_row.addWidget(replace_all_btn); btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        def do_replace(all_matches):
            try:
                count = self.presenter.replace_cells(
                    find_edit.text(), replace_edit.text(),
                    match_case=match_case.isChecked(),
                    whole_word=whole_word.isChecked(),
                    replace_all=all_matches,
                    start_row=self.page * self.PAGE_SIZE + max(0, self.table.currentRow()),
                    start_col=max(0, self.table.currentColumn()),
                )
                self.refresh()
                status_lbl.setText(f"Replaced {count} cell(s).")
            except ValueError as exc:
                status_lbl.setText(str(exc))
        replace_one_btn.clicked.connect(lambda: do_replace(False))
        replace_all_btn.clicked.connect(lambda: do_replace(True))
        close_btn.clicked.connect(dialog.accept)
        dialog.exec()

    def cell_comment_dialog(self):
        self._commit_editor()
        r = self.page * self.PAGE_SIZE + max(0, self.table.currentRow())
        c = max(0, min(self.table.currentColumn(), len(self.presenter.worksheet.columns) - 1))
        col = self.presenter.worksheet.columns[c]
        existing = col.metadata.get("cell_comments", {}).get(str(r), "")
        text, accepted = QInputDialog.getMultiLineText(self, f"Cell Comment (Row {r + 1}, C{c + 1})", "Comment:", existing)
        if accepted:
            self._call(lambda: self.presenter.set_cell_comment(r, c, text))

    def format_column_dialog(self):
        self._commit_editor()
        c = max(0, min(self.table.currentColumn(), len(self.presenter.worksheet.columns) - 1))
        col = self.presenter.worksheet.columns[c]
        fmt = col.metadata.get("format", {})
        dialog = QDialog(self); dialog.setWindowTitle(f"Format Column — C{c + 1} ({col.name})"); dialog.setMinimumWidth(380)
        layout = QVBoxLayout(dialog); form = QFormLayout()
        mode_combo = QComboBox()
        modes = [("Automatic", "automatic"), ("Fixed decimal", "fixed"), ("Currency", "currency"), ("Percent", "percent"), ("Scientific", "scientific")]
        for title, key in modes:
            mode_combo.addItem(title, key)
        cur_mode = fmt.get("mode", "automatic")
        mode_combo.setCurrentIndex(next((i for i, (_, k) in enumerate(modes) if k == cur_mode), 0))
        dec_edit = QLineEdit(str(fmt.get("decimals", 2)))
        form.addRow("Format type:", mode_combo)
        form.addRow("Decimal places (0–12):", dec_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        def accept_fmt():
            try:
                decimals = int(dec_edit.text().strip() or "2")
            except ValueError:
                decimals = 2
            self._call(lambda: self.presenter.set_column_format(c, mode_combo.currentData(), decimals))
            dialog.accept()
        buttons.accepted.connect(accept_fmt); buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def column_description_dialog(self):
        self._commit_editor()
        c = max(0, min(self.table.currentColumn(), len(self.presenter.worksheet.columns) - 1))
        col = self.presenter.worksheet.columns[c]
        existing = col.metadata.get("description", "")
        text, accepted = QInputDialog.getMultiLineText(self, f"Column Description — C{c + 1} ({col.name})", "Description:", existing)
        if accepted:
            self._call(lambda: self.presenter.set_column_description(c, text))

    def column_value_order_dialog(self):
        self._commit_editor()
        c = max(0, min(self.table.currentColumn(), len(self.presenter.worksheet.columns) - 1))
        col = self.presenter.worksheet.columns[c]
        order_meta = col.metadata.get("value_order", {})
        if col.kind != 'text':
            QMessageBox.information(
                self,
                "Value Order",
                f"Value Order customization is designed for categorical text columns.\n\n"
                f"Column C{c + 1} ({col.name}) is a '{col.kind}' column, which orders naturally."
            )
            return

        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QRadioButton, QListWidget,
            QListWidgetItem, QPushButton, QDialogButtonBox, QLabel, QGroupBox
        )

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Value Order — C{c + 1} ({col.name})")
        dialog.setMinimumWidth(440)
        layout = QVBoxLayout(dialog)

        rb_alpha = QRadioButton("Alphabetical order (default)")
        rb_first = QRadioButton("Order of occurrence in worksheet")
        rb_custom = QRadioButton("User-specified order")

        mode = order_meta.get("mode", "alphabetical")
        rb_alpha.setChecked(mode == "alphabetical")
        rb_first.setChecked(mode == "occurrence")
        rb_custom.setChecked(mode == "custom")

        layout.addWidget(rb_alpha)
        layout.addWidget(rb_first)
        layout.addWidget(rb_custom)

        observed = list(dict.fromkeys(v for v in col.values if v is not None and str(v).strip()))
        custom_saved = order_meta.get("values", [])

        list_group = QGroupBox("Category Ordering")
        list_layout = QHBoxLayout(list_group)

        order_list = QListWidget()
        order_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        def populate_list(vals):
            order_list.clear()
            for v in vals:
                order_list.addItem(QListWidgetItem(str(v)))
            if order_list.count() > 0:
                order_list.setCurrentRow(0)

        if mode == "custom" and custom_saved:
            unlisted = sorted([v for v in observed if v not in custom_saved], key=lambda x: (x.casefold(), x))
            populate_list(custom_saved + unlisted)
        elif mode == "occurrence":
            populate_list(observed)
        else:
            populate_list(sorted(observed, key=lambda x: (x.casefold(), x)))

        list_layout.addWidget(order_list, 1)

        btn_box = QVBoxLayout()
        btn_top = QPushButton("Move to Top")
        btn_up = QPushButton("Move Up")
        btn_down = QPushButton("Move Down")
        btn_bottom = QPushButton("Move to Bottom")
        btn_box.addWidget(btn_top)
        btn_box.addWidget(btn_up)
        btn_box.addWidget(btn_down)
        btn_box.addWidget(btn_bottom)
        btn_box.addStretch()
        list_layout.addLayout(btn_box)

        layout.addWidget(list_group)

        def move_row(delta):
            row = order_list.currentRow()
            if row < 0: return
            target_row = max(0, min(order_list.count() - 1, row + delta))
            if target_row == row: return
            item = order_list.takeItem(row)
            order_list.insertItem(target_row, item)
            order_list.setCurrentRow(target_row)
            rb_custom.setChecked(True)

        def move_extreme(top):
            row = order_list.currentRow()
            if row < 0: return
            target_row = 0 if top else order_list.count() - 1
            if target_row == row: return
            item = order_list.takeItem(row)
            order_list.insertItem(target_row, item)
            order_list.setCurrentRow(target_row)
            rb_custom.setChecked(True)

        btn_top.clicked.connect(lambda: move_extreme(True))
        btn_bottom.clicked.connect(lambda: move_extreme(False))
        btn_up.clicked.connect(lambda: move_row(-1))
        btn_down.clicked.connect(lambda: move_row(1))

        def on_mode_toggled():
            if rb_alpha.isChecked():
                populate_list(sorted(observed, key=lambda x: (x.casefold(), x)))
            elif rb_first.isChecked():
                populate_list(observed)

        rb_alpha.toggled.connect(on_mode_toggled)
        rb_first.toggled.connect(on_mode_toggled)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        error = label('', 'error')
        layout.addWidget(error)

        def accept_order():
            chosen = "custom" if rb_custom.isChecked() else "occurrence" if rb_first.isChecked() else "alphabetical"
            vals = [order_list.item(i).text() for i in range(order_list.count())]
            try:
                self.presenter.set_column_value_order(c, chosen, vals)
            except ValueError as exc:
                error.setText(str(exc))
                return
            self.refresh()
            dialog.accept()

        buttons.accepted.connect(accept_order)
        buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def column_width_dialog(self):
        c = max(0, min(self.table.currentColumn(), self.table.columnCount() - 1))
        cur_w = self.table.columnWidth(c)
        val, accepted = QInputDialog.getInt(self, "Column Width", f"Width in pixels for C{c + 1}:", cur_w, 38, 400)
        if accepted:
            targets = sorted(self._selected_columns) if self._selected_columns else [c]
            for idx in targets:
                self.table.setColumnWidth(idx, val)
                self.column_names.setColumnWidth(idx, val)

    def standard_column_width_dialog(self):
        cur_w = self.table.horizontalHeader().defaultSectionSize()
        val, accepted = QInputDialog.getInt(self, "Standard Column Width", "Standard width in pixels for all columns:", cur_w, 38, 400)
        if accepted:
            self.table.horizontalHeader().setDefaultSectionSize(val)
            self.column_names.horizontalHeader().setDefaultSectionSize(val)
            for idx in range(self.table.columnCount()):
                self.table.setColumnWidth(idx, val)
                self.column_names.setColumnWidth(idx, val)

    def hide_selected_columns(self):
        targets = set(self._column_targets())
        if len(targets) < len(self.presenter.worksheet.columns):
            self._hidden_columns |= targets
            self.refresh()

    def unhide_all_columns(self):
        self._hidden_columns.clear()
        self.refresh()

    def conditional_formatting_dialog(self, rule_type, title):
        self._commit_editor()
        c = max(0, min(self.table.currentColumn(), len(self.presenter.worksheet.columns) - 1))
        dialog = QDialog(self); dialog.setWindowTitle(f"Conditional Formatting — {title}"); dialog.setMinimumWidth(380)
        layout = QVBoxLayout(dialog); form = QFormLayout()
        p1_edit = QLineEdit("0")
        p2_edit = QLineEdit("10")
        form.addRow("Value:" if rule_type != "between" else "Minimum:", p1_edit)
        if rule_type == "between":
            form.addRow("Maximum:", p2_edit)
        color_combo = QComboBox()
        for label_text, hex_code in (("Light Red Fill", "#f8d7da"), ("Light Green Fill", "#d4edda"), ("Light Yellow Fill", "#fff3cd")):
            color_combo.addItem(label_text, hex_code)
        form.addRow("Style:", color_combo)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        def accept_rule():
            self._call(lambda: self.presenter.apply_conditional_formatting(c, rule_type, p1_edit.text().strip(), p2_edit.text().strip(), color_combo.currentData()))
            dialog.accept()
        buttons.accepted.connect(accept_rule); buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def subset_worksheet_dialog(self):
        self._commit_editor()
        dialog = QDialog(self); dialog.setWindowTitle("Subset Worksheet"); dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog); form = QFormLayout()
        name_edit = QLineEdit(self.presenter.worksheet.name + " Subset")
        mode_combo = QComboBox()
        mode_combo.addItem("Include rows", "include")
        mode_combo.addItem("Exclude rows", "exclude")
        rows_edit = QLineEdit("1:5")
        form.addRow("New worksheet name:", name_edit)
        form.addRow("Include or exclude:", mode_combo)
        form.addRow("Row numbers (e.g., 1 3 5 or 1:5):", rows_edit)
        layout.addLayout(form)
        err = label("", "error"); layout.addWidget(err)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        def accept_subset():
            try:
                rows = []
                for part in rows_edit.text().replace(",", " ").split():
                    if ":" in part:
                        a, b = part.split(":", 1)
                        rows.extend(range(int(a) - 1, int(b)))
                    else:
                        rows.append(int(part) - 1)
                self.presenter.subset_worksheet(name_edit.text().strip() or None, mode_combo.currentData(), rows)
            except ValueError as exc:
                err.setText(str(exc)); return
            dialog.accept(); self.refresh()
        buttons.accepted.connect(accept_subset); buttons.rejected.connect(dialog.reject)
        dialog.exec()

    def _office_snapshot(self, entry=None):
        from .office_export import OfficeSnapshot, report_text
        if not isinstance(entry,dict) and self.result_tabs.currentWidget() is self._report_pad_editor:
            return OfficeSnapshot('ReportPad',self._report_pad_editor.toPlainText())
        from PySide6.QtCore import QBuffer, QIODevice
        self._commit_editor()
        if not self.graph_options_pane.flush(): return None
        target = entry if isinstance(entry, dict) else self.selected_entry
        if target is None: return None
        if target is not self.selected_entry: self.show_result(target)
        png = b''
        frame = getattr(self, '_active_graph_frame', None)
        if frame is not None:
            buffer = QBuffer(); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            if not frame.capture().save(buffer, 'PNG'): raise ValueError('Unable to capture the graph.')
            png = bytes(buffer.data()); buffer.close()
        return OfficeSnapshot(target.get('title', 'Output'), report_text(target), png)

    def _export_office(self, kind, entry=None):
        from .office_export import export_docx, export_pptx
        import re
        try:
            snapshot = self._office_snapshot(entry)
            if snapshot is None:
                self.statusBar().showMessage('Select an output to export', 5000); return
            suffix = '.docx' if kind == 'Word' else '.pptx'
            title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', snapshot.title).strip(' .')[:120] or 'Output'
            path, _ = QFileDialog.getSaveFileName(self, 'Export to '+kind, title+suffix, kind+' files (*'+suffix+')')
            if not path: return
            if not path.lower().endswith(suffix): path += suffix
            if kind == 'Word': export_docx(path, snapshot)
            else: export_pptx(path, snapshot)
            self.statusBar().showMessage('Saved '+kind+' file to '+str(path), 6000)
        except (ValueError, OSError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Office export', str(exc))

    def send_output_to_word(self, entry=None):
        self._export_office('Word', entry)

    def send_output_to_powerpoint(self, entry=None):
        self._export_office('PowerPoint', entry)

    def send_output_to_report(self, entry=None):
        target=entry if isinstance(entry,dict) else self.selected_entry
        if target is not None:
            self._workspace.append(target)
            self.statusBar().showMessage('Appended output to ReportPad',5000)

    def copy_output_graph(self, entry=None):
        target = entry or self.selected_entry
        if target is None:
            return
        if target is not self.selected_entry:self.show_result(target)
        self.graph_options_pane.flush()
        chart = getattr(self, "_active_graph_frame", None)
        if chart is not None:
            pix = chart.capture()
            if not pix.isNull():
                QApplication.clipboard().setPixmap(pix)
                self.statusBar().showMessage("Copied graph image to clipboard", 5000)
                return
        current_widget = self.result_tabs.currentWidget()
        if current_widget is not None:
            pix = current_widget.grab()
            if not pix.isNull():
                QApplication.clipboard().setPixmap(pix)
                self.statusBar().showMessage("Copied output image to clipboard", 5000)
                return
        QApplication.clipboard().setText(format_entry(target))

    def make_similar_graph(self, entry=None):
        target = entry or self.selected_entry
        if target is None:return
        self._commit_editor()
        if not self.graph_options_pane.flush():return
        from .similar_graph_dialog import create_similar_dialog,run_similar_graphs,supports_similar
        if not supports_similar(target):
            self.statusBar().showMessage('Make Similar Graph is available for supported tracked graph recipes.',8000);return
        dialog=create_similar_dialog(self,self.presenter.result_worksheet(target),target)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            created=self._call(lambda:run_similar_graphs(self.presenter,target,dialog.recipes(),appearance=dialog.appearance_settings()))
            if created:self.show_result(created[-1])

    def edit_graph_dialog(self, entry=None):
        target = entry or self.selected_entry
        from .modern_charts import supported
        if target is None or not supported(target):return
        if target is not self.selected_entry:self.show_result(target)
        self.graph_options_pane.load_entry(target)
        self.graph_options_pane.show()
        self.splitter.setSizes([self.navigator_container.width(),max(300,self.width()-self.navigator_container.width()-330),330])
        self.graph_options_pane.controls['title'].setFocus()

    def refit_native_model(self,entry=None):
        entry=entry or self.selected_entry
        if entry is None:return
        self._commit_editor();self.page=0
        return self._call(lambda:self.presenter.refit_native_model(entry),result=True)

    def _native_graph_switched(self,entry,chart,index):
        previous=entry.get('_native_graph_index',0)
        pane=self.graph_options_pane
        if pane.bound_entry is entry and not pane.flush():
            with QSignalBlocker(chart):chart.select_graph(previous)
            return
        entry['_native_graph_index']=index
        frame=getattr(self,'_active_graph_frame',None)
        if frame is not None and frame.entry is entry:frame.apply_appearance()
        if pane.bound_entry is entry:
            # Stop the old timer before loading controls for the new gallery page.
            pane.bound_entry=None;pane.load_entry(entry)

    def native_graph_appearance(self,entry=None):
        entry=entry or self.selected_entry
        if entry is None or entry.get('result',{}).get('analysis')!='native_saved_output':return
        if not self.graph_options_pane.flush():return
        if entry is not self.selected_entry:self.show_result(entry)
        chart=self._active_chart_widget
        from .native_graph_appearance import NativeGraphAppearanceDialog
        dialog=NativeGraphAppearanceDialog(chart.current_view(),any(p.get('kind')=='surface' for p in chart.panels),self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self._call(lambda:self.presenter.update_native_graph_view(entry,chart.graph_index,dialog.settings))

    def close_graph_options(self):
        self.graph_options_pane.flush();self.graph_options_pane.hide()

    def _graph_object_selected(self,target):
        chart=getattr(self,'_active_chart_widget',None)
        if chart is None:return
        text=next((obj['label'] for obj in chart.editable_objects() if obj['target']==target),'')
        self.statusBar().showMessage('Selected: '+text if text else 'Ready')

    def _activate_graph_object(self,entry,target):
        if not target or target.startswith(('cad_', 'viewcube_')):
            return
        if entry.get('origin') != 'statcraft' and entry.get('result', {}).get('analysis') != 'native_saved_output':
            return
        if target.endswith(':axis'):self.edit_graph_scales(entry)
        else:self.edit_graph_object(entry,target)

    def edit_graph_annotation(self,entry,name):
        self.edit_graph_dialog(entry)
        field=self.graph_options_pane.controls[name];field.setFocus();field.selectAll()

    def edit_graph_scales(self,entry=None):
        self.edit_graph_dialog(entry)
        pane=self.graph_options_pane;pane.more_button.setChecked(True)
        pane.controls['x_min'].setFocus()

    def edit_graph_object(self,entry=None,target=None):
        entry=entry or self.selected_entry
        if entry is None:return
        if not self.graph_options_pane.flush():return
        if entry is not self.selected_entry:self.show_result(entry)
        chart=getattr(self,'_active_chart_widget',None)
        if chart is None:return
        objects=chart.editable_objects()
        if not objects:return
        from .graph_object_dialog import GraphObjectDialog
        styles=chart.current_styles() if entry.get('result',{}).get('analysis')=='native_saved_output' else entry.get('graph_styles',{})
        dialog=GraphObjectDialog(objects,styles,target or chart.selected_object,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self._call(lambda:self.presenter.update_graph_styles(entry,dialog.styles()))

    def histogram_options_dialog(self,entry=None):
        entry=entry or self.selected_entry
        if entry is None:return
        if not self.graph_options_pane.flush():return
        if entry is not self.selected_entry:self.show_result(entry)
        from .histogram_options_dialog import HistogramOptionsDialog
        dialog=HistogramOptionsDialog(entry,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self._call(lambda:self.presenter.update_histogram_settings(entry,dialog.settings()))
            if self.graph_options_pane.bound_entry is entry:self.graph_options_pane.load_entry(entry)

    def _apply_graph_settings(self,entry,settings):
        self.presenter.update_graph_presentation(entry,settings)
        if entry is self.selected_entry and getattr(self,'_active_graph_frame',None) is not None:
            self._active_graph_frame.apply(settings)
        if not self.windowTitle().endswith(' *'):self.setWindowTitle(self.windowTitle()+' *')
        return True

    def panel_graph_dialog(self, entry=None):
        entry=entry or self.selected_entry
        if entry is None:return
        if entry.get('source_unavailable'):
            self.statusBar().showMessage(entry['source_unavailable'],12000);return
        if not self.graph_options_pane.flush():return
        from .panel_graph_dialog import PanelGraphDialog
        sheet=self.presenter.result_worksheet(entry)
        dialog=PanelGraphDialog(sheet,entry,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            settings=dialog.settings()
            from .compositions import appearance_from_entry
            appearance=appearance_from_entry(entry)
            def create():
                if self.presenter.native_project is not None:
                    self.presenter.select_worksheet(next(i for i,s in enumerate(self.presenter.native_project.worksheets) if s is sheet))
                return self.presenter.panel_graph(**settings,source_appearance=appearance)
            self._call(create,result=True)

    def brush_points_dialog(self, entry=None):
        self._commit_editor();entry=entry or self.selected_entry
        if entry is None:return
        if entry is not self.selected_entry:self.show_result(entry)
        chart=getattr(self,'_active_chart_widget',None)
        if chart is None or not hasattr(chart,'set_brushing'):return
        if self.presenter.result_stale(entry) is not False:
            self.statusBar().showMessage('Rerun this graph with current data before brushing its worksheet rows.',12000);return
        chart.set_brushing(not chart.is_brushing)
        self.statusBar().showMessage('Brush points: click or drag a rectangle; Ctrl adds rows; Esc stops brushing.' if chart.is_brushing else 'Brushing stopped',12000)
        chart.setFocus()

    def _receive_brushed_rows(self,entry,rows):
        try:rows=self.presenter.validate_brushed_rows(entry,rows)
        except ValueError as exc:
            chart=getattr(self,'_active_chart_widget',None)
            if chart is not None and hasattr(chart,'brushed_rows'):chart.brushed_rows=set();chart.update()
            self.statusBar().showMessage(str(exc),12000);return
        self._brushed_entry=entry;self._brushed_rows=rows
        frame = getattr(self, "_active_graph_frame", None)
        if frame and hasattr(frame, "update_selection_strip"):
            frame.update_selection_strip(len(rows))
        self._show_brushed_rows(rows[0] if rows else None)
        self.statusBar().showMessage(str(len(rows))+' brushed rows'+(': '+', '.join(map(str,rows[:20])) if rows else ''),12000)

    def _show_brushed_rows(self,target_row=None):
        entry=getattr(self,'_brushed_entry',None)
        if entry is None:return
        source=self.presenter.result_worksheet(entry)
        if self.presenter.native_project is not None:
            self.presenter.select_worksheet(next(i for i,sheet in enumerate(self.presenter.native_project.worksheets) if sheet is source))
        if target_row is not None:self.page=(target_row-1)//self.PAGE_SIZE;self._navigation_row=target_row-1
        self.refresh();blocker=QSignalBlocker(self.table)
        if target_row is not None:self.table.setCurrentCell((target_row-1)%self.PAGE_SIZE,0)
        self.table.clearSelection()
        for row in getattr(self,'_brushed_rows',[]):
            local=row-1-self.page*self.PAGE_SIZE
            if 0<=local<self.table.rowCount():self.table.setRangeSelected(QTableWidgetSelectionRange(local,0,local,self.table.columnCount()-1),True)
        del blocker;self._sync_selection_highlights()
        if self.table.currentItem():self.table.scrollToItem(self.table.currentItem())

    def go_to_brushed_row(self,direction):
        entry=getattr(self,'_brushed_entry',None);rows=getattr(self,'_brushed_rows',[])
        if entry is None or not rows:return
        try:self.presenter.validate_brushed_rows(entry,rows)
        except ValueError as exc:self.statusBar().showMessage(str(exc),12000);return
        source=self.presenter.result_worksheet(entry)
        current=self.page*self.PAGE_SIZE+max(0,self.table.currentRow())+1
        if source is not self.presenter.worksheet:target=rows[0] if direction>0 else rows[-1]
        else:
            candidates=[row for row in rows if row>current] if direction>0 else [row for row in rows if row<current]
            if not candidates:self.statusBar().showMessage('No further brushed row in this direction.',4000);return
            target=candidates[0] if direction>0 else candidates[-1]
        self._show_brushed_rows(target)

    def layout_tool_dialog(self, entry=None):
        if not self.graph_options_pane.flush():return
        from .graph_layouts import layout_eligible
        from .graph_layout_dialog import GraphLayoutDialog
        current=entry or self.selected_entry
        editing=current if current is not None and current.get('result',{}).get('graph')=='graph_layout' else None
        entries=[item for item in self.presenter.history if layout_eligible(item)]
        if not entries and editing is None:
            QMessageBox.information(self,'Layout Tool','Create at least one graph first.');return
        dialog=GraphLayoutDialog(entries,self,layout=editing)
        if editing is None and current is not None and layout_eligible(current):
            index=next((i for i,item in enumerate(dialog.entries) if item is current),None)
            if index is not None:
                item=next((dialog.available.item(i) for i in range(dialog.available.count()) if dialog.available.item(i).data(Qt.ItemDataRole.UserRole)==index),None)
                if item is not None:item.setSelected(True);dialog.add_entries()
            count=max(1,len(dialog.selected_entries()));columns=math.ceil(math.sqrt(count))
            dialog.columns.setValue(columns);dialog.rows.setValue(math.ceil(count/columns))
        if dialog.exec()==QDialog.DialogCode.Accepted:
            settings=dialog.settings();selected=dialog.selected_entries()
            if editing is None:self._call(lambda:self.presenter.graph_layout(selected,**settings),result=True)
            else:
                self._call(lambda:self.presenter.update_graph_layout(editing,selected,**settings))
                self.show_result(editing)

    def reset_graph_size(self):
        self.set_zoom(100)
        if self.selected_entry is not None:
            self.show_result(self.selected_entry)
        self.statusBar().showMessage("Graph size reset to default (100%)", 4000)

    def save_graph_as(self, entry=None):
        target = entry or self.selected_entry
        if target is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Graph As", target.get("title", "Graph") + ".png", "PNG Image (*.png);;Text Report (*.txt)")
        if not path:
            return
        if target is not self.selected_entry:self.show_result(target)
        self.graph_options_pane.flush()
        chart = getattr(self, "_active_graph_frame", None)
        if Path(path).suffix.lower() == ".png" and chart is not None:
            chart.capture().save(path, "PNG")
        else:
            Path(path).write_text(format_entry(target), encoding="utf-8")
        self.statusBar().showMessage("Saved graph to " + str(path), 6000)

    def rename_output_dialog(self, entry=None):
        target = entry or self.selected_entry
        if target is None:
            return
        new_title, accepted = QInputDialog.getText(self, "Rename Output", "Title:", text=target.get("title", ""))
        if accepted and new_title.strip():
            self._call(lambda: self.presenter.rename_result(target, new_title))
            self.show_result(target)

    def delete_selected_output(self, entry=None):
        target = entry if isinstance(entry, dict) else self.selected_entry
        if target is None:
            return
        if self.graph_options_pane.bound_entry is target:
            self.graph_options_pane.flush();self.graph_options_pane.load_entry(None);self.graph_options_pane.hide()
        self.presenter.delete_result(target)
        if self.selected_entry is target:
            remaining = [e for e in self.presenter.history if e.get("origin") == "statcraft" or not str(e.get("title", "")).startswith("Native command ")]
            if remaining:
                self.show_result(remaining[-1])
            else:
                self.selected_entry = None
                self._show_welcome()
                self.refresh()
        else:
            self.refresh()

    def rerun_selected(self):
        self._commit_editor()
        entry = self.selected_entry
        if entry is None:
            item = self.navigator.currentItem(); data = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
            if isinstance(data, dict) and data.get("kind") == "result": entry = data["entry"]
        if entry is None: QMessageBox.information(self, "Rerun", "Select a supported result first."); return None
        return self._call(lambda: self.presenter.rerun_result(entry), result=True)

    def check_for_updates_dialog(self):
        from .updater_dialog import CheckForUpdatesDialog
        dlg = CheckForUpdatesDialog(self)
        dlg.exec()

    def _check_startup_updates(self):
        import os
        if getattr(self, "sandbox_mode", False) or os.environ.get("STATCRAFT_TESTING") or "unittest" in sys.modules or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        try:
            from .updater_dialog import UpdateCheckWorker
            from .updater import read_install_metadata, STATCRAFT_VERSION
            installed = read_install_metadata()
            cur_v = installed.get("version", STATCRAFT_VERSION)
            self._startup_worker = UpdateCheckWorker(cur_v)
            self._startup_worker.finished.connect(self._on_startup_update_finished)
            self._startup_worker.start()
        except Exception:
            pass

    def _on_startup_update_finished(self, info: dict):
        if not info or not info.get("update_available"):
            return

        # Only interrupt/prompt user automatically on startup if this is a MAJOR version upgrade (e.g. 104 -> 105).
        # Minor patches, internal tweaks, and small changes never force existing users to reinstall.
        from .updater import is_major_update
        cur_v = info.get("current_version", "")
        latest_v = info.get("latest_version", "")
        if not is_major_update(cur_v, latest_v):
            return

        name = info.get("release_name") or f"StatCraft v{latest_v}"
        reply = QMessageBox.question(
            self,
            "StatCraft Major Update Available",
            f"A major new version of StatCraft is available: {name}\n\n"
            f"Would you like to review update details and install now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.check_for_updates_dialog()

    def about(self):
        from .updater import STATCRAFT_VERSION
        QMessageBox.information(
            self,
            "About StatCraft",
            f"StatCraft v{STATCRAFT_VERSION}\n\n"
            "The Modern, Native Statistical Engine for Engineers & Scientists.\n"
            "Open-source alternative to both Minitab® and JMP® with R Workbench.\n\n"
            "• Direct .MPX/.MTW and .JMP/.JSL file compatibility\n"
            "• JMP Fit Y by X (Bivariate, Means Diamonds, Contingency Mosaic)\n"
            "• Interactive Prediction Profiler with Desirability Optimization\n"
            "• Full DOE: Definitive Screening (DSD), Custom D-Optimal, RSM & Factorial\n"
            "• Six Sigma Process Capability Sixpack & SPC Control Charts\n"
            "• Positron-Style R Data Science Workbench\n"
            "• 100% Local, Offline & Zero Cloud Lock-in\n\n"
            "Co-developed with Antigravity (Google DeepMind) and Codex (OpenAI)."
        )




    def _get_entry_r_script(self, entry=None) -> tuple[str, str]:
        target = entry or self.selected_entry
        if target is None and self.presenter.history:
            target = self.presenter.history[-1]
        ws = self.presenter.worksheet
        from .connect_r import generate_dataframe_init_code, build_self_contained_r_script
        if target is not None:
            conn_dict = target.get("connected_analysis")
            if not conn_dict:
                from .connect import create_connected_analysis_from_entry
                try:
                    conn_obj = create_connected_analysis_from_entry(target, ws)
                    if conn_obj:
                        conn_dict = conn_obj.to_dict()
                        target["connected_analysis"] = conn_dict
                except Exception:
                    conn_dict = None
            if conn_dict and conn_dict.get("r_script"):
                title = conn_dict.get("title", target.get("title", "Analysis"))
                full_script = build_self_contained_r_script(conn_dict["r_script"], ws, title)
                return full_script, title
        code = generate_dataframe_init_code(ws)
        return code, f"Worksheet: {ws.name}"

    def copy_active_r_script(self):
        script, title = self._get_entry_r_script()
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(script)
        if self.statusBar():
            self.statusBar().showMessage(f"✓ Copied reproducible Base R script for '{title}' to clipboard!", 5000)

    def view_active_r_code(self):
        script, title = self._get_entry_r_script()
        from .connect_hub import ViewRCodeDialog
        dlg = ViewRCodeDialog(self, script, title=f"R Code: {title}")
        dlg.exec()

    def export_active_r_file(self):
        script, title = self._get_entry_r_script()
        clean = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in title).strip("_")
        path, _ = QFileDialog.getSaveFileName(self, "Export R Script", f"{clean}_script.R", "R Scripts (*.R *.r)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(script)
                if self.statusBar():
                    self.statusBar().showMessage(f"✓ Saved R script to {path}", 5000)
            except OSError as err:
                QMessageBox.critical(self, "Export Error", f"Failed to save R script:\n{err}")

    def copy_entry_r_script(self, entry):
        script, title = self._get_entry_r_script(entry)
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(script)
        if self.statusBar():
            self.statusBar().showMessage(f"✓ Copied reproducible Base R script for '{title}' to clipboard!", 5000)

    def view_entry_r_code(self, entry):
        script, title = self._get_entry_r_script(entry)
        from .connect_hub import ViewRCodeDialog
        dlg = ViewRCodeDialog(self, script, title=f"R Code: {title}")
        dlg.exec()

    def export_entry_r_file(self, entry):
        script, title = self._get_entry_r_script(entry)
        clean = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in title).strip("_")
        path, _ = QFileDialog.getSaveFileName(self, "Export R Script", f"{clean}_script.R", "R Scripts (*.R *.r)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(script)
                if self.statusBar():
                    self.statusBar().showMessage(f"✓ Saved R script to {path}", 5000)
            except OSError as err:
                QMessageBox.critical(self, "Export Error", f"Failed to save R script:\n{err}")

    def export_worksheet_r_dataframe(self):
        from .connect_r import generate_dataframe_init_code
        ws = self.presenter.worksheet
        script = generate_dataframe_init_code(ws)
        clean = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in ws.name).strip("_")
        path, _ = QFileDialog.getSaveFileName(self, "Export Worksheet to R Data Frame", f"{clean}_dataframe.R", "R Scripts (*.R *.r)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(script)
                if self.statusBar():
                    self.statusBar().showMessage(f"✓ Saved worksheet R script to {path}", 5000)
            except OSError as err:
                QMessageBox.critical(self, "Export Error", f"Failed to save R script:\n{err}")

def main():
    sandbox_mode = "--sandbox" in sys.argv
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("StatCraft"); app.setOrganizationName("StatCraft")
    from .startup import start_window, dispose_startup
    start_window(app, lambda: ModernWindow(sandbox_mode=sandbox_mode), sys.argv[1:])
    result=app.exec()
    dispose_startup(app)
    return result


if __name__ == "__main__": raise SystemExit(main())

