"""StatCraft Production Auto-Updater & Version Management Module.

Provides version tracking, remote update checks against GitHub releases or
custom update manifests, safe downloading, and Windows shortcut management.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Optional

STATCRAFT_VERSION = "104.0.0"
DEFAULT_GITHUB_REPO = "statcraft/statcraft"


def parse_version(ver_str: str) -> tuple[int, ...]:
    """Parse a semantic version string (e.g. 'v103.1.2' -> (103, 1, 2))."""
    if not ver_str:
        return (0, 0, 0)
    cleaned = re.sub(r'^[vV]', '', str(ver_str).strip())
    match = re.search(r'(\d+(?:\.\d+)*)', cleaned)
    if not match:
        return (0, 0, 0)
    parts = []
    for num in match.group(1).split('.'):
        try:
            parts.append(int(num))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings. Returns -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2."""
    t1 = parse_version(v1)
    t2 = parse_version(v2)
    if t1 < t2:
        return -1
    elif t1 > t2:
        return 1
    return 0


def get_default_install_dir() -> Path:
    """Get the standard user-level installation directory for StatCraft across OSes."""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "StatCraft"
        return Path.home() / "AppData" / "Local" / "StatCraft"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "StatCraft"
    else:
        # Linux / Unix XDG standard
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            return Path(xdg_data) / "statcraft"
        return Path.home() / ".local" / "share" / "statcraft"


def read_install_metadata(install_dir: Optional[Path] = None) -> dict:
    """Read version.json metadata from the installation directory."""
    target_dir = install_dir or get_default_install_dir()
    meta_file = target_dir / "version.json"
    if meta_file.exists():
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": STATCRAFT_VERSION, "channel": "release"}


def write_install_metadata(install_dir: Path, version: str, channel: str = "release", **kwargs) -> Path:
    """Write version.json metadata into the target install directory."""
    install_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "version": version,
        "channel": channel,
        "installed_at": kwargs.get("installed_at"),
        "install_dir": str(install_dir),
        "repo": kwargs.get("repo", DEFAULT_GITHUB_REPO)
    }
    meta_file = install_dir / "version.json"
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta_file


def check_for_updates(
    current_ver: Optional[str] = None,
    manifest_url: Optional[str] = None,
    repo: str = DEFAULT_GITHUB_REPO,
    timeout: float = 6.0
) -> dict:
    """Check for software updates against a GitHub releases API endpoint or JSON manifest.

    Returns a status dict:
      {
        "update_available": bool,
        "current_version": str,
        "latest_version": str,
        "release_name": str,
        "release_notes": str,
        "download_url": str | None,
        "published_at": str | None,
        "error": str | None
      }
    """
    cur_v = current_ver or STATCRAFT_VERSION
    res = {
        "update_available": False,
        "current_version": cur_v,
        "latest_version": cur_v,
        "release_name": "",
        "release_notes": "",
        "download_url": None,
        "published_at": None,
        "error": None
    }

    try:
        # Support file:/// or local filesystem path for testing and enterprise feeds
        if manifest_url and (manifest_url.startswith("file://") or Path(manifest_url).exists()):
            file_path = manifest_url[7:] if manifest_url.startswith("file://") else manifest_url
            data = json.loads(Path(file_path).read_text(encoding="utf-8"))
        else:
            url = manifest_url or f"https://api.github.com/repos/{repo}/releases/latest"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": f"StatCraft-Updater/{cur_v}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
                data = json.loads(payload)

        # Parse release payload (standard GitHub release JSON or custom manifest)
        tag = data.get("tag_name") or data.get("version") or ""
        latest_ver = tag.lstrip("vV")
        res["latest_version"] = latest_ver
        res["release_name"] = data.get("name") or f"StatCraft v{latest_ver}"
        res["release_notes"] = data.get("body") or data.get("notes") or ""
        res["published_at"] = data.get("published_at")

        # Locate download URL for Setup or Exe
        assets = data.get("assets", [])
        setup_url = None
        exe_url = None
        for asset in assets:
            name = asset.get("name", "").lower()
            if "setup" in name and name.endswith(".exe"):
                setup_url = asset.get("browser_download_url")
            elif name.endswith(".exe"):
                exe_url = asset.get("browser_download_url")

        res["download_url"] = setup_url or exe_url or data.get("download_url")

        if compare_versions(cur_v, latest_ver) < 0:
            res["update_available"] = True

    except urllib.error.URLError as err:
        res["error"] = f"Network connection failed: {err.reason}"
    except Exception as exc:
        res["error"] = f"Update check error: {exc}"

    return res


def download_file(
    url: str,
    destination: Path,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    chunk_size: int = 65536
) -> Path:
    """Download a file with real-time byte progress reporting."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": f"StatCraft-Downloader/{STATCRAFT_VERSION}"})
    with urllib.request.urlopen(req) as resp, open(destination, 'wb') as out_f:
        total_size = int(resp.headers.get('Content-Length', 0))
        downloaded = 0
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            out_f.write(chunk)
            downloaded += len(chunk)
            if progress_callback:
                progress_callback(downloaded, total_size)
    return destination


def create_windows_shortcut(
    target_path: Path,
    shortcut_path: Path,
    description: str = "StatCraft Statistical Software",
    icon_path: Optional[Path] = None,
    working_dir: Optional[Path] = None
) -> bool:
    """Create a Windows .lnk shortcut using PowerShell WScript.Shell."""
    if sys.platform != "win32":
        return False
    try:
        shortcut_path.parent.mkdir(parents=True, exist_ok=True)
        work_dir = working_dir or target_path.parent
        icon_arg = str(icon_path or target_path).replace("'", "''")
        target_arg = str(target_path).replace("'", "''")
        lnk_arg = str(shortcut_path).replace("'", "''")
        work_arg = str(work_dir).replace("'", "''")
        desc_arg = str(description).replace("'", "''")

        ps_script = (
            f"$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{lnk_arg}'); "
            f"$s.TargetPath = '{target_arg}'; "
            f"$s.WorkingDirectory = '{work_arg}'; "
            f"$s.Description = '{desc_arg}'; "
            f"$s.IconLocation = '{icon_arg}'; "
            f"$s.Save()"
        )
        import subprocess
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10
        )
        return res.returncode == 0 and shortcut_path.exists()
    except Exception:
        return False


def setup_shortcuts(
    target_exe: Path,
    desktop: bool = True,
    start_menu: bool = True,
    icon_path: Optional[Path] = None
) -> dict[str, bool]:
    """Create Desktop and/or Start Menu shortcuts for StatCraft."""
    results = {}
    if not target_exe.exists():
        return {"desktop": False, "start_menu": False}

    if desktop:
        desktop_dir = Path(os.environ.get("USERPROFILE", "~")) / "Desktop"
        if not desktop_dir.exists():
            desktop_dir = Path.home() / "Desktop"
        shortcut = desktop_dir / "StatCraft.lnk"
        results["desktop"] = create_windows_shortcut(target_exe, shortcut, icon_path=icon_path)

    if start_menu:
        appdata = os.environ.get("APPDATA")
        start_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" if appdata else Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        shortcut = start_dir / "StatCraft.lnk"
        results["start_menu"] = create_windows_shortcut(target_exe, shortcut, icon_path=icon_path)

    return results
