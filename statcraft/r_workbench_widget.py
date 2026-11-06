"""R script editor, console, environment, worksheet and plot tools."""
from __future__ import annotations

import os
import json
import threading
import re
import shutil
import tempfile
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPixmap,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .model import Column, Worksheet, display_date
from .r_bridge import (
    download_and_install_r_direct,
    RPersistentSession,
    find_r_executable,
    get_cran_installer_url,
    get_r_help_text,
    get_r_version,
    install_r_via_winget,
    is_r_available,
)


class _JobSignals(QObject):
    finished = Signal(object)


class _RJob(QRunnable):
    def __init__(self, work):
        super().__init__()
        self.work = work
        self.signals = _JobSignals()

    def run(self):
        try:
            value = self.work()
        except Exception as exc:
            value = exc
        self.signals.finished.emit(value)


def _start_job(work, finished):
    job = _RJob(work)
    job.signals.finished.connect(finished, Qt.ConnectionType.QueuedConnection)
    QThreadPool.globalInstance().start(job)


class VSCodeRSyntaxHighlighter(QSyntaxHighlighter):
    """VS Code R Syntax Highlighter supporting Light+ and Dark Modern themes."""

    def __init__(self, parent=None, is_dark: bool = False):
        super().__init__(parent)
        self._is_dark = is_dark
        self.rules: List[Tuple[re.Pattern, QTextCharFormat]] = []
        self._rebuild_rules()

    @property
    def is_dark(self) -> bool:
        return self._is_dark

    def set_dark_mode(self, is_dark: bool) -> None:
        if self._is_dark != is_dark:
            self._is_dark = is_dark
            self._rebuild_rules()
            self.rehighlight()

    def _rebuild_rules(self) -> None:
        self.rules = []
        is_dark = self._is_dark

        # Keywords (#0000ff in Light, #569cd6 in Dark)
        kw_format = QTextCharFormat()
        kw_format.setForeground(QColor("#569cd6" if is_dark else "#0000ff"))
        kw_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            r"\bif\b", r"\belse\b", r"\brepeat\b", r"\bwhile\b", r"\bfunction\b",
            r"\bfor\b", r"\bin\b", r"\bnext\b", r"\bbreak\b", r"\bTRUE\b",
            r"\bFALSE\b", r"\bNULL\b", r"\bInf\b", r"\bNaN\b", r"\bNA\b",
            r"\blibrary\b", r"\brequire\b", r"\bstatcraft_export\b", r"\bView\b",
        ]
        for kw in keywords:
            self.rules.append((re.compile(kw), kw_format))

        # Functions (#795e26 in Light, #dcdcaa in Dark)
        fn_format = QTextCharFormat()
        fn_format.setForeground(QColor("#dcdcaa" if is_dark else "#795e26"))
        functions = [
            r"\blm\b", r"\baov\b", r"\bglm\b", r"\bsummary\b", r"\bplot\b",
            r"\bhist\b", r"\bboxplot\b", r"\babline\b", r"\bprint\b",
            r"\bcat\b", r"\bc\b", r"\blist\b", r"\bnames\b", r"\bcolnames\b",
            r"\bhead\b", r"\btail\b", r"\bstr\b", r"\bpredict\b", r"\bresid\b",
            r"\bprcomp\b", r"\bcor\b", r"\bvar\b", r"\bsd\b", r"\bmean\b",
            r"\bmedian\b", r"\bquantile\b", r"\bt\.test\b", r"\bdata\.frame\b",
            r"\bas\.data\.frame\b", r"\btransform\b", r"\bgrid\b", r"\bpar\b",
            r"\bhelp\b", r"\binteraction\.plot\b", r"\bbiplot\b",
        ]
        for fn in functions:
            self.rules.append((re.compile(fn), fn_format))

        # Strings (#a31515 in Light, #ce9178 in Dark)
        str_format = QTextCharFormat()
        str_format.setForeground(QColor("#ce9178" if is_dark else "#a31515"))
        self.rules.append((re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), str_format))
        self.rules.append((re.compile(r"'[^'\\]*(\\.[^'\\]*)*'"), str_format))

        # Comments (#008000 in Light, #6a9955 in Dark)
        comm_format = QTextCharFormat()
        comm_format.setForeground(QColor("#6a9955" if is_dark else "#008000"))
        comm_format.setFontItalic(True)
        self.rules.append((re.compile(r"#.*"), comm_format))

        # Numbers (#098658 in Light, #b5cea8 in Dark)
        num_format = QTextCharFormat()
        num_format.setForeground(QColor("#b5cea8" if is_dark else "#098658"))
        self.rules.append((re.compile(r"\b[0-9]+(\.[0-9]+)?\b"), num_format))

        # Operators (#000000 in Light, #d4d4d4 in Dark)
        op_format = QTextCharFormat()
        op_format.setForeground(QColor("#d4d4d4" if is_dark else "#0f172a"))
        op_format.setFontWeight(QFont.Weight.Bold)
        for op in [r"<-", r"->", r"%>%", r"\+", r"-", r"\*", r"/", r"==", r"!=", r"<=", r">="]:
            self.rules.append((re.compile(op), op_format))

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)


class LineNumberGutter(QWidget):
    """VS Code-style Line Number Gutter."""

    def __init__(self, editor: RCodeEditor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event) -> None:
        self.editor.gutter_paint_event(event)


class RCodeEditor(QPlainTextEdit):
    """VS Code-style R Code Editor with line gutter, active highlight, and Positron shortcuts."""

    def __init__(self, workbench: Optional[RWorkbenchWidget] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.workbench = workbench
        self._is_dark = False
        self.gutter = LineNumberGutter(self)

        font = QFont("Cascadia Code" if QFont("Cascadia Code").exactMatch() else "Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.blockCountChanged.connect(self.update_gutter_width)
        self.updateRequest.connect(self.update_gutter)
        self.cursorPositionChanged.connect(self.highlight_current_line)

        self.update_gutter_width(0)
        self.highlight_current_line()

    @property
    def is_dark(self) -> bool:
        return self._is_dark

    def set_dark_mode(self, is_dark: bool) -> None:
        self._is_dark = is_dark
        self.gutter.update()
        self.highlight_current_line()

    def gutter_width(self) -> int:
        digits = max(1, len(str(max(1, self.blockCount()))))
        space = 20 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def update_gutter_width(self, _) -> None:
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def update_gutter(self, rect: QRect, dy: int) -> None:
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_gutter_width(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def highlight_current_line(self) -> None:
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor("#282828" if self._is_dark else "#f1f5f9")
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def gutter_paint_event(self, event) -> None:
        painter = QPainter(self.gutter)
        is_dark = self._is_dark
        bg_color = QColor("#1e1e1e" if is_dark else "#f8fafc")
        num_color = QColor("#858585" if is_dark else "#94a3b8")
        cur_num_color = QColor("#c6c6c6" if is_dark else "#0f172a")

        painter.fillRect(event.rect(), bg_color)
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        current_block = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(cur_num_color if block_number == current_block else num_color)
                painter.drawText(
                    0, top, self.gutter.width() - 8, self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight, number
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def keyPressEvent(self, event) -> None:
        # Ctrl+Enter: Run current line or selection and advance cursor (Positron model)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            if self.workbench:
                self.workbench.run_selection_or_line()
            return
        # Tab key: Insert 4 spaces
        if event.key() == Qt.Key.Key_Tab and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.insertPlainText("    ")
            return
        super().keyPressEvent(event)


class RDataViewerWidget(QWidget):
    """Positron View(df) Interactive Spreadsheet Data Viewer."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Top Control & Search Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.lbl_info = QLabel("df · Active StatCraft Dataset")
        self.lbl_info.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_info.setStyleSheet("font-size: 11px;")
        top_bar.addWidget(self.lbl_info)

        top_bar.addStretch()

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("🔍 Filter rows...")
        self.txt_filter.setMaximumWidth(220)
        self.txt_filter.textChanged.connect(self._filter_rows)
        top_bar.addWidget(self.txt_filter)

        self.btn_refresh = QToolButton()
        self.btn_refresh.setText("🔄 Refresh")
        self.btn_refresh.setToolTip("Reload data from active worksheet")
        top_bar.addWidget(self.btn_refresh)

        layout.addLayout(top_bar)

        # Spreadsheet Data Table
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

    def load_worksheet(self, ws: Optional[Worksheet]) -> None:
        if not ws or not ws.columns:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self.lbl_info.setText("df · No active worksheet loaded")
            return

        total_rows, total_columns = ws.row_count, len(ws.columns)
        nrows, ncols = min(total_rows, 1000), min(total_columns, 100)
        self.lbl_info.setText(f"{ws.name} · {total_rows:,} rows × {total_columns:,} columns"
                              + (f" · Preview {nrows:,} × {ncols}" if (nrows, ncols) != (total_rows, total_columns) else ""))

        self.table.setRowCount(nrows)
        self.table.setColumnCount(ncols)
        headers = [f"{c.name} ({c.kind})" for c in ws.columns[:ncols]]
        self.table.setHorizontalHeaderLabels(headers)

        for col_idx, col in enumerate(ws.columns[:ncols]):
            for row_idx, val in enumerate(col.values[:nrows]):
                txt = "" if val is None else (display_date(val) if col.kind == "date" else str(val))
                item = QTableWidgetItem(txt)
                if col.kind == "number":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row_idx, col_idx, item)

    def _filter_rows(self, text: str) -> None:
        q = text.lower().strip()
        for r in range(self.table.rowCount()):
            if not q:
                self.table.setRowHidden(r, False)
                continue
            match = False
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                if item and q in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(r, not match)


class RPlotGalleryWidget(QWidget):
    """Positron Multi-Plot History Carousel with back/forward navigation and export."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.plot_history: List[str] = []
        self.current_idx: int = -1
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        self.tb_frame = QFrame()
        self.tb_frame.setFixedHeight(34)
        tb = QHBoxLayout(self.tb_frame)
        tb.setContentsMargins(8, 2, 8, 2)
        tb.setSpacing(4)

        self.btn_prev = QToolButton()
        self.btn_prev.setText("◀")
        self.btn_prev.setToolTip("Previous Plot in History")
        self.btn_prev.clicked.connect(self.show_prev_plot)
        self.btn_prev.setEnabled(False)
        tb.addWidget(self.btn_prev)

        self.btn_next = QToolButton()
        self.btn_next.setText("▶")
        self.btn_next.setToolTip("Next Plot in History")
        self.btn_next.clicked.connect(self.show_next_plot)
        self.btn_next.setEnabled(False)
        tb.addWidget(self.btn_next)

        self.lbl_counter = QLabel("No plots")
        self.lbl_counter.setStyleSheet("font-size: 10px; color: #71717a; padding: 0 4px;")
        tb.addWidget(self.lbl_counter)

        tb.addStretch()

        self.btn_copy = QToolButton()
        self.btn_copy.setText("📋 Copy")
        self.btn_copy.setToolTip("Copy Plot to Clipboard")
        self.btn_copy.clicked.connect(self.copy_current_plot)
        tb.addWidget(self.btn_copy)

        self.btn_save = QToolButton()
        self.btn_save.setText("💾 Save…")
        self.btn_save.setToolTip("Export Plot Image (PNG, PDF, SVG)")
        self.btn_save.clicked.connect(self.save_current_plot)
        tb.addWidget(self.btn_save)

        self.btn_clear = QToolButton()
        self.btn_clear.setText("Clear")
        self.btn_clear.setToolTip("Clear Plot History")
        self.btn_clear.clicked.connect(self.clear_all_plots)
        tb.addWidget(self.btn_clear)

        layout.addWidget(self.tb_frame)

        # Plot Canvas Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.canvas_label = QLabel("No graphics generated yet.\nRun a plotting command (e.g. plot(), hist(), ggplot()).")
        self.canvas_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas_label.setStyleSheet("color: #71717a; font-size: 11px; padding: 24px;")
        self.scroll_area.setWidget(self.canvas_label)
        layout.addWidget(self.scroll_area)

    def add_plot(self, path: str) -> None:
        if not path or not Path(path).exists():
            return
        # Store copy in persistent temp list
        self.plot_history.append(path)
        self.current_idx = len(self.plot_history) - 1
        self._display_current()

    def show_prev_plot(self) -> None:
        if self.current_idx > 0:
            self.current_idx -= 1
            self._display_current()

    def show_next_plot(self) -> None:
        if self.current_idx < len(self.plot_history) - 1:
            self.current_idx += 1
            self._display_current()

    def _display_current(self) -> None:
        total = len(self.plot_history)
        if total == 0 or self.current_idx < 0:
            self.canvas_label.setPixmap(QPixmap())
            self.canvas_label.setText("No graphics generated yet.\nRun a plotting command (e.g. plot(), hist(), ggplot()).")
            self.lbl_counter.setText("No plots")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            return

        path = self.plot_history[self.current_idx]
        pix = QPixmap(path)
        if not pix.isNull():
            # Scale smoothly to viewport
            view_size = self.scroll_area.viewport().size()
            scaled = pix.scaled(
                max(200, view_size.width() - 20),
                max(200, view_size.height() - 20),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.canvas_label.setPixmap(scaled)
            self.canvas_label.setText("")
        self.lbl_counter.setText(f"Plot {self.current_idx + 1} of {total}")
        self.btn_prev.setEnabled(self.current_idx > 0)
        self.btn_next.setEnabled(self.current_idx < total - 1)

    def copy_current_plot(self) -> None:
        if 0 <= self.current_idx < len(self.plot_history):
            pix = QPixmap(self.plot_history[self.current_idx])
            if not pix.isNull():
                QApplication.clipboard().setPixmap(pix)

    def save_current_plot(self) -> None:
        if 0 <= self.current_idx < len(self.plot_history):
            src = self.plot_history[self.current_idx]
            dest, _ = QFileDialog.getSaveFileName(self, "Export R Plot", "Rplot.png", "Images (*.png *.jpg *.pdf)")
            if dest:
                shutil.copy2(src, dest)

    def clear_all_plots(self) -> None:
        self.plot_history.clear()
        self.current_idx = -1
        self._display_current()


class RHelpViewerWidget(QWidget):
    """Positron Integrated R Help & Documentation Viewer."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Search Bar
        search_box = QHBoxLayout()
        search_box.setSpacing(6)

        self.txt_topic = QLineEdit()
        self.txt_topic.setPlaceholderText("Search R Help (e.g. lm, plot, summary, aov)...")
        self.txt_topic.returnPressed.connect(self._do_search)
        search_box.addWidget(self.txt_topic)

        btn_search = QToolButton()
        btn_search.setText("Search")
        btn_search.clicked.connect(self._do_search)
        search_box.addWidget(btn_search)
        layout.addLayout(search_box)

        # Documentation Text View
        self.text_view = QPlainTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setFont(QFont("Cascadia Code" if QFont("Cascadia Code").exactMatch() else "Consolas", 9.5))
        self.text_view.setPlainText("Type an R topic above or run '?topic' in the console/editor to view official documentation.")
        layout.addWidget(self.text_view)

    def show_topic_help(self, topic: str) -> None:
        self.txt_topic.setText(topic)
        self.text_view.setPlainText("Loading help…")
        _start_job(lambda: (topic, get_r_help_text(topic)), self._show_help)

    def _show_help(self, result):
        if isinstance(result, Exception):
            self.text_view.setPlainText(str(result))
        elif self.txt_topic.text() == result[0]:
            self.text_view.setPlainText(result[1])

    def _do_search(self) -> None:
        topic = self.txt_topic.text().strip()
        if topic:
            self.show_topic_help(topic)


class RWorkbenchWidget(QWidget):
    """Authentic VS Code / Positron-style R data science workbench platform."""

    TEMPLATES = {
        "Linear Regression & Diagnostics": (
            "# 1. Linear Regression Model\n"
            "fit <- lm(df[[2]] ~ df[[1]], data=df)\n"
            "print(summary(fit))\n\n"
            "# 2. Diagnostic Plots\n"
            "par(mfrow=c(2,2))\n"
            "plot(fit)\n"
        ),
        "Two-Way ANOVA & Interaction Plot": (
            "# Two-Way ANOVA Model\n"
            "fit_aov <- aov(df[[1]] ~ as.factor(df[[2]]) * as.factor(df[[3]]), data=df)\n"
            "print(summary(fit_aov))\n\n"
            "# Interaction Plot\n"
            "interaction.plot(df[[2]], df[[3]], df[[1]], col=c('#0284c7', '#dc2626'), lwd=2)\n"
        ),
        "Principal Component Analysis (PCA)": (
            "# PCA with Scaling\n"
            "num_data <- df[sapply(df, is.numeric)]\n"
            "pca_res <- prcomp(num_data, scale.=TRUE)\n"
            "print(summary(pca_res))\n"
            "biplot(pca_res, col=c('#64748b', '#0284c7'))\n"
        ),
        "Logistic Regression (GLM)": (
            "# Binary Logistic Regression\n"
            "fit_glm <- glm(df[[1]] ~ df[[2]], family=binomial, data=df)\n"
            "print(summary(fit_glm))\n"
            "print(exp(coef(fit_glm))) # Odds Ratios\n"
        ),
        "Export Transformed Data to StatCraft": (
            "# Create modified data and push back to StatCraft as a new worksheet\n"
            "df_transformed <- transform(df, Log_Col1 = log(df[[1]] + 1))\n"
            "statcraft_export(df_transformed, 'LogTransformed')\n"
            "cat('Exported LogTransformed to StatCraft Worksheets!\\n')\n"
        ),
    }

    def __init__(self, main_window, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.main_window = main_window
        self.presenter = getattr(main_window, "presenter", None)
        self._history: List[str] = []
        self._history_idx: int = -1
        self._is_dark: bool = False
        self._connected_analysis = None

        self._build_ui()
        self.set_dark_mode(getattr(main_window, "_dark_mode", False))
        self._session = RPersistentSession()
        self._cancel = None
        self._source = None
        self._snapshot = None
        self._status_checking = False
        self._status_checked = False
        self.destroyed.connect(lambda _obj=None, session=self._session: session.interrupt())

    def showEvent(self, event):
        super().showEvent(event)
        if not self._status_checked:
            self._check_and_update_r_status()

    @property
    def is_dark(self) -> bool:
        return self._is_dark

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Top Header Bar (Positron Header)
        self.hdr_frame = QFrame()
        self.hdr_frame.setObjectName("rHeader")
        self.hdr_frame.setFixedHeight(38)
        hdr_layout = QHBoxLayout(self.hdr_frame)
        hdr_layout.setContentsMargins(10, 0, 10, 0)
        hdr_layout.setSpacing(8)

        self.brand_lbl = QLabel("R Workbench")
        self.brand_lbl.setStyleSheet("font-size: 11px;")
        hdr_layout.addWidget(self.brand_lbl)

        # Status Pill
        self.status_pill = QFrame()
        self.status_pill.setObjectName("statusPill")
        sp_layout = QHBoxLayout(self.status_pill)
        sp_layout.setContentsMargins(6, 2, 6, 2)
        sp_layout.setSpacing(4)
        self.status_dot = QLabel("")
        self.status_dot.hide()
        self.status_text = QLabel("R available on demand")
        self.status_text.setStyleSheet("font-size: 10.5px; font-weight: 600;")
        sp_layout.addWidget(self.status_dot)
        sp_layout.addWidget(self.status_text)
        hdr_layout.addWidget(self.status_pill)

        hdr_layout.addStretch()

        self.btn_run_sel = QPushButton("Run")
        self.btn_run_sel.setToolTip("Run selection or current line (Ctrl+Enter)")
        self.btn_run_sel.setToolTip("Run current line or selection and advance to next line (Ctrl+Enter)")
        self.btn_run_sel.clicked.connect(self.run_selection_or_line)
        hdr_layout.addWidget(self.btn_run_sel)

        self.btn_run_all = QPushButton("Run Script")
        self.btn_run_all.setToolTip("Run entire active R script (Ctrl+Shift+Enter)")
        self.btn_run_all.clicked.connect(self.run_all)
        hdr_layout.addWidget(self.btn_run_all)

        self.btn_view_df = QPushButton("Worksheet")
        self.btn_view_df.setToolTip("Open active StatCraft dataset in spreadsheet grid")
        self.btn_view_df.clicked.connect(self.open_data_viewer_tab)
        hdr_layout.addWidget(self.btn_view_df)

        self.btn_sync_df = QPushButton("📥 Sync Data (df)")
        self.btn_sync_df.setToolTip("Export current StatCraft worksheet into R session as 'df' and 'worksheet'")
        self.btn_sync_df.clicked.connect(lambda: self.sync_active_worksheet_to_r())
        hdr_layout.addWidget(self.btn_sync_df)

        self.btn_templates = QPushButton("Examples ▾")
        self.btn_templates.clicked.connect(self._show_templates_menu)
        hdr_layout.addWidget(self.btn_templates)

        # Integrated Model Connection Tag & Apply Button
        self.connect_tag = QLabel("")
        self.connect_tag.setStyleSheet("color: #38bdf8; font-weight: 600; font-size: 8.5pt; padding-left: 8px;")
        self.connect_tag.hide()
        hdr_layout.addWidget(self.connect_tag)

        self.btn_sync_top = QPushButton("Sync to Worksheet")
        self.btn_sync_top.setStyleSheet("background-color: #0284c7; color: white; font-weight: 600; border-radius: 4px; padding: 3px 8px; font-size: 8.5pt;")
        self.btn_sync_top.setToolTip("Store R fitted values and residuals back into the active worksheet")
        self.btn_sync_top.clicked.connect(self.apply_connected_predictions)
        self.btn_sync_top.hide()
        hdr_layout.addWidget(self.btn_sync_top)

        root_layout.addWidget(self.hdr_frame)

        # 2. R Not Detected Banner (Hidden if R is present)
        self.r_banner = QFrame()
        self.r_banner.setObjectName("rBanner")
        b_layout = QHBoxLayout(self.r_banner)
        b_layout.setContentsMargins(12, 6, 12, 6)
        b_layout.setSpacing(8)

        b_icon = QLabel("")
        b_layout.addWidget(b_icon)
        self.b_text = QLabel("<b>R is not detected on your system.</b> Install R to execute scripts, run REPL commands, and render graphics.")
        b_layout.addWidget(self.b_text)
        b_layout.addStretch()

        self.btn_auto_install = QPushButton("Install R")
        self.btn_auto_install.setStyleSheet("background-color: #dc2626; color: white; font-weight: bold; border-radius: 4px; padding: 4px 10px;")
        self.btn_auto_install.clicked.connect(self._install_r_automatically)
        b_layout.addWidget(self.btn_auto_install)

        self.btn_browse = QPushButton("Locate R…")
        self.btn_browse.clicked.connect(self._browse_r_executable)
        b_layout.addWidget(self.btn_browse)

        self.btn_cran = QPushButton("CRAN")
        self.btn_cran.clicked.connect(lambda: webbrowser.open("https://cloud.r-project.org/"))
        b_layout.addWidget(self.btn_cran)

        btn_dismiss = QPushButton("✕")
        btn_dismiss.setStyleSheet("background: transparent; color: #94a3b8; font-size: 11px; border: none; padding: 2px 6px;")
        btn_dismiss.setToolTip("Dismiss notice")
        btn_dismiss.clicked.connect(self.r_banner.hide)
        b_layout.addWidget(btn_dismiss)

        root_layout.addWidget(self.r_banner)

        # Compact connect_banner (hidden, 0 height)
        self.connect_banner = QFrame()
        self.connect_banner.hide()
        self.cb_title = QLabel()
        self.btn_apply_connect = QPushButton()

        # 3. Main Splitters (4 Quadrants)
        main_h_split = QSplitter(Qt.Orientation.Horizontal)
        left_v_split = QSplitter(Qt.Orientation.Vertical)
        right_v_split = QSplitter(Qt.Orientation.Vertical)

        # Top-Left: Multi-Tab Script Editor & Data Viewer
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setObjectName("editorTabs")
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.tabCloseRequested.connect(self._close_tab)
        self.editor_tabs.currentChanged.connect(self._select_editor)

        # Tab 1: script.R
        self.editor = RCodeEditor(workbench=self)
        self.highlighter = VSCodeRSyntaxHighlighter(self.editor.document(), is_dark=self._is_dark)
        default_code = (
            "# StatCraft R Workbench\n"
            "# Active worksheet is automatically bound as 'df' and 'worksheet'\n\n"
            "# 1. Summary of active data\n"
            "print(summary(df))\n\n"
            "# 2. Linear Regression & Plot\n"
            "if (ncol(df) >= 2) {\n"
            "    fit <- lm(df[[2]] ~ df[[1]], data=df)\n"
            "    print(summary(fit))\n"
            "    plot(df[[1]], df[[2]], pch=19, col='#0284c7', cex=1.2,\n"
            "         main='Regression Fit', xlab=colnames(df)[1], ylab=colnames(df)[2])\n"
            "    abline(fit, col='#ef4444', lwd=2)\n"
            "    grid(col='#cbd5e1', lty='dotted')\n"
            "}\n"
        )
        self.editor.setPlainText(default_code)
        self.editor_tabs.addTab(self.editor, "script.R")

        # Tab 2: View(df) Data Viewer
        self.data_viewer = RDataViewerWidget()
        self.data_viewer.btn_refresh.clicked.connect(self.open_data_viewer_tab)
        self.editor_tabs.addTab(self.data_viewer, "Worksheet")
        from PySide6.QtWidgets import QTabBar
        for index in (0, 1):
            for position in (QTabBar.ButtonPosition.LeftSide, QTabBar.ButtonPosition.RightSide):
                self.editor_tabs.tabBar().setTabButton(index, position, None)

        left_v_split.addWidget(self.editor_tabs)

        # Bottom-Left: Interactive Console / Terminal
        self.console_frame = QFrame()
        self.console_frame.setObjectName("consoleFrame")
        c_lay = QVBoxLayout(self.console_frame)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(0)

        # Console Header
        con_hdr = QFrame()
        con_hdr.setObjectName("panelHeader")
        con_hdr.setFixedHeight(30)
        ch_lay = QHBoxLayout(con_hdr)
        ch_lay.setContentsMargins(8, 0, 8, 0)
        ch_lay.setSpacing(6)
        ch_lay.addWidget(QLabel("Console"))
        self.con_status_lbl = QLabel("Ready")
        self.con_status_lbl.setStyleSheet("color: #71717a; font-size: 10px;")
        ch_lay.addWidget(self.con_status_lbl)
        ch_lay.addStretch()

        self.btn_stop = QToolButton()
        self.btn_stop.setText("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setToolTip("Stop the running command and end this R session")
        self.btn_stop.clicked.connect(self.stop_execution)
        ch_lay.addWidget(self.btn_stop)

        btn_restart = QToolButton()
        btn_restart.setText("Restart")
        btn_restart.clicked.connect(self._restart_session)
        ch_lay.addWidget(btn_restart)

        btn_clear = QToolButton()
        btn_clear.setText("Clear")
        btn_clear.clicked.connect(self._clear_console)
        ch_lay.addWidget(btn_clear)
        c_lay.addWidget(con_hdr)

        self.console_output = QPlainTextEdit()
        self.console_output.setObjectName("consoleOutput")
        self.console_output.setReadOnly(True)
        self.console_output.setMaximumBlockCount(5000)
        self.console_output.setFont(QFont("Cascadia Code" if QFont("Cascadia Code").exactMatch() else "Consolas", 9.5))
        c_lay.addWidget(self.console_output)

        # REPL input row
        repl_bar = QFrame()
        repl_bar.setObjectName("replBar")
        r_row = QHBoxLayout(repl_bar)
        r_row.setContentsMargins(6, 2, 6, 2)
        r_row.setSpacing(6)
        r_prompt = QLabel(">")
        r_prompt.setStyleSheet("color: #0284c7; font-weight: bold; font-size: 12px;")
        r_row.addWidget(r_prompt)

        self.repl_input = QLineEdit()
        self.repl_input.setObjectName("replInput")
        self.repl_input.setPlaceholderText("Type R expression (e.g. summary(df), plot(df[[1]]), ?lm)...")
        self.repl_input.returnPressed.connect(self._run_repl)
        self.repl_input.installEventFilter(self)
        r_row.addWidget(self.repl_input)
        c_lay.addWidget(repl_bar)

        left_v_split.addWidget(self.console_frame)
        main_h_split.addWidget(left_v_split)

        # Top-Right: Environment / Variable Explorer
        self.env_frame = QFrame()
        self.env_frame.setObjectName("envFrame")
        e_lay = QVBoxLayout(self.env_frame)
        e_lay.setContentsMargins(0, 0, 0, 0)
        e_lay.setSpacing(0)

        env_hdr = QFrame()
        env_hdr.setObjectName("panelHeader")
        env_hdr.setFixedHeight(30)
        eh_lay = QHBoxLayout(env_hdr)
        eh_lay.setContentsMargins(8, 0, 8, 0)
        eh_lay.setSpacing(6)
        eh_lay.addWidget(QLabel("Environment"))
        eh_lay.addStretch()

        btn_import_sheet = QToolButton()
        btn_import_sheet.setText("Import")
        btn_import_sheet.setToolTip("Export selected variable into a new StatCraft worksheet")
        btn_import_sheet.clicked.connect(self._import_selected_to_worksheet)
        eh_lay.addWidget(btn_import_sheet)

        btn_reset_env = QToolButton()
        btn_reset_env.setText("Reset")
        btn_reset_env.clicked.connect(self._reset_environment)
        eh_lay.addWidget(btn_reset_env)
        e_lay.addWidget(env_hdr)

        self.env_table = QTableWidget()
        self.env_table.setObjectName("envTable")
        self.env_table.setColumnCount(4)
        self.env_table.setHorizontalHeaderLabels(["Object", "Type", "Size", "Preview"])
        self.env_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.env_table.setColumnWidth(0, 116)
        self.env_table.setColumnWidth(1, 82)
        self.env_table.setColumnWidth(2, 70)
        self.env_table.setAlternatingRowColors(True)
        self.env_table.horizontalHeader().setStretchLastSection(True)
        self.env_table.verticalHeader().setVisible(False)
        self.env_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.env_table.itemDoubleClicked.connect(self._on_env_item_double_clicked)
        e_lay.addWidget(self.env_table)
        right_v_split.addWidget(self.env_frame)

        # Bottom-Right: Plots Gallery & R Help Tabs
        self.viz_tabs = QTabWidget()
        self.viz_tabs.setObjectName("vizTabs")

        self.plot_gallery = RPlotGalleryWidget()
        self.viz_tabs.addTab(self.plot_gallery, "Plots")

        self.help_viewer = RHelpViewerWidget()
        self.viz_tabs.addTab(self.help_viewer, "Help")

        right_v_split.addWidget(self.viz_tabs)
        main_h_split.addWidget(right_v_split)

        main_h_split.setSizes([750, 450])
        left_v_split.setSizes([450, 350])
        right_v_split.setSizes([350, 450])

        root_layout.addWidget(main_h_split)

    def set_dark_mode(self, is_dark: bool) -> None:
        """Fast, single-block theme update without multi-widget thrashing."""
        self._is_dark = is_dark
        for index in range(self.editor_tabs.count()):
            widget = self.editor_tabs.widget(index)
            if isinstance(widget, RCodeEditor):
                widget.set_dark_mode(is_dark)
        self.highlighter.set_dark_mode(is_dark)

        # Single consolidated stylesheet for the entire R workbench
        if is_dark:
            self.setStyleSheet("""
                QWidget { background-color: #18181b; color: #f4f4f5; font-family: 'Segoe UI'; font-size: 9pt; }
                QFrame#rHeader { background-color: #1f1f23; border-bottom: 1px solid #27272a; }
                QFrame#statusPill { background-color: #064e3b; border: 1px solid #059669; border-radius: 4px; }
                QFrame#panelHeader { background-color: #1f1f23; border-bottom: 1px solid #27272a; }
                QFrame#consoleFrame, QFrame#envFrame { background-color: #18181b; }
                QFrame#replBar { background-color: #1f1f23; border-top: 1px solid #27272a; }
                QFrame#rBanner { background-color: #450a0a; border-bottom: 1px solid #7f1d1d; }
                QPlainTextEdit#consoleOutput { background-color: #18181b; color: #f4f4f5; border: none; }
                QLineEdit#replInput { background-color: #27272a; color: #f4f4f5; border: 1px solid #3f3f46; border-radius: 4px; padding: 3px 6px; }
                QLineEdit#replInput:focus { border-color: #0284c7; }
                QTableWidget { background-color: #18181b; color: #f4f4f5; gridline-color: #27272a; border: none; }
                QHeaderView::section { background-color: #27272a; color: #d4d4d8; border: none; border-bottom: 1px solid #3f3f46; padding: 3px 6px; }
                QTabWidget::pane { border: 1px solid #27272a; background-color: #18181b; }
                QTabBar::tab { background-color: #1f1f23; color: #a1a1aa; padding: 6px 12px; border: 1px solid #27272a; border-bottom: none; }
                QTabBar::tab:selected { background-color: #18181b; color: #ffffff; border-top: 2px solid #0284c7; }
                QPushButton, QToolButton { background-color: #27272a; color: #f4f4f5; border: 1px solid #3f3f46; border-radius: 4px; padding: 3px 8px; font-weight: 500; }
                QPushButton:disabled, QToolButton:disabled { color: #80858d; }
                QPushButton:hover, QToolButton:hover { background-color: #3f3f46; color: #ffffff; border-color: #0284c7; }
                QSplitter::handle { background-color: #27272a; }
            """)
        else:
            self.setStyleSheet("""
                QWidget { background-color: #ffffff; color: #1e293b; font-family: 'Segoe UI'; font-size: 9pt; }
                QFrame#rHeader { background-color: #f8fafc; border-bottom: 1px solid #e2e8f0; }
                QFrame#statusPill { background-color: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 4px; }
                QFrame#panelHeader { background-color: #f1f5f9; border-bottom: 1px solid #e2e8f0; }
                QFrame#consoleFrame, QFrame#envFrame { background-color: #ffffff; }
                QFrame#replBar { background-color: #f8fafc; border-top: 1px solid #e2e8f0; }
                QFrame#rBanner { background-color: #fef2f2; border-bottom: 1px solid #fecaca; }
                QPlainTextEdit#consoleOutput { background-color: #ffffff; color: #1e293b; border: none; }
                QLineEdit#replInput { background-color: #ffffff; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; }
                QLineEdit#replInput:focus { border-color: #0284c7; }
                QTableWidget { background-color: #ffffff; color: #1e293b; gridline-color: #e2e8f0; border: none; }
                QHeaderView::section { background-color: #f8fafc; color: #475569; border: none; border-bottom: 1px solid #cbd5e1; padding: 3px 6px; }
                QTabWidget::pane { border: 1px solid #e2e8f0; background-color: #ffffff; }
                QTabBar::tab { background-color: #f1f5f9; color: #64748b; padding: 6px 12px; border: 1px solid #e2e8f0; border-bottom: none; }
                QTabBar::tab:selected { background-color: #ffffff; color: #0284c7; border-top: 2px solid #0284c7; font-weight: 600; }
                QPushButton, QToolButton { background-color: #ffffff; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 8px; font-weight: 500; }
                QPushButton:disabled, QToolButton:disabled { color: #80858d; }
                QPushButton:hover, QToolButton:hover { background-color: #f1f5f9; color: #0284c7; border-color: #0284c7; }
                QSplitter::handle { background-color: #e2e8f0; }
            """)
        self.update()

    def _check_and_update_r_status(self):
        if self._status_checking:
            return
        self._status_checking = True
        self.status_text.setText("Checking R…")
        _start_job(get_r_version, self._show_r_status)

    def _show_r_status(self, version):
        self._status_checking = False
        self._status_checked = True
        available = isinstance(version, str) and bool(version)
        match = re.search(r"\bversion\s+([0-9.]+)", version, re.IGNORECASE) if available else None
        self.status_text.setText(f"R {match[1]}" if match else ("R ready" if available else "R unavailable"))
        self.status_text.setToolTip(version if available else "Choose an installed R executable.")
        self.r_banner.setVisible(not available)
        if self._cancel is None:
            self.con_status_lbl.setText("Ready" if available else "Locate R to run scripts")
        if available and not self.console_output.toPlainText():
            self.console_output.setPlainText("Run a selection or line with Ctrl+Enter. The active worksheet is available as df.")

    def run_selection_or_line(self) -> None:
        """Positron line runner: executes selection or current line and advances cursor to next line."""
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            code = cursor.selectedText().replace("\u2029", "\n")
            self._execute_r(code)
        else:
            block = cursor.block()
            line = block.text()
            if line.strip():
                self._execute_r(line)
            # Advance to the next line
            cursor.movePosition(QTextCursor.MoveOperation.Down)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
            self.editor.setTextCursor(cursor)

    def run_all(self) -> None:
        """Execute the entire active R script."""
        code = self.editor.toPlainText()
        self._execute_r(code)

    def open_data_viewer_tab(self) -> None:
        """Switch to or refresh the View(df) spreadsheet data viewer."""
        ws = self.presenter.worksheet if self.presenter else None
        self.data_viewer.load_worksheet(ws)
        self.editor_tabs.setTabText(self.editor_tabs.indexOf(self.data_viewer), "Worksheet")
        self.editor_tabs.setCurrentWidget(self.data_viewer)

    def _select_editor(self, index):
        widget = self.editor_tabs.widget(index)
        if isinstance(widget, RCodeEditor):
            self.editor = widget

    def _close_tab(self, index: int) -> None:
        widget = self.editor_tabs.widget(index)
        if index > 1 and widget is not None:
            self.editor_tabs.removeTab(index)
            widget.deleteLater()
            active = self.editor_tabs.currentWidget()
            self.editor = active if isinstance(active, RCodeEditor) else self.editor_tabs.widget(0)

    def _on_env_item_double_clicked(self, item: QTableWidgetItem) -> None:
        name = self.env_table.item(item.row(), 0).text() if self.env_table.item(item.row(), 0) else ""
        if name in ("df", "worksheet") or "data.frame" in (self.env_table.item(item.row(), 1).text() if self.env_table.item(item.row(), 1) else ""):
            self._view_object(name)

    def _run_repl(self) -> None:
        expr = self.repl_input.text().strip()
        if not expr or self._cancel is not None:
            return
        self._history.append(expr)
        self._history_idx = -1
        self.repl_input.clear()

        # Intercept help requests '?topic'
        if expr.startswith("?") or expr.startswith("help("):
            match = re.match(r"^(?:\?|help\()(['\"]?)([\w.]+)\1\)?", expr)
            if match:
                topic = match.group(2)
                self.viz_tabs.setCurrentWidget(self.help_viewer)
                self.help_viewer.show_topic_help(topic)
                self.console_output.appendPlainText(f"> {expr}\n[Displaying help for '{topic}' in Help Pane]")
                return

        view = re.fullmatch(r"View\(\s*([\w.]+)\s*\)", expr, re.IGNORECASE)
        if view:
            self._view_object(view.group(1))
        else:
            self._execute_r(expr, is_repl=True)

    def history_prev(self) -> None:
        """Recall previous command in REPL history."""
        if not self._history:
            return
        if self._history_idx == -1:
            self._history_idx = len(self._history) - 1
        elif self._history_idx > 0:
            self._history_idx -= 1
        self.repl_input.setText(self._history[self._history_idx])

    def sync_active_worksheet_to_r(self, silent: bool = False) -> None:
        """Actively export and bind the current worksheet into the running R session as 'df' and 'worksheet'."""
        ws = getattr(self.presenter, "worksheet", None) if self.presenter else None
        if not ws:
            return
        self._source = None
        self._execute_r(
            f"# [StatCraft Connect: Active worksheet '{ws.name}' ({ws.row_count} rows, {len(ws.columns)} cols) synchronized]\n"
            f"cat('[StatCraft Connect] df ready: ', nrow(df), ' observations, ', ncol(df), ' variables.\n')",
            is_repl=True
        )

    def load_connected_analysis(self, connected) -> None:
        """Load a StatCraft Connect model into the editor and display connection banner."""
        self._connected_analysis = connected
        title = connected.get("title") if isinstance(connected, dict) else getattr(connected, "title", "Model")
        resp = connected.get("response_name") if isinstance(connected, dict) else getattr(connected, "response_name", "Y")
        r_script = connected.get("r_script") if isinstance(connected, dict) else getattr(connected, "r_script", "")

        if hasattr(self, "connect_tag"):
            self.connect_tag.setText(f"Model: {title}")
            self.connect_tag.show()
        if hasattr(self, "btn_sync_top"):
            self.btn_sync_top.show()

        if r_script:
            self.editor.setPlainText(r_script)
            self.editor_tabs.setCurrentWidget(self.editor)
            self.editor_tabs.setTabText(0, f"Connect_{resp}.R")

        ws_name = self.presenter.worksheet.name if self.presenter and hasattr(self.presenter, "worksheet") else ""
        self.console_output.appendPlainText(
            f"\n[StatCraft Connect: Linked to {title}]\n"
            f"Active worksheet '{ws_name}' is bound as 'df'.\n"
            "Press Ctrl+Enter to step through line-by-line, or click 'Run All'.\n"
            "-----------------------------------------------------------------------------------\n"
        )
        self.console_output.ensureCursorVisible()
        self.sync_active_worksheet_to_r()

    def apply_connected_predictions(self) -> None:
        """Extract predictions from active session or model and apply to worksheet."""
        if not self._connected_analysis or not self.main_window:
            return
        if hasattr(self.main_window, "connect_apply_predictions"):
            self.main_window.connect_apply_predictions({"connected_analysis": self._connected_analysis})

    def history_next(self) -> None:
        """Recall next command in REPL history."""
        if not self._history:
            return
        if self._history_idx < len(self._history) - 1 and self._history_idx != -1:
            self._history_idx += 1
            self.repl_input.setText(self._history[self._history_idx])
        else:
            self._history_idx = -1
            self.repl_input.clear()

    def eventFilter(self, obj, event):
        if obj == getattr(self, "repl_input", None) and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Up:
                self.history_prev()
                return True
            elif event.key() == Qt.Key.Key_Down:
                self.history_next()
                return True
        return super().eventFilter(obj, event)

    def _execute_r(self, code, is_repl=False, *, view_name=None):
        if self._cancel is not None or not code.strip():
            return
        source = self.presenter.worksheet if self.presenter else None
        key = (source, getattr(self.presenter, "_revision", 0))
        if self._source is None or self._source[0] is not source or self._source[1] != key[1]:
            self._source = key
            self._snapshot_key = object()
            self._snapshot = Worksheet(source.name, [
                Column(col.name, col.kind, list(col.values)) for col in source.columns
            ]) if source else None
        session = self._session
        snapshot = self._snapshot
        snapshot_key = self._snapshot_key
        cancelled = self._cancel = threading.Event()
        self._job_view = view_name
        self._job_source = source
        self._set_running(True)
        self.con_status_lbl.setText("Running…")
        if view_name is None:
            self.console_output.appendPlainText("> " + code.strip())
        _start_job(lambda: session.execute_instant(code, worksheet=snapshot,
                    worksheet_key=snapshot_key, cancelled=cancelled, timeout=None), self._finish_r)

    def _set_running(self, running):
        self.btn_stop.setEnabled(running)
        self.btn_run_sel.setEnabled(not running)
        self.btn_run_all.setEnabled(not running)
        self.repl_input.setReadOnly(running)

    def _finish_r(self, result):
        cancelled = self._cancel is not None and self._cancel.is_set()
        self._cancel = None
        self._set_running(False)
        if cancelled:
            self.con_status_lbl.setText("Stopped")
            self.console_output.appendPlainText("Stopped. Run a command to start a fresh session.")
            self.refresh_environment([])
            return
        if isinstance(result, Exception):
            self.con_status_lbl.setText("Error")
            self.console_output.appendPlainText(str(result))
            return
        elapsed = result.get("duration_ms", 0)
        self.con_status_lbl.setText(f"{'Ready' if result['success'] else 'Error'} · {elapsed:.0f} ms")
        if result.get("stdout"):
            self.console_output.appendPlainText(result["stdout"])
        if result.get("stderr"):
            self.console_output.appendPlainText("Error: " + result["stderr"])
        for path in result.get("plot_paths", []):
            self.plot_gallery.add_plot(path)
        if result.get("plot_paths"):
            self.viz_tabs.setCurrentWidget(self.plot_gallery)
        if result["success"]:
            for name, data in result["exported_worksheets"].items():
                if name == "Bootstrap_Summary" and self._connected_analysis and self.presenter:
                    try:
                        metric_map = {}
                        cols = data.get("columns", [])
                        if len(cols) >= 2:
                            for m, v in zip(cols[0]["values"], cols[1]["values"]):
                                metric_map[str(m)] = v
                        from .connect import ConnectedAnalysis
                        from .connect_r import create_bootstrap_result_entry
                        conn_obj = (
                            ConnectedAnalysis.from_dict(self._connected_analysis)
                            if isinstance(self._connected_analysis, dict)
                            else self._connected_analysis
                        )
                        cand_pts = self.presenter.worksheet.metadata.get("candidate_points", []) if hasattr(self.presenter.worksheet, "metadata") else []
                        cand_point = cand_pts[-1].get("factors", {}) if cand_pts else {}
                        card_entry = create_bootstrap_result_entry(conn_obj, cand_point, metric_map)
                        self.presenter.history.append(card_entry)
                        if self.main_window and hasattr(self.main_window, "show_result"):
                            self.main_window.show_result(card_entry)
                        self.console_output.appendPlainText(
                            f"\n[StatCraft Connect] Created Result Card: 'R Bootstrap Uncertainty: {conn_obj.response_name}'"
                        )
                    except Exception as exc:
                        self.console_output.appendPlainText(f"[StatCraft Connect] Could not construct Bootstrap card: {exc}")
                    continue

                try:
                    sheet = Worksheet(self._job_view or name, [
                        Column(col["name"], col["kind"], col["values"]) for col in data["columns"]
                    ])
                    if self._job_view:
                        self.data_viewer.load_worksheet(sheet)
                        self.editor_tabs.setTabText(self.editor_tabs.indexOf(self.data_viewer), self._job_view)
                        self.editor_tabs.setCurrentWidget(self.data_viewer)
                    elif self.presenter:
                        self._install_export(sheet)
                except (ValueError, OSError, TypeError) as exc:
                    self.console_output.appendPlainText(f"Could not import {name}. {exc}")
        self.refresh_environment(result.get("environment", []))
        self.console_output.ensureCursorVisible()

    def _install_export(self, sheet):
        from .data_prep_dialogs import install, destinations
        target = ("New worksheet" if self.presenter.worksheet is self._job_source
                  and "New worksheet" in destinations(self.presenter) else "New project")
        if target == "New worksheet":
            project = self.presenter.native_project
            sheets = project.worksheets if project else [self.presenter.worksheet]
            used = {item.name.casefold() for item in sheets}
            original = sheet.name
            sequence = 2
            while sheet.name.casefold() in used:
                sheet.name = f"{original} {sequence}"
                sequence += 1
        install(self.main_window, sheet, target)
        if target == "New worksheet":
            self._job_source = self.presenter.worksheet
        self.console_output.appendPlainText(f"Imported {sheet.name} ({sheet.row_count} rows).")

    def refresh_environment(self, env_vars=None):
        if env_vars is None:
            if self.env_table.rowCount():
                return
            ws = self.presenter.worksheet if self.presenter else None
            if ws is None:
                return
            shape = f"{ws.row_count} × {len(ws.columns)}"
            env_vars = [
                {"name": "df", "type": "data.frame", "length": shape, "value": "Active worksheet"},
                {"name": "worksheet", "type": "data.frame", "length": shape, "value": "Alias of df"},
            ]
            env_vars.extend({"name": f'df$"{col.name}"', "type": col.kind,
                             "length": str(len(col.values)), "value": ""}
                            for col in ws.columns[:100])
        self.env_table.setUpdatesEnabled(False)
        try:
            self.env_table.setRowCount(len(env_vars))
            for row_index, row in enumerate(env_vars):
                for column, key in enumerate(("name", "type", "length", "value")):
                    self.env_table.setItem(row_index, column, QTableWidgetItem(str(row.get(key, ""))))
        finally:
            self.env_table.setUpdatesEnabled(True)

    def _object_expression(self, name):
        if name.startswith('df$"') and name.endswith('"'):
            return "df[[" + json.dumps(name[4:-1], ensure_ascii=False) + "]]"
        return "get(" + json.dumps(name, ensure_ascii=False) + ", envir=.GlobalEnv, inherits=FALSE)"

    def _view_object(self, name):
        self._execute_r(f'statcraft_export({self._object_expression(name)}, "viewer")', view_name=name)

    def _import_selected_to_worksheet(self):
        row = self.env_table.currentRow()
        if row < 0:
            self.con_status_lbl.setText("Select an environment object")
            return
        name = self.env_table.item(row, 0).text()
        self._execute_r(f"statcraft_export({self._object_expression(name)}, {json.dumps(name, ensure_ascii=False)})")

    def stop_execution(self):
        if self._cancel is not None:
            self._cancel.set()
            self._session.interrupt()
            self.con_status_lbl.setText("Stopping…")

    def shutdown(self, *, wait=False):
        if self._cancel is not None:
            self._cancel.set()
        self._session.interrupt(wait=wait)

    def _reset_environment(self):
        self._restart_session()

    def _clear_console(self):
        self.console_output.clear()

    def _restart_session(self):
        self.shutdown()
        self.refresh_environment([])
        if self._cancel is None:
            self.con_status_lbl.setText("Ready")
            self.console_output.appendPlainText("R session cleared. The next command starts a new session.")

    def _show_templates_menu(self) -> None:
        menu = QMenu(self)
        for title, template_code in self.TEMPLATES.items():
            act = menu.addAction(title)
            act.triggered.connect(lambda chk=False, c=template_code: self.editor.setPlainText(c))
        menu.exec(self.btn_templates.mapToGlobal(QPoint(0, self.btn_templates.height())))

    def _open_script_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open R Script", "", "R Scripts (*.R *.r);;All Files (*.*)")
        if path:
            self.load_file(path)

    def load_file(self, path: str) -> None:
        p = Path(path)
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="ignore")
            # Open in new editor tab
            new_ed = RCodeEditor(workbench=self)
            new_ed.setPlainText(text)
            VSCodeRSyntaxHighlighter(new_ed.document(), is_dark=self._is_dark)
            idx = self.editor_tabs.addTab(new_ed, p.name)
            self.editor_tabs.setCurrentIndex(idx)
            self.editor = new_ed

    def _save_script_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save R Script", "script.R", "R Scripts (*.R);;All Files (*.*)")
        if path:
            Path(path).write_text(self.editor.toPlainText(), encoding="utf-8")

    def _browse_r_executable(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Locate Rscript.exe or R.exe", "C:\\", "Executables (*.exe);;All Files (*.*)")
        if path:
            from PySide6.QtCore import QSettings
            QSettings("StatCraft", "StatCraft").setValue("custom_r_path", path)
            find_r_executable(refresh=True)
            self._restart_session()
            self._check_and_update_r_status()

    def _install_r_automatically(self):
        self.btn_auto_install.setEnabled(False)
        self.b_text.setText("Installing R…")
        _start_job(lambda: download_and_install_r_direct() or install_r_via_winget(),
                   self._finish_install)

    def _finish_install(self, installed):
        self.btn_auto_install.setEnabled(True)
        self.b_text.setText("R installed." if installed is True else "R setup did not finish. Locate an existing installation or open CRAN.")
        find_r_executable(refresh=True)
        self._check_and_update_r_status()
