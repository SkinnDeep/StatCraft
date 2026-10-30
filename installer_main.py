"""StatCraft Setup & Auto-Updater Wizard.

Production installer, uninstaller, and update manager for StatCraft statistical software.
Built following modern design system specifications with clean typography, elevated cards,
real-time byte progress streaming, and native Windows integration.
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
    QStackedWidget, QFrame, QMessageBox, QComboBox
)

from statcraft.updater import (
    STATCRAFT_VERSION, DEFAULT_GITHUB_REPO, check_for_updates,
    compare_versions, get_default_install_dir, read_install_metadata,
    write_install_metadata, setup_shortcuts, download_file,
    register_windows_uninstaller, unregister_windows_uninstaller,
    remove_shortcuts, perform_uninstall, _run_hidden_subprocess
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


class InstallWorker(QThread):
    progress_changed = Signal(int, str, str)  # percent, main_status, detail_status
    finished = Signal(bool, str)

    def __init__(self, target_dir: Path, desktop_shortcut: bool, start_shortcut: bool, channel: str):
        super().__init__()
        self.target_dir = target_dir
        self.desktop_shortcut = desktop_shortcut
        self.start_shortcut = start_shortcut
        self.channel = channel

    def run(self):
        try:
            self.progress_changed.emit(5, "Preparing destination directory...", str(self.target_dir))
            
            # Terminate running instance if any to release Windows file locks silently
            if sys.platform == "win32":
                try:
                    _run_hidden_subprocess(["taskkill", "/F", "/IM", "StatCraft.exe"], capture_output=True)
                except Exception:
                    pass

            self.target_dir.mkdir(parents=True, exist_ok=True)
            time.sleep(0.15)

            self.progress_changed.emit(15, "Checking for local packages...", "Inspecting installer package directory")
            src_exe = find_source_binary()
            target_exe = self.target_dir / "StatCraft.exe"

            if src_exe and src_exe.exists() and src_exe != target_exe:
                size_mb = max(1, src_exe.stat().st_size // (1024 * 1024))
                self.progress_changed.emit(40, f"Copying StatCraft package ({size_mb} MB)...", str(src_exe.name))
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

            self.progress_changed.emit(82, "Writing installation metadata...", f"Version {STATCRAFT_VERSION}")
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

            self.progress_changed.emit(92, "Configuring shortcuts and Windows integration...", "Desktop and Start Menu")
            setup_shortcuts(
                target_exe,
                desktop=self.desktop_shortcut,
                start_menu=self.start_shortcut,
                icon_path=icon_file
            )

            # Register in Windows Add/Remove Programs
            register_windows_uninstaller(self.target_dir, STATCRAFT_VERSION, icon_path=icon_file)

            self.progress_changed.emit(100, "Installation complete!", "Ready to launch")
            time.sleep(0.3)
            self.finished.emit(True, str(target_exe))
        except Exception as exc:
            self.finished.emit(False, str(exc))


class InstallerWindow(QMainWindow):
    """Modern setup wizard designed with clean Google Stitch / Material Design 3 ergonomics."""

    def __init__(self, target_dir: Path | None = None, check_updates_mode: bool = False):
        super().__init__()
        self.setWindowTitle("StatCraft Setup")
        self.setFixedSize(700, 530)
        self.installed_exe_path = None
        self.custom_target_dir = target_dir or get_default_install_dir()

        # Set window icon
        icon = get_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        # Global stylesheet to prevent any child widget clipping or unwanted margin inheritance
        self.setStyleSheet("""
            QMainWindow { background-color: #0f172a; }
            QWidget#mainContainer { background-color: #0f172a; color: #f8fafc; }
            QLabel { background: transparent; color: #f8fafc; }
            QCheckBox {
                color: #e2e8f0;
                font-family: 'Segoe UI';
                font-size: 9.5pt;
                spacing: 10px;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #475569;
                border-radius: 4px;
                background-color: #0f172a;
            }
            QCheckBox::indicator:hover {
                border-color: #3b82f6;
            }
            QCheckBox::indicator:checked {
                background-color: #2563eb;
                border-color: #2563eb;
            }
        """)

        # Main widget & layout
        main_widget = QWidget()
        main_widget.setObjectName("mainContainer")
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header Bar
        header = QFrame()
        header.setFixedHeight(72)
        header.setStyleSheet("background-color: #0b1120; border-bottom: 1px solid #1e293b;")
        head_layout = QHBoxLayout(header)
        head_layout.setContentsMargins(24, 12, 24, 12)

        # App branding with icon
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(12)

        self.logo_label = QLabel()
        if not icon.isNull():
            self.logo_label.setPixmap(icon.pixmap(36, 36))
        brand_layout.addWidget(self.logo_label)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)
        title = QLabel("StatCraft Setup")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff; border: none; background: transparent;")
        
        subtitle = QLabel(f"Version {STATCRAFT_VERSION} • 64-bit Windows")
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet("color: #94a3b8; border: none; background: transparent;")
        
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        brand_layout.addLayout(title_layout)
        head_layout.addLayout(brand_layout)

        head_layout.addStretch()

        # Step indicator breadcrumb pills
        self.step_pills = []
        pills_layout = QHBoxLayout()
        pills_layout.setSpacing(6)
        
        step_names = ["Welcome", "Options", "Installing", "Complete"]
        for i, name in enumerate(step_names):
            pill = QLabel(f"{i+1}. {name}")
            pill.setFont(QFont("Segoe UI", 8.5, QFont.Weight.Medium))
            pill.setStyleSheet("""
                QLabel {
                    padding: 4px 10px;
                    border-radius: 12px;
                    background-color: transparent;
                    color: #64748b;
                }
            """)
            self.step_pills.append(pill)
            pills_layout.addWidget(pill)

        head_layout.addLayout(pills_layout)
        main_layout.addWidget(header)

        # 2. Main Content Stack
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: transparent;")
        self.stack.addWidget(self._create_welcome_page())
        self.stack.addWidget(self._create_options_page())
        self.stack.addWidget(self._create_progress_page())
        self.stack.addWidget(self._create_finish_page())
        main_layout.addWidget(self.stack)

        # 3. Modern Footer Bar
        footer = QFrame()
        footer.setFixedHeight(64)
        footer.setStyleSheet("background-color: #0b1120; border-top: 1px solid #1e293b;")
        foot_layout = QHBoxLayout(footer)
        foot_layout.setContentsMargins(24, 12, 24, 12)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                padding: 7px 18px;
                border: 1px solid #334155;
                border-radius: 6px;
                background-color: #1e293b;
                color: #e2e8f0;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """)
        self.btn_cancel.clicked.connect(self.close)
        foot_layout.addWidget(self.btn_cancel)

        foot_layout.addStretch()

        self.btn_back = QPushButton("Back")
        self.btn_back.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        self.btn_back.setEnabled(False)
        self.btn_back.setStyleSheet("""
            QPushButton {
                padding: 7px 20px;
                border: 1px solid #334155;
                border-radius: 6px;
                background-color: #1e293b;
                color: #e2e8f0;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
            QPushButton:disabled {
                color: #475569;
                background-color: #0f172a;
                border-color: #1e293b;
            }
        """)
        self.btn_back.clicked.connect(self._go_back)
        foot_layout.addWidget(self.btn_back)

        self.btn_next = QPushButton("Next")
        self.btn_next.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.btn_next.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                padding: 7px 24px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
        """)
        self.btn_next.clicked.connect(self._go_next)
        foot_layout.addWidget(self.btn_next)

        main_layout.addWidget(footer)

        self._update_step_styles(0)

    def _update_step_styles(self, current_idx: int):
        for idx, pill in enumerate(self.step_pills):
            if idx == current_idx:
                pill.setStyleSheet("""
                    QLabel {
                        padding: 4px 10px;
                        border-radius: 12px;
                        background-color: #1e293b;
                        color: #60a5fa;
                        font-weight: bold;
                        border: 1px solid #3b82f6;
                    }
                """)
            elif idx < current_idx:
                pill.setStyleSheet("""
                    QLabel {
                        padding: 4px 10px;
                        border-radius: 12px;
                        background-color: transparent;
                        color: #10b981;
                        font-weight: medium;
                    }
                """)
            else:
                pill.setStyleSheet("""
                    QLabel {
                        padding: 4px 10px;
                        border-radius: 12px;
                        background-color: transparent;
                        color: #64748b;
                    }
                """)

    def _create_welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 20, 36, 16)
        layout.setSpacing(14)

        # Title block
        h = QLabel("Welcome to StatCraft")
        h.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        h.setStyleSheet("color: #f8fafc;")
        layout.addWidget(h)

        sub = QLabel(
            "StatCraft is a modern desktop statistical analysis and quality engineering suite. "
            "This setup wizard will download and configure the complete application on your computer."
        )
        sub.setFont(QFont("Segoe UI", 9.5))
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #94a3b8; line-height: 1.4;")
        layout.addWidget(sub)

        # Feature highlights card
        feat_card = QFrame()
        feat_card.setObjectName("featCard")
        feat_card.setStyleSheet("QFrame#featCard { background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; }")
        f_layout = QVBoxLayout(feat_card)
        f_layout.setContentsMargins(18, 14, 18, 14)
        f_layout.setSpacing(10)

        features = [
            ("📊  Comprehensive Statistics", "Parametric tests, ANOVA, DOE, MSA, and Six Sigma control charts."),
            ("🧊  Interactive CAD 3D Viewport", "Rotatable response surface plots with live orientation ViewCube and lighting."),
            ("📁  Native File Compatibility", "Direct support for opening and saving standard MPX projects and worksheets.")
        ]

        for title_text, desc_text in features:
            row = QVBoxLayout()
            row.setSpacing(2)
            lbl_title = QLabel(title_text)
            lbl_title.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
            lbl_title.setStyleSheet("color: #f1f5f9;")
            
            lbl_desc = QLabel(desc_text)
            lbl_desc.setFont(QFont("Segoe UI", 8.5))
            lbl_desc.setStyleSheet("color: #94a3b8;")
            
            row.addWidget(lbl_title)
            row.addWidget(lbl_desc)
            f_layout.addLayout(row)

        layout.addWidget(feat_card)

        # Target installation summary card
        status_card = QFrame()
        status_card.setObjectName("statusCard")
        status_card.setStyleSheet("QFrame#statusCard { background-color: #111d32; border: 1px solid #1e3a5f; border-radius: 8px; }")
        s_layout = QHBoxLayout(status_card)
        s_layout.setContentsMargins(16, 10, 16, 10)
        
        info_icon = QLabel("ℹ️")
        info_icon.setStyleSheet("font-size: 11pt;")
        s_layout.addWidget(info_icon)

        meta = read_install_metadata(self.custom_target_dir)
        cur_v = meta.get("version")
        target_exe = self.custom_target_dir / "StatCraft.exe"

        if target_exe.exists() and cur_v:
            txt = f"Existing installation detected (v{cur_v}). Ready to upgrade to version {STATCRAFT_VERSION}."
        else:
            txt = f"Ready for clean installation of version {STATCRAFT_VERSION} into your user profile."

        self.lbl_detect = QLabel(txt)
        self.lbl_detect.setFont(QFont("Segoe UI", 9))
        self.lbl_detect.setStyleSheet("color: #60a5fa;")
        s_layout.addWidget(self.lbl_detect)
        s_layout.addStretch()

        layout.addWidget(status_card)
        layout.addStretch()
        return page

    def _create_options_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 20, 36, 16)
        layout.setSpacing(14)

        h = QLabel("Installation Configuration")
        h.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        h.setStyleSheet("color: #f8fafc;")
        layout.addWidget(h)

        sub = QLabel("Select your preferred installation directory and system integration options.")
        sub.setFont(QFont("Segoe UI", 9.5))
        sub.setStyleSheet("color: #94a3b8;")
        layout.addWidget(sub)

        # Directory card
        dir_card = QFrame()
        dir_card.setObjectName("dirCard")
        dir_card.setStyleSheet("QFrame#dirCard { background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; }")
        d_layout = QVBoxLayout(dir_card)
        d_layout.setContentsMargins(18, 14, 18, 14)
        d_layout.setSpacing(8)

        dest_lbl = QLabel("Install Directory:")
        dest_lbl.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        dest_lbl.setStyleSheet("color: #f1f5f9;")
        d_layout.addWidget(dest_lbl)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.txt_dir = QLineEdit(str(self.custom_target_dir))
        self.txt_dir.setFont(QFont("Segoe UI", 9))
        self.txt_dir.setStyleSheet("""
            QLineEdit {
                padding: 7px 10px;
                border: 1px solid #475569;
                border-radius: 6px;
                background-color: #0f172a;
                color: #f8fafc;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        row.addWidget(self.txt_dir)

        btn_browse = QPushButton("Browse…")
        btn_browse.setFont(QFont("Segoe UI", 9))
        btn_browse.setStyleSheet("""
            QPushButton {
                padding: 7px 16px;
                border: 1px solid #475569;
                border-radius: 6px;
                background-color: #334155;
                color: #f1f5f9;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        btn_browse.clicked.connect(self._browse_dir)
        row.addWidget(btn_browse)
        d_layout.addLayout(row)
        layout.addWidget(dir_card)

        # Integration preferences card
        pref_card = QFrame()
        pref_card.setObjectName("prefCard")
        pref_card.setStyleSheet("QFrame#prefCard { background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; }")
        p_layout = QVBoxLayout(pref_card)
        p_layout.setContentsMargins(18, 14, 18, 14)
        p_layout.setSpacing(10)

        pref_lbl = QLabel("Integration & Shortcuts:")
        pref_lbl.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        pref_lbl.setStyleSheet("color: #f1f5f9;")
        p_layout.addWidget(pref_lbl)

        self.chk_desktop = QCheckBox("Create Desktop shortcut")
        self.chk_desktop.setChecked(True)
        p_layout.addWidget(self.chk_desktop)

        self.chk_start = QCheckBox("Create Start Menu shortcut and Windows Add/Remove integration")
        self.chk_start.setChecked(True)
        p_layout.addWidget(self.chk_start)

        self.chk_auto_update = QCheckBox("Check for software updates automatically")
        self.chk_auto_update.setChecked(True)
        p_layout.addWidget(self.chk_auto_update)

        layout.addWidget(pref_card)
        layout.addStretch()
        return page

    def _create_progress_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 26, 36, 20)
        layout.setSpacing(16)

        h = QLabel("Installing StatCraft")
        h.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        h.setStyleSheet("color: #f8fafc;")
        layout.addWidget(h)

        sub = QLabel("Please wait while StatCraft is downloaded and configured on your computer.")
        sub.setFont(QFont("Segoe UI", 9.5))
        sub.setStyleSheet("color: #94a3b8;")
        layout.addWidget(sub)

        layout.addSpacing(10)

        # Progress card container
        card = QFrame()
        card.setObjectName("progressCard")
        card.setStyleSheet("QFrame#progressCard { background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; }")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 18, 20, 18)
        c_layout.setSpacing(14)

        # Status text row
        stat_row = QHBoxLayout()
        self.lbl_progress_status = QLabel("Initializing setup...")
        self.lbl_progress_status.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_progress_status.setStyleSheet("color: #f1f5f9;")
        stat_row.addWidget(self.lbl_progress_status)

        stat_row.addStretch()

        self.lbl_percent = QLabel("0%")
        self.lbl_percent.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_percent.setStyleSheet("color: #60a5fa;")
        stat_row.addWidget(self.lbl_percent)
        c_layout.addLayout(stat_row)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 6px;
                background-color: #0f172a;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #38bdf8);
                border-radius: 6px;
            }
        """)
        c_layout.addWidget(self.progress_bar)

        # Detail text
        self.lbl_detail = QLabel("Connecting to distribution server...")
        self.lbl_detail.setFont(QFont("Segoe UI", 8.5))
        self.lbl_detail.setStyleSheet("color: #94a3b8;")
        c_layout.addWidget(self.lbl_detail)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _create_finish_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 26, 36, 20)
        layout.setSpacing(16)

        # Success banner
        h = QLabel("StatCraft is Ready!")
        h.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        h.setStyleSheet("color: #10b981;")
        layout.addWidget(h)

        sub = QLabel("StatCraft has been successfully installed and configured on your computer.")
        sub.setFont(QFont("Segoe UI", 10))
        sub.setStyleSheet("color: #94a3b8;")
        layout.addWidget(sub)

        layout.addSpacing(10)

        # Summary card
        card = QFrame()
        card.setObjectName("summaryCard")
        card.setStyleSheet("QFrame#summaryCard { background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; }")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20, 16, 20, 16)
        c_layout.setSpacing(10)

        v_lbl = QLabel(f"✓  Installed Version:  StatCraft v{STATCRAFT_VERSION}")
        v_lbl.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Bold))
        v_lbl.setStyleSheet("color: #f1f5f9;")
        c_layout.addWidget(v_lbl)

        loc_lbl = QLabel(f"✓  Installed Location:  {self.custom_target_dir}")
        loc_lbl.setFont(QFont("Segoe UI", 9))
        loc_lbl.setStyleSheet("color: #94a3b8;")
        c_layout.addWidget(loc_lbl)

        sc_lbl = QLabel("✓  Shortcuts created on Desktop and Start Menu")
        sc_lbl.setFont(QFont("Segoe UI", 9))
        sc_lbl.setStyleSheet("color: #94a3b8;")
        c_layout.addWidget(sc_lbl)

        layout.addWidget(card)

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
        self.worker = InstallWorker(
            target_dir=self.custom_target_dir,
            desktop_shortcut=self.chk_desktop.isChecked(),
            start_shortcut=self.chk_start.isChecked(),
            channel="release"
        )
        self.worker.progress_changed.connect(self._on_install_progress)
        self.worker.finished.connect(self._on_install_finished)
        self.worker.start()

    def _on_install_progress(self, percent: int, main_msg: str, detail_msg: str):
        self.progress_bar.setValue(percent)
        self.lbl_percent.setText(f"{percent}%")
        self.lbl_progress_status.setText(main_msg)
        self.lbl_detail.setText(detail_msg)

    def _on_install_finished(self, success: bool, info: str):
        self.btn_cancel.setEnabled(True)
        if success:
            self.installed_exe_path = Path(info)
            self.stack.setCurrentIndex(3)
            self._update_step_styles(3)
            self.btn_back.setEnabled(False)
            self.btn_next.setEnabled(True)
            self.btn_next.setText("Finish")
            self.btn_cancel.setVisible(False)
        else:
            QMessageBox.critical(
                self,
                "Installation Failed",
                f"An error occurred during installation:\n\n{info}"
            )
            self.btn_next.setEnabled(False)
            self.btn_back.setEnabled(True)
            self.btn_cancel.setEnabled(True)


class UninstallerWindow(QMainWindow):
    """Modern uninstaller window matching the setup design system."""

    def __init__(self, target_dir: Path | None = None):
        super().__init__()
        self.setWindowTitle("StatCraft Uninstaller")
        self.setFixedSize(540, 360)
        self.target_dir = target_dir or get_default_install_dir()

        icon = get_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        widget = QWidget()
        widget.setStyleSheet("background-color: #0f172a; color: #f8fafc;")
        self.setCentralWidget(widget)
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(64)
        header.setStyleSheet("background-color: #0b1120; border-bottom: 1px solid #1e293b;")
        head_layout = QHBoxLayout(header)
        head_layout.setContentsMargins(20, 10, 20, 10)

        title = QLabel("Uninstall StatCraft")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #f8fafc;")
        head_layout.addWidget(title)
        head_layout.addStretch()

        main_layout.addWidget(header)

        # Body
        body = QWidget()
        b_layout = QVBoxLayout(body)
        b_layout.setContentsMargins(28, 20, 28, 16)
        b_layout.setSpacing(14)

        self.lbl_prompt = QLabel(
            "Are you sure you want to completely remove StatCraft from your computer?\n\n"
            f"• Location: {self.target_dir}\n"
            "• Desktop & Start Menu shortcuts will be removed\n"
            "• Windows Add/Remove registry entry will be deleted"
        )
        self.lbl_prompt.setFont(QFont("Segoe UI", 9.5))
        self.lbl_prompt.setStyleSheet("color: #cbd5e1; line-height: 1.5;")
        b_layout.addWidget(self.lbl_prompt)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #1e293b;
            }
            QProgressBar::chunk {
                background-color: #ef4444;
                border-radius: 4px;
            }
        """)
        b_layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setFont(QFont("Segoe UI", 9.5, QFont.Weight.Medium))
        self.lbl_status.setStyleSheet("color: #10b981;")
        b_layout.addWidget(self.lbl_status)

        b_layout.addStretch()
        main_layout.addWidget(body)

        # Footer
        footer = QFrame()
        footer.setFixedHeight(56)
        footer.setStyleSheet("background-color: #0b1120; border-top: 1px solid #1e293b;")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(20, 10, 20, 10)
        f_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFont(QFont("Segoe UI", 9))
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                padding: 6px 18px;
                border: 1px solid #334155;
                border-radius: 6px;
                background-color: #1e293b;
                color: #e2e8f0;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)
        self.btn_cancel.clicked.connect(self.close)
        f_layout.addWidget(self.btn_cancel)

        self.btn_uninstall = QPushButton("Uninstall")
        self.btn_uninstall.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.btn_uninstall.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                padding: 6px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        self.btn_uninstall.clicked.connect(self._run_uninstall)
        f_layout.addWidget(self.btn_uninstall)

        main_layout.addWidget(footer)

    def _run_uninstall(self):
        self.btn_uninstall.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(25)
        self.lbl_status.setText("Removing shortcuts and registry entries...")
        QApplication.processEvents()

        time.sleep(0.3)
        remove_shortcuts()
        unregister_windows_uninstaller()
        self.progress_bar.setValue(65)
        self.lbl_status.setText("Cleaning up application files...")
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
        # Download from GitHub
        print("Pulling StatCraft release binary...")
        url = f"https://github.com/{DEFAULT_GITHUB_REPO}/releases/download/v{STATCRAFT_VERSION}/StatCraft-v{STATCRAFT_VERSION}-Windows-x64.exe"
        download_file(url, target_exe)

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
