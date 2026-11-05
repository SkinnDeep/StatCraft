"""VS Code-Grade File Explorer & Workspace Navigator for R Mode.

Provides an integrated developer sidebar for StatCraft's R Mode:
1. Workspace File Explorer: Browse project directories, edit .R scripts, import .csv/.jmp data.
2. Active Worksheets Browser: Quick switching and 1-click binding to R 'df' memory.
3. R Package Manager: Search, view installed packages, and 1-click CRAN package installation.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDir, QModelIndex, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFileSystemModel,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


def _make_file_badge_icon(ext: str, is_dark: bool) -> QIcon:
    """Generate crisp vector badge icon for file extensions."""
    px = QPixmap(18, 18)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    ext = ext.lower().lstrip(".")
    if ext in ("r", "rmd", "qmd"):
        bg_col = QColor("#0284c7") if not is_dark else QColor("#38bdf8")
        text = "R"
    elif ext in ("csv", "tsv", "tab"):
        bg_col = QColor("#059669") if not is_dark else QColor("#34d399")
        text = "CSV"
    elif ext in ("jmp", "jsl"):
        bg_col = QColor("#ea580c") if not is_dark else QColor("#fb923c")
        text = "JMP"
    elif ext in ("mpx", "statcraft"):
        bg_col = QColor("#7c3aed") if not is_dark else QColor("#a78bfa")
        text = "SC"
    elif ext in ("png", "jpg", "jpeg", "svg"):
        bg_col = QColor("#db2777") if not is_dark else QColor("#f472b6")
        text = "IMG"
    else:
        bg_col = QColor("#64748b") if not is_dark else QColor("#94a3b8")
        text = ext[:3].upper() if ext else "FILE"

    p.setBrush(bg_col)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(1, 2, 16, 14, 3, 3)

    p.setPen(QColor("#ffffff") if not is_dark or ext not in ("r", "csv", "jmp") else QColor("#0f172a"))
    font = QFont("Segoe UI", 6, QFont.Weight.Bold)
    p.setFont(font)
    p.drawText(1, 2, 16, 14, Qt.AlignmentFlag.AlignCenter, text[:3])
    p.end()
    return QIcon(px)


class RExplorerPanel(QWidget):
    """VS Code-style File Explorer, Worksheets, and R Packages sidebar panel."""

    file_opened = Signal(str)  # emitted when user requests to open an R file in editor
    script_executed = Signal(str)  # emitted when user requests to execute script in REPL
    data_opened = Signal(str)  # emitted when user requests to open CSV/JMP into worksheet

    COMMON_PACKAGES = [
        ("ggplot2", "Declarative graphics & data visualization"),
        ("dplyr", "Fast data manipulation & grammar"),
        ("tidyr", "Tidy messy datasets & pivots"),
        ("readr", "Fast rectangular data ingestion"),
        ("car", "Companion to Applied Regression (ANOVA, VIF)"),
        ("lme4", "Linear mixed-effects modeling"),
        ("MASS", "Modern Applied Statistics with S"),
        ("survival", "Survival analysis & reliability modeling"),
        ("forecast", "Time series forecasting & ARIMA models"),
        ("knitr", "Dynamic report generation"),
    ]

    def __init__(self, main_window=None, presenter=None, workbench=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.presenter = presenter
        self.workbench = workbench
        self._is_dark = False
        self._root_path = os.getcwd()

        self._build_ui()
        self.set_dark_mode(False)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Header with brand and action icons
        self.header_frame = QFrame()
        self.header_frame.setFixedHeight(36)
        hdr_layout = QHBoxLayout(self.header_frame)
        hdr_layout.setContentsMargins(8, 0, 6, 0)
        hdr_layout.setSpacing(4)

        self.title_lbl = QLabel("EXPLORER")
        self.title_lbl.setStyleSheet("font-size: 10.5px; font-weight: 700; letter-spacing: 0.5px;")
        hdr_layout.addWidget(self.title_lbl)

        hdr_layout.addStretch()

        self.btn_new_file = QToolButton()
        self.btn_new_file.setText("📄+")
        self.btn_new_file.setToolTip("New R Script")
        self.btn_new_file.clicked.connect(self._create_new_r_file)
        hdr_layout.addWidget(self.btn_new_file)

        self.btn_open_folder = QToolButton()
        self.btn_open_folder.setText("📂")
        self.btn_open_folder.setToolTip("Open Folder…")
        self.btn_open_folder.clicked.connect(self._browse_folder)
        hdr_layout.addWidget(self.btn_open_folder)

        self.btn_refresh = QToolButton()
        self.btn_refresh.setText("🔄")
        self.btn_refresh.setToolTip("Refresh Explorer")
        self.btn_refresh.clicked.connect(self.refresh_all)
        hdr_layout.addWidget(self.btn_refresh)

        root.addWidget(self.header_frame)

        # 2. Main Accordion Sections using QSplitter
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(1)

        # Section A: Workspace Files
        files_box = QWidget()
        fb_layout = QVBoxLayout(files_box)
        fb_layout.setContentsMargins(0, 0, 0, 0)
        fb_layout.setSpacing(0)

        self.folder_bar = QFrame()
        self.folder_bar.setFixedHeight(24)
        fbar_layout = QHBoxLayout(self.folder_bar)
        fbar_layout.setContentsMargins(8, 0, 6, 0)
        self.folder_label = QLabel(f"📁 {Path(self._root_path).name.upper() or 'WORKSPACE'}")
        self.folder_label.setStyleSheet("font-size: 9.5px; font-weight: bold;")
        fbar_layout.addWidget(self.folder_label)
        fb_layout.addWidget(self.folder_bar)

        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath(self._root_path)
        self.fs_model.setNameFilters([
            "*.R", "*.r", "*.Rmd", "*.qmd",
            "*.csv", "*.tsv", "*.tab",
            "*.jmp", "*.jsl",
            "*.mpx", "*.statcraft",
            "*.png", "*.jpg", "*.svg", "*.txt",
        ])
        self.fs_model.setNameFilterDisables(False)

        self.tree_view = QTreeView()
        self.tree_view.setModel(self.fs_model)
        self.tree_view.setRootIndex(self.fs_model.index(self._root_path))
        self.tree_view.header().hide()
        self.tree_view.setColumnHidden(1, True)
        self.tree_view.setColumnHidden(2, True)
        self.tree_view.setColumnHidden(3, True)
        self.tree_view.setAnimated(True)
        self.tree_view.setIndentation(14)
        self.tree_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._show_file_context_menu)
        self.tree_view.doubleClicked.connect(self._on_item_double_clicked)
        fb_layout.addWidget(self.tree_view)
        splitter.addWidget(files_box)

        # Section B: Active StatCraft Worksheets
        sheets_box = QWidget()
        sb_layout = QVBoxLayout(sheets_box)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        self.sheets_bar = QFrame()
        self.sheets_bar.setFixedHeight(24)
        sbar_layout = QHBoxLayout(self.sheets_bar)
        sbar_layout.setContentsMargins(8, 0, 6, 0)
        self.sheets_label = QLabel("📊 OPEN WORKSHEETS")
        self.sheets_label.setStyleSheet("font-size: 9.5px; font-weight: bold;")
        sbar_layout.addWidget(self.sheets_label)
        sb_layout.addWidget(self.sheets_bar)

        self.sheets_list = QListWidget()
        self.list_sheets = self.sheets_list
        self.sheets_list.itemDoubleClicked.connect(self._on_worksheet_double_clicked)
        sb_layout.addWidget(self.sheets_list)
        splitter.addWidget(sheets_box)

        # Section C: R Packages & Tools
        pkg_box = QWidget()
        pb_layout = QVBoxLayout(pkg_box)
        pb_layout.setContentsMargins(0, 0, 0, 0)
        pb_layout.setSpacing(0)

        self.pkg_bar = QFrame()
        self.pkg_bar.setFixedHeight(24)
        pbar_layout = QHBoxLayout(self.pkg_bar)
        pbar_layout.setContentsMargins(8, 0, 6, 0)
        self.pkg_label = QLabel("📦 R PACKAGES")
        self.pkg_label.setStyleSheet("font-size: 9.5px; font-weight: bold;")
        pbar_layout.addWidget(self.pkg_label)
        pbar_layout.addStretch()

        btn_install_pkg = QToolButton()
        btn_install_pkg.setText("+ Install…")
        btn_install_pkg.setToolTip("Install an R package from CRAN")
        btn_install_pkg.clicked.connect(self._prompt_install_package)
        pbar_layout.addWidget(btn_install_pkg)
        pb_layout.addWidget(self.pkg_bar)

        self.pkg_list = QListWidget()
        self.pkg_list.itemDoubleClicked.connect(self._on_package_double_clicked)
        for name, desc in self.COMMON_PACKAGES:
            it = QListWidgetItem(f"{name} — {desc}")
            it.setToolTip(f"Double-click to load library({name}) or install")
            it.setData(Qt.ItemDataRole.UserRole, name)
            self.pkg_list.addItem(it)
        pb_layout.addWidget(self.pkg_list)
        splitter.addWidget(pkg_box)

        splitter.setSizes([340, 160, 180])
        root.addWidget(splitter)

        self.refresh_worksheets()

    @property
    def is_dark(self) -> bool:
        return getattr(self, "_is_dark", False)

    def set_dark_mode(self, is_dark: bool) -> None:
        """Dynamically apply Light (VS Code Light+) or Dark (VS Code Dark Modern) theme."""
        self._is_dark = is_dark

        if is_dark:
            # VS Code Dark Modern styling
            self.setStyleSheet("""
                QFrame { background-color: #18181b; }
                QLabel { color: #f4f4f5; }
                QToolButton { background-color: transparent; color: #a1a1aa; border: none; padding: 2px 4px; border-radius: 3px; font-size: 11px; }
                QToolButton:hover { background-color: #27272a; color: #ffffff; }
                QTreeView { background-color: #18181b; color: #e4e4e7; border: none; outline: 0; }
                QTreeView::item { padding: 3px 2px; }
                QTreeView::item:hover { background-color: #27272a; color: #ffffff; }
                QTreeView::item:selected { background-color: #094771; color: #ffffff; }
                QListWidget { background-color: #18181b; color: #e4e4e7; border: none; outline: 0; }
                QListWidget::item { padding: 4px 8px; border-bottom: 1px solid #27272a; font-size: 11px; }
                QListWidget::item:hover { background-color: #27272a; color: #ffffff; }
                QListWidget::item:selected { background-color: #094771; color: #ffffff; }
                QSplitter::handle { background-color: #27272a; }
            """)
            self.header_frame.setStyleSheet("background-color: #1f1f23; border-bottom: 1px solid #27272a;")
            self.folder_bar.setStyleSheet("background-color: #27272a; border-top: 1px solid #3f3f46; border-bottom: 1px solid #3f3f46;")
            self.sheets_bar.setStyleSheet("background-color: #27272a; border-top: 1px solid #3f3f46; border-bottom: 1px solid #3f3f46;")
            self.pkg_bar.setStyleSheet("background-color: #27272a; border-top: 1px solid #3f3f46; border-bottom: 1px solid #3f3f46;")
            self.title_lbl.setStyleSheet("font-size: 10.5px; font-weight: 700; color: #38bdf8; letter-spacing: 0.5px;")
        else:
            # VS Code Light+ / Clean StatCraft Light styling
            self.setStyleSheet("""
                QFrame { background-color: #f8fafc; }
                QLabel { color: #1e293b; }
                QToolButton { background-color: transparent; color: #64748b; border: none; padding: 2px 4px; border-radius: 3px; font-size: 11px; }
                QToolButton:hover { background-color: #e2e8f0; color: #0f172a; }
                QTreeView { background-color: #ffffff; color: #1e293b; border: none; outline: 0; }
                QTreeView::item { padding: 3px 2px; }
                QTreeView::item:hover { background-color: #f1f5f9; color: #0f172a; }
                QTreeView::item:selected { background-color: #e0f2fe; color: #005a9e; }
                QListWidget { background-color: #ffffff; color: #1e293b; border: none; outline: 0; }
                QListWidget::item { padding: 4px 8px; border-bottom: 1px solid #f1f5f9; font-size: 11px; }
                QListWidget::item:hover { background-color: #f1f5f9; color: #0f172a; }
                QListWidget::item:selected { background-color: #e0f2fe; color: #005a9e; }
                QSplitter::handle { background-color: #e2e8f0; }
            """)
            self.header_frame.setStyleSheet("background-color: #f8fafc; border-bottom: 1px solid #e2e8f0;")
            self.folder_bar.setStyleSheet("background-color: #f1f5f9; border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0;")
            self.sheets_bar.setStyleSheet("background-color: #f1f5f9; border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0;")
            self.pkg_bar.setStyleSheet("background-color: #f1f5f9; border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0;")
            self.title_lbl.setStyleSheet("font-size: 10.5px; font-weight: 700; color: #0284c7; letter-spacing: 0.5px;")

    def set_root_path(self, path: str) -> None:
        """Change workspace root directory."""
        if not os.path.isdir(path):
            return
        self._root_path = os.path.abspath(path)
        self.fs_model.setRootPath(self._root_path)
        self.tree_view.setRootIndex(self.fs_model.index(self._root_path))
        self.folder_label.setText(f"📁 {Path(self._root_path).name.upper() or 'WORKSPACE'}")

    def refresh_all(self) -> None:
        """Refresh filesystem and open worksheets."""
        self.fs_model.setRootPath(self._root_path)
        self.tree_view.setRootIndex(self.fs_model.index(self._root_path))
        self.refresh_worksheets()

    def refresh_worksheets(self) -> None:
        """Populate active worksheets list from presenter."""
        self.sheets_list.clear()
        if not self.presenter:
            return

        sheets = []
        if getattr(self.presenter, "native_project", None) and self.presenter.native_project.worksheets:
            sheets = self.presenter.native_project.worksheets
        elif getattr(self.presenter, "worksheet", None):
            sheets = [self.presenter.worksheet]

        active_ws = getattr(self.presenter, "worksheet", None)

        for ws in sheets:
            is_active = (ws is active_ws)
            n_rows = ws.row_count
            n_cols = len(ws.columns)
            title = f"{'🟢 ' if is_active else '📄 '}{ws.name} ({n_rows} rows × {n_cols} cols)"
            it = QListWidgetItem(title)
            it.setData(Qt.ItemDataRole.UserRole, ws.name)
            font = it.font()
            if is_active:
                font.setBold(True)
            it.setFont(font)
            self.sheets_list.addItem(it)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Workspace Folder", self._root_path)
        if folder:
            self.set_root_path(folder)

    def _create_new_r_file(self) -> None:
        name, ok = QInputDialog.getText(self, "New R Script", "Script name:", text="analysis.R")
        if not ok or not name.strip():
            return
        if not name.endswith(".R") and not name.endswith(".r"):
            name += ".R"
        target_path = Path(self._root_path) / name.strip()
        if target_path.exists():
            QMessageBox.warning(self, "File Exists", f"'{name}' already exists in workspace.")
            return

        initial_content = (
            f"# {name} - StatCraft R Data Science Script\n"
            "# Active worksheet is automatically bound to 'df'\n\n"
            "summary(df)\n"
        )
        try:
            target_path.write_text(initial_content, encoding="utf-8")
            self.file_opened.emit(str(target_path))
            if self.workbench:
                self.workbench.editor.setPlainText(initial_content)
                self.workbench._last_script_path = str(target_path)
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Failed to create file: {e}")

    def _on_item_double_clicked(self, index: QModelIndex) -> None:
        path = self.fs_model.filePath(index)
        if os.path.isfile(path):
            ext = Path(path).suffix.lower()
            if ext in (".r", ".rmd", ".qmd"):
                self._open_script_file(path)
            elif ext in (".csv", ".tsv", ".tab", ".jmp", ".jsl", ".mpx", ".statcraft"):
                self._open_data_file(path)

    def _open_script_file(self, path: str) -> None:
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            self.file_opened.emit(path)
            if self.workbench:
                self.workbench.editor.setPlainText(content)
                self.workbench._last_script_path = path
                if self.main_window and hasattr(self.main_window, "statusBar"):
                    self.main_window.statusBar().showMessage(f"Opened {Path(path).name} in R Workbench", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Open Error", f"Could not read script file:\n{e}")

    def _open_data_file(self, path: str) -> None:
        self.data_opened.emit(path)
        if self.main_window and hasattr(self.main_window, "load_path"):
            try:
                self.main_window.load_path(path)
                self.refresh_worksheets()
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Could not open data file:\n{e}")

    def _on_worksheet_double_clicked(self, item: QListWidgetItem) -> None:
        sheet_name = item.data(Qt.ItemDataRole.UserRole)
        if not sheet_name or not self.presenter:
            return

        # Switch active sheet if native project exists
        project = getattr(self.presenter, "native_project", None)
        if project:
            for idx, ws in enumerate(project.worksheets):
                if ws.name == sheet_name:
                    project.active_index = idx
                    self.presenter.worksheet = ws
                    if self.main_window and hasattr(self.main_window, "refresh"):
                        self.main_window.refresh()
                    break

        self.refresh_worksheets()
        if self.workbench:
            self.workbench.refresh_environment()

    def _show_file_context_menu(self, pos) -> None:
        idx = self.tree_view.indexAt(pos)
        if not idx.isValid():
            return
        path = self.fs_model.filePath(idx)
        is_file = os.path.isfile(path)

        menu = QMenu(self)
        if self._is_dark:
            menu.setStyleSheet("QMenu { background-color: #1f1f23; color: #e4e4e7; border: 1px solid #3f3f46; padding: 4px; } QMenu::item:selected { background-color: #0078d4; }")

        if is_file:
            ext = Path(path).suffix.lower()
            if ext in (".r", ".rmd"):
                menu.addAction("Open in R Editor", lambda: self._open_script_file(path))
                menu.addAction("Run Entire Script in R", lambda: self._run_script_in_r(path))
                menu.addSeparator()
            elif ext in (".csv", ".tsv", ".jmp", ".mpx"):
                menu.addAction("Import into StatCraft Worksheet", lambda: self._open_data_file(path))
                menu.addSeparator()

        menu.addAction("Reveal in File Explorer", lambda: self._reveal_in_os(path))
        menu.addSeparator()
        menu.addAction("Rename…", lambda: self._rename_path(path))
        menu.addAction("Delete", lambda: self._delete_path(path))

        menu.exec(self.tree_view.mapToGlobal(pos))

    def _run_script_in_r(self, path: str) -> None:
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            if self.workbench:
                self.workbench._execute_r(content)
        except Exception as e:
            QMessageBox.critical(self, "Run Error", f"Could not run script:\n{e}")

    def _reveal_in_os(self, path: str) -> None:
        if sys.platform == "win32":
            os.system(f'explorer /select,"{os.path.abspath(path)}"')
        else:
            folder = os.path.dirname(path) if os.path.isfile(path) else path
            import webbrowser
            webbrowser.open(f"file://{folder}")

    def _rename_path(self, path: str) -> None:
        old_name = Path(path).name
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            target = Path(path).parent / new_name.strip()
            try:
                os.rename(path, target)
                self.refresh_all()
            except OSError as e:
                QMessageBox.critical(self, "Rename Failed", str(e))

    def _delete_path(self, path: str) -> None:
        p = Path(path)
        confirm = QMessageBox.question(
            self,
            "Delete Confirmation",
            f"Are you sure you want to delete '{p.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                self.refresh_all()
            except OSError as e:
                QMessageBox.critical(self, "Delete Failed", str(e))

    def _prompt_install_package(self) -> None:
        pkg, ok = QInputDialog.getText(
            self,
            "Install R Package",
            "Enter package name from CRAN (e.g. ggplot2, lme4, car):",
            text="ggplot2",
        )
        if ok and pkg.strip():
            cmd = f'install.packages("{pkg.strip()}", repos="https://cloud.r-project.org")'
            if self.workbench:
                self.workbench._execute_r(cmd, is_repl=True)

    def _on_package_double_clicked(self, item: QListWidgetItem) -> None:
        pkg_name = item.data(Qt.ItemDataRole.UserRole)
        if not pkg_name:
            return
        cmd = f'if (!require("{pkg_name}", quietly=TRUE)) install.packages("{pkg_name}", repos="https://cloud.r-project.org")\nlibrary({pkg_name})'
        if self.workbench:
            self.workbench._execute_r(cmd, is_repl=True)
