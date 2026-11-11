"""StatCraft Production Auto-Updater & Version Management Module.

Provides version tracking, remote update checks against GitHub releases or
custom update manifests, safe downloading, and Windows shortcut management.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Optional

STATCRAFT_VERSION = "116.5.0"
DEFAULT_GITHUB_REPO = "SkinnDeep/StatCraft"


def _run_hidden_subprocess(cmd: list[str] | str, **kwargs) -> subprocess.CompletedProcess:
    """Execute a command completely hidden in the background on Windows with zero visible consoles."""
    if sys.platform == "win32":
        creationflags = kwargs.get("creationflags", 0) | 0x08000000  # CREATE_NO_WINDOW
        kwargs["creationflags"] = creationflags
        startupinfo = kwargs.get("startupinfo")
        if startupinfo is None:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            kwargs["startupinfo"] = startupinfo
    return subprocess.run(cmd, **kwargs)


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


def is_major_update(cur_v: str, latest_v: str) -> bool:
    """Check if latest_v represents a major version increment over cur_v (e.g. 104.x -> 105.x)."""
    t1 = parse_version(cur_v)
    t2 = parse_version(latest_v)
    return t2[0] > t1[0]


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
        data = None
        # Support file:/// or local filesystem path for testing and enterprise feeds
        if manifest_url and (manifest_url.startswith("file://") or Path(manifest_url).exists()):
            file_path = manifest_url[7:] if manifest_url.startswith("file://") else manifest_url
            data = json.loads(Path(file_path).read_text(encoding="utf-8"))
        else:
            url = manifest_url or f"https://api.github.com/repos/{repo}/releases/latest"

            # Method 1: Microsoft Windows native curl.exe with OS Schannel certificate store
            import shutil
            curl_bin = shutil.which("curl.exe") or shutil.which("curl")
            if curl_bin:
                try:
                    c_res = _run_hidden_subprocess(
                        [
                            curl_bin,
                            "-s",
                            "--fail",
                            "-L",
                            "-H", f"User-Agent: StatCraft-Updater/{cur_v}",
                            "-H", "Accept: application/vnd.github.v3+json",
                            url
                        ],
                        capture_output=True,
                        text=True,
                        timeout=int(timeout) + 2
                    )
                    if c_res.returncode == 0 and c_res.stdout.strip():
                        data = json.loads(c_res.stdout)
                except Exception:
                    pass

            # Method 2: Python urllib with SSL fallback
            if data is None:
                import ssl
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": f"StatCraft-Updater/{cur_v}",
                        "Accept": "application/vnd.github.v3+json"
                    }
                )
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as response:
                        payload = response.read().decode("utf-8")
                        data = json.loads(payload)
                except (FileNotFoundError, OSError, ssl.SSLError):
                    # PyInstaller bundle on Windows without bundled OpenSSL CA certs
                    ctx = ssl._create_unverified_context()
                    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                        payload = response.read().decode("utf-8")
                        data = json.loads(payload)

        if not data:
            raise RuntimeError("Could not retrieve release metadata.")

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

        res["setup_download_url"] = setup_url or f"https://github.com/{repo}/releases/download/v{latest_ver}/StatCraft-Setup-v{latest_ver}-Windows-x64.exe"
        res["app_download_url"] = exe_url or f"https://github.com/{repo}/releases/download/v{latest_ver}/StatCraft-v{latest_ver}-Windows-x64.exe"
        res["download_url"] = data.get("download_url") or exe_url or setup_url or res["app_download_url"]

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
    """Download a file with real-time byte progress reporting and native fallback."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_dest = destination.with_suffix(".part_download")

    err_list = []

    # Method 1: Python urllib with temporary buffer file
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"StatCraft-Downloader/{STATCRAFT_VERSION}",
                "Accept": "*/*"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp, open(temp_dest, 'wb') as out_f:
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
            out_f.flush()

        if temp_dest.exists() and temp_dest.stat().st_size > 0:
            if destination.exists():
                try:
                    destination.unlink()
                except Exception:
                    pass
            temp_dest.replace(destination)
            return destination
    except Exception as exc:
        err_list.append(f"urllib error: {exc}")
        if temp_dest.exists():
            try:
                temp_dest.unlink()
            except Exception:
                pass

    # Method 2: Microsoft Windows native curl.exe fallback (executed silently)
    import shutil
    curl_bin = shutil.which("curl.exe") or shutil.which("curl")
    if curl_bin:
        try:
            cmd = [
                curl_bin,
                "-L",  # Follow redirects
                "--fail",  # Fail on HTTP errors
                "--silent",
                "--show-error",
                "--retry", "3",
                "-o", str(temp_dest),
                url
            ]
            res = _run_hidden_subprocess(cmd, capture_output=True, text=True, timeout=180)
            if res.returncode == 0 and temp_dest.exists() and temp_dest.stat().st_size > 0:
                if destination.exists():
                    try:
                        destination.unlink()
                    except Exception:
                        pass
                temp_dest.replace(destination)
                return destination
            else:
                err_list.append(f"curl error (code {res.returncode}): {res.stderr.strip()}")
        except Exception as exc:
            err_list.append(f"curl invocation error: {exc}")
            if temp_dest.exists():
                try:
                    temp_dest.unlink()
                except Exception:
                    pass

    # Method 3: urllib with unverified SSL context fallback (handles corporate SSL inspection / proxies)
    try:
        import ssl
        unverified_ctx = ssl._create_unverified_context()
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"StatCraft-Updater/{STATCRAFT_VERSION} (Windows; x64)",
                "Accept": "application/octet-stream"
            }
        )
        with urllib.request.urlopen(req, context=unverified_ctx, timeout=45) as resp, open(temp_dest, 'wb') as out_f:
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
            out_f.flush()

        if temp_dest.exists() and temp_dest.stat().st_size > 0:
            if destination.exists():
                try:
                    destination.unlink()
                except Exception:
                    pass
            temp_dest.replace(destination)
            return destination
    except Exception as exc:
        err_list.append(f"urllib fallback error: {exc}")
        if temp_dest.exists():
            try:
                temp_dest.unlink()
            except Exception:
                pass

    raise RuntimeError(" ; ".join(err_list) or "All download methods failed.")


def create_windows_shortcut(
    target_path: Path,
    shortcut_path: Path,
    description: str = "StatCraft Statistical Software",
    icon_path: Optional[Path] = None,
    working_dir: Optional[Path] = None
) -> bool:
    """Create a Windows .lnk shortcut using native Windows Script Host silently."""
    if sys.platform != "win32":
        return False
    try:
        shortcut_path.parent.mkdir(parents=True, exist_ok=True)
        work_dir = working_dir or target_path.parent
        icon_arg = str(icon_path or target_path).replace('"', '""')
        target_arg = str(target_path).replace('"', '""')
        lnk_arg = str(shortcut_path).replace('"', '""')
        work_arg = str(work_dir).replace('"', '""')
        desc_arg = str(description).replace('"', '""')

        # Primary method: Windows Script Host via cscript/wscript (no PowerShell process spawned)
        vbs_path = shortcut_path.parent / f"_sc_{os.getpid()}_{int(time.time()*1000)%10000}.vbs"
        try:
            vbs_script = (
                f'Set ws = WScript.CreateObject("WScript.Shell")\r\n'
                f'Set s = ws.CreateShortcut("{lnk_arg}")\r\n'
                f's.TargetPath = "{target_arg}"\r\n'
                f's.WorkingDirectory = "{work_arg}"\r\n'
                f's.Description = "{desc_arg}"\r\n'
                f's.IconLocation = "{icon_arg}"\r\n'
                f's.Save\r\n'
            )
            vbs_path.write_text(vbs_script, encoding="ansi")
            res = _run_hidden_subprocess(["cscript.exe", "//nologo", str(vbs_path)], timeout=10)
            if res.returncode == 0 and shortcut_path.exists():
                return True
        finally:
            if vbs_path.exists():
                try:
                    vbs_path.unlink()
                except Exception:
                    pass

        return shortcut_path.exists()
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


def remove_shortcuts() -> None:
    """Remove Desktop and Start Menu shortcuts for StatCraft."""
    if sys.platform != "win32":
        return
    desktop_dir = Path(os.environ.get("USERPROFILE", "~")) / "Desktop"
    if not desktop_dir.exists():
        desktop_dir = Path.home() / "Desktop"
    d_lnk = desktop_dir / "StatCraft.lnk"
    if d_lnk.exists():
        try:
            d_lnk.unlink()
        except Exception:
            pass

    appdata = os.environ.get("APPDATA")
    start_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" if appdata else Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    s_lnk = start_dir / "StatCraft.lnk"
    if s_lnk.exists():
        try:
            s_lnk.unlink()
        except Exception:
            pass


def register_windows_uninstaller(
    install_dir: Path,
    version: str = STATCRAFT_VERSION,
    icon_path: Optional[Path] = None
) -> bool:
    """Register StatCraft in Windows Add/Remove Programs (HKCU uninstall registry)."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\StatCraft"
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)

        uninstall_exe = install_dir / "StatCraft-Uninstall.exe"
        if not uninstall_exe.exists():
            uninstall_exe = install_dir / "StatCraft-Setup.exe"

        ico = icon_path or (install_dir / "StatCraft.ico")
        if not ico.exists():
            ico = install_dir / "StatCraft.exe"

        # Calculate estimated size in KB
        size_kb = 0
        try:
            for f in install_dir.rglob("*"):
                if f.is_file():
                    size_kb += f.stat().st_size // 1024
        except Exception:
            size_kb = 95000

        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "StatCraft")
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "StatCraft Developers")
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(ico))
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstall_exe}" --uninstall')
        winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, f'"{uninstall_exe}" --uninstall --silent')
        winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, size_kb)
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "URLInfoAbout", 0, winreg.REG_SZ, "https://github.com/SkinnDeep/StatCraft")
        winreg.SetValueEx(key, "HelpLink", 0, winreg.REG_SZ, "https://github.com/SkinnDeep/StatCraft")
        winreg.CloseKey(key)
        return True
    except Exception as exc:
        print(f"Warning: Failed to register Windows uninstaller: {exc}")
        return False


def unregister_windows_uninstaller() -> bool:
    """Remove StatCraft from Windows Add/Remove Programs registry."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\StatCraft"
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        return True
    except FileNotFoundError:
        return True
    except Exception as exc:
        print(f"Warning: Failed to unregister Windows uninstaller: {exc}")
        return False


def _delete_reg_key_tree(root, subkey: str):
    """Recursively delete a Windows registry key tree."""
    import winreg
    try:
        with winreg.OpenKey(root, subkey, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    child = winreg.EnumKey(k, 0)
                    _delete_reg_key_tree(root, f"{subkey}\\{child}")
                except OSError:
                    break
        winreg.DeleteKey(root, subkey)
    except Exception:
        pass


def register_file_associations(target_exe: Path, extensions: Optional[list[str]] = None) -> bool:
    """Register file associations in HKCU\\Software\\Classes for Minitab and JMP files."""
    if sys.platform != "win32":
        return False
    if extensions is None:
        extensions = [".mpx", ".mtw", ".mwx", ".jmp"]
    try:
        import winreg
        exe_path = str(target_exe.resolve())
        ico_str = f'"{exe_path}",0'

        file_types = {
            ".mpx": ("StatCraft.MpxFile", "Minitab Project File"),
            ".mtw": ("StatCraft.MtwFile", "Minitab Worksheet File"),
            ".mwx": ("StatCraft.MwxFile", "Minitab XML Worksheet"),
            ".jmp": ("StatCraft.JmpFile", "JMP Data Table"),
        }

        for ext in extensions:
            ext_lower = ext.lower().strip()
            if ext_lower not in file_types:
                continue
            prog_id, desc = file_types[ext_lower]

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext_lower}") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, prog_id)

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, desc)

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}\DefaultIcon") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, ico_str)

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{prog_id}\shell\open\command") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f'"{exe_path}" "%1"')

        try:
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, 0, 0)
        except Exception:
            pass
        return True
    except Exception as exc:
        print(f"Warning: Failed to register file associations: {exc}")
        return False


def unregister_file_associations(extensions: Optional[list[str]] = None) -> bool:
    """Unregister file associations from HKCU\\Software\\Classes."""
    if sys.platform != "win32":
        return False
    if extensions is None:
        extensions = [".mpx", ".mtw", ".mwx", ".jmp"]
    try:
        import winreg
        prog_ids = ["StatCraft.MpxFile", "StatCraft.MtwFile", "StatCraft.MwxFile", "StatCraft.JmpFile"]
        for pid in prog_ids:
            _delete_reg_key_tree(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{pid}")

        for ext in extensions:
            ext_lower = ext.lower().strip()
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{ext_lower}", 0, winreg.KEY_READ | winreg.KEY_WRITE) as k:
                    val, _ = winreg.QueryValueEx(k, "")
                    if "StatCraft" in str(val):
                        winreg.DeleteValue(k, "")
            except Exception:
                pass

        try:
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, 0, 0)
        except Exception:
            pass
        return True
    except Exception as exc:
        print(f"Warning: Failed to unregister file associations: {exc}")
        return False


def perform_uninstall(target_dir: Optional[Path] = None) -> bool:
    """Fully uninstall StatCraft: remove shortcuts, unregister from Windows, and remove files."""
    install_dir = target_dir or get_default_install_dir()
    remove_shortcuts()
    unregister_file_associations()
    unregister_windows_uninstaller()

    # Remove files in install directory
    if install_dir.exists():
        import shutil
        try:
            # Delete non-running files
            for item in install_dir.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink()
                except Exception:
                    pass
            # If directory is empty, remove it
            try:
                install_dir.rmdir()
            except Exception:
                pass
            return True
        except Exception as exc:
            print(f"Uninstall cleanup warning: {exc}")
            return False
    return True
