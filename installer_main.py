"""StatCraft Setup & Auto-Updater Wizard.

Production installer, uninstaller, and update manager for StatCraft statistical software.
Mirrors modern statistical software installation wizards with offline bundled installation,
automatic update checks, silent installs, shortcut creation, and Windows Add/Remove integration.
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
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("StatCraft.Suite.Setup.104")
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
from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QCheckBox, QProgressBar,
    QStackedWidget, QFrame, QMessageBox, QComboBox, QTextEdit
)

from statcraft.updater import (
    STATCRAFT_VERSION, DEFAULT_GITHUB_REPO, check_for_updates,
    compare_versions, get_default_install_dir, read_install_metadata,
    write_install_metadata, setup_shortcuts, download_file,
    register_windows_uninstaller, unregister_windows_uninstaller,
    remove_shortcuts, perform_uninstall
)


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
    for name in ["StatCraft.exe", f"StatCraft-v{STATCRAFT_VERSION}-Windows-x64.exe"]:
        sibling = current_exe_dir / name
        if sibling.exists():
            return sibling
    return None


class InstallWorker(QThread):
    progress_changed = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self, target_dir: Path, desktop_shortcut: bool, start_shortcut: bool, channel: str):
        super().__init__()
        self.target_dir = target_dir
        self.desktop_shortcut = desktop_shortcut
        self.start_shortcut = start_shortcut
        self.channel = channel

    def run(self):
        try:
            self.progress_changed.emit(10, "Preparing installation directory...")
            self.target_dir.mkdir(parents=True, exist_ok=True)
            time.sleep(0.15)

            self.progress_changed.emit(25, "Locating StatCraft application binaries...")
            # Terminate running instance if any to release Windows file locks
            if sys.platform == "win32":
                try:
                    subprocess.run(["taskkill", "/F", "/IM", "StatCraft.exe"], capture_output=True)
                except Exception:
                    pass

            src_exe = find_source_binary()
            target_exe = self.target_dir / "StatCraft.exe"

            if src_exe and src_exe.exists() and src_exe != target_exe:
                size_mb = max(1, src_exe.stat().st_size // (1024 * 1024))
                self.progress_changed.emit(45, f"Installing local StatCraft binary ({size_mb} MB)...")
                if target_exe.exists():
                    try:
                        target_exe.unlink()
                    except Exception:
                        pass
                shutil.copy2(src_exe, target_exe)
            else:
                self.progress_changed.emit(25, "Connecting to GitHub release server...")
                info = check_for_updates(repo=DEFAULT_GITHUB_REPO)
                dl_url = info.get("app_download_url") or info.get("download_url")
                if not dl_url:
                    dl_url = f"https://github.com/{DEFAULT_GITHUB_REPO}/releases/download/v{STATCRAFT_VERSION}/StatCraft-v{STATCRAFT_VERSION}-Windows-x64.exe"

                self.progress_changed.emit(30, f"Downloading StatCraft from GitHub...")

                def on_download_progress(downloaded: int, total: int):
                    if total > 0:
                        pct = int((downloaded / total) * 55)
                        d_mb = downloaded / (1024 * 1024)
                        t_mb = total / (1024 * 1024)
                        self.progress_changed.emit(30 + pct, f"Downloading StatCraft ({d_mb:.1f} MB / {t_mb:.1f} MB)...")
                    else:
                        d_mb = downloaded / (1024 * 1024)
                        self.progress_changed.emit(45, f"Downloading StatCraft ({d_mb:.1f} MB)...")

                download_succeeded = False
                candidate_urls = [
                    dl_url,
                    f"https://github.com/{DEFAULT_GITHUB_REPO}/releases/download/v{STATCRAFT_VERSION}/StatCraft-v{STATCRAFT_VERSION}-Windows-x64.exe",
                    f"https://github.com/{DEFAULT_GITHUB_REPO}/releases/download/v{STATCRAFT_VERSION}/StatCraft.exe"
                ]

                # De-duplicate while preserving order
                seen = set()
                urls_to_try = []
                for u in candidate_urls:
                    if u and u not in seen:
                        seen.add(u)
                        urls_to_try.append(u)

                last_err = ""
                for u in urls_to_try:
                    try:
                        self.progress_changed.emit(32, f"Connecting to {u}...")
                        download_file(u, target_exe, progress_callback=on_download_progress)
                        download_succeeded = True
                        break
                    except Exception as exc:
                        last_err = str(exc)

                if not download_succeeded or not target_exe.exists():
                    msg = (
                        f"Could not download StatCraft binary from GitHub.\n\n"
                        f"Last error: {last_err}\n\n"
                        f"Please verify that 'StatCraft-v{STATCRAFT_VERSION}-Windows-x64.exe' is uploaded to the release:\n"
                        f"https://github.com/{DEFAULT_GITHUB_REPO}/releases/tag/v{STATCRAFT_VERSION}\n\n"
                        f"Or place 'StatCraft-v{STATCRAFT_VERSION}-Windows-x64.exe' in the same folder as this setup tool."
                    )
                    self.finished.emit(False, msg)
                    return

            self.progress_changed.emit(70, "Writing installation and version metadata...")
            write_install_metadata(
                self.target_dir,
                version=STATCRAFT_VERSION,
                channel=self.channel,
                installed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )

            # Copy icon if available
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

            # Copy this installer as the uninstaller into target directory
            try:
                cur_exe = Path(sys.executable)
                if cur_exe.exists() and cur_exe.suffix.lower() == ".exe":
                    uninstall_dest = self.target_dir / "StatCraft-Uninstall.exe"
                    shutil.copy2(cur_exe, uninstall_dest)
            except Exception:
                pass

            self.progress_changed.emit(85, "Registering Windows shortcuts & Add/Remove Programs...")
            setup_shortcuts(
                target_exe,
                desktop=self.desktop_shortcut,
                start_menu=self.start_shortcut,
                icon_path=icon_file
            )

            # Register in Windows Add/Remove Programs
            register_windows_uninstaller(self.target_dir, STATCRAFT_VERSION, icon_path=icon_file)

            self.progress_changed.emit(100, "Installation completed successfully.")
            time.sleep(0.2)
            self.finished.emit(True, str(target_exe))
        except Exception as exc:
            self.finished.emit(False, str(exc))


class InstallerWindow(QMainWindow):
    """Modern statistical setup wizard with universal high-contrast dark theme."""

    def __init__(self, target_dir: Path | None = None, check_updates_mode: bool = False):
        super().__init__()
        self.setWindowTitle("StatCraft Setup Wizard")
        self.setFixedSize(700, 530)
        self.installed_exe_path = None
        self.custom_target_dir = target_dir or get_default_install_dir()

        # Set window icon
        icon = get_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        # Main widget & layout
        main_widget = QWidget()
        main_widget.setStyleSheet("background-color: #0b1329; color: #f8fafc;")
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header Banner
        header = QFrame()
        header.setFixedHeight(86)
        header.setStyleSheet("background-color: #081124; border-bottom: 2px solid #c5a059;")
        head_layout = QHBoxLayout(header)
        head_layout.setContentsMargins(24, 12, 24, 12)

        head_text = QVBoxLayout()
        title = QLabel("StatCraft Setup Wizard")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; border: none; background: transparent;")
        subtitle = QLabel("Statistical Software & Quality Tools • Version " + STATCRAFT_VERSION)
        subtitle.setStyleSheet("color: #fbbf24; font-size: 10pt; font-weight: 500; border: none; background: transparent;")
        head_text.addWidget(title)
        head_text.addWidget(subtitle)
        head_layout.addLayout(head_text)
        head_layout.addStretch()

        badge = QLabel("PRODUCTION READY")
        badge.setStyleSheet("color: #4ade80; background: #064e3b; border: 1px solid #22c55e; border-radius: 4px; padding: 4px 10px; font-weight: bold; font-size: 8pt;")
        head_layout.addWidget(badge)

        main_layout.addWidget(header)

        # 2. Content Area: Sidebar + Stacked Pages
        body_widget = QWidget()
        body_widget.setStyleSheet("background-color: #0b1329; color: #f8fafc;")
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(18, 18, 18, 18)
        body_layout.setSpacing(18)

        # Sidebar navigation steps
        sidebar = QFrame()
        sidebar.setFixedWidth(160)
        sidebar.setStyleSheet("background-color: #111e38; border: 1px solid #1e293b; border-radius: 8px; padding: 6px;")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setSpacing(10)
        side_layout.setContentsMargins(12, 14, 12, 14)

        nav_title = QLabel("STEPS")
        nav_title.setStyleSheet("font-size: 8pt; font-weight: bold; color: #94a3b8; border: none; background: transparent;")
        side_layout.addWidget(nav_title)

        self.step_labels = [
            QLabel("1. Welcome"),
            QLabel("2. Configuration"),
            QLabel("3. Installation"),
            QLabel("4. Finish")
        ]
        for idx, lbl in enumerate(self.step_labels):
            lbl.setFont(QFont("Segoe UI", 9.5))
            lbl.setStyleSheet("color: #94a3b8; padding: 6px 0px; border: none; background: transparent;")
            side_layout.addWidget(lbl)
        side_layout.addStretch()
        body_layout.addWidget(sidebar)

        # Stacked Pages
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: transparent;")
        self.stack.addWidget(self._create_welcome_page())
        self.stack.addWidget(self._create_options_page())
        self.stack.addWidget(self._create_progress_page())
        self.stack.addWidget(self._create_finish_page())
        body_layout.addWidget(self.stack)

        main_layout.addWidget(body_widget)

        # 3. Bottom Navigation Bar
        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(60)
        bottom_bar.setStyleSheet("background-color: #081124; border-top: 1px solid #1e293b;")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(20, 10, 20, 10)

        self.btn_check_online = QPushButton("Check Online for Updates…")
        self.btn_check_online.setStyleSheet("""
            QPushButton { padding: 7px 14px; border: 1px solid #334155; border-radius: 5px; background-color: #1e293b; color: #f1f5f9; font-weight: 500; }
            QPushButton:hover { background-color: #334155; color: #ffffff; }
        """)
        self.btn_check_online.clicked.connect(self._check_online_updates)
        bottom_layout.addWidget(self.btn_check_online)

        bottom_layout.addStretch()

        self.btn_back = QPushButton("Back")
        self.btn_back.setEnabled(False)
        self.btn_back.setStyleSheet("""
            QPushButton { padding: 7px 18px; border: 1px solid #334155; border-radius: 5px; background-color: #1e293b; color: #f1f5f9; font-weight: 500; }
            QPushButton:hover { background-color: #334155; color: #ffffff; }
            QPushButton:disabled { color: #475569; background-color: #0f172a; border-color: #1e293b; }
        """)
        self.btn_back.clicked.connect(self._go_back)
        bottom_layout.addWidget(self.btn_back)

        self.btn_next = QPushButton("Next")
        self.btn_next.setStyleSheet("""
            QPushButton { background-color: #0284c7; color: #ffffff; font-weight: bold; padding: 7px 22px; border-radius: 5px; border: none; }
            QPushButton:hover { background-color: #0369a1; }
        """)
        self.btn_next.clicked.connect(self._go_next)
        bottom_layout.addWidget(self.btn_next)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("""
            QPushButton { padding: 7px 18px; border: 1px solid #334155; border-radius: 5px; background-color: #1e293b; color: #f1f5f9; }
            QPushButton:hover { background-color: #334155; color: #ffffff; }
        """)
        self.btn_cancel.clicked.connect(self.close)
        bottom_layout.addWidget(self.btn_cancel)

        main_layout.addWidget(bottom_bar)

        self._update_step_styles(0)

        if check_updates_mode:
            self._check_online_updates()

    def _update_step_styles(self, current_idx: int):
        for idx, lbl in enumerate(self.step_labels):
            if idx == current_idx:
                lbl.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
                lbl.setStyleSheet("color: #38bdf8; font-weight: bold; padding: 6px 0px; border: none; background: transparent;")
            elif idx < current_idx:
                lbl.setStyleSheet("color: #4ade80; padding: 6px 0px; border: none; background: transparent;")
            else:
                lbl.setStyleSheet("color: #64748b; padding: 6px 0px; border: none; background: transparent;")

    def _create_welcome_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        h = QLabel("Install or Upgrade StatCraft")
        h.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        h.setStyleSheet("color: #f8fafc; border: none; background: transparent;")
        layout.addWidget(h)

        desc = QLabel(
            "This setup wizard guides you through installing or updating StatCraft.\n\n"
            "• Offline-ready standalone installation with zero external dependencies\n"
            "• Interactive 3D Surface plots with rotatable CAD ViewCube and lighting\n"
            "• Comprehensive Basic Statistics, DOE, MSA, Quality & Control Charts\n"
            "• Native MPX project compatibility and Windows Add/Remove integration"
        )
        desc.setStyleSheet("color: #cbd5e1; line-height: 1.6; font-size: 9.5pt; border: none; background: transparent;")
        layout.addWidget(desc)

        # Detect existing install status
        box = QFrame()
        box.setStyleSheet("background-color: #111e38; border: 1px solid #1e293b; border-radius: 8px; padding: 12px;")
        b_layout = QVBoxLayout(box)

        meta = read_install_metadata(self.custom_target_dir)
        cur_v = meta.get("version")
        target_exe = self.custom_target_dir / "StatCraft.exe"

        status_title = QLabel("System Status:")
        status_title.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        status_title.setStyleSheet("color: #f8fafc; border: none; background: transparent;")
        b_layout.addWidget(status_title)

        if target_exe.exists():
            self.lbl_detect = QLabel(f"StatCraft detected at {self.custom_target_dir} (Version: v{cur_v}).\nReady to upgrade to version {STATCRAFT_VERSION}.")
            self.lbl_detect.setStyleSheet("color: #38bdf8; font-weight: 500; font-size: 9pt; border: none; background: transparent;")
        else:
            self.lbl_detect = QLabel(f"StatCraft is not yet installed.\nReady for fresh installation of version {STATCRAFT_VERSION}.")
            self.lbl_detect.setStyleSheet("color: #4ade80; font-weight: 500; font-size: 9pt; border: none; background: transparent;")
        b_layout.addWidget(self.lbl_detect)

        layout.addWidget(box)
        layout.addStretch()
        return page

    def _create_options_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        h = QLabel("Installation Options")
        h.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        h.setStyleSheet("color: #f8fafc; border: none; background: transparent;")
        layout.addWidget(h)

        # Destination Folder
        dest_lbl = QLabel("Destination Directory:")
        dest_lbl.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        dest_lbl.setStyleSheet("color: #cbd5e1; border: none; background: transparent;")
        layout.addWidget(dest_lbl)

        d_layout = QHBoxLayout()
        self.txt_dir = QLineEdit(str(self.custom_target_dir))
        self.txt_dir.setStyleSheet("padding: 7px 10px; border: 1px solid #334155; border-radius: 5px; background-color: #111e38; color: #f8fafc;")
        d_layout.addWidget(self.txt_dir)

        btn_browse = QPushButton("Browse…")
        btn_browse.setStyleSheet("""
            QPushButton { padding: 7px 14px; border: 1px solid #334155; border-radius: 5px; background-color: #1e293b; color: #f1f5f9; }
            QPushButton:hover { background-color: #334155; color: #ffffff; }
        """)
        btn_browse.clicked.connect(self._browse_dir)
        d_layout.addWidget(btn_browse)
        layout.addLayout(d_layout)

        layout.addSpacing(8)

        # Shortcuts
        sc_lbl = QLabel("Shortcuts & Integration:")
        sc_lbl.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        sc_lbl.setStyleSheet("color: #cbd5e1; border: none; background: transparent;")
        layout.addWidget(sc_lbl)

        self.chk_desktop = QCheckBox("Create Desktop Shortcut")
        self.chk_desktop.setChecked(True)
        self.chk_desktop.setStyleSheet("color: #e2e8f0; font-size: 9.5pt;")
        layout.addWidget(self.chk_desktop)

        self.chk_start = QCheckBox("Create Start Menu Shortcut & Add/Remove Programs Entry")
        self.chk_start.setChecked(True)
        self.chk_start.setStyleSheet("color: #e2e8f0; font-size: 9.5pt;")
        layout.addWidget(self.chk_start)

        self.chk_auto_update = QCheckBox("Automatically check for updates on startup")
        self.chk_auto_update.setChecked(True)
        self.chk_auto_update.setStyleSheet("color: #e2e8f0; font-size: 9.5pt;")
        layout.addWidget(self.chk_auto_update)

        layout.addSpacing(8)

        # Channel
        ch_lbl = QLabel("Update Channel:")
        ch_lbl.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        ch_lbl.setStyleSheet("color: #cbd5e1; border: none; background: transparent;")
        layout.addWidget(ch_lbl)

        self.combo_channel = QComboBox()
        self.combo_channel.addItems(["Release (Recommended)", "Preview"])
        self.combo_channel.setStyleSheet("padding: 6px; border: 1px solid #334155; border-radius: 5px; background-color: #111e38; color: #f8fafc;")
        layout.addWidget(self.combo_channel)

        layout.addStretch()
        return page

    def _create_progress_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(14)

        h = QLabel("Installing StatCraft")
        h.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        h.setStyleSheet("color: #f8fafc; border: none; background: transparent;")
        layout.addWidget(h)

        self.lbl_progress_status = QLabel("Initializing setup...")
        self.lbl_progress_status.setStyleSheet("color: #38bdf8; font-weight: 500; font-size: 10pt; border: none; background: transparent;")
        layout.addWidget(self.lbl_progress_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #334155; border-radius: 5px; text-align: center; height: 24px; background-color: #111e38; color: #ffffff; font-weight: bold; }
            QProgressBar::chunk { background-color: #0284c7; border-radius: 4px; }
        """)
        layout.addWidget(self.progress_bar)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background-color: #070d1e; border: 1px solid #1e293b; border-radius: 6px; font-family: Consolas, monospace; font-size: 8.5pt; color: #38bdf8;")
        layout.addWidget(self.log_box)

        return page

    def _create_finish_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(14)

        h = QLabel("StatCraft is Ready!")
        h.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        h.setStyleSheet("color: #4ade80; border: none; background: transparent;")
        layout.addWidget(h)

        desc = QLabel(
            "StatCraft has been successfully installed and configured on your computer.\n"
            "You can launch it anytime from your Desktop, Start Menu, or open .mpx files directly.\n\n"
            f"Installed Version: v{STATCRAFT_VERSION}\n"
            f"Location: {self.custom_target_dir}"
        )
        desc.setStyleSheet("color: #cbd5e1; font-size: 10pt; line-height: 1.6; border: none; background: transparent;")
        layout.addWidget(desc)

        layout.addSpacing(12)

        self.chk_launch = QCheckBox("Launch StatCraft now")
        self.chk_launch.setChecked(True)
        self.chk_launch.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.chk_launch.setStyleSheet("color: #f8fafc;")
        layout.addWidget(self.chk_launch)

        layout.addStretch()
        return page

    def _browse_dir(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select Installation Directory", self.txt_dir.text())
        if chosen:
            self.txt_dir.setText(chosen)
            self.custom_target_dir = Path(chosen)

    def _check_online_updates(self):
        info = check_for_updates()
        if info.get("error"):
            QMessageBox.warning(self, "Update Check", f"Could not check for updates:\n{info['error']}")
        elif info.get("update_available"):
            ans = QMessageBox.question(
                self,
                "Update Available",
                f"StatCraft v{info['remote_version']} is available!\n\nRelease notes:\n{info.get('notes', 'Bug fixes and improvements.')}\n\nWould you like to install now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ans == QMessageBox.StandardButton.Yes:
                self.stack.setCurrentIndex(2)
                self._update_step_styles(2)
                self._start_installation()
        else:
            QMessageBox.information(self, "Up to Date", f"You are on the latest version of StatCraft (v{STATCRAFT_VERSION}).")

    def _go_back(self):
        cur = self.stack.currentIndex()
        if cur > 0:
            self.stack.setCurrentIndex(cur - 1)
            self._update_step_styles(cur - 1)
            self.btn_back.setEnabled(cur - 1 > 0)
            if cur - 1 == 0:
                self.btn_next.setText("Next")
            elif cur - 1 == 1:
                self.btn_next.setText("Install")

    def _go_next(self):
        cur = self.stack.currentIndex()
        if cur == 0:
            self.stack.setCurrentIndex(1)
            self._update_step_styles(1)
            self.btn_back.setEnabled(True)
            self.btn_next.setText("Install")
        elif cur == 1:
            # Begin install
            self.custom_target_dir = Path(self.txt_dir.text().strip())
            self.stack.setCurrentIndex(2)
            self._update_step_styles(2)
            self.btn_back.setEnabled(False)
            self.btn_next.setEnabled(False)
            self.btn_cancel.setEnabled(False)
            self._start_installation()
        elif cur == 3:
            # Finish
            if self.chk_launch.isChecked() and self.installed_exe_path:
                try:
                    subprocess.Popen([str(self.installed_exe_path)])
                except Exception as exc:
                    print(f"Failed to launch: {exc}")
            self.close()

    def _start_installation(self):
        channel = "preview" if "Preview" in self.combo_channel.currentText() else "release"
        self.worker = InstallWorker(
            target_dir=self.custom_target_dir,
            desktop_shortcut=self.chk_desktop.isChecked(),
            start_shortcut=self.chk_start.isChecked(),
            channel=channel
        )
        self.worker.progress_changed.connect(self._on_install_progress)
        self.worker.finished.connect(self._on_install_finished)
        self.worker.start()

    def _on_install_progress(self, percent: int, msg: str):
        self.progress_bar.setValue(percent)
        self.lbl_progress_status.setText(msg)
        self.log_box.append(f"[{percent}%] {msg}")

    def _on_install_finished(self, success: bool, info: str):
        self.btn_cancel.setEnabled(True)
        if success:
            self.installed_exe_path = Path(info)
            self.stack.setCurrentIndex(3)
            self._update_step_styles(3)
            self.btn_next.setEnabled(True)
            self.btn_next.setText("Finish")
            self.btn_cancel.setVisible(False)
        else:
            QMessageBox.critical(self, "Installation Failed", f"An error occurred during installation:\n{info}")
            self.btn_back.setEnabled(True)
            self.btn_next.setEnabled(True)
            self.btn_next.setText("Retry")


class UninstallerWindow(QMainWindow):
    """Dedicated Windows Add/Remove uninstallation wizard."""

    def __init__(self, target_dir: Path | None = None):
        super().__init__()
        self.setWindowTitle("StatCraft Uninstaller")
        self.setFixedSize(560, 380)
        self.target_dir = target_dir or get_default_install_dir()

        icon = get_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        main_widget = QWidget()
        main_widget.setStyleSheet("background-color: #0b1329; color: #f8fafc;")
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(76)
        header.setStyleSheet("background-color: #081124; border-bottom: 2px solid #ef4444;")
        head_layout = QHBoxLayout(header)
        head_layout.setContentsMargins(20, 10, 20, 10)

        title = QLabel("Uninstall StatCraft")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; border: none; background: transparent;")
        head_layout.addWidget(title)
        head_layout.addStretch()

        ver_lbl = QLabel(f"Version {STATCRAFT_VERSION}")
        ver_lbl.setStyleSheet("color: #94a3b8; font-size: 9pt; border: none; background: transparent;")
        head_layout.addWidget(ver_lbl)
        main_layout.addWidget(header)

        # Body
        body = QWidget()
        body.setStyleSheet("background-color: #0b1329; color: #f8fafc;")
        b_layout = QVBoxLayout(body)
        b_layout.setContentsMargins(24, 20, 24, 20)
        b_layout.setSpacing(14)

        self.lbl_prompt = QLabel(
            "Are you sure you want to uninstall StatCraft from your computer?\n\n"
            "This will remove:\n"
            f"• Application files from {self.target_dir}\n"
            "• Desktop and Start Menu shortcuts\n"
            "• Windows Add/Remove Programs registry registration"
        )
        self.lbl_prompt.setStyleSheet("color: #cbd5e1; font-size: 9.5pt; line-height: 1.5; border: none; background: transparent;")
        b_layout.addWidget(self.lbl_prompt)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #334155; border-radius: 4px; text-align: center; height: 20px; background-color: #111e38; color: #ffffff; }
            QProgressBar::chunk { background-color: #ef4444; border-radius: 3px; }
        """)
        b_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #4ade80; font-weight: 500; font-size: 9.5pt; border: none; background: transparent;")
        b_layout.addWidget(self.lbl_status)

        b_layout.addStretch()
        main_layout.addWidget(body)

        # Footer
        footer = QFrame()
        footer.setFixedHeight(56)
        footer.setStyleSheet("background-color: #081124; border-top: 1px solid #1e293b;")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(20, 10, 20, 10)

        f_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("""
            QPushButton { padding: 6px 18px; border: 1px solid #334155; border-radius: 5px; background-color: #1e293b; color: #f1f5f9; }
            QPushButton:hover { background-color: #334155; color: #ffffff; }
        """)
        self.btn_cancel.clicked.connect(self.close)
        f_layout.addWidget(self.btn_cancel)

        self.btn_uninstall = QPushButton("Uninstall")
        self.btn_uninstall.setStyleSheet("""
            QPushButton { background-color: #dc2626; color: #ffffff; font-weight: bold; padding: 6px 22px; border-radius: 5px; border: none; }
            QPushButton:hover { background-color: #b91c1c; }
        """)
        self.btn_uninstall.clicked.connect(self._run_uninstall)
        f_layout.addWidget(self.btn_uninstall)

        main_layout.addWidget(footer)

    def _run_uninstall(self):
        self.btn_uninstall.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(20)
        self.lbl_status.setText("Removing shortcuts and registry entries...")
        QApplication.processEvents()

        time.sleep(0.3)
        remove_shortcuts()
        unregister_windows_uninstaller()
        self.progress_bar.setValue(60)
        self.lbl_status.setText("Cleaning up installed files...")
        QApplication.processEvents()

        time.sleep(0.3)
        perform_uninstall(self.target_dir)
        self.progress_bar.setValue(100)
        self.lbl_status.setText("StatCraft was successfully removed from your computer.")
        self.btn_uninstall.setVisible(False)
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setText("Close")


def perform_silent_install(target_dir: Path | None = None, desktop: bool = True, start_menu: bool = True) -> int:
    """Run non-interactive headless installation."""
    target = target_dir or get_default_install_dir()
    print(f"Performing silent StatCraft v{STATCRAFT_VERSION} installation into {target}...")
    target.mkdir(parents=True, exist_ok=True)
    src_exe = find_source_binary()
    target_exe = target / "StatCraft.exe"
    if src_exe and src_exe.exists():
        shutil.copy2(src_exe, target_exe)
    else:
        print("Error: Source StatCraft.exe binary not found for silent install.")
        return 1

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
    setup_shortcuts(target_exe, desktop=desktop, start_menu=start_menu, icon_path=target / 'StatCraft.ico')
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
        app.setApplicationName("StatCraft Uninstaller")
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
