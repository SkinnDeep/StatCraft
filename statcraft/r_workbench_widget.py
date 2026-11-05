"""Positron-style R Workbench Platform for StatCraft.

Provides a full-featured R statistical workspace:
- Multi-pane data science environment:
  1. Top-Left: R Script Editor with syntax highlighting, line numbers, templates, and script load/save
  2. Bottom-Left: Interactive R Console (REPL) with command history (Up/Down)
  3. Top-Right: Environment / Data Object Inspector with 1-click 'Import to StatCraft Worksheet'
  4. Bottom-Right: Live Plot & Graphics Viewer with 1-click clipboard / export
- Direct bi-directional integration with StatCraft Worksheets and automatic worksheet creation
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QPixmap,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import (
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
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .model import Column, Worksheet
from .r_bridge import (
    execute_r_code,
    find_r_executable,
    get_r_version,
    is_r_available,
    reset_r_session,
)


class RSyntaxHighlighter(QSyntaxHighlighter):
    """Clean syntax highlighter for R scripts."""

    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        kw_format = QTextCharFormat()
        kw_format.setForeground(QColor("#0284c7"))  # Fluent Blue
        kw_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            r"\bif\b", r"\belse\b", r"\brepeat\b", r"\bwhile\b", r"\bfunction\b",
            r"\bfor\b", r"\bin\b", r"\bnext\b", r"\bbreak\b", r"\bTRUE\b",
            r"\bFALSE\b", r"\bNULL\b", r"\bNA\b", r"\bNaN\b", r"\bInf\b",
            r"\blibrary\b", r"\brequire\b", r"\bdata\.frame\b", r"\blm\b",
            r"\baov\b", r"\bsummary\b", r"\bplot\b", r"\bggplot\b", r"\bprint\b",
            r"\bstatcraft_export\b", r"\bstatcraft_save\b", r"\bprcomp\b", r"\bglm\b"
        ]
        for kw in keywords:
            self.rules.append((kw, kw_format))

        # Strings
        str_format = QTextCharFormat()
        str_format.setForeground(QColor("#16a34a"))  # Green
        self.rules.append((r'"[^"\\]*(\\.[^"\\]*)*"', str_format))
        self.rules.append((r"'[^'\\]*(\\.[^'\\]*)*'", str_format))

        # Numbers
        num_format = QTextCharFormat()
        num_format.setForeground(QColor("#d97706"))  # Amber
        self.rules.append((r"\b[0-9]+(\.[0-9]+)?\b", num_format))

        # Comments
        comm_format = QTextCharFormat()
        comm_format.setForeground(QColor("#94a3b8"))  # Muted Slate
        comm_format.setFontItalic(True)
        self.rules.append((r"#.*", comm_format))

    def highlightBlock(self, text: str) -> None:
        import re
        for pattern, fmt in self.rules:
            for match in re.finditer(pattern, text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)


class LineNumberArea(QWidget):
    """Gutter widget displaying line numbers for the script editor."""

    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:
        self.code_editor.line_number_area_paint_event(event)


class RCodeEditor(QPlainTextEdit):
    """Code editor with gutter line numbers and smooth cursor navigation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.update_line_number_area_width(0)
        self.highlight_current_line()

    def line_number_area_width(self) -> int:
        digits = max(1, len(str(max(1, self.blockCount()))))
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def update_line_number_area_width(self, _) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy) -> None:
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def highlight_current_line(self) -> None:
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEditSelection() if hasattr(self, 'QTextEditSelection') else None
        self.setExtraSelections(extra_selections)

    def line_number_area_paint_event(self, event) -> None:
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#f1f5f9"))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        painter.setFont(QFont("Consolas", 9))
        painter.setPen(QColor("#94a3b8"))

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.drawText(0, top, self.line_number_area.width() - 6, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1


class RWorkbenchWidget(QWidget):
    """Positron-style R data science workbench platform."""

    TEMPLATES = {
        "Linear Regression & Diagnostics": (
            "# 1. Linear Regression Model\n"
            "fit <- lm(df[[1]] ~ df[[2]], data=df)\n"
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
        self.presenter = main_window.presenter if main_window else None
        self._last_plot_path: Optional[str] = None
        self._history: List[str] = []
        self._history_idx: int = -1

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: #f8fafc; font-family: 'Segoe UI', sans-serif;")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # 1. Top Workbench Header Bar
        hdr = QHBoxLayout()
        hdr.setSpacing(10)

        title_lbl = QLabel("<b>R Data Science Workbench</b> (Mode)")
        title_lbl.setStyleSheet("font-size: 14px; color: #0f172a;")
        hdr.addWidget(title_lbl)

        r_ver = get_r_version() or "R not detected"
        ver_badge = QLabel(f"<b>{r_ver.splitlines()[0] if r_ver else 'CRAN R'}</b>")
        ver_badge.setStyleSheet(
            "background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-size: 11px;"
        )
        hdr.addWidget(ver_badge)

        hdr.addStretch()

        btn_open = QPushButton("Open Script…")
        btn_open.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        btn_open.clicked.connect(self._open_script_file)
        hdr.addWidget(btn_open)

        btn_save = QPushButton("Save Script…")
        btn_save.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; font-size: 11px;")
        btn_save.clicked.connect(self._save_script_file)
        hdr.addWidget(btn_save)

        self.btn_template = QPushButton("Templates ▾")
        self.btn_template.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 10px; font-size: 11px;")
        self.btn_template.clicked.connect(self._show_templates_menu)
        hdr.addWidget(self.btn_template)

        btn_run_sel = QPushButton("▶ Run Line / Selection")
        btn_run_sel.setToolTip("Run current line or selected code in R (Ctrl+Enter)")
        btn_run_sel.setStyleSheet(
            "QPushButton { background: #0284c7; color: white; border: none; border-radius: 4px; padding: 4px 12px; font-weight: 600; font-size: 11px; } "
            "QPushButton:hover { background: #0369a1; }"
        )
        btn_run_sel.clicked.connect(self.run_selection)
        hdr.addWidget(btn_run_sel)

        btn_run_all = QPushButton("▶▶ Run All")
        btn_run_all.setToolTip("Execute entire script in R")
        btn_run_all.setStyleSheet(
            "QPushButton { background: #ffffff; color: #334155; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 12px; font-weight: 600; font-size: 11px; } "
            "QPushButton:hover { background: #f1f5f9; }"
        )
        btn_run_all.clicked.connect(self.run_all)
        hdr.addWidget(btn_run_all)

        root_layout.addLayout(hdr)

        # 2. Main 4-Pane Splitter Layout (Positron / RStudio interaction architecture)
        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        left_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Pane 1: R Script Editor
        editor_card = self._create_card()
        ed_layout = QVBoxLayout(editor_card)
        ed_layout.setContentsMargins(8, 6, 8, 8)
        ed_layout.setSpacing(4)

        ed_hdr = QHBoxLayout()
        ed_hdr.addWidget(QLabel("<b>R SCRIPT EDITOR</b>"))
        ed_hdr.addStretch()
        ed_layout.addLayout(ed_hdr)

        self.editor = RCodeEditor()
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 4px; color: #0f172a;")
        self.highlighter = RSyntaxHighlighter(self.editor.document())

        default_code = (
            "# StatCraft R Data Science Workbench\n"
            "# Active worksheet is pre-loaded as 'df' and 'worksheet'\n\n"
            "# 1. Display summary of active worksheet\n"
            "print(summary(df))\n\n"
            "# 2. Linear Regression & Plot\n"
            "if (ncol(df) >= 2) {\n"
            "    fit <- lm(df[[2]] ~ df[[1]], data=df)\n"
            "    print(summary(fit))\n"
            "    plot(df[[1]], df[[2]], main='StatCraft R Regression',\n"
            "         xlab=colnames(df)[1], ylab=colnames(df)[2], pch=19, col='#0284c7')\n"
            "    abline(fit, col='#dc2626', lwd=2)\n"
            "}\n"
        )
        self.editor.setPlainText(default_code)
        ed_layout.addWidget(self.editor)
        left_splitter.addWidget(editor_card)

        # Pane 2: Interactive R Console (REPL)
        console_card = self._create_card()
        con_layout = QVBoxLayout(console_card)
        con_layout.setContentsMargins(8, 6, 8, 8)
        con_layout.setSpacing(4)

        con_hdr = QHBoxLayout()
        con_hdr.addWidget(QLabel("<b>R CONSOLE</b>"))
        con_hdr.addStretch()

        btn_clear_con = QPushButton("Clear Console")
        btn_clear_con.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 8px; font-size: 10px;")
        btn_clear_con.clicked.connect(self._clear_console)
        con_hdr.addWidget(btn_clear_con)
        con_layout.addLayout(con_hdr)

        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setFont(QFont("Consolas", 9.5))
        self.console_output.setStyleSheet("background: #0f172a; color: #f8fafc; border-radius: 4px; padding: 6px;")
        self.console_output.setPlainText(
            f"StatCraft R Console [Version: {r_ver}]\n"
            "Interactive R REPL active. Type expressions below or press Ctrl+Enter in the editor.\n"
            "-----------------------------------------------------------------------------------\n"
        )
        con_layout.addWidget(self.console_output)

        repl_row = QHBoxLayout()
        prompt_lbl = QLabel(">")
        prompt_lbl.setStyleSheet("color: #0284c7; font-weight: bold; font-family: Consolas; font-size: 13px;")
        repl_row.addWidget(prompt_lbl)

        self.repl_input = QLineEdit()
        self.repl_input.setFont(QFont("Consolas", 10))
        self.repl_input.setPlaceholderText("Enter R expression (e.g. summary(df), hist(df[[1]]), cor(df))...")
        self.repl_input.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px;")
        self.repl_input.returnPressed.connect(self._run_repl)
        repl_row.addWidget(self.repl_input)
        con_layout.addLayout(repl_row)

        left_splitter.addWidget(console_card)

        # Pane 3: Environment / Objects Inspector
        env_card = self._create_card()
        env_layout = QVBoxLayout(env_card)
        env_layout.setContentsMargins(8, 6, 8, 8)
        env_layout.setSpacing(4)

        env_hdr = QHBoxLayout()
        env_hdr.addWidget(QLabel("<b>ENVIRONMENT / DATA OBJECTS</b>"))
        env_hdr.addStretch()

        btn_import_sheet = QPushButton("Import to Worksheet")
        btn_import_sheet.setToolTip("Import selected R data.frame into a new StatCraft worksheet")
        btn_import_sheet.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 8px; font-size: 10px; font-weight: 600;")
        btn_import_sheet.clicked.connect(self._import_selected_to_worksheet)
        env_hdr.addWidget(btn_import_sheet)

        btn_reset_env = QPushButton("Reset Env")
        btn_reset_env.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 8px; font-size: 10px;")
        btn_reset_env.clicked.connect(self._reset_environment)
        env_hdr.addWidget(btn_reset_env)

        env_layout.addLayout(env_hdr)

        self.env_table = QTableWidget()
        self.env_table.setColumnCount(4)
        self.env_table.setHorizontalHeaderLabels(["Name", "Type", "Length / Dim", "Value Preview"])
        self.env_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.env_table.horizontalHeader().setStretchLastSection(True)
        self.env_table.verticalHeader().setVisible(False)
        self.env_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.env_table.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; font-size: 11px;")
        env_layout.addWidget(self.env_table)
        right_splitter.addWidget(env_card)

        # Pane 4: Plots & Visual Output
        plot_card = self._create_card()
        plot_layout = QVBoxLayout(plot_card)
        plot_layout.setContentsMargins(8, 6, 8, 8)
        plot_layout.setSpacing(4)

        plot_hdr = QHBoxLayout()
        plot_hdr.addWidget(QLabel("<b>R GRAPHICS & PLOTS</b>"))
        plot_hdr.addStretch()

        self.btn_copy_plot = QPushButton("Copy Plot")
        self.btn_copy_plot.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px 8px; font-size: 10px;")
        self.btn_copy_plot.clicked.connect(self._copy_plot)
        plot_hdr.addWidget(self.btn_copy_plot)

        plot_layout.addLayout(plot_hdr)

        self.plot_scroll = QScrollArea()
        self.plot_scroll.setWidgetResizable(True)
        self.plot_scroll.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 4px;")
        self.plot_label = QLabel("No graphics generated yet.\nRun a plotting command (e.g. plot(), hist(), ggplot()).")
        self.plot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.plot_label.setStyleSheet("color: #94a3b8; font-size: 11px; padding: 20px;")
        self.plot_scroll.setWidget(self.plot_label)
        plot_layout.addWidget(self.plot_scroll)

        right_splitter.addWidget(plot_card)

        # Set initial splitter proportions
        left_splitter.setSizes([340, 260])
        right_splitter.setSizes([260, 340])
        h_splitter.addWidget(left_splitter)
        h_splitter.addWidget(right_splitter)
        h_splitter.setSizes([580, 520])

        root_layout.addWidget(h_splitter)

        self.refresh_environment()

    def _create_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px;")
        return card

    def refresh_environment(self, custom_objects: Optional[List[Dict[str, str]]] = None) -> None:
        """Populate Environment table with active worksheet dataframe and R objects."""
        rows = []
        if self.presenter and self.presenter.worksheet:
            ws = self.presenter.worksheet
            n_rows = ws.row_count
            n_cols = len(ws.columns)
            rows.append(("df", "data.frame", f"{n_rows}x{n_cols}", f"Columns: {', '.join(c.name for c in ws.columns[:3])}..."))
            rows.append(("worksheet", "data.frame", f"{n_rows}x{n_cols}", "Alias of df"))
            for col in ws.columns:
                rows.append((
                    f"df${col.name}",
                    col.kind,
                    f"{len(col.values)} items",
                    f"{col.values[:3]}..." if col.values else "empty",
                ))

        if custom_objects:
            for obj in custom_objects:
                if obj.get("name") not in ("df", "worksheet"):
                    rows.append((
                        obj.get("name", ""),
                        obj.get("type", ""),
                        obj.get("dim", ""),
                        obj.get("preview", ""),
                    ))

        self.env_table.setRowCount(len(rows))
        for r_idx, r_data in enumerate(rows):
            for c_idx, val in enumerate(r_data):
                item = QTableWidgetItem(str(val))
                if c_idx == 0:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(QColor("#0284c7"))
                self.env_table.setItem(r_idx, c_idx, item)

    def run_selection(self) -> None:
        """Run selected lines or current line in R."""
        cursor = self.editor.textCursor()
        code = cursor.selectedText()
        if not code.strip():
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            code = cursor.selectedText()
        if not code.strip():
            code = self.editor.toPlainText()
        self._execute_r(code)

    def run_all(self) -> None:
        """Run entire script."""
        code = self.editor.toPlainText()
        self._execute_r(code)

    def _run_repl(self) -> None:
        expr = self.repl_input.text().strip()
        if not expr:
            return
        self._history.append(expr)
        self._history_idx = len(self._history)
        self.repl_input.clear()
        self._execute_r(expr, is_repl=True)

    def _execute_r(self, code: str, is_repl: bool = False) -> None:
        ws = self.presenter.worksheet if self.presenter else None
        self.console_output.appendPlainText(f"> {code.strip()}")

        res = execute_r_code(code, worksheet=ws, persist_session=True)
        if res.get("stdout"):
            self.console_output.appendPlainText(res["stdout"].rstrip())
        if res.get("stderr") and not res.get("success"):
            self.console_output.appendPlainText(f"Error: {res['stderr'].strip()}")

        # Update Plot View if graphic was generated
        if res.get("plot_path"):
            self._last_plot_path = res["plot_path"]
            pix = QPixmap(res["plot_path"])
            if not pix.isNull():
                self.plot_label.setPixmap(pix.scaled(
                    self.plot_scroll.viewport().size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))

        # Check for automatically exported worksheets from R
        exported = res.get("exported_worksheets", {})
        if exported and self.main_window and self.presenter:
            for sheet_name, sheet_dict in exported.items():
                cols = [Column(c["name"], kind=c.get("kind", "number"), values=c.get("values", [])) for c in sheet_dict.get("columns", [])]
                if hasattr(self.presenter, "add_worksheet"):
                    try:
                        new_ws = self.presenter.add_worksheet(sheet_name)
                        new_ws.columns = cols
                    except Exception:
                        new_ws = Worksheet(sheet_name, cols)
                        self.presenter.worksheet = new_ws
                else:
                    self.presenter.worksheet = Worksheet(sheet_name, cols)
            if hasattr(self.main_window, "refresh"):
                self.main_window.refresh()
            self.main_window.statusBar().showMessage(f"Created {len(exported)} new worksheet(s) from R export!", 4000)

        # Update environment inspector
        self.refresh_environment(res.get("environment"))

    def _import_selected_to_worksheet(self) -> None:
        """Trigger R to export the currently selected object as a StatCraft worksheet."""
        curr_row = self.env_table.currentRow()
        if curr_row < 0:
            QMessageBox.information(self, "Import to Worksheet", "Please select an object in the Environment table to import.")
            return
        obj_name = self.env_table.item(curr_row, 0).text()
        obj_type = self.env_table.item(curr_row, 1).text()

        # Execute export command in R
        cmd = f"statcraft_export(as.data.frame({obj_name}), '{obj_name}')"
        self._execute_r(cmd)

    def _clear_console(self) -> None:
        self.console_output.clear()

    def _reset_environment(self) -> None:
        reset_r_session()
        self.refresh_environment()
        self.console_output.appendPlainText("\n[R session workspace reset to clean state]\n")

    def _copy_plot(self) -> None:
        if self._last_plot_path and os.path.isfile(self._last_plot_path):
            pix = QPixmap(self._last_plot_path)
            QGuiApplication.clipboard().setPixmap(pix)
            if self.main_window:
                self.main_window.statusBar().showMessage("Plot copied to clipboard", 3000)

    def _show_templates_menu(self) -> None:
        menu = QMenu(self)
        for t_name, code in self.TEMPLATES.items():
            menu.addAction(t_name, lambda c=code: self.editor.appendPlainText(f"\n{c}"))
        menu.exec(self.btn_template.mapToGlobal(self.btn_template.rect().bottomLeft()))

    def _open_script_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open R Script", "", "R Scripts (*.R *.r);;All Files (*.*)")
        if path:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
            self.editor.setPlainText(text)
            if self.main_window:
                self.main_window.statusBar().showMessage(f"Loaded {Path(path).name}", 3000)

    def _save_script_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save R Script", "script.R", "R Scripts (*.R);;All Files (*.*)")
        if path:
            Path(path).write_text(self.editor.toPlainText(), encoding="utf-8")
            if self.main_window:
                self.main_window.statusBar().showMessage(f"Saved {Path(path).name}", 3000)
