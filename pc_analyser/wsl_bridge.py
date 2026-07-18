"""WSL bridge — call Windows PowerShell/WMI from WSL to get real hardware data."""

import json
import os
import subprocess
import platform

_POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
_IS_WSL = None


def is_wsl() -> bool:
    global _IS_WSL
    if _IS_WSL is not None:
        return _IS_WSL
    if platform.system() != "Linux":
        _IS_WSL = False
        return _IS_WSL
    try:
        with open("/proc/version") as f:
            _IS_WSL = "microsoft" in f.read().lower()
    except OSError:
        _IS_WSL = False
    return _IS_WSL


def powershell(command: str, timeout: int = 8):
    """Run PowerShell and return parsed JSON, or None on failure."""
    if not is_wsl() or not os.path.exists(_POWERSHELL):
        return None
    try:
        result = subprocess.run(
            [_POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout.strip()
        if not output:
            return None
        return json.loads(output)
    except Exception:
        return None


def powershell_raw(command: str, timeout: int = 15) -> str:
    """Run PowerShell and return raw string output."""
    if not is_wsl() or not os.path.exists(_POWERSHELL):
        return ""
    try:
        result = subprocess.run(
            [_POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_gpu_info() -> list[dict]:
    data = powershell(
        "Get-WmiObject Win32_VideoController | "
        "Select-Object Name,AdapterRAM,DriverVersion,"
        "CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate | "
        "ConvertTo-Json"
    )
    if data is None:
        return []
    if isinstance(data, dict):
        data = [data]

    load_pct = _get_gpu_load()

    result = []
    for i, g in enumerate(data):
        vram_mb = None
        ram = g.get("AdapterRAM")
        if ram and int(ram) > 0:
            vram_mb = round(int(ram) / 1024 ** 2, 0)
        res = g.get("CurrentHorizontalResolution")
        resolution = (
            f"{res}x{g.get('CurrentVerticalResolution')} @ {g.get('CurrentRefreshRate')}Hz"
            if res else None
        )
        result.append({
            "id": i,
            "name": g.get("Name") or "Unknown GPU",
            "driver": g.get("DriverVersion"),
            "vram_total_mb": vram_mb,
            "vram_used_mb": None,
            "vram_free_mb": None,
            "load_percent": load_pct,
            "temperature_c": None,
            "fan_speed_percent": None,
            "vendor": _guess_vendor(g.get("Name", "")),
            "resolution": resolution,
        })
    return result


def _get_gpu_load() -> float | None:
    """Get GPU 3D engine utilisation % via WMI performance counters."""
    data = powershell(
        "Get-WmiObject -Namespace root/cimv2 "
        "-Class Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine "
        "-ErrorAction SilentlyContinue | "
        "Where-Object { $_.Name -like '*engtype_3D*' } | "
        "Measure-Object -Property UtilizationPercentage -Sum | "
        "Select-Object Sum | ConvertTo-Json",
        timeout=6,
    )
    if data and data.get("Sum") is not None:
        return float(data["Sum"])
    return None


def get_ram_info() -> dict:
    """Get RAM speed, type, and slot info from WMI."""
    data = powershell(
        "Get-WmiObject Win32_PhysicalMemory | "
        "Select-Object Speed,MemoryType,Capacity,Manufacturer,PartNumber,DeviceLocator | "
        "ConvertTo-Json"
    )
    if data is None:
        return {}
    if isinstance(data, dict):
        data = [data]

    mem_type_map = {
        20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM",
        24: "DDR3", 26: "DDR4", 34: "DDR5",
    }
    sticks = []
    for s in data:
        cap = s.get("Capacity")
        mem_type_code = int(s.get("MemoryType") or 0)
        sticks.append({
            "slot": s.get("DeviceLocator") or "Unknown",
            "size_gb": round(int(cap) / 1024 ** 3, 2) if cap else None,
            "speed_mhz": s.get("Speed"),
            "type": mem_type_map.get(mem_type_code, "DDR4"),
            "manufacturer": (s.get("Manufacturer") or "").strip(),
            "part_number": (s.get("PartNumber") or "").strip(),
        })

    speeds = [s["speed_mhz"] for s in sticks if s.get("speed_mhz")]
    types = [s["type"] for s in sticks if s.get("type")]
    return {
        "sticks": sticks,
        "slots_used": len(sticks),
        "slots_total": None,
        "speed_mhz": speeds[0] if speeds else None,
        "type": types[0] if types else None,
    }


def get_motherboard_info() -> dict:
    """Get motherboard and BIOS info from WMI."""
    board = powershell(
        "Get-WmiObject Win32_BaseBoard | "
        "Select-Object Manufacturer,Product,Version,SerialNumber | ConvertTo-Json"
    )
    bios = powershell(
        "Get-WmiObject Win32_BIOS | "
        "Select-Object Manufacturer,SMBIOSBIOSVersion,ReleaseDate | ConvertTo-Json"
    )
    result = {}
    if board:
        if isinstance(board, list):
            board = board[0]
        result["manufacturer"] = (board.get("Manufacturer") or "").strip() or None
        result["product"] = (board.get("Product") or "").strip() or None
        result["version"] = (board.get("Version") or "").strip() or None
        result["serial"] = (board.get("SerialNumber") or "").strip() or None
    if bios:
        if isinstance(bios, list):
            bios = bios[0]
        result["bios_vendor"] = (bios.get("Manufacturer") or "").strip() or None
        result["bios_version"] = (bios.get("SMBIOSBIOSVersion") or "").strip() or None
        date = bios.get("ReleaseDate") or ""
        result["bios_date"] = date[:8] if date else None
    return result


def get_temperatures_and_fans() -> dict:
    """
    Get temperatures and fan RPMs from LibreHardwareMonitor WMI bridge.
    LHM must be running with WMI enabled for this to work.
    Returns lhm_available=False if not running.
    """
    result = {
        "temperatures": {},
        "fans": {},
        "cpu_temp_c": None,
        "lhm_available": False,
    }

    data = powershell(
        "Get-WmiObject -Namespace root/LibreHardwareMonitor -Class Sensor "
        "-ErrorAction SilentlyContinue | "
        "Select-Object Name,Value,SensorType,Parent | ConvertTo-Json",
        timeout=6,
    )
    if not data:
        return result

    if isinstance(data, dict):
        data = [data]

    result["lhm_available"] = True

    for s in data:
        name = s.get("Name") or "Unknown"
        value = s.get("Value")
        sensor_type = s.get("SensorType") or ""
        parent = s.get("Parent") or "LHM"

        if value is None:
            continue
        try:
            value = float(value)
        except (ValueError, TypeError):
            continue

        if sensor_type == "Temperature":
            if parent not in result["temperatures"]:
                result["temperatures"][parent] = []
            result["temperatures"][parent].append({
                "label": name,
                "current_c": round(value, 1),
                "high_c": None,
                "critical_c": None,
            })
            if "cpu" in name.lower() and result["cpu_temp_c"] is None:
                result["cpu_temp_c"] = round(value, 1)

        elif sensor_type == "Fan":
            if parent not in result["fans"]:
                result["fans"][parent] = []
            result["fans"][parent].append({
                "label": name,
                "rpm": int(value),
            })

    # Derive cpu_temp_c from parent averages if not found by name
    if result["cpu_temp_c"] is None:
        for parent, entries in result["temperatures"].items():
            if any(k in parent.lower() for k in ("cpu", "ryzen", "core", "amd")):
                vals = [e["current_c"] for e in entries if e["current_c"] is not None]
                if vals:
                    result["cpu_temp_c"] = round(sum(vals) / len(vals), 1)
                    break

    return result


def get_cpu_cache() -> dict:
    """Get accurate CPU cache sizes via lscpu."""
    try:
        out = subprocess.check_output(["lscpu"], text=True, timeout=5)
        result = {}
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("L2 cache:"):
                result["cache_l2_kb"] = _parse_lscpu_cache(line)
            elif line.startswith("L3 cache:"):
                result["cache_l3_kb"] = _parse_lscpu_cache(line)
        return result
    except Exception:
        return {}


def _parse_lscpu_cache(line: str) -> int:
    try:
        parts = line.split(":")[1].strip().split()
        num = float(parts[0])
        unit = parts[1].upper() if len(parts) > 1 else "KB"
        if "MIB" in unit or "MB" in unit:
            return int(num * 1024)
        if "GIB" in unit or "GB" in unit:
            return int(num * 1024 * 1024)
        return int(num)
    except Exception:
        return 0


def _guess_vendor(name: str) -> str:
    n = name.lower()
    if "amd" in n or "radeon" in n:
        return "AMD"
    if "nvidia" in n or "geforce" in n or "quadro" in n:
        return "NVIDIA"
    if "intel" in n:
        return "Intel"
    return "Unknown"


def get_os_info() -> dict:
    """Get detailed Windows OS information."""
    reg = powershell(
        "Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion' | "
        "Select-Object ProductName,DisplayVersion,ReleaseId,InstallDate,"
        "RegisteredOwner,CurrentBuildNumber,UBR | ConvertTo-Json"
    )
    os_info = powershell(
        "Get-WmiObject Win32_OperatingSystem | "
        "Select-Object Caption,Version,OSArchitecture,SerialNumber,"
        "InstallDate,LastBootUpTime,NumberOfUsers | ConvertTo-Json"
    )
    comp = powershell(
        "Get-WmiObject Win32_ComputerSystem | "
        "Select-Object Name,Model,Manufacturer,SystemType | ConvertTo-Json"
    )
    result = {}
    if reg:
        result.update({
            "os_name": reg.get("ProductName"),
            "os_version": reg.get("DisplayVersion"),
            "os_release_id": reg.get("ReleaseId"),
            "os_build": reg.get("CurrentBuildNumber"),
            "os_ubr": reg.get("UBR"),
            "registered_owner": reg.get("RegisteredOwner"),
        })
    if os_info:
        result.update({
            "os_caption": os_info.get("Caption"),
            "os_architecture": os_info.get("OSArchitecture"),
            "product_id": os_info.get("SerialNumber"),
        })
    if comp:
        result.update({
            "hostname": comp.get("Name"),
            "computer_model": comp.get("Model"),
            "computer_manufacturer": comp.get("Manufacturer"),
            "system_type": comp.get("SystemType"),
        })
    # Last update times
    upd = powershell(
        "try { "
        "$wu = New-Object -ComObject Microsoft.Update.AutoUpdate; "
        "$r = $wu.Results; "
        "[PSCustomObject]@{ LastInstall=$r.LastInstallationSuccessDate; LastSearch=$r.LastSearchSuccessDate } | ConvertTo-Json "
        "} catch { '{\"LastInstall\":null,\"LastSearch\":null}' | ConvertTo-Json }"
    )
    if upd:
        result["last_update_install"] = upd.get("LastInstall")
        result["last_update_search"] = upd.get("LastSearch")
    # Secure Boot
    sb = powershell_raw("try { (Confirm-SecureBootUEFI) } catch { 'Unknown' }")
    result["secure_boot"] = sb.strip() if sb else "Unknown"
    # SMBIOS
    bios = powershell(
        "Get-WmiObject Win32_BIOS | "
        "Select-Object SMBIOSMajorVersion,SMBIOSMinorVersion | ConvertTo-Json"
    )
    if bios:
        result["smbios"] = f"{bios.get('SMBIOSMajorVersion')}.{bios.get('SMBIOSMinorVersion')}"
    return result


def get_disk_info() -> list[dict]:
    """Get physical disk details including type, bus, serial, firmware."""
    disks = powershell(
        "Get-PhysicalDisk | "
        "Select-Object FriendlyName,MediaType,BusType,SerialNumber,"
        "FirmwareVersion,Size,HealthStatus,OperationalStatus | ConvertTo-Json"
    )
    wmi_disks = powershell(
        "Get-WmiObject Win32_DiskDrive | "
        "Select-Object Model,MediaType,InterfaceType,SerialNumber,"
        "FirmwareRevision,Size,Index | ConvertTo-Json"
    )
    # Volume letter mapping
    vols = powershell(
        "Get-Partition | Where-Object { $_.DriveLetter } | "
        "Select-Object DiskNumber,DriveLetter,Size | ConvertTo-Json"
    )

    bus_map = {
        7: "USB", 11: "SATA", 17: "NVMe", 3: "SCSI", 4: "IDE", 0: "Unknown"
    }
    health_map = {0: "Healthy", 1: "Warning", 2: "Unhealthy", 5: "Unknown"}

    result = []
    raw = disks if isinstance(disks, list) else ([disks] if disks else [])

    vol_map = {}
    if vols:
        vol_list = vols if isinstance(vols, list) else [vols]
        for v in vol_list:
            dn = v.get("DiskNumber")
            dl = v.get("DriveLetter")
            if dn is not None and dl:
                vol_map.setdefault(dn, []).append(dl)

    wmi_list = wmi_disks if isinstance(wmi_disks, list) else ([wmi_disks] if wmi_disks else [])
    wmi_by_model = {d.get("Model", "").strip(): d for d in wmi_list if d}

    for i, d in enumerate(raw):
        if not d or not d.get("FriendlyName"):
            continue
        bus_code = d.get("BusType", 0)
        bus_str = bus_map.get(bus_code, f"Bus {bus_code}")
        size_bytes = d.get("Size") or 0
        size_gb = round(size_bytes / 1024 ** 3, 1) if size_bytes else None

        wmi = wmi_by_model.get(d.get("FriendlyName", ""), {})
        media = d.get("MediaType") or wmi.get("MediaType") or "Unknown"
        media_clean = {"SSD": "Solid State Drive", "HDD": "Hard Disk Drive",
                       "SCM": "Storage Class Memory"}.get(media, media)

        result.append({
            "index": i,
            "model": d.get("FriendlyName"),
            "media_type": media_clean,
            "bus_type": bus_str,
            "serial": (d.get("SerialNumber") or "").strip().rstrip("."),
            "firmware": d.get("FirmwareVersion") or wmi.get("FirmwareRevision"),
            "size_gb": size_gb,
            "health": health_map.get(d.get("HealthStatus", 5), "Unknown"),
            "volumes": vol_map.get(i, []),
            # SMART filled in separately
            "smart_temp_c": None,
            "smart_power_on_hours": None,
            "smart_wear_percent": None,
            "smart_data_read_gb": None,
            "smart_data_written_gb": None,
            "smart_reallocated": None,
        })

    return result


def get_disk_smart_windows(disk_index: int) -> dict:
    """
    Get SMART data for a Windows physical disk using smartmontools on Windows.
    Requires smartctl.exe to be installed on Windows.
    Falls back to basic WMI data.
    """
    smartctl_paths = [
        r"C:\Program Files\smartmontools\bin\smartctl.exe",
        r"C:\Program Files (x86)\smartmontools\bin\smartctl.exe",
    ]
    smartctl = None
    for p in smartctl_paths:
        check = powershell_raw(f"Test-Path '{p}'")
        if check.strip().lower() == "true":
            smartctl = p
            break

    if not smartctl:
        return {}

    out = powershell_raw(
        f"& '{smartctl}' -A -H /dev/pd{disk_index} 2>&1",
        timeout=10,
    )
    result = {}
    for line in out.splitlines():
        ll = line.lower()
        if "temperature_celsius" in ll or "temperature" in ll and "celsius" in ll:
            result["smart_temp_c"] = _extract_smart_val_str(line)
        if "power_on_hours" in ll:
            result["smart_power_on_hours"] = _extract_smart_val_str(line)
        if "wear_leveling" in ll or "percent_lifetime" in ll:
            v = _extract_smart_val_str(line)
            if v is not None:
                result["smart_wear_percent"] = 100 - v if "percent_lifetime" in ll else v
        if "reallocated_sector" in ll:
            result["smart_reallocated"] = _extract_smart_val_str(line)
        if "data_units_read" in ll:
            v = _extract_smart_val_str(line)
            if v:
                result["smart_data_read_gb"] = round(v * 512000 / 1024 ** 3, 1)
        if "data_units_written" in ll:
            v = _extract_smart_val_str(line)
            if v:
                result["smart_data_written_gb"] = round(v * 512000 / 1024 ** 3, 1)
        # NVMe health
        if "smart overall-health" in ll or "nvme smart" in ll:
            result["smart_health"] = "PASSED" if "passed" in ll or "ok" in ll else "FAILED"
    return result


def _extract_smart_val_str(line: str):
    parts = line.split()
    for p in reversed(parts):
        try:
            v = int(p.split("+")[0].split("h")[0].split(",")[0])
            if 0 <= v < 10_000_000:
                return v
        except ValueError:
            continue
    return None


def get_gpu_extended() -> list[dict]:
    """Get extended GPU info: VBIOS, WDDM, PCI location, GPU functions."""
    data = powershell(
        "Get-WmiObject Win32_VideoController | "
        "Select-Object Name,AdapterRAM,DriverVersion,PNPDeviceID,"
        "VideoProcessor,AdapterCompatibility,InstalledDisplayDrivers,"
        "CurrentHorizontalResolution,CurrentVerticalResolution,CurrentRefreshRate | "
        "ConvertTo-Json"
    )
    if not data:
        return []
    if isinstance(data, dict):
        data = [data]

    load_pct = _get_gpu_load()
    result = []
    for i, g in enumerate(data):
        pnp = g.get("PNPDeviceID", "")
        # Parse PCI bus/device/func from PNPDeviceID
        pci_loc = None
        if "PCI\\" in pnp:
            parts = pnp.split("\\")[-1].split("&")
            if parts:
                pci_loc = pnp.split("\\")[-1]

        vram = g.get("AdapterRAM") or 0
        vram_mb = round(int(vram) / 1024 ** 2) if vram and int(vram) > 0 else None
        # WMI caps VRAM at ~4GB — use 6144 for RX 5600 XT if we detect it
        if vram_mb and vram_mb >= 4094 and "5600" in (g.get("Name") or ""):
            vram_mb = 6144

        res = g.get("CurrentHorizontalResolution")
        resolution = (
            f"{res}x{g.get('CurrentVerticalResolution')} @ {g.get('CurrentRefreshRate')}Hz"
            if res else None
        )

        result.append({
            "id": i,
            "name": g.get("Name") or "Unknown",
            "vendor": g.get("AdapterCompatibility") or _guess_vendor(g.get("Name", "")),
            "driver": g.get("DriverVersion"),
            "video_processor": g.get("VideoProcessor"),
            "vram_total_mb": vram_mb,
            "vram_used_mb": None,
            "vram_free_mb": None,
            "load_percent": load_pct,
            "temperature_c": None,
            "fan_speed_percent": None,
            "core_clock_mhz": None,
            "mem_clock_mhz": None,
            "power_draw_w": None,
            "junction_temp_c": None,
            "pci_location": pci_loc,
            "resolution": resolution,
        })
    return result


def install_smartmontools_windows() -> tuple[bool, str]:
    """Download and install smartmontools on Windows silently."""
    # Check if already installed
    for p in [r"C:\Program Files\smartmontools\bin\smartctl.exe",
              r"C:\Program Files (x86)\smartmontools\bin\smartctl.exe"]:
        if powershell_raw(f"Test-Path '{p}'").strip().lower() == "true":
            return True, f"Already installed at {p}"

    # Try winget first
    out = powershell_raw(
        "winget install --id=smartmontools.smartmontools --silent --accept-package-agreements "
        "--accept-source-agreements 2>&1",
        timeout=120,
    )
    if "successfully installed" in out.lower():
        return True, "Installed via winget"

    # Fallback: direct download
    url = "https://builds.smartmontools.org/win32/smartmontools-7.5-1.win32-setup.exe"
    installer = r"$env:TEMP\smartmontools-setup.exe"
    dl = powershell_raw(
        f"Invoke-WebRequest -Uri '{url}' -OutFile {installer} -UseBasicParsing; "
        f"Start-Process -FilePath {installer} -Args '/S' -Wait -Verb RunAs",
        timeout=120,
    )
    for p in [r"C:\Program Files\smartmontools\bin\smartctl.exe",
              r"C:\Program Files (x86)\smartmontools\bin\smartctl.exe"]:
        if powershell_raw(f"Test-Path '{p}'").strip().lower() == "true":
            return True, "Installed via direct download"

    return False, "Installation failed. Install manually from https://www.smartmontools.org"
