"""StatCraft Live Testing Sandbox Hub.

A lightweight launcher and status control panel that lets the user
instantly launch and test local source code edits without waiting for
PyInstaller builds or downloading releases from GitHub.
"""
from __future__ import annotations

import os
import sys
import subprocess
import platform
from pathlib import Path
from typing import Dict, Any

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon, QColor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QTextEdit,
    QMessageBox,
)

import statcraft


def get_git_status_info(repo_root: Path | None = None) -> Dict[str, str]:
    """Retrieve active git branch, short commit SHA, and latest commit subject."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[1]

    info = {
        "branch": "local-dev",
        "commit": "source",
        "message": "Local development working tree",
    }
    try:
        flags = 0x08000000 if sys.platform == "win32" else 0
        r_branch = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            creationflags=flags,
            timeout=3,
        )
        if r_branch.returncode == 0 and r_branch.stdout.strip():
            info["branch"] = r_branch.stdout.strip()

        r_commit = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            creationflags=flags,
            timeout=3,
        )
        if r_commit.returncode == 0 and r_commit.stdout.strip():
            info["commit"] = r_commit.stdout.strip()

        r_msg = subprocess.run(
            ["git", "-C", str(repo_root), "log", "-1", "--pretty=%s"],
            capture_output=True,
            text=True,
            creationflags=flags,
            timeout=3,
        )
        if r_msg.returncode == 0 and r_msg.stdout.strip():
            info["message"] = r_msg.stdout.strip()
    except Exception:
        pass
    return info


class StatCraftSandboxHub(QDialog):
    """Lightweight 1-click desktop control panel for launching the live StatCraft sandbox."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🧪 StatCraft Live Testing Sandbox Hub")
        self.resize(700, 480)
        self.setMinimumSize(560, 380)
        self.setSizeGripEnabled(True)

        self.repo_root = Path(__file__).resolve().parents[1]
        self.git_info = get_git_status_info(self.repo_root)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Header Title Banner
        header = QLabel("<b>🧪 StatCraft Live Testing Sandbox</b>")
        header.setStyleSheet("font-size: 13pt; color: #0284c7; font-weight: 700;")
        layout.addWidget(header)

        sub = QLabel(
            "Direct local execution environment. Any code changes in your workspace "
            "apply immediately upon launching with zero compilation or download lag."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("font-size: 9pt; color: #64748b;")
        layout.addWidget(sub)

        # Status Card
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; }"
        )
        c_lay = QVBoxLayout(card)
        c_lay.setSpacing(6)

        c_title = QLabel("<b>Current Workspace Environment</b>")
        c_title.setStyleSheet("font-size: 9.5pt; color: #0f172a;")
        c_lay.addWidget(c_title)

        v_lbl = QLabel(f"• <b>Active Target Version:</b> v{statcraft.__version__}-dev")
        v_lbl.setStyleSheet("font-size: 9pt; color: #334155;")
        c_lay.addWidget(v_lbl)

        b_lbl = QLabel(f"• <b>Git Branch:</b> <code>{self.git_info['branch']}</code> (commit <code>{self.git_info['commit']}</code>)")
        b_lbl.setStyleSheet("font-size: 9pt; color: #334155;")
        c_lay.addWidget(b_lbl)

        m_lbl = QLabel(f"• <b>Latest Commit:</b> {self.git_info['message']}")
        m_lbl.setStyleSheet("font-size: 9pt; color: #334155;")
        m_lbl.setWordWrap(True)
        c_lay.addWidget(m_lbl)

        p_lbl = QLabel(f"• <b>Python Runtime:</b> <code>{Path(sys.executable).name}</code>")
        p_lbl.setStyleSheet("font-size: 8.5pt; color: #64748b;")
        c_lay.addWidget(p_lbl)

        layout.addWidget(card)

        # Primary Launch Action
        self.btn_launch = QPushButton("🚀 Launch Live Sandbox Instance")
        self.btn_launch.setFixedHeight(44)
        self.btn_launch.setStyleSheet(
            "QPushButton { background-color: #0284c7; color: white; font-size: 10.5pt; font-weight: 700; border-radius: 6px; }"
            "QPushButton:hover { background-color: #0369a1; }"
            "QPushButton:pressed { background-color: #075985; }"
        )
        self.btn_launch.setToolTip("Launch StatCraft directly against live source with --sandbox active.")
        self.btn_launch.clicked.connect(self.launch_sandbox)
        layout.addWidget(self.btn_launch)

        self.status_msg = QLabel("Ready to launch live sandbox.")
        self.status_msg.setStyleSheet("font-size: 8.5pt; color: #059669; font-weight: 500;")
        self.status_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_msg)

        # Secondary Actions
        sec_bar = QHBoxLayout()
        sec_bar.setSpacing(8)

        btn_diag = QPushButton("📋 Copy Diagnostics")
        btn_diag.setStyleSheet("padding: 6px 12px; font-size: 8.5pt;")
        btn_diag.setToolTip("Copy system, git, and python diagnostics to clipboard for quick feedback.")
        btn_diag.clicked.connect(self.copy_diagnostics)
        sec_bar.addWidget(btn_diag)

        btn_scratch = QPushButton("🧪 Open Scratch Folder")
        btn_scratch.setStyleSheet("padding: 6px 12px; font-size: 8.5pt;")
        btn_scratch.setToolTip("Open the isolated sandbox scratch workspace directory.")
        btn_scratch.clicked.connect(self.open_scratch_dir)
        sec_bar.addWidget(btn_scratch)

        btn_src = QPushButton("📂 Open Source Folder")
        btn_src.setStyleSheet("padding: 6px 12px; font-size: 8.5pt;")
        btn_src.clicked.connect(self.open_source_dir)
        sec_bar.addWidget(btn_src)

        btn_update = QPushButton("🔄 Check for Updates")
        btn_update.setStyleSheet("padding: 6px 12px; font-size: 8.5pt;")
        btn_update.setToolTip("Check for new StatCraft software updates.")
        btn_update.clicked.connect(self.check_updates)
        sec_bar.addWidget(btn_update)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet("padding: 6px 12px; font-size: 8.5pt;")
        btn_close.clicked.connect(self.accept)
        sec_bar.addWidget(btn_close)

        layout.addLayout(sec_bar)

    def launch_sandbox(self):
        """Spawn launch_modern.py --sandbox as an independent background process."""
        entry_script = self.repo_root / "launch_modern.py"
        deps_dir = self.repo_root.parent / "statcraft-build-deps"

        env = os.environ.copy()
        paths = []
        if deps_dir.is_dir():
            paths.append(str(deps_dir))
        paths.append(str(self.repo_root))
        if env.get("PYTHONPATH"):
            paths.append(env["PYTHONPATH"])
        env["PYTHONPATH"] = os.pathsep.join(paths)

        cmd = [sys.executable, str(entry_script), "--sandbox"]

        kwargs: Dict[str, Any] = {
            "cwd": str(self.repo_root),
            "env": env,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW for launcher
        else:
            kwargs["start_new_session"] = True

        try:
            proc = subprocess.Popen(cmd, **kwargs)
            self.status_msg.setText(f"✓ Launched live sandbox process (PID: {proc.pid})")
            self.status_msg.setStyleSheet("font-size: 8.5pt; color: #0284c7; font-weight: 600;")
            return proc
        except Exception as exc:
            self.status_msg.setText(f"⚠ Failed to launch: {exc}")
            self.status_msg.setStyleSheet("font-size: 8.5pt; color: #dc2626; font-weight: 600;")
            return None

    def copy_diagnostics(self):
        """Copy diagnostic details to clipboard for easy feedback reporting."""
        diag = (
            f"=== StatCraft Live Sandbox Diagnostics ===\n"
            f"Target Version: v{statcraft.__version__}-dev\n"
            f"Git Branch: {self.git_info['branch']}\n"
            f"Git Commit: {self.git_info['commit']}\n"
            f"Latest Message: {self.git_info['message']}\n"
            f"Source Root: {self.repo_root}\n"
            f"Python: {sys.executable} ({platform.python_version()})\n"
            f"OS: {platform.platform()}\n"
        )
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(diag)
        self.status_msg.setText("✓ Diagnostic details copied to clipboard!")
        self.status_msg.setStyleSheet("font-size: 8.5pt; color: #059669; font-weight: 600;")

    def open_scratch_dir(self):
        """Open the isolated sandbox scratch workspace in File Explorer."""
        scratch_dir = self.repo_root / ".sandbox_workspace"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(scratch_dir))
        else:
            subprocess.run(["xdg-open", str(scratch_dir)])

    def open_source_dir(self):
        """Open the working source directory in File Explorer."""
        if sys.platform == "win32":
            os.startfile(str(self.repo_root))
        else:
            subprocess.run(["xdg-open", str(self.repo_root)])

    def check_updates(self):
        """Open the in-app Check for Updates dialog."""
        from .updater_dialog import CheckForUpdatesDialog
        dlg = CheckForUpdatesDialog(self)
        dlg.exec()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    hub = StatCraftSandboxHub()
    hub.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
