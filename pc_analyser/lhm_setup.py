"""
LibreHardwareMonitor setup helper.

Downloads, installs, and launches LHM on Windows (from WSL via PowerShell).
LHM is required for CPU/GPU temperatures and fan RPM data.
"""

import os
import time
from .wsl_bridge import powershell, powershell_raw, is_wsl, get_temperatures_and_fans

LHM_VERSION = "v0.9.6"
LHM_ZIP_URL = (
    "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor"
    "/releases/download/v0.9.6/LibreHardwareMonitor.NET.10.zip"
)
LHM_INSTALL_DIR = r"$env:APPDATA\LibreHardwareMonitor"
LHM_EXE = r"$env:APPDATA\LibreHardwareMonitor\LibreHardwareMonitor.exe"
LHM_ZIP_PATH = r"$env:TEMP\LibreHardwareMonitor.zip"


def is_lhm_installed() -> bool:
    """Check if LHM exe exists in AppData."""
    result = powershell_raw(f"Test-Path {LHM_EXE}")
    return result.strip().lower() == "true"


def is_lhm_running() -> bool:
    """Check if LHM process is currently running."""
    result = powershell_raw(
        "Get-Process -Name LibreHardwareMonitor -ErrorAction SilentlyContinue | "
        "Select-Object -First 1 -ExpandProperty Id"
    )
    return bool(result.strip())


def is_wmi_active() -> bool:
    """Check if LHM WMI namespace is actually responding."""
    data = get_temperatures_and_fans()
    return data.get("lhm_available", False)


def download_and_install() -> tuple[bool, str]:
    """
    Download LHM zip and extract to AppData.
    Returns (success, message).
    """
    # Download
    ok = powershell_raw(
        f"Invoke-WebRequest -Uri '{LHM_ZIP_URL}' "
        f"-OutFile {LHM_ZIP_PATH} -UseBasicParsing"
    )
    if not is_lhm_installed():
        # Extract
        powershell_raw(
            f"Expand-Archive -Path {LHM_ZIP_PATH} "
            f"-DestinationPath {LHM_INSTALL_DIR} -Force"
        )

    if not is_lhm_installed():
        return False, "Download or extraction failed."
    return True, f"LHM {LHM_VERSION} installed to %APPDATA%\\LibreHardwareMonitor"


def launch_lhm() -> tuple[bool, str]:
    """Launch LHM as Administrator (required for sensor access)."""
    powershell_raw(
        f"Start-Process -FilePath {LHM_EXE} "
        f"-Verb RunAs -WindowStyle Minimized"
    )
    # Wait up to 10s for WMI to become active
    for _ in range(10):
        time.sleep(1)
        if is_wmi_active():
            return True, "LHM is running and WMI is active."
    return False, (
        "LHM launched but WMI not yet active.\n"
        "  In LibreHardwareMonitor: Options → Enable WMI"
    )


def enable_wmi_registry() -> None:
    """
    Write LHM config to enable WMI on next launch via registry/config file.
    LHM stores settings in AppData — we patch them if present.
    """
    powershell_raw(r"""
$cfg = "$env:APPDATA\LibreHardwareMonitor\LibreHardwareMonitor.config"
if (Test-Path $cfg) {
    $xml = [xml](Get-Content $cfg)
    $wmi = $xml.SelectSingleNode("//setting[@name='wmiProvider']")
    if ($wmi) { $wmi.value = 'True' }
    else {
        $s = $xml.CreateElement('setting')
        $s.SetAttribute('name','wmiProvider')
        $s.SetAttribute('serializeAs','String')
        $v = $xml.CreateElement('value')
        $v.InnerText = 'True'
        $s.AppendChild($v) | Out-Null
        $xml.DocumentElement.AppendChild($s) | Out-Null
    }
    $xml.Save($cfg)
}
""")


def setup_lhm(console=None) -> bool:
    """
    Full setup flow: check → download → install → launch → verify.
    Uses Rich console for output if provided, else prints plainly.
    Returns True if LHM is running and WMI is active.
    """
    def _print(msg, style=""):
        if console:
            console.print(msg)
        else:
            print(msg)

    if not is_wsl():
        _print("[yellow]LHM setup is only needed when running in WSL.[/yellow]")
        return False

    _print("\n[bold cyan]LibreHardwareMonitor Setup[/bold cyan]")
    _print("[dim]LHM provides CPU/GPU temperatures and fan RPM data.[/dim]\n")

    # Step 1 — check if already running
    if is_wmi_active():
        _print("[green]LHM is already running and WMI is active.[/green]")
        return True

    # Step 2 — check if installed but not running
    if is_lhm_installed():
        _print("[yellow]LHM is installed but not running.[/yellow]")
        _print("Launching LHM (requires Administrator approval)...")
        ok, msg = launch_lhm()
        _print(f"{'[green]' if ok else '[yellow]'}{msg}{'[/green]' if ok else '[/yellow]'}")
        if not ok:
            _print(_wmi_manual_instructions())
        return ok

    # Step 3 — download and install
    _print(f"Downloading LibreHardwareMonitor {LHM_VERSION}...")
    ok, msg = download_and_install()
    if not ok:
        _print(f"[red]{msg}[/red]")
        _print(_wmi_manual_instructions())
        return False
    _print(f"[green]{msg}[/green]")

    # Step 4 — patch config to enable WMI
    enable_wmi_registry()

    # Step 5 — launch
    _print("Launching LHM (a UAC prompt may appear — click Yes)...")
    ok, msg = launch_lhm()
    _print(f"{'[green]' if ok else '[yellow]'}{msg}{'[/green]' if ok else '[/yellow]'}")

    if not ok:
        _print(_wmi_manual_instructions())

    return ok


def _wmi_manual_instructions() -> str:
    return (
        "\n[dim]To enable manually:[/dim]\n"
        "  1. Open LibreHardwareMonitor on Windows\n"
        "  2. Go to [bold]Options → WMI[/bold] and check [bold]Enable WMI[/bold]\n"
        "  3. Re-run [bold]pc-analyser[/bold]\n"
        "  LHM download: [link=https://github.com/LibreHardwareMonitor/"
        "LibreHardwareMonitor/releases]github.com/LibreHardwareMonitor[/link]\n"
    )
