
def _is_dark_active(widget=None) -> bool:
    if widget is not None:
        try:
            win = widget.window()
            if win and hasattr(win, "_dark_mode"):
                return bool(win._dark_mode)
        except Exception:
            pass
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    return False

"""Worksheet key navigation, active cell editor, and Standard statistical column/row selection painting."""
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QHeaderView, QLineEdit, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTableWidget,
)


def movement(event, enter_direction='down', in_editor=False):
    if event.type() != QEvent.Type.KeyPress:
        return None
    mods = event.modifiers()
    if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier):
        return None
    key = event.key()
    reverse = bool(mods & Qt.KeyboardModifier.ShiftModifier)
    if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
        return 'left' if reverse or key == Qt.Key.Key_Backtab else 'right'
    if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
        if enter_direction == 'right':
            return 'left' if reverse else 'right'
        return 'up' if reverse else 'down'
    if in_editor:
        if key == Qt.Key.Key_Down:
            return 'down'
        if key == Qt.Key.Key_Up:
            return 'up'
    return None


class WorksheetHeaderView(QHeaderView):
    """Standard statistical column (`C1`, `C2`, `C3-T`...) and row (`1`, `2`, `3`...) header bar."""
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.selected_sections = set()
        self.active_sections = set()
        self.formula_columns = set()
        self.setSectionsClickable(True)
        self.setHighlightSections(False)

    def paintSection(self, painter, rect, logicalIndex):
        if not rect.isValid():
            return
        painter.save()
        model = self.model()
        label_text = ""
        if model is not None:
            raw = model.headerData(logicalIndex, self.orientation(), Qt.ItemDataRole.DisplayRole)
            if raw is not None:
                label_text = str(raw)

        is_selected = logicalIndex in self.selected_sections
        is_active = logicalIndex in self.active_sections

        dark = _is_dark_active(self)
        if self.orientation() == Qt.Orientation.Horizontal:
            if dark:
                bg = QColor("#0284c7") if is_selected else QColor("#27272a") if is_active else QColor("#1f1f23")
                fg = QColor("#ffffff") if is_selected else QColor("#38bdf8") if is_active else QColor("#e4e4e7")
                border = QColor("#3f3f46")
            else:
                bg = QColor("#004a7c") if is_selected else QColor("#dfe6ed") if is_active else QColor("#f0f0f0")
                fg = QColor("#ffffff") if is_selected else QColor("#004a7c") if is_active else QColor("#222222")
                border = QColor("#c8c8c8")
            bold = is_selected or is_active
        else:
            if dark:
                bg = QColor("#0284c7") if is_selected else QColor("#27272a") if is_active else QColor("#18181b")
                fg = QColor("#ffffff") if is_selected else QColor("#38bdf8") if is_active else QColor("#a1a1aa")
                border = QColor("#3f3f46")
            else:
                bg = QColor("#004a7c") if is_selected else QColor("#d8d8d8") if is_active else QColor("#f0f0f0")
                fg = QColor("#ffffff") if is_selected else QColor("#004a7c") if is_active else QColor("#222222")
                border = QColor("#c8c8c8")
            bold = is_selected or is_active

        painter.fillRect(rect, bg)
        painter.setPen(border)
        painter.drawLine(rect.topRight(), rect.bottomRight())
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        font = QFont(self.font())
        font.setBold(bold)
        painter.setFont(font)
        painter.setPen(fg)

        has_formula = self.orientation() == Qt.Orientation.Horizontal and logicalIndex in getattr(self, 'formula_columns', set())
        text_right_margin = -26 if (has_formula and rect.width() >= 42) else -2
        painter.drawText(rect.adjusted(2, 0, text_right_margin, 0), Qt.AlignmentFlag.AlignCenter, label_text)

        # Dynamic calculated column formula indicator badge (f(x))
        if has_formula and rect.width() >= 36:
            pill_w = 22
            pill_h = 13
            pill_x = rect.right() - pill_w - 3
            pill_y = rect.top() + (rect.height() - pill_h) // 2
            pill_rect = QRectF(pill_x, pill_y, pill_w, pill_h)

            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if dark:
                painter.setBrush(QColor("#064e3b"))
                painter.setPen(QPen(QColor("#059669"), 1))
            else:
                painter.setBrush(QColor("#dcfce7"))
                painter.setPen(QPen(QColor("#16a34a"), 1))
            painter.drawRoundedRect(pill_rect, 3, 3)

            fx_font = QFont(self.font())
            fx_font.setPointSize(6.5)
            fx_font.setBold(True)
            painter.setFont(fx_font)
            painter.setPen(QColor("#6ee7b7") if dark else QColor("#15803d"))
            painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, "f(x)")

        painter.restore()


class WorksheetDelegate(QStyledItemDelegate):
    def __init__(self, parent, navigate, is_column_names=False):
        super().__init__(parent)
        self.navigate = navigate
        self.page_rows = None
        self.is_column_names = is_column_names
        self._initial_editor_text = ""

    def setEditorData(self, editor, index):
        super().setEditorData(editor, index)
        if isinstance(editor, QLineEdit):
            self._initial_editor_text = editor.text()

    def eventFilter(self, editor, event):
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape and isinstance(editor, QLineEdit):
                editor.setText(self._initial_editor_text)
                self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.RevertModelCache)
                return True
            direction = movement(event, getattr(self.parent(), 'enter_direction', 'down'), in_editor=True)
            if direction is not None and isinstance(editor, QLineEdit):
                if self.navigate is not None:
                    self.navigate(direction, editor, self)
                    return True
        return super().eventFilter(editor, event)

    def paint(self, painter, option, index):
        table = self.parent()
        col = index.column()
        row = index.row()
        sel_cols = getattr(table, "selected_columns", set())
        sel_rows = getattr(table, "selected_rows", set())
        in_sel_col = col in sel_cols
        in_sel_row = (not self.is_column_names) and (row in sel_rows)

        custom_bg = index.data(Qt.ItemDataRole.BackgroundRole)
        comment_note = index.data(Qt.ItemDataRole.UserRole + 2)

        opt = QStyleOptionViewItem(option)
        is_cell_selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        opt.state &= ~QStyle.StateFlag.State_Selected
        opt.state &= ~QStyle.StateFlag.State_HasFocus

        dark = _is_dark_active(table)
        painter.save()
        if isinstance(custom_bg, QColor):
            painter.fillRect(opt.rect, custom_bg)
        elif in_sel_col or in_sel_row:
            painter.fillRect(opt.rect, QColor("#27272a") if dark else QColor("#eaeaea"))
        elif is_cell_selected:
            painter.fillRect(opt.rect, QColor("#094771") if dark else QColor("#e4effa"))
        elif self.is_column_names:
            painter.fillRect(opt.rect, QColor("#1f1f23") if dark else QColor("#f0f0f0"))
        else:
            painter.fillRect(opt.rect, QColor("#18181b") if dark else QColor("#ffffff"))

        if dark:
            opt.palette.setColor(opt.palette.ColorRole.Text, QColor("#f4f4f5"))

        super().paint(painter, opt, index)

        # Cell comment indicator (small top-right triangle like StatCraft)
        if comment_note:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#d9534f"))
            r = opt.rect
            painter.drawPolygon(QPolygonF([
                QPointF(r.right() - 5, r.top()),
                QPointF(r.right() + 1, r.top()),
                QPointF(r.right() + 1, r.top() + 6),
            ]))

        # Crisp dark-navy StatCraft outline along the edges of selected columns/rows
        pen = QPen(QColor("#38bdf8") if dark else QColor("#004a7c"), 2)
        painter.setPen(pen)
        r = opt.rect
        if in_sel_col:
            if (col - 1) not in sel_cols:
                painter.drawLine(r.topLeft(), r.bottomLeft())
            if (col + 1) not in sel_cols:
                painter.drawLine(r.topRight(), r.bottomRight())
            if self.is_column_names:
                painter.drawLine(r.topLeft(), r.topRight())
        if in_sel_row:
            if (row - 1) not in sel_rows:
                painter.drawLine(r.topLeft(), r.topRight())
            if (row + 1) not in sel_rows:
                painter.drawLine(r.bottomLeft(), r.bottomRight())
        if is_cell_selected and not in_sel_col and not in_sel_row and table.currentIndex() == index:
            painter.drawRect(r.adjusted(1, 1, -1, -1))
        painter.restore()


class WorksheetTable(QTableWidget):
    def __init__(self, navigate, parent=None):
        super().__init__(parent)
        self.navigate = navigate
        self.enter_direction = 'down'
        self.selected_columns = set()
        self.selected_rows = set()
        self.setItemDelegate(WorksheetDelegate(self, navigate))

    def event(self, event):
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            # Ctrl+Home / Ctrl+End / Ctrl+Up
            if (mods & Qt.KeyboardModifier.ControlModifier) and not (mods & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)):
                if key == Qt.Key.Key_Home:
                    self.navigate('top_left')
                    return True
                if key == Qt.Key.Key_End:
                    self.navigate('bottom_right')
                    return True
                if key == Qt.Key.Key_Up and self.currentRow() == 0:
                    self.navigate('column_name')
                    return True
            elif not mods:
                scroll = self.verticalScrollBar()
                if key == Qt.Key.Key_Down and self.currentRow() == self.rowCount() - 1:
                    self.navigate('down')
                    return True
                if key == Qt.Key.Key_Up and self.currentRow() == 0:
                    self.navigate('up')
                    return True
                if self.page_rows and ((key == Qt.Key.Key_PageDown and scroll.value() == scroll.maximum()) or (key == Qt.Key.Key_PageUp and scroll.value() == scroll.minimum())):
                    if self.page_rows(1 if key == Qt.Key.Key_PageDown else -1):
                        return True
            direction = movement(event, self.enter_direction, in_editor=False)
            if direction is not None:
                self.navigate(direction)
                return True
        return super().event(event)

    def wheelEvent(self, event):
        delta = event.angleDelta().y() or event.pixelDelta().y()
        scroll = self.verticalScrollBar()
        at_edge = (delta < 0 and scroll.value() == scroll.maximum()) or (delta > 0 and scroll.value() == scroll.minimum())
        if delta and at_edge and self.page_rows and not event.modifiers():
            if self.page_rows(1 if delta < 0 else -1):
                event.accept()
                return
        super().wheelEvent(event)


class ColumnNamesTable(QTableWidget):
    """Header row table for column names (C1, C2...) with seamless Minitab-style navigation."""
    def __init__(self, navigate, parent=None):
        super().__init__(1, 0, parent)
        self.navigate = navigate
        self.enter_direction = 'down'
        self.selected_columns = set()
        self.selected_rows = set()
        self.setItemDelegate(WorksheetDelegate(self, navigate, is_column_names=True))

    def event(self, event):
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if not (mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)):
                if key == Qt.Key.Key_Down:
                    if self.navigate is not None:
                        self.navigate('down')
                        return True
                direction = movement(event, self.enter_direction, in_editor=False)
                if direction is not None:
                    if self.navigate is not None:
                        self.navigate(direction)
                        return True
        return super().event(event)

