"""JMP-style Data Table Panel for StatCraft.

Provides authentic JMP table panel layout:
- Table metadata and executable Table Scripts (green play icons ▶)
- Columns panel with authentic JMP modeling type indicators (▲ Continuous, ▮ Nominal, 📶 Ordinal)
- Rows panel with selection/exclusion state counters and quick action buttons
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import Qt, QPointF, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPixmap,
    QPolygonF,
    QPen,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from .modern_app import ModernWindow


_ICON_CACHE: dict[str, QIcon] = {}


def get_jmp_icon(kind: str) -> QIcon:
    """Return cached crisp vector QIcon for JMP modeling types and scripts."""
    if kind in _ICON_CACHE:
        return _ICON_CACHE[kind]

    size = 16
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    kind_lower = (kind or "continuous").lower()
    if kind_lower in ("continuous", "number", "numeric"):
        # JMP Blue equilateral triangle pointing up
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#0277bd"))
        poly = QPolygonF([QPointF(8, 2.5), QPointF(2.5, 13.5), QPointF(13.5, 13.5)])
        p.drawPolygon(poly)
    elif kind_lower in ("nominal", "text", "category"):
        # JMP Red 3 distinct categorical bars
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#c62828"))
        p.drawRect(2, 6, 3, 8)
        p.drawRect(6, 3, 3, 11)
        p.drawRect(10, 8, 3, 6)
    elif kind_lower in ("ordinal", "ordered", "datetime"):
        # JMP Green ascending staircase steps
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2e7d32"))
        p.drawRect(2, 10, 3, 4)
        p.drawRect(6, 6, 3, 8)
        p.drawRect(10, 2, 3, 12)
    elif kind_lower == "play_script":
        # JMP green script play triangle ▶
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#2e7d32"))
        poly = QPolygonF([QPointF(4, 3), QPointF(13, 8), QPointF(4, 13)])
        p.drawPolygon(poly)
    elif kind_lower == "table":
        # JMP data grid icon
        p.setPen(QPen(QColor("#0277bd"), 1.2))
        p.setBrush(QColor("#e1f5fe"))
        p.drawRect(2, 2, 12, 12)
        p.drawLine(2, 6, 14, 6)
        p.drawLine(6, 6, 6, 14)
        p.drawLine(10, 6, 10, 14)
    else:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#757575"))
        p.drawEllipse(3, 3, 10, 10)

    p.end()
    icon = QIcon(pm)
    _ICON_CACHE[kind] = icon
    return icon


class ColumnPropertiesDialog(QDialog):
    """JMP Column Info / Properties Dialog."""

    def __init__(self, parent: QWidget, col_name: str, modeling_type: str, kind: str):
        super().__init__(parent)
        self.setWindowTitle(f"Column Info - {col_name}")
        self.setFixedSize(360, 260)
        self.setFont(QFont("Segoe UI", 9))
        self.setStyleSheet("""
            QDialog { background-color: #f8fafc; color: #1e293b; }
            QLabel { color: #1e293b; font-size: 9pt; }
            QLineEdit { background-color: #ffffff; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; }
            QLineEdit:focus { border-color: #0078d7; }
            QRadioButton { color: #1e293b; font-size: 9pt; spacing: 6px; }
            QRadioButton::indicator { width: 14px; height: 14px; border-radius: 7px; border: 1px solid #94a3b8; background-color: #ffffff; }
            QRadioButton::indicator:checked { border: 1px solid #0078d7; background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #0078d7, stop:0.55 #0078d7, stop:0.65 #ffffff, stop:1 #ffffff); }
            QPushButton { background-color: #ffffff; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 14px; min-height: 22px; }
            QPushButton:hover { background-color: #f1f5f9; border-color: #94a3b8; }
            QPushButton:default { background-color: #005a9e; color: #ffffff; border-color: #004578; font-weight: 600; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        self.txt_name = QLineEdit(col_name)
        form.addRow("Column Name:", self.txt_name)

        # Modeling Type Radios
        type_box = QWidget()
        t_layout = QVBoxLayout(type_box)
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_layout.setSpacing(4)

        self.rad_continuous = QRadioButton("Continuous (▲)")
        self.rad_continuous.setIcon(get_jmp_icon("continuous"))
        self.rad_ordinal = QRadioButton("Ordinal (📶)")
        self.rad_ordinal.setIcon(get_jmp_icon("ordinal"))
        self.rad_nominal = QRadioButton("Nominal (▮)")
        self.rad_nominal.setIcon(get_jmp_icon("nominal"))

        mt = modeling_type.lower()
        if mt == "nominal":
            self.rad_nominal.setChecked(True)
        elif mt == "ordinal":
            self.rad_ordinal.setChecked(True)
        else:
            self.rad_continuous.setChecked(True)

        t_layout.addWidget(self.rad_continuous)
        t_layout.addWidget(self.rad_ordinal)
        t_layout.addWidget(self.rad_nominal)
        form.addRow("Modeling Type:", type_box)

        layout.addLayout(form)
        layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_values(self) -> tuple[str, str]:
        name = self.txt_name.text().strip()
        if self.rad_nominal.isChecked():
            mt = "nominal"
        elif self.rad_ordinal.isChecked():
            mt = "ordinal"
        else:
            mt = "continuous"
        return name, mt


class JMPTablePanel(QWidget):
    """JMP-style left sidebar containing Table Scripts, Columns, and Rows panels."""

    def __init__(self, main_window: ModernWindow):
        super().__init__()
        self.main_window = main_window
        self.setObjectName("jmpTablePanel")
        self.setMinimumWidth(185)
        self.setMaximumWidth(380)

        self.setStyleSheet("""
            QWidget#jmpTablePanel {
                background-color: #f8fafc;
                border-right: 1px solid #e2e8f0;
            }
            QWidget#jmpHeader {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #0369a1);
                color: #ffffff;
                border-bottom: 1px solid #0284c7;
            }
            QLabel#jmpHeaderTitle {
                color: #ffffff;
                font-size: 9.5pt;
                font-weight: 700;
            }
            QLabel#jmpHeaderSub {
                color: #e0f2fe;
                font-size: 8pt;
            }
            QWidget#jmpSectionHeader {
                background-color: #f1f5f9;
                border-top: 1px solid #e2e8f0;
                border-bottom: 1px solid #e2e8f0;
            }
            QLabel#jmpSectionTitle {
                font-size: 8.5pt;
                font-weight: 600;
                color: #334155;
            }
            QListWidget {
                background-color: #ffffff;
                border: none;
                font-family: 'Segoe UI', -apple-system, sans-serif;
                font-size: 8.5pt;
            }
            QListWidget::item {
                padding: 5px 8px;
                border-bottom: 1px solid #f8fafc;
                color: #1e293b;
            }
            QListWidget::item:hover {
                background-color: #f1f5f9;
            }
            QListWidget::item:selected {
                background-color: #e0f2fe;
                color: #0369a1;
                font-weight: 600;
            }
            QLineEdit#jmpFilter {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 8.5pt;
            }
            QLineEdit#jmpFilter:focus {
                border-color: #0284c7;
            }
            QPushButton.jmpMiniBtn {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                font-size: 8pt;
                padding: 2px 6px;
                min-width: 40px;
                color: #334155;
            }
            QPushButton.jmpMiniBtn:hover {
                background-color: #e0f2fe;
                border-color: #0284c7;
                color: #0369a1;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. JMP Table Header
        header = QWidget()
        header.setObjectName("jmpHeader")
        header.setFixedHeight(46)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 4, 10, 4)
        h_layout.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_jmp_icon("table").pixmap(24, 24))
        h_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(0)
        self.lbl_table_name = QLabel("Data Table")
        self.lbl_table_name.setObjectName("jmpHeaderTitle")
        self.lbl_table_meta = QLabel("0 Rows, 0 Columns")
        self.lbl_table_meta.setObjectName("jmpHeaderSub")
        title_vbox.addWidget(self.lbl_table_name)
        title_vbox.addWidget(self.lbl_table_meta)
        h_layout.addLayout(title_vbox, 1)

        layout.addWidget(header)

        # 2. Scrollable Body containing 3 JMP Panels: Table Variables & Scripts, Columns, Rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)

        # SECTION A: Table Variables & Scripts
        sec_scripts = self._create_section_header("▾ Table Scripts", tooltip="Saved JMP analyses and workflows")
        c_layout.addWidget(sec_scripts)

        self.list_scripts = QListWidget()
        self.list_scripts.setMaximumHeight(140)
        self.list_scripts.itemDoubleClicked.connect(self._run_script_item)
        c_layout.addWidget(self.list_scripts)

        # SECTION B: Columns Panel
        self.sec_cols_title = QLabel("▾ Columns (0)")
        sec_cols = self._create_section_header(self.sec_cols_title, tooltip="Columns and modeling types (▲ Continuous, ▮ Nominal, 📶 Ordinal)")
        c_layout.addWidget(sec_cols)

        # Filter bar
        filter_box = QWidget()
        filter_box.setStyleSheet("background-color: #ffffff; padding: 3px 6px; border-bottom: 1px solid #e0e0e0;")
        fb_layout = QHBoxLayout(filter_box)
        fb_layout.setContentsMargins(0, 0, 0, 0)
        fb_layout.setSpacing(4)
        self.txt_col_filter = QLineEdit()
        self.txt_col_filter.setObjectName("jmpFilter")
        self.txt_col_filter.setPlaceholderText("Filter columns...")
        self.txt_col_filter.textChanged.connect(self._filter_columns)
        fb_layout.addWidget(self.txt_col_filter)
        c_layout.addWidget(filter_box)

        self.list_cols = QListWidget()
        self.list_cols.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_cols.itemSelectionChanged.connect(self._sync_col_selection_to_table)
        self.list_cols.itemDoubleClicked.connect(self._open_col_properties)
        self.list_cols.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_cols.customContextMenuRequested.connect(self._show_col_context_menu)
        c_layout.addWidget(self.list_cols, 1)

        # SECTION C: Rows Panel
        sec_rows = self._create_section_header("▾ Rows", tooltip="Row state summary and actions")
        c_layout.addWidget(sec_rows)

        rows_box = QWidget()
        rows_box.setStyleSheet("background-color: #ffffff; border-top: 1px solid #f0f0f0; padding: 6px 8px;")
        r_layout = QVBoxLayout(rows_box)
        r_layout.setContentsMargins(6, 4, 6, 6)
        r_layout.setSpacing(4)

        self.lbl_row_all = QLabel("All: 0")
        self.lbl_row_sel = QLabel("Selected: 0")
        self.lbl_row_excl = QLabel("Excluded: 0")
        for lbl in (self.lbl_row_all, self.lbl_row_sel, self.lbl_row_excl):
            lbl.setFont(QFont("Segoe UI", 8.5))
            lbl.setStyleSheet("color: #424242;")
            r_layout.addWidget(lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        btn_clear = QPushButton("Clear")
        btn_clear.setProperty("class", "jmpMiniBtn")
        btn_clear.clicked.connect(self._clear_row_selection)
        btn_invert = QPushButton("Invert")
        btn_invert.setProperty("class", "jmpMiniBtn")
        btn_invert.clicked.connect(self._invert_row_selection)
        btn_goto = QPushButton("Go To...")
        btn_goto.setProperty("class", "jmpMiniBtn")
        btn_goto.clicked.connect(lambda: self.main_window.goto_dialog())
        btn_row.addWidget(btn_clear)
        btn_row.addWidget(btn_invert)
        btn_row.addWidget(btn_goto)
        r_layout.addLayout(btn_row)

        c_layout.addWidget(rows_box)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        self._populate_scripts()

    def _create_section_header(self, title_or_widget: str | QLabel, tooltip: str = "") -> QWidget:
        sec = QWidget()
        sec.setObjectName("jmpSectionHeader")
        sec.setFixedHeight(24)
        if tooltip:
            sec.setToolTip(tooltip)
        s_layout = QHBoxLayout(sec)
        s_layout.setContentsMargins(8, 2, 8, 2)
        s_layout.setSpacing(4)

        if isinstance(title_or_widget, str):
            lbl = QLabel(title_or_widget)
            lbl.setObjectName("jmpSectionTitle")
            s_layout.addWidget(lbl)
        else:
            title_or_widget.setObjectName("jmpSectionTitle")
            s_layout.addWidget(title_or_widget)

        s_layout.addStretch()
        return sec

    def _populate_scripts(self):
        """Populate standard JMP Table Scripts with green play icon ▶."""
        self.list_scripts.clear()
        scripts = [
            ("Fit Y by X (Bivariate & Oneway)", lambda: self.main_window.fit_y_by_x_dialog()),
            ("Distribution (Descriptive & Histograms)", lambda: self.main_window.jmp_distribution_dialog()),
            ("Variability / Attribute Gauge Chart", lambda: self.main_window.variability_chart_dialog()),
            ("Control Chart Builder (Interactive SPC)", lambda: self.main_window.control_chart_builder_dialog()),
            ("Process Screening Dashboard", lambda: self.main_window.process_screening_dialog()),
            ("Prediction Profiler", lambda: self.main_window.prediction_profiler("regression")),
            ("Fit Model (Regression & GLM)", lambda: self.main_window.multiple_regression()),
            ("Partition (Decision Tree)", lambda: self.main_window.cart_tree_dialog() if hasattr(self.main_window, "cart_tree_dialog") else self.main_window.describe()),
            ("Wheeler EMP Gauge Study", lambda: self.main_window.emp_dialog() if hasattr(self.main_window, "emp_dialog") else None),
            ("Definitive Screening Design (DSD)", lambda: self.main_window.analyze_dsd_dialog()),
            ("D-Optimal Custom Design", lambda: self.main_window.create_d_optimal_dialog()),
            ("R Data Science Workbench", lambda: self.main_window.set_ui_mode("r")),
            ("3D Surface Plot", lambda: self.main_window.model_surface_plot("rsm")),
            ("Correlation Heatmap", lambda: self.main_window.correlation()),
        ]

        play_icon = get_jmp_icon("play_script")
        for name, callback in scripts:
            item = QListWidgetItem(play_icon, name)
            item.setToolTip(f"Double-click to run JMP {name} script")
            item.setData(Qt.ItemDataRole.UserRole, callback)
            self.list_scripts.addItem(item)

    def _run_script_item(self, item: QListWidgetItem):
        cb = item.data(Qt.ItemDataRole.UserRole)
        if callable(cb):
            cb()

    def refresh(self):
        """Sync JMP panel with active worksheet, columns, and rows."""
        sheet = self.main_window.presenter.worksheet
        self.lbl_table_name.setText(sheet.name or "Untitled")

        row_count = sheet.row_count
        col_count = len(sheet.columns)
        self.lbl_table_meta.setText(f"{row_count} Rows, {col_count} Columns")
        self.sec_cols_title.setText(f"▾ Columns ({col_count})")

        # Sync Columns list
        self.list_cols.blockSignals(True)
        self.list_cols.clear()
        filter_text = self.txt_col_filter.text().strip().lower()

        for idx, col in enumerate(sheet.columns):
            name = col.name or f"C{idx+1}"
            if filter_text and filter_text not in name.lower():
                continue

            mt = col.metadata.get("modeling_type")
            if not mt:
                if col.kind == "text":
                    mt = "nominal"
                elif col.kind == "datetime":
                    mt = "ordinal"
                else:
                    mt = "continuous"

            icon = get_jmp_icon(mt)
            item = QListWidgetItem(icon, f"{idx+1}  {name}")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            item.setToolTip(f"Column: {name}\nIndex: {idx+1}\nModeling Type: {mt.capitalize()}\nKind: {col.kind}")

            if idx in getattr(self.main_window, "_selected_columns", set()):
                item.setSelected(True)

            self.list_cols.addItem(item)
        self.list_cols.blockSignals(False)

        # Sync Rows statistics
        sel_rows = len(getattr(self.main_window, "_selected_rows", set()))
        self.lbl_row_all.setText(f"All Rows: {row_count}")
        self.lbl_row_sel.setText(f"Selected: {sel_rows}")
        self.lbl_row_excl.setText("Excluded: 0")

    def _filter_columns(self, text: str):
        self.refresh()

    def _sync_col_selection_to_table(self):
        """When user selects columns in JMP columns list, highlight them in worksheet table."""
        selected_indexes = [item.data(Qt.ItemDataRole.UserRole) for item in self.list_cols.selectedItems()]
        if not selected_indexes:
            return

        table = self.main_window.table
        table.clearSelection()
        rows = self.main_window.presenter.worksheet.row_count or 1
        for c in selected_indexes:
            if c < table.columnCount():
                table.selectColumn(c)

    def _open_col_properties(self, item: QListWidgetItem):
        col_idx = item.data(Qt.ItemDataRole.UserRole)
        sheet = self.main_window.presenter.worksheet
        if col_idx >= len(sheet.columns):
            return

        col = sheet.columns[col_idx]
        current_mt = col.metadata.get("modeling_type") or ("nominal" if col.kind == "text" else "continuous")

        dlg = ColumnPropertiesDialog(self, col.name, current_mt, col.kind)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_name, new_mt = dlg.get_values()
            if new_name and new_name != col.name:
                self.main_window.presenter.rename_column(col_idx, new_name)
            col.metadata["modeling_type"] = new_mt
            self.main_window.refresh()
            self.refresh()

    def _show_col_context_menu(self, pos):
        item = self.list_cols.itemAt(pos)
        if not item:
            return

        col_idx = item.data(Qt.ItemDataRole.UserRole)
        sheet = self.main_window.presenter.worksheet
        if col_idx >= len(sheet.columns):
            return

        col = sheet.columns[col_idx]
        menu = QMenu(self)

        act_cont = menu.addAction(get_jmp_icon("continuous"), "Continuous (▲)")
        act_ord = menu.addAction(get_jmp_icon("ordinal"), "Ordinal (📶)")
        act_nom = menu.addAction(get_jmp_icon("nominal"), "Nominal (▮)")
        menu.addSeparator()

        act_formula = menu.addAction("Formula Editor (Assign Formula)...")
        act_props = menu.addAction("Column Info / Properties...")
        act_rename = menu.addAction("Rename Column...")
        menu.addSeparator()
        act_delete = menu.addAction("Delete Column")

        action = menu.exec(self.list_cols.mapToGlobal(pos))
        if action == act_cont:
            col.metadata["modeling_type"] = "continuous"
            self.main_window.refresh()
            self.refresh()
        elif action == act_ord:
            col.metadata["modeling_type"] = "ordinal"
            self.main_window.refresh()
            self.refresh()
        elif action == act_nom:
            col.metadata["modeling_type"] = "nominal"
            self.main_window.refresh()
            self.refresh()
        elif action == act_formula:
            self.main_window.assign_formula_dialog()
        elif action == act_props:
            self._open_col_properties(item)
        elif action == act_rename:
            self.main_window.rename_column(col_idx)
        elif action == act_delete:
            self.main_window.presenter.delete_columns([col_idx])
            self.main_window.refresh()
            self.refresh()

    def _clear_row_selection(self):
        self.main_window.table.clearSelection()
        self.main_window._selected_rows.clear()
        self.refresh()

    def _invert_row_selection(self):
        total = self.main_window.presenter.worksheet.row_count
        cur_sel = getattr(self.main_window, "_selected_rows", set())
        new_sel = set(range(total)) - cur_sel
        self.main_window._selected_rows = new_sel
        self.refresh()


def populate_jmp_menubar(win: ModernWindow, bar: QMenuBar) -> QMenuBar:
    """Populate authentic JMP platform menus into the given QMenuBar."""
    from PySide6.QtGui import QKeySequence

    def _act(menu, text, slot=None, shortcut=None, icon=None):
        if icon:
            ic = get_jmp_icon(icon) if isinstance(icon, str) else icon
            act = menu.addAction(ic, text)
        else:
            act = menu.addAction(text)
        if slot:
            act.triggered.connect(slot)
        if shortcut:
            act.setShortcut(shortcut)
        return act

    # 1. FILE
    file_m = bar.addMenu("&File")
    new_m = file_m.addMenu("New")
    _act(new_m, "Data Table", win.new_worksheet, QKeySequence("Ctrl+N"), "table")
    _act(new_m, "Project", win.new_document, QKeySequence("Ctrl+Shift+N"))
    _act(file_m, "Open…", win.open_document, QKeySequence.StandardKey.Open)
    _act(file_m, "Import Delimited Text with Column Types…", lambda: win.open_document(True))
    file_m.addSeparator()
    _act(file_m, "Save", win.save_document, QKeySequence.StandardKey.Save)
    _act(file_m, "Save As…", lambda: win.save_document(True), QKeySequence.StandardKey.SaveAs)
    _act(file_m, "Save Current Data Table As…", win.export_data)
    export_m = file_m.addMenu("Export")
    _act(export_m, "Export to Excel (All Tables)…", lambda: win.export_excel(True))
    _act(export_m, "Export to Excel (Current Table)…", lambda: win.export_excel(False))
    _act(export_m, "Export to Word…", win.send_output_to_word)
    _act(export_m, "Export to PowerPoint…", win.send_output_to_powerpoint)
    _act(export_m, "Export to PDF…", lambda: win._printing().run("pdf"))
    _act(export_m, "Export Report…", win.export_report)
    file_m.addSeparator()
    _act(file_m, "Page Setup…", lambda: win._printing().page_setup())
    _act(file_m, "Print Preview…", lambda: win._printing().run("preview"))
    _act(file_m, "Print…", win.print_current, QKeySequence.StandardKey.Print)
    file_m.addSeparator()
    _act(file_m, "Exit", win.close, QKeySequence.StandardKey.Quit)

    # 2. TABLES
    tables_m = bar.addMenu("&Tables")
    _act(tables_m, "Summary / Tabulate…", win.cross_tabulation_dialog, icon="table")
    _act(tables_m, "Subset…", getattr(win, "subset_worksheet_dialog", win.sort_dialog))
    _act(tables_m, "Sort…", win.sort_dialog)
    from .data_prep_dialogs import open_dialog as prepare_dialog
    stack_m = tables_m.addMenu("Stack")
    _act(stack_m, "Stack Columns…", lambda: prepare_dialog(win, "stack"))
    _act(stack_m, "Stack Worksheets…", lambda: prepare_dialog(win, "stack_worksheets"))
    _act(tables_m, "Split / Unstack Columns…", lambda: prepare_dialog(win, "unstack"))
    _act(tables_m, "Transpose Columns…", lambda: prepare_dialog(win, "transpose"))
    _act(tables_m, "Concatenate / Merge Tables…", lambda: prepare_dialog(win, "merge"))
    tables_m.addSeparator()
    _act(tables_m, "Summary Statistics…", win.describe)
    _act(tables_m, "Table Information", win.show_worksheet_information)
    _act(tables_m, "Table Description…", win.worksheet_description_dialog)

    # 3. ROWS
    rows_m = bar.addMenu("&Rows")
    row_sel_m = rows_m.addMenu("Row Selection")
    _act(row_sel_m, "Select All Rows", win.table.selectAll, QKeySequence.StandardKey.SelectAll)
    _act(row_sel_m, "Clear Selection", win.table.clearSelection)
    _act(row_sel_m, "Invert Row Selection", lambda: win.jmp_panel._invert_row_selection() if hasattr(win, "jmp_panel") else None)
    rows_m.addSeparator()
    _act(rows_m, "Go To Row…", win.goto_dialog, QKeySequence("Ctrl+G"))
    _act(rows_m, "Previous Brushed Row", lambda: win.go_to_brushed_row(-1))
    _act(rows_m, "Next Brushed Row", lambda: win.go_to_brushed_row(1))
    rows_m.addSeparator()
    _act(rows_m, "Insert Rows…", win.insert_rows_action_handler)
    _act(rows_m, "Add Rows…", win.add_rows)
    _act(rows_m, "Delete Selected Rows", win.delete_selected_rows)
    _act(rows_m, "Delete Rows Dialog…", win.delete_rows_dialog)

    # 4. COLS
    cols_m = bar.addMenu("&Cols")
    _act(cols_m, "New Column…", win.add_column)
    _act(cols_m, "Column Info & Properties…", lambda: win.rename_column())
    mod_m = cols_m.addMenu("Modeling Type")
    def _set_active_col_type(mt):
        sheet = win.presenter.worksheet
        cols = getattr(win, "_selected_columns", set())
        for c in cols:
            if c < len(sheet.columns):
                sheet.columns[c].metadata["modeling_type"] = mt
        win.refresh()
        if hasattr(win, "jmp_panel"): win.jmp_panel.refresh()

    _act(mod_m, "Continuous (▲)", lambda: _set_active_col_type("continuous"), icon="continuous")
    _act(mod_m, "Ordinal (📶)", lambda: _set_active_col_type("ordinal"), icon="ordinal")
    _act(mod_m, "Nominal (▮)", lambda: _set_active_col_type("nominal"), icon="nominal")
    cols_m.addSeparator()
    _act(cols_m, "Formula Editor (Assign Formula)…", win.assign_formula_dialog)
    _act(cols_m, "Standardize…", win.standardize_dialog)
    cols_m.addSeparator()
    _act(cols_m, "Move Columns…", win.move_columns_dialog)
    _act(cols_m, "Insert Columns…", win.insert_columns_action_handler)
    _act(cols_m, "Delete Selected Columns", lambda: win.presenter.delete_columns(list(getattr(win, "_selected_columns", []))) or win.refresh())
    _act(cols_m, "Erase Variables…", win.erase_variables_dialog)

    # 5. DOE
    doe_m = bar.addMenu("&DOE")
    _act(doe_m, "Custom Design (D-Optimal)…", win.create_d_optimal_dialog, icon="play_script")
    _act(doe_m, "Definitive Screening Design (DSD)…", win.create_dsd_dialog, icon="play_script")
    class_doe = doe_m.addMenu("Classical")
    _act(class_doe, "Create Factorial Design…", win.create_factorial)
    _act(class_doe, "General Factorial Design…", lambda: win.doe_planner("general_factorial"))
    _act(class_doe, "Plackett–Burman Design…", lambda: win.doe_planner("plackett_burman"))
    _act(class_doe, "Response Surface Design…", lambda: win.doe_planner("response_surface"))
    doe_m.addSeparator()
    _act(doe_m, "Analyze Definitive Screening Design…", win.analyze_dsd_dialog)
    _act(doe_m, "Analyze Factorial Design…", win.analyze_factorial)
    _act(doe_m, "DOE Planner…", win.doe_planner)
    diag_m = doe_m.addMenu("Design Diagnostics")
    _act(diag_m, "Color Map on Correlations…", win.evaluate_design_dialog)

    # 6. ANALYZE
    ana_m = bar.addMenu("&Analyze")
    _act(ana_m, "Distribution (Descriptive & Histograms)…", win.jmp_distribution_dialog, icon="play_script")
    _act(ana_m, "Fit Y by X (Bivariate, Oneway, Contingency)…", win.fit_y_by_x_dialog, icon="play_script")
    fit_m = ana_m.addMenu("Fit Model")
    _act(fit_m, "Multiple Regression…", win.multiple_regression)
    _act(fit_m, "General Linear Model (GLM)…", win.general_linear_model)
    _act(fit_m, "Binary Logistic Regression…", win.fit_binary_logistic)
    pred_m = ana_m.addMenu("Predictive Modeling")
    _act(pred_m, "Partition (Decision Tree)…", win.cart_tree_dialog if hasattr(win, "cart_tree_dialog") else win.describe)
    ana_m.addSeparator()
    qp_m = ana_m.addMenu("Quality and Process")
    _act(qp_m, "Control Chart Builder…", getattr(win, "control_chart_builder_dialog", win.xbar_r_dialog), icon="chart")
    _act(qp_m, "Variability / Attribute Gauge Chart…", getattr(win, "variability_chart_dialog", win.gage_rr), icon="chart")
    _act(qp_m, "Process Screening…", getattr(win, "process_screening_dialog", win.capability), icon="table")
    _act(qp_m, "Wheeler EMP Gauge Study…", win.emp_dialog if hasattr(win, "emp_dialog") else None)
    _act(qp_m, "Gage R&R (Crossed / Nested)…", win.gage_rr)
    _act(qp_m, "Variables Control Charts (Xbar-R, I-MR)…", win.xbar_r_dialog)
    _act(qp_m, "Attributes Control Charts (P, NP, C, U)…", lambda: win.attribute_control_dialog("P"))
    _act(qp_m, "Process Capability (Normal & Nonnormal)…", win.capability)
    rel_m = ana_m.addMenu("Reliability and Survival")
    _act(rel_m, "Life Distribution…", win.reliability_distribution_dialog)
    _act(rel_m, "Fit Life by X (Accelerated Life Testing)…", win.alt_dialog)
    mult_m = ana_m.addMenu("Multivariate Methods")
    _act(mult_m, "Principal Components Analysis (PCA)…", win.pca_dialog)
    _act(mult_m, "Correlation Matrix…", win.correlation)
    _act(mult_m, "Covariance…", win.covariance_dialog)

    # 7. GRAPH
    graph_m = bar.addMenu("&Graph")
    _act(graph_m, "Graph Builder…", lambda: win.graph("builder"), icon="play_script")
    _act(graph_m, "Prediction Profiler…", lambda: win.prediction_profiler("regression"), icon="play_script")
    _act(graph_m, "Contour Plot…", lambda: win.model_contour_plot("regression"))
    _act(graph_m, "Surface Plot (3D Response Surface)…", lambda: win.model_surface_plot("rsm"))
    _act(graph_m, "Scatterplot Matrix…", lambda: win.graph("matrix"))
    _act(graph_m, "Variability / Attribute Gauge Chart…", win.multivari_dialog, icon="play_script")
    _act(graph_m, "Pareto Plot…", win.pareto_chart_dialog)
    _act(graph_m, "Boxplot…", lambda: win.graph("boxplot"))
    _act(graph_m, "Histogram…", lambda: win.graph("histogram"))
    _act(graph_m, "Time Series Plot…", lambda: win.graph("time_series"))

    # 8. TOOLS
    tools_m = bar.addMenu("&Tools")
    _act(tools_m, "Calculator…", win.calculator)
    _act(tools_m, "Edit Last Dialog", win.edit_last_dialog, QKeySequence("Ctrl+E"))
    _act(tools_m, "Find…", win.find_dialog, QKeySequence.StandardKey.Find)
    _act(tools_m, "Find Next", win.find_next, QKeySequence("F3"))
    tools_m.addSeparator()
    _act(tools_m, "Stored Constants…", win.stored_constants)
    _act(tools_m, "Stored Matrices…", win.stored_matrices)
    _act(tools_m, "Probability Distributions…", win.probability)
    _act(tools_m, "Graph Customization Options…", win.edit_graph_object)

    # 9. VIEW
    view_m = bar.addMenu("&View")
    mode_sub = view_m.addMenu("Workspace Mode")
    _act(mode_sub, "Minitab Mode (Quality & SPC)", lambda: win.set_ui_mode("minitab"))
    _act(mode_sub, "JMP Mode (Visual Platforms)", lambda: win.set_ui_mode("jmp"))
    _act(mode_sub, "R Mode (Data Science Workbench)", lambda: win.set_ui_mode("r"))
    view_m.addSeparator()
    _act(view_m, "Toggle Table Panel", win.toggle_navigator)
    _act(view_m, "Command Line / Script Editor", win.toggle_command_line)
    view_m.addSeparator()
    _act(view_m, "Data Table Only", lambda: win.set_view_mode("data"))
    _act(view_m, "Output & Graphs Only", lambda: win.set_view_mode("output"))
    _act(view_m, "Split View (Table + Output)", lambda: win.set_view_mode("both"))
    view_m.addSeparator()
    _act(view_m, "Zoom In", lambda: win.set_zoom(min(300, win._zoom_percent + 20)), QKeySequence.StandardKey.ZoomIn)
    _act(view_m, "Zoom Out", lambda: win.set_zoom(max(20, win._zoom_percent - 20)), QKeySequence.StandardKey.ZoomOut)
    _act(view_m, "Reset Zoom", lambda: win.set_zoom(100))

    # 10. WINDOW
    win_m = bar.addMenu("&Window")
    _act(win_m, "Close Output Tab", lambda: win._workspace.close_current())
    _act(win_m, "Close All Output Tabs", lambda: win._workspace.close_all() if hasattr(win._workspace, "close_all") else None)

    # 11. HELP
    help_m = bar.addMenu("&Help")
    _act(help_m, "StatCraft Guide…", lambda: win._module_notice("Help", "StatCraft provides a unified statistical workbench supporting Minitab Mode, JMP Mode, and R Mode.\n\nSwitch seamlessly between modes anytime using the Mode toggle at the top or Ctrl+Alt+J!"))
    _act(help_m, "Keyboard Shortcuts…", lambda: win._module_notice("Keyboard Shortcuts", "Ctrl+N: New Worksheet\nCtrl+O: Open File\nCtrl+S: Save\nCtrl+E: Edit Last Dialog\nCtrl+G: Go To Row\nCtrl+Alt+J: Toggle Workspace Mode (Minitab / JMP / R)"))
    _act(help_m, "Check for Updates…", win.check_for_updates_dialog)
    _act(help_m, "About StatCraft…", win.about)

    return bar


def build_jmp_menubar(win: ModernWindow) -> QMenuBar:
    from PySide6.QtWidgets import QMenuBar
    bar = QMenuBar(win)
    return populate_jmp_menubar(win, bar)

