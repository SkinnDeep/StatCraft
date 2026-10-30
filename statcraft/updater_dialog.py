"""In-app Check for Updates dialog for StatCraft."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QMessageBox, QFrame
)

from .updater import (
    STATCRAFT_VERSION, check_for_updates, get_default_install_dir, read_install_metadata
)


class UpdateCheckWorker(QThread):
    finished = Signal(dict)

    def __init__(self, current_ver: str, manifest_url: str | None = None):
        super().__init__()
        self.current_ver = current_ver
        self.manifest_url = manifest_url

    def run(self):
        info = check_for_updates(current_ver=self.current_ver, manifest_url=self.manifest_url)
        self.finished.emit(info)


class CheckForUpdatesDialog(QDialog):
    """StatCraft/Adobe-style Check for Updates dialog."""

    def __init__(self, parent=None, manifest_url: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("StatCraft - Check for Updates")
        self.setMinimumSize(520, 380)
        self.manifest_url = manifest_url
        self.update_info = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header Box
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #0e2238; border-radius: 6px; padding: 12px;")
        h_layout = QVBoxLayout(header_frame)
        title_lbl = QLabel("StatCraft Software Updates")
        title_font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        title_lbl.setFont(title_font)
        title_lbl.setStyleSheet("color: #ffffff;")
        h_layout.addWidget(title_lbl)

        installed = read_install_metadata()
        cur_v = installed.get("version", STATCRAFT_VERSION)
        ver_lbl = QLabel(f"Current Version: v{cur_v}")
        ver_lbl.setStyleSheet("color: #c5a059; font-size: 11pt;")
        h_layout.addWidget(ver_lbl)
        layout.addWidget(header_frame)

        # Status text
        self.status_lbl = QLabel("Checking for available updates...")
        self.status_lbl.setStyleSheet("font-size: 10pt; font-weight: 500;")
        layout.addWidget(self.status_lbl)

        # Progress bar (indeterminate while checking)
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 0)
        layout.addWidget(self.prog_bar)

        # Release Notes / Details Box
        self.notes_lbl = QLabel("Release Notes:")
        self.notes_lbl.setVisible(False)
        layout.addWidget(self.notes_lbl)

        self.notes_box = QTextEdit()
        self.notes_box.setReadOnly(True)
        self.notes_box.setVisible(False)
        self.notes_box.setStyleSheet("background: #fdfdfd; border: 1px solid #d0d7de; border-radius: 4px; padding: 6px;")
        layout.addWidget(self.notes_box)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_action = QPushButton("Install Update")
        self.btn_action.setEnabled(False)
        self.btn_action.setVisible(False)
        self.btn_action.setStyleSheet("background-color: #0078d4; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        self.btn_action.clicked.connect(self._on_action_clicked)
        btn_layout.addWidget(self.btn_action)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        # Start background update check
        self.worker = UpdateCheckWorker(cur_v, manifest_url)
        self.worker.finished.connect(self._on_check_finished)
        self.worker.start()

    def _on_check_finished(self, info: dict):
        self.update_info = info
        self.prog_bar.setVisible(False)

        if info.get("error"):
            self.status_lbl.setText(f"Unable to check for updates: {info['error']}")
            self.status_lbl.setStyleSheet("color: #d83b01; font-weight: bold;")
            return

        if info.get("update_available"):
            self.status_lbl.setText(f"A new version is available: v{info['latest_version']} ({info['release_name']})")
            self.status_lbl.setStyleSheet("color: #107c10; font-weight: bold;")
            self.notes_lbl.setVisible(True)
            self.notes_box.setVisible(True)
            self.notes_box.setPlainText(info.get("release_notes") or "Performance enhancements and bug fixes.")
            self.btn_action.setText("Download & Install Update")
            self.btn_action.setEnabled(True)
            self.btn_action.setVisible(True)
        else:
            self.status_lbl.setText(f"StatCraft is up to date (v{info['current_version']}). No updates available.")
            self.status_lbl.setStyleSheet("color: #107c10; font-weight: bold;")

    def _on_action_clicked(self):
        if not self.update_info:
            return
        download_url = self.update_info.get("download_url")
        if not download_url:
            QMessageBox.information(
                self,
                "Update Information",
                f"Please visit the official release page:\nhttps://github.com/{DEFAULT_GITHUB_REPO}/releases"
            )
            return

        # Check if adjacent StatCraft-Setup.exe exists to run
        setup_exe = Path(sys.executable).parent / "StatCraft-Setup.exe"
        if not setup_exe.exists():
            setup_exe = Path(__file__).resolve().parent.parent / "outputs" / "StatCraft-Setup.exe"

        if setup_exe.exists():
            subprocess.Popen([str(setup_exe)])
            self.accept()
        else:
            import webbrowser
            webbrowser.open(download_url)
            self.accept()
