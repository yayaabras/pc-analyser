"""
build_windows.py — build pc-analyser.exe for Windows and create a Desktop shortcut.

Run this from WSL:
    python build_windows.py

It uses PowerShell to:
1. Install Python on Windows if needed
2. Install dependencies
3. Build pc-analyser.exe with PyInstaller
4. Create a Desktop shortcut pointing to the exe
"""

import os
import subprocess
import sys

PS = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
PROJECT_WIN = r"C:\Users\yahya\Desktop\Foto\pc-analyser"
DIST_WIN = rf"{PROJECT_WIN}\dist\pc-analyser"
EXE_WIN = rf"{DIST_WIN}\pc-analyser.exe"
DESKTOP = r"C:\Users\yahya\Desktop"
SHORTCUT = rf"{DESKTOP}\PC Analyser.lnk"


def ps(cmd: str, timeout: int = 120) -> tuple[int, str, str]:
    r = subprocess.run(
        [PS, "-NoProfile", "-NonInteractive", "-Command", cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def step(msg: str):
    print(f"\n\033[1;36m==> {msg}\033[0m")


def ok(msg: str):
    print(f"  \033[32m✓ {msg}\033[0m")


def err(msg: str):
    print(f"  \033[31m✗ {msg}\033[0m")


def main():
    # ── Step 1: Check Windows Python ─────────────────────────────────────────
    step("Checking Windows Python installation")
    rc, out, _ = ps("python --version")
    if rc != 0 or "Python" not in out:
        err("Python not found on Windows.")
        print("\n  Install Python from https://www.python.org/downloads/")
        print("  Make sure to check 'Add Python to PATH' during install.")
        sys.exit(1)
    ok(f"Found {out}")

    # ── Step 2: Install dependencies + PyInstaller ────────────────────────────
    step("Installing dependencies on Windows Python")
    rc, out, stderr = ps(
        f"cd '{PROJECT_WIN}'; "
        f"python -m pip install -q psutil py-cpuinfo GPUtil click rich "
        f"flask flask-socketio requests pyinstaller",
        timeout=180,
    )
    if rc != 0:
        err(f"pip install failed: {stderr}")
        sys.exit(1)
    ok("Dependencies installed")

    # ── Step 3: Build exe ─────────────────────────────────────────────────────
    step("Building pc-analyser.exe with PyInstaller")

    # Write a minimal spec / use CLI flags
    build_cmd = (
        f"cd '{PROJECT_WIN}'; "
        f"python -m PyInstaller "
        f"--onedir "
        f"--console "
        f"--name pc-analyser "
        f"--distpath dist "
        f"--workpath build "
        f"--noconfirm "
        f"--add-data 'pc_analyser/web/templates;pc_analyser/web/templates' "
        f"--add-data 'pc_analyser/web/static;pc_analyser/web/static' "
        f"--hidden-import=pc_analyser "
        f"--hidden-import=pc_analyser.collectors "
        f"--hidden-import=flask_socketio "
        f"--hidden-import=engineio "
        f"--hidden-import=socketio "
        f"pc_analyser/cli.py"
    )
    rc, out, stderr = ps(build_cmd, timeout=300)
    if rc != 0:
        err("PyInstaller build failed")
        print(stderr[-2000:])
        sys.exit(1)

    # Verify exe exists
    rc2, exists, _ = ps(f"Test-Path '{EXE_WIN}'")
    if exists.lower() != "true":
        err(f"exe not found at {EXE_WIN}")
        sys.exit(1)
    ok(f"Built: {EXE_WIN}")

    # ── Step 4: Create desktop shortcut ───────────────────────────────────────
    step("Creating Desktop shortcut")

    shortcut_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{SHORTCUT}')
$Shortcut.TargetPath = '{EXE_WIN}'
$Shortcut.WorkingDirectory = '{DIST_WIN}'
$Shortcut.Description = 'PC Analyser - Hardware Monitor'
$Shortcut.IconLocation = '{EXE_WIN},0'
$Shortcut.Save()
"""
    rc, out, stderr = ps(shortcut_script)
    if rc != 0:
        err(f"Shortcut creation failed: {stderr}")
    else:
        ok(f"Shortcut created: {SHORTCUT}")

    # ── Done ──────────────────────────────────────────────────────────────────
    print(f"""
\033[1;32m
  Build complete!
  ─────────────────────────────────────────────
  Exe:       {EXE_WIN}
  Shortcut:  {SHORTCUT}

  Double-click "PC Analyser" on your Desktop to launch.
\033[0m""")


if __name__ == "__main__":
    main()
