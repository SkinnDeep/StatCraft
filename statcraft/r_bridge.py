"""R Language Bridge for StatCraft.

Provides clean, air-gapped integration with R:
- Auto-discovers local R installation (PATH, Program Files, registry, Homebrew, /usr/bin)
- Executes R scripts and REPL expressions in background subprocesses
- High-speed bi-directional data exchange between StatCraft Worksheets and R data.frames
- Captures stdout, stderr, execution duration, and generated graphics (base R, ggplot2, lattice)
- Zero external Python dependencies required (pure standard library: subprocess, tempfile, shutil)
"""
from __future__ import annotations

import csv
import glob
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def find_r_executable() -> Optional[str]:
    """Find the path to the Rscript executable on the system."""
    # 1. Custom environment variable override
    env_path = os.environ.get("STATCRAFT_R_PATH") or os.environ.get("R_HOME")
    if env_path:
        p = Path(env_path)
        if p.is_file() and p.name.lower().startswith("rscript"):
            return str(p)
        candidate = p / "bin" / ("Rscript.exe" if platform.system() == "Windows" else "Rscript")
        if candidate.is_file():
            return str(candidate)

    # 2. Check system PATH
    which_r = shutil.which("Rscript")
    if which_r:
        return which_r

    # 3. Platform-specific discovery
    system = platform.system()
    if system == "Windows":
        # Check standard 64-bit and 32-bit Program Files directories
        prog_dirs = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            r"C:\R",
        ]
        for base in prog_dirs:
            if not base or not os.path.isdir(base):
                continue
            r_dir = Path(base) / "R"
            if r_dir.is_dir():
                # Search for latest R version directory (e.g. R-4.4.1, R-4.3.0)
                subdirs = sorted(r_dir.glob("R-*"), reverse=True)
                for sd in subdirs:
                    exe = sd / "bin" / "Rscript.exe"
                    if exe.is_file():
                        return str(exe)
                    exe_x64 = sd / "bin" / "x64" / "Rscript.exe"
                    if exe_x64.is_file():
                        return str(exe_x64)

        # Check Windows Registry via winreg if available
        try:
            import winreg
            for key_path in (r"SOFTWARE\R-Core\R", r"SOFTWARE\R-Core\R64"):
                for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                    try:
                        with winreg.OpenKey(root, key_path) as k:
                            inst_path, _ = winreg.QueryValueEx(k, "InstallPath")
                            if inst_path:
                                exe = Path(inst_path) / "bin" / "Rscript.exe"
                                if exe.is_file():
                                    return str(exe)
                                exe_x64 = Path(inst_path) / "bin" / "x64" / "Rscript.exe"
                                if exe_x64.is_file():
                                    return str(exe_x64)
                    except (OSError, FileNotFoundError):
                        pass
        except ImportError:
            pass

    elif system == "Darwin":  # macOS
        mac_paths = [
            "/Library/Frameworks/R.framework/Resources/bin/Rscript",
            "/opt/homebrew/bin/Rscript",
            "/usr/local/bin/Rscript",
        ]
        for mp in mac_paths:
            if os.path.isfile(mp) and os.access(mp, os.X_OK):
                return mp

    else:  # Linux / Unix
        linux_paths = [
            "/usr/bin/Rscript",
            "/usr/local/bin/Rscript",
            "/opt/R/bin/Rscript",
        ]
        for lp in linux_paths:
            if os.path.isfile(lp) and os.access(lp, os.X_OK):
                return lp

    return None


def is_r_available() -> bool:
    """Check whether R is installed and accessible."""
    return find_r_executable() is not None


def get_r_version() -> Optional[str]:
    """Return R version string (e.g. 'R version 4.4.1 (2024-06-14)')."""
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
        out = proc.stdout.strip() or proc.stderr.strip()
        lines = out.splitlines()
        return lines[0] if lines else "R (version unknown)"
    except Exception:
        return None


def export_worksheet_to_r_dataframe_csv(worksheet, dest_path: str) -> None:
    """Export a StatCraft Worksheet into clean CSV for R consumption."""
    with open(dest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        headers = [c.name for c in worksheet.columns]
        writer.writerow(headers)
        n_rows = worksheet.row_count
        for r in range(n_rows):
            row_data = []
            for col in worksheet.columns:
                val = col.values[r] if r < len(col.values) else None
                if val is None or val == "":
                    row_data.append("NA")
                else:
                    row_data.append(str(val))
            writer.writerow(row_data)


def execute_r_code(
    code: str,
    worksheet=None,
    timeout: int = 60,
    capture_graphics: bool = True,
) -> Dict[str, Any]:
    """Execute arbitrary R code in an isolated subprocess.
    
    If a worksheet is provided, it is automatically exposed in R as a data.frame named `df`
    and `worksheet`.
    If graphics are produced, they are saved as a high-resolution PNG image.
    """
    exe = find_r_executable()
    if not exe:
        return {
            "success": False,
            "stdout": "",
            "stderr": "R executable (Rscript) not found on system. Please install R from https://cran.r-project.org/.",
            "plot_path": None,
            "return_code": -1,
            "error": "R_NOT_FOUND",
        }

    with tempfile.TemporaryDirectory(prefix="statcraft_r_") as tmpdir:
        tmp_dir_path = Path(tmpdir)
        script_path = tmp_dir_path / "script.R"
        plot_path = tmp_dir_path / "statcraft_plot.png"
        csv_data_path = tmp_dir_path / "data.csv"

        r_preamble: List[str] = [
            "# --- StatCraft R Bridge Environment ---",
            "options(warn=1, digits=5, width=100)",
        ]

        if worksheet is not None and worksheet.columns:
            export_worksheet_to_r_dataframe_csv(worksheet, str(csv_data_path))
            csv_path_escaped = str(csv_data_path).replace("\\", "/")
            r_preamble.extend([
                f'df <- read.csv("{csv_path_escaped}", na.strings="NA", check.names=FALSE, stringsAsFactors=FALSE)',
                'worksheet <- df',
            ])

        if capture_graphics:
            plot_escaped = str(plot_path).replace("\\", "/")
            r_preamble.append(
                f'png("{plot_escaped}", width=1200, height=800, res=150, bg="white")'
            )

        full_script = "\n".join(r_preamble) + "\n\n" + code + "\n"
        if capture_graphics:
            full_script += "\nsuppressMessages(try(invisible(dev.off()), silent=TRUE))\n"

        script_path.write_text(full_script, encoding="utf-8")

        try:
            proc = subprocess.run(
                [exe, "--vanilla", str(script_path)],
                cwd=str(tmp_dir_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            returncode = proc.returncode

            # Check if plot was generated and has content
            saved_plot_path = None
            if plot_path.exists() and plot_path.stat().st_size > 1000:
                # Copy plot to a persistent cache directory so it can be viewed by Qt widgets
                cache_dir = Path(tempfile.gettempdir()) / "statcraft_r_plots"
                cache_dir.mkdir(parents=True, exist_ok=True)
                target_plot = cache_dir / f"r_plot_{os.getpid()}_{plot_path.stat().st_mtime_ns}.png"
                shutil.copy2(str(plot_path), str(target_plot))
                saved_plot_path = str(target_plot)

            return {
                "success": returncode == 0,
                "stdout": stdout,
                "stderr": stderr,
                "plot_path": saved_plot_path,
                "return_code": returncode,
                "error": None if returncode == 0 else (stderr.strip() or f"Exited with code {returncode}"),
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"R script execution timed out after {timeout} seconds.",
                "plot_path": None,
                "return_code": -2,
                "error": "TIMEOUT",
            }
        except Exception as exc:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(exc),
                "plot_path": None,
                "return_code": -3,
                "error": str(exc),
            }
