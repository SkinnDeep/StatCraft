"""In-app Check for Updates dialog for StatCraft."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QMessageBox, QFrame, QWidget, QApplication
)

from .updater import (
    STATCRAFT_VERSION, check_for_updates, download_file, get_default_install_dir,
    read_install_metadata, DEFAULT_GITHUB_REPO
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


class UpdateDownloadWorker(QThread):
    progress = Signal(int, int)  # downloaded, total
    finished = Signal(str)       # downloaded local path
    error = Signal(str)          # error message

    def __init__(self, download_url: str, dest_path: Path):
        super().__init__()
        self.download_url = download_url
        self.dest_path = dest_path

    def run(self):
        try:
            def on_progress(downloaded, total):
                self.progress.emit(downloaded, total)

            download_file(self.download_url, self.dest_path, progress_callback=on_progress)
            self.finished.emit(str(self.dest_path))
        except Exception as exc:
            self.error.emit(str(exc))


class CheckForUpdatesDialog(QDialog):
    """Modern executive Check for Updates dialog for StatCraft.
    
    Handles checking, in-app downloading with real-time byte progress,
    and launching the installer completely inside StatCraft.
    """

    def __init__(
        self,
        parent=None,
        manifest_url: str | None = None,
        auto_download: bool = False,
        initial_info: dict | None = None
    ):
        super().__init__(parent)
        self.setWindowTitle("StatCraft - Software Updates")
        self.setMinimumSize(540, 420)
        self.resize(540, 420)
        self.setSizeGripEnabled(True)
        self.manifest_url = manifest_url
        self.update_info = initial_info
        self.auto_download = auto_download
        self.download_worker: UpdateDownloadWorker | None = None

        # Dark Slate modern styling matching setup wizard
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            QLabel {
                color: #f8fafc;
            }
            QProgressBar {
                border: 1px solid #334155;
                border-radius: 4px;
                background-color: #1e293b;
                height: 8px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 3px;
            }
            QTextEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #e2e8f0;
                padding: 10px;
                font-size: 9pt;
            }
            QPushButton#btnAction {
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 600;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 9pt;
            }
            QPushButton#btnAction:hover {
                background-color: #1d4ed8;
            }
            QPushButton#btnClose {
                background-color: #1e293b;
                color: #e2e8f0;
                font-weight: 500;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 9pt;
            }
            QPushButton#btnClose:hover {
                background-color: #334155;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        # Header Card
        header_card = QFrame()
        header_card.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 8px;")
        h_layout = QVBoxLayout(header_card)
        h_layout.setContentsMargins(18, 14, 18, 14)
        h_layout.setSpacing(4)

        title_lbl = QLabel("StatCraft Software Updates")
        title_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #ffffff;")
        h_layout.addWidget(title_lbl)

        installed = read_install_metadata()
        cur_v = installed.get("version", STATCRAFT_VERSION)
        ver_lbl = QLabel(f"Current Installed Version: v{cur_v}")
        ver_lbl.setStyleSheet("color: #94a3b8; font-size: 9pt;")
        h_layout.addWidget(ver_lbl)
        layout.addWidget(header_card)

        # Status text
        self.status_lbl = QLabel("Checking for available updates...")
        self.status_lbl.setFont(QFont("Segoe UI", 9.5))
        self.status_lbl.setStyleSheet("color: #94a3b8;")
        layout.addWidget(self.status_lbl)

        # Progress bar (indeterminate while checking, determined 0-100 during download)
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 0)
        self.prog_bar.setFixedHeight(8)
        layout.addWidget(self.prog_bar)

        # Release Notes / Details Box
        self.notes_lbl = QLabel("Release Notes:")
        self.notes_lbl.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        self.notes_lbl.setVisible(False)
        layout.addWidget(self.notes_lbl)

        self.notes_box = QTextEdit()
        self.notes_box.setReadOnly(True)
        self.notes_box.setVisible(False)
        layout.addWidget(self.notes_box, 1)

        layout.addStretch(1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.btn_action = QPushButton("Download & Install Update")
        self.btn_action.setObjectName("btnAction")
        self.btn_action.setEnabled(False)
        self.btn_action.setVisible(False)
        self.btn_action.clicked.connect(self._on_action_clicked)
        btn_layout.addWidget(self.btn_action)

        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("btnClose")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        if initial_info:
            self._on_check_finished(initial_info)
            if self.auto_download and initial_info.get("update_available"):
                QTimer.singleShot(150, self._on_action_clicked)
        else:
            # Start background update check
            self.worker = UpdateCheckWorker(cur_v, manifest_url)
            self.worker.finished.connect(self._on_check_finished)
            self.worker.start()

    def _on_check_finished(self, info: dict):
        self.prog_bar.setVisible(False)
        self.update_info = info

        if info.get("error"):
            self.status_lbl.setText(f"Unable to check for updates: {info['error']}")
            self.status_lbl.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 9.5pt;")
            return

        if info.get("update_available"):
            latest = info.get("latest_version", "")
            name = info.get("release_name") or f"StatCraft v{latest}"
            self.status_lbl.setText(f"✓ A new version is available: v{latest} ({name})")
            self.status_lbl.setStyleSheet("color: #10b981; font-weight: bold; font-size: 10pt;")
            self.notes_lbl.setVisible(True)
            self.notes_box.setVisible(True)
            notes = info.get("release_notes") or "This update includes performance optimizations, statistical calculation improvements, and bug fixes."
            self.notes_box.setPlainText(notes)
            self.btn_action.setText("Download & Install Update")
            self.btn_action.setEnabled(True)
            self.btn_action.setVisible(True)
        else:
            cur = info.get("current_version", STATCRAFT_VERSION)
            self.status_lbl.setText(f"✓ StatCraft is up to date (v{cur}). No updates available.")
            self.status_lbl.setStyleSheet("color: #10b981; font-weight: bold; font-size: 10pt;")

    def _on_action_clicked(self):
        if not self.update_info:
            return

        download_url = (
            self.update_info.get("setup_download_url")
            or self.update_info.get("download_url")
            or self.update_info.get("app_download_url")
        )
        if not download_url:
            self.status_lbl.setText("No download package URL found in release.")
            return

        latest_v = self.update_info.get("latest_version", "latest")
        temp_dir = Path(os.environ.get("TEMP", os.environ.get("LOCALAPPDATA", str(Path.home())))) / "StatCraftUpdates"
        temp_dir.mkdir(parents=True, exist_ok=True)
        dest_path = temp_dir / f"StatCraft-Setup-v{latest_v}.exe"

        self.btn_action.setEnabled(False)
        self.btn_action.setText("Downloading...")
        self.prog_bar.setVisible(True)
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.status_lbl.setText(f"Connecting to download update (v{latest_v})...")
        self.status_lbl.setStyleSheet("color: #38bdf8; font-size: 9.5pt;")

        self.download_worker = UpdateDownloadWorker(download_url, dest_path)
        self.download_worker.progress.connect(self._on_download_progress)
        self.download_worker.finished.connect(self._on_download_finished)
        self.download_worker.error.connect(self._on_download_error)
        self.download_worker.start()

    def _on_download_progress(self, downloaded: int, total: int):
        if total > 0:
            pct = max(0, min(100, int((downloaded / total) * 100)))
            self.prog_bar.setValue(pct)
            mb_down = downloaded / (1024 * 1024)
            mb_tot = total / (1024 * 1024)
            self.status_lbl.setText(f"Downloading update: {mb_down:.1f} MB / {mb_tot:.1f} MB ({pct}%)...")
        else:
            mb_down = downloaded / (1024 * 1024)
            self.status_lbl.setText(f"Downloading update: {mb_down:.1f} MB...")

    def _on_download_finished(self, dest_path_str: str):
        self.prog_bar.setValue(100)
        self.status_lbl.setText("✓ Download complete! Ready to install.")
        self.status_lbl.setStyleSheet("color: #10b981; font-weight: bold; font-size: 10pt;")
        self.btn_action.setText("Install & Restart")
        self.btn_action.setEnabled(True)
        try:
            self.btn_action.clicked.disconnect()
        except Exception:
            pass
        self.btn_action.clicked.connect(lambda: self._launch_installer(dest_path_str))

        reply = QMessageBox.question(
            self,
            "Install StatCraft Update",
            f"The update has been downloaded successfully.\n\n"
            f"Would you like to install it now? StatCraft will close so the update can be applied.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._launch_installer(dest_path_str)

    def _launch_installer(self, exe_path: str):
        try:
            subprocess.Popen([exe_path])
        except Exception as exc:
            QMessageBox.critical(self, "Installation Error", f"Failed to launch installer:\n{exc}")
            return

        self.accept()
        app = QApplication.instance()
        if app:
            for win in list(app.topLevelWidgets()):
                try:
                    win.close()
                except Exception:
                    pass
            app.quit()

    def _on_download_error(self, err_msg: str):
        self.prog_bar.setVisible(False)
        self.status_lbl.setText(f"Download failed: {err_msg}")
        self.status_lbl.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 9.5pt;")
        self.btn_action.setEnabled(True)
        self.btn_action.setText("Retry Download")
