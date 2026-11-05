"""StatCraft Automated GitHub Release Publisher.

Builds, signs, and automatically uploads release binaries to GitHub Releases
via the GitHub REST API using saved git credentials or GITHUB_TOKEN.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_REPO = "SkinnDeep/StatCraft"
DEFAULT_CERT_THUMBPRINT = "BF26A8FE2AFB6218CDC2E2CB90CE9EF6DA8E89C5"


def get_current_version(repo_root: Path) -> str:
    """Read STATCRAFT_VERSION from statcraft/updater.py."""
    updater_file = repo_root / "statcraft" / "updater.py"
    if updater_file.exists():
        text = updater_file.read_text(encoding="utf-8")
        match = re.search(r'STATCRAFT_VERSION\s*=\s*["\']([^"\']+)["\']', text)
        if match:
            return match.group(1).strip()
    return "108.0.0"


def get_github_token() -> str | None:
    """Retrieve GitHub Personal Access Token from environment or Git Credential Manager."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()

    # Query Git Credential Helper
    try:
        proc = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n",
            capture_output=True,
            text=True,
            timeout=5
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if line.startswith("password="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass

    return None


def run_cmd(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and stream output."""
    print(f"--> Executing: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {proc.returncode}: {' '.join(cmd)}")
    return proc


def sign_binary_if_possible(exe_path: Path, thumbprint: str = DEFAULT_CERT_THUMBPRINT) -> bool:
    """Sign a Windows executable using PowerShell Set-AuthenticodeSignature if cert is present."""
    if sys.platform != "win32" or not exe_path.exists():
        return False

    clean_path = str(exe_path).replace("'", "''")
    ps_script = (
        f"$cert = Get-Item 'Cert:\\CurrentUser\\My\\{thumbprint}' -ErrorAction SilentlyContinue; "
        f"if ($cert) {{ "
        f"  Set-AuthenticodeSignature -FilePath '{clean_path}' -Certificate $cert | Out-Null; "
        f"  Write-Output 'SIGNED'; "
        f"}} else {{ "
        f"  Write-Output 'NO_CERT'; "
        f"}}"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=30
        )
        if "SIGNED" in proc.stdout:
            print(f"  [OK] Authenticode signature applied to {exe_path.name}")
            return True
        else:
            print(f"  [!] Certificate {thumbprint} not found in Cert:\\CurrentUser\\My. Binary left unsigned.")
            return False
    except Exception as exc:
        print(f"  [!] Signing failed: {exc}")
        return False


def build_binaries(repo_root: Path, version: str) -> tuple[Path, Path]:
    """Build StatCraft.exe and StatCraft-Setup.exe using PyInstaller."""
    print("\n=== Building Binaries with PyInstaller ===")
    
    # Locate python executable
    python_exe = sys.executable

    # Output directory
    candidates = [
        repo_root / "outputs",
        repo_root.parent / "outputs",
        repo_root.parent.parent / "outputs",
    ]
    outputs_dir = next((d for d in candidates if d.exists()), repo_root / "outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)

    dist_app = repo_root / "dist" / "app"
    work_app = repo_root / "build" / "app"
    dist_setup = repo_root / "dist" / "setup"
    work_setup = repo_root / "build" / "setup"

    # Step 1: Main Application
    print("Building StatCraft main application binary...")
    run_cmd([
        python_exe, "-m", "PyInstaller",
        "--noconfirm",
        "--distpath", str(dist_app),
        "--workpath", str(work_app),
        str(repo_root / "StatCraft.spec")
    ], cwd=repo_root)

    app_exe = dist_app / "StatCraft.exe"
    if not app_exe.exists():
        raise FileNotFoundError(f"Expected binary not found: {app_exe}")

    versioned_app_name = f"StatCraft-v{version}-Windows-x64.exe"
    final_app_exe = outputs_dir / versioned_app_name
    final_app_exe.write_bytes(app_exe.read_bytes())
    (outputs_dir / "StatCraft.exe").write_bytes(app_exe.read_bytes())
    sign_binary_if_possible(final_app_exe)
    sign_binary_if_possible(outputs_dir / "StatCraft.exe")

    # Step 2: Setup Bootstrapper
    print("\nBuilding StatCraft Setup web installer...")
    run_cmd([
        python_exe, "-m", "PyInstaller",
        "--noconfirm",
        "--distpath", str(dist_setup),
        "--workpath", str(work_setup),
        str(repo_root / "installer.spec")
    ], cwd=repo_root)

    setup_exe = dist_setup / "StatCraft-Setup.exe"
    if not setup_exe.exists():
        raise FileNotFoundError(f"Expected setup binary not found: {setup_exe}")

    versioned_setup_name = f"StatCraft-Setup-v{version}-Windows-x64.exe"
    final_setup_exe = outputs_dir / versioned_setup_name
    final_setup_exe.write_bytes(setup_exe.read_bytes())
    (outputs_dir / "StatCraft-Setup.exe").write_bytes(setup_exe.read_bytes())
    sign_binary_if_possible(final_setup_exe)
    sign_binary_if_possible(outputs_dir / "StatCraft-Setup.exe")

    return final_setup_exe, final_app_exe


def get_or_create_release(token: str, repo: str, tag: str, name: str, body: str) -> dict:
    """Fetch existing GitHub release for tag, or create one if it doesn't exist."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "StatCraft-Release-Publisher"
    }

    get_url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    req = urllib.request.Request(get_url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"Found existing GitHub release for {tag} (ID: {data['id']})")
            return data
    except urllib.error.HTTPError as err:
        if err.code != 404:
            raise

    # Create new release
    print(f"Creating new GitHub release for {tag}...")
    create_url = f"https://api.github.com/repos/{repo}/releases"
    payload = {
        "tag_name": tag,
        "name": name,
        "body": body,
        "draft": False,
        "prerelease": False
    }
    create_req = urllib.request.Request(
        create_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    with urllib.request.urlopen(create_req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"Created new GitHub release for {tag} (ID: {data['id']})")
        return data


def upload_asset(token: str, upload_url_tmpl: str, file_path: Path, asset_name: str) -> dict:
    """Upload or replace a binary asset in a GitHub release."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "StatCraft-Release-Publisher"
    }

    size = file_path.stat().st_size
    print(f"Uploading {asset_name} ({size / (1024*1024):.2f} MB)...")

    clean_upload_url = upload_url_tmpl.split("{")[0]
    encoded_name = urllib.parse.quote(asset_name)
    target_url = f"{clean_upload_url}?name={encoded_name}"

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    upload_headers = {
        **headers,
        "Content-Type": "application/octet-stream",
        "Content-Length": str(size),
    }

    req = urllib.request.Request(target_url, data=file_bytes, headers=upload_headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print(f"  [OK] Successfully uploaded {res['name']} (Asset ID: {res['id']})")
        return res


def publish_release(
    repo: str = DEFAULT_REPO,
    custom_version: str | None = None,
    skip_build: bool = False,
    notes: str | None = None
) -> None:
    """Main orchestration function to build and publish a release."""
    current_dir = Path(__file__).resolve().parent
    repo_root = current_dir if (current_dir / "statcraft").exists() else current_dir.parent.parent
    version = custom_version or get_current_version(repo_root)
    tag = f"v{version}"

    token = get_github_token()
    if not token:
        print("\n[ERROR] GitHub authentication token not found.")
        print("Please set the GITHUB_TOKEN environment variable or login via 'git credential fill'.")
        sys.exit(1)

    print(f"==================================================")
    print(f" StatCraft Release Publisher - {tag}")
    print(f" Repository: {repo}")
    print(f"==================================================")

    candidates = [
        repo_root / "outputs",
        repo_root.parent / "outputs",
        repo_root.parent.parent / "outputs",
    ]
    outputs_dir = next((d for d in candidates if d.exists()), repo_root / "outputs")
    setup_file = outputs_dir / f"StatCraft-Setup-v{version}-Windows-x64.exe"
    app_file = outputs_dir / f"StatCraft-v{version}-Windows-x64.exe"

    if skip_build:
        print("\nSkipping PyInstaller build (using existing output files)...")
        if not setup_file.exists() or not app_file.exists():
            raise FileNotFoundError(f"Missing required release binaries in {outputs_dir}. Run without --skip-build.")
    else:
        setup_file, app_file = build_binaries(repo_root, version)

    # Prepare release release notes
    release_name = f"StatCraft v{version}"
    release_body = notes or (
        f"### StatCraft v{version} Production Release\n\n"
        f"- **Installer**: `StatCraft-Setup-v{version}-Windows-x64.exe` (Lightweight web bootstrapper with background download)\n"
        f"- **Application**: `StatCraft-v{version}-Windows-x64.exe` (Full portable standalone package)\n\n"
        f"#### What's New in v{version}:\n"
        f"- **D-Optimal Custom Design & Evaluation**: Coordinate-exchange optimal design algorithm, D/A/G-efficiency diagnostics, and JMP-style Color Map on Correlations\n"
        f"- **CART® Partition Trees**: Interactive decision trees with hierarchical split diagrams, variable importance ranking, and session reporting\n"
        f"- **Wheeler EMP Gauge Study**: Evaluating the Measurement Process classification spectrum (First–Fourth Class), ICC, signal attenuation, and shift detection curves\n"
        f"- **Definitive Screening (DSD) & ALT**: Orthogonal designs with stepwise heredity selection, and Accelerated Life Testing with right-censored Arrhenius/IPL models\n"
        f"- **RSM Surface & Contour Plots**: Fixed factor coordinate dereferencing and rendering for native MPX project files\n"
        f"- **Unified Report Output**: Streamlined single Report workbook matching Minitab with Navigator navigation to individual table cards\n"
        f"- **PE Metadata & Authenticode**: Embedded PE version resource and Windows application manifests for SmartScreen trust\n"
    )

    # Connect to GitHub Release
    release = get_or_create_release(token, repo, tag, release_name, release_body)
    upload_url_tmpl = release["upload_url"]

    upload_list = [(setup_file, setup_file.name), (app_file, app_file.name)]
    mac_file = outputs_dir / f"StatCraft-v{version}-macOS.zip"
    linux_file = outputs_dir / f"StatCraft-v{version}-Linux-x86_64.tar.gz"
    if mac_file.exists():
        upload_list.append((mac_file, mac_file.name))
    if linux_file.exists():
        upload_list.append((linux_file, linux_file.name))

    # Delete existing assets with the same name to prevent upload conflicts
    existing_assets = {a["name"]: a["id"] for a in release.get("assets", [])}
    for file_to_upload, asset_name in upload_list:
        if asset_name in existing_assets:
            asset_id = existing_assets[asset_name]
            print(f"Removing old asset {asset_name} (ID {asset_id})...")
            del_url = f"https://api.github.com/repos/{repo}/releases/assets/{asset_id}"
            del_req = urllib.request.Request(
                del_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "StatCraft-Release-Publisher"
                },
                method="DELETE"
            )
            with urllib.request.urlopen(del_req) as del_resp:
                print(f"  [OK] Removed old asset (Status {del_resp.status})")

    # Upload fresh binaries
    for file_to_upload, asset_name in upload_list:
        upload_asset(token, upload_url_tmpl, file_to_upload, asset_name)

    # Also copy to Downloads folder for convenient local testing
    downloads_dir = Path.home() / "Downloads"
    if downloads_dir.exists():
        try:
            (downloads_dir / setup_file.name).write_bytes(setup_file.read_bytes())
            (downloads_dir / app_file.name).write_bytes(app_file.read_bytes())
            print(f"\n[OK] Copied latest binaries to {downloads_dir}")
        except Exception:
            pass

    print(f"\n==================================================")
    print(f" [SUCCESS] Release {tag} is live on GitHub!")
    print(f" URL: https://github.com/{repo}/releases/tag/{tag}")
    print(f"==================================================")


def main():
    parser = argparse.ArgumentParser(description="Build and publish StatCraft releases to GitHub.")
    parser.add_argument("--version", help="Override version tag (e.g. 104.0.0)")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repository (owner/repo)")
    parser.add_argument("--skip-build", action="store_true", help="Skip packaging step and upload existing binaries")
    parser.add_argument("--notes", help="Custom markdown release notes")

    args = parser.parse_args()
    publish_release(
        repo=args.repo,
        custom_version=args.version,
        skip_build=args.skip_build,
        notes=args.notes
    )


if __name__ == "__main__":
    main()
