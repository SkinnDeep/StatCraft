"""Local R process, worksheet exchange, and installation helpers."""
from __future__ import annotations

import atexit
import csv
import json
import math
import uuid
import glob
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_SESSION_DIR: Optional[Path] = None
_PERSISTENT_SESSION: Optional["RPersistentSession"] = None
_SESSION_LOCK = threading.Lock()
_DISCOVERY_LOCK = threading.Lock()
_DISCOVERY = (0.0, None)
_TEMP_ROOT = None
_PROCESS_LOCK = threading.Lock()
_ACTIVE_PROCESSES = set()


def get_r_session_dir() -> Path:
    """Return the persistent directory for the active StatCraft session."""
    global _SESSION_DIR, _TEMP_ROOT
    with _DISCOVERY_LOCK:
        if _SESSION_DIR is None:
            _TEMP_ROOT = tempfile.TemporaryDirectory(prefix="statcraft-r-")
            _SESSION_DIR = Path(_TEMP_ROOT.name)
            # Exit handlers run in reverse registration order. Stop R before tempfile removes its working directory.
            atexit.register(_shutdown_r_processes)
        return _SESSION_DIR


def _stop_process(process, *, wait=False):
    try:
        if process.poll() is None:
            process.kill()
        if wait:
            process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _shutdown_r_processes():
    with _PROCESS_LOCK:
        processes = list(_ACTIVE_PROCESSES)
    for process in processes:
        _stop_process(process, wait=True)


def reset_r_session() -> None:
    """Stop R. A new session starts when the next command runs."""
    if _PERSISTENT_SESSION is not None:
        _PERSISTENT_SESSION.interrupt(wait=True)


def find_r_executable(*, refresh=False) -> Optional[str]:
    """Cache local discovery, including a short cache for a missing installation."""
    global _DISCOVERY
    with _DISCOVERY_LOCK:
        expires, path = _DISCOVERY
        now = time.monotonic()
        if refresh or now >= expires or path and not Path(path).is_file():
            path = _discover_r_executable()
            _DISCOVERY = (now + (60 if path else 5), path)
        return path


def _discover_r_executable() -> Optional[str]:
    # 0. User configured path in QSettings
    try:
        from PySide6.QtCore import QSettings
        settings = QSettings("StatCraft", "StatCraft")
        cust = settings.value("custom_r_path")
        if cust and Path(str(cust)).is_file():
            return str(cust)
    except Exception:
        pass

    # 1. Custom environment variable override
    env_path = os.environ.get("STATCRAFT_R_PATH") or os.environ.get("R_HOME")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            return str(p)
        for cand_name in ("Rscript.exe", "Rterm.exe", "R.exe", "Rscript", "R"):
            cand = p / "bin" / cand_name
            if cand.is_file():
                return str(cand)
            cand_x64 = p / "bin" / "x64" / cand_name
            if cand_x64.is_file():
                return str(cand_x64)

    # 2. Check system PATH
    for cmd in ("Rscript", "Rterm", "R"):
        which_r = shutil.which(cmd)
        if which_r:
            return which_r

    system = platform.system()
    if system == "Windows":
        # 3. Check Windows Registry with both 64-bit and 32-bit views
        try:
            import winreg
            reg_views = [winreg.KEY_READ]
            if hasattr(winreg, "KEY_WOW64_64KEY"):
                reg_views.append(winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            if hasattr(winreg, "KEY_WOW64_32KEY"):
                reg_views.append(winreg.KEY_READ | winreg.KEY_WOW64_32KEY)

            for key_path in (r"SOFTWARE\R-Core\R", r"SOFTWARE\R-Core\R64", r"SOFTWARE\R-Core"):
                for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                    for access in reg_views:
                        try:
                            with winreg.OpenKey(root, key_path, 0, access) as k:
                                for sub_val in ("InstallPath", "Current Version"):
                                    try:
                                        inst_path, _ = winreg.QueryValueEx(k, sub_val)
                                        if inst_path and os.path.isdir(inst_path):
                                            for ex in ("bin/Rscript.exe", "bin/x64/Rscript.exe", "bin/x64/Rterm.exe", "bin/R.exe"):
                                                target = Path(inst_path) / ex
                                                if target.is_file():
                                                    return str(target)
                                    except (OSError, FileNotFoundError):
                                        pass
                        except (OSError, FileNotFoundError):
                            pass
        except ImportError:
            pass

        # 4. Search Standard Windows directories
        prog_dirs = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
            str(Path.home() / "AppData" / "Local" / "Programs"),
            str(Path.home()),
            r"C:\R",
            r"D:\R",
            r"C:\tools\R",
        ]

        for base in prog_dirs:
            if not base or not os.path.isdir(base):
                continue
            base_path = Path(base)

            # Check direct or sub R directory
            check_dirs = [base_path / "R", base_path] if base_path.name.lower() != "r" else [base_path]
            for r_dir in check_dirs:
                if r_dir.is_dir():
                    # Subdirectories matching R-* (e.g. R-4.6.1, R-4.4.2)
                    subdirs = sorted(r_dir.glob("R-*"), reverse=True)
                    if not subdirs and (r_dir / "bin").is_dir():
                        subdirs = [r_dir]
                    for sd in subdirs:
                        for ex_rel in (
                            "bin/x64/Rterm.exe",
                            "bin/Rscript.exe",
                            "bin/x64/Rscript.exe",
                            "bin/R.exe",
                            "bin/x64/R.exe",
                        ):
                            exe = sd / ex_rel
                            if exe.is_file():
                                return str(exe)

        # 5. Conda / Scoop / Chocolatey environments
        user_home = Path.home()
        conda_paths = [
            user_home / "miniconda3" / "Scripts" / "Rscript.exe",
            user_home / "anaconda3" / "Scripts" / "Rscript.exe",
            user_home / "miniforge3" / "Scripts" / "Rscript.exe",
            Path(r"C:\ProgramData\miniconda3\Scripts\Rscript.exe"),
            Path(r"C:\ProgramData\anaconda3\Scripts\Rscript.exe"),
            user_home / "scoop" / "apps" / "r" / "current" / "bin" / "Rscript.exe",
        ]
        for cp in conda_paths:
            if cp.is_file():
                return str(cp)

    elif system == "Darwin":  # macOS
        mac_paths = [
            "/Library/Frameworks/R.framework/Resources/bin/Rscript",
            "/Library/Frameworks/R.framework/Resources/bin/R",
            "/opt/homebrew/bin/Rscript",
            "/opt/homebrew/bin/R",
            "/usr/local/bin/Rscript",
            "/usr/local/bin/R",
        ]
        for mp in mac_paths:
            if os.path.isfile(mp) and os.access(mp, os.X_OK):
                return mp

    else:  # Linux / Unix
        linux_paths = [
            "/usr/bin/Rscript",
            "/usr/bin/R",
            "/usr/local/bin/Rscript",
            "/usr/local/bin/R",
            "/opt/R/bin/Rscript",
            "/opt/R/bin/R",
        ]
        for lp in linux_paths:
            if os.path.isfile(lp) and os.access(lp, os.X_OK):
                return lp

    return None


def find_interactive_r_executable() -> Optional[str]:
    """Find the best interactive R binary for persistent REPL (e.g. Rterm.exe or R)."""
    base_exe = find_r_executable()
    if not base_exe:
        return None

    p = Path(base_exe)
    system = platform.system()

    if system == "Windows":
        # Look for Rterm.exe in same directory or adjacent x64
        candidates = [
            p.parent / "Rterm.exe",
            p.parent / "x64" / "Rterm.exe",
            p.parent.parent / "bin" / "x64" / "Rterm.exe",
            p.parent.parent / "bin" / "Rterm.exe",
            p.parent / "R.exe",
            p.parent / "x64" / "R.exe",
            p,
        ]
        for cand in candidates:
            if cand.is_file():
                return str(cand)
    else:
        # Unix / macOS prefers 'R' over 'Rscript' for interactive pipe
        candidates = [
            p.parent / "R",
            p,
        ]
        for cand in candidates:
            if cand.is_file() and os.access(cand, os.X_OK):
                return str(cand)

    return base_exe


def is_r_available() -> bool:
    """Return True if an R executable is found and executable."""
    return find_r_executable() is not None


def get_r_version() -> Optional[str]:
    """Return R version string (e.g. 'R version 4.6.1 (2026-06-24)')."""
    exe = find_r_executable()
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        output = proc.stdout or proc.stderr
        for line in output.splitlines():
            if "version" in line.lower():
                return line.strip()
        return output.splitlines()[0] if output else "R (version detected)"
    except Exception:
        return None


# --- High-Speed Persistent R Session (Positron Interaction Model) ---


def _r_string(value):
    return json.dumps(str(value), ensure_ascii=False)


_R_DRIVER = r"""
local({
    .job_dir <- NULL
    .sheet_count <- 0L
    .missing <- "__STATCRAFT_MISSING_7c59cb5e__"
    .hex <- function(value) {
        paste(format(charToRaw(enc2utf8(as.character(value)))), collapse="")
    }
    assign("statcraft_export", function(data, name="Exported_R_Data") {
        data <- as.data.frame(data)
        if (length(name) != 1L || is.na(name) || !nzchar(trimws(name))) name <- "Exported_R_Data"
        .sheet_count <<- .sheet_count + 1L
        path <- file.path(.job_dir, sprintf("sheet-%06d.csv", .sheet_count))
        if (any(vapply(data, function(col) any(as.character(col) == .missing, na.rm=TRUE), logical(1)))) {
            stop("A text value conflicts with the worksheet exchange missing-value marker.")
        }
        types <- vapply(data, function(col) {
            if (inherits(col, "Date")) "date"
            else if (inherits(col, "POSIXt")) "datetime"
            else if (is.numeric(col) && !is.complex(col)) "number"
            else "text"
        }, character(1))
        for (i in which(types == "datetime")) {
            data[[i]] <- format(data[[i]], "%Y-%m-%d %H:%M:%OS6", tz="UTC")
        }
        write.csv(data, path, row.names=FALSE, na=.missing, fileEncoding="UTF-8")
        writeLines(types, paste0(path, ".types"))
        writeLines(.hex(substr(name, 1L, 96L)), paste0(path, ".name"))
        invisible(data)
    }, envir=.GlobalEnv)
    assign(".statcraft_run", function(script, folder, worksheet, kinds, dates, missing, token, graphics, inspect) {
        .job_dir <<- folder
        .sheet_count <<- 0L
        old_device <- getOption("device")
        if (graphics) options(device=function(...) {
            png(file.path(folder, "plot-%03d.png"), width=1000, height=640, res=110)
        })
        failure <- tryCatch({
            if (nzchar(worksheet)) {
                data <- read.csv(worksheet, stringsAsFactors=FALSE, check.names=FALSE,
                    fileEncoding="UTF-8", na.strings=missing, colClasses=kinds)
                for (index in dates) {
                    if (all(is.na(data[[index]]) | data[[index]] == trunc(data[[index]]))) {
                        data[[index]] <- as.Date(data[[index]], origin="1899-12-30")
                    } else {
                        data[[index]] <- as.POSIXct(data[[index]] * 86400, origin="1899-12-30", tz="UTC")
                    }
                }
                assign("df", data, envir=.GlobalEnv)
                assign("worksheet", data, envir=.GlobalEnv)
            }
            for (expr in parse(file=script, encoding="UTF-8")) {
                value <- withVisible(eval(expr, envir=.GlobalEnv))
                if (value$visible) print(value$value)
            }
            ""
        }, error=function(e) conditionMessage(e))
        if (graphics) {
            try(grDevices::graphics.off(), silent=TRUE)
            options(device=old_device)
        }
        cat("\n")
        if (inspect) {
            objects <- head(setdiff(ls(envir=.GlobalEnv), "statcraft_export"), 300L)
            for (name in objects) try({
                if (bindingIsActive(name, .GlobalEnv)) next
                value <- get(name, envir=.GlobalEnv, inherits=FALSE)
                kind <- paste(class(value), collapse="/")
                shape <- if (is.null(dim(value))) as.character(length(value)) else paste(dim(value), collapse=" × ")
                preview <- if (is.atomic(value) && length(value) <= 5) paste(substr(value, 1L, 100L), collapse=", ") else ""
                cat(token, "ENV|", .hex(name), "|", .hex(kind), "|", .hex(shape), "|", .hex(preview), "\n", sep="")
            }, silent=TRUE)
        }
        cat(token, "DONE|", .hex(failure), "\n", sep="")
        flush(stdout())
        invisible(NULL)
    }, envir=.GlobalEnv)
})
"""


def _empty_result(error, *, elapsed=0.0):
    return {"success": False, "stdout": "", "stderr": error, "duration_ms": elapsed,
            "plot_path": None, "plot_paths": [], "exported_worksheets": {}, "environment": []}


class RPersistentSession:
    """Serialize jobs through one R process with an isolated output queue per process."""

    def __init__(self):
        self.process = None
        self._queue = None
        self._bound_key = None
        self._executable = None
        self._lock = threading.Lock()

    def _start_process(self, executable):
        name = Path(executable).stem.lower()
        if name == "rscript":
            command = [executable, "--vanilla", "-"]
        else:
            command = [executable, "--vanilla", "--slave"]
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        environment = os.environ.copy()
        if os.name == "nt":
            for variable in ("LC_ALL", "LC_COLLATE", "LC_CTYPE", "LC_MONETARY", "LC_TIME"):
                if environment.get(variable) == "C.UTF-8":
                    environment.pop(variable)
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                   errors="replace", bufsize=1, creationflags=flags,
                                   env=environment, cwd=get_r_session_dir())
        with _PROCESS_LOCK:
            _ACTIVE_PROCESSES.add(process)
        messages = queue.Queue()
        self.process, self._queue = process, messages
        self._executable = executable
        self._bound_key = None

        def read_output():
            try:
                for line in process.stdout:
                    messages.put(line)
            finally:
                process.stdout.close()
                process.wait()
                with _PROCESS_LOCK:
                    _ACTIVE_PROCESSES.discard(process)
                process.stdin.close()
                messages.put(None)

        threading.Thread(target=read_output, daemon=True).start()
        self._send(process, _R_DRIVER)
        return process, messages

    @staticmethod
    def _send(process, code):
        process.stdin.write(code + "\n")
        process.stdin.flush()

    def is_alive(self):
        return self.process is not None and self.process.poll() is None

    def interrupt(self, *, wait=False):
        """Stop the active process immediately without waiting on the job lock."""
        process = self.process
        if process is not None:
            _stop_process(process, wait=wait)

    def restart(self):
        self.interrupt()

    def execute_instant(self, code, worksheet=None, on_line_output=None, timeout=30.0,
                        *, capture_graphics=True, inspect=True, worksheet_key=None,
                        cancelled=None):
        start = time.perf_counter()
        with self._lock:
            if cancelled is not None and cancelled.is_set():
                return _empty_result("Execution stopped.")
            executable = find_interactive_r_executable()
            if not executable:
                return _empty_result("R executable not found. Choose an installed R executable in R Workbench.")
            try:
                if not self.is_alive() or self._executable != executable:
                    self.interrupt()
                    process, messages = self._start_process(executable)
                else:
                    process, messages = self.process, self._queue
                folder = Path(tempfile.mkdtemp(prefix="run-", dir=get_r_session_dir()))
                script = folder / "code.R"
                script.write_text(code, encoding="utf-8")
                worksheet_path = ""
                kinds = "NULL"
                dates = "NULL"
                missing = "__SC_NA_" + uuid.uuid4().hex
                if worksheet is not None and (worksheet_key is None or worksheet_key != self._bound_key):
                    worksheet_path = (folder / "worksheet.csv").as_posix()
                    export_worksheet_to_r_dataframe_csv(worksheet, worksheet_path, missing)
                    kinds = "c(" + ",".join(
                        '"character"' if col.kind == "text" else '"numeric"' for col in worksheet.columns
                    ) + ")"
                    dates = "c(" + ",".join(
                        str(i) for i, col in enumerate(worksheet.columns, 1) if col.kind == "date"
                    ) + ")"
                token = "<<<SC_" + uuid.uuid4().hex + ">>>"
                args = [_r_string(script.as_posix()), _r_string(folder.as_posix()), _r_string(worksheet_path),
                        kinds, dates, _r_string(missing), _r_string(token),
                        "TRUE" if capture_graphics else "FALSE", "TRUE" if inspect else "FALSE"]
                self._send(process, ".statcraft_run(" + ",".join(args) + ")")
            except (OSError, ValueError) as exc:
                self.interrupt()
                return _empty_result(f"Could not start the R job. {exc}")
            output = []
            environment = []
            deadline = time.monotonic() + timeout if timeout is not None else math.inf
            failure = "R exited before completing the command."
            finished = False
            output_size = 0
            while True:
                if cancelled is not None and cancelled.is_set():
                    self.interrupt()
                    failure = "Execution stopped. Run again to start a fresh R session."
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.interrupt()
                    failure = f"R execution timed out after {timeout:g} seconds."
                    break
                try:
                    line = messages.get(timeout=min(remaining, .1))
                except queue.Empty:
                    continue
                if line is None:
                    break
                if line.startswith(token):
                    record = line[len(token):].rstrip("\r\n")
                    fields = record.split("|")
                    try:
                        values = [bytes.fromhex(field).decode("utf-8", "replace") for field in fields[1:]]
                    except ValueError:
                        continue
                    if fields[0] == "DONE" and len(values) == 1:
                        failure, finished = values[0], True
                        break
                    if fields[0] == "ENV" and len(values) == 4:
                        environment.append(dict(zip(("name", "type", "length", "value"), values)))
                    continue
                if output_size < 1_000_000:
                    output.append(line)
                    output_size += len(line)
                    if on_line_output:
                        on_line_output(line)
            if not finished:
                self.interrupt(wait=True)
            if finished and worksheet_path:
                self._bound_key = worksheet_key if not failure else None
            for temporary in (script, folder / "worksheet.csv"):
                temporary.unlink(missing_ok=True)
            exported = {}
            for path in sorted(folder.glob("sheet-*.csv")):
                name_path = Path(str(path) + ".name")
                try:
                    if finished and not failure:
                        name = bytes.fromhex(name_path.read_text(encoding="ascii")).decode("utf-8")
                        exported[name] = parse_csv_to_worksheet_dict(path)
                except (OSError, ValueError) as exc:
                    failure = f"Could not import a worksheet from R. {exc}"
                finally:
                    name_path.unlink(missing_ok=True)
                    path.unlink(missing_ok=True)
                    Path(str(path) + ".types").unlink(missing_ok=True)
            plots = [str(path) for path in sorted(folder.glob("plot-*.png")) if path.stat().st_size]
            if not plots:
                folder.rmdir()
            return {"success": finished and not failure, "stdout": "".join(output).rstrip("\n"),
                    "stderr": failure, "duration_ms": (time.perf_counter() - start) * 1000,
                    "plot_path": plots[-1] if plots else None, "plot_paths": plots,
                    "exported_worksheets": exported, "environment": environment}


def get_persistent_r_session():
    global _PERSISTENT_SESSION
    with _SESSION_LOCK:
        if _PERSISTENT_SESSION is None:
            _PERSISTENT_SESSION = RPersistentSession()
        return _PERSISTENT_SESSION


def export_worksheet_to_r_dataframe_csv(worksheet, dest_path: str, missing="NA") -> None:
    """Export a StatCraft Worksheet to a clean CSV format suitable for R's read.csv()."""
    with open(dest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        headers = [col.name for col in worksheet.columns]
        writer.writerow(headers)

        num_rows = worksheet.row_count
        for r in range(num_rows):
            row_data = []
            for col in worksheet.columns:
                val = col.values[r] if r < len(col.values) else None
                if val is None:
                    row_data.append(missing)
                else:
                    row_data.append(val)
            writer.writerow(row_data)


def parse_csv_to_worksheet_dict(csv_path: Path) -> Dict[str, Any]:
    """Recover exported column types without treating text such as NA as missing."""
    from datetime import datetime
    from .model import datetime_to_serial
    from .io import MAX_CELLS

    type_path = Path(str(csv_path) + ".types")
    types = type_path.read_text(encoding="utf-8").splitlines() if type_path.exists() else []
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        headers = next(reader, [])
        rows = []
        for row in reader:
            if len(row) != len(headers) or (len(rows) + 1) * len(headers) > MAX_CELLS:
                raise ValueError("R table dimensions exceed import limits.")
            rows.append(row)
    columns = []
    for index, header in enumerate(headers):
        values = [row[index] for row in rows]
        values = [None if value == "__STATCRAFT_MISSING_7c59cb5e__" else value for value in values]
        kind = types[index] if index < len(types) else "text"
        if kind == "number":
            values = [float(value) if value is not None else None for value in values]
            values = [value if value is None or math.isfinite(value) else None for value in values]
        elif kind in ("date", "datetime"):
            values = [datetime_to_serial(datetime.fromisoformat(value)) if value is not None else None for value in values]
            kind = "date"
        columns.append({"name": header, "kind": kind, "values": values})
    return {"columns": columns, "row_count": len(rows)}


def execute_r_code(code, worksheet=None, timeout=60, capture_graphics=True, persist_session=True,
                   on_line_output=None, *, worksheet_key=None, inspect=True, cancelled=None):
    """Run an R command, optionally retaining objects for the next command."""
    session = get_persistent_r_session() if persist_session else RPersistentSession()
    try:
        return session.execute_instant(code, worksheet, on_line_output, timeout,
                                       capture_graphics=capture_graphics, inspect=inspect,
                                       worksheet_key=worksheet_key, cancelled=cancelled)
    finally:
        if not persist_session:
            session.interrupt(wait=True)


# --- Automatic CRAN / WinGet Installer Helper ---


def check_winget_available() -> bool:
    """Return True if Microsoft WinGet CLI is installed and responsive."""
    if platform.system() != "Windows":
        return False
    return shutil.which("winget") is not None


def get_cran_installer_url() -> str:
    """Return the official direct download URL for the latest CRAN R release on Windows."""
    # Standard CRAN release redirection URL
    return "https://cloud.r-project.org/bin/windows/base/release.html"


def install_r_via_winget(progress_callback: Optional[Callable[[str], None]] = None) -> bool:
    """Trigger silent installation of R using WinGet."""
    if not check_winget_available():
        return False
    try:
        if progress_callback:
            progress_callback("Running 'winget install RProject.R' in background...")
        proc = subprocess.run(
            ["winget", "install", "--id", "RProject.R", "--source", "winget", "--accept-source-agreements", "--accept-package-agreements", "--silent"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300,
        )
        return proc.returncode == 0
    except Exception:
        return False


def get_r_help_text(topic: str) -> str:
    """Fetch formatted help text for a given R topic (e.g. 'lm', 'plot', 'summary')."""
    clean_topic = re.sub(r'^[?]', '', topic.strip())
    if not clean_topic or not is_r_available():
        return f"Help unavailable: R is not active or invalid topic '{clean_topic}'."

    code = """
local({
    topic <- TOPIC
    rd <- utils::help(topic)
    if (!length(rd)) cat("No documentation found for ", topic, ".", sep="")
    else tools::Rd2txt(utils:::.getHelpFile(rd), out=stdout())
})
""".replace("TOPIC", _r_string(clean_topic))
    res = execute_r_code(code, persist_session=False, capture_graphics=False, inspect=False)
    out = re.sub(r".\x08", "", res.get("stdout", "")).strip()
    return out if out else f"No documentation found for '{clean_topic}'."


def download_and_install_r_direct(progress_callback: Optional[Callable[[str], None]] = None) -> bool:
    """Download official Windows R installer directly from CRAN and run setup."""
    import tempfile
    import urllib.request

    installer_url = "https://cloud.r-project.org/bin/windows/base/R-4.4.2-win.exe"
    tmp_exe = Path(tempfile.gettempdir()) / "R-Setup-Latest.exe"

    if progress_callback:
        progress_callback("Connecting to official CRAN repository (cloud.r-project.org)...")

    try:
        def reporthook(blocknum, blocksize, totalsize):
            if totalsize > 0 and progress_callback and blocknum % 100 == 0:
                percent = min(100, int(blocknum * blocksize * 100 / totalsize))
                mb = round(blocknum * blocksize / (1024 * 1024), 1)
                total_mb = round(totalsize / (1024 * 1024), 1)
                progress_callback(f"Downloading R ({percent}% - {mb} MB of {total_mb} MB)...")

        urllib.request.urlretrieve(installer_url, str(tmp_exe), reporthook=reporthook)

        if progress_callback:
            progress_callback("Launching R installer...")

        proc = subprocess.run([str(tmp_exe), "/SILENT"], timeout=300)
        return proc.returncode == 0
    except Exception as e:
        if progress_callback:
            progress_callback(f"Direct download error: {e}")
        return False
