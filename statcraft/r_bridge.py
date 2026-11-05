"""R Language Bridge for StatCraft.

Provides clean, air-gapped integration with R:
- Auto-discovers local R installation (PATH, Program Files, registry, Homebrew, /usr/bin)
- Executes R scripts and REPL expressions in persistent or isolated background subprocesses
- High-speed bi-directional data exchange between StatCraft Worksheets and R data.frames
- Automatically exposes `statcraft_export(data, name)` in R to push data back into StatCraft worksheets
- Captures stdout, stderr, execution duration, and generated graphics (base R, ggplot2, lattice)
- Inspects active environment objects for the Positron-style Environment Inspector
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

_SESSION_DIR: Optional[Path] = None


def get_r_session_dir() -> Path:
    """Return the persistent directory for the active StatCraft session."""
    global _SESSION_DIR
    if _SESSION_DIR is None or not _SESSION_DIR.exists():
        base = Path(tempfile.gettempdir()) / f"statcraft_r_session_{os.getpid()}"
        base.mkdir(parents=True, exist_ok=True)
        _SESSION_DIR = base
    return _SESSION_DIR


def reset_r_session() -> None:
    """Clear persistent workspace memory and cached files."""
    s_dir = get_r_session_dir()
    for f in s_dir.glob("*"):
        try:
            if f.is_file():
                f.unlink()
        except OSError:
            pass


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
                subdirs = sorted(r_dir.glob("R-*"), reverse=True)
                for sd in subdirs:
                    exe = sd / "bin" / "Rscript.exe"
                    if exe.is_file():
                        return str(exe)
                    exe_x64 = sd / "bin" / "x64" / "Rscript.exe"
                    if exe_x64.is_file():
                        return str(exe_x64)

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


def parse_csv_to_worksheet_dict(csv_path: Path) -> Dict[str, Any]:
    """Parse a CSV exported from R into columns dictionary."""
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        headers = next(reader, [])
        rows = list(reader)

    cols: List[Dict[str, Any]] = []
    for c_idx, h in enumerate(headers):
        vals = [r[c_idx] if c_idx < len(r) else "" for r in rows]
        # Infer kind
        numeric_count = 0
        total_valid = 0
        converted_vals = []
        for v in vals:
            if v == "" or v.upper() == "NA":
                converted_vals.append(None)
            else:
                total_valid += 1
                try:
                    fval = float(v)
                    converted_vals.append(int(fval) if fval.is_integer() else fval)
                    numeric_count += 1
                except ValueError:
                    converted_vals.append(v)

        kind = "number" if total_valid > 0 and numeric_count == total_valid else "text"
        cols.append({"name": h, "kind": kind, "values": converted_vals})

    return {"columns": cols, "row_count": len(rows)}


def execute_r_code(
    code: str,
    worksheet=None,
    timeout: int = 60,
    capture_graphics: bool = True,
    persist_session: bool = True,
) -> Dict[str, Any]:
    """Execute arbitrary R code in background subprocess.
    
    Features:
    - Pre-injects `df` and `worksheet` with active StatCraft data
    - Injects `statcraft_export(data, name)` for pushing dataframes back into StatCraft
    - Restores and saves session variables in `.statcraft_workspace.RData`
    - Gathers environment objects and dimensions for the Positron Inspector
    """
    exe = find_r_executable()
    if not exe:
        return {
            "success": False,
            "stdout": "",
            "stderr": "R executable (Rscript) not found on system. Please install R from https://cran.r-project.org/.",
            "plot_path": None,
            "exported_worksheets": {},
            "environment": [],
            "return_code": -1,
            "error": "R_NOT_FOUND",
        }

    s_dir = get_r_session_dir()
    script_path = s_dir / "active_script.R"
    plot_path = s_dir / "statcraft_plot.png"
    csv_data_path = s_dir / "statcraft_active_data.csv"
    rdata_path = s_dir / ".statcraft_workspace.RData"
    env_csv_path = s_dir / ".sc_env.csv"

    # Clean previous plot and export CSVs
    if plot_path.exists():
        try:
            plot_path.unlink()
        except OSError:
            pass
    for old_exp in s_dir.glob(".sc_export_*.csv"):
        try:
            old_exp.unlink()
        except OSError:
            pass

    r_preamble: List[str] = [
        "# --- StatCraft R Environment Preamble ---",
        "options(warn=1, digits=5, width=100)",
    ]

    # Load persistent session state if available
    if persist_session:
        rdata_escaped = str(rdata_path).replace("\\", "/")
        r_preamble.append(
            f'if (file.exists("{rdata_escaped}")) {{ try(load("{rdata_escaped}"), silent=TRUE) }}'
        )

    # Inject StatCraft export helper
    r_preamble.extend([
        "statcraft_export <- function(data, name='R_Output') {",
        "    f_name <- paste0('.sc_export_', gsub('[^A-Za-z0-9_]', '_', name), '.csv')",
        "    write.csv(data, file=f_name, row.names=FALSE)",
        "    invisible(data)",
        "}",
        "statcraft_save <- statcraft_export",
    ])

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

    # Postamble: inspect objects and save session state
    r_postamble: List[str] = []
    if capture_graphics:
        r_postamble.append("suppressMessages(try(invisible(dev.off()), silent=TRUE))")

    # Environment Inspector inspection script (pure base R, zero package dependencies)
    env_escaped = str(env_csv_path).replace("\\", "/")
    r_postamble.extend([
        ".sc_objs <- ls(all.names=FALSE)",
        ".sc_lines <- c('name,type,dim,preview')",
        "for (.o in .sc_objs) {",
        "    if (!grepl('^\\\\.sc_', .o) && !(.o %in% c('statcraft_export', 'statcraft_save'))) {",
        "        .val <- get(.o)",
        "        .cl <- class(.val)[1]",
        "        .d <- dim(.val)",
        "        .d_str <- if (!is.null(.d)) paste0(.d[1], 'x', .d[2]) else paste0('len: ', length(.val))",
        "        .prev <- gsub('[,\\\"\\r\\n]', ' ', paste(head(as.character(.val), 3), collapse='; '))",
        "        .sc_lines <- c(.sc_lines, paste(paste0('\"', .o, '\"'), paste0('\"', .cl, '\"'), paste0('\"', .d_str, '\"'), paste0('\"', .prev, '\"'), sep=','))",
        "    }",
        "}",
        f'writeLines(.sc_lines, "{env_escaped}")',
    ])

    if persist_session:
        rdata_escaped = str(rdata_path).replace("\\", "/")
        r_postamble.append(f'try(save.image("{rdata_escaped}"), silent=TRUE)')

    full_script = "\n".join(r_preamble) + "\n\n" + code + "\n\n" + "\n".join(r_postamble) + "\n"
    script_path.write_text(full_script, encoding="utf-8")

    try:
        proc = subprocess.run(
            [exe, "--vanilla", str(script_path)],
            cwd=str(s_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        stdout = proc.stdout
        stderr = proc.stderr
        returncode = proc.returncode

        # Check plot
        saved_plot_path = None
        if plot_path.exists() and plot_path.stat().st_size > 1000:
            cache_dir = Path(tempfile.gettempdir()) / "statcraft_r_plots"
            cache_dir.mkdir(parents=True, exist_ok=True)
            target_plot = cache_dir / f"r_plot_{os.getpid()}_{plot_path.stat().st_mtime_ns}.png"
            shutil.copy2(str(plot_path), str(target_plot))
            saved_plot_path = str(target_plot)

        # Parse any exported worksheets
        exported_worksheets: Dict[str, Any] = {}
        for exp_csv in s_dir.glob(".sc_export_*.csv"):
            name = exp_csv.stem.replace(".sc_export_", "")
            try:
                exported_worksheets[name] = parse_csv_to_worksheet_dict(exp_csv)
            except Exception:
                pass

        # Parse environment objects
        env_objects: List[Dict[str, str]] = []
        if env_csv_path.exists():
            try:
                with open(env_csv_path, "r", encoding="utf-8", errors="replace") as f:
                    rdr = csv.DictReader(f)
                    for row in rdr:
                        env_objects.append(row)
            except Exception:
                pass

        return {
            "success": returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "plot_path": saved_plot_path,
            "exported_worksheets": exported_worksheets,
            "environment": env_objects,
            "return_code": returncode,
            "error": None if returncode == 0 else (stderr.strip() or f"Exited with code {returncode}"),
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"R script execution timed out after {timeout} seconds.",
            "plot_path": None,
            "exported_worksheets": {},
            "environment": [],
            "return_code": -2,
            "error": "TIMEOUT",
        }
    except Exception as exc:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(exc),
            "plot_path": None,
            "exported_worksheets": {},
            "environment": [],
            "return_code": -3,
            "error": str(exc),
        }
