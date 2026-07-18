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
    """Get GPU info + live load % from Windows WMI."""
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
