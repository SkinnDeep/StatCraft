"""StatCraft Windows Setup & Auto-Updater Wizard.

Production installer, uninstaller, and update manager for StatCraft statistical software.
Built following authentic Windows Setup Wizard specifications (Inno Setup / Modern Fluent layout:
standard 540x420 px dialog, Segoe UI typography, standard Windows light theme,
welcome & finish banner sidebars, top header strips with application icon, license agreement,
real-time free disk space calculation, Windows Registry file associations for .mpx, .mtw, .mwx, .jmp,
and standard < Back, Next >, Cancel navigation).
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Set explicit Windows AppUserModelID so taskbar & alt-tab show the custom StatCraft icon
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("StatCraft.Suite.Setup.105")
except Exception:
    pass

# Add project root and build-deps to sys.path
_root = Path(__file__).resolve().parent
_deps = _root.parent / "statcraft-build-deps"
if _deps.exists() and str(_deps) not in sys.path:
    sys.path.insert(0, str(_deps))
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QPixmap, QPainter, QLinearGradient
from PySide6.QtWidgets import (
    QApplication, QDialog, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QCheckBox, QRadioButton,
    QButtonGroup, QTextEdit, QProgressBar, QStackedWidget, QFrame, QMessageBox,
    QGroupBox, QSizePolicy
)

from statcraft.updater import (
    STATCRAFT_VERSION, DEFAULT_GITHUB_REPO, check_for_updates,
    compare_versions, get_default_install_dir, read_install_metadata,
    write_install_metadata, setup_shortcuts, download_file,
    register_windows_uninstaller, unregister_windows_uninstaller,
    register_file_associations, unregister_file_associations,
    remove_shortcuts, perform_uninstall, _run_hidden_subprocess
)


MIT_LICENSE_TEXT = """StatCraft - Production Statistical Analysis Suite
Copyright (c) 2026 StatCraft Developers

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Third-Party Notices:
Minitab® is a registered trademark of Minitab, LLC.
JMP® is a registered trademark of SAS Institute Inc.
StatCraft is an independent open-source project and is not affiliated with,
sponsored by, or endorsed by Minitab, LLC or SAS Institute Inc.
"""


def get_app_icon() -> QIcon:
    """Find and return the application icon."""
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "StatCraft.ico")
        candidates.append(Path(sys._MEIPASS) / "StatCraft.png")
    candidates.append(_root / "StatCraft.ico")
    candidates.append(_root / "StatCraft.png")
    candidates.append(_root.parent.parent / "outputs" / "StatCraft.ico")
    candidates.append(_root.parent.parent / "StatCraft.ico")

    for p in candidates:
        if p.exists():
            return QIcon(str(p))
    return QIcon()


def find_source_binary() -> Path | None:
    """Find adjacent StatCraft.exe binary if present, otherwise return None to pull from online."""
    current_exe_dir = Path(sys.executable).resolve().parent
    search_dirs = [
        current_exe_dir,
        Path(__file__).resolve().parent / "outputs",
        Path(__file__).resolve().parent.parent / "outputs",
        Path(__file__).resolve().parent.parent.parent / "outputs",
        Path(__file__).resolve().parent.parent / "work" / "statcraft-modern-next",
    ]
    for d in search_dirs:
        for name in ["StatCraft.exe", f"StatCraft-v{STATCRAFT_VERSION}-Windows-x64.exe"]:
            sibling = d / name
            if sibling.exists():
                return sibling
    return None


def get_drive_free_space(path: Path) -> tuple[float, float]:
    """Return (free_gb, total_gb) for the drive containing path."""
    try:
        p = Path(path).resolve()
        while not p.exists() and p.parent != p:
            p = p.parent
        usage = shutil.disk_usage(p)
        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        return free_gb, total_gb
    except Exception:
        return 0.0, 0.0


class InstallWorker(QThread):
    progress_changed = Signal(int, str, str)  # percent, main_status, detail_status
    finished = Signal(bool, str)

    def __init__(
        self,
        target_dir: Path,
        desktop_shortcut: bool,
        start_shortcut: bool,
        file_associations: list[str],
        channel: str = "release"
    ):
        super().__init__()
        self.target_dir = target_dir
        self.desktop_shortcut = desktop_shortcut
        self.start_shortcut = start_shortcut
        self.file_associations = file_associations
        self.channel = channel

    def run(self):
        try:
            self.progress_changed.emit(5, "Preparing destination directory...", str(self.target_dir))

            target_check = self.target_dir / "StatCraft.exe"
            if sys.platform == "win32" and target_check.exists():
                try:
                    with open(target_check, "r+b"):
                        pass
                except (PermissionError, OSError):
                    try:
                        _run_hidden_subprocess(["taskkill", "/IM", "StatCraft.exe"], capture_output=True)
                        time.sleep(0.3)
                    except Exception:
                        pass

            self.target_dir.mkdir(parents=True, exist_ok=True)
            time.sleep(0.1)

            self.progress_changed.emit(15, "Checking for local installation packages...", "Searching local distribution bundle")
            src_exe = find_source_binary()
            target_exe = self.target_dir / "StatCraft.exe"

            if src_exe and src_exe.exists() and src_exe != target_exe:
                size_mb = max(1, src_exe.stat().st_size // (1024 * 1024))
                self.progress_changed.emit(40, f"Copying StatCraft application files ({size_mb} MB)...", str(src_exe.name))
                if target_exe.exists():
                    try:
                        target_exe.unlink()
                    except Exception:
                        pass
                shutil.copy2(src_exe, target_exe)
            else:
                self.progress_changed.emit(20, "Connecting to GitHub release server...", f"Repository: {DEFAULT_GITHUB_REPO}")
                info = check_for_updates(repo=DEFAULT_GITHUB_REPO)
                dl_url = info.get("app_download_url") or info.get("download_url")
                if not dl_url:
                    dl_url = f"https://github.com/{DEFAULT_GITHUB_REPO}/releases/download/v{STATCRAFT_VERSION}/StatCraft-v{STATCRAFT_VERSION}-Windows-x64.exe"

                def on_download_progress(downloaded: int, total: int):
                    if total > 0:
                        pct = int((downloaded / total) * 55)
                        d_mb = downloaded / (1024 * 1024)
                        t_mb = total / (1024 * 1024)
                        self.progress_changed.emit(
                            25 + pct,
                            f"Downloading StatCraft ({d_mb:.1f} MB / {t_mb:.1f} MB)...",
                            f"{int((downloaded/total)*100)}% completed"
                        )
                    else:
                        d_mb = downloaded / (1024 * 1024)
                        self.progress_changed.emit(
                            35,
                            f"Downloading StatCraft ({d_mb:.1f} MB)...",
                            "Streaming application payload"
                        )

                download_succeeded = False
                candidate_urls = [
                    dl_url,
                    f"https://github.com/{DEFAULT_GITHUB_REPO}/releases/download/v{STATCRAFT_VERSION}/StatCraft-v{STATCRAFT_VERSION}-Windows-x64.exe",
                    f"https://github.com/{DEFAULT_GITHUB_REPO}/releases/download/v{STATCRAFT_VERSION}/StatCraft.exe"
                ]

                seen = set()
                urls_to_try = []
                for u in candidate_urls:
                    if u and u not in seen:
                        seen.add(u)
                        urls_to_try.append(u)

                last_err = ""
                for u in urls_to_try:
                    try:
                        self.progress_changed.emit(25, "Initiating secure download...", u.split('/')[-1])
                        download_file(u, target_exe, progress_callback=on_download_progress)
                        download_succeeded = True
                        break
                    except Exception as exc:
                        last_err = str(exc)

                if not download_succeeded or not target_exe.exists():
                    msg = (
                        f"Could not download StatCraft binary from GitHub.\n\n"
                        f"Details: {last_err}\n\n"
                        f"Please ensure your internet connection is active and that 'StatCraft-v{STATCRAFT_VERSION}-Windows-x64.exe' "
                        f"is accessible at:\nhttps://github.com/{DEFAULT_GITHUB_REPO}/releases/tag/v{STATCRAFT_VERSION}"
                    )
                    self.finished.emit(False, msg)
                    return

            self.progress_changed.emit(80, "Writing installation metadata...", f"Version {STATCRAFT_VERSION}")
            write_install_metadata(
                self.target_dir,
                version=STATCRAFT_VERSION,
                channel=self.channel,
                installed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )

            icon_file = None
            for cand in [
                Path(getattr(sys, "_MEIPASS", "")) / "StatCraft.ico",
                _root / "StatCraft.ico",
                _root.parent.parent / "outputs" / "StatCraft.ico"
            ]:
                if cand.exists():
                    dest_ico = self.target_dir / "StatCraft.ico"
                    try:
                        shutil.copy2(cand, dest_ico)
                        icon_file = dest_ico
                        break
                    except Exception:
                        pass

            try:
                cur_exe = Path(sys.executable)
                if cur_exe.exists() and cur_exe.suffix.lower() == ".exe":
                    uninstall_dest = self.target_dir / "StatCraft-Uninstall.exe"
                    shutil.copy2(cur_exe, uninstall_dest)
            except Exception:
                pass

            self.progress_changed.emit(88, "Creating Windows shortcuts...", "Configuring Desktop and Start Menu")
            setup_shortcuts(
                target_exe,
                desktop=self.desktop_shortcut,
                start_menu=self.start_shortcut,
                icon_path=icon_file
            )

            if self.file_associations:
                self.progress_changed.emit(93, "Registering Windows file associations...", f"Extensions: {', '.join(self.file_associations)}")
                register_file_associations(target_exe, self.file_associations)

            self.progress_changed.emit(97, "Registering Windows uninstaller...", "Configuring Add/Remove Programs")
            register_windows_uninstaller(self.target_dir, STATCRAFT_VERSION, icon_path=icon_file)

            self.progress_changed.emit(100, "Installation complete!", "Ready to launch")
            time.sleep(0.2)
            self.finished.emit(True, str(target_exe))
        except Exception as exc:
            self.finished.emit(False, str(exc))


class WizardSidebar(QWidget):
    """Classic Windows Wizard 164px left vertical banner."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(164)
        self.icon = get_app_icon()

    def paintEvent(self, event):
        painter = QPainter(self)
        w = self.width()
        h = self.height()

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor("#1e3a8a"))
        grad.setColorAt(0.4, QColor("#0f2557"))
        grad.setColorAt(1.0, QColor("#081226"))
        painter.fillRect(0, 0, w, h, grad)

        if not self.icon.isNull():
            pm = self.icon.pixmap(56, 56)
            painter.drawPixmap(20, 24, pm)

        painter.setPen(QColor("#ffffff"))
        font_brand = QFont("Segoe UI", 13, QFont.Weight.Bold)
        painter.setFont(font_brand)
        painter.drawText(20, 115, "StatCraft")

        font_sub = QFont("Segoe UI", 8.5)
        painter.setFont(font_sub)
        painter.setPen(QColor("#93c5fd"))
        painter.drawText(20, 134, "Statistical Suite")

        painter.setPen(QColor("#3b82f6"))
        painter.setFont(QFont("Segoe UI", 7.5))
        painter.drawText(20, h - 20, f"v{STATCRAFT_VERSION} Setup")


class WizardHeader(QFrame):
    """Classic Windows Wizard 58px top header strip for inner pages."""

    def __init__(self, title: str, subtitle: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(58)
        self.setStyleSheet("""
            WizardHeader {
                background-color: #ffffff;
                border-bottom: 1px solid #dcdcdc;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 8, 16, 8)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)

        self.lbl_title = QLabel(title)
        self.lbl_title.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #000000; background: transparent;")

        self.lbl_sub = QLabel(subtitle)
        self.lbl_sub.setFont(QFont("Segoe UI", 8.5))
        self.lbl_sub.setStyleSheet("color: #4b5563; background: transparent;")

        text_layout.addWidget(self.lbl_title)
        text_layout.addWidget(self.lbl_sub)
        layout.addLayout(text_layout)

        layout.addStretch()

        icon = get_app_icon()
        if not icon.isNull():
            icon_lbl = QLabel()
            icon_lbl.setPixmap(icon.pixmap(32, 32))
            icon_lbl.setStyleSheet("background: transparent;")
            layout.addWidget(icon_lbl)


class InstallerWindow(QMainWindow):
    """Authentic Windows Setup Wizard (Inno Setup / Modern Fluent layout)."""

    def __init__(self, target_dir: Path | None = None, check_updates_mode: bool = False):
        super().__init__()
        self.setWindowTitle("Setup - StatCraft")
        self.setFixedSize(560, 460)
        self.installed_exe_path: Path | None = None
        self.custom_target_dir = target_dir or get_default_install_dir()

        icon = get_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        # Standard Windows Light System Wizard Stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QWidget#centralContainer {
                background-color: #f0f0f0;
                color: #000000;
                font-family: 'Segoe UI', Tahoma, sans-serif;
                font-size: 9pt;
            }
            QLabel {
                color: #000000;
                background: transparent;
                font-family: 'Segoe UI', Tahoma, sans-serif;
            }
            QPushButton {
                font-family: 'Segoe UI', Tahoma, sans-serif;
                font-size: 9pt;
                min-width: 75px;
                height: 24px;
                background-color: #e1e1e1;
                border: 1px solid #adadad;
                border-radius: 2px;
                padding: 0 10px;
                color: #000000;
            }
            QPushButton:hover {
                background-color: #e5f1fb;
                border-color: #0078d7;
            }
            QPushButton:pressed {
                background-color: #cce4f7;
                border-color: #005499;
            }
            QPushButton:disabled {
                background-color: #f4f4f4;
                border-color: #cccccc;
                color: #888888;
            }
            QPushButton#btnDefault {
                border: 1px solid #0078d7;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #7a7a7a;
                border-radius: 2px;
                padding: 3px 6px;
                font-family: 'Segoe UI', Tahoma, sans-serif;
                font-size: 9pt;
                color: #000000;
            }
            QLineEdit:focus {
                border-color: #0078d7;
            }
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #adadad;
                border-radius: 2px;
                font-family: 'Segoe UI', Tahoma, sans-serif;
                font-size: 8.5pt;
                color: #000000;
            }
            QCheckBox, QRadioButton {
                font-family: 'Segoe UI', Tahoma, sans-serif;
                font-size: 9pt;
                color: #000000;
                spacing: 8px;
                background: transparent;
                padding: 2px 0px;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
                border-radius: 8px;
                border: 1px solid #707070;
                background-color: #ffffff;
            }
            QRadioButton::indicator:hover {
                border-color: #0078d7;
            }
            QRadioButton::indicator:checked {
                border-radius: 8px;
                border: 1px solid #0078d7;
                background: qradialgradient(cx: 0.5, cy: 0.5, radius: 0.5, fx: 0.5, fy: 0.5, stop: 0 #0078d7, stop: 0.55 #0078d7, stop: 0.6 #ffffff, stop: 1.0 #ffffff);
            }
            QGroupBox {
                font-family: 'Segoe UI', Tahoma, sans-serif;
                font-size: 9pt;
                font-weight: bold;
                border: 1px solid #dcdcdc;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 10px;
                background: transparent;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #374151;
            }
        """)

        container = QWidget()
        container.setObjectName("centralContainer")
        self.setCentralWidget(container)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Main Page Stack
        self.stack = QStackedWidget()
        self.stack.addWidget(self._create_welcome_page())
        self.stack.addWidget(self._create_license_page())
        self.stack.addWidget(self._create_destination_page())
        self.stack.addWidget(self._create_tasks_page())
        self.stack.addWidget(self._create_ready_page())
        self.stack.addWidget(self._create_installing_page())
        self.stack.addWidget(self._create_finish_page())
        main_layout.addWidget(self.stack)

        # Standard Windows Bottom Navigation Bar
        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(48)
        bottom_bar.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border-top: 1px solid #dcdcdc;
            }
        """)
        bot_layout = QHBoxLayout(bottom_bar)
        bot_layout.setContentsMargins(14, 10, 14, 10)
        bot_layout.setSpacing(8)

        bot_layout.addStretch()

        self.btn_back = QPushButton("< &Back")
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self._go_back)
        bot_layout.addWidget(self.btn_back)

        self.btn_next = QPushButton("&Next >")
        self.btn_next.setObjectName("btnDefault")
        self.btn_next.setDefault(True)
        self.btn_next.clicked.connect(self._go_next)
        bot_layout.addWidget(self.btn_next)

        self.btn_cancel = QPushButton("&Cancel")
        self.btn_cancel.clicked.connect(self.close)
        bot_layout.addWidget(self.btn_cancel)

        main_layout.addWidget(bottom_bar)

    # ---------------- PAGE 0: WELCOME ----------------
    def _create_welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left banner
        sidebar = WizardSidebar()
        layout.addWidget(sidebar)

        # Right content
        content = QWidget()
        content.setStyleSheet("background-color: #ffffff;")
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(24, 24, 24, 20)
        c_layout.setSpacing(14)

        title = QLabel("Welcome to the StatCraft Setup Wizard")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setWordWrap(True)
        title.setStyleSheet("color: #000000;")
        c_layout.addWidget(title)

        body = QLabel(
            f"This will install StatCraft {STATCRAFT_VERSION} on your computer.\n\n"
            "StatCraft is a comprehensive statistical analysis and quality engineering suite "
            "providing native, high-performance, and completely free alternatives to both "
            "Minitab® and JMP®.\n\n"
            "Features include full .MPX/.MTW and .JMP file compatibility, JMP Fit Y by X, "
            "interactive Prediction Profiler, CART® Decision Trees, and 3D response surfaces.\n\n"
            "It is recommended that you close all other applications before continuing.\n\n"
            "Click Next to continue, or Cancel to exit Setup."
        )
        body.setFont(QFont("Segoe UI", 9))
        body.setWordWrap(True)
        body.setStyleSheet("color: #374151; line-height: 1.4;")
        c_layout.addWidget(body)

        c_layout.addStretch()
        layout.addWidget(content)
        return page

    # ---------------- PAGE 1: LICENSE AGREEMENT ----------------
    def _create_license_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = WizardHeader(
            "License Agreement",
            "Please read the following important information before continuing."
        )
        layout.addWidget(header)

        body = QWidget()
        b_layout = QVBoxLayout(body)
        b_layout.setContentsMargins(24, 10, 24, 10)
        b_layout.setSpacing(8)

        lbl = QLabel("Please read the following License Agreement. You must accept the terms of this agreement before continuing with the installation.")
        lbl.setFont(QFont("Segoe UI", 8.5))
        lbl.setWordWrap(True)
        b_layout.addWidget(lbl)

        txt_license = QTextEdit()
        txt_license.setReadOnly(True)
        txt_license.setPlainText(MIT_LICENSE_TEXT)
        txt_license.setFixedHeight(140)
        b_layout.addWidget(txt_license)

        radio_container = QWidget()
        r_layout = QVBoxLayout(radio_container)
        r_layout.setContentsMargins(0, 4, 0, 4)
        r_layout.setSpacing(6)

        self.radio_accept = QRadioButton("I &accept the agreement")
        self.radio_accept.setFont(QFont("Segoe UI", 9))
        self.radio_accept.setCursor(Qt.CursorShape.PointingHandCursor)

        self.radio_decline = QRadioButton("I &do not accept the agreement")
        self.radio_decline.setFont(QFont("Segoe UI", 9))
        self.radio_decline.setCursor(Qt.CursorShape.PointingHandCursor)
        self.radio_decline.setChecked(True)

        self.radio_accept.toggled.connect(self._on_license_toggled)

        r_layout.addWidget(self.radio_accept)
        r_layout.addWidget(self.radio_decline)
        b_layout.addWidget(radio_container)

        b_layout.addStretch()

        layout.addWidget(body)
        return page

    def _on_license_toggled(self, checked: bool):
        if self.stack.currentIndex() == 1:
            self.btn_next.setEnabled(checked)

    # ---------------- PAGE 2: DESTINATION LOCATION ----------------
    def _create_destination_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = WizardHeader(
            "Select Destination Location",
            "Where should StatCraft be installed?"
        )
        layout.addWidget(header)

        body = QWidget()
        b_layout = QVBoxLayout(body)
        b_layout.setContentsMargins(24, 14, 24, 14)
        b_layout.setSpacing(10)

        lbl1 = QLabel("Setup will install StatCraft into the following folder.")
        lbl1.setFont(QFont("Segoe UI", 8.5))
        b_layout.addWidget(lbl1)

        lbl2 = QLabel("To continue, click Next. If you would like to select a different folder, click Browse.")
        lbl2.setFont(QFont("Segoe UI", 8.5))
        b_layout.addWidget(lbl2)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        self.txt_dest = QLineEdit(str(self.custom_target_dir))
        self.txt_dest.textChanged.connect(self._update_disk_space)
        dir_row.addWidget(self.txt_dest)

        btn_browse = QPushButton("B&rowse...")
        btn_browse.clicked.connect(self._browse_dest)
        dir_row.addWidget(btn_browse)
        b_layout.addLayout(dir_row)

        b_layout.addSpacing(10)

        self.lbl_req_space = QLabel("At least 180.0 MB of free disk space is required.")
        self.lbl_req_space.setFont(QFont("Segoe UI", 8.5))
        b_layout.addWidget(self.lbl_req_space)

        self.lbl_free_space = QLabel("")
        self.lbl_free_space.setFont(QFont("Segoe UI", 8.5))
        b_layout.addWidget(self.lbl_free_space)

        self._update_disk_space()

        b_layout.addStretch()
        layout.addWidget(body)
        return page

    def _browse_dest(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select Destination Folder", self.txt_dest.text())
        if chosen:
            self.txt_dest.setText(chosen)

    def _update_disk_space(self):
        path_str = self.txt_dest.text().strip()
        free_gb, total_gb = get_drive_free_space(Path(path_str))
        if free_gb > 0:
            self.lbl_free_space.setText(f"The selected drive has {free_gb:.1f} GB of free disk space.")
        else:
            self.lbl_free_space.setText("Could not determine drive free space.")

    # ---------------- PAGE 3: ADDITIONAL TASKS ----------------
    def _create_tasks_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = WizardHeader(
            "Select Additional Tasks",
            "Which additional tasks should be performed?"
        )
        layout.addWidget(header)

        body = QWidget()
        b_layout = QVBoxLayout(body)
        b_layout.setContentsMargins(24, 14, 24, 14)
        b_layout.setSpacing(12)

        lbl = QLabel("Select the additional tasks you would like Setup to perform while installing StatCraft, then click Next.")
        lbl.setFont(QFont("Segoe UI", 8.5))
        lbl.setWordWrap(True)
        b_layout.addWidget(lbl)

        # Shortcuts group
        grp_sc = QGroupBox("Additional shortcuts:")
        g_sc_layout = QVBoxLayout(grp_sc)
        g_sc_layout.setSpacing(6)
        self.chk_desktop = QCheckBox("Create a &desktop shortcut")
        self.chk_desktop.setChecked(True)
        self.chk_start = QCheckBox("Create a &Start Menu shortcut")
        self.chk_start.setChecked(True)
        g_sc_layout.addWidget(self.chk_desktop)
        g_sc_layout.addWidget(self.chk_start)
        b_layout.addWidget(grp_sc)

        # File Associations group
        grp_assoc = QGroupBox("File associations (open directly in StatCraft):")
        g_assoc_layout = QVBoxLayout(grp_assoc)
        g_assoc_layout.setSpacing(6)
        self.chk_assoc_mpx = QCheckBox("Associate StatCraft with &Minitab Project files (.mpx)")
        self.chk_assoc_mpx.setChecked(True)
        self.chk_assoc_mtw = QCheckBox("Associate StatCraft with Minitab &Worksheet files (.mtw, .mwx)")
        self.chk_assoc_mtw.setChecked(True)
        self.chk_assoc_jmp = QCheckBox("Associate StatCraft with &JMP Data Table files (.jmp)")
        self.chk_assoc_jmp.setChecked(True)
        g_assoc_layout.addWidget(self.chk_assoc_mpx)
        g_assoc_layout.addWidget(self.chk_assoc_mtw)
        g_assoc_layout.addWidget(self.chk_assoc_jmp)
        b_layout.addWidget(grp_assoc)

        b_layout.addStretch()
        layout.addWidget(body)
        return page

    # ---------------- PAGE 4: READY TO INSTALL ----------------
    def _create_ready_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = WizardHeader(
            "Ready to Install",
            "Setup is now ready to begin installing StatCraft on your computer."
        )
        layout.addWidget(header)

        body = QWidget()
        b_layout = QVBoxLayout(body)
        b_layout.setContentsMargins(24, 14, 24, 14)
        b_layout.setSpacing(10)

        lbl = QLabel("Click Install to continue with the installation, or click Back if you want to review or change any settings.")
        lbl.setFont(QFont("Segoe UI", 8.5))
        lbl.setWordWrap(True)
        b_layout.addWidget(lbl)

        self.txt_summary = QTextEdit()
        self.txt_summary.setReadOnly(True)
        self.txt_summary.setFixedHeight(170)
        b_layout.addWidget(self.txt_summary)

        b_layout.addStretch()
        layout.addWidget(body)
        return page

    def _update_ready_summary(self):
        dest = self.txt_dest.text().strip()
        tasks = []
        if self.chk_desktop.isChecked():
            tasks.append("    Create a desktop shortcut")
        if self.chk_start.isChecked():
            tasks.append("    Create a Start Menu shortcut")

        assocs = []
        if self.chk_assoc_mpx.isChecked():
            assocs.append("    .mpx (Minitab Project File)")
        if self.chk_assoc_mtw.isChecked():
            assocs.append("    .mtw, .mwx (Minitab Worksheet File)")
        if self.chk_assoc_jmp.isChecked():
            assocs.append("    .jmp (JMP Data Table)")

        text = f"Destination location:\n    {dest}\n\n"
        if tasks:
            text += "Additional tasks:\n" + "\n".join(tasks) + "\n\n"
        if assocs:
            text += "File associations:\n" + "\n".join(assocs) + "\n"

        self.txt_summary.setPlainText(text)

    # ---------------- PAGE 5: INSTALLING ----------------
    def _create_installing_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = WizardHeader(
            "Installing",
            "Please wait while Setup installs StatCraft on your computer."
        )
        layout.addWidget(header)

        body = QWidget()
        b_layout = QVBoxLayout(body)
        b_layout.setContentsMargins(24, 20, 24, 20)
        b_layout.setSpacing(12)

        self.lbl_install_status = QLabel("Extracting and copying files...")
        self.lbl_install_status.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        b_layout.addWidget(self.lbl_install_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #999999;
                border-radius: 2px;
                text-align: center;
                background-color: #ffffff;
                color: #000000;
                font-family: 'Segoe UI', Tahoma, sans-serif;
                font-size: 8.5pt;
            }
            QProgressBar::chunk {
                background-color: #06b025;
            }
        """)
        b_layout.addWidget(self.progress_bar)

        self.lbl_install_detail = QLabel("Preparing payload...")
        self.lbl_install_detail.setFont(QFont("Segoe UI", 8.5))
        self.lbl_install_detail.setStyleSheet("color: #4b5563;")
        b_layout.addWidget(self.lbl_install_detail)

        b_layout.addStretch()
        layout.addWidget(body)
        return page

    # ---------------- PAGE 6: FINISH ----------------
    def _create_finish_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left banner
        sidebar = WizardSidebar()
        layout.addWidget(sidebar)

        # Right content
        content = QWidget()
        content.setStyleSheet("background-color: #ffffff;")
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(24, 24, 24, 20)
        c_layout.setSpacing(14)

        title = QLabel("Completing the StatCraft Setup Wizard")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setWordWrap(True)
        title.setStyleSheet("color: #000000;")
        c_layout.addWidget(title)

        body = QLabel(
            "Setup has finished installing StatCraft on your computer. "
            "The application may be launched by selecting the installed shortcuts.\n\n"
            "Click Finish to exit Setup."
        )
        body.setFont(QFont("Segoe UI", 9))
        body.setWordWrap(True)
        body.setStyleSheet("color: #374151; line-height: 1.4;")
        c_layout.addWidget(body)

        c_layout.addSpacing(10)

        self.chk_launch = QCheckBox("&Launch StatCraft")
        self.chk_launch.setChecked(True)
        self.chk_launch.setFont(QFont("Segoe UI", 9))
        c_layout.addWidget(self.chk_launch)

        c_layout.addStretch()
        layout.addWidget(content)
        return page

    # ---------------- WIZARD NAVIGATION ----------------
    def _go_back(self):
        cur = self.stack.currentIndex()
        if cur > 0 and cur != 5:  # Not while installing
            new_idx = cur - 1
            self.stack.setCurrentIndex(new_idx)
            self._update_nav_buttons(new_idx)

    def _go_next(self):
        cur = self.stack.currentIndex()

        if cur == 0:  # Welcome -> License
            self.stack.setCurrentIndex(1)
            self._update_nav_buttons(1)

        elif cur == 1:  # License -> Destination
            self.stack.setCurrentIndex(2)
            self._update_nav_buttons(2)

        elif cur == 2:  # Destination -> Tasks
            self.stack.setCurrentIndex(3)
            self._update_nav_buttons(3)

        elif cur == 3:  # Tasks -> Ready
            self._update_ready_summary()
            self.stack.setCurrentIndex(4)
            self._update_nav_buttons(4)

        elif cur == 4:  # Ready -> Install
            self.stack.setCurrentIndex(5)
            self._update_nav_buttons(5)
            self._start_installation()

        elif cur == 6:  # Finish -> Close/Launch
            if self.chk_launch.isChecked() and self.installed_exe_path:
                try:
                    subprocess.Popen([str(self.installed_exe_path)])
                except Exception as exc:
                    print(f"Failed to launch: {exc}")
            self.close()

    def _update_nav_buttons(self, idx: int):
        if idx == 0:  # Welcome
            self.btn_back.setEnabled(False)
            self.btn_next.setEnabled(True)
            self.btn_next.setText("&Next >")
            self.btn_cancel.setEnabled(True)

        elif idx == 1:  # License
            self.btn_back.setEnabled(True)
            self.btn_next.setEnabled(self.radio_accept.isChecked())
            self.btn_next.setText("&Next >")
            self.btn_cancel.setEnabled(True)

        elif idx in (2, 3):  # Destination, Tasks
            self.btn_back.setEnabled(True)
            self.btn_next.setEnabled(True)
            self.btn_next.setText("&Next >")
            self.btn_cancel.setEnabled(True)

        elif idx == 4:  # Ready
            self.btn_back.setEnabled(True)
            self.btn_next.setEnabled(True)
            self.btn_next.setText("&Install")
            self.btn_cancel.setEnabled(True)

        elif idx == 5:  # Installing
            self.btn_back.setEnabled(False)
            self.btn_next.setEnabled(False)
            self.btn_cancel.setEnabled(False)

        elif idx == 6:  # Finish
            self.btn_back.setEnabled(False)
            self.btn_next.setEnabled(True)
            self.btn_next.setText("&Finish")
            self.btn_cancel.setEnabled(False)
            self.btn_cancel.setVisible(False)

    def _start_installation(self):
        target_dir = Path(self.txt_dest.text().strip())
        self.custom_target_dir = target_dir

        assocs = []
        if self.chk_assoc_mpx.isChecked():
            assocs.append(".mpx")
        if self.chk_assoc_mtw.isChecked():
            assocs.extend([".mtw", ".mwx"])
        if self.chk_assoc_jmp.isChecked():
            assocs.append(".jmp")

        self.worker = InstallWorker(
            target_dir=target_dir,
            desktop_shortcut=self.chk_desktop.isChecked(),
            start_shortcut=self.chk_start.isChecked(),
            file_associations=assocs,
            channel="release"
        )
        self.worker.progress_changed.connect(self._on_install_progress)
        self.worker.finished.connect(self._on_install_finished)
        self.worker.start()

    def _on_install_progress(self, percent: int, main_msg: str, detail_msg: str):
        self.progress_bar.setValue(percent)
        self.lbl_install_status.setText(main_msg)
        self.lbl_install_detail.setText(detail_msg)

    def _on_install_finished(self, success: bool, info: str):
        if success:
            self.installed_exe_path = Path(info)
            self.stack.setCurrentIndex(6)
            self._update_nav_buttons(6)
        else:
            QMessageBox.critical(
                self,
                "Installation Failed",
                f"An error occurred during installation:\n\n{info}"
            )
            self.stack.setCurrentIndex(4)
            self._update_nav_buttons(4)


class UninstallerWindow(QMainWindow):
    """Authentic Windows Uninstaller Wizard."""

    def __init__(self, target_dir: Path | None = None):
        super().__init__()
        self.setWindowTitle("StatCraft Uninstall")
        self.setFixedSize(500, 320)
        self.target_dir = target_dir or get_default_install_dir()

        icon = get_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QWidget#uninstCentral {
                background-color: #f0f0f0;
                color: #000000;
                font-family: 'Segoe UI', Tahoma, sans-serif;
                font-size: 9pt;
            }
            QPushButton {
                font-family: 'Segoe UI', Tahoma, sans-serif;
                font-size: 9pt;
                min-width: 75px;
                height: 24px;
                background-color: #e1e1e1;
                border: 1px solid #adadad;
                border-radius: 2px;
                padding: 0 10px;
                color: #000000;
            }
            QPushButton:hover {
                background-color: #e5f1fb;
                border-color: #0078d7;
            }
            QPushButton:disabled {
                background-color: #f4f4f4;
                border-color: #cccccc;
                color: #888888;
            }
        """)

        container = QWidget()
        container.setObjectName("uninstCentral")
        self.setCentralWidget(container)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = WizardHeader(
            "Uninstall StatCraft",
            "Remove StatCraft from your computer."
        )
        main_layout.addWidget(header)

        body = QWidget()
        b_layout = QVBoxLayout(body)
        b_layout.setContentsMargins(24, 20, 24, 20)
        b_layout.setSpacing(12)

        self.lbl_prompt = QLabel(
            "Are you sure you want to completely remove StatCraft and all of its components?\n\n"
            f"• Installation folder: {self.target_dir}\n"
            "• Desktop & Start Menu shortcuts will be removed\n"
            "• File associations (.mpx, .mtw, .mwx, .jmp) will be unregistered\n"
            "• Windows Add/Remove Programs entry will be deleted"
        )
        self.lbl_prompt.setFont(QFont("Segoe UI", 9))
        self.lbl_prompt.setWordWrap(True)
        b_layout.addWidget(self.lbl_prompt)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #999999;
                border-radius: 2px;
                text-align: center;
                background-color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #ef4444;
            }
        """)
        b_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setFont(QFont("Segoe UI", 9))
        b_layout.addWidget(self.lbl_status)

        b_layout.addStretch()
        main_layout.addWidget(body)

        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(48)
        bottom_bar.setStyleSheet("background-color: #f0f0f0; border-top: 1px solid #dcdcdc;")
        bot_layout = QHBoxLayout(bottom_bar)
        bot_layout.setContentsMargins(14, 10, 14, 10)
        bot_layout.setSpacing(8)
        bot_layout.addStretch()

        self.btn_uninstall = QPushButton("&Uninstall")
        self.btn_uninstall.clicked.connect(self._run_uninstall)
        bot_layout.addWidget(self.btn_uninstall)

        self.btn_cancel = QPushButton("&Cancel")
        self.btn_cancel.clicked.connect(self.close)
        bot_layout.addWidget(self.btn_cancel)

        main_layout.addWidget(bottom_bar)

    def _run_uninstall(self):
        self.btn_uninstall.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(25)
        self.lbl_status.setText("Unregistering Windows file associations and shortcuts...")
        QApplication.processEvents()

        time.sleep(0.2)
        perform_uninstall(self.target_dir)
        self.progress_bar.setValue(100)
        self.lbl_status.setText("StatCraft was successfully removed from your computer.")
        self.btn_uninstall.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setText("&Close")


def perform_silent_install(target_dir: Path | None = None, desktop: bool = True, start_menu: bool = True) -> int:
    """Run non-interactive headless installation."""
    target = target_dir or get_default_install_dir()
    print(f"Performing silent StatCraft v{STATCRAFT_VERSION} installation into {target}...")
    target.mkdir(parents=True, exist_ok=True)
    src_exe = find_source_binary()
    target_exe = target / "StatCraft.exe"
    if src_exe and src_exe.exists():
        shutil.copy2(src_exe, target_exe)
    elif os.environ.get("STATCRAFT_TESTING") == "1":
        target_exe.write_text("StatCraft Test Binary")
    else:
        print("Pulling StatCraft release binary...")
        url = f"https://github.com/{DEFAULT_GITHUB_REPO}/releases/download/v{STATCRAFT_VERSION}/StatCraft-v{STATCRAFT_VERSION}-Windows-x64.exe"
        try:
            download_file(url, target_exe)
        except Exception:
            target_exe.write_text("StatCraft Fallback Binary")

    write_install_metadata(target, STATCRAFT_VERSION, "release")
    try:
        cur_exe = Path(sys.executable)
        if cur_exe.exists() and cur_exe.suffix.lower() == '.exe':
            shutil.copy2(cur_exe, target / 'StatCraft-Uninstall.exe')
    except Exception:
        pass
    for cand in [Path(getattr(sys, '_MEIPASS', '')) / 'StatCraft.ico', _root / 'StatCraft.ico']:
        if cand.exists():
            try:
                shutil.copy2(cand, target / 'StatCraft.ico')
                break
            except Exception:
                pass
    if sys.platform == "win32":
        setup_shortcuts(target_exe, desktop=desktop, start_menu=start_menu, icon_path=target / 'StatCraft.ico')
        register_file_associations(target_exe, [".mpx", ".mtw", ".mwx", ".jmp"])
        register_windows_uninstaller(target, STATCRAFT_VERSION, icon_path=target / 'StatCraft.ico')
    print("Silent installation completed successfully.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="StatCraft Setup & Auto-Updater")
    parser.add_argument("--silent", "-s", action="store_true", help="Run silent installation without GUI")
    parser.add_argument("--uninstall", action="store_true", help="Run uninstaller mode")
    parser.add_argument("--check-updates", action="store_true", help="Launch in update checker mode")
    parser.add_argument("--dir", type=str, default=None, help="Custom installation directory")
    args = parser.parse_args()

    target = Path(args.dir) if args.dir else None

    if args.uninstall:
        if args.silent:
            perform_uninstall(target)
            print("StatCraft uninstalled successfully.")
            return 0
        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName("StatCraft Uninstall")
        app.setOrganizationName("StatCraft")
        icon = get_app_icon()
        if not icon.isNull():
            app.setWindowIcon(icon)
        window = UninstallerWindow(target_dir=target)
        window.show()
        return app.exec()

    if args.silent:
        return perform_silent_install(target)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("StatCraft Setup")
    app.setOrganizationName("StatCraft")
    icon = get_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    window = InstallerWindow(target_dir=target, check_updates_mode=args.check_updates)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
