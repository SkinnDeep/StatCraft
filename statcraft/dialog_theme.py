"""Shared light/dark theme helpers for StatCraft QDialog subclasses and gallery choosers."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget


def is_dark_active(widget: QWidget | None = None) -> bool:
    """Return True when dark mode is enabled on the owning window or Qt application."""
    if widget is not None:
        try:
            win = widget.window()
            if win is not None and hasattr(win, "_dark_mode"):
                return bool(win._dark_mode)
        except Exception:
            pass
    app = QApplication.instance()
    if app is not None:
        try:
            return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except Exception:
            return False
    return False


def dialog_stylesheet(dark: bool) -> str:
    """Return consistent dark/light QSS matching ProcedureDialog."""
    if dark:
        return """
            QDialog {
                background-color: #18181b;
                color: #f4f4f5;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QLabel {
                color: #f4f4f5;
                font-size: 9pt;
            }
            QLabel#secondary {
                color: #a1a1aa;
                font-size: 8.5pt;
                padding-bottom: 4px;
            }
            QLabel#error {
                color: #f87171;
                background-color: #450a0a;
                border: 1px solid #7f1d1d;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 8.5pt;
                font-weight: 500;
            }
            QGroupBox {
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
            QListWidget, QTableWidget {
                background-color: #1f1f23;
                color: #f4f4f5;
                border: 1px solid #27272a;
                border-radius: 6px;
                font-family: 'Segoe UI', -apple-system, sans-serif;
                font-size: 8.5pt;
                padding: 4px;
            }
            QListWidget::item {
                padding: 4px 8px;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #27272a;
            }
            QListWidget::item:selected {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: 600;
            }
            QHeaderView::section {
                background-color: #27272a;
                color: #d4d4d8;
                border: none;
                border-right: 1px solid #3f3f46;
                border-bottom: 1px solid #3f3f46;
                padding: 4px 6px;
                font-weight: 600;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #1f1f23;
                color: #f4f4f5;
                border: 1px solid #3f3f46;
                border-radius: 5px;
                padding: 5px 8px;
                font-size: 9pt;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1.5px solid #38bdf8;
                background-color: #1f1f23;
            }
            QPushButton {
                background-color: #27272a;
                color: #f4f4f5;
                border: 1px solid #3f3f46;
                border-radius: 5px;
                padding: 5px 14px;
                font-size: 9pt;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3f3f46;
                border-color: #52525b;
            }
            QPushButton:pressed {
                background-color: #52525b;
            }
            QPushButton:disabled {
                background-color: #18181b;
                color: #52525b;
                border-color: #27272a;
            }
            QDialogButtonBox QPushButton {
                min-width: 72px;
            }
            QDialogButtonBox QPushButton[text="&OK"], QDialogButtonBox QPushButton[text="OK"] {
                background: #0284c7;
                color: #ffffff;
                border: 1px solid #0369a1;
                font-weight: 600;
            }
            QDialogButtonBox QPushButton[text="&OK"]:hover, QDialogButtonBox QPushButton[text="OK"]:hover {
                background: #0369a1;
            }
        """
    return """
        QDialog {
            background-color: #f8fafc;
            color: #0f172a;
            font-family: 'Segoe UI', -apple-system, sans-serif;
        }
        QLabel {
            color: #0f172a;
            font-size: 9pt;
        }
        QLabel#secondary {
            color: #475569;
            font-size: 8.5pt;
            padding-bottom: 4px;
        }
        QLabel#error {
            color: #b91c1c;
            background-color: #fef2f2;
            border: 1px solid #fca5a5;
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 8.5pt;
            font-weight: 500;
        }
        QListWidget, QTableWidget {
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            font-family: 'Segoe UI', -apple-system, sans-serif;
            font-size: 8.5pt;
            padding: 4px;
        }
        QListWidget::item {
            padding: 4px 8px;
            border-radius: 4px;
        }
        QListWidget::item:hover {
            background-color: #f1f5f9;
        }
        QListWidget::item:selected {
            background-color: #e0f2fe;
            color: #005a9e;
            font-weight: 600;
        }
        QHeaderView::section {
            background-color: #f1f5f9;
            color: #475569;
            border: none;
            border-right: 1px solid #e2e8f0;
            border-bottom: 1px solid #cbd5e1;
            padding: 4px 6px;
            font-weight: 600;
        }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 5px;
            padding: 5px 8px;
            font-size: 9pt;
        }
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 1.5px solid #0078d7;
            background-color: #ffffff;
        }
        QPushButton {
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 5px;
            padding: 5px 14px;
            font-size: 9pt;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #f1f5f9;
            border-color: #94a3b8;
        }
        QPushButton:pressed {
            background-color: #e2e8f0;
        }
        QPushButton:disabled {
            background-color: #f8fafc;
            color: #94a3b8;
            border-color: #e2e8f0;
        }
        QDialogButtonBox QPushButton {
            min-width: 72px;
        }
        QDialogButtonBox QPushButton[text="&OK"], QDialogButtonBox QPushButton[text="OK"] {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0078d7, stop:1 #005a9e);
            color: #ffffff;
            border: 1px solid #005a9e;
            font-weight: 600;
        }
        QDialogButtonBox QPushButton[text="&OK"]:hover, QDialogButtonBox QPushButton[text="OK"]:hover {
            background: #005a9e;
        }
    """


def gallery_button_stylesheet(dark: bool) -> str:
    """Return theme-aware QToolButton styling for graph type picker galleries."""
    if dark:
        return (
            "QToolButton { border: 1px solid #3f3f46; border-radius: 6px; padding: 8px; "
            "background: #1f1f23; color: #f4f4f5; } "
            "QToolButton:hover { border-color: #38bdf8; background: #27272a; } "
            "QToolButton:checked { border: 2px solid #38bdf8; background: #1e3a5f; color: #ffffff; }"
        )
    return (
        "QToolButton { border: 1px solid #cbd5df; border-radius: 6px; padding: 8px; "
        "background: #ffffff; color: #0f172a; } "
        "QToolButton:hover { border-color: #94a3b8; background: #f8fafc; } "
        "QToolButton:checked { border: 2px solid #205b92; background: #eaf1f8; color: #0f172a; }"
    )


def subtle_label_style(dark: bool, bold: bool = False, font_size: str = "8.5pt", extra: str = "") -> str:
    """Return legible muted secondary label CSS for either light or dark mode."""
    color = "#a1a1aa" if dark else "#475569"
    weight = " font-weight: bold;" if bold else ""
    extra_css = f" {extra.strip()}" if extra else ""
    return f"color: {color}; font-size: {font_size};{weight}{extra_css}"


def error_label_style(dark: bool) -> str:
    """Return accessible error text color for dark or light mode."""
    return "color: #f87171; font-weight: 500;" if dark else "color: #a00000; font-weight: 500;"
