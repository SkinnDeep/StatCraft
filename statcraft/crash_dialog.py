"""Air-gap-safe Crash Recovery Dialog with pre-filled GitHub Issue link (zero background telemetry)."""
from __future__ import annotations

import os
import platform
import re
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .updater import DEFAULT_GITHUB_REPO, STATCRAFT_VERSION

_MAX_URL_BODY_CHARS = 1400


def _scrub_paths(text: str) -> str:
    """Redact user home / local account paths before displaying or pre-filling an issue."""
    home = str(Path.home())
    cleaned = text
    if home and len(home) > 3:
        cleaned = cleaned.replace(home, "~")
    username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if username and len(username) > 2:
        cleaned = re.sub(rf"([\\/])({re.escape(username)})([\\/])", r"\1<user>\3", cleaned, flags=re.IGNORECASE)
    return cleaned


def _pkg_version(name: str) -> str:
    try:
        mod = __import__(name)
        return str(getattr(mod, "__version__", "unknown"))
    except Exception:
        return "unavailable"


def format_crash_report(exc_type, exc_value, exc_tb, context: Optional[str] = None) -> str:
    """Format an anonymized diagnostic crash summary containing zero worksheet data."""
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb)).strip()
    tb_text = _scrub_paths(tb_text)
    header = [
        f"StatCraft Version: v{STATCRAFT_VERSION}",
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"OS / Platform: {platform.system()} {platform.release()} ({platform.machine()})",
        f"Python: {platform.python_version()} | PySide6: {_pkg_version('PySide6')} | NumPy: {_pkg_version('numpy')} | SciPy: {_pkg_version('scipy')}",
    ]
    if context:
        header.append(f"Context: {context}")
    header.append("")
    header.append("Traceback (worksheet data excluded):")
    header.append(tb_text)
    return "\n".join(header)


def build_github_issue_url(title: str, body: str, repo: str = DEFAULT_GITHUB_REPO) -> str:
    """Build a bounded GitHub 'new issue' URL pre-filled with scrubbed crash diagnostics."""
    safe_title = (title or "Unexpected StatCraft Error").strip()[:120]
    trimmed_body = body.strip()
    if len(trimmed_body) > _MAX_URL_BODY_CHARS:
        trimmed_body = "...\n" + trimmed_body[-_MAX_URL_BODY_CHARS:]
    md_body = (
        "### What happened?\n"
        "_(Please add a brief note on what you clicked before this happened)_\n\n"
        "### Diagnostics\n"
        f"```\n{trimmed_body}\n```\n"
    )
    return (
        f"https://github.com/{repo}/issues/new"
        f"?labels=bug&title={quote(safe_title)}&body={quote(md_body)}"
    )


def write_crash_log(report_text: str, directory: Optional[Path] = None) -> Path:
    """Persist crash details locally for offline debugging."""
    if directory is None:
        if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
            directory = Path(os.environ["LOCALAPPDATA"]) / "StatCraft"
        else:
            directory = Path(tempfile.gettempdir()) / "StatCraft"
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "last_crash.log"
    log_path.write_text(report_text, encoding="utf-8")
    return log_path


class CrashReportDialog(QDialog):
    """Friendly crash recovery dialog offering Copy + 1-click GitHub Issue link."""

    def __init__(self, report_text: str, issue_url: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("StatCraft Encountered an Unexpected Error")
        self.resize(640, 440)
        self.report_text = report_text
        self.issue_url = issue_url

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        msg = QLabel(
            "<b>Something went wrong cleanly — no automatic telemetry was sent.</b><br>"
            "You can copy the anonymized technical details below or click <b>Report Issue on GitHub…</b> "
            "to open a pre-filled bug report in your web browser."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        self.viewer = QPlainTextEdit()
        self.viewer.setReadOnly(True)
        self.viewer.setFont(QFont("Consolas", 9))
        self.viewer.setPlainText(report_text)
        layout.addWidget(self.viewer, 1)

        btns = QHBoxLayout()
        copy_btn = QPushButton("Copy Crash Details")
        copy_btn.clicked.connect(self.copy_details)
        gh_btn = QPushButton("Report Issue on GitHub…")
        gh_btn.setDefault(True)
        gh_btn.clicked.connect(self.open_github_issue)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btns.addWidget(copy_btn)
        btns.addWidget(gh_btn)
        btns.addStretch()
        btns.addWidget(close_btn)
        layout.addLayout(btns)

    def copy_details(self) -> None:
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(self.report_text)

    def open_github_issue(self) -> bool:
        return bool(QDesktopServices.openUrl(QUrl(self.issue_url)))


def show_crash_dialog(exc_type, exc_value, exc_tb, context: Optional[str] = None, parent: Optional[QWidget] = None) -> None:
    """Format diagnostics, save local log, and show the CrashReportDialog."""
    report = format_crash_report(exc_type, exc_value, exc_tb, context=context)
    try:
        write_crash_log(report)
    except OSError:
        pass
    title = f"Crash v{STATCRAFT_VERSION}: {getattr(exc_type, '__name__', 'Error')}: {str(exc_value)[:60]}"
    url = build_github_issue_url(title, report)
    if QApplication.instance() is not None:
        dlg = CrashReportDialog(report, url, parent=parent)
        dlg.exec()


def install_crash_hook(parent_getter=None, force: bool = False) -> None:
    """Install unhandled-exception hook that surfaces the GitHub Issue link dialog on crashes."""
    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        if not force and (os.environ.get("STATCRAFT_TESTING") == "1" or os.environ.get("QT_QPA_PLATFORM") == "offscreen"):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        parent = parent_getter() if callable(parent_getter) else None
        show_crash_dialog(exc_type, exc_value, exc_tb, parent=parent)

    sys.excepthook = _hook
