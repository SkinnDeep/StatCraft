"""StatCraft Setup & Auto-Updater Wizard.

Production installer and update manager for StatCraft statistical software.
Mirrors modern Adobe / StatCraft installation wizards with automatic
update checks, silent installs, shortcut creation, and upgrade migration.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Add project root and build-deps to sys.path
_root = Path(__file__).resolve().parent
_deps = _root.parent / "statcraft-build-deps"
if _deps.exists() and str(_deps) not in sys.path:
    sys.path.insert(0, str(_deps))
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon, QPalette, QColor
from PySide6.QtWidgets import (
    QApplication, QDialog, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QCheckBox, QProgressBar,
    QStackedWidget, QFrame, QMessageBox, QComboBox, QTextEdit
)

from statcraft.updater import (
    STATCRAFT_VERSION, DEFAULT_GITHUB_REPO, check_for_updates,
    compare_versions, get_default_install_dir, read_install_metadata,
    write_install_metadata, setup_shortcuts, download_file
)


def find_source_binary() -> Path | None:
    """Find the source StatCraft.exe binary bundled or adjacent to the setup executable."""
    # Check if bundled inside PyInstaller single-file package
    if hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "StatCraft.exe"
        if bundled.exists():
            return bundled

    # Check directory containing the installer executable
    current_exe_dir = Path(sys.executable).resolve().parent
    sibling = current_exe_dir / "StatCraft.exe"
    if sibling.exists():
        return sibling

    # Check repository outputs folder
    repo_outputs = _root.parent.parent / "outputs" / "StatCraft.exe"
    if repo_outputs.exists():
        return repo_outputs

    # Check work/statcraft-modern-next/StatCraft.exe
    work_out = _root.parent / "statcraft-modern-next" / "StatCraft.exe"
    if work_out.exists():
        return work_out

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
            src_exe = find_source_binary()

            target_exe = self.target_dir / "StatCraft.exe"

            if src_exe and src_exe.exists():
                self.progress_changed.emit(45, f"Copying StatCraft binary ({src_exe.stat().st_size // (1024*1024)} MB)...")
                # If target is running or exists, try clean replace
                if target_exe.exists():
                    try:
                        target_exe.unlink()
                    except Exception:
                        pass
                shutil.copy2(src_exe, target_exe)
            else:
                self.progress_changed.emit(40, "Downloading StatCraft from release feed...")
                info = check_for_updates()
                dl_url = info.get("download_url")
                if not dl_url:
                    self.finished.emit(False, "Could not find local or remote StatCraft binary to install.")
                    return
                download_file(dl_url, target_exe)

            self.progress_changed.emit(70, "Writing installation and version metadata...")
            write_install_metadata(
                self.target_dir,
                version=STATCRAFT_VERSION,
                channel=self.channel,
                installed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )

            # Copy icon if available
            icon_file = None
            if hasattr(sys, "_MEIPASS"):
                bundled_ico = Path(sys._MEIPASS) / "StatCraft.ico"
                if bundled_ico.exists():
                    dest_ico = self.target_dir / "StatCraft.ico"
                    shutil.copy2(bundled_ico, dest_ico)
                    icon_file = dest_ico
            if not icon_file:
                repo_ico = _root / "StatCraft.ico"
                if repo_ico.exists():
                    dest_ico = self.target_dir / "StatCraft.ico"
                    try:
                        shutil.copy2(repo_ico, dest_ico)
                        icon_file = dest_ico
                    except Exception:
                        pass

            self.progress_changed.emit(85, "Registering Windows shortcuts...")
            setup_shortcuts(
                target_exe,
                desktop=self.desktop_shortcut,
                start_menu=self.start_shortcut,
                icon_path=icon_file
            )

            self.progress_changed.emit(100, "Installation completed successfully.")
            time.sleep(0.2)
            self.finished.emit(True, str(target_exe))
        except Exception as exc:
            self.finished.emit(False, str(exc))


class InstallerWindow(QMainWindow):
    """Modern Adobe/Standard statistical setup wizard window."""

    def __init__(self, target_dir: Path | None = None, check_updates_mode: bool = False):
        super().__init__()
        self.setWindowTitle("StatCraft Setup Wizard")
        self.setFixedSize(680, 520)
        self.installed_exe_path = None
        self.custom_target_dir = target_dir or get_default_install_dir()

        # Main widget & layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header Banner
        header = QFrame()
        header.setFixedHeight(84)
        header.setStyleSheet("background-color: #0e2238; border-bottom: 3px solid #c5a059;")
        head_layout = QHBoxLayout(header)
        head_layout.setContentsMargins(24, 12, 24, 12)

        head_text = QVBoxLayout()
        title = QLabel("StatCraft Setup Wizard")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")
        subtitle = QLabel("Statistical Software & Quality Tools • Version " + STATCRAFT_VERSION)
        subtitle.setStyleSheet("color: #c5a059; font-size: 10pt; font-weight: 500;")
        head_text.addWidget(title)
        head_text.addWidget(subtitle)
        head_layout.addLayout(head_text)
        head_layout.addStretch()

        badge = QLabel("PRODUCTION READY")
        badge.setStyleSheet("color: #107c10; background: #e2f6ea; border: 1px solid #107c10; border-radius: 4px; padding: 4px 8px; font-weight: bold; font-size: 8pt;")
        head_layout.addWidget(badge)

        main_layout.addWidget(header)

        # 2. Content Area: Sidebar + Stacked Pages
        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(16, 16, 16, 16)
        body_layout.setSpacing(16)

        # Sidebar navigation steps
        sidebar = QFrame()
        sidebar.setFixedWidth(160)
        sidebar.setStyleSheet("background: #f3f4f6; border-radius: 6px; padding: 8px;")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setSpacing(10)
        side_layout.setContentsMargins(12, 12, 12, 12)

        nav_title = QLabel("STEPS")
        nav_title.setStyleSheet("font-size: 8pt; font-weight: bold; color: #6e7781;")
        side_layout.addWidget(nav_title)

        self.step_labels = [
            QLabel("1. Welcome"),
            QLabel("2. Configuration"),
            QLabel("3. Installation"),
            QLabel("4. Finish")
        ]
        for idx, lbl in enumerate(self.step_labels):
            lbl.setFont(QFont("Segoe UI", 9))
            lbl.setStyleSheet("color: #57606a; padding: 4px 0px;")
            side_layout.addWidget(lbl)
        side_layout.addStretch()
        body_layout.addWidget(sidebar)

        # Stacked Pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self._create_welcome_page())
        self.stack.addWidget(self._create_options_page())
        self.stack.addWidget(self._create_progress_page())
        self.stack.addWidget(self._create_finish_page())
        body_layout.addWidget(self.stack)

        main_layout.addWidget(body_widget)

        # 3. Bottom Navigation Bar
        bottom_bar = QFrame()
        bottom_bar.setFixedHeight(56)
        bottom_bar.setStyleSheet("background: #ffffff; border-top: 1px solid #d0d7de;")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(20, 10, 20, 10)

        self.btn_check_online = QPushButton("Check Online for Updates…")
        self.btn_check_online.setStyleSheet("padding: 6px 12px; border: 1px solid #d0d7de; border-radius: 4px; background: #f6f8fa;")
        self.btn_check_online.clicked.connect(self._check_online_updates)
        bottom_layout.addWidget(self.btn_check_online)

        bottom_layout.addStretch()

        self.btn_back = QPushButton("Back")
        self.btn_back.setEnabled(False)
        self.btn_back.setStyleSheet("padding: 6px 16px; border: 1px solid #d0d7de; border-radius: 4px;")
        self.btn_back.clicked.connect(self._go_back)
        bottom_layout.addWidget(self.btn_back)

        self.btn_next = QPushButton("Next")
        self.btn_next.setStyleSheet("background-color: #0078d4; color: white; font-weight: bold; padding: 6px 20px; border-radius: 4px;")
        self.btn_next.clicked.connect(self._go_next)
        bottom_layout.addWidget(self.btn_next)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("padding: 6px 16px; border: 1px solid #d0d7de; border-radius: 4px;")
        self.btn_cancel.clicked.connect(self.close)
        bottom_layout.addWidget(self.btn_cancel)

        main_layout.addWidget(bottom_bar)

        self._update_step_styles(0)

        if check_updates_mode:
            self._check_online_updates()

    def _update_step_styles(self, current_idx: int):
        for idx, lbl in enumerate(self.step_labels):
            if idx == current_idx:
                lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                lbl.setStyleSheet("color: #0078d4; font-weight: bold; padding: 4px 0px;")
            elif idx < current_idx:
                lbl.setStyleSheet("color: #107c10; padding: 4px 0px;")
            else:
                lbl.setStyleSheet("color: #8c959f; padding: 4px 0px;")

    def _create_welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        h = QLabel("Install or Upgrade StatCraft")
        h.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(h)

        desc = QLabel(
            "This setup wizard guides you through installing or updating StatCraft.\n\n"
            "• Full desktop worksheet and statistical workflows\n"
            "• Interactive 3D Surface plots with rotatable ViewCube and lighting\n"
            "• Comprehensive Basic Statistics, DOE, MSA, Quality & Control Charts\n"
            "• Automatic updates and GitHub release integration"
        )
        desc.setStyleSheet("color: #24292f; line-height: 1.5; font-size: 9.5pt;")
        layout.addWidget(desc)

        # Detect existing install status
        box = QFrame()
        box.setStyleSheet("background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 12px;")
        b_layout = QVBoxLayout(box)

        meta = read_install_metadata(self.custom_target_dir)
        cur_v = meta.get("version")
        target_exe = self.custom_target_dir / "StatCraft.exe"

        status_title = QLabel("System Status:")
        status_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        b_layout.addWidget(status_title)

        if target_exe.exists():
            self.lbl_detect = QLabel(f"StatCraft detected at {self.custom_target_dir} (Version: v{cur_v}).\nReady to upgrade to version {STATCRAFT_VERSION}.")
            self.lbl_detect.setStyleSheet("color: #0078d4; font-weight: 500;")
        else:
            self.lbl_detect = QLabel(f"StatCraft is not yet installed.\nReady for fresh installation of version {STATCRAFT_VERSION}.")
            self.lbl_detect.setStyleSheet("color: #107c10; font-weight: 500;")
        b_layout.addWidget(self.lbl_detect)

        layout.addWidget(box)
        layout.addStretch()
        return page

    def _create_options_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        h = QLabel("Installation Options")
        h.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(h)

        # Destination Folder
        dest_lbl = QLabel("Destination Directory:")
        dest_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        layout.addWidget(dest_lbl)

        d_layout = QHBoxLayout()
        self.txt_dir = QLineEdit(str(self.custom_target_dir))
        self.txt_dir.setStyleSheet("padding: 6px; border: 1px solid #d0d7de; border-radius: 4px;")
        d_layout.addWidget(self.txt_dir)

        btn_browse = QPushButton("Browse…")
        btn_browse.setStyleSheet("padding: 6px 12px; border: 1px solid #d0d7de; border-radius: 4px;")
        btn_browse.clicked.connect(self._browse_dir)
        d_layout.addWidget(btn_browse)
        layout.addLayout(d_layout)

        layout.addSpacing(8)

        # Shortcuts
        sc_lbl = QLabel("Shortcuts & Integration:")
        sc_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        layout.addWidget(sc_lbl)

        self.chk_desktop = QCheckBox("Create Desktop Shortcut")
        self.chk_desktop.setChecked(True)
        layout.addWidget(self.chk_desktop)

        self.chk_start = QCheckBox("Create Start Menu Shortcut")
        self.chk_start.setChecked(True)
        layout.addWidget(self.chk_start)

        self.chk_auto_update = QCheckBox("Automatically check for updates on startup")
        self.chk_auto_update.setChecked(True)
        layout.addWidget(self.chk_auto_update)

        layout.addSpacing(8)

        # Channel
        ch_lbl = QLabel("Update Channel:")
        ch_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        layout.addWidget(ch_lbl)

        self.combo_channel = QComboBox()
        self.combo_channel.addItems(["Release (Recommended)", "Preview"])
        self.combo_channel.setStyleSheet("padding: 4px; border: 1px solid #d0d7de; border-radius: 4px;")
        layout.addWidget(self.combo_channel)

        layout.addStretch()
        return page

    def _create_progress_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        h = QLabel("Installing StatCraft")
        h.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(h)

        self.lbl_progress_status = QLabel("Initializing setup...")
        self.lbl_progress_status.setStyleSheet("font-weight: 500;")
        layout.addWidget(self.lbl_progress_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #d0d7de; border-radius: 4px; text-align: center; height: 22px; }
            QProgressBar::chunk { background-color: #0078d4; border-radius: 3px; }
        """)
        layout.addWidget(self.progress_bar)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 4px; font-family: Consolas, monospace; font-size: 8.5pt;")
        layout.addWidget(self.log_box)

        return page

    def _create_finish_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(14)

        h = QLabel("StatCraft is Ready!")
        h.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        h.setStyleSheet("color: #107c10;")
        layout.addWidget(h)

        desc = QLabel(
            "StatCraft has been successfully installed and configured on your computer.\n"
            "You can launch it anytime from your Desktop or Start Menu.\n\n"
            f"Installed Version: v{STATCRAFT_VERSION}\n"
            f"Location: {self.custom_target_dir}"
        )
        desc.setStyleSheet("font-size: 10pt; line-height: 1.5;")
        layout.addWidget(desc)

        layout.addSpacing(12)

        self.chk_launch = QCheckBox("Launch StatCraft now")
        self.chk_launch.setChecked(True)
        self.chk_launch.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
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
            QMessageBox.warning(self, "Update Check", f"Could not check for online updates:\n{info['error']}")
        elif info.get("update_available"):
            QMessageBox.information(
                self,
                "New Version Available",
                f"A new version of StatCraft is available online!\n\n"
                f"Version: v{info['latest_version']}\n"
                f"Release: {info['release_name']}\n\n"
                f"The installer can download this update during setup."
            )
        else:
            QMessageBox.information(
                self,
                "Up to Date",
                f"You have the latest version (v{STATCRAFT_VERSION}). No updates required."
            )

    def _go_back(self):
        cur = self.stack.currentIndex()
        if cur > 0:
            self.stack.setCurrentIndex(cur - 1)
            self._update_step_styles(cur - 1)
            self.btn_back.setEnabled(cur - 1 > 0)
            self.btn_next.setText("Next")

    def _go_next(self):
        cur = self.stack.currentIndex()
        if cur == 0:
            # Move from Welcome to Options
            self.stack.setCurrentIndex(1)
            self._update_step_styles(1)
            self.btn_back.setEnabled(True)
            self.btn_next.setText("Install")
        elif cur == 1:
            # Start Installation
            target = Path(self.txt_dir.text().strip())
            self.custom_target_dir = target
            self.stack.setCurrentIndex(2)
            self._update_step_styles(2)
            self.btn_back.setEnabled(False)
            self.btn_next.setEnabled(False)
            self.btn_check_online.setVisible(False)
            self.btn_cancel.setEnabled(False)

            channel = "preview" if "Preview" in self.combo_channel.currentText() else "release"
            self.worker = InstallWorker(
                target_dir=target,
                desktop_shortcut=self.chk_desktop.isChecked(),
                start_shortcut=self.chk_start.isChecked(),
                channel=channel
            )
            self.worker.progress_changed.connect(self._on_install_progress)
            self.worker.finished.connect(self._on_install_finished)
            self.worker.start()
        elif cur == 3:
            # Finish
            if self.chk_launch.isChecked() and self.installed_exe_path:
                try:
                    subprocess.Popen([str(self.installed_exe_path)])
                except Exception as exc:
                    print(f"Failed to launch: {exc}")
            self.close()

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
    setup_shortcuts(target_exe, desktop=desktop, start_menu=start_menu)
    print("Silent installation completed successfully.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="StatCraft Setup & Auto-Updater")
    parser.add_argument("--silent", "-s", action="store_true", help="Run silent installation without GUI")
    parser.add_argument("--check-updates", action="store_true", help="Launch in update checker mode")
    parser.add_argument("--dir", type=str, default=None, help="Custom installation directory")
    args = parser.parse_args()

    target = Path(args.dir) if args.dir else None

    if args.silent:
        return perform_silent_install(target)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("StatCraft Setup")
    app.setOrganizationName("StatCraft")

    window = InstallerWindow(target_dir=target, check_updates_mode=args.check_updates)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
