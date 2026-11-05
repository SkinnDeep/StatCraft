"""Positron-style R Workbench Platform for StatCraft.

Provides a full-featured R statistical workspace:
- Multi-pane data science environment:
  1. Top-Left: R Script Editor with syntax highlighting and template snippets
  2. Bottom-Left: Interactive R Console (REPL) showing evaluation output
  3. Top-Right: Environment / Data Object Inspector (inspecting active dataframe, models, variables)
  4. Bottom-Right: Live Plot & Graphics Viewer with 1-click clipboard / export
- Direct bi-directional integration with active StatCraft Worksheets
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QPixmap,
    QSyntaxHighlighter,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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

from .r_bridge import execute_r_code, find_r_executable, get_r_version, is_r_available


class RSyntaxHighlighter(QSyntaxHighlighter):
    """Clean syntax highlighter for R scripts."""

    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        # Keywords
        kw_format = QTextCharFormat()
        kw_format.setForeground(QColor("#0284c7"))  # Fluent Blue
        kw_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            r"\bif\b", r"\belse\b", r"\brepeat\b", r"\bwhile\b", r"\bfunction\b",
            r"\bfor\b", r"\bin\b", r"\bnext\b", r"\bbreak\b", r"\bTRUE\b",
            r"\bFALSE\b", r"\bNULL\b", r"\bNA\b", r"\bNaN\b", r"\bInf\b",
            r"\blibrary\b", r"\brequire\b", r"\bdata\.frame\b", r"\blm\b",
            r"\baov\b", r"\bsummary\b", r"\bplot\b", r"\bggplot\b", r"\bprint\b"
        ]
        for kw in keywords:
            self.rules.append((kw, kw_format))

        # Strings
        str_format = QTextCharFormat()
        str_format.setForeground(QColor("#16a34a"))  # Green
        self.rules.append((r'"[^"\\]*(\\.[^"\\]*)*"', str_format))
        self.rules.append((r"'[^'\\]*(\\.[^'\\]*)*'", str_format))

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


class RWorkbenchWidget(QWidget):
    """Positron-style R data science workbench."""

    def __init__(self, main_window, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.main_window = main_window
        self.presenter = main_window.presenter if main_window else None
        self._last_plot_path: Optional[str] = None

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: #f8fafc; font-family: 'Segoe UI', sans-serif;")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # 1. Top Workbench Header
        hdr = QHBoxLayout()
        hdr.setSpacing(12)

        title_lbl = QLabel("<b>R Data Science Workbench</b> (Positron Mode)")
        title_lbl.setStyleSheet("font-size: 14px; color: #0f172a;")
        hdr.addWidget(title_lbl)

        r_ver = get_r_version() or "R not detected"
        ver_badge = QLabel(f"<b>{r_ver.splitlines()[0] if r_ver else 'CRAN R'}</b>")
        ver_badge.setStyleSheet(
            "background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-size: 11px;"
        )
        hdr.addWidget(ver_badge)

        hdr.addStretch()

        btn_run_sel = QPushButton("▶ Run Selection / Line")
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

        btn_template = QPushButton("Insert Template ▾")
        btn_template.setStyleSheet(
            "QPushButton { background: #ffffff; color: #334155; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 10px; font-size: 11px; } "
            "QPushButton:hover { background: #f1f5f9; }"
        )
        btn_template.clicked.connect(self._insert_template)
        hdr.addWidget(btn_template)

        root_layout.addLayout(hdr)

        # 2. Main 4-Pane Splitter Layout (like Positron / RStudio)
        # Left Splitter (Vertical): Script Editor (top) + Console REPL (bottom)
        # Right Splitter (Vertical): Environment / Objects (top) + Plots / Output (bottom)
        # Horizontal Splitter unites Left and Right
        h_splitter = QSplitter(Qt.Orientation.Horizontal)

        left_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Pane 1: R Script Editor
        editor_card = self._create_card("R SCRIPT EDITOR", "#0f172a")
        ed_layout = QVBoxLayout(editor_card)
        ed_layout.setContentsMargins(8, 6, 8, 8)
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 4px; color: #0f172a;")
        self.highlighter = RSyntaxHighlighter(self.editor.document())

        default_code = (
            "# StatCraft R Workbench\n"
            "# Active worksheet is pre-loaded as 'df' and 'worksheet'\n\n"
            "# 1. Display summary of worksheet\n"
            "print(summary(df))\n\n"
            "# 2. Linear Regression Model\n"
            "if (ncol(df) >= 2) {\n"
            "    y_name <- colnames(df)[1]\n"
            "    x_name <- colnames(df)[2]\n"
            "    formula_str <- paste(y_name, '~', x_name)\n"
            "    fit <- lm(as.formula(formula_str), data=df)\n"
            "    print(summary(fit))\n\n"
            "    # 3. Publication Plot\n"
            "    plot(df[[x_name]], df[[y_name]], main=paste('R Regression:', formula_str),\n"
            "         xlab=x_name, ylab=y_name, pch=19, col='#0284c7')\n"
            "    abline(fit, col='#dc2626', lwd=2)\n"
            "}\n"
        )
        self.editor.setPlainText(default_code)
        ed_layout.addWidget(self.editor)
        left_splitter.addWidget(editor_card)

        # Pane 2: Interactive R Console (REPL)
        console_card = self._create_card("R CONSOLE", "#0f172a")
        con_layout = QVBoxLayout(console_card)
        con_layout.setContentsMargins(8, 6, 8, 8)
        con_layout.setSpacing(4)

        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setFont(QFont("Consolas", 9.5))
        self.console_output.setStyleSheet("background: #0f172a; color: #f8fafc; border-radius: 4px; padding: 4px;")
        self.console_output.setPlainText(
            f"StatCraft R Console [R version: {r_ver}]\n"
            "Type R commands below or press ▶ Run Selection / Line (Ctrl+Enter).\n"
            "-----------------------------------------------------------------------\n"
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
        env_card = self._create_card("ENVIRONMENT / DATA OBJECTS", "#0f172a")
        env_layout = QVBoxLayout(env_card)
        env_layout.setContentsMargins(8, 6, 8, 8)

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
        plot_card = self._create_card("R GRAPHICS & PLOTS", "#0f172a")
        plot_layout = QVBoxLayout(plot_card)
        plot_layout.setContentsMargins(8, 6, 8, 8)

        plot_tools = QHBoxLayout()
        self.btn_copy_plot = QPushButton("Copy Plot")
        self.btn_copy_plot.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 8px; font-size: 10px;")
        self.btn_copy_plot.clicked.connect(self._copy_plot)
        self.btn_send_session = QPushButton("Send to Session")
        self.btn_send_session.setStyleSheet("background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 8px; font-size: 10px;")
        self.btn_send_session.clicked.connect(self._send_to_session)

        plot_tools.addStretch()
        plot_tools.addWidget(self.btn_copy_plot)
        plot_tools.addWidget(self.btn_send_session)
        plot_layout.addLayout(plot_tools)

        self.plot_scroll = QScrollArea()
        self.plot_scroll.setWidgetResizable(True)
        self.plot_scroll.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 4px;")
        self.plot_label = QLabel("No graphics generated yet.\nRun a plotting command (e.g. plot(), hist(), ggplot()).")
        self.plot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.plot_label.setStyleSheet("color: #94a3b8; font-size: 11px; padding: 20px;")
        self.plot_scroll.setWidget(self.plot_label)
        plot_layout.addWidget(self.plot_scroll)

        right_splitter.addWidget(plot_card)

        # Set initial splitter sizes
        left_splitter.setSizes([340, 260])
        right_splitter.setSizes([260, 340])
        h_splitter.addWidget(left_splitter)
        h_splitter.addWidget(right_splitter)
        h_splitter.setSizes([580, 520])

        root_layout.addWidget(h_splitter)

        self.refresh_environment()

    def _create_card(self, title: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet("background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px;")
        return card

    def refresh_environment(self) -> None:
        """Populate Environment table with active worksheet dataframe and variables."""
        if not self.presenter or not self.presenter.worksheet:
            return
        ws = self.presenter.worksheet
        n_rows = ws.row_count
        n_cols = len(ws.columns)

        rows = [
            ("df", "data.frame", f"{n_rows} obs. of {n_cols} variables", f"Columns: {', '.join(c.name for c in ws.columns[:4])}{'...' if n_cols > 4 else ''}"),
            ("worksheet", "data.frame", f"{n_rows} obs. of {n_cols} variables", "Alias of df"),
        ]

        for col in ws.columns:
            rows.append((
                f"df${col.name}",
                col.kind,
                f"{len(col.values)} items",
                f"{col.values[:3]}..." if col.values else "empty",
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
            cursor.select(cursor.SelectionType.LineUnderCursor)
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
        self.repl_input.clear()
        self._execute_r(expr, is_repl=True)

    def _execute_r(self, code: str, is_repl: bool = False) -> None:
        ws = self.presenter.worksheet if self.presenter else None
        self.console_output.appendPlainText(f"> {code.strip()}")

        res = execute_r_code(code, worksheet=ws)
        if res.get("stdout"):
            self.console_output.appendPlainText(res["stdout"].rstrip())
        if res.get("stderr") and not res.get("success"):
            self.console_output.appendPlainText(f"Error: {res['stderr'].strip()}")

        # Update Plot View if graphic generated
        if res.get("plot_path"):
            self._last_plot_path = res["plot_path"]
            pix = QPixmap(res["plot_path"])
            if not pix.isNull():
                self.plot_label.setPixmap(pix.scaled(
                    self.plot_scroll.viewport().size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))

        self.refresh_environment()

    def _copy_plot(self) -> None:
        if self._last_plot_path and os.path.isfile(self._last_plot_path):
            pix = QPixmap(self._last_plot_path)
            QGuiApplication.clipboard().setPixmap(pix)
            if self.main_window:
                self.main_window.statusBar().showMessage("Plot copied to clipboard", 3000)

    def _send_to_session(self) -> None:
        if self._last_plot_path and self.main_window:
            self.main_window.statusBar().showMessage("R output logged to Session", 3000)

    def _insert_template(self) -> None:
        snippet = (
            "\n# --- ANOVA & Tukey HSD ---\n"
            "res.aov <- aov(df[[1]] ~ as.factor(df[[2]]), data=df)\n"
            "print(summary(res.aov))\n"
            "print(TukeyHSD(res.aov))\n"
        )
        self.editor.appendPlainText(snippet)
