"""Global Fuzzy Procedure & Action Command Palette (Ctrl+K) for StatCraft."""
from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


def collect_menu_actions(menu_bar) -> List[Tuple[str, QAction]]:
    """Collect (breadcrumb_label, QAction) pairs recursively from a QMenuBar."""
    items: List[Tuple[str, QAction]] = []
    seen = set()

    def walk(menu, prefix: str) -> None:
        for act in menu.actions():
            if act.isSeparator():
                continue
            txt = act.text().replace("&&", "\x00").replace("&", "").replace("\x00", "&").strip()
            if not txt:
                continue
            full = f"{prefix} > {txt}" if prefix else txt
            if act.menu():
                walk(act.menu(), full)
            else:
                key = (full, id(act))
                if key not in seen:
                    seen.add(key)
                    items.append((full, act))

    for top_act in menu_bar.actions():
        if top_act.menu():
            top_name = top_act.text().replace("&&", "\x00").replace("&", "").replace("\x00", "&").strip()
            walk(top_act.menu(), top_name)
    return items


class CommandPaletteDialog(QDialog):
    """VS Code-style Ctrl+K fuzzy launcher for all StatCraft Stat/Graph/Calc procedures."""

    def __init__(self, parent: Optional[QWidget], actions: List[Tuple[str, QAction]], dark_mode: bool = False):
        super().__init__(parent)
        self.setWindowTitle("StatCraft Command Palette")
        self.resize(580, 400)
        self.all_actions = actions
        self.selected_action: Optional[QAction] = None

        if dark_mode:
            self.setStyleSheet("""
                QDialog { background-color: #18181b; color: #f4f4f5; }
                QLineEdit { background-color: #27272a; color: #ffffff; border: 1.5px solid #38bdf8; border-radius: 6px; padding: 8px 10px; font-size: 10pt; }
                QListWidget { background-color: #1f1f23; color: #e4e4e7; border: 1px solid #3f3f46; border-radius: 6px; padding: 4px; }
                QListWidget::item { padding: 6px 10px; border-radius: 4px; }
                QListWidget::item:selected { background-color: #0284c7; color: #ffffff; font-weight: 600; }
                QLabel { color: #a1a1aa; font-size: 8.5pt; }
            """)
        else:
            self.setStyleSheet("""
                QDialog { background-color: #f8fafc; color: #0f172a; }
                QLineEdit { background-color: #ffffff; color: #0f172a; border: 1.5px solid #0284c7; border-radius: 6px; padding: 8px 10px; font-size: 10pt; }
                QListWidget { background-color: #ffffff; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px; }
                QListWidget::item { padding: 6px 10px; border-radius: 4px; }
                QListWidget::item:selected { background-color: #0284c7; color: #ffffff; font-weight: 600; }
                QLabel { color: #64748b; font-size: 8.5pt; }
            """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(8)

        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("Type procedure name (e.g. Random Forests, REML, Tornado, Pareto, Mars)…")
        self.query_edit.textChanged.connect(self._refresh_list)
        self.query_edit.installEventFilter(self)
        layout.addWidget(self.query_edit)

        self.results_list = QListWidget()
        self.results_list.itemActivated.connect(lambda _: self._accept_current())
        layout.addWidget(self.results_list, 1)

        hint = QLabel("Up/Down to navigate  ·  Enter to launch  ·  Esc to close")
        layout.addWidget(hint)

        self._refresh_list("")
        self.query_edit.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.query_edit and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Down and self.results_list.count() > 0:
                nxt = min(self.results_list.count() - 1, max(0, self.results_list.currentRow() + 1))
                self.results_list.setCurrentRow(nxt)
                return True
            if key == Qt.Key.Key_Up and self.results_list.count() > 0:
                prv = max(0, self.results_list.currentRow() - 1)
                self.results_list.setCurrentRow(prv)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._accept_current()
                return True
        return super().eventFilter(obj, event)

    def _refresh_list(self, text: str) -> None:
        tokens = [t for t in text.lower().split() if t]
        self.results_list.clear()
        for label, act in self.all_actions:
            low = label.lower()
            if all(tok in low for tok in tokens):
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, act)
                self.results_list.addItem(item)
                if self.results_list.count() >= 60:
                    break
        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)

    def _accept_current(self) -> None:
        item = self.results_list.currentItem()
        if item is not None:
            self.selected_action = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
