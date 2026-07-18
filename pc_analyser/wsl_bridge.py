"""WSL bridge — call Windows PowerShell/WMI from WSL to get real hardware data."""

import json
import os
import subprocess
import platform

_POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
_IS_WSL = None


def is_wsl() -> bool:
    """Detect if running inside WSL."""
    global _IS_WSL
    if _IS_WSL is not None:
        return _IS_WSL
    if platform.system() != "Linux":
        _IS_WSL = False
        return _IS_WSL
    try:
        with open("/proc/version") as f:
            content = f.read().lower()
            _IS_WSL = "microsoft" in content or "wsl" in content
    except OSError:
        _IS_WSL = False
    return _IS_WSL


def powershell(command: str, timeout: int = 8):
    """
    Run a PowerShell command via WSL bridge and return parsed JSON.
    Returns None on failure.
    """
    if not is_wsl():
        return None
    if not os.path.exists(_POWERSHELL):
        return None
    try:
        result = subprocess.run(
            [_POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        if not output:
            return None
        return json.loads(output)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        return None


def get_gpu_info() -> list[dict]:
    """Get GPU info from Windows WMI via PowerShell."""
    data = powershell(
        "Get-WmiObject Win32_VideoController | "
        "Select-Object Name,AdapterRAM,DriverVersion,VideoProcessor | "
        "ConvertTo-Json"
    )
    if data is None:
        return []
    if isinstance(data, dict):
        data = [data]
    result = []
    for i, g in enumerate(data):
        vram_mb = None
        ram = g.get("AdapterRAM")
        if ram and int(ram) > 0:
            vram_mb = round(int(ram) / 1024 ** 2, 0)
        result.append({
            "id": i,
            "name": g.get("Name") or "Unknown GPU",
            "driver": g.get("DriverVersion"),
            "vram_total_mb": vram_mb,
            "vram_used_mb": None,
            "vram_free_mb": None,
            "load_percent": None,
            "temperature_c": None,
            "fan_speed_percent": None,
            "vendor": _guess_vendor(g.get("Name", "")),
        })
    return result


def get_ram_info() -> dict:
    """Get RAM speed and slot info from Windows WMI via PowerShell."""
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
    """Get motherboard and BIOS info from Windows WMI via PowerShell."""
    board = powershell(
        "Get-WmiObject Win32_BaseBoard | "
        "Select-Object Manufacturer,Product,Version,SerialNumber | "
        "ConvertTo-Json"
    )
    bios = powershell(
        "Get-WmiObject Win32_BIOS | "
        "Select-Object Manufacturer,SMBIOSBIOSVersion,ReleaseDate | "
        "ConvertTo-Json"
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


def get_cpu_cache() -> dict:
    """Get accurate CPU cache sizes via lscpu (works in WSL)."""
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
    """Parse '4 MiB (8 instances)' -> KB."""
    try:
        val = line.split(":")[1].strip().split()[0]
        unit = line.split(":")[1].strip().split()[1].upper()
        num = float(val)
        if "MIB" in unit or "MB" in unit:
            return int(num * 1024)
        if "GIB" in unit or "GB" in unit:
            return int(num * 1024 * 1024)
        return int(num)
    except Exception:
        return 0


def _guess_vendor(name: str) -> str:
    name_lower = name.lower()
    if "amd" in name_lower or "radeon" in name_lower:
        return "AMD"
    if "nvidia" in name_lower or "geforce" in name_lower or "quadro" in name_lower:
        return "NVIDIA"
    if "intel" in name_lower:
        return "Intel"
    return "Unknown"
